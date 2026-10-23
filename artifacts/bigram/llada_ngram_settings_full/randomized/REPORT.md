# Randomized BG+TG Viterbi: matched study extension

Adds one configuration to all 282 previously retained prompt/NFE cases (94 each open, coding and math). The seven historical arms are frozen; the combined eight-arm archive has 2,256 outputs. NFE 4, 8, 16, 32, 64, 128; max/block length 128; top-k 16; bigram weight 1; trigram relative weight .5; PMI count≥1/clip±2; trigram count≥2/clip±2; seed 42; no repetition penalty/APD/early stopping. Open answers delay EOS/EOT with strength 10; coding/math do not. All other settings copy the original BG+TG cases exactly.

## Findings

At noise scale .7, randomized Viterbi achieves almost the same aggregate score as exact sampling (0.543 versus0.544), with higher open quality (1.915 versus1.798), more coding passes (48 versus45), and fewer correct math answers (45 versus52). Deterministic BG+TG remains descriptively ahead overall (0.576). Paired uncertainty intervals overlap zero versus both BG+TG alternatives, so these data do not establish superiority or equivalence.

The fast recurrence is retained, with no clear additional total-time cost in the saved optimized comparison. The user adopted Gumbel Viterbi as standard temperature behavior to provide fast variation. This interface decision does not establish a quality improvement over deterministic decoding. Temperature 0 remains deterministic. To reproduce this arm: expanded BG+TG, exact sequence sampling OFF, temperature .7, all other settings as above; API evaluations can explicitly set randomized_viterbi=True.

## What temperature .7 means

Each denoising iteration adds independent unit Gumbel noise multiplied by .7 to editable candidate unary log-scores. Then the existing optimized deterministic Viterbi decoder selects a path with unchanged BG/TG transitions. Fixed tokens and candidate support remain unchanged; confidence uses original diffusion probabilities. Noise is redrawn each iteration, using the existing seeded RNG. During the experiment this was an explicit option, default OFF. The current LLaDA interface now uses it as standard temperature behavior; temperature 0 consumes no extra random numbers and reproduces deterministic decoding. Exact sequence sampling and randomized Viterbi are mutually exclusive.

**This is approximate perturb-and-MAP, not exact sampling from exp(S/.7).** A noise scale of .7 does not guarantee the same entropy or distribution as the exact .7 sampler. This study tests usefulness of that explicit setting. One seed per case cannot establish the full output distribution or optimal noise strength.

## Overall results

| Method | Open quality /3 | Coding passes /94 | Math correct /94 | Macro score |
| --- | --- | --- | --- | --- |
| Confidence T=.7 | 1.394 | 36 | 48 | 0.453 |
| Confidence T=0 | 1.319 | 45 | 46 | 0.469 |
| BG | 1.830 | 49 | 45 | 0.537 |
| BG + R | 1.819 | 48 | 53 | 0.560 |
| BG + TG | 1.957 | 49 | 52 | 0.576 |
| BG + TG + R | 1.979 | 48 | 50 | 0.567 |
| BG + TG exact sampling .7 | 1.798 | 45 | 52 | 0.544 |
| BG + TG randomized .7 | 1.915 | 48 | 45 | 0.543 |

## Open quality /3

| NFE | Cases | Confidence T=.7 | Confidence T=0 | BG + TG | BG + TG exact sampling .7 | BG + TG randomized .7 |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | 15 | 0.07 | 0.07 | 0.60 | 0.60 | 0.60 |
| 8 | 16 | 0.62 | 0.38 | 1.56 | 1.44 | 1.44 |
| 16 | 16 | 1.19 | 1.06 | 2.00 | 1.69 | 2.06 |
| 32 | 15 | 1.87 | 1.67 | 2.27 | 2.00 | 2.47 |
| 64 | 16 | 2.00 | 2.06 | 2.56 | 2.38 | 2.56 |
| 128 | 16 | 2.56 | 2.62 | 2.69 | 2.62 | 2.31 |

## Coding correct

| NFE | Cases | Confidence T=.7 | Confidence T=0 | BG + TG | BG + TG exact sampling .7 | BG + TG randomized .7 |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | 15 | 0/15 | 0/15 | 1/15 | 0/15 | 1/15 |
| 8 | 16 | 2/16 | 4/16 | 7/16 | 4/16 | 7/16 |
| 16 | 16 | 4/16 | 7/16 | 8/16 | 9/16 | 9/16 |
| 32 | 16 | 9/16 | 11/16 | 10/16 | 9/16 | 8/16 |
| 64 | 16 | 11/16 | 13/16 | 13/16 | 13/16 | 13/16 |
| 128 | 15 | 10/15 | 10/15 | 10/15 | 10/15 | 10/15 |

## Math correct

| NFE | Cases | Confidence T=.7 | Confidence T=0 | BG + TG | BG + TG exact sampling .7 | BG + TG randomized .7 |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | 16 | 1/16 | 5/16 | 5/16 | 6/16 | 4/16 |
| 8 | 15 | 7/15 | 6/15 | 9/15 | 8/15 | 8/15 |
| 16 | 16 | 9/16 | 8/16 | 11/16 | 11/16 | 8/16 |
| 32 | 16 | 7/16 | 7/16 | 9/16 | 8/16 | 8/16 |
| 64 | 16 | 12/16 | 9/16 | 9/16 | 9/16 | 8/16 |
| 128 | 15 | 12/15 | 11/15 | 9/15 | 10/15 | 9/15 |

