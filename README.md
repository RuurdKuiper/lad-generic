# Bidirectional denoising adaptation for instruction models

This project adapts causal instruction models as same-position, bidirectional denoisers. It supports Llama 3 8B Instruct, Qwen2.5 7B Instruct, Gemma 2 9B IT, and the text-only Ministral 8B Instruct 2410 checkpoint through one entry point.

`mask_only` retokenizes the dataset source fields (`instruction`, `input`, `output`) for the chosen tokenizer and corrupts only genuine answer tokens online. Training masks are resampled; validation and test masks are deterministic from the configured seed and example index.

`structured` uses Llama-tokenized stored rows. Legacy rows with pre-corrupted
`input_ids` are consumed unchanged; clean rows (`input_ids == labels`) receive
the historical LAD structural answer noise online. Training noise is resampled,
while validation/test noise is deterministic from the seed and row index.

The current configurations use `Ruurd/LAD-training-100k-256`. `mask_only`
retokenize its `system`, `instruction`, `input`, and `output` fields with a
512-token limit. Llama structured runs use the stored clean tokenization and
apply structural corruption online.

## Commands

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

On NVIDIA CUDA/Linux, install the optional 8-bit optimizer support as well:

```bash
python -m pip install -e '.[cuda]'
```

The CUDA extra is intentionally optional because `bitsandbytes` is not
generally supported on macOS/MPS. Select it with `optimizer: adamw8bit` in the
config.

For native FP8 training on Ada SM89, Hopper, or Blackwell GPUs, install NVIDIA
Transformer Engine as well:

```bash
python -m pip install -e '.[fp8]'
```

The FP8 extra pins Transformer Engine 2.13 because its PyTorch extension uses
the CUDA 12 core provided by current Colab runtimes. Transformer Engine 2.14+
PyPI PyTorch packages require CUDA 13 and will fail there with a missing
`libcublas.so.13` error.

Current Colab images may also include TorchAO 0.10, while PEFT requires
TorchAO 0.16 or newer whenever it detects that optional package. This project
does not use TorchAO, so remove the incompatible preinstalled copy after
installing the project:

```bash
python -m pip uninstall -y torchao
```

Enable it with an FP16 or BF16 master-weight precision. Unsupported GPUs such
as A100 automatically fall back to BF16 and print a warning; an FP8-capable GPU
without Transformer Engine installed fails with an installation instruction.

```yaml
precision: bf16
fp8:
  enabled: true
  backend: transformer_engine
  format: HYBRID
```

FP8 is used only while the model is training. Validation and generation remain
at the configured master-weight precision. Each run records `fp8_requested`,
`fp8_active`, the GPU capability, and `resolved_training_precision` in
`resolved_config.json`.

For gated Hugging Face models, put your token in a local `.env` file (do not commit it):

```dotenv
HF_TOKEN=hf_your_token_here
```

`train.py` loads this file automatically and passes the token to the tokenizer and model loaders.

Dataset artifacts are cached in `data/huggingface/` and base model/tokenizer snapshots in `base_models/` by default. Override these with `cache_dir` and `base_model_cache_dir` in a configuration if you prefer other locations. Both directories are excluded from version control.

### Build and publish the training mixture

Create the 500k-row, 45% general / 18% reasoning / 18% math / 19% code
mixture and upload it in one command:

```bash
python build_training_dataset.py --repo-id YOUR_HF_USER/LAD-training-v2
```

`HF_TOKEN` is read from `.env`; it needs write access for uploads. Pass
`--private` for a private dataset or `--no-upload` to only save under
`data/lad-training-v2`. The builder uses only upstream training splits and
removes exact normalized prompt matches from the represented benchmarks'
validation/test splits. It keeps complete examples whose prompt is at most 256
tokens and whose full chat sequence is at most 512 tokens—accepted answers are
never silently truncated.

Within each category, preferred source shares are filled first. If a smaller
source runs out, unused unique examples from the larger sources fill the gap.
Only when the entire category is exhausted does the builder cycle through its
eligible rows again, distributing repeats evenly while preserving the requested
45/18/18/19 category proportions. The console reports each oversampled category
and its unique-row count.

