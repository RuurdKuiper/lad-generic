"""Resumable HF Job worker. All output is private; never launches another job."""
from __future__ import annotations
import argparse,contextlib,hashlib,json,os,shutil,sys,time
from pathlib import Path
from protocol import TASKS,MODELS,digest,fingerprint
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'code/src'))

def read_rows(path):
    return [json.loads(s) for s in Path(path).read_text().split('\n') if s.strip()]

def interleave_tasks(examples):
    """Extend each task in turn, preserving its frozen question order."""
    groups={task:[e for e in examples if e['task']==task] for task in TASKS}
    return [groups[task][i] for i in range(max((len(g) for g in groups.values()),default=0)) for task in TASKS if i<len(groups[task])]

def sync_due(now,last_sync,next_retry=0,force=False):
    return now>=next_retry and (force or now-last_sync>=120)

def verify(bundle,phase="full"):
    plan=json.loads((bundle/'plan.json').read_text());unhashed=dict(plan);expected=unhashed.pop('plan_id')
    if digest(unhashed)!=expected:raise ValueError('Plan hash mismatch')
    if any('math' in spec.get('settings',{}) for spec in plan['models'].values()):
        import importlib.util
        if importlib.util.find_spec('math_verify') is None:
            raise RuntimeError('MATH evaluation requires pinned math-verify; install the evaluation requirements before running or rescoring.')
    for name,key in [('examples.jsonl','examples_sha256'),('reuse.jsonl','reuse_sha256')]:
        if hashlib.sha256((bundle/name).read_bytes()).hexdigest()!=plan[key]:raise ValueError('Input hash mismatch: '+name)
    for name,expected in plan['code_hashes'].items():
        if hashlib.sha256((bundle/name).read_bytes()).hexdigest()!=expected:raise ValueError('Code hash mismatch: '+name)
    if plan.get('resume_sha256') and hashlib.sha256((bundle/'resume.jsonl').read_bytes()).hexdigest()!=plan['resume_sha256']:raise ValueError('Resume hash mismatch')
    if not plan['checkpoints_ready'] and not (phase=='pilot' and plan.get('pilot_ready')):raise ValueError('Exact paper checkpoints have not been staged; only the replay pilot is ready')
    for key,spec in plan['models'].items():
        if 'checkpoint_path' not in spec:continue
        for name,expected in spec['checkpoint_hashes'].items():
            h=hashlib.sha256()
            with (bundle/spec['checkpoint_path']/name).open('rb') as f:
                while chunk:=f.read(8*1024*1024):h.update(chunk)
            if h.hexdigest()!=expected:raise ValueError('Checkpoint hash mismatch: '+key+'/'+name)
    return plan

def protected_score(example,prediction):
    # Generated benchmark code runs as an unprivileged account with no Hub token.
    # This is a resource-limited subprocess, not a complete network sandbox.
    import diffusion_lm.benchmarks as b
    if example.kind!='code':return bool(b.score_prediction(example,prediction))
    if sys.platform!='linux' or os.geteuid()!=0:raise RuntimeError('Code scoring requires Linux root so child privileges can be dropped')
    import resource,subprocess
    original=subprocess.run
    def limits():
        resource.setrlimit(resource.RLIMIT_CPU,(10,10));resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
        resource.setrlimit(resource.RLIMIT_FSIZE,(1024**2,1024**2));resource.setrlimit(resource.RLIMIT_NPROC,(16,16))
    def run(args,**kwargs):
        directory=Path(kwargs['cwd']);directory.chmod(0o755)
        for p in directory.iterdir():p.chmod(0o644)
        kwargs.pop('capture_output',None)
        return original(args,**kwargs,user=65534,group=65534,extra_groups=[],preexec_fn=limits,
                        env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(directory)},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run=run
    try:return bool(b.score_prediction(example,prediction))
    finally:subprocess.run=original

