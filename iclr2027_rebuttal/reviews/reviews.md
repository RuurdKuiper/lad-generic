# ICLR 2027 reviews

Source: user-provided review export. Original preserved verbatim in [reviews_original.txt](reviews_original.txt). Formatting below changes only headings, whitespace, and export separators. Reviewer wording, including missing text, is preserved.

## Review index

| Reviewer | Rating | Confidence | Response |
|---|---|---|---|
| [mNeh](#reviewer-mneh) | 2 — Weak rejection | 2 | [Response template](../reviewer_responses.md#reviewer-mneh) |
| [dPsL](#reviewer-dpsl) | 2 — Weak rejection | 2 | [Response template](../reviewer_responses.md#reviewer-dpsl) |
| [fC22](#reviewer-fc22) | 1 — Clear rejection | 4 | [Response template](../reviewer_responses.md#reviewer-fc22) |


## Reviewer mNeh

Posted: 22 Oct 2026, 10:45. Modified: 06 Nov 2026, 14:33. Visibility in export: Everyone. [Revisions](https://openreview.net/revisions?id=vYnu400TXw)


### Paper Summary

The paper proposes BYOD, which is a LoRA-based method converting frozen autoregressive models into diffusion language models. The method is applied to four model families, which requires 3.1 to 4 hours on a single GPU. The authors evaluated the performance, generation quality, and bidirectional attention. For the main result, BYOD-Gemma reaches 50.6% average accuracy compared to 51.9% for LLaDA, although the performance and the quality remains below the autoregressive baselines.

### Presentation

2: Generally understandable, but requires substantial effort in places.

### Informativeness

2: I learned something interesting or useful.

### Soundness

2: I have minor or fixable concerns about the paper’s soundness.

### Critical Strengths

- The one strength of BYOD that I want to point out is that the conversion provides a practical way to convert an autoregressive model to a diffusion language model with a limited compute. Furthermore, the evaluation on four different model families adds generalizability to the method.
- The comparison to the original autoregressive model was meaningful for understanding what features are preserved after the conversion and where the performance drops. This is especially important for future research since we can have a better view of what needs to be improved.

### Critical Weaknesses

The most critical weakness that I found is the lack of experimental support on the existing LoRA-based conversion methods. LAD already claims a conversion using LoRA and bidirectional attention, while the paper lacks the comparison against it. The ablation on different hyperparameters that are related to LoRA is lacking and also, it is not clear whether the additional parameter provides a meaningful tradeoff between the conversion cost and performance.
Furthermore, the benchmark evaluation uses only 125 examples per task and does not report uncertainty estimates. This makes it difficult to judge how reliable the small average gap against LLaDA is. Since competitive performance at a low conversion cost is a major reason to use the method, I would want stronger evidence for this comparison.
Reference: Kuiper, R. J. A., de Groot, L., van Es, B., van Smeden, M., & Bagheri, A. (2025). LAD: LoRA-Adapted Diffusion. Proceedings of EMNLP 2025: System Demonstrations, pp. 97–110.

### Questions For Authors

- Can the authors compare BYOD against LAD using the same training data and budget? How much does performance change with a smaller LoRA rank?
- Does the reported proximity to LLaDA hold on larger benchmark subsets, with confidence intervals for the paired differences?

### Flag For Ethics Review

No

### Rating

2: Weak rejection

### Confidence

2: I have broad familiarity with this field but little or no direct research experience on this topic.


## Reviewer dPsL

Posted: 21 Oct 2026, 09:40. Modified: 06 Nov 2026, 14:33. Visibility in export: Everyone. [Revisions](https://openreview.net/revisions?id=tO5yanIwY4)


### Paper Summary

BYOD converts four pretrained autoregressive model families into masked diffusion models using attention-only LoRA and a shared training recipe. Conversion takes a few single-GPU hours, although generation quality remains below the AR parents and often below LLaDA.

### Presentation

3: Clear and easy to follow.

### Informativeness

2: I learned something interesting or useful.

### Soundness

2: I have minor or fixable concerns about the paper’s soundness.

### Critical Strengths

- The conversion recipe is simple and accessible to groups with limited training hardware.
- Testing four model families with their AR parents gives useful practical evidence.
- The paper clearly reports quality failures, low-NFE limitations, and the difference between training cost and inference speed.

### Critical Weaknesses

- The recipe is not compared with a matched-budget LoRA conversion baseline such as LAD. Without rank and trainable-module ablations, the benefit of the specific BYOD choices is unclear.
- Each task uses only 125 fixed examples, without uncertainty estimates. The 1.3-point mean gap to LLaDA is therefore hard to interpret, and MMLU-Pro gives AR 2,048 output tokens but diffusion only 128.
- Generation quality remains a large limitation. Math and code lose substantial accuracy versus the AR parents, and even 128-step generation has worse perplexity than LLaDA.

### Questions For Authors

- How does BYOD compare with LAD or a simple LoRA conversion control at the same token and compute budget, and how sensitive is it to rank and target modules?
- Do the main comparisons hold on full benchmarks or with paired confidence intervals, using matched output limits for MMLU-Pro?
- Can you show an infilling or constrained-generation task where the conversion provides a useful capability at an acceptable quality and latency?

### Flag For Ethics Review

No

### Details Of Ethics Concerns

NA

### Rating

2: Weak rejection

### Confidence

2: I have broad familiarity with this field but little or no direct research experience on this topic.


## Reviewer fC22

Posted: 17 Oct 2026, 05:03. Modified: 06 Nov 2026, 14:33. Visibility in export: Everyone. [Revisions](https://openreview.net/revisions?id=XkRYKqVN20)


### Paper Summary

This paper introduces the method BYOD which converts instruction-tuned AR LMs into masked diffusion LMs with bidirectional attention mask. The method uses rank-1024 LoRA on Q/V with frozen base weights. It is trained on a mixture of instruction, multiple-choice, math and code data. Each conversion uses 102.4M tokens and takes roughly 4 h on one GPU. It is applied to Gemma 2 9B, Llama 3.1 8B, Qwen2.5 7B and Ministral 8B. The converted models are compared with their frozen AR parents and LLaDA 8B Instruct on nine benchmarks on Phi-4 perplexity and Distinct-n of open-ended generations, and on a right-context copy test. The best model, BYOD-Gemma, averages 50.6% vs 51.9% for LLaDA and 65.7% for its parent.

### Presentation

3: Clear and easy to follow.

### Informativeness

1: I learned little or nothing new from this paper.

### Soundness

1: I have significant concerns about the paper’s soundness that do not appear easy to address.

### Critical Strengths

1. A cheap, uniform, reproducible conversion recipe with candid reporting. One fixed configuration converts four different model families in single-GPU hours. The best model comes within 1.3 points of LLaDA on the paper's harness (Table 3). The limitations are stated openly (Sec. 7).

### Critical Weaknesses

1. The evaluation cannot support the comparative claims.
   - All benchmarks use 125-example subsets (App. D), giving about  points of uncertainty per task, but no intervals are reported. Yet the text interprets differences of 0.5-1.3 points (BYOD-Gemma vs LLaDA; 25k vs 50k updates).
   - Four AR-parent scores cannot come from 125 examples: HumanEval .740/.890/.940 and Gemma MBPP .740 (Table 3).
   - The training mixture includes the MMLU, HellaSwag, GSM8K and MBPP training splits (Sec. 3.3), while the AR parents get no comparable fine-tuning. So the claimed knowledge retention and the "conversion gap" are confounded with task-format exposure.
2. Limited novelty and no demonstrated benefit of the converted models.
   - The recipe combines known components; the paper itself credits LAD with first showing that LoRA induces diffusion generation (Sec. 2). Its own choices (rank, Q/V-only targets, label shift, loss weights) are not ablated.
   - All benchmarks decode one token per step (Table 8), so parallel decoding is never tested. Where NFE is reduced, quality degrades sharply: BYOD-Gemma perplexity is 14.56 at 32 NFE vs 3.01 for its parent (Table 12).
   - With no latency results and large math/code drops (e.g. Qwen MATH-500 .352 vs .784), the contribution rests on conversion cost alone.

### Questions For Authors

1. How were the four non- AR scores in Table 3 obtained? Can you report full-benchmark results with confidence intervals?
2. What are benchmark accuracies at reduced NFE (e.g. 2-4 tokens per step), and the wall-clock latency vs the AR parents?
3. Training sequences are capped at 256 tokens (Table 7), yet GSM8K/MATH/HumanEval decode 256 tokens plus the prompt (Table 8). How much of the math/code gap does this length mismatch explain?

### Flag For Ethics Review

No

### Rating

1: Clear rejection

### Confidence

4: I have substantial direct research experience on this topic.


## Export issues

The fC22 review has missing text in “giving about  points of uncertainty per task” and “four non- AR scores”. No missing values or words have been inferred. All numerical assertions above are reviewer statements, not independently verified findings.
