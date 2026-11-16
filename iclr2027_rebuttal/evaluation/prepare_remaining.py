"""Resume only missing non-HumanEval outcomes from the adopted corrected cohort."""
import hashlib,json,math,shutil,statistics
from pathlib import Path
from protocol import digest
from worker import read_rows,verify
from campaign_worker import validated_rows
HERE=Path(__file__).resolve().parent

def main():
    old=HERE/'campaign_bundle';out=HERE/'remaining_bundle';audit_dir=HERE/'generation_diagnostic/nov15_gemma'
    if out.exists():raise RuntimeError('Remaining bundle exists; preserve immutable inputs')
    audit=json.loads((audit_dir/'assembled_audit.json').read_text())
    scorer=HERE.parents[1]/'src/diffusion_lm/benchmarks.py'
    if hashlib.sha256(scorer.read_bytes()).hexdigest()!=audit['scorer_sha256']:raise ValueError('Rescore saved answers before preparing a changed scorer')
    examples=[e for e in read_rows(old/'examples.jsonl') if e['task']!='humaneval']
    plan=json.loads((old/'plan.json').read_text());parent=plan.pop('plan_id');selected=read_rows(audit_dir/'assembled_results.jsonl')
    done={(r['model_key'],r['fingerprint']) for r in selected}
    missing={key:[e for e in examples if (key,e['fingerprint']) not in done] for key in plan['models']}
    keys=[key for key,items in missing.items() if items]
    rows=[r for r in selected if r['model_key'] in keys and r['task']!='humaneval']
    estimated={}
    for key in keys:
        seconds=0
        for task in {e['task'] for e in missing[key]}:
            timings=[r['generation_seconds'] for r in rows if r['model_key']==key and r['task']==task and r['source']=='new_generation' and r['generation_seconds']>0]
            if not timings:raise ValueError('Missing empirical generation timing: '+key+'/'+task)
            seconds+=sum(e['task']==task for e in missing[key])*statistics.mean(timings)
        estimated[key]={'missing':len(missing[key]),'estimated_generation_seconds':seconds}
    out.mkdir();shutil.copytree(old/'code',out/'code');shutil.copy2(scorer,out/'code/src/diffusion_lm/benchmarks.py')
    for name in ['protocol.py','worker.py','report.py','requirements.txt','campaign_worker.py']:shutil.copy2(HERE/name,out/name)
    for name,data in [('examples.jsonl',examples),('reuse.jsonl',[]),('resume.jsonl',rows)]:
        (out/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in data))
    plan['models']={key:plan['models'][key] for key in keys}
    for key,spec in plan['models'].items():
        spec['settings']={t:s for t,s in spec['settings'].items() if t!='humaneval'}
        if key=='gemma_d':spec.update(attention_backend='sdpa',fresh_environment_cohort=True)
    plan.update(execution='complete_remaining_non_humaneval_from_adopted_cohorts',active_tasks=list(dict.fromkeys(e['task'] for e in examples)),
                deferred_tasks=['humaneval_handled_in_separate_active_plan'],resume_parent_plan_ids=sorted({r['plan_id'] for r in rows}),
                parent_plan_id_for_audit_only=parent,source_policy='Reuse adopted scored outcomes without regeneration; verified originals and unchanged decoding; fresh Gemma cohort; corrected MATH scorer',
                expected_remaining=sum(len(missing[k]) for k in keys),empirical_generation_estimates=estimated,selection_policy=audit['selection_policy'],
                assembly_source_revision=audit['source']['revision'],max_gpu_timeout_seconds=36000,additional_compute_ceiling_usd=25.5)
    plan.pop('resume_source',None)
    for name,key in [('examples.jsonl','examples_sha256'),('reuse.jsonl','reuse_sha256'),('resume.jsonl','resume_sha256')]:plan[key]=hashlib.sha256((out/name).read_bytes()).hexdigest()
    names=['protocol.py','worker.py','report.py','requirements.txt','campaign_worker.py']
    plan['code_hashes']={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted([*(out/'code').rglob('*.py'),*(out/n for n in names)])}
    plan['plan_id']=digest(plan);(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');verify(out,phase='pilot')
    checked=validated_rows(rows,plan,examples)
    assert len(checked)==14342 and plan['expected_remaining']==1658 and len(keys)==8
    print(json.dumps({'plan_id':plan['plan_id'],'resumed_outcomes':len(checked),'target_outcomes':len(examples)*len(keys),'remaining':plan['expected_remaining'],'estimated_generation_hours':sum(v['estimated_generation_seconds'] for v in estimated.values())/3600,'models':estimated},indent=2))

if __name__=='__main__':main()
