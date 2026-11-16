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

To address the hyperparameter question, we have added a rank ablation on Llama 3.1 8B in Appendix C (Figure 5 and Table 6), testing 128, 512, 1024 and 2048 under otherwise fixed settings. Rank 1024 was chosen to balance validation quality with single-GPU training: in the original implementation, it allowed batch size 16 on an 80GB A100 or batch size 8 on a 40GB A100. Rank 2048 lowers validation loss further, but doubles the adapter parameters and takes longer per update. Its loss reduction per added rank unit is smaller: going from 1024 to 2048 adds twice as many rank units as going from 512 to 1024. This supports a practical resource trade-off rather than an optimal rank. We did not benchmark these ablation models, so lower validation loss does not establish higher task accuracy. Earlier exploratory tests of other attention projections, MLP targets and learning rates informed the recipe; a full sweep of these interacting choices was outside this study's scope.
#### mNeh-W2

> *Furthermore, the benchmark evaluation uses only 125 examples per task and does not report uncertainty estimates. This makes it difficult to judge how reliable the small average gap against LLaDA is. Since competitive performance at a low conversion cost is a major reason to use the method, I would want stronger evidence for this comparison.*

**Response:**

We appreciate this point and agree that the comparison needs stronger evidence.We have now doubled the target from 125 to 250 questions on eight tasks and evaluated all 164 HumanEval questions, using the same questions across models. Across ten model/checkpoint configurations, the completed results contain 21,640 model–question outcomes, a net increase of 10,570 over the recovered historical results. We would like to note that while we reported the number of samples used for evaluation in our manuscript, this is often not customary for studies of this type.

