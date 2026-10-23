#!/usr/bin/env python3
"""Prepare or update Ruurd/lad with expanded BG + TG Gumbel decoding."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SPACE_ID = "Ruurd/lad"


def make_space_bundle(destination: Path, checkpoint: Path = ROOT / "artifacts/bigram/llama.pt"):
    """Bundle the existing LAD app and the shared scorer, without model weights."""
    if not checkpoint.is_file():
        raise FileNotFoundError(f"Build the Llama-tokenized scorer first: {checkpoint}")
    destination.mkdir(parents=True, exist_ok=True)
    source = ROOT / "huggingface/lad_space"
    for path in source.iterdir():
        if path.is_file():
            shutil.copy2(path, destination / path.name)
    package = destination / "src/diffusion_lm"
    package.mkdir(parents=True, exist_ok=True)
    for name in ("__init__.py", "bigram.py", "trigram.py", "repetition_risk.py", "repetition_schedule.py"):
        shutil.copy2(ROOT / "src/diffusion_lm" / name, package / name)
    shutil.copy2(checkpoint, destination / "bigram.pt")
    if checkpoint.with_suffix(".json").is_file():
        shutil.copy2(checkpoint.with_suffix(".json"), destination / "bigram.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/bigram/lad_space/bundle")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--expected-revision", help="Reject publication if the Space changed after review")
    args = parser.parse_args()
    make_space_bundle(args.output)
    if not args.execute:
        print(json.dumps(dict(space=SPACE_ID, bundle=str(args.output), execute=False)))
        return

    from dotenv import load_dotenv
    from huggingface_hub import HfApi
    load_dotenv(ROOT / ".env")
    api = HfApi()
    if api.whoami()["name"].casefold() != "ruurd":
        raise RuntimeError("Updating LAD requires the Ruurd account")
    info = api.repo_info(SPACE_ID, repo_type="space")
    if args.expected_revision and info.sha != args.expected_revision:
        raise RuntimeError("The LAD Space changed since review; inspect its latest source before updating")
    commit = api.upload_folder(
        repo_id=SPACE_ID, repo_type="space", folder_path=str(args.output),
        parent_commit=info.sha,
        commit_message="Update LAD decoding options and default settings",
        ignore_patterns=["__pycache__/*", "*.pyc"],
    )
    record = dict(space=SPACE_ID, parent_revision=info.sha, revision=commit.oid,
                  private=info.private, bundle=str(args.output))
    (args.output.parent / "deployment.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
