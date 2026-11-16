# Benchmark precision and sample plan

**Actual execution update, 15 November 2026:** all planned sample targets are now complete, but only MMLU and MMLU-Pro used seeded random selection. The other partial benchmarks used released-order prefixes; HumanEval is complete. The planning calculations below are not evidence that the executed subsets were simple random samples. See the [selection audit and interpretation limits](evaluation/SAMPLE_SELECTION.md).

Calculated at 95% confidence; percentage points (pp), not relative percentages. No evaluations have been run. Regenerate with `python3 iclr2027_rebuttal/analysis/precision_plan.py`.

## Precision at different evaluation sizes

| Unique examples | Worst-case Wilson half-width |
|---:|---:|
| 125 | ±8.63 pp |
| 164 | ±7.56 pp |
| 250 | ±6.15 pp |
| 257 | ±6.07 pp |
| 300 | ±5.62 pp |
| 375 | ±5.03 pp |
| 448 | ±4.61 pp |
| 500 | ±4.37 pp |
| 1,000 | ±3.09 pp |

At 50% observed accuracy the Wilson interval is symmetric; other accuracies give asymmetric endpoints. Report actual endpoints from integer successes/denominators, not a fixed symmetric error bar.

## Sample sizes for requested population precision

Normal planning approximation: `n = ceil(z² p(1−p) / e²)`, with `z = 1.959964`. For a conservative plan use `p = 0.5`. Wilson intervals are used for reporting, not Wald intervals.

| Desired 95% half-width | Conservative n | Planning n at p=0.8 |
|---:|---:|---:|
| ±1 pp | 9,604 | 6,147 |
| ±2 pp | 2,401 | 1,537 |
| ±3 pp | 1,068 | 683 |
| ±4 pp | 601 | 385 |
| ±5 pp | 385 | 246 |

The current cap is 250 total unique items/task, including the first 125 when reusable. It cannot generally deliver ±1–2 pp per-model population precision. Around 80% accuracy, n=250 gives Wilson endpoints approximately 74.60%–84.49%. Planning at a favorable observed accuracy is not a guarantee.

## Target under the requested cap

Counts reflect the current evaluator and public dataset cards, not a completed audit of the submitted runs. Pin dataset revisions and verify loaded lengths before execution.