Each row retains `system`, `instruction`, `input`, and `output` for tokenizer-independent
`mask_only` training. It also stores identical clean `input_ids` and `labels`
tokenized with Llama 3.1 for `structured` compatibility. Arrays are variable
length; the existing collator pads each batch dynamically. To build a smaller
trial before the full upload:

```bash
python build_training_dataset.py --total-examples 1000 --no-upload
```

On macOS CPU/MPS, use a tiny configuration after setting a reachable tiny dataset/model:

```bash
python train.py --config configs/smoke_test.yaml
```

On one NVIDIA GPU:

```bash
python train.py --config configs/llama3_8b.yaml
# Text-only Ministral 8B (not the multimodal checkpoint):
python train.py --config configs/ministral8b.yaml
```

On an Ubuntu multi-GPU cluster:

```bash
accelerate launch --num_processes 8 train.py --config configs/qwen25_7b.yaml
```

## One-command HPC training

After filling in the valid account, partition, time, and resource values in
`hpc/slurm.env`, submit and follow the 8B run from any local directory with:

```bash
./hpc/run.sh configs/llama3_8b_hpc.yaml
```

The launcher requires a working `ssh umcu-hpc`, local `rsync`, the remote
Micromamba executable at `/home/julius_bs/rkuiper2/.local/bin/micromamba`, and
the remote-only Hugging Face token file at `$HOME/.hf_token`. It validates the
YAML, synchronizes uncommitted source changes without copying caches, outputs,
or secrets, submits with `sbatch --parsable`, then follows status and logs.
It stages job-local outputs periodically under `/hpc/tmp/rkuiper2/<job-id>/`
and downloads them, including partial checkpoints and Slurm logs, to
`results/<job-id>/` when the job ends.

`hpc/slurm.env` is the sole location for Slurm account and resource settings;
there were no existing repository settings to reuse, so its blank values must
be set to values approved for this cluster. If the local terminal closes, run
`squeue -j <job-id>` and inspect `/hpc/tmp/rkuiper2/<job-id>/` after reconnecting;
you can copy the staged directory with `rsync`. Cancel only when intended with
`ssh umcu-hpc scancel <job-id>`. Ctrl-C in the launcher asks whether to cancel
the remote job and otherwise leaves it running.

When `LAD_STORAGE` is set, training resolves relative `output_dir`, cache, and
resume paths below that directory. Normal local execution is unchanged when it
is unset.

For Colab, mount Google Drive and set `LAD_OUTPUT_ROOT` before launching runs:

```python
from google.colab import drive
import os

drive.mount("/content/drive")
os.environ["LAD_OUTPUT_ROOT"] = "/content/drive/MyDrive/lad-generic-results"
```

This persists outputs, checkpoints, metrics, and resolved configurations on
Drive while leaving model/dataset caches on the faster temporary Colab disk.
Set this variable only in Colab; local and HPC runs are unaffected. The output
subdirectory from each YAML is preserved below the chosen Drive root.

### Colab inference from Google Drive

Saved adapters can be used directly from Drive; do not copy them back to
`/content`. After mounting Drive and installing this repository, point the
inference loader at the `outputs` directory below the same `LAD_OUTPUT_ROOT`:

```python
from diffusion_lm.inference import find_adapters, load_session, denoise

drive_outputs = "/content/drive/MyDrive/lad-generic-results/outputs"
print("\\n".join(find_adapters(drive_outputs)))  # for example: llama-3.1-8b-mask/best

session = load_session("llama-3.1-8b-mask/best", drive_outputs, device_name="cuda", quantization="4bit")
answer, status = denoise(
    session,
    question="What do you know about Amsterdam?",
    system_prompt="You are a helpful assistant.",
    max_new_tokens=128,
    num_steps=32,
    noise_level=1.0,
    temperature=.7,
    top_k=20,
    seed=42,
)
print(status)
print(answer)
```

