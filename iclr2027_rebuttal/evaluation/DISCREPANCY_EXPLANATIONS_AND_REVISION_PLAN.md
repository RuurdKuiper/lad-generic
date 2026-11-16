## Explaining the largest discrepancies

This section adds a new offline analysis of the final saved answers. Python outputs were parsed and read, not executed. Counts below use the final selected cohort, rather than the older incomplete HumanEval diagnostics. [Reproduction script](../analysis/explain_final_discrepancies.py); [aggregate diagnostic results](../analysis/final_discrepancy_explanations.json). No new GPU jobs or score replacements were needed.

### 1. BYOD-Gemma HumanEval: a mixture of output allocation and real code errors

The fresh first 125 answers score 47/125 (37.6%); the added 39 score 2/39 (5.1%). All were generated in the adopted current cohort, so this particular difference cannot be attributed simply to replacing historical Gemma answers with fresh answers.

| Diagnostic | Fresh original 125 | Added 39 |
|---|---:|---:|
| Correct | 47 (37.6%) | 2 (5.1%) |
| Invalid Python after normal extraction | 30 (24.0%) | 11 (28.2%) |
| Unterminated triple-quoted string | 8 (6.4%) | 6 (15.4%) |
| Incorrect but syntactically valid | 48 | 26 |
| Mean specification length, Gemma tokens | 140.7 | 166.6 |
| Mean canonical function length, including specification/docstring | 198.4 | 249.1 |
| Canonical full function exceeds 256 tokens | 26 (20.8%) | 16 (41.0%) |
| Canonical answer body alone exceeds 256 tokens | 1 | 0 |

The output canvas is 256 tokens. All 39 added outputs retokenize to within eight tokens of that limit, but so do 124/125 original outputs. A full canvas is therefore not, by itself, an explanation for the drop: completed functions can be followed by repeated fences or a second copy of the function. Retokenized decoded text is only an approximate length diagnostic, not a stored generation-token count.

There is direct evidence of wasted output space in individual failures. HumanEval/126 (`is_sorted`) copies the specification and ends inside its docstring without reaching an implementation. HumanEval/127 (`intersection`) does the same. Six added outputs have unterminated triple-quoted strings. The increased specification length makes this mechanism plausible on more added questions. However, **all 39 canonical answer bodies fit within 256 tokens** if the specification is not repeated. We should describe an output-allocation failure, not claim that these questions are inherently impossible under the canvas.

Length also does not account for the **26 syntactically valid failures** among the added answers. For example, HumanEval/125 (`split_words`) checks commas before whitespace and uses the wrong alphabet parity, violating the stated behavior. HumanEval/128 (`prod_signs`) multiplies the actual integer values instead of just their signs; for `[1,2,2,-4]`, its implementation computes −144 instead of −9. These are real logic errors in extractable code.

**Supported explanation:** the added questions have longer specifications, some answers spend their canvas copying those specifications, and many completed implementations are wrong. **Still unresolved:** how much of the 32.47-point cohort difference each mechanism causes. The syntax-invalid rate itself rises only about four points, so syntax failures alone cannot explain the accuracy gap. A controlled no-docstring or longer-canvas condition could test the output-allocation hypothesis, but it would be a separate decoding/prompt ablation, not a silent replacement of these results.

### 2. HumanEval declines across models: shared item effects, not one universal backend failure

The final static audit gives the following syntax-invalid totals. Passing syntax does not imply passing tests. The counts are unchanged when parsing with Python 3.11 grammar instead of the local parser's default grammar; this remains a syntax check, not a new execution audit.

| Model | Invalid HumanEval programs / 164 | Invalid MBPP programs / 250 |
|---|---:|---:|
| BYOD-Gemma | 41 (25.0%) | 22 (8.8%) |
| BYOD-Llama 50k | 51 (31.1%) | 24 (9.6%) |
| Llama AR | 0 | 0 |
| Gemma AR | 1 (0.6%) | 0 |

Other final HumanEval syntax-invalid counts are BYOD-Qwen 61/164, BYOD-Ministral 52/164, BYOD-Llama 25k 57/164, and LLaDA 4/164. Qwen AR and Ministral AR have no syntax-invalid HumanEval programs in these final outputs. This supports a much larger syntax problem in the conversions, but the blanket manuscript statement that AR answers never have syntax errors needs qualification: Gemma AR has one.

