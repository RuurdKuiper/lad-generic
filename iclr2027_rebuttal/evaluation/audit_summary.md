# Historical rerun audit

Source: original Drive JSONL files read without modification. No generation or generated code was executed. Counts below use the recorded scorer; scoring verification is pending.

Selection: within each model/task, use the most recent run’s settings, then the newest available prediction for each exact current prompt/target among the original first 125 positions. Earlier runs fill missing positions only when compatible. A partial latest run is not promoted to a complete 125-question result. Seeds may differ for temperature-zero decoding. No result is selected by accuracy.

| Model | Task | Latest run | Latest correct/n | Retained unique n |
|---|---|---|---:|---:|
| gemma_d | arc_c | 20260922T095556.834769Z | 108/125 | 125 |
| gemma_d | gpqa | 20260922T095556.834769Z | 40/125 | 125 |
| gemma_d | hellaswag | 20260922T095556.834769Z | 94/125 | 125 |
| gemma_d | mmlu | 20260924T073259.327829Z | 8/11 | 125 |
| gemma_d | mmlu_pro | 20260922T095556.834769Z | 46/125 | 125 |
| gemma_d | gsm8k | 20260922T095556.834769Z | 80/125 | 125 |
| gemma_d | math | 20260922T095556.834769Z | 37/125 | 125 |
| gemma_d | humaneval | 20260924T182515.574720Z | 32/125 | 125 |
| gemma_d | mbpp | 20260924T182515.574720Z | 46/125 | 125 |
| gemma_ar | arc_c | 20260922T095556.834769Z | 111/125 | 125 |
| gemma_ar | gpqa | 20260922T095556.834769Z | 35/125 | 125 |
| gemma_ar | hellaswag | 20260922T095556.834769Z | 87/125 | 125 |
| gemma_ar | mmlu | 20260922T095556.834769Z | 81/125 | 125 |
| gemma_ar | mmlu_pro | 20260922T095556.834769Z | 56/125 | 125 |
| gemma_ar | gsm8k | 20260922T095556.834769Z | 109/125 | 125 |
| gemma_ar | math | 20260922T095556.834769Z | 75/125 | 125 |
| gemma_ar | humaneval | 20260918T155517.804510Z | 37/50 | 50 |
| gemma_ar | mbpp | 20260918T155517.804510Z | 37/50 | 50 |
| llada | arc_c | 20260921T170118.455805Z | 108/125 | 125 |
| llada | gpqa | 20260921T170118.455805Z | 39/125 | 125 |
| llada | hellaswag | 20260921T170118.455805Z | 87/125 | 125 |
| llada | mmlu | 20260921T170118.455805Z | 70/125 | 125 |
| llada | mmlu_pro | 20260921T170118.455805Z | 53/125 | 125 |
| llada | gsm8k | 20260921T170118.455805Z | 81/125 | 125 |
| llada | math | 20260921T170118.455805Z | 43/125 | 125 |
| llada | humaneval | 20260921T170118.455805Z | 50/125 | 125 |
| llada | mbpp | 20260921T170118.455805Z | 53/125 | 125 |
| qwen_d | arc_c | 20260925T063651.044858Z | 105/125 | 125 |
| qwen_d | gpqa | 20260924T073620.648034Z | 36/125 | 125 |
| qwen_d | hellaswag | 20260925T063651.044858Z | 91/125 | 125 |
| qwen_d | mmlu | 20260925T063651.044858Z | 71/125 | 125 |
| qwen_d | mmlu_pro | 20260925T063651.044858Z | 36/125 | 125 |
| qwen_d | gsm8k | 20260925T063651.044858Z | 7/14 | 125 |
| qwen_d | math | 20260924T073620.648034Z | 44/125 | 125 |
| qwen_d | humaneval | 20260924T073620.648034Z | 37/125 | 125 |
| qwen_d | mbpp | 20260924T073620.648034Z | 55/125 | 125 |
| qwen_ar | arc_c | 20260925T075355.953265Z | 114/125 | 125 |
| qwen_ar | gpqa | 20260925T075355.953265Z | 43/125 | 125 |
| qwen_ar | hellaswag | 20260925T063651.044858Z | 94/125 | 125 |
| qwen_ar | mmlu | 20260925T063651.044858Z | 82/125 | 125 |
| qwen_ar | mmlu_pro | 20260925T063651.044858Z | 53/125 | 125 |
| qwen_ar | gsm8k | 20260925T075355.953265Z | 115/125 | 125 |
| qwen_ar | math | 20260925T075355.953265Z | 98/125 | 125 |
| qwen_ar | humaneval | 20260925T075355.953265Z | 83/95 | 95 |
| qwen_ar | mbpp | 20260925T103125.705197Z | 95/125 | 125 |
| ministral_d | arc_c | 20260924T073620.648034Z | 104/125 | 125 |
| ministral_d | gpqa | 20260924T073620.648034Z | 34/125 | 125 |
| ministral_d | hellaswag | 20260924T073620.648034Z | 96/125 | 125 |
| ministral_d | mmlu | 20260924T073620.648034Z | 72/125 | 125 |
| ministral_d | mmlu_pro | 20260924T073620.648034Z | 45/125 | 125 |
| ministral_d | gsm8k | 20260924T073620.648034Z | 82/125 | 125 |
| ministral_d | math | 20260924T073620.648034Z | 26/125 | 125 |
| ministral_d | humaneval | 20260924T073620.648034Z | 44/125 | 125 |
| ministral_d | mbpp | 20260924T073620.648034Z | 58/125 | 125 |
| ministral_ar | arc_c | 20260925T111612.477543Z | 96/125 | 125 |
| ministral_ar | gpqa | 20260925T111612.477543Z | 46/125 | 125 |
| ministral_ar | hellaswag | 20260925T111612.477543Z | 85/125 | 125 |
| ministral_ar | mmlu | 20260925T111612.477543Z | 68/125 | 125 |
| ministral_ar | mmlu_pro | 20260925T111612.477543Z | 41/125 | 125 |
| ministral_ar | gsm8k | 20260925T111612.477543Z | 109/125 | 125 |
| ministral_ar | math | 20260925T111612.477543Z | 72/125 | 125 |
| ministral_ar | humaneval | 20260925T111612.477543Z | 107/125 | 125 |
| ministral_ar | mbpp | 20260925T103125.705197Z | 90/125 | 125 |
| llama_25k | arc_c | 20260921T170118.455805Z | 104/125 | 125 |
| llama_25k | gpqa | 20260921T170118.455805Z | 37/125 | 125 |
| llama_25k | hellaswag | 20260921T170118.455805Z | 88/125 | 125 |
| llama_25k | mmlu | 20260921T170118.455805Z | 74/125 | 125 |
| llama_25k | mmlu_pro | 20260921T170118.455805Z | 38/125 | 125 |
| llama_25k | gsm8k | 20260921T170118.455805Z | 82/125 | 125 |
| llama_25k | math | 20260921T170118.455805Z | 32/125 | 125 |
| llama_25k | humaneval | 20260921T170118.455805Z | 39/125 | 125 |
| llama_25k | mbpp | 20260921T170118.455805Z | 54/125 | 125 |
| llama_ar | arc_c | 20260921T170118.455805Z | 99/125 | 125 |
| llama_ar | gpqa | 20260921T170118.455805Z | 40/125 | 125 |
| llama_ar | hellaswag | 20260921T170118.455805Z | 76/125 | 125 |
| llama_ar | mmlu | 20260921T170118.455805Z | 67/125 | 125 |
| llama_ar | mmlu_pro | 20260921T170118.455805Z | 52/125 | 125 |
| llama_ar | gsm8k | 20260921T170118.455805Z | 108/125 | 125 |
| llama_ar | math | 20260921T170118.455805Z | 60/125 | 125 |
| llama_ar | humaneval | 20260921T170118.455805Z | 70/125 | 125 |
| llama_ar | mbpp | 20260921T170118.455805Z | 89/125 | 125 |
| llama_50k | arc_c | 20260924T195342.825090Z | 103/125 | 125 |
| llama_50k | gpqa | 20260924T195342.825090Z | 34/125 | 125 |
| llama_50k | hellaswag | 20260924T195342.825090Z | 95/125 | 125 |
| llama_50k | mmlu | 20260924T195342.825090Z | 77/125 | 125 |
| llama_50k | mmlu_pro | 20260924T195342.825090Z | 41/125 | 125 |
| llama_50k | gsm8k | 20260924T195342.825090Z | 77/125 | 125 |
| llama_50k | math | 20260924T195342.825090Z | 37/125 | 125 |
| llama_50k | humaneval | 20260924T195342.825090Z | 35/125 | 125 |
| llama_50k | mbpp | 20260924T195342.825090Z | 55/125 | 125 |

