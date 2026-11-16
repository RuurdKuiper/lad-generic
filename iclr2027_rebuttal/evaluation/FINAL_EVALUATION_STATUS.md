# Final evaluation status and before/after comparison

Internal working report, 15 November 2026. All differences are percentage points (pp), not relative percentage changes.

## Summary of the main changes

- **All current sample targets are complete:** 21,640 selected outcomes, ten model configurations, 250 questions on each of eight tasks and all 164 HumanEval questions. The historical comparison contains 11,070 available outcomes. The net increase of 10,570 selected outcomes excludes replacement generations and diagnostics.
- **BYOD-Gemma's nine-task mean rises from 50.58% originally recorded to 52.43% (+1.85 pp).** This combines scoring-policy changes, a fresh rerun and added questions. Under the current scorer, its historical mean is 50.58%; rerunning those same questions gives 53.51%; adding the remaining questions brings this to 52.43%. It would be incorrect to attribute the gain entirely to sample expansion.
- **HumanEval is the main cluster of declines.** Gemma AR falls from 74.0% on its historical 50 questions to 59.8% on all 164. BYOD-Gemma's fresh initial 125 score 37.6%, but the added 39 score only 5.1%; this is the one old-versus-added cohort difference that survives correction across all 90 model–task comparisons. Its final 29.9% remains above its historically recorded 25.6% because the initial questions were rerun.
- **The new failure analysis gives a partial explanation for Gemma HumanEval:** 11/39 added programs are invalid Python, including six unfinished docstrings, but 26 further answers are syntactically valid and wrong. The added specifications are longer; all their canonical answer bodies still fit the 256-token canvas if the specification is not copied. Length alone does not explain the gap.
- **LLaDA's largest drop is MATH: 34.4% → 26.0% (−8.4 pp).** Its added questions score 17.6%, versus 34.4% originally. This is unusual in an isolated test, but does not survive the 90-comparison correction. Manual inspection of 12 added LLaDA answers found no scoring error; its earlier 18 replay controls all matched historical correctness.
- **BYOD-Gemma's MBPP gain is mainly a rerun effect:** historical 36.8% → fresh same-question 48.8% → final 43.6%. Both MBPP and HumanEval have 20 gains and five losses on their original 125 questions; these matched rerun changes survive a separate nine-task correction. The cause of historical generation drift remains unresolved.
- **Qwen AR's large intermediate collapse was repaired, not retained.** Its final GSM8K is 92.4% and HumanEval 81.1%. Known faulty new eager-attention outputs were replaced under SDPA, while verified historical predictions were reused.
- **MATH presentation follow-up completed (v3):** whole numeric answers with stray escapes, complete scalar final statements and reference-aware percent units are now handled consistently. Nine historical decisions and four final decisions are restored; their old flags and scorer are archived. BYOD-Gemma and LLaDA final scores are unchanged. [Correction policy and exact impact](MATH_PRESENTATION_CORRECTION.md).

## How to read the comparisons

The before column uses the preserved `recorded_correct` flags from the latest compatible historical per-question results, not the first cloud campaign's incomplete/exact-only rescoring. It is a recovered historical baseline, not an assertion that every value exactly reproduces an older printed manuscript table. The final column uses the adopted fresh-Gemma/corrected-Qwen selection and the current uniform MATH scorer.

Each benchmark table separates **historical**, **current results on those same question IDs**, **new question IDs**, and **final combined**. `Net Δ` is final minus originally recorded. `Added Δ` is final minus the current same-ID score, isolating the arithmetic effect of adding questions after the selected cohort/scorer is fixed. It is not a causal estimate of a runtime or training effect. For MATH, the additional scoring table separates historical rescoring from generation changes.

Historical denominators are 125 except Gemma AR HumanEval/MBPP (50 each) and Qwen AR HumanEval (95). Therefore their added subsets contain 114, 200 and 69 questions respectively, rather than 39 or 125. All final configurations share the same question IDs for a task. BYOD-Gemma uses a complete fresh cohort, including its original questions, uniformly across tasks and regardless of whether answers improved or worsened.

## Nine-task averages and decomposition

Each task has equal weight. The following components add to the net change before rounding: historical rescoring, changed generations on the original IDs, and then adding question IDs. The original-ID denominators differ between models where historical files were incomplete.

| Model | Historical mean | Scoring Δ | Rerun Δ | Added Δ | Final mean | Net Δ |
|---|---:|---:|---:|---:|---:|---:|
| BYOD-Gemma | 50.58% | +0.00 | +2.93 | -1.08 | 52.43% | +1.85 |
| Gemma AR | 65.69% | +0.00 | +0.00 | -2.96 | 62.73% | -2.96 |
| LLaDA | 51.91% | +0.00 | +0.00 | -2.36 | 49.55% | -2.36 |
| BYOD-Qwen | 48.98% | -0.18 | +0.00 | -0.51 | 48.29% | -0.69 |
| Qwen AR | 71.40% | +0.00 | +0.00 | -0.74 | 70.66% | -0.74 |
| BYOD-Ministral | 49.87% | +0.00 | +0.00 | -1.33 | 48.54% | -1.33 |
| Ministral AR | 63.47% | +0.00 | +0.00 | -0.76 | 62.70% | -0.76 |
| BYOD-Llama 25k | 48.71% | +0.00 | +0.00 | -0.78 | 47.93% | -0.78 |
| BYOD-Llama 50k | 49.24% | -0.18 | +0.00 | -1.27 | 47.80% | -1.45 |
| Llama AR | 58.76% | -0.09 | +0.00 | -1.95 | 56.71% | -2.04 |

### Largest net individual-score changes

These rank changes from originally recorded to final scores. They are not automatically sample-size effects or statistically significant differences.

| Model | Task | Historical | Final | Net Δ |
|---|---|---:|---:|---:|
| Gemma AR | HumanEval | 74.0% | 59.8% | -14.24 |
| Gemma AR | MBPP sanitized | 74.0% | 65.6% | -8.40 |
| LLaDA | MATH-500 | 34.4% | 26.0% | -8.40 |
| Gemma AR | MATH-500 | 60.0% | 52.0% | -8.00 |
| BYOD-Gemma | MBPP sanitized | 36.8% | 43.6% | +6.80 |
| BYOD-Ministral | MBPP sanitized | 46.4% | 40.0% | -6.40 |
| Qwen AR | HumanEval | 87.4% | 81.1% | -6.27 |
| BYOD-Llama 25k | HumanEval | 31.2% | 25.0% | -6.20 |
| BYOD-Ministral | HumanEval | 35.2% | 29.3% | -5.93 |
| BYOD-Qwen | HumanEval | 29.6% | 23.8% | -5.82 |
| LLaDA | MMLU-Pro | 42.4% | 36.8% | -5.60 |
| Llama AR | MATH-500 | 48.0% | 42.4% | -5.60 |

## Benchmark-by-benchmark results

Cells with counts show `correct / evaluated (accuracy)`. The same-ID column is the selected current outcome, not necessarily the historical generation. Both delta columns use percentage points.

### ARC-Challenge

