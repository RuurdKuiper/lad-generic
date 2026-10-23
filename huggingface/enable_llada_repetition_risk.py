#!/usr/bin/env python3
"""Prepare/deploy the optional joint-probability repetition-risk penalty to LLaDA."""

import argparse
import json
from pathlib import Path

from enable_repetition_penalty import ROOT, make_bundle

SPACE = "Ruurd/llada-8b-instruct"
OUT = ROOT / "artifacts/bigram/llada_repetition_risk"


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
            commit_message="Add optional joint bigram repetition-risk penalty",
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

## Optional repetition-risk penalty

With **PMI Viterbi + Repetition Penalty**, enable **Repetition-risk penalty**
(default OFF) to estimate earlier repetition risk from joint diffusion+PMI
sequence probabilities. This overrides the candidate-count checkbox if both
are enabled; OFF preserves the existing expected/candidate-count choice.

A forward/backward sum-product pass on the unpenalized candidate lattice yields
q_s(a,b). Earlier risk is approximated as r_t=1-prod_(s<t)(1-q_s).
The raw log-score correction is -gamma*log((1-r+9r)/(1-r)). At T=1, gamma=1,
risk 0.1 gives multiplier 0.5; risk 0.5 gives multiplier 0.1. Sequence temperature
subsequently scales the entire corrected score as usual. This is an approximate
risk heuristic, not the exact conditional probability of repetition or a guarantee
on normalized output probabilities. Overlapping occurrences are dependent.

Risk uses the same temperature as sequence sampling; maximum-path decoding uses
a T=1 soft distribution, including when sampling temperature is zero. Fixed
positions and existing PMI boundary terms are included. Duplicate fixed columns
have zero marginal. Counts reset per iteration/block and do not cross prompt or
block boundaries. EOS/EOT pairs neither seed risk nor receive penalties. Gamma=0
matches the unpenalized selected decoding mode exactly. A 1e-7 survival floor
keeps near-certain risk finite. Marginals are computed once before risk adjustment;
no iterative fixed-point calculation is performed.

There are no extra model forwards, external language models, or training changes.
The extra decoder passes add overhead. Existing defaults and other Spaces remain
unchanged. Independent temperature/bigram weight controls are preserved.
"""
        make_bundle(bundle, config, readme, apd=True)
        record = dict(space=SPACE, parent_revision=revision, bundle=str(bundle))
        manifest.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
