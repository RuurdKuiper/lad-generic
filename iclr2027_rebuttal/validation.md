# Workspace validation

## 15 November — rank-study logs and recovery preparation

Prepared ranks 128/512/2048 at 25k updates with validation-loss-only evaluation.
The three configurations differ only in rank, alpha and output directory.
Training logs remain separate from the final adapter and two retained recovery
checkpoints. The private-Hub worker uploads logs after validation and completed
checkpoints before pruning. A CPU interruption/resume test checks optimizer-step
continuation, historical best loss, checkpoint retention and replay-free active
curves; unit checks cover torn log tails and failed cloud uploads. A plotting CLI
smoke check rendered three validation-component curves into a standalone PDF
and exported their six raw points as CSV, using synthetic temporary fixtures.
The training, recovery, plotting, model and corruption checks passed: **92
tests**. The recovery test also passes with final test evaluation disabled.

CPU checks do not validate native FP8/Transformer Engine checkpoint recovery
or GPU memory. The author subsequently authorized a **$42 total cap**, conditional
on the complete study appearing feasible. CPU runtime compilation succeeded
after correcting cuDNN header paths. A private artifact repository was created
and the existing published token profile was checked against the exact recipe
with no differences. The pinned GPU runtime includes a hash-verified compiled
FP8 wheel and source manifest. The bounded GPU job was submitted on 15 November
at 22:48 Windhoek time, with a 14-hour provider timeout, a measured full-study
forecast gate with 20% headroom, and no automatic GPU retries. Combined worst-case
job reservations plus a $3 startup buffer total **$41.606553**. The expanded
training/recovery/budget test selection passes **96 tests**. GPU recovery and
the measured forecast remain to be confirmed. Full setup, receipts and plotting
commands are in [rank_ablation/README.md](rank_ablation/README.md).

The sections below are dated historical workspace checks, not current campaign
status. Current benchmark results are in
[evaluation/FINAL_EVALUATION_STATUS.md](evaluation/FINAL_EVALUATION_STATUS.md).

Checked 8 November 2026.

- Original review attachment preserved byte for byte; all three reviews formatted with reviewer IDs and metadata.
- Initial working-paper source and dependencies checked against SHA-256 hashes in `baseline/manifest.json`, excluding the rebuilt output PDF.
- Working TeX remains byte-identical to `../iclr2027_submission/iclr2027_conference.tex`.
- Local links in the root workspace Markdown files checked for existing targets.
- `latexmk -pdf -interaction=nonstopmode -halt-on-error iclr2027_conference.tex` completed successfully in `paper/`, including BibTeX and subsequent LaTeX passes.
- Working PDF: `paper/iclr2027_conference.pdf`, 23 total pages including bibliography and appendices. Total pages are not the main-text page count; the final revision still needs a main-text formatting check.
- Final build log contains existing underfull-box messages and float-placement adjustments; no unresolved-reference or unresolved-citation warnings remain.

This validates the workspace and baseline build, not the correctness of reported scientific results. The OpenReview-uploaded baseline, exact response comment cap, and exact discussion cutoff time have not been verified. No experiments or substantive paper revisions have been performed.

## Response planning update

The precision script was run and its deterministic output checked. Normal-planning counts are 2,401 for ±2 pp and 9,604 for ±1 pp; worst-case n=500 Wilson half-width is 4.36587347 pp. Dataset-plan totals are 3,869/model and 2,744 additional over a reusable 125/task baseline. Wilson endpoints were checked against the defining score-test equation, and the script's generated Markdown/CSV were checked for reproducibility. Relative Markdown links were checked for existing targets. Initial paper source hashes remain unchanged (the generated PDF is excluded).

These are planning calculations, not empirical confidence intervals for the paper's rounded scores. Variant counts derive from current public cards and current loader code; historical run manifests still need auditing. The main-table literature check covers three papers and does not verify the pasted ten-paper prevalence claim.

## Current 375-item plan and ten-paper audit

