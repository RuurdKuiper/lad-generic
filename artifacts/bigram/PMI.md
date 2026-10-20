# PMI scoring for BYOD Gemma

The existing `Bigram Viterbi` strategy now offers `Conditional bigram` (default)
and `PMI bigram`. Both use the same Viterbi DP, top-k candidates, block constraints,
and confidence-guided remasking. The weight remains adjustable, default 0.5.
Normal generation adds no model forward passes or timing synchronization.

For candidate pair `(a, b)`, conditional scoring is the original smoothed
`log P(b|a)`. PMI scoring subtracts `log P_successor(b)` and then applies safeguards:

- Observed count below `min_count` (default 5): zero correction.
- Unseen pairs: zero correction, including when the threshold is set to zero.
- Other corrections: clipped to `[-pmi_clip, pmi_clip]` (default `[-5, 5]`).

The safeguards affect PMI only. Setting lambda to zero gives independent
full-vocabulary diffusion argmax at editable positions in either mode. Frozen
positions remain constraints. Known boundary tokens use the chosen scoring
method too; rare or unseen boundary pairs are neutral under PMI.

## Marginals and checkpoints

The training builder already counts all token occurrences as well as sparse
adjacent pairs. It now saves version-2 checkpoints with both all-token unigrams
and explicit successor counts. Successor counts are column sums of the sparse
bigram counts: document-initial tokens are excluded, singleton documents
contribute no successors, and no pair crosses a document boundary. The PMI
marginal is `(successor_count[b] + beta) / (total_successors + beta * V)`, using
the same corpus, tokenizer, and beta smoothing (default 0.1).

Conditional probabilities intentionally retain their original all-token
unigram backoff. This preserves conditional outputs when selecting the new
mode is not requested. `BigramScorer.log_prob` always returns this original
conditional log-probability; `transition_score` and `forward` accept
`scoring_method='conditional'|'pmi'`, `min_count`, and `pmi_clip`.

Version-1 checkpoints remain loadable. Their exact successor counts are
reconstructed from existing pair counts, so no approximate replacement
marginal or corpus retokenization is needed. Version-2 loading verifies that
saved successor counts agree with the pairs. Saving a loaded v1 scorer writes
v2. The deployed full-training-split checkpoint was upgraded this way:
980,000 responses, 73,467,371 tokens, 72,487,371 successor tokens, 6,032,223 pairs.
The tokenizer mapping and conditional scores are preserved.

The existing `scripts/build_bigram.py` rebuild command in [README.md](README.md)
now produces the additional successor statistics automatically. No extra
training flags or dependencies are needed.

## Reproducible evaluation

The Space exposes a seed field under `Reproducible evaluation`; -1 preserves
random-seed behavior, while nonnegative values are reproducible. Scoring method,
minimum count, clipping, and weight are per-request selector settings; cached
count models are shared without mutating their scoring configuration.

Opt-in decoding measurements report time after GPU completion and compare each
selected editable token against independent argmax on that *same iteration's
logits*. Fixed rows are excluded. This is distinct from comparing final answers,
which includes downstream changes over denoising iterations. Measurements add
synchronization and metric-collection overhead and are disabled by default.
`bigram_evaluation.py` wraps the selector without extra model forwards.

```sh
.venv/bin/python -m pytest tests/test_bigram.py tests/test_inference.py tests/test_publish_byod.py -q
.venv/bin/python scripts/benchmark_bigram.py \
  --checkpoint artifacts/bigram/gemma.pt --methods conditional pmi \
  --output artifacts/bigram/pmi_benchmark_cpu.json
.venv/bin/python scripts/evaluate_bigram_space.py \
  --prompts 'What do you know about Amsterdam?' 'Explain why the sky looks blue.' \
    'What is 2 + 2? Answer with only the number.' \
  --lengths 32 128 256 --steps 16 --seeds 42 1234 \
  --output artifacts/bigram/pmi_space_evaluation.json
```

For every prompt/block length/seed, the hosted script compares independent
argmax (lambda 0), conditional Viterbi (lambda .5), and PMI Viterbi (lambda .5).
All other diffusion settings and seeds are identical, with early stopping and
ending-retention delay disabled. It saves complete outputs, same-logit token
change fractions, selector timings, overhead versus the argmax selector path,
final-answer differences, and word-repetition diagnostics. End-to-end latency
also includes queueing, GPU allocation, and network time. The lambda-zero
selector uses exact full-vocabulary argmax and skips top-k/DP. This also fixes
the previous top-k tie discrepancy on BF16 logits. It still computes normalized
probabilities for retention confidence; raw argmax cost is measured separately
in the CPU benchmark.