| Model | Historical | Same IDs, now | Added IDs only | Final | Net Δ | Added Δ |
|---|---:|---:|---:|---:|---:|---:|
| BYOD-Gemma | 108/125 (86.4%) | 111/125 (88.8%) | 114/125 (91.2%) | 225/250 (90.0%) | +3.60 | +1.20 |
| Gemma AR | 111/125 (88.8%) | 111/125 (88.8%) | 111/125 (88.8%) | 222/250 (88.8%) | +0.00 | +0.00 |
| LLaDA | 108/125 (86.4%) | 108/125 (86.4%) | 109/125 (87.2%) | 217/250 (86.8%) | +0.40 | +0.40 |
| BYOD-Qwen | 105/125 (84.0%) | 105/125 (84.0%) | 105/125 (84.0%) | 210/250 (84.0%) | +0.00 | +0.00 |
| Qwen AR | 114/125 (91.2%) | 114/125 (91.2%) | 111/125 (88.8%) | 225/250 (90.0%) | -1.20 | -1.20 |
| BYOD-Ministral | 104/125 (83.2%) | 104/125 (83.2%) | 101/125 (80.8%) | 205/250 (82.0%) | -1.20 | -1.20 |
| Ministral AR | 96/125 (76.8%) | 96/125 (76.8%) | 84/125 (67.2%) | 180/250 (72.0%) | -4.80 | -4.80 |
| BYOD-Llama 25k | 104/125 (83.2%) | 104/125 (83.2%) | 103/125 (82.4%) | 207/250 (82.8%) | -0.40 | -0.40 |
| BYOD-Llama 50k | 103/125 (82.4%) | 103/125 (82.4%) | 101/125 (80.8%) | 204/250 (81.6%) | -0.80 | -0.80 |
| Llama AR | 99/125 (79.2%) | 99/125 (79.2%) | 96/125 (76.8%) | 195/250 (78.0%) | -1.20 | -1.20 |

### GPQA-Main

| Model | Historical | Same IDs, now | Added IDs only | Final | Net Δ | Added Δ |
|---|---:|---:|---:|---:|---:|---:|
| BYOD-Gemma | 40/125 (32.0%) | 40/125 (32.0%) | 37/125 (29.6%) | 77/250 (30.8%) | -1.20 | -1.20 |
| Gemma AR | 35/125 (28.0%) | 35/125 (28.0%) | 39/125 (31.2%) | 74/250 (29.6%) | +1.60 | +1.60 |
| LLaDA | 39/125 (31.2%) | 39/125 (31.2%) | 39/125 (31.2%) | 78/250 (31.2%) | +0.00 | +0.00 |
| BYOD-Qwen | 36/125 (28.8%) | 36/125 (28.8%) | 42/125 (33.6%) | 78/250 (31.2%) | +2.40 | +2.40 |
| Qwen AR | 43/125 (34.4%) | 43/125 (34.4%) | 41/125 (32.8%) | 84/250 (33.6%) | -0.80 | -0.80 |
| BYOD-Ministral | 34/125 (27.2%) | 34/125 (27.2%) | 43/125 (34.4%) | 77/250 (30.8%) | +3.60 | +3.60 |
| Ministral AR | 46/125 (36.8%) | 46/125 (36.8%) | 35/125 (28.0%) | 81/250 (32.4%) | -4.40 | -4.40 |
| BYOD-Llama 25k | 37/125 (29.6%) | 37/125 (29.6%) | 32/125 (25.6%) | 69/250 (27.6%) | -2.00 | -2.00 |
| BYOD-Llama 50k | 34/125 (27.2%) | 34/125 (27.2%) | 36/125 (28.8%) | 70/250 (28.0%) | +0.80 | +0.80 |
| Llama AR | 40/125 (32.0%) | 40/125 (32.0%) | 28/125 (22.4%) | 68/250 (27.2%) | -4.80 | -4.80 |

### HellaSwag

| Model | Historical | Same IDs, now | Added IDs only | Final | Net Δ | Added Δ |
|---|---:|---:|---:|---:|---:|---:|
| BYOD-Gemma | 94/125 (75.2%) | 94/125 (75.2%) | 103/125 (82.4%) | 197/250 (78.8%) | +3.60 | +3.60 |
| Gemma AR | 87/125 (69.6%) | 87/125 (69.6%) | 89/125 (71.2%) | 176/250 (70.4%) | +0.80 | +0.80 |
| LLaDA | 87/125 (69.6%) | 87/125 (69.6%) | 87/125 (69.6%) | 174/250 (69.6%) | +0.00 | +0.00 |
| BYOD-Qwen | 91/125 (72.8%) | 91/125 (72.8%) | 93/125 (74.4%) | 184/250 (73.6%) | +0.80 | +0.80 |
| Qwen AR | 94/125 (75.2%) | 94/125 (75.2%) | 92/125 (73.6%) | 186/250 (74.4%) | -0.80 | -0.80 |
| BYOD-Ministral | 96/125 (76.8%) | 96/125 (76.8%) | 96/125 (76.8%) | 192/250 (76.8%) | +0.00 | +0.00 |
| Ministral AR | 85/125 (68.0%) | 85/125 (68.0%) | 96/125 (76.8%) | 181/250 (72.4%) | +4.40 | +4.40 |
| BYOD-Llama 25k | 88/125 (70.4%) | 88/125 (70.4%) | 94/125 (75.2%) | 182/250 (72.8%) | +2.40 | +2.40 |
| BYOD-Llama 50k | 95/125 (76.0%) | 95/125 (76.0%) | 98/125 (78.4%) | 193/250 (77.2%) | +1.20 | +1.20 |
| Llama AR | 76/125 (60.8%) | 76/125 (60.8%) | 71/125 (56.8%) | 147/250 (58.8%) | -2.00 | -2.00 |

### MMLU

| Model | Historical | Same IDs, now | Added IDs only | Final | Net Δ | Added Δ |
|---|---:|---:|---:|---:|---:|---:|
| BYOD-Gemma | 86/125 (68.8%) | 80/125 (64.0%) | 86/125 (68.8%) | 166/250 (66.4%) | -2.40 | +2.40 |
| Gemma AR | 81/125 (64.8%) | 81/125 (64.8%) | 83/125 (66.4%) | 164/250 (65.6%) | +0.80 | +0.80 |
| LLaDA | 70/125 (56.0%) | 70/125 (56.0%) | 76/125 (60.8%) | 146/250 (58.4%) | +2.40 | +2.40 |
| BYOD-Qwen | 71/125 (56.8%) | 71/125 (56.8%) | 80/125 (64.0%) | 151/250 (60.4%) | +3.60 | +3.60 |
| Qwen AR | 82/125 (65.6%) | 82/125 (65.6%) | 91/125 (72.8%) | 173/250 (69.2%) | +3.60 | +3.60 |
| BYOD-Ministral | 72/125 (57.6%) | 72/125 (57.6%) | 74/125 (59.2%) | 146/250 (58.4%) | +0.80 | +0.80 |
| Ministral AR | 68/125 (54.4%) | 68/125 (54.4%) | 69/125 (55.2%) | 137/250 (54.8%) | +0.40 | +0.40 |
| BYOD-Llama 25k | 74/125 (59.2%) | 74/125 (59.2%) | 79/125 (63.2%) | 153/250 (61.2%) | +2.00 | +2.00 |
| BYOD-Llama 50k | 77/125 (61.6%) | 77/125 (61.6%) | 73/125 (58.4%) | 150/250 (60.0%) | -1.60 | -1.60 |
| Llama AR | 67/125 (53.6%) | 67/125 (53.6%) | 73/125 (58.4%) | 140/250 (56.0%) | +2.40 | +2.40 |

### MMLU-Pro

