Thank you for your careful review. We revised the manuscript and expanded the experiments and data. We address your comments below and refer to our responses to other reviewers where questions overlap to save space.

Weakness 1.1

> *125-example subsets ...*

Please see our response to Reviewer mNeh, Weakness 2 and Question 2, for the expanded evaluation, confidence intervals and revised Gemma–LLaDA comparison. We also withdrew the longer-training accuracy-gain claim: Llama averages 47.80% at 50k updates versus 47.93% at 25k.

Weakness 1.2

> *Four AR-parent scores ...*

Thank you for catching this. We corrected intermediate scores and incorrect counts using verified results (Appendix D).

Weakness 1.3

> *The training mixture includes ...*

Although we agree that exposing the models to the training sets of their benchmarks might have improved results, using this data is not actually uncommon. Qwen2.5-Math explicitly uses GSM8K and MATH training examples for SFT ([Section 3.1](https://arxiv.org/html/2409.12122)), and d1 trains on GSM8K/MATH training splits and evaluates on held-out questions ([Appendix B.1.1](https://dllm-reasoning.github.io/media/preprint.pdf)). However, most models, like LLaDA for instance, do not release their training data at all. 

We agree that additional task exposure confounds a direct causal interpretation of the parent-to-conversion difference. However, our main question is whether an inexpensive conversion works across different models. The parents provide a reference, rather than a target we claim to outperform. Broad benchmark capabilities after only 400,000 training samples are indicative of substantial knowledge retention: learning this much knowledge from such a small additional training set is unlikely.

Weakness 2.1

> *The recipe combines ...*

Please see our response to Reviewer dPsL, Weakness 1 and Question 1, for the LAD comparison, rank ablation and distinction between a shared working recipe and optimal settings. Removing the AR label shift implements same-position reconstruction. We have not separately ablated label alignment or loss weights.

Weakness 2.2

> *One token per step ...*

We have indeed not evaluated the full benchmark suite at reduced NFE. Parallel denoising is instead tested in our open-generation experiments: Perplexity- and diversity metrics are an established way to study this trade-off, as in [MDLM](https://arxiv.org/html/2406.07524), [SEDD](https://arxiv.org/pdf/2310.16834) and [Time-Agnostic Masked Models](https://arxiv.org/html/2409.02908). Other studies do report reduced-step benchmark performance, but often only on a few tasks: [LLaDA](https://arxiv.org/html/2502.09992) tests only mathematics/coding tasks and [Dream](https://arxiv.org/html/2508.15487) uses a one task (Countdown). Showing (full) benchmark performance with reduced NFE is thus not standard practice. 

We corrected the perplexity claim: the 2.7–5.0 times AR range applies only at 64 NFE. At 128 NFE, BYOD-Gemma scores 4.33 versus its parent's 3.01. We do not claim faster inference at matched quality.

Weakness 2.3

> *No latency results ...*

Please see our response to Reviewer dPsL, Weakness 3, for the mathematics and code results, remaining perplexity gap and conversion-cost comparison. These support useful diffusion capabilities after inexpensive conversion, rather than equivalence to the AR parents or LLaDA. Wall-clock latency remains unmeasured.

Question 1

> *How were ... scores ... obtained ...*

Thank you for catching this. Intermediate scores remained in the submitted table; we replaced them with verified results. Please see our response to Reviewer mNeh, Weakness 2 and Question 2, for expanded coverage and uncertainty estimates.

Question 2

> *What are benchmark accuracies at reduced NFE ...*

As discussed in W2.2, we report perplexity- and diversity metrics at 32 and 64 NFE for 128-token outputs, but have not measured benchmark accuracies at those budgets. A reduced-NFE benchmark accuracy sweep remains outside this study's scope.

Wall-clock profiling also remains future work. However, merging folds the LoRA weights into the parent projections and removes the separate adapter branches, so the adapters need not add significant inference overhead compared to other diffusion models. 

Question 3

> *Training sequences are capped ...*

Handling variable-length sequences is part of our training setup: examples have different prompt and answer lengths, and each batch is padded to its longest sequence. However, the reviewer is correct that the limits differ: 256 tokens covers the complete training sequence, whereas evaluation allows up to 256 answer tokens plus the prompt.

How length affects quality thus remains an interesting question. Simply comparing shorter and longer examples would mix length effects with  question difficulty. A controlled comparison with a model trained on longer sequences would more directly test this, but is beyond the scope of this study.