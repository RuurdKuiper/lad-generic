# Current historical macro-average confidence intervals

Updated from per-question outputs using the latest compatible reruns. Counts are verified; correctness remains the recorded historical scorer, pending consistent rescoring. Earlier manuscript-only approximations are superseded.

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


Variance: SE² = Σ[p_t(1−p_t)/(n_t−1)]/81; CI = mean ± 1.959964×SE. These are item intervals on nine fixed tasks, not training-seed or causal conversion-effect intervals. No multiplicity correction or finite-population correction. See [the run-selection audit](evaluation/audit_summary.md) and [reproduction script](evaluation/historical_report.py).