## Current averages from historical recorded outcomes

These are descriptive historical protocols, with unequal AR/diffusion output limits. The expansion preserves these intentional method-specific output limits. Intervals are unadjusted 95% normal intervals for the equal-weight mean of nine fixed tasks, using actual item counts and independent items/tasks. Code results have not yet been rescored with the current harness.

| Model | Historical mean | Approximate 95% CI | n by task (table order) |
|---|---:|---:|---|
| gemma_d | 50.58% | 47.93–53.22% | 125, 125, 125, 125, 125, 125, 125, 125, 125 |
| gemma_ar | 65.69% | 62.71–68.66% | 125, 125, 125, 125, 125, 125, 125, 50, 50 |
| llada | 51.91% | 49.16–54.66% | 125, 125, 125, 125, 125, 125, 125, 125, 125 |
| qwen_d | 48.98% | 46.28–51.68% | 125, 125, 125, 125, 125, 125, 125, 125, 125 |
| qwen_ar | 71.40% | 68.97–73.82% | 125, 125, 125, 125, 125, 125, 125, 95, 125 |
| ministral_d | 49.87% | 47.20–52.53% | 125, 125, 125, 125, 125, 125, 125, 125, 125 |
| ministral_ar | 63.47% | 60.86–66.07% | 125, 125, 125, 125, 125, 125, 125, 125, 125 |
| llama_25k | 48.71% | 46.03–51.40% | 125, 125, 125, 125, 125, 125, 125, 125, 125 |
| llama_ar | 58.76% | 56.04–61.47% | 125, 125, 125, 125, 125, 125, 125, 125, 125 |
| llama_50k | 49.24% | 46.57–51.92% | 125, 125, 125, 125, 125, 125, 125, 125, 125 |

