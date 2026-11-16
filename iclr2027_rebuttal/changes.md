# Decisions, evidence, and manuscript changes

Status: workspace and evidence-backed response planning prepared; no scientific manuscript edits or new experiments completed. The author selected a first-stage target of 250 total unique items/task (full sets below 250), then budget-contingent expansion of Gemma/Gemma AR/LLaDA and an emphasis on accessible cross-family mask-only conversion. Execution details and other experiments remain open. Issue definitions and reviewer coverage are in [review_summary.md](review_summary.md).

## Decision tracker

| Issue | Decision | Evidence needed | Likely manuscript location |
|---|---|---|---|
| R01 | Open | Cell-to-run provenance, denominators, item IDs, metric definitions | Table `tab:accuracy`; derived figures, abstract, results |
| R02 | Expand toward min(250, available); execution pending | Paired benchmark outcomes, verified variants/counts and actual Wilson/paired intervals; see `sampling_plan.md` | Task evaluation; accuracy table; training-duration discussion; inference appendix |
| R03 | Open | Matched LAD/simple control, data and hardware budgets | Related work; method; baseline evaluation; new results table |
| R04 | Provisional rank/resource response added; final fresh-1024 endpoint pending | Matched 25k loss trade-off; measured update times; adapter-state counts. Peak VRAM unrecorded; module/LR explorations not a systematic sweep | Conversion method; ablation results; limitations |
| R05 | Draft clarified; paper/audit pending | Instruct-parent provenance; overlap audit; descriptive gap interpretation; matched AR control acknowledged as future work | Training mixture; evaluation; retention/conversion-gap claims |
| R06 | Open | Matched MMLU-Pro output limits; truncation and scoring | Tables `tab:diffusion-inference` / `tab:ar-inference`; accuracy table |
| R07 | Open | Reduced-NFE task accuracy; controlled timing | Evaluation protocol; practical performance results |
| R08 | Open | Existing error/quality evidence; any tested improvements | Results; code-error appendix; discussion; limitations |
| R09 | Open | Useful capability task and quality/latency comparison | Bidirectional test section or separate capability experiment |
| R10 | Open | Prompt+answer token lengths and truncation; controlled length comparison if feasible | Training/inference configuration; error analysis; limitations |
| R11 | Open | Contribution statement; optional label-shift/loss-weight controls | Related work; objective; discussion |
| R12 | Open | Final terminology and protocol consistency check | Table captions, sample-count descriptions, cross-references |

## Evidence record template

For a selected issue record: decision and rationale; exact training/evaluation configs; checkpoint and dataset versions; task/split/sample IDs; saved outputs and denominators; scoring and uncertainty procedure; measured hardware/time; limitations; resulting manuscript locations; corresponding response text. Mark unperformed experiments as proposals.

## Completed-change log

| Date | Change | Verification |
|---|---|---|
| 2026-11-08 | Created isolated rebuttal workspace, preserved original reviews, formatted reviews, synthesized issues, researched response format, drafted response structure, and copied local paper source/dependencies | Original attachment copied verbatim; initial paper hashes archived in `baseline/manifest.json` |
| 2026-11-08 | Expanded response draft with LAD inheritance/objective table, qualified data-exposure argument, source checks, benchmark precision plan and explicit remaining-work IDs | Primary sources in `literature_notes.md`; reproducible planning script/CSV in `analysis/` |

No issue is marked resolved. Build validation is recorded in [validation.md](validation.md).

## Open-work IDs in the response draft

| Work IDs | Issue coverage | Status |
|---|---|---|
| L1 | R03/R11: contribution clarification and LAD table in paper | Draft prepared; manuscript edit pending |
| L2–L4 | R03/R04/R11: matched control, rank/modules, objective controls | Proposed; experiment selection open |
| D1–D4 | R05: historical dataset, overlap audit, claim qualification, possible AR control | Pending |
| E1–E3 | R01/R02/R06: score provenance, frozen IDs/variants, MMLU-Pro budget | Pending; prerequisite to expanded comparisons |
| E4 | R02: pilot cost and expanded evaluation | Author requested 250 total/task first; priority-trio expansion if budget remains; not launched |
| E5–E7 | R02: actual Wilson/paired intervals and propagated results | Pending item-level evidence |
| U1–U5 | R07–R10: useful task, failure analysis, reduced NFE, latency and length audit | Open; separate documented experiments from explanatory limitations |

## Author training-data response incorporated

Preserved the latest attachment in `author_notes/training_data_response_original.txt`. Expanded R05 and the fC22 response mapping with the supplied reasoning, four-source table, computed mixture proportions and d1's explicit benchmark-training precedent. Qualified shared-source overlap, documented current Tulu filtering, and retained D1–D4 as open historical-data/interpretation/control work. This changes response planning, not the scientific manuscript or experiment status.

## Training-time attribution clarified

