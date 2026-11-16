"""Stage private inputs, preview a bounded job, or launch after explicit approval."""
from __future__ import annotations
import argparse,json,os,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
IMAGE='pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385'
REPO='Ruurd/iclr2027-rebuttal-eval'

def main():
    from dotenv import load_dotenv
    from huggingface_hub import HfApi,get_token
    from huggingface_hub.utils import get_session
    load_dotenv(HERE.parents[1]/'.env');api=HfApi()
    p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','preview','launch']);p.add_argument('--phase',choices=['pilot','full'],default='pilot')
    p.add_argument('--approved',action='store_true',help='Only use after user explicitly approves this paid phase');a=p.parse_args()
    if a.action=='stage':
        from worker import verify
        plan=verify(HERE/'bundle',phase='pilot')
        api.create_repo(REPO,repo_type='dataset',private=True,exist_ok=True)
        if not api.dataset_info(REPO).private:raise RuntimeError('Refusing public staging repository')
        commit=api.upload_folder(repo_id=REPO,repo_type='dataset',folder_path=HERE/'bundle',path_in_repo='input',
            commit_message='Stage exact paper checkpoints and private reproducible rebuttal evaluation',
            allow_patterns=['*.py','requirements.txt','plan.json','examples.jsonl','reuse.jsonl','code/**']+(['checkpoints/*/*'] if plan['checkpoints_ready'] else []))
        receipt={'repo':REPO,'revision':commit.oid,'plan_id':plan['plan_id'],'private':True,'image':IMAGE}
        (HERE/'staging.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2));return
    receipt=json.loads((HERE/'staging.json').read_text());hard_seconds=7200 if a.phase=='pilot' else 100800
    seconds=6600 if a.phase=='pilot' else 100200
    # Runs reference only an immutable private input commit. Results use a separate path.
    bootstrap="""import os,subprocess,sys
from huggingface_hub import snapshot_download
os.umask(0o077)
bundle=snapshot_download(os.environ['INPUT_REPO'],repo_type='dataset',revision=os.environ['INPUT_REVISION'],allow_patterns=['input/**'],local_dir='/tmp/byod-input')+'/input'
subprocess.run([sys.executable,'-m','pip','install','--quiet','--disable-pip-version-check','-r',bundle+'/requirements.txt'],check=True)
os.chdir(bundle)
os.execv(sys.executable,[sys.executable,bundle+'/worker.py','--repo',os.environ['INPUT_REPO'],'--phase',os.environ['EVAL_PHASE'],'--seconds',os.environ['WORKER_SECONDS']])
"""
    command=['bash','-lc','python -m pip install --quiet --disable-pip-version-check huggingface-hub==0.36.2 && exec python -c "$BOOTSTRAP"']
    env={'INPUT_REPO':receipt['repo'],'INPUT_REVISION':receipt['revision'],'EVAL_PHASE':a.phase,'WORKER_SECONDS':str(seconds),
         'HF_HOME':'/tmp/byod-hf-private','HF_HUB_CACHE':'/tmp/byod-hf-private/hub','TOKENIZERS_PARALLELISM':'false','BOOTSTRAP':bootstrap}
    preview={'repo':receipt['repo'],'input_revision':receipt['revision'],'plan_id':receipt['plan_id'],'phase':a.phase,'hardware':'a100-large',
             'image':IMAGE,'external_timeout_seconds':hard_seconds,'max_compute_usd_approx':hard_seconds/3600*2.5,
             'worker_stop_seconds':seconds,'launch_requested':a.action=='launch','automatic_followup_jobs':False}
    print(json.dumps(preview,indent=2))
    if a.action!='launch':return
    from worker import verify
    plan=verify(HERE/'bundle',phase=a.phase)
    if plan['plan_id']!=receipt['plan_id']:raise RuntimeError('Local plan changed after staging')
    if not a.approved:raise RuntimeError('Paid launch requires explicit user approval and --approved')
    if not api.dataset_info(REPO).private:raise RuntimeError('Evaluation repository must remain private')
    history_path=HERE/'launches.json';history=json.loads(history_path.read_text()) if history_path.exists() else []
    if any(x['phase']==a.phase for x in history):raise RuntimeError('Phase already submitted; inspect/resume rather than duplicate charges')
    if sum(x['timeout_seconds'] for x in history)+hard_seconds>108000:raise RuntimeError('Thirty-hour total reservation limit exceeded')
    response=get_session().get('https://huggingface.co/api/jobs/hardware',headers=api._build_hf_headers(),timeout=30);response.raise_for_status()
    hardware=next(x for x in response.json() if x['name']=='a100-large')
    if hardware['unitLabel']!='minute' or float(hardware['unitCostUSD'])>0.041667:raise RuntimeError('GPU price changed; review estimate before launching')
    job=api.run_job(image=IMAGE,command=command,env=env,secrets={'HF_TOKEN':get_token()},flavor='a100-large',timeout=hard_seconds,namespace='Ruurd')
    item={'job_id':job.id,'phase':a.phase,'timeout_seconds':hard_seconds,'input_revision':receipt['revision'],'plan_id':receipt['plan_id']}
    history.append(item);history_path.write_text(json.dumps(history,indent=2)+'\n');print(json.dumps(item,indent=2))
if __name__=='__main__':main()
