# Bidirectional denoising adaptation for instruction models

This project adapts causal instruction models as same-position, bidirectional denoisers. It supports Llama 3 8B Instruct, Qwen2.5 7B Instruct, and Gemma 2 9B IT through one entry point.

`mask_only` retokenizes the dataset source fields (`instruction`, `input`, `output`) for the chosen tokenizer and corrupts only genuine answer tokens online. Training masks are resampled; validation and test masks are deterministic from the configured seed and example index.

`structured` consumes the existing stored Llama-tokenized `input_ids`. It deliberately fails for Qwen and Gemma: the published structured corruption is token-ID-specific and its generator is not available. Use `mask_only`, or add tokenizer-specific structured preprocessing.

## Commands

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

For gated Hugging Face models, put your token in a local `.env` file (do not commit it):

```dotenv
HF_TOKEN=hf_your_token_here
```

`train.py` loads this file automatically and passes the token to the tokenizer and model loaders.

Dataset artifacts are cached in `data/huggingface/` and base model/tokenizer snapshots in `base_models/` by default. Override these with `cache_dir` and `base_model_cache_dir` in a configuration if you prefer other locations. Both directories are excluded from version control.

On macOS CPU/MPS, use a tiny configuration after setting a reachable tiny dataset/model:

```bash
python train.py --config configs/smoke_test.yaml
```

On one NVIDIA GPU:

```bash
python train.py --config configs/llama3_8b.yaml
```

On an Ubuntu multi-GPU cluster:

```bash
accelerate launch --num_processes 8 train.py --config configs/qwen25_7b.yaml
```

Gated Llama/Gemma access must be configured through the normal Hugging Face authentication mechanism. Each run verifies that literal `MASK` is exactly one ordinary vocabulary token and records the token ID/decoding in `mask_token.json`.

## Outputs

Each run writes `resolved_config.json`, `parameter_audit.json`, `mask_token.json`, `metrics.jsonl`, regular `checkpoint-*` Accelerate states, `best`, `final`, and `test_metrics.json`. Resume with `resume_from_checkpoint: outputs/.../checkpoint-N` in the YAML.

During training, the terminal displays a live progress bar with completed batches and the current training loss. At each validation interval it prints both training and deterministic validation loss; the same values are recorded in `metrics.jsonl`. Configurations use a deterministic 200-example validation subset by default (`validation_samples: 200`) so runs are directly comparable. The test split remains separate and is evaluated only after model selection.

Checkpoint policy is controlled by `checkpoint_mode`:

- `only_best_model`: overwrite `best/` whenever validation improves; no regular checkpoint snapshots or `final/` copy are written.
- `every_checkpoint`: retain resumable `checkpoint-N/` snapshots and write `final/` at the end.

For an exact interruption resume, set `checkpoint_mode: every_checkpoint` and use `resume_from_checkpoint: outputs/<run>/checkpoint-N`; this restores optimizer, scheduler, and RNG state. With `only_best_model`, continue from the saved adapter by adding `resume_from_adapter: outputs/<run>/best`; this warm-starts the weights with a fresh optimizer and step counter.

## Interactive inference

After a validation step has created `outputs/<run>/best/`, launch the local Gradio app:

```bash
python app.py
```

The app discovers saved adapter directories under `outputs/`. Select one, choose a device, click **Load model**, then provide a question and denoising settings. It uses the selected run's base model and tokenizer, its LoRA adapter, saved normalization parameters, and the same bidirectional attention mask as training. During generation it streams the intermediate states: confidence-colored tokens, gray `MASK` positions, blue permanently retained tokens, and the current denoising step. Inference includes temperature, top-k, permanent unmasking, confidence-guided retention, and proportional unmasking. Legacy n-gram grammar and repetition-removal options are intentionally not included.

## Benchmark validation

The optional benchmark runner evaluates every saved `best/` adapter, or the model paths listed in `configs/benchmarks.yaml`, using pure diffusion generation. It reads each run’s `corruption_mode` from `resolved_config.json`; structured runs use LAD-style retention defaults and mask-only runs use LLaDA-style global remasking. Autoregressive evaluation of the original base model is optional and disabled by default.

```bash
python evaluate_benchmarks.py --config configs/benchmarks.yaml
```

Set `limit` for a smoke evaluation before running full benchmark splits. Per-example predictions are appended to `outputs/benchmark_results.jsonl`; aggregate scores are written to `outputs/benchmark_results_summary.json`. Code tasks are executed with a local timeout, so evaluate generated code only in a trusted environment. The task protocol follows the official LLaDA evaluation distinction between conditional generation and likelihood evaluation, while this project intentionally uses pure diffusion generation for the requested comparison: [LLaDA EVAL.md](https://github.com/ML-GSAI/LLaDA/blob/main/EVAL.md).

For structured loss, `all_answer_tokens` is the default safe objective; `corrupted_answer_tokens` restricts loss to changed answer positions; and `all_tokens` explicitly reproduces the full-sequence objective, including prompt, assistant formatting, and EOS padding. Validation can optionally run fixed-prompt generation and base-model perplexity. Enable `generation_perplexity.enabled` in a YAML to save each prompt’s full denoising trajectory in `generation_metrics.jsonl` and add `generation_perplexity`, `generation_mean_nll`, and `generation_tokens` to validation metrics. The evaluator temporarily disables LoRA and restores the original pre-training normalization weights, so trained norms do not contaminate the base-model score. `train_normalization_layers` independently controls whether norms are trainable.
