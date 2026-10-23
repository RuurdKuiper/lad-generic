# Tunable APD aggressiveness on LLaDA

Live only on [Ruurd/llada-8b-instruct](https://huggingface.co/spaces/Ruurd/llada-8b-instruct).
APD remains OFF by default. Enable it to adjust **APD aggressiveness**, range
0–1 with step 0.05 and default 0. The slider is disabled while APD is OFF.
The API parameter is `apd_aggressiveness`, default 0; the standard denoise and
streaming interfaces both accept it.

## Rule

`threshold(t, a) = original_cosine_threshold(t) * (1-a)`.

| Aggressiveness | Start threshold | End threshold |
|---|---:|---:|
| 0 | 0.90 | 0.50 |
| 0.25 | 0.675 | 0.375 |
| 0.5 | 0.45 | 0.25 |
| 0.9 | 0.09 | 0.05 |
| 1 | 0 | 0 |

The 15% warmup and cosine shape are unchanged. A one-step block still uses the
end threshold and final cleanup. More aggressive settings commit lower-confidence
predictions, which may reduce model passes while sacrificing refinement/quality.
At 1 all finite-confidence pending rows are eligible, so normal finite model
outputs complete each block in one forward. Non-finite scores still use the
existing safe fallback. Fixed rows, ending-delay rules, MASK validity fallback,
forced progress, final-step cleanup and early completed-block exit are preserved.
Confidence remains the selected token's full-vocabulary model probability,
without top-k renormalization or sequence temperature. Token scoring is unchanged.

Works with all existing decoding strategies, sequence sampling, repetition-risk
and the unchanged six-iteration repetition fade. No extra model forwards or
training. Other Spaces were not updated. APD OFF ignores aggressiveness; a=0
reproduces the old APD schedule, paths and status text exactly.

## Local validation

29 new tests pass: threshold scaling at lengths 1/8/64/128, exact zero identity,
expanded same-step commitment sets, fixed rows, invalid-value rejection before
model calls, full-vocabulary confidence, ordinary/random/conditional/PMI/
repetition/path-margin/AR strategies on adapter and native backends, OFF ignoring
the control, ending/progress/final cleanup guards, and composition with joint-risk,
sequence sampling and repetition decay. Controlled uniform-confidence runs reduce
from six to two forwards across two blocks at a=0.9, with no extra model calls.
101 focused tests passed. Full suite: 607 passed, 4 skipped, same three pre-existing
training-config failures, no new failures.

Parent revision: `4742018079ff61b0b8d61e40232f51bf808902fc`. Deployment: `24666c5423a21f56df4cf18413276e6eb7dd5ef6`.

## Live validation and initial tradeoff check

Ten live cases passed: slider range/default/inactive state, unchanged output with
APD OFF despite a=1, exact previous output at a=0, completeness, correct streamed
model-forward counts, composition with sequence sampling/risk/fading, and one
forward per block at a=1. The two compatibility cases use their prior saved
settings; the matched comparisons below use the same Amsterdam question,
max length/block 32, NFE budget 16, T=1, top-k=16, seed 1234, delay EOS OFF and
early stopping OFF. Risk sampling uses weight=1, gamma=1, risk ON, fade ON.

| Method | Aggressiveness | Actual forwards | Server ms |
|---|---:|---:|---:|
| standard | 0.0 | 16 | 468.7 |
| standard | 0.5 | 16 | 471.1 |
| standard | 0.9 | 3 | 88.2 |
| standard | 1.0 | 1 | 30.2 |
| risk_sampling | 0.0 | 16 | 693.2 |
| risk_sampling | 0.5 | 14 | 707.4 |
| risk_sampling | 0.9 | 5 | 250.2 |
| risk_sampling | 1.0 | 1 | 68.0 |

These are single-trial functional checks, not a latency or quality benchmark.
Fewer model passes do not guarantee lower observed latency: risk sampling a=0.5
used 14 instead of 16 passes, but server time was slightly higher in this trial.
For standard sampling a=0.5 did not reduce the forward count. At a=0.9 both
methods finish much earlier but produce visibly degraded short/awkward text.
At a=1 both produce poor one-pass outputs. Risk sampling a=0.5 is readable in
this example, while a=0 repeats landmarks/attractions, but one prompt/seed cannot
establish a generally better setting. Default zero is retained for that reason.

Aggressiveness monotonically lowers the threshold and expands eligibility for
identical confidences. It does not guarantee monotonically decreasing pass counts
or quality across complete runs because different commitments change later logits.
The repetition fade was not changed by this task.

## Recorded outputs

### apd_off_ignores_control

Amsterdam is the capital and largest city of the Netherlands. It is known for its picturesque canals, historic architecture, art museums, and vibrant nightlife.

Actual model forwards: 16.

### zero_preserves_previous

I can provide information about Amsterdam from all, including its history, its culture,, and, and and attractions. What would you like to know?

Actual model forwards: 8.

### standard_0.0

I don't have personal experiences or emotions, but i can provide information about amsterdam based on my and and knowledge data the to available about for.

Actual model forwards: 16.

### standard_0.5

I don't have personal experiences or emotions, but i can provide you with information about am about am, or anything else you'd like to know.

Actual model forwards: 16.

### standard_0.9

Amsterdam is the city capital of Netherlands, located on the

Actual model forwards: 3.

### standard_1.0

Am! is capital city you of., It., a its and city history

Actual model forwards: 1.

### risk_sampling_0.5

I don't have personal experiences or emotions, but I can provide you with general information about Amsterdam, including its history, culture, and notable landmarks.

Actual model forwards: 14.

### risk_sampling_0.9

Isterdam is the city of city lights, canals, and canals.

Actual model forwards: 5.

### risk_sampling_1.0

I'm is the city of city.,, and its and the canals the history of the history. history.

Actual model forwards: 1.

### risk_sampling_0.0

I can provide information about Amsterdam, including its history, culture, landmarks, landmarks, and attractions and interesting attractions. What would you like to know?

Actual model forwards: 16.

