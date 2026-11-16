"""Migrate the completed pilot to immutable, original-adapter campaign inputs."""
import ast,hashlib,json,shutil,sys
from pathlib import Path
from prepare import snapshot_code
from protocol import digest
HERE=Path(__file__).resolve().parent

def main():
    old=HERE/'bundle';out=HERE/'campaign_bundle';out.mkdir(exist_ok=True);plan=json.loads((old/'plan.json').read_text());parent=plan.pop('plan_id')
    final=HERE/'pilot_runs/6af05e99e6320c66fad74a2a'
    for name in ['examples.jsonl','reuse.jsonl']:shutil.copy2(old/name,out/name)
    shutil.copy2(final/'results.jsonl',out/'resume.jsonl')
    plan['resume_sha256']=hashlib.sha256((out/'resume.jsonl').read_bytes()).hexdigest();plan['resume_parent_plan_ids']=[parent]
    plan['resume_source']=json.loads((final/'download_manifest.json').read_text());plan['execution']='resumable_original_adapter_expansion'
    plan['source_policy']='Original checkpoint assets verified by SHA-256 before BYOD generation; unchanged frozen datasets and decoding; checkpointed per-question continuation'
    plan['pilot_checkpoint_note']='Pilot compatibility gate permits input validation; campaign worker additionally requires original asset hashes before any BYOD generation.'
    plan['campaign_original_assets_required']=True;plan['campaign_compute_ceiling_usd']=75
    for key,spec in plan['models'].items():
        if spec['method']=='diffusion' and key!='llada':
            for name in ['adapter_repo','adapter_revision','published_config_matches_original']:spec.pop(name,None)
            spec['original_asset_model_key']=key
    plan['code_hashes']=snapshot_code(out)
    shutil.copy2(HERE/'campaign_worker.py',out/'campaign_worker.py')
    plan['code_hashes']['campaign_worker.py']=hashlib.sha256((out/'campaign_worker.py').read_bytes()).hexdigest()
    # Generated/scored pilot answers are reusable only while the underlying
    # scorer and generation source remain identical.
    previous=json.loads((old/'plan.json').read_text())
    for name,h in previous['code_hashes'].items():
        if name.startswith('code/') and plan['code_hashes'][name]!=h:raise ValueError('Pilot scoring/generation source changed: '+name)
    plan['plan_id']=digest(plan);(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    from worker import verify
    from campaign_worker import validated_rows
    verify(out,phase='pilot');rows=validated_rows([json.loads(s) for s in (out/'resume.jsonl').read_text().split('\n') if s.strip()],plan,[json.loads(s) for s in (out/'examples.jsonl').read_text().split('\n') if s.strip()])
    print(json.dumps({'plan_id':plan['plan_id'],'imported_scored_rows':len(rows),'completed_new_predictions':sum(r['source']=='new_generation' for r in rows.values()),'target_per_task':250,'target_all_models':21640,'original_assets_required':True},indent=2))
if __name__=='__main__':main()
