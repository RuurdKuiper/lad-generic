#!/usr/bin/env python3
"""Merge a diffusion-lm PEFT adapter into a standalone Hugging Face model."""
from __future__ import annotations

import argparse
import json

from diffusion_lm.merging import merge_adapter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("adapter", help="Adapter directory containing adapter_config.json")
    parser.add_argument("output", help="New or empty output directory")
    parser.add_argument("--dtype", choices=["fp16", "bf16", "fp32"], default="bf16")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--max-shard-size", default="5GB")
    parser.add_argument("--no-verify", action="store_true", help="Skip the pre/post-merge logit check")
    parser.add_argument("--verification-prompt", default="The capital of the Netherlands is")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = merge_adapter(
        args.adapter,
        args.output,
        dtype=args.dtype,
        device=args.device,
        cache_dir=args.cache_dir,
        max_shard_size=args.max_shard_size,
        verify=not args.no_verify,
        verification_prompt=args.verification_prompt,
    )
    print(json.dumps(report.__dict__, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