Added a footnote to the LAD/BYOD comparison attributing the shorter reported times primarily to implementation efficiencies, including frozen-backbone FP8 execution. Used the manuscript's precise terminology: HYBRID FP8 execution with BF16 master weights. Included the author's report that the completed precision ablation showed small performance changes, with a placeholder for its settings, results and table reference. L1 now tracks recovery of that existing evidence; no new ablation is assumed necessary. The scientific manuscript remains unchanged.

## Current evaluation plan and reporting audit

The author selected 375 total unique questions/task, retaining the first 125 where protocol and provenance permit. Smaller selected sets are completed in full. This supersedes the earlier 500-item proposal: 3,046 total / 1,921 additional per model. Added a ten-paper reporting audit with explicit counterexamples to blanket sample-count omission, and a response emphasizing concrete expansion and paired macro-average uncertainty. GPU preference is an unattended rental; options are documented separately. No rental or evaluation was launched.

## €100 compute budget

Recorded the author's approximately €100 total budget in `gpu_options.md`. Recommend a ~$75 compute cap, a small timed pilot, and prioritization of paired BYOD-Gemma / Gemma-AR / LLaDA evaluation rather than promising the ten-column expansion. Provider choice and achieved coverage remain pending; no GPU has been rented and no evaluation run has started.

## Evaluation breadth contextualized

Added a general-response paragraph counting ten main-table model/checkpoint configurations across all nine tasks (90 cells), with the distinction between full-suite task coverage and full-dataset evaluation. Added `model_breadth.md` comparing LAD, LLaDA, Dream, DiffuLLaMA and DiffuCoder, separating common-protocol/author-evaluated configurations from imported scores. This supports substantial four-family coverage, not an exceptional model-count or total-compute claim. Nominal question totals remain subject to the denominator audit. No scientific manuscript or experiment changes were made.

## Instruction-tuned-parent clarification integrated

Updated the shared R05 answer and fC22 mapping: all four parents are released instruction-tuned checkpoints; the conversion gap is the descriptive change after additional adaptation plus conversion, not an isolated diffusion-objective effect. Added Qwen2.5/Llama/Gemma 2 report citations and the official Ministral card. D3 tracks the corresponding manuscript wording; D4 now tracks the limitation and future-work statement, rather than implying a new matched AR training run is required for this response. This clarification does not mark the historical data audit or scientific manuscript edits complete.

## Latest plan: 250 first, priority-trio expansion second; current CIs calculated

This supersedes the 375-item first-stage plan. Stage 1 targets 250 total/task across ten main-table configurations, preserving the first 125 only when verified/reusable, and all 164 HumanEval items. Sanitized MBPP uses 250/257. Stage 1 adds 1,039/model (10,390 across ten columns). If budget remains, expand matched IDs for Gemma/Gemma AR/LLaDA; a subsequent 375 cap would add 2,646 evaluations across that trio. The €100 budget and pilot still apply.

Calculated current approximate unadjusted macro CIs from manuscript Table 3 under n=125/task and independent-item/task assumptions. Seven columns are arithmetically compatible; Gemma/Qwen/Ministral AR CIs are withheld because their denominators remain unresolved. Added reproducible script, CSV, JSON and method/provenance document. Found workbook legends/comments supporting a mixed-history audit, plus differences from manuscript cells. No raw paired outcomes were recovered and no paired-difference CI is claimed. No empirical issue is marked resolved solely by this conditional calculation.


## 8 November: recovered reruns and evaluation preparation

- Author confirms longer AR limits are intentional. Preserve 1,024 tokens (2,048 for MMLU-Pro); do not queue matched-output reruns. Correct diffusion MMLU-Pro documentation to the recovered 64-token setting.
- Latest compatible prediction per exact model/task/prompt/target takes precedence, independent of score. Partial reruns can use compatible older predictions for unchanged questions. Preserve all original files.
- Corrected working-paper HumanEval Qwen AR to 83/95 (rounded .874) and Ministral AR to later 107/125 (.856), propagating equal-weight averages to .714 and .635. Gemma AR HumanEval and MBPP remain 37/50 (.740), with explicit denominators. Recorded-score provenance remains pending uniform rescoring.
- Historical macro intervals now use actual recovered denominators for all ten columns. Initial GPQA 124 count was an audit reader error caused by a Unicode line separator inside a JSON string; physical newline parsing confirms 125 and zero invalid records.
- Figure files still reflect the submission-era data. Regenerate benchmark plots after final scoring/expansion; the working PDF is not ready for submission.
- 250-target queue: 2,164 unique items/model, 11,070 compatible historical generations, 10,570 new generations across ten columns, subject to checkpoint/pilot verification. Reused outputs will be rescored, not regenerated merely to change a score parser.
- Paid execution requires explicit user permission. Pilot package uses the configuration-identical published Gemma checkpoint for replay verification; full weight identity with the Drive original remains unverified, so full evaluation is blocked until resolved. Original adapters must not be silently replaced.


## 8 November: separate backup and approved credit test

Created `results_before_expansion/2026-11-08/`: 11,070 selected full records in 90 model/task groups, 197 copied original source artifacts, actual counts, run provenance and 295 verified file hashes. Independently verified every selected prediction against its copied original source. Files are read-only and private; both successful and failed answers are preserved. Original Drive files are unchanged.

