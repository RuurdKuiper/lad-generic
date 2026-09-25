# Results and provenance notes

This file records the assumptions used for the first manuscript pass. It is not intended for submission.

## Selected runs

| Paper label | Saved run | Updates | Training examples in stage | Parent |
|---|---|---:|---:|---|
| Gemma-25k | `gemma-2-9b-mask` | 25,000 | 400,000 | `google/gemma-2-9b-it` |
| Llama-25k | `llama-3.1-8b-mask` | 25,000 | 400,000 | `meta-llama/Llama-3.1-8B-Instruct` |
| Llama-50k | `llama-3.1-8b-mask-long` | 50,000 | 800,000 | `meta-llama/Llama-3.1-8B-Instruct` |
| Qwen-25k | `qwen-2.5-7b-mask` | 25,000 | 400,000 | `Qwen/Qwen2.5-7B-Instruct` |
| Ministral-25k | `ministral-8b-mask` | 25,000 | 400,000 | `mistralai/Ministral-8B-Instruct-2410` |

The user's shorthand `ministral-mask` maps to the saved folder `ministral-8b-mask`.

## Workbook interpretation

- Original source: `source_results/Results.xlsx`, copied from `results/Results.xlsx` on 2026-09-18.
- Latest open-ended snapshot: `source_results/Results_open-ended-128t-32i-merged_20260918.xlsx`, copied from `results/Results_open-ended-128t-32i_20260918.xlsx` after importing the merge benchmark.
- Current paper workbook: `source_results/Results_training-20260924.xlsx`, copied from `results/Results_training-20260924.xlsx`. It contains the corrected 32/64/128-NFE long-run progression, completed validation loss, and the latest task-benchmark values.
- Table 3 uses the populated task cells directly and computes an unweighted nine-task macro average. The current matched-harness DLM averages are Gemma 50.6%, Qwen 49.0%, Ministral 49.9%, Llama-25k 48.7%, Llama-50k 49.2%, and LLaDA 51.9%. The average is recomputed from all nine tasks rather than trusting cached spreadsheet formulas.
- The workbook row named `1-gram repetition` predates the final sliding model-token Distinct-n implementation. Those numbers are intentionally not presented as Distinct-1.
- The manuscript treats published LLaDA results as protocol-separated context, not as directly matched measurements.

## Automatically generated figures

- Run `python scripts/generate_paper_figures.py` from the repository root to regenerate the paper figures from `results/Results_training-20260924.xlsx`.
- Install the spreadsheet dependency with `pip install -e '.[paper]'` if `openpyxl` is unavailable.
- PDF and 300-DPI PNG outputs are written to `iclr2027_submission/figures/`; `figure_data.json` records the exact extracted values and source workbook.
- `benchmark_radar_panels` contains the matched LLaDA/BYOD-Llama/Llama-AR comparison and the four-family BYOD comparison, both using 125 examples per task.
- `llama_training_diagnostics` reads the corrected 32/64/128-NFE progression directly from the current workbook. Solid marked lines are BYOD-Llama checkpoints; matching dashed horizontal lines are LLaDA references. The dotted gray line is the unchanged Llama AR parent.
- `scripts/calculate_open_ended_uncertainty.py` reconstructs prompt token counts with the Phi-4 tokenizer and archives 20,000-resample percentile-bootstrap 95% CIs in `source_results/open_ended_uncertainty.json`. These intervals are retained for analysis but are not displayed in the paper figures or table.
- Table 4 uses 30 prompts for most rows. The uninterrupted Llama-50k row uses 100 prompts from `20260923T190517.263478Z--colab-validation`; the other main rows come from `20260918T135058.643507Z--colab-validation`, with the corrected Ministral row from `20260921T131916.314780Z--colab-validation`.
- Bidirectional-attention results come from `20260924T085113.502527Z--colab-validation` and are archived in `source_results/right_context_copy_results.json`. With-clue exact match for Gemma, Llama-25k, Llama-long-best, Qwen, Ministral, and LLaDA is 100/90/70/20/100/100%; all score 0% without the clue. The clue changes every model's greedy prediction in 100% of examples. This run uses the clarified `COPY:` prompt, a training-matched system message, and single-forward argmax decoding.
- The code-error appendix compares BYOD-Llama-50k from `20260924T195342.825090Z--colab-validation` with its AR parent from `20260921T170118.455805Z--colab-validation`. Their 125 HumanEval prompts and 125 MBPP prompts match exactly. After the evaluator's ordinary Markdown-code extraction, Python `ast.parse` rejects 35/125 BYOD HumanEval and 11/125 BYOD MBPP outputs, versus 0/125 for both AR sets. The displayed fragments are saved items HumanEval/10, HumanEval/2, MBPP/25, and MBPP/79.
- The third diagnostics panel reads `Long validation loss`, imported from `outputs/llama-3.1-8b-mask-long/metrics.jsonl`. The reproducible snapshot covers validation measurements every 500 updates through update 50,000. The uninterrupted `llama-3.1-8b-mask-long` run supplies the Llama-50k factual benchmarks and the 32/64/128-NFE generation trajectories.
- Radar spokes deliberately retain a common absolute 0--100% accuracy scale. Per-benchmark min--max normalization would visually magnify narrow ranges and make equal radii and polygon areas incomparable across tasks.

