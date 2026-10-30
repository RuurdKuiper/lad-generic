# Publishing the BYOD models and demos

For the original structural-correction LAD demo, see
[LAD with BG + TG Gumbel decoding](lad_space/README.md). Its app is maintained in
`huggingface/lad_space`; prepare an update with
`python huggingface/publish_lad_viterbi.py`. Add `--execute --expected-revision
<reviewed-space-commit>` to update only `Ruurd/lad`, preserving model weights
and existing Space settings. Its pinned expanded BYOD-Llama scorers are configured
in `lad_space/ngram_assets.json`; the original local Llama bigram checkpoint is
also bundled for legacy decoding. Verify a deployment with
`python scripts/verify_lad_trigram.py --smoke`. LAD defaults to Sampling at temperature 0.7,
top-k 16 and independent bigram weight 1, with its noising controls intact.
LAD keeps every answer position editable, even without re-noising; its
correction loop is separate from BYOD's permanently retained tokens.

This directory packages the selected checkpoints as Hugging Face adapter
repositories and creates one fixed-model ZeroGPU Space per model. Gemma, Qwen,
and Ministral use their original `best` checkpoints; Llama uses the final
checkpoint of its uninterrupted 50k-update run. Inference is BF16/unquantized;
no 4-bit fallback is configured.

## Repositories

| Model repository | Space |
|---|---|
| `Ruurd/BYOD-Gemma-2-9B` | `Ruurd/byod-gemma-2-9b` |
| `Ruurd/BYOD-Llama-3.1-8B` | `Ruurd/byod-llama-3.1-8b` |
| `Ruurd/BYOD-Qwen2.5-7B` | `Ruurd/byod-qwen2.5-7b` |
| `Ruurd/BYOD-Ministral-8B` | `Ruurd/byod-ministral-8b` |

The model repositories contain only the trained adapters, tokenizer metadata,
normalization state, and resolved training configuration. Users must accept
the upstream terms for gated base models.

## Publish

Authenticate without putting a token in the repository:

```bash
hf auth login
```

Preview and validate all source files:

```bash
python huggingface/publish_byod.py
```

Create/update the public model repositories and Spaces:

```bash
python huggingface/publish_byod.py --execute
```

To update only the demo code without re-uploading the model repositories:

```bash
python huggingface/publish_byod.py --spaces-only --execute
```

To replace only the Llama adapter without redeploying the Space:

```bash
python huggingface/publish_byod.py --namespace Dovelove --anonymous-review \
  --models-only --only BYOD-Llama-3.1-8B --execute
```

The four Spaces request the Hugging Face `zero-a10g` hardware tier (ZeroGPU).
Hugging Face currently permits two ZeroGPU Spaces for a free personal account
and up to ten for PRO. Existing ZeroGPU Spaces count toward the limit.

Gemma, Llama, and Ministral base weights may require authentication. Create a
separate read-only Hugging Face token and add it to each Space as the
`HF_TOKEN` secret in **Settings → Variables and secrets**. Do not put it in a
file, notebook, or Git commit.

### BYOD Viterbi decoding controls

Ruurd's Gemma and native LLaDA Spaces include a default-OFF **Adaptive Parallel
Decoding (APD)** checkbox. It replaces commitment/remasking decisions after
the existing token-selection method, leaving sampling and Viterbi scores intact.
The block-local cosine threshold uses a 15% warmup and decreases from 0.90 to
0.50. Confidence is the selected token's full-vocabulary diffusion probability,
including existing ending adjustments, rather than normalized top-k confidence
or a Viterbi path margin. A highest-confidence fallback commits at least one
pending token when necessary; the final block step commits all remaining rows.
If the decoder selects MASK itself, a validity fallback uses the same forward's
best non-mask prediction for that row. Committed rows stay fixed and completed
blocks exit without using the remaining planned steps. EOS/EOT retention delay
and the whole-answer Early stopping control remain supported.

