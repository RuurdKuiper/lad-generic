#!/usr/bin/env python3
"""Prepare/deploy the tunable APD aggressiveness to LLaDA."""

import argparse
import json
from pathlib import Path

from enable_repetition_penalty import ROOT, make_bundle

SPACE = "Ruurd/llada-8b-instruct"
OUT = ROOT / "artifacts/bigram/llada_apd_aggressiveness"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    from dotenv import load_dotenv
    from huggingface_hub import HfApi, hf_hub_download

    load_dotenv(ROOT / ".env")
    api = HfApi()
    if api.whoami()["name"].casefold() != "ruurd":
        raise RuntimeError("Requires Ruurd account")
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = OUT / "prepared.json"
    if args.execute:
        record = json.loads(manifest.read_text())
        if (
            record["space"] != SPACE
            or api.repo_info(SPACE, repo_type="space").sha != record["parent_revision"]
        ):
            raise RuntimeError("Space changed since preparation; review current source")
        commit = api.upload_folder(
            repo_id=SPACE,
            repo_type="space",
            folder_path=record["bundle"],
            parent_commit=record["parent_revision"],
            commit_message="Add adjustable APD commitment aggressiveness; preserve default behavior",
        )
        record["revision"] = commit.oid
        (OUT / "deployment.json").write_text(json.dumps(record, indent=2) + "\n")
    else:
        revision = api.repo_info(SPACE, repo_type="space").sha

        def read(name):
            return Path(
                hf_hub_download(
                    SPACE, name, repo_type="space", revision=revision, token=api.token
                )
            ).read_text()

        config = json.loads(read("space_model.json"))
        if config.get("model_backend") != "llada" or not config.get("bigram_enabled"):
            raise RuntimeError("Unexpected Space configuration")
        bundle = OUT / "bundle"
        readme = read("README.md") + """

## Tunable APD aggressiveness

With **Adaptive Parallel Decoding (APD)** ON, **APD aggressiveness** ranges from
0 to 1 and defaults to 0. The original warmup/cosine threshold schedule is
multiplied by (1-a). Thus a=0 retains 0.90 to 0.50, a=0.5 gives 0.45 to 0.25,
a=0.9 gives 0.09 to 0.05, and a=1 gives zero threshold, committing all finite
selected-token predictions in one forward per block. Higher values can reduce
passes but may reduce generation quality by locking less-confident predictions.

The control is interactive only while APD is enabled. API parameter is
apd_aggressiveness, default 0. APD OFF ignores it. The zero default reproduces
existing APD paths, thresholds and status text. Selected-token confidence stays
full-vocabulary and untempered, including when Viterbi selects a non-argmax token.
Progress fallback, final cleanup, MASK validity fallback, fixed positions, ending
retention delay, and early block exit remain unchanged. No extra model forwards.

Works with all existing decoding strategies, sequence sampling, repetition-risk
penalties and their fade. It changes commitment only. Repetition fading and all
other settings remain unchanged. Only this LLaDA Space was updated.
"""
        make_bundle(bundle, config, readme, apd=True)
        record = dict(space=SPACE, parent_revision=revision, bundle=str(bundle))
        manifest.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
