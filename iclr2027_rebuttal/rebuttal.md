# BYOD — working author response and remaining work

**Internal draft; not ready to post.** Shared response prose, evidence notes and open-work checklists coexist here. Individual reviewer comments and blank answer fields are in [reviewer_responses.md](reviewer_responses.md). No new evaluation or manuscript revision is claimed as complete. Resolve placeholders and remove internal notes before posting individual OpenReview comments. The numerical comment cap remains unverified.

Sources: [literature notes](literature_notes.md). Calculations and dataset links: [sampling plan](sampling_plan.md). Evidence/change log: [changes.md](changes.md).

## Direction agreed with the author

Emphasize conversion feasibility, accessible compute and one mask-only recipe across four tested model families, rather than superior benchmark performance. LAD is the author's prior work; use third-person citations in public replies. Distinguish inherited LoRA/bidirectional adaptation from the new empirical question. “Universally converts any autoregressive model” exceeds the evidence; use “cross-family transfer” with the tested scope stated explicitly.

Use a two-stage evaluation plan: first target **250 total unique examples/task across the ten main-table configurations**, taking the full set below 250; then use remaining budget for more matched questions on **BYOD-Gemma, Gemma AR and LLaDA**. Execution has not begun. Add uncertainty without promising ±1–2 percentage-point intervals, statistical equivalence to LLaDA, or significant gains from longer training.

## General response

We thank the reviewers for recognizing BYOD's accessible conversion budget and the value of the four-family study. Our aim is to establish a practical conversion recipe rather than superior benchmark performance. BYOD builds on prior LoRA-based adaptation and investigates whether a mask-only MDLM formulation can support conversion across distinct model families under one shared configuration. We agree that the relationship to prior work and the uncertainty of the benchmark comparisons need to be clearer.

We also emphasize the breadth of the evaluation: the main table covers the entire nine-task suite for ten model/checkpoint configurations—four primary BYOD conversions, a longer-trained Llama checkpoint, their four AR parents, and LLaDA—giving 90 model–task results across four parent families. This breadth motivated the initial use of fixed evaluation subsets. It does not remove uncertainty in individual scores, so we are preparing expanded paired comparisons and explicit uncertainty estimates. “Entire suite” here refers to task coverage, not full-dataset evaluation.

[Internal: count the two Llama training-duration checkpoints separately, reuse the one AR parent, and exclude imported reference scores. The reported 125/task protocol and disputed denominators still need auditing. Expanded coverage will reflect the €100 budget and achieved runs, not an automatic promise for all ten columns.]

[Before posting: summarize only completed corrections and new results, with exact revised sections/tables.]

## Shared response: relationship to LAD — R03/R04/R11

