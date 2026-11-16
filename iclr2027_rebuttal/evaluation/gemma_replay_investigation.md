# Gemma diffusion replay investigation

**Latest 15 November decision:** after considering both cohorts, the user explicitly chose the fresh results, including the fresh initial 125, consistently across the eight rerun tasks and regardless of correctness. MBPP is **74/156 (47.4%)**, combining 61/125 initial fresh and 13/31 added. The old-retention alternative is archived and no longer selected. A CPU audit reproduced all 281 old/fresh MBPP score flags. Historical environment drift remains unexplained; adopting the fresh cohort controls reporting consistency without claiming to establish its cause. HumanEval correction remains deferred. See [the detailed investigation](gemma_math_mbpp_investigation.md).

## 9 November focused probe and implemented resolution

The user subsequently authorized further diagnosis and fixes, superseding the earlier deferral below. In A100 probe [6af15e38e6320c66fad7e2b4](https://huggingface.co/jobs/Ruurd/6af15e38e6320c66fad7e2b4), all three disputed inputs produced **byte-identical text on two consecutive runs**. Switching from SDPA to eager also produced identical text for these three inputs. This confirms reproducibility for the tested current environment and rules out an eager/SDPA remedy on these cases. It does not identify the exact historical environment difference or prove stability for every input.

There is no evidence here that Gemma fails to load or generate. The blocking condition is the historical replay-equality gate. Instead of deleting disagreement records or accepting incompatible historical answers, the corrected execution uses **a fresh Gemma cohort with no historical outcomes reused**, pinned to the tested SDPA environment and verified original weights. It reruns all 250 questions on each of eight non-HumanEval tasks. Historical outputs and all replay disagreements remain separately available. HumanEval remains deferred as requested.

This fixes the evaluation blockage by separating cohorts; it does not claim to repair an identified model defect or recreate the old Colab environment. See [correction execution and restart instructions](CORRECTIONS.md).

Gemma loads and generates answers. It is deferred by our conservative replay gate, which rejects a model if even one of 18 replayed correctness flags differs from the corresponding historical prediction. The check does not establish that the model is broken or that newer predictions are worse.

## What the three disagreements mean

| Task | Historical correctness under the current scorer | Current replay correctness | Sample index |
|---|---|---|---:|
| GPQA | Incorrect | Correct | 0 |
| MMLU-Pro | Correct | Incorrect | 0 |
| HumanEval | Incorrect | Correct | 0 |

Replay files store `score_matches`, not the actual replayed text. The current labels above follow from binary disagreement with the historical, consistently rescored outcome. They are not human adjudications. These three cases are distinct from the thirteen historical MATH scorer disagreements.

## Checks completed without additional GPU jobs

- Original and published Gemma adapter tensors and normalization-state files have matching SHA-256 hashes. Adapter weight SHA-256: `cf4eafa39c596b237e183f56800a230a8991c50d635d2e21291b90a3b529bfee`.
- Original saved tokenizer and the current pinned base tokenizer have identical vocabularies, chat templates and special-token IDs. All three failing prompts produce identical token-ID sequences (214 GPQA tokens; 449 MMLU-Pro; 218 HumanEval).
- Decoding settings match the selected historical runs. HumanEval's historical seed is 5678 versus current 1234; both use temperature zero and low-confidence transfer. The sampler's zero-temperature noise function returns the logits without drawing random noise, so this seed difference does not by itself explain the discrepancy.
- Comparing the current repository to September commit `5f11acb` gives identical function ASTs for `llada_generate`, `_llada_gumbel_noise`, `_prompt_ids`, `forward_denoising`, `bidirectional_attention_mask` and `forward_bidirectional`. This is evidence about an archived repository revision, not proof of the exact Colab checkout used for every historical run. The newer optional trainable-base-state loader has no effect for this LoRA checkpoint, which has no trainable-base-state file.
- The historical run manifests do not record package versions, GPU execution backend or the exact base-model commit. They cannot completely reconstruct the old execution environment.

## Interpretation and remaining diagnostic

A cross-environment numerical difference is plausible, not confirmed. BF16 logits/confidences and the iterative low-confidence transfer decisions can amplify small differences in attention or matrix multiplication. The old Colab setup and current A100 container are different environments. [PyTorch 2.8's reproducibility documentation](https://docs.pytorch.org/docs/2.8/notes/randomness.html) explicitly does not guarantee exact reproduction across releases or platforms, even with matching seeds. This general warning is not proof of the cause in these three cases.

The replay gate is a precaution for safe historical reuse; zero cross-environment score disagreements is stricter than the model's intended scientific claim. Do not relabel these cases as a model failure, silently erase the disagreement records or unblock by inventing matching results.

The focused GPU diagnostic is to replay these three inputs twice in the same A100 environment, save the full output texts and exact package/GPU/attention/dtype metadata, and compare those with the historical strings. Testing the original seed on HumanEval and an explicit attention backend can then distinguish repeatability from backend sensitivity. This small diagnostic does not need the rest of the benchmark suite to finish. No extra GPU Job was launched during the checks above, and the ongoing campaign was not interrupted or modified.


## User-directed deferral

The user requested a quick fix only if well supported, otherwise to defer further Gemma work and continue the existing run. No verified small fix has been established. Controlled replays and environment comparisons are therefore deferred; the active campaign is left running without changes to its replay gate, historical outcomes, frozen code or settings. Other eligible models continue, and Gemma remains a distinct pending task.
