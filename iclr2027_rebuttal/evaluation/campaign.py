"""Start/status/resume a single private, budget-capped HF evaluation campaign."""
from __future__ import annotations
import argparse,base64,json,math,os,sys,time,uuid
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO='Ruurd/iclr2027-rebuttal-eval'
IMAGE='pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385'
TERMINAL={'COMPLETED','ERROR','FAILED','CANCELED','CANCELLED','DELETED'}
ACTIVE_STAGES={'RUNNING','STARTING','PENDING','QUEUED','BUILDING','SCHEDULING'}
CPU_SECONDS=36*3600
RATE=.041667

def block_seconds(state):
    spent=state['prior_compute_reserved_usd']+sum(x['reserved_usd'] for x in state['cpu_reservations'])
    spent+=sum(x.get('cost_upper_usd',x['reserved_usd']) for x in state['gpu_jobs'])
    # Include one extra billable minute in every provider reservation.
    minutes=min(240,math.floor((state['total_compute_ceiling_usd']-spent)/RATE)-1)
    if state.get('max_gpu_timeout_seconds') is not None:
        allocated=sum(x.get('timeout_seconds',14400) for x in state['gpu_jobs'])
        minutes=min(minutes,(state['max_gpu_timeout_seconds']-allocated)//60)
    return max(0,minutes)*60

def observed_cost_upper(created_at,finished_at,timeout):
    seconds=min(timeout,max(0,(finished_at-created_at).total_seconds()))
    return (math.ceil(seconds/60)+1)*RATE

def bootstrap():
    return """import os,subprocess,sys
from huggingface_hub import snapshot_download
os.umask(0o077)
bundle=snapshot_download(os.environ['INPUT_REPO'],repo_type='dataset',revision=os.environ['INPUT_REVISION'],allow_patterns=['campaign_input/**'],local_dir='/tmp/byod-input')+'/campaign_input'
subprocess.run([sys.executable,'-m','pip','install','--quiet','--disable-pip-version-check','-r',bundle+'/requirements.txt'],check=True)
os.chdir(bundle)
os.execv(sys.executable,[sys.executable,bundle+'/campaign_worker.py','--repo',os.environ['INPUT_REPO'],'--seconds',os.environ['WORKER_SECONDS']])
"""

def remote_main():
    from huggingface_hub import HfApi,get_token,hf_hub_download
    from huggingface_hub.errors import EntryNotFoundError
    from huggingface_hub.utils import get_session
    api=HfApi();state=json.loads(os.environ['CAMPAIGN_STATE']);plan_id=state['plan_id'];path='campaigns/'+plan_id;started=time.monotonic()
    controller_seconds=state.get('controller_timeout_seconds',CPU_SECONDS)
    def persist():
        api.upload_file(repo_id=REPO,repo_type='dataset',path_or_fileobj=json.dumps(state,indent=2).encode(),path_in_repo=path+'/controller.json',commit_message='Save resumable campaign control and budget ledger')
        print(json.dumps({'status':state['status'],'gpu_jobs':len(state['gpu_jobs']),'plan_id':plan_id}),flush=True)
    def progress():
        try:return json.loads(Path(hf_hub_download(REPO,path+'/progress.json',repo_type='dataset')).read_text())
        except EntryNotFoundError:return None
    def asset_count():
        try:return len(json.loads(Path(hf_hub_download(REPO,'assets/manifest.json',repo_type='dataset')).read_text())['models'])
        except EntryNotFoundError:return 0
    state['status']='running';persist();consecutive_failures=0
    while time.monotonic()-started<controller_seconds-600:
        p=progress()
        if p and p['status']=='complete':state['status']='complete';persist();return
        if p and p['status']=='needs_review':state['status']='needs_review';state['reason']=p.get('blocked_models');persist();return
        if p and p['status']=='waiting_for_original_assets':
            baseline=len(p.get('original_assets_used',{}))
            if asset_count()<=baseline:
                state['status']='waiting_for_original_assets';persist();time.sleep(300);continue
        seconds=block_seconds(state)
        if seconds<1200:state['status']='budget_limit';persist();return
        if time.monotonic()-started<controller_seconds-600 and seconds>controller_seconds-(time.monotonic()-started)-300:
            seconds=int((controller_seconds-(time.monotonic()-started)-300)//60)*60
        if seconds<1200:state['status']='controller_time_limit';persist();return
        # Refuse overlap even if a prior API response was lost before its receipt.
        matching=[j for j in api.list_jobs(namespace='Ruurd') if (j.environment or {}).get('CAMPAIGN_ID')==plan_id and (j.environment or {}).get('CAMPAIGN_ROLE')=='gpu']
        known={x['job_id'] for x in state['gpu_jobs']}
        unknown=[j for j in matching if j.id not in known]
        if unknown or any(j.status.stage not in TERMINAL for j in matching):
            state['status']='existing_job_requires_reconciliation';state['existing_job_ids']=[j.id for j in matching if j.id not in known or j.status.stage not in TERMINAL];persist();return
        h=get_session().get('https://huggingface.co/api/jobs/hardware',headers=api._build_hf_headers(),timeout=30);h.raise_for_status()
        rate=next(x for x in h.json() if x['name']=='a100-large')
        if float(rate['unitCostUSD'])>RATE:state['status']='price_changed';persist();return
        env={'CAMPAIGN_ID':plan_id,'CAMPAIGN_ROLE':'gpu','INPUT_REPO':REPO,'INPUT_REVISION':state['input_revision'],
             'WORKER_SECONDS':str(seconds-600),'HF_HOME':'/tmp/byod-hf-private','HF_HUB_CACHE':'/tmp/byod-hf-private/hub',
             'TOKENIZERS_PARALLELISM':'false','BOOTSTRAP':bootstrap()}
        state['status']='launching_gpu';persist()
        try:
            # Never retry an ambiguous launch response. A later resume checks
            # matching Jobs and adopts/reconciles them before launching again.
            job=api.run_job(image=IMAGE,command=['bash','-lc','python -m pip install --quiet --disable-pip-version-check huggingface-hub==0.36.2 && exec python -c "$BOOTSTRAP"'],
                env=env,secrets={'HF_TOKEN':get_token()},flavor='a100-large',timeout=seconds,namespace='Ruurd')
        except Exception as exc:
            state['status']='launch_blocked';state['reason']=type(exc).__name__+': '+str(exc)[:600];persist();return
        record={'job_id':job.id,'url':job.url,'created_at':job.created_at.isoformat(),'timeout_seconds':seconds,
                'reserved_usd':(math.ceil(seconds/60)+1)*RATE,'status':job.status.stage}
        state['gpu_jobs'].append(record);state['status']='gpu_running';persist()
        while True:
            time.sleep(30);current=api.inspect_job(job_id=job.id,namespace='Ruurd')
            if current.status.stage in TERMINAL:break
            if current.status.stage not in ACTIVE_STAGES:
                state['status']='provider_paused';state['reason']=current.status.stage;persist();return
        finished=datetime.now(timezone.utc);record.update(status=current.status.stage,observed_finished_at=finished.isoformat(),
            cost_upper_usd=observed_cost_upper(job.created_at,finished,seconds))
        p=progress();record['progress_status']=p.get('status') if p else None;state['status']='checking_saved_progress';persist()
        if current.status.stage in ['CANCELED','CANCELLED']:
            state['status']='cancelled';persist();return
        if current.status.stage!='COMPLETED' or not p or p.get('status') not in ['time_limit','complete','waiting_for_original_assets','needs_review']:
            state['status']='interrupted_or_failed';state['reason']=current.status.message or (p.get('status') if p else 'No saved progress');persist();return
        # A controlled time-limit completion automatically continues from the
        # durable checkpoint. Funding/runtime failures stop for explicit resume.
    state['status']='controller_time_limit';persist()

def main():
    from dotenv import load_dotenv
    from huggingface_hub import HfApi,get_token,hf_hub_download
    from huggingface_hub.errors import EntryNotFoundError
    load_dotenv(HERE.parents[1]/'.env');p=argparse.ArgumentParser();p.add_argument('action',choices=['start','resume','status'])
    p.add_argument('--staging',type=Path,default=HERE/'campaign_staging.json')
    a=p.parse_args();api=HfApi()
    staging=json.loads(a.staging.read_text());plan_id=staging['plan_id'];path='campaigns/'+plan_id
    try:state=json.loads(Path(hf_hub_download(REPO,path+'/controller.json',repo_type='dataset')).read_text())
    except EntryNotFoundError:state=None
    jobs=api.list_jobs(namespace='Ruurd');matching=[j for j in jobs if (j.environment or {}).get('CAMPAIGN_ID')==plan_id]
    active=[j for j in matching if j.status.stage not in TERMINAL]
    if a.action=='status':
        print(json.dumps({'state':state,'active_jobs':[{'id':j.id,'status':j.status.stage,'url':j.url} for j in active]},indent=2));return
    if active:raise RuntimeError('Campaign already has active Jobs: '+', '.join(j.id for j in active))
    if a.action=='start' and state is not None:raise RuntimeError('Campaign already exists; use resume')
    if a.action=='resume' and state is None:raise RuntimeError('No existing campaign to resume')
    if state is None:state={'schema':1,'plan_id':plan_id,'input_revision':staging['revision'],'status':'prepared','total_compute_ceiling_usd':staging.get('total_compute_ceiling_usd',75.0),
                          'prior_compute_reserved_usd':staging.get('prior_compute_reserved_usd',4.890069),'cpu_reservations':[],'gpu_jobs':[],
                          'max_gpu_timeout_seconds':staging.get('max_gpu_timeout_seconds'),'controller_timeout_seconds':staging.get('controller_timeout_seconds',CPU_SECONDS)}
    if state['status']=='complete':print('All target questions are complete; nothing to launch.');return
    # Reconcile jobs whose receipt was lost by conservatively charging their
    # full known provider reservation, rather than silently creating duplicates.
    known={x['job_id'] for x in state['gpu_jobs']}
    for job in matching:
        if (job.environment or {}).get('CAMPAIGN_ROLE')=='gpu' and job.id not in known:
            state['gpu_jobs'].append({'job_id':job.id,'url':job.url,'status':job.status.stage,'timeout_seconds':14400,'reserved_usd':241*RATE,'reconciled_conservatively':True})
    controller_key=str(uuid.uuid4());state['cpu_reservations'].append({'controller_key':controller_key,'reserved_usd':.37})
    if block_seconds(state)<1200:raise RuntimeError('Insufficient remaining campaign budget')
    if not api.dataset_info(REPO).private:raise RuntimeError('Private repository required')
    state['status']='controller_prepared';api.upload_file(repo_id=REPO,repo_type='dataset',path_or_fileobj=json.dumps(state,indent=2).encode(),path_in_repo=path+'/controller.json',commit_message='Prepare authorized resumable campaign controller')
    source=base64.b64encode(Path(__file__).read_bytes()).decode()
    env={'CAMPAIGN_ID':plan_id,'CAMPAIGN_ROLE':'controller','CAMPAIGN_STATE':json.dumps(state),'CONTROLLER_SOURCE':source,'REMOTE_CAMPAIGN':'1','HF_HOME':'/tmp/campaign-hf-private'}
    entry="import os,base64;exec(compile(base64.b64decode(os.environ['CONTROLLER_SOURCE']),'<campaign-controller>','exec'),{'__name__':'__main__','__file__':'/tmp/campaign.py'})"
    env['REMOTE_ENTRY']=entry
    job=api.run_job(image='python:3.11-slim',command=['bash','-lc','pip install --quiet --disable-pip-version-check huggingface-hub==0.36.2 && exec python -c "$REMOTE_ENTRY"'],env=env,secrets={'HF_TOKEN':get_token()},flavor='cpu-basic',timeout=state.get('controller_timeout_seconds',CPU_SECONDS),namespace='Ruurd')
    resume_command='.venv/bin/python iclr2027_rebuttal/evaluation/campaign.py resume'
    if a.staging.name!='campaign_staging.json':
        import shlex
        resume_command+=' --staging '+shlex.quote(str(a.staging))
    receipt={'controller_job_id':job.id,'url':job.url,'plan_id':plan_id,'input_revision':staging['revision'],'total_compute_ceiling_usd':state['total_compute_ceiling_usd'],'resume_command':resume_command}
    receipt.update(max_gpu_timeout_seconds=state.get('max_gpu_timeout_seconds'),controller_timeout_seconds=state.get('controller_timeout_seconds',CPU_SECONDS))
    receipt_path=HERE/'campaign_launch.json' if a.staging.name=='campaign_staging.json' else a.staging.with_name(a.staging.stem+'_launch.json')
    receipt_path.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':
    if os.getenv('REMOTE_CAMPAIGN')=='1':remote_main()
    else:main()
