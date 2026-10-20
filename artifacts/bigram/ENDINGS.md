# Ending delay and blockwise early stopping

The fixes address two separate behaviors:

- Retention-only delay can keep remasking EOS/EOT without changing a
  deterministic Viterbi prediction. The same short ending can win every time.
- Block convergence used to skip the rest of the current block's steps, then
  start another block even after a completed answer. It could also override
  the delayed-ending retention schedule.

## Bigram ending delay

With `Delay EOS/EOT retention (longer answers)` enabled, Bigram Viterbi now
applies a fading ending-prediction penalty in addition to the existing
retention policy. `Bigram ending delay strength` defaults to 10 and is
configurable. Strength 1 restores retention-only behavior.

For block refinement index `s` starting at 1, with `N` steps allocated to that
block, the penalty is `strength ** (1 - s/N)`. Its logarithm is subtracted from
EOS/EOT logits before candidate extraction. The penalty affects only the
current block and is exactly 1 (no change) on its final step, including
single-step blocks. This discourages early ending predictions without forcing
a minimum answer length. Strong natural endings can still win. Fixed tokens
remain constrained and no additional model passes are made. Sampling-based
strategies retain their existing token-selection behavior.

Convergence cannot finalize an ending while the delay schedule would still
remask it: an unfrozen ending must wait until it is retained/fixed or the
block reaches its final refinement. This applies to the shared retention
option across strategies, preventing early stopping from bypassing it.

## Completing an answer versus completing a block

With `Early stopping` enabled:

- A stable block without an ending can converge and advance to the next block.
- A stable ending, a fixed ending, or an ending in a completed block finishes
  the whole answer once every preceding token is resolved.
- Later blocks are skipped; no further model forward passes are issued.
- A transient ending or an ending preceded by unresolved masks cannot terminate
  the answer prematurely.

Both EOS and the backbone's native EOT are recognized, regardless of the delay
checkbox. Rendering, copying, convergence comparisons, and visible token counts
all stop at the first ending. The debug option that explicitly shows ending
markers keeps its previous behavior. Status now reports `answer finished
(EOS)` or `answer finished (EOT)` and `remaining blocks skipped` when applicable.
Disabling early stopping still runs the full configured step budget.

## Validation

109 targeted tests passed, with 2 CUDA parity skips. The full repository suite
reported 280 passed, 2 skipped, and the same 3 existing Llama training-YAML
expectation failures. No training configurations were changed.

New synthetic tests exercise both ending types, conditional/PMI selectors and
ordinary sampling, convergence and final-step completion, transient endings,
fixed endings with masked prefixes, ordinary block convergence, disabling
early stopping, the fading penalty, final-step unbiased logits, and unchanged
model-forward counts. Existing code-rendering and inference regressions pass.

```sh
.venv/bin/python -m pytest tests/test_inference_endings.py tests/test_inference.py \
  tests/test_bigram.py tests/test_publish_byod.py -q
```

## Hosted regression checks

The Gemma Space is running revision `08a73ed0cd27d0c99f2b41320d3327c19df4a493`.
All ten matched-seed checks completed on the hosted GPU.

For the short arithmetic answer (`4.`), both conditional and PMI decoding
finished after **1 model pass instead of 16** with early stopping enabled;
turning early stopping off still ran all 16 passes. The finalized ending was
in block 1/4, and the status explicitly reported that later blocks were skipped.

For the Amsterdam prompt (128-token cap, 64-token blocks, 32 total steps,
seed 42), the observed outputs were:

| Scoring method | Ending-delay setting | Words | Model passes |
| --- | --- | ---: | ---: |
| Conditional bigram | Off | 16 | 4 |
| Conditional bigram | Retention only (strength 1) | 39 | 12 |
| Conditional bigram | Retention + fading penalty (strength 10) | 43 | 15 |
| PMI bigram | Off | 13 | 13 |
| PMI bigram | Retention only (strength 1) | 43 | 13 |
| PMI bigram | Retention + fading penalty (strength 10) | 51 | 16 |

All six Amsterdam runs finalized EOS in the first block and skipped the
second block. The restored retention/convergence interaction accounts for
much of the length difference; the fading penalty adds further encouragement.
These are single-prompt control checks, not evidence of a general quality gain
or a guaranteed minimum answer length. Full text and metrics are saved in
`ending_space_evaluation.json`.

Reproduce the hosted checks:

```sh
.venv/bin/python scripts/evaluate_ending_controls.py \
  --output artifacts/bigram/ending_space_evaluation.json
```
