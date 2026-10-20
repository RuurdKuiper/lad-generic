#!/usr/bin/env python3
"""Check whole-answer block stopping and compare bigram ending-delay strengths."""
import argparse
import json
import os
from html.parser import HTMLParser
from pathlib import Path


class PlainOutput(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.text = ''
    def handle_starttag(self, tag, attrs):
        if tag == 'textarea': self.active = True
    def handle_endtag(self, tag):
        if tag == 'textarea': self.active = False
    def handle_data(self, data):
        if self.active: self.text += data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--space', default='Ruurd/byod-gemma-2-9b')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from dotenv import load_dotenv
    from gradio_client import Client
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    client = Client(args.space, token=os.getenv('HF_TOKEN'), verbose=False)
    names = [p['parameter_name'] for p in client.view_api(print_info=False, return_format='dict')['named_endpoints']['/generate']['parameters']]
    if 'bigram_eos_delay_penalty' not in names:
        raise RuntimeError('The ending-control deployment is not ready')
    rows = []
    cases = []
    for method in ['Conditional bigram', 'PMI bigram']:
        for early in [True, False]:
            cases.append(dict(case='block_stopping', method=method, early=early, delay=True, strength=10.,
                prompt='What is 2 + 2? Answer with only the number.', tokens=64, block=16, steps=16))
        for name, delay, strength in [('delay_off', False, 10.), ('retention_only', True, 1.), ('fading_penalty', True, 10.)]:
            cases.append(dict(case=name, method=method, early=True, delay=delay, strength=strength,
                prompt='What do you know about Amsterdam?', tokens=128, block=64, steps=32))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        status, html = client.submit(question=case['prompt'], system_prompt='You are a helpful assistant.',
            max_new_tokens=case['tokens'], num_steps=case['steps'], block_length=case['block'],
            temperature=1., top_k=16, pause_per_step=0., trajectory_color_mode='No coloring',
            remasking_strategy='Bigram Viterbi', revisable_tokens=False, ar_check_interval=4,
            delay_eos_eot=case['delay'], early_stopping=case['early'],
            bigram_scoring_method=case['method'], generation_seed=42, measure_decoding=True,
            bigram_eos_delay_penalty=case['strength'], api_name='/generate').result(timeout=300)
        metrics = json.loads(status.split('Decoding metrics: ', 1)[1])
        plain = PlainOutput(); plain.feed(html)
        row = dict(**case, text=plain.text, status=status, decoding=metrics,
                   words=len(plain.text.split()), skipped_forwards=case['steps']-metrics['selector_calls'])
        rows.append(row)
        args.output.write_text(json.dumps(dict(space=args.space, seed=42, weight=.5, temperature=1., top_k=16, results=rows), indent=2)+'\n')
        print(json.dumps(row), flush=True)
        if case['case'] == 'block_stopping':
            assert plain.text.strip().rstrip('.') == '4'  # Allow harmless final punctuation in this stopping check.
            if case['early']:
                assert metrics['selector_calls'] < case['steps'] and 'remaining blocks skipped' in status
            else:
                assert metrics['selector_calls'] == case['steps']


if __name__ == '__main__':
    main()
