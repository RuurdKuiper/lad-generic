#!/usr/bin/env python3
"""Prepare/deploy the logistic repetition-penalty decay to LLaDA."""

import argparse
import json
from pathlib import Path

from enable_repetition_penalty import ROOT, make_bundle

SPACE = "Ruurd/llada-8b-instruct"
OUT = ROOT / "artifacts/bigram/llada_repetition_decay"


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
            commit_message="Fade repetition penalties over early block iterations; retain constant-strength option",
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

## Early-iteration repetition-penalty fade

**Fade repetition penalty over early iterations** is ON by default in the UI
for LLaDA. It only affects the repetition strategy, including expected-count,
candidate-count and risk modes. Turn it OFF to retain constant strength.
API calls that omit decay_repetition_penalty retain constant strength for
compatibility; pass true explicitly to match the new UI.

Gamma_t = gamma * f(t), with zero-based iteration t within each block.
Let L=6, c=(L-1)/2 and g(t)=1/(1+exp(1.6*(t-c))). Then
f(t)=(g(t)-g(L-1))/(g(0)-g(L-1)) for 0<=t<L-1, and zero afterward.
The first iteration is exactly full strength. From iteration 6 the penalty is
exactly zero, not merely asymptotically small, so the original unpenalized
sequence decoder runs and risk/count computations are bypassed.

The active window is absolute and does not stretch with total NFE. A one-step
block receives full strength, while longer blocks spend their later iterations
without repetition penalties. The schedule resets at each new block. APD early
exit does not rescale it. Edit REPETITION_FADE_ITERATIONS in app.py to change the
window. The sigmoid slope is fixed at 1.6. Sampling, diffusion confidence, PMI,
temperature and ending retention keep their existing scoring behavior.

There are no extra model forwards. All existing penalty modes and the constant
option remain available; improvement across budgets still needs evaluation.
"""
        make_bundle(bundle, config, readme, apd=True)
        record = dict(space=SPACE, parent_revision=revision, bundle=str(bundle))
        manifest.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