| Model | Historical | Same IDs, now | Added IDs only | Final | Net Δ | Added Δ |
|---|---:|---:|---:|---:|---:|---:|
| BYOD-Gemma | 46/125 (36.8%) | 48/125 (38.4%) | 50/125 (40.0%) | 98/250 (39.2%) | +2.40 | +0.80 |
| Gemma AR | 56/125 (44.8%) | 56/125 (44.8%) | 55/125 (44.0%) | 111/250 (44.4%) | -0.40 | -0.40 |
| LLaDA | 53/125 (42.4%) | 53/125 (42.4%) | 39/125 (31.2%) | 92/250 (36.8%) | -5.60 | -5.60 |
| BYOD-Qwen | 36/125 (28.8%) | 36/125 (28.8%) | 44/125 (35.2%) | 80/250 (32.0%) | +3.20 | +3.20 |
| Qwen AR | 53/125 (42.4%) | 53/125 (42.4%) | 63/125 (50.4%) | 116/250 (46.4%) | +4.00 | +4.00 |
| BYOD-Ministral | 45/125 (36.0%) | 45/125 (36.0%) | 37/125 (29.6%) | 82/250 (32.8%) | -3.20 | -3.20 |
| Ministral AR | 41/125 (32.8%) | 41/125 (32.8%) | 48/125 (38.4%) | 89/250 (35.6%) | +2.80 | +2.80 |
| BYOD-Llama 25k | 38/125 (30.4%) | 38/125 (30.4%) | 46/125 (36.8%) | 84/250 (33.6%) | +3.20 | +3.20 |
| BYOD-Llama 50k | 41/125 (32.8%) | 41/125 (32.8%) | 38/125 (30.4%) | 79/250 (31.6%) | -1.20 | -1.20 |
| Llama AR | 52/125 (41.6%) | 52/125 (41.6%) | 56/125 (44.8%) | 108/250 (43.2%) | +1.60 | +1.60 |

### GSM8K

| Model | Historical | Same IDs, now | Added IDs only | Final | Net Δ | Added Δ |
|---|---:|---:|---:|---:|---:|---:|
| BYOD-Gemma | 80/125 (64.0%) | 85/125 (68.0%) | 87/125 (69.6%) | 172/250 (68.8%) | +4.80 | +0.80 |
| Gemma AR | 109/125 (87.2%) | 109/125 (87.2%) | 112/125 (89.6%) | 221/250 (88.4%) | +1.20 | +1.20 |
| LLaDA | 81/125 (64.8%) | 81/125 (64.8%) | 68/125 (54.4%) | 149/250 (59.6%) | -5.20 | -5.20 |
| BYOD-Qwen | 76/125 (60.8%) | 76/125 (60.8%) | 72/125 (57.6%) | 148/250 (59.2%) | -1.60 | -1.60 |
| Qwen AR | 115/125 (92.0%) | 115/125 (92.0%) | 116/125 (92.8%) | 231/250 (92.4%) | +0.40 | +0.40 |
| BYOD-Ministral | 82/125 (65.6%) | 82/125 (65.6%) | 84/125 (67.2%) | 166/250 (66.4%) | +0.80 | +0.80 |
| Ministral AR | 109/125 (87.2%) | 109/125 (87.2%) | 116/125 (92.8%) | 225/250 (90.0%) | +2.80 | +2.80 |
| BYOD-Llama 25k | 82/125 (65.6%) | 82/125 (65.6%) | 80/125 (64.0%) | 162/250 (64.8%) | -0.80 | -0.80 |
| BYOD-Llama 50k | 77/125 (61.6%) | 77/125 (61.6%) | 75/125 (60.0%) | 152/250 (60.8%) | -0.80 | -0.80 |
| Llama AR | 108/125 (86.4%) | 108/125 (86.4%) | 105/125 (84.0%) | 213/250 (85.2%) | -1.20 | -1.20 |

### MATH-500

| Model | Historical | Same IDs, now | Added IDs only | Final | Net Δ | Added Δ |
|---|---:|---:|---:|---:|---:|---:|
| BYOD-Gemma | 37/125 (29.6%) | 36/125 (28.8%) | 25/125 (20.0%) | 61/250 (24.4%) | -5.20 | -4.40 |
| Gemma AR | 75/125 (60.0%) | 75/125 (60.0%) | 55/125 (44.0%) | 130/250 (52.0%) | -8.00 | -8.00 |
| LLaDA | 43/125 (34.4%) | 43/125 (34.4%) | 22/125 (17.6%) | 65/250 (26.0%) | -8.40 | -8.40 |
| BYOD-Qwen | 44/125 (35.2%) | 42/125 (33.6%) | 34/125 (27.2%) | 76/250 (30.4%) | -4.80 | -3.20 |
| Qwen AR | 98/125 (78.4%) | 98/125 (78.4%) | 86/125 (68.8%) | 184/250 (73.6%) | -4.80 | -4.80 |
| BYOD-Ministral | 26/125 (20.8%) | 26/125 (20.8%) | 25/125 (20.0%) | 51/250 (20.4%) | -0.40 | -0.40 |
| Ministral AR | 72/125 (57.6%) | 72/125 (57.6%) | 68/125 (54.4%) | 140/250 (56.0%) | -1.60 | -1.60 |
| BYOD-Llama 25k | 32/125 (25.6%) | 32/125 (25.6%) | 25/125 (20.0%) | 57/250 (22.8%) | -2.80 | -2.80 |
| BYOD-Llama 50k | 37/125 (29.6%) | 35/125 (28.0%) | 26/125 (20.8%) | 61/250 (24.4%) | -5.20 | -3.60 |
| Llama AR | 60/125 (48.0%) | 59/125 (47.2%) | 47/125 (37.6%) | 106/250 (42.4%) | -5.60 | -4.80 |

Historical MATH rescoring of the **same saved text**, before any rerun or added questions:

| Model | Originally recorded | Current scorer on historical answers | Change |
|---|---:|---:|---:|
| BYOD-Gemma | 37/125 (29.6%) | 37/125 (29.6%) | +0.00 |
| Gemma AR | 75/125 (60.0%) | 75/125 (60.0%) | +0.00 |
| LLaDA | 43/125 (34.4%) | 43/125 (34.4%) | +0.00 |
| BYOD-Qwen | 44/125 (35.2%) | 42/125 (33.6%) | -1.60 |
| Qwen AR | 98/125 (78.4%) | 98/125 (78.4%) | +0.00 |
| BYOD-Ministral | 26/125 (20.8%) | 26/125 (20.8%) | +0.00 |
| Ministral AR | 72/125 (57.6%) | 72/125 (57.6%) | +0.00 |
| BYOD-Llama 25k | 32/125 (25.6%) | 32/125 (25.6%) | +0.00 |
| BYOD-Llama 50k | 37/125 (29.6%) | 35/125 (28.0%) | -1.60 |
| Llama AR | 60/125 (48.0%) | 59/125 (47.2%) | -0.80 |

For example, Gemma AR's historical record is 75/125 (60.0%), the first cloud exact-only rescore was 71/125 (56.8%), and the strict v2 scorer gave 74/125 (59.2%), and the presentation-corrected v3 scorer restores 75/125 (60.0%). These are different scoring versions of the same historical answers. The earlier 56.8% value must not be presented as the original recorded baseline. See the completed presentation correction below.

### MBPP sanitized

| Model | Historical | Same IDs, now | Added IDs only | Final | Net Δ | Added Δ |
|---|---:|---:|---:|---:|---:|---:|
| BYOD-Gemma | 46/125 (36.8%) | 61/125 (48.8%) | 48/125 (38.4%) | 109/250 (43.6%) | +6.80 | -5.20 |
| Gemma AR | 37/50 (74.0%) | 37/50 (74.0%) | 127/200 (63.5%) | 164/250 (65.6%) | -8.40 | -8.40 |
| LLaDA | 53/125 (42.4%) | 53/125 (42.4%) | 54/125 (43.2%) | 107/250 (42.8%) | +0.40 | +0.40 |
| BYOD-Qwen | 55/125 (44.0%) | 55/125 (44.0%) | 45/125 (36.0%) | 100/250 (40.0%) | -4.00 | -4.00 |
| Qwen AR | 95/125 (76.0%) | 95/125 (76.0%) | 93/125 (74.4%) | 188/250 (75.2%) | -0.80 | -0.80 |
| BYOD-Ministral | 58/125 (46.4%) | 58/125 (46.4%) | 42/125 (33.6%) | 100/250 (40.0%) | -6.40 | -6.40 |
| Ministral AR | 90/125 (72.0%) | 90/125 (72.0%) | 82/125 (65.6%) | 172/250 (68.8%) | -3.20 | -3.20 |
| BYOD-Llama 25k | 54/125 (43.2%) | 54/125 (43.2%) | 48/125 (38.4%) | 102/250 (40.8%) | -2.40 | -2.40 |
| BYOD-Llama 50k | 55/125 (44.0%) | 55/125 (44.0%) | 52/125 (41.6%) | 107/250 (42.8%) | -1.20 | -1.20 |
| Llama AR | 89/125 (71.2%) | 89/125 (71.2%) | 82/125 (65.6%) | 171/250 (68.4%) | -2.80 | -2.80 |

