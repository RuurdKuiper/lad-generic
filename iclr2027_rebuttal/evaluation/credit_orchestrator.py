"""Low-cost CPU wait/stage/handoff for one explicitly approved GPU replacement."""
from __future__ import annotations
import argparse,base64,hashlib,io,json,math,os,subprocess,sys,time,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO='Ruurd/iclr2027-rebuttal-eval'
GPU_IMAGE='pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385'
CPU_TIMEOUT=5400
GPU_BOOTSTRAP="""import os,subprocess,sys
from huggingface_hub import snapshot_download
os.umask(0o077)
bundle=snapshot_download(os.environ['INPUT_REPO'],repo_type='dataset',revision=os.environ['INPUT_REVISION'],allow_patterns=['input/**'],local_dir='/tmp/byod-input')+'/input'
subprocess.run([sys.executable,'-m','pip','install','--quiet','--disable-pip-version-check','-r',bundle+'/requirements.txt'],check=True)
os.chdir(bundle)
os.execv(sys.executable,[sys.executable,bundle+'/worker.py','--repo',os.environ['INPUT_REPO'],'--phase','pilot','--seconds',os.environ['WORKER_SECONDS'],'--expand-pilot'])
"""

def budget_limits(prior_cost,credit=4.95,price_per_minute=.041667):
    cpu_max=math.ceil(CPU_TIMEOUT/60)*.000167
    minutes=math.floor((credit-prior_cost-cpu_max-.05)/price_per_minute)
    if minutes<10:raise ValueError('Insufficient remaining approved credits')
    return {'approved_credit_usd':credit,'prior_cost_reserved_usd':prior_cost,'cpu_max_usd':cpu_max,
            'gpu_minutes':minutes,'gpu_max_usd':minutes*price_per_minute,'total_max_usd':prior_cost+cpu_max+minutes*price_per_minute,
            'gpu_timeout_seconds':minutes*60,'worker_seconds':minutes*60-300}

def remote_main():
    from huggingface_hub import HfApi,get_token,hf_hub_download,snapshot_download
    from huggingface_hub.errors import HfHubHTTPError
    os.umask(0o077);api=HfApi();started=time.monotonic();limit=json.loads(os.environ['CREDIT_LIMITS'])
    old=json.loads(os.environ['SOURCE_STAGING']);raw=base64.b64decode(os.environ['OVERRIDES_ZIP'])
    base=Path(snapshot_download(REPO,repo_type='dataset',revision=old['revision'],allow_patterns=['input/**'],local_dir='/tmp/credit-input'))/'input'
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for name in z.namelist():
            if name not in ['plan.json','worker.py','report.py','protocol.py','requirements.txt']:raise ValueError('Unexpected override file')
            (base/name).write_bytes(z.read(name))
    plan=json.loads((base/'plan.json').read_text());resume=plan['resume_source']
    source=hf_hub_download(resume['repo'],resume['filename'],repo_type='dataset',revision=resume['revision'])
    (base/'resume.jsonl').write_bytes(Path(source).read_bytes())
    sys.path.insert(0,str(base))
    from worker import verify
    verify(base,phase='pilot')
    if not api.dataset_info(REPO).private:raise RuntimeError('Refusing public evaluation repository')
    # No GPU is allocated while waiting for Hub commit access to recover.
    while True:
        try:
            api.upload_file(path_or_fileobj=json.dumps({'status':'approved_credit_pilot_staging','plan_id':plan['plan_id']}).encode(),repo_id=REPO,repo_type='dataset',path_in_repo='control/credit-pilot-ready.json',commit_message='Check recovered commit access for approved pilot')
            break
        except HfHubHTTPError as exc:
            if exc.response is None or exc.response.status_code not in [429,500,502,503,504]:raise
            try:delay=float(exc.response.headers.get('Retry-After','600'))
            except ValueError:delay=600
            delay=max(120,delay)
            if time.monotonic()-started+delay>CPU_TIMEOUT-300:raise RuntimeError('Commit access still blocked; GPU was not launched') from exc
            print(json.dumps({'status':'waiting_for_hub_commit_window','http_status':exc.response.status_code,'retry_seconds':delay,'gpu_launched':False}),flush=True)
            time.sleep(delay)
    commit=api.upload_folder(repo_id=REPO,repo_type='dataset',folder_path=base,path_in_repo='input',allow_patterns=['*.py','plan.json','examples.jsonl','reuse.jsonl','resume.jsonl','requirements.txt','code/**'],commit_message='Stage approved Gemma-first credit-bounded continuation')
    env={'INPUT_REPO':REPO,'INPUT_REVISION':commit.oid,'WORKER_SECONDS':str(limit['worker_seconds']),
         'HF_HOME':'/tmp/byod-hf-private','HF_HUB_CACHE':'/tmp/byod-hf-private/hub','TOKENIZERS_PARALLELISM':'false','BOOTSTRAP':GPU_BOOTSTRAP}
    from huggingface_hub.utils import get_session
    resp=get_session().get('https://huggingface.co/api/jobs/hardware',headers=api._build_hf_headers(),timeout=30);resp.raise_for_status()
    hw={x['name']:x for x in resp.json()}
    if float(hw['a100-large']['unitCostUSD'])>.041667:raise RuntimeError('A100 price increased; no GPU launched')
    # One call only. No retry or automatic follow-up GPU jobs.
    job=api.run_job(image=GPU_IMAGE,command=['bash','-lc','python -m pip install --quiet --disable-pip-version-check huggingface-hub==0.36.2 && exec python -c "$BOOTSTRAP"'],env=env,secrets={'HF_TOKEN':get_token()},flavor='a100-large',timeout=limit['gpu_timeout_seconds'],namespace='Ruurd')
    receipt={'gpu_job_id':job.id,'gpu_job_url':job.url,'plan_id':plan['plan_id'],'input_revision':commit.oid,'limits':limit,'queue':plan['pilot_model_order'],'automatic_followup_gpu_jobs':False}
    print(json.dumps(receipt),flush=True)
    api.upload_file(path_or_fileobj=json.dumps(receipt,indent=2).encode(),repo_id=REPO,repo_type='dataset',path_in_repo='control/credit-pilot-launch.json',commit_message='Record single approved credit-bounded GPU handoff')

