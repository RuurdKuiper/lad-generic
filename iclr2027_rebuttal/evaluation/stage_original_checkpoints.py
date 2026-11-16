"""Copy and hash original Drive checkpoints in parallel, then stage private assets."""
from __future__ import annotations
import concurrent.futures,hashlib,json,os,shutil,sys,time
from pathlib import Path
from dotenv import load_dotenv
from huggingface_hub import HfApi
HERE=Path(__file__).resolve().parent
DRIVE=Path('/Users/rkuiper/Library/CloudStorage/GoogleDrive-ruurd.kuiper@gmail.com/My Drive/lad-generic-results/outputs')
SOURCES={'gemma_d':'gemma-2-9b-mask/best','qwen_d':'qwen-2.5-7b-mask/best','ministral_d':'ministral-8b-mask/best','llama_25k':'llama-3.1-8b-mask/best','llama_50k':'llama-3.1-8b-mask-long/checkpoint-50000'}
REPOS={'gemma_d':'Ruurd/BYOD-Gemma-2-9B','qwen_d':'Ruurd/BYOD-Qwen2.5-7B','ministral_d':'Ruurd/BYOD-Ministral-8B','llama_25k':'Ruurd/BYOD-Llama-3.1-8B'}
REPO='Ruurd/iclr2027-rebuttal-eval'
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while block:=f.read(8*1024*1024):h.update(block)
    return h.hexdigest()
def copy_one(key):
    src=DRIVE/SOURCES[key];out=HERE/'original_checkpoints'/key;out.mkdir(parents=True,exist_ok=True)
    for f in src.iterdir():
        if not f.is_file() or f.suffix not in ['.safetensors','.pt','.json','.jinja','.model']:continue
        dst=out/f.name
        # Resume an interrupted local copy after checking its existing prefix.
        offset=dst.stat().st_size if dst.exists() else 0
        if offset>f.stat().st_size:raise ValueError('Oversized partial copy')
        with f.open('rb') as source:
            if offset:
                with dst.open('rb') as old:
                    remaining=offset
                    while remaining:
                        block=old.read(min(8*1024*1024,remaining))
                        if source.read(len(block))!=block:raise ValueError('Partial copy prefix differs: '+key)
                        remaining-=len(block)
            with dst.open('ab') as target:
                while block:=source.read(8*1024*1024):target.write(block);target.flush()
        if dst.stat().st_size!=f.stat().st_size:raise ValueError('Incomplete checkpoint')
    if not (out/'resolved_config.json').exists():shutil.copy2(src.parent/'resolved_config.json',out/'resolved_config.json')
    hashes={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (HERE/'original_checkpoints'/f'{key}.json').write_text(json.dumps({'model':key,'source':str(src),'hashes':hashes},indent=2)+'\n')
    return key,out,hashes

def main():
    load_dotenv(HERE.parents[1]/'.env');os.umask(0o077);api=HfApi();lock=json.loads((HERE/'hub_lock.json').read_text())
    if not api.dataset_info(REPO).private:raise RuntimeError('Assets must remain private')
    manifest_path=HERE/'original_assets.json';manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'schema':1,'models':{}}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures=[pool.submit(copy_one,key) for key in SOURCES]
        for future in concurrent.futures.as_completed(futures):
            key,folder,hashes=future.result();print('Copied and verified original',key,flush=True)
            commit=api.upload_folder(repo_id=REPO,repo_type='dataset',folder_path=folder,path_in_repo='assets/checkpoints/'+key,commit_message='Preserve verified original paper checkpoint '+key)
            record={'model':key,'source':SOURCES[key],'repo':REPO,'revision':commit.oid,'path':'assets/checkpoints/'+key,'hashes':hashes}
            if key in REPOS:
                published={f['name']:f.get('sha256') for f in lock['models'][REPOS[key]]['files']}
                names=[n for n in hashes if n.endswith(('.pt','.safetensors'))]
                record['published_tensor_files_match']=all(hashes[n]==published.get(n) for n in names)
            manifest['models'][key]=record;manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
            api.upload_file(repo_id=REPO,repo_type='dataset',path_or_fileobj=manifest_path,path_in_repo='assets/manifest.json',commit_message='Record original checkpoint provenance '+key)
            print('Staged original',key,'revision',commit.oid,flush=True)
if __name__=='__main__':main()
