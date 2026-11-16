"""Reproduce 95% accuracy precision planning; no model inference or dataset downloads."""
from pathlib import Path
import csv
from math import ceil, sqrt
from statistics import NormalDist

ROOT = Path(__file__).resolve().parents[1]
Z = NormalDist().inv_cdf(.975)
CAP = 250  # Current author-selected total per task, including reusable original items.
# Match current byod-reproducible evaluator; verify against original run manifests.
TASKS = [
    ('ARC-Challenge', 1172, 'test', 'https://huggingface.co/datasets/allenai/ai2_arc'),
    ('GPQA-Main', 448, 'gpqa_main / train (evaluation)', 'https://huggingface.co/datasets/Idavidrein/gpqa/blob/main/README.md'),
    ('GSM8K', 1319, 'main / test', 'https://huggingface.co/datasets/openai/gsm8k'),
    ('HellaSwag', 10042, 'validation', 'https://huggingface.co/datasets/Rowan/hellaswag'),
    ('HumanEval', 164, 'test', 'https://huggingface.co/datasets/openai/openai_humaneval'),
    ('MATH-500', 500, 'test', 'https://huggingface.co/datasets/HuggingFaceH4/MATH-500'),
    ('MBPP sanitized', 257, 'sanitized / test', 'https://huggingface.co/datasets/google-research-datasets/mbpp/raw/main/README.md'),
    ('MMLU', 14042, 'all / test', 'https://huggingface.co/datasets/cais/mmlu'),
    ('MMLU-Pro', 12032, 'test', 'https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro'),
]

def wilson(p, n):
    d = 1 + Z*Z/n
    center = (p + Z*Z/(2*n))/d
    half = Z*sqrt(p*(1-p)/n + Z*Z/(4*n*n))/d
    return center-half, center+half

def wald_n(error, p=.5):
    return ceil(Z*Z*p*(1-p)/(error*error))

def finite_n(N, error):
    a = Z*Z*.25/(error*error)
    return ceil(N*a/(N-1+a))

rows=[]
for task,N,split,url in TASKS:
    n=min(CAP,N)
    lo,hi=wilson(.5,n)
    rows.append(dict(task=task,available=N,split=split,target=n,
        additional_if_125_reusable=n-125,worst_case_wilson_halfwidth_pp=100*(hi-lo)/2,
        approx_finite_n_for_2pp=finite_n(N,.02),approx_finite_n_for_1pp=finite_n(N,.01),source=url))