### HumanEval

| Model | Historical | Same IDs, now | Added IDs only | Final | Net Δ | Added Δ |
|---|---:|---:|---:|---:|---:|---:|
| BYOD-Gemma | 32/125 (25.6%) | 47/125 (37.6%) | 2/39 (5.1%) | 49/164 (29.9%) | +4.28 | -7.72 |
| Gemma AR | 37/50 (74.0%) | 37/50 (74.0%) | 61/114 (53.5%) | 98/164 (59.8%) | -14.24 | -14.24 |
| LLaDA | 50/125 (40.0%) | 50/125 (40.0%) | 7/39 (17.9%) | 57/164 (34.8%) | -5.24 | -5.24 |
| BYOD-Qwen | 37/125 (29.6%) | 37/125 (29.6%) | 2/39 (5.1%) | 39/164 (23.8%) | -5.82 | -5.82 |
| Qwen AR | 83/95 (87.4%) | 83/95 (87.4%) | 50/69 (72.5%) | 133/164 (81.1%) | -6.27 | -6.27 |
| BYOD-Ministral | 44/125 (35.2%) | 44/125 (35.2%) | 4/39 (10.3%) | 48/164 (29.3%) | -5.93 | -5.93 |
| Ministral AR | 107/125 (85.6%) | 107/125 (85.6%) | 28/39 (71.8%) | 135/164 (82.3%) | -3.28 | -3.28 |
| BYOD-Llama 25k | 39/125 (31.2%) | 39/125 (31.2%) | 2/39 (5.1%) | 41/164 (25.0%) | -6.20 | -6.20 |
| BYOD-Llama 50k | 35/125 (28.0%) | 35/125 (28.0%) | 4/39 (10.3%) | 39/164 (23.8%) | -4.22 | -4.22 |
| Llama AR | 70/125 (56.0%) | 70/125 (56.0%) | 14/39 (35.9%) | 84/164 (51.2%) | -4.78 | -4.78 |

## Are any changes larger than expected?

A final 250-question score contains the original questions, so treating historical and final scores as independent would give the wrong comparison. Instead, compare **current outcomes on original IDs against disjoint added IDs**, after fixing scorer and cohort. For each of the 90 model–task cells, use a two-sided Fisher exact test of equal success probabilities; apply Holm correction across all 90. This is an exploratory check for cohort differences under an exchangeability model, not proof that the subsets are random or a test of whether software changed.

There are **11 nominal p<0.05 differences**. After Holm correction at 0.05, the number flagged is **1**. Non-significance is not equivalence or proof that a discrepancy is harmless. Shared task composition can produce correlated changes across models.

| Model / task | Original IDs, current cohort | Added IDs | Added minus original (pp) | Nominal 95% interval (pp) | Exact p | Holm-adjusted p |
|---|---:|---:|---:|---:|---:|---:|
| BYOD-Gemma / HumanEval | 47/125 (37.6%) | 2/39 (5.1%) | -32.47 | [-41.97, -18.25] | 4e-05 | 0.0036 |
| BYOD-Llama 25k / HumanEval | 39/125 (31.2%) | 2/39 (5.1%) | -26.07 | [-35.42, -12.15] | 0.00057 | 0.0509 |
| BYOD-Qwen / HumanEval | 37/125 (29.6%) | 2/39 (5.1%) | -24.47 | [-33.76, -10.63] | 0.0011 | 0.0926 |
| BYOD-Ministral / HumanEval | 44/125 (35.2%) | 4/39 (10.3%) | -24.94 | [-35.62, -9.50] | 0.0023 | 0.2034 |
| LLaDA / MATH-500 | 43/125 (34.4%) | 22/125 (17.6%) | -16.80 | [-27.17, -5.94] | 0.0037 | 0.3212 |
| LLaDA / HumanEval | 50/125 (40.0%) | 7/39 (17.9%) | -22.05 | [-34.59, -5.22] | 0.0124 | 1.0000 |
| Gemma AR / HumanEval | 37/50 (74.0%) | 61/114 (53.5%) | -20.49 | [-34.12, -4.28] | 0.0157 | 1.0000 |
| Gemma AR / MATH-500 | 75/125 (60.0%) | 55/125 (44.0%) | -16.00 | [-27.71, -3.62] | 0.0160 | 1.0000 |
| Qwen AR / HumanEval | 83/95 (87.4%) | 50/69 (72.5%) | -14.90 | [-27.56, -2.65] | 0.0252 | 1.0000 |
| BYOD-Llama 50k / HumanEval | 35/125 (28.0%) | 4/39 (10.3%) | -17.74 | [-28.21, -2.64] | 0.0299 | 1.0000 |
| Llama AR / HumanEval | 70/125 (56.0%) | 14/39 (35.9%) | -20.10 | [-35.71, -2.14] | 0.0428 | 1.0000 |
| BYOD-Ministral / MBPP sanitized | 58/125 (46.4%) | 42/125 (33.6%) | -12.80 | [-24.42, -0.66] | 0.0526 | 1.0000 |

The intervals are nominal 95% Newcombe-Wilson intervals for the difference of two disjoint proportions; they are not simultaneous 90-comparison intervals. They are not obtained by inverting Fisher's exact test, so their zero-crossing and the exact p-value can differ near a threshold, as for Ministral MBPP. The Holm-adjusted p column provides the multiple-comparison decision. These calculations do not measure training-seed variance or remove systematic differences between question subsets.

**BYOD-Gemma HumanEval is the clearest remaining discrepancy.** Its added cohort is only 2/39 correct, versus 47/125 on the fresh original IDs: −32.47 pp between cohorts, adjusted p≈0.00363. Adding that small low-scoring cohort lowers the fresh score from 37.6% to 29.88%, even though comparison with the historical 25.6% still shows a gain. BYOD-Llama 25k HumanEval is borderline after the global correction (adjusted p≈0.0509). The other HumanEval declines form a coherent pattern worth documenting; none should be discarded solely because its individual adjusted p is above 0.05.

HumanEval's earlier CPU audit reproduced all 1,601 saved scores and passed all 164 reference solutions. Added answers contain real algorithmic/runtime failures and, for some diffusion models, outputs that exhaust their 256-token canvas while copying a docstring. The fresh Gemma cohort was generated after that earlier audit; that audit is supporting harness evidence, not an exhaustive execution audit of every final fresh Gemma answer. Static inspection and a current-runtime investigation would be appropriate if further diagnosis is desired. No common scoring repair has been established from the cohort statistics alone.

**LLaDA MATH remains an observed decline, not a demonstrated bug.** The added subset scores 22/125 versus 43/125 initially; exact p≈0.00374 before adjustment and 0.321 after adjustment. The added half contains more level-4/5 items (69 versus 55). The [manual check](LLADA_MANUAL_CHECK.md) found genuine errors in sampled answers, and rescoring all 375 added MATH/GSM8K/MMLU-Pro answers reproduced their flags. None of this proves that question difficulty fully explains the decrease.

