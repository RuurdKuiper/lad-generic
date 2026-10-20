#!/usr/bin/env python3
"""Make a shuffled, method-blind reading sheet from saved experiment outputs."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--pending', action='store_true')
    parser.add_argument('--reveal', action='store_true')
    args = parser.parse_args()
    grades = json.loads((args.directory/'manual_reviews.json').read_text()) if args.pending else {}
    manifest = json.loads((args.directory/'manifest.json').read_text())
    rows = [json.loads(line) for line in (args.directory/'results.jsonl').read_text().splitlines()]
    configs = [(m[0],s) for m in manifest['methods'] for s in manifest['steps']]
    random.Random(20261020).shuffle(configs)
    labels = {config:f'C{i+1:02}' for i,config in enumerate(configs)}
    (args.directory/'review_key.json').write_text(json.dumps({label:dict(method=m,steps=s) for (m,s),label in labels.items()},indent=2)+'\n')
    if args.reveal:
        labels = {config:f'{config[0]} / {config[1]} steps' for config in configs}
    review = ['# Saved answers for manual review', '', f'{len(rows)} / {manifest["total"]} answers available.', '',
              ('Configurations are named. Identical answers are grouped within each prompt.' if args.reveal else 'Configuration IDs are shuffled. Mapping is in review_key.json. Identical answers are grouped within each prompt.'), '']
    for task in manifest['tasks'][30:]+manifest['tasks'][:30]:
        matches = [r for r in rows if r['id']==task['id']]
        if args.pending:
            matches = [r for r in matches if hashlib.sha256(r['text'].encode()).hexdigest()[:12] not in grades.get(task['id'], {})]
        if not matches: continue
        review += [f'## {task["id"]}', '', task['prompt'], '']
        grouped = {}
        for row in matches:
            grouped.setdefault(row['text'], []).append(labels[row['method'],row['steps']])
        for text, ids in sorted(grouped.items(), key=lambda pair: min(pair[1])):
            digest = hashlib.sha256(text.encode()).hexdigest()
            if args.pending and digest[:12] in grades.get(task['id'], {}): continue
            counts = sorted({int(re.search(r'(\d+) output tokens', r['status'])[1]) for r in matches if r['text']==text})
            review += [f'### {", ".join(sorted(ids))} · {digest[:12]} · visible tokens {counts}', '', '````text', text, '````', '']
    (args.directory/('pending_review.md' if args.pending else ('answers_labeled.md' if args.reveal else 'answers_blind.md'))).write_text('\n'.join(review))
    print(json.dumps(dict(responses=len(rows),unique_prompt_answers=len({(r['id'],r['text']) for r in rows}))))


if __name__ == '__main__':
    main()
