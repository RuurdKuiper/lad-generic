"""Read-only Hugging Face metadata/access checks; no paid API calls."""
from pathlib import Path
import json
from dotenv import load_dotenv
from huggingface_hub import HfApi,hf_hub_download,hf_hub_url,get_hf_file_metadata
from huggingface_hub.utils import get_session
ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT.parents[1]/'.env')
api=HfApi();who=api.whoami()
models={}
for repo in ['Ruurd/BYOD-Gemma-2-9B','Ruurd/BYOD-Qwen2.5-7B','Ruurd/BYOD-Ministral-8B','Ruurd/BYOD-Llama-3.1-8B','GSAI-ML/LLaDA-8B-Instruct','google/gemma-2-9b-it','meta-llama/Llama-3.1-8B-Instruct','Qwen/Qwen2.5-7B-Instruct','mistralai/Ministral-8B-Instruct-2410']:
    m=api.model_info(repo,files_metadata=True)
    entry={'repo_id':repo,'revision':m.sha,'files':[]}
    for f in m.siblings:
        item={'name':f.rfilename,'size':f.size}
        if f.lfs:item['sha256']=f.lfs.sha256
        entry['files'].append(item)
    for name in ['resolved_config.json','adapter_config.json','config.json']:
        if any(f.rfilename==name for f in m.siblings):
            try:
                path=hf_hub_download(repo,name,revision=m.sha,cache_dir=ROOT/'cache')
                entry[name]=json.loads(Path(path).read_text())
            except Exception as e:entry[name+'_error']=type(e).__name__
    models[repo]=entry;print('Checked model',repo,flush=True)
datasets={}
for repo in ['cais/mmlu','TIGER-Lab/MMLU-Pro','Rowan/hellaswag','allenai/ai2_arc','openai/gsm8k','HuggingFaceH4/MATH-500','Idavidrein/gpqa','openai/openai_humaneval','google-research-datasets/mbpp']:
    d=api.dataset_info(repo)
    entry={'repo_id':repo,'revision':d.sha,'gated':d.gated}
    if d.gated:
        f=next(s.rfilename for s in d.siblings if s.rfilename.endswith(('.csv','.parquet')))
        try:get_hf_file_metadata(hf_hub_url(repo,f,repo_type='dataset',revision=d.sha),token=api.token or True);entry['data_access']=True
        except Exception as e:entry['data_access']=False;entry['access_error']=type(e).__name__
    datasets[repo]=entry;print('Checked dataset',repo,flush=True)
headers=api._build_hf_headers()
resp=get_session().get('https://huggingface.co/api/jobs/hardware',headers=headers,timeout=30)
hardware=resp.json() if resp.ok else {'http_status':resp.status_code}
lock={'account':who['name'],'models':models,'datasets':datasets,'hardware':hardware}
(ROOT/'hub_lock.json').write_text(json.dumps(lock,indent=2,default=str)+'\n')
print('Saved pinned revisions, access checks and live hardware metadata. No job launched.',flush=True)