For LLaDA, only one of the 32 failed added HumanEval answers is syntactically invalid; the other 31 are valid Python that fails the benchmark tests. Its drop is therefore not primarily a Markdown extraction or syntax problem. The manual review identified concrete type/API and edge-case errors. Its historical first 50 questions already scored 58.0%, versus 28.0% on questions 50–124, before the new cloud answers were added. That supports a question-composition contribution without proving a universal difficulty ordering.

Gemma AR's large final decline has an additional denominator explanation: its original 74.0% came from just 50 questions. Its 114 additions score 53.5%, resulting in 59.8% overall. The canonical answer body's median length increases from 112 characters on those original 50 to 168.5 on the additions. None of its final answers retokenizes near the intentional 1,024-token cap; only one is syntax-invalid. Longer specifications and more demanding code are plausible contributors, while output truncation is not supported as a general explanation for this AR decline. The historical subset was small, and its 74% point estimate should not be treated as the true whole-benchmark accuracy.

### 3. LLaDA and Gemma AR MATH: difficulty mix contributes, but does not reproduce the full drop

The original and added MATH halves have different level counts: 55 versus 69 level-4/5 questions. We checked whether this alone reproduces the score decline by applying each model's historical, level-specific success rates to the added half's level counts.

| Model | Correct on original 125, current scorer | Expected correct on added 125 if historical within-level rates held | Observed correct on added 125 |
|---|---:|---:|---:|
| LLaDA | 43 | 36.5 | 22 |
| Gemma AR | 75 | 69.9 | 55 |
| BYOD-Gemma, fresh cohort | 36 | 32.5 | 25 |

For LLaDA, this descriptive reweighting moves the expected added score from 34.4% to about 29.2%, while the observed added score is 17.6%. Difficulty labels therefore capture part of the discrepancy but do not account for all of it. Success rates also fall within levels; for example, level 3 goes from 10/25 to 5/27. These are small, noisy groups with different questions and potentially different topics. The table is not a causal decomposition or a guaranteed prediction.

The evidence does not support discarding the low answers. LLaDA's 18 earlier replay controls matched historical correctness, and the manual review found actual arithmetic, reasoning and code errors in new samples. Gemma AR's earlier ten-question backend probe yielded the same five correct and five wrong under eager and SDPA, with verified original normalization tensors. Thus the Qwen attention remedy is not established for Gemma AR. Remaining explanations include item composition within broad difficulty levels and ordinary model errors; unrecorded historical/runtime effects cannot be ruled out exhaustively. The current evidence does not establish one full cause.

### 4. BYOD-Gemma MBPP and HumanEval rerun gains: a real cohort difference, cause still open

On each task's original 125 IDs, the fresh Gemma run has 20 gains and five losses relative to the historical answers. That is +12 pp on the same questions, rather than an effect of adding questions. For MBPP, the historical/fresh code-scoring audit found no disagreements, and the current matched difference survives the nine-task correction. Original weights/tokenizer checks and selected repeat runs do not identify an incorrect loading path or an eager/SDPA remedy.

The most precise explanation we can give is **historical/current generation drift with verified source assets and a consistently selected fresh cohort**. Floating-point/backend differences in iterative denoising are a plausible mechanism, but the historical software/hardware state is incomplete and the causal mechanism has not been established. Do not describe this as a newly trained better model, a random-seed improvement, or a proven backend bug. Both fresh gains and fresh losses were retained.

The final MBPP increase is smaller than the rerun gain because the added questions score 38.4%, versus 48.8% on the fresh original IDs: the final result is 43.6%. Gemma AR's separate MBPP decrease is 74.0% on its original 50 versus 63.5% on 200 additions, giving 65.6%. Its historical 50 were a much smaller subset than the other models' 125; no new Gemma AR scoring or backend defect was established.

### 5. Qwen AR: the severe intermediate discrepancy has a tested remedy

The matched A100 probe isolated eager versus SDPA as the trigger for four selected arithmetic/code failures, holding the model, BF16, greedy decoding and other settings fixed. The bad eager texts reproduced; SDPA corrected all four. The final nine-task results consistently exclude the faulty new eager cohort. This is stronger evidence for a concrete operational fix than the unproven explanations for the remaining Gemma/LLaDA shifts.

The corrected Qwen AR HumanEval result is 133/164 (81.1%), up from the faulty intermediate 110/164 (67.1%). It remains below its original 83/95 (87.4%) because the 69 corrected added questions score 50/69 (72.5%). None of the final Qwen AR HumanEval programs is syntax-invalid. The original severe eager-runtime collapse and the smaller remaining original-versus-added gap are different phenomena and should not be conflated.