Thank you for highlighting LAD. BYOD builds directly on its LoRA-based adaptation approach. LAD combines masking with structural perturbations; BYOD tests a mask-only MDLM objective. The additional question is whether a common conversion recipe transfers across four distinct instruction-tuned model families with a small conversion budget. We do not claim to introduce LoRA-based diffusion conversion itself. [LAD](https://aclanthology.org/2025.emnlp-demos.8.pdf).

The objective difference motivates the study and makes a controlled comparison informative. Published LAD scores cannot isolate it because training/evaluation settings differ. Clarifying the contribution does not by itself resolve the requests for matched controls and adapter ablations.

### Candidate comparison table for the revised manuscript

Put a compact version in related work, with details in the appendix, and retain a short response version. LAD entries follow Sections 2–3/Table 1 of the [published paper](https://aclanthology.org/2025.emnlp-demos.8.pdf); BYOD entries follow the local submission candidate.

| Aspect | LAD | BYOD | Relationship |
|---|---|---|---|
| Adaptation | Frozen backbone; Q/V LoRA | Frozen backbone; Q/V LoRA | Inherited |
| Attention | Bidirectional | Bidirectional | Inherited |
| Corruption | Masking + swaps, duplication, span shifts | IID masking | Changed objective |
| Scope | Llama 1B/3B/8B | Gemma, Llama, Qwen, Ministral | Expanded families |
| Rank | Multiple ranks | Shared r=1024 | Transfer setting, not optimum |
| Training time† | 16.0h, 8B/r1024 | 3.1–4.0h across families | Primarily implementation efficiencies; different protocols |
| Task benchmarks | Five | Nine | Different protocols |
| Question | Structured denoising adaptation | Cross-family mask-only conversion | Extension |

† The shorter BYOD training times primarily reflect a more efficient training implementation, including FP8 execution with a frozen backbone, rather than an intrinsic speed advantage of the mask-only objective. Our precision ablation found only small changes in the evaluated results [insert verified ablation settings, metrics and table reference]. The reported implementation uses Transformer Engine HYBRID FP8 execution with BF16 master weights; this is the precise meaning of the 8-bit training setting here. These timings come from different training protocols and do not isolate implementation, hardware, data volume or objective effects.

**Internal evidence note:** the implementation attribution and completed precision ablation are supplied by the author. The local manuscript documents FP8/BF16 settings in the complete training configuration, but the precision-ablation results have not yet been located in this workspace. Recover the existing ablation outputs and add the comparison/reference before posting; this is an evidence-recovery item, not a request to repeat an already completed experiment. Keep implementation efficiency distinct from the methodological contribution. Q/V targeting and high-rank LoRA are inherited choices.

### Remaining work

- [ ] **L1 — Clarify contributions in the paper:** align abstract, introduction, related work and discussion; add the table and implementation-efficiency footnote. Recover and cite the existing precision ablation, with settings and numerical results. State the mask-only transfer question LAD alone did not settle, without a universal or unverified first-ever claim.
- [ ] **L2 — Decide and implement a matched LAD/objective control:** common parent/checkpoint, training items/order, tokens and evaluation IDs; report measured compute and unavoidable differences. Delimit conclusions if only one family is feasible.
- [ ] **L3 — Finalize the separate rank sensitivity experiment:** update the provisional trade-off response below when the fresh rank-1024 run reaches 25k. Report validation loss, adapter parameters and measured update times; peak GPU memory was not recorded. Earlier target-module/LR explorations are design motivation, not a controlled ablation. LAD's rank sweep remains separate evidence.
- [ ] **L4 — Decide label-alignment and answer/padding-loss controls:** separate from rank/modules and not automatically resolved by a LAD comparison.

**Separate rank experiment (R04; not a replacement for benchmarked BYOD-Llama):** ranks 128, 512 and 2048 have each completed 25,000 updates using the same current mask-only recipe. The author has now requested a fresh rank-1024 run, with a $17 additional allowance, to complete a four-rank comparison under that identical recipe. All four use the same data, seed, Q/V targets, frozen normalization layers, validation examples and masks, and separately normalized answer/padding losses weighted 0.9/0.1; only rank and alpha change together. We evaluate denoising validation loss and retain the complete curves, final adapter and recovery checkpoints. No nine-task benchmark evaluation is planned for this experiment. The original BYOD-Llama checkpoint and all benchmark results remain unchanged. The old rank-1024 curve is retained as a historical reference with incompletely documented loss weighting; its close agreement with rank 2048 on the common unweighted metric does not establish a problem or a controlled rank effect. Use the fresh rank-1024 result in the matched ablation after it finishes. See [setup, provenance and interpretation limits](rank_ablation/README.md). Validation loss alone does not establish a preferred rank for benchmark accuracy or generation quality; matched LAD/objective and target-module controls remain separate questions.

**Loss-weight evidence follow-up:** the author reports that tenfold increases/decreases performed poorly in earlier experiments. Recover the exact settings and numerical results before presenting that sensitivity as evidence; do not call the current weights experimentally optimal without a supported comparison.

Avoid dismissing LAD as unsuitable merely because its corruption differs.

### Provisional rank and resource trade-off response

**Draft response\*:** We are adding a focused rank study on Llama 3.1 8B, holding the training data, update budget, Q/V targets, learning rate and loss fixed. The preliminary curves suggest diminishing validation-loss gains as rank increases. At 5,000 matched updates, increasing rank from 512 to 1024 reduces the 90/10-weighted validation loss from 1.3179 to 1.2650, a reduction of 0.0529. Increasing rank again to 2048 reduces it to 1.2545, a further reduction of 0.0105—about one fifth as large. If the final endpoints retain this pattern, it would support rank 1024 as a practical compromise between denoising validation loss and training cost under this recipe.\*

The resource trade-off is already measurable. Median training-update times are approximately 0.386 s for rank 512, 0.405 s for rank 1024 and 0.434 s for rank 2048. Rank 2048 is therefore about 12.4% slower per update than rank 512 and 7.2% slower than the current rank-1024 estimate. It also doubles the adapter parameter count relative to rank 1024, from 436.2M to 872.4M. With the same precision and optimizer, storage for adapter parameters, gradients and optimizer state scales accordingly. We did not record peak GPU memory, so we report this parameter-state cost without claiming a measured peak-VRAM comparison.\*

Our choices of Q/V targets and learning rate were informed by earlier exploratory experiments, including MLP adapters and other attention-projection targets. Those trials were not retained as a systematic controlled sweep, so we use them as design motivation rather than quantitative evidence of optimality. Rank, target modules, learning rate and backbone interact, making a full joint search a substantial additional study. Our focus is a shared, accessible conversion recipe across model families. The present ablation isolates rank under fixed choices; systematic target-module and learning-rate sensitivity remain outside its scope and useful further work.

\* **Update when the final fresh rank-1024 results are in:** replace the 5k comparison with all four matched 25k endpoints; refresh timing estimates and the figure; retain or revise the rank-1024 compromise interpretation according to those results. This is one parent and one seed, evaluated by denoising validation loss. It does not establish benchmark-accuracy or generation-quality gains, or a universal optimal rank. The original benchmarked BYOD-Llama checkpoint and all benchmark results remain unchanged.

**Internal evidence:** [rank trade-off snapshot and method](rank_ablation/RANK_TRADEOFF.md), [all matched-step comparisons](rank_ablation/rank_tradeoff_matched_steps.csv), and [source hashes/timing intervals](rank_ablation/rank_tradeoff_snapshot.json). Timings are medians of clean 100-update logging intervals, excluding validation/checkpoint work and restart-clock resets; they are not full job durations. The first three ranks shared one GPU allocation; the fresh 1024 uses the same GPU type in another allocation. The current 1024 timing estimate covers 5k updates, versus 25k for the completed ranks. The early curves do not show smaller marginal gains at every individual update, so keep the diminishing-returns claim provisional. A focused module or learning-rate control need not require an exhaustive joint sweep; those requested controls remain unquantified here.

## Shared response: training exposure and fairness — R05

Adapted from the author's [original response](author_notes/training_data_response_original.txt). Draft prose below is for refinement into an OpenReview comment; the verification notes and checklist are internal.

### Draft response

We thank the reviewer for raising this concern. All four AR models we start from are **already instruction-tuned**: Gemma 2 9B IT, Llama 3.1 8B Instruct, Qwen2.5 7B Instruct and Ministral 8B Instruct 2410. We apply our post-training to these checkpoints and compare the converted models with the released versions.

The published results show large benchmark gains following the parents' original post-training. These models have already majorly benefitted from their fine-tuning regimens. Some examples: Qwen2.5 7B, HumanEval rises from 57.9% to 84.8% and MATH from 49.8% to 75.5%. For Llama 3.1 8B, HumanEval rises from 37.2% to 72.6%. For Gemma 2 9B, MBPP rises from 52.4% to 59.2%. [Qwen, Tables 4/8](https://arxiv.org/html/2412.15115v2), [Llama, Tables 10/18](https://arxiv.org/html/2407.21783), [Gemma, Table 17](https://arxiv.org/html/2408.00118).

We report our training sources and their proportions in detail, as we believe this transparency is important. This may draw more scrutiny than when a model's training mixture is unavailable, which is often the case for these types of studies. LLaDA, for example, explicitly states that its training data are not provided. [Official repository](https://github.com/ML-GSAI/LLaDA#pre-training-and-supervised-fine-tuning). The descriptions of our AR parents' post-training also do not give a complete record of which benchmark examples they encountered. This means it's unclear whether these models have been trained on training splits of their benchmarks or not. However, there are ample indications that they have or might have, as shown below.

There are **documented examples of other models using benchmark training splits**. For example, Qwen2.5-Math explicitly uses the GSM8K and MATH training splits for SFT. General Qwen2.5 includes Math CoT data, though the reports do not specify exactly which subset. [Specialist report, Section 3.1](https://arxiv.org/html/2409.12122), [general report, Section 4.1](https://arxiv.org/html/2412.15115v2). DeepSeekMath also lists GSM8K/MATH problems as SFT sources. [Section 3.1](https://arxiv.org/html/2402.03300). There is a diffusion example too: d1 trains on GSM8K/MATH training splits and evaluates on held-out examples. [Section 4.1 and Appendix B.1.1](https://dllm-reasoning.github.io/media/preprint.pdf). Another AR model, Tülu 3 uses both GSM8K and MATH for reinforcement learning, and their dataset is often used by other models as well. [Section 6.1](https://arxiv.org/html/2411.15124).

Dream uses Tülu 3 for SFT, Marin 8B Instruct lists the Tülu SFT mixture, and OLMo 2 uses a variant. [Dream](https://arxiv.org/html/2508.15487), [Marin](https://huggingface.co/marin-community/marin-8b-instruct), [OLMo 2](https://huggingface.co/allenai/OLMo-2-1124-13B-Instruct). The [Tülu SFT mixture](https://huggingface.co/datasets/allenai/tulu-3-sft-mixture) includes FLAN v2. FLAN's original recipe contains GSM8K training data and other training sources beyond mathematics. [FLAN configuration](https://github.com/google-research/FLAN/blob/main/flan/v2/task_configs.py).

BYOD uses one broad mixture across tasks, without separate training for each evaluation task. The specified mixture weights assign approximately 19% to explicit benchmark training sources. Most of this comes from MMLU and HellaSwag, with smaller contributions from ARC-Easy, GSM8K and MBPP. The rest comes from other instruction, mathematics and coding sources. Using training splits is different from training on held-out test examples. We explicitly check for and remove any prompts that are both in our training and test sets.

It should be noted that BYOD does add further fine-tuning on top of the already fine-tuned models. Our study thus measures the change from an instruction-tuned parent to a furhter fine-tuned diffusion model. It does not tell us how much of that change was caused by the diffusion objective alone. Our main focus remains to answer whether models from different families can be converted efficiently, and which capabilities they retain. We do not test whether diffusion performs better than additional AR fine-tuning with the same budget. A matched AR control would help separate these effects and remains useful future work.

### Internal evidence notes

The detailed [source checks, published-score table and provenance distinctions](post_training_evidence.md) support the condensed response. Before posting, substantiate the historical filtering and realized training exposure with D1/D2 below, and replace planned manuscript changes with completed edits. The visibility/scrutiny explanation is a possibility, not a measured claim that BYOD is more transparent than the entire field; Tülu itself is highly open. Likewise, upstream non-math sources do not establish specific membership in a retained Tülu subset or undisclosed checkpoint.

### Mixture arithmetic and historical-data verification

These percentages are calculated from Section 3.3's category and within-category weights, not measured row counts from a recovered training manifest.

| Source | Specified share of constructed mixture |
|---|---:|
| MMLU | 18% × 73% = 13.140% |
| HellaSwag | 18% × 25% = 4.500% |
| ARC-Easy | 18% × 2% = 0.360% |
| GSM8K | 18% × 5% = 0.900% |
| MBPP | 19% × 0.3% = 0.057% |
| **Explicit benchmark sources** | **18.957% ≈ 19%** |
| Other named sources | 81.043% |
| Tulu 3 (within other named sources) | 45% × 35% = 15.750% |
| OpenCoder (within other named sources) | 19% × 99.7% = 18.943% |

The evaluated checkpoints use prefixes of the shuffled dataset, so realized exposure percentages may differ from these mixture weights. Training-source weights also do not count any benchmark-derived examples nested inside other upstream mixtures.

Current `tools/byod_data/dataset_builder.py::format_tulu` excludes rows whose source label contains `math` or `code`. Thus, the full upstream Tulu card cannot establish that its listed math sources reached BYOD; nor does that filter prove all mathematical/coding content was removed. Determine the historical builder version and retained source counts before making a more specific overlap claim. See [verification notes](literature_notes.md#training-data-response-update-d1-and-tulu-3).

### Remaining work

- [ ] **D1 — Recover the actual conversion dataset revision, historical builder and retained source/split counts.** Check the nominal percentages above against the realized corpus and the 400k/800k training prefixes.
- [ ] **D2 — Audit evaluated IDs/content against that dataset**, including derived benchmarks, normalized exact matching, near-duplicate checks and their limits. Substantiate the safeguards already described in Section 3.3 rather than treating current code as proof of historical execution.
- [ ] **D3 — Implement the instruction-tuned-parent clarification and qualified gap wording:** describe post-conversion performance relative to each original Instruct checkpoint, not an isolated causal effect. Retain source documentation without assuming identical exposure.
- [ ] **D4 — Document a matched additional AR fine-tuning control as valuable future work and the unmatched additional exposure as a limitation.** The response does not promise a new control run or claim superiority over equal-budget AR adaptation. Neither prior instruction tuning nor upstream-source overlap removes this limitation.

## Shared response: sample size and uncertainty — R01/R02

Our central claim concerns conversion feasibility and cost, rather than statistically significant superiority over AR parents or LLaDA. Nevertheless, small benchmark subsets limit descriptive comparisons too. Explicit denominators, expanded coverage and paired uncertainty will make the reported gaps easier to interpret.

**Completed update, 16 November:** The expanded selection now contains **21,640 model–question outcomes** across ten configurations: 250 questions on each of eight tasks and all 164 HumanEval questions per model. This is a net increase of **10,570** selected outcomes over the recovered 11,070, excluding replacements and diagnostics. All models use the same questions. Uniform MATH scoring, a fresh BYOD-Gemma cohort and corrected Qwen AR additions are reflected in the adopted results; changes are not solely due to adding questions.

The revised manuscript now reports all final task scores, the equal-weight nine-task averages and nominal 95% bootstrap intervals in Table 3. Appendix D gives available/evaluated set sizes, full 95% Wilson intervals, the within-task bootstrap method and provenance notes. The main text, abstract and radar plots use the versioned [completed results source](paper/source_results/benchmark_results_20261116.json). See [reproducible macro intervals](analysis/manuscript_benchmark_intervals.md) and the populated [mNeh-W2 response](reviewer_responses.md#mneh-w2).

The principal paired comparisons are BYOD-Gemma minus LLaDA **+2.88 pp [0.74, 4.98]**, BYOD-Gemma minus Gemma AR **−10.30 pp [−12.33, −8.31]**, and Llama-50k minus Llama-25k **−0.14 pp [−1.81, 1.49]**. Intervals preserve question pairing within tasks, use 20,000 replicates, and are nominal/unadjusted. They describe item variation, not training-run or unseen-task uncertainty.

**Interpretation agreed with the author:** these intervals are not adjusted for comparing five BYOD configurations or selecting Gemma as the strongest conversion. We make no superiority claim. Gemma 2 9B is larger than LLaDA 8B and has a different training history; this is evidence that LoRA conversion is a viable low-cost route, not a controlled test against full fine-tuning.

The ten-paper audit below concerns specified comparisons, not a field-wide prevalence estimate: CIs were not identified alongside those results, while denominators are often absent beside scores and sometimes reported elsewhere. HumanEval has 164 items and **sanitized** MBPP has 257; full MBPP's 500-item split is different.

<details>
<summary>Historical planning calculations and interim results — superseded by the completed update above</summary>


### Precision calculation

A conservative 95% planning approximation is `n = ceil(z² × .25 / e²)`, with `z=1.959964` and desired half-width `e` as a proportion. Report Wilson endpoints from integer successes/denominators, not Wald intervals or rounded table entries.

| Desired 95% margin | Approximate independent examples needed |
|---|---:|
| ±1 percentage point | 9,604 |
| ±2 percentage points | 2,401 |
| ±3 percentage points | 1,068 |
| ±4 percentage points | 601 |

At n=125 the worst-case Wilson half-width is **±8.63 pp**; at the selected n=250 it is **±6.15 pp** (n=500 would give ±4.37 pp). At 80% observed accuracy, n=500 gives about **76.27–83.27%**, still wider than ±2 pp. Boundary accuracies can yield narrower intervals, but these cannot be promised beforehand. Individual accuracy precision is different from precision of a paired difference or macro mean.

### Coverage under the requested cap

For each benchmark, all model configurations are evaluated on the same fixed question subset, so comparisons use matched examples.

Proposed counts use the current evaluator and [dataset-card sources](sampling_plan.md#target-under-the-requested-cap). Original run variants still need verification.

| Task | Evaluation split | Available evaluation items | Stage-1 total unique items | Extra if first 125 reusable | Worst-case Wilson half-width |
|---|---|---:|---:|---:|---:|
| [ARC-Challenge](https://huggingface.co/datasets/allenai/ai2_arc) | test | 1,172 | 250 | 125 | ±6.15 pp |
| [GPQA-Main](https://huggingface.co/datasets/Idavidrein/gpqa/blob/main/README.md) | gpqa_main / train (evaluation) | 448 | 250 | 125 | ±6.15 pp |
| [GSM8K](https://huggingface.co/datasets/openai/gsm8k) | main / test | 1,319 | 250 | 125 | ±6.15 pp |
| [HellaSwag](https://huggingface.co/datasets/Rowan/hellaswag) | validation | 10,042 | 250 | 125 | ±6.15 pp |
| [HumanEval](https://huggingface.co/datasets/openai/openai_humaneval) | test | 164 | 164, full | 39 | ±7.56 pp |
| [MATH-500](https://huggingface.co/datasets/HuggingFaceH4/MATH-500) | test | 500 | 250 | 125 | ±6.15 pp |
| [MBPP sanitized](https://huggingface.co/datasets/google-research-datasets/mbpp/raw/main/README.md) | sanitized / test | 257 | 250 | 125 | ±6.15 pp |
| [MMLU](https://huggingface.co/datasets/cais/mmlu) | all / test | 14,042 | 250 | 125 | ±6.15 pp |
| [MMLU-Pro](https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro) | test | 12,032 | 250 | 125 | ±6.15 pp |
| **Total/model** | Mixed tasks | — | **2,164** | **1,039** | Not a pooled single-task interval |

Sanitized MBPP has 257 test items, versus 500 for full MBPP; current code selects sanitized. Verify the historical variant and do not mix them. GPQA-Main has 448 items; Diamond is not the paper's task. [MBPP card](https://huggingface.co/datasets/google-research-datasets/mbpp/raw/main/README.md), [GPQA card](https://huggingface.co/datasets/Idavidrein/gpqa/blob/main/README.md). HellaSwag uses its labeled validation set because public test labels are withheld. GPQA-Main’s released split is named `train`; it is used here for evaluation and must remain excluded from conversion training. “Available evaluation items” counts the selected split, not all rows across training/validation/test; original-run counts still need verification.

All ten evaluated model/checkpoint columns would mean **21,640 total model–item evaluations / 10,390 additional**, conditional on reusing the original 125/task. Stage 1 covers all ten configurations where budget permits. Stage 2 gives remaining compute to Gemma, its AR parent and LLaDA; increasing that trio from stage 1 to a 375-item cap would add **2,646 model–question evaluations**. That second target is conditional on pilot cost and remaining funds. These are counts, not GPU-time estimates. Measure seconds/item per model/task; changed protocols and provenance failures may require rerunning old items too.

A full small benchmark removes item-subsampling error for that fixed set under a fixed deterministic protocol, not uncertainty about future task instances. The [full plan](sampling_plan.md#finite-benchmark-versus-broader-task-population) separately calculates finite-benchmark precision targets. Do not use those to imply population ±1–2 pp accuracy precision.

### Breadth of the evaluation and compute allocation

**Draft response:** The initial sample allocation enabled a common-harness evaluation spanning ten model/checkpoint configurations and nine tasks, including converted models and unchanged parents across four families. Several DLM studies likewise evaluate multiple checkpoints and baselines; our distinction is the breadth of the shared conversion recipe and paired parent comparisons. We therefore present this as context for the computational trade-off, while accepting the request to improve sample coverage and uncertainty reporting.

The [source-backed comparison](model_breadth.md) counts nine main-table configurations for LAD, six explicitly common-protocol Base/Instruct checkpoints for LLaDA, four explicitly common-protocol Base checkpoints for Dream (with four further Instruct entries), nine configurations for DiffuLLaMA, and ten author-evaluated configurations for DiffuCoder. Counts are scoped to the inspected main comparisons; imported reference scores and different task/sample scales prevent a direct ranking of GPU effort.

**Internal conclusion:** substantial cross-family coverage, comparable to other broad studies, rather than an exceptional total model count. Do not say “full benchmarks” when only task coverage is complete. Nominal 10 × 9 × 125 = 11,250 evaluations requires denominator verification before being used as an audited total.

### Reporting conventions and our response

**Draft context paragraph:** Prominent DLM papers commonly present their principal comparisons as point estimates without accompanying confidence intervals, and per-task evaluation denominators are often not printed alongside those scores. Our ten-paper check below documents this reporting pattern while distinguishing counts disclosed elsewhere. Established benchmark sizes can also limit precision for small per-task differences, even when every available example is evaluated. These observations motivate clearer uncertainty reporting; they do not establish that every small benchmark is inadequate or that another paper's actual sample count is impossible to recover.

**Draft action paragraph:** We appreciate the reviewers' request and will expand the evaluation from 125 to **250 total unique examples per task where available**, retaining the original 125 under the same verified protocol and adding 125 disjoint examples. HumanEval will use all 164 items; sanitized MBPP will use 250 of its 257 items. If budget remains, we will add further matched examples for BYOD-Gemma, Gemma AR and LLaDA. We will report actual sample counts, 95% Wilson intervals for individual accuracies, and paired intervals for model differences and the equal-weight nine-task average. Our aim remains to demonstrate feasible, efficient conversion, and we will qualify comparisons that remain statistically unresolved.

[Planned work, not completed results. Where sample provenance or protocols differ, re-evaluate affected original items before combining them. Use “have expanded” only after the runs finish.]

#### Ten-paper context table

| Paper / primary source | Inspected result | Benchmark CIs in that result | Evaluation-count disclosure |
|---|---|---|---|
| [LLaDA](https://arxiv.org/html/2502.09992) | Tables 1–2 | Not identified | Not shown beside benchmark entries; Appendix B.6 supplies protocols. Other experiments explicitly specify 100 questions per difficulty setting and 496 poem pairs. |
| [Dream 7B](https://arxiv.org/html/2508.15487) | Tables 1–2 | Not identified | No per-task denominators adjacent to main scores; benchmark/protocol descriptions given. Few-shot counts are not test counts. |
| [DiffuLLaMA](https://arxiv.org/html/2410.17891) | Tables 1–2 | Not identified | Main-score denominators not adjacent; Appendix B.3 explicitly specifies 1,000 ROCStories and 1,033 code-infilling cases. |
| [Scaling up Masked Diffusion Models](https://arxiv.org/html/2410.18514) | Table 2 | Not identified | No denominators beside task scores; Section 7.2 separately specifies 0.5B evaluation tokens per time period. |
| [MDLM](https://arxiv.org/html/2406.07524) | Tables 1–3 | Not identified | Section 5.1 / Appendix D.4 explicitly reserve 100,000 OWT validation documents. Not an omission of all evaluation sizes. |
| [SEDD](https://arxiv.org/pdf/2310.16834) | Table 1 | Not identified | Names likelihood datasets, with no document/token denominators alongside table entries. Not a binary-accuracy sample count. |
| [Time-Agnostic Masked Models](https://arxiv.org/html/2409.02908) | Table 2 and Figure 7 | Not identified | Explicit counts: 8 samples in the Table 2 ablation; 64 for sampling comparisons; 100,000 OWT validation documents in Appendix H.2. |
| [DiffuCoder](https://arxiv.org/html/2506.20639) | Table 1 | Not identified | No per-task question counts beside entries; Appendix B.2 links evaluation toolkits. The ± notation describes score changes, not CIs. |
| [LLaDA2.0](https://arxiv.org/pdf/2512.15745) | Tables 1–2 | Not identified | No per-task denominators beside scores; Section 6.1 names benchmarks/settings. 47 benchmarks is not a question count. |
| [Mercury](https://arxiv.org/html/2506.17298) | Table 1 coding comparison | Not identified | No per-task counts beside coding scores; Section 3.2.1 names benchmarks. Other experiments, including human evaluation, are outside this row’s scope. |

This is a representative check, not a bibliometric “top ten” or proof that all ten omit all sample counts. In particular, MDLM and the time-agnostic paper explicitly report their OWT split sizes, and DiffuLLaMA reports infilling counts. Missing table denominators can sometimes be recovered from benchmark definitions or code. See [audit scope and evidence](reporting_audit.md). We should not write “almost always omitted” as a field-wide frequency estimate or “cannot be verified” solely because a table lacks n.

### Current nine-task averages: provisional 95% confidence intervals

**Internal scoring update, 15 November:** the numeric-escape, scalar-final-prose and percentage-unit follow-up is completed under MATH scorer v3. Four final MATH flags were restored uniformly (Gemma AR +1, BYOD-Ministral +2, Ministral AR +1); Gemma and LLaDA diffusion final scores are unchanged. Use the regenerated [final comparison](evaluation/FINAL_EVALUATION_STATUS.md) and [correction record](evaluation/MATH_PRESENTATION_CORRECTION.md) when updating the manuscript, rather than older intermediate numbers below.

**Updated from recovered per-question outputs; no new model evaluations were run.** These are approximate, unadjusted normal intervals for each equal-weight nine-task average, using the actual denominators below. Scoring verification remains pending.

The recovered per-question outputs now establish the historical denominators. We prioritize the latest compatible prediction per model/task/question, including corrected reruns, and fill partial reruns only with compatible earlier predictions for unchanged prompts and targets. No selection uses accuracy. These remain the **recorded historical scores**, pending rescoring under one frozen harness and a pilot replay check.

| Model/checkpoint | Historical nine-task mean | Approximate 95% CI |
|---|---:|---:|
| BYOD-Gemma | 50.58% | 47.93–53.22% |
| Gemma AR | 65.69% | 62.71–68.66% |
| BYOD-Qwen | 48.98% | 46.28–51.68% |
| Qwen AR | 71.40% | 68.97–73.82% |
| BYOD-Ministral | 49.87% | 47.20–52.53% |
| Ministral AR | 63.47% | 60.86–66.07% |
| BYOD-Llama-25k | 48.71% | 46.03–51.40% |
| BYOD-Llama-50k | 49.24% | 46.57–51.92% |
| Llama AR | 58.76% | 56.04–61.47% |
| LLaDA (own evaluation) | 51.91% | 49.16–54.66% |

Method: `mean = Σp_t/9`; `SE² = Σ[p_t(1−p_t)/(n_t−1)]/81`; interval `mean ± 1.959964×SE`, using actual n per task. Gemma AR has 50 HumanEval and 50 MBPP items; Qwen AR has 95 HumanEval items. Other historical task cells have 125 items after compatible partial reruns are reconciled. These conditional, unadjusted intervals assume independent items/tasks and concern nine fixed benchmarks.

**Confirmed corrections:** the latest recovered Ministral AR HumanEval is 107/125 (85.6%), superseding 47/50 (94%). Qwen AR HumanEval is 83/95 (87.37%) in its latest partial run, which does not verify the manuscript's 89%. Their historical means above reflect those recovered outcomes. Gemma AR's two 74% code scores are each 37/50. The initial GPQA count discrepancy was a Unicode JSONL parsing error in our audit; the corrected reader confirms 125 records. Original outputs remain unchanged.

The historical AR controls used 1,024 output tokens (2,048 on MMLU-Pro), while diffusion used the shorter task-specific limits. Diffusion MMLU-Pro was 64 tokens, rather than the manuscript's stated 128. The longer AR limits were intentional, as confirmed by the author. The expansion preserves the original method-specific limits and reuses compatible AR generations; differing token limits alone are not a reason to invalidate them. We will correct the documented settings and distinguish the comparison from equal-output or equal-compute evaluation. A matched-output sensitivity experiment is optional and is not included in the current budget.

Gemma-minus-LLaDA remains −1.33 percentage points as a historical point difference. Paired outputs have now been located; the worker will rescore retained predictions consistently and calculate paired intervals from matching question fingerprints. See [actual counts and historical intervals](current_macro_intervals.md), [run-selection audit](evaluation/audit_summary.md), and [evaluation setup](evaluation/README.md). Final rebuttal claims must use the completed, consistently rescored comparison with the retained method-specific limits.

### Credit-limited pilot: interim results (not final rebuttal evidence)

The completed pilot saved 728 additional Gemma AR questions and stopped cleanly at its time limit. Gemma AR now has 206 questions on each of seven non-code tasks, 131 HumanEval questions and 130 MBPP questions. BYOD-Gemma remains at 125 questions per task. No new diffusion/LLaDA generations were reached.

| Model | Historical nine-task mean | Rescored original questions | Rescored with additional questions |
|---|---:|---:|---:|
| BYOD-Gemma | 50.58% | 49.78% | 49.78% (no new questions) |
| Gemma AR | 65.69% | 65.33% | 62.25% |

Approximate current 95% macro intervals are 47.16–52.40% for BYOD-Gemma and 60.05–64.46% for expanded Gemma AR, under independent-item/task assumptions. The scorer changes nine historical BYOD-Gemma MATH answers and four AR MATH answers from true to false. These are scorer disagreements, not adjudicated ground truth; inspect those cases before adopting new scores as definitive. Retained code answers have unchanged labels, while the expanded AR code scores are lower on the larger subsets. Different subset coverage and unverified checkpoint replay prevent treating this table as a completed paired conversion-gap analysis.

See [per-task before/after results, exact counts and methods](evaluation/results_comparison.md). Keep the manuscript’s fully historical table separate until scorer disagreements and expanded evaluation are resolved. Next compute should measure diffusion throughput before committing to the full expansion.

The author has now authorized the [resumable expansion campaign](evaluation/CAMPAIGN.md) after adding credits. It carries forward the 728 new answers, uses verified original adapters, rotates model batches and checkpoints progress. This is ongoing work, not completed rebuttal evidence. Actual final sample counts and paired intervals remain pending.

**9 November interim update:** the campaign has saved 6,524 new generations and 17,594 total scored outcomes. Gemma AR has reached the planned 250-per-task / 164-HumanEval target. Other expanded scores remain interim. See [old, rescored-old and expanded scores with actual counts](evaluation/campaign_score_check.md). Qwen AR’s expanded mean is 60.97%, versus 70.42% on rescored original items; this large discrepancy requires protocol/reproducibility review before interpreting the conversion gap. Gemma diffusion remains deferred; the literature/rebuttal edits have not changed the running campaign.

**HumanEval diagnostic (internal; not yet a reviewer-facing claim):** all active models now have 164 saved HumanEval outcomes; Gemma diffusion remains deferred at 125. A CPU audit re-executed all 1,601 saved predictions with zero scoring disagreements, and all 164 canonical solutions pass the frozen harness. The original HumanEval subset was a fixed prefix, and several models already declined on later questions within their historical runs. Some diffusion failures also exhaust the 256-token canvas while copying docstrings; others are complete but incorrect implementations. No shared scoring fix was identified. Keep the completed full-set results, avoid additional HumanEval generation for now, and leave Qwen AR provisional pending matched GPU replay. See [diagnostic evidence and limitations](evaluation/humaneval_investigation.md). Do not interpret old-prefix versus added-tail differences as a causal runtime comparison.

**Verified runtime correction:** a matched A100 probe reproduced four saved Qwen AR errors exactly with eager attention and corrected all four by changing only the backend to SDPA. Qwen's new eager-cohort results must remain provisional and be replaced consistently, including its correct answers; they cannot support a conversion-gap claim. The [separate correction run](evaluation/CORRECTIONS.md) retains candidate historical Qwen outputs behind an AR replay gate and restarts Gemma on a fresh cohort, because its three historical replay disagreements are stable in the current environment and persist with both tested backends. HumanEval reruns remain deferred; corrected full-suite macro scores are therefore still pending. The prior CPU scoring audit remains valid but did not establish GPU generation correctness.

**15 November scoring/cohort correction (internal):** the GPU requirements omitted the symbolic MATH verifier. Pinned it and fixed final-answer-only symbolic comparison, then rescored every model and historical baseline consistently; old frozen MATH flags are superseded in derived reports. Gemma AR MATH changes from 71/125 → 120/250 under exact-only scoring to **74/125 (59.2%) → 129/250 (51.6%)**. A matched ten-question A100 probe gives identical correctness outcomes under eager and SDPA (5/10 each), so no Gemma backend change is supported; the remaining drop is retained. The added MATH questions contain more level-4/5 problems, and inspected failures include actual algebra errors.

**Latest Gemma cohort decision:** after reviewing both options, the author chose the fresh initial answers consistently across all eight rerun tasks, including both gains and losses. Adopted BYOD-Gemma MBPP is **74/156 (47.4%)**, comprising **61/125 (48.8%)** on the fresh initial subset and **13/31 (41.9%)** on added questions. The historical initial subset is 46/125 (36.8%); do not attribute the historical-to-fresh improvement solely to sample expansion. The intermediate original-retention assembly (59/156, 37.8%) is archived and superseded. A CPU audit reproduces all 281 old/fresh MBPP flags and all 250 reference solutions pass. [Discrepancy register](evaluation/DISCREPANCY_LOG.md) and [full investigation](evaluation/gemma_math_mbpp_investigation.md). Raw answers remain unchanged, historical generation drift is not fully explained, HumanEval correction remains deferred, and incomplete benchmark targets remain incomplete.

**Latest priority — HumanEval:** the author requests resolving the omitted task before continuing other expansion. Submitted a separate HumanEval-only plan replacing Qwen's 69 eager-generated additions with SDPA outputs and generating a fresh 164-question Gemma cohort; Qwen's historical 95 are retained subject to replay checks. Other models already have 164 saved outcomes. The previous harness audit found no shared scoring defect; actual code errors and short diffusion outputs are retained rather than repaired post hoc. The assembler adopts complete validated task cohorts and emits nine-task summaries only once all selected HumanEval cells reach 164. Current eight-task averages must not be presented as full-suite gains. [Execution, budgets and status](evaluation/HUMANEVAL_CORRECTION.md). Remaining non-HumanEval expansion is stopped.

**Latest execution update:** the author subsequently authorized the remaining non-HumanEval samples in parallel with the active HumanEval correction. Two disjoint queues import the 14,342 adopted outcomes for their eight incomplete models and generate only the remaining 1,658; completed Gemma AR/Qwen AR non-HumanEval tasks are excluded. Three GPUs are active in total while HumanEval runs. Expected remaining wall time is approximately 2.5–3 hours, with a combined $25.50 / ten GPU-hour cap for the two new queues. HumanEval's snapshot has Qwen 164/164 and Gemma 47/164; no new nine-task conclusion is asserted before completion. [Run ledger and assembly instructions](evaluation/PARALLEL_COMPLETION.md).

**HumanEval completed — latest checkpoint:** corrected Qwen AR scores **133/164 (81.1%)**, replacing the faulty eager full-set 110/164 (67.1%). Fresh BYOD-Gemma scores **49/164 (29.9%)**, comprising 47/125 initial and 2/39 added; historical Gemma was 32/125 (25.6%). All selected HumanEval model cells now have 164 outcomes and the complete cohorts are adopted. Current nine-task descriptive means are available but remain interim while other benchmarks finish (BYOD-Gemma 52.20%, LLaDA 50.05% on unequal coverage; not a paired superiority claim). The remaining queues had generated 325/739 and 440/919 new outcomes at this checkpoint, leaving 893. Do not interpret a switch from eight-task to nine-task means as an accuracy change.

### Primary comparison: the task average

Use the **paired difference in the equal-weight nine-task average** as the principal descriptive model comparison, with per-task intervals for context. Resample matching model outcomes together within each task. Preserve task weights rather than pooling all questions; related/overlapping tasks may require additional dependence handling. Under independent-item/task assumptions, the current sample allocation gives a conservative normal-approximation half-width of roughly ±2.13 pp for one model's macro average, versus ±2.92 pp at 125/task. This is not the interval for the paired difference, which depends on actual disagreements.

The 9,604 figure is the unadjusted sample-size approximation for ±1 pp precision of one accuracy estimate at p=.5; **no multiple-testing correction was used**. Averaging nine tasks does not create nine separate tests for one prespecified aggregate contrast. Multiple additional confirmatory contrasts require an explicit testing plan. Do not interpret a difference interval spanning zero as equivalence.

GPU execution will use an unattended rented server or batch job, not Colab. See [GPU options and budget scenarios](gpu_options.md); no resource has been provisioned.

### Remaining work

- [ ] **E1 — Propagate audited AR corrections:** exact runs, checkpoints, integer successes/denominators, IDs and scoring; correct dependent averages/figures/text if needed.
- [ ] **E2 — Freeze revisions, variants and common sample IDs:** all items for smaller tasks; append disjoint sampled items only if the original subset/protocol is reusable. No outcome-based selection.
- [ ] **E3 — Document intentional method-specific output budgets:** retain AR 2,048 vs diffusion 64 for MMLU-Pro, correct the manuscript settings, and avoid implying equal output/compute. A matched-output sensitivity analysis is optional, outside the present run plan.
- [ ] **E4 — Measure pilot cost and schedule expanded evaluation:** stage 1 targets 250 total unique questions/task across all ten columns, followed by budget-contingent additional questions for Gemma/Gemma AR/LLaDA. No expanded evaluation has run yet.
- [ ] **E5 — Finalize task and macro intervals from verified counts:** historical macro intervals above now use verified denominators; final estimates await consistent rescoring and completion of the expansion. Do not treat repeated generations as independent questions.
- [ ] **E6 — Calculate paired difference intervals:** match IDs/protocol, bootstrap paired outcomes, and preserve equal task weights by resampling within tasks for the macro mean. Pairing precision depends on disagreement; no ±1–2 pp guarantee at n=250.
- [ ] **E7 — Update all comparisons and plots:** include Gemma–LLaDA and 25k→50k claims. An interval crossing zero is not equivalence evidence. Item sampling intervals do not measure training-seed variation or give simultaneous coverage for every comparison.

</details>

## Individual reviewer responses

Write the point-by-point replies in [reviewer_responses.md](reviewer_responses.md). Each reviewer’s original weaknesses, questions and presentation comment has a separate blank response field; overlapping points are kept separate. Shared arguments and evidence remain in this document. The previous reviewer-specific scaffolding is preserved in the new document’s collapsed [internal appendix](reviewer_responses.md#previous-reviewer-specific-drafting-notes). Answers will be populated in a later step.

## Final-response completion gate

All task IDs remain open. Add evidence paths, results, manuscript locations and response text to [changes.md](changes.md) as work completes. Only then change planned prose to past tense. Remove internal notes/checklists from final OpenReview comments, keeping unresolved limitations explicit. No substantive paper edits have been implemented in this turn.
