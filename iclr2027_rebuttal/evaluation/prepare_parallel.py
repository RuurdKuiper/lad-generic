"""Split remaining work by model into disjoint, independently capped queues."""
import hashlib,json,shutil
from pathlib import Path
from protocol import digest
from worker import read_rows,verify
from campaign_worker import validated_rows
HERE=Path(__file__).resolve().parent

def main():
    seed=HERE/'remaining_bundle';root=HERE/'parallel_bundles'
    if root.exists():raise RuntimeError('Parallel bundles exist; keep frozen inputs immutable')
    root.mkdir();original=json.loads((seed/'plan.json').read_text());resume=read_rows(seed/'resume.jsonl');examples=read_rows(seed/'examples.jsonl')
    groups={'gemma':['gemma_d'],'others':[k for k in original['models'] if k!='gemma_d']};seen=set();summary={}
    for lane,keys in groups.items():
        out=root/lane;shutil.copytree(seed,out);plan=json.loads((out/'plan.json').read_text());parent=plan.pop('plan_id')
        plan['models']={k:plan['models'][k] for k in keys};rows=[r for r in resume if r['model_key'] in keys]
        identities={(r['model_key'],r['fingerprint']) for r in rows}
        if seen&identities:raise ValueError('Overlapping lane outcomes')
        seen.update(identities)
        (out/'resume.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
        plan.update(execution='parallel_remaining_'+lane,parallel_lane=lane,parent_remaining_plan_id=parent,
                    expected_remaining=sum(original['empirical_generation_estimates'][k]['missing'] for k in keys),
                    empirical_generation_estimates={k:original['empirical_generation_estimates'][k] for k in keys},
                    resume_parent_plan_ids=sorted({r['plan_id'] for r in rows}),max_gpu_timeout_seconds=18000,additional_compute_ceiling_usd=12.75)
        plan['resume_sha256']=hashlib.sha256((out/'resume.jsonl').read_bytes()).hexdigest();plan['plan_id']=digest(plan)
        (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');verify(out,phase='pilot');checked=validated_rows(rows,plan,examples)
        summary[lane]={'plan_id':plan['plan_id'],'models':keys,'saved':len(checked),'remaining':plan['expected_remaining'],'generation_hours':sum(v['estimated_generation_seconds'] for v in plan['empirical_generation_estimates'].values())/3600,'cash_ceiling_usd':12.75,'max_gpu_hours':5}
    assert len(seen)==14342 and sum(s['remaining'] for s in summary.values())==1658
    (root/'manifest.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