def load_model(key,spec,runtime):
    import torch
    from huggingface_hub import snapshot_download
    from diffusion_lm.inference import _load_adapter_path,load_llada_session
    if key=='llada':return load_llada_session(spec['repo'],device_name='cuda',revision=spec['revision'])
    base=snapshot_download(spec['base_repo'],revision=spec['base_revision'],ignore_patterns=['*.gguf','*.bin','*.h5','*.msgpack','original/*','consolidated*'])
    if spec['method']=='autoregressive':
        from transformers import AutoModelForCausalLM,AutoTokenizer
        tokenizer=AutoTokenizer.from_pretrained(base,fix_mistral_regex=True) if spec['family']=='ministral' else AutoTokenizer.from_pretrained(base)
        # Qwen's BF16 eager path produced corrupted arithmetic/code in matched
        # A100 replays. SDPA restored historical text on tested GSM8K inputs
        # and corrected the tested failures without changing decoding settings.
        attention=spec.get('attention_backend','sdpa' if key=='qwen_ar' else 'eager')
        model=AutoModelForCausalLM.from_pretrained(base,torch_dtype=torch.bfloat16,attn_implementation=attention).to('cuda').eval()
        return (model,tokenizer)
    source=Path(snapshot_download(spec['adapter_repo'],revision=spec['adapter_revision'])) if spec.get('adapter_repo') else HERE/spec['checkpoint_path'];dest=runtime/key;dest.mkdir(parents=True,exist_ok=True)
    for f in source.iterdir():
        target=dest/f.name
        if target.exists() or target.is_symlink():target.unlink()
        if f.suffix=='.json':shutil.copy2(f,target)
        else:target.symlink_to(f)
    config=json.loads((dest/'adapter_config.json').read_text());config['base_model_name_or_path']=base
    (dest/'adapter_config.json').write_text(json.dumps(config))
    cfg=dest/'resolved_config.json';run=json.loads(cfg.read_text()) if cfg.exists() else {}
    run.update(model_name_or_path=base,tokenizer_name_or_path=base,base_model_cache_dir=str(runtime/'base-cache'),quantization='none')
    cfg.write_text(json.dumps(run))
    session=_load_adapter_path(dest,device_name='cuda',quantization='none')
    if spec.get('attention_backend'):
        session.model.get_base_model().set_attn_implementation(spec['attention_backend'])
    return session