Synthetic CPU benchmarks use identical seeded full-vocabulary logits for both
scorers, with B=1/8/32/128/256 and weights 0/.25/.5/1. They report matrix time,
DP time, total selector time, and direct token differences. Synthetic logits
measure cost and algorithm behavior, not generation quality.

Tests cover known PMI probabilities, successor rather than all-token marginals,
threshold boundary counts, neutral unseen/rare pairs, both clipping directions,
v1/v2 compatibility, conditional-score identity, fixed positions and boundary
context, lambda zero, lengths 1–256, and unchanged forward counts. CUDA parity
tests for both modes are present but skipped on the local CPU-only machine.

Python use:

```python
from diffusion_lm.bigram import BigramScorer, BigramViterbiSelector

scorer = BigramScorer.load("artifacts/bigram/gemma.pt", device="cuda")
selector = BigramViterbiSelector(scorer, weight=0.5,
    scoring_method="pmi", min_count=5, pmi_clip=5.0)
```

Set `scoring_method="conditional"` to retain the original scoring objective.
The original conditional formula is tested for exact equality across checkpoint
migration. The only zero-weight behavior correction is deterministic tie
handling: it now uses full-vocabulary `argmax`, rather than top-k's arbitrary
ordering of equal maxima.

## Code rendering

The trajectory now keeps real newlines in its existing `white-space:pre-wrap`
container instead of substituting arrow glyphs. A `Plain text / copy code`
textarea provides decoded source without per-token rich-text styles. Full
completed output retains indentation, tabs, and internal line breaks; HTML
escaping occurs once at the rendering boundary. Model-generated HTML/entities
remain source text rather than being interpreted or decoded a second time.
During incomplete steps, masks use the existing explicit mask placeholders.

Regression tests cover all three color modes, code fences, tabs, spaces,
newlines, literal HTML entities, and markup escaping. A local preview generated
with the actual Gemma tokenizer round-trips the Fibonacci snippet exactly,
including all seven line breaks: [code_rendering_preview.html](code_rendering_preview.html).
The existing API still returns `(status, trajectory_html)`.

Current targeted validation: 80 passed, 2 CUDA parity skips. The broad repository
suite, run after the PMI/argmax changes, reported 248 passed, 2 CUDA skips, and
the same 3 pre-existing Llama training-YAML expectation failures. Rendering
changes were subsequently checked with the complete inference/decoder/Space
bundle test set. No training configurations were changed.

## Measured comparison

The combined revision `f3ca90d2b51bad138961ee8821a531d4cc00885e` completed all
54 hosted runs: 3 prompts × 3 block lengths × 2 seeds × 3 configurations,
with 16 denoising steps per run. All independent-argmax measurements report
exactly zero changed predictions, including BF16 tied maxima.

| Configuration | Same-logit token changes | Selector time / step | Extra selector time / step vs argmax | Mean adjacent repeated words | Arithmetic exact |
| --- | ---: | ---: | ---: | ---: | ---: |
| Independent argmax | 0.00% | 1.39 ms | 0.00 ms | 1.00 | 6/6 |
| Conditional bigram | 23.70% | 12.46 ms | 11.07 ms | 0.00 | 6/6 |
| PMI bigram | 21.82% | 12.16 ms | 10.77 ms | 0.33 | 6/6 |

Changes are aggregated over all editable predictions in the planned blocks,
including positions after the first displayed EOS. Selector timing includes
full-vocabulary scoring/candidate extraction and DP, but excludes model forwards
and the diagnostics' extra argmax/count collection. Synchronization itself
changes scheduling. Differences of a few tenths of a millisecond between PMI
and conditional scoring should not be interpreted as a reliable speed ranking.
End-to-end latency contains startup and queue variation; it is not an isolated
measurement of inference overhead.

Conditional scoring was more fluent in the Amsterdam samples. PMI retained some
repetition and repeated “blue light” at B=256 for the sky prompt. Scientific
explanations remained incomplete or malformed across methods. Every arithmetic
response was exactly `4`. This small evaluation does not establish a semantic
quality gain for PMI; conditional scoring remains the default.

Both seeds produced identical answers under these deterministic settings.
Complete per-run output and metrics are in `pmi_space_evaluation.json`; aggregate
numbers and qualitative observations are in `pmi_evaluation_summary.json`.

The updated builder was also exercised end-to-end on tokenized JSONL: it
produced a reloadable v2 checkpoint with 6 token occurrences and 3 successor
occurrences, excluding the singleton document from successor counts.
The final hosted code smoke check confirmed multiline output and the copyable
textarea in the live Space; see `code_space_smoke.json` and
`code_space_smoke.html`. This checks formatting fidelity, not Python correctness.
