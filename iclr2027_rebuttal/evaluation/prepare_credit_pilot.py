"""Prepare the approved Gemma-first continuation; does not launch compute."""
import ast,base64,hashlib,io,json,shutil,sys,zipfile
from pathlib import Path
from prepare import snapshot_code
from protocol import digest
HERE=Path(__file__).resolve().parent

def function_ast(path,name):
    module=ast.parse(path.read_text());return ast.dump(next(x for x in module.body if isinstance(x,ast.FunctionDef) and x.name==name))
def main():
    bundle=HERE/'bundle';plan=json.loads((bundle/'plan.json').read_text());old_id=plan.pop('plan_id')
    previous=HERE/'pilot_runs/6af04fc8e6320c66fad74304';old_source=previous/'input_source';old_source.mkdir(exist_ok=True)
    for name in ['plan.json','worker.py','report.py','protocol.py','requirements.txt']:shutil.copy2(bundle/name,old_source/name)
    for name in ['protected_score','load_model','generate']:
        if function_ast(bundle/'worker.py',name)!=function_ast(HERE/'worker.py',name):raise ValueError('Cannot reuse prior scored rows after semantic change: '+name)
    source=json.loads((previous/'source.json').read_text());shutil.copy2(previous/'results.jsonl',bundle/'resume.jsonl')
    plan['resume_sha256']=hashlib.sha256((bundle/'resume.jsonl').read_bytes()).hexdigest();plan['resume_parent_plan_ids']=[old_id]
    plan['resume_source']={**source,'filename':'runs/'+old_id+'/results.jsonl'}
    lock=json.loads((HERE/'hub_lock.json').read_text());drive=Path('/Users/rkuiper/Library/CloudStorage/GoogleDrive-ruurd.kuiper@gmail.com/My Drive/lad-generic-results/outputs')
    for key,repo in [('qwen_d','Ruurd/BYOD-Qwen2.5-7B'),('ministral_d','Ruurd/BYOD-Ministral-8B'),('llama_25k','Ruurd/BYOD-Llama-3.1-8B')]:
        spec=plan['models'][key];published=lock['models'][repo];checkpoint=drive/spec['source']
        if json.loads((checkpoint/'adapter_config.json').read_text())!=published['adapter_config.json']:raise ValueError('Adapter configuration changed: '+key)
        if json.loads((checkpoint.parent/'resolved_config.json').read_text())!=published['resolved_config.json']:raise ValueError('Training configuration changed: '+key)
        spec.update(adapter_repo=repo,adapter_revision=published['revision'],published_config_matches_original=True)
    plan['pilot_model_order']=['gemma_ar','gemma_d','llada','qwen_ar','qwen_d','ministral_ar','ministral_d','llama_ar','llama_25k']
    plan['pilot_checkpoint_note']='Published adapters match original training/adapter configurations; diffusion replay checks gate additional generations. Full tensor identity is unverified. Llama 50k is excluded until its original checkpoint is staged.'
    plan['pilot_expand_within_budget']=True;plan['pilot_max_total_credit_usd']=4.95;plan['code_hashes']=snapshot_code(bundle);plan['plan_id']=digest(plan)
    (bundle/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    from worker import verify
    verify(bundle,phase='pilot')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in ['plan.json','worker.py','protocol.py','report.py','requirements.txt']:z.write(bundle/name,name)
    (HERE/'credit_overrides.zip').write_bytes(stream.getvalue())
    print(json.dumps({'plan_id':plan['plan_id'],'model_order':plan['pilot_model_order'],'preserved_scored_rows':sum(1 for _ in (bundle/'resume.jsonl').open()),'compressed_overrides_bytes':len(stream.getvalue()),'launch_requested':False},indent=2))
if __name__=='__main__':main()
