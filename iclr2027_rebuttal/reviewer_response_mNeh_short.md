Thank you for your careful review and constructive feedback. We have revised the manuscript, expanded the benchmark evaluation, added uncertainty estimates and a LoRA-rank ablation, and clarified our comparisons and claims. We address your comments individually below.

Weakness 1

> *The most critical weakness that I found ...*

**Response:**

We understand this concern. However, LAD has a significantly different generation objective; it combines masking and structured corruption, resulting in a different inference paradigm. BYOD instead uses mask-only MDLM, and focusses on whether a reproducible recipe works across model families, whereas  LAD tested on only one model family.

We do agree that a more in-depth comparison is granted, and have added LAD's published 8B benchmark results alongside BYOD-Llama in Appendix B (Table 5). However, these were not obtained in the same harness and thus not a controlled comparison.

To address the hyperparameter question, we have added a rank ablation on Llama 3.1 8B in Appendix C (Figure 5 and Table 6), testing rank 128, 512, 1024 and 2048. Rank 1024 was originally chosen to balance validation quality with single-GPU training, which was a major target of this study: it allowed batch size 16 on an 80GB A100 or batch size 8 on a 40GB A100. Rank 2048 lowers validation loss further, but doubles the adapter parameters and takes longer per update. Its loss reduction per added rank unit is smaller: going from 1024 to 2048 adds twice as many rank units as going from 512 to 1024. Earlier exploratory tests of other attention projections, MLP targets and learning rates informed the recipe; a full sweep of these interacting choices was outside this study's scope.

Weakness 2

> *Furthermore, the benchmark evaluation uses only 125 examples per task ...*

**Response:**

We appreciate this point and agree that the comparison needs stronger evidence. We have now doubled the target from 125 to 250 questions on eight tasks and all 164 HumanEval questions across all ten model configurations.  We also revised some benchmarks sligthly due to some discrepancies in scoring, which are now solved. These changes are documented in Appendix D.

We also appreciate the need for confidence intervals, which we have now included in our results. For context, the main comparisons we inspected in ten prominent diffusion language model papers present point estimates without accompanying confidence intervals, and often omit per-task sample counts beside the scores: [LLaDA](https://arxiv.org/html/2502.09992), [Dream](https://arxiv.org/html/2508.15487), [DiffuLLaMA](https://arxiv.org/html/2410.17891), [Scaling up Masked Diffusion Models](https://arxiv.org/html/2410.18514), [MDLM](https://arxiv.org/html/2406.07524), [SEDD](https://arxiv.org/pdf/2310.16834), [Time-Agnostic Masked Models](https://arxiv.org/html/2409.02908), [DiffuCoder](https://arxiv.org/html/2506.20639), [LLaDA2.0](https://arxiv.org/pdf/2512.15745) and [Mercury](https://arxiv.org/html/2506.17298). 

We nevertheless agree that providing both counts and uncertainty estimates strengthens our evaluation and have therefore included confidence intervals for all benchmark results. Table 3 gives the updated scores using the 250 samples, and 95% confidence intervals for the nine-task averages. Appendix D gives the full per-task table with 95% confidence intervals, the actual sample counts and the calculation details.

BYOD-Gemma now averages 52.43%, compared with 49.55% for LLaDA. This does not prove that the BYOD-Gemma architecture itself is superior, as the difference is still not signicant when accounting for multiple testing. Moreover, BYOD-Gemma's 9B parent is larger than 8B LLaDA, and their training histories differ. The comparison rather shows that LoRA conversion can produce useful diffusion capabilities at low training cost.

Question 1

> *Can the authors compare BYOD against LAD  ...*

**Response:**

A LAD control using the same data and training budget would most directly test our mask-only formulation, but was outside of the scope of this study. However, Appendix B (Table 5) now compares published LAD results with BYOD under different protocols. Appendix C examines rank under otherwise fixed settings. Smaller ranks give higher validation loss, while rank 2048 improves it further at greater training cost. Rank 1024 was chosen as a practical balance within a single-A100 training budget; the loss reduction per added rank unit decreases at higher ranks.

Question 2

> *Does the reported proximity to LLaDA hold ...*

**Response:**

Yes. As described in W2, we now use 250 questions per task. BYOD-Gemma averages 52.43%, versus 49.55% for LLaDA, with a difference of +2.88 percentage points and a nominal 95% interval of [+0.74, +4.98]. This interval is unadjusted for multiple comparisons. We make no superiority claim; the models also differ in size and training history. Table 3 and Appendix D give the updated results and uncertainty estimates.