#!/usr/bin/env python3
"""Deploy only optional randomized Viterbi and its UI to the Ruurd LLaDA Space."""

import argparse, difflib, hashlib, json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/bigram/llada_ngram_settings_full/randomized"
SPACE = "Ruurd/llada-8b-instruct"
FILES = {
    "app.py": "huggingface/byod_space/app.py",
    "src/diffusion_lm/bigram.py": "src/diffusion_lm/bigram.py",
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--execute", action="store_true")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--standard-temperature", action="store_true")
    mode.add_argument("--simplified-interface", action="store_true")
    args = p.parse_args()
    from dotenv import load_dotenv
    from huggingface_hub import HfApi, hf_hub_download, CommitOperationAdd

    load_dotenv(ROOT / ".env")
    api = HfApi(token=os.getenv("HF_TOKEN"))
    if api.whoami()["name"].casefold() != "ruurd":
        raise RuntimeError("Requires Ruurd account")
    folder = (
        OUT
        / ("simple_interface" if args.simplified_interface else "standard_temperature")
        if (args.standard_temperature or args.simplified_interface)
        else OUT
    )
    folder.mkdir(parents=True, exist_ok=True)
    files = (
        {"app.py": FILES["app.py"]}
        if (args.standard_temperature or args.simplified_interface)
        else FILES
    )
    plan = folder / "deployment_plan.json"
    if not args.execute:
        record = dict(
            space=SPACE,
            parent_revision=api.repo_info(SPACE, repo_type="space").sha,
            files={},
        )
        for target, local in files.items():
            remote = Path(
                hf_hub_download(
                    SPACE,
                    target,
                    repo_type="space",
                    revision=record["parent_revision"],
                    token=api.token,
                )
            ).read_bytes()
            source = (ROOT / local).read_bytes()
            name = target.replace("/", "_")
            (folder / (name + ".before")).write_bytes(remote)
            (folder / (name + ".diff")).write_text(
                "".join(
                    difflib.unified_diff(
                        remote.decode().splitlines(True),
                        source.decode().splitlines(True),
                        fromfile=target + " before",
                        tofile=target + " after",
                    )
                )
            )
            record["files"][target] = dict(
                local=local,
                sha256=hashlib.sha256(source).hexdigest(),
                old_sha256=hashlib.sha256(remote).hexdigest(),
            )
        plan.write_text(json.dumps(record, indent=2) + "\n")
    else:
        record = json.loads(plan.read_text())
        assert api.repo_info(SPACE, repo_type="space").sha == record["parent_revision"]
        operations = []
        for target, data in record["files"].items():
            path = ROOT / data["local"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == data["sha256"]
            operations.append(
                CommitOperationAdd(path_in_repo=target, path_or_fileobj=path)
            )
        c = api.create_commit(
            repo_id=SPACE,
            repo_type="space",
            parent_commit=record["parent_revision"],
            operations=operations,
            commit_message=(
                "Simplify LLaDA UI to confidence and BG+TG Gumbel Viterbi"
                if args.simplified_interface
                else (
                    "Use Gumbel Viterbi as standard BG/BG+TG temperature behavior"
                    if args.standard_temperature
                    else "Add optional temperature-scaled Gumbel randomized Viterbi, retaining fast exact MAP decoding"
                )
            ),
        )
        record["revision"] = c.oid
        (folder / "deployment.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
