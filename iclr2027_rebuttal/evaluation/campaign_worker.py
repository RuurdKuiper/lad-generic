"""Checkpointed expansion in bounded, fair model batches; original adapters only."""
from __future__ import annotations
import argparse,collections,hashlib,json,os,signal,sys,time
from pathlib import Path
import worker as core
from protocol import TASKS,fingerprint
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'code/src'))
PRIORITY=['gemma_d','llada','gemma_ar','qwen_d','qwen_ar','ministral_d','ministral_ar','llama_25k','llama_50k','llama_ar']

def remaining_examples(examples,done,key):
    return core.interleave_tasks([e for e in examples if (key,e['fingerprint']) not in done])
def queue_order(keys,done,total,priority=None):
    counts=collections.Counter(key for key,fp in done)
    priority=priority or PRIORITY
    return sorted(keys,key=lambda key:(counts[key]/total,priority.index(key)))
def scheduled_keys(plan,done,total,timed):
    keys=queue_order(list(plan['models']),done,total,plan.get('model_priority'))
    if 'llada' in keys and 'llada' not in timed:
        keys=['llada']+[k for k in keys if k!='llada']
    return keys
def no_progress_status(deferred,stop,now,deadline):
    # Reaching the model-load shutdown margin is a normal block boundary,
    # not evidence that eligible models require scientific replay review.
    if stop:return 'interrupted'
    if now>=deadline-420:return 'time_limit'
    return 'waiting_for_original_assets' if deferred else 'needs_review'
def validated_rows(rows,plan,examples):
    allowed={e['fingerprint']:e for e in examples};selected={}
    for row in rows:
        if row['plan_id'] not in [plan['plan_id'],*plan.get('resume_parent_plan_ids',[])]:raise ValueError('Unexpected checkpoint plan identity')
        key=row['model_key'];ex=allowed.get(row['fingerprint'])
        if ex is None or ex['task']!=row['task']:raise ValueError('Unknown checkpoint question')
        if row['settings']!=plan['models'][key]['settings'][row['task']]:raise ValueError('Checkpoint settings changed')
        if not isinstance(row['correct'],bool):raise ValueError('Invalid correctness flag')
        row=dict(row,previous_plan_id=row.get('previous_plan_id',row['plan_id']),plan_id=plan['plan_id'])
        identity=(key,row['fingerprint'])
        if identity in selected and selected[identity]['prediction']!=row['prediction']:raise ValueError('Conflicting duplicate checkpoint predictions')
        selected[identity]=row
    return selected

