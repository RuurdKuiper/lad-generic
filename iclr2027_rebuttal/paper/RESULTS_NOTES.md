# Results and provenance notes

This internal file records current revised-paper sources and retained historical measurements. It is not intended for submission.

## Selected runs

| Paper label | Saved run | Updates | Training examples in stage | Parent |
|---|---|---:|---:|---|
| Gemma-25k | `gemma-2-9b-mask` | 25,000 | 400,000 | `google/gemma-2-9b-it` |
| Llama-25k | `llama-3.1-8b-mask` | 25,000 | 400,000 | `meta-llama/Llama-3.1-8B-Instruct` |
| Llama-50k | `llama-3.1-8b-mask-long` | 50,000 | 800,000 | `meta-llama/Llama-3.1-8B-Instruct` |
| Qwen-25k | `qwen-2.5-7b-mask` | 25,000 | 400,000 | `Qwen/Qwen2.5-7B-Instruct` |
| Ministral-25k | `ministral-8b-mask` | 25,000 | 400,000 | `mistralai/Ministral-8B-Instruct-2410` |

The user's shorthand `ministral-mask` maps to the saved folder `ministral-8b-mask`.

## Completed benchmark source — 16 November revision

- Current task scores are exported from the final selected per-question outcomes into `source_results/benchmark_results_20261116.json`; source hashes, integer correct/evaluated counts, scorer/selection versions, bootstrap settings and all intervals are recorded there. Historical workbooks are unchanged.
- Ten configurations each use the same 250 questions on eight tasks and all 164 HumanEval questions: 21,640 selected outcomes, a net increase of 10,570 over the recovered historical selection. Sanitized MBPP has 257 available test items; we use 250.
- Equal-weight nine-task means are Gemma D 52.43%, Gemma AR 62.73%, Qwen D 48.29%, Qwen AR 70.66%, Ministral D 48.54%, Ministral AR 62.70%, Llama-25k 47.93%, Llama-50k 47.80%, Llama AR 56.71%, and LLaDA 49.55%.
- Mean intervals use 20,000 within-task item bootstrap replicates (seed 20261116); paired differences use the same item draws for both models (seed 20261115). Individual task intervals use Wilson's method. All are nominal 95% intervals, not training-seed or unseen-task uncertainty. They do not adjust for comparing five BYOD configurations or selecting Gemma as the strongest conversion. No superiority claim is made; Gemma 9B and LLaDA 8B also differ in size and training history, and there is no matched full-fine-tuning control.
- BYOD-Gemma minus LLaDA is +2.88 pp [0.74, 4.98]; Gemma minus its AR parent is −10.30 pp [−12.33, −8.31]; Llama-50k minus Llama-25k is −0.14 pp [−1.81, 1.49]. The longer run has no clear average task-accuracy benefit.
- Updated syntax counts are 51/164 HumanEval and 24/250 MBPP for BYOD-Llama-50k, versus 0/164 and 0/250 for Llama AR. Other AR outputs include one invalid Gemma HumanEval program. Historical syntax examples remain illustrative saved fragments.
- The selected Gemma cohort is fresh across all tasks; Qwen's faulty new eager-attention cohort was replaced using SDPA; MATH uses the uniformly applied v3 final-answer scorer. Do not attribute all historical-to-final differences to sample size.

## Historical workbook interpretation (superseded for expanded benchmarks)

- Original source: `source_results/Results.xlsx`, copied from `results/Results.xlsx` on 2026-09-18.
- Latest open-ended snapshot: `source_results/Results_open-ended-128t-32i-merged_20260918.xlsx`, copied from `results/Results_open-ended-128t-32i_20260918.xlsx` after importing the merge benchmark.
- Current paper workbook: `source_results/Results_training-20260924.xlsx`, copied from `results/Results_training-20260924.xlsx`. It contains the corrected 32/64/128-NFE long-run progression, completed validation loss, and the latest task-benchmark values.
- The earlier manuscript used workbook task cells for its nine-task average. Those historical scores are superseded in Table 3 by the completed per-question selection above. The workbook remains a source for independent open-generation/training measurements.
- The workbook row named `1-gram repetition` predates the final sliding model-token Distinct-n implementation. Those numbers are intentionally not presented as Distinct-1.
- The manuscript treats published LLaDA results as protocol-separated context, not as directly matched measurements.

