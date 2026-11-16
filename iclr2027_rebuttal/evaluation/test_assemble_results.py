import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from assemble_results import select_results,merge_remaining

def row(key,fp,source,correct,**kwargs):
    return {'model_key':key,'fingerprint':fp,'source':source,'correct':correct,'task':'mbpp',**kwargs}

def test_user_selected_fresh_cohort_replaces_history_regardless_of_score():
    old=row('gemma_d','old','legacy_rescored',False)
    rerun=row('gemma_d','old','new_generation',True)
    added=row('gemma_d','added','new_generation',True)
    selected,discarded=select_results([old],[rerun,added])
    assert selected==[rerun,added]
    assert discarded[0]['reason']=='historical_outcome_superseded_by_user_selected_fresh_cohort'
    old_better=row('gemma_d','old','legacy_rescored',True)
    rerun_worse=row('gemma_d','old','new_generation',False)
    selected,_=select_results([old_better],[rerun_worse])
    assert selected==[rerun_worse]

def test_verified_qwen_historical_answers_remain_reusable():
    old=row('qwen_ar','old','legacy_rescored',False)
    duplicate=row('qwen_ar','old','legacy_rescored',False)
    selected,discarded=select_results([old],[duplicate])
    assert selected==[old] and discarded[0]['reason']=='retain_original_outcome'

def test_qwen_eager_answers_are_excluded_regardless_of_correctness():
    eager=[row('qwen_ar','a','new_generation',True),row('qwen_ar','b','new_generation',False)]
    replacement=row('qwen_ar','a','new_generation',False,attention_backend='sdpa')
    selected,discarded=select_results(eager,[replacement])
    assert selected==[replacement] and len(discarded)==2
    with pytest.raises(ValueError,match='SDPA'):select_results([],eager)

def test_deferred_tasks_and_unexpected_models_cannot_enter_corrections():
    with pytest.raises(ValueError,match='HumanEval'):select_results([],[row('gemma_d','a','new_generation',True,task='humaneval')])
    with pytest.raises(ValueError,match='Unexpected'):select_results([],[row('llada','a','new_generation',True)])

def test_humaneval_cohort_must_be_complete_before_replacing_historical_gemma():
    main=[row('llada',str(i),'legacy_rescored',True,task='humaneval') for i in range(164)]
    historical=row('gemma_d','0','legacy_rescored',True,task='humaneval')
    main.append(historical)
    fresh=[row('gemma_d',str(i),'new_generation',False,task='humaneval',attention_backend='sdpa') for i in range(164)]
    selected,_=select_results(main,[],fresh[:20])
    assert [r for r in selected if r['model_key']=='gemma_d']==[historical]
    selected,_=select_results(main,[],fresh)
    assert [r for r in selected if r['model_key']=='gemma_d']==fresh
    with pytest.raises(ValueError,match='Duplicate'):select_results(main,[],fresh+[fresh[0]])
    wrong=[dict(r,attention_backend='eager') for r in fresh]
    with pytest.raises(ValueError,match='SDPA'):select_results(main,[],wrong)

def test_parallel_merge_adds_only_disjoint_continuations_and_preserves_answers():
    old=row('llada','a','new_generation',False,prediction='old')
    resumed=dict(old,plan_id='continuation')
    added=row('llada','b','new_generation',True,prediction='new')
    gemma=row('gemma_d','c','new_generation',False,prediction='fresh',attention_backend='sdpa')
    result=merge_remaining([old],[[resumed,added],[gemma]])
    assert result==[resumed,added,gemma]
    with pytest.raises(ValueError,match='overlap'):merge_remaining([old],[[resumed],[resumed]])
    with pytest.raises(ValueError,match='changed'):merge_remaining([old],[[dict(resumed,prediction='replacement')]])
    with pytest.raises(ValueError,match='model/task'):merge_remaining([],[[row('qwen_ar','a','new_generation',True,prediction='x')]])
    with pytest.raises(ValueError,match='fresh SDPA'):merge_remaining([],[[dict(gemma,source='legacy_rescored')]])
