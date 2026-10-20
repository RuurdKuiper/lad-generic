# Paper-style coding comparison

Manually reviewed 150 of 150 saved outputs; 150 planned. Runs execute on Hugging Face Space `Ruurd/byod-gemma-2-9b`; local code submits requests, stores answers, and aggregates manual judgments.

Same ten custom assignments and all five methods at NFE 32, 64, and 128. The paper prescribes greedy temperature 0, low-confidence retention, one full block, no repetition penalty, and delayed EOS/EOT retention for coding ([paper source](../../../arxiv_submission/paper.tex)). This run uses a 128-token canvas and block, corresponding to the paper’s MBPP-sized budget, with the requested NFE ablation. It is not a HumanEval/MBPP benchmark reproduction.

**Settings:** temperature 0, sampling top-k 1, bigram candidates 16, bigram weight 0.5, PMI minimum count 1, clipping ±2, seed 42, retained tokens frozen. Delayed EOS/EOT retention is on; ending prediction strength 1 is neutral (no logit penalty). Early stopping is off to spend the requested NFE. No additional model forward passes are introduced by bigram selection.

## Interpretation

PMI plus path-margin retention is the most consistent coding variant descriptively in this small paper-style test: it ties PMI plus diffusion at 32 and 128 NFE and exceeds it by one correct assignment at 64 NFE. Their mean manual scores likewise tie at 32/128 and favor path margin at 64. That is a weak signal from ten assignments, not enough evidence to establish a general winner. The earlier open-ended evaluation is separate evidence and was not repeated here.

PMI plus diffusion has only one assignment-level score change against the greedy baseline at each of 64 and 128 NFE: it loses partial correctness on flatten at 64, and fixes the baseline's invalid import in sum_even at 128. At 32 all ten assignment scores tie. This does not establish a broad coding gain across NFE regimes.

The dominant remaining failures are malformed syntax and incorrect logic: no configuration fully solves palindrome, Fibonacci (including n=1), bracket matching, word counts as standalone code, or FizzBuzz in this rerun. The 128-NFE PMI successes are sum_even, deduplicate, merge_sorted, and flatten. FizzBuzz often misses the both-divisors case; word counts often omit Counter imports; Fibonacci often returns two values for n=1. These observations come from reading outputs, not executing them.

## Fully correct solutions

Each cell is fully correct / reviewed assignments. A solution must be self-contained, runnable Python and satisfy stated edge cases. A linear lookup does not count as a correct binary-search implementation. Scores come from reading the verbatim answers; generated code was not executed. Exact duplicate answers for the same prompt reuse their recorded judgment.

| Method | 32 NFE | 64 NFE | 128 NFE |
|---|---:|---:|---:|
| Greedy confidence baseline | 1/10 | 0/10 | 3/10 |
| Conditional + diffusion | 1/10 | 0/10 | 2/10 |
| PMI + diffusion | 1/10 | 0/10 | 4/10 |
| Conditional + path margin | 0/10 | 1/10 | 3/10 |
| PMI + path margin | 1/10 | 1/10 | 4/10 |

## Partial correctness

Mean manual score out of 3: 3 correct, 2 localized defect, 1 substantial syntax/logic error but recognizable approach, 0 unusable. This is descriptive evidence from ten small assignments, one deterministic trajectory per configuration, not a statistically established ranking.

| Method | 32 NFE | 64 NFE | 128 NFE |
|---|---:|---:|---:|
| Greedy confidence baseline | 1.20 | 1.10 | 1.90 |
| Conditional + diffusion | 1.20 | 1.00 | 1.60 |
| PMI + diffusion | 1.20 | 1.00 | 2.00 |
| Conditional + path margin | 1.00 | 1.20 | 1.70 |
| PMI + path margin | 1.20 | 1.30 | 2.00 |

## Paired PMI/diffusion versus baseline

Comparison uses the same assignments within each fixed NFE. Wins/losses below compare the full 0–3 manual scores.

| NFE | Matched assignments | PMI wins | Ties | PMI losses |
|---|---:|---:|---:|---:|
| 32 | 10 | 0 | 10 | 0 |
| 64 | 10 | 0 | 9 | 1 |
| 128 | 10 | 1 | 9 | 0 |

## What changed relative to the earlier test

The earlier coding run used temperature 1, sampling top-k 16, and ordinary EOS/EOT retention. This rerun changes both baseline sampling/confidence and ending retention, so it does not isolate temperature.

