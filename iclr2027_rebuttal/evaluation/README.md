# Additional evaluation: staged replay pilot

The original short-sample Job was submitted, hit the Hub commit limit during rescoring, and was cancelled with explicit approval. Its 2,540 saved scored outcomes are preserved. The credit-bounded replacement uses the CPU staging/handoff described below. The original private package is staged at [Ruurd/iclr2027-rebuttal-eval](https://huggingface.co/datasets/Ruurd/iclr2027-rebuttal-eval). `staging.json` records its immutable commit and plan hash. The user approved cancellation and replacement within $4.95 on 8 November 2026.

## Scope and reuse

Target 250 unique questions on each of nine tasks, capped at all 164 HumanEval questions: 2,164 per model, ten model/checkpoint configurations, 21,640 outcomes. Dataset revisions, exact prompts/targets and question fingerprints are frozen. MMLU/MMLU-Pro keep the original deterministic shuffled prefix; other tasks keep their original prefix. New questions extend those prefixes without outcome-based selection.

| Configuration | Candidate retained generations | New generations to reach target |
|---|---:|---:|
| Gemma diffusion | 1,125 | 1,039 |
| Gemma AR | 975 | 1,189 |
| LLaDA | 1,125 | 1,039 |
| Qwen diffusion | 1,125 | 1,039 |
| Qwen AR | 1,095 | 1,069 |
| Ministral diffusion | 1,125 | 1,039 |
| Ministral AR | 1,125 | 1,039 |
| Llama diffusion 25k | 1,125 | 1,039 |
| Llama AR | 1,125 | 1,039 |
| Llama diffusion 50k | 1,125 | 1,039 |
| **Total** | **11,070** | **10,570** |

These are reuse candidates, conditional on checkpoint and harness verification. Latest compatible per-question predictions supersede earlier ones even if their accuracy is lower. Partial reruns retain compatible older predictions for unchanged questions; no duplicate questions are counted twice. See [the historical audit](audit_summary.md) for actual latest-run sizes, recovered counts and historical intervals.

**Author-confirmed generation limits:** AR retains 1,024 tokens, or 2,048 for MMLU-Pro. Diffusion retains 64 for ARC/HellaSwag/MMLU/MMLU-Pro, 128 for GPQA/MBPP, and 256 for GSM8K/MATH/HumanEval, with full-length NFE/block size. The 64-token diffusion MMLU-Pro setting corrects the manuscript's 128-token description. Different limits are intentional; this is not equal-output or equal-compute evaluation. No matched-output AR reruns are queued.

Retained predictions are rescored under a single frozen harness without GPU regeneration. This separates parser/test-harness fixes from genuinely missing predictions. Recorded historical scores remain available alongside rescored outcomes. Reports use actual denominators, per-task Wilson intervals, approximate stratified macro intervals and task-stratified paired bootstrap intervals on shared questions. Partial results must not be presented as a completed 250-item evaluation.

## Pilot for approval

- One A100 80 GB Job (`a100-large`), hard provider timeout **2 hours**; worker stops starting work earlier. Current verified rate is about **$2.50/hour**, so maximum compute is approximately **$5**, before applicable tax. No automatic follow-up Jobs.
- Models: Gemma diffusion, Gemma AR, LLaDA. Rescore their retained predictions, then generate at most two missing questions per task/model (54 total) and replay two retained questions per task for Gemma diffusion and LLaDA (36 total). Replays verify reproducibility and are not counted as new independent questions.
- Persist private outcomes, progress and timings at most once every two minutes, plus at clean shutdown, with backoff for HTTP 429 and transient server errors. Every scored item is also written and flushed locally. Resume uses plan/model/question identities, preventing double counting. An abrupt provider kill may lose work since the last successful upload; it does not invalidate previously saved outcomes.
- Pilot results determine actual throughput, scoring corrections and feasibility of the remaining queue. A two-hour pilot is not a promise to finish all 90 generated/replayed predictions.

**Checkpoint limitation:** downloading the original Drive weights is unusually slow. The published Gemma adapter has exactly matching adapter and training configurations; its complete tensor identity with the original has not yet been established. The pilot explicitly tests replay compatibility using that pinned published adapter. Full evaluation remains blocked by the launcher until the original checkpoints are staged/verified or checkpoint equivalence is resolved. Llama 25k and 50k must remain separate; do not silently substitute the published Llama adapter for either.

The original Drive files were read without modification. A stopped partial local checkpoint copy is excluded from the staged package. Inputs include gated GPQA data and must remain private.

## Reproduce and operate

From the repository root, using the existing environment:

```sh
.venv/bin/python -m pytest -q iclr2027_rebuttal/evaluation/test_protocol.py
.venv/bin/python iclr2027_rebuttal/analysis/current_macro_intervals.py
.venv/bin/python iclr2027_rebuttal/evaluation/hf_job.py preview --phase pilot
```

Only after explicit approval for the paid pilot:

```sh
.venv/bin/python iclr2027_rebuttal/evaluation/hf_job.py launch --phase pilot --approved
```

`launches.json` records the Job ID and timeout; repeated launches of the same phase are refused. The full phase is separately gated by checkpoint readiness and approval. The overall design reserves no more than 30 GPU-hours (about $75 compute at the checked rate), leaving margin within the €100 budget, but full-run feasibility must be assessed from the pilot rather than assumed. Positive Hugging Face credit balance and current A100 availability are required; neither is established by staging. No credit purchase was made.

Job image is pinned by Docker digest (PyTorch 2.8.0, CUDA 12.8); inference dependencies and model/dataset commits are pinned. The Hub token is supplied as a Job secret, never written into the package. Code benchmark answers run in resource-limited subprocesses under a separate unprivileged Linux account without that token. This is not a complete network sandbox.

Offline checks cover latest-rerun precedence, compatible partial-run reuse, changed prompts/settings, intentional AR limits, real denominators, Unicode JSONL records and the pilot/full checkpoint gate. CUDA execution is deliberately left to the approved pilot.

References: [Hugging Face Jobs](https://huggingface.co/docs/hub/en/jobs), [Jobs SDK guide](https://huggingface.co/docs/huggingface_hub/guides/jobs). Hardware rates were checked against the authenticated Jobs hardware API on 8 November 2026; the launcher refuses a rate above the checked A100 price.

## Separate historical backup

The selected pre-expansion predictions and byte-for-byte contributing source files are preserved separately in [results_before_expansion/2026-11-08](../results_before_expansion/2026-11-08/README.md), with actual counts, source provenance and SHA-256 verification. Snapshot files are read-only; new and rescored outcomes go to the private Job results path. Original success flags remain historical, and the snapshot contains failed answers as well as successful ones.


## Approved $4.95 credit-bounded replacement

The user confirmed $4.95 in credits and explicitly approved cancelling the submitted pilot and replacing it with Gemma-first continuation. The first Job (`6af04fc8e6320c66fad74304`) is cancelled. Its log identifies HTTP 429 after too many checkpoint commits; no new GPU generations were completed. The historical backup remains unchanged.

The replacement fixes checkpoint throttling (two minutes, independent of how quickly rows are scored), handles rate-limit backoff and resumes 2,540 saved scores without rescoring them. Ten offline tests pass, including the upload cadence, task interleaving and total-credit calculation. The source scorer and generation functions are unchanged, as verified before importing the prior outcomes.

`credit_orchestrator.py` runs on CPU Basic while waiting for Hub commit access to recover. It tests commit access before staging and before allocating an A100. It has a 90-minute hard timeout, maximum CPU cost $0.01503, and launches at most one GPU job. The A100 has a 110-minute provider timeout and a 105-minute worker limit with shutdown margin. Conservative prior usage ($0.291669), CPU wait and the new A100 ceiling ($4.58337) total **$4.890069 compute**, leaving margin below $4.95. This is an upper bound based on the checked rates, not a measured bill. No credit purchase or top-up is authorized.

Order: **Gemma AR, Gemma diffusion, LLaDA, Qwen AR, Qwen diffusion, Ministral AR, Ministral diffusion, Llama AR, Llama-25k diffusion**. Within each model, missing questions are interleaved across tasks while preserving each task's frozen order. Work continues toward the 250 targets until the time limit, rather than stopping after two new questions per task. Later models run only if the preceding work finishes in time. Llama-50k remains excluded until its original checkpoint is available. Diffusion models undergo replay checks; a score disagreement conservatively skips that model's additional generations and flags it for review.

The CPU Job ID and budget are in `credit_orchestrator_job.json`. After handoff, the GPU Job ID and new immutable input commit are saved privately at `control/credit-pilot-launch.json` in the HF dataset and printed in CPU Job logs. Do not submit another orchestrator or GPU pilot while this handoff is pending. The old `hf_job.py` command/`staging.json` describe the original submission, not a new launch instruction.


## Pilot results now available

The replacement completed normally at its worker time limit, saving 728 new Gemma AR generations. See [before/after task scores and macro intervals](results_comparison.md) and [execution outcome](pilot_outcome.md). No new diffusion timing was obtained. Thirteen historical MATH labels disagree with the current scorer and require review; no new paid Job has been submitted following this result check.


## Continued evaluation after additional credit

The user authorized continuation. See [the resumable campaign](CAMPAIGN.md) for active execution, budget, checkpoints and the status/resume commands. The earlier pilot commands above are historical; use campaign.py for further continuation. The one-time upload of original Drive weights needs the local computer awake until staging finishes.
