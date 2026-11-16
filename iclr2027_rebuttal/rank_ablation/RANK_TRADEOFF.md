# Rank trade-off evidence — provisional snapshot

All comparisons use the fresh controlled runs and their actual 90/10 validation objective. The historical rank-1024 curve is excluded. Main benchmark models and results are unchanged.

At **5,000 matched updates**, losses are 512: **1.317903**, 1024: **1.265038**, 2048: **1.254511**. The 512→1024 reduction is **0.052865**; 1024→2048 is **0.010527**. Compare the same training step, not finished 25k models against a partially trained 1024.

| Rank | LoRA parameters | Median seconds/update | Clean 100-update intervals | Validation through update |
|---|---:|---:|---:|---:|
| 128 | 54.5M | 0.3736 | 150 | 25,000 |
| 512 | 218.1M | 0.3857 | 150 | 25,000 |
| 1024 | 436.2M | 0.4045 | 30 | 5,000 |
| 2048 | 872.4M | 0.4336 | 150 | 25,000 |

Rank 2048 is **12.41%** slower per update than 512 and **7.18%** slower than the current 1024 timing estimate. The 1024 estimate is provisional while training continues. These are training-update timings on the same GPU family and recipe, with validation/checkpoint work excluded. The first three ranks shared one GPU allocation; the fresh 1024 uses another allocation of the same hardware type. These timings are not full end-to-end run durations or repeated-run confidence intervals.

## Memory evidence

Our training logs contain no peak-VRAM measurement. Rank 2048 has twice the adapter parameters of 1024 (872.4M vs 436.2M), and four times those of 512. At fixed precision and optimizer, adapter parameters, gradients and Adam moments scale with this count. This is an inferred increase in adapter-related training-state storage, **not a measured doubling of total peak GPU memory**. Frozen backbone storage, activations, workspaces and allocator behavior also contribute to the peak. No GPU rerun is required or proposed solely to measure memory.

## Interpretation and remaining work

The current matched-step curves suggest diminishing validation-loss gains and make rank 1024 a candidate practical compromise under this recipe. They do not yet establish a final-endpoint result or a globally optimal rank. The pattern need not hold at every early update: the CSV includes all shared steps, including points with a larger 1024→2048 gain. Keep the endpoint claim pending until 1024 reaches 25k; then regenerate this summary and compare all four final losses. One seed/parent and a validation-only objective do not establish downstream benchmark accuracy or generation quality.

The author reports earlier exploratory trials with MLP adapters, other attention-projection targets and learning rates. These guided the shared recipe but were not retained as a systematic controlled sweep. Treat them as author-reported design motivation, without numerical superiority or optimality claims. Rank, target modules, learning rate and backbone can interact. The present experiment isolates rank under fixed choices; focused module/LR sensitivity controls remain separate from an exhaustive joint sweep.

## Reproduce

After refreshing the logs, run `python iclr2027_rebuttal/rank_ablation/summarize_rank_tradeoff.py`. The adjacent JSON contains source hashes, available Hub revisions and each retained timing interval; the CSV contains every shared-step loss comparison. Regeneration after further 1024 progress updates this snapshot.
