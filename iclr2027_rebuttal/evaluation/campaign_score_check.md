# Old versus new evaluation scores — 9 November 2026

Pinned saved-result revision: `d7f685a1ae81c305d00e9a650cf1e46523fb14fc`. The campaign remains in progress; these are equal-weight nine-task means, not pooled accuracies. Historical outcomes and the pre-expansion backup are unchanged.

Saved outcomes: **17594 / 21,640**. New generations: **6524 / 10,570**, including the initial pilot. Gemma AR is complete at 250 questions/task, capped at HumanEval 164. Gemma diffusion remains deferred at 125/task. Other models have varying intermediate counts.

| Model | Old historical score | Old answers rescored | Expanded score now | Change from rescored old | New answers saved | n/task range |
|---|---:|---:|---:|---:|---:|---:|
| BYOD-Gemma | 50.58% | 49.78% | 49.78% | +0.00 pp | 0 | 125–125 |
| Gemma AR | 65.69% | 65.33% | 62.28% | -3.05 pp | 1189 | 164–250 |
| LLaDA | 51.91% | 51.64% | 50.31% | -1.34 pp | 584 | 164–196 |
| BYOD-Qwen | 48.98% | 48.53% | 48.58% | +0.04 pp | 768 | 164–218 |
| Qwen AR | 71.40% | 70.42% | 60.97% | -9.44 pp | 763 | 164–215 |
| BYOD-Ministral | 49.87% | 49.24% | 47.78% | -1.46 pp | 652 | 164–204 |
| Ministral AR | 63.47% | 62.58% | 61.81% | -0.77 pp | 640 | 164–202 |
| BYOD-Llama 25k | 48.71% | 48.36% | 48.22% | -0.13 pp | 640 | 164–202 |
| Llama AR | 58.76% | 58.04% | 56.96% | -1.09 pp | 640 | 164–202 |
| BYOD-Llama 50k | 49.24% | 48.89% | 47.86% | -1.03 pp | 648 | 164–203 |

## Interpretation

Most expanded diffusion-model averages remain within about 1.5 points of the same original answers rescored under the current harness. Qwen AR is a substantial exception: it drops about 9.44 points on expansion (10.42 versus the old recorded mean). Its GSM8K accuracy shifts from 92% to 65.40%, HumanEval from 87.37% to 67.07%, and its MATH result from 69.60% on rescored old items to 54.29% on the larger subset. This warrants a protocol/reproducibility check; do not attribute the full difference to sampling noise or claim a smaller causal conversion gap. The expansion uses deterministic prefixes, so changes are not independent random-sample comparisons.

The rescored baselines still contain unresolved historical MATH-scorer disagreements. They separate scoring effects from item expansion but are not human-adjudicated corrections. Different models have different current question coverage; final paired comparisons must align fingerprints. Gemma replay disagreement investigation remains deferred at the author’s request.

## Per-task counts and scores

