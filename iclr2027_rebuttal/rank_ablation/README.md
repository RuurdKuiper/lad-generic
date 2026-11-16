# Llama 8B rank study — all four validation histories reach 25k

Ranks **128, 512, 1024 and 2048** have each reached **25,000 optimizer updates**.
This is a separate validation-only rank experiment: the original benchmarked
BYOD-Llama checkpoint and scores remain unchanged.

**Artifact status:** the final rank-1024 validation result and full loss history
are saved, but the recovery job failed during the 25k checkpoint upload with
HTTP 403: Hugging Face requires automatic credit recharge for more storage.
Its final adapter is absent; the latest persisted recovery checkpoint is 22.5k.
The other three runs' final adapters remain saved. See
[verification](final_run_verification.json) and
[provider diagnosis](rank1024_recovery_diagnosis.json).
No recharge, storage deletion or additional GPU job was started in response.

Rank 1024 was originally chosen to balance quality with single-A100 feasibility:
per-device batch 16 on an 80GB A100, or 8 on a 40GB A100, in the original
implementation. The controlled rank study uses RTX PRO 6000 GPUs; these are
separate implementation/hardware configurations. We compare loss improvement
**per added rank/adapter parameter**, since 1024→2048 adds twice as many
parameters as 512→1024. The larger rank still achieves lower validation loss.

## Curves and model retention

The four [configurations](configs/) use:

| Artifact | Policy |
|---|---|
| Training loss | `metrics.jsonl`, every 100 updates |
| Validation loss | Same file, every 250 updates: weighted total, answer loss and padding loss |
| Validation examples | Same 200 examples, seed 42; deterministic per-example corruption and identical evaluation batches of 8 |
| Published run model | One `final/` adapter after update 25,000; `save_best_model: false` |
| Recovery state | Every 2,500 updates, including model, optimizer, scheduler and RNG state; keep the latest **two completed checkpoints** |
| Loss-log retention | Independent of checkpoints; never pruned with older checkpoints |
| Cloud persistence | Private Hub dataset, separate `rank-128/`, `rank-512/`, `rank-1024/`, `rank-2048/` directories |

[The worker](run_training.py) commits logs/configuration after every validation.
It uploads each completed checkpoint before deleting older completed checkpoints
from the current Hub tree or allowing local checkpoint pruning. If an upload
fails, the worker stops and leaves older recovery state available. A new worker
downloads the latest completed checkpoint and the full logs before resuming.
At most 2,499 completed updates between regular checkpoints may need repeating
after a failure during training; the first checkpoint is at update 2,500.

On restart, metric points beyond the restored checkpoint are moved out of the
active curve into a `metrics.before-resume-*.jsonl` backup before replaying those
steps. Original log history remains available. The historical best validation
loss is restored too. Stochastic training corruption with worker processes is
not promised to resume bit for bit; deterministic validation remains comparable.

Checkpoints are full Accelerate recovery states and can be substantially larger
than the final LoRA adapter. GPU preflight must measure save/upload/restore time
and space, including Transformer Engine state. The two-checkpoint limit bounds
the active checkpoint set; Hub commit history can retain older blobs. No history
rewriting or permanent cleanup is included here.

## Plot after training

The actual 90/10 training objective is available as a separate
[PNG](figures/rank_validation_training_objective.png),
[PDF](figures/rank_validation_training_objective.pdf), and
[raw CSV](figures/rank_validation_training_objective.csv). It uses the three
completed runs and the available **fresh rank-1024** points; it does not include
the historical 1024 loss with its different/uncertain normalization. Every
plotted point is verified against `0.9 * answer_loss + 0.1 * padding_loss`.
The old log lacks the components needed to reconstruct its full curve under
this objective. Rebuild the current objective plot after downloading logs:

```sh
.venv/bin/python iclr2027_rebuttal/rank_ablation/plot_rank_validation.py --objective
```