## Automatically generated figures

- For revised benchmark artifacts, run `MPLCONFIGDIR=/tmp/byod-paper-mpl XDG_CACHE_HOME=/tmp/byod-paper-cache .venv/bin/python iclr2027_rebuttal/analysis/update_manuscript_benchmarks.py` from the repository root. This regenerates the benchmark source, main/appendix tables, all benchmark radar PDFs/PNGs and their manifest. It does not alter open-generation figures or historical workbooks.
- The original `scripts/generate_paper_figures.py` workbook workflow is retained for independent historical/open-generation measurements. Running it over the revised figure folder would restore old radar data; use the revised benchmark export afterwards.
- Install the spreadsheet dependency with `pip install -e '.[paper]'` if `openpyxl` is unavailable.
- Revised benchmark PDF/PNG outputs are written to `iclr2027_rebuttal/paper/figures/`; `figure_data.json` records their versioned source and exact values separately from the historical workbook-backed non-benchmark measurements.
- `benchmark_radar_panels` and both standalone radar exports use the expanded shared 250-question lists and all 164 HumanEval items.
- `llama_training_diagnostics` reads the corrected 32/64/128-NFE progression directly from the current workbook. Solid marked lines are BYOD-Llama checkpoints; matching dashed horizontal lines are LLaDA references. The dotted gray line is the unchanged Llama AR parent.
- `scripts/calculate_open_ended_uncertainty.py` reconstructs prompt token counts with the Phi-4 tokenizer and archives 20,000-resample percentile-bootstrap 95% CIs in `source_results/open_ended_uncertainty.json`. These intervals are retained for analysis but are not displayed in the paper figures or table.
- Table 4 uses 30 prompts for most rows. The uninterrupted Llama-50k row uses 100 prompts from `20260923T190517.263478Z--colab-validation`; the other main rows come from `20260918T135058.643507Z--colab-validation`, with the corrected Ministral row from `20260921T131916.314780Z--colab-validation`.
- Bidirectional-attention results come from `20260924T085113.502527Z--colab-validation` and are archived in `source_results/right_context_copy_results.json`. With-clue exact match for Gemma, Llama-25k, Llama-long-best, Qwen, Ministral, and LLaDA is 100/90/70/20/100/100%; all score 0% without the clue. The clue changes every model's greedy prediction in 100% of examples. This run uses the clarified `COPY:` prompt, a training-matched system message, and single-forward argmax decoding.
- The code-error appendix uses final selected outputs for its expanded rates. The displayed historical fragments remain saved examples from HumanEval/10, HumanEval/2, MBPP/25, and MBPP/79; their texts were not rewritten during expansion.
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

1. Completed: all ten configurations now have the shared target counts, including the AR parents.
2. Completed for revised benchmark export: source hashes, per-question selection and scoring provenance are retained; public anonymous release packaging remains pending.
3. Completed: explicit 250/164 denominators, full available-set counts and item-based uncertainty intervals are in the revised manuscript.
4. Archive the exact Hugging Face dataset commit used during training. The live dataset page may have changed since the runs.
5. Recover or regenerate the dataset manifest with category/source counts and filtering policy.
6. Record wall-clock time, GPU-hours, peak memory, and inference latency/throughput.
7. Recompute Distinct-1/2/3 with the final sliding model-token implementation.
8. Verify every external bibliographic entry and add model/dataset technical-report citations.
9. Complete the checkpoint-by-NFE sweep needed to test whether continued training preferentially improves the parallel decoding regime ($\mathrm{NFE}<L$).
