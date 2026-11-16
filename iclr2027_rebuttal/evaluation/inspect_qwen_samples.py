"""Inspect saved Qwen outputs without executing generated Python or renting compute."""
import ast,collections,json,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'src'))
from diffusion_lm.benchmarks import extract_answer,score_prediction,BenchmarkExample,_extract_python_code

def inspect(rows,examples,tokenizer):
    summary={};cases=[]
    for task in ['gsm8k','humaneval']:
        for source in ['legacy_rescored','new_generation']:
            selected=[r for r in rows if r['model_key']=='qwen_ar' and r['task']==task and r['source']==source]
            stats={'n':len(selected),'correct':sum(r['correct'] for r in selected),'near_output_cap':0,'syntax_errors':0,'final_numeric_matches_reference':0,'final_numeric_matches_but_scored_false':0,'scorer_disagreements':0,'without_hash_answer':0}
            for r in selected:
                ex=examples[r['fingerprint']];prediction=r['prediction'];ids=tokenizer.encode(prediction,add_special_tokens=False)
                if len(ids)>=1020:stats['near_output_cap']+=1
                extra={'decoded_retokenized_length':len(ids)}
                if task=='gsm8k':
                    hashes=re.findall(r'####\s*([^\n]+)',prediction)
                    if not hashes:stats['without_hash_answer']+=1
                    final=extract_answer(hashes[-1] if hashes else prediction,'gsm8k');target=extract_answer(ex['target'],'gsm8k')
                    final_matches=final==target
                    stats['final_numeric_matches_reference']+=final_matches
                    stats['final_numeric_matches_but_scored_false']+=final_matches and not r['correct']
                    current=score_prediction(BenchmarkExample(task,str(ex['example_id']),ex['prompt'],ex['target'],ex['kind'],ex['metadata']),prediction)
                    stats['scorer_disagreements']+=current!=r['correct']
                    extra.update(extracted_final=final,extracted_target=target)
                else:
                    code=_extract_python_code(prediction,ex['metadata']['entry_point'])
                    try:ast.parse(code);extra['syntax']='valid'
                    except SyntaxError as err:stats['syntax_errors']+=1;extra['syntax']='invalid';extra['syntax_error']=str(err)
                if source=='new_generation' and not r['correct']:
                    cases.append({'task':task,'sample_index':r['sample_index'],'fingerprint':r['fingerprint'],'prompt':ex['prompt'],'prediction':prediction,'reference':ex['target'],**extra})
            summary[task+'/'+source]=stats
    return summary,cases

def main():
    from dotenv import load_dotenv
    from transformers import AutoTokenizer
    load_dotenv(HERE.parents[1]/'.env')
    folder=HERE/'qwen_diagnostic';plan=json.loads((HERE/'campaign_bundle/plan.json').read_text())
    spec=plan['models']['qwen_ar'];tokenizer=AutoTokenizer.from_pretrained(spec['base_repo'],revision=spec['base_revision'],cache_dir=HERE/'cache')
    with (folder/'results.jsonl').open() as f:rows=[json.loads(s) for s in f if s.strip()]
    with (HERE/'campaign_bundle/examples.jsonl').open() as f:examples={r['fingerprint']:r for r in (json.loads(s) for s in f if s.strip())}
    summary,cases=inspect(rows,examples,tokenizer)
    (folder/'sample_inspection.json').write_text(json.dumps({'summary':summary,'cases':cases},indent=2)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