The historical four-curve overlay (three new ranks and the old rank 1024) is saved as
[PNG](figures/rank_validation_common_ce.png),
[PDF](figures/rank_validation_common_ce.pdf),
[SVG](figures/rank_validation_common_ce.svg) and
[raw CSV](figures/rank_validation_common_ce.csv). It uses the common logged
unweighted masked-token cross-entropy, not the differently normalized weighted
losses. All four curves have 100 validation points through 25,000 updates. The
main axis is logarithmic and an inset enlarges the late-stage 1024/2048 curves.
The historical-reference caveat remains. Source hashes are recorded in the
adjacent JSON manifest. Rebuild it with:

```sh
.venv/bin/python iclr2027_rebuttal/rank_ablation/plot_rank_validation.py
```

Once the three run directories are downloaded under `outputs/rank-ablation/fp8-checkpoint-v2/`,
run from the repository root:

```sh
.venv/bin/python iclr2027_rebuttal/rank_ablation/download_results.py
.venv/bin/python plot_losses.py \
  outputs/rank-ablation/fp8-checkpoint-v2/rank-128 \
  outputs/rank-ablation/fp8-checkpoint-v2/rank-512 \
  outputs/rank-ablation/fp8-checkpoint-v2/rank-2048 \
  --labels r128 r512 r2048 --split validation \
  --output iclr2027_rebuttal/rank_ablation/validation_loss.pdf \
  --csv iclr2027_rebuttal/rank_ablation/validation_loss.csv
```

Use `--metric answer_loss` or `--metric padding_loss` for component curves.
Use `--output ...png` for a PNG, or omit `--split validation` to show training
loss too. Validation curves are unsmoothed; CSV exports raw, unsmoothed points.
The logs are sufficient to regenerate every curve without loading a model or
renting a GPU. Report the final loss at update 25,000 as the primary comparison,
and report the lowest observed validation loss and its step separately. The
weights at that lowest-loss step are not guaranteed to be retained under the
chosen final-only model policy.

## Controlled settings and interpretation

The controlled configurations derive from the archived original Llama 25k configuration,
rather than the current general-purpose configuration, which has since changed.
Only `lora_r`, `lora_alpha` and the output path differ between the four configs.
Alpha equals rank, so alpha/r remains one. Targets are Q/V projections, dropout
is zero and normalization layers remain frozen. Other settings include batch
16, 256 tokens, cosine LR 1e-5, warmup 100 and IID mask-only corruption. Model,
tokenizer and raw dataset revisions are pinned. FP8 is requested with BF16
master weights; validation remains BF16. GPU preflight must confirm that FP8 is
actually active for all three runs.

| Rank | Trainable LoRA parameters |
|---|---:|
| 128 | 54,525,952 |
| 512 | 218,103,808 |
| 1024 — fresh controlled run | 436,207,616 |
| 2048 | 872,415,232 |

Llama's V projection has output width 1,024, so its effective matrix rank cannot
increase beyond that width. Rank 2,048 still increases Q capacity and the V
factorization's parameter count; it does not double effective rank everywhere.

All four controlled runs use the author-confirmed paper objective: separately
normalized answer and padding losses, weighted 0.9/0.1. The historical 1024
configuration predates the explicit weighting setting. Treat it as a historical
reference with a training-objective provenance limitation, not a fourth perfectly
controlled run. Re-score the existing adapter on the same validation examples,
corruption masks, batches and objective before comparing its endpoint with the
three new runs. Do not directly overlay an old loss curve with a different or
unknown loss definition. Its saved `best` adapter may also represent a different
step than the final 25k endpoint.

This study can establish sensitivity of the denoising objective to rank under
these settings. It cannot establish benchmark accuracy, generation quality,
statistical robustness across training seeds or an optimal rank for every model.
The author's earlier tenfold loss-weight experiments are preliminary reported
observations until their configurations and numerical outputs are recovered;
they do not establish that the present weights are optimal.

## Original three-rank launch and budget record

