# Breadth of model evaluation: contextual comparison

Checked 8 November 2026 against the local BYOD main table and the primary sources below. This is a targeted comparison, not a comprehensive ranking of evaluation effort.

## BYOD count

The main accuracy table reports **ten model/checkpoint configurations on each of nine tasks**, yielding **90 model–task cells**:

- Four primary BYOD conversions: Gemma, Llama-25k, Qwen and Ministral.
- One additional BYOD checkpoint: Llama-50k.
- Four unchanged AR parents, with the same Llama parent reused for both Llama diffusion checkpoints.
- One independently evaluated external diffusion baseline: LLaDA-8B-Instruct.

This is nine model identities plus a second training-duration checkpoint, not ten independent architectures or ten independent training seeds. Published LLaDA scores, other published reference systems, the separate merged-model ablation, open-generation NFE/checkpoint sweeps, and the right-context experiment are excluded from the ten-column count.

The submitted protocol states 125 examples/task. If every cell used exactly that denominator, the main table would represent 11,250 model–question evaluations. **That is nominal arithmetic, not a verified completed-run count:** the disputed AR denominators must be resolved before presenting it as an audited total.

“Entire nine-task suite” means all nine tasks, not all questions in each dataset. Do not use “full benchmarks” to describe the 125-item subsets.

## Comparison with other papers

| Paper / source | Model/checkpoint breadth in the inspected main comparison | Evaluation coverage / counting caveat |
|---|---|---|
| BYOD, local Table 3 | **10 common-harness columns**: 5 BYOD checkpoints + 4 AR parents + LLaDA | All 9 task rows populated; fixed subsets claimed, denominator audit pending |
| [LAD](https://aclanthology.org/2025.emnlp-demos.8.pdf), Tables 1–2 | **9 configurations**: 6 converted size/rank variants + 3 AR parents | 5 benchmark tasks, plus fluency metrics; converted backbones belong to the Llama family |
| [LLaDA](https://arxiv.org/html/2502.09992), Tables 1–2 | **6 explicitly common-protocol checkpoints**: LLaDA/Llama 3/Llama 2, each Base and Instruct; **14 model entries overall** | 15 task rows in Base table and 9 in Instruct table; other entries include imported results and missing cells. Separate scaling/ablation models excluded |
| [Dream 7B](https://arxiv.org/html/2508.15487), Tables 1–2 | **4 explicitly common-protocol Base checkpoints**; **4 Instruct entries** in the second table; **10 entries across both tables** | Base table has 16 tasks; Instruct table 8. Do not assume every listed result was independently rerun merely from its presence in the table |
| [DiffuLLaMA](https://arxiv.org/html/2410.17891), Table 1 / Section 4 | **9 configurations**: 3 converted models + 3 AR parents + 2 SEDD sizes + Plaid | 9 task groupings including infilling; three ROUGE components for one task are not three extra datasets. Conversion covers GPT-2 and Llama; parent scales differ substantially |
| [DiffuCoder](https://arxiv.org/html/2506.20639), Table 1 | **10 unstarred, author-evaluated configurations**; **14 entries including 4 marked as imported** | Coding-focused suite with HumanEval/MBPP and their plus variants, BigCodeBench full/hard. EvalPlus is an aggregate, not an additional independent dataset |

Base and Instruct are counted as separate checkpoints, as are different ranks, sizes and additional fine-tuning stages. These counts concern main comparisons, not every run or intermediate checkpoint anywhere in the papers. Task counts do not imply equal numbers of evaluated questions or comparable GPU cost.

### Source-specific counting notes

**LAD:** Table 1 lists six size/rank settings; Table 2 compares them with three parent models. This is substantial within-family coverage rather than cross-family conversion evidence. [Paper](https://aclanthology.org/2025.emnlp-demos.8.pdf).

**LLaDA:** each main table lists seven models, with three starred as evaluated under the shared protocol. Base/Instruct yield six starred checkpoint configurations across the tables; the fourteen listed entries must not all be called independently rerun. [Tables 1–2](https://arxiv.org/html/2502.09992).

**Dream:** Table 1 has six entries, of which four are explicitly starred as common-protocol; Table 2 adds four instruction-tuned entries. This establishes table breadth, not a blanket self-evaluation count for all ten. [Tables 1–2](https://arxiv.org/html/2508.15487).

**DiffuLLaMA:** Table 1 rows are GPT2-S, SEDD-S, DiffuGPT-S, GPT2-M, SEDD-M, DiffuGPT-M, Plaid1B, LLaMA2 and DiffuLLaMA. Section 4 describes implementing tasks across models. [Table 1 / Section 4](https://arxiv.org/html/2410.17891).

**DiffuCoder:** twelve Base/Instruct/GRPO rows plus two commercial rows give fourteen. Four starred rows are imported: OpenCoder Base/Instruct, GPT-4o and Mercury. This leaves ten author-evaluated configurations. [Table 1 caption and entries](https://arxiv.org/html/2506.20639).

## Conclusion for rebuttal wording

BYOD is broad in the number of comparable-scale parent/conversion pairs and the use of a shared recipe across four adapted families. Its ten-column main comparison is larger than the explicitly common-protocol subset in some reference studies and comparable to other substantial studies. The evidence does **not** support “unusually many models compared with all other DLM papers” or “more total evaluation compute than these papers.” Several reference papers evaluate more tasks, different scales, larger datasets, or many additional ablations.

Use this breadth to explain the initial allocation of evaluation compute. It does not replace uncertainty estimates or establish that 125 items suffice for small numerical differences. The cost-aware response is a shared, expanded paired comparison for the priority models, while labeling any remaining 125-item comparisons accurately.
