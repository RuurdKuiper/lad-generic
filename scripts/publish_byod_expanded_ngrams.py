#!/usr/bin/env python3
"""Publish validated expanded assets and pin both accounts' BYOD Spaces to them."""

import argparse, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "huggingface"))
from rollout_byod_simple_interface import accounts
from build_byod_expanded_ngrams import digest

OUT = ROOT / "artifacts/bigram/byod_expanded_rollout"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--model", choices=["gemma", "llama", "qwen", "ministral"], required=True
    )
    a = p.parse_args()
    from huggingface_hub import (
        hf_hub_download,
        CommitOperationAdd,
        CommitOperationDelete,
    )

    apis = accounts()
    OUT.mkdir(exist_ok=True)
    deployments = json.loads(
        (ROOT / "artifacts/bigram/byod_simple_rollout/deployment.json").read_text()
    )
    trained = ROOT / "artifacts/bigram/byod_expanded_ngrams" / a.model
    report = json.loads((trained / "complete.json").read_text())
    assert report["added_tokens"] == 800_000_000
    for filename, asset in report["assets"].items():
        assert digest(trained / filename) == asset["sha256"]
    path = OUT / "deployment.json"
    records = json.loads(path.read_text()) if path.exists() else []
    for r in deployments:
        if r["model"] != a.model:
            continue
        if any(x["space"] == r["space"] for x in records):
            continue
        api = apis[r["owner"]]
        info = api.repo_info(r["space"], repo_type="space", files_metadata=True)
        assert info.sha == r["revision"], "Space changed since smaller rollout"
        # Same-owner repositories keep model identity and account attribution intact.
        asset_repo = r["owner"] + "/byod-" + a.model + "-ngram-guidance-expanded"
        bundle = OUT / "bundles" / r["owner"] / a.model
        bundle.mkdir(parents=True, exist_ok=True)
        for filename in report["assets"]:
            target = bundle / filename
            if not target.exists():
                os.link(trained / filename, target)
        (bundle / "training_report.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        (bundle / "README.md").write_text("""---
tags:
- n-gram
---
# BYOD expanded n-gram guidance

Tokenizer-specific bigram and trigram statistics, without diffusion-model weights.
Full original 980,000 response documents plus 800 million added tokens: 90% FineWeb-Edu,
5% Python-Edu and 5% FineMath. Added token budgets are measured separately with each
model tokenizer. Sources, pinned revisions, hashes and exact counts are in training_report.json.

All bigram counts are retained. Trigrams retain counts >=2, including count two;
prefix totals include singleton contributions. Counts never cross document boundaries.
PMI uses the successor marginal; trigram backoff strength is 50. No model retraining.

Sources: https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu,
https://huggingface.co/datasets/Avelina/python-edu-cleaned,
https://huggingface.co/datasets/HuggingFaceTB/finemath.
""")
        api.create_repo(asset_repo, repo_type="model", private=False, exist_ok=True)
        commit = api.upload_folder(
            repo_id=asset_repo,
            repo_type="model",
            folder_path=str(bundle),
            commit_message="Publish 800M-token expanded BYOD bigram/trigram guidance",
        )
        remote = api.repo_info(
            asset_repo, repo_type="model", revision=commit.oid, files_metadata=True
        )
        files = {f.rfilename: f for f in remote.siblings}
        for filename, asset in report["assets"].items():
            assert files[filename].lfs.sha256 == asset["sha256"]

        def read(name):
            return Path(
                hf_hub_download(
                    r["space"],
                    name,
                    repo_type="space",
                    revision=info.sha,
                    token=api.token,
                )
            ).read_text()

        before = read("space_model.json")
        config = json.loads(before)
        assert config["trigram_enabled"]
        config.update(ngram_scorer_repo=asset_repo, ngram_scorer_revision=commit.oid)
        readme = read("README.md")
        marker = (
            "These tokenizer-specific bigram/trigram counts use all980000 original BYOD"
        )
        start = readme.find(marker)
        if start >= 0:
            end = readme.find("Older research-option descriptions", start)
            assert end >= 0
            readme = (
                readme[:start]
                + """These tokenizer-specific bigram/trigram counts now use all 980,000 original BYOD
responses plus 800 million added tokens: 90% FineWeb-Edu, 5% Python-Edu and
5% FineMath. The expanded scorer repository and immutable revision are pinned
in space_model.json. Provenance and hashes are in ngram_training_report.json.
Trigrams retain counts >=2; corrections clip to +/-2, with relative weight 0.5.
No model training or additional model forward passes are introduced.
"""
                + readme[end:]
            )
        operations = [
            CommitOperationAdd(
                path_in_repo="space_model.json",
                path_or_fileobj=(json.dumps(config, indent=2) + "\n").encode(),
            ),
            CommitOperationAdd(
                path_in_repo="ngram_training_report.json",
                path_or_fileobj=(json.dumps(report, indent=2) + "\n").encode(),
            ),
            CommitOperationAdd(
                path_in_repo="README.md", path_or_fileobj=readme.encode()
            ),
        ]
        # Expanded artifacts live in the pinned model repository to avoid the Space
        # per-file size limit. Remove superseded small copies; keep legacy bigram.pt.
        prior_files = {f.rfilename: f for f in info.siblings}
        previous_sources = {
            "bigram_expanded.pt": ROOT / "artifacts/bigram" / (a.model + ".pt"),
            "trigram_expanded.pt": ROOT
            / "artifacts/bigram/byod_trigrams"
            / a.model
            / "trigram_expanded.pt",
        }
        for filename, source in previous_sources.items():
            assert prior_files[filename].lfs.sha256 == digest(source), (
                "Unexpected existing scorer: " + filename
            )
            operations.append(CommitOperationDelete(path_in_repo=filename))
        deployed = api.create_commit(
            repo_id=r["space"],
            repo_type="space",
            parent_commit=info.sha,
            operations=operations,
            commit_message="Use expanded tokenizer-specific bigram and trigram scorers",
        )
        record = dict(
            space=r["space"],
            owner=r["owner"],
            model=a.model,
            parent_revision=info.sha,
            revision=deployed.oid,
            asset_repo=asset_repo,
            asset_revision=commit.oid,
            config_before=json.loads(before),
            config_after=config,
            assets=report["assets"],
            tokens=report["tokens"],
        )
        records.append(record)
        path.write_text(json.dumps(records, indent=2) + "\n")
        print(
            json.dumps({k: v for k, v in record.items() if not k.startswith("config")}),
            flush=True,
        )
        manifest = {
            x["space"]: dict(
                trigram_enabled=True,
                ngram_scorer_repo=x["asset_repo"],
                ngram_scorer_revision=x["asset_revision"],
            )
            for x in records
        }
        (ROOT / "huggingface/byod_ngram_assets.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )


if __name__ == "__main__":
    main()