### Matched historical-versus-fresh Gemma checks

This is a separate question from sample expansion. Compare the same 125 question IDs before and after rerunning Gemma, using the current scorer on both sets. Exact two-sided McNemar tests use the gained/lost pairs; Holm correction covers Gemma's nine tasks.

| Task | Incorrect → correct | Correct → incorrect | Exact p | Holm-adjusted p |
|---|---:|---:|---:|---:|
| ARC-Challenge | 7 | 4 | 0.5488 | 1.0000 |
| GPQA-Main | 15 | 15 | 1.0000 | 1.0000 |
| HellaSwag | 8 | 8 | 1.0000 | 1.0000 |
| MMLU | 5 | 11 | 0.2101 | 1.0000 |
| MMLU-Pro | 10 | 8 | 0.8145 | 1.0000 |
| GSM8K | 17 | 12 | 0.4583 | 1.0000 |
| MATH-500 | 17 | 18 | 1.0000 | 1.0000 |
| MBPP sanitized | 20 | 5 | 0.0041 | 0.0367 |
| HumanEval | 20 | 5 | 0.0041 | 0.0367 |

MBPP and HumanEval each have 20 gains and five losses (+12 pp on the original questions), adjusted p≈0.0367. These indicate meaningful historical/current generation differences on those fixed items under this diagnostic. They do not establish a training improvement or identify the cause. Original weights/tokenizer were checked, and selected current-runtime answers reproduced across repeat runs and tested backends; the exact historical environment was not fully logged.

### Current paired model comparisons

For context, the following equal-weight nine-task differences use paired item bootstrap intervals, stratified by task (20,000 replicates, seed 20261115). Both models always use identical IDs. These are nominal 95% intervals, not part of the 90 cohort-discrepancy tests and not adjusted across these contrasts. They describe empirical item variation on the selected tasks, not training runs or unseen task families.

| Comparison | Difference (pp) | Nominal 95% interval (pp) |
|---|---:|---:|
| BYOD-Gemma minus LLaDA | +2.88 | [+0.74, +4.98] |
| BYOD-Gemma minus Gemma AR | -10.30 | [-12.33, -8.31] |
| BYOD-Llama 50k minus BYOD-Llama 25k | -0.14 | [-1.81, +1.49] |

The current Gemma–LLaDA interval excludes zero on these selected questions. This is narrower and different from the earlier incomplete eight-task interval; neither its values nor the earlier eight-task point estimate should be carried over unchanged. Gemma remains substantially below its AR parent, while the Llama 50k/25k comparison remains unresolved. These derived comparisons include the completed v3 MATH presentation correction.

## What changed in evaluation and code

1. **Historical data recovery and sample matching.** We selected the latest compatible saved answer for each exact model/task/prompt/target, not the highest-scoring answer. Partial historical denominators remain explicit. Frozen question fingerprints and dataset/model revisions support exact reuse. Raw originals and the pre-expansion backup were retained.
2. **Expanded coverage.** Eight tasks now have 250 unique questions per configuration; HumanEval has its full 164. New queues skip completed IDs and checkpoint each answer locally, with periodic private uploads. Parallel queues were disjoint; all original adapter assets were verified rather than silently replaced with public alternatives.
3. **Qwen AR attention fix.** A matched A100 probe reproduced four selected bad GSM8K/HumanEval answers under eager attention; SDPA corrected all four while holding the model, BF16, greedy decoding, output caps and repetition penalty fixed. The adopted Qwen AR path uses SDPA. A separate historical replay passed 16/16 correctness comparisons, with 13 identical texts. All faulty new eager outputs were excluded regardless of whether they happened to pass. Its originally faulty full HumanEval score was 110/164 (67.07%), versus the corrected 133/164 (81.10%). [Investigation](qwen_investigation.md).
4. **Fresh BYOD-Gemma cohort.** Historical replays disagreed despite matching weight/tokenizer checks. Three selected current-runtime outputs repeated exactly and did not change between the tested eager/SDPA paths. We did not identify a model-loading bug or recover the exact historical environment. The author chose a complete fresh cohort, applied consistently to all tasks and both gains/losses. All 2,164 final Gemma answers are fresh generations; the historical cohort remains separate. [Investigation](gemma_replay_investigation.md).
5. **MATH dependency and final-answer scorer.** The first cloud bundle lacked `math-verify`; normalized exact comparison rejected equivalent expressions. Pinned `math-verify[antlr4_13_2]==0.8.0` and added a startup guard. The current comparator normalizes final answers, respects `FINAL:`, avoids accepting correct intermediate values when the declared final is wrong, and uses bounded symbolic parsing/verification without a permissive whole-rationale fallback. We rescored historical and final answers consistently. Original recorded flags, intermediate cloud flags, strict v2 flags and corrected v3 flags are retained. The v3 rules repair complete scalar presentation and interpret percent units using the reference, without searching rationales for a matching number. See [the completed correction](MATH_PRESENTATION_CORRECTION.md). [Investigation](gemma_math_mbpp_investigation.md).
6. **Code-harness investigations.** HumanEval's CPU audit reproduced 1,601 saved predictions with zero score disagreements, and all 164 reference solutions passed. A separate Gemma MBPP audit reproduced all 281 old/fresh saved flags and passed all 250 reference solutions. No broad code-test harness defect was found. Generated code was executed only in resource-limited cloud children for these audits, not on the laptop. The code extractor handles full functions, canonical body completions, and incomplete/trailing Markdown fences; these paths were audited rather than assumed to explain every decline.
7. **Budgets and decoding deliberately preserved.** AR keeps the author's longer caps (1,024 tokens, or 2,048 for MMLU-Pro). Diffusion retains its task-specific 64/128/256-token canvases, full-NFE decoding, temperature zero and the frozen transfer settings. There was no new low-NFE benchmark condition, matched extra-AR training control, or retraining of BYOD checkpoints. Changes in generation implementation/runtime must not be mistaken for changes to trained weights.
8. **Assembly, uncertainty and restart safeguards.** Assembly rejects wrong plan IDs, overlapping continuation lanes and changed saved predictions, requires the chosen provenance, and verifies every target count. Controller fixes recognize provider scheduling states and normal shutdown margins; bounded queues can resume without duplicating answers. All 75 targeted campaign/protocol/scoring tests pass after the v3 presentation correction; this report adds offline comparison checks and no new generation. Statistical summaries distinguish nine-task means from older eight-task means and use the correct paired/disjoint comparisons.

### Completed MATH presentation correction (v3)

The previously listed numeric-escape, scalar-prose and percent-unit cases are now implemented, tested and uniformly rescored. See [the correction policy, validation and old/new counts](MATH_PRESENTATION_CORRECTION.md). The former scorer and labels remain archived. All 21,640 prediction texts, settings and question identities are unchanged; four final MATH flags and nine historical-baseline flags change from false to true. This is a scoring correction, not new generation or selective answer replacement. Malformed symbolic/truncated answers outside these narrow rules remain subject to the existing final-answer policy.

## Internal sampling and interpretation record

As agreed with the author, detailed ordering diagnostics remain internal. All models share the same selected questions. The [ordering audit](DATASET_ORDER_AUDIT.md) records the ActivityNet-only HellaSwag subset, more reassuring measured distributions for some other tasks, and limits of the checks. Matched questions support within-subset comparisons; the cohort tests and item intervals do not remove systematic selection effects or certify benchmark-wide representativeness. Full HumanEval removes item-subsampling uncertainty for that fixed test set under deterministic decoding, not uncertainty about future problems.

## Explaining the largest discrepancies