def original_spec(key,spec,api,repo,cache):
    if spec['method']=='autoregressive' or key=='llada':return dict(spec),None
    from huggingface_hub import hf_hub_download,snapshot_download
    from huggingface_hub.errors import EntryNotFoundError
    try:
        rev=api.dataset_info(repo).sha
        manifest=json.loads(Path(hf_hub_download(repo,'assets/manifest.json',repo_type='dataset',revision=rev)).read_text())
    except EntryNotFoundError:return None,None
    asset=manifest['models'].get(key)
    if not asset:return None,None
    if asset['source']!=spec['source']:raise ValueError('Original checkpoint source mismatch')
    downloaded=Path(snapshot_download(asset['repo'],repo_type='dataset',revision=asset['revision'],allow_patterns=[asset['path']+'/**']))/asset['path']
    for name,expected in asset['hashes'].items():
        h=hashlib.sha256()
        with (downloaded/name).open('rb') as f:
            while chunk:=f.read(8*1024*1024):h.update(chunk)
        if h.hexdigest()!=expected:raise ValueError('Original checkpoint checksum mismatch')
    resolved=dict(spec);resolved.pop('adapter_repo',None);resolved['checkpoint_path']=str(downloaded)
    return resolved,asset

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--seconds',type=int,required=True);a=p.parse_args()
    os.umask(0o077);HERE.chmod(0o700);plan=core.verify(HERE,phase='pilot')
    if a.seconds>13800:raise ValueError('Worker must fit a four-hour provider block')
    started=time.monotonic();deadline=started+a.seconds;stop=False
    def interrupt(signum,frame):
        nonlocal stop
        stop=True
    signal.signal(signal.SIGTERM,interrupt);signal.signal(signal.SIGINT,interrupt)
    from huggingface_hub import HfApi,hf_hub_download
    from huggingface_hub.errors import EntryNotFoundError,HfHubHTTPError
    from diffusion_lm.benchmarks import BenchmarkExample
    from report import write_report
    for name in ['HF_HOME','HF_HUB_CACHE']:
        if os.getenv(name):Path(os.environ[name]).mkdir(parents=True,exist_ok=True);Path(os.environ[name]).chmod(0o700)
    api=HfApi();root=Path('/tmp/byod-campaign-results');root.mkdir(exist_ok=True);root.chmod(0o700)
    remote='campaigns/'+plan['plan_id'];output=root/'results.jsonl';replays=root/'replays.jsonl'
    examples=core.read_rows(HERE/'examples.jsonl');reuse={(r['model_key'],r['fingerprint']):r for r in core.read_rows(HERE/'reuse.jsonl')}
    try:output.write_bytes(Path(hf_hub_download(a.repo,remote+'/results.jsonl',repo_type='dataset')).read_bytes())
    except EntryNotFoundError:output.write_bytes((HERE/'resume.jsonl').read_bytes())
    done=validated_rows(core.read_rows(output),plan,examples)
    with output.open('w') as f:
        for row in done.values():f.write(json.dumps(row,ensure_ascii=False)+'\n')
    try:replays.write_bytes(Path(hf_hub_download(a.repo,remote+'/replays.jsonl',repo_type='dataset')).read_bytes())
    except EntryNotFoundError:replays.touch()
    last_sync=0;next_retry=0;status='running';errors={};assets_used={};current_model=None
    def sync(force=False):
        nonlocal last_sync,next_retry,stop
        now=time.monotonic()
        if not core.sync_due(now,last_sync,next_retry,force):return False
        progress={'plan_id':plan['plan_id'],'status':status,'scored_items':len(done),'target_items':len(examples)*len(plan['models']),
                  'elapsed_seconds':now-started,'current_model':current_model,'counts_by_model':dict(collections.Counter(k for k,fp in done)),
                  'blocked_models':errors,'original_assets_used':assets_used}
        (root/'progress.json').write_text(json.dumps(progress,indent=2)+'\n')
        write_report(list(done.values()),root,paired=force)
        try:
            api.upload_folder(repo_id=a.repo,repo_type='dataset',folder_path=root,path_in_repo=remote,
                allow_patterns=['results.jsonl','replays.jsonl','progress.json','report.json','report.md'],commit_message='Checkpoint resumable benchmark expansion')
        except Exception as exc:
            http=getattr(getattr(exc,'response',None),'status_code',None)
            if http and http not in [429,500,502,503,504]:raise
            headers=getattr(getattr(exc,'response',None),'headers',{})
            try:delay=max(120,float(headers.get('Retry-After','120')))
            except ValueError:delay=120
            next_retry=now+delay;print(json.dumps({'status':'checkpoint_upload_deferred','error':type(exc).__name__,'retry_seconds':delay}),flush=True)
            # Do not keep generating expensive answers without a working
            # durable checkpoint. Stop after the current saved local item.
            stop=True
            return False
        last_sync=time.monotonic();next_retry=0;print(json.dumps(progress),flush=True);return True
    def save(key,ex,prediction,source,seconds=0,old=None,asset=None):
        row={'plan_id':plan['plan_id'],'model_key':key,'fingerprint':ex['fingerprint'],'task':ex['task'],'sample_index':ex['sample_index'],
             'prediction':prediction,'correct':core.protected_score(BenchmarkExample(ex['task'],str(ex['example_id']),ex['prompt'],ex['target'],ex['kind'],ex['metadata']),prediction),
             'source':source,'generation_seconds':seconds,'settings':plan['models'][key]['settings'][ex['task']]}
        if old:row.update(legacy_run=old['legacy_run'],recorded_correct=old['recorded_correct'])
        if asset:row['original_adapter']={'revision':asset['revision'],'sha256':asset['hashes']['adapter_model.safetensors']}
        if source=='new_generation':
            row['attention_backend']=plan['models'][key].get('attention_backend','default')
            row['evaluation_cohort']=plan.get('execution','original_campaign')
        with output.open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())
        done[(key,ex['fingerprint'])]=row;sync()
    def time_left():return not stop and time.monotonic()<deadline-180
    sync(force=True)
    import gc,torch
    timed=set()
    try:
        while time_left():
            if len(done)==len(examples)*len(plan['models']):status='complete';break
            # Finish at most 128 fresh generations/model before rotating. This
            # keeps one slow model from consuming the whole expansion budget.
            keys=scheduled_keys(plan,done,len(examples),timed)
            made_progress=False;deferred=[]
            for key in keys:
                if not time_left():break
                current_model=key;spec=plan['models'][key]
                for ex in examples:
                    identity=(key,ex['fingerprint'])
                    if identity in done or identity not in reuse:continue
                    if not time_left():break
                    old=reuse[identity];save(key,ex,old['prediction'],'legacy_rescored',old=old);made_progress=True
                if not time_left():break
                missing=remaining_examples(examples,done,key)
                if not missing or key in errors:continue
                resolved,asset=original_spec(key,spec,api,a.repo,root)
                if resolved is None:deferred.append(key);continue
                if asset:assets_used[key]={'revision':asset['revision'],'sha256':asset['hashes']['adapter_model.safetensors']}
                if time.monotonic()>deadline-420:break
                print(json.dumps({'status':'loading_model','model':key,'remaining':len(missing)}),flush=True)
                session=core.load_model(key,resolved,root/'runtime')
                try:
                    if spec['method']=='diffusion' or spec.get('verify_ar_replay',False):
                        completed_replays={(r['model_key'],r['fingerprint']) for r in core.read_rows(replays)}
                        for task in TASKS:
                            for ex in [e for e in examples if e['task']==task and (key,e['fingerprint']) in reuse][:2]:
                                identity=(key,ex['fingerprint'])
                                if identity in completed_replays:continue
                                if not time_left():break
                                t=time.monotonic();pred=core.generate(session,resolved,ex);old=reuse[identity]
                                example=BenchmarkExample(ex['task'],str(ex['example_id']),ex['prompt'],ex['target'],ex['kind'],ex['metadata'])
                                replay={'model_key':key,'task':task,'fingerprint':ex['fingerprint'],'generation_seconds':time.monotonic()-t,
                                        'prediction':pred,'historical_prediction':old['prediction'],
                                        'prediction_matches':pred==old['prediction'],'score_matches':core.protected_score(example,pred)==done[identity]['correct']}
                                with replays.open('a') as f:f.write(json.dumps(replay)+'\n');f.flush();os.fsync(f.fileno())
                                sync()
                        mismatches=[r for r in core.read_rows(replays) if r['model_key']==key and not r['score_matches']]
                        if mismatches:
                            errors[key]={'reason':'replay_score_mismatch','count':len(mismatches)};sync(force=True);continue
                    # A brief first LLaDA batch gives measured diffusion timing
                    # before any one model receives its larger 128-item batch.
                    batch=missing[:18] if key=='llada' and key not in timed else missing[:128]
                    for ex in batch:
                        if not time_left():break
                        t=time.monotonic();pred=core.generate(session,resolved,ex)
                        save(key,ex,pred,'new_generation',time.monotonic()-t,asset=asset);made_progress=True
                    timed.add(key);sync(force=True)
                finally:
                    del session;gc.collect();torch.cuda.empty_cache()
            if not made_progress:
                status=no_progress_status(deferred,stop,time.monotonic(),deadline);break
        else:status='interrupted' if stop else 'time_limit'
        if len(done)==len(examples)*len(plan['models']):status='complete'
    except BaseException:
        status='failed';raise
    finally:
        current_model=None
        # Retry a transient final upload within the provider shutdown margin.
        for attempt in range(3):
            if sync(force=True):break
            delay=max(1,min(60,next_retry-time.monotonic()))
            if attempt<2 and time.monotonic()+delay<deadline+120:
                time.sleep(delay)
            else:break
if __name__=='__main__':main()