Use an adapter name printed by `find_adapters`; this can be `best`, `final`,
or a saved `checkpoint-N` model. The base model is loaded normally (and may
need `HF_TOKEN` for gated models), while only the small LoRA adapter and its
normalization state are read from Drive. To use the interactive interface
instead, set `DIFFUSION_LM_OUTPUTS_DIR` to `drive_outputs` and run
`python app.py` in a Colab cell. The app automatically requests a temporary
Gradio share link in Colab. If needed, force it with
`DIFFUSION_LM_GRADIO_SHARE=1 python app.py`; share links are public to anyone
who has the URL, so do not enter secrets into the interface.

`quantization="auto"` (the default) follows the saved run's `quantization`
setting; use `quantization="4bit"` to force memory-efficient CUDA inference,
including for a run trained without quantization. It requires the CUDA extra
(`pip install -e '.[cuda]'`) and an NVIDIA GPU. The Gradio interface has the
same `Inference quantization` selector. On CUDA GPUs without native BF16
support (including T4), inference automatically uses FP16 compute even when
the saved training configuration requested BF16.

For an inference-only comparison with the earlier full-model checkpoint, the
app has one `Legacy checkpoint` loader row. It automatically uses
`legacy/inference/diffusion-model-3B.pth` when that local file exists, without
downloading the checkpoint from Hugging Face; otherwise it uses the configured
Hugging Face repository and filename as a fallback. The selected checkpoint
filename is looked up in the same local directory as the 8B checkpoint. Override
the local path with `DIFFUSION_LM_LEGACY_CHECKPOINT=/path/to/model.pth`. The tokenizer may
still be loaded from its Hugging Face cache (or downloaded once if it is not
cached). This runs the checkpoint through the current sampling and remasking implementation. The
historical base tokenizer has no native chat template, so
that loader automatically uses the legacy Llama prompt layout; the current
sampling and remasking implementation remains in use. The legacy wrapper
retains its own full bidirectional attention forward because passing a second
attention mask to it is invalid. Full `.pth` checkpoints use Python pickle;
load only sources you trust. Every loader performs a one-step real
forward-pass preflight before reporting success, so incompatible checkpoints
fail at load time rather than after starting a generation.

The app can also load the official `GSAI-ML/LLaDA-8B-Instruct` model from
Hugging Face. This loader runs on CUDA or, experimentally, Apple MPS; CUDA is
preferred for speed and memory headroom. MPS loads the 8B model in FP16 and may
need substantial unified memory. LLaDA runs through this project's denoising
loop, so the ordinary re-masking and retention controls remain available. It
downloads and executes the model's trusted remote Hugging Face code. The
project pins Transformers to the LLaDA-compatible 4.x range.

The app's `Selected-token retention` control has two retention variants.
`Retain positions; allow token changes` prevents selected positions from being
masked again while allowing later denoising steps to replace their token
values. `Retain and lock token values` also prevents re-masking, but restores
the selected value after every later prediction. Existing YAML settings with
`permanent_unmask: true` retain the locked behavior for compatibility.

The optional app setting `Early stop after 3 identical predictions` ends a
denoising request after the complete sampled answer-token sequence is unchanged
for three consecutive iterations, matching the legacy app. It is disabled by
default. For validation generation, set
`generation_perplexity.early_stopping: true` in the YAML.

Run the same check without starting Gradio:

```bash
python preflight_inference.py --legacy-repo ruurd/tini_model --device cuda
```

For a saved adapter, use `python preflight_inference.py --adapter RUN/best
--outputs-dir outputs --device cuda`. A successful command has completed an
actual denoising forward pass, not merely downloaded or deserialized the model.

Set `max_updates` in a training YAML to a positive integer to stop after that
many optimizer (gradient-update) steps. Training then performs its normal final
evaluation/output handling and the Slurm job exits, releasing its allocation.
When set, training preparation bounds the train split to approximately
`max_updates × gradient_accumulation_steps × batch_size` examples; structured
preprocessing stops once that many usable examples are available. Validation
and test splits are not reduced by this optimization.

Set `max_grad_norm` to a positive value to clip the global gradient norm once
per optimizer update, after all gradient-accumulation microbatches have
contributed. Omit it for no clipping.