This section adds a new offline analysis of the final saved answers. Python outputs were parsed and read, not executed. Counts below use the final selected cohort, rather than the older incomplete HumanEval diagnostics. [Reproduction script](../analysis/explain_final_discrepancies.py); [aggregate diagnostic results](../analysis/final_discrepancy_explanations.json). No new GPU jobs or score replacements were needed.

### 1. BYOD-Gemma HumanEval: a mixture of output allocation and real code errors

The fresh first 125 answers score 47/125 (37.6%); the added 39 score 2/39 (5.1%). All were generated in the adopted current cohort, so this particular difference cannot be attributed simply to replacing historical Gemma answers with fresh answers.

| Diagnostic | Fresh original 125 | Added 39 |
|---|---:|---:|
| Correct | 47 (37.6%) | 2 (5.1%) |
| Invalid Python after normal extraction | 30 (24.0%) | 11 (28.2%) |
| Unterminated triple-quoted string | 8 (6.4%) | 6 (15.4%) |
| Incorrect but syntactically valid | 48 | 26 |
| Mean specification length, Gemma tokens | 140.7 | 166.6 |
| Mean canonical function length, including specification/docstring | 198.4 | 249.1 |
| Canonical full function exceeds 256 tokens | 26 (20.8%) | 16 (41.0%) |
| Canonical answer body alone exceeds 256 tokens | 1 | 0 |

The output canvas is 256 tokens. All 39 added outputs retokenize to within eight tokens of that limit, but so do 124/125 original outputs. A full canvas is therefore not, by itself, an explanation for the drop: completed functions can be followed by repeated fences or a second copy of the function. Retokenized decoded text is only an approximate length diagnostic, not a stored generation-token count.

There is direct evidence of wasted output space in individual failures. HumanEval/126 (`is_sorted`) copies the specification and ends inside its docstring without reaching an implementation. HumanEval/127 (`intersection`) does the same. Six added outputs have unterminated triple-quoted strings. The increased specification length makes this mechanism plausible on more added questions. However, **all 39 canonical answer bodies fit within 256 tokens** if the specification is not repeated. We should describe an output-allocation failure, not claim that these questions are inherently impossible under the canvas.

Length also does not account for the **26 syntactically valid failures** among the added answers. For example, HumanEval/125 (`split_words`) checks commas before whitespace and uses the wrong alphabet parity, violating the stated behavior. HumanEval/128 (`prod_signs`) multiplies the actual integer values instead of just their signs; for `[1,2,2,-4]`, its implementation computes −144 instead of −9. These are real logic errors in extractable code.

**Supported explanation:** the added questions have longer specifications, some answers spend their canvas copying those specifications, and many completed implementations are wrong. **Still unresolved:** how much of the 32.47-point cohort difference each mechanism causes. The syntax-invalid rate itself rises only about four points, so syntax failures alone cannot explain the accuracy gap. A controlled no-docstring or longer-canvas condition could test the output-allocation hypothesis, but it would be a separate decoding/prompt ablation, not a silent replacement of these results.

### 2. HumanEval declines across models: shared item effects, not one universal backend failure

The final static audit gives the following syntax-invalid totals. Passing syntax does not imply passing tests. The counts are unchanged when parsing with Python 3.11 grammar instead of the local parser's default grammar; this remains a syntax check, not a new execution audit.

| Model | Invalid HumanEval programs / 164 | Invalid MBPP programs / 250 |
|---|---:|---:|
| BYOD-Gemma | 41 (25.0%) | 22 (8.8%) |
| BYOD-Llama 50k | 51 (31.1%) | 24 (9.6%) |
| Llama AR | 0 | 0 |
| Gemma AR | 1 (0.6%) | 0 |

Other final HumanEval syntax-invalid counts are BYOD-Qwen 61/164, BYOD-Ministral 52/164, BYOD-Llama 25k 57/164, and LLaDA 4/164. Qwen AR and Ministral AR have no syntax-invalid HumanEval programs in these final outputs. This supports a much larger syntax problem in the conversions, but the blanket manuscript statement that AR answers never have syntax errors needs qualification: Gemma AR has one.

For LLaDA, only one of the 32 failed added HumanEval answers is syntactically invalid; the other 31 are valid Python that fails the benchmark tests. Its drop is therefore not primarily a Markdown extraction or syntax problem. The manual review identified concrete type/API and edge-case errors. Its historical first 50 questions already scored 58.0%, versus 28.0% on questions 50–124, before the new cloud answers were added. That supports a question-composition contribution without proving a universal difficulty ordering.

Gemma AR's large final decline has an additional denominator explanation: its original 74.0% came from just 50 questions. Its 114 additions score 53.5%, resulting in 59.8% overall. The canonical answer body's median length increases from 112 characters on those original 50 to 168.5 on the additions. None of its final answers retokenizes near the intentional 1,024-token cap; only one is syntax-invalid. Longer specifications and more demanding code are plausible contributors, while output truncation is not supported as a general explanation for this AR decline. The historical subset was small, and its 74% point estimate should not be treated as the true whole-benchmark accuracy.

### 3. LLaDA and Gemma AR MATH: difficulty mix contributes, but does not reproduce the full drop

The original and added MATH halves have different level counts: 55 versus 69 level-4/5 questions. We checked whether this alone reproduces the score decline by applying each model's historical, level-specific success rates to the added half's level counts.

| Model | Correct on original 125, current scorer | Expected correct on added 125 if historical within-level rates held | Observed correct on added 125 |
|---|---:|---:|---:|
| LLaDA | 43 | 36.5 | 22 |
| Gemma AR | 75 | 69.9 | 55 |
| BYOD-Gemma, fresh cohort | 36 | 32.5 | 25 |

For LLaDA, this descriptive reweighting moves the expected added score from 34.4% to about 29.2%, while the observed added score is 17.6%. Difficulty labels therefore capture part of the discrepancy but do not account for all of it. Success rates also fall within levels; for example, level 3 goes from 10/25 to 5/27. These are small, noisy groups with different questions and potentially different topics. The table is not a causal decomposition or a guaranteed prediction.

The evidence does not support discarding the low answers. LLaDA's 18 earlier replay controls matched historical correctness, and the manual review found actual arithmetic, reasoning and code errors in new samples. Gemma AR's earlier ten-question backend probe yielded the same five correct and five wrong under eager and SDPA, with verified original normalization tensors. Thus the Qwen attention remedy is not established for Gemma AR. Remaining explanations include item composition within broad difficulty levels and ordinary model errors; unrecorded historical/runtime effects cannot be ruled out exhaustively. The current evidence does not establish one full cause.

### 4. BYOD-Gemma MBPP and HumanEval rerun gains: a real cohort difference, cause still open

On each task's original 125 IDs, the fresh Gemma run has 20 gains and five losses relative to the historical answers. That is +12 pp on the same questions, rather than an effect of adding questions. For MBPP, the historical/fresh code-scoring audit found no disagreements, and the current matched difference survives the nine-task correction. Original weights/tokenizer checks and selected repeat runs do not identify an incorrect loading path or an eager/SDPA remedy.

The most precise explanation we can give is **historical/current generation drift with verified source assets and a consistently selected fresh cohort**. Floating-point/backend differences in iterative denoising are a plausible mechanism, but the historical software/hardware state is incomplete and the causal mechanism has not been established. Do not describe this as a newly trained better model, a random-seed improvement, or a proven backend bug. Both fresh gains and fresh losses were retained.

The final MBPP increase is smaller than the rerun gain because the added questions score 38.4%, versus 48.8% on the fresh original IDs: the final result is 43.6%. Gemma AR's separate MBPP decrease is 74.0% on its original 50 versus 63.5% on 200 additions, giving 65.6%. Its historical 50 were a much smaller subset than the other models' 125; no new Gemma AR scoring or backend defect was established.

