#!/usr/bin/env python
"""Load an inference model and verify one real denoising forward pass."""
from __future__ import annotations

import argparse

from diffusion_lm.inference import denoise, load_hosted_legacy_session, load_local_legacy_session, load_session, release_session


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--adapter", help="Saved adapter path relative to --outputs-dir")
    source.add_argument("--legacy-repo", help="Trusted Hugging Face repository containing a legacy full checkpoint")
    source.add_argument("--legacy-checkpoint", help="Trusted local legacy full-model .pth checkpoint")
    parser.add_argument("--outputs-dir", default="outputs", help="Root containing saved adapters")
    parser.add_argument("--device", default="auto", choices=["auto", "cuda", "mps", "cpu"])
    parser.add_argument("--quantization", default="auto", choices=["auto", "4bit", "none"], help="Saved-adapter inference quantization")
    parser.add_argument("--legacy-file", default="diffusion-model-8B.pth", help="Legacy checkpoint filename")
    parser.add_argument("--legacy-tokenizer", default="meta-llama/Llama-3.2-3B", help="Tokenizer/base-model name for a legacy checkpoint")
    parser.add_argument("--smoke-generate", action="store_true", help="Also run a tiny two-step end-to-end generation check")
    args = parser.parse_args()

    if args.adapter:
        session = load_session(args.adapter, args.outputs_dir, args.device, args.quantization)
        source_name = f"adapter {args.adapter}"
    elif args.legacy_repo:
        session = load_hosted_legacy_session(args.legacy_repo, args.legacy_file, args.legacy_tokenizer, args.device)
        source_name = f"legacy checkpoint {args.legacy_repo}/{args.legacy_file}"
    else:
        session = load_local_legacy_session(args.legacy_checkpoint, args.legacy_tokenizer, args.device)
        source_name = f"local legacy checkpoint {args.legacy_checkpoint}"
    try:
        print(f"PASS: {source_name} loaded and completed its denoising preflight on {session.device} ({session.compute_dtype}, {session.quantization}).")
        if args.smoke_generate:
            text, status = denoise(
                session,
                "Reply with OK.",
                "You are a helpful assistant.",
                max_new_tokens=4,
                num_steps=2,
                noise_level=0.5,
                temperature=0.7,
                top_k=20,
                seed=1234,
            )
            print(f"PASS: smoke generation completed ({status}): {text!r}")
    finally:
        release_session(session)


if __name__ == "__main__":
    main()
