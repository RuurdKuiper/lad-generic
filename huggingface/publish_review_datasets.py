#!/usr/bin/env python3
"""Publish fresh anonymous-review copies of the paper's exact data artifacts."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download


ROOT = Path(__file__).resolve().parents[1]
PROMPTS_PATH = ROOT / "src" / "diffusion_lm" / "generation_prompts.txt"
SOURCE_TRAINING_REPO = "Ruurd/LAD-training-1m-256"
SOURCE_TRAINING_REVISION = "6041513b684d6ca627879ffdb547b8629bb8b8de"


def load_prompts() -> list[str]:
    prompts = [
        line.strip()
        for line in PROMPTS_PATH.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(prompts) != 100 or len(set(prompts)) != 100:
        raise ValueError(f"Expected 100 unique open-ended prompts, found {len(prompts)}")
    return prompts


def prompts_card() -> str:
    return """---
pretty_name: BYOD fixed open-ended evaluation prompts
language:
- en
task_categories:
- text-generation
---

# BYOD fixed open-ended evaluation prompts

This anonymous review artifact contains the 100 fixed, ordered questions used
for the paper's open-ended generation evaluation. Every evaluated model receives
the same prompt text and ordering. The repository intentionally contains prompts
only; model generations and scores are not part of this dataset.

## Schema

- `id`: zero-based prompt index used by the evaluation harness.
- `prompt`: the exact user question.
"""


def training_card() -> str:
    return """---
pretty_name: BYOD 1M training mixture (256-token sequences)
language:
- en
task_categories:
- text-generation
license: other
---

# BYOD 1M training mixture

This is the exact one-million-example training artifact used for the four
primary BYOD conversions and the longer BYOD-Llama run. It contains 980,000
training, 10,000 validation, and 10,000 test examples, prepared for a maximum
sequence length of 256 tokens with the Llama 3.1 8B Instruct tokenizer.

The top-level mixture is 45% general instruction following, 18% multiple-choice
reasoning, 18% mathematics, and 19% code. Within those groups, sources are mixed
as follows:

| Group | Upstream datasets | Within-group proportions |
|---|---|---|
| General | Clean-Instruct-3M; Tulu 3 SFT; Alpaca-GPT4; Alpaca | 40/35/20/5 |
| Reasoning | MMLU; HellaSwag; ARC-Easy | 73/25/2 |
| Mathematics | Orca-Math; GSM8K | 95/5 |
| Code | OpenCoder stage-2 educational instructions; MBPP | 99.7/0.3 |

Prompts were normalized and deduplicated, exact matches with held-out benchmark
prompts were excluded, and only examples fitting the 256-token sequence limit
were retained. The `source` field records row-level provenance.

## Upstream repositories and terms

- `crumb/Clean-Instruct-3M` (no license declared on its Hub card)
- `allenai/tulu-3-sft-mixture` (ODC-By)
- `vicgalle/alpaca-gpt4` and `tatsu-lab/alpaca` (CC BY-NC 4.0)
- `cais/mmlu`, `microsoft/orca-math-word-problems-200k`,
  `openai/gsm8k`, and `OpenCoder-LLM/opc-sft-stage2` (MIT)
- `Rowan/hellaswag` (MIT in the upstream project repository)
- `allenai/ai2_arc` (CC BY-SA 4.0)
- `google-research-datasets/mbpp` (CC BY 4.0)

This mixed artifact is not assigned a new permissive blanket license. Users
must comply with the terms and restrictions of each upstream source, including
the non-commercial restrictions applying to the Alpaca-derived subsets.
"""


def stage_prompts(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    rows = "".join(
        json.dumps({"id": index, "prompt": prompt}, ensure_ascii=False) + "\n"
        for index, prompt in enumerate(load_prompts())
    )
    (destination / "open_ended_questions.jsonl").write_text(rows)
    (destination / "README.md").write_text(prompts_card())


def stage_training(destination: Path) -> None:
    downloaded = Path(
        snapshot_download(
            SOURCE_TRAINING_REPO,
            repo_type="dataset",
            revision=SOURCE_TRAINING_REVISION,
            allow_patterns=["data/*.parquet"],
            local_dir=destination,
        )
    )
    if downloaded.resolve() != destination.resolve():
        raise RuntimeError(f"Unexpected snapshot destination: {downloaded}")
    (destination / "README.md").write_text(training_card())


def publish_bundle(api: HfApi, repo_id: str, folder: Path) -> None:
    api.create_repo(repo_id, repo_type="dataset", private=True, exist_ok=True)
    api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=folder,
        ignore_patterns=[".cache/**", "*.pyc", "__pycache__/**"],
        commit_message="Add anonymous review dataset",
    )
    api.update_repo_settings(repo_id, repo_type="dataset", private=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--prompts-only", action="store_true")
    parser.add_argument("--training-only", action="store_true")
    args = parser.parse_args()
    if args.prompts_only and args.training_only:
        raise ValueError("--prompts-only and --training-only are mutually exclusive")

    api = HfApi()
    identity = api.whoami().get("name", "unknown")
    if identity.casefold() != args.namespace.casefold():
        raise RuntimeError(f"Authenticated as {identity!r}, target namespace is {args.namespace!r}")

    targets = (
        (f"{args.namespace}/BYOD-open-ended-questions", stage_prompts),
        (f"{args.namespace}/BYOD-training-1m-256", stage_training),
    )
    if args.prompts_only:
        targets = targets[:1]
    elif args.training_only:
        targets = targets[1:]
    print(f"Authenticated as {identity}")
    print("Targets:", *(repo for repo, _ in targets), sep="\n- ")
    if not args.execute:
        print("Validation complete; pass --execute to publish.")
        return

    with tempfile.TemporaryDirectory(prefix="byod-review-data-") as temp:
        root = Path(temp)
        for index, (repo_id, stage) in enumerate(targets):
            bundle = root / str(index)
            stage(bundle)
            publish_bundle(api, repo_id, bundle)
            shutil.rmtree(bundle)
            print(f"Published https://huggingface.co/datasets/{repo_id}")


if __name__ == "__main__":
    main()
