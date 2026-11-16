# Resumable benchmark expansion

The user authorized continued evaluation after adding Hugging Face credit. Targets remain 250 distinct questions/task, or all 164 HumanEval questions, across the ten original model/checkpoint configurations. The campaign imports all **3,268** saved scored outcomes, including **728** new Gemma AR generations. Original historical backups remain unchanged.

## How continuation works

A cloud CPU controller submits one A100 80 GB Job at a time in blocks of at most four hours. A clean time-limit completion automatically starts the next block from its saved checkpoint. Model batches rotate after at most 128 new questions, prioritizing models with less completed coverage. LLaDA gets a brief initial diffusion timing batch. Each task retains the frozen question ordering, prompts, dataset/model revisions and method-specific generation limits.

Every scored answer is flushed locally immediately. Private Hugging Face checkpoints are committed at most once every two minutes and at clean shutdown. Resume validates the model, exact question fingerprint, frozen settings and plan identity before skipping completed answers. No saved GPU generation is repeated simply because a new job starts.

A sudden provider kill can lose approximately the last two minutes of unuploaded work (plus a question still being generated). Those questions can be regenerated; uploaded results remain available and are deduplicated. An upload failure stops further generation rather than spending hours accumulating uncheckpointed answers. Checkpoints and code execution tests remain private, with tokens passed as secrets and generated code scored under an unprivileged Linux account.

Credits running out, a runtime error, an explicit cancellation, a provider pause or a reproducibility disagreement stop the campaign for review/resume. The controller does not blindly retry errors or create overlapping Jobs. Its own timeout is 36 hours; the same resume command also starts a fresh controller after that timeout. Adding credit does not by itself guarantee a stopped campaign has restarted.

## Budget

Total compute uses a conservative **$75 ceiling including previous tests**, within the earlier approximately €100 plan. Each controller reserves at most $0.37 CPU compute. GPU blocks reserve their full timeout plus a rounding minute, then use an observed conservative upper bound after completion. Resume retains the previous budget ledger. No credit purchase or automatic top-up is authorized. Current rates are checked before new GPU Jobs.

If the campaign reaches its budget ceiling before all questions finish, it stops with the remaining queue intact. Changing this ceiling requires a subsequent explicit instruction. Results and checkpoint counts are actual outcomes; the budget ledger is conservative accounting rather than a measured Hugging Face invoice.

## Original model assets

BYOD generation uses SHA-256-verified original paper adapters. All five Drive checkpoints are being copied and privately staged by `stage_original_checkpoints.py`, including distinct Llama 25k and 50k assets. Each manifest points to an immutable Hub commit and records the original path and every file hash. The worker verifies the downloaded hashes before model loading. Published adapter configurations alone are not treated as proof of identical tensors.

**One-time local requirement:** keep the computer awake while the original Drive adapters finish copying/uploading. The copy/stage process is local; progress is in `/tmp/iclr-original-assets-progress.txt` and `original_assets.json`. Cloud evaluation and cloud checkpointing run independently of the laptop. If local staging stops, it can be restarted with the same script; copies resume after verifying their existing prefixes. Models awaiting original adapters are deferred while other work continues. Once eligible work finishes, the GPU stops and the CPU controller waits for assets rather than renting idle GPU time.

## Status and resume

From the repository root:

```sh
.venv/bin/python iclr2027_rebuttal/evaluation/campaign.py status
.venv/bin/python iclr2027_rebuttal/evaluation/campaign.py resume
```

`resume` refuses to start when matching campaign Jobs are active. It also refuses an exhausted budget. Unknown Job receipts are conservatively reconciled before launching another Job.

The immutable input commit and local Job links are in `campaign_staging.json` and `campaign_launch.json`. Cloud state is in the private dataset `Ruurd/iclr2027-rebuttal-eval`:

- `campaigns/<plan_id>/results.jsonl`: durable per-question outcomes.
- `campaigns/<plan_id>/replays.jsonl`: diffusion replay checks, excluded from independent sample counts.
- `campaigns/<plan_id>/progress.json`: actual counts, deferred/blocked models and status.
- `campaigns/<plan_id>/controller.json`: submitted Jobs and cumulative budget ledger.
- `assets/manifest.json`: verified original checkpoint revisions/hashes.

Fifteen offline checks cover latest-compatible reuse, Unicode JSONL parsing, actual denominators, upload throttling, changed-setting rejection, task interleaving, budget reservations, interrupted-block accounting, deduplication, fair model rotation and refusal to use unverified published BYOD weights.

The historical MATH scorer disagreements still need inspection. This campaign keeps one frozen scorer; saved predictions can be rescored later without paying for new GPU generation. Partial results must not be presented as completed 250-item benchmark evaluations.


Gemma diffusion replay investigation: see [verified checks, case directions and remaining diagnostic](gemma_replay_investigation.md). The three disagreements are two improvements and one regression, not evidence of a loading failure. Other campaign models remain unaffected by this diagnostic.
