# Completed benchmark intervals for the revised manuscript

Generated offline from the versioned per-question selection; historical workbooks are unchanged.

| Model | Nine-task mean | Nominal 95% bootstrap interval |
|---|---:|---:|
| BYOD-Gemma | 52.43% | [50.53, 54.34]% |
| Gemma AR | 62.73% | [60.83, 64.62]% |
| BYOD-Qwen | 48.29% | [46.34, 50.24]% |
| Qwen AR | 70.66% | [68.91, 72.44]% |
| BYOD-Ministral | 48.54% | [46.65, 50.48]% |
| Ministral AR | 62.70% | [60.85, 64.60]% |
| BYOD-Llama-25k | 47.93% | [46.01, 49.85]% |
| BYOD-Llama-50k | 47.80% | [45.88, 49.70]% |
| Llama AR | 56.71% | [54.74, 58.67]% |
| LLaDA | 49.55% | [47.55, 51.55]% |

20,000 percentile resamples within each of nine fixed tasks (seed 20261116); every task retains equal weight. Paired contrasts use shared item draws (seed 20261115), rather than subtracting marginal confidence limits.

21,640 final selected outcomes versus 11,070 historical outcomes: net +10,570. Replacement generations and diagnostics are not counted as newly added selected items.

Per-task intervals are 95% Wilson intervals from integer counts. All intervals are nominal/unadjusted and describe item variation, not variation across training seeds. They do not establish benchmark-wide representativeness or uncertainty over unseen task families.
