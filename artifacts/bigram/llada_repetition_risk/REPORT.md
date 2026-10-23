# Optional joint-probability repetition-risk penalty

Deployed only to [Ruurd/llada-8b-instruct](https://huggingface.co/spaces/Ruurd/llada-8b-instruct).
Select **PMI Viterbi + Repetition Penalty**, then enable **Repetition-risk penalty**.
The checkbox defaults OFF, preserving existing behavior. Gamma starts at 1.
Both maximum-path Viterbi and sequence sampling are supported, with or without APD.
Risk overrides the candidate-count checkbox when both are ON. Other Spaces,
model weights, checkpoints, temperature/weight defaults and training are unchanged.

## Algorithm

1. Build the existing top-k lattice with fixed-row constraints, raw diffusion
   emissions, weighted PMI edges and existing boundary terms.
2. Compute joint edge marginals q_s(a,b) from the unpenalized sequence distribution
   using forward/backward sum-product. These are probabilities conditional on the
   candidate lattice, not independent full-vocabulary probability products.
3. Estimate earlier risk `r_t(a,b) = 1-product_(s<t)(1-q_s(a,b))`.
4. Subtract `gamma*log((1-r+9r)/(1-r))` from the transition score; score before
   updating the earlier-risk dictionary. At T=1, gamma=1: risks 0, .1, .25, .5,
   .9 yield score multipliers 1, .5, .25, .1, approximately .0122.
5. Run the existing max-path or sequence sampler on corrected scores. Temperature
   still scales the complete sequence score when sampling.

Sequence-sampling marginals use its positive temperature; deterministic max-path
and zero-temperature sampling use a T=1 soft surrogate. This avoids taking a
singular distribution as the risk estimate. No random numbers are consumed by
risk estimation. No iterative recalculation after applying the penalty is used.

EOS/EOT pairs neither contribute nor incur a penalty. Fixed-row duplicate dummy
columns have zero marginal; retained values cannot change. State resets each
iteration/block, without crossing prompt/block boundaries. Gamma=0 follows the
original unpenalized decoder exactly. A 1e-7 survival floor keeps effectively
certain risk finite. There are extra decoder calculations but no extra model
forwards, separate language model, or training.

This is a risk heuristic, not an exact conditional probability of repetition:
overlapping occurrences are dependent, while the product approximates them as
independent. The marginals describe the unpenalized lattice distribution. Applying
the penalty changes that distribution. Score multipliers are not guarantees on
normalized output probabilities or elimination of repeated phrases.

## Validation

17 new tests pass, including exact enumeration of joint edge marginals at four
temperatures with a fixed row, PMI influence, half-score calibration at 10% risk,
progressive risk, EOS exemption, fixed dummy columns, per-call reset, finite
extreme scores/length 1–256, gamma-zero identity, raw retention confidence,
native LLaDA with max-path/sampling and APD, and app routing/precedence.
98 focused tests passed. Full suite: 554 passed, 4 skipped, same three pre-existing
training-config failures. No new failures.

Nine live checks passed. All three OFF outputs match the prior deployment exactly.
Gamma-zero max and sampled paths match unpenalized reference outputs. Every case
resolves its masks and uses only the configured denoising forward budget. The APD
case uses 8 forwards; all other cases use 1. These are short functional smoke tests,
not a representative quality/latency evaluation.

In the one-step Amsterdam example, risk at gamma=1 reduced the city-of loop and
canal repetitions compared with the old expected-count mode, but the output still
repeats canals and makes factual/grammatical mistakes. Sampling remains weak at
one NFE. The 8-step sampling+APD example is more readable, but differs in NFE and
cannot isolate the risk penalty's quality effect. Gamma=10 still does not guarantee
no repetition. Single-trial server times include cold/warm variation.

Parent: `35914ffa96f3e2687f06de44f1dee45078f61d8a`. Deployment: `82e83e1d1f7fe6442ad3c4d068df08013999cbc7`.

## Live outputs

All cases: Amsterdam question, block/max length 32, T=1, weight=1, top-k=100,
seed 1234, delay EOS OFF, early stopping OFF. Gamma=1 except explicitly named.

### risk_off_viterbi

Amsterdam is the city of the city of the city known for its history, and canals, and canals, and canals, you know about it?

Denoising forwards: 1. Server time: 511.8 ms.

### risk_off_sampling

I'm so the city of the history with rich and its city of canals canals of its culture history history for something with something you in the city?

Denoising forwards: 1. Server time: 122.2 ms.

### risk_off_expected_penalty

Amsterdam is the city of the city of the city known for its history, and canals, and canals, you would like you know about it?

Denoising forwards: 1. Server time: 73.0 ms.

### risk_zero_gamma_viterbi

Amsterdam is the city of the city of the city known for its history, and canals, and canals, and canals, you know about it?

Denoising forwards: 1. Server time: 32.2 ms.

### risk_zero_gamma_sampling

I'm so the city of the history with rich and its city of canals canals of its culture history history for something with something you in the city?

Denoising forwards: 1. Server time: 36.7 ms.

### risk_viterbi

Amsterdam is the city of the Netherlands, and its history and its canals and canals and culture.

Denoising forwards: 1. Server time: 52.7 ms.

### risk_sampling

I'm so the city of the history with rich on its love of canals are any It unique history. for something with something you about the city?

Denoising forwards: 1. Server time: 46.9 ms.

### risk_sampling_apd

I can provide information about Amsterdam from all, including its history, its capital, attractions and landmarks and cultural attractions. What would you like to know?

Denoising forwards: 8. Server time: 385.0 ms.

### risk_viterbi_gamma10

Amsterdam is the city of the Netherlands, known for its canals and canals.

Denoising forwards: 1. Server time: 41.9 ms.