### 5. Qwen AR: the severe intermediate discrepancy has a tested remedy

The matched A100 probe isolated eager versus SDPA as the trigger for four selected arithmetic/code failures, holding the model, BF16, greedy decoding and other settings fixed. The bad eager texts reproduced; SDPA corrected all four. The final nine-task results consistently exclude the faulty new eager cohort. This is stronger evidence for a concrete operational fix than the unproven explanations for the remaining Gemma/LLaDA shifts.

The corrected Qwen AR HumanEval result is 133/164 (81.1%), up from the faulty intermediate 110/164 (67.1%). It remains below its original 83/95 (87.4%) because the 69 corrected added questions score 50/69 (72.5%). None of the final Qwen AR HumanEval programs is syntax-invalid. The original severe eager-runtime collapse and the smaller remaining original-versus-added gap are different phenomena and should not be conflated.

## Required changes to the original manuscript

This is an implementation checklist. The new evaluation is complete, but these manuscript edits have **not** all been applied. All listed numerical values include the completed v3 MATH presentation correction. The earlier follow-up is resolved; manuscript tables still need updating from the regenerated results.

### Completed scoring correction and remaining data propagation

- [x] Implement narrow numeric-escape and complete scalar-statement rules, plus reference-aware percentage comparison. Validate correct and wrong final answers and apply the policy uniformly to every model and both old/new cohorts. Preserve the v2 scorer/results and a per-item v3 change audit. [Completed correction](MATH_PRESENTATION_CORRECTION.md).
- [x] Regenerate selected outcomes/audit, this comparison, diagnostic summaries and paired macro intervals under v3; verify unchanged predictions and non-MATH flags.
- [ ] Propagate the corrected source to individual-interval/manuscript artifacts and numerical tables. Keep immutable raw predictions and the original workbook; write a versioned revised-results source rather than editing historical cells without a record.

### Table 3, abstract, main results and discussion

- [ ] Replace all ten common-harness model columns in Table 3 with final 250-question scores, or 164 for HumanEval, and recompute the equal-weight nine-task averages, bolding and underlining. Keep external published LLaDA results in their separate protocol column.
- [ ] State the actual dataset variants and denominators: MATH-500, GPQA-Main, sanitized MBPP, HellaSwag's labeled validation split, and full HumanEval. Explain that all models share the same fixed questions. The detailed ordering audit remains in internal records, as agreed with the author; do not introduce a claim of uniform random selection.
- [ ] Update the abstract in both `paper/iclr2027_conference.tex` and `paper/ABSTRACT.md`: the current Gemma/LLaDA averages are **52.43%/49.55%**, replacing **50.6%/51.9%**. Replace the old “within 1.3 points of LLaDA” statement with the observed **+2.88 pp** difference on the selected questions and appropriately scoped paired uncertainty. Do not turn it into superiority over all DLMs or a claim about every full benchmark.
- [ ] Retain “Gemma is the strongest BYOD conversion” for the current nine-task suite. Update the parent comparison: Gemma AR averages 62.73%, so its matched gap from BYOD-Gemma is **−10.30 pp**, with the current nominal paired 95% interval **[−12.33, −8.31] pp**. Other families also remain below their parents on the nine-task mean.
- [ ] Remove the claimed +0.5-point task-accuracy gain from doubling Llama training. Current means are **47.93% at 25k** and **47.80% at 50k**, a difference of **−0.14 pp**, with paired nominal 95% interval **[−1.81, +1.49] pp**. Four task scores rise and five fall. Say there is no clear task-accuracy benefit in this comparison; do not claim equivalence. Existing validation-loss and perplexity trends are separate measurements and are not invalidated by this accuracy result.
- [ ] Keep the main conclusion focused on feasible conversion across the four tested families. Neither more evaluation questions nor frozen base weights establish universal conversion of any model or isolate capability retention from the added adaptation stage.

The updated task profile still supports a useful distinction between multiple-choice tasks and mathematics/code. The following are differences between category means (each task weighted equally within its category), using the current scorer:

| BYOD model minus its AR parent | Five multiple-choice tasks | Two mathematics tasks | Two code tasks |
|---|---:|---:|---:|
| Gemma | +1.28 pp | −23.60 pp | −25.94 pp |
| Qwen | −6.48 pp | −38.20 pp | −46.26 pp |
| Ministral | +2.72 pp | −29.60 pp | −40.92 pp |
| Llama 25k | +2.96 pp | −20.00 pp | −26.91 pp |

These are descriptive task-score differences, not causal measures of knowledge retention or individually significant improvements. They give a clearer account of where conversion works relatively well and where it remains weak. Additional adaptation and method-specific output budgets remain part of the comparison.

### Correct the specific AR entries questioned by fC22

The [archived submitted manuscript](../baseline/iclr2027_conference.tex) and the recovered historical outputs are not identical. Some problems were unequal denominators; two submitted values also differ from the recovered compatible records. Do not explain all four discrepancies as merely a 125-versus-50 denominator issue.

| Entry | Submitted Table 3 | Recovered historical record | Final expanded result |
|---|---:|---:|---:|
| Gemma AR HumanEval | 74.0% | 37/50 = 74.0% | 98/164 = 59.76% |
| Qwen AR HumanEval | 89.0% | 83/95 = 87.37% | 133/164 = 81.10% |
| Ministral AR HumanEval | 94.0% | 107/125 = 85.6% | 135/164 = 82.32% |
| Gemma AR MBPP | 74.0% | 37/50 = 74.0% | 164/250 = 65.6% |

- [ ] Replace the submitted values and inconsistent blanket “125 per model” note; give explicit denominators. The working paper already corrected some historical entries, but final expansion values and notes still need propagating.
- [ ] Describe the correction as recovery from compatible per-question outputs plus expanded evaluation. The records do not establish exactly why the original spreadsheet contained 89%/94%; call them unsupported/stale submitted values rather than inventing a causal history.
- [ ] Archive the exact source revision, question IDs, model/checkpoint, settings, raw outputs and scoring version for each final cell, with an appropriate anonymous reproducibility artifact before claiming its public availability.

### Protocol, error analysis, uncertainty and figures

- [ ] Replace “planned expansion,” “results pending,” and the historical-only Table 3 caption with completed counts and the final provenance policy. Distinguish retained compatible outcomes from the fresh Gemma cohort and corrected Qwen additions.
- [ ] Document Qwen AR's SDPA backend and the pinned runtime/scoring requirements. Keep the intentional AR output caps (1,024 tokens; MMLU-Pro 2,048), and the recovered diffusion caps (including **64 for MMLU-Pro**, rather than the submitted 128). “Matched” must refer to question IDs/harness, not equal output budgets or equal compute.
- [ ] Add individual 95% Wilson intervals from integer counts and paired, within-task bootstrap intervals for the nine-task differences. Do not pool all questions as if they were one benchmark, compare overlapping before/final scores as independent, or imply ±1–2 pp precision from n=250. Distinguish these uncertainty estimates from the exploratory cohort-discrepancy tests in this internal report.
- [ ] Recompute the syntax-error appendix on final answers. For BYOD-Llama 50k, replace historical HumanEval 35/125 (28.0%) with **51/164 (31.1%)**, and MBPP 11/125 (8.8%) with **24/250 (9.6%)**. The paired Llama AR remains 0/164 and 0/250. Qualify any broader statement that AR outputs never have syntax errors, since Gemma AR has 1/164 HumanEval syntax failure.
- [ ] Add the supported HumanEval diagnosis: copying long docstrings sometimes prevents implementation, while many syntactically valid answers have real semantic errors. Make clear that output allocation is not a complete explanation and that a 256-token answer canvas is separate from the training total-sequence cap of 256.
- [ ] Regenerate benchmark radar panels and any derived task/average plots from the revised data source; update figure captions and embedded `figure_data.json`. The current figure-generation instructions still reference the historical workbook. Cross-check the abstract, Table 3, further-training section, discussion, appendix and `RESULTS_NOTES.md` for stale numbers.
- [ ] Keep open-generation perplexity-/diversity metrics, NFE sweeps, conversion-training time, adapter sizes and the right-context experiment unchanged unless independently re-evaluated. The added task answers do not constitute new evidence for those measurements. Likewise, the merged-model comparison remains a separate smaller historical evaluation, not automatically a 250-question merge result.

