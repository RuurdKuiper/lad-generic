#!/usr/bin/env python3
"""Prepare or deploy optional sequence sampling/candidate counts to Ruurd LLaDA only."""

import argparse
import json
from pathlib import Path

from enable_repetition_penalty import ROOT, make_bundle

SPACE = "Ruurd/llada-8b-instruct"
OUTPUT = ROOT / "artifacts/bigram/llada_sequence_sampling"


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
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = OUTPUT / "prepared.json"
    if args.execute:
        record = json.loads(manifest.read_text())
        if (
            record["space"] != SPACE
            or api.repo_info(SPACE, repo_type="space").sha != record["parent_revision"]
        ):
            raise RuntimeError(
                "Space changed since preparation; review before deploying"
            )
        commit = api.upload_folder(
            repo_id=SPACE,
            repo_type="space",
            folder_path=record["bundle"],
            parent_commit=record["parent_revision"],
            commit_message="Add optional bigram-guided sequence sampling and candidate-occurrence repetition counts",
        )
        record["revision"] = commit.oid
        (OUTPUT / "deployment.json").write_text(json.dumps(record, indent=2) + "\n")
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
            raise RuntimeError("Unexpected model setup")
        readme = read("README.md")
        bundle = OUTPUT / "bundle"
        make_bundle(bundle, config, readme, apd=True)
        with (bundle / "README.md").open("a") as f:
            f.write("""\n\n## Optional sequence sampling and candidate-occurrence counts

Both checkboxes default OFF, preserving existing decoding. **Sample bigram-guided
sequences** replaces the maximum-path decision with exact forward-filter/backward
sampling from exp(total path score) on the same candidate lattice. Diffusion,
PMI, boundaries and any repetition scores are unchanged; no score perturbations
or extra model forwards are used. Seed controls reproducibility. This applies
to either bigram decoding strategy, independently of APD.

**Count every candidate bigram occurrence** applies only with the repetition
penalty strategy. Each earlier adjacent pair of candidate sets containing (a,b)
adds 1 to C(a,b), irrespective of probability. Duplicate fixed-token columns
count once; EOS/EOT pairs are excluded. Counts update after scoring each edge
and reset each block/iteration. Gamma still subtracts gamma*C in log-score units;
this is not a percentage-parameter remapping. Gamma=0 restores unpenalized results
for the selected maximum-path or sampling mode. Ordinary decoding ignores these
checkboxes; the original temperature weighting is unchanged.
""")
        (OUTPUT / "before_app.py.txt").write_text(read("app.py"))
        record = dict(space=SPACE, parent_revision=revision, bundle=str(bundle))
        manifest.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
