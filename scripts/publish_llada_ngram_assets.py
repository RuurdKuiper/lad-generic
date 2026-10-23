#!/usr/bin/env python3
"""Publish trained scorer artifacts outside the Space's one-GB file limit."""

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "huggingface"))
from enable_llada_trigram import digest


def main():
    from dotenv import load_dotenv
    from huggingface_hub import HfApi

    load_dotenv(ROOT / ".env")
    api = HfApi()
    if api.whoami()["name"].casefold() != "ruurd":
        raise RuntimeError("Requires Ruurd account")
    out = ROOT / "artifacts/bigram/llada_expanded_ngrams"
    repo = "Ruurd/llada-ngram-guidance-877m"
    bundle = out / "model-bundle"
    bundle.mkdir(exist_ok=True)
    files = {
        "bigram_expanded.pt": out / "bigram_expanded.pt",
        "trigram_expanded.pt": out / "deployment-assets/trigram_expanded.pt",
    }
    assets = {}
    for name, source in files.items():
        target = bundle / name
        if target.exists():
            target.unlink()
        os.link(source, target)
        assets[name] = dict(sha256=digest(source), bytes=source.stat().st_size)
    (bundle / "training_report.json").write_text(
        (out / "training_report.json").read_text()
    )
    (bundle / "compaction.json").write_text((out / "compaction.json").read_text())
    (bundle / "README.md").write_text("""---
tags:
- n-gram
- llada
---
# LLaDA n-gram guidance statistics

Sparse bigram and trigram statistics for [Ruurd/llada-8b-instruct](https://huggingface.co/spaces/Ruurd/llada-8b-instruct).
No diffusion-model weights. Both scorers use the exact pinned LLaDA tokenizer and 877,064,287 tokens.
The added 800M tokens are 90% FineWeb-Edu, 5% Python-Edu and 5% FineMath, plus all original responses.

Sources: [FineWeb-Edu](https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu),
[Python-Edu text mirror](https://huggingface.co/datasets/Avelina/python-edu-cleaned),
[FineMath](https://huggingface.co/datasets/HuggingFaceTB/finemath).
Pinned revisions and file/document/token counts are in training_report.json.
Documents are counted separately without crossing boundaries.

All bigram counts are retained. Trigrams with count >=2 are retained; only singleton
trigrams are excluded. All required prefix totals include singleton contributions.
Runtime trigram minimum count is two, correction clip +/-2 and backoff strength 50.
Compaction is exact at thresholds >=2; lowering the threshold below two requires retraining/export from the full counts.
See the Space source for scorer loading, smoothing and second-order sequence decoding.
""")
    api.create_repo(repo, repo_type="model", private=False, exist_ok=True)
    commit = api.upload_folder(
        repo_id=repo,
        repo_type="model",
        folder_path=str(bundle),
        commit_message="Publish expanded bigram and count-two trigram statistics for LLaDA",
    )
    record = dict(repo=repo, revision=commit.oid, assets=assets)
    (out / "model_deployment.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