## Required changes to the original manuscript

This is an implementation checklist. The new evaluation is complete, but these manuscript edits have **not** all been applied. All listed numerical values include the completed v3 MATH presentation correction. The earlier follow-up is resolved; manuscript tables still need updating from the regenerated results.

### Completed scoring correction and remaining data propagation

- [x] Implement narrow numeric-escape and complete scalar-statement rules, plus reference-aware percentage comparison. Validate correct and wrong final answers and apply the policy uniformly to every model and both old/new cohorts. Preserve the v2 scorer/results and a per-item v3 change audit. [Completed correction](MATH_PRESENTATION_CORRECTION.md).
- [x] Regenerate selected outcomes/audit, this comparison, diagnostic summaries and paired macro intervals under v3; verify unchanged predictions and non-MATH flags.
- [ ] Propagate the corrected source to individual-interval/manuscript artifacts and numerical tables. Keep immutable raw predictions and the original workbook; write a versioned revised-results source rather than editing historical cells without a record.

### Table 3, abstract, main results and discussion

- [ ] Replace all ten common-harness model columns in Table 3 with final 250-question scores, or 164 for HumanEval, and recompute the equal-weight nine-task averages, bolding and underlining. Keep external published LLaDA results in their separate protocol column.
- [ ] State the actual dataset variants and denominators: MATH-500, GPQA-Main, sanitized MBPP, HellaSwag's labeled validation split, and full HumanEval. Explain that all models share the same fixed questions. The detailed ordering audit remains in internal records, as agreed with the author; do not introduce a claim of uniform random selection.
- [ ] Update the abstract in both `paper/iclr2027_conference.tex` and `paper/ABSTRACT.md`: the current Gemma/LLaDA averages are **52.43%/49.55%**, replacing **50.6%/51.9%**. Replace the old “within 1.3 points of LLaDA” statement with the observed **+2.88 pp** difference on the selected questions and appropriately scoped paired uncertainty. Do not turn it into superiority over all DLMs or a claim about every full benchmark.
- [ ] Retain “Gemma is the strongest BYOD conversion” for the current nine-task suite. Update the parent comparison: Gemma AR averages 62.73%, so its matched gap from BYOD-Gemma is **−10.30 pp**, with the current nominal paired 95% interval **[−12.33, −8.31] pp**. Other families also remain below their parents on the nine-task mean.
- [ ] Remove the claimed +0.5-point task-accuracy gain from doubling Llama training. Current means are **47.93% at 25k** and **47.80% at 50k**, a difference of **−0.14 pp**, with paired nominal 95% interval **[−1.81, +1.49] pp**. Four task scores rise and five fall. Say there is no clear task-accuracy benefit in this comparison; do not claim equivalence. Existing validation-loss and perplexity trends are separate measurements and are not invalidated by this accuracy result.
- [ ] Keep the main conclusion focused on feasible conversion across the four tested families. Neither more evaluation questions nor frozen base weights establish universal conversion of any model or isolate capability retention from the added adaptation stage.

The updated task profile still supports a useful distinction between multiple-choice tasks and mathematics/code. The following are differences between category means (each task weighted equally within its category), using the current scorer:

| BYOD model minus its AR parent | Five multiple-choice tasks | Two mathematics tasks | Two code tasks |
|---|---:|---:|---:|
| Gemma | +1.28 pp | −23.60 pp | −25.94 pp |
| Qwen | −6.48 pp | −38.20 pp | −46.26 pp |
| Ministral | +2.72 pp | −29.60 pp | −40.92 pp |
| Llama 25k | +2.96 pp | −20.00 pp | −26.91 pp |

These are descriptive task-score differences, not causal measures of knowledge retention or individually significant improvements. They give a clearer account of where conversion works relatively well and where it remains weak. Additional adaptation and method-specific output budgets remain part of the comparison.

### Correct the specific AR entries questioned by fC22

The [archived submitted manuscript](../baseline/iclr2027_conference.tex) and the recovered historical outputs are not identical. Some problems were unequal denominators; two submitted values also differ from the recovered compatible records. Do not explain all four discrepancies as merely a 125-versus-50 denominator issue.