APD uses the DLM commitment probability even with Random or AR-guided retention
selected; those retention policies and retained-token revision are bypassed while
APD is ON. In particular, optional AR confidence forwards are not run under APD.
No token budgets, position factors, grinding detection, extra model passes, or
weight changes are added. The schedule is inspired by
[CAI-dLLM](https://arxiv.org/abs/2608.22646), with the fixed endpoint requested
for this experiment. OFF preserves the prior generation behavior.

Deploy these two Spaces using `python huggingface/enable_repetition_penalty.py
--feature apd`, inspect its prepared manifest, then add `--execute`. The small
ON/OFF check is `scripts/evaluate_apd_spaces.py`; results and saved outputs are
in `artifacts/bigram/apd_rollout`. When decoding measurements are requested,
`Inference metrics` reports denoising forward count and in-function elapsed
milliseconds, separate from allocation/queue time and existing selector metrics.

The Ruurd Gemma and native LLaDA Spaces also offer **PMI Viterbi + Repetition
Penalty**, with a gamma slider defaulting to 1.0. Its edge score is
`0.5 * temperature * PMI(a,b) - gamma * C(a,b)`, where C sums earlier expected
pair occurrences within the current block/iteration from full-vocabulary
diffusion probabilities. EOS/EOT pairs are excluded. Retained positions remain
fixed; there are no additional model forwards. Gamma zero reproduces the
original PMI option, which remains the default. The existing Ruurd evaluation
controls remain visible via `show_bigram_evaluation_controls` in the Space config.

Prepare these two existing Spaces with
`python huggingface/enable_repetition_penalty.py`, inspect its prepared manifest,
then run the same command with `--execute` to upload code only. Existing
dependencies, checkpoints and hardware settings are preserved. Live comparisons
are recorded by `scripts/verify_repetition_spaces.py`.

The Ruurd and Dovelove BYOD Spaces use the same `temperature` and `top_k` inputs for
sampling and Viterbi. The hosted bigram weight is fixed at 0.5; the separate
`bigram_weight` and `bigram_top_k` API inputs have been removed.

For Viterbi, temperature scales diffusion emissions relative to bigrams:
`log_softmax(logits / temperature) + 0.5 * bigram_score`. Implementation uses
the equivalent, stable objective `log_softmax(logits) + 0.5 * temperature *
bigram_score`. Temperature 1 preserves the former weight-0.5 path selection;
0 ignores bigram scores and uses greedy predictions on the current logits.
Existing ending penalties and delayed retention still apply. Viterbi remains
deterministic. Its diffusion retention confidence uses full-vocabulary probabilities
from the selection logits (including any ending-delay adjustment); path margins use the stable objective's
score gaps. No extra model evaluations are required.

Top-k limits the candidate count for either strategy. Top-k 1 leaves only
the model argmax candidate at editable positions, so bigrams cannot change
the selected tokens. Retained tokens remain fixed constraints.

Hosted evaluation scripts now submit these shared controls. Historical result
folders retain their original manifests and source revisions; they describe
the earlier independent controls. `evaluate_decoding_quality.py` records the
control scheme and refuses to resume results with a different revision or
configuration. Its paper profile (temperature 0, top-k 1) now removes bigram
influence; use positive temperature and top-k greater than 1 to compare
Viterbi's transition methods.

Each interface defaults to PMI bigrams with diffusion-probability
retention, minimum bigram count 1, and clipping bound 2. Edit
`BIGRAM_SCORING_METHOD`, `BIGRAM_REMASKING_CONFIDENCE`, `PMI_MIN_COUNT`, and
`PMI_CLIP` near the top of `huggingface/byod_space/app.py` to change these
settings. Their interface controls are hidden; programmatic evaluation can
still override them. Ending-delay strength is fixed at the editable
`BIGRAM_ENDING_DELAY_STRENGTH = 10.0` default. Its control, checkpoint path,
seed, and decoding measurements are hidden from the interface; the API retains
evaluation overrides.

The shared controls default to temperature 2 and top-k 16, matching the
preferred configuration in the recent comparisons. Ending
suppression affects both path selection and diffusion retention probabilities.
The retention probabilities are normalized over the full vocabulary after
the fading ending penalty. An audit found that changing them to probabilities
before that penalty worsened the tested 16-step Amsterdam answers; the prior
calculation is retained.

The publisher includes a separate full-corpus scorer for each tokenizer:
`artifacts/bigram/gemma.pt`, `llama.pt`, `ministral.pt`, and `qwen.pt`.
Build each from `data/lad-training-1m-256-long` with `--text-column output
--response-eos`, its exact backbone tokenizer, and `--vocab-size` matching the
backbone output vocabulary. Qwen requires 152,064 output IDs, including padded
IDs beyond its tokenizer vocabulary. Missing per-model checkpoints stop
publication rather than reusing another model's statistics. Other namespaces
retain their existing interface without automatically bundling these scorers.

### Native LLaDA-Instruct comparison Space

`huggingface/publish_llada.py` prepares the same interface for the official
`GSAI-ML/LLaDA-8B-Instruct` model with its native bidirectional forward pass,
chat template, and mask ID 126336. It pins model/tokenizer revision
`08b83a6feb34df1a6011b80c3c00c7563e963b07` and Transformers 4.57.6. The native
loader can defer inference preflight until a GPU allocation is available.

Build the separate scorer from the full existing training split:

```bash
.venv/bin/python scripts/build_bigram.py \
  --tokenizer GSAI-ML/LLaDA-8B-Instruct --vocab-size 126464 \
  --saved-dataset data/lad-training-1m-256-long --text-column output \
  --response-eos --output artifacts/bigram/llada.pt
```

The output vocabulary includes 115 IDs beyond the tokenizer's 126,349 entries;
the scorer covers all 126,464 model outputs. The scorer uses response text
retokenized with LLaDA, preserving document boundaries and the training split.
Existing Gemma statistics cannot be reused.

Prepare the bundle with `python huggingface/publish_llada.py`; add `--execute`
to create the private `Ruurd/llada-8b-instruct` Space and request ZeroGPU.
Publication refuses to overwrite an existing repository. Public activation
of the corpus-derived scorer requires explicit user approval. The available
strategies are confidence-guided, random, and PMI Viterbi; autoregressive
adapter confidence applies to BYOD models. This publisher updates no existing
BYOD Spaces.

### LLaDA: optional sequence sampling and candidate-set repetition counts

On `Ruurd/llada-8b-instruct`, **Sample bigram-guided sequences** uses exact
forward filtering/backward sampling from `exp(total path score)` instead of the
maximum path. It retains diffusion, PMI, boundary and repetition scores without
perturbing logits. **Count every candidate bigram occurrence** changes the
repetition strategy's counts from probability products to candidate-set
membership: one count per earlier adjacent candidate-list occurrence, regardless
of probability. Duplicate fixed-token columns count once, and EOS/EOT pairs are
excluded. Both checkboxes default OFF and can be combined independently with APD;
ordinary decoding ignores them. Counts remain local to each iteration/block.
Temperature and the existing `gamma*C` log penalty are unchanged. No additional
model calls, training, or checkpoints are required.

Prepare the LLaDA-only code bundle with
`python huggingface/enable_llada_sequence_sampling.py`, then deploy the captured
parent revision with the same command and `--execute`. Run
`python scripts/verify_llada_sequence_sampling.py --baseline` before deployment,
and omit `--baseline` afterward to check the live output and seed regressions.
Reports and examples are in `artifacts/bigram/llada_sequence_sampling/`.

### LLaDA: independent temperature and PMI weight

The LLaDA Space supersedes its earlier temperature-dependent PMI coefficient with
`S = sum(log p) + bigram_weight*sum(PMI) - gamma*sum(C)`. The visible **Bigram
weight** slider ranges 0–5 and defaults to 1. Maximum-path Viterbi ignores
temperature. Sequence sampling uses `P(y) proportional to exp(S/T)`; T=0 selects
the maximum path, and positive T is floored at 1e-6 for stability. This temperature
controls whole-sequence entropy without changing coefficient ratios. Confidence,
APD, and expected counts still use raw full-vocabulary diffusion probabilities.
The default T is now 1; weight=1, T=1 preserves the former default score and
sampling distribution at fixed weight=0.5, T=2. Other hosted models keep their
existing behavior. Standard independent diffusion uses its existing temperature.

Prepare/deploy with `python huggingface/enable_llada_temperature.py` and then
`--execute`. Verify with `python scripts/verify_llada_temperature.py`. Artifacts
are in `artifacts/bigram/llada_temperature/`; earlier experiment reports retain
their historical formulas and settings.

### LLaDA: optional repetition-risk penalty

With **PMI Viterbi + Repetition Penalty**, the **Repetition-risk penalty** checkbox
(default OFF) uses joint bigram marginals from forward/backward sum-product over
the unpenalized diffusion+PMI candidate lattice. With q_s(a,b) as those marginals,
it estimates `r_t = 1 - product_(s<t)(1-q_s)` and subtracts
`gamma*log((1-r+9r)/(1-r))` from each transition score. At T=1, gamma=1,
risk 0.1 gives multiplier 0.5, and risk 0.5 gives multiplier 0.1. This is an
approximation because occurrences are dependent, not an exact conditional
repetition probability. The baseline marginals are computed once, before the
penalty, including fixed rows and PMI boundary scores. Sampled decoding uses its
sequence temperature; deterministic decoding and T=0 use a T=1 soft surrogate.
The final corrected sequence score still follows the existing temperature rule.

Risk takes precedence over **Count every candidate bigram occurrence** if both
are ON. EOS/EOT pairs are exempt, state resets per block/iteration, and a survival
floor of 1e-7 keeps the correction finite near certainty. Gamma=0 is exactly the
unpenalized selected decoding mode. The new calculation costs extra decoder
passes, with no additional model forwards or training. OFF preserves the original
expected/candidate-count modes.

Prepare and deploy using `python huggingface/enable_llada_repetition_risk.py`
and then `--execute`; verify with `python scripts/verify_llada_repetition_risk.py`.
See `artifacts/bigram/llada_repetition_risk/` for deployment and example records.

### LLaDA: fading repetition strength over early iterations

The LLaDA UI enables **Fade repetition penalty over early iterations** by default.
It applies to expected-count, candidate-count and risk penalties only. Turn it OFF
for constant gamma. API calls retain constant strength unless
`decay_repetition_penalty=True` is supplied explicitly.

For zero-based block iteration t, L=6, c=(L-1)/2, define
`g(t)=1/(1+exp(1.6*(t-c)))`. The factor is
`f(t)=(g(t)-g(L-1))/(g(0)-g(L-1))` until t=L-1, then exactly zero. The actual
strength is `gamma*f(t)`. A one-step block gets full strength. The window uses
absolute iterations, does not stretch with the NFE budget, and resets per block.
Edit `REPETITION_FADE_ITERATIONS` in app.py to change it. Other decoding scores,
retention confidence and ending-delay behavior are unchanged. No extra model
forwards are used; zero strength bypasses repetition-risk/count calculations.

Prepare/deploy with `python huggingface/enable_llada_repetition_decay.py` and then
`--execute`; verify with `python scripts/verify_llada_repetition_decay.py`. Outputs
and deployment records live in `artifacts/bigram/llada_repetition_decay/`.

### LLaDA: APD aggressiveness

The **APD aggressiveness** slider (0–1, default 0) becomes interactive while APD is
ON. It multiplies the original warmup/cosine threshold by `(1-a)`: 0 preserves
0.90→0.50; 0.5 gives 0.45→0.25; 0.9 gives 0.09→0.05; and 1 gives zero threshold.
Higher values permit committing less-confident selected tokens, potentially
reducing denoising passes at a quality cost. At 1, finite model predictions resolve
a block in one pass. All progress/ending/fixed-token guards remain in place.
The selected token's full-vocabulary probability still determines confidence.

The API option is `apd_aggressiveness`, default 0; APD OFF ignores it. It composes
with every existing decoding strategy, sequence sampling, repetition risk and the
unchanged repetition fade. The control changes commitment only, with no extra
model forwards. Other Spaces were not deployed.

Prepare/deploy via `python huggingface/enable_llada_apd_aggressiveness.py` and then
`--execute`; run `python scripts/verify_llada_apd_aggressiveness.py` to verify.
See `artifacts/bigram/llada_apd_aggressiveness/` for outputs and deployment records.

### LLaDA: minimum commitment quota with APD

APD now commits at least `ceil(block_length / allocated_block_iterations)` tokens
per pass, capped by the number still masked. For a 64-token block and 16 steps,
that means at least 4 per step. Threshold-qualified rows can exceed the quota;
any deficit is filled by selected-token diffusion confidence. This is a fixed
per-step minimum even after earlier above-quota commits, not a reduced cumulative
target. Nondivisible ratios round up, and each unequal block uses its own budget.

Retained rows remain fixed. With ending delay, quota filling exhausts ordinary
rows before selecting EOS/EOT. Nonfinite scores rank last with a deterministic
fallback. The scheduled final pass resolves all remaining rows, which cannot exceed the
quota if earlier steps met their minimums. Earlier threshold-based completion can
commit a larger group together. APD OFF is unchanged. At aggressiveness
0 the old threshold curve is preserved, but the new floor intentionally changes
APD commitments; previous full-behavior equivalence statements are historical.
No extra model forwards, scoring changes, or UI controls are introduced.

Prepare/deploy with `python huggingface/enable_llada_apd_quota.py` and then
`--execute`; verify with `python scripts/verify_llada_apd_quota.py`. Results are
in `artifacts/bigram/llada_apd_quota/`. Other Spaces were not updated.

### LLaDA: optional expanded bigram and trigram guidance

**N-gram guidance** offers **Original bigram** (default), **Expanded bigram**, and
**Expanded bigram + trigram**. It applies to the existing bigram decoding
strategies, including sequence sampling, repetition modes/fading and APD/quota.
Independent diffusion ignores it. The original checkpoint remains available.

The expanded corpus adds 800M exact LLaDA-tokenizer tokens: 720M FineWeb-Edu,
40M Python-Edu (via Avelina's text-resolved mirror), and 40M FineMath-4+, plus the
full original response training split. These are 90/5/5 proportions of the added
tokens. Both scorers use the same text. Counts never cross document boundaries;
complete raw documents receive EOS, and truncated original responses retain the
old EOS policy. Exact duplicate raw texts are skipped within each source. The
final raw document can be truncated to its exact source token budget.

The optional trigram correction is
`delta(a,b,c) = log P(c|a,b) - log P(c|b)`, with alpha=50 bigram backoff,
minimum count 2 and clipping ±2. The overall raw score adds
`bigram_weight * TRIGRAM_RELATIVE_WEIGHT * sum(delta)`, where the relative weight
is 0.5. These settings are editable in app.py. Unseen/rare triples back off to
zero correction. Full prefix totals include singleton triples even though
checkpoint storage retains only triples observed at least twice.

Exact second-order Viterbi, sequence sampling, path margins and joint pair
marginals use state pairs and vectorized candidate dimensions. Risk estimation
therefore includes trigram guidance. Trigrams stay within each block; existing
bigram boundary scores remain. Length 1–2 blocks have no trigram contribution.
Bigram weight 0 disables both n-gram corrections. At K=16, B=64 the extra FP32
potential table is about 1 MiB. Large candidate pools incur K^3 work; sparse
lookup temporaries are chunked to limit memory. No extra model forwards are used.

For training, install the optional dependency with `pip install -e '.[ngrams]'`
and run `python scripts/build_mixed_ngrams.py`. Pinned source revisions/token
budgets live in that script. Per-source count checkpoints permit resuming after
a completed source. A worker may count selected sources using `--sources ...
--count-only`; the normal invocation merges all sources. The script expects the
project's cached pinned LLaDA tokenizer and original saved training dataset.

Before deployment run `python scripts/compact_llada_trigram.py`. This retains
all triples with count >=2 and their required context totals, preserving exact
corrections at the default threshold of two. Bigram minimum count stays one.
Compaction verifies corrections against the full checkpoint.
Then run `python scripts/publish_llada_ngram_assets.py` to publish scorer files
in a model repository; the Space downloads its pinned revision at startup,
avoiding the Space's 1 GB file limit without dropping count-two triples.

Prepare and deploy with `python huggingface/enable_llada_trigram.py` then
`--execute`. The rollout guards the Space revision and checkpoint SHA256 hashes,
preserves the old scorer and pinned model configuration, and uploads no corpus
text. Use `python scripts/evaluate_llada_trigram_speed.py` for matched GPU
selector/end-to-end timing and output records, or
`python scripts/benchmark_trigram_dp.py` for a model-free DP microbenchmark.
See `artifacts/bigram/llada_expanded_ngrams/` for provenance and results.

For deterministic trigram decoding, small CUDA lattices (up to 256 positions
and K<=16) use an exact CPU MAP recurrence after one packed score transfer.
Normalization stays on the original device; the recurrence preserves float32
operation order and first-index tie breaking. This avoids hundreds of tiny GPU
operations per iteration. Larger lattices and positive-temperature sequence
sampling retain the device implementation. Prefix/backoff count lookups use
K^2 tables while triple counts still require K^3 queries. No scoring parameters
or model forward counts change. Matched output and hosted timing checks are in
`artifacts/bigram/llada_ngram_speed/`; run
`scripts/evaluate_llada_ngram_speedup.py` for its recorded deployment stages.

LLaDA uses Gumbel Viterbi as its standard BG/BG+TG temperature strategy, with
default Temperature 0.7. Each iteration adds `Temperature * Gumbel(0,1)` to
editable candidate unary log-scores and uses the same fast MAP decoder. BG/TG
transitions, top-k support, fixed positions and diffusion retention probabilities
are unchanged. Temperature 0 reproduces deterministic decoding without consuming
additional RNG state. This is low-dimensional perturb-and-MAP, an approximate
structured sampler; temperature .7 is a noise scale, not a guarantee of the
exact sampler's `.7` distribution. The matched 282-case extension is recorded
under `artifacts/bigram/llada_ngram_settings_full/randomized/`. The simplified
LLaDA interface exposes only **Confidence-guided** and **BG + TG Viterbi
(Gumbel)**. The latter always selects the expanded bigram/trigram checkpoints
and uses Temperature; 0 requests deterministic decoding. APD, early stopping,
EOS retention and bigram weight remain adjustable. Ending-delay strength is
fixed to the editable app.py constant (10).

Set `SHOW_LEGACY_DECODING_CONTROLS = True` in app.py to restore the older
interface, including exact sampling, repetition penalties, other corpora and
evaluation controls. Their implementation and programmatic arguments remain in
the code; no training/scoring modules were removed. In legacy mode the API
override `randomized_viterbi=False` supports historical deterministic evaluations;
explicit exact sampling takes precedence over default randomization. The simple
BG+TG method always uses Gumbel Viterbi, ignoring incompatible legacy overrides.
Rebuild the eight-arm report, tables and figures without inference using
`python scripts/integrate_llada_randomized_report.py`. Seven-arm inputs are
archived as `pre_randomized_*`, and the previous report is
`PRE_RANDOMIZED_REPORT.md`.

The same simplified interface supports the eight BYOD demos (Gemma, Llama,
Qwen and Ministral on Ruurd and Dovelove). Their `space_model.json` sets
`trigram_enabled=true`; this is a scorer capability and does not change the
BYOD model backend to LLaDA. Bigram weight and Temperature are independent,
with default weight 1 and Gumbel temperature 0.3. All guided demos use matching
tokenizer-specific counts, and retain APD, early stopping and EOS retention.

`scripts/build_byod_trigrams.py --model {gemma,llama,qwen,ministral}` builds
trigrams from all 980,000 original BYOD response-training documents. It respects
the original EOS/truncation policy, reconstructs and checks bigram/unigram
counts exactly against the existing checkpoint, and retains count>=2 triples
with full context totals. These are the original response-corpus scorers,
not LLaDA's expanded English/code/math corpus. Reports and fingerprints live in
`artifacts/bigram/byod_trigrams/`.

Prepare the guarded rollout using
`python huggingface/rollout_byod_simple_interface.py`, then `--execute` to upload
the reviewed bundles. It preserves each Space's model selection, links and
account-specific configuration, and verifies the two writing credentials.
`scripts/verify_byod_simple_rollout.py --smoke` checks the public interface and
both decoding methods. Deployment and verification records are in
`artifacts/bigram/byod_simple_rollout/`.

To expand the BYOD scorers, run
`python scripts/build_byod_expanded_ngrams.py --model {gemma,llama,qwen,ministral}`.
This reuses the verified original counts and adds 800M tokens per tokenizer:
720M FineWeb-Edu, 40M Python-Edu and 40M FineMath, using pinned source revisions
and the shared cached corpus. Statistics never cross document boundaries.
It exports all bigrams and count>=2 trigrams; compact prefix totals include
singleton contributions. Completed, validated builds remove only their own
reproducible count intermediates to bound disk usage.

`python scripts/publish_byod_expanded_ngrams.py --model MODEL` publishes the
expanded pair to separate same-account model repositories, verifies their
hashes, and atomically updates each Space's pinned asset revision. Superseded
small expanded files are removed from the Space; the original `bigram.pt`
remains available for legacy decoding. `byod_ngram_assets.json` preserves the
validated pins for normal future publishes. It changes no model weights or
interface settings. `python scripts/verify_byod_expanded_rollout.py --smoke`
checks pinned assets, preserved settings, interface and both live methods.
Expanded training provenance is under `artifacts/bigram/byod_expanded_ngrams/`;
deployment and verification records are under
`artifacts/bigram/byod_expanded_rollout/`.

The [decoding artifact index](../artifacts/bigram/README.md) links the current
production defaults, complete LLaDA study, timing analysis and scorer provenance.
Historical reports retain the settings used at the time of each experiment.

### LLaDA2.2-mini companion Space

The separate [LLaDA2.2 app](llada22_space/README.md) preserves the live diffusion
layout while using the official edit-aware decoder and a new tokenizer-matched
BG + TG scorer pair. Research and native insertion/deletion semantics are
recorded in `artifacts/llada22/RESEARCH.md`.

Build all response + 800M expanded-token statistics with
`python scripts/build_llada22_ngrams.py`. Prepare the two reviewable repository
bundles using `python huggingface/publish_llada22.py`. Publication uses
`--execute`: private publication requires a separate read-only `HF_READ_TOKEN`
for the new Space's private scorer downloads; `--execute --public` publishes
both new repositories publicly. It refuses to overwrite existing repositories.
The original Space is untouched.

Use the isolated Space requirements (Transformers 5.2.0); do not upgrade the
main project's Transformers 4 environment. `python scripts/verify_llada22.py
--tiny` validates the real model architecture with synthetic tiny weights
without downloading the 16B checkpoint. `--space Ruurd/llada2.2-mini` checks
both hosted decoding methods. Model-free integration tests can extract the
pinned native decoder via `LLADA22_NATIVE_SOURCE=/path/to/modeling_llada2_moe.py
pytest tests/test_llada22_streaming.py`.

Published companion: [Ruurd/llada2.2-mini](https://huggingface.co/spaces/Ruurd/llada2.2-mini).
The [matching scorer repository](https://huggingface.co/Ruurd/llada2.2-mini-ngram-guidance)
contains counts trained on 875,507,295 exact model-tokenizer tokens. Deployment
pins and full-model native/guided GPU verification records are in
`artifacts/llada22/`; the original LLaDA Space was preserved.