def local_main():
    from dotenv import load_dotenv
    from huggingface_hub import HfApi,get_token
    from huggingface_hub.utils import get_session
    load_dotenv(HERE.parents[1]/'.env');p=argparse.ArgumentParser();p.add_argument('--launch',action='store_true');p.add_argument('--approved',action='store_true');a=p.parse_args()
    history=json.loads((HERE/'launches.json').read_text())
    if any(x.get('status')!='cancelled_for_user_updated_budget_and_queue' for x in history):raise RuntimeError('Prior GPU job is not recorded as cancelled')
    prior=sum(x['conservative_compute_usd'] for x in history);limit=budget_limits(prior)
    print(json.dumps(limit,indent=2))
    if not a.launch:return
    if not a.approved:raise RuntimeError('Explicitly approved replacement required')
    receipt=HERE/'credit_orchestrator_job.json'
    if receipt.exists():raise RuntimeError('Orchestrator already submitted; inspect it instead of duplicating jobs')
    api=HfApi()
    for item in history:
        stage=api.inspect_job(job_id=item['job_id'],namespace='Ruurd').status.stage
        if stage not in ['CANCELED','CANCELLED','COMPLETED','ERROR','FAILED']:raise RuntimeError('Original job is still active')
    resp=get_session().get('https://huggingface.co/api/jobs/hardware',headers=api._build_hf_headers(),timeout=30);resp.raise_for_status();hw={x['name']:x for x in resp.json()}
    if float(hw['cpu-basic']['unitCostUSD'])>.000167 or float(hw['a100-large']['unitCostUSD'])>.041667:raise RuntimeError('Compute price increased')
    source_staging=json.loads((HERE/'staging.json').read_text());encoded=base64.b64encode((HERE/'credit_overrides.zip').read_bytes()).decode()
    code=base64.b64encode(Path(__file__).read_bytes()).decode()
    bootstrap="import os,base64;exec(compile(base64.b64decode(os.environ['ORCHESTRATOR_SOURCE']),'<credit-orchestrator>','exec'),{'__name__':'__main__','__file__':'/tmp/credit_orchestrator.py'})"
    env={'ORCHESTRATOR_SOURCE':code,'REMOTE_ORCHESTRATOR':'1','CREDIT_LIMITS':json.dumps(limit),'SOURCE_STAGING':json.dumps(source_staging),
         'OVERRIDES_ZIP':encoded,'HF_HOME':'/tmp/hf-private'}
    command=['bash','-lc','pip install --quiet --disable-pip-version-check huggingface-hub==0.36.2 && exec python -c "$REMOTE_BOOTSTRAP"']
    env['REMOTE_BOOTSTRAP']=bootstrap
    job=api.run_job(image='python:3.11-slim',command=command,env=env,secrets={'HF_TOKEN':get_token()},flavor='cpu-basic',timeout=CPU_TIMEOUT,namespace='Ruurd')
    data={'orchestrator_job_id':job.id,'url':job.url,'status':'waiting/staging','limits':limit,'source_input_revision':source_staging['revision'],'user_approved_credit_usd':4.95}
    receipt.write_text(json.dumps(data,indent=2)+'\n');print(json.dumps(data,indent=2))
if __name__=='__main__':
    if os.getenv('REMOTE_ORCHESTRATOR')=='1':remote_main()
    else:local_main()
