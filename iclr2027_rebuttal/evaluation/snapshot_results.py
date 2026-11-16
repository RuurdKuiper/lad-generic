"""Export selected historical outputs and byte-for-byte source files before expansion."""
from __future__ import annotations
import argparse,collections,concurrent.futures,csv,hashlib,json,os,shutil
from pathlib import Path
from protocol import MODELS,TASKS,select_legacy,fingerprint
HERE=Path(__file__).resolve().parent

def rows(path):
    with Path(path).open() as f:return [json.loads(line) for line in f if line.strip()]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve()
    if out.exists():raise FileExistsError('Refusing to overwrite historical snapshot: '+str(out))
    os.umask(0o077);out.mkdir(parents=True)
    records=rows(HERE/'audit/legacy_records.jsonl');examples=rows(HERE/'bundle/examples.jsonl')
    plan=json.loads((HERE/'bundle/plan.json').read_text());reuse=rows(HERE/'bundle/reuse.jsonl')
    expected={(r['model_key'],r['fingerprint']):(r['prediction'],r['legacy_run']) for r in reuse}
    chosen=[];actual={}
    for key in MODELS:
        selected,_=select_legacy(records,examples,key)
        for fp,record in selected.items():
            actual[(key,fp)]=(record['prediction'],record['legacy_run']);chosen.append(record)
    if actual!=expected:raise ValueError('Export selection disagrees with frozen pilot inputs')
    sources={Path(r['legacy_file']) for r in chosen};artifacts=set(sources)
    for source in sources:
        for candidate in [source.parent/'summary.json',source.parents[4]/'run.json',source.parents[4]/'summary.json']:
            if candidate.is_file():artifacts.add(candidate)
    def copy_source(source):
        run_root=source.parents[4] if source.name=='results.jsonl' else None
        # Determine the enclosing benchmark run without relying on manifest depth.
        for parent in source.parents:
            if parent.name=='benchmark_runs':
                relative=source.relative_to(parent);break
        else:raise ValueError('Unexpected source location: '+str(source))
        target=out/'source_runs'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
        if sha(target)!=sha(source):raise ValueError('Source copy verification failed')
        return {'original':str(source),'copy':str(target.relative_to(out)),'sha256':sha(target)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:source_manifest=list(pool.map(copy_source,sorted(artifacts)))
    grouped=collections.defaultdict(list)
    for r in chosen:grouped[(r['model_key'],r['task'])].append(r)
    counts=[]
    for (key,task),items in sorted(grouped.items()):
        target=out/'selected'/key/task/'results.jsonl';target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('w') as f:
            for r in sorted(items,key=lambda r:fingerprint(r['task'],r['prompt'],r['target'])):f.write(json.dumps(r,ensure_ascii=False)+'\n')
        k=sum(r['correct'] is True for r in items);counts.append({'model':key,'task':task,'n':len(items),'recorded_correct':k,'recorded_accuracy':k/len(items)})
    with (out/'counts.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(counts[0]));writer.writeheader();writer.writerows(counts)
    for name in ['plan.json','reuse.jsonl','examples.jsonl']:shutil.copy2(HERE/'bundle'/name,out/name)
    for name in ['protocol.py','audit_summary.md','staging.json']:shutil.copy2(HERE/name,out/name)
    readme=['# Historical results before additional evaluation','','Snapshot date: 8 November 2026. Original Drive files are unchanged.','','This preserves the latest compatible historical outputs, including both successful and failed answers. “Selected” means the predictions chosen for reuse, not only correct answers or finalized rescored results. Historical correctness flags are preserved; uniform rescoring and checkpoint replay verification remain pending.','','- `selected/<model>/<task>/results.jsonl`: the selected full per-question records, including prompts, targets, predictions, settings, and original run/file provenance.','- `source_runs/`: byte-for-byte copies of each contributing results file and available run/group metadata. These can also contain superseded records; `selected/` defines the retained set.','- `counts.csv`: actual denominators and recorded successes by model and task.','- `manifest.json`: source paths, SHA-256 hashes, frozen plan identity and file integrity checks.','- `plan.json`, `reuse.jsonl`, `examples.jsonl`, `protocol.py`: exact reuse decisions, frozen inputs and selection rules.','- `audit_summary.md`: partial reruns, superseded scores and known limitations.','','Selection uses the latest compatible prediction per exact model/task/prompt/target; compatible older records fill partial reruns. Accuracy never determines selection. Intentional longer AR generation limits are preserved.','','**Private:** includes benchmark questions/answers and gated GPQA content; do not publish this folder.','','| Model | Selected predictions |','|---|---:|']
    for key in MODELS:readme.append(f"| {key} | {sum(c['n'] for c in counts if c['model']==key)} |")
    readme+=['',f'Total: **{len(chosen):,} selected predictions** across {len(grouped)} model/task groups.']
    (out/'README.md').write_text('\n'.join(readme)+'\n')
    files={str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*')) if f.is_file()}
    manifest={'schema':1,'snapshot_date':'2026-11-08','timezone':'Africa/Windhoek','plan_id':plan['plan_id'],
              'selected_predictions':len(chosen),'model_task_groups':len(grouped),'selection_matches_staged_reuse':True,
              'originals_modified':False,'source_files':source_manifest,'files_sha256':files,'counts':counts}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for relative,expected_sha in files.items():
        if sha(out/relative)!=expected_sha:raise ValueError('Snapshot verification failed: '+relative)
    for file in out.rglob('*'):
        if file.is_file():file.chmod(0o400)
    print(json.dumps({'snapshot':str(out),'selected_predictions':len(chosen),'groups':len(grouped),'source_artifacts':len(source_manifest),'hashes_verified':len(files),'read_only_files':True},indent=2))
if __name__=='__main__':main()
