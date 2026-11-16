# Gemma results before and after the credit-limited pilot

Historical baseline uses the selected latest-compatible records preserved in results_before_expansion/2026-11-08. Current results use the completed pilot’s saved outcomes. Original files and the baseline backup are unchanged.

BYOD-Gemma has no additional generated questions; its change is entirely rescoring. Gemma AR has 728 additional questions plus rescoring of retained predictions. This is an incomplete expansion, not a completed 250-item evaluation.

| Task | BYOD before | BYOD rescored now (n=125) | AR before | AR rescored, same old items | AR expanded now | Current AR n |
|---|---:|---:|---:|---:|---:|---:|
| ARC-C | 86.40% | 86.40% | 88.80% (111/125) | 88.80% | 88.83% (183/206) | 206 |
| GPQA | 32.00% | 32.00% | 28.00% (35/125) | 28.00% | 29.61% (61/206) | 206 |
| HellaSwag | 75.20% | 75.20% | 69.60% (87/125) | 69.60% | 69.42% (143/206) | 206 |
| MMLU | 68.80% | 68.80% | 64.80% (81/125) | 64.80% | 65.05% (134/206) | 206 |
| MMLU-Pro | 36.80% | 36.80% | 44.80% (56/125) | 44.80% | 45.15% (93/206) | 206 |
| GSM8K | 64.00% | 64.00% | 87.20% (109/125) | 87.20% | 87.86% (181/206) | 206 |
| MATH-500 | 29.60% | 22.40% | 60.00% (75/125) | 56.80% | 50.97% (105/206) | 206 |
| HumanEval | 25.60% | 25.60% | 74.00% (37/50) | 74.00% | 60.31% (79/131) | 131 |
| MBPP | 36.80% | 36.80% | 74.00% (37/50) | 74.00% | 63.08% (82/130) | 130 |
| **Nine-task mean** | **50.58%** | **49.78%** | **65.69%** | **65.33%** | **62.25%** | — |

## Approximate macro intervals

Equal-weight mean of nine fixed tasks; unadjusted normal item-sampling intervals using the actual task denominators. Independent-item/task assumption; not a paired difference interval or training-seed uncertainty.

| Model / stage | Macro mean | Approximate 95% CI |
|---|---:|---:|
| BYOD-Gemma historical | 50.58% | 47.93–53.22% |
| BYOD-Gemma rescored | 49.78% | 47.16–52.40% |
| Gemma AR historical | 65.69% | 62.71–68.66% |
| Gemma AR rescored on old items | 65.33% | 62.36–68.31% |
| Gemma AR expanded | 62.25% | 60.05–64.46% |

## Scoring changes and scope

Nine historical BYOD-Gemma MATH answers and four historical Gemma AR MATH answers change from true to false under the frozen scorer. This identifies disagreements between scorers, not independently adjudicated errors in the old labels. Inspect those answers before treating the new labels as definitive. Other retained Gemma answers have unchanged correctness flags.

Averages have equal task weights, despite different question counts. Expanded AR and unchanged-size diffusion averages therefore describe different sample coverage; use shared question fingerprints for any paired difference analysis. LLaDA was only partly rescored before cancellation and was not expanded, so no fully rescored LLaDA average is asserted here. Checkpoint replay verification remains outstanding.