| Benchmark / source | Available | Proposed n | Extra over 125* | Worst-case Wilson half-width |
|---|---:|---:|---:|---:|
| [ARC-Challenge](https://huggingface.co/datasets/allenai/ai2_arc) | 1,172 | 250 | 125 | ±6.15 pp |
| [GPQA-Main](https://huggingface.co/datasets/Idavidrein/gpqa/blob/main/README.md) | 448 | 250 | 125 | ±6.15 pp |
| [GSM8K](https://huggingface.co/datasets/openai/gsm8k) | 1,319 | 250 | 125 | ±6.15 pp |
| [HellaSwag](https://huggingface.co/datasets/Rowan/hellaswag) | 10,042 | 250 | 125 | ±6.15 pp |
| [HumanEval](https://huggingface.co/datasets/openai/openai_humaneval) | 164 | 164 | 39 | ±7.56 pp |
| [MATH-500](https://huggingface.co/datasets/HuggingFaceH4/MATH-500) | 500 | 250 | 125 | ±6.15 pp |
| [MBPP sanitized](https://huggingface.co/datasets/google-research-datasets/mbpp/raw/main/README.md) | 257 | 250 | 125 | ±6.15 pp |
| [MMLU](https://huggingface.co/datasets/cais/mmlu) | 14,042 | 250 | 125 | ±6.15 pp |
| [MMLU-Pro](https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro) | 12,032 | 250 | 125 | ±6.15 pp |

**Total per model: 2,164 scored unique items; 1,039 additional items if all original 125/task are reusable.** Ten evaluated model/checkpoint columns would require 21,640 total model–item evaluations (10,390 additional). A first pass on BYOD-Gemma, its AR parent, and LLaDA would require 6,492 total (3,117 additional). These counts do not predict GPU time.

*Original sample counts and protocols are disputed. Reuse only verified item-level results with identical prompts, checkpoints, scoring and decoding. Changed protocols require rerunning affected existing items, not merely adding items.

**MBPP:** sanitized test has 257, whereas full MBPP test has 500. Do not mix them to reach the cap. If original runs used full MBPP, sample 250 of its 500 test items. The current first-stage total is unchanged because sanitized MBPP also has at least 250 items. **GPQA:** use Main (448), not Diamond (198); its released split is named `train` and must be held out from BYOD conversion (verify the historical dataset). **HellaSwag:** use labeled validation, not unlabeled test.

## Finite benchmark versus broader task population

The table below concerns only estimating the exact score on a fixed finite benchmark by simple random sampling without replacement. Approximate conservative planning uses `n = ceil(N n0 / (N−1+n0))`, where `n0=z²/(4e²)`. It is not the same estimand as performance on future task instances; use a suitable finite-population interval if reporting this analysis.

| Benchmark | Approx. n for ±2 pp on fixed benchmark | Approx. n for ±1 pp on fixed benchmark |
|---|---:|---:|
| ARC-Challenge | 788 | 1,045 |
| GPQA-Main | 378 | 429 |
| GSM8K | 852 | 1,160 |
| HellaSwag | 1,938 | 4,910 |
| HumanEval | 154 | 162 |
| MATH-500 | 414 | 476 |
| MBPP sanitized | 233 | 251 |
| MMLU | 2,051 | 5,704 |
| MMLU-Pro | 2,002 | 5,342 |

A full census eliminates item-subsampling error for the fixed dataset and fixed deterministic protocol. It does not establish zero uncertainty about future problems, decoding randomness, training seeds, or scoring errors. Do not claim population ±1–2 pp by invoking a census of a small benchmark.

## Paired comparisons and compute

For each matched item define dᵢ = correctness(BYOD) − correctness(baseline). The normal approximation is `SE(mean d) ≈ sqrt((q−delta²)/n)`, where q is the fraction of discordant items and delta is the mean paired difference. At n=250 and delta near zero, approximate 95% half-width is ±3.92 pp for q=.10, ±5.54 pp for q=.20, and ±6.79 pp for q=.30. Paired precision cannot be promised before observing disagreements. A 1.3-point gap may remain unresolved.

Use a paired bootstrap of matched item IDs for differences; resample within each task and preserve equal task weights for the nine-task macro mean. Report each task denominator. Do not infer equivalence from a nonsignificant difference. Item intervals do not measure training-seed variability, nor are separate 95% intervals simultaneous guarantees across all comparisons.

Freeze sample IDs before new scoring; retain the original 125 only if audited as a valid reusable subset and append disjoint sampled IDs. If changing to subject-stratified MMLU sampling, document weights and use matching stratified uncertainty. Do not stop when a favorable interval first appears or count multiple outputs for one item as independent questions.

Estimate cost using a small fixed pilot per model/task: incremental seconds ≈ additional unique items × measured seconds/item, plus loading and scoring overhead. Record GPU, batch size, prompt/output tokens, NFE, memory and scoring failures. At the same protocol, moving 125→250 doubles item-level work for that task. Fix the MMLU-Pro budget comparison before expanding it; otherwise the new runs perpetuate the mismatch.

No benchmark run, download, training job, or paid compute is launched by this script.

## Primary comparison: equal-weight task average

Plan the paired difference in the nine-task macro average as the main descriptive comparison, with per-task intervals showing heterogeneity. This preserves equal task weights rather than pooling all questions.

| Coverage | Approximate conservative 95% half-width for one model’s macro average |
|---|---:|
| Original 125/task | ±2.92 pp |
| Current capped plan | ±2.13 pp |

These normal approximations assume independent items and tasks. Overlapping/related tasks can violate that assumption. They are not intervals for the paired model difference; actual paired uncertainty requires saved outcomes. No multiple-testing adjustment was used to obtain 9,604 or the other individual-accuracy planning counts. A single prespecified macro contrast does not require nine tests merely because it contains nine tasks; additional confirmatory contrasts need their own multiplicity plan.

GPU preference: an unattended rented server, not Colab. No instance has been provisioned; compare current options in gpu_options.md and measure a fixed pilot before estimating total runtime.

## Two-stage allocation under the approximately €100 budget

Stage 1 targets 250 total unique items/task for all ten main-table configurations, or all available items below 250. Keep the initial 125 only after verifying counts/IDs and unchanged protocols. This adds 125 questions for eight tasks and 39 for HumanEval: 1,039/model and 10,390 across ten columns. Sanitized MBPP is 250 of 257 in this stage, not its full set.

Stage 2 uses any remaining budget for identical additional IDs on BYOD-Gemma, Gemma AR and LLaDA. An illustrative 375-item cap would add 882/model (2,646 across the trio): 125 on seven larger tasks, 7 on sanitized MBPP, none on already-complete HumanEval. Choose the stopping budget/counts before examining new accuracy differences. Stage 2 is conditional, not a promise that those counts are affordable.

The approximately €100 budget and pilot remain binding. Doubling question counts does not halve interval widths: ideal precision improves by about sqrt(2), with less improvement where HumanEval is capped. No rental or evaluation has been launched.