The user approved the pilot, then specified $4.95 credits and Gemma-first continuation. After explicit cancellation approval, the first submitted Job was cancelled. Its attached log exposes an HTTP 429 caused by our excessive checkpoint commit frequency, before any new GPU generations. Preserved 2,540 saved rescored outcomes; fixed upload throttling and backoff. A CPU wait/staging handoff is used to avoid spending A100 time waiting for the commit window. The replacement A100 is capped at 110 minutes, with conservative combined compute ceiling $4.890069 including prior usage and CPU wait. Ten offline checks pass. Full paper results remain pending; partial pilot outputs must not replace complete benchmark tables.


## Continued resumable campaign after added credit

The user authorized all remaining samples as far as possible and explicitly requested interruption-safe continuation. Started a private cloud controller and a single A100 worker with four-hour provider blocks, cumulative conservative $75 compute cap including prior tests, and checkpoint-aware automatic continuation after normal block completion. Funding/runtime/cancellation/replay failures stop for review; `campaign.py resume` resumes the same queue and budget once the interruption is resolved. Imported 3,268 saved scored outcomes (728 new generations) after validating unchanged fingerprints, settings and source code. Fifteen offline checks pass.

All five original Drive adapters are copying/staging in parallel with SHA-256 manifests, including distinct Llama-50k. BYOD models are deferred until verified originals are available; published configuration equality is insufficient. The cloud campaign starts with a short LLaDA timing batch, then rotates up to 128 new generations/model according to completed coverage. Source staging is a one-time local operation and needs the laptop awake; cloud execution does not. Up to approximately two minutes of unsynced work may be repeated after a hard kill, while uploaded answers are skipped.

Active Job links, exact input commit, original assets, restart commands and budget accounting are documented in `evaluation/CAMPAIGN.md` and the local campaign JSON receipts. The outcome is ongoing evaluation, not completed scientific evidence or final expanded tables.


Gemma follow-up: the user explicitly prioritizes continuing the existing evaluation if a verified quick fix is unavailable. No unproven decoding or precision change was applied. Gemma diagnostic work is deferred; the running campaign and checkpoint integrity are preserved.


## Reduced-NFE benchmarking literature check

Checked the same ten representative DLM papers for downstream task scores at reduced sampling budgets. Found direct examples in LLaDA (Appendix B.7 / Figure 5), Dream (Section 5.5.2 / Figure 7) and DiffuCoder (Appendix C.3 / Figure 11), plus related MT-Bench/CFG and adaptive tokens-per-forward analyses in Scaling up Masked Diffusion Models and LLaDA2.0. Therefore the conditional proposal to call this evaluation unusual is not supported. Added `reduced_nfe_audit.md` with ten source-linked, scoped findings.

Added a short fC22 Q2 response distinguishing the existing 128-token/32–64-NFE parallel-generation experiments from the full-NFE task table. Acknowledged the reported low-NFE quality loss and the missing task-accuracy/latency trade-off. Reduced-NFE task benchmarking remains future work; no new GPU experiments were added to the active sample-expansion campaign.


## Stronger full-suite wording and DiffuLLaMA correction

Revised fC22 Q2 at the author's request: characterizing reduced-NFE generation with perplexity/diversity is an established approach, while the named task-level studies examine selected tasks rather than every task in their main suite at each budget. LLaDA covers four tasks, Dream one, and DiffuLLaMA Appendix C.5 / Table 11 compares four tasks at T=32 versus 8. The latter was missed in the initial audit and the earlier negative finding is withdrawn. Kept DiffuCoder and LLaDA2.0 counterexamples in the internal evidence note; avoided asserting an unsupported field-wide majority or equating full task-suite coverage with evaluating every dataset question. No evaluation jobs were changed.


## Clarified perplexity comparison and terminology

At the author's request, changed the relevant response/audit terminology to “perplexity- and diversity metrics.” Added a courteous clarification that BYOD-Gemma 32-NFE perplexity versus standard AR-parent perplexity compares distinct decoding regimes, not a common reduced-denoising budget. Included the closer same-canvas/32-NFE LLaDA reference (5.33 vs BYOD-Gemma 14.56), alongside BYOD-Gemma at 128 NFE (4.33) and AR (3.01). Kept the AR reference useful, acknowledged the quality gaps and avoided equating equal diffusion NFE with equal compute/latency or assigning “full diffusion NFE” to an AR model. No benchmark jobs or manuscript numerical results were changed.

## HumanEval investigation

Audited all 1,601 saved HumanEval predictions in a CPU-only HF job with the frozen scoring harness: zero pass/fail disagreements; all 164 canonical solutions pass. Preserved private error traces and added `evaluation/humaneval_investigation.md`. Found historical declines within the fixed-prefix data, genuine semantic/syntax failures on added questions, and several diffusion answers cut off while copying long specifications into the 256-token canvas. These findings do not isolate Qwen AR's generation issue. No new GPU generation, scoring changes, or running-campaign modifications were made. Added an internal diagnostic note to the rebuttal draft; the completed HumanEval results remain available rather than being excluded for lower scores. CPU diagnostic maximum reservation is $0.005177, to account against the overall ceiling before a future campaign resume.