Viterbi ignores sampling temperature and sampling top-k. Its candidate extraction uses a separate bigram top-k of 16 and full-vocabulary raw-logit log probabilities. Those candidates and scores were not made less random by these two sampling controls; the Viterbi path was already deterministic. Delayed ending retention can nevertheless change later Viterbi inputs by changing which tokens get frozen.

For temperature exactly zero, the baseline was corrected to select raw-logit argmax and rank retention by the selected token’s full-vocabulary probability. Using top-k-1 sampling probability would assign every token confidence 1 and destroy confidence ranking. Positive-temperature behavior and the Viterbi code path are unchanged. Targeted validation: 136 tests passed, 3 CUDA-only skips. Deployed revision: `3e22ca7e38f1380b343928763fe1709b4173e76d`. One initial PMI/32 credit probe is reused from the preceding revision because this baseline-only fix cannot affect its execution path.

## Timing and selection changes

Means are over saved runs in each group. Wall time includes network/queue/startup effects and is not a controlled latency benchmark. Selector milliseconds measure the selection stage per denoising step. Changed percentage counts editable Viterbi decisions that differ from same-step diffusion argmax, not differences between final answers.

| NFE | Method | n | Wall seconds | Selector ms/step | Changed decisions |
|---:|---|---:|---:|---:|---:|
| 32 | Greedy confidence baseline | 10 | 3.45 | — | — |
| 32 | Conditional + diffusion | 10 | 4.58 | 12.25 | 12.8% |
| 32 | PMI + diffusion | 10 | 4.64 | 11.97 | 12.3% |
| 32 | Conditional + path margin | 10 | 3.68 | 24.65 | 14.2% |
| 32 | PMI + path margin | 10 | 4.23 | 25.92 | 12.4% |
| 64 | Greedy confidence baseline | 10 | 9.76 | — | — |
| 64 | Conditional + diffusion | 10 | 13.82 | 11.28 | 15.4% |
| 64 | PMI + diffusion | 10 | 6.53 | 11.20 | 13.2% |
| 64 | Conditional + path margin | 10 | 6.93 | 24.64 | 14.1% |
| 64 | PMI + path margin | 10 | 7.04 | 24.55 | 12.2% |
| 128 | Greedy confidence baseline | 10 | 9.40 | — | — |
| 128 | Conditional + diffusion | 10 | 10.88 | 10.76 | 15.9% |
| 128 | PMI + diffusion | 10 | 12.20 | 11.34 | 12.5% |
| 128 | Conditional + path margin | 10 | 12.90 | 23.71 | 15.3% |
| 128 | PMI + path margin | 10 | 22.69 | 23.80 | 12.6% |

## Artifacts

- [Verbatim labeled outputs](answers_labeled.md)
- [Manual scores and defect notes](manual_scores.csv)
- [Exact run settings](manifest.json)
- [Per-output data and timings](results.jsonl)
- [Review protocol](REVIEW_PROTOCOL.md)

## Earlier coding setup versus paper-style setup

Each cell shows earlier → current fully correct solutions, using the same ten assignments. Earlier: temperature 1, sampling top-k 16, delayed retention off. Current: temperature 0, sampling top-k 1, delayed retention on. Viterbi is unaffected by those sampling controls; its relevant intervention is delayed retention.

| Method | 32 NFE | 64 NFE | 128 NFE |
|---|---:|---:|---:|---:|
| Greedy confidence baseline | 1/10 → 1/10 | 1/10 → 0/10 | 2/10 → 3/10 |
| Conditional + diffusion | 1/10 → 1/10 | 1/10 → 0/10 | 2/10 → 2/10 |
| PMI + diffusion | 1/10 → 1/10 | 2/10 → 0/10 | 2/10 → 4/10 |
| Conditional + path margin | 1/10 → 0/10 | 1/10 → 1/10 | 2/10 → 3/10 |
| PMI + path margin | 1/10 → 1/10 | 1/10 → 1/10 | 1/10 → 4/10 |

The earlier PMI/diffusion 64-NFE successes were sum_even and flatten. With delayed retention, sum_even gains a duplicated empty def and flatten gains a malformed header/comprehension. At 128 NFE, PMI/diffusion instead gains correct deduplication and merging. The ending policy has mixed effects across budgets and assignments; it is not a universal improvement.
