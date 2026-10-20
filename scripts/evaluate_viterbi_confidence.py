#!/usr/bin/env python3
"""Compare optional Viterbi-margin remasking with diffusion-probability remasking."""
import argparse
import json
import os
from pathlib import Path

from evaluate_ending_controls import PlainOutput


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
    if 'bigram_remasking_confidence' not in names:
        raise RuntimeError('The Viterbi confidence deployment is not ready')
    rows = []
    cases = []
    for method in ['Conditional bigram', 'PMI bigram']:
        for mode in ['Diffusion probability', 'Viterbi path margin']:
            for prompt in ['What do you know about Amsterdam?', 'Explain why the sky looks blue.']:
                for length in [32, 128]:
                    cases.append(dict(method=method, mode=mode, prompt=prompt, tokens=length, block=length, early=False, steps=16))
            cases.append(dict(method=method, mode=mode, prompt='What is 2 + 2? Answer with only the number.',
                              tokens=64, block=16, early=True, steps=16))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for case in cases:
        options = {}
        # Omitting the new input verifies backward compatibility/default behavior.
        if case['mode'] != 'Diffusion probability':
            options['bigram_remasking_confidence'] = case['mode']
        status, html = client.submit(question=case['prompt'], system_prompt='You are a helpful assistant.',
            max_new_tokens=case['tokens'], num_steps=case['steps'], block_length=case['block'],
            temperature=1., top_k=16, pause_per_step=0., trajectory_color_mode='Prediction probability',
            remasking_strategy='Bigram Viterbi', revisable_tokens=False, ar_check_interval=4,
            delay_eos_eot=True, early_stopping=case['early'],
            bigram_scoring_method=case['method'], generation_seed=42, measure_decoding=True,
            bigram_eos_delay_penalty=10., **options, api_name='/generate').result(timeout=300)
        metrics = json.loads(status.split('Decoding metrics: ', 1)[1])
        plain = PlainOutput(); plain.feed(html)
        row = dict(**case, text=plain.text, status=status, decoding=metrics)
        rows.append(row)
        args.output.write_text(json.dumps(dict(space=args.space, seed=42, weight=.5, temperature=1., top_k=16, results=rows), indent=2)+'\n')
        print(json.dumps(row), flush=True)
        assert ('Viterbi-margin remasking' in status) == (case['mode'] == 'Viterbi path margin')
        if case['early']:
            assert metrics['selector_calls'] < case['steps'] and 'remaining blocks skipped' in status
            assert plain.text.strip().rstrip('.') == '4'
        else:
            assert metrics['selector_calls'] == case['steps']


if __name__ == '__main__':
    main()