## Verified Qwen backend fix and separate Gemma cohort

The subsequently authorized bounded A100 probe reproduced four saved Qwen AR failures with eager attention and corrected all four with SDPA, holding BF16/greedy decoding/repetition penalty/output lengths fixed. Implemented and explicitly pinned Qwen SDPA. Gemma's three disputed texts were identical on repeated runs and on both tested backends; its exact historical drift remains unresolved, and no model defect was established. Resolved its evaluation blockage with a fresh eight-task cohort rather than deleting disagreements or pooling incompatible historical outcomes. HumanEval reruns remain deferred.

Launched a separate correction controller with immutable inputs and resume checkpoints; the original campaign is unchanged. Added optional staging-file selection to the controller so both cohorts retain separate budget ledgers/receipts. Qwen gets an AR replay gate; all replay records now retain text. The corrected run replaces the entire new eight-task Qwen cohort, including previously correct answers, and generates Gemma's eight tasks afresh. All 15 offline checks passed. The correction controller's $18 ceiling includes the two diagnostics; aggregate upper cap with the original controller is $93. See `evaluation/CORRECTIONS.md` for exact revisions, job links and restart commands. Corrected scores are not yet final.

The initial correction worker failed before generation because the scheduler injected LLaDA into a two-model run. Fixed subset scheduling, added a regression check (16 total tests pass), preserved the failed plan, and carried its CPU/GPU reservation into the unchanged correction ceiling. The restarted worker passed all 16 historical Qwen score replays (13 exact texts) and saved its first eight new corrected answers; Gemma follows the first bounded Qwen batch. No historical disagreement flags were erased.

## 15 November: Gemma MATH and MBPP fixes

Found missing `math-verify` in GPU requirements. Pinned the verifier, added a startup dependency check, and repaired symbolic comparison to use final expressions only, including explicit FINAL markers and rejection of intermediate rationale matches. Uniform CPU rescoring updates 86 selected MATH outcomes (51 retained historical plus 35 added) from false to true; the baseline is rescored with the same rules. Gemma AR becomes 59.2% → 51.6%, rather than 56.8% → 48.0%. A bounded matched GPU probe reproduces the same pass/fail outcomes under eager and SDPA (5/10 each); all 169 initial norm tensors match. No Gemma backend/length change was made and the remaining performance decline is not erased.

MBPP CPU audit reproduces all 281 old/fresh score flags and all 250 canonical solutions pass. The apparent BYOD-Gemma jump came mainly from rerunning old questions. Implemented provenance-based result assembly retaining original outcomes uniformly across Gemma tasks and adding only new question IDs, regardless of correctness. MBPP expansion is 46/125 → 59/156 (36.8% → 37.8%); the fresh-only 47.4% cohort remains separate. Raw outputs/plans are unmodified. Added tests against choosing higher-scoring reruns, accepting wrong Qwen backends, and accepting correct intermediate math despite wrong final answers. All 66 targeted tests pass. Diagnostics finished; their maximum additional reservation is $1.296854 and the combined observed/reserved upper bound is $71.760949. No full evaluation campaign was restarted.

Evidence and regeneration commands are in `evaluation/gemma_math_mbpp_investigation.md`. The rebuttal draft records updated internal numbers; manuscript tables remain separate while expansion is incomplete.

## Latest 15 November user decision: adopt fresh Gemma consistently

After reviewing historical versus fresh MBPP outputs, the user explicitly selected the fresh initial 125. Updated assembly policy to `user_selected_fresh_gemma_and_corrected_qwen_sdpa_v2`, applied consistently to all eight rerun Gemma tasks and including both gains and losses. MBPP is 61/125 + 13/31 = **74/156 (47.44%)**. Historical and retained-original alternatives remain archived; the prior assembled dataset/audit was copied to `generation_diagnostic/nov15_gemma/retained_original_policy_v1/` before regeneration. Qwen source selection and uniform MATH rescoring are unchanged. HumanEval remains deferred/historical.

Added `evaluation/DISCREPANCY_LOG.md` as the canonical status register, identifying fixed issues, controlled but unexplained historical drift, unfinished targets, deferred HumanEval corrections and pending final tables. Updated the rebuttal and investigation summaries to match the current decision. Selection tests now verify that fresh outcomes replace historical outcomes even when they are worse, rather than choosing by accuracy. No GPU jobs or additional generation were launched for this policy/logging update.

## HumanEval correction now prioritized

The user explicitly requests fixing HumanEval before remaining benchmark expansion. Prepared and submitted a HumanEval-only immutable plan for Qwen AR and Gemma diffusion: 95 Qwen reuse candidates plus 69 SDPA replacement generations, and 164 fresh Gemma generations. Original sampler/token limits are preserved; no code-repair postprocessing or new decoding protocol. Older campaigns remain stopped. The new phase has a $6 additional ceiling, carrying prior observed/conservative reservations into a cumulative $77.760949 ceiling below $93.

