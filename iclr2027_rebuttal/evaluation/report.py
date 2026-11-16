"""Reports from verified item outcomes; equal task weights and paired bootstrap."""
import argparse,json,math,random
from pathlib import Path
from protocol import TASKS,MODELS

def wilson(k,n):
    if not n:return None
    z=1.959963984540054;p=k/n;d=1+z*z/n
    c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [c-h,c+h]

def summarize(rows,paired=True):
    latest={(r['model_key'],r['fingerprint']):r for r in rows};out={}
    for key in MODELS:
        tasks={}
        for task in TASKS:
            selected=[r for r in latest.values() if r['model_key']==key and r['task']==task and isinstance(r.get('correct'),bool)]
            n=len(selected);k=sum(r['correct'] for r in selected)
            tasks[task]={'n':n,'correct':k,'accuracy':k/n if n else None,'wilson95':wilson(k,n)}
        complete=all(x['n']>1 for x in tasks.values());mean=se=None
        if complete:
            mean=sum(x['accuracy'] for x in tasks.values())/len(TASKS)
            se=math.sqrt(sum(x['accuracy']*(1-x['accuracy'])/(x['n']-1) for x in tasks.values()))/len(TASKS)
        out[key]={'tasks':tasks,'macro_mean':mean,'macro95_normal':[max(0,mean-1.959964*se),min(1,mean+1.959964*se)] if complete else None}
    pairs={}
    for first,second in ([('gemma_d','llada'),('gemma_d','gemma_ar'),('llama_50k','llama_25k')] if paired else []):
        groups=[]
        for task in TASKS:
            aa={r['fingerprint']:r['correct'] for r in latest.values() if r['model_key']==first and r['task']==task and isinstance(r.get('correct'),bool)}
            bb={r['fingerprint']:r['correct'] for r in latest.values() if r['model_key']==second and r['task']==task and isinstance(r.get('correct'),bool)}
            groups.append([int(aa[fp])-int(bb[fp]) for fp in sorted(aa.keys()&bb.keys())])
        if not all(len(g)>1 for g in groups):continue
        rng=random.Random(2027);samples=[]
        for _ in range(2000):samples.append(sum(sum(rng.choices(g,k=len(g)))/len(g) for g in groups)/len(groups))
        samples.sort();pairs[first+' minus '+second]={'paired_n_by_task':dict(zip(TASKS,map(len,groups))),
            'difference':sum(sum(g)/len(g) for g in groups)/len(groups),'bootstrap95':[samples[49],samples[1949]],'replicates':2000,'seed':2027}
    return {'models':out,'paired_macro':pairs,'scope':'Item uncertainty on nine fixed tasks; no multiplicity adjustment; incomplete queues are not final tables.'}

def write_report(rows,destination,paired=True):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    result=summarize(rows,paired=paired);(destination/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# Audited item results','','Only scored outcomes are included. Partial runs are not completed benchmark results.','','| Model | Task | Correct / n | Accuracy | 95% Wilson CI |','|---|---|---:|---:|---:|']
    for model,data in result['models'].items():
        for task,s in data['tasks'].items():
            if s['n']:
                lo,hi=s['wilson95'];lines.append(f"| {model} | {task} | {s['correct']}/{s['n']} | {100*s['accuracy']:.2f}% | {100*lo:.2f}–{100*hi:.2f}% |")
    lines+=['','Macro and paired intervals, exact per-task denominators and bootstrap settings are in report.json. These intervals do not establish equivalence or training-seed robustness.']
    (destination/'report.md').write_text('\n'.join(lines)+'\n')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('results',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    write_report([json.loads(x) for x in a.results.read_text().split('\n') if x.strip()],a.out)
