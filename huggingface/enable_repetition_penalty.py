#!/usr/bin/env python3
"""Add optional repetition-aware Viterbi to Ruurd's existing Gemma/LLaDA Spaces."""
import argparse
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
SPACE_IDS = ("Ruurd/byod-gemma-2-9b", "Ruurd/llada-8b-instruct")


def make_bundle(destination, config, readme, *, apd=False):
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "huggingface/byod_space/app.py", destination / "app.py")
    shutil.copytree(ROOT / "src/diffusion_lm", destination / "src/diffusion_lm",
                    dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # The hosted checkpoints, dependencies, hardware and model revisions stay in
    # their existing repositories; upload only app/library code and documentation.
    config = dict(config, show_bigram_evaluation_controls=True)
    (destination / "space_model.json").write_text(json.dumps(config, indent=2) + "\n")
    if "## Optional repetition-aware PMI Viterbi" not in readme:
        readme += """

## Optional repetition-aware PMI Viterbi

Select **PMI Viterbi + Repetition Penalty** to use the block-local transition
score `0.5 * temperature * PMI(a,b) - gamma * C(a,b)`. Gamma defaults to 1.0;
0 reproduces the original PMI decoder. C accumulates earlier expected bigram
occurrences from full-vocabulary diffusion probabilities, updated only after
scoring each position. EOS/EOT pairs are neither penalized nor counted. Retained
tokens remain fixed constraints. Counts reset each iteration and block, without
crossing prompt/block boundaries. There are no additional model forward passes.
The original **Bigram Viterbi** option and generation defaults remain available.
"""
    if apd and "## Adaptive Parallel Decoding" not in readme:
        readme += """

## Adaptive Parallel Decoding

The **Adaptive Parallel Decoding (APD)** checkbox defaults OFF. APD is a
commitment layer after the selected sampling or sequence decoder. Each block
uses a cosine confidence threshold from 0.90 to 0.50, with a 15% warmup. It
commits all qualifying masked positions using their selected token's original
full-vocabulary diffusion probability. Remaining positions stay masked; a
best-confidence fallback makes progress and the final step resolves all masks.
Completed blocks exit early, independently of the convergence-stop checkbox.
Existing EOS/EOT retention delay is respected, with endings retained after
ordinary predictions; whole-answer EOS/EOT stopping still follows Early stopping.
Committed values stay fixed. Optional AR retention scoring and retained-token
revision are bypassed under APD. No additional model forwards, token budgets,
position factors, or grinding-phase detection are used. OFF retains the original
decoding configuration. This implements the requested APD subset, inspired by
[CAI-dLLM](https://arxiv.org/abs/2608.22646), rather than its complete controller.
"""
    (destination / "README.md").write_text(readme)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--feature", choices=["repetition", "apd"], default="repetition")
    parser.add_argument("--execute", action="store_true", help="Upload the already prepared, reviewed bundles")
    args = parser.parse_args()
    if args.output is None:
        args.output = ROOT / "artifacts/bigram" / ("apd_rollout" if args.feature == "apd" else "repetition_rollout")
    from dotenv import load_dotenv
    from huggingface_hub import HfApi, hf_hub_download
    load_dotenv(ROOT / ".env")
    api = HfApi()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = args.output / "prepared.json"
    if not args.execute:
        prepared = []
        for space in SPACE_IDS:
            info = api.repo_info(space, repo_type="space")

            def read(name):
                return Path(hf_hub_download(space, name, repo_type="space", revision=info.sha, token=api.token)).read_text()

            config, readme, original_app = json.loads(read("space_model.json")), read("README.md"), read("app.py")
            if not config.get("bigram_enabled"):
                raise RuntimeError(f"Existing scorer is not enabled in {space}")
            if 'label="Bigram ending delay strength"' not in original_app:
                raise RuntimeError(f"Review changed interface controls before updating {space}")
            folder = args.output / "bundles" / space.split("/")[1]
            make_bundle(folder, config, readme, apd=args.feature == "apd")
            prepared.append(dict(space=space, parent_revision=info.sha, private=info.private,
                                 bundle=str(folder), model=config["model_repo_id"]))
        manifest.write_text(json.dumps(prepared, indent=2) + "\n")
        print(manifest.read_text())
        return
    if api.whoami()["name"].casefold() != "ruurd":
        raise RuntimeError("This rollout requires the Ruurd account")
    prepared = json.loads(manifest.read_text())
    if tuple(record["space"] for record in prepared) != SPACE_IDS:
        raise RuntimeError("Prepared targets do not match the intended two Spaces")
    # Verify both revisions before uploading either one, then guard each commit.
    for record in prepared:
        if api.repo_info(record["space"], repo_type="space").sha != record["parent_revision"]:
            raise RuntimeError(f"Space changed since preparation: {record['space']}")
    deployed = []
    for record in prepared:
        commit = api.upload_folder(repo_id=record["space"], repo_type="space",
            folder_path=record["bundle"], parent_commit=record["parent_revision"],
            commit_message=("Add optional adaptive parallel decoding; preserve APD-off behavior" if args.feature == "apd"
                            else "Add optional PMI Viterbi transition repetition penalty; preserve existing defaults"))
        deployed.append(dict(record, revision=commit.oid))
        (args.output / "deployment.json").write_text(json.dumps(deployed, indent=2) + "\n")
        print(json.dumps(deployed[-1]), flush=True)


if __name__ == "__main__":
    main()
