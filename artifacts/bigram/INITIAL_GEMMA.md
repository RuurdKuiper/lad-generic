> Historical implementation record. This describes the initial Gemma-only
> conditional-bigram deployment, before shared temperature/top-k controls, PMI
> defaults, and the multi-model rollout. See [README.md](README.md) for current behavior.

# Bigram Viterbi for Gemma

Enabled only for `Ruurd/byod-gemma-2-9b`. The selector is inference-only:
`src/diffusion_lm/bigram.py` contains sparse scoring and the Viterbi DP;
`denoise_stream` has an opt-in selector argument. Training code, model weights,
and adapters are unchanged.

Defaults: Bigram Viterbi, 16 candidates, lambda 0.5 (experimental). The Space
retains its existing 1–512 block-length range, including short final blocks.
The new strategy uses full-vocabulary log-softmax of the adjusted diffusion
logits and deterministic maximum-score selection. Temperature and the existing
sampling top-k remain specific to the other strategies. Remasking still uses
the existing confidence-guided schedule, with confidence equal to the selected
token's full-vocabulary probability. There are no extra model forwards.

All positions in the current contiguous block participate in the DP. Frozen
rows have a single legal ID; they are never compressed out. The previous prompt
or completed-block token supplies left context. A known right neighbor also
supplies context; future masks do not. Fixed-row emissions are path-independent
and omitted. Boundary transitions are added once. Candidate-only calls accept
relative logits, which cannot recover full-vocabulary probabilities; constants
per position do not change the maximizing path.

Sparse pair counts use sorted packed int64 keys. Probability is
`(pair_count + alpha * unigram(next)) / (row_count + alpha)`, with alpha 10 and
unigram additive smoothing beta 0.1. Unseen rows back off to unigrams; unseen
pairs and specials have finite scores. No vocabulary-squared tensor is created.
The checkpoint records a SHA256 hash of the exact token-to-ID mapping; loading
with a mismatched tokenizer fails explicitly. Checkpoints load once per path
and move to the allocated inference device. Missing checkpoints produce a clear
error, with no random fallback.

## Build

The shipped scorer uses all 980,000 responses in the cached BYOD training split,
retokenized with `google/gemma-2-9b-it` (snapshot
`11c9b309abf73637e4b6f9a3fa1e92e615547819`). Stored Llama IDs are ignored.
Validation and test remain held out. Response texts are independent documents;
there are no cross-example transitions. The `--response-eos` option matches
BYOD targets by appending EOS to completed responses, while preserving
`answer_truncated` rows without an artificial ending. Other unseen special-token
transitions use smoothing.
See `gemma.json` for provenance and counts. Binary checkpoints are rebuildable
artifacts ignored by Git; the deployed Space contains `bigram.pt`.

```sh
.venv/bin/python scripts/build_bigram.py \
  --tokenizer google/gemma-2-9b-it \
  --saved-dataset data/lad-training-1m-256-long \
  --text-column output --response-eos --output artifacts/bigram/gemma.pt
```

For offline builds, pass the local tokenizer snapshot directory and
`--local-files-only`. The builder also supports tokenized/text JSONL, local Arrow,
and streamed HF text datasets; tokenized inputs must already use the exact
specified tokenizer. `--max-documents` optionally caps the count; by default
all training rows are used. `--alpha` and `--beta` configure smoothing.

Publish only the intended Space using:

```sh
.venv/bin/python huggingface/publish_byod.py \
  --namespace Ruurd --only BYOD-Gemma-2-9B --spaces-only --execute
```

The bundle enables the UI and includes the checkpoint only for this exact
namespace/Space combination. Other Space configurations keep their existing
strategy defaults. `BIGRAM_MODEL_PATH` or the UI checkpoint field can override
the deployed checkpoint path.

## Verification and evaluation

```sh
.venv/bin/python -m pytest tests/test_bigram.py tests/test_inference.py tests/test_publish_byod.py -q
.venv/bin/python scripts/benchmark_bigram.py \
  --checkpoint artifacts/bigram/gemma.pt --output artifacts/bigram/benchmark_cpu.json
.venv/bin/python scripts/evaluate_bigram.py \
  --checkpoint artifacts/bigram/gemma.pt --dataset data/lad-training-1m-256-long \
  --tokenizer /path/to/local/gemma/tokenizer --output artifacts/bigram/heldout.json
.venv/bin/python scripts/evaluate_bigram_space.py --output artifacts/bigram/space_evaluation.json
```

