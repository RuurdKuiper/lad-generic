# Review synthesis: major to minor

Status: initial triage, 8 November 2026. Severity and proposed remedies below are our interpretation, not reviewer labels. Decisions about experiments versus explanation remain open.

Author discussion update: foreground the extension from LAD's structured corruption to cross-family mask-only MDLM conversion. The author intends to expand evaluations 250 total unique items/task first (full sets below 250), then more Gemma/Gemma AR/LLaDA samples if budget remains; this does not generally yield ±1–2 pp population precision. See the updated [response and open work](rebuttal.md), [sample calculations](sampling_plan.md) and [verified literature](literature_notes.md). Rank/module/control experiments remain proposals. The initial ranking below is retained as triage, not an assertion that all proposed runs are selected.

## Overall reading

All three reviewers recognize the accessible conversion budget and the four-family evaluation. mNeh also values comparison to the AR parents; dPsL and fC22 recognize candid reporting of limitations. The main disagreement concerns whether the experiments establish the value of this particular recipe and support the comparative claims.

| Reviewer | Rating | Confidence | Presentation / Informativeness / Soundness |
|---|---|---|---|
| mNeh | 2 — Weak rejection | 2 | 2 / 2 / 2 |
| dPsL | 2 — Weak rejection | 2 | 3 / 2 / 2 |
| fC22 | 1 — Clear rejection | 4 | 3 / 1 / 1 |

The strongest overlap is **missing matched conversion controls and ablations** plus **small benchmark subsets without uncertainty**. fC22 additionally identifies a specific score-provenance inconsistency and a training-exposure confound. These deserve attention even though only one reviewer raises them.

## Ranked issues

| Rank / ID | Severity | Concern | Reviewers | Provisional route; decision pending |
|---|---|---|---|---|
| 1 / R01 | Major: validity | Four AR scores appear inconsistent with 125-example binary accuracy; exact provenance is unclear | fC22 W1, Q1 | Audit saved runs and denominators; correct or rerun affected cells and derived averages/figures |
| 2 / R02 | Major: evidence | 125 examples/task and no uncertainty cannot substantiate small gaps to LLaDA or 25k→50k improvements | All | Recover paired outcomes, add paired intervals; expand evaluation where feasible; qualify claims |
| 3 / R03 | Major: contribution | No matched LAD or simple LoRA conversion baseline | All | Match parent, data, tokens, evaluation, and hardware accounting; measure compute rather than assume equal tokens imply equal compute |
| 4 / R04 | Major: design justification | No rank/module ablations; Q/V-only rank 1024 may not justify its parameter/compute trade-off | All | Discuss a focused rank and target-module comparison with quality, trainable parameters, memory, and time |
| 5 / R05 | Major: interpretation | Benchmark-training exposure differs between BYOD and unchanged AR parents, confounding retention/conversion-gap claims | fC22 W1 | Audit train/eval splits; narrow causal claims; consider an AR fine-tuning control on the same mixture |
| 6 / R06 | Major: fairness | MMLU-Pro permits 2,048 output tokens for AR and 128 for diffusion | dPsL W2, Q2 | Author confirms longer AR limits were intentional. Document the recovered 2,048-vs-64 setting, qualify “matched” wording, and treat matched-output sensitivity as optional, outside the current run budget |
| 7 / R07 | Major: practical value | Task benchmarks use one token/step; reduced-NFE task accuracy and wall-clock latency are absent | fC22 W2, Q2; dPsL Q3 | Quality/latency comparison at 2–4 tokens per step, with comparable outputs and hardware |
| 8 / R08 | Major: quality | Large math/code losses and poorer open-generation perplexity persist even at high NFE | dPsL W3; fC22 W2; mNeh summary | Quantify limitations and errors; improvements require evidence, not wording alone |
| 9 / R09 | Moderate–major: usefulness | No realistic infilling or constrained-generation use case at acceptable quality/latency | dPsL Q3; fC22 W2 | Discuss a small useful task beyond the right-context copy probe; report quality, constraint success, and latency |
| 10 / R10 | Moderate: diagnosis | Training caps total sequence length at 256, but some evaluations generate 256 plus prompt tokens | fC22 Q3 | Inspect length/truncation distributions; compare within-length and longer cases; causal attribution needs a controlled intervention |
| 11 / R11 | Moderate: novelty | Known components; label shift and loss weights are unablated as well as rank/modules | fC22 W2; mNeh/dPsL W1 | Clarify empirical contribution relative to LAD; consider focused objective controls separately from R04 |
| 12 / R12 | Minor relative to evidence | Presentation takes effort in places | mNeh presentation score | Improve protocol definitions, sample counts, and table notes after resolving the substantive issues |

