# BYOD — individual reviewer responses

**Working template; answers intentionally left blank.** Respond to each reviewer separately, keeping repeated comments and questions in their original order. Reviewer text is quoted in italics; item labels are added only for navigation. The quotes reproduce the supplied export, including missing words and historical numerical claims. They have not been silently corrected.

Source: [original reviews](reviews/reviews.md), with the [verbatim export](reviews/reviews_original.txt) retained separately. Use [the shared arguments and evidence](rebuttal.md) when we start writing answers. Previous reviewer-specific drafting notes have been moved unchanged to a collapsed [internal appendix](#previous-reviewer-specific-drafting-notes); they are not populated answers to this template.

- [Reviewer mNeh](#reviewer-mneh)
- [Reviewer dPsL](#reviewer-dpsl)
- [Reviewer fC22](#reviewer-fc22)

## Reviewer mNeh

Posted: 22 Oct 2026, 10:45. Modified: 06 Nov 2026, 14:33. Visibility in export: Everyone. [Revisions](https://openreview.net/revisions?id=vYnu400TXw)

**Rating:** 2: Weak rejection  
**Confidence:** 2: I have broad familiarity with this field but little or no direct research experience on this topic.

### Opening response

_[To be written.]_

<details>
<summary>Original review context: summary, strengths and assessments</summary>

**Paper Summary**

> *The paper proposes BYOD, which is a LoRA-based method converting frozen autoregressive models into diffusion language models. The method is applied to four model families, which requires 3.1 to 4 hours on a single GPU. The authors evaluated the performance, generation quality, and bidirectional attention. For the main result, BYOD-Gemma reaches 50.6% average accuracy compared to 51.9% for LLaDA, although the performance and the quality remains below the autoregressive baselines.*

**Critical Strengths**

> *- The one strength of BYOD that I want to point out is that the conversion provides a practical way to convert an autoregressive model to a diffusion language model with a limited compute. Furthermore, the evaluation on four different model families adds generalizability to the method.*
> *- The comparison to the original autoregressive model was meaningful for understanding what features are preserved after the conversion and where the performance drops. This is especially important for future research since we can have a better view of what needs to be improved.*

**Presentation**

> *2: Generally understandable, but requires substantial effort in places.*

**Informativeness**

> *2: I learned something interesting or useful.*

**Soundness**

> *2: I have minor or fixable concerns about the paper’s soundness.*

**Rating**

> *2: Weak rejection*

**Confidence**

> *2: I have broad familiarity with this field but little or no direct research experience on this topic.*

**Flag For Ethics Review**

> *No*

</details>

### Presentation comment

#### mNeh-P1

> *2: Generally understandable, but requires substantial effort in places.*

**Response:**

_[To be written.]_

### Critical weaknesses

#### mNeh-W1

> *The most critical weakness that I found is the lack of experimental support on the existing LoRA-based conversion methods. LAD already claims a conversion using LoRA and bidirectional attention, while the paper lacks the comparison against it. The ablation on different hyperparameters that are related to LoRA is lacking and also, it is not clear whether the additional parameter provides a meaningful tradeoff between the conversion cost and performance.*

**Response:**

We understand this concern. BYOD is indeed similar to LAD, in that it uses LoRA and bidirectional attention. However, LAD has a significantly different generation objective; it combines masking with structured corruption (token swaps, duplications and span shifts). BYOD instead uses mask-only MDLM, which is more comparable to classical MDLM studies, and tests whether a reproducible recipe works across model families. LAD tested on only one model family, the Llama model, while we developed a shared recipe across Gemma, Llama, Qwen and Ministral.

Because we do agree that a more in-depth comparison is granted, we have added LAD's published 8B benchmark results alongside BYOD-Llama in Appendix B (Table 5), and reference this comparison in the main text. These are useful context, but they were not obtained in the same harness. We therefore keep the protocols separate and do not treat the table as a controlled comparison of the two objectives.

To address the comment about hyperparameter ablation, we have added a rank ablation on Llama 3.1 8B in Appendix C (Figure 5 and Table 6), varying rank across 128, 512, 1024 and 2048 while keeping the other settings fixed. The results show that rank 1024 offers a practical balance, as the drop in validation loss is much larger going from rank 512 to 1024, then when going from 1024 to 2048, while the latter of course adds twice as much parameters. Running the full benchmark suite for all of these models was out of the scope of this study, but lower validation loss is of course indicative of better performance. We did perform earlier exploratory tests of using other layers (q,k,v-projection, MLP-layers) as LoRA targets, as well as learning rates, but a full sweep of these was outside this study's scope, as we already had four different model types + extended training as 'hyperparameters' as well. 

#### mNeh-W2

> *Furthermore, the benchmark evaluation uses only 125 examples per task and does not report uncertainty estimates. This makes it difficult to judge how reliable the small average gap against LLaDA is. Since competitive performance at a low conversion cost is a major reason to use the method, I would want stronger evidence for this comparison.*

**Response:**

We appreciate this point and agree that the comparison needs stronger evidence.We have now doubled the target from 125 to 250 questions on eight tasks and evaluated all 164 HumanEval questions, using the same questions across models. Across ten model/checkpoint configurations, the completed results contain 21,640 model–question outcomes, a net increase of 10,570 over the recovered historical results. 

We would like to note that while we reported the number of samples used for evaluation in our manuscript, this is often not customary for studies of this type. Moreover, we have performed a review of ten top diffusion language model papers and found that none of them had accompanying confidence intervals, or per-task sample counts beside the scores: [LLaDA](https://arxiv.org/html/2502.09992), [Dream](https://arxiv.org/html/2508.15487), [DiffuLLaMA](https://arxiv.org/html/2410.17891), [Scaling up Masked Diffusion Models](https://arxiv.org/html/2410.18514), [MDLM](https://arxiv.org/html/2406.07524), [SEDD](https://arxiv.org/pdf/2310.16834), [Time-Agnostic Masked Models](https://arxiv.org/html/2409.02908), [DiffuCoder](https://arxiv.org/html/2506.20639), [LLaDA2.0](https://arxiv.org/pdf/2512.15745) and [Mercury](https://arxiv.org/html/2506.17298). Finally, benchmark sizes can also be small, for example, [HumanEval has only 164 questions](https://huggingface.co/datasets/openai/openai_humaneval).

However, we agree with the reviewer that this information is actually important, and have therefore now included confidence intervals for all benchmark results. Table 3 gives the updated scores using the 250 samples, and 95% confidence intervals for the nine-task averages. Appendix D gives the full per-task table with 95% confidence intervals, the actual sample counts and the calculation details.

BYOD-Gemma now averages 52.43%, compared with 49.55% for LLaDA. The paired difference is +2.88 percentage points for BYOD-Gemma, with a 95% difference interval of [+0.74, +4.98]. This does not prove that the BYOD-Gemma architecture is superior: While BYOD-Gemma was the strongest observed conversion among five BYOD configurations, its 9B parent is larger than 8B LLaDA, and their training histories differ. The comparison rather shows that LoRA conversion can produce useful diffusion capabilities at low training cost; it does not isolate LoRA versus full fine-tuning. We have updated all benchmark figures, tables and comparative claims, including withdrawing the earlier claim of an average accuracy gain from longer Llama training.

### Questions for authors

#### mNeh-Q1

> *Can the authors compare BYOD against LAD using the same training data and budget? How much does performance change with a smaller LoRA rank?*

**Response:**

As discussed in W1, Appendix B compares published LAD results with BYOD; we have not rerun LAD with matched training data and budget. Appendix C examines rank under otherwise fixed settings. At 5,000 matched updates, validation loss is 1.4144 at rank 128, 1.3179 at 512 and 1.2650 at 1024. Smaller ranks therefore give higher validation loss in this preliminary comparison. We did not run downstream benchmarks for these ablations, so we cannot quantify their effect on benchmark accuracy.

#### mNeh-Q2

> *Does the reported proximity to LLaDA hold on larger benchmark subsets, with confidence intervals for the paired differences?*

**Response:**

Yes. As described in W2, we now use 250 shared questions per task and all 164 HumanEval questions. BYOD-Gemma averages 52.43%, versus 49.55% for LLaDA, with a paired difference of +2.88 percentage points and a nominal 95% interval of [+0.74, +4.98]. This interval is unadjusted for multiple comparisons or selecting the strongest conversion. We make no superiority claim; the models also differ in size and training history. Table 3 and Appendix D give the updated results and uncertainty estimates.

## Reviewer dPsL

Posted: 21 Oct 2026, 09:40. Modified: 06 Nov 2026, 14:33. Visibility in export: Everyone. [Revisions](https://openreview.net/revisions?id=tO5yanIwY4)

**Rating:** 2: Weak rejection  
**Confidence:** 2: I have broad familiarity with this field but little or no direct research experience on this topic.

### Opening response

_[To be written.]_

<details>
<summary>Original review context: summary, strengths and assessments</summary>

**Paper Summary**

> *BYOD converts four pretrained autoregressive model families into masked diffusion models using attention-only LoRA and a shared training recipe. Conversion takes a few single-GPU hours, although generation quality remains below the AR parents and often below LLaDA.*

**Critical Strengths**

> *- The conversion recipe is simple and accessible to groups with limited training hardware.*
> *- Testing four model families with their AR parents gives useful practical evidence.*
> *- The paper clearly reports quality failures, low-NFE limitations, and the difference between training cost and inference speed.*

**Presentation**

> *3: Clear and easy to follow.*

**Informativeness**

> *2: I learned something interesting or useful.*

**Soundness**

> *2: I have minor or fixable concerns about the paper’s soundness.*

**Rating**

> *2: Weak rejection*

**Confidence**

> *2: I have broad familiarity with this field but little or no direct research experience on this topic.*

**Flag For Ethics Review**

> *No*

**Details Of Ethics Concerns**

> *NA*

</details>

### Presentation comment

#### dPsL-P1

> *3: Clear and easy to follow.*

**Response:**

_[To be written.]_

### Critical weaknesses

#### dPsL-W1

> *The recipe is not compared with a matched-budget LoRA conversion baseline such as LAD. Without rank and trainable-module ablations, the benefit of the specific BYOD choices is unclear.*

**Response:**

_[To be written.]_

#### dPsL-W2

> *Each task uses only 125 fixed examples, without uncertainty estimates. The 1.3-point mean gap to LLaDA is therefore hard to interpret, and MMLU-Pro gives AR 2,048 output tokens but diffusion only 128.*

**Response:**

_[To be written.]_

#### dPsL-W3

> *Generation quality remains a large limitation. Math and code lose substantial accuracy versus the AR parents, and even 128-step generation has worse perplexity than LLaDA.*

**Response:**

_[To be written.]_

### Questions for authors

#### dPsL-Q1

> *How does BYOD compare with LAD or a simple LoRA conversion control at the same token and compute budget, and how sensitive is it to rank and target modules?*

**Response:**

_[To be written.]_

#### dPsL-Q2

> *Do the main comparisons hold on full benchmarks or with paired confidence intervals, using matched output limits for MMLU-Pro?*

**Response:**

_[To be written.]_

#### dPsL-Q3

> *Can you show an infilling or constrained-generation task where the conversion provides a useful capability at an acceptable quality and latency?*

**Response:**

_[To be written.]_

## Reviewer fC22

Posted: 17 Oct 2026, 05:03. Modified: 06 Nov 2026, 14:33. Visibility in export: Everyone. [Revisions](https://openreview.net/revisions?id=XkRYKqVN20)

**Rating:** 1: Clear rejection  
**Confidence:** 4: I have substantial direct research experience on this topic.

### Opening response

_[To be written.]_

<details>
<summary>Original review context: summary, strengths and assessments</summary>

**Paper Summary**

> *This paper introduces the method BYOD which converts instruction-tuned AR LMs into masked diffusion LMs with bidirectional attention mask. The method uses rank-1024 LoRA on Q/V with frozen base weights. It is trained on a mixture of instruction, multiple-choice, math and code data. Each conversion uses 102.4M tokens and takes roughly 4 h on one GPU. It is applied to Gemma 2 9B, Llama 3.1 8B, Qwen2.5 7B and Ministral 8B. The converted models are compared with their frozen AR parents and LLaDA 8B Instruct on nine benchmarks on Phi-4 perplexity and Distinct-n of open-ended generations, and on a right-context copy test. The best model, BYOD-Gemma, averages 50.6% vs 51.9% for LLaDA and 65.7% for its parent.*

**Critical Strengths**

> *1. A cheap, uniform, reproducible conversion recipe with candid reporting. One fixed configuration converts four different model families in single-GPU hours. The best model comes within 1.3 points of LLaDA on the paper's harness (Table 3). The limitations are stated openly (Sec. 7).*

**Presentation**

> *3: Clear and easy to follow.*

**Informativeness**

> *1: I learned little or nothing new from this paper.*

**Soundness**

> *1: I have significant concerns about the paper’s soundness that do not appear easy to address.*

**Rating**

> *1: Clear rejection*

**Confidence**

> *4: I have substantial direct research experience on this topic.*

**Flag For Ethics Review**

> *No*

</details>

### Presentation comment

#### fC22-P1

> *3: Clear and easy to follow.*

**Response:**

_[To be written.]_

### Critical weaknesses

#### fC22-W1 — overall concern

> *The evaluation cannot support the comparative claims.*

**Response:**

_[To be written.]_

#### fC22-W1.1

> *All benchmarks use 125-example subsets (App. D), giving about  points of uncertainty per task, but no intervals are reported. Yet the text interprets differences of 0.5-1.3 points (BYOD-Gemma vs LLaDA; 25k vs 50k updates).*

**Response:**

_[To be written.]_

#### fC22-W1.2

> *Four AR-parent scores cannot come from 125 examples: HumanEval .740/.890/.940 and Gemma MBPP .740 (Table 3).*

**Response:**

_[To be written.]_

#### fC22-W1.3

> *The training mixture includes the MMLU, HellaSwag, GSM8K and MBPP training splits (Sec. 3.3), while the AR parents get no comparable fine-tuning. So the claimed knowledge retention and the "conversion gap" are confounded with task-format exposure.*

**Response:**

_[To be written.]_

#### fC22-W2 — overall concern

> *Limited novelty and no demonstrated benefit of the converted models.*

**Response:**

_[To be written.]_

#### fC22-W2.1

> *The recipe combines known components; the paper itself credits LAD with first showing that LoRA induces diffusion generation (Sec. 2). Its own choices (rank, Q/V-only targets, label shift, loss weights) are not ablated.*

**Response:**

_[To be written.]_

#### fC22-W2.2

> *All benchmarks decode one token per step (Table 8), so parallel decoding is never tested. Where NFE is reduced, quality degrades sharply: BYOD-Gemma perplexity is 14.56 at 32 NFE vs 3.01 for its parent (Table 12).*

**Response:**

_[To be written.]_

#### fC22-W2.3

> *With no latency results and large math/code drops (e.g. Qwen MATH-500 .352 vs .784), the contribution rests on conversion cost alone.*

**Response:**

_[To be written.]_

### Questions for authors

#### fC22-Q1

> *How were the four non- AR scores in Table 3 obtained? Can you report full-benchmark results with confidence intervals?*

**Response:**

_[To be written.]_

#### fC22-Q2

> *What are benchmark accuracies at reduced NFE (e.g. 2-4 tokens per step), and the wall-clock latency vs the AR parents?*

**Response:**

_[To be written.]_

#### fC22-Q3

> *Training sequences are capped at 256 tokens (Table 7), yet GSM8K/MATH/HumanEval decode 256 tokens plus the prompt (Table 8). How much of the math/code gap does this length mismatch explain?*

**Response:**

_[To be written.]_

## Previous reviewer-specific drafting notes

<details>
<summary>Earlier scaffolding moved from rebuttal.md — internal reference only</summary>

These notes predate this point-by-point template and may contain stale statuses or partial prose. They are retained for later use; none has been copied into the response fields above. References here to shared material “above” mean [rebuttal.md](rebuttal.md).

## Response to Reviewer mNeh

Thank you for highlighting the conversion budget and parent comparisons.

### Q1 — LAD comparison and smaller rank

Use the shared LAD response/table and the provisional rank/resource response above. The asterisk marks the final-1024 update still needed. A matched LAD/objective control remains separate work. [Insert final evidence and manuscript locations: L1–L3.]

### Q2 — Larger subsets and paired intervals

Use the shared uncertainty response. [Insert achieved counts, verified paired Gemma–LLaDA difference/interval and revised table location: E1–E7. Do not describe the plan as completed.]

## Response to Reviewer dPsL

Thank you for recognizing the accessible recipe, four-family study and candid limitations.

### Q1 — Control, rank and target modules

Use the shared LAD response and the provisional rank/resource response above. Keep the asterisk until the final fresh-1024 endpoint is available. Module/LR choices are supported here by author-reported exploratory observations, not a systematic ablation; a matched LAD/objective control remains separate work. [Insert final evidence and manuscript locations: L1–L3. Merging is not a substitute for these experiments.]

### Q2 — Coverage, paired intervals and MMLU-Pro

Recovered runs used AR 2,048 MMLU-Pro output tokens versus diffusion 64; the manuscript incorrectly states 128 for diffusion. Document these intentional limits accurately and qualify the interpretation; matched-output sensitivity runs are optional and not currently scheduled. [Insert results, actual scope and paired intervals: E2–E7.]

### Q3 — Useful infilling, quality and latency

The right-context copy test probes access to later context, not realistic infilling quality or a favorable quality–latency trade-off. Math/code and open-generation deficits remain material limitations.

- [ ] **U1 — Select a useful infilling/constrained-generation task and baseline**, with quality, constraint success and measured latency; otherwise limit the utility claim.
- [ ] **U2 — Report existing failure analysis accurately** and distinguish observed syntax errors from untested explanations.

[Insert measured evidence and revised sections, or explicit limitations.]

## Response to Reviewer fC22

Thank you for the detailed protocol and score-provenance scrutiny.

### Q1 — Four AR scores and full benchmarks/intervals

The audit locates 50-item Gemma AR code results, a 95-item partial Qwen AR HumanEval rerun, and a later 125-item Ministral AR HumanEval rerun that supersedes its 50-item score. [Insert verified provenance, denominators and any corrections/propagated changes: E1. Insert actual expanded scope and intervals: E2–E7. A 250-item subset of a larger dataset is not full-benchmark evaluation.]

### Q2 — Reduced-NFE task accuracy and latency

**Draft response:** We thank the reviewer for raising this point. Parallel generation is already evaluated in our open-generation experiments: we report perplexity and Distinct-1/2/3 for 128-token outputs at 32, 64 and 128 NFE. The 32- and 64-NFE settings therefore explicitly test parallel denoising; the one-token-per-step setting applies to the task-benchmark table.

We would also like to clarify the interpretation of the 14.56-versus-3.01 perplexity comparison. The former uses only 32 denoising steps for a 128-token output, whereas the AR parent uses its standard sequential decoding procedure; it has no directly analogous reduced diffusion-NFE setting. The AR result remains a useful quality reference, but this comparison does not hold the denoising budget fixed. For assessing the reduced-NFE diffusion regime, the closer comparison in the same table is LLaDA at 32 NFE on the same 128-token canvas: perplexity 5.33 versus 14.56 for BYOD-Gemma. At 128 NFE, BYOD-Gemma's perplexity is 4.33, compared with 3.01 for its AR parent. We acknowledge the remaining gap; our point is that the reduced-NFE and standard-decoding comparisons answer different questions.

Our use of perplexity- and diversity metrics follows an established evaluation approach in diffusion language modeling. The generation analyses in [MDLM](https://arxiv.org/html/2406.07524), [SEDD](https://arxiv.org/html/2310.16834) and [Time-Agnostic Masked Models](https://arxiv.org/html/2409.02908) emphasize metrics such as generative perplexity and diversity/entropy. Where the cited studies provide reduced-compute task analyses, these cover selected tasks rather than repeating their entire benchmark suite at every budget: [LLaDA](https://arxiv.org/pdf/2502.09992) tests GSM8K, MATH, HumanEval and MBPP; [Dream](https://arxiv.org/html/2508.15487) uses Countdown; and [DiffuLLaMA](https://arxiv.org/html/2410.17891) reports a T=32 versus T=8 comparison on HellaSwag, WinoGrande, SIQA and PIQA. Thus, a full-suite sweep across lower NFE budgets is not a uniform reporting convention in these examples.

We nevertheless agree that reduced-NFE task accuracy and measured latency would strengthen the evaluation and are valuable directions for further work. The reported low-NFE quality degradation remains a limitation; our contribution concerns efficient cross-family conversion, and we do not claim a demonstrated inference-speed advantage at matched quality.

**Internal evidence/scope note:** Avoid calling AR decoding “full diffusion NFE”: it is a different procedure. Equal diffusion NFE and output canvas align step budgets but do not establish equal FLOPs, memory use or wall-clock latency across Gemma and LLaDA. The numbers above are the manuscript’s historical open-generation measurements, not new results from the ongoing accuracy campaign. “Full suite” means all task benchmarks at multiple inference budgets, not necessarily every question within a dataset. Do not turn this contextual statement into “most DLM papers never evaluate reduced-NFE task accuracy.” DiffuLLaMA Appendix C.5 / Table 11 is a genuine additional task-score comparison missed in the initial audit; its multiple-choice evaluation uses likelihood scoring elsewhere, so it should not be silently equated with BYOD's generated-answer protocol. DiffuCoder also tests four coding tasks at halved steps, and LLaDA2.0 explicitly uses a representative benchmark subset for score/TPF analysis. These remain documented in [the corrected ten-paper audit](reduced_nfe_audit.md). Negative findings are limited to the inspected versions/results; this is not a citation-ranked or systematic frequency survey. The literature context does not supply BYOD task accuracy at low NFE or remove its reported quality gap.

- [ ] **U3 — Reduced-NFE task accuracy remains future work**, unless separately selected: e.g. 2/4 tokens transferred per step on fixed paired items with unchanged output budgets. The current campaign expands sample counts at the original NFE settings; this literature check does not add runs.
- [ ] **U4 — Measured quality/latency trade-offs remain future work:** document hardware, batch size and timing procedure; retain the limitation and avoid a wall-clock speedup claim until measured.

### Q3 — Training/evaluation length mismatch

Training caps total sequence length at 256; some evaluations allow 256 answer tokens plus the prompt. This may contribute to degradation, but its contribution has not been isolated.

- [ ] **U5 — Audit prompt+answer lengths/truncation per model/task** and compare within/beyond-range performance. A causal attribution needs an appropriate controlled intervention; otherwise report the diagnosis as provisional.

### W1 — Exposure and knowledge retention

Use the expanded shared training-data response above, including the already instruction-tuned parent clarification, descriptive before/after interpretation, mixture breakdown and supporting sources. [Insert verified historical split/filtering evidence, the matched-AR-control limitation/future-work statement, and exact manuscript changes: D1–D4. Preserve the distinction between train-split legitimacy and the adaptation confound.]

### W2 — Novelty and objective choices

Use the shared LAD response and inheritance table. [Insert L2–L4 and practical evidence U1/U3/U4 if available; state what remains unablated. Emphasize demonstrated feasibility/cost and four-family transfer.]

</details>