Added HumanEval integration to result assembly: verify the input plan and backend, reject duplicate/mismatched question sets, adopt each task only at all 164 outcomes, retain verified Qwen history, and replace the complete Gemma task cohort. Eight-task and nine-task summaries remain separate, with nine-task output gated on selected HumanEval completion. 68 targeted tests pass. Jobs and scores are pending; this does not resolve all unfinished targets or establish that other models' valid coding failures were measurement errors. See `evaluation/HUMANEVAL_CORRECTION.md`.

The HumanEval controller treated provider `SCHEDULING` as a pause and exited, but its GPU worker continued. Fixed active-state classification for future controllers (69 tests now pass). Automatic approval review rejected replacing the controller snapshot while its GPU was active due to overwrite/race risk; used a read-only actual-job/progress monitor instead, with no observer job launched and no cloud state/budget edits. Verified 129/328 saved outcomes with no blocked models and actual GPU RUNNING. Current worker checkpointing continues; if its one block ends incomplete, terminal usage must be reconciled before any resume.

## Remaining samples launched in parallel with explicit aggregate caps

The user authorized continuing other missing samples while HumanEval runs and asked about three GPU instances. Used the existing HumanEval GPU plus two new disjoint queues: Gemma 739 missing / 1,261 saved, and other models 919 missing / 13,081 saved. No HumanEval generations or already-complete Gemma AR/Qwen AR non-HumanEval tasks enter the new queues. The selected original/fresh/Qwen/MATH provenance policy is preserved.

Measured timings predict 4.24 total GPU-hours of generation, roughly five with overhead; two balanced workers imply approximately 2.5–3 elapsed hours. Static hard allocations are $12.75 and five allocated GPU-hours per queue, totaling $25.50 / ten GPU-hours, with eight-hour controller wall limits. Overall reserved compute ceiling including HumanEval and all prior costs is $103.260949, about €93.43 at the verified ECB 13 November rate of 1.1052 USD/EUR. This supersedes the earlier self-imposed $93 dollar ceiling while staying within the user's €100 compute budget.

Added cumulative runtime enforcement independent of cash refunds and fixed false `needs_review` classification at model-load shutdown margins. Added provenance-safe parallel merging to result assembly and final target-completion flags. All 72 targeted tests pass. Verified all three GPUs RUNNING; the new queues imported exactly 14,342 saved outcomes without blocked models, and HumanEval had Qwen 164/164 and Gemma 47/164 at that checkpoint. New run details, sources, budget and restart/assembly commands are in `evaluation/PARALLEL_COMPLETION.md`. No active HumanEval controller file was changed.

## HumanEval completed and adopted

Read-only verification confirms actual HumanEval GPU COMPLETED and complete saved progress, 328/328 outcomes. Corrected Qwen is 133/164 (81.10%), up from its faulty eager full-set 110/164 (67.07%). Fresh Gemma is 49/164 (29.88%): 47/125 initial and 2/39 added. All ten selected HumanEval cells now have 164 outcomes. Archived the previous assembled dataset/audit under `before_parallel_and_humaneval/`, downloaded pinned checkpoints for all three queues and regenerated selection plus consistent MATH rescoring. Nine-task descriptive summaries are emitted; all-sample-target completion remains false. At the snapshot, parallel Gemma generated 325/739 and the other lane 440/919, leaving 893. No new jobs, budget changes or cloud controller-state writes were made for this check.

## Published base/Instruct differences added to training-data response

At the author's request, verified the Qwen2.5 HumanEval 57.9% base versus 84.8% Instruct example and added original-report comparisons for Qwen MATH, Llama 3.1 HumanEval and Gemma 2 MBPP to shared response R05. Added `post_training_evidence.md` with exact table locations and comparability checks; the Llama report explicitly says its abbreviated family names refer to 3.1. Preserved the distinction between complete post-training versus SFT alone, association versus causal attribution, and score gains versus evidence of benchmark-example membership. The unmatched additional BYOD adaptation confound and future matched-AR control remain explicit. No manuscript benchmark numbers, jobs or budgets were changed.

## Qwen source disclosure and filtering follow-up

Checked the author's pasted Qwen data-composition interpretation against the general and specialist reports. Found a more direct specialist SFT disclosure than the pasted account suggested. Added its correctly scoped lineage to R05 and the evidence note, while acknowledging evaluation-overlap filtering, distinguishing screening from observed/retained contamination, and leaving exact general-checkpoint membership unestablished. No claim of GSM8K test leakage or equality of training exposure is made. Evaluation jobs and budgets are unchanged.

## AR benchmark-training precedents and disclosure framing

Added Tülu 3's explicitly named GSM8K/MATH training splits in RLVR and DeepSeekMath's benchmark-source SFT disclosure to R05 and the evidence note. Distinguished RL from SFT and explicit split names from dataset-source names. Incorporated the author's transparency argument: BYOD's source proportions make exposure visible, while missing disclosures elsewhere do not demonstrate exclusion. Comparable exposure is a reasonable possibility supported by precedents, not an established fact for undisclosed models. Avoided unmeasured claims that most models hide their mixtures or BYOD is unusually open across the field; retained the additional-adaptation confound. No jobs or budgets changed.

