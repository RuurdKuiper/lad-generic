# Expanded LLaDA study: fixed protocol

Frozen while the main run is in progress, before any winner selection or sampling follow-up.

## Design

60 prompts: the first 20 existing standard open-ended questions, 20 short Python-function tasks, and 20 elementary math problems. Includes the original six prompts and 54 new ones. Main experiment: five methods × six budgets × 60 prompts = **1,800 fresh generations**. A single fixed seed42 is used for every matched request. This expands prompt coverage, rather than drawing ten random samples of the original six prompts.

Settings match the pilot: max answer/block128; NFE4,8,16,32,64,128; top-k16; temperature0.7; bigram weight1; repetition strength1; expected probability-weighted repetition counts (count-every-candidate OFF); fading ON for repetition methods; APD OFF; sequence sampling OFF for the main phase. PMI min-count1/clip2, trigram min-count2/clip2/relative weight0.5. Open: EOS retention delay ON, ending strength10. Code/math: delay OFF, neutral ending strength1. Early stopping OFF for matched NFE. Existing six-iteration absolute logistic fade is preserved. All methods/scorer/model revisions are held fixed.

Methods: confidence guidance, expanded bigram, expanded bigram + fading repetition, expanded bigram + trigram, and expanded bigram + trigram + fading repetition. Main Viterbi is MAP/deterministic; temperature applies to confidence sampling. The follow-up turns bigram-guided sequence sampling ON at0.7.

## Scoring

- **Open:** assistant manual inspection using the pilot 0–3 quality rubric:0 unusable;1 recognizable but seriously repetitive/incoherent;2 mostly usable with noticeable grammar/content/repetition errors;3 coherent, relevant and without a substantive issue found. Record fluency0–3 separately. Review packets hide method, NFE and split. This is an assistant review, not an independent human or external judge model.
- **Code:** extract code without repairing it, syntax-check and execute in restricted subprocesses against frozen input/output edge cases. A task passes only if every test and any explicit algorithm constraint pass. Unsupported safety-policy constructs are flagged for review, not silently counted as wrong. Test suites are part of manifest.json and are never included in generation prompts.
- **Math:** manual answer/working inspection against frozen reference values. Record correct final answer and correct complete working separately. Correct answer without requested explanation is not a fully correct worked solution. Fraction/decimal equivalents accepted. Numeric-looking text anywhere in the answer is insufficient; the asserted solution must be correct. Grades:0 unusable/no answer;1 incorrect answer;2 correct final answer with missing/invalid work;3 correct final answer and valid requested work.
- Exact text duplicates within a prompt share a judgment. No pilot output or pilot judgment is imported. Distinct-1 is supplementary, computed with the pinned LLaDA tokenizer over visible output; it never determines the winner.

## Selection and sequence-sampling follow-up

Before generation, split each category deterministically into10 development and10 validation prompts (stratified seed20261022; assignments are in the manifest). Select **two n-gram configurations per NFE** using development results only. Selection score is an equal average of open mean quality/3, code all-test-pass rate, and math final-answer accuracy. Ties are broken by lower mean server latency, then method id. The confidence baseline remains in all comparisons but has no bigram sequence sampler to enable.

Run the two selected configurations with sequence sampling ON on **all60 prompts at that NFE**, keeping other settings and seed unchanged: **720 planned follow-up generations**. Compare each to its exact sampling-OFF counterpart. Primary follow-up interpretation uses the30 validation prompts; show development and all-prompt results separately. Selection is saved and locked before starting the follow-up. Because the same validation set also supports the main study, describe this as an exploratory paired follow-up, not an independent external benchmark.

Report by category and NFE as well as the equal-budget/category aggregate. Preserve per-prompt pairing. Bootstrap prompts within category, preserving each prompt's full vector of NFE/method results for overall estimates. CIs are exploratory and unadjusted for multiple comparisons; do not declare confidence guidance universally inferior or claim a global optimum from this dataset.

## Runtime and interruptions

Save each successful output immediately and assert actual model-forward/selector counts. Rotate budget and method order to reduce interruption bias. Use the current Hugging Face Space and existing GPU allowance; do not purchase credits or modify serving defaults. If a long GPU reservation is quota-blocked, try remaining shorter budgets. Keep incomplete cases explicitly pending and never fill them with fabricated results or scores. The scripts are resumable with revision and manifest guards.

Raw outputs, anonymous judgments, code checks, selection, statistics and representative successes/failures will accompany the report. Report the ending-delay and stochastic-baseline/deterministic-Viterbi differences as existing method-package confounds. Generations are judged at their final iteration; intermediate preview quality is outside scope.

## User-requested amendment: one sampled BG + TG arm

After the main study was stopped at 1,413 generated outputs and finalized using 1,410 matched outputs, the user requested one additional configuration: BG + TG without repetition, Sample bigram-guided sequences ON, temperature 0.7. Run precisely the 282 retained prompt/NFE cases, with all other settings and seed unchanged. This supersedes the cancelled 720-run selected follow-up; it does not resume the uncompleted main study.

The original manifest and stop snapshot remain frozen. `sampling_amendment.json` records the additional arm and the retained-source hash. This arm was chosen after seeing the original results; all comparisons are exploratory, with no held-out selection claim. Reuse the existing blinded review rubric, exact-text duplicate propagation and independent code checks. Update the current report and combined analysis only after all 282 added outputs are generated and graded.

## User-requested amendment: confidence at temperature zero

After completing all 282 sampled BG+TG runs, their grading and the six-configuration report, add one independent confidence-guided decoding arm with temperature 0 on the same 282 retained prompt/NFE cases. Preserve every other request setting from Confidence T=0.7, including seed, top-k, ending controls and forward budgets. Do not resume the missing original cases. Store outputs in `confidence_zero/`, freeze the previous six-configuration results and report, and update the common report and combined files only when the new arm is fully generated and graded.

This follow-up was user-requested after inspecting the earlier results and is exploratory. Reuse the original grading rubric and code tests. Report temperature-zero confidence against the original confidence arm, deterministic BG+TG and sampled BG+TG, including open-ended quality, coding/math correctness, valid math working, NFE curves and latency.
