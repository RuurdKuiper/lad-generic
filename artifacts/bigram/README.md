# BYOD bigram Viterbi decoding

Inference uses a sparse count scorer and exact Viterbi decoding over top-k
candidates, with no additional model forward passes. The implementation supports
BYOD Gemma, Llama, Ministral, Qwen, and native LLaDA-Instruct. Each model has a
separate scorer trained on all 980,000 training responses using its own tokenizer;
validation and test responses are held out.

## Current defaults

The shared Space interface uses PMI bigrams, diffusion-probability retention
confidence, temperature 2, top-k/candidates 16, fixed bigram weight 0.5, PMI
minimum count 1, and clipping ±2. New-token limit, block length, and denoising
steps default to 64. EOS/EOT retention delay and early stopping default on;
ending prediction delay has strength 10 and fades to 1 at the final block step.

The objective is equivalent to `sum(log_softmax(logits / T)) + 0.5 * sum(PMI)`
for positive temperature. The implementation uses the numerically stable form
`sum(log_softmax(logits)) + 0.5 * T * sum(PMI)`. Temperature 0 ignores bigrams;
top-k 1 leaves only the diffusion argmax candidate. Viterbi is deterministic.
Retention confidence uses the full-vocabulary diffusion distribution after the
ending-delay adjustment, without temperature scaling or top-k renormalization.

Already retained positions remain in the Viterbi path as singleton constraints.
Known tokens immediately outside the current block provide boundary context.
PMI uses smoothed successor-token marginals; unseen or below-threshold pairs
receive zero correction. Conditional bigrams and Viterbi path-margin retention
remain available through the Python/API configuration.

Edit expert defaults near the top of `huggingface/byod_space/app.py`. The shared
interface hides the scorer path, scoring method, retention method, PMI safeguards,
ending-delay strength, seed, and measurements. API overrides remain available.
Deployment records below identify the exact hosted revisions: earlier Ruurd
revisions still expose some controls hidden by the latest Dovelove interface.

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

## Experiments and deployment records

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
