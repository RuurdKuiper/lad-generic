# LLaDA added-sample check — 15 November 2026

Manually inspected 12 newly generated answers: two saved failures and one saved success for each of MATH, GSM8K, MMLU-Pro and HumanEval. Selection used a fixed seed of 20261115 within those groups, before reading their contents. This deliberately checks both scoring outcomes; it is not a random sample for estimating accuracy or an exhaustive manual audit. All 12 saved decisions agree with the manual inspection.

Raw question/reference/output packets and machine-readable checks are retained locally in ignored `llada_manual_check/`. Code answers were read and traced, not executed on the laptop. No GPU jobs were launched and no predictions or benchmark scores were changed.

## Manual findings

Indices below are zero-based positions in the frozen evaluation manifest, not necessarily the original dataset's task identifier.

| Task | Sample index | Saved score | Manual check |
|---|---:|---|---|
| MATH | 172 | Fail | Fourth/eighth sequence terms are 200/500, so the sixth is their mean, 350. Output incorrectly subtracts 7d−3d as 3d and concludes 300. Explicit final answer is wrong. |
| MATH | 128 | Fail | Walking four miles every third day gives a minimum nine walks in a 28-day February, hence 36 miles. Output incorrectly evaluates 28/3 as 7 and concludes 28 miles. |
| MATH | 196 | Pass | The requested expression equals 441+798+361=1600, which matches the final answer. Intermediate arithmetic in the response is inconsistent; the benchmark scores the final answer, not every reasoning step. |
| GSM8K | 227 | Fail | Burrito plus extras and upgrade cost 14; after a 5 gift card, 9 remains. Output adds the costs as 15 and returns 10. The numeric answer was extracted correctly. |
| GSM8K | 240 | Fail | Robert has 27 candies, James 33 and John 54, giving a difference of 21. Output computes 27+6 as 30 and returns 24. |
| GSM8K | 156 | Pass | Monthly bananas total 700; two months require 1400. Output and final numeric answer are correct. |
| MMLU-Pro | 194 | Fail | The coefficient of z^-1 in z²sin(1/z) is −1/6; the contour integral is −πi/3, giving option A (approximately −1.047). Output incorrectly calls this an Airy function and chooses B. |
| MMLU-Pro | 161 | Fail | 196 g NaCN is 4 mol; the stated reaction yields 4 mol gas, or 89.6 L at STP, option F. Output chooses E (22.4 L). |
| MMLU-Pro | 211 | Pass | Output identifies Phobos and Deimos and chooses D. Extra text after the answer label does not cause a false failure. |
| HumanEval | 138 | Fail | For the sum of four positive even integers, the generated implementation calls `itertools.combinations` with an invalid `repeat` keyword and an integer rather than an iterable. It cannot correctly return True for the required n=8 case. The source code is present and extractable. |
| HumanEval | 131 | Fail | The odd-digit product function starts at 1 and never changes this when all digits are even. It returns 1 for 2468, whereas the specification and a supplied test require 0. |
| HumanEval | 133 | Pass | The implementation applies ceiling to each element, squares it and sums. This agrees with the reference and supplied tests, including negative and fractional inputs. |

## Protocol and scoring checks

All 2,164 selected LLaDA records have saved generation settings matching the frozen per-task protocol: deterministic temperature-zero sampling, the prescribed output lengths and NFE, and the same masking/EOS options. Question/target identities are preserved by the frozen fingerprints. This does not prove every historical software/hardware detail is identical.

The existing startup replay file contains 18 LLaDA controls: all 18 match historical correctness and 15 have byte-identical output. This is supporting evidence against a broad generation regression, not proof that no environment effect is possible.

Recomputed scoring on all 375 added non-code answers across MATH, GSM8K and MMLU-Pro: **zero mismatches** with the saved scores. The machine-readable checks contain the exact selected-results hash. This checks stored flags against the current scorer, rather than independently proving every scorer decision. The manual examples above provide the independent answer checks. HumanEval findings here are static manual checks, not a newly executed code audit.

## What the lower totals reflect

| Task | Original subset | Added subset | Combined |
|---|---:|---:|---:|
| MATH | 43/125 (34.4%) | 22/125 (17.6%) | 65/250 (26.0%) |
| MMLU-Pro | 53/125 (42.4%) | 39/125 (31.2%) | 92/250 (36.8%) |
| GSM8K | 81/125 (64.8%) | 68/125 (54.4%) | 149/250 (59.6%) |
| HumanEval | 50/125 (40.0%) | 7/39 (17.9%) | 57/164 (34.8%) |

The inspected failures are genuine wrong answers or invalid implementations, rather than correct answers lost by formatting or extraction. No scoring correction follows from this check. The evidence does not establish that the whole decrease is random fluctuation or that later questions are intrinsically harder. The added items differ from the original items, and benchmark ordering/composition can matter. In particular, MATH's supplied difficulty labels show 69 level-4/5 items in the added 125, versus 55 in the original 125. This is evidence of a different difficulty mix that may contribute, not a quantified explanation of the full decrease. Keep that distinction when interpreting this small diagnostic review.
