# Gemma AR MATH and BYOD-Gemma MBPP investigation — 15 November

The audit found a MATH scoring dependency/answer-comparison defect and an MBPP comparison-cohort problem. It does not establish that every score decrease or increase was erroneous. Raw predictions and original correctness flags are preserved.

**Latest user decision, 15 November:** adopt the complete fresh BYOD-Gemma cohort consistently across all eight rerun tasks, including both improvements and regressions. MBPP's first 125 are **61/125 (48.8%)** and the additional 31 are **13/31 (41.9%)**, giving **74/156 (47.4%)**. This is a rerun plus expansion, not a pure sample-expansion gain over the historical 46/125. HumanEval has no corrected fresh cohort and remains deferred/historical. The historical-retention assembly was archived under `generation_diagnostic/nov15_gemma/retained_original_policy_v1/` before regeneration. Current policy ID: `user_selected_fresh_gemma_and_corrected_qwen_sdpa_v2`. See [the discrepancy register](DISCREPANCY_LOG.md).

## Implemented fixes

| Case | Previously reported before → after | Corrected comparable before → after |
| --- | ---: | ---: |
| Gemma AR MATH | 56.8% (71/125) → 48.0% (120/250) | **59.2% (74/125) → 51.6% (129/250)** |
| BYOD-Gemma MBPP | Historical 36.8% (46/125) → fresh rerun 47.4% (74/156) | Adopted fresh cohort: **48.8% (61/125) → 47.4% (74/156)**; historical baseline remains separate |

### MATH scoring

The frozen GPU requirements omitted the `math-verify` evaluation dependency. The code silently used normalized exact-string/decimal comparison when the verifier was unavailable, rejecting equivalent final expressions. Inspected Gemma examples include `\frac65` versus `\frac{6}{5}`, `\dfrac{17}{50}` versus `\frac{17}{50}`, `x=5` versus `5`, LaTeX thousands spacing, and scalar multiples of the same plane equation.

Pinned `math-verify[antlr4_13_2]==0.8.0` in evaluation requirements and added a startup dependency check. Updated symbolic comparison to parse **extracted final answers**, rather than whole rationales, with no string fallback and bounded parse/verification timeouts. Added support for the explicitly requested `FINAL:` marker and tests ensuring a correct intermediate value cannot override a wrong final answer. The comparison uses the [official Math-Verify parse/verify API](https://github.com/huggingface/Math-Verify).

Rescored every selected model's MATH answers and its historical baseline under the same version. The earlier original-retention selection changed 86 expanded labels; after the latest fresh-Gemma decision, **87 selected expanded labels** change from false to true. The baseline separately has 51 changes, overlapping with reused historical outcomes; these counts must not be summed as independent corrected predictions. No selected true label changed to false. The Gemma AR change is 9 answers: 3 historical and 6 added. Full per-item normalized answers, provenance, prior flags and scorer SHA-256 are in ignored `generation_diagnostic/nov15_gemma/assembled_audit.json`; raw snapshot files are unchanged.

The remaining Gemma AR difference is **−7.6 percentage points**, and the added 125 questions score 55/125 (44.0%). They contain more level-4/5 problems (69/125, versus 55/125 in the original subset). This supports a composition contribution but does not causally explain the entire difference. Only one added answer is within eight retokenized tokens of the 1,024-token limit; most failures are not truncations. Inspected failures contain genuine arithmetic/algebra mistakes: index 133 solves `3x + 180 = 360` as `x=40` and returns 80 instead of 120; index 130 returns remainder 1 instead of 13.

### MBPP cohorts and code audit

CPU audit [6af96fa423985fb9cd83167d](https://huggingface.co/jobs/Ruurd/6af96fa423985fb9cd83167d) reran all **281** saved old/fresh BYOD-Gemma predictions under the frozen Linux harness: **zero score disagreements**. All **250 canonical MBPP solutions pass**. Generated code executed only in resource-limited unprivileged cloud children, never on the laptop. Private error traces are in `generation_diagnostic/nov15_gemma/mbpp_audit.json`.

- Original 125 answers: **46/125 = 36.8%**.
- Fresh rerun of those same questions: **61/125 = 48.8%** (20 gains and 5 losses; 24 byte-identical predictions).
- Newly added 31 questions: **13/31 = 41.9%**.
- Original 125 plus new 31: **59/156 = 37.82%**.
- Full fresh cohort, a separate valid experiment: **74/156 = 47.44%**.

Thus the apparent +10.6-point increase was mostly a rerun/environment effect, not the effect of adding 31 questions. It was wrong to describe the fresh-cohort comparison as sample expansion alone. No broken MBPP tests/scoring were found. The exact cause of historical generation drift is still unestablished; previous original weight/tokenizer checks and same-environment repeatability probes remain documented separately.

Initially implemented original-outcome retention and archived that assembly. Following the user's subsequent explicit choice, `assemble_results.py` now selects the fresh Gemma cohort **uniformly across all rerun tasks**, never selecting between old and fresh answers by correctness. Both 20 gains and 5 losses on the original MBPP questions are included. Historical outcomes remain separately available. Corrected Qwen outputs are used only with explicit SDPA provenance; known eager outputs are excluded regardless of correctness. HumanEval correction remains deferred. All selected rows preserve their original plan IDs plus an explicit selection/scoring version.

Run `.venv/bin/python iclr2027_rebuttal/evaluation/assemble_results.py` to regenerate the ignored derived dataset and per-model audit. The prior `nov15/comparison.json` remains an immutable record of the earlier comparison; its scores are superseded for reporting by `nov15_gemma/assembled_audit.json`.

## Matched GPU diagnostic

Job [6af9705929dd05ff03686da7](https://huggingface.co/jobs/Ruurd/6af9705929dd05ff03686da7) completed, comparing eager and SDPA on the same 10 Gemma AR MATH questions and preserving full outputs. All **169** saved initial normalization tensors match the native base model. In the eager pass, three of four selected historical outputs and all six selected added outputs match their saved texts exactly. Both backends get **the same five questions correct and the same five wrong** (5/10 each). Text can differ without changing these outcomes. This is a selected diagnostic set, not an accuracy estimate.

These checks support correct model loading and repeatable failures. Unlike the Qwen investigation, this probe establishes no backend remedy for Gemma AR. **No Gemma generation backend or output limit was changed.** Remaining MATH performance loss is retained as observed, with question-composition and model reasoning limitations noted rather than claiming it has been eliminated.

## Validation, costs and remaining scope

67 targeted tests pass after the latest policy update, covering final-answer scoring, non-equivalence, fresh-cohort selection regardless of accuracy, historical Qwen reuse, rejection of the wrong Qwen backend, deferred tasks, and existing benchmark/campaign behavior.

Both prior controllers were stopped before diagnosis. Their accumulated conservative cost upper bound was $70.464095, including earlier diagnostics/startups. This investigation reserves at most **$1.296854** ($1.291677 GPU + $0.005177 CPU), keeping the combined upper bound at **$71.760949**, below $93. Receipts are in the ignored diagnostic folder. No benchmark campaign was resumed and no full benchmark generations were added.

Old immutable worker bundles still contain the old scoring dependency set. Freeze updated source/requirements before a new scientific run, or apply the versioned CPU rescorer to their saved outputs. Do not use their old math flags/report files directly as final corrected results. Manuscript benchmark tables are not silently replaced while evaluations remain incomplete.