## Interpreting the math difference

The exact sampler got 52/94 math answers correct, versus45/94 for randomized Viterbi: 10 cases changed from correct to incorrect, while3 changed from incorrect to correct. Some losses retain a correct setup and then choose a wrong digit/result (for example fraction_equation at NFE16 reaches5x=30 but answersx=-1; mean at NFE128 subtracts70-48 as20). Other losses are malformed low-NFE output or contradictory final answers. These are observed error patterns, not proof of a specific causal mechanism.

The .7 scale was a principled starting point from independent categorical Gumbel-max sampling, **not an empirically calibrated equivalence to the coupled sampler**. The exact sampler uses exp(S/.7); this method maximizes S+.7*sum(token-Gumbels). Overlapping sequences share token noises, so their perturbations are correlated and have a different distribution from independent sequence-level Gumbels. BG/TG tables are computed first; only unary token log-scores receive additive noise immediately before MAP. No transition probabilities or retention probabilities are perturbed.

A lower noise scale might reduce disruptive math changes, but this run cannot establish that .7 overshot, nor identify an equivalent exact-sampler temperature. Approximation bias and single-seed variation are alternative explanations. No noise-strength sweep was performed.

| Task | NFE | Exact sampler correct | Randomized correct |
| --- | --- | --- | --- |
| fraction_equation | 16 | True | False |
| pipes | 16 | True | False |
| percent_change | 4 | True | False |
| train | 16 | True | False |
| mixture | 4 | False | True |
| triangle | 64 | True | False |
| train | 32 | True | False |
| pipes | 4 | True | False |
| ages | 32 | False | True |
| mixture | 8 | False | True |
| mean | 4 | True | False |
| fraction_equation | 8 | True | False |
| mean | 128 | True | False |

## Paired uncertainty

Exploratory post-hoc comparisons on the same cases, using the existing prompt-cluster bootstrap (4,000 repeats). Repeated NFEs for a prompt stay in one cluster; missing cases remain matched. Intervals do not account for method selection after inspecting earlier results or manual grading uncertainty. Macro averages open grade/3, coding pass fraction and math answer-correct fraction equally.

| Randomized minus | Macro delta [95% CI] |
| --- | --- |
| Confidence T=.7 | +0.090 [+0.027, +0.150] |
| BG + TG | -0.033 [-0.078, +0.009] |
| BG + TG exact sampling .7 | -0.001 [-0.039, +0.037] |

## Timing

The randomized arm uses the optimized CPU MAP implementation. Historical deterministic/exact-sampler timings were collected before that optimization, at different times on shared ZeroGPU hardware. They are retained below for context, not a controlled measurement of randomization overhead. No additional model forwards are used.

| NFE | Historical BG+TG ms | Historical exact sample ms | Randomized BG+TG ms | Randomized selector ms |
| --- | --- | --- | --- | --- |
| 4 | 212 | 365 | 188 | 28 |
| 8 | 430 | 672 | 376 | 55 |
| 16 | 876 | 1257 | 697 | 95 |
| 32 | 1707 | 2445 | 1427 | 201 |
| 64 | 3340 | 4822 | 2735 | 369 |
| 128 | 6662 | 9664 | 5489 | 741 |

On the 14 cases overlapping the saved **optimized** K16 timing screen, deterministic generation averaged 1514.4 ms and randomized generation 1481.6 ms (-2.2%). These also ran at different times; small differences should not be attributed to noise generation alone.

## Validation and artifacts

Local implementation checks: 143 passed, six CUDA cases skipped on this CPU workstation. Checks include Gumbel transform/endpoints, seeded reproducibility and variation, zero-temperature equivalence without RNG consumption, fixed tokens, unperturbed confidence, and existing trigram/sampling/shared-control behavior. Hosted logs verify requested NFE and selector counts and complete outputs for every case.

Manual open/math reviews reuse the original rubric and exact-text judgments; new texts were shown without method/NFE labels. Math score 2 means correct answer but faulty/incomplete explanation; score 3 also requires correct working. Code uses the existing restricted executable tests. `reviews.json`, `code_checks.json`, `results.jsonl`, `combined_scores.csv`, `summary.json` and `EXAMPLES.md` preserve outputs and evidence.

Space revision: `67a9c62687fcd05f9f02ee4cfd580e3dda3e0822`. Only app.py and bigram.py changed; optimized trigram.py, model configuration and weights were retained. Deployment/source hashes and before/after diffs are saved beside this report. No conclusion here establishes general superiority beyond these prompts/settings.

## Seed-variation check

A separate check used seeds42,43,44 at NFE32 for the machine-learning explanation and Fibonacci coding task. Both produced three distinct text outputs. Seed42 is from the main study; the four extra runs are saved in diversity.jsonl and excluded from every main quality/timing metric. This demonstrates variation on these two prompts, not distributional equivalence or diverse-code correctness.
