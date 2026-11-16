# Published base-to-Instruct results supporting the training-data response

Checked 15 November 2026. These are external published scores, not BYOD measurements or a common-harness experiment. The purpose is to illustrate the relevance of upstream post-training, not establish membership of benchmark training/test examples.

| Model family | Task | Base | Instruct / IT | Difference | Original-report location |
|---|---|---:|---:|---:|---|
| Qwen2.5 7B | HumanEval | 57.9% | 84.8% | +26.9 pp | [Qwen2.5 v2](https://arxiv.org/html/2412.15115v2), Tables 4 and 8 |
| Qwen2.5 7B | MATH | 49.8% | 75.5% | +25.7 pp | Same tables |
| Llama 3.1 8B | HumanEval | 37.2% | 72.6% | +35.4 pp | [The Llama 3 Herd of Models](https://arxiv.org/html/2407.21783), Tables 10 and 18 |
| Gemma 2 9B | MBPP | 52.4% | 59.2% | +6.8 pp | [Gemma 2 report](https://arxiv.org/html/2408.00118), Table 17 |

## Source and comparability checks

- **Qwen:** the author's HumanEval example is verified. The report describes both SFT and reinforcement-learning stages; a base/Instruct score difference must not be attributed to SFT alone. Its evaluation sections distinguish pretrained and instruction-tuned settings. We have not established exact prompt/decoding parity between those sections.
- **Llama:** Table 1 and its following paragraph explicitly state that all results in the report are for **Llama 3.1**, abbreviated as “Llama 3.” The table pair therefore concerns the selected parent family, not an April-to-July model-generation comparison. The official [Llama 3.1 card](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct) also reports the 72.6 instruction-tuned result. Do not instead subtract Qwen's Table 4 **Llama 3 8B** value from Table 8 **Llama 3.1 8B**: those table labels differ in model version.
- **Gemma:** Table 17 directly compares PT and IT variants within the same report on few-shot benchmarks. Use this MBPP pair rather than combining Google's base score with a different organization's instruction score. The Qwen report's Gemma results use different evaluation settings and are not interchangeable with Google's values.
- **Ministral:** no numerical pair is inserted because an exact matched base/Instruct comparison for the selected 8B checkpoint has not been verified. Do not substitute Mistral 7B for Ministral 8B.

## Interpretation adopted in the rebuttal

The parents already reflect upstream adaptation and can exhibit substantial base-to-Instruct differences. Published score changes do not identify training-example membership or prove contamination; partial disclosure of training sources is not a complete item-level exposure history. They are not matched causal ablations of SFT, benchmark-specific training, or additional AR versus diffusion adaptation. Keep BYOD's unmatched additional-exposure limitation and matched-AR-control discussion explicit.

The condensed R05 response cites selected comparisons in prose; the full table and checks remain here. It does not use these external scores to rank BYOD, replace measured parent baselines, or claim that prior instruction tuning eliminates the reviewer's confound.

## Upstream data lineage and decontamination

| Source | Verified disclosure | Limit |
|---|---|---|
| [General Qwen2.5 v2](https://arxiv.org/html/2412.15115v2), Sections 4–4.1 | Family-level SFT scale; Math CoT and Coder instruction-data inputs | No checkpoint-specific item inventory established for the general 7B parent |
| [Qwen2.5-Math](https://arxiv.org/html/2409.12122), Sections 3.1.1–3.1.2 | GSM8K/MATH training splits explicitly supply annotated SFT queries | Does not identify which examples entered the general model |
| Same specialist report, Section 4 | 13-gram/LCS screening; MATH train/test similarity examples filtered in Table 1 | No GSM8K-specific hit count or proof of retained test overlap |

This is stronger than merely speculating about specialist training sources, but still not a checkpoint-level membership audit. The [official Math blog's decontamination section](https://qwenlm.github.io/blog/qwen2.5-math/#decontamination) corroborates the filtering account. Preserve that safeguard in the response. Do not turn “screened against GSM8K” into “found GSM8K test contamination,” or transfer the specialist filter guarantee to every component of the general model's mixture. The earlier pasted suggestion that specialist GSM8K training-split use was wholly unspecified is superseded by its explicit SFT disclosure.

## Additional AR precedents and the disclosure argument

| Primary source | Verified practice | Scope |
|---|---|---|
| [Tülu 3](https://arxiv.org/html/2411.15124), Section 6.1, Table 22 | RLVR uses GSM8K Train (7,473 prompts) and MATH Train (7,500 prompts) | Direct split-specific precedent in general-purpose AR post-training; this stage is RL, not SFT |
| [DeepSeekMath](https://arxiv.org/html/2402.03300), Section 3.1 | Its 776K-example SFT collection includes GSM8K/MATH problems with tool-integrated solutions | Direct benchmark-source SFT precedent in a specialist AR model; the cited paragraph does not explicitly label these two sources' splits |

Together with Qwen2.5-Math's explicit split-specific SFT disclosure, these support describing benchmark-training use as a documented AR post-training practice. They do not measure how common it is, establish that most mixtures are unknown, or prove membership in undisclosed checkpoints. BYOD's detailed reporting makes its exposure visible; this may make the issue more apparent, but no evidence here establishes that BYOD is unusually transparent relative to the field as a whole (Tülu 3 is itself highly open). Use “absence of disclosure does not establish exclusion” and “reasonable possibility,” rather than assume hidden exposure. Keep unmatched additional adaptation explicit.

## Tülu datasets: reuse and benchmark lineage

Checked 15 November 2026. Tülu names a model family, a recipe, and several distinct training artifacts, not one interchangeable dataset.

| Model / family | Documented reuse | Primary source |
|---|---|---|
| Tülu 3 | Released SFT mixture for its own family | [Dataset card](https://huggingface.co/datasets/allenai/tulu-3-sft-mixture) |
| Dream 7B | SFT collection drawn from Tülu 3 and SmolLM2 | [Report, Section 4.3](https://arxiv.org/html/2508.15487) |
| Marin 8B Instruct | Tülu 3 SFT mixture among named SFT sources | [Official card, Instruct datasets](https://huggingface.co/marin-community/marin-8b-instruct) |
| OLMo 2 (November 2024 7B/13B) | OLMo-specific Tülu 3 SFT variant, followed by separate DPO/RLVR | [Official 13B card and checkpoint table](https://huggingface.co/allenai/OLMo-2-1124-13B-Instruct) |

The [standard mixture card](https://huggingface.co/datasets/allenai/tulu-3-sft-mixture) lists 939,344 examples, including 89,982 FLAN v2, 49,980 Persona GSM, 149,960 Persona MATH and 64,312 NuminaMath-TIR prompts. The [older Tülu 2 card](https://huggingface.co/datasets/allenai/tulu-v2-sft-mixture) also lists FLAN v2, including deliberate CoT sampling. FLAN's [original task configuration](https://github.com/google-research/FLAN/blob/main/flan/v2/task_configs.py) defines `cot_gsm8k` from `gsm8k_train.tsv` with 7,473 examples. This verifies benchmark-training data in an upstream source, but no row-level audit here establishes how many GSM8K examples survive each sampled/filtered Tülu mixture or downstream training run.

The Persona names must not be interpreted as direct benchmark membership: [Tülu 3 Section 3.1.2](https://arxiv.org/html/2411.15124) describes synthetic persona-conditioned math/code prompts. Its Section 3.2 documents evaluation decontamination; Table 8 reports removing 11.3% of NuminaMath-TIR against MATH evaluation overlap. This documents filtering, not retained contamination. Section 6.1 explicitly uses original GSM8K/MATH training splits for RLVR, which is a separate dataset and stage. Neither Dream's use of SFT data nor another model's Tülu-data tag establishes use of that RLVR collection. We have several verified adopters, not a census or an independent-model count inferred from Hub download/derivative statistics.

## Consolidated source lookup for R05

| Source | What it establishes | What it does not establish |
|---|---|---|
| [Qwen2.5 report](https://arxiv.org/html/2412.15115), Section 4.1 | Prior SFT includes mathematical CoT with public/synthetic query sources | Verified membership of particular benchmark examples |
| [Qwen2.5-Math report](https://arxiv.org/html/2409.12122), Sections 3.1 and 4 | Explicit benchmark-training sources and evaluation-overlap screening in the specialist pipeline | Exact retained examples in general Qwen2.5-7B-Instruct; retained test contamination |
| [Tülu 3 report](https://arxiv.org/html/2411.15124), Section 6.1 and Table 22 | Explicit GSM8K and MATH training-split use in AR RLVR | SFT use of those exact splits, or identical exposure in our parents |
| [DeepSeekMath](https://arxiv.org/html/2402.03300), Section 3.1 | GSM8K/MATH problems with annotated solutions used in SFT | This paragraph alone does not explicitly identify their split or establish exposure in other checkpoints |
| [Llama report](https://arxiv.org/html/2407.21783), Sections 4.2–4.3 | Prior SFT and capability-targeted code/math/reasoning data | Equal exposure to BYOD's additional mixture |
| [Gemma 2 report](https://arxiv.org/html/2408.00118), Section 4 | Prior SFT and RLHF, with synthetic/human-generated data | Complete example-level exposure history |
| [Ministral card](https://huggingface.co/mistralai/Ministral-8B-Instruct-2410) | The selected parent is instruction fine-tuned | Detailed benchmark membership |
| [Dream 7B](https://arxiv.org/abs/2508.15487) | Tulu 3/SmolLM2 SFT; OpenCoder among pretraining sources | Identical retained data to BYOD |
| [LLaDA](https://arxiv.org/abs/2502.09992), [release policy](https://github.com/ML-GSAI/LLaDA#pre-training-and-supervised-fine-tuning) | Disclosed training scale; actual training data not released | Exposure to any particular benchmark item |
| [d1](https://dllm-reasoning.github.io/media/preprint.pdf) | Task-specific benchmark-training use, including explicit GSM8K train/test separation | A matched general-purpose conversion control |
| [Tulu 3 mixture](https://huggingface.co/datasets/allenai/tulu-3-sft-mixture) | Documented mathematical/reasoning sources | Those same components survived BYOD's filtering |

## Beyond mathematics: what the Tülu sources actually establish

The original [FLAN task configuration](https://github.com/google-research/FLAN/blob/main/flan/v2/task_configs.py) lists StrategyQA, CREAK, QASC, eSNLI, ECQA, Sensemaking, AQUA and QED alongside GSM8K in its CoT source loop. Each is read from a corresponding `*_train.tsv` file under the `train` split. This is direct evidence of broader benchmark training sources in upstream FLAN, which is a named Tülu SFT component. It is not a row-level audit of the sampled/filtered Tülu mixture or any downstream checkpoint. The Tülu card does not separately enumerate these benchmarks as direct sources; do not rewrite upstream lineage as verified retained membership.

Tülu's [Section 6.1](https://arxiv.org/html/2411.15124) separately lists GSM8K, MATH and an instruction-following source for RLVR. Its IF examples combine Tülu 2 instructions with constraints from IFEval's taxonomy; this is not evidence of an original IFEval training split. Its Persona examples are synthetic. The condensed response therefore presents concrete GSM8K/MATH precedents, broader non-math upstream sources, and a qualified inference of possible wider exposure, without claiming field-wide frequency or checkpoint-specific hidden membership.