| Entry | Submitted Table 3 | Recovered historical record | Final expanded result |
|---|---:|---:|---:|
| Gemma AR HumanEval | 74.0% | 37/50 = 74.0% | 98/164 = 59.76% |
| Qwen AR HumanEval | 89.0% | 83/95 = 87.37% | 133/164 = 81.10% |
| Ministral AR HumanEval | 94.0% | 107/125 = 85.6% | 135/164 = 82.32% |
| Gemma AR MBPP | 74.0% | 37/50 = 74.0% | 164/250 = 65.6% |

- [ ] Replace the submitted values and inconsistent blanket “125 per model” note; give explicit denominators. The working paper already corrected some historical entries, but final expansion values and notes still need propagating.
- [ ] Describe the correction as recovery from compatible per-question outputs plus expanded evaluation. The records do not establish exactly why the original spreadsheet contained 89%/94%; call them unsupported/stale submitted values rather than inventing a causal history.
- [ ] Archive the exact source revision, question IDs, model/checkpoint, settings, raw outputs and scoring version for each final cell, with an appropriate anonymous reproducibility artifact before claiming its public availability.

### Protocol, error analysis, uncertainty and figures

- [ ] Replace “planned expansion,” “results pending,” and the historical-only Table 3 caption with completed counts and the final provenance policy. Distinguish retained compatible outcomes from the fresh Gemma cohort and corrected Qwen additions.
- [ ] Document Qwen AR's SDPA backend and the pinned runtime/scoring requirements. Keep the intentional AR output caps (1,024 tokens; MMLU-Pro 2,048), and the recovered diffusion caps (including **64 for MMLU-Pro**, rather than the submitted 128). “Matched” must refer to question IDs/harness, not equal output budgets or equal compute.
- [ ] Add individual 95% Wilson intervals from integer counts and paired, within-task bootstrap intervals for the nine-task differences. Do not pool all questions as if they were one benchmark, compare overlapping before/final scores as independent, or imply ±1–2 pp precision from n=250. Distinguish these uncertainty estimates from the exploratory cohort-discrepancy tests in this internal report.
- [ ] Recompute the syntax-error appendix on final answers. For BYOD-Llama 50k, replace historical HumanEval 35/125 (28.0%) with **51/164 (31.1%)**, and MBPP 11/125 (8.8%) with **24/250 (9.6%)**. The paired Llama AR remains 0/164 and 0/250. Qualify any broader statement that AR outputs never have syntax errors, since Gemma AR has 1/164 HumanEval syntax failure.
- [ ] Add the supported HumanEval diagnosis: copying long docstrings sometimes prevents implementation, while many syntactically valid answers have real semantic errors. Make clear that output allocation is not a complete explanation and that a 256-token answer canvas is separate from the training total-sequence cap of 256.
- [ ] Regenerate benchmark radar panels and any derived task/average plots from the revised data source; update figure captions and embedded `figure_data.json`. The current figure-generation instructions still reference the historical workbook. Cross-check the abstract, Table 3, further-training section, discussion, appendix and `RESULTS_NOTES.md` for stale numbers.
- [ ] Keep open-generation perplexity-/diversity metrics, NFE sweeps, conversion-training time, adapter sizes and the right-context experiment unchanged unless independently re-evaluated. The added task answers do not constitute new evidence for those measurements. Likewise, the merged-model comparison remains a separate smaller historical evaluation, not automatically a 250-question merge result.

## How the additional data help answer the reviewers

### Concerns directly strengthened by the new evidence

| Concern / reviewers | New evidence we can use | What still needs doing before the response claims completion |
|---|---|---|
| **R01: implausible AR cells / provenance — fC22 W1/Q1** | Recovered actual counts and corrected values; all final HumanEval cells now share all 164 questions and MBPP cells share 250; preserved per-question outputs and scorer provenance | Replace manuscript entries/denominator notes and explain the two submitted-versus-recovered value differences transparently |
| **R02: 125 questions, no uncertainty, small LLaDA gap — all reviewers** | Doubled target coverage on eight tasks; full HumanEval; 21,640 selected outcomes; paired model contrasts with task-preserving bootstrap intervals | MATH presentation policy is now corrected; put regenerated counts/intervals in the paper and qualify that the other test sets were not all evaluated in full |
| **R02: alleged gain from 25k→50k — mNeh/dPsL/fC22** | Updated −0.14 pp difference and interval spanning zero | Withdraw the small positive accuracy claim rather than defend it; preserve separate loss/perplexity findings |
| **R08: poor mathematics/code performance — dPsL/fC22/mNeh** | Larger evaluations confirm the deficits; final syntax counts, manually checked math/code errors and separated runtime/scorer corrections make them better characterized | Acknowledge the actual losses and add error analysis; do not imply that correcting Qwen AR fixed BYOD's quality limitations |
| **R10: training/evaluation length mismatch — fC22 Q3** | Static evidence of wasted canvas on copied specifications, longer added HumanEval specifications, and the distinction between full-function and body-only lengths | State the plausible contribution without claiming a causal ablation; separately account for prompt-plus-answer length versus the training total-sequence cap |
| **R12: clarity and reproducibility — mNeh** | Uniform final denominators, explicit cohort rules, code/backend versions and reproducible aggregate analysis | Propagate the clarification to captions/methods and release the promised artifacts before claiming availability |

