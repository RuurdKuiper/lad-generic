"""Prepare private, immutable inputs and reuse decisions locally; no GPU jobs."""
from __future__ import annotations
import argparse,concurrent.futures,hashlib,json,os,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;REPO=HERE.parents[1]
sys.path.insert(0,str(REPO/'src'))
from protocol import MODELS,BASES,TASKS,settings,fingerprint,digest,select_legacy

def snapshot_code(out):
    target=out/'code';target.mkdir(parents=True,exist_ok=True)
    shutil.copytree(REPO/'src/diffusion_lm',target/'src/diffusion_lm',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copy2(REPO/'evaluate_benchmarks.py',target/'evaluate_benchmarks.py')
    for name in ['protocol.py','worker.py','report.py','requirements.txt']:
        shutil.copy2(HERE/name,out/name)
    return {str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted([*target.rglob('*.py'),*(out/name for name in ['protocol.py','worker.py','report.py','requirements.txt'])])}

def copy_checkpoint(source,target):
    target.mkdir(parents=True,exist_ok=True);hashes={}
    wanted={'.json','.safetensors','.pt','.jinja'}
    for p in sorted(source.iterdir()):
        if not p.is_file() or p.suffix not in wanted:continue
        h=hashlib.sha256()
        with p.open('rb') as src,(target/p.name).open('wb') as dst:
            while block:=src.read(8*1024*1024):h.update(block);dst.write(block)
        hashes[p.name]=h.hexdigest()
    if 'resolved_config.json' not in hashes and (source.parent/'resolved_config.json').is_file():
        p=source.parent/'resolved_config.json';shutil.copy2(p,target/p.name);hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    if 'adapter_model.safetensors' not in hashes:raise ValueError('Missing adapter weights: '+str(source))
    return hashes

def main():
    p=argparse.ArgumentParser();p.add_argument('--drive-root',type=Path,required=True);p.add_argument('--target',type=int,default=250)
    p.add_argument('--out',type=Path,default=HERE/'bundle');p.add_argument('--skip-checkpoints',action='store_true');p.add_argument('--published-pilot',action='store_true',help='Stage a replay pilot using the configuration-identical published Gemma adapter; full runs remain blocked');a=p.parse_args()
    from dotenv import load_dotenv
    load_dotenv(REPO/'.env')
    lock=json.loads((HERE/'hub_lock.json').read_text());out=a.out;out.mkdir(parents=True,exist_ok=True);os.chmod(out,0o700)
    from diffusion_lm.benchmarks import load_benchmark,_benchmark_spec
    import datasets
    original_load=datasets.load_dataset
    def pinned_load(path,*args,**kwargs):
        kwargs['revision']=lock['datasets'][path]['revision'];return original_load(path,*args,**kwargs)
    datasets.load_dataset=pinned_load
    examples=[];dataset_specs={}
    for task in TASKS:
        repo,config,split=_benchmark_spec(task,'test');dataset_specs[task]={'repo':repo,'config':config,'split':split,'revision':lock['datasets'][repo]['revision']}
        # Load beyond the target to fill any exact duplicate question slots.
        loaded=load_benchmark(task,'test',min(a.target+20,500),str(HERE/'cache/datasets'),os.getenv('HF_TOKEN'))
        seen=set();n=0
        for ex in loaded:
            fp=fingerprint(task,ex.prompt,ex.answer)
            if fp in seen:continue
            seen.add(fp);examples.append({'task':task,'sample_index':n,'example_id':ex.example_id,'prompt':ex.prompt,'target':ex.answer,'kind':ex.kind,'metadata':ex.metadata,'fingerprint':fp});n+=1
            if n==a.target:break
        print('Prepared',task,n,'unique questions',flush=True)
    with (out/'examples.jsonl').open('w') as f:
        for row in examples:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    old=[json.loads(l) for l in (HERE/'audit/legacy_records.jsonl').read_text().split('\n') if l.strip()]
    reuse=[];counts=[]
    for key in MODELS:
        selected,rejected=select_legacy(old,examples,key)
        for fp,row in selected.items():
            reuse.append({'model_key':key,'fingerprint':fp,'prediction':row['prediction'],'recorded_correct':row['correct'],
                          'legacy_run':row['legacy_run'],'legacy_example_id':row['example_id'],'inference_settings':row['inference_settings']})
        for task in TASKS:
            total=sum(e['task']==task for e in examples);n=sum(e['task']==task and e['fingerprint'] in selected for e in examples)
            counts.append({'model':key,'task':task,'target':total,'reusable_generations':n,'requires_generation':total-n})
        print('Reuse',key,len(selected),'/',len(examples),'rejected historical settings',rejected,flush=True)
    with (out/'reuse.jsonl').open('w') as f:
        for row in reuse:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    model_specs={key:{**spec,'settings':{task:settings(key,task) for task in TASKS}} for key,spec in MODELS.items()}
    for key,spec in model_specs.items():
        if spec['family']!='llada':
            spec['base_repo']=BASES[spec['family']];spec['base_revision']=lock['models'][spec['base_repo']]['revision']
        else:spec['revision']=lock['models'][spec['repo']]['revision']
    if a.published_pilot:
        spec=model_specs['gemma_d'];repo='Ruurd/BYOD-Gemma-2-9B';published=lock['models'][repo]
        source=a.drive_root/'outputs'/spec['source'];local_adapter=json.loads((source/'adapter_config.json').read_text())
        local_run=json.loads((source.parent/'resolved_config.json').read_text())
        if local_adapter!=published['adapter_config.json'] or local_run!=published['resolved_config.json']:raise ValueError('Published Gemma configuration differs from original')
        spec.update(adapter_repo=repo,adapter_revision=published['revision'],published_config_matches_original=True)
    if not a.skip_checkpoints and not a.published_pilot:
        for key,spec in model_specs.items():
            if 'source' not in spec:continue
            source=a.drive_root/'outputs'/spec['source'];destination=out/'checkpoints'/key
            print('Snapshot exact paper checkpoint',key,flush=True)
            spec['checkpoint_hashes']=copy_checkpoint(source,destination);spec['checkpoint_path']='checkpoints/'+key
    hashes=snapshot_code(out)
    plan={'schema':1,'target_per_task':a.target,'account':lock['account'],'datasets':dataset_specs,'models':model_specs,
          'examples_sha256':hashlib.sha256((out/'examples.jsonl').read_bytes()).hexdigest(),
          'reuse_sha256':hashlib.sha256((out/'reuse.jsonl').read_bytes()).hexdigest(),'code_hashes':hashes,
          'max_gpu_hours':30,'hardware':'a100-large','max_compute_usd':75,'pilot_only_seconds':6600,
          'source_policy':'latest compatible per model/task/prompt; no score-based selection',
          'counts':counts,'pilot_ready':a.published_pilot or not a.skip_checkpoints,'checkpoints_ready':not a.skip_checkpoints and not a.published_pilot,
          'pilot_checkpoint_note':'Published Gemma has identical adapter/training configuration; full weight identity is unverified. Replay pilot only; full evaluation blocked until resolved.' if a.published_pilot else 'Original checkpoint snapshots'}
    plan['plan_id']=digest(plan);(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    (HERE/'reuse_plan.json').write_text(json.dumps({'plan_id':plan['plan_id'],'counts':counts},indent=2)+'\n')
    print('Prepared',len(examples),'items/model;',len(reuse),'reusable generations;',sum(x['requires_generation'] for x in counts),'new/rerun evaluations. No job launched.',flush=True)
if __name__=='__main__':main()
