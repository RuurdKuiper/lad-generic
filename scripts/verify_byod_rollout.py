#!/usr/bin/env python3
"""Check deployed UI defaults and both inference modes on each BYOD Space."""
import concurrent.futures
import argparse
import json
import os
from pathlib import Path
import time

from evaluate_ending_controls import PlainOutput

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/bigram/byod_rollout'


def verify(record, token, simplified_ui=False):
    from huggingface_hub import HfApi
    from gradio_client import Client
    api=HfApi(token=token)
    deadline=time.monotonic()+900
    while True:
        runtime=api.get_space_runtime(record['space'])
        stage=str(runtime.stage)
        if stage=='RUNNING':break
        if 'ERROR' in stage:raise RuntimeError(f"{record['space']}: {stage}")
        if time.monotonic()>deadline:raise TimeoutError(f"{record['space']}: {stage}")
        print(json.dumps(dict(space=record['space'],stage=stage)),flush=True)
        time.sleep(20)
    assert api.repo_info(record['space'],repo_type='space').sha==record['revision']
    client=Client(record['space'],token=token,verbose=False)
    props={c['props'].get('label'):c['props'] for c in client.config['components'] if c.get('props',{}).get('label')}
    expected={'Temperature':2.,'Top-k':16,'Remasking strategy':'Bigram Viterbi',
        'New tokens':64,'Denoising steps':64,'Block length':64,
        'Delay EOS/EOT retention (longer answers)':True,
        'Early stopping':True}
    actual={label:props[label]['value'] for label in expected}
    assert actual==expected,(record['space'],actual)
    if simplified_ui:
        components={c['id']:c['props'] for c in client.config['components']}
        dependency=next(d for d in client.config['dependencies'] if d.get('api_name')=='generate')
        params=client.view_api(print_info=False,return_format='dict')['named_endpoints']['/generate']['parameters']
        inputs={parameter['parameter_name']:components[cid] for parameter,cid in zip(params,dependency['inputs'])}
        hidden={'bigram_eos_delay_penalty':10.,'generation_seed':-1,'measure_decoding':False,
                'bigram_scoring_method':'PMI bigram','bigram_remasking_confidence':'Diffusion probability',
                'pmi_min_count':1,'pmi_clip':2.}
        for name,value in hidden.items():
            assert inputs[name]['visible'] is False and inputs[name]['value']==value,(name,inputs[name])
        assert inputs['bigram_model_path']['visible'] is False
        assert inputs['bigram_model_path']['value'].endswith('/bigram.pt')
        assert 'Reproducible evaluation' not in props
        assert not any('Bigram Viterbi selects a sequence jointly' in (c.get('info') or '') for c in components.values())
    shared=dict(question='Explain the difference between weather and climate.',
        system_prompt='You are a helpful assistant.',max_new_tokens=64,num_steps=16,
        block_length=64,pause_per_step=0.,trajectory_color_mode='No coloring',
        revisable_tokens=False,ar_check_interval=4,delay_eos_eot=True,early_stopping=False,
        bigram_scoring_method='PMI bigram',pmi_min_count=1,pmi_clip=2.,generation_seed=1234,
        bigram_remasking_confidence='Diffusion probability')
    results=[]
    for method,strategy,temperature,k,penalty in [('pmi','Bigram Viterbi',2.,16,10.),
                                               ('baseline','Confidence-guided',.7,3,1.)]:
        options=dict(shared,remasking_strategy=strategy,temperature=temperature,top_k=k,
                     bigram_eos_delay_penalty=penalty,measure_decoding=method=='pmi')
        start=time.monotonic()
        status,html=client.submit(**options,api_name='/generate').result(timeout=600)
        plain=PlainOutput();plain.feed(html)
        assert plain.text.strip(),status
        assert 'Denoising step 16/16' in status,status
        metrics=json.loads(status.split('Decoding metrics: ',1)[1]) if 'Decoding metrics: ' in status else None
        if method=='pmi':assert metrics['selector_calls']==16,metrics
        results.append(dict(method=method,text=plain.text,status=status,metrics=metrics,
                            options=options,seconds=time.monotonic()-start))
        print(json.dumps(dict(space=record['space'],method=method,passed=True)),flush=True)
    return dict(space=record['space'],revision=record['revision'],stage=stage,
                defaults=actual,results=results,passed=True)


def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--credential-name')
    parser.add_argument('--simplified-ui',action='store_true')
    args=parser.parse_args();OUT=args.output
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env')
    if args.credential_name:
        from huggingface_hub.utils._auth import get_stored_tokens
        token=get_stored_tokens().get(args.credential_name)
        if not token:raise RuntimeError('Selected credential unavailable')
    else:token=os.getenv('HF_TOKEN')
    records=json.loads((OUT/'deployment.json').read_text())
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        jobs={pool.submit(verify,record,token,args.simplified_ui):record for record in records}
        for job in concurrent.futures.as_completed(jobs):
            try:result=job.result()
            except Exception as exc:result=dict(space=jobs[job]['space'],passed=False,error=str(exc))
            results.append(result)
            (OUT/'hosted_verification.json').write_text(json.dumps(results,indent=2)+'\n')
            print(json.dumps({k:v for k,v in result.items() if k not in ['results','defaults']}),flush=True)
    assert len(results)==len(records) and all(r['passed'] for r in results),results


if __name__=='__main__':main()
