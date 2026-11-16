"""Freeze separate corrected cohorts without mutating the active campaign."""
import hashlib,json,shutil
from pathlib import Path
from protocol import digest
from worker import verify,read_rows
HERE=Path(__file__).resolve().parent

def main():
    old=HERE/'campaign_bundle';out=HERE/'correction_bundle'
    if out.exists():raise RuntimeError('Correction bundle exists; preserve immutable inputs')
    out.mkdir();plan=json.loads((old/'plan.json').read_text());parent=plan.pop('plan_id')
    shutil.copytree(old/'code',out/'code')
    for name in ['protocol.py','worker.py','report.py','requirements.txt','campaign_worker.py']:
        shutil.copy2(HERE/name,out/name)
    # Historical snippets are references only for Gemma. None are adopted as
    # outcomes in its fresh cohort; Qwen may reuse verified historical outputs.
    examples=[e for e in read_rows(old/'examples.jsonl') if e['task']!='humaneval']
    fingerprints={e['fingerprint'] for e in examples}
    reuse=[r for r in read_rows(old/'reuse.jsonl') if r['model_key']=='qwen_ar' and r['fingerprint'] in fingerprints]
    for filename,rows in [('examples.jsonl',examples),('reuse.jsonl',reuse),('resume.jsonl',[])]:
        (out/filename).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    plan['models']={k:plan['models'][k] for k in ['qwen_ar','gemma_d']}
    plan['models']['qwen_ar'].update(attention_backend='sdpa',verify_ar_replay=True)
    plan['models']['gemma_d'].update(attention_backend='sdpa',fresh_environment_cohort=True)
    plan['execution']='corrected_qwen_sdpa_and_fresh_gemma_non_humaneval'
    plan['model_priority']=['qwen_ar','gemma_d']
    plan['supersedes_parent_for']={'qwen_ar':'All newly generated non-HumanEval outcomes; historical outputs require AR replay verification','gemma_d':'Fresh non-HumanEval cohort; historical predictions retained separately, never pooled here'}
    plan['source_policy']='Original weights verified; Qwen SDPA matched probes; Gemma full fresh cohort after stable cross-environment mismatch; no HumanEval reruns'
    plan['parent_plan_id_for_audit_only']=parent
    plan['resume_parent_plan_ids']=[];plan.pop('resume_source',None)
    plan['campaign_compute_ceiling_usd']=18
    plan['deferred_tasks']=['humaneval']
    for name,key in [('examples.jsonl','examples_sha256'),('reuse.jsonl','reuse_sha256'),('resume.jsonl','resume_sha256')]:plan[key]=hashlib.sha256((out/name).read_bytes()).hexdigest()
    plan['code_hashes']={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted([*(out/'code').rglob('*.py'),*(out/n for n in ['protocol.py','worker.py','report.py','requirements.txt','campaign_worker.py'])])}
    plan['plan_id']=digest(plan);(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    verify(out,phase='pilot')
    assert len(examples)==2000 and len(reuse)==1000
    print(json.dumps({'plan_id':plan['plan_id'],'target_items':4000,'qwen_historical_reuse_candidates':len(reuse),'gemma_fresh_items':len(examples),'new_generations':3000,'deferred_tasks':['humaneval']},indent=2))

if __name__=='__main__':main()
