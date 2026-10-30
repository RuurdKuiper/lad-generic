#!/usr/bin/env python3
"""Prepare the LLaDA2.2 Space and matching scorers; publish only with --execute."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "huggingface/llada22_space"))
from streaming import MODEL_ID, MODEL_REVISION

SPACE_ID = "Ruurd/llada2.2-mini"
SCORER_ID = "Ruurd/llada2.2-mini-ngram-guidance"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def prepare(destination):
    training = ROOT / "artifacts/llada22/ngrams"
    report = json.loads((training / "complete.json").read_text())
    if report["tokenizer"] != MODEL_ID or report["model_revision"] != MODEL_REVISION:
        raise ValueError("Scorer model/tokenizer revision mismatch")
    if report["new_tokens"] != 800_000_000:
        raise ValueError("Expected the full 800M-token expansion")
    responses = next(s for s in report["sources"] if s["name"] == "responses")
    if responses["documents"] != 980_000:
        raise ValueError("Expected all original training responses")
    destination.mkdir(parents=True, exist_ok=True)
    model_bundle = destination / "scorers"
    space_bundle = destination / "space"
    model_bundle.mkdir(exist_ok=True)
    space_bundle.mkdir(exist_ok=True)
    for cache in space_bundle.rglob("__pycache__"):
        shutil.rmtree(cache)
    for name, expected in report["assets"].items():
        source = training / name
        if digest(source) != expected["sha256"]:
            raise ValueError(f"Scorer checksum mismatch: {name}")
        target = model_bundle / name
        if target.exists():
            target.unlink()
        os.link(source, target)
    shutil.copy2(training / "complete.json", model_bundle / "training_report.json")
    (model_bundle / "README.md").write_text(f"""---
tags:
- n-gram
- diffusion
---
# LLaDA2.2-mini BG + TG statistics

Tokenizer-matched sparse counts for [{SPACE_ID}](https://huggingface.co/spaces/{SPACE_ID}).
Model/tokenizer: [{MODEL_ID}](https://huggingface.co/{MODEL_ID}), revision `{MODEL_REVISION}`.
Contains no model weights and no raw training documents.

{report['tokens']:,} tokens: all 980,000 original response-training documents plus
800M exact tokenizer-specific tokens (720M FineWeb-Edu, 40M Python-Edu, 40M FineMath).
Sources: [FineWeb-Edu](https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu),
[Python-Edu](https://huggingface.co/datasets/Avelina/python-edu-cleaned),
[FineMath](https://huggingface.co/datasets/HuggingFaceTB/finemath).
Source revisions/files, boundary/EOS policy, tokenizer fingerprint, counts and
SHA256 checksums are recorded in training_report.json. Documents are counted separately.

Bigram PMI: minimum count 1, clip ±2. Trigram correction: count>=2, alpha=50,
clip ±2. Prefix totals include singleton contributions; only prefixes needed
by retained trigrams are stored. Relative trigram weight is 0.5.
""")
    template = ROOT / "huggingface/llada22_space"
    for name in ("app.py", "streaming.py", "requirements.txt", "README.md"):
        shutil.copy2(template / name, space_bundle / name)
    (space_bundle / "space_model.json").write_text(json.dumps(dict(
        model_repo_id=MODEL_ID, model_revision=MODEL_REVISION,
        ngram_scorer_repo=SCORER_ID, ngram_scorer_revision=None,
        assets=report["assets"],
    ), indent=2) + "\n")
    src = space_bundle / "src/diffusion_lm"
    src.mkdir(parents=True, exist_ok=True)
    (src / "__init__.py").write_text("")
    for name in ("bigram.py", "trigram.py", "repetition_risk.py", "repetition_schedule.py"):
        shutil.copy2(ROOT / "src/diffusion_lm" / name, src / name)
    manifest = dict(space=SPACE_ID, scorers=SCORER_ID, model=MODEL_ID,
                    model_revision=MODEL_REVISION, tokens=report["tokens"],
                    assets=report["assets"],
                    source_hashes={str(p.relative_to(space_bundle)): digest(p)
                                   for p in space_bundle.rglob("*") if p.is_file()})
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/llada22/bundle")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--public", action="store_true", help="Publish both new repositories publicly")
    args = parser.parse_args()
    manifest = prepare(args.output)
    if not args.execute:
        print(json.dumps(manifest, indent=2))
        return
    from dotenv import load_dotenv
    from huggingface_hub import HfApi
    load_dotenv(ROOT / ".env")
    api = HfApi()
    if api.whoami()["name"].casefold() != "ruurd":
        raise RuntimeError("Publishing requires Ruurd's account")
    secrets = None
    if not args.public:
        read_token = os.getenv("HF_READ_TOKEN")
        if not read_token or HfApi(token=read_token).whoami()["auth"]["accessToken"]["role"] != "read":
            raise RuntimeError("Private scorer downloads require HF_READ_TOKEN with read-only access; no write credential is copied into the Space")
        secrets = [dict(key="HF_TOKEN", value=read_token)]
    # Validate all names before creating anything. Never touch the original demo.
    for repo, kind in ((SCORER_ID, "model"), (SPACE_ID, "space")):
        if api.repo_exists(repo, repo_type=kind):
            raise RuntimeError(f"Refusing to overwrite existing {kind}: {repo}")
    api.create_repo(SCORER_ID, repo_type="model", private=not args.public, exist_ok=False)
    commit = api.upload_folder(repo_id=SCORER_ID, repo_type="model",
                               folder_path=str(args.output / "scorers"),
                               commit_message="Publish tokenizer-matched LLaDA2.2 bigram/trigram statistics")
    # Record successful asset upload before creating the Space.
    record = dict(scorers=SCORER_ID, scorer_revision=commit.oid, public=args.public)
    (args.output.parent / "deployment.json").write_text(json.dumps(record, indent=2) + "\n")
    config_path = args.output / "space/space_model.json"
    config = json.loads(config_path.read_text())
    config["ngram_scorer_revision"] = commit.oid
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    api.create_repo(SPACE_ID, repo_type="space", space_sdk="gradio", private=not args.public,
                    exist_ok=False, space_hardware="zero-a10g", space_secrets=secrets)
    commit = api.upload_folder(repo_id=SPACE_ID, repo_type="space",
                               folder_path=str(args.output / "space"),
                               ignore_patterns=["**/__pycache__/**", "*.pyc"],
                               commit_message="Deploy LLaDA2.2-mini with native edits and BG + TG live visualization")
    record.update(space=SPACE_ID, space_revision=commit.oid, requested_hardware="zero-a10g")
    (args.output.parent / "deployment.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