The current allocation supersedes the earlier 500-item proposal: min(375, available), with the first 125 retained when reusable. Recalculated totals: 3,046/model, 1,921 added/model, 19,210 added across ten columns, 5,763 added for the three-column first pass. The individual n=375 worst-case Wilson half-width is 5.03488256 pp. The independent-task conservative macro approximation is 1.84 pp. Script-generated artifacts were checked for deterministic regeneration, arithmetic consistency and local-link integrity; these are not measured experimental intervals.

Expanded the literature check to ten representative papers, scoped to the named results, recording explicit sample-count disclosures rather than asserting blanket omission. Added current primary-source GPU rental quotes and conditional runtime/cost scenarios. No GPU allocation, paid job, training or expanded benchmark evaluation has been launched.

## Latest 250-stage plan and conditional current macro intervals

Validated deterministic regeneration of the 250-item plan and provisional current-CI artifacts. First-stage counts are 2,164 total / 1,039 additional per model. Current macro intervals use the manuscript, not silently substituted workbook values, and withhold the three AR columns with incompatible n=125 rates. Seven calculated intervals remain conditional on denominators and independent-item/task assumptions; no paired interval was calculated. The paper source remains unchanged and no new model inference has been run.


8 November, recovered-run update: seven offline evaluation-preparation tests pass. Latest compatible selection, partial reruns, intentional longer AR limits, actual denominators, Unicode JSONL handling and pilot/full checkpoint gates are covered. Corrected working paper builds successfully with latexmk (23 pages). No GPU inference was run. CUDA compatibility, replay agreement, uniform code rescoring and final expanded results remain pending the approved pilot. Historical figure files await regeneration and the working paper is not ready to submit.


## 15 November — native FP8 recovery format correction

The first bounded GPU check reached rank-2048 update 250 at roughly 0.44
seconds/update, then failed strict checkpoint restoration because Accelerate
dropped empty Transformer Engine `_extra_state` keys during safetensors saving.
The job stopped automatically before full training. FP8 recovery saves now use
native Torch serialization and explicitly capture calibration state after BF16
validation. A CPU regression checks strict restoration and calibration retention;
the targeted selection passes **97 tests**. The original attempt is preserved
under `rank-2048/` in the private Hub dataset. Corrected runs start fresh under
`fp8-checkpoint-v2/`. This is a recovery-format fix, not a change to the loss,
training examples, rank settings, inference settings or scorer.

The corrected GPU job is `6afa1def23985fb9cd83bc2c`, immutable source revision
`ac79d63b638c28fe95ff554eaff39042a3026f06`. Its provider timeout is reduced to
50,040 seconds (13h54). Prior stopped GPU usage is conservatively accounted at
$0.641662; CPU reservations, the corrected GPU reservation and a $3 startup
contingency bring the total upper planning envelope to **$41.973217**. The
corrected GPU recovery check and full-study forecast gate are still pending.


The corrected native GPU recovery check has passed: strict model-state loading
succeeded, training resumed from update 250 to 500, validation remained finite,
and the controller verified update count 500 for every optimizer parameter.
The saved real-GPU loss totals also match 0.9 × answer loss + 0.1 × padding loss
and use all 200 fixed validation examples. First corrected rank-2048 validation
losses were 1.77852 at update 250 and 1.60960 at 500; rank 128 was 2.27262 at
update 250. These are startup diagnostics, not final rank-study results.


The measured all-three-runs budget gate has now **passed**. Initial speeds were
0.37871 / 0.38994 / 0.43588 seconds per update for ranks 128 / 512 / 2048.
The remaining forecast, including 20% headroom, was 10.99 hours against 13.51
hours available before the reserve. Estimated full-study cost is $31.56, or
$34.56 including the entire startup contingency. The active worker is now
continuing rank 128 toward 25k; ranks 512 and 2048 follow. Scientific completion
and final loss comparisons are still pending. The reproducible cost projection
and captured source-backed status are in `rank_ablation/`.


## 16 November — matched rank-1024 run submitted separately

The author authorized a fresh rank-1024 control with $17 available. The new
configuration matches the **actual resolved configurations** of all three
completed rank runs in every field except rank, alpha and its output path.
Scientific-library hashes match their immutable training revision. The original
benchmark report and working manuscript hashes were checked after setup and
remain unchanged. No benchmark evaluator is run for the new model.

