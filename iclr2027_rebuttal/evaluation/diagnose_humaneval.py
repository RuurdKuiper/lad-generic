"""CPU-only Linux audit of saved code; generated code runs in unprivileged children."""
import ast,collections,json,os,re,resource,subprocess,sys,tempfile,time
from pathlib import Path

def main():
    from huggingface_hub import hf_hub_download,HfApi
    os.umask(0o077)
    private=Path('/tmp/humaneval-private');private.mkdir(exist_ok=True);private.chmod(0o700)
    repo=os.environ['AUDIT_REPO'];revision=os.environ['AUDIT_REVISION'];plan=os.environ['AUDIT_PLAN']
    def get(name,rev):return Path(hf_hub_download(repo,name,repo_type='dataset',revision=rev))
    examples={r['fingerprint']:r for r in map(json.loads,get('campaign_input/examples.jsonl',os.environ['INPUT_REVISION']).open())}
    task=os.environ.get('AUDIT_TASK','humaneval');model_filter=os.environ.get('AUDIT_MODEL')
    def selected(r):return r['task']==task and (not model_filter or r['model_key']==model_filter)
    rows=[dict(r,audit_cohort='main') for r in map(json.loads,get('campaigns/'+plan+'/results.jsonl',revision).open()) if selected(r)]
    if os.environ.get('AUDIT_SECONDARY_PLAN'):
        rows.extend(dict(r,audit_cohort='corrections') for r in map(json.loads,get('campaigns/'+os.environ['AUDIT_SECONDARY_PLAN']+'/results.jsonl',revision).open()) if selected(r))
    source=get('campaign_input/code/src/diffusion_lm/benchmarks.py',os.environ['INPUT_REVISION']).read_text()
    tree=ast.parse(source);wanted={'_extract_python_code','_run_code'}
    selected=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted],type_ignores=[])
    namespace=dict(re=re,subprocess=subprocess,sys=sys,tempfile=tempfile,Path=Path,BenchmarkExample=object)
    exec(compile(selected,'frozen_benchmark_harness','exec'),namespace)
    original=subprocess.run;last={}
    def limits():
        resource.setrlimit(resource.RLIMIT_CPU,(10,10));resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
        resource.setrlimit(resource.RLIMIT_FSIZE,(1024**2,1024**2));resource.setrlimit(resource.RLIMIT_NPROC,(16,16))
    def guarded(args,**kwargs):
        directory=Path(kwargs['cwd']);directory.chmod(0o755)
        for p in directory.iterdir():p.chmod(0o644)
        kwargs.update(user=65534,group=65534,extra_groups=[],preexec_fn=limits,env={'PATH':'/usr/local/bin:/usr/bin:/bin','HOME':str(directory)})
        try:
            result=original(args,**kwargs)
            last.update(returncode=result.returncode,stderr=result.stderr.decode(errors='replace')[-6000:])
            return result
        except subprocess.TimeoutExpired:
            last.update(returncode=None,stderr='TimeoutExpired');raise
    subprocess.run=guarded
    def score(ex,pred):
        from types import SimpleNamespace
        last.clear();ok=namespace['_run_code'](pred,SimpleNamespace(task=task,metadata=ex['metadata']))
        return {'correct':ok,**last}
    canonical=[]
    for ex in examples.values():
        if ex['task']!=task:continue
        result=score(ex,ex['target']);canonical.append({'sample_index':ex['sample_index'],**result})
    output=[]
    for row in rows:
        ex=examples[row['fingerprint']];result=score(ex,row['prediction'])
        output.append({k:row[k] for k in ['model_key','sample_index','source','correct','fingerprint','audit_cohort']}|{'retest':result})
    report={'revision':revision,'canonical':canonical,'rows':output}
    dest=private/'audit.json';dest.write_text(json.dumps(report,indent=2)+'\n')
    HfApi().upload_file(repo_id=repo,repo_type='dataset',path_or_fileobj=dest,path_in_repo='diagnostics/'+task+'/'+revision+'/audit.json',commit_message='Audit saved '+task+' code with isolated error logging; no GPU generation')
    print(json.dumps({'canonical_passed':sum(x['correct'] for x in canonical),'canonical_total':len(canonical),'predictions_checked':len(output),'score_disagreements':sum(r['correct']!=r['retest']['correct'] for r in output)}),flush=True)

if __name__=='__main__':main()
