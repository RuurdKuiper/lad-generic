#!/usr/bin/env python
"""Build the LAD instruction mixture locally and optionally publish it."""
import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from diffusion_lm.dataset_builder import BuildConfig, build_dataset, write_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", help="Hugging Face dataset repo, e.g. Ruurd/LAD-training-v2")
    parser.add_argument("--output-dir", default="data/lad-training-v2")
    parser.add_argument("--total-examples", type=int, default=500_000)
    parser.add_argument("--tokenizer", default="meta-llama/Llama-3.1-8B-Instruct")
    parser.add_argument("--max-prompt-tokens", type=int, default=256)
    parser.add_argument("--max-sequence-tokens", type=int, default=512)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--private", action="store_true", help="Create/update a private Hub dataset")
    parser.add_argument("--no-upload", action="store_true", help="Build and save locally only")
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parent / ".env")
    token = os.getenv("HF_TOKEN")
    if not args.no_upload and not args.repo_id:
        parser.error("--repo-id is required unless --no-upload is used")
    config = BuildConfig(tokenizer_name=args.tokenizer, total_examples=args.total_examples,
                         max_prompt_tokens=args.max_prompt_tokens, max_sequence_tokens=args.max_sequence_tokens,
                         seed=args.seed)
    dataset = build_dataset(config, token=token)
    output = Path(args.output_dir)
    dataset.save_to_disk(str(output))
    write_manifest(dataset, config, output / "manifest.json")
    if not args.no_upload:
        dataset.push_to_hub(args.repo_id, token=token, private=args.private)
    print(f"Saved {sum(len(x) for x in dataset.values()):,} rows to {output}")
    if not args.no_upload:
        print(f"Uploaded to https://huggingface.co/datasets/{args.repo_id}")


if __name__ == "__main__":
    main()