## Tülu dataset adoption and upstream benchmark sources

Verified Tülu-data reuse by Dream, Marin and OLMo 2 (the latter a specific variant). Added FLAN's explicit upstream GSM8K-train configuration alongside the Tülu mixture's FLAN component. Kept actual retained-example membership unverified, synthetic Persona data distinct from original benchmark examples, and SFT distinct from the explicit benchmark-train RLVR stage. Acknowledged Tülu's evaluation-overlap filtering. Updated R05 and the source evidence note; no evaluation jobs, budgets or measured scores changed.

## Condensed training-exposure response

Rewrote R05 from roughly 1,390 to 550 words, starting with instruction-tuned parents and published base/Instruct score gains, followed by disclosure visibility, direct AR/diffusion benchmark-training precedents, reused instruction mixtures, BYOD's mixture and the interpretation of the conversion gap. Moved the duplicate source lookup to `post_training_evidence.md`; detailed mixture arithmetic and the D1–D4 work items remain in the draft. Verified additional non-math training sources in FLAN's original configuration (including StrategyQA, QASC and eSNLI), keeping upstream membership distinct from retained Tülu examples. Treated increased scrutiny as a possible effect of disclosure, and wider benchmark exposure as plausible rather than asserting an unmeasured field-wide frequency. No jobs, budgets or benchmark results changed.

## Final evaluation targets completed

Verified all three GPU workers COMPLETED, downloaded pinned final checkpoints, preserved the prior local assembly, and reran provenance/selection checks plus consistent MATH rescoring. All ten configurations now have 250 outcomes on each of eight tasks and 164 on HumanEval: 21,640 selected outcomes, with both completion flags true. HumanEval’s old controller label remains stale; actual job and saved outcomes establish completion. See `evaluation/FINAL_EVALUATION_STATUS.md` for current nine-task means and artifact locations. No jobs launched, cloud state or budgets changed, or manuscript numerical tables updated.

## Manual review of added LLaDA samples

Reviewed 12 added answers across MATH, GSM8K, MMLU-Pro and HumanEval, sampling two saved failures and one success per task with a fixed seed. All 12 scoring decisions agree with manual answer checks/code tracing. Recomputed all 375 added non-code scores for these tasks without discrepancies; all 2,164 LLaDA saved settings match the frozen protocol. Recovered startup replays with 18/18 historical score matches and 15/18 identical texts. MATH's added questions include more level-4/5 items (69 versus 55), which may contribute to the drop without proving its full cause. Documented examples and limits in `evaluation/LLADA_MANUAL_CHECK.md`; raw packets/checks are locally ignored. No new jobs, score changes or fixes were needed from this review.

## Actual sampling design checked

Verified the frozen preparation code and saved examples: only MMLU/MMLU-Pro shuffle the full split with seed 1234; other partial benchmarks use the first unique items in release order. HumanEval is complete. LLaDA's historical first-125 fingerprints match the frozen first 125 on every task. Documented the distinction in `evaluation/SAMPLE_SELECTION.md`, the sampling plan and internal rebuttal notes, including selection-bias limits of confidence intervals. No claim that all original subsets were random is supported. No new jobs, scores or numerical result tables changed.

## Released-order representativeness audit

Compared exact saved subsets with all unused items in the six pinned partial/unshuffled benchmarks using 29 metadata diagnostics and 9,999 fixed-seed random-subset simulations, with global Holm correction. HellaSwag has a clear problem: all 250 selected examples are ActivityNet, but the full validation pool is 67.71% WikiHow, and source blocks are contiguous. GSM8K/ARC/MATH show no strong discrepancy on checked features; this is not proof of unbiasedness. GPQA expert-validation performance differs (77.0% versus 68.2%, exploratory corrected p=0.0576). MBPP excludes only seven of 257 items, all from one source notebook. Added reproducible analysis, aggregated results and `evaluation/DATASET_ORDER_AUDIT.md`; flagged HellaSwag in internal rebuttal/completion notes. No jobs, budgets, predictions, scores or manuscript numerical tables changed.

## Author's reporting preference for matched question sets

Kept the ordering audit and its findings in internal evaluation records, as requested. Removed the ordering-audit discussion from the rebuttal working text and replaced it with the shared-fixed-question clarification. Added the same clarification to the working manuscript, preserving its existing historical denominator exceptions and paired-ID restrictions. No claim of uniform random sampling or full-set representativeness was introduced; no scores, budgets or runs changed.

## Detailed final before/after comparison

