"""Offline safety and correctness checks for budgeted, resumable execution."""
import sys
from pathlib import Path
from datetime import datetime,timedelta,timezone
sys.path.insert(0,str(Path(__file__).resolve().parent))
from campaign import block_seconds,observed_cost_upper,RATE,ACTIVE_STAGES,TERMINAL
from campaign_worker import validated_rows,remaining_examples,queue_order,scheduled_keys,no_progress_status
import pytest

def state():return {'prior_compute_reserved_usd':4.890069,'total_compute_ceiling_usd':75,'cpu_reservations':[{'reserved_usd':.37}],'gpu_jobs':[]}

def test_provider_scheduling_is_an_active_state():
    assert 'SCHEDULING' in ACTIVE_STAGES
    assert not (ACTIVE_STAGES & TERMINAL)

def test_cumulative_timeout_cap_is_independent_of_cash_refunds():
    s=state();s['max_gpu_timeout_seconds']=36000
    s['gpu_jobs']=[{'timeout_seconds':14400,'reserved_usd':10.05,'cost_upper_usd':1} for _ in range(2)]
    assert block_seconds(s)==7200
    s['gpu_jobs'].append({'timeout_seconds':7200,'reserved_usd':5.05,'cost_upper_usd':1})
    assert block_seconds(s)==0

def test_shutdown_margin_does_not_trigger_false_replay_review():
    assert no_progress_status([],False,580,1000)=='time_limit'
    assert no_progress_status([],False,579,1000)=='needs_review'
    assert no_progress_status(['gemma_d'],False,579,1000)=='waiting_for_original_assets'
    assert no_progress_status([],True,579,1000)=='interrupted'
def test_blocks_never_exceed_remaining_budget():
    s=state()
    while (seconds:=block_seconds(s))>=1200:
        reserved=(seconds//60+1)*RATE
        assert seconds<=14400
        s['gpu_jobs'].append({'reserved_usd':reserved})
        assert s['prior_compute_reserved_usd']+sum(c['reserved_usd'] for c in s['cpu_reservations'])+sum(j['reserved_usd'] for j in s['gpu_jobs'])<=75
    assert len(s['gpu_jobs'])>=6

def test_interrupted_block_releases_only_observed_conservative_allowance():
    s=state();s['gpu_jobs']=[{'reserved_usd':241*RATE}]
    old=block_seconds(s);start=datetime(2026,11,8,tzinfo=timezone.utc)
    cost=observed_cost_upper(start,start+timedelta(minutes=20),14400)
    assert cost==pytest.approx(21*RATE)
    s['gpu_jobs'][0]['cost_upper_usd']=cost
    assert block_seconds(s)>=old
    assert observed_cost_upper(start,start+timedelta(hours=8),14400)==pytest.approx(241*RATE)

def fixtures():
    ex={'fingerprint':'fp','task':'gsm8k'}
    plan={'plan_id':'new','resume_parent_plan_ids':['old'],'models':{'gemma_ar':{'settings':{'gsm8k':{'max_new_tokens':1024}}}}}
    row={'plan_id':'old','model_key':'gemma_ar','fingerprint':'fp','task':'gsm8k','prediction':'answer','correct':True,'settings':{'max_new_tokens':1024}}
    return ex,plan,row

def test_resume_skips_saved_questions_and_validates_protocol():
    ex,plan,row=fixtures();done=validated_rows([row,row],plan,[ex])
    assert len(done)==1 and done[('gemma_ar','fp')]['plan_id']=='new'
    assert remaining_examples([ex],done,'gemma_ar')==[]
    changed=dict(row,settings={'max_new_tokens':256})
    with pytest.raises(ValueError,match='settings'):validated_rows([changed],plan,[ex])
    with pytest.raises(ValueError,match='Unknown checkpoint question'):validated_rows([dict(row,fingerprint='other')],plan,[ex])
    with pytest.raises(ValueError,match='Conflicting duplicate'):validated_rows([row,dict(row,prediction='different')],plan,[ex])

def test_fair_rotation_prioritizes_models_with_less_saved_coverage():
    done={('gemma_ar',str(i)):{} for i in range(206)}
    done.update({('gemma_d',str(i)):{} for i in range(125)})
    assert queue_order(['gemma_ar','gemma_d'],done,250)==['gemma_d','gemma_ar']

def test_subset_campaign_never_injects_an_unrequested_model():
    plan={'models':{'qwen_ar':{},'gemma_d':{}},'model_priority':['qwen_ar','gemma_d']}
    assert scheduled_keys(plan,{},2000,set())==['qwen_ar','gemma_d']
    plan['models']['llada']={};plan['model_priority'].append('llada')
    assert scheduled_keys(plan,{},2000,set())[0]=='llada'
    assert scheduled_keys(plan,{},2000,{'llada'})==['qwen_ar','gemma_d','llada']

def test_byod_never_falls_back_to_unverified_published_weights(tmp_path,monkeypatch):
    import huggingface_hub,json
    from campaign_worker import original_spec
    manifest=tmp_path/'assets.json';manifest.write_text(json.dumps({'models':{}}))
    monkeypatch.setattr(huggingface_hub,'hf_hub_download',lambda *a,**k:str(manifest))
    class Info:sha='pinned'
    class API:
        def dataset_info(self,*a,**k):return Info()
    spec={'method':'diffusion','adapter_repo':'unverified/published','source':'original/best'}
    assert original_spec('gemma_d',spec,API(),'private/repo',tmp_path)==(None,None)
