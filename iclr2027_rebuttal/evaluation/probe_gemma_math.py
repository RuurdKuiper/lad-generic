"""Matched Gemma AR MATH backend probe. Does not overwrite benchmark answers."""
import gc,json,os,sys,time
from pathlib import Path

def main():
    import torch,transformers,peft
    from huggingface_hub import HfApi,hf_hub_download,snapshot_download
    os.umask(0o077);root=Path('/tmp/gemma-math-private');root.mkdir(exist_ok=True);root.chmod(0o700)
    repo=os.environ['INPUT_REPO'];rev=os.environ['INPUT_REVISION'];api=HfApi()
    bundle=Path(snapshot_download(repo,repo_type='dataset',revision=rev,allow_patterns=['campaign_input/**'],local_dir=root/'inputs'))/'campaign_input'
    sys.path.insert(0,str(bundle));sys.path.insert(0,str(bundle/'code/src'))
    import worker
    plan=json.loads((bundle/'plan.json').read_text());spec=plan['models']['gemma_ar'];examples=worker.read_rows(bundle/'examples.jsonl');reuse={(r['model_key'],r['fingerprint']):r for r in worker.read_rows(bundle/'reuse.jsonl')}
    session=worker.load_model('gemma_ar',spec,root/'runtime');model,tokenizer=session
    metadata={'torch':torch.__version__,'transformers':transformers.__version__,'peft':peft.__version__,'gpu':torch.cuda.get_device_name(),'input_revision':rev,'base_revision':spec['base_revision'],'generation_config':model.generation_config.to_dict()}
    manifest=json.loads(Path(hf_hub_download(repo,'assets/manifest.json',repo_type='dataset')).read_text());asset=manifest['models']['gemma_d']
    path=hf_hub_download(asset['repo'],asset['path']+'/normalization_initial_state.pt',repo_type='dataset',revision=asset['revision'])
    state=torch.load(path,map_location='cpu',weights_only=True);params=dict(model.named_parameters());diff=[]
    for name,value in state.items():
        native=name.removeprefix('base_model.model.')
        if native in params:
            difference=float((params[native].detach().cpu().float()-value.float()).abs().max())
            if difference:diff.append({'name':native,'max_abs_difference':difference})
    metadata['initial_norm_tensors']=len(state);metadata['different_norms']=diff
    selected=[e for e in examples if e['task']=='math' and e['sample_index'] in [0,2,5,8,129,130,133,134,136,157]]
    rows=[];started=time.monotonic()
    def sync():
        path=root/'probe.json';path.write_text(json.dumps({'metadata':metadata,'rows':rows},indent=2)+'\n')
        api.upload_file(repo_id=repo,repo_type='dataset',path_or_fileobj=path,path_in_repo='diagnostics/gemma-math-2026-11-15/probe.json',commit_message='Matched Gemma AR MATH backend diagnostic; no campaign mutation')
    for backend in ['eager','sdpa']:
        model.set_attn_implementation(backend)
        for ex in selected:
            if time.monotonic()-started>1500:sync();return
            t=time.monotonic();prediction=worker.generate(session,spec,ex);old=reuse.get(('gemma_ar',ex['fingerprint']))
            row={'backend':backend,'sample_index':ex['sample_index'],'fingerprint':ex['fingerprint'],'prediction':prediction,'seconds':time.monotonic()-t}
            if old:row.update(historical_prediction=old['prediction'],historical_text_matches=prediction==old['prediction'])
            rows.append(row);print(json.dumps({k:v for k,v in row.items() if k not in ['prediction','historical_prediction']}),flush=True)
        sync()
    metadata['complete']=True;sync()

if __name__=='__main__':main()
