# Results and provenance notes

This file records the assumptions used for the first manuscript pass. It is not intended for submission.

## Selected runs

| Paper label | Saved run | Updates | Training examples in stage | Parent |
|---|---|---:|---:|---|
| Gemma-25k | `gemma-2-9b-mask` | 25,000 | 400,000 | `google/gemma-2-9b-it` |
| Llama-25k | `llama-3.1-8b-mask` | 25,000 | 400,000 | `meta-llama/Llama-3.1-8B-Instruct` |
| Llama-50k | `llama-3.1-8b-mask-continued` | 25,000 additional | next 400,000 | Llama-25k final adapter |
| Qwen-25k | `qwen-2.5-7b-mask` | 25,000 | 400,000 | `Qwen/Qwen2.5-7B-Instruct` |
| Ministral-25k | `ministral-8b-mask` | 25,000 | 400,000 | `mistralai/Ministral-8B-Instruct-2410` |

The user's shorthand `ministral-mask` maps to the saved folder `ministral-8b-mask`.

## Workbook interpretation

- Original source: `source_results/Results.xlsx`, copied from `results/Results.xlsx` on 2026-09-18.
- Latest open-ended snapshot: `source_results/Results_open-ended-128t-32i-merged_20260918.xlsx`, copied from `results/Results_open-ended-128t-32i_20260918.xlsx` after importing the merge benchmark.
- The workbook legend says red text is measured over 250 samples and black text over 50 samples.
- Most diffusion values are present, but many autoregressive cells are unfinished.
- The Ministral workbook average formula omits GPQA and three unfinished tasks; the paper therefore does not report a Ministral macro average.
- The workbook row named `1-gram repetition` predates the final sliding model-token Distinct-n implementation. Those numbers are intentionally not presented as Distinct-1.
- The manuscript treats published LLaDA results as protocol-separated context, not as directly matched measurements.

## Earlier-draft statements corrected

- Four parent families are now included, not three: Gemma, Llama, Qwen, and Ministral.
- The selected runs use a 256-token maximum sequence length, not 1,024.
- LoRA targets only `q_proj` and `v_proj`, not query/value/output projections.
- Normalization layers are frozen (`train_normalization_layers: false`).
- The selected runs use IID answer/EOS-padding masking; frontier masking belongs to later ablations that are not part of the final model set.
- Preliminary frontier ablations lowered external Phi-4 generative perplexity but also substantially lowered sliding model-token Distinct-1/2/3 and visibly increased repetition. Preserve the matched run/checkpoint/NFE values and representative samples before replacing the manuscript placeholder.
- Repeated EOS batch padding is visible to bidirectional attention, can be masked, and participates in the loss because `eos_padding_loss: true`.
- Each first-stage run uses 400,000 examples over 25,000 batch-16 updates. The continued Llama run skips the consumed 400,000-example prefix and uses the next 400,000 examples.
- The continued run restores the adapter but not optimizer state; AdamW and the cosine schedule restart.

## Llama merge ablation

- Unmerged adapter run: `20260918T112818.173051Z--colab-validation`, model `llama-3.1-8b-mask/best`.
- Merged run: `20260918T123901.774999Z--colab-validation`, model `merged:/content/drive/MyDrive/lad-generic-results/merged/llama-3.1-8b-mask`.
- Both use 30 prompts, 128 generated tokens, 32 denoising steps, seed 1234, temperature 0.7, the LLaDA-style sampler, and Phi-4 scoring.
- Adapter-loaded: token-weighted PPL 19.381430; mean sliding model-token Distinct-1/2/3 = 0.495153/0.788446/0.898893.
- Merged: token-weighted PPL 19.282753; mean sliding model-token Distinct-1/2/3 = 0.497539/0.806884/0.917994.
- The merged safetensors index records 8,030,261,248 parameters and 16,060,522,496 bytes of BF16 weights. The adapter-loaded parameter audit records 8.466B total parameters, including 436.2M LoRA parameters. Phrase the conclusion as restoration of the base architecture's parameter count; on-disk size can vary with dtype, quantization, and serialization.

## Must resolve before submission

1. Finish all paired autoregressive benchmark evaluations.
2. Save the exact benchmark run directory/manifests behind every workbook column.
3. Use one declared benchmark sample size (preferably full sets) and add uncertainty intervals.
4. Archive the exact Hugging Face dataset commit used during training. The live dataset page may have changed since the runs.
5. Recover or regenerate the dataset manifest with category/source counts and filtering policy.
6. Record wall-clock time, GPU-hours, peak memory, and inference latency/throughput.
7. Recompute Distinct-1/2/3 with the final sliding model-token implementation.
8. Verify every external bibliographic entry and add model/dataset technical-report citations.
9. Complete the checkpoint-by-NFE sweep needed to test whether continued training preferentially improves the parallel decoding regime ($\mathrm{NFE}<L$).
10. Consolidate the frontier-versus-IID ablation metrics and blinded qualitative samples.
