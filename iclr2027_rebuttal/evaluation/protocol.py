"""Frozen rebuttal protocol with intentional method-specific output budgets and conservative legacy reuse."""
from __future__ import annotations
import hashlib,json
TASKS=['arc_c','gpqa','hellaswag','mmlu','mmlu_pro','gsm8k','math','humaneval','mbpp']
LENGTHS={'arc_c':64,'gpqa':128,'hellaswag':64,'mmlu':64,'mmlu_pro':64,'gsm8k':256,'math':256,'humaneval':256,'mbpp':128}
# MMLU-Pro intentionally uses the actual historical diffusion length, not the
# manuscript's incorrectly stated 128. AR retains its intentional longer limits.
BASES={'gemma':'google/gemma-2-9b-it','llama':'meta-llama/Llama-3.1-8B-Instruct','qwen':'Qwen/Qwen2.5-7B-Instruct','ministral':'mistralai/Ministral-8B-Instruct-2410'}
MODELS={
 'gemma_d':{'family':'gemma','method':'diffusion','source':'gemma-2-9b-mask/best','eot_token_id':107},
 'gemma_ar':{'family':'gemma','method':'autoregressive'},
 'llada':{'family':'llada','method':'diffusion','repo':'GSAI-ML/LLaDA-8B-Instruct','eot_token_id':126348},
 'qwen_d':{'family':'qwen','method':'diffusion','source':'qwen-2.5-7b-mask/best','eot_token_id':None},
 'qwen_ar':{'family':'qwen','method':'autoregressive','attention_backend':'sdpa'},
 'ministral_d':{'family':'ministral','method':'diffusion','source':'ministral-8b-mask/best','eot_token_id':None},
 'ministral_ar':{'family':'ministral','method':'autoregressive'},
 'llama_25k':{'family':'llama','method':'diffusion','source':'llama-3.1-8b-mask/best','eot_token_id':128009},
 'llama_ar':{'family':'llama','method':'autoregressive'},
 'llama_50k':{'family':'llama','method':'diffusion','source':'llama-3.1-8b-mask-long/checkpoint-50000','eot_token_id':128009}}

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def fingerprint(task,prompt,target):return digest([task,prompt,target])
def settings(model_key,task):
    model=MODELS[model_key];length=LENGTHS[task]
    if model['method']=='autoregressive':return {'max_new_tokens':2048 if task=='mmlu_pro' else 1024}
    return {'sampler':'llada_official','seed':1234,'repetition_penalty':1.0,'max_new_tokens':length,
            'num_steps':length,'block_length':length,'temperature':0.0,'cfg_scale':0.0,'remasking':'low_confidence',
            'logits_eos_inf':task=='humaneval','confidence_eos_eot_inf':task in ['gpqa','mmlu_pro','gsm8k','math','humaneval','mbpp'],
            'proportional_unmask':False,'eot_token_id':model.get('eot_token_id')}

def compatible(old,wanted):
    # Temperature-zero generation has no sampling noise, so changing the seed
    # alone does not invalidate a completed deterministic prediction.
    defaults={'temperature':0.0,'cfg_scale':0.0,'remasking':'low_confidence','logits_eos_inf':False,
              'confidence_eos_eot_inf':False,'proportional_unmask':False,'repetition_penalty':1.0,
              'system_prompt':'','eot_token_id':None}
    for key,value in wanted.items():
        if key=='seed' and wanted.get('temperature')==0:continue
        if old.get(key,defaults.get(key))!=value:return False,key
    if old.get('system_prompt','')!='':return False,'system_prompt'
    return True,None

def select_legacy(records,examples,model_key):
    """Latest compatible result for each exact prompt/target; never rank by score."""
    by_fp={e['fingerprint']:e for e in examples};selected={};rejected={}
    for record in sorted(records,key=lambda r:(r.get('legacy_run',''),r.get('legacy_file',''))):
        if record.get('model_key')!=model_key:continue
        fp=fingerprint(record['task'],record['prompt'],record['target'])
        if fp not in by_fp:continue
        ok,reason=compatible(record.get('inference_settings',{}),settings(model_key,record['task']))
        if not ok:rejected[reason]=rejected.get(reason,0)+1;continue
        selected[fp]=record
    return selected,rejected
