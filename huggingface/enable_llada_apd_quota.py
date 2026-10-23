#!/usr/bin/env python3
"""Prepare/deploy the minimum per-step APD commitment quota to LLaDA."""

import argparse
import json
from pathlib import Path

from enable_repetition_penalty import ROOT, make_bundle

SPACE = "Ruurd/llada-8b-instruct"
OUT = ROOT / "artifacts/bigram/llada_apd_quota"


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
            commit_message="Guarantee a minimum token commitment quota each APD step",
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

## APD minimum commitment per iteration

APD now commits at least ceil(block_length / allocated_block_iterations) pending
positions on each pass, capped by the number still masked. For a 64-token block
with 16 iterations, the minimum is 4 tokens per iteration. Nondivisible lengths
round up: a 65-token block at 16 iterations has a minimum of 5 until fewer remain.
This avoids leaving a large unresolved tail for the final pass. This is a fixed
per-step floor, not a reduced cumulative target after an earlier large commit.

All threshold-qualified pending positions still commit, even above the quota.
If they are fewer than the quota, fill the deficit by selected-token diffusion
confidence, without changing the selected IDs or adding model calls. Frozen rows
are excluded. With EOS/EOT delay, fill ordinary rows first; if fewer ordinary rows
remain than needed, fill endings only after all ordinary rows have been selected.
Final cleanup and early block exit remain. Each block uses its own length and
allocated iteration budget; unequal final blocks are handled independently.

No new UI control is added. APD OFF is unchanged. At aggressiveness 0 the original
threshold curve remains, but the quota is now guaranteed; the previous claim of
identical full APD behavior at zero is superseded by this intended commitment
change. Aggressiveness still lowers thresholds and can commit more than the quota.
All decoding strategies, sequence sampling, risk/expected/candidate penalties,
repetition decay and ending safeguards remain available. Other Spaces were not
updated. No extra model forwards or training changes are introduced.
"""
        make_bundle(bundle, config, readme, apd=True)
        record = dict(space=SPACE, parent_revision=revision, bundle=str(bundle))
        manifest.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