Expanded `evaluation/FINAL_EVALUATION_STATUS.md` into a reproducible report covering all 90 model–benchmark cells, correct historical denominator exceptions, original recorded flags versus rescored baselines, fresh same-ID outcomes, added-only outcomes and final scores. Decomposed macro changes into rescoring, rerun and expansion effects. Added exact disjoint-cohort tests with Holm correction across 90 comparisons, separate matched Gemma checks across nine tasks, and task-stratified paired bootstrap intervals for three model contrasts. Gemma HumanEval's added-cohort decline is the one global-adjusted flag; LLaDA MATH is notable only before adjustment. Baseline reconciliation exposed remaining strict MATH-format handling cases; documented them without changing any scorer, predictions or labels. Added analysis script/JSON with input hashes and deterministic checks. This work launched no jobs, changed no budget and updated no manuscript score table.

## Discrepancy explanations, manuscript changes and reviewer response plan

Added offline static analysis of final code outputs and MATH level distributions. Gemma HumanEval's added 39 contain 11 syntax failures (six unfinished docstrings) and 26 syntactically valid failures; the canonical answer bodies all fit 256 tokens, so copying the longer specifications and real logic errors are distinct mechanisms. Reweighting historical MATH level rates predicts about 36.5 LLaDA successes on the additions versus 22 observed: the measured difficulty mix does not reproduce the entire decline. Recomputed final syntax counts, including one Gemma AR HumanEval syntax error, requiring qualification of the manuscript's blanket AR claim. Added detailed manuscript edits and reviewer-specific evidence/limits, including the submitted/recovered/final AR provenance corrections, revised Gemma/LLaDA and Llama-25k/50k claims, and draft response material. Integrated `DISCREPANCY_EXPLANATIONS_AND_REVISION_PLAN.md` into the reproducible final status report. No generated programs executed locally, new jobs launched, scoring labels changed or manuscript numerical tables updated.

## MATH presentation follow-up completed

Confirmed all three quoted cases were still rejected, then implemented complete-scalar numeric-escape and final-prose normalization plus reference-aware percent comparison. Percent units are not stripped indiscriminately: a bare reference value keeps its mathematical scale unless the final reference explicitly gives a percentage. Added regression checks for correct/wrong numbers, ambiguous or unfinished prose, percent context/scale and wrong final answers after correct intermediates. All 75 targeted tests pass. Uniform v3 reassembly restores nine historical flags and four final MATH flags, all false-to-true; prediction texts, IDs, settings and all non-MATH outcomes are unchanged. Final MATH becomes Gemma AR 130/250, BYOD-Ministral 51/250 and Ministral AR 140/250; other final cells are unchanged. Preserved v2 scorer/results/reports and a per-item change audit. Regenerated diagnostics, comparisons, intervals and the report, marked the follow-up complete, and updated manuscript-plan numbers. No GPU jobs, cloud writes, new generations or manuscript numerical-table edits.


## 16 November — separate rank experiment and fresh rank 1024

The author has requested a fresh rank-1024 control after inspecting the curves,
with $17 available. Ranks 128/512/2048 have completed their 25k validation-only
runs. The new 1024 configuration matches their actual resolved settings except
rank, alpha and its own output path; scientific source hashes are unchanged.
This experiment does not replace the original benchmarked BYOD-Llama model or
change any benchmark result. A new private study adapter is trained from the
pinned instruction-tuned parent. The historical 1024 curve and benchmark
checkpoint remain separate. Use the fresh control for the four-rank sensitivity
analysis after completion; retain the historical overlay as a labeled reference.

Job: `6afaaed223985fb9cd8452fa`, source revision
`c333ae2669d7d76faab394c7f9db9272bccc7ff6`. Expected runtime is about three hours;
the five-hour provider timeout and $2 startup reserve total $15.795733, within
the additional $17. Including prior provider-duration accounting, the combined
planning envelope is $41.466213, within the original $42 as well. See the
rank-study README, `controlled_recipe.json` and `budget_ledger.json`.


## 16 November — provisional rank/resource argument and hyperparameter scope

Added an asterisk-marked draft response to R04, explicitly awaiting the final
fresh-1024 endpoint. The current matched 5k losses suggest a smaller gain from
1024→2048 than from 512→1024. The timing analysis uses clean logged intervals:
2048 is 12.4% slower per update than 512, and 7.2% slower than the current 1024
estimate. Adapter parameter counts are 218.1M/436.2M/872.4M for 512/1024/2048.
Peak GPU VRAM was not recorded; the draft distinguishes measured counts and
update times from inferred adapter-related training-state storage. A 1024
practical-compromise interpretation is conditional on the final matched losses.

Included the author's earlier exploratory target-module (MLP/attention
projections) and learning-rate observations as design motivation, with their
lack of a systematic retained sweep stated. The fixed-recipe rank study does
not resolve module/LR optimality or replace a matched LAD control. The original
benchmark results and checkpoint remain unchanged. Source hashes, timing
intervals and all matched-step gaps are in `rank_ablation/RANK_TRADEOFF.md`,
`rank_tradeoff_snapshot.json` and `rank_tradeoff_matched_steps.csv`.


## 16 November — separate point-by-point reviewer template

