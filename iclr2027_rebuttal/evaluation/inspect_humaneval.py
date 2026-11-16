"""Static analysis of HumanEval outputs; never executes generated code."""
import ast,collections,json,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'src'))
from diffusion_lm.benchmarks import _extract_python_code

def main():
    from transformers import AutoTokenizer,PreTrainedTokenizerFast
    plan=json.loads((HERE/'campaign_bundle/plan.json').read_text())
    with (HERE/'campaign_bundle/examples.jsonl').open() as f:examples={r['fingerprint']:r for r in map(json.loads,f)}
    with (HERE/'qwen_diagnostic/results.jsonl').open() as f:rows=[r for r in map(json.loads,f) if r['task']=='humaneval']
    tokenizers={};output={};cases=[]
    for key,spec in plan['models'].items():
        if key=='llada':repo=spec['repo'];rev=spec['revision']
        else:repo=spec['base_repo'];rev=spec['base_revision']
        if repo not in tokenizers:
            cls=PreTrainedTokenizerFast if key=='llada' else AutoTokenizer
            local={'llama':'llama_25k','ministral':'ministral_d'}.get(spec['family'])
            location=HERE/'original_checkpoints'/local if local else repo
            try:tokenizers[repo]=cls.from_pretrained(location,revision=rev,cache_dir=HERE/'cache',local_files_only=True)
            except (ValueError,ImportError,OSError):tokenizers[repo]=None
        tokenizer=tokenizers[repo];groups={}
        for source in ['legacy_rescored','new_generation']:
            selected=[r for r in rows if r['model_key']==key and r['source']==source]
            stats={'n':len(selected),'correct':sum(r['correct'] for r in selected),'syntax_errors':0,'near_cap':0,'syntax_errors_near_cap':0,'missing_entry_point':0,'canonical_body_over_cap':0,'tokenizer_available':tokenizer is not None}
            for r in selected:
                ex=examples[r['fingerprint']];entry=ex['metadata']['entry_point'];code=_extract_python_code(r['prediction'],entry)
                cap=spec['settings']['humaneval']['max_new_tokens'];length=len(tokenizer.encode(r['prediction'],add_special_tokens=False)) if tokenizer else None;near=length is not None and length>=cap-8
                stats['near_cap']+=near
                if tokenizer:stats['canonical_body_over_cap']+=len(tokenizer.encode(ex['target'],add_special_tokens=False))>cap
                hasentry=bool(re.search(rf'(?m)^\s*def\s+{re.escape(entry)}\s*\(',code))
                stats['missing_entry_point']+=not hasentry
                if not hasentry:
                    first=next((s for s in code.splitlines() if s.strip()),'')
                    if first and not first[:1].isspace():code='\n'.join('    '+s if s else s for s in code.splitlines())
                    code=ex['metadata']['prompt'].rstrip('\n')+'\n'+code
                error=None
                try:ast.parse(code)
                except SyntaxError as e:error=str(e);stats['syntax_errors']+=1;stats['syntax_errors_near_cap']+=near
                if source=='new_generation' and not r['correct']:
                    cases.append({'model_key':key,'sample_index':r['sample_index'],'prediction':r['prediction'],'syntax_error':error,'retokenized_length':length,'near_cap':near})
            groups[source]=stats
        groups['index_bands']={}
        for lo,hi in [(0,50),(50,95),(95,125),(125,164)]:
            sel=[r for r in rows if r['model_key']==key and lo<=r['sample_index']<hi]
            groups['index_bands'][f'{lo}:{hi}']={'n':len(sel),'correct':sum(r['correct'] for r in sel)}
        output[key]=groups
    folder=HERE/'humaneval_diagnostic';(folder/'static.json').write_text(json.dumps({'summary':output,'failed_new_cases':cases},indent=2)+'\n')
    print(json.dumps(output,indent=2))
if __name__=='__main__':main()
