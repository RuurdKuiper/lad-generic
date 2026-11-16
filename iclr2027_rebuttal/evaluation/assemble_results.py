"""Select outcomes by protocol/provenance, never by correctness, then rescore MATH."""
import argparse,hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'src'))
POLICY='user_selected_fresh_gemma_and_corrected_qwen_sdpa_v2'
SCORING_VERSION='final_answer_math_verify_0.8.0_v3'

def select_results(main,corrections,humaneval=None):
    selected={};discarded=[]
    for row in main:
        identity=(row['model_key'],row['fingerprint'])
        # Known eager-path outputs are retained in raw inputs, but cannot be
        # used as evaluation outcomes, even when they happened to pass.
        if row['model_key']=='qwen_ar' and row['source']=='new_generation':
            discarded.append({'identity':identity,'reason':'qwen_eager_cohort'});continue
        if identity in selected:raise ValueError('Duplicate main outcome')
        selected[identity]=dict(row)
    for row in corrections:
        key=row['model_key'];identity=(key,row['fingerprint'])
        if key not in ['gemma_d','qwen_ar']:raise ValueError('Unexpected correction model')
        if row['task']=='humaneval':raise ValueError('HumanEval corrections remain deferred')
        existing=selected.get(identity)
        if existing and existing['source']=='legacy_rescored':
            if key=='gemma_d':
                discarded.append({'identity':identity,'reason':'historical_outcome_superseded_by_user_selected_fresh_cohort'})
                selected[identity]=dict(row);continue
            discarded.append({'identity':identity,'reason':'retain_original_outcome'});continue
        if key=='qwen_ar' and row['source']=='new_generation' and row.get('attention_backend')!='sdpa':
            raise ValueError('Qwen replacement must explicitly use SDPA')
        if existing:raise ValueError('Conflicting new outcomes require explicit review')
        selected[identity]=dict(row)
    if humaneval is not None:
        allowed={r['fingerprint'] for r in main if r['task']=='humaneval'}
        groups={key:[] for key in ['qwen_ar','gemma_d']}
        for row in humaneval:
            if row['task']!='humaneval' or row['model_key'] not in groups:
                raise ValueError('HumanEval correction contains an unexpected model/task')
            groups[row['model_key']].append(row)
        for key,group in groups.items():
            fps=[r['fingerprint'] for r in group]
            if len(fps)!=len(set(fps)):raise ValueError('Duplicate HumanEval outcomes')
            # Adopt each complete task cohort, never replace part of Gemma's
            # historical cohort and silently report a mixed environment.
            if len(group)!=164:
                discarded.append({'model_key':key,'reason':'HumanEval_correction_incomplete','saved':len(group)});continue
            if set(fps)!=allowed or len(allowed)!=164:
                raise ValueError('HumanEval correction question identities changed')
            for row in group:
                if row['source']=='new_generation' and row.get('attention_backend')!='sdpa':
                    raise ValueError('HumanEval replacement requires explicit SDPA provenance')
                if key=='gemma_d' and row['source']!='new_generation':
                    raise ValueError('Gemma HumanEval must use the full fresh cohort')
                identity=(key,row['fingerprint']);old=selected.get(identity)
                if key=='qwen_ar' and old and old['source']=='legacy_rescored':
                    if old['prediction']!=row['prediction']:
                        raise ValueError('Historical Qwen HumanEval answer changed')
                    continue
                if old:discarded.append({'identity':identity,'reason':'complete_corrected_HumanEval_cohort'})
                selected[identity]=dict(row)
    return list(selected.values()),discarded

def merge_remaining(selected,lanes):
    allowed={'gemma_d','llada','qwen_d','ministral_d','ministral_ar','llama_25k','llama_50k','llama_ar'}
    result={(r['model_key'],r['fingerprint']):dict(r) for r in selected};seen=set()
    for lane in lanes:
        for row in lane:
            key=row['model_key'];identity=(key,row['fingerprint'])
            if key not in allowed or row['task']=='humaneval':raise ValueError('Unexpected parallel continuation model/task')
            if identity in seen:raise ValueError('Parallel lanes overlap or contain duplicate outcomes')
            seen.add(identity)
            if key=='gemma_d' and (row['source']!='new_generation' or row.get('attention_backend')!='sdpa'):
                raise ValueError('Parallel Gemma must retain the fresh SDPA cohort')
            if identity in result and result[identity]['prediction']!=row['prediction']:
                raise ValueError('Continuation changed an existing answer')
            result[identity]=dict(row)
    return list(result.values())

