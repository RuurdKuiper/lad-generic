#!/usr/bin/env python3
"""Aggregate explicitly recorded manual judgments, requiring complete coverage."""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
import statistics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.directory/'manifest.json').read_text())
    total = manifest['total']
    rows = [json.loads(x) for x in (args.directory/'results.jsonl').read_text().splitlines()]
    judgments = json.loads((args.directory/'manual_reviews.json').read_text())
    reviewed, missing = [], []
    for row in rows:
        digest = hashlib.sha256(row['text'].encode()).hexdigest()[:12]
        grade = judgments.get(row['id'], {}).get(digest)
        if grade is None:
            missing.append(dict(id=row['id'], digest=digest))
            continue
        assert grade['score'] in [0,1,2,3] and isinstance(grade['complete'], bool) and grade['note']
        reviewed.append(dict(key=row['key'], id=row['id'], task=row['task'], method=row['method'], steps=row['steps'],
            digest=digest, **grade, wall_seconds=row['wall_seconds'],
            visible_tokens=int(re.search(r'(\d+) output tokens', row['status'])[1]),
            hit_token_cap=int(re.search(r'(\d+) output tokens', row['status'])[1]) == row['options']['max_new_tokens'],
            mean_selector_ms=(row['metrics'] or {}).get('mean_selector_ms'),
            changed_fraction=(row['metrics'] or {}).get('changed_fraction')))
    if reviewed:
        fields=list(dict.fromkeys(k for row in reviewed for k in row))
        with (args.directory/'manual_scores.csv').open('w') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(reviewed)
    groups=[]
    for task in ['code','open']:
        for steps in [128,64,32]:
            for method in ['confidence','conditional_diffusion','pmi_diffusion','conditional_margin','pmi_margin']:
                sample=[r for r in reviewed if (r['task'],r['steps'],r['method'])==(task,steps,method)]
                if not sample:continue
                group=dict(task=task,steps=steps,method=method,n=len(sample),mean_score=statistics.mean(r['score'] for r in sample),
                    full_score=sum(r['score']==3 for r in sample),
                    strict_full_score=sum(r['score']==3 and not r.get('algorithm_issue',False) for r in sample),
                    full_complete_score=sum(r['score']==3 and r['complete'] for r in sample),complete=sum(r['complete'] for r in sample),
                    format_issues=sum(r.get('format_issue',False) for r in sample),
                    hit_token_cap=sum(r['hit_token_cap'] for r in sample),
                    mean_visible_tokens=statistics.mean(r['visible_tokens'] for r in sample),
                    mean_wall_seconds=statistics.mean(r['wall_seconds'] for r in sample))
                for metric in ['mean_selector_ms','changed_fraction']:
                    values=[r[metric] for r in sample if r[metric] is not None]
                    group[metric]=statistics.mean(values) if values else None
                groups.append(group)
    summary=dict(complete=len(rows)==total and len(reviewed)==total,total=total,generated=len(rows),reviewed=len(reviewed),missing_reviews=list({(m['id'],m['digest']):m for m in missing}.values()),groups=groups)
    (args.directory/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(dict(generated=len(rows),reviewed=len(reviewed),unreviewed_unique=len(summary['missing_reviews']))))


if __name__=='__main__':main()
