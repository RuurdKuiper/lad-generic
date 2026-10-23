#!/usr/bin/env python3
"""Microbenchmark exact chain decoding on identical fixed candidate potentials."""

import argparse
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import torch
from diffusion_lm.bigram import BigramViterbiSelector
from diffusion_lm.trigram import decode_second_order, sample_second_order


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--device", default="cpu")
    p.add_argument("--length", type=int, default=64)
    p.add_argument("--top-k", type=int, default=16)
    p.add_argument("--repeats", type=int, default=20)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    torch.set_num_threads(1)
    torch.manual_seed(1234)
    device = torch.device(args.device)
    n, k = args.length, args.top_k
    ids = torch.arange(k, device=device)[None, :].expand(n, -1)
    unary = torch.randn(n, k, device=device)
    edges = torch.randn(n - 1, k, k, device=device)
    triples = torch.randn(max(0, n - 2), k, k, k, device=device) * 0.5
    methods = dict(
        bigram_viterbi=lambda: BigramViterbiSelector.decode(ids, unary, edges, 1.0),
        trigram_viterbi=lambda: decode_second_order(ids, unary, edges, triples),
        bigram_sample=lambda: BigramViterbiSelector.sample_sequence(ids, unary, edges),
        trigram_sample=lambda: sample_second_order(ids, unary, edges, triples),
    )

    def sync():
        if device.type == "cuda":
            torch.cuda.synchronize()

    report = dict(
        device=str(device),
        length=n,
        top_k=k,
        repeats=args.repeats,
        threads=1,
        bigram_edge_bytes=edges.numel() * edges.element_size(),
        trigram_additional_bytes=triples.numel() * triples.element_size(),
        methods={},
    )
    for name, run in methods.items():
        for _ in range(3):
            run()
        sync()
        times = []
        for _ in range(args.repeats):
            start = time.perf_counter()
            run()
            sync()
            times.append(1000 * (time.perf_counter() - start))
        report["methods"][name] = dict(
            median_ms=statistics.median(times),
            minimum_ms=min(times),
            maximum_ms=max(times),
        )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
