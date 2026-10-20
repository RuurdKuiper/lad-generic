#!/usr/bin/env python3
"""Measure selector overhead on synthetic emissions. This does not measure model quality.

Optionally replay captured Gemma logits from a weights-only .pt file containing
'logits' [B,V]. Synthetic cases use the checkpoint vocabulary and a fixed seed.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from diffusion_lm.bigram import BigramScorer, BigramViterbiSelector


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--device', default='cpu')
    p.add_argument('--lengths', nargs='+', type=int, default=[1, 8, 32, 128, 256])
    p.add_argument('--weights', nargs='+', type=float, default=[0., 0.25, 0.5, 1.])
    p.add_argument('--methods', nargs='+', choices=['conditional', 'pmi'], default=['conditional', 'pmi'])
    p.add_argument('--remasking-confidences', nargs='+', choices=['diffusion', 'viterbi_margin'], default=['diffusion'])
    p.add_argument('--min-count', type=int, default=5)
    p.add_argument('--pmi-clip', type=float, default=5.)
    p.add_argument('--repeats', type=int, default=10)
    p.add_argument('--logits', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    torch.set_num_threads(1)
    torch.manual_seed(42)
    model = BigramScorer.load(args.checkpoint, device=args.device)
    def timed(fn):
        samples = []
        for _ in range(args.repeats + 1):
            if args.device.startswith('cuda'):
                torch.cuda.synchronize()
            start = time.perf_counter()
            result = fn()
            if args.device.startswith('cuda'):
                torch.cuda.synchronize()
            samples.append((time.perf_counter() - start) * 1000)
        return result, sum(samples[1:]) / args.repeats
    rows = []
    with torch.inference_mode():
        captured = torch.load(args.logits, weights_only=True, map_location=args.device)['logits'] if args.logits else None
        for length in args.lengths:
            logits = captured[:length] if captured is not None else torch.randn(length, model.vocab_size, device=args.device)
            if len(logits) != length:
                raise ValueError('Captured logits do not cover requested block length')
            (emissions, candidates), topk_ms = timed(lambda: logits.float().log_softmax(-1).topk(16, dim=-1))
            baseline = logits.argmax(-1)
            _, baseline_ms = timed(lambda: logits.argmax(-1))
            for method in args.methods:
                transitions, matrix_ms = timed(lambda: model(candidates, emissions,
                    scoring_method=method, min_count=args.min_count, pmi_clip=args.pmi_clip))
                for weight in args.weights:
                    for confidence_mode in args.remasking_confidences:
                        selector = BigramViterbiSelector(model, weight, scoring_method=method,
                            min_count=args.min_count, pmi_clip=args.pmi_clip, remasking_confidence=confidence_mode)
                        decode_ms = 0.0
                        decoded = selector.decode(candidates, emissions, transitions, weight)
                        if weight:
                            decoded, decode_ms = timed(lambda: selector.decode(candidates, emissions, transitions, weight))
                        margin_ms = 0.0
                        if confidence_mode == 'viterbi_margin':
                            _, margin_ms = timed(lambda: selector.path_margins(candidates, emissions, transitions, decoded, weight))
                        (selected, _), total_ms = timed(lambda: selector.select_block(logits, baseline, torch.ones(length, dtype=torch.bool, device=args.device)))
                        rows.append(dict(length=length, scoring_method=method, remasking_confidence=confidence_mode,
                            weight=weight, topk_ms=topk_ms, matrix_ms=matrix_ms, decode_ms=decode_ms,
                            margin_ms=margin_ms, total_selector_ms=total_ms, argmax_ms=baseline_ms,
                            overhead_vs_argmax_ms=total_ms-baseline_ms,
                            changed_fraction=float((selected != baseline).float().mean())))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(device=args.device, min_count=args.min_count, pmi_clip=args.pmi_clip, torch=torch.__version__, seed=42,
        emissions='captured' if args.logits else 'synthetic Gaussian; not a quality evaluation', results=rows), indent=2)+'\n')
    print(args.output)


if __name__ == '__main__':
    main()
