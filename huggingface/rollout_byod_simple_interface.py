#!/usr/bin/env python3
"""Guarded two-account BYOD BG+TG rollout; preserve weights/config/identity."""

import argparse, hashlib, json, os, shutil
from pathlib import Path
from publish_byod import MODELS

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/bigram/byod_simple_rollout"
NAMES = {
    "byod-gemma-2-9b": "gemma",
    "byod-llama-3.1-8b": "llama",
    "byod-qwen2.5-7b": "qwen",
    "byod-ministral-8b": "ministral",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def accounts():
    from dotenv import load_dotenv
    from huggingface_hub import HfApi
    from huggingface_hub.utils._auth import get_stored_tokens

    load_dotenv(ROOT / ".env")
    tokens = get_stored_tokens()
    dove = tokens.get("BYOD-update")
    if not dove:
        raise RuntimeError("Saved Dovelove deployment credential not found")
    result = {
        "Ruurd": HfApi(token=os.getenv("HF_TOKEN")),
        "Dovelove": HfApi(token=dove),
    }
    for owner, api in result.items():
        if api.whoami()["name"].casefold() != owner.casefold():
            raise RuntimeError("Credential account mismatch: " + owner)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute", action="store_true")
    args = p.parse_args()
    from huggingface_hub import hf_hub_download, CommitOperationAdd

    apis = accounts()
    OUT.mkdir(parents=True, exist_ok=True)
    plan = OUT / "prepared.json"
    if not args.execute:
        prepared = []
        for owner, api in apis.items():
            for spec in MODELS:
                name = NAMES[spec.space_name]
                space = owner + "/" + spec.space_name
                trained = ROOT / "artifacts/bigram/byod_trigrams" / name
                record = json.loads((trained / "complete.json").read_text())
                assert (
                    record["exact_bigram_match"]
                    and record["exact_unigram_match"]
                    and record["documents"] == 980000
                )
                info = api.repo_info(space, repo_type="space", files_metadata=True)
                files = {x.rfilename: x for x in info.siblings}
                bg = ROOT / "artifacts/bigram" / (name + ".pt")
                tri = trained / "trigram_expanded.pt"
                assert files["bigram.pt"].lfs.sha256 == sha(
                    bg
                ), "Deployed original scorer mismatch"
                assert sha(tri) == record["checkpoint_sha256"]
                assert max(bg.stat().st_size, tri.stat().st_size) < 1_000_000_000

                def read(filename):
                    return Path(
                        hf_hub_download(
                            space,
                            filename,
                            repo_type="space",
                            revision=info.sha,
                            token=api.token,
                        )
                    ).read_bytes()

                config_bytes = read("space_model.json")
                config = json.loads(config_bytes)
                assert (
                    config["model_repo_id"] == owner + "/" + spec.model_name
                    and config["bigram_enabled"]
                )
                before = OUT / "before" / owner / spec.space_name
                before.mkdir(parents=True, exist_ok=True)
                (before / "space_model.json").write_bytes(config_bytes)
                (before / "app.py").write_bytes(read("app.py"))
                bundle = OUT / "bundles" / owner / spec.space_name
                bundle.mkdir(parents=True, exist_ok=True)
                for target, source in [
                    ("app.py", ROOT / "huggingface/byod_space/app.py"),
                    (
                        "requirements.txt",
                        ROOT / "huggingface/byod_space/requirements.txt",
                    ),
                    ("bigram_expanded.pt", bg),
                    ("trigram_expanded.pt", tri),
                ]:
                    shutil.copy2(source, bundle / target)
                shutil.copytree(
                    ROOT / "src/diffusion_lm",
                    bundle / "src/diffusion_lm",
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
                config.update(trigram_enabled=True)
                (bundle / "space_model.json").write_text(
                    json.dumps(config, indent=2) + "\n"
                )
                public_report = {
                    k: v for k, v in record.items() if k not in ["seconds"]
                }
                public_report.update(
                    corpus="Full original BYOD response training split, 980000 documents; not the LLaDA expanded web corpus",
                    bigram_sha256=sha(bg),
                    trigram_min_count=2,
                    trigram_clip=2.0,
                    trigram_relative_weight=0.5,
                )
                (bundle / "ngram_training_report.json").write_text(
                    json.dumps(public_report, indent=2) + "\n"
                )
                readme = read("README.md").decode()
                readme += """\n\n## Current simplified interface

Two methods: **Confidence-guided** and **BG + TG Viterbi (Gumbel)**. Guided
Temperature0 is deterministic; positive values add unary Gumbel noise, default0.3.
Bigram weight defaults1. APD, early stopping and EOS/EOT retention remain
available; ending-delay strength is10. Other research controls are hidden.
Set SHOW_LEGACY_DECODING_CONTROLS=True in app.py to restore them.

These tokenizer-specific bigram/trigram counts use all980000 original BYOD
training responses, with matching EOS/truncation policy and no document-crossing
counts. They do not use the larger LLaDA expanded corpus. Reconstructed bigram
and unigram counts were verified exactly against the existing scorer. Trigrams
retain count>=2 and clip corrections to+/-2, with relative weight0.5. No diffusion
model training, extra model forwards or external language model are introduced.
Older research-option descriptions in this file describe retained legacy
implementations, not controls exposed by the simplified interface.
"""
                (bundle / "README.md").write_text(readme)
                hashes = {
                    str(f.relative_to(bundle)): sha(f)
                    for f in bundle.rglob("*")
                    if f.is_file()
                }
                prepared.append(
                    dict(
                        space=space,
                        owner=owner,
                        parent_revision=info.sha,
                        private=info.private,
                        model=name,
                        bundle=str(bundle),
                        original_bigram_sha256=sha(bg),
                        files=hashes,
                        config_before=config_bytes.decode(),
                    )
                )
        plan.write_text(json.dumps(prepared, indent=2) + "\n")
        print(
            json.dumps(
                [
                    dict(space=r["space"], model=r["model"], files=len(r["files"]))
                    for r in prepared
                ],
                indent=2,
            )
        )
        return
    prepared = json.loads(plan.read_text())
    assert len(prepared) == 8
    deployed_path = OUT / "deployment.json"
    deployed = json.loads(deployed_path.read_text()) if deployed_path.exists() else []
    done = {r["space"]: r for r in deployed}
    for r in prepared:
        expected = (
            done[r["space"]]["revision"] if r["space"] in done else r["parent_revision"]
        )
        assert (
            apis[r["owner"]].repo_info(r["space"], repo_type="space").sha == expected
        ), ("Space changed: " + r["space"])
    for r in prepared:
        if r["space"] in done:
            continue
        bundle = Path(r["bundle"])
        for name, expected in r["files"].items():
            assert sha(bundle / name) == expected, "Prepared file changed: " + name
        commit = apis[r["owner"]].create_commit(
            repo_id=r["space"],
            repo_type="space",
            parent_commit=r["parent_revision"],
            operations=[
                CommitOperationAdd(path_in_repo=name, path_or_fileobj=bundle / name)
                for name in r["files"]
            ],
            commit_message="Add tokenizer-matched trigrams and simplify to confidence / BG+TG Gumbel decoding",
        )
        deployed.append(
            dict(
                space=r["space"],
                owner=r["owner"],
                model=r["model"],
                parent_revision=r["parent_revision"],
                revision=commit.oid,
            )
        )
        deployed_path.write_text(json.dumps(deployed, indent=2) + "\n")
        print(json.dumps(deployed[-1]), flush=True)


if __name__ == "__main__":
    main()