Tests cover exhaustive small-path optimality, a greedy failure, single counting
of emissions, lambda zero, sparse backoff and serialization, missing/mismatched
checkpoints, fixed and noncontiguous editable positions, both boundaries,
lengths 1/8/32/128/256, unequal final blocks, and one diffusion forward per step.
The CUDA parity test is skipped on machines without CUDA.

`benchmark_cpu.json` separates matrix construction, DP, full selector time, and
overhead relative to independent argmax at lengths 1/8/32/128/256 and weights
0/0.25/0.5/1. Synthetic Gaussian emissions test cost and token differences, not
model quality. `--logits path.pt` can replay captured model logits instead.
At B=256, K=16, lambda=.5, the CPU measurement is about 2.27 ms for matrices,
1.51 ms for DP, and 111 ms total including full-vocabulary normalization/top-k.
GPU latency must be measured separately; CPU timings are not GPU estimates.

On all 10,000 held-out validation responses, including true EOS boundaries (736,142 transitions), bigram
perplexity is 116.17 versus 1516.68 for unigram backoff; 5.29% of transitions are
unseen. This measures scorer likelihood, not diffusion generation quality.

The hosted comparison saves complete outputs, latency, word repetition, and
sequence differences from lambda-zero decoding. Single runs are exploratory:
existing sampling strategies use random seeds, and latency includes allocation,
queueing, and network overhead. These measurements do not establish an optimal
lambda or a statistically significant output-quality improvement.

Targeted tests: 53 passed, 1 CUDA skip. The full repository suite has 224 passes,
1 CUDA skip, and 3 existing failures in `tests/test_training.py`: Llama training
configuration expectations disagree with unchanged YAML learning-rate/batch-size
settings. No training settings were changed for this implementation.

The initial response-text-only checkpoint was also evaluated and its outputs
are retained in `space_evaluation_response_text.json`. Missing EOS counts
contributed to long continuations; the published scorer includes true response
endings without adding terminal targets to truncated examples.

## Hosted comparison after EOS alignment

The deployed revision is `440eb901a653d8dbbc9110ec9021b2b975076653` in
[Ruurd/byod-gemma-2-9b](https://huggingface.co/spaces/Ruurd/byod-gemma-2-9b).
All 25 Amsterdam cases completed on the Space GPU: lengths 1/8/32/128/256,
weights 0/.5/1, confidence-guided, and random, using eight denoising steps.
At lambda .5, the 128/256-token cases now end naturally; the initial scorer
without EOS counts produced repetitive continuations instead.

| Block length | Lambda .5 latency (s) | Sequence difference from lambda 0 | Adjacent repeated words |
| --- | ---: | ---: | ---: |
| 1 | 1.14 | 100.0% | 0 |
| 8 | 0.89 | 0.0% | 0 |
| 32 | 0.96 | 46.7% | 0 |
| 128 | 1.15 | 56.8% | 1 |
| 256 | 1.42 | 38.5% | 0 |

Sequence difference uses a sequence-matching ratio on the rendered token spans;
it includes downstream effects over denoising steps. The standalone benchmark
also measures direct same-logit differences from argmax. At length one, the
candidate-only decoder is argmax; the integrated selector also includes known
prompt-boundary context, which can change that token.

In these single samples, lambda .5 reduces repeated words relative to independent
argmax, but some grammar remains awkward. Lambda 1 is not consistently better.
The default .5 remains an experimental starting point. No claims about factual
accuracy or general quality follow from this small comparison.

A second prompt, “Explain why the sky looks blue,” completed all five strategies
at 64 tokens and 32 steps. Lambda .5 generated “The sky appears blue due to the
scattering of sunlight by air.” All runs ended without adjacent word repeats;
complete results are in `space_evaluation_sky.json`.

PMI scoring, successor marginals, and matched-seed comparisons are documented in [PMI.md](PMI.md).

Ending delay and whole-answer stopping across blocks are documented in [ENDINGS.md](ENDINGS.md).

Optional Viterbi path-margin remasking is documented in [VITERBI_CONFIDENCE.md](VITERBI_CONFIDENCE.md).