No reviewer requests an ethics review. There are few independent cosmetic complaints: most concerns are scientific or evidential.

## Evidence and discussion notes

### R01 — Score provenance first

The challenged Table 3 entries are Gemma/Qwen/Ministral AR HumanEval `.740/.890/.940` and Gemma AR MBPP `.740`. For ordinary binary accuracy on exactly 125 items, the step size is `1/125 = .008`; none of these values is a rounded fraction with that denominator. This establishes a reporting inconsistency to investigate, not its cause. Different denominators, aggregation, stale workbook cells, or another metric remain possibilities until the run outputs are checked.

The local paper contains these values and declares 125 examples for every model. `paper/RESULTS_NOTES.md` maps Table 3 to `source_results/Results_training-20260924.xlsx`, but also lists unfinished paired evaluations and missing run manifests. These notes are a starting point, not verification. Audit sample IDs, denominators, extraction/scoring rules, and run/checkpoint IDs for every relevant column; propagate any corrections into means, highlights, radar plots, abstract, and replies.

### R02 — Uncertainty and small reported gaps

Both the 50.6% versus 51.9% comparison and the 48.7% versus 49.2% longer-training comparison are questioned. Use paired item-level differences where sample IDs actually match. For the nine-task macro mean, preserve task weighting in resampling rather than pooling all questions as one task. Separate uncertainty across evaluation items from variability across training seeds. Do not infer equivalence from an interval that includes zero.

The repository already archives **open-generation** uncertainty in `paper/source_results/open_ended_uncertainty.json`; that does not answer the request for benchmark-accuracy paired intervals. Full benchmarks are requested by fC22; the other reviewers allow larger subsets or paired intervals. What is feasible remains to be discussed.

### R03 / R04 / R11 — Controls and novelty

Distinguish three questions: whether BYOD differs usefully from LAD; whether high-rank Q/V-only LoRA is justified; and whether same-position labels and answer/padding loss weighting matter. A single adapter-merging ablation does not resolve these. All reviewers ask about the first two; fC22 explicitly adds label shift and loss weights.

A candidate minimal experiment set is one representative parent with matched LAD/BYOD recipes, a smaller-rank condition, and a target-module control. Any choice needs budget and implementation review before commitment. Holding token count fixed measures a different trade-off from holding elapsed compute fixed; report both and identify what was actually controlled. Clarify the contribution as an accessible cross-family empirical recipe unless stronger mechanistic or novelty claims are supported.

### R05 / R06 — Fairness of comparisons

The training mixture includes MMLU, HellaSwag, GSM8K, and MBPP training splits; unchanged AR parents do not receive that adaptation. Training-split exposure is not by itself test contamination, but frozen base weights do not establish unconfounded knowledge retention in the adapted model. An AR control or removing exposed tasks from a sensitivity analysis may help; wording alone can narrow the claim but cannot measure the confound.

MMLU-Pro's unequal output limits are explicit in the local inference tables. Matching output length helps assess this issue but does not match computational cost. Do not retrospectively describe the current comparison as fully matched.

### R07 / R08 / R09 / R10 — Practical value and failure analysis

Open-generation perplexity at reduced NFE exists, but reduced-NFE **benchmark accuracy** and measured **latency** are separate missing evidence. One-token-per-step diffusion does not establish speedup. Report hardware, batch size, length, prompt handling, and timing procedure for any latency claim.

The right-context copy test demonstrates a controlled capability, not useful infilling quality. Existing parser-failure analysis documents code errors but does not establish why they occur. Similarly, a length mismatch is a plausible explanation to test, not an established cause of math/code degradation. Account for prompt-plus-answer length and tokenizer differences when analyzing it.

## Coverage of every explicit author question

| Reviewer question | Issue IDs |
|---|---|
| mNeh Q1: matched LAD and smaller rank | R03, R04 |
| mNeh Q2: larger subsets and paired confidence intervals | R02 |
| dPsL Q1: LAD/simple control; rank and modules | R03, R04 |
| dPsL Q2: full benchmarks/paired intervals; matched MMLU-Pro output | R02, R06 |
| dPsL Q3: useful infilling/constrained generation, quality and latency | R07, R09 |
| fC22 Q1: inconsistent AR cells; full benchmarks and intervals | R01, R02 |
| fC22 Q2: reduced-NFE benchmark accuracy and latency | R07 |
| fC22 Q3: training/evaluation length mismatch | R10 |

## Suggested discussion order

Start with R01/R02 because they determine which numerical claims are defensible. Then decide the feasible scope of R03/R04 and the fairness fixes R05/R06. Finally choose whether practical-capability or length experiments can materially strengthen the paper. This ordering is provisional; it does not commit us to runs or settle which issues can be answered in prose.
