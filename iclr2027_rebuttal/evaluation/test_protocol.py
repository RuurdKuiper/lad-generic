"""Offline checks of provenance selection, statistics and budget guards."""
import copy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from protocol import settings,fingerprint,select_legacy
from report import summarize,wilson

def record(run,pred,correct=False,task='gsm8k',key='gemma_d'):
    return {'model_key':key,'task':task,'prompt':'question','target':'answer','prediction':pred,'correct':correct,
            'legacy_run':run,'legacy_file':run,'inference_settings':settings(key,task)}
def example(task='gsm8k'):
    return {'task':task,'prompt':'question','target':'answer','fingerprint':fingerprint(task,'question','answer')}
def test_newest_supersedes_even_if_lower_score():
    older=record('20260918','old',True);newer=record('20260925','new',False)
    chosen,_=select_legacy([newer,older],[example()],'gemma_d')
    assert chosen[example()['fingerprint']]['prediction']=='new'
def test_partial_rerun_keeps_compatible_other_questions():
    old=record('20260918','old');second=copy.deepcopy(old);second['prompt']='other'
    newer=record('20260925','new')
    ex2={'task':'gsm8k','prompt':'other','target':'answer','fingerprint':fingerprint('gsm8k','other','answer')}
    chosen,_=select_legacy([old,second,newer],[example(),ex2],'gemma_d')
    assert len(chosen)==2 and chosen[ex2['fingerprint']]['prediction']=='old'
def test_changed_prompt_and_settings_not_reused():
    bad=record('20260925','bad');bad['inference_settings']['max_new_tokens']=1024
    chosen,rejected=select_legacy([bad],[example()],'gemma_d')
    assert not chosen and rejected=={'max_new_tokens':1}
    bad=record('20260925','bad');bad['target']='changed'
    assert not select_legacy([bad],[example()],'gemma_d')[0]
def test_ar_retains_intentional_longer_limit():
    old=record('20260925','old',key='gemma_ar');old['inference_settings']['max_new_tokens']=1024
    assert select_legacy([old],[example()],'gemma_ar')[0]
    old['inference_settings']['max_new_tokens']=256
    assert not select_legacy([old],[example()],'gemma_ar')[0]
def test_real_denominators_and_wilson_edges():
    rows=[{'model_key':'gemma_ar','task':'humaneval','fingerprint':str(i),'correct':i<37} for i in range(50)]
    summary=summarize(rows)['models']['gemma_ar']
    assert summary['tasks']['humaneval']['accuracy']==.74
    assert summary['tasks']['humaneval']['n']==50 and summary['macro_mean'] is None
    assert wilson(0,10)[0]>=-1e-15 and wilson(10,10)[1]<=1+1e-15

def test_unicode_jsonl_records_use_physical_newlines(tmp_path):
    import json
    from worker import read_rows
    rows=[{'prediction':'first\u2028second\u2029third'},{'prediction':'another'}]
    path=tmp_path/'rows.jsonl';path.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows))
    assert read_rows(path)==rows

def test_pilot_ready_does_not_authorize_full_run(tmp_path):
    import hashlib,json
    from protocol import digest
    from worker import verify
    (tmp_path/'examples.jsonl').write_text('');(tmp_path/'reuse.jsonl').write_text('')
    h=hashlib.sha256(b'').hexdigest()
    plan={'examples_sha256':h,'reuse_sha256':h,'code_hashes':{},'models':{},'pilot_ready':True,'checkpoints_ready':False}
    plan['plan_id']=digest(plan);(tmp_path/'plan.json').write_text(json.dumps(plan))
    assert verify(tmp_path,phase='pilot')['pilot_ready']
    import pytest
    with pytest.raises(ValueError,match='only the replay pilot'):verify(tmp_path,phase='full')
    plan['target_per_task']=500;(tmp_path/'plan.json').write_text(json.dumps(plan))
    with pytest.raises(ValueError,match='Plan hash'):verify(tmp_path,phase='pilot')

def test_upload_throttle_is_independent_of_item_count():
    from worker import sync_due
    # A fast CPU pass must not generate a commit every ten items.
    assert not any(sync_due(t,0) for t in range(120))
    assert sync_due(120,0)
    assert not sync_due(180,120)
    assert sync_due(180,120,force=True)
    assert not sync_due(180,120,next_retry=300,force=True)

def test_task_interleaving_preserves_prefixes():
    from worker import interleave_tasks
    examples=[{'task':'arc_c','sample_index':i} for i in [125,126]]+[{'task':'gsm8k','sample_index':125}]
    assert [(x['task'],x['sample_index']) for x in interleave_tasks(examples)]==[('arc_c',125),('gsm8k',125),('arc_c',126)]

def test_replacement_accounts_for_prior_cost_and_cpu_wait():
    from credit_orchestrator import budget_limits
    limits=budget_limits(.291669)
    assert limits['gpu_minutes']==110
    assert limits['total_max_usd']<4.95
    assert limits['worker_seconds']<limits['gpu_timeout_seconds']
    assert budget_limits(.8)['gpu_minutes']<limits['gpu_minutes']
