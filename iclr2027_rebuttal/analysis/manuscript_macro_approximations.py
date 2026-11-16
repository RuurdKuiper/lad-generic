"""Approximate current macro-accuracy intervals from the manuscript, with denominator checks.

No inference, downloads, empirical paired intervals or raw-run validation is performed.
"""
from pathlib import Path
from statistics import NormalDist
from math import sqrt
import csv,json,re,hashlib

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'paper/iclr2027_conference.tex'
text=SOURCE.read_text()
section=text[text.index(r'\label{tab:accuracy}'):]
section=section[:section.index(r'\end{table*}')]
tasks=[]
for line in section.splitlines():
    if re.match(r'^(ARC-C|GPQA|HellaSwag|MMLU |MMLU-Pro|GSM8K|MATH-500|HumanEval|MBPP)\s*&',line):
        cells=line.split('&')
        values=[float(re.search(r'\.\d+',cell).group()) for cell in cells[1:]]
        assert len(values)==11
        tasks.append((cells[0].strip(),values))
assert len(tasks)==9
N=125
Z=NormalDist().inv_cdf(.975)
NAMES=['BYOD-Gemma','Gemma AR','BYOD-Qwen','Qwen AR','BYOD-Ministral','Ministral AR','BYOD-Llama-25k','BYOD-Llama-50k','Llama AR','LLaDA (own evaluation)']
rows=[]
for column,name in enumerate(NAMES):
    rates=[values[column] for _,values in tasks]
    incompatible=[task for task,values in tasks if abs(values[column]*N-round(values[column]*N))>1e-8]
    mean=sum(rates)/len(rates)
    # For binary item observations, p_hat(1-p_hat)/(N-1) is an unbiased
    # estimator of Var(p_hat). Preserve equal task weights, not pooled variance.
    se=sqrt(sum(p*(1-p)/(N-1) for p in rates))/len(rates) if not incompatible else None
    rows.append(dict(model=name,mean_pct=mean*100,
        ci95_low_pct=(mean-Z*se)*100 if se is not None else None,
        ci95_high_pct=(mean+Z*se)*100 if se is not None else None,
        status='provisional: assumes 125/task and independent items/tasks' if se is not None else 'withheld: unresolved denominators',
        incompatible_tasks='; '.join(incompatible)))
with (ROOT/'analysis/current_macro_intervals.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
metadata=dict(source=str(SOURCE.relative_to(ROOT)),sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    assumed_n_per_task=N,tasks=[t for t,_ in tasks],method='Unadjusted 95% normal interval; within-task Bernoulli variance, equal task weights, variance estimate p(1-p)/(n-1).',
    interpretation='Conditional approximate intervals for one model macro mean, not paired differences or equivalence.',results=rows)
(ROOT/'analysis/current_macro_intervals.json').write_text(json.dumps(metadata,indent=2)+'\n')
lines=['# Current macro-average confidence intervals','',
    '**Provisional approximations, not final run-audited or paired intervals.** Source: the local manuscript main accuracy table; script: `analysis/current_macro_intervals.py`. The older workbook differs from the manuscript in some cells and is not silently substituted. No new benchmark evaluations were run.','',
    '| Model/checkpoint | Nine-task mean | Approximate 95% CI | Status |','|---|---:|---:|---|']
for row in rows:
    interval=f"{row['ci95_low_pct']:.2f}–{row['ci95_high_pct']:.2f}%" if row['ci95_low_pct'] is not None else 'Pending denominator audit'
    status='Assumes n=125/task' if row['ci95_low_pct'] is not None else 'Incompatible 125-item cells: '+row['incompatible_tasks']
    lines.append(f"| {row['model']} | {row['mean_pct']:.2f}% | {interval} | {status} |")
lines+=['','## Method and interpretation','',
    'The estimand is the equal-weight mean accuracy over the nine fixed tasks. Assume independent binary items within and across tasks and n_t=125 for every task. Let p_t be the manuscript task rate and T=9. Calculate:', '',
    '`mean = sum(p_t)/T`',
    '`SE² = sum[p_t(1−p_t)/(n_t−1)] / T²`',
    '`95% interval ≈ mean ± 1.959964 × SE`', '',
    'The n_t−1 denominator arises from the unbiased estimate of the variance of a binary sample mean. This is a normal approximation for a stratified mean, not a Wilson interval applied to the macro mean, not variability across nine task means, and not treating all tasks as identical Bernoulli trials. No multiple-testing correction is applied.', '',
    'Task rates are read at their reported precision. For the seven reported intervals they are arithmetically compatible with integer successes/125; that compatibility is not proof of the actual counts, sample selection or protocol. Raw-run denominator verification remains necessary. The three withheld AR means include rates incompatible with ordinary binary accuracy/125, so no count-based interval is assigned to them.', '',
    'These intervals describe evaluation-item uncertainty under the stated assumptions, not training-seed variation, uncertainty over arbitrary new task families, or uncertainty about scoring/contamination. Related or overlapping tasks/items can violate independence. No finite-population correction is used: these concern a broader within-task item population rather than merely estimating the fixed finite dataset score.', '',
    'The recomputed Gemma-minus-LLaDA point difference is −1.333 percentage points. A proper paired CI requires correctness outcomes aligned by item ID; individual-model intervals do not recover their covariance. Do not infer a difference test or equivalence from interval overlap. The same limitation applies to 25k-versus-50k differences.', '',
    'Workbook inspection also found an explicit legend distinguishing updated 125-item cells from earlier preserved cells (typically 50), and some comments refer to values older than the current cells. These are provenance clues, not sufficient evidence to infer unknown denominators. Audit the underlying runs and reconcile workbook, comments, figures and manuscript.', '']
(ROOT/'current_macro_intervals.md').write_text('\n'.join(lines))
assert sum(row['ci95_low_pct'] is not None for row in rows)==7
assert all(0<row['ci95_low_pct']<row['mean_pct']<row['ci95_high_pct']<100 for row in rows if row['ci95_low_pct'] is not None)
print('Wrote provisional current macro CI Markdown/CSV/JSON: 7 approximations; 3 withheld pending denominator audit.')
for row in rows:
    if row['ci95_low_pct'] is not None:print(f"{row['model']}: {row['mean_pct']:.2f}% [{row['ci95_low_pct']:.2f}, {row['ci95_high_pct']:.2f}]")