Order: arc_c, gpqa, hellaswag, mmlu, mmlu_pro, gsm8k, math, humaneval, mbpp.

## Confirmed provenance issues

- Gemma AR HumanEval and MBPP are 37/50 in the latest recovered files, consistent with 74%, rather than 125 evaluated items.
- Qwen AR HumanEval has 83/95 in the latest recovered file; this does not establish the manuscript’s 89% value.
- Ministral AR HumanEval has a later 107/125 run (85.6%), superseding the earlier 47/50 (94%) result.
- Latest Gemma diffusion MMLU contains 11 items and latest Qwen diffusion GSM8K contains 14; matching older results can fill unchanged questions.
- GPQA has 125 records in the later runs. An initial audit split a Unicode line separator inside a JSON string; reading physical newline boundaries fixes that parsing error, with zero invalid records.
- Actual historical AR output caps are 1,024 tokens, or 2,048 for MMLU-Pro. Historical diffusion MMLU-Pro uses 64, despite the manuscript’s 128-token description. The expansion preserves 64 for diffusion and 2,048 for AR on MMLU-Pro, as the author confirms that the longer AR limits were intentional.

Dataset/base model commit IDs were not recorded in the original files. Exact prompt/target matching and the original adapter paths support provisional reuse; complete checkpoint identity and pilot replay checks are still required. New base/dataset revisions are frozen in hub_lock.json. Never label recorded historical scores as rescored outcomes.
