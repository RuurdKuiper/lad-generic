# Early-iteration logistic repetition-penalty fade

Deployed to [Ruurd/llada-8b-instruct](https://huggingface.co/spaces/Ruurd/llada-8b-instruct)
only. The new **Fade repetition penalty over early iterations** checkbox is ON
by default in the UI. It affects the repetition strategy's expected-count,
candidate-count and risk modes, including sampled sequence decoding and APD.
Turn OFF for constant strength. Existing API calls that omit the new
`decay_repetition_penalty` parameter preserve constant strength; supply True to
match the new UI. Standard decoding and unpenalized Viterbi are unaffected.

## Schedule

For zero-based iteration t within a block, L=6 and c=(L-1)/2:

`g(t)=1/(1+exp(1.6*(t-c)))`

`f(t)=(g(t)-g(L-1))/(g(0)-g(L-1))` until t=L-1; zero thereafter.

`gamma_t = gamma * f(t)`

| Iteration | Strength multiplier |
|---|---:|
| 1 | 1.0000 |
| 2 | 0.9324 |
| 3 | 0.6971 |
| 4 | 0.3029 |
| 5 | 0.0676 |
| 6 onward | 0 |

The first iteration is exactly full strength, preserving the penalty at one NFE.
The fade window is absolute, independent of total NFE: longer runs do not stretch
it across the entire run. It resets at each block, whose initially masked rows
need fresh early decoding. APD completion skips later steps without rescaling the
window. Edit REPETITION_FADE_ITERATIONS in app.py to change the window. The sigmoid
slope is fixed at 1.6; there is no additional numeric UI control.

The decay scales gamma before the existing penalty calculation; it does not change
PMI, diffusion scores, risk estimation, sequence temperature, retention confidence,
EOS/EOT exemption or ending-delay behavior. At zero strength, risk/count calculations
are bypassed and the original unpenalized sequence decoder runs. Late decoding is
identical for the same logits, current/fixed tokens and RNG state, although earlier
penalized decisions can change a whole generation's trajectory.

No extra model forwards, training changes or external model are introduced. A step
context hook passes the block iteration through the optional profiling wrapper.
Library decay defaults OFF; UI enables it only in the deployed LLaDA Space.

## Local validation

24 schedule tests pass: normalized logistic endpoints and monotonicity, invalid
settings, absolute window, full first iteration, constant-strength compatibility,
zero-tail exact path/confidence/RNG equivalence, resets between blocks, all three
penalty modes, max/sampled decoding, APD and profiling propagation, completeness,
one forward per iteration, and hosted app routing/API compatibility.
89 focused tests passed. Full suite: 578 passed, 4 skipped, and the same three
pre-existing training-config failures; no new failures.

Parent revision: `82e83e1d1f7fe6442ad3c4d068df08013999cbc7`. Deployed revision: `4742018079ff61b0b8d61e40232f51bf808902fc`.

## Live verification and initial comparison

Eight hosted cases passed at 1, 8 and 16 NFE. Constant-mode one-step and
sampling+APD eight-step outputs exactly match the previous deployment. Fading and
constant modes match at one NFE, preserving early strength. All outputs resolve
masks and streamed/reported model-forward counts match their configured budgets.
No extra model passes were introduced. The UI checkbox is verified ON by default.

This is one Amsterdam prompt, seed 1234, max length/block 32, top-k 100, T=1,
weight=1, risk penalty gamma=1, delay EOS OFF and early stopping OFF. It does not
establish that decay improves quality. In this check:

- At 1 NFE, fading and constant outputs are identical, as intended.
- At 8 NFE with sampled decoding+APD, fading produced more punctuation/conjunction
  repetition than constant strength. This is evidence against assuming the
  six-step schedule is always beneficial; the fade window may need tuning.
- At 16 NFE, both sampled and maximum-path decoders produce identical final text
  with and without fading for this seed/prompt.
- Later zero-strength iterations skip risk calculations. Server times were lower
  for fading in these paired longer runs, but timings are single trials and
  should not be interpreted as a stable speed benchmark. The cold one-step
  constant run is particularly unsuitable for timing comparison.

The constant option remains available for comparison. A broader prompt/NFE study
would be needed to choose the fade window or justify a quality recommendation.

## Recorded outputs

### constant_one_step

Amsterdam is the city of the Netherlands, and its history and its canals and canals and culture.

Model forwards: 1; server time: 647.6 ms.

### fade_one_step

Amsterdam is the city of the Netherlands, and its history and its canals and canals and culture.

Model forwards: 1; server time: 44.0 ms.

### constant_sampling_apd8

I can provide information about Amsterdam from all, including its history, its capital, attractions and landmarks and cultural attractions. What would you like to know?

Model forwards: 8; server time: 394.8 ms.

### fade_sampling_apd8

I can provide information about Amsterdam from all, including its history, its culture,, and, and and attractions. What would you like to know?

Model forwards: 8; server time: 366.8 ms.

### constant_sampling16

I don't have personal experiences or emotions, but I can provide you with information about Amsterdam, Netherlands. What would you like to know about it?

Model forwards: 16; server time: 808.3 ms.

### fade_sampling16

I don't have personal experiences or emotions, but I can provide you with information about Amsterdam, Netherlands. What would you like to know about it?

Model forwards: 16; server time: 654.6 ms.

### constant_viterbi16

Amsterdam is the capital and largest city of the Netherlands. It is known for its picturesque canals, historic architecture, art museums, and vibrant nightlife.

Model forwards: 16; server time: 705.8 ms.

### fade_viterbi16

Amsterdam is the capital and largest city of the Netherlands. It is known for its picturesque canals, historic architecture, art museums, and vibrant nightlife.

Model forwards: 16; server time: 583.0 ms.

