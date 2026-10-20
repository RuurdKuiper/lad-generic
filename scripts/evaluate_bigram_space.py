#!/usr/bin/env python3
"""Compare hosted Gemma strategies; persist outputs and end-to-end latency.

Compare argmax, conditional, and PMI with matched seeds and settings.
Latency includes queue/network/GPU startup; selector times are synchronized.
"""
import argparse
import difflib
import json
import os
import re
import time
from html.parser import HTMLParser
from pathlib import Path


class Tokens(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tokens, self.inside = [], False
    def handle_starttag(self, tag, attrs):
        if tag == 'span':
            self.inside = True
    def handle_endtag(self, tag):
        if tag == 'span':
            self.inside = False
    def handle_data(self, data):
        if self.inside:
            self.tokens.append(data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--space', default='Ruurd/byod-gemma-2-9b')
    p.add_argument('--lengths', nargs='+', type=int, default=[32, 128])
    p.add_argument('--temperature', type=float, default=1.)
    p.add_argument('--top-k', type=int, default=16)
    p.add_argument('--min-count', type=int, default=5)
    p.add_argument('--pmi-clip', type=float, default=5.)
    p.add_argument('--seeds', nargs='+', type=int, default=[42, 1234])
    p.add_argument('--steps', type=int, default=16)
    p.add_argument('--prompt', default='What do you know about Amsterdam?')
    p.add_argument('--prompts', nargs='+', help='Optional multiple prompts with the same evaluation grid')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    from gradio_client import Client
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    client = Client(args.space, token=os.getenv('HF_TOKEN'), verbose=False)
    endpoints = client.view_api(return_format='dict', print_info=False)['named_endpoints']
    names = [p['parameter_name'] for p in endpoints['/generate']['parameters']]
    if 'bigram_scoring_method' not in names:
        raise RuntimeError('The PMI Space deployment is not ready yet')
    if 'bigram_weight' in names:
        raise RuntimeError('This harness requires the shared temperature/top-k Space deployment')
    rows = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for prompt in args.prompts or [args.prompt]:
        for length in args.lengths:
            for seed in args.seeds:
                baseline_tokens = None
                cases = [('Independent argmax', 'Conditional bigram', 0.),
                         ('Conditional bigram', 'Conditional bigram', args.temperature),
                         ('PMI bigram', 'PMI bigram', args.temperature)]
                baseline_metrics = None
                for configuration, method, temperature in cases:
                    start = time.perf_counter()
                    common = dict(question=prompt, system_prompt='You are a helpful assistant.',
                        max_new_tokens=length, num_steps=args.steps, block_length=length,
                        temperature=temperature, top_k=args.top_k, pause_per_step=0., trajectory_color_mode='No coloring',
                        remasking_strategy='Bigram Viterbi', revisable_tokens=False, ar_check_interval=4,
                        delay_eos_eot=False, early_stopping=False,
                        bigram_scoring_method=method, pmi_min_count=args.min_count, pmi_clip=args.pmi_clip,
                        generation_seed=seed, measure_decoding=True)
                    try:
                        status, html = client.submit(**common, api_name='/generate').result(timeout=300)
                        metrics = json.loads(status.split('Decoding metrics: ', 1)[1])
                        parser = Tokens()
                        parser.feed(html)
                        tokens = parser.tokens
                        text = ''.join(tokens)
                        if temperature == 0:
                            if metrics['changed_predictions'] != 0:
                                raise RuntimeError('The independent argmax baseline must have zero changed predictions')
                            baseline_tokens, baseline_metrics = tokens, metrics
                        words = re.findall(r'\w+', text.lower())
                        row = dict(prompt=prompt, length=length, seed=seed, configuration=configuration, weight=.5, temperature=temperature, top_k=args.top_k,
                            elapsed_seconds=time.perf_counter()-start, status=status, text=text, decoding=metrics,
                            selector_overhead_vs_argmax_ms=metrics['selector_ms']-baseline_metrics['selector_ms'],
                            adjacent_word_repeats=sum(a == b for a, b in zip(words, words[1:])),
                            unique_word_fraction=len(set(words))/max(1, len(words)),
                            final_sequence_difference_from_argmax=1-difflib.SequenceMatcher(a=baseline_tokens, b=tokens).ratio())
                    except Exception as exc:
                        row = dict(prompt=prompt, length=length, seed=seed, configuration=configuration, error=str(exc))
                    rows.append(row)
                    args.output.write_text(json.dumps(dict(space=args.space, steps=args.steps,
                        seeds=args.seeds, temperature=args.temperature, top_k=args.top_k, weight=.5, min_count=args.min_count, pmi_clip=args.pmi_clip,
                        note='Matched prompts/settings/seeds. Same-logit change fraction excludes fixed positions. Timings include synchronization; end-to-end latency also includes allocation/queue/network. Quality diagnostics are not semantic correctness scores.',
                        results=rows), indent=2)+'\n')
                    print(json.dumps(row), flush=True)
                    if 'error' in row:
                        raise RuntimeError(row['error'])


if __name__ == '__main__':
    main()