Current paired nine-task results give a concrete answer to “does proximity to LLaDA hold?” On the selected questions, BYOD-Gemma averages 52.43% versus LLaDA 49.55%; the **+2.88 pp** paired difference has nominal 95% interval **[+0.74, +4.98] pp**. State the protocol and item scope. This supports the practical comparison more strongly than the original point estimates, but is not evidence of universal dominance, identical training exposure or equality of open-generation quality.

### Concerns the extra questions do not resolve

| Concern | Accurate scope of our response |
|---|---|
| **R03: matched LAD/simple conversion control** | More precise scores do not replace a control. Use the LAD/BYOD contribution clarification, and either perform a matched control separately or retain the limitation. |
| **R04/R11: rank, modules, label alignment and loss weights** | The same checkpoints were evaluated more extensively; these are not new training ablations. No new optimum or mechanistic conclusion follows. |
| **R05: additional adaptation and benchmark-training exposure** | We can clarify that all parents are already instruction-tuned and retain the documented source precedents, but added test questions do not isolate the diffusion objective or match additional AR training. |
| **R06: unequal output budgets** | The recovered settings and fixed shared questions improve transparency. They do not supply a matched-length or matched-compute sensitivity experiment. |
| **R07: parallel decoding, reduced-NFE task accuracy and speed** | These runs still use full NFE with one transferred token per step. They do not demonstrate benchmark quality at reduced NFE or controlled latency/throughput gains. |
| **R09: useful infilling/constrained generation** | The expanded suite remains the same nine standard tasks; it is not a new practical infilling evaluation. |

### Draft response material grounded in completed work

**Sample size and uncertainty:** “We thank the reviewers for requesting a larger evaluation. We have expanded the suite to 250 unique questions per task where available and evaluated the full 164-question HumanEval set. All ten model configurations use the same fixed questions for each task, giving 21,640 evaluated model–question pairs. We have computed paired uncertainty for the task averages and will include the counts and intervals in the revised tables. On these questions, BYOD-Gemma averages 52.43% and LLaDA 49.55%, with a paired difference of +2.88 percentage points (nominal 95% CI +0.74 to +4.98).” These aggregate numbers include the completed v3 scoring correction.

**Provenance correction:** “We thank the reviewer for identifying the inconsistent AR entries. Recovering the per-question records showed that some historical cells used fewer than 125 questions, while the submitted Qwen and Ministral HumanEval values also differed from the compatible saved results. We have now evaluated every model on all 164 HumanEval questions and on 250 MBPP questions, with explicit integer counts and saved provenance. The final AR HumanEval scores are 98/164 for Gemma, 133/164 for Qwen and 135/164 for Ministral; Gemma AR MBPP is 164/250.” Add exact manuscript references once the corresponding tables are updated.

**Longer training:** “The larger evaluation changes our earlier interpretation of the 25k-to-50k result. The means are now 47.93% and 47.80%, respectively, and the paired interval for their difference includes zero. We therefore no longer claim an accuracy improvement from this longer run. Its validation-loss and perplexity measurements remain separate observations.” These averages include the completed v3 scoring correction.

**Code quality and length:** “The additional evaluation confirms that mathematics and code remain important limitations. We inspected the failures and separated scoring/runtime defects from model errors. On the fresh Gemma HumanEval cohort, some outputs exhaust the canvas while copying the specification, while many complete functions contain genuine logic errors. We will add these findings and qualify the possible role of output length; we have not established that a larger generation budget alone resolves the gap.”

These passages describe completed evaluation and planned manuscript edits separately. They do not promise new controls, ablations or inference experiments. Use the added evidence to answer the criticism directly, rather than relying on other papers' reporting omissions as the main defense.
