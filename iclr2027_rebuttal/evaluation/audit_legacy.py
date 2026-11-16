"""Read-only audit of original Colab records; never executes generated code."""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, re
from pathlib import Path

TASKS=['arc_c','gpqa','hellaswag','mmlu','mmlu_pro','gsm8k','math','humaneval','mbpp']
ALIASES={
 'gemma_d':'gemma-2-9b-mask/best','qwen_d':'qwen-2.5-7b-mask/best','ministral_d':'ministral-8b-mask/best',
 'llama_25k':'llama-3.1-8b-mask/best','llama_50k':'llama-3.1-8b-mask-long/checkpoint-50000',
 'gemma_ar':'google/gemma-2-9b-it','qwen_ar':'Qwen/Qwen2.5-7B-Instruct',
 'ministral_ar':'mistralai/Ministral-8B-Instruct-2410','llama_ar':'meta-llama/Llama-3.1-8B-Instruct',
 'llada':'llada:GSAI-ML/LLaDA-8B-Instruct'}

def fingerprint(record):
    return hashlib.sha256(json.dumps([record['task'],record['prompt'],record['target']],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def model_key(record):
    name=record.get('model','')
    for key,alias in ALIASES.items():
        if name.casefold()==alias.casefold():return key
    if name.casefold() in ['llama-3.1-8b-mask-long/final']:return 'llama_50k'
    return None

def read_group(path):
    records=[]; invalid=0
    try:
        for line in path.read_text().split('\n'):
            if not line.strip():continue
            try:r=json.loads(line)
            except json.JSONDecodeError:invalid+=1;continue
            key=model_key(r)
            if key is not None and r.get('task') in TASKS:
                r['model_key']=key;r['legacy_run']=path.parents[4].name
                r['legacy_file']=str(path);r['item_fingerprint']=fingerprint(r)
                records.append(r)
        if not records:return None
        unique={}
        conflicts=0
        for r in records:
            fp=r['item_fingerprint']
            if fp in unique and unique[fp]['prediction']!=r['prediction']:conflicts+=1
            unique[fp]=r
        out=list(unique.values())
        return {'model_key':records[0]['model_key'],'task':records[0]['task'],'run_id':records[0]['legacy_run'],
                'path':str(path),'count':len(out),'correct':sum(r['correct'] is True for r in out),
                'invalid_lines':invalid,'duplicate_lines':len(records)-len(out),'conflicting_duplicates':conflicts,
                'settings':records[0].get('inference_settings',{}),'records':out}
    except Exception as e:return {'path':str(path),'error':type(e).__name__+': '+str(e)}

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--since',default='20260918');args=p.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    paths=[]
    for run in sorted(args.root.iterdir()):
        if run.is_dir() and run.name>=args.since:paths.extend(run.glob('models/*/*/*/results.jsonl'))
    print(f'Auditing {len(paths)} result files from runs since {args.since}',flush=True)
    groups=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for index,g in enumerate(pool.map(read_group,paths),1):
            if g is not None:groups.append(g)
            if index%40==0:print(f'Read {index}/{len(paths)} files; relevant groups {len(groups)}',flush=True)
    summaries=[{k:v for k,v in g.items() if k!='records'} for g in groups]
    (args.out/'legacy_groups.json').write_text(json.dumps(summaries,indent=2)+'\n')
    with (args.out/'legacy_records.jsonl').open('w') as f:
        for g in groups:
            for row in g.get('records',[]):f.write(json.dumps(row,ensure_ascii=False)+'\n')
    for key in ALIASES:
        print(key,flush=True)
        for task in TASKS:
            matches=sorted([g for g in groups if g.get('model_key')==key and g.get('task')==task],key=lambda g:g['run_id'])
            if matches:
                g=matches[-1];print(f"  {task}: {g['correct']}/{g['count']} {g['run_id']} settings={g['settings']}",flush=True)
    print('Audit saved. Original records unmodified; no model inference or generated code executed.',flush=True)
if __name__=='__main__':main()
