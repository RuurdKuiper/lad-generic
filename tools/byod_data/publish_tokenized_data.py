#!/usr/bin/env python3
"""Prepare and publish revision-pinned BYOD clean-token profiles on the Hub."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2] / "byod-reproducible"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from train import load_training_config
from diffusion_lm.prepared_cache import preparation_metadata, preparation_key
from prepare import prepare_training_data


PROFILES = {
    "llama-3.2-1b-instruct": ("llama", "quick"),
    "gemma-3-1b-it": ("gemma", "quick"),
    "qwen2.5-1.5b-instruct": ("qwen", "quick"),
    "llama-3.1-8b-instruct": ("llama", "paper"),
    "gemma-2-9b-it": ("gemma", "paper"),
    "qwen2.5-7b-instruct": ("qwen", "paper"),
    "ministral-8b-instruct-2410": ("ministral", "paper"),
}


def main():
    from datasets import DatasetDict, load_dataset
    from huggingface_hub import HfApi, DatasetCard, hf_hub_download

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--profiles", nargs="+", choices=list(PROFILES), default=list(PROFILES))
    parser.add_argument("--cache-dir", default="data/huggingface")
    parser.add_argument("--model-cache-dir", default="base_models")
    parser.add_argument("--prepared-data-cache-dir", default="data/prepared")
    parser.add_argument("--summary", default="outputs/tokenized-publication.json")
    parser.add_argument("--full-dataset", action="store_true", help="Prepare all source training rows instead of the standard 400k prefix")
    parser.add_argument("--publish", action="store_true", help="Upload the locally prepared profiles as a public dataset")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    api = HfApi(token=os.getenv("HF_TOKEN"))
    results = {}
    for profile in args.profiles:
        model, mode = PROFILES[profile]
        config = load_training_config(model, mode)
        config.update(cache_dir=args.cache_dir, base_model_cache_dir=args.model_cache_dir,
                      prepared_data_cache_dir=args.prepared_data_cache_dir, prepared_dataset_name=None, preprocessing_num_workers=1)
        limit = None if args.full_dataset else config["max_updates"] * config["batch_size"] * config["gradient_accumulation_steps"]
        print(f"Preparing {profile} (training prefix: {limit or 'all'})", flush=True)
        tokenizer, train, validation, test, _ = prepare_training_data(config, limit)
        data = DatasetDict(train=train, validation=validation, test=test)
        # Preserve original source/category attribution by stable source indices.
        raw = load_dataset(config["dataset_name"], revision=config["dataset_revision"],
                           cache_dir=args.cache_dir, token=os.getenv("HF_TOKEN"))
        for split, dataset in data.items():
            original = raw[split].select(list(dataset["_index"]))
            for column in ("source", "category"):
                if column in original.column_names:
                    dataset = dataset.add_column(column, list(original[column]))
            data[split] = dataset
        metadata = preparation_metadata(config, tokenizer, limit)
        manifest = {"profile": profile, "preparation": metadata,
                    "cache_key": preparation_key(metadata),
                    "rows": {split: len(dataset) for split, dataset in data.items()},
                    "random_corruption": "online, not stored",
                    "software": "https://github.com/RuurdKuiper/BYOD"}
        manifest_path = Path(args.prepared_data_cache_dir) / manifest["cache_key"] / "publication.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        if args.publish:
            api.create_repo(args.repo_id, repo_type="dataset", private=False, exist_ok=True)
            data.push_to_hub(args.repo_id, config_name=profile, private=False,
                             token=os.getenv("HF_TOKEN"), max_shard_size="250MB",
                             commit_message=f"Add BYOD token profile {profile}")
            commit = api.upload_file(
                path_or_fileobj=manifest_path, path_in_repo=f"prepared/{profile}.json",
                repo_id=args.repo_id, repo_type="dataset",
                commit_message=f"Record pinned preparation metadata for {profile}",
            )
            manifest["published_revision"] = commit.oid
        results[profile] = manifest
        summary = Path(args.summary)
        summary.parent.mkdir(parents=True, exist_ok=True)
        summary.write_text(json.dumps({"repo": args.repo_id, "profiles": results}, indent=2) + "\n")
        print(f"Completed {profile}: {manifest['rows']}", flush=True)

    if args.publish:
        # Preserve the automatically generated multi-configuration YAML metadata.
        card = DatasetCard.load(args.repo_id, token=os.getenv("HF_TOKEN"))
        card.data.license = "other"
        card.text = """# BYOD: pretokenized 256-token training profiles

Clean token IDs and deterministic answer/padding masks for the standalone
[BYOD implementation](https://github.com/RuurdKuiper/BYOD). Random masking is
resampled online during training; these are not fixed noisy training inputs.

Each configuration uses its own pinned tokenizer and native chat template.
`prepared/CONFIG.json` records exact tokenizer/source revisions, recipe, row
counts, source indices, seed, and training prefix. Use the matching configuration;
token IDs are not interchangeable across models. The default publication uses
the seed-42 prefix of up to 400,000 nonempty training examples and the nonempty
validation/test splits for the standard 25,000-update recipe. Larger/custom
training budgets require a compatible full-data publication or local preparation.

The source is [Ruurd/LAD-training-1m-256](https://huggingface.co/datasets/Ruurd/LAD-training-1m-256)
at revision `6041513b684d6ca627879ffdb547b8629bb8b8de`.
`_index` identifies the original row in each source split; `source` and `category`
retain row-level attribution. `_lad_clean_ids` and the two boolean masks are
truncated exactly as in the training implementation. No model weights or
tokenizer files are redistributed here.

## Terms and provenance

This derivative retains the upstream mixture's restrictions and is **not**
covered by the software repository's MIT license. In particular, Alpaca-derived
rows carry non-commercial restrictions. See the [upstream provenance and terms](https://huggingface.co/datasets/Dovelove/BYOD-training-1m-256#upstream-repositories-and-terms).
Comply with each source's terms and the applicable parent-model/tokenizer terms.

Sources include Clean-Instruct-3M (no license declared on its source card), Tulu 3
(ODC-By), Alpaca-GPT4/Alpaca (CC BY-NC 4.0), MMLU/Orca-Math/GSM8K/OpenCoder
(MIT), HellaSwag (MIT in its project), ARC (CC BY-SA 4.0), and MBPP (CC BY 4.0).
"""
        card.push_to_hub(args.repo_id, token=os.getenv("HF_TOKEN"), commit_message="Document BYOD token profiles and upstream terms")
        print("FINAL_REVISION=" + api.dataset_info(args.repo_id).sha, flush=True)


if __name__ == "__main__":
    main()