Optional learning-rate scaling treats `learning_rate` as the rate for a
reference effective batch size:

```yaml
learning_rate: 1.0e-5
learning_rate_scaling:
  enabled: true
  mode: sqrt  # sqrt or linear
  reference_batch_size: 8
```

The effective batch size is `batch_size × gradient_accumulation_steps × number
of processes`. With `mode: sqrt`, the multiplier is `sqrt(effective batch /
reference batch)`; with `mode: linear`, it is `effective batch / reference
batch`. Disable the block to use `learning_rate` unchanged. Each run records
`effective_batch_size`, `learning_rate_scale`, and `resolved_learning_rate` in
`resolved_config.json`.

Mask-only runs tokenize and truncate each clean example once, then reuse the
prepared Arrow cache from `prepared_data_cache_dir`; stochastic corruption
still happens online for every training batch. CUDA runs also use pinned,
non-blocking batch transfers. `prefetch_factor` controls the number of batches
prepared ahead by each DataLoader worker (default `4`). For sparse objectives,
`selected_logit_optimization: true` applies the frozen language-model head only
to supervised positions rather than constructing unused vocabulary logits for
the rest of the sequence.

Gated model access must be configured through the normal Hugging Face authentication mechanism. Each run verifies that `mask_token` (default `MASK`) is exactly one ordinary vocabulary token and records its text, token ID, and decoding in `mask_token.json`. Ministral's Tekken tokenizer splits uppercase `MASK`, so its supplied configurations use the verified single-token `<?>` vocabulary marker instead.

## Outputs

Each run writes `resolved_config.json`, `parameter_audit.json`, `mask_token.json`, `metrics.jsonl`, regular `checkpoint-*` Accelerate states, `best`, `final`, and `test_metrics.json`. Resume with `resume_from_checkpoint: outputs/.../checkpoint-N` in the YAML.

During training, the terminal displays a live progress bar with completed batches and the current training loss. At each validation interval it prints both training and deterministic validation loss; the same values are recorded in `metrics.jsonl`. Configurations use a deterministic 200-example validation subset by default (`validation_samples: 200`) so runs are directly comparable. The test split remains separate and is evaluated only after model selection.

Plot one or more runs with `plot_losses.py`. It smooths the logged training
loss by ten points by default and overlays validation points:

```bash
python plot_losses.py outputs/llama-3.1-8b-mask outputs/llama-3.1-8b-structured \
  --labels mask_only structured --output outputs/loss-comparison.png
```

For Drive-backed Colab runs, pass their Drive output directories and an output
path on Drive. Use `--smooth 1` for the raw training curve or `--log-y` when
early losses dominate the graph. Matplotlib is included in the normal project
installation.

Checkpoint policy is controlled by `checkpoint_mode`:

- `only_best_model`: overwrite `best/` whenever validation improves; no regular checkpoint snapshots or `final/` copy are written.
- `every_model`: save inference-ready adapter/tokenizer/normalization snapshots at each `checkpoint_steps` interval as `checkpoint-N/`, plus `final/`; optimizer, scheduler, and RNG state are not stored.
- `every_checkpoint`: retain resumable `checkpoint-N/` snapshots and write `final/` at the end.

For an exact interruption resume, set `checkpoint_mode: every_checkpoint` and use `resume_from_checkpoint: outputs/<run>/checkpoint-N`; this restores optimizer, scheduler, and RNG state. With `only_best_model`, continue from the saved adapter by adding `resume_from_adapter: outputs/<run>/best`; this warm-starts the weights with a fresh optimizer and step counter.

Starting again with the same `output_dir` replaces the project-managed
checkpoints, adapters, metrics, and metadata, including stale checkpoint
numbers from an earlier run. Runs with `resume_from_checkpoint` or
`resume_from_adapter` preserve the existing artifacts so the resume source is
not deleted.

## Interactive inference

Generation parameters can be tuned with open-ended prompts using:

```bash
python optimize_generation.py --config configs/generation_search.yaml
```

The search varies the configured grid, generates each prompt repeatedly, and
reports autoregressive perplexity plus repeated 3-gram fraction (decoded EOS
tokens are not included). Results and the best parameter set are written to
`outputs/generation_search.json`.

