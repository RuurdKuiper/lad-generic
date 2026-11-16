# MATH final-answer presentation correction — 15 November 2026

**Implemented and uniformly rescored.** Scorer version `final_answer_math_verify_0.8.0_v3` resolves the three presentation cases previously marked as follow-up. No model was rerun, no GPU job was launched, and no generated answer was edited.

## Accepted presentation variants and limits

- A complete numeric final answer with a stray LaTeX escape, such as `FINAL: \78`, `FINAL: \0.15` or `FINAL: \3}`, is normalized to its number. The rule matches the entire scalar answer; it does not search a rationale for a correct number or repair arbitrary broken expressions.
- A complete scalar final statement, such as `FINAL: The value is 83.`, is normalized to its number. Alternatives such as “83 or 84,” unfinished reasoning and wrong declared final answers remain rejected.
- Numeric percent answers respect the reference's unit. In the actual square-area example, gold ends with `\boxed{10} percent`, so `10%` and `10` are accepted as the requested percentage coefficient. `0.1%` is not accepted. When gold gives a bare number without percentage units, `10%` retains its scale: it can equal `0.1`, but cannot equal `10`. An unrelated percentage earlier in the reference reasoning does not supply the final unit.

These rules apply to every model and to both historical and expanded answers. There is no model-, index- or correctness-dependent exception. Malformed symbolic answers and truncated rationales are outside this repair; the scorer still prioritizes the declared final answer over a correct intermediate expression.

## Changes from v2

| Cohort | Model | Restored correct answers |
|---|---|---:|
| Historical baseline | BYOD-Gemma | 5 |
| Historical baseline | Gemma AR | 1 |
| Historical baseline | BYOD-Ministral | 2 |
| Historical baseline | Ministral AR | 1 |
| Final selected results | Gemma AR | 1 |
| Final selected results | BYOD-Ministral | 2 |
| Final selected results | Ministral AR | 1 |

All changes are false-to-true. The four final answers are reused historical predictions, so the two cohort counts must not be summed as independent newly corrected generations. Nine distinct saved answer texts are restored overall: five historical Gemma answers superseded by its fresh cohort, plus four answers appearing in both baseline and final sets.

| Model | Final MATH v2 | Final MATH v3 | Nine-task mean v2 → v3 |
|---|---:|---:|---:|
| Gemma AR | 129/250 (51.6%) | 130/250 (52.0%) | 62.68% → 62.73% |
| BYOD-Ministral | 49/250 (19.6%) | 51/250 (20.4%) | 48.45% → 48.54% |
| Ministral AR | 139/250 (55.6%) | 140/250 (56.0%) | 62.66% → 62.70% |

Other final scores are unchanged, including BYOD-Gemma and LLaDA. Historical Gemma MATH is restored from the v2 rescore's 32/125 (25.6%) to 37/125 (29.6%), matching its original recorded count. This changes the decomposition of its historical-to-final mean without changing the final mean itself. Gemma's gap to its AR parent is now −10.30 pp; its comparison with LLaDA is unchanged.

## Validation and provenance

All **75 targeted benchmark, selection, protocol and campaign tests pass**. Regression cases cover correct/wrong escaped numbers, complete/ambiguous scalar prose, percentage context and scale, and a wrong final answer following a correct intermediate box.

Uniform reassembly verifies all 21,640 original identities, settings and prediction texts are unchanged; only four final MATH correctness flags change. All non-MATH correctness flags are unchanged. Recomputed paired intervals and the detailed final report use the v3 results. The cohort-discrepancy conclusion is unchanged: Gemma HumanEval remains the only globally adjusted flag.

The previous scorer, selected outcomes, scoring audit and reports are preserved in ignored `generation_diagnostic/nov15_gemma/before_math_presentation_v3/`. The per-item v2→v3 change audit, including scorer/result hashes, is `generation_diagnostic/nov15_gemma/presentation_v3_changes.json`. Immutable downloaded inputs and original `recorded_correct` fields remain intact. The final comparison report records the current source hashes and correction policy.

This completes the quoted presentation follow-up. It does not claim to solve all model errors or independently adjudicate every malformed/truncated MATH response. Manuscript numerical tables still need their separately planned update.
