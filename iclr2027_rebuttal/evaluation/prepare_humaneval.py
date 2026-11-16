"""Prepare only the deferred HumanEval corrections; do not resume other tasks."""
import hashlib,json,shutil
from pathlib import Path
from protocol import digest
from worker import read_rows,verify
HERE=Path(__file__).resolve().parent

def main():
    old=HERE/'campaign_bundle';out=HERE/'humaneval_bundle'
    if out.exists():raise RuntimeError('HumanEval bundle exists; preserve immutable inputs')
    out.mkdir();plan=json.loads((old/'plan.json').read_text());parent=plan.pop('plan_id')
    shutil.copytree(old/'code',out/'code')
    shutil.copy2(HERE.parents[1]/'src/diffusion_lm/benchmarks.py',out/'code/src/diffusion_lm/benchmarks.py')
    for name in ['protocol.py','worker.py','report.py','requirements.txt','campaign_worker.py']:shutil.copy2(HERE/name,out/name)
    examples=[r for r in read_rows(old/'examples.jsonl') if r['task']=='humaneval'];fps={r['fingerprint'] for r in examples}
    reuse=[r for r in read_rows(old/'reuse.jsonl') if r['model_key']=='qwen_ar' and r['fingerprint'] in fps]
    for name,rows in [('examples.jsonl',examples),('reuse.jsonl',reuse),('resume.jsonl',[])]:
        (out/name).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    plan['models']={k:plan['models'][k] for k in ['qwen_ar','gemma_d']}
    for spec in plan['models'].values():spec['settings']={'humaneval':spec['settings']['humaneval']}
    plan['models']['qwen_ar'].update(attention_backend='sdpa',verify_ar_replay=True)
    plan['models']['gemma_d'].update(attention_backend='sdpa',fresh_environment_cohort=True)
    plan.update(execution='priority_humaneval_corrected_qwen_and_fresh_gemma',model_priority=['qwen_ar','gemma_d'],
                source_policy='Only HumanEval: retain verified historical Qwen outputs and replace eager additions; Gemma fresh full 164; unchanged output budgets',
                parent_plan_id_for_audit_only=parent,resume_parent_plan_ids=[],active_tasks=['humaneval'],deferred_tasks=[],campaign_additional_compute_ceiling_usd=6)
    plan.pop('resume_source',None)
    for name,key in [('examples.jsonl','examples_sha256'),('reuse.jsonl','reuse_sha256'),('resume.jsonl','resume_sha256')]:plan[key]=hashlib.sha256((out/name).read_bytes()).hexdigest()
    names=['protocol.py','worker.py','report.py','requirements.txt','campaign_worker.py']
    plan['code_hashes']={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted([*(out/'code').rglob('*.py'),*(out/n for n in names)])}
    plan['plan_id']=digest(plan);(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');verify(out,phase='pilot')
    assert len(examples)==164 and len(reuse)==95
    print(json.dumps({'plan_id':plan['plan_id'],'target_scored_outcomes':328,'qwen_historical_reuse_candidates':95,'qwen_new_replacements':69,'gemma_fresh_generations':164,'total_new_generations':233},indent=2))

if __name__=='__main__':main()
