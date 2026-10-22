# Optional repetition penalty for Ruurd Gemma and LLaDA

Added **PMI Viterbi + Repetition Penalty** alongside the original Bigram Viterbi option. Gamma defaults to 1; the original option remains selected by default.

The edge score is `0.5 * temperature * PMI(a,b) - gamma * C(a,b)`. Counts accumulate earlier expected pair occurrences from the full-vocabulary diffusion distribution and reset each iteration/block. EOS/EOT pairs are neither counted nor penalized. Retained tokens remain singleton constraints; no additional model forwards are used.

Existing model checkpoints, scorer files, dependencies, hardware settings, pinned native LLaDA revision, repository links and visitor counters were retained. The ending-delay control and reproducibility accordion remain visible.

| Space | Revision |
|---|---|
| [Ruurd/byod-gemma-2-9b](https://huggingface.co/spaces/Ruurd/byod-gemma-2-9b) | `5cd9cd06831177f15d01e03c5c82913e6ff4032a` |
| [Ruurd/llada-8b-instruct](https://huggingface.co/spaces/Ruurd/llada-8b-instruct) | `6e413636fbb77457fabaaec9a61b31a6a9423fdf` |

Local integration checks: 192 passed, 1 CUDA-only skip. The full suite has 476 passes, 4 skips, and the same three pre-existing training-config failures. Tests cover both adapter/native forward paths, fixed rows, two-block boundaries, exact gamma-zero equivalence, and profiling without extra forwards.

Before/after live comparisons use Amsterdam, seed 1234, temperature 2, top-k 16, 32 new tokens, block length 16, 4 total forwards, delayed EOS/EOT retention on, ending strength 10, and early stopping off. Saved records: `before.json`, `prepared.json`, `deployment.json`, `hosted_verification.json`. The live checks include original PMI and gamma 0/1/10; this small check does not establish general quality improvements.

All eight hosted checks passed. On both models, original output matched the
pre-deployment baseline and gamma zero matched original output exactly. Each
run reported four selector calls. The new gamma control and preserved advanced
controls were checked live. Complete outputs: [EXAMPLES.md](EXAMPLES.md).

In this one low-budget example, LLaDA moved from a city-of loop to a mostly
coherent answer at gamma 1, with punctuation/repetition flaws still present.
Gemma retained repetitions at gamma 1; gamma 10 disrupted the loop but introduced
awkward wording and an unrelated Zealand mention. These observations do not
establish general quality improvements or an optimal gamma.
