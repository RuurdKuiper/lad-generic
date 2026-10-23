#!/usr/bin/env python3
"""Publish only the tested trigram scorer/traceback optimization to Ruurd LLaDA."""

import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/bigram/llada_ngram_speed"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute", action="store_true")
    p.add_argument("--variant", choices=["initial", "host"], default="initial")
    args = p.parse_args()
    from dotenv import load_dotenv
    from huggingface_hub import HfApi, CommitOperationAdd

    load_dotenv(ROOT / ".env")
    api = HfApi(token=os.getenv("HF_TOKEN"))
    if api.whoami()["name"].casefold() != "ruurd":
        raise RuntimeError("Requires Ruurd account")
    suffix = "" if args.variant == "initial" else "_host"
    plan_path = OUT / ("deployment" + suffix + "_plan.json")
    if args.variant == "host" and not plan_path.exists():
        record = json.loads((OUT / "deployment.json").read_text())
        record["parent_revision"] = record.pop("revision")
    else:
        record = json.loads(plan_path.read_text())
    source = ROOT / "src/diffusion_lm/trigram.py"
    current = hashlib.sha256(source.read_bytes()).hexdigest()
    if (
        api.repo_info(record["space"], repo_type="space").sha
        != record["parent_revision"]
    ):
        raise RuntimeError("Space changed since baseline/preparation")
    if not args.execute:
        record.update(
            source=str(source),
            source_sha256=current,
            original_sha256=hashlib.sha256(
                (OUT / "trigram_remote_before.py").read_bytes()
            ).hexdigest(),
        )
        plan_path.write_text(json.dumps(record, indent=2) + "\n")
    else:
        if current != record.get("source_sha256"):
            raise RuntimeError("Prepared source changed")
        baseline = [
            json.loads(s) for s in (OUT / "before.jsonl").read_text().splitlines()
        ]
        if len(baseline) != 24:
            raise RuntimeError("Finish pre-change measurements first")
        commit = api.create_commit(
            repo_id=record["space"],
            repo_type="space",
            parent_commit=record["parent_revision"],
            operations=[
                CommitOperationAdd(
                    path_in_repo=record["path_in_repo"], path_or_fileobj=source
                )
            ],
            commit_message=(
                "Run small exact trigram MAP chains on CPU to reduce GPU launch overhead"
                if args.variant == "host"
                else "Speed up exact trigram scoring and avoid GPU scalar traceback synchronization"
            ),
        )
        record["revision"] = commit.oid
        (OUT / ("deployment" + suffix + ".json")).write_text(
            json.dumps(record, indent=2) + "\n"
        )
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
