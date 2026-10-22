# Transition-based expected repetition penalty

The latest **PMI Viterbi + Repetition Penalty** strategy applies a correction
to the particular candidate transition, replacing the initial unary formula.
Deployed revision: `a51224e831820c03732595608ddee8c0e7356bc4`; parent: `d3d8e4581679b9ffd7c4f59f4aee54a9e38991c5`.

For each block and denoising iteration, start C(a,b)=0. At adjacent positions:

1. Score each candidate edge as `0.5 * temperature * PMI(a,b) - gamma * C(a,b)`.
2. After scoring all edges at that position, update
   `C(a,b) += p_t(a) * p_(t+1)(b)`.

Here p is the original full-vocabulary diffusion probability, including the
existing EOS bias, without top-k renormalization or temperature scaling. The
current pair probability no longer multiplies its penalty. The decoder's
unary diffusion log-scores and selected-token confidence are unchanged.

Pairs involving EOS or end-of-turn are neither penalized nor counted. Counts
reset each iteration/block, excluding prompt and right-boundary transitions.
Fixed positions remain constrained to their known token, with probability 1
for expected-count updates; visible LAD positions remain editable. Gamma is
independent of the PMI weight and temperature, including temperature zero.
Gamma defaults to 1; gamma=0 follows the original PMI decoder exactly.
There are no additional model forwards or changes to model training.

## Validation

- Relevant checks: 180 passed, 3 CUDA-only skips.
- Full suite: 466 passed, 4 skipped, with the same three pre-existing training
  configuration assertion failures.
- Exhaustive path enumeration verifies the objective and path margins at
  temperatures 0, 0.6, and 2, including fixed rows and both boundary contexts.
- Further tests cover progressive counts, no current-q dilution, updates only
  after scoring the complete position, EOS/EOT exemptions, zero-strength
  equivalence, block/iteration resets, numerical stability, and one forward
  per denoising iteration.

Live two-iteration outputs for original PMI and the repetition decoder at
strengths 0/1/10 are saved in `transition_penalty_hosted_verification.json`.
This is a smoke test on one prompt, not a quality benchmark. Expected counts
are still computed from candidates rather than the final path; repetition is
discouraged rather than strictly forbidden.

All four live checks completed with two prediction steps. Gamma zero matched
the original PMI output exactly. Gamma 10 changed the output and shortened it
from 49 to 46 tokens in this sample, but repeated Amsterdam phrases remained.
This confirms the stronger correction is active, not that two-step generation
is free from repetition.
