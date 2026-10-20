# Viterbi path-margin remasking

Gemma's `Bigram Viterbi` strategy now has a `Bigram remasking confidence` choice:

- **Diffusion probability** (default): retain higher-probability diffusion predictions.
- **Viterbi path margin**: retain predictions with a larger complete-path score gap;
  remask the positions whose token choice is less stable under the joint objective.

For each position, the margin is the best complete-path score with its selected
ID minus the best complete-path score with a different ID at that position.
The alternative may change other editable positions too. This measures the
cost of changing the token after allowing the rest of the block to readjust.
It is not the accumulated prefix score, nor a calibrated probability.

The implementation runs forward/backward max-sum dynamic programming over the
same top-k lattice. Each diffusion emission and adjacent transition is counted
once per path. Normalizing each DP row by a shared constant reduces numerical
cancellation without changing the gaps. Complexity remains O(B K²), with O(B K)
additional DP storage, and the transition matrices are reused. There are no
additional diffusion-model forwards. The extra DP passes add selector latency.

## Constraints and inference behavior

Frozen tokens still have exactly one legal ID and anchor their adjacent
transitions. Margin alternatives exclude every copy of the selected ID, not
just one candidate column. Fixed rows therefore have infinite margins. With
K=1 there is also no alternative, giving infinite margin. Both mean “forced
within this lattice,” not certainty about tokens outside the shortlist. Tied
complete-path alternatives give zero margin.

Boundary context, conditional/PMI scoring, candidate extraction, the remasking
count schedule, and delayed-ending rules are preserved. EOS/EOT retention delay
still takes priority over the confidence ranking. For lambda zero, selection
continues to use exact full-vocabulary argmax, including BF16 ties; margins
reflect alternatives in the top-k set.

For identical logits and constraints, both modes return identical selected IDs
and diffusion probabilities. They can produce different final answers over
multiple iterations because they retain different positions. A synthetic
regression demonstrates opposite rankings: the lower-probability token has a
larger joint-path margin and is retained first only in the new mode.

The inference engine keeps retention scores separate from displayed diffusion
probabilities. Token colors, hover probabilities, frozen-token probability
history, and mean-confidence display remain probabilities. Status explicitly
indicates `Viterbi-margin remasking` when active. Count checkpoints are unchanged;
this is per-request selector configuration, not a scorer or training update.

## Python use

```python
selector = BigramViterbiSelector(
    scorer, weight=0.5, scoring_method="pmi",
    remasking_confidence="viterbi_margin",
)
selected_ids, diffusion_probabilities = selector.select_block(
    logits, current_ids, editable, top_k=16,
)
retention_scores = selector.last_path_margins
```

Use `remasking_confidence="diffusion"` for the original/default behavior.
`select_block` keeps its existing two-value return contract. The optional
profiling wrapper forwards the margin tensor without extra model calls.

## Validation

Tests compare gaps with exhaustive path enumeration, test constant-shift
invariance, tied paths, singleton blocks/candidates, fixed-ID duplication,
boundary context, both scoring methods, block lengths 1/8/32/128/256,
zero-weight BF16 ties, retention-ranking changes inside actual denoising,
unchanged displayed probabilities, and unchanged forward counts with/without
profiling. Existing delayed-ending tests also run with margin confidence.

The full suite reports 305 passed, 3 CUDA parity skips, and the same 3 existing
Llama training-YAML expectation failures. No training configurations changed.

```sh
.venv/bin/python -m pytest tests/test_viterbi_confidence.py tests/test_bigram.py \
  tests/test_inference.py tests/test_inference_endings.py tests/test_publish_byod.py -q
.venv/bin/python scripts/benchmark_bigram.py \
  --checkpoint artifacts/bigram/gemma.pt --methods conditional pmi --weights .5 \
  --remasking-confidences diffusion viterbi_margin \
  --output artifacts/bigram/viterbi_margin_benchmark_cpu.json
```

This confidence measures stability under the selected bigram objective and
candidate set. A stable but wrong bigram pattern can still be retained. It is
an experimental alternative, rather than evidence of a general quality gain.

## CPU benchmark

Measured with the full Gemma vocabulary, K=16, lambda=.5 and identical seeded
synthetic logits. These timings measure selection cost, not output quality:

| Scoring | Confidence | B=256 total selector | Margin calculation |
| --- | --- | ---: | ---: |
| conditional | diffusion | 103.32 ms | 0.00 ms |
| conditional | viterbi_margin | 105.87 ms | 2.33 ms |
| pmi | diffusion | 103.91 ms | 0.00 ms |
| pmi | viterbi_margin | 106.64 ms | 2.30 ms |

## Hosted checks

Revision `c8003db3f4da4569d0915199751c1b7e0f1147d2` is running on
[Ruurd/byod-gemma-2-9b](https://huggingface.co/spaces/Ruurd/byod-gemma-2-9b).
All 20 hosted cases completed with matched seed 42 and weight .5: conditional
and PMI scoring, both confidence modes, Amsterdam/sky prompts at lengths
32/128, and a four-block arithmetic ending check. Diffusion-mode requests omitted
the new parameter to verify that existing callers keep the default behavior.

Every fixed-budget case used exactly 16 selector/model calls in either mode.
All four early-stopping cases completed after one call and skipped the remaining
blocks, with the expected short arithmetic answer. The active-mode status was
checked in every case. Delayed ending strength remained 10 throughout.

Measured GPU-completed selector time per iteration (average of the two prompts):

| Scoring | Block length | Diffusion confidence | Path-margin confidence |
| --- | ---: | ---: | ---: |
| Conditional bigram | 32 | 3.19 ms | 7.75 ms |
| Conditional bigram | 128 | 11.97 ms | 27.95 ms |
| PMI bigram | 32 | 3.67 ms | 7.58 ms |
| PMI bigram | 128 | 12.24 ms | 26.94 ms |

These are synchronized opt-in diagnostic timings, not a statistically robust
latency benchmark. They include candidate extraction and DP but exclude model
forwards and rendering. The new mode adds DP work; it does not add model passes.

Some generated answers changed, as expected from different retained positions.
The small smoke set does not establish a quality advantage: repetition and
incomplete explanations still occur. Full outputs and timing metrics are in
`viterbi_confidence_space_evaluation.json`; diffusion probability remains the
default.

Reproduce the live checks:

```sh
.venv/bin/python scripts/evaluate_viterbi_confidence.py \
  --output artifacts/bigram/viterbi_confidence_space_evaluation.json
```