Created `reviewer_responses.md` with each reviewer's original weaknesses and
questions quoted in italics, retaining repeated points, original ordering,
incomplete export wording and historical numerical claims. Added separate
blank response fields for each item and an opening response per reviewer;
summary/strength/assessment context is retained in collapsible sections.
No new reviewer answers were populated. The old reviewer-specific section
was moved verbatim from `rebuttal.md` into a collapsed internal appendix in
the new document. Shared response material remains in `rebuttal.md`. Updated
the workspace index and review response links.

Verified all original quoted blocks, all eight explicit questions, 27 blank
fields including openings, preservation of the prior response scaffolding,
and local file links. Original benchmark report and manuscript hashes remain
unchanged.


## 16 November — mNeh-W1 response and corresponding manuscript changes

Filled only mNeh-W1 in `reviewer_responses.md`, using plain language and the
shared LAD/rank evidence. Corrected the proposed scope contrast: LAD tested
three Llama sizes and six rank variants, while BYOD tests four model families;
this does not establish conversion of every possible AR model.

Added Appendix B / Table 5 with LAD's published 8B rank-1024/2048 scores and
the current expanded BYOD-Llama-25k results (250 questions per overlapping
task, from `evaluation/FINAL_EVALUATION_STATUS.md`). Explicitly identified
different sample counts, GPT-4o judging and LAD's semi-AR GSM8K protocol. This provides context rather than a matched objective control. The
main benchmark table has not been changed or updated to the expanded campaign.

Added Appendix C / Figure 5 / Table 6 for the separate rank experiment. Refreshed
the existing weighted-objective figure from local logs through 5k for fresh
1024, with the other ranks reaching 25k. Numerical comparisons use matched 5k
losses, adapter counts and clean update-time medians. The practical-compromise
interpretation remains preliminary, with a visible final-results TODO only in
the paper appendix. Documented exploratory target/LR choices without claiming
a systematic sweep or optimality. Added main-text references and replaced the
obsolete statement that the entire rank study remains future work.

The author declined the optional extra note attributing shorter LAD/BYOD training
times to implementation/hardware/budget differences; that note was not added.
No GPU jobs or benchmark model changes were made. Editing the revised manuscript
was explicitly requested; its older hash in `controlled_recipe.json` remains
unchanged as launch-time experiment provenance.


## 16 November — mNeh-W2, expanded benchmarks and descriptive comparisons

Populated only mNeh-W2, keeping the review quote and all other responses
unchanged. Cited the ten-paper reporting audit with its actual scope: CIs were
not found beside the inspected main comparisons, and counts are sometimes
reported elsewhere. Distinguished sanitized MBPP (257 available items) from the
full MBPP split, and corrected the work count to 21,640 total selected outcomes,
net +10,570 over 11,070 recovered historical outcomes.

Added the versioned `paper/source_results/benchmark_results_20261116.json` export,
`analysis/update_manuscript_benchmarks.py`, generated main/appendix tables and
macro-interval notes. All 90 final cells are checked against the preserved
per-question analysis; means use equal task weights. Main-table mean intervals
use 20,000 within-task bootstrap replicates; appendix per-task intervals use
Wilson's method. Paired contrasts reproduce the audited task-stratified item
bootstrap. Original workbooks and raw selections are unchanged.

Updated all benchmark-derived values and claims in the working TeX/abstract,
regenerated all three radar exports and their figure manifest, updated the
syntax-error counts and inference/provenance description, and removed the old
positive mean-accuracy claim from longer Llama training. Preserved independent
PPL/diversity, right-context and historical merge measurements, with the merge
comparison explicitly labelled. Added full available/evaluated counts and three
readable portrait interval panels in Appendix D. No landscape page was needed;
the checked official rules do not expressly address landscape appendices.

The author then requested avoiding superiority claims because of multiple
comparisons and model differences. Revised the response, abstract, methods,
results, discussion and limitations accordingly: intervals are nominal and
unadjusted for comparing five BYOD configurations or selecting Gemma. Gemma 9B
and LLaDA 8B differ in size and training history, and no matched full-fine-tuning
control was run. Results support LoRA conversion as a useful low-cost route,
not superiority or matched-method equivalence. No extra GPU work was launched.

`paper/BENCHMARK_UPDATE_20261116.md` records the completed claim/data propagation
and supersedes the older report's manuscript-work checklist. The old report
itself remains an audited snapshot. The rank study and its preliminary appendix
TODO remain separate. Moved the plotting script's optional Excel import into
its workbook entry point, allowing its existing radar renderer to be reused
without loading an Excel dependency for the revised per-question export.


## 16 November — concise mNeh-Q1 and Q2 answers

Filled the two explicit mNeh questions with short references to W1/W2 and the
existing appendices. Q1 states that the LAD comparison is not a matched-data,
matched-budget rerun and gives preliminary matched-step rank validation losses,
without inferring benchmark accuracy. Q2 reports the expanded coverage and
paired Gemma/LLaDA interval, retaining the lack of multiplicity/selection
adjustment and the model-size/training-history caveat. Preserved the author's
edited W1/W2 and every other response verbatim. No paper changes or new runs.
