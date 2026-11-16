Thank you for your careful review. We expanded evaluation and added intervals and a rank study.

Weakness 1

> *The recipe is not compared ...*

**Response:**

BYOD builds on LAD's LoRA and bidirectional attention. LAD uses masking plus structured corruption within Llama; BYOD tests mask-only MDLM across Gemma, Llama, Qwen and Ministral. Although it was not feasible to run a LAD control with matched data and budget, we have added Appendix B (Table 5), which compares our results with the published LAD 8B results.

Furthermore, we added rank ablation testing in Appendix C (Figure 5, Table 6). We test ranks 128, 512, 1024 and 2048 on Llama 3.1 8B under fixed settings. Rank 1024 was originally chosen as it allowed batch size 16 on an 80GB A100 or 8 on a 40GB A100. Rank 2048 still lowers validation loss but doubles adapter parameters and takes longer per update. Also, its loss gain per added rank unit is smaller. We did perform earlier, experimental module/learning-rate tests to inform our Q/V and rank choices, but these were not systematic, instead prioritising cross-family testing.

Weakness 2

> *Each task uses only 125 fixed examples ...*

**Response:**

We now use 250 shared questions on eight tasks and all 164 HumanEval questions across ten model configurations. We also rescored some results after we found some discrepancies; Appendix D documents these changes. We also included confidence intervals, with an updated Table 3 showing averages and Appendix D gives per-task scores and intervals.

Although we agree that reporting confidence intervals strengthens results, we'd like to note that adding confidence intervals is not often done in these studies, which why it was originally omitted; we inspected ten prominent diffusion papers which all also omit confidence intervals: [LLaDA](https://arxiv.org/html/2502.09992), [Dream](https://arxiv.org/html/2508.15487), [DiffuLLaMA](https://arxiv.org/html/2410.17891), [Scaling up Masked Diffusion Models](https://arxiv.org/html/2410.18514), [MDLM](https://arxiv.org/html/2406.07524), [SEDD](https://arxiv.org/pdf/2310.16834), [Time-Agnostic Masked Models](https://arxiv.org/html/2409.02908), [DiffuCoder](https://arxiv.org/html/2506.20639), [LLaDA2.0](https://arxiv.org/pdf/2512.15745) and [Mercury](https://arxiv.org/html/2506.17298). 

After expanding the benchmarks BYOD-Gemma averages 52.43% versus LLaDA's 49.55%. However, this does not prove superiority, as the difference is not significant after compensating for multiple testing. Moreover, Gemma is larger and has a different training history.

Finally, the reason for the larger AR budget for MMLU-Pro: On MMLU-Pro, AR models often reasoned before answering and needed longer budgets. The 2,048-token limit is a maximum; answers often ended earlier. Diffusion answers were usually short and direct, so a shorter canvas reduced cost. We found none cut short by the budget.

Weakness 3

> *Generation quality remains a large limitation ...*

**Response:**

We agree that the BYOD models underperform in math/code tasks, but this is a feature of many diffusion models, not just BYOD. BYOD-Gemma scores similar to LLaDA on these tasks, with 24.4/26.0% on MATH-500, 43.6/42.8% on MBPP, 68.8/59.6% on GSM8K and 29.9/34.8% on HumanEval (Table 3). These mixed results support useful capabilities approaching a pretrained DLM, not equivalence or superiority to AR parents.

At 128 NFE, BYOD perplexity is 4.33–6.21 versus LLaDA's 2.79, showing that perplexity is indeed the largest gap between LlaDa and the BYOD models, and we explicitly cite this as the gap we still would like to close. We therefore propose in our manuscript that our recipe can be used as a starting point for for full diffusion fine-tuning from merged models to improve quality while preserving capabilities.

Question 1

> *How does BYOD compare with LAD ...*

**Response:**

Please see our response at Weakness 1.

Question 2

> *Do the main comparisons hold ...*

**Response:**

Please see our response at Weakness 2.

Question 3

> *Can you show an infilling ...*

**Response:**

We agree that infilling and constrained generation are interesting research directions. However, our study focuses text generation capabilities of diffusion models, and more specifically on whether a low-cost LoRA recipe can convert AR models into functional diffusion models, and which capabilities they retain after conversion.

We have therefore not expanded the study to evaluate a realistic infilling or constrained-generation benchmark. We did already include our right-context copy test (Figure 2 and Appendix J) which confirms access to later context, but is a diagnostic rather than evidence of practical infilling. A dedicated evaluation of task quality, constraint satisfaction and wall-clock latency against suitable baselines would be a valuable extension, but is outside the present study's scope.