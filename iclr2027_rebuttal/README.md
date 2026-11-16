# ICLR 2027 rebuttal workspace

Created 8 November 2026 for BYOD. Start with [the ranked synthesis](review_summary.md), then use [the response draft](rebuttal.md) during our discussion.

| File | Purpose |
|---|---|
| [review_summary.md](review_summary.md) | Deduplicated concerns, ranked major to minor, with stable issue IDs and provisional ways to address them |
| [reviews/reviews.md](reviews/reviews.md) | Readable reviews, retaining reviewer wording and metadata |
| [reviews/reviews_original.txt](reviews/reviews_original.txt) | Verbatim attachment |
| [FORMAT.md](FORMAT.md) | Official response format, dates, sources, and remaining format uncertainty |
| [rebuttal.md](rebuttal.md) | Shared arguments, background evidence and remaining work; incomplete and not ready to post |
| [reviewer_responses.md](reviewer_responses.md) | Original comments/questions by reviewer, italicized and paired with blank response fields; earlier drafting notes preserved in a collapsed appendix |
| [current_macro_intervals.md](current_macro_intervals.md) | Historical nine-task intervals from recovered per-question outputs and actual denominators |
| [evaluation/README.md](evaluation/README.md) | Private Hugging Face pilot setup, reuse counts, safeguards and remaining checkpoint verification |
| [rank_ablation/README.md](rank_ablation/README.md) | 128/512/2048 validation-loss study with a $42 cap, persistent curves, rotating recovery checkpoints and a measured budget gate |
| [evaluation/audit_summary.md](evaluation/audit_summary.md) | Latest reruns, partial runs and corrected historical provenance |
| [results_before_expansion/2026-11-08/README.md](results_before_expansion/2026-11-08/README.md) | Separate read-only snapshot of selected historical predictions, original source files and verified hashes |
| [sampling_plan.md](sampling_plan.md) | 95% precision calculations, benchmark-specific caps, additional item counts and compute-planning notes |
| [reporting_audit.md](reporting_audit.md) | Ten-paper, result-specific audit of confidence intervals and evaluation-count disclosure |
| [reduced_nfe_audit.md](reduced_nfe_audit.md) | Same ten papers: reduced-step task benchmarks versus generation-quality analyses; source-backed response to the parallel-decoding concern |
| [model_breadth.md](model_breadth.md) | Counts of evaluated checkpoints and task coverage compared with five related DLM papers |
| [gpu_options.md](gpu_options.md) | Unattended GPU rental options, current rates and illustrative budgets |
| [literature_notes.md](literature_notes.md) | Verified LAD/data-disclosure/reporting-practice sources and limits of the evidence |
| [analysis/precision_plan.py](analysis/precision_plan.py) | Reproduce the sampling plan and its CSV without running evaluations |
| [changes.md](changes.md) | Proposed manuscript locations, decisions, evidence, and completed-change log |
| [paper/iclr2027_conference.tex](paper/iclr2027_conference.tex) | Editable paper copy with bibliography, styles, figures, and source results |
| [baseline/manifest.json](baseline/manifest.json) | Initial file hashes and source provenance |

## Paper baseline

The working paper was copied from `../iclr2027_submission/`. The older `iclr2027_conference-manualedits.tex` was excluded; it differs substantially and includes older results. Original submission files remain untouched. A baseline TeX, PDF, and bibliography are preserved in `baseline/`; hashes cover the initial working-paper dependencies too.

This is a **local submission candidate**, not a verified download of the submitted OpenReview paper. The source TeX was modified after the local PDF was built on 25 September. Confirm the uploaded version before attributing an exact passage to the submitted PDF. The copied `paper/RESULTS_NOTES.md` is historical provenance and contains unresolved items; it is not a current rebuttal task list.

The working paper now corrects recovered historical AR code scores, denominators, and documented inference limits. No new model experiments have been run. Figures await final rescoring/expansion and must be regenerated before submission. Draft responses distinguish existing evidence from missing evidence; placeholders must be resolved before posting.

## Build the working paper

From the repository root:

```sh
cd iclr2027_rebuttal/paper
latexmk -pdf -interaction=nonstopmode -halt-on-error iclr2027_conference.tex
```

The resulting `paper/iclr2027_conference.pdf` is a working build. The preserved local PDF is in `baseline/`. Figure-generation scripts elsewhere in the repository currently target the original submission directory; inspect or redirect their output before using them for rebuttal revisions.

## Next discussion

Decide issue by issue which evidence is already available, which runs are feasible, and which claims should be narrowed. Record decisions in `changes.md`, then update the paper and responses together. No experiment listed here is a commitment to perform it.
