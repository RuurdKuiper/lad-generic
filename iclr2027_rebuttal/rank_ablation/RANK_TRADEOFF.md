# Rank trade-off evidence — completed 25k comparison

All comparisons use the fresh controlled runs and their actual 90/10 validation objective. The historical rank-1024 curve is excluded. Main benchmark models and results are unchanged.

At **25,000 matched updates**, losses are 128: **1.268363**, 512: **1.195119**, 1024: **1.152463**, 2048: **1.102089**. The 512→1024 reduction is **0.042656**; 1024→2048 is **0.050374**. All four ranks have completed the matched 25,000-update budget.

The rank increases differ: 512 additional rank units versus 1,024. Loss reduction per added rank unit is **0.00008331** versus **0.00004919**, a **41.0%** smaller return for the latter increase. Adapter parameter count scales linearly with rank in this fixed-backbone/Q/V experiment. This is the diminishing-return comparison; it must not be confused with a smaller absolute loss reduction.

| Rank | LoRA parameters | Median seconds/update | Clean 100-update intervals | Validation through update |
|---|---:|---:|---:|---:|
| 128 | 54.5M | 0.3736 | 150 | 25,000 |
| 512 | 218.1M | 0.3857 | 150 | 25,000 |
| 1024 | 436.2M | 0.4029 | 150 | 25,000 |
| 2048 | 872.4M | 0.4336 | 150 | 25,000 |

Rank 2048 is **12.41%** slower per update than 512 and **7.63%** slower than 1024 in the available timing intervals. These are training-update timings on the same GPU family and recipe, with validation/checkpoint work excluded. The first three ranks shared one GPU allocation; rank 1024 uses separate allocations of the same hardware type. These timings are not full end-to-end run durations or repeated-run confidence intervals.

## Memory evidence

Rank 1024 was selected to balance validation quality with single-A100 feasibility: per-device batch size 16 on an 80GB A100, or 8 on a 40GB A100, in the original implementation. This is the author's reported configuration rationale, not a new controlled hardware comparison. The rank study uses RTX PRO 6000 GPUs. Memory requirements depend on the implementation and configuration.

The four-rank logs contain no common peak-VRAM comparison. Rank 2048 has twice the adapter parameters of 1024 (872.4M vs 436.2M), and four times those of 512. At fixed precision and optimizer, adapter parameters, gradients and Adam moments scale with this count. This is an inferred increase in adapter-related training-state storage, **not a measured doubling of total peak GPU memory**. Live device-memory samples from the rank-1024 recovery are retained separately in `gpu_memory_*.jsonl`; they do not establish peaks for the other ranks.

## Interpretation and remaining work

Rank 1024 offers a practical quality/resource compromise under the original single-GPU constraint; rank 2048 still gives lower validation loss. All four ranks have completed the matched 25,000-update budget. The resource-normalized return is the relevant comparison, not a claim that the absolute 1024→2048 gain is always smaller. The CSV retains every shared step. One seed/parent and a validation-only objective do not establish downstream benchmark accuracy, generation quality or a universally optimal rank.

The author reports earlier exploratory trials with MLP adapters, other attention-projection targets and learning rates. These guided the shared recipe but were not retained as a systematic controlled sweep. Treat them as author-reported design motivation, without numerical superiority or optimality claims. Rank, target modules, learning rate and backbone can interact. The present experiment isolates rank under fixed choices; focused module/LR sensitivity controls remain separate from an exhaustive joint sweep.

## Artifact status

All four loss histories reach 25k: **True**. The latest provider job stage is **ERROR**, and the rank-1024 final adapter is present: **False**. Training completion and successful model persistence are separate checks. See `final_run_verification.json` and `rank1024_recovery_diagnosis.json`. The final recovery saved its 25k validation result but encountered a Hub storage/billing 403 when uploading the final recovery checkpoint; its 22.5k recovery state remains available. No recharge or storage deletion is authorized by this report.

## Reproduce

After refreshing the logs, run `python iclr2027_rebuttal/rank_ablation/summarize_rank_tradeoff.py`. The adjacent JSON contains source hashes, available Hub revisions and each retained timing interval; the CSV contains every shared-step loss comparison, including reductions normalized by added rank.