Nineteen budget/recovery tests pass. Job `6afaaed223985fb9cd8452fa` is running
with a five-hour provider timeout. Its initial 250 updates produced finite
validation loss 1.82255 and the correct 436,207,616 LoRA parameters. Measured
speed is 0.40730 seconds/update. Its 20%-margin forecast passed and training
is continuing to 25k. Full loss history, final adapter and two resumable
checkpoints are kept in the private rank-study folder. The additional
reservation plus startup contingency is $15.795733, within $17; combined
accounting is $41.466213, within the original $42 ceiling. Completion and the
matched four-rank plot remain pending.


## 16 November — mNeh-W1 manuscript/response verification

- Verified the original mNeh-W1 quote, every other reviewer-response field and
  the manuscript's complete historical benchmark table are unchanged. Exactly
  one of the 27 blank response fields was populated. No TODO is in that answer.
- Verified the final expanded evaluation report still has its recorded SHA-256
  `b34de868572087389f5ba315cf582991061e8a6690018a55e1abe3564aa4586c`.
- Rechecked LAD's published Sections 2.1/2.6 and Table 2 against the ACL paper
  (https://aclanthology.org/2025.emnlp-demos.8.pdf). Confirmed the model-family
  distinction, all five LAD table rows, sample counts, judging and GSM8K generation.
  Cross-checked expanded BYOD-Llama values against the final evaluation report:
  ARC-C 207/250, HellaSwag 182/250, MMLU 153/250 and GSM8K 162/250.
- Regenerated the 90/10-objective plot from 320 local validation records. Its
  provenance JSON records source hashes and 5k/25k curve extents. Copied its PDF
  into the revised manuscript; inspected the chart and rendered appendix pages
  15–16 for layout and readable table/figure content.
- `latexmk -pdf -interaction=nonstopmode -halt-on-error` completed successfully
  (25-page PDF). Final log has no undefined citations/references or overfull
  boxes; existing underfull-box and float-placement warnings remain. Verified
  Appendix B/C and Table 5/6 / Figure 5 references against the generated AUX.
- No training/evaluation code was changed, and no paid job was launched.


## 16 November — expanded manuscript verification for mNeh-W2

- The offline export validated 90 integer correct/evaluated cells, all shared
  question fingerprints and all 250/164 denominators against the final selected
  per-question data and the audited analysis. Independent raw historical
  counting confirms 11,070 outcomes and the net +10,570 to 21,640.
- Three paired contrasts exactly reproduce the final report's 20,000-replicate
  bootstrap. Individual-model mean-bootstrap endpoints agree with an independent
  normal-approximation diagnostic within 0.0372 percentage points. All Wilson
  endpoints contain their point estimates and remain within [0,1].
- Compared the response document with the pre-edit snapshot: only mNeh-W2's
  answer changed, its original quote is identical, and every other answer,
  including mNeh-W1, is unchanged. Twenty-five blank fields remain.
- Verified source hashes, raw selection/diagnostic compatibility, unchanged
  final evaluation report and unchanged non-benchmark figure measurements.
  All four displayed syntax-error fragments still occur in final Llama-50k
  predictions. No generated code was executed for this propagation work.
- Reopened primary sources for the ten-paper reporting context and dataset
  sizes. Explicitly distinguished absent adjacent denominators from counts
  reported elsewhere, and a purposive audit from a field-wide frequency claim.
- Rechecked ICLR 2027 formatting: rebuttal main-text allowance is 10 pages,
  appendices follow references with no page cap. No explicit landscape guidance
  was identified; all new interval tables use portrait pages.
- The final `latexmk -pdf -interaction=nonstopmode -halt-on-error` build succeeds
  (27 pages total). The conclusion ends on page 10; excluded statements and
  references follow. No undefined citations/references or overfull boxes;
  ordinary existing float-placement warnings remain. Inspected rendered main
  table, abstract and appendix intervals, and the exact figure source values.
- Added explicit nominal/unadjusted and model-selection language throughout;
  no superiority inference is drawn from the Gemma/LLaDA interval. Preserved
  separate rank-study logs/figure and original benchmarked model weights.
