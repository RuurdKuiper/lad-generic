#!/usr/bin/env python3
"""Render manually curated examples with verbatim answers and current metrics."""
import argparse
import json
from pathlib import Path


def render(directory):
    manifest = json.loads((directory/'manifest.json').read_text())
    model = 'LLaDA-8B-Instruct' if 'llada' in manifest['space'].lower() else 'Gemma'
    rows = {r['key']:r for r in map(json.loads,(directory/'results.jsonl').read_text().splitlines())}
    scores = {r['key']:r for r in map(json.loads,(directory/'scores.jsonl').read_text().splitlines())}
    diversity = json.loads((directory/'diversity.json').read_text())['results']
    curated = json.loads((directory/'representative_examples.json').read_text())['examples']
    assert len(curated) == len({c['key'] for c in curated}) == len(manifest['steps'])*6
    lines = ['## Representative examples by NFE and decoding method', '',
        f"Both methods use the same {model} model. These examples come from the "
        f"{len(manifest['prompts'])}-question, {manifest['shared']['max_new_tokens']}-token-limit experiment.", '',
        'I read all saved answers and selected a good, average, and bad example '
        'within each method/NFE group. Selection considers readability, relevance, '
        'coherence, repetition, and obvious content problems; it is not based on '
        'perplexity rank and is not a comprehensive factual audit. Average means '
        'typical of the group, not the mathematical median. Selections are made '
        'independently within each group, so prompts can differ between methods.', '',
        '**The labels are relative.** Good means one of the stronger answers in '
        'that group, not necessarily an acceptable answer. At low NFE even good '
        'examples can be flawed; at high NFE a bad example can still be mostly '
        'fluent. These are illustrative selections, not a separate benchmark score.', '',
        'Full outputs are quoted verbatim, including duplicated words, punctuation, '
        'line breaks, and unfinished endings. PPL is per-answer Phi-4 perplexity. '
        'Distinct-1 is unique token types / total tokens in the complete answer, '
        'using the model’s native tokenizer and excluding special tokens. '
        'Unique-token counts are shown alongside the ratios.', '']
    names = {'confidence':'Confidence-guided baseline',
             'pmi_diffusion':'PMI Viterbi + diffusion confidence'}
    for n in manifest['steps']:
        lines += [f'### NFE {n}', '']
        for method,name in names.items():
            selected = [c for c in curated if rows[c['key']]['steps']==n and rows[c['key']]['method']==method]
            assert len(selected)==3 and {c['grade'] for c in selected}=={'Good','Average','Bad'}
            lines += [f'#### {name}', '']
            for c in selected:
                row = rows[c['key']]; score = scores[c['key']]; d = diversity[c['key']]
                lines += [f"**{c['grade']} example — question {row['prompt_id']}**", '',
                    f"**Prompt:** {row['prompt']}", '',
                    f"**Metrics:** PPL {score['perplexity']:.2f}; Distinct-1 {d['distinct_1']:.3f}; "
                    f"{d['unique_tokens']}/{d['tokens']} unique token types / total tokens.", '',
                    f"**Selection note:** {c['reason']}", '',
                    '\n'.join('> '+line if line else '>' for line in row['text'].split('\n')), '']
    (directory/'REPRESENTATIVE_EXAMPLES.md').write_text('\n'.join(lines)+'\n')
    print(f'Rendered {len(curated)} examples for {model}.')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    render(parser.parse_args().directory)