def generate(session,spec,row):
    import torch
    from diffusion_lm.data import apply_neutral_chat_template
    from diffusion_lm.inference import llada_generate
    s=spec['settings'][row['task']]
    if spec['method']=='diffusion':
        return llada_generate(session,row['prompt'],gen_length=s['max_new_tokens'],steps=s['num_steps'],block_length=s['block_length'],
            temperature=s['temperature'],cfg_scale=s['cfg_scale'],remasking=s['remasking'],logits_eos_inf=s['logits_eos_inf'],
            confidence_eos_eot_inf=s['confidence_eos_eot_inf'],eot_token_id=s['eot_token_id'],system_prompt='',seed=s['seed'],repetition_penalty=1.0)
    model,tokenizer=session
    prefix=apply_neutral_chat_template(tokenizer,[{'role':'user','content':row['prompt']}],tokenize=True,add_generation_prompt=True)
    if isinstance(prefix,str):prefix=tokenizer.encode(prefix,add_special_tokens=False)
    elif hasattr(prefix,'input_ids'):prefix=prefix.input_ids
    if prefix and isinstance(prefix[0],list):prefix=prefix[0]
    ids=torch.tensor([prefix],device='cuda');pad=tokenizer.pad_token_id
    if pad is None:pad=tokenizer.eos_token_id
    with torch.inference_mode():answer=model.generate(input_ids=ids,attention_mask=torch.ones_like(ids),max_new_tokens=s['max_new_tokens'],do_sample=False,use_cache=True,pad_token_id=pad)
    return tokenizer.decode(answer[0,len(prefix):],skip_special_tokens=True).strip()

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--phase',choices=['pilot','full'],required=True)
    p.add_argument('--seconds',type=int,required=True);p.add_argument('--expand-pilot',action='store_true');a=p.parse_args()
    started=time.monotonic();deadline=started+a.seconds
    if a.seconds>(6600 if a.phase=='pilot' else 100200):raise ValueError('Worker exceeds approved phase limit')
    # Private inputs and model cache must not be readable by code-scoring children.
    os.umask(0o077);HERE.chmod(0o700)
    for name in ['HF_HOME','HF_HUB_CACHE']:
        if os.getenv(name):Path(os.environ[name]).mkdir(parents=True,exist_ok=True);Path(os.environ[name]).chmod(0o700)
    plan=verify(HERE,phase=a.phase)
    from huggingface_hub import HfApi,hf_hub_download
    from huggingface_hub.errors import EntryNotFoundError
    from diffusion_lm.benchmarks import BenchmarkExample
    from report import write_report
    api=HfApi();root=Path('/tmp/byod-private-results');root.mkdir(exist_ok=True);root.chmod(0o700)
    path_in_repo='runs/'+plan['plan_id'];output=root/'results.jsonl'
    try:shutil.copy2(hf_hub_download(a.repo,path_in_repo+'/results.jsonl',repo_type='dataset'),output)
    except EntryNotFoundError:
        output.touch()
        if plan.get('resume_sha256'):
            with output.open('w') as f:
                for row in read_rows(HERE/'resume.jsonl'):
                    if row['plan_id'] not in plan.get('resume_parent_plan_ids',[]):raise ValueError('Unrecognized resume source')
                    if row['settings']!=plan['models'][row['model_key']]['settings'][row['task']]:raise ValueError('Resume settings changed')
                    row=dict(row,previous_plan_id=row['plan_id'],plan_id=plan['plan_id'])
                    f.write(json.dumps(row,ensure_ascii=False)+'\n')
    replay_path=root/'replays.jsonl'
    try:shutil.copy2(hf_hub_download(a.repo,path_in_repo+'/replays.jsonl',repo_type='dataset'),replay_path)
    except EntryNotFoundError:replay_path.touch()
    rows=read_rows(output);done={}
    for row in rows:
        if row['plan_id']!=plan['plan_id']:raise ValueError('Refusing to mix plans')
        done[(row['model_key'],row['fingerprint'])]=row
    examples=read_rows(HERE/'examples.jsonl');reuse={(x['model_key'],x['fingerprint']):x for x in read_rows(HERE/'reuse.jsonl')}
    last_sync=0;next_retry=0;count=0;status='running'
    def sync(force=False):
        nonlocal last_sync,next_retry
        if not sync_due(time.monotonic(),last_sync,next_retry,force):return
        progress={'plan_id':plan['plan_id'],'phase':a.phase,'status':status,'scored_items':len(done),'elapsed_seconds':time.monotonic()-started,
                  'model_order':plan.get('pilot_model_order'),'expand_pilot':a.expand_pilot}
        (root/'progress.json').write_text(json.dumps(progress,indent=2));write_report(list(done.values()),root,paired=force)
        from huggingface_hub.errors import HfHubHTTPError
        try:
            api.upload_folder(repo_id=a.repo,repo_type='dataset',folder_path=root,path_in_repo=path_in_repo,allow_patterns=['results.jsonl','progress.json','report.json','report.md','replays.jsonl'],commit_message='Save private resumable evaluation outcomes')
        except HfHubHTTPError as exc:
            if exc.response is None or exc.response.status_code not in [429,500,502,503,504]:raise
            try:delay=float(exc.response.headers.get('Retry-After','300'))
            except ValueError:delay=300
            next_retry=time.monotonic()+max(120,delay)
            print(json.dumps({'status':'upload_deferred','http_status':exc.response.status_code,'retry_seconds':max(120,delay),'local_scored_items':len(done)}),flush=True)
            return
        last_sync=time.monotonic();next_retry=0;print(json.dumps(progress),flush=True)
    def score_and_save(key,ex,prediction,source,seconds,legacy=None):
        nonlocal count
        example=BenchmarkExample(ex['task'],str(ex['example_id']),ex['prompt'],ex['target'],ex['kind'],ex['metadata'])
        row={'plan_id':plan['plan_id'],'model_key':key,'task':ex['task'],'fingerprint':ex['fingerprint'],'sample_index':ex['sample_index'],
             'prediction':prediction,'correct':protected_score(example,prediction),'source':source,'generation_seconds':seconds,'settings':plan['models'][key]['settings'][ex['task']]}
        if legacy:row.update(legacy_run=legacy['legacy_run'],recorded_correct=legacy['recorded_correct'])
        with output.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
        done[(key,ex['fingerprint'])]=row;count+=1;sync()
    try:
        keys=plan.get('pilot_model_order',['gemma_d','gemma_ar','llada']) if a.phase=='pilot' else list(MODELS)
        import gc,torch
        for key in keys:
            # Score only the current model before loading it. Previously saved
            # scoring work is resumed and never charged as fresh generation.
            for ex in examples:
                identity=(key,ex['fingerprint'])
                if identity in done or identity not in reuse:continue
                if time.monotonic()>deadline-180:status='time_limit';return
                old=reuse[identity];score_and_save(key,ex,old['prediction'],'legacy_rescored',0,old)
            missing=[e for e in examples if (key,e['fingerprint']) not in done]
            if a.phase=='pilot' and not a.expand_pilot:missing=[e for task in TASKS for e in [x for x in missing if x['task']==task][:2]]
            elif a.expand_pilot:missing=interleave_tasks(missing)
            if not missing:continue
            if time.monotonic()>deadline-300:status='time_limit';return
            session=load_model(key,plan['models'][key],root/'runtime')
            try:
                if a.phase=='pilot' and plan['models'][key]['method']=='diffusion':
                    replayed={(r['model_key'],r['fingerprint']) for r in read_rows(replay_path)}
                    for task in TASKS:
                        for ex in [e for e in examples if e['task']==task and (key,e['fingerprint']) in reuse][:2]:
                            identity=(key,ex['fingerprint'])
                            if identity in replayed:continue
                            if time.monotonic()>deadline-180:status='time_limit';return
                            t=time.monotonic();pred=generate(session,plan['models'][key],ex);old=reuse[identity]
                            example=BenchmarkExample(ex['task'],str(ex['example_id']),ex['prompt'],ex['target'],ex['kind'],ex['metadata'])
                            replay={'model_key':key,'task':task,'fingerprint':ex['fingerprint'],'generation_seconds':time.monotonic()-t,
                                    'prediction_matches':pred==old['prediction'],'score_matches':protected_score(example,pred)==done[identity]['correct']}
                            with replay_path.open('a') as f:f.write(json.dumps(replay)+'\n');f.flush();os.fsync(f.fileno())
                            sync()
                    mismatches=[r for r in read_rows(replay_path) if r['model_key']==key and not r['score_matches']]
                    if a.expand_pilot and mismatches:
                        print(json.dumps({'model':key,'status':'replay_score_mismatch_requires_review','mismatches':len(mismatches)}),flush=True)
                        sync(force=True)
                        continue
                for ex in missing:
                    if time.monotonic()>deadline-180:status='time_limit';return
                    t=time.monotonic();pred=generate(session,plan['models'][key],ex)
                    score_and_save(key,ex,pred,'new_generation',time.monotonic()-t)
            finally:
                del session;gc.collect();torch.cuda.empty_cache()
        status='pilot_complete' if a.phase=='pilot' else ('complete' if len(done)==len(examples)*len(MODELS) else 'incomplete')
    except BaseException:
        status='failed';raise
    finally:sync(force=True)
if __name__=='__main__':main()
