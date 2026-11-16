"""Bounded GPU probe; keeps texts and does not modify campaign checkpoints."""
import collections,gc,json,os,sys,time
from pathlib import Path

def main():
    import torch,transformers,peft
    from huggingface_hub import HfApi,snapshot_download,hf_hub_download
    from dotenv import load_dotenv
    repo=os.environ['INPUT_REPO'];rev=os.environ['INPUT_REVISION'];planid=os.environ['PLAN_ID']
    root=Path('/tmp/byod-generation-probe');root.mkdir(exist_ok=True);root.chmod(0o700);os.umask(0o077)
    bundle=Path(snapshot_download(repo,repo_type='dataset',revision=rev,allow_patterns=['campaign_input/**'],local_dir=root/'inputs'))/'campaign_input'
    os.chdir(bundle);sys.path.insert(0,str(bundle));sys.path.insert(0,str(bundle/'code/src'))
    import worker,campaign_worker
    from diffusion_lm.inference import llada_generate
    api=HfApi();plan=json.loads((bundle/'plan.json').read_text());examples=worker.read_rows(bundle/'examples.jsonl');reuse={(r['model_key'],r['fingerprint']):r for r in worker.read_rows(bundle/'reuse.jsonl')}
    rows=[];metadata={'torch':torch.__version__,'transformers':transformers.__version__,'peft':peft.__version__,'gpu':torch.cuda.get_device_name(),'cuda':torch.version.cuda,'input_revision':rev}
    started=time.monotonic()
    def sync():
        dest=root/'probe.json';dest.write_text(json.dumps({'metadata':metadata,'rows':rows},indent=2)+'\n')
        api.upload_file(repo_id=repo,repo_type='dataset',path_or_fileobj=dest,path_in_repo='diagnostics/generation/'+os.environ['PROBE_ID']+'/probe.json',commit_message='Save bounded Qwen/Gemma generation diagnostic; campaign untouched')
    def record(key,variant,ex,pred,session,t):
        old=reuse.get((key,ex['fingerprint']));example=type('Example',(),{'task':ex['task'],'kind':ex['kind'],'metadata':ex['metadata'],'answer':ex['target']})()
        # protected_score needs the concrete BenchmarkExample for scoring only.
        from diffusion_lm.benchmarks import BenchmarkExample
        example=BenchmarkExample(ex['task'],str(ex['example_id']),ex['prompt'],ex['target'],ex['kind'],ex['metadata'])
        model=session[0] if isinstance(session,tuple) else session.model
        row={'model_key':key,'variant':variant,'task':ex['task'],'sample_index':ex['sample_index'],'fingerprint':ex['fingerprint'],'prediction':pred,'correct':worker.protected_score(example,pred),'seconds':time.monotonic()-t,'attention':model.config._attn_implementation,'dtype':str(next(model.parameters()).dtype)}
        if old:row.update(historical_prediction=old['prediction'],historical_correct=bool(worker.protected_score(example,old['prediction'])),prediction_matches=pred==old['prediction'])
        rows.append(row);print(json.dumps({k:v for k,v in row.items() if k not in ['prediction','historical_prediction']}),flush=True)
    key='qwen_ar';spec=plan['models'][key];session=worker.load_model(key,spec,root/'runtime');model,tokenizer=session
    metadata['qwen_generation_config']=model.generation_config.to_dict()
    selected=[e for e in examples if (e['task']=='gsm8k' and e['sample_index'] in [0,1,127,128]) or (e['task']=='humaneval' and e['sample_index'] in [0,1,95,98])]
    for backend,penalty in [('eager',1.05),('sdpa',1.05),('sdpa',1.0)]:
        model.set_attn_implementation(backend);model.generation_config.repetition_penalty=penalty
        for ex in selected:
            if time.monotonic()-started>2100:sync();return
            t=time.monotonic();pred=worker.generate(session,spec,ex);record(key,backend+'_rep'+str(penalty),ex,pred,session,t)
        sync()
    del session,model;gc.collect();torch.cuda.empty_cache()
    key='gemma_d';spec=plan['models'][key];resolved,asset=campaign_worker.original_spec(key,spec,api,repo,root)
    session=worker.load_model(key,resolved,root/'runtime');metadata['gemma_asset']=asset;metadata['gemma_initial_attention']=session.model.config._attn_implementation
    selected=[e for e in examples if e['task'] in ['gpqa','mmlu_pro','humaneval'] and e['sample_index']==0]
    base=session.model.get_base_model()
    initial=base.config._attn_implementation
    for label,backend in [('default_first',initial),('default_repeat',initial),('alternate','eager' if initial!='eager' else 'sdpa')]:
        base.set_attn_implementation(backend)
        for ex in selected:
            if time.monotonic()-started>2100:sync();return
            t=time.monotonic();pred=worker.generate(session,resolved,ex);record(key,label,ex,pred,session,t)
        sync()
    metadata['complete']=True;sync()

if __name__=='__main__':main()