After a validation step has created `outputs/<run>/best/`, launch the local Gradio app:

```bash
python app.py
```

The app discovers saved adapter directories under `outputs/`. Select one, choose a device, click **Load model**, then provide a question and denoising settings. It uses the selected run's base model and tokenizer, its LoRA adapter, saved normalization parameters, and the same bidirectional attention mask as training. During generation it streams the intermediate states: confidence-colored tokens, gray `MASK` positions, blue permanently retained tokens, and the current denoising step. Inference includes temperature, top-k, permanent unmasking, confidence-guided retention, and proportional unmasking. Legacy n-gram grammar and repetition-removal options are intentionally not included.

## Benchmark validation

The optional benchmark runner evaluates every saved `best/` adapter, or the model paths listed in `configs/benchmarks.yaml`, using pure diffusion generation. It reads each run’s `corruption_mode` from `resolved_config.json`; structured runs use LAD-style retention defaults and mask-only runs use the official LLaDA fixed-budget, low-confidence transfer sampler. Autoregressive evaluation of the original base model is optional and disabled by default.

```bash
python evaluate_benchmarks.py --config configs/benchmarks.yaml
```

Set `tasks` to `[mmlu, mmlu_pro, hellaswag, arc_c, gsm8k, math, gpqa, humaneval, mbpp, open_ended]` for the complete suite. Leave both limits unset for full datasets, set `limit` for a fixed number per task, or set `limit_fraction: 0.05` for a deterministic, evenly-spaced 1/20 smoke sample from each task. MMLU and MMLU-Pro are the exception: their subsets use a fixed-seed shuffle before selection so grouped source rows do not all come from the first subject. Other benchmarks retain their original subset selection and ordering. `limit` and `limit_fraction` are mutually exclusive.

Set `models` to adapter paths relative to `outputs/`, or add a hosted LLaDA model with the `llada:` prefix, for example `llada:GSAI-ML/LLaDA-8B-Instruct`. List LLaDA and one or more adapter paths together to compare them in the same suite. A local legacy LAD checkpoint can be added with `legacy:/absolute/path/to/diffusion-model-3B.pth`; a Hugging Face-hosted legacy checkpoint can be added with `legacy-hf:Ruurd/tini_model|diffusion-model-8B.pth`. Configure its tokenizer with `legacy_tokenizer_name_or_path` (default `meta-llama/Llama-3.2-3B`). Hosted LLaDA and mask-only adapters use the same reproduction of the official fixed-budget sampler: greedy/Gumbel prediction, low-confidence token transfer, and the linear schedule's exact number of permanent transfers per step, with no proportional-unmask heuristic. They automatically apply the published LLaDA-8B-Instruct generation length, step count, block length, and EOS/EoT treatment for MMLU, MMLU-Pro, HellaSwag, ARC-C, GSM8K, MATH, GPQA, HumanEval, and MBPP. Adapters retain their native tokenizer and chat template, including native EOS/EoT IDs. `llada_generation`/`llada_task_generation` override the hosted model, while `mask_only_generation`/`mask_only_task_generation` override trained adapters. Both LLaDA and legacy LAD skip the autoregressive comparison and can run alongside saved adapters. Set `tasks` to any combination of the standard tasks or `open_ended`. The effective settings are recorded in every per-example result and summary. Multiple-choice prompts and `A: answer` targets match the training formatter and are scored by their leading label. HellaSwag uses its labelled validation split, GPQA uses its published train-named evaluation set, GSM8K extracts the final number from a full rationale, and MATH compares normalized final answers. Each non-code JSONL record includes the extracted prediction and target used for scoring. The `open_ended` task uses 30 fixed questions by default and records per-answer perplexity plus unigram/bigram/trigram repetition in the JSONL results. Perplexity is calculated after generation with one shared configurable reference model (`perplexity.model_name_or_path`, default `microsoft/phi-4`), loaded once and kept separate from training-time perplexity. The supplied Colab configuration loads this independent 14B reference in 4-bit mode with BF16 compute. Repetition metrics remain tokenizer-based and are reported alongside token-weighted perplexity and mean NLL. Changing the reference model/tokenizer changes the perplexity scale, so compare only runs scored with the same recorded `perplexity_reference`. For a comparative quality score, enable `open_ended_judge` and provide `OPENAI_API_KEY`; the default `gpt-5` judge receives anonymous, deterministically shuffled responses and awards unique Borda points from `N-1` to `0` for each prompt. It compares diffusion outputs by default; add `autoregressive` to `open_ended_judge.methods` only when that baseline should compete. The run saves the complete audit trail in `judge_rankings.jsonl`, its standings in `judge_leaderboard.json`, and judge fields in the ordinary result and summary records. The Colab template [`notebooks/lad-generic-validation.ipynb`](notebooks/lad-generic-validation.ipynb) mounts Drive, includes official LLaDA in the example run list, and exposes these settings in one cell. Set `limit` for a smoke evaluation before running full benchmark splits. Code tasks are executed with a local timeout, so evaluate generated code only in a trusted environment. The task protocol and defaults follow the official [LLaDA evaluation guide](https://github.com/ML-GSAI/LLaDA/blob/main/EVAL.md) and [generation implementation](https://github.com/ML-GSAI/LLaDA/blob/main/generate.py). Prompts, dataset normalization, and scoring remain this suite's shared protocol for fair within-suite model comparisons, so these results are not an exact reproduction of the paper's separate OpenCompass harness.

