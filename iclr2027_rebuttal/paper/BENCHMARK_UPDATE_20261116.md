# Revised benchmark propagation — 16 November 2026

This records the completed manuscript update from the final evaluation report.
It supersedes that report's earlier manuscript-propagation checklist; raw
predictions, the audited report and historical workbooks are unchanged.

| Item | Implemented change |
|---|---|
| Main table | All 90 common-harness task cells now use the final selected outcomes; means and best-observed highlighting are recomputed. Scores are percentages. |
| Sample counts | 250 shared questions on eight tasks and all 164 HumanEval questions, for each of ten configurations. Appendix D lists full available split sizes, including sanitized MBPP's 257. |
| Additional work | 21,640 final selected model–question outcomes versus 11,070 recovered historical outcomes: net +10,570. Replacements and diagnostics are excluded from this increase. |
| Mean uncertainty | Table 3 gives nominal 95% within-task percentile-bootstrap intervals for the equal-weight nine-task averages (20,000 replicates, seed 20261116). |
| Individual uncertainty | Three portrait appendix tables give all 90 task scores and Wilson intervals from integer counts. No landscape pages are needed. |
| Paired comparisons | Shared item draws within tasks; 20,000 replicates, seed 20261115. Paired intervals exactly reproduce the final audited analysis. |
| Multiple comparisons | No correction for comparing five BYOD configurations or selecting the strongest conversion. Intervals are labelled nominal/unadjusted and no superiority claim is made. |
| Gemma/LLaDA | 52.43% / 49.55%, nominal paired gap +2.88 pp [0.74, 4.98]. Descriptive context: Gemma 9B and LLaDA 8B differ in size and training history; this is not a matched LoRA/full-fine-tuning control. |
| Parent comparison | Gemma AR 62.73%; BYOD-Gemma minus parent −10.30 pp [−12.33, −8.31]. Every conversion has a lower observed mean than its AR parent. |
| Longer Llama training | 47.93% at 25k / 47.80% at 50k, gap −0.14 pp [−1.81, 1.49], four tasks rise and five fall. Removed the earlier positive average-accuracy claim. |
| Abstract/results/discussion | Updated numbers and interpretation in TeX and `ABSTRACT.md`; no superiority framing from an unadjusted interval. |
| Figures | Regenerated the two-panel benchmark radar and both standalone exports; updated exact values, source hashes and sample counts in `figures/figure_data.json`. |
| Code error analysis | Llama-50k: 51/164 invalid HumanEval programs and 24/250 invalid MBPP programs; Llama AR has none. Qualified the broader AR statement because Gemma AR has one invalid HumanEval program. Saved illustrative fragments remain unchanged and occur in the final selection. |
| Scoring/provenance | Documented uniform v3 MATH scoring, full fresh Gemma cohort, Qwen AR SDPA corrections and compatible historical reuse. Changes are not solely sample-size effects. |
| Inference protocol | Completed counts replace pending/historical-only wording; intentional longer AR output limits remain explicit. |
| LAD appendix | Expanded BYOD-Llama values match the revised main table; LAD's published 100-item results remain protocol-separated. |
| Separate measurements | Historical 125-item merge comparison is explicitly labelled and retained. Perplexity/diversity, NFE sweeps, right-context test and original rank-study snapshot are unchanged. |

Source: [versioned benchmark export](source_results/benchmark_results_20261116.json).
Regenerate with `analysis/update_manuscript_benchmarks.py` from the rebuttal
workspace (see `RESULTS_NOTES.md` for the repository-root command). The source
contains raw-selection hashes, integer counts, interval settings and the exact
scoring/selection versions. Original benchmark model weights are unchanged.

The main contribution is that LoRA conversion yields useful diffusion behavior
across the four tested families at a small additional training budget. This
study does not establish a superior conversion method, universal conversion,
or equivalence to matched full-parameter adaptation.
