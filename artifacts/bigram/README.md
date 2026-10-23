# Decoding studies and scorer provenance

This directory keeps experiment outputs, judgments, reports, scorer provenance,
and deployment verification. Model checkpoints, downloaded corpora, count caches,
deployment bundles and generated source backups are excluded from Git. They stay
available locally; the production scorers are also pinned on Hugging Face.

## Current BYOD deployment

- [Expanded scorer rollout](byod_expanded_rollout/REPORT.md): all eight Gemma,
  Llama, Qwen and Ministral Spaces on Ruurd and Dovelove.
- [Current temperature default](byod_temperature_03/REPORT.md): **0.3** for BYOD.
- [Per-tokenizer training reports](byod_expanded_ngrams/): the complete original
  response dataset plus 800M added tokens, with pinned sources and asset hashes.
- [Pinned production assets](../../huggingface/byod_ngram_assets.json): used by
  ordinary future Space publishes.

The simplified interface offers Confidence-guided and BG + TG Viterbi (Gumbel),
with APD, early stopping, EOS retention and adjustable bigram weight. Native
LLaDA retains its separate default temperature of 0.7. Historical experiment
settings are recorded as actually run; changing production defaults does not
change those reports.

## Studies

The original structural-correction LAD Space now also offers the shared guided
decoder: [LAD BG + TG rollout](lad_trigram_rollout/REPORT.md). Its own noising,
correction and multi-turn controls remain available.

- [Full LLaDA n-gram study](llada_ngram_settings_full/REPORT.md): eight matched
  configurations, including deterministic, exact sampled and Gumbel variants.
- [Math error analysis](llada_ngram_settings_full/HIGH_NFE_MATH_ANALYSIS.md).
- [Timing analysis](llada_ngram_settings_full/TIMING_NOTES.md).
- [Decoder speed comparison](llada_ngram_speed/REPORT.md).
- [Initial smaller study](llada_ngram_settings/REPORT.md).
- [Expanded LLaDA scorer training](llada_expanded_ngrams/REPORT.md).

Raw JSONL outputs, grades, examples and figures accompany each study. Files
prefixed `pre_` and `PRE_` preserve earlier analysis stages used by the report
regenerators; `combined_*` and unprefixed score/summary files intentionally serve
as compatible entry points. Git deduplicates files with identical contents.

## Earlier deployment records

The `llada_sequence_sampling`, `llada_temperature`, `llada_repetition_risk`,
`llada_repetition_decay`, `llada_apd_aggressiveness` and `llada_apd_quota` reports
record the individual feature checks. `byod_simple_rollout` and `byod_trigrams`
record the initial response-corpus rollout before the expanded scorers.

See [the deployment guide](../../huggingface/README.md) for build, publish,
verification and report-regeneration commands. Scorer training needs the pinned
tokenizer snapshots and original prepared dataset; offline expansion also needs
the shared Hugging Face corpus cache. Install count aggregation dependencies
with `pip install -e '.[ngrams]'`.

## Current scoring

The guided method maximizes diffusion unary log-probabilities plus `weight * PMI`
bigram scores and `0.5 * weight` trigram corrections. Positive temperature adds
`temperature * Gumbel(0,1)` to editable unary scores before fast Viterbi decoding;
temperature zero selects the deterministic best path. This perturb-and-MAP method
is an approximate structured sampler, not exact sequence sampling. Bigram weight
is independent of temperature and defaults to one.

Retained tokens are singleton path constraints. Retention uses full-vocabulary
diffusion probabilities after the ending-delay adjustment, with no additional
model forward passes. PMI uses successor-token marginals, minimum count one and
clipping +/-2; trigram storage and runtime minimum count are two.

## Build and verify

Binary checkpoints, tokenizer downloads, and deployment bundles are ignored by
Git. Small provenance files, saved outputs, reports, and benchmarks are retained.
Rebuild a checkpoint from the existing local dataset, for example:

```sh
.venv/bin/python scripts/build_bigram.py \
  --tokenizer google/gemma-2-9b-it \
  --saved-dataset data/lad-training-1m-256-long \
  --text-column output --response-eos --output artifacts/bigram/gemma.pt
.venv/bin/python -m pytest -q
```

Use the corresponding tokenizer for each model and pass `--vocab-size` when the
model output vocabulary is padded beyond the tokenizer vocabulary (Qwen: 152064;
LLaDA: 126464). The builder preserves document boundaries and appends EOS only
to complete responses. Fingerprints reject mismatched tokenizers at load time.
Checkpoint version 2 adds successor counts; version 1 remains loadable by
reconstructing those counts from its sparse pairs.

See [publishing instructions](../../huggingface/README.md) for per-model builds
and deployment commands. Publishing is separate from running local checks.

## Earlier experiments and deployment records

- [Gemma and LLaDA perplexity comparison](perplexity_models/REPORT.md): 10 questions,
  128-token answers, NFE 8/16/32/64/128, Phi-4 reference perplexity, Distinct-1,
  and links to representative good/typical/bad answers for every configuration.
  This compares complete settings bundles, rather than isolating Viterbi alone.
- [Initial 64-token perplexity experiment](perplexity_quick/REPORT.md): stopped
  after 21 complete questions at the user's request.
- [Original five-method quality comparison](quality_experiment/REPORT.md) and
  [coding follow-up](coding_paper_settings/REPORT.md): historical experiments
  before temperature and top-k controlled Viterbi. Keep their original settings
  and source revisions when interpreting the results.
- [Shared-control audit](viterbi_audit/REPORT.md): includes an unsuccessful
  retention-confidence experiment that was reverted; its saved patch is historical.
- [Ruurd BYOD rollout](byod_rollout/README.md),
  [Dovelove BYOD rollout](dovelove_rollout/README.md), and
  [native LLaDA deployment](llada_space/RESULTS.md).

Technical and historical notes:
[PMI](PMI.md), [ending controls](ENDINGS.md),
[path-margin retention](VITERBI_CONFIDENCE.md), and
[initial Gemma implementation](INITIAL_GEMMA.md).

Reference perplexity can reward repetitive text and does not measure factuality.
Distinct-1 is the fraction of unique token IDs in each complete generated answer,
then averaged across questions; compare changes within a tokenizer. These small,
single-seed experiments are exploratory.
