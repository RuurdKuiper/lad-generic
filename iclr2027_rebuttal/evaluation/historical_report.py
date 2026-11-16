"""Recorded historical outcomes, latest compatible reruns; never executes code."""
import json
from pathlib import Path
from protocol import TASKS,MODELS,fingerprint,compatible
from report import write_report
HERE=Path(__file__).resolve().parent

def main():
    groups=json.loads((HERE/'audit/legacy_groups.json').read_text())
    records=[json.loads(l) for l in (HERE/'audit/legacy_records.jsonl').read_text().split('\n') if l.strip()]
    examples=[json.loads(l) for l in (HERE/'bundle/examples.jsonl').read_text().split('\n') if l.strip()]
    allowed={x['fingerprint'] for x in examples if x['sample_index']<125}
    newest={};selected={};summary=[]
    for group in sorted([g for g in groups if 'model_key' in g],key=lambda g:(g['run_id'],g['path'])):newest[(group['model_key'],group['task'])]=group
    for record in sorted(records,key=lambda r:(r['legacy_run'],r['legacy_file'])):
        key=(record['model_key'],record['task']);fp=fingerprint(record['task'],record['prompt'],record['target'])
        if fp not in allowed:continue
        if not compatible(record['inference_settings'],newest[key]['settings'])[0]:continue
        selected[(record['model_key'],fp)]=record
    rows=[{'model_key':r['model_key'],'task':r['task'],'fingerprint':fp,'correct':r['correct']} for (_,fp),r in selected.items()]
    result=write_report(rows,HERE/'audit/historical')
    lines=['# Historical rerun audit','','Source: original Drive JSONL files read without modification. No generation or generated code was executed. Counts below use the recorded scorer; scoring verification is pending.','','Selection: within each model/task, use the most recent run’s settings, then the newest available prediction for each exact current prompt/target among the original first 125 positions. Earlier runs fill missing positions only when compatible. A partial latest run is not promoted to a complete 125-question result. Seeds may differ for temperature-zero decoding. No result is selected by accuracy.','','| Model | Task | Latest run | Latest correct/n | Retained unique n |','|---|---|---|---:|---:|']
    for key in MODELS:
        for task in TASKS:
            g=newest.get((key,task))
            if not g:continue
            n=result['models'][key]['tasks'][task]['n']
            lines.append(f"| {key} | {task} | {g['run_id'].split('--')[0]} | {g['correct']}/{g['count']} | {n} |")
    lines+=['','## Current averages from historical recorded outcomes','','These are descriptive historical protocols, with unequal AR/diffusion output limits. The expansion preserves these intentional method-specific output limits. Intervals are unadjusted 95% normal intervals for the equal-weight mean of nine fixed tasks, using actual item counts and independent items/tasks. Code results have not yet been rescored with the current harness.','','| Model | Historical mean | Approximate 95% CI | n by task (table order) |','|---|---:|---:|---|']
    for key in MODELS:
        data=result['models'][key];mean=data['macro_mean'];ci=data['macro95_normal']
        if ci:lines.append(f"| {key} | {100*mean:.2f}% | {100*ci[0]:.2f}–{100*ci[1]:.2f}% | "+', '.join(str(data['tasks'][t]['n']) for t in TASKS)+' |')
    lines+=['','Order: '+', '.join(TASKS)+'.','','## Confirmed provenance issues','','- Gemma AR HumanEval and MBPP are 37/50 in the latest recovered files, consistent with 74%, rather than 125 evaluated items.','- Qwen AR HumanEval has 83/95 in the latest recovered file; this does not establish the manuscript’s 89% value.','- Ministral AR HumanEval has a later 107/125 run (85.6%), superseding the earlier 47/50 (94%) result.','- Latest Gemma diffusion MMLU contains 11 items and latest Qwen diffusion GSM8K contains 14; matching older results can fill unchanged questions.','- GPQA has 125 records in the later runs. An initial audit split a Unicode line separator inside a JSON string; reading physical newline boundaries fixes that parsing error, with zero invalid records.','- Actual historical AR output caps are 1,024 tokens, or 2,048 for MMLU-Pro. Historical diffusion MMLU-Pro uses 64, despite the manuscript’s 128-token description. The expansion preserves 64 for diffusion and 2,048 for AR on MMLU-Pro, as the author confirms that the longer AR limits were intentional.','','Dataset/base model commit IDs were not recorded in the original files. Exact prompt/target matching and the original adapter paths support provisional reuse; complete checkpoint identity and pilot replay checks are still required. New base/dataset revisions are frozen in hub_lock.json. Never label recorded historical scores as rescored outcomes.']
    averages=lines[lines.index('## Current averages from historical recorded outcomes'):lines.index('## Confirmed provenance issues')]
    (HERE.parent/'current_macro_intervals.md').write_text('# Current historical macro-average confidence intervals\n\nUpdated from per-question outputs using the latest compatible reruns. Counts are verified; correctness remains the recorded historical scorer, pending consistent rescoring. Earlier manuscript-only approximations are superseded.\n\n'+'\n'.join(averages)+'\n\nVariance: SE² = Σ[p_t(1−p_t)/(n_t−1)]/81; CI = mean ± 1.959964×SE. These are item intervals on nine fixed tasks, not training-seed or causal conversion-effect intervals. No multiplicity correction or finite-population correction. See [the run-selection audit](evaluation/audit_summary.md) and [reproduction script](evaluation/historical_report.py).\n')
    (HERE.parent/'analysis/current_macro_intervals.json').write_text(json.dumps(result,indent=2)+'\n')
    import csv
    with (HERE.parent/'analysis/current_macro_intervals.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['model','mean_pct','ci95_low_pct','ci95_high_pct','status'])
        for key,data in result['models'].items():
            if data['macro95_normal']:writer.writerow([key,100*data['macro_mean'],100*data['macro95_normal'][0],100*data['macro95_normal'][1],'latest compatible historical recorded outcomes; rescoring pending'])
    (HERE/'audit_summary.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines[lines.index('## Current averages from historical recorded outcomes'):]))
if __name__=='__main__':main()