## How the additional data help answer the reviewers

### Concerns directly strengthened by the new evidence

| Concern / reviewers | New evidence we can use | What still needs doing before the response claims completion |
|---|---|---|
| **R01: implausible AR cells / provenance — fC22 W1/Q1** | Recovered actual counts and corrected values; all final HumanEval cells now share all 164 questions and MBPP cells share 250; preserved per-question outputs and scorer provenance | Replace manuscript entries/denominator notes and explain the two submitted-versus-recovered value differences transparently |
| **R02: 125 questions, no uncertainty, small LLaDA gap — all reviewers** | Doubled target coverage on eight tasks; full HumanEval; 21,640 selected outcomes; paired model contrasts with task-preserving bootstrap intervals | MATH presentation policy is now corrected; put regenerated counts/intervals in the paper and qualify that the other test sets were not all evaluated in full |
| **R02: alleged gain from 25k→50k — mNeh/dPsL/fC22** | Updated −0.14 pp difference and interval spanning zero | Withdraw the small positive accuracy claim rather than defend it; preserve separate loss/perplexity findings |
| **R08: poor mathematics/code performance — dPsL/fC22/mNeh** | Larger evaluations confirm the deficits; final syntax counts, manually checked math/code errors and separated runtime/scorer corrections make them better characterized | Acknowledge the actual losses and add error analysis; do not imply that correcting Qwen AR fixed BYOD's quality limitations |
| **R10: training/evaluation length mismatch — fC22 Q3** | Static evidence of wasted canvas on copied specifications, longer added HumanEval specifications, and the distinction between full-function and body-only lengths | State the plausible contribution without claiming a causal ablation; separately account for prompt-plus-answer length versus the training total-sequence cap |
| **R12: clarity and reproducibility — mNeh** | Uniform final denominators, explicit cohort rules, code/backend versions and reproducible aggregate analysis | Propagate the clarification to captions/methods and release the promised artifacts before claiming availability |

Current paired nine-task results give a concrete answer to “does proximity to LLaDA hold?” On the selected questions, BYOD-Gemma averages 52.43% versus LLaDA 49.55%; the **+2.88 pp** paired difference has nominal 95% interval **[+0.74, +4.98] pp**. State the protocol and item scope. This supports the practical comparison more strongly than the original point estimates, but is not evidence of universal dominance, identical training exposure or equality of open-generation quality.

### Concerns the extra questions do not resolve

| Concern | Accurate scope of our response |
|---|---|
| **R03: matched LAD/simple conversion control** | More precise scores do not replace a control. Use the LAD/BYOD contribution clarification, and either perform a matched control separately or retain the limitation. |
| **R04/R11: rank, modules, label alignment and loss weights** | The same checkpoints were evaluated more extensively; these are not new training ablations. No new optimum or mechanistic conclusion follows. |
| **R05: additional adaptation and benchmark-training exposure** | We can clarify that all parents are already instruction-tuned and retain the documented source precedents, but added test questions do not isolate the diffusion objective or match additional AR training. |
| **R06: unequal output budgets** | The recovered settings and fixed shared questions improve transparency. They do not supply a matched-length or matched-compute sensitivity experiment. |
| **R07: parallel decoding, reduced-NFE task accuracy and speed** | These runs still use full NFE with one transferred token per step. They do not demonstrate benchmark quality at reduced NFE or controlled latency/throughput gains. |
| **R09: useful infilling/constrained generation** | The expanded suite remains the same nine standard tasks; it is not a new practical infilling evaluation. |

### Draft response material grounded in completed work

**Sample size and uncertainty:** “We thank the reviewers for requesting a larger evaluation. We have expanded the suite to 250 unique questions per task where available and evaluated the full 164-question HumanEval set. All ten model configurations use the same fixed questions for each task, giving 21,640 evaluated model–question pairs. We have computed paired uncertainty for the task averages and will include the counts and intervals in the revised tables. On these questions, BYOD-Gemma averages 52.43% and LLaDA 49.55%, with a paired difference of +2.88 percentage points (nominal 95% CI +0.74 to +4.98).” These aggregate numbers include the completed v3 scoring correction.

**Provenance correction:** “We thank the reviewer for identifying the inconsistent AR entries. Recovering the per-question records showed that some historical cells used fewer than 125 questions, while the submitted Qwen and Ministral HumanEval values also differed from the compatible saved results. We have now evaluated every model on all 164 HumanEval questions and on 250 MBPP questions, with explicit integer counts and saved provenance. The final AR HumanEval scores are 98/164 for Gemma, 133/164 for Qwen and 135/164 for Ministral; Gemma AR MBPP is 164/250.” Add exact manuscript references once the corresponding tables are updated.

**Longer training:** “The larger evaluation changes our earlier interpretation of the 25k-to-50k result. The means are now 47.93% and 47.80%, respectively, and the paired interval for their difference includes zero. We therefore no longer claim an accuracy improvement from this longer run. Its validation-loss and perplexity measurements remain separate observations.” These averages include the completed v3 scoring correction.

**Code quality and length:** “The additional evaluation confirms that mathematics and code remain important limitations. We inspected the failures and separated scoring/runtime defects from model errors. On the fresh Gemma HumanEval cohort, some outputs exhaust the canvas while copying the specification, while many complete functions contain genuine logic errors. We will add these findings and qualify the possible role of output length; we have not established that a larger generation budget alone resolves the gap.”

These passages describe completed evaluation and planned manuscript edits separately. They do not promise new controls, ablations or inference experiments. Use the added evidence to answer the criticism directly, rather than relying on other papers' reporting omissions as the main defense.

## Completion, provenance and reproduction

The final checkpoint was verified at dataset revision `3d68a562325f857ccca3905c894f12cd96deed12`. All three GPU workers are COMPLETED. Both parallel controllers report complete; HumanEval's controller label is stale (`provider_paused`), but its actual worker and saved 328/328 correction outcomes are complete. `all_sample_targets_complete` and `all_humaneval_complete` are true.

- Final selected outcomes and scoring audit: `generation_diagnostic/nov15_gemma/assembled_results.jsonl` and `assembled_audit.json`.
- Preserved historical/intermediate results: `generation_diagnostic/nov15/main_results.jsonl`; original September flags are `recorded_correct`, while `correct` in that file is an intermediate cloud rescore.
- Final checkpoints and pinned source/hash records: `parallel_runs/gemma/`, `parallel_runs/others/`, and `humaneval_runs/latest/`.
- Reproducible numerical comparison: [analysis script](../analysis/final_evaluation_comparison.py) and [JSON with all 90 cells, exact tests, decomposition and input hashes](../analysis/final_evaluation_comparison.json).
- Earlier policy decisions, investigations and immutable inputs remain available through [the discrepancy register](DISCREPANCY_LOG.md). Its older progress paragraphs are historical; this final report supersedes them for current counts and scores.

Regenerate this document and the numerical artifact with:

```sh
.venv/bin/python iclr2027_rebuttal/analysis/explain_final_discrepancies.py
.venv/bin/python iclr2027_rebuttal/analysis/final_evaluation_comparison.py
```

This analysis launched no jobs, changed no cloud state or budgets, and did not update manuscript numerical tables.
