# Evaluation discrepancy register

Last updated: 15 November 2026. This register records known issues and the adopted reporting policy; it does not certify that every possible problem has been excluded.

**Final completion supersedes older progress below:** all 21,640 selected outcomes are complete, covering ten configurations, eight tasks at 250 questions each, and all 164 HumanEval questions. The [final comparison report](FINAL_EVALUATION_STATUS.md) is authoritative for current counts, scores, cohort decomposition and uncertainty. The three MATH presentation cases are now corrected under v3, uniformly rescored and [documented with exact changes](MATH_PRESENTATION_CORRECTION.md); the previous flags/scorer remain archived. The older running/partial-cohort paragraphs below are execution history, not current status.

**Latest execution decision:** HumanEval correction continues (Qwen 164/164 complete, Gemma 47/164 at the verified startup snapshot). The author subsequently authorized the remaining samples in parallel with generous hard limits. Two [disjoint continuation queues](PARALLEL_COMPLETION.md) now run alongside HumanEval, creating three GPU instances total. Combined new cap $25.50 / ten GPU-hours; cumulative compute upper bound $103.260949 (approximately €93.43 at the recorded ECB reference rate), within the original €100 budget. Earlier benchmark controllers remain stopped. Do not interpret the eight-task average as a completed nine-task result.

## Current result-selection decision

The user chose the **fresh BYOD-Gemma cohort**, including its initial 125, after reviewing its differences from the historical data. Apply this uniformly to every rerun task, including regressions as well as gains. Do not choose the better answer per question or selectively adopt only improved tasks. HumanEval currently remains historical in selected reports until its complete fresh correction is available; it is now running rather than deferred.

For MBPP, the adopted result is **74/156 (47.44%)**: 61/125 on the fresh initial questions, plus 13/31 added. Historical 46/125 and the intermediate retained-original combination 59/156 are preserved separately. Historical-to-fresh comparison is **rerun plus expansion**, not an isolated sample-size effect.

Current assembly policy: `user_selected_fresh_gemma_and_corrected_qwen_sdpa_v2` in [assemble_results.py](assemble_results.py). Known erroneous eager Qwen AR answers are excluded regardless of correctness; verified historical Qwen answers remain reusable and new replacements require SDPA provenance. MATH is rescored uniformly for baseline and expanded results with the pinned final-answer verifier.

## Issue status

| Issue | Evidence / action | Status |
| --- | --- | --- |
| Qwen AR eager generation degradation | Matched probe corrects known failures with SDPA; eight tasks reached 250 questions and corrected HumanEval is 133/164 (81.10%). | **Fixed and complete** for all nine Qwen AR tasks. |
| BYOD-Gemma historical replay mismatch | Three disputed texts repeat exactly in the current environment and are unchanged across tested backends. Original weight/tokenizer checks match. Fresh MBPP rerun has 20 gains and 5 losses over the historical initial 125. | Controlled through consistent fresh-cohort selection. Exact historical cause remains **open**. |
| Missing symbolic MATH verifier | GPU requirements omitted the dependency, rejecting equivalent fractions, equations and other final forms. Pinned verifier, added dependency guard and final-answer-only comparison; uniformly rescored all selected models. | Scoring fix implemented and tested; raw flags retained for audit. Old frozen report files are superseded for scoring. |
| Gemma AR MATH decline | Corrected scores are 74/125 (59.2%) → 129/250 (51.6%). Matched backend probe gets the same five correct/five wrong with both backends; 169 initial norm tensors match. Added subset has more level-4/5 questions and inspected answers contain real algebra mistakes. | Known scoring defect fixed. Remaining decline retained as observed; full causal decomposition is **not established**. |
| BYOD-Gemma MBPP increase | CPU audit reproduces all 281 saved code scores; 250/250 canonical solutions pass. Historical and fresh initial scores differ, while added questions score 13/31. | No scoring defect found. Cohort choice and reporting description now explicit. |
| HumanEval decline / short diffusion answers | CPU audit found no common harness defect. All models now have 164 selected outcomes, including corrected Qwen and fresh Gemma. Actual code errors and short diffusion outputs remain. | **Correction complete**; model-quality limitations and historical environment drift are not thereby eliminated. |
| Unfinished sample targets | Older controllers stopped: original for replay review, corrections at budget limit. Two new disjoint queues reuse all saved selected outcomes and generate the **1,658 non-HumanEval outcomes missing at submission**. | **Running**, with durable checkpoints and combined hard time/cash caps. No duplicate reruns scheduled. |
| Final aggregate tables and uncertainty | Nine-task summaries are regenerated with complete selected HumanEval cells. Some other task targets remain unfinished; historical-to-fresh Gemma comparisons include environment changes. | Current nine-task descriptive means available; final full-target tables and paired uncertainty remain **pending**. |

## Evidence locations

- [Gemma MATH/MBPP investigation](gemma_math_mbpp_investigation.md): score corrections, CPU/GPU diagnostics, counts, source revisions and limitations.
- [Qwen investigation](qwen_investigation.md), [Gemma replay investigation](gemma_replay_investigation.md), [HumanEval investigation](humaneval_investigation.md).
- [Correction run and restart instructions](CORRECTIONS.md) and [original campaign](CAMPAIGN.md): immutable inputs, budgets, checkpoint behavior and jobs.
- [Current parallel completion](PARALLEL_COMPLETION.md): three-GPU execution layout, exact queue splits, combined caps, current job links and complete result-assembly command.
- [Change history](../changes.md) and [rebuttal draft](../rebuttal.md): latest author decision and internal manuscript-work notes.
- Original backup: `../results_before_expansion/2026-11-08/` (selected predictions plus original artifacts and hashes).
- Private raw cloud data: Hugging Face dataset `Ruurd/iclr2027-rebuttal-eval`, under `campaigns/<plan-id>/` and `diagnostics/`.
- Current local derived predictions: `generation_diagnostic/nov15_gemma/assembled_results.jsonl`.
- Current machine-readable audit: `generation_diagnostic/nov15_gemma/assembled_audit.json` (policy ID, source revision, scorer hash, prior/new flags and task summaries).
- Archived previous selection: `generation_diagnostic/nov15_gemma/retained_original_policy_v1/`. Unchanged downloaded raw snapshot: `generation_diagnostic/nov15/`.

Raw/derived per-question files remain ignored by Git because they contain private benchmark material. Their local existence and the private Hub data do not mean the working notes have been committed or published.

Regenerate the current derived audit with `.venv/bin/python iclr2027_rebuttal/evaluation/assemble_results.py`. Final selection tests explicitly verify that a fresh wrong answer replaces a historical correct one when the fresh cohort is selected, preventing selection by accuracy.
