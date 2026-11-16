"""Read-only HumanEval status checks; never writes cloud state or manages jobs."""
import argparse,json,time
from pathlib import Path

def main():
    from huggingface_hub import HfApi,hf_hub_download
    from dotenv import load_dotenv
    here=Path(__file__).resolve().parent;load_dotenv(here.parents[1]/'.env')
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args()
    api=HfApi();stage=json.loads((here/'humaneval_staging.json').read_text());repo=stage['repo'];path='campaigns/'+stage['plan_id']
    terminal={'COMPLETED','ERROR','FAILED','CANCELED','CANCELLED','DELETED'}
    while True:
        revision=api.dataset_info(repo).sha
        state=json.loads(Path(hf_hub_download(repo,path+'/controller.json',repo_type='dataset',revision=revision)).read_text())
        job_id=state['gpu_jobs'][-1]['job_id']
        job=api.inspect_job(job_id=job_id,namespace='Ruurd')
        progress=json.loads(Path(hf_hub_download(repo,path+'/progress.json',repo_type='dataset',revision=revision)).read_text())
        print(json.dumps({'source_revision':revision,'controller_status':state['status'],'gpu_job_id':job_id,'actual_gpu_status':job.status.stage,'progress':progress},indent=2),flush=True)
        if args.once or job.status.stage in terminal:return
        time.sleep(30)

if __name__=='__main__':main()
