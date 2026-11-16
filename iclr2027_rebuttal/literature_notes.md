# Evidence checked for the response

Checked 8 November 2026. Targeted primary-source checks, not a systematic review. The earlier blanket “0/10 omit both” statement is not supported; see the expanded [ten-paper audit](reporting_audit.md).

## LAD

Sections 2–3 and Table 1 document Q/V LoRA, frozen backbones, bidirectional attention, combined masking/structural corruption, Llama 1B/3B/8B variants, and multiple ranks. Table 1 reports 16.0 hours for 8B/r1024. [Published LAD paper](https://aclanthology.org/2025.emnlp-demos.8.pdf).

The scientific question is whether the mask-only recipe transfers across families. LAD alone does not settle this; different corruption makes a controlled objective comparison informative. Four tested families support cross-family evidence, not a proof for every AR model. Broader priority claims require further literature verification. Shared authorship is author-supplied internal context; use third-person citations in public replies.

## Training sources and availability

| Model | Verified information | Limit of inference |
|---|---|---|
| LLaDA | 2.3T pretraining tokens; 4.5M SFT pairs; Appendix B.1 describes broad sources and processing. [Paper](https://arxiv.org/html/2502.09992) | Its description does not establish membership of each benchmark item. |
| LLaDA release | Official repository explicitly says training data will not be provided. [Repository](https://github.com/ML-GSAI/LLaDA#pre-training-and-supervised-fine-tuning) | Supports non-release of the actual corpus, not contamination or absence of any composition disclosure. |
| Dream 7B | Section 4.3 names Dolma 1.7, OpenCoder, DCLM-Baseline and Tulu 3/SmolLM 2 SFT sources. [Paper](https://arxiv.org/html/2508.15487) | “No training sources are disclosed” would be false. |
| DiffuLLaMA | Appendix B.1 describes 65B adaptation tokens from SlimPajama/Starcoder in a 7:3 mixture. [Paper](https://arxiv.org/html/2410.17891) | Named sources do not identify every realized example or all inherited exposure. |

Source-name disclosure, release of the realized corpus, benchmark membership and a contamination audit are distinct. Neither non-disclosure nor web-scale training proves exposure to a particular benchmark. Do not assign a probability of exposure without evidence.

Legitimate training-split use is not itself test leakage. It can still confound the comparison with the unchanged AR parent. Unknown external-model exposure does not remove that confound. BYOD's actual conversion dataset revision and evaluated IDs need auditing before claiming verified held-out evaluation.

LLaDA also investigates leakage using a fresh GSM8K-like task (Appendix B.8); do not imply it takes no precautions. [Paper](https://arxiv.org/html/2502.09992).

## Confidence-interval reporting

The checked main benchmark comparisons use point estimates without accompanying benchmark CIs: LLaDA Tables 1–2, Dream Table 1, DiffuLLaMA Tables 1–2. [LLaDA](https://arxiv.org/html/2502.09992), [Dream](https://arxiv.org/html/2508.15487), [DiffuLLaMA](https://arxiv.org/html/2410.17891). HTML searches also found no “interval” in these versions; this does not prove absence from all figures, versions, code or artifacts.

This initial three-paper check has now been expanded in [reporting_audit.md](reporting_audit.md). The expanded audit remains result-specific, does not establish field-wide rarity, and records explicit evaluation-count disclosures. Tool-reported standard errors, training-seed variation, paired intervals and significance tests are different forms of evidence. Few-shot counts are not evaluation sample counts.

Prefer accepting the request for uncertainty directly. Reporting convention does not reduce the uncertainty of a 125-item evaluation. Expanding coverage and reporting intervals address related but separate concerns.

## Dataset variants

The individual dataset-card sources are linked in [sampling_plan.md](sampling_plan.md). Current loader: `byod-reproducible/src/diffusion_lm/benchmarks.py`, `_benchmark_spec`. It selects sanitized MBPP and GPQA-Main; reconcile this with the original run manifests. No gated GPQA examples were accessed or reproduced.

## Training-data response update: d1 and Tulu 3

Author's full original wording is preserved in [training_data_response_original.txt](author_notes/training_data_response_original.txt). The response includes the four supplied sources, with tracking parameters removed.

- **d1:** Section 4.1 specifies separate task-specific RL models. Appendix B.1.1 explicitly identifies GSM8K training/test splits and MATH training data for the MATH-500 task. This supports a concrete precedent, not a claim about all DLM training or matched experimental conditions. [Primary paper](https://dllm-reasoning.github.io/media/preprint.pdf).
- **Tulu 3:** the source list includes Persona MATH, Persona GSM and NuminaMath-TIR. Dataset names alone do not establish copied benchmark instances or leakage. [Primary dataset card](https://huggingface.co/datasets/allenai/tulu-3-sft-mixture).
- **BYOD percentages:** Section 3.3 of the local paper gives nominal weights yielding 18.957% explicit benchmark sources, 15.750% Tulu 3 and 18.943% OpenCoder. These are specified mixture shares, not audited historical sample counts or necessarily the shares in training prefixes.
- **Filtering caveat:** current `tools/byod_data/dataset_builder.py::format_tulu` rejects source labels containing `math` or `code`. Do not infer that all published Tulu components reached BYOD. Its historical implementation and retained source distribution remain open evidence items.
- **Scope:** nominal dataset size is one million examples; primary training processes 400,000 examples, with the longer Llama run processing 800,000. Keep dataset construction and consumed training exposure separate.

No historical overlap audit or control experiment was completed by adding these sources.

## Instruction-tuned parents and the interpretation of conversion gaps

The run mapping in `paper/RESULTS_NOTES.md` identifies `google/gemma-2-9b-it`, `meta-llama/Llama-3.1-8B-Instruct`, `Qwen/Qwen2.5-7B-Instruct` and `mistralai/Ministral-8B-Instruct-2410`. “Unchanged” denotes no extra BYOD-stage AR adaptation, not absence of the original instruction tuning.

| Primary source | Checked support |
|---|---|
| [Qwen2.5 technical report](https://arxiv.org/html/2412.15115), Section 4.1 | Mathematical SFT introduces CoT data from Qwen2.5-Math, including public-dataset, K–12 and synthetic query sources. This is evidence in the general Qwen2.5 report, not a substitution of the separate specialist model for our parent. |
| [Llama report](https://arxiv.org/html/2407.21783), Sections 4.2–4.3 | SFT includes human/rejection-sampled and synthetic capability-targeted data; code and math/reasoning are explicit post-training capabilities. |
| [Gemma 2 report](https://arxiv.org/html/2408.00118), Section 4 | Instruction post-training uses SFT and RLHF, including synthetic/human-generated prompt-response data and internal/public sources. |
| [Ministral model card](https://huggingface.co/mistralai/Ministral-8B-Instruct-2410) | Explicitly describes the selected checkpoint as instruction fine-tuned. |

These reports disclose parts of the post-training procedures, so avoid saying they disclose nothing. They do not establish complete benchmark item histories for our exact checkpoints. Prior instruction tuning clarifies the starting point; it does not match BYOD's additional data exposure. The gap is a descriptive change after the complete adaptation/conversion procedure, with matched extra AR fine-tuning retained as a useful future control rather than promised rebuttal work.

## Quantitative base-to-Instruct context

Added verified original-report comparisons to the shared training-data response: Qwen2.5 7B HumanEval 57.9% → 84.8% and MATH 49.8% → 75.5%; Llama 3.1 8B HumanEval 37.2% → 72.6%; Gemma 2 9B MBPP 52.4% → 59.2%. These support the relevance of upstream post-training, with explicit limits on causal attribution and dataset-membership inference. See [sources, exact table locations and model/protocol checks](post_training_evidence.md). No benchmark outcomes, control experiments or GPU runs were changed by this literature addition.

### Qwen training-lineage follow-up

Verified the general-to-specialist data link and the specialist report's explicit benchmark-training sources. Added the decontamination account with correct scope and no inference of retained test leakage; see [the evidence note](post_training_evidence.md). The exact general-parent item inventory remains unresolved, and the matched additional-AR-training limitation remains unchanged.


## Mistral-family priority check — 16 November 2026

Primary-source checks found prior diffusion conversions in the broader family:

- TESS 2, ACL 2025, Sections 4.2–4.3: adaptation of Mistral 7B v0.1/v0.3,
  including full diffusion adaptation and instruction tuning. This uses simplex
  diffusion rather than BYOD's mask-only LoRA recipe.
  https://aclanthology.org/2025.acl-long.1029.pdf
- Nemotron-Labs-Diffusion, arXiv:2607.05722, Section 5.1: starts from pretrained
  Ministral 3 models, with AR continued pretraining followed by joint AR/diffusion
  training. This is a newer parent family/checkpoint than Ministral-8B-Instruct-2410.
  https://arxiv.org/html/2607.05722

Do not infer that BYOD is the first diffusion model anywhere in the Mistral
family from failure to locate a prior conversion of the exact 2410 checkpoint.
The author elected to keep this correction in rebuttal materials for now;
no new prior-work citations or priority correction were applied to the working
manuscript. The generality/accessibility argument remains about the shared,
low-budget LoRA recipe and evidence across the four selected families.
