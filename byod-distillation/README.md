# Frozen AR teacher → diffusion student

[Open experimental Colab](https://colab.research.google.com/github/RuurdKuiper/lad-generic/blob/experiment/ar-distillation/byod-distillation/notebooks/train_distillation.ipynb)

[Open the automatic baseline vs mixed-loss comparison](https://colab.research.google.com/github/RuurdKuiper/lad-generic/blob/experiment/ar-distillation/byod-distillation/notebooks/compare_distillation.ipynb)
runs both 1,000-update Llama 3.2 1B trials sequentially, with live dashboards,
Drive saving, loss-versus-time plots, and a final summary table. Select a GPU,
provide Hugging Face access, and run all cells. Set `BATCH_SIZE = 8` in the
comparison settings for batches of eight in both runs (8,000 examples each
at 1,000 updates). The default batch size is 1.

This is an independent source snapshot of BYOD on the
`experiment/ar-distillation` branch of `RuurdKuiper/lad-generic`.
The published [BYOD reproduction](https://github.com/RuurdKuiper/BYOD), its
notebook, and `byod-reproducible/` are unchanged. This folder does not import code
from either the reproduction folder or the parent project's `src/`.
`UPSTREAM_SNAPSHOT.json` records the original files and their SHA-256 hashes.

## Objective

The teacher is the pretrained causal base model with LoRA disabled and dropout
off. All base weights, including normalization layers and the vocabulary head,
stay frozen. It shares storage with the student rather than loading a second
model. The student has active LoRA and bidirectional attention.

For each clean target token at position `t`, the teacher reads the unmasked
label sequence with the architecture's native causal attention mask (including
its sliding windows, if any). Its output at `t - 1`
predicts token `t`, using only tokens before `t`. The student instead predicts
that token at position `t` from the corrupted bidirectional input. The teacher
never sees the masked student input, nor the current/future target as context.
Position zero has no previous token and contributes no distillation loss.

```text
teacher target: p_AR(v | clean tokens before t), LoRA disabled, no gradients
student output: p_DLM(v | masked sequence), bidirectional, LoRA trainable
L = (1 - weight) * original_denoising_loss
    + weight * temperature² * KL(p_teacher,T || p_student,T)
```

Both experimental objectives warm up for 25 updates to a peak learning rate of
`1e-5`, then cosine-decay to `1e-6`. After warmup, decay is limited to a factor
of ten from the resolved peak, including when the peak learning rate is changed.
The current learning rate is saved in the training metrics.

The defaults are **weight 0.5** and **temperature 1.0**. The KL uses every
vocabulary token, not just the probability of the ground-truth label and not a
top-k approximation. It is applied at the same supervised positions as the
ordinary denoising loss (normally masked answer/EOS-padding positions), with
the same inverse-noise weighting and 0.9/0.1 answer/padding reduction. Prompt
positions keep the ordinary recipe's exclusion. Setting teacher weight to zero
skips the teacher pass entirely and recovers the unmodified loss.

The LM head runs only at the relevant positions. KL is computed in chunks with
FP32 log-softmax and recomputed during backward to limit vocabulary-sized
intermediate storage. Gemma 2's output softcapping is preserved.

## Run the comparison

Open the Colab link above and select a GPU runtime. The notebook uses a shallow,
sparse checkout of **only this experimental folder** from the experimental
branch. Its installer retains the startup improvements from BYOD, including
reusing the GPU stack and delaying Gradio installation until inference.

1. Choose a small model in Quick mode. Defaults are 500 updates, batch size 1,
   gradient accumulation 4, and gradient checkpointing. Start with 2 updates
   for a GPU smoke test; 500 is a pilot, not evidence of convergence.
2. Set **Teacher weight** to `0`, run training, and retain its run directory.
3. Set **Teacher weight** to `0.5`, keep all other settings identical, and run
   training again. Each run starts from the same pretrained model, not from
   the previous run's adapter.
4. In Results, fill in `BASELINE_RUN` and `DISTILLED_RUN`. Compare the ordinary
   validation denoising loss versus both optimizer updates and elapsed time.

Use the same GPU type/runtime, model, seed, data, learning rate, batch settings,
and budget for both runs; repeat with several seeds for a stronger result.
The comparison helper rejects mismatched resolved configurations. Training
curves record the mixed objective, the original hard-target loss, teacher KL,
and elapsed seconds separately. The live dashboard plots all three training
losses, alongside the original validation loss, and displays the latest component
values in its status line. Components are shown before applying the mixing weights.
Validation/test and best-checkpoint selection
use only the original denoising objective, so they stay comparable.
Elapsed time starts after model/data setup and includes training and validation;
model download and dataset preparation are excluded.

The teacher adds a forward pass per training batch. This experiment tests
whether fewer updates can offset that extra compute; it does not assume faster
individual updates. Inspect generation quality as well as validation loss before
concluding that one model is better.

Experimental runs and token caches use `BYOD-distillation-runs/` and
`BYOD-distillation-cache/`, separate from the reproduction's Drive folders.
Each run saves its resolved experimental settings. Custom overrides can be
provided in the notebook's Config YAML field. Keep
`train_normalization_layers: false` so the shared teacher remains frozen.

## Run locally

Use a separate Python environment for this snapshot: it has its own project
metadata but retains the `diffusion_lm` import name for compatibility.

```bash
cd byod-distillation
pip install -e '.[colab,test]'
python train.py --model llama --mode quick --config configs/baseline.yaml
python train.py --model llama --mode quick --config configs/distillation.yaml
python compare_runs.py BASELINE_RUN_DIR DISTILLED_RUN_DIR --output comparison.png
pytest -q
```

For a matched 1,000-update pilot with batch size 1 and no gradient accumulation:

```bash
python run_comparison.py --output-root results/llama1b-1000
```

This runs both objectives in fresh processes and writes the configs, full logs,
adapters, `summary.json`, and `comparison.png`. It evaluates every 100 updates
on 64 fixed validation examples and uses 64 test examples for a quick final
check. The model/data revisions and all training settings match between runs.
Apple Silicon is supported through MPS; laptop timings should not be interpreted
as Colab CUDA timings. For a throughput-only estimate after caching the model
configuration, use `python scripts/benchmark_device.py`; its random weights and
synthetic inputs cannot establish learning quality.

Install `.[demo]` for the local Gradio inference app. Other BYOD model, data,
and inference instructions are in [UPSTREAM_README.md](UPSTREAM_README.md).
The shipped CPU tests cover the causal shift, absence of future-token leakage,
frozen teacher behavior after adapter changes, full-vocabulary KL values and
gradients, exception cleanup, gradient checkpointing/accumulation, and the
actual training loop at teacher weights 0, 0.5, and 1. A fresh Colab GPU run is
still needed to measure convergence and memory on your selected hardware.

Original trained-model demos (not trained with this experimental objective):
[Llama](https://huggingface.co/spaces/Dovelove/byod-llama-3.1-8b),
[Gemma](https://huggingface.co/spaces/Dovelove/byod-gemma-2-9b),
[Qwen](https://huggingface.co/spaces/Dovelove/byod-qwen2.5-7b),
[Ministral](https://huggingface.co/spaces/Dovelove/byod-ministral-8b).

[MIT license](LICENSE); inherited source attribution is retained.