## Earlier-draft statements corrected

- Four parent families are now included, not three: Gemma, Llama, Qwen, and Ministral.
- The selected runs use a 256-token maximum sequence length, not 1,024.
- LoRA targets only `q_proj` and `v_proj`, not query/value/output projections.
- Normalization layers are frozen (`train_normalization_layers: false`).
- The selected runs use IID answer/EOS-padding masking.
- Repeated EOS batch padding is visible to bidirectional attention, can be masked, and participates in the loss because `eos_padding_loss: true`.
- Each 25k run uses 400,000 examples over 25,000 batch-16 updates. The uninterrupted Llama-50k run uses 800,000 examples over 50,000 updates.

## Llama merge ablation

- Unmerged adapter run: `20260918T112818.173051Z--colab-validation`, model `llama-3.1-8b-mask/best`.
- Merged run: `20260918T123901.774999Z--colab-validation`, model `merged:/content/drive/MyDrive/lad-generic-results/merged/llama-3.1-8b-mask`.
- Both use 30 prompts, 128 generated tokens, 32 denoising steps, seed 1234, temperature 0.7, the LLaDA-style sampler, and Phi-4 scoring.
- Adapter-loaded: token-weighted PPL 19.381430; mean sliding model-token Distinct-1/2/3 = 0.495153/0.788446/0.898893.
- Merged: token-weighted PPL 19.282753; mean sliding model-token Distinct-1/2/3 = 0.497539/0.806884/0.917994.
- At 128 denoising steps, token-weighted PPL is 5.081 (adapter-loaded) versus 4.764 (merged).
- Adapter-loaded / merged accuracies: ARC-C 83.2/84.0, GPQA 29.6/30.4, GSM8K 65.6/63.2, HellaSwag 70.4/69.6, HumanEval 31.2/29.6, MATH 25.6/24.8, MBPP 43.2/41.6, MMLU 59.2/60.8, and MMLU-Pro 30.4/30.4. The unweighted means are 48.7% and 48.3%.
- The merged safetensors index records 8,030,261,248 parameters and 16,060,522,496 bytes of BF16 weights. The adapter-loaded parameter audit records 8.466B total parameters, including 436.2M LoRA parameters. Phrase the conclusion as restoration of the base architecture's parameter count; on-disk size can vary with dtype, quantization, and serialization.

## Compute-estimate reproduction

- Run `python scripts/estimate_paper_compute.py --output iclr2027_submission/source_results/compute_estimates.csv` from the repository root.
- The manuscript uses $C=6ND$, 40% MFU, and 989 dense-BF16 TFLOP/s for standardized H100-equivalent estimates.
- The LLaDA calibration gives 77,519.380 predicted versus 130,000 reported GPU-hours and 23.8521% implied utilization.
- The Fast-dLLM v2 calibration uses its exact appendix token count, $2{,}500\times256\times2{,}048=1.31072$B, and 312 dense-BF16 TFLOP/s for A100: 122.530 predicted versus 768 reported GPU-hours and 6.3818% implied utilization. Its doubled clean/noised representation and specialized attention make this an estimator diagnostic rather than a measured MFU.

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