The author authorized a **$42 total cap** and instructed us not to start if the
complete study does not appear to fit. The private artifact repository is
[`Ruurd/iclr2027-rank-ablation`](https://huggingface.co/datasets/Ruurd/iclr2027-rank-ablation).
CPU runtime preparation completed successfully. The bounded
[corrected GPU job](https://huggingface.co/jobs/Ruurd/6afa1def23985fb9cd83bc2c) was
submitted on 15 November at 23:02 Windhoek time. It starts with timing and recovery checks;
native GPU recovery is verified and the all-three-runs forecast gate has passed. Rank 128 is now continuing toward 25,000 updates; ranks 512 and 2048 follow.
Receipts and reservations are in [budget_ledger.json](budget_ledger.json).

The current plan uses one RTX PRO 6000 sequentially, with a **13-hour 54-minute
provider timeout**, reduced after accounting for the stopped first GPU attempt.
At the verified $0.045833/minute rate that reserves $38.270555, including one
extra billing minute. Each one-hour CPU build reserves $0.0305. The first GPU
job is confirmed stopped and conservatively accounted at $0.641662, including
time before submission was reconciled; this upper bound is not a billing receipt.
The combined reservations/accounting plus a $3 startup contingency total
**$41.973217**, below $42. There are
no automatic GPU retries or follow-up jobs. Historical 3.2-hour Llama training
provides the initial feasibility estimate; it is not a measured rank-study time.

The initial FP8 source build caught missing cuDNN include paths on the CPU image;
those paths were corrected before any GPU allocation. The compiled wheel is
built on CPU, recorded with a SHA-256 and loaded into the same pinned Torch
2.8/CUDA 12.8 image on GPU. Matching published clean tokens are reused: their
manifest exactly matches our recipe, with 400,000 training rows. No paid raw-data
retokenization is permitted if that profile does not match.

The first GPU check reached update 250 at approximately 0.44 seconds/update,
then caught an actual checkpoint restoration failure. Accelerate's safetensors
cleanup removed separate empty Transformer Engine `_extra_state` keys. The
corrected trainer uses native Torch serialization for FP8 recovery checkpoints
and explicitly preserves FP8 calibration after BF16 validation. A CPU regression
test verifies strict restoration of the extra state and calibration. The final
inference adapter still uses safetensors. The updated local selection passes
97 tests. The corrected GPU job has now strictly restored its saved model and FP8 state, continued from update 250 to 500, and verified that every optimizer parameter retained update count 500.
The original attempt remains at `rank-2048/` for diagnosis. It is excluded from
the corrected study, whose models and curves start fresh under
`fp8-checkpoint-v2/rank-{rank}/`. No original prediction/log files were overwritten.

[batch_worker.py](batch_worker.py) times the first 250 updates of each actual
run and checks rank-2048 full-state recovery from update 250 to 500. These
updates use the full 25k data prefix and LR schedule and will be reused.
Recovery checkpoints at 250/500 supplement the normal 2,500-update cadence.
The full-run gate forecasts remaining training, validation and checkpoint
save/upload time with a **20% margin**, plus finalization time. If that forecast
does not fit the remaining allocation, it stops. It checks the forecast again
between completed ranks. A soft deadline requests a saved checkpoint before
the provider timeout. The provider timeout and the reservation ledger bound
spending even if a runtime forecast is wrong. Do not claim all three completed
until `study_status.json` reports completion.

The prepared worker requires an existing private Hub **dataset** repository and
an environment-provided `HF_TOKEN` with gated Llama access and write permission:

```sh
python iclr2027_rebuttal/rank_ablation/run_training.py \
  --rank 128 --repo Ruurd/REPLACE_WITH_PRIVATE_RANK_STUDY_REPO
```

This command runs training on its current machine; it does not submit a Hugging
Face GPU job. [hf_jobs.py](hf_jobs.py) stages immutable sources, builds the runtime
on CPU and submits the bounded GPU worker after the runtime is ready. The GPU
timing/recovery check runs before the decision to continue all three models to
25,000 updates. Read `study_status.json` in the private repository for the current
decision and progress; the local receipts alone do not establish experiment
completion.
No benchmark evaluator, generation/perplexity validation or final denoising test
evaluation is invoked. This study uses validation loss only.


## Measured budget decision

The live worker passed its all-three-runs forecast gate after strictly testing
GPU checkpoint recovery. Observed times/update were 0.37871s (rank 128),
0.38994s (rank 512) and 0.43588s (rank 2048). Save plus upload took 43.94s,
46.71s and 67.56s respectively; fixed-set validation took 2.90s, 3.02s and
3.68s. At that decision, 13.51 hours remained before the reserved deadline
and the conservative remaining forecast was 10.99 hours, including the 20%
margin. The projected study cost is **$31.56**, or **$34.56** if the entire
$3 startup contingency is used. The reservation/accounting envelope remains
**$41.973217**, below the author's $42 ceiling. These are forecasts and
conservative reservations, not a final invoice. See [cost_projection.json](cost_projection.json)
and the captured [study status](latest_study_status.json).

All three ranks use the same 25k-update plan, training data and fixed validation
procedure. Pilot updates from the corrected study are reused; the first failed
serialization attempt is retained separately and excluded. The live worker
rechecks the remaining forecast between completed ranks, stops on non-finite
validation, and saves a checkpoint near the soft deadline. It does not submit
new GPU jobs automatically. Completion and final losses remain pending.


## 16 November — separate fresh rank-1024 control

The author has authorized a fresh **rank 1024**, 25,000-update run with **$17
available**, replacing the earlier decision not to retrain that rank. This
completes the separate rank experiment under one recipe. **The benchmarked
BYOD-Llama checkpoint and its benchmark results remain unchanged.** The new
adapter belongs only to the rank study at `fp8-checkpoint-v2/rank-1024/`.

`configs/rank_1024.yaml` matches all three completed configurations in every
field except rank, alpha and its own output directory. Scientific source hashes
are identical to immutable revision `ac79d63b638c28fe95ff554eaff39042a3026f06`.
[controlled_recipe.json](controlled_recipe.json) records those hashes and the
unchanged benchmark report/manuscript hashes. The fresh model starts from the
pinned instruction-tuned parent, without loading the historical diffusion
adapter. Its first 250 updates are saved and resumed, matching ranks 128/512.

[single_rank_worker.py](single_rank_worker.py) reports to `rank1024_status.json`,
keeping the completed three-rank `study_status.json` intact. Validation-only
evaluation, deterministic 200-example masks, full logs and the two-checkpoint
retention policy are unchanged. The historical figure and original rank-1024
logs remain historical artifacts; generate a distinct matched figure after the
new run completes, and do not silently substitute it into benchmark tables.

Provider duration metadata puts all previous jobs at a conservative **$25.67048**
total, including scheduling time and one extra minute per job. The expected new
run is around **3 hours / $8–10**. Its provider timeout is **5 hours**, reserving
**$13.795733** plus **$2** startup contingency: **$15.795733** maximum planning
allowance, below the additional $17. Combined with the earlier jobs the envelope
is **$41.466213**, below the original $42 ceiling as well. The worker checks a
20%-margin forecast after update 250 and stops at a saved checkpoint near its
soft deadline. No additional benchmark run is submitted.


Fresh rank-1024 job: [6afaaed223985fb9cd8452fa](https://huggingface.co/jobs/Ruurd/6afaaed223985fb9cd8452fa),
submitted 16 November at 09:20 Windhoek time. Its immutable input revision is
`c333ae2669d7d76faab394c7f9db9272bccc7ff6`. Budget/recovery checks pass (19
targeted tests), and setup verified the scientific library against the other
three runs and their **actual resolved configurations**, not only the templates.
The original benchmark report/manuscript hashes remain unchanged.