with (ROOT/'analysis/sampling_plan.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader();writer.writerows(rows)
lines=['# Benchmark precision and sample plan', '',
    'Calculated at 95% confidence; percentage points (pp), not relative percentages. No evaluations have been run. Regenerate with `python3 iclr2027_rebuttal/analysis/precision_plan.py`.', '',
    '## Precision at different evaluation sizes', '',
    '| Unique examples | Worst-case Wilson half-width |', '|---:|---:|']
for n in [125,164,250,257,300,375,448,500,1000]:
    lo,hi=wilson(.5,n); lines.append(f'| {n:,} | ±{100*(hi-lo)/2:.2f} pp |')
lines+=['', 'At 50% observed accuracy the Wilson interval is symmetric; other accuracies give asymmetric endpoints. Report actual endpoints from integer successes/denominators, not a fixed symmetric error bar.', '',
    '## Sample sizes for requested population precision', '',
    'Normal planning approximation: `n = ceil(z² p(1−p) / e²)`, with `z = 1.959964`. For a conservative plan use `p = 0.5`. Wilson intervals are used for reporting, not Wald intervals.', '',
    '| Desired 95% half-width | Conservative n | Planning n at p=0.8 |', '|---:|---:|---:|']
for e in [.01,.02,.03,.04,.05]:lines.append(f'| ±{100*e:.0f} pp | {wald_n(e):,} | {wald_n(e,.8):,} |')
lines+=['', f'The current cap is {CAP} total unique items/task, including the first 125 when reusable. It cannot generally deliver ±1–2 pp per-model population precision. Around 80% accuracy, n={CAP} gives Wilson endpoints approximately '+ '–'.join(f'{100*x:.2f}%' for x in wilson(.8,CAP))+'. Planning at a favorable observed accuracy is not a guarantee.', '',
    '## Target under the requested cap', '',
    'Counts reflect the current evaluator and public dataset cards, not a completed audit of the submitted runs. Pin dataset revisions and verify loaded lengths before execution.', '',
    '| Benchmark / source | Available | Proposed n | Extra over 125* | Worst-case Wilson half-width |', '|---|---:|---:|---:|---:|']
for r in rows:
    lines.append(f"| [{r['task']}]({r['source']}) | {r['available']:,} | {r['target']} | {r['additional_if_125_reusable']} | ±{r['worst_case_wilson_halfwidth_pp']:.2f} pp |")
total=sum(r['target'] for r in rows); extra=sum(r['additional_if_125_reusable'] for r in rows)
lines+=['',f'**Total per model: {total:,} scored unique items; {extra:,} additional items if all original 125/task are reusable.** Ten evaluated model/checkpoint columns would require {10*total:,} total model–item evaluations ({10*extra:,} additional). A first pass on BYOD-Gemma, its AR parent, and LLaDA would require {3*total:,} total ({3*extra:,} additional). These counts do not predict GPU time.', '',
    '*Original sample counts and protocols are disputed. Reuse only verified item-level results with identical prompts, checkpoints, scoring and decoding. Changed protocols require rerunning affected existing items, not merely adding items.', '',
    '**MBPP:** sanitized test has 257, whereas full MBPP test has 500. Do not mix them to reach the cap. If original runs used full MBPP, sample 250 of its 500 test items. The current first-stage total is unchanged because sanitized MBPP also has at least 250 items. **GPQA:** use Main (448), not Diamond (198); its released split is named `train` and must be held out from BYOD conversion (verify the historical dataset). **HellaSwag:** use labeled validation, not unlabeled test.', '',
    '## Finite benchmark versus broader task population', '',
    'The table below concerns only estimating the exact score on a fixed finite benchmark by simple random sampling without replacement. Approximate conservative planning uses `n = ceil(N n0 / (N−1+n0))`, where `n0=z²/(4e²)`. It is not the same estimand as performance on future task instances; use a suitable finite-population interval if reporting this analysis.', '',
    '| Benchmark | Approx. n for ±2 pp on fixed benchmark | Approx. n for ±1 pp on fixed benchmark |', '|---|---:|---:|']
for r in rows:lines.append(f"| {r['task']} | {r['approx_finite_n_for_2pp']:,} | {r['approx_finite_n_for_1pp']:,} |")
lines+=['', 'A full census eliminates item-subsampling error for the fixed dataset and fixed deterministic protocol. It does not establish zero uncertainty about future problems, decoding randomness, training seeds, or scoring errors. Do not claim population ±1–2 pp by invoking a census of a small benchmark.', '',
    '## Paired comparisons and compute', '',
    'For each matched item define dᵢ = correctness(BYOD) − correctness(baseline). The normal approximation is `SE(mean d) ≈ sqrt((q−delta²)/n)`, where q is the fraction of discordant items and delta is the mean paired difference. At n=250 and delta near zero, approximate 95% half-width is ±3.92 pp for q=.10, ±5.54 pp for q=.20, and ±6.79 pp for q=.30. Paired precision cannot be promised before observing disagreements. A 1.3-point gap may remain unresolved.', '',
    'Use a paired bootstrap of matched item IDs for differences; resample within each task and preserve equal task weights for the nine-task macro mean. Report each task denominator. Do not infer equivalence from a nonsignificant difference. Item intervals do not measure training-seed variability, nor are separate 95% intervals simultaneous guarantees across all comparisons.', '',
    'Freeze sample IDs before new scoring; retain the original 125 only if audited as a valid reusable subset and append disjoint sampled IDs. If changing to subject-stratified MMLU sampling, document weights and use matching stratified uncertainty. Do not stop when a favorable interval first appears or count multiple outputs for one item as independent questions.', '',
    'Estimate cost using a small fixed pilot per model/task: incremental seconds ≈ additional unique items × measured seconds/item, plus loading and scoring overhead. Record GPU, batch size, prompt/output tokens, NFE, memory and scoring failures. At the same protocol, moving 125→250 doubles item-level work for that task. Fix the MMLU-Pro budget comparison before expanding it; otherwise the new runs perpetuate the mismatch.', '',
    'No benchmark run, download, training job, or paid compute is launched by this script.', '']
lines += ['## Primary comparison: equal-weight task average', '',
    'Plan the paired difference in the nine-task macro average as the main descriptive comparison, with per-task intervals showing heterogeneity. This preserves equal task weights rather than pooling all questions.', '',
    '| Coverage | Approximate conservative 95% half-width for one model’s macro average |',
    '|---|---:|']
for label,ns in [('Original 125/task',[125]*len(rows)), ('Current capped plan',[int(r['target']) for r in rows])]:
    width=100*Z*sqrt(sum(.25/n for n in ns))/len(ns)
    lines.append(f'| {label} | ±{width:.2f} pp |')
lines += ['', 'These normal approximations assume independent items and tasks. Overlapping/related tasks can violate that assumption. They are not intervals for the paired model difference; actual paired uncertainty requires saved outcomes. No multiple-testing adjustment was used to obtain 9,604 or the other individual-accuracy planning counts. A single prespecified macro contrast does not require nine tests merely because it contains nine tasks; additional confirmatory contrasts need their own multiplicity plan.', '',
    'GPU preference: an unattended rented server, not Colab. No instance has been provisioned; compare current options in gpu_options.md and measure a fixed pilot before estimating total runtime.', '']
lines += ['## Two-stage allocation under the approximately €100 budget', '',
    'Stage 1 targets 250 total unique items/task for all ten main-table configurations, or all available items below 250. Keep the initial 125 only after verifying counts/IDs and unchanged protocols. This adds 125 questions for eight tasks and 39 for HumanEval: 1,039/model and 10,390 across ten columns. Sanitized MBPP is 250 of 257 in this stage, not its full set.', '',
    'Stage 2 uses any remaining budget for identical additional IDs on BYOD-Gemma, Gemma AR and LLaDA. An illustrative 375-item cap would add 882/model (2,646 across the trio): 125 on seven larger tasks, 7 on sanitized MBPP, none on already-complete HumanEval. Choose the stopping budget/counts before examining new accuracy differences. Stage 2 is conditional, not a promise that those counts are affordable.', '',
    'The approximately €100 budget and pilot remain binding. Doubling question counts does not halve interval widths: ideal precision improves by about sqrt(2), with less improvement where HumanEval is capped. No rental or evaluation has been launched.', '']
(ROOT/'sampling_plan.md').write_text('\n'.join(lines))
assert total==2164 and extra==1039
assert wald_n(.02)==2401 and wald_n(.01)==9604
lo,hi=wilson(.5,500)
assert abs((lo+hi)-1)<1e-12 and .043<((hi-lo)/2)<.044
print(f'Wrote sampling_plan.md and analysis/sampling_plan.csv; n={total}, extra={extra}.')
print('95% worst-case Wilson half-width at n=500:',100*(hi-lo)/2)