| Model | Task | Historical score (n) | Old answers rescored | Current score (correct/n) |
|---|---|---:|---:|
| BYOD-Gemma | arc_c | 86.40% (125) | 86.40% | 86.40% (108/125) |
| BYOD-Gemma | gpqa | 32.00% (125) | 32.00% | 32.00% (40/125) |
| BYOD-Gemma | hellaswag | 75.20% (125) | 75.20% | 75.20% (94/125) |
| BYOD-Gemma | mmlu | 68.80% (125) | 68.80% | 68.80% (86/125) |
| BYOD-Gemma | mmlu_pro | 36.80% (125) | 36.80% | 36.80% (46/125) |
| BYOD-Gemma | gsm8k | 64.00% (125) | 64.00% | 64.00% (80/125) |
| BYOD-Gemma | math | 29.60% (125) | 22.40% | 22.40% (28/125) |
| BYOD-Gemma | humaneval | 25.60% (125) | 25.60% | 25.60% (32/125) |
| BYOD-Gemma | mbpp | 36.80% (125) | 36.80% | 36.80% (46/125) |
| Gemma AR | arc_c | 88.80% (125) | 88.80% | 88.80% (222/250) |
| Gemma AR | gpqa | 28.00% (125) | 28.00% | 29.60% (74/250) |
| Gemma AR | hellaswag | 69.60% (125) | 69.60% | 70.40% (176/250) |
| Gemma AR | mmlu | 64.80% (125) | 64.80% | 65.60% (164/250) |
| Gemma AR | mmlu_pro | 44.80% (125) | 44.80% | 44.40% (111/250) |
| Gemma AR | gsm8k | 87.20% (125) | 87.20% | 88.40% (221/250) |
| Gemma AR | math | 60.00% (125) | 56.80% | 48.00% (120/250) |
| Gemma AR | humaneval | 74.00% (50) | 74.00% | 59.76% (98/164) |
| Gemma AR | mbpp | 74.00% (50) | 74.00% | 65.60% (164/250) |
| LLaDA | arc_c | 86.40% (125) | 86.40% | 86.73% (170/196) |
| LLaDA | gpqa | 31.20% (125) | 31.20% | 31.63% (62/196) |
| LLaDA | hellaswag | 69.60% (125) | 69.60% | 68.91% (133/193) |
| LLaDA | mmlu | 56.00% (125) | 56.00% | 57.29% (110/192) |
| LLaDA | mmlu_pro | 42.40% (125) | 42.40% | 39.58% (76/192) |
| LLaDA | gsm8k | 64.80% (125) | 64.80% | 63.02% (121/192) |
| LLaDA | math | 34.40% (125) | 32.00% | 28.12% (54/192) |
| LLaDA | humaneval | 40.00% (125) | 40.00% | 34.76% (57/164) |
| LLaDA | mbpp | 42.40% (125) | 42.40% | 42.71% (82/192) |
| BYOD-Qwen | arc_c | 84.00% (125) | 84.00% | 84.40% (184/218) |
| BYOD-Qwen | gpqa | 28.80% (125) | 28.80% | 32.57% (71/218) |
| BYOD-Qwen | hellaswag | 72.80% (125) | 72.80% | 73.15% (158/216) |
| BYOD-Qwen | mmlu | 56.80% (125) | 56.80% | 57.87% (125/216) |
| BYOD-Qwen | mmlu_pro | 28.80% (125) | 28.80% | 33.80% (73/216) |
| BYOD-Qwen | gsm8k | 60.80% (125) | 60.80% | 58.60% (126/215) |
| BYOD-Qwen | math | 35.20% (125) | 31.20% | 31.16% (67/215) |
| BYOD-Qwen | humaneval | 29.60% (125) | 29.60% | 23.78% (39/164) |
| BYOD-Qwen | mbpp | 44.00% (125) | 44.00% | 41.86% (90/215) |
| Qwen AR | arc_c | 91.20% (125) | 91.20% | 90.23% (194/215) |
| Qwen AR | gpqa | 34.40% (125) | 34.40% | 30.70% (66/215) |
| Qwen AR | hellaswag | 75.20% (125) | 75.20% | 74.41% (157/211) |
| Qwen AR | mmlu | 65.60% (125) | 65.60% | 68.25% (144/211) |
| Qwen AR | mmlu_pro | 42.40% (125) | 42.40% | 32.23% (68/211) |
| Qwen AR | gsm8k | 92.00% (125) | 92.00% | 65.40% (138/211) |
| Qwen AR | math | 78.40% (125) | 69.60% | 54.29% (114/210) |
| Qwen AR | humaneval | 87.37% (95) | 87.37% | 67.07% (110/164) |
| Qwen AR | mbpp | 76.00% (125) | 76.00% | 66.19% (139/210) |
| BYOD-Ministral | arc_c | 83.20% (125) | 83.20% | 81.86% (167/204) |
| BYOD-Ministral | gpqa | 27.20% (125) | 27.20% | 29.90% (61/204) |
| BYOD-Ministral | hellaswag | 76.80% (125) | 76.80% | 75.74% (153/202) |
| BYOD-Ministral | mmlu | 57.60% (125) | 57.60% | 55.94% (113/202) |
| BYOD-Ministral | mmlu_pro | 36.00% (125) | 36.00% | 34.33% (69/201) |
| BYOD-Ministral | gsm8k | 65.60% (125) | 65.60% | 65.00% (130/200) |
| BYOD-Ministral | math | 20.80% (125) | 15.20% | 17.50% (35/200) |
| BYOD-Ministral | humaneval | 35.20% (125) | 35.20% | 29.27% (48/164) |
| BYOD-Ministral | mbpp | 46.40% (125) | 46.40% | 40.50% (81/200) |
| Ministral AR | arc_c | 76.80% (125) | 76.80% | 73.76% (149/202) |
| Ministral AR | gpqa | 36.80% (125) | 36.80% | 33.66% (68/202) |
| Ministral AR | hellaswag | 68.00% (125) | 68.00% | 71.50% (143/200) |
| Ministral AR | mmlu | 54.40% (125) | 54.40% | 53.50% (107/200) |
| Ministral AR | mmlu_pro | 32.80% (125) | 32.80% | 36.00% (72/200) |
| Ministral AR | gsm8k | 87.20% (125) | 87.20% | 89.45% (178/199) |
| Ministral AR | math | 57.60% (125) | 49.60% | 47.74% (95/199) |
| Ministral AR | humaneval | 85.60% (125) | 85.60% | 82.32% (135/164) |
| Ministral AR | mbpp | 72.00% (125) | 72.00% | 68.34% (136/199) |
| BYOD-Llama 25k | arc_c | 83.20% (125) | 83.20% | 83.66% (169/202) |
| BYOD-Llama 25k | gpqa | 29.60% (125) | 29.60% | 30.69% (62/202) |
| BYOD-Llama 25k | hellaswag | 70.40% (125) | 70.40% | 73.00% (146/200) |
| BYOD-Llama 25k | mmlu | 59.20% (125) | 59.20% | 60.00% (120/200) |
| BYOD-Llama 25k | mmlu_pro | 30.40% (125) | 30.40% | 35.00% (70/200) |
| BYOD-Llama 25k | gsm8k | 65.60% (125) | 65.60% | 62.81% (125/199) |
| BYOD-Llama 25k | math | 25.60% (125) | 22.40% | 21.61% (43/199) |
| BYOD-Llama 25k | humaneval | 31.20% (125) | 31.20% | 25.00% (41/164) |
| BYOD-Llama 25k | mbpp | 43.20% (125) | 43.20% | 42.21% (84/199) |
| Llama AR | arc_c | 79.20% (125) | 79.20% | 77.72% (157/202) |
| Llama AR | gpqa | 32.00% (125) | 32.00% | 28.71% (58/202) |
| Llama AR | hellaswag | 60.80% (125) | 60.80% | 61.50% (123/200) |
| Llama AR | mmlu | 53.60% (125) | 53.60% | 55.50% (111/200) |
| Llama AR | mmlu_pro | 41.60% (125) | 41.60% | 42.50% (85/200) |
| Llama AR | gsm8k | 86.40% (125) | 86.40% | 86.43% (172/199) |
| Llama AR | math | 48.00% (125) | 41.60% | 39.70% (79/199) |
| Llama AR | humaneval | 56.00% (125) | 56.00% | 51.22% (84/164) |
| Llama AR | mbpp | 71.20% (125) | 71.20% | 69.35% (138/199) |
| BYOD-Llama 50k | arc_c | 82.40% (125) | 82.40% | 80.79% (164/203) |
| BYOD-Llama 50k | gpqa | 27.20% (125) | 27.20% | 26.60% (54/203) |
| BYOD-Llama 50k | hellaswag | 76.00% (125) | 76.00% | 78.61% (158/201) |
| BYOD-Llama 50k | mmlu | 61.60% (125) | 61.60% | 60.70% (122/201) |
| BYOD-Llama 50k | mmlu_pro | 32.80% (125) | 32.80% | 32.34% (65/201) |
| BYOD-Llama 50k | gsm8k | 61.60% (125) | 61.60% | 58.71% (118/201) |
| BYOD-Llama 50k | math | 29.60% (125) | 26.40% | 25.50% (51/200) |
| BYOD-Llama 50k | humaneval | 28.00% (125) | 28.00% | 23.78% (39/164) |
| BYOD-Llama 50k | mbpp | 44.00% (125) | 44.00% | 43.72% (87/199) |