def main():
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,default=HERE/'generation_diagnostic/nov15')
    p.add_argument('--humaneval-results',type=Path);p.add_argument('--remaining-results',type=Path,action='append',default=[]);a=p.parse_args()
    folder=a.snapshot.parent/'nov15_gemma';folder.mkdir(exist_ok=True)
    def read(name):
        with (a.snapshot/name).open() as f:return [json.loads(x) for x in f if x.strip()]
    original=read('main_results.jsonl');corrected=read('corrections_results.jsonl');human=None
    if a.humaneval_results:
        with a.humaneval_results.open() as f:human=[json.loads(x) for x in f if x.strip()]
        stage=json.loads((HERE/'humaneval_staging.json').read_text())
        if any(r['plan_id']!=stage['plan_id'] for r in human):raise ValueError('Unexpected HumanEval correction plan')
    rows,discarded=select_results(original,corrected,human)
    policy=POLICY if human is None else POLICY+'+complete_humaneval'
    lane_sources=[];lanes=[]
    known={json.loads((HERE/('parallel_'+name+'_staging.json')).read_text())['plan_id'] for name in ['gemma','others']} if a.remaining_results else set()
    for path in a.remaining_results:
        with path.open() as f:lane=[json.loads(x) for x in f if x.strip()]
        ids={r['plan_id'] for r in lane}
        if len(ids)!=1 or not ids<=known:raise ValueError('Unexpected parallel continuation plan')
        lanes.append(lane);lane_sources.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'plan_id':next(iter(ids))})
    if lanes:rows=merge_remaining(rows,lanes);policy+='+parallel_continuation'
    with (HERE/'campaign_bundle/examples.jsonl').open() as f:examples={r['fingerprint']:r for r in map(json.loads,f)}
    if any(r['fingerprint'] not in examples or examples[r['fingerprint']]['task']!=r['task'] for r in rows):raise ValueError('Unknown selected question/task')
    from diffusion_lm.benchmarks import _math_answers_equal,_normalize_math_answer
    import importlib.metadata
    verifier_version=importlib.metadata.version('math-verify')
    changes=[]
    def rescore(row,group):
        row=dict(row)
        if row['task']=='math':
            ex=examples[row['fingerprint']];new=bool(_math_answers_equal(row['prediction'],ex['target']))
            changes.append({'group':group,'model_key':row['model_key'],'sample_index':row['sample_index'],'fingerprint':row['fingerprint'],'before':row['correct'],'after':new,'prediction_final':_normalize_math_answer(row['prediction']),'target_final':_normalize_math_answer(ex['target'])})
            row.update(previous_correct=row['correct'],correct=new,scoring_version=SCORING_VERSION)
        row['selection_policy']=policy
        return row
    rows=[rescore(r,'expanded') for r in rows]
    baseline=[rescore(r,'baseline') for r in original if r['source']=='legacy_rescored']
    tasks=['arc_c','gpqa','hellaswag','mmlu','mmlu_pro','gsm8k','math','mbpp']
    def stats(items,key,active_tasks=tasks):
        groups={t:[r for r in items if r['model_key']==key and r['task']==t] for t in active_tasks}
        return {'mean':100*sum(sum(r['correct'] for r in x)/len(x) for x in groups.values())/len(active_tasks),'tasks':{t:{'correct':sum(r['correct'] for r in x),'n':len(x),'accuracy':100*sum(r['correct'] for r in x)/len(x)} for t,x in groups.items()}}
    summary={k:{'before':stats(baseline,k),'after':stats(rows,k)} for k in dict.fromkeys(r['model_key'] for r in original)}
    manifest={'source':json.loads((a.snapshot/'source.json').read_text()),'selection_policy':policy,'math_verify_version':verifier_version,'scorer_sha256':hashlib.sha256((HERE.parents[1]/'src/diffusion_lm/benchmarks.py').read_bytes()).hexdigest(),'discarded':discarded,'math_scoring_audit':changes,'summary':summary}
    if lane_sources:manifest['parallel_sources']=lane_sources
    counts={(key,t):sum(r['model_key']==key and r['task']==t for r in rows) for key in summary for t in tasks+['humaneval']}
    manifest['all_sample_targets_complete']=all(n==(164 if task=='humaneval' else 250) for (key,task),n in counts.items())
    if human is not None:
        manifest['humaneval_correction']={'path':str(a.humaneval_results),'sha256':hashlib.sha256(a.humaneval_results.read_bytes()).hexdigest(),'plan_id':stage['plan_id']}
        ready=all(sum(r['model_key']==key and r['task']=='humaneval' for r in rows)==164 for key in summary)
        manifest['all_humaneval_complete']=ready
        if ready:manifest['summary_nine_tasks']={k:{'before':stats(baseline,k,tasks+['humaneval']),'after':stats(rows,k,tasks+['humaneval'])} for k in summary}
    (folder/'assembled_results.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    (folder/'assembled_audit.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for k,s in summary.items():
        print(k,'mean',round(s['before']['mean'],2),round(s['after']['mean'],2),'MATH',s['before']['tasks']['math'],s['after']['tasks']['math'],flush=True)
    print('Gemma MBPP',summary['gemma_d']['before']['tasks']['mbpp'],summary['gemma_d']['after']['tasks']['mbpp'],flush=True)
    print('Math score changes',sum(x['before']!=x['after'] for x in changes),flush=True)

if __name__=='__main__':main()
