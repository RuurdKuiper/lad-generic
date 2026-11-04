#!/usr/bin/env python3
"""Validate canonical eight-arm evidence and recompute descriptive study metrics.

Default: read-only verification against the saved final summary. --output writes
a fresh descriptive summary to a new file; historical bootstrap/report generation
is preserved separately in the verified research archive.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'artifacts/bigram/llada_ngram_settings_full'
CATEGORIES = ('open', 'code', 'math')


def analyze(folder):
    raw = [json.loads(line) for line in (folder / 'combined_results.jsonl').read_text().splitlines()]
    with (folder / 'combined_scores.csv').open() as stream:
        scores = list(csv.DictReader(stream))
    rows = {r['key']: r for r in raw}
    if len(rows) != len(raw) or len({r['key'] for r in scores}) != len(scores):
        raise ValueError('Duplicate result or score keys')
    if set(rows) != {r['key'] for r in scores} or len(raw) != 2256:
        raise ValueError('Expected 2,256 matched results with one score each')
    reviews = {}
    code_checks = {}
    for source in (folder, folder / 'randomized'):
        for key, value in json.loads((source / 'reviews.json').read_text()).items():
            reviews[(source.name, key)] = value
        for key, value in json.loads((source / 'code_checks.json').read_text()).items():
            code_checks[(source.name, key)] = value
    cases = {}
    for score in scores:
        row = rows[score['key']]
        digest = hashlib.sha256(row['text'].encode()).hexdigest()
        if digest != row['sha256'] or digest != score['sha256']:
            raise ValueError(f'Text/score checksum mismatch: {row["key"]}')
        for field in ('task', 'category', 'method'):
            if row[field] != score[field]:
                raise ValueError(f'Result/score {field} mismatch: {row["key"]}')
        if int(score['steps']) != row['steps'] or row['inference']['denoising_forward_passes'] != row['steps']:
            raise ValueError(f'Forward-budget mismatch: {row["key"]}')
        source = 'randomized' if row['method'] == 'trigram_randomized' else folder.name
        if row['category'] == 'code':
            judgment = code_checks[(source, row['key'])]
            normalized = float(judgment['all_pass'])
        else:
            review_id = hashlib.sha256((row['task'] + ':' + digest).encode()).hexdigest()[:12]
            # The extension reused existing exact-text judgments where available.
            judgment = reviews.get((source, review_id), reviews.get((folder.name, review_id)))
            if judgment is None:
                raise ValueError(f'Missing judgment: {row["key"]}')
            normalized = judgment['score'] / 3 if row['category'] == 'open' else float(judgment['answer_correct'])
        if judgment['sha256'] != digest or int(score['score']) != judgment['score'] or not math.isclose(float(score['normalized']), normalized):
            raise ValueError(f'Judgment mismatch: {row["key"]}')
        if not math.isclose(float(score['server_ms']), row['inference']['elapsed_ms']):
            raise ValueError(f'Timing mismatch: {row["key"]}')
        cases.setdefault(score['method'], set()).add((score['task'], score['steps']))
    if len(cases) != 8 or any(len(c) != 282 for c in cases.values()) or any(c != next(iter(cases.values())) for c in cases.values()):
        raise ValueError('Expected eight methods on the same 282 prompt/NFE cases')
    groups = []
    for budget in (None, 4, 8, 16, 32, 64, 128):
        for method in sorted(cases):
            selected = [r for r in scores if r['method'] == method and (budget is None or int(r['steps']) == budget)]
            group = dict(budget=budget, method=method)
            for category in CATEGORIES:
                subset = [r for r in selected if r['category'] == category]
                group[category] = dict(n=len(subset), mean_grade=mean(float(r['score']) for r in subset),
                                       mean_normalized=mean(float(r['normalized']) for r in subset))
            group['macro_score'] = mean(group[c]['mean_normalized'] for c in CATEGORIES)
            group['latency_ms'] = mean(float(r['server_ms']) for r in selected)
            groups.append(group)
    published = json.loads((folder / 'combined_summary.json').read_text())
    indexed = {(g['budget'], g['method']): g for g in published['groups']}
    for group in groups:
        expected = indexed[(group['budget'], group['method'])]
        for category in CATEGORIES:
            for field, value in group[category].items():
                if not math.isclose(value, expected[category][field], rel_tol=1e-9, abs_tol=1e-9):
                    raise ValueError(f'Published {category}/{field} differs: {group["method"]}/{group["budget"]}')
        for field in ('macro_score', 'latency_ms'):
            if not math.isclose(group[field], expected[field], rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError(f'Published {field} differs: {group["method"]}/{group["budget"]}')
    return dict(results=len(raw), methods=len(cases), matched_cases=282,
                descriptive_groups=groups,
                validation='Text, judgments, timing, matched coverage, and published descriptive metrics agree.',
                scope='Historical bootstrap intervals are retained in combined_summary.json; regenerate those using the archived analysis code.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, default=STUDY)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = analyze(args.study)
    if args.output:
        with args.output.open('x') as stream:
            stream.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'descriptive_groups'}, indent=2))


if __name__ == '__main__':
    main()
