# Ten-paper reporting audit

Checked 8 November 2026. This is a purposive selection of ten prominent/foundational DLM papers from the earlier proposed list, **not a verified top-ten citation ranking**. Findings concern the specified results in the linked versions. This is not a systematic estimate of field-wide reporting frequency.

## Findings

| Paper / primary source | Inspected result | Benchmark CIs in that result | Evaluation-count disclosure |
|---|---|---|---|
| [LLaDA](https://arxiv.org/html/2502.09992) | Tables 1–2 | Not identified | Not shown beside benchmark entries; Appendix B.6 supplies protocols. Other experiments explicitly specify 100 questions per difficulty setting and 496 poem pairs. |
| [Dream 7B](https://arxiv.org/html/2508.15487) | Tables 1–2 | Not identified | No per-task denominators adjacent to main scores; benchmark/protocol descriptions given. Few-shot counts are not test counts. |
| [DiffuLLaMA](https://arxiv.org/html/2410.17891) | Tables 1–2 | Not identified | Main-score denominators not adjacent; Appendix B.3 explicitly specifies 1,000 ROCStories and 1,033 code-infilling cases. |
| [Scaling up Masked Diffusion Models](https://arxiv.org/html/2410.18514) | Table 2 | Not identified | No denominators beside task scores; Section 7.2 separately specifies 0.5B evaluation tokens per time period. |
| [MDLM](https://arxiv.org/html/2406.07524) | Tables 1–3 | Not identified | Section 5.1 / Appendix D.4 explicitly reserve 100,000 OWT validation documents. Not an omission of all evaluation sizes. |
| [SEDD](https://arxiv.org/pdf/2310.16834) | Table 1 | Not identified | Names likelihood datasets, with no document/token denominators alongside table entries. Not a binary-accuracy sample count. |
| [Time-Agnostic Masked Models](https://arxiv.org/html/2409.02908) | Table 2 and Figure 7 | Not identified | Explicit counts: 8 samples in the Table 2 ablation; 64 for sampling comparisons; 100,000 OWT validation documents in Appendix H.2. |
| [DiffuCoder](https://arxiv.org/html/2506.20639) | Table 1 | Not identified | No per-task question counts beside entries; Appendix B.2 links evaluation toolkits. The ± notation describes score changes, not CIs. |
| [LLaDA2.0](https://arxiv.org/pdf/2512.15745) | Tables 1–2 | Not identified | No per-task denominators beside scores; Section 6.1 names benchmarks/settings. 47 benchmarks is not a question count. |
| [Mercury](https://arxiv.org/html/2506.17298) | Table 1 coding comparison | Not identified | No per-task counts beside coding scores; Section 3.2.1 names benchmarks. Other experiments, including human evaluation, are outside this row’s scope. |

## Interpretation and limits

The inspected comparisons present point estimates without accompanying benchmark confidence intervals. This does not prove that a paper contains no uncertainty estimate anywhere, that raw outputs could not support intervals, or that all comparison results were newly measured rather than imported. Likelihood bounds, prediction confidence, score-change ± notation and Monte Carlo draw counts are not automatically benchmark CIs.

Exact per-task question counts are often absent beside main result entries. That supports asking for clearer reporting, but **not** saying all ten omit evaluation sizes everywhere. Several provide explicit counts elsewhere. Dataset definitions, named variants/splits and linked evaluation code can make a denominator recoverable; the absence of a number in a table does not make a result inherently unverifiable. We did not execute every linked pipeline or verify the actual completed count for every run.

Paper-section/table checks were combined with targeted HTML/PDF searches for interval terminology, sample counts and protocol references. Negative findings are scoped to the inspected results; searches alone cannot establish universal absence from figures, alternative versions or artifacts. SEDD and LLaDA2.0 used PDF fallbacks after HTML retrieval errors.

MDLM, SEDD and the time-agnostic analysis include likelihood/generation-quality measurements. Their document/token/generated-sequence counts are not interchangeable with independent binary task questions, and the Wilson calculation for accuracy does not directly apply to perplexity.

## Small fixed datasets and precision

A request for ±1–2 pp population precision cannot be met by increasing unique questions within a smaller fixed benchmark. HumanEval has 164 items and sanitized MBPP has 257; their conservative 95% Wilson half-widths near 50% accuracy are about ±7.56 pp and ±6.07 pp. This is not a declaration that these benchmarks are unusable: precision depends on the estimand, accuracy, paired disagreements and claim size. A full deterministic benchmark score has no item-subsampling error for that fixed set. Its uncertainty for future task instances is a separate question.

## Proposed rebuttal use

Include a brief context statement and this qualified table in the internal draft, then foreground the concrete response: expand first toward 250 total unique items/task, retain the first 125 under unchanged verified protocols, use complete sets below 250, then add priority-trio questions if budget permits, report achieved denominators and paired uncertainty. Do not frame that work as proof that all requested comparisons are resolved or as a concession that prior papers’ reporting establishes sufficient precision.