We also appreciate the need for confidence intervals, which we have now included in our results. However, we would again like to note that these are rarely reported; a review of ten top diffusion language model papers found that none of them had accompanying confidence intervals, or reported their sample size for benchmarks: [LLaDA](https://arxiv.org/html/2502.09992), [Dream](https://arxiv.org/html/2508.15487), [DiffuLLaMA](https://arxiv.org/html/2410.17891), [Scaling up Masked Diffusion Models](https://arxiv.org/html/2410.18514), [MDLM](https://arxiv.org/html/2406.07524), [SEDD](https://arxiv.org/pdf/2310.16834), [Time-Agnostic Masked Models](https://arxiv.org/html/2409.02908), [DiffuCoder](https://arxiv.org/html/2506.20639), [LLaDA2.0](https://arxiv.org/pdf/2512.15745) and [Mercury](https://arxiv.org/html/2506.17298). 

However, we agree with the reviewer that this information is actually important, and have therefore now included confidence intervals for all benchmark results. Table 3 gives the updated scores using the 250 samples, and 95% confidence intervals for the nine-task averages. Appendix D gives the full per-task table with 95% confidence intervals, the actual sample counts and the calculation details.

BYOD-Gemma now averages 52.43%, compared with 49.55% for LLaDA. The paired difference is +2.88 percentage points for BYOD-Gemma, with a 95% difference interval of [+0.74, +4.98]. This does not prove that the BYOD-Gemma architecture is superior: While BYOD-Gemma was the strongest observed conversion among five BYOD configurations, its 9B parent is larger than 8B LLaDA, and their training histories differ. The comparison rather shows that LoRA conversion can produce useful diffusion capabilities at low training cost; it does not isolate LoRA versus full fine-tuning. We have updated all benchmark figures, tables and comparative claims, including withdrawing the earlier claim of an average accuracy gain from longer Llama training.

### Questions for authors

#### mNeh-Q1

> *Can the authors compare BYOD against LAD using the same training data and budget? How much does performance change with a smaller LoRA rank?*

**Response:**

As discussed in W1, Appendix B compares published LAD results with BYOD; we have not rerun LAD with matched training data and budget. Appendix C examines rank under otherwise fixed settings. Smaller ranks give higher validation loss, while rank 2048 improves it further at greater adapter and training cost. Rank 1024 was chosen as a practical balance within a single-A100 training budget; the loss reduction per added rank unit decreases at higher ranks. We did not run downstream benchmarks for these ablations, so cannot quantify their effect on task accuracy.
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

We appreciate this concern. BYOD builds on LAD's use of LoRA and bidirectional attention, but it's method of diffusive generation and the objective of the studies is significantly different; LAD combines masking with structured corruption, while BYOD instead tests a shared mask-only MDLM recipe, which made direct comparison infeasible. Furthermore BYOD introduces and tests a generalizable recipe for Gemma, Llama, Qwen and Ministral models, while LAD only tested Llama models. We have clarified this relationship in the main text and added LAD's published 8B benchmark results alongside BYOD-Llama in Appendix B (Table 5). The training and evaluation settings differ, so this provides context rather than a direct control.

To address the ablation question, we have added a rank study on Llama 3.1 8B in Appendix C (Figure 5 and Table 6), testing 128, 512, 1024 and 2048 under otherwise fixed settings. Rank 1024 was chosen to balance validation quality with training on a single A100: batch size 16 on the 80GB variant, or 8 on the 40GB variant, in the original implementation. Rank 2048 gives lower validation loss, but doubles the adapter parameters and takes longer per update. The gain per added rank unit decreases, since 1024→2048 adds twice as many rank units as 512→1024. We therefore present 1024 as a practical resource trade-off, rather than a uniquely optimal rank. These are validation-loss comparisons; we have not measured downstream benchmark accuracy for the ablation models.

Finally, trainable-module and learning rate ablations were performed earlier during exploratory tests and informed our configuration. We have described these choices and their limits in Appendix C. These tests were not a systematic trainable-module ablation; a full search over the interacting choices was outside this study's scope, as we already had the different 'model families' as hyperparameters here as well. We therefore present Q/V adapters and rank 1024 as a shared working recipe, rather than claiming that these choices are uniquely optimal.

#### dPsL-W2

> *Each task uses only 125 fixed examples, without uncertainty estimates. The 1.3-point mean gap to LLaDA is therefore hard to interpret, and MMLU-Pro gives AR 2,048 output tokens but diffusion only 128.*

**Response:**

We appreciate this concern. We have now expanded the evaluation to 250 shared questions on eight tasks and all 164 HumanEval questions. Across ten model/checkpoint configurations, this gives 21,640 model–question outcomes, a net increase of 10,570 over the recovered historical results. Table 3 reports the updated nine-task averages with 95% confidence intervals; Appendix D gives the expanded per-task scores and confidence intervals. 

We would like to note that while we reported the number of samples used for evaluation in our manuscript, this is often not customary for studies of this type.

We also appreciate the need for confidence intervals, which we have now included in our results. However, we would again like to note that these are rarely reported; a review of ten top diffusion language model papers found that none of them had accompanying confidence intervals, or reported their sample size for benchmarks: [LLaDA](https://arxiv.org/html/2502.09992), [Dream](https://arxiv.org/html/2508.15487), [DiffuLLaMA](https://arxiv.org/html/2410.17891), [Scaling up Masked Diffusion Models](https://arxiv.org/html/2410.18514), [MDLM](https://arxiv.org/html/2406.07524), [SEDD](https://arxiv.org/pdf/2310.16834), [Time-Agnostic Masked Models](https://arxiv.org/html/2409.02908), [DiffuCoder](https://arxiv.org/html/2506.20639), [LLaDA2.0](https://arxiv.org/pdf/2512.15745) and [Mercury](https://arxiv.org/html/2506.17298). 

BYOD-Gemma now averages 52.43%, versus 49.55% for LLaDA, with a paired difference of +2.88 percentage points and a 95% difference interval of [+0.74, +4.98]. This interval is unadjusted for multiple comparisons or selecting the strongest conversion. We therefore do not claim superiority: Gemma is larger and has a different training history. The results are shown rather to support the feasibility of low-cost LoRA conversion.

We understand the MMLU-Pro output limits might have been confusing. We found that the AR models often reasoned before giving their answer, and thus did not finish their answer in lower token budgets, so we allowed up to 2,048 new tokens; this is a maximum, not a fixed output length, and answers often ended much earlier. The diffusion models generally gave shorter, direct answers, so we used a shorter canvas to reduce evaluation cost. We found no diffusion-model answers that were cut short by the token budget. 

#### dPsL-W3

> *Generation quality remains a large limitation. Math and code lose substantial accuracy versus the AR parents, and even 128-step generation has worse perplexity than LLaDA.*

**Response:**

We agree that the losses on mathematics and code are important limitations. Our aim is to show that a small LoRA adaptation can produce useful diffusion capabilities approaching those of a pretrained diffusion model, rather than outperforming the AR parents or establishing full equivalence.

The expanded results in Table 3 show mixed but often close task scores. BYOD-Gemma reaches 24.4% on MATH-500 and 43.6% on MBPP, compared with 26.0% and 42.8% for LLaDA. Its GSM8K score is higher (68.8% versus 59.6%), while HumanEval remains lower (29.9% versus 34.8%). These are descriptive comparisons between models with different sizes and training histories.

BYOD's additional conversion takes 3.1–4.0 GPU-hours per model, including 3.2 for Llama and 4.0 for Gemma, whereas LLaDA reports 130,000 H800 GPU-hours for pretraining alone ([paper](https://arxiv.org/html/2502.09992)). BYOD reuses an already pretrained AR model, whose earlier training cost is excluded; the hardware also differs. This illustrates the accessibility of conversion, rather than a matched comparison of total training cost.

The perplexity gap remains: at 128 NFE, BYOD scores 4.33–6.21 versus 2.79 for LLaDA. We retain this limitation and have clarified in the Discussion that task-score proximity does not imply overall equivalence. As proposed in the Conclusion, a promising next step is partial or full diffusion fine-tuning initialized from the merged model, testing whether quality can improve without eroding retained capabilities. This remains a direction for future work, not a demonstrated result.

### Questions for authors

#### dPsL-Q1

> *How does BYOD compare with LAD or a simple LoRA conversion control at the same token and compute budget, and how sensitive is it to rank and target modules?*

**Response:**

As explained in W1, Appendix B compares published LAD results with BYOD, but we have not run a matched-token, matched-compute LAD or alternative conversion control. This is also not feasible due to the different training settings necessary to train with the significanlty different LAD training objective. 
We did perform a rank ablation, shown in Appendix C where we compare ranks 128, 512, 1024 and 2048 under otherwise fixed settings. Rank 1024 balances validation loss with the original single-A100 training budget. Rank 2048 improves loss further, but doubles the adapter parameters; its gain per added rank unit is smaller. We performed earlier exploratory tests which informed our Q/V LoRA targets and other hyperparameters such as learning rate, but we have not systematically quantified sensitivity to these paramaters. We therefore present a working recipe, rather than uniquely optimal hyperparameter choices. A more detailed is also included under 'dPsL-W1'.

#### dPsL-Q2

> *Do the main comparisons hold on full benchmarks or with paired confidence intervals, using matched output limits for MMLU-Pro?*

**Response:**

As described under 'dPsL-W2', we now evaluate 250 shared questions on eight tasks and all 164 HumanEval questions; only HumanEval uses its full test set. BYOD-Gemma minus LLaDA is +2.88 percentage points, with a nominal paired 95% interval of [+0.74, +4.98] (Table 3 and Appendix D). The intervals are unadjusted, and we make no superiority claim. MMLU-Pro output limits remain different: up to 2,048 new tokens for AR and a 64-token diffusion canvas, as explained in W2 and Appendix G. We have not rerun this comparison with matched output limits, so the results do not establish an equal-budget comparison.

#### dPsL-Q3

> *Can you show an infilling or constrained-generation task where the conversion provides a useful capability at an acceptable quality and latency?*

**Response:**

We agree that infilling and constrained generation are interesting research directions. However, our study focuses text generation capabilities of diffusion models, and more specifically on whether a low-cost LoRA recipe can convert AR models into functional diffusion models, and which capabilities they retain after conversion.

We have therefore not expanded the study to evaluate a realistic infilling or constrained-generation benchmark. We did already include our right-context copy test (Figure 2 and Appendix J) which confirms access to later context, but is a diagnostic rather than evidence of practical infilling. A dedicated evaluation of task quality, constraint satisfaction and wall-clock latency against suitable baselines would be a valuable extension, but is outside the present study's scope.

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

#### fC22-W1.1

> *All benchmarks use 125-example subsets (App. D), giving about  points of uncertainty per task, but no intervals are reported. Yet the text interprets differences of 0.5-1.3 points (BYOD-Gemma vs LLaDA; 25k vs 50k updates).*

**Response:**

We appreciate this concern. We have now expanded the evaluation to 250 shared questions on eight tasks and all 164 HumanEval questions. Across ten model/checkpoint configurations, this gives 21,640 model–question outcomes, a net increase of 10,570 over the recovered historical results.

For context, the main comparisons we inspected in ten prominent diffusion papers present point estimates without accompanying confidence intervals, and often omit per-task sample counts beside the scores: [LLaDA](https://arxiv.org/html/2502.09992), [Dream](https://arxiv.org/html/2508.15487), [DiffuLLaMA](https://arxiv.org/html/2410.17891), [Scaling up Masked Diffusion Models](https://arxiv.org/html/2410.18514), [MDLM](https://arxiv.org/html/2406.07524), [SEDD](https://arxiv.org/pdf/2310.16834), [Time-Agnostic Masked Models](https://arxiv.org/html/2409.02908), [DiffuCoder](https://arxiv.org/html/2506.20639), [LLaDA2.0](https://arxiv.org/pdf/2512.15745) and [Mercury](https://arxiv.org/html/2506.17298). Some report evaluation counts elsewhere. We agree that reporting uncertainty makes our comparisons easier to interpret.

Table 3 now reports the updated nine-task averages with 95% confidence intervals. Appendix D gives the full per-task results, Wilson intervals and actual sample counts. Average intervals use 20,000 bootstrap resamples within each task, with equal task weights; model differences preserve question pairing.

BYOD-Gemma now averages 52.43%, versus 49.55% for LLaDA: a paired difference of +2.88 percentage points, with a nominal 95% interval of [+0.74, +4.98]. These intervals are unadjusted for multiple comparisons or selecting the strongest conversion. We make no superiority claim, particularly given Gemma's larger size and different training history.

The longer Llama run averages 47.80%, compared with 47.93% at 25k updates. Its paired difference is −0.14 percentage points, with a nominal 95% interval of [−1.81, +1.49]. We have therefore removed the earlier claim of an average accuracy gain from longer training. All benchmark figures, tables and comparative claims have been updated; the main contribution remains feasible conversion at low additional training cost.

#### fC22-W1.2

> *Four AR-parent scores cannot come from 125 examples: HumanEval .740/.890/.940 and Gemma MBPP .740 (Table 3).*

**Response:**

We thank the reviewer for catching this error. Table 3 incorrectly retained intermediate results, and the blanket statement of 125 examples did not reflect the actual sample counts. We have now replaced these entries with the verified expanded results: 250 questions per task and all 164 HumanEval questions. The corrected table and Appendix D report the actual counts and confidence intervals.

#### fC22-W1.3

> *The training mixture includes the MMLU, HellaSwag, GSM8K and MBPP training splits (Sec. 3.3), while the AR parents get no comparable fine-tuning. So the claimed knowledge retention and the "conversion gap" are confounded with task-format exposure.*

**Response:**

We thank the reviewer for raising this concern. All four AR parents are already instruction-tuned checkpoints, with prior exposure to instruction-following, mathematics and coding formats. Published base/Instruct scores illustrate the importance of this post-training: Qwen2.5-7B reports 57.9% HumanEval for its base model and 84.8% for Instruct ([Tables 4 and 8](https://arxiv.org/html/2412.15115v2)). This does not establish which benchmark examples the parent encountered.

Using benchmark training splits during post-training is a documented practice. Qwen2.5-Math explicitly uses GSM8K and MATH training examples for SFT ([Section 3.1](https://arxiv.org/html/2409.12122)); Tülu 3 uses these training splits for reinforcement learning ([Section 6.1](https://arxiv.org/html/2411.15124)). There is also a diffusion example: d1 trains on GSM8K/MATH training splits and evaluates on held-out questions ([Appendix B.1.1](https://dllm-reasoning.github.io/media/preprint.pdf)). These examples do not prove identical exposure in our parents or baselines. LLaDA, for instance, does not release its training data ([official repository](https://github.com/ML-GSAI/LLaDA#pre-training-and-supervised-fine-tuning)); missing disclosure does not establish that benchmark training examples were excluded.

Shared instruction mixtures provide another route for such exposure. Dream uses Tülu 3 SFT data ([report](https://arxiv.org/html/2508.15487)), whose [mixture includes FLAN v2](https://huggingface.co/datasets/allenai/tulu-3-sft-mixture). FLAN's [source configuration](https://github.com/google-research/FLAN/blob/main/flan/v2/task_configs.py) includes GSM8K and other benchmark training sources, including StrategyQA and QASC. This documents upstream data sources, not exact retained examples in every downstream model; Tülu's benchmark-trained reinforcement-learning stage is separate from its SFT mixture.

We report our own sources and proportions explicitly. About 19% of the specified mixture comes from benchmark training splits, within one shared instruction mixture rather than separate task-specific adaptations. We used training splits and explicitly filtered normalized prompt duplicates against held-out benchmark prompts, as described in Section 3.3. This addresses direct training/test duplication, while additional exposure to task formats remains a separate issue.

We agree that this additional training can influence the scores. The conversion gap therefore describes the change from the released instruction-tuned parent to its further-adapted diffusion counterpart; it does not isolate the effect of the diffusion objective. A matched additional AR fine-tuning control would help separate these effects and remains useful future work.

Our central question is whether a shared, inexpensive conversion works across different model families and yields useful performance alongside diffusion references such as LLaDA. The AR parents provide a reference for capability changes, rather than a target we claim to outperform. Broad capabilities after only 400,000 training-example presentations per primary conversion are consistent with substantial reuse of pretrained knowledge, but do not separate retained knowledge from learning during adaptation. The supported result is feasible cross-family conversion with a small additional training budget, not equivalence to other models or a causal estimate of knowledge retention.

#### fC22-W2 — overall concern

> *Limited novelty and no demonstrated benefit of the converted models.*

#### fC22-W2.1

> *The recipe combines known components; the paper itself credits LAD with first showing that LoRA induces diffusion generation (Sec. 2). Its own choices (rank, Q/V-only targets, label shift, loss weights) are not ablated.*

**Response:**

We agree that the individual components have precedents, including LAD's use of LoRA and bidirectional attention. Our contribution is a shared, reproducible mask-only conversion recipe and evidence that it works across Gemma, Llama, Qwen and Ministral. Each primary conversion takes 3.1–4.0 hours on one GPU, making diffusion-model training and experimentation accessible without a large training cluster. 

We have expanded the comparison with LAD in the main text and Appendix B, covering implementation settings and published benchmark performance. LAD combines masking with structural corruption and tests several sizes within the Llama family; BYOD tests mask-only MDLM conversion across four families. The published results use different training and evaluation protocols, so they do not constitute a matched control.

We have also added the rank study in Appendix C, testing 128, 512, 1024 and 2048 under otherwise fixed settings. Rank 1024 was chosen to balance validation quality with single-A100 training: batch size 16 on the 80GB variant, or 8 on the 40GB variant, in the original implementation. Rank 2048 does lower validation loss further, but doubles the adapter parameters and takes longer per update. Its loss reduction per added rank unit is smaller, since 1024 to 2048 adds twice as many rank units as 512 to 1024. Earlier exploratory tests informed the Q/V targets, learning rate and loss weights, but were not a systematic controlled sweep. Removing the AR label shift implements our same-position reconstruction target, as explained in the Method. We have not separately ablated label alignment or loss weights in this study, and do not claim that every configuration choice is optimal.

The converted models are useful research artifacts even when they do not outperform models trained for much longer. Their merged checkpoints also provide a starting point for the partial or full diffusion fine-tuning proposed in our Conclusion. Whether this initialization improves later training remains to be tested; our demonstrated benefit is accessible conversion across the four tested families.

#### fC22-W2.2

> *All benchmarks decode one token per step (Table 8), so parallel decoding is never tested. Where NFE is reduced, quality degrades sharply: BYOD-Gemma perplexity is 14.56 at 32 NFE vs 3.01 for its parent (Table 12).*

**Response:**

The reviewer is correct in that we have not evaluated the full benchmark suite at reduced NFE. Parallel denoising is instead tested in our open-generation experiments: Figure 3 and Appendix I report perplexity and Distinct-1/2/3 for 128-token outputs at 32, 64 and 128 NFE. The 32- and 64-NFE settings update multiple positions per step. Perplexity- and diversity metrics are an established way to study this trade-off, as in [MDLM](https://arxiv.org/html/2406.07524), [SEDD](https://arxiv.org/pdf/2310.16834) and [Time-Agnostic Masked Models](https://arxiv.org/html/2409.02908). Other studies do report reduced-step benchmark performance, but often only on selected tasks: [LLaDA](https://arxiv.org/html/2502.09992) tests only mathematics/coding tasks, [Dream](https://arxiv.org/html/2508.15487) uses a single task (Countdown) and [DiffuLLaMA](https://arxiv.org/html/2410.17891) only compares four multiple-choice tasks. Showing (full) benchmark performance with reduced token budgets is thus not necessarily standard practice. 

We also would like to thank the reviewer for highlighting an error in our previous Results text. We incorrectly described the 2.7–5.0× AR-perplexity range as applying across NFE budgets; this applied only at 64 NFE, and we have revised our manuscript accordingly. A better comparison for the AR-parent would be BYOD-Gemma's 4.33 perplexity score at 128 NFE, compared with 3.01 for its AR parent. As can be seen, these are much closer together. 

Reduced-NFE task benchmarks and measured quality–latency trade-offs remain useful future work, as reflected in our Limitations section. Our demonstrated efficiency concerns conversion training; we do not claim an inference-speed advantage at matched quality.


#### fC22-W2.3

> *With no latency results and large math/code drops (e.g. Qwen MATH-500 .352 vs .784), the contribution rests on conversion cost alone.*

**Response:**

We agree that the mathematics/code losses and lack of latency measurements are important limitations. The expanded evaluation still shows a large Qwen MATH-500 gap: 30.4% for BYOD-Qwen versus 73.6% for its AR parent. We do not claim to outperform the AR parents or demonstrate faster inference at matched quality.

However, these task difficulties are also present in our diffusion reference. LLaDA scores 26.0% on MATH-500 and 34.8% on HumanEval under our harness. BYOD-Gemma reaches 24.4% and 29.9%, respectively, and 43.6% on MBPP compared with LLaDA's 42.8% (Table 3). These mixed, descriptively similar scores show that inexpensive LoRA conversion can yield useful capabilities alongside a model pretrained and instruction-tuned as a DLM. Differences in model size and training history prevent treating this as proof of equivalence or superiority.

The contribution combines this performance with a shared conversion recipe that works across four model families in 3.1–4.0 GPU-hours per model. LLaDA reports 130,000 H800 GPU-hours for pretraining alone ([paper](https://arxiv.org/html/2502.09992)). Our figure excludes the AR parents' earlier training, and the hardware differs; it describes the small additional cost of obtaining a diffusion model from an existing checkpoint.

The study therefore establishes accessible conversion and useful diffusion capabilities across the tested families. Improving mathematics, code and perplexity, and establishing a favorable quality–latency trade-off, remain future work, as stated in our Discussion and Limitations.

### Questions for authors

#### fC22-Q1

> *How were the four non- AR scores in Table 3 obtained? Can you report full-benchmark results with confidence intervals?*

**Response:**

We thank the reviewer for catching these inconsistencies. As explained in W1.2, intermediate results remained in the submitted table. We have corrected the entries using verified per-question outputs and expanded evaluation to 250 shared questions on eight tasks and all 164 HumanEval questions. These are expanded subsets, rather than full test sets except for HumanEval. Table 3 reports the updated averages with confidence intervals; Appendix D gives the per-task results, intervals and actual sample counts, as discussed in W1.1.

#### fC22-Q2

> *What are benchmark accuracies at reduced NFE (e.g. 2-4 tokens per step), and the wall-clock latency vs the AR parents?*

**Response:**

As discussed in W2.2, we report perplexity- and diversity metrics at 32 and 64 NFE for 128-token outputs, but have not measured task-benchmark accuracies at those budgets. Other papers provide selected-task analyses; repeating the full benchmark suite at every NFE budget is not a uniform reporting convention. A reduced-NFE accuracy sweep remains outside this study's scope.

Wall-clock profiling also remains future work. Merging folds the LoRA weights into the parent projections and removes the separate adapter branches, so the adapters need not add inference overhead. However, architectural similarity alone does not establish latency comparable to LLaDA: the backbone, sampler, implementation and hardware also matter. We therefore do not claim measured inference speedups or latency parity; our demonstrated efficiency concerns conversion training, as stated in the Limitations.

#### fC22-Q3

> *Training sequences are capped at 256 tokens (Table 7), yet GSM8K/MATH/HumanEval decode 256 tokens plus the prompt (Table 8). How much of the math/code gap does this length mismatch explain?*

**Response:**

Handling variable-length sequences is part of our training setup: examples have different prompt and answer lengths, and each batch is padded to its longest sequence, rounded to a multiple of 16. The converted models can also generate at shorter and longer lengths than the training cap. However, the reviewer is correct that the limits differ: 256 tokens covers the complete training sequence, whereas evaluation allows up to 256 answer tokens plus the prompt.

How length affects quality remains an interesting question. Simply comparing shorter and longer examples would mix length effects with differences in question difficulty and the reasoning or code required. Evaluating the same questions with different answer-canvas lengths could test sensitivity to inference length, although shorter canvases can also truncate otherwise correct answers. A controlled comparison with a model trained on longer sequences would more directly test whether the training cap limits performance. However, these experiments are beyond the scope of this study.

Our expanded results nevertheless show broadly comparable math/code performance to LLaDA. This supports the usefulness of the conversion despite the short training sequences, without establishing that length has no effect on quality.