> Historical first implementation. The current strategy uses a transition
> penalty without the current-pair probability factor. See
> [TRANSITION_REPETITION_PENALTY.md](TRANSITION_REPETITION_PENALTY.md).

# PMI Viterbi + Repetition Penalty

Adds the separate **PMI Viterbi + Repetition Penalty** option to
[Ruurd/lad](https://huggingface.co/spaces/Ruurd/lad). Gamma defaults to 1.0;
the existing Sampling and PMI Viterbi options retain their behavior.
Deployment revision: `a74c9563d79be7d89f59d6ec31d0e7964c3bdbbf`; parent: `a5de76b85b0f3d1b03f9006d33cd954efedea5f1`.
The intervening UI change lowering the context-window minimum to 8 is preserved.

## Scoring

Use the existing top-k candidate IDs and their full-vocabulary diffusion
probabilities after the existing EOS bias, without temperature scaling or
renormalization over candidates. For each edge t and candidate pair (a,b):

- `q_t(a,b) = p_t(a) * p_(t+1)(b)`.
- Subtract `gamma * sum_a(q_t(a,b) * C(a,b))` from b's unary log-score.
- Only after computing all penalties at edge t, add q_t to C.

The first expected occurrence is unpenalized; further expected occurrences
increase the correction. Counts use the original probabilities throughout,
rather than probabilities recalculated from penalized unaries. PMI transitions
remain unchanged. The shared decoder uses the adjusted raw log-probability
unaries plus its existing `0.5 * temperature * PMI` contribution. Thus gamma
uses raw log-probability units; temperature zero still permits the new repetition
correction while disabling PMI influence.

The sparse cumulative dictionary stays on the inference device and is rebuilt
on every selector call. It is confined to the current block, excluding prompt
and right-boundary transitions. Truly fixed rows contribute one legal token
with probability 1; their values and singleton constraints remain unchanged.
Visible LAD answer positions remain editable, reflecting the model's direct
correction training. Its current answer is one refinement block.

No model forwards, reference models, checkpoint changes, or training are added.
Selected-token confidence still comes from the original diffusion distribution.
Gamma zero bypasses penalty computation entirely. The original PMI strategy
always passes zero internally, independently of the slider's stored value.

## Verification

- Relevant tests: 171 passed, 3 CUDA-only skips.
- Full suite: 457 passed, 4 skipped; the same three existing training-config
  assertion failures remain.
- Tests cover the expected-count formula against a literal dictionary scan,
  progressive corrections, no same-edge count contamination, sparse/fixed rows,
  reset across calls, unchanged PMI transitions and confidence, zero-strength
  equality across temperatures/dtypes/block lengths, finite extreme logits,
  invalid/overflowing strengths, and one forward per iteration.

Three live 4-iteration checks completed: original PMI, new gamma=0, and new
gamma=1, without re-noising. Gamma=0 reproduced the original output exactly.
Gamma=1 changed the selected output; repetitions still remain in this small
sample. Live results and UI defaults are recorded in
`repetition_hosted_verification.json` and `repetition_interface_verification.json`.
These are integration checks, not evidence of general output-quality improvement.

## EOS/EOT exemption

Pairs containing EOS or end-of-turn are now excluded from both corrections and
cumulative expected counts. Their probability mass is not redistributed to
ordinary candidates. Regression tests cover mixed ordinary/EOS/EOT candidates
and an all-EOS tail at high gamma. Relevant checks: 173 passed, 3 CUDA skips.
Earlier live examples above were generated before this exemption.

EOS-exemption deployment: `d3d8e4581679b9ffd7c4f59f4aee54a9e38991c5`.
