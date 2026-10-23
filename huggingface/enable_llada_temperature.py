#!/usr/bin/env python3
"""Deploy independent sequence temperature and PMI weight to Ruurd LLaDA only."""

import argparse
import json
from pathlib import Path

from enable_repetition_penalty import ROOT, make_bundle

SPACE = "Ruurd/llada-8b-instruct"
OUT = ROOT / "artifacts/bigram/llada_temperature"


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
            raise RuntimeError("Space changed since preparation")
        commit = api.upload_folder(
            repo_id=SPACE,
            repo_type="space",
            folder_path=record["bundle"],
            parent_commit=record["parent_revision"],
            commit_message="Decouple PMI weight from sequence sampling temperature",
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
        readme = read("README.md")
        # Supersede the historical temperature-dependent formula above.
        readme += """\n\n## Independent temperature and bigram weight

The LLaDA Space now uses S(y) = sum log p_t(y_t) + w sum PMI - gamma sum C.
**Bigram weight** ranges from 0 to 5, default 1. A weight of 1 gives equal
coefficients, not necessarily equal numerical influence. Weight 0 disables PMI
but does not disable repetition penalties. The previous fixed 0.5*temperature
PMI coefficient described above is superseded for this Space.

**Sample bigram-guided sequences** samples P(y) proportional to exp(S(y)/T).
Temperature controls the entropy of the whole sequence score, including repetition,
without changing the ratios of score coefficients. T=0 selects the maximum path;
positive T is floored to 1e-6 for numerical stability. Maximum-path Viterbi ignores
temperature. Raw full-vocabulary diffusion probabilities still determine expected
repetition counts and retention/APD confidence. Default T is now 1, w is 1,
matching the former T=2 PMI coefficient and sequence distribution. Ordinary
diffusion retains its usual temperature behavior. No extra model forwards.

Unseen pairs have a neutral PMI correction of zero, never a forbidden transition.
Conditional scoring instead uses smoothed finite probabilities. Expected repetition
counts remain the default; the optional candidate-set count mode is unchanged.
"""
        make_bundle(bundle, config, readme, apd=True)
        record = dict(space=SPACE, parent_revision=revision, bundle=str(bundle))
        manifest.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