Each invocation creates a new timestamped directory under `results_dir` (default `outputs/benchmark_runs`). `run.json` captures status and the resolved evaluator config, while `summary.json` is the complete rollup. Detailed files are separated as `models/<model>/<task>/<method>/results.jsonl` and `summary.json`; a model-level `summary.json` is also written. Set `run_name` to append a readable label to the generated run ID. The old `results_path` setting is accepted for compatibility, but now routes into a sibling `benchmark_runs/` directory instead of appending to the shared file.

For structured loss, `all_answer_tokens` is the default safe objective; `corrupted_answer_tokens` restricts loss to changed answer positions; and `all_tokens` supervises prompt, assistant formatting, and answer positions. Set `eos_padding_loss: true` to include trailing EOS padding in any of these objectives, or `false` to exclude it. When omitted, the legacy behavior is retained: enabled for `all_tokens`, disabled for answer-only objectives. Validation can optionally run fixed-prompt generation and base-model perplexity. Enable `generation_perplexity.enabled` in a YAML to save each prompt’s final generated answer in `generation_metrics.jsonl` and add the corresponding per-prompt `generation_perplexity` plus aggregate `generation_perplexity`, `generation_mean_nll`, and `generation_tokens` to validation metrics. Set `generation_perplexity.interval_steps` to run this more expensive generation calculation less often than ordinary loss validation; it defaults to `validation_steps` and must be a multiple of it. The shared ordered prompt set lives in `src/diffusion_lm/generation_prompts.txt`; `generation_perplexity.num_prompts` selects its prefix, and it is loaded once so every validation checkpoint in a run uses the same prompts. The evaluator temporarily disables LoRA and restores the original pre-training normalization weights, so trained norms do not contaminate the base-model score. `train_normalization_layers` independently controls whether norms are trainable.

With `corruption_mode: mask_only`, enabled `eos_padding_loss` also places EOS padding in the stochastic corruption candidates. Thus it is learned as a denoising target rather than simply copied from the input; this applies to all three loss behaviors. EOS padding is visible to attention in both directions, making the configured context width an explicit signal during concise-answer training.

For an adapter warm-start where the original run did not save full
Accelerate checkpoints, set `resume_data_updates` to the number of updates
already consumed. This excludes the corresponding prefix of the deterministically
prepared training examples before constructing the new dataloader, while
retaining fresh on-the-fly mask sampling:

```yaml
resume_from_adapter: outputs/llama-3.1-8b-mask/checkpoint-10000
resume_data_updates: 10000
max_updates: 90000
```

Keep the seed, batch size, gradient accumulation, and dataset configuration
unchanged for this data offset to correspond to the original run.
