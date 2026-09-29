# BYOD: Build Your Own DLM

Convert a pretrained instruction model into a bidirectional masked-diffusion
language model on one GPU. The same training entry point supports:

- Llama 3.1 8B Instruct
- Gemma 2 9B IT
- Qwen2.5 7B Instruct
- Ministral 8B Instruct 2410

[![Open the training notebook in Google Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/RuurdKuiper/BYOD/blob/main/notebooks/train_diffusion.ipynb)

The notebook is the recommended starting point: select a model, choose a run
mode, and watch the training and validation losses update while training runs.
Its source is also available at
[`notebooks/train_diffusion.ipynb`](notebooks/train_diffusion.ipynb).

Try the converted models directly in the full-precision demos:
[Gemma](https://huggingface.co/spaces/Dovelove/byod-gemma-2-9b),
[Llama](https://huggingface.co/spaces/Dovelove/byod-llama-3.1-8b),
[Qwen](https://huggingface.co/spaces/Dovelove/byod-qwen2.5-7b), and
[Ministral](https://huggingface.co/spaces/Dovelove/byod-ministral-8b).

## Two run modes

| Mode | Purpose | Important settings |
|---|---|---|
| `quick` | Train the full recipe with a smaller backbone | 25,000 updates, rank-128 LoRA, smaller base model |
| `paper` | Reproduce the original reported conversion | 25,000 updates, rank-1024 LoRA, batch 16, no quantization |

Quick mode uses Llama 3.2 1B, Gemma 3 1B, or Qwen2.5 1.5B in full FP16.
There is no comparable official text-only ~1B Ministral checkpoint, so
Ministral is intentionally not offered in quick mode. The original Ministral
8B checkpoint remains available for paper reproduction.

| Family | Quick model | Paper reproduction |
|---|---|---|
| Llama | Llama 3.2 1B Instruct | Llama 3.1 8B Instruct |
| Gemma | Gemma 3 1B IT | Gemma 2 9B IT |
| Qwen | Qwen2.5 1.5B Instruct | Qwen2.5 7B Instruct |
| Ministral | — | Ministral 8B Instruct 2410 |

`paper` is the configuration used for the original `llama-3.1-8b-mask/best`
training and its Gemma, Qwen, and Ministral counterparts. It requires a
high-memory NVIDIA GPU; the original runs used one 96 GB GPU. `quick` is an
accessible full-length conversion, but it is not expected to reproduce the
paper scores because it changes both the backbone and adapter rank. All other
objective, data, validation, and optimization settings are retained; it uses
FP16 instead of BF16/FP8 for compatibility with common Colab GPUs.
Here, “quick” refers to the smaller memory requirement, not a shortened run.

## Local use

```bash
git clone https://github.com/RuurdKuiper/BYOD.git
cd BYOD
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[colab]'
cp .env.example .env  # then add a read-only Hugging Face token
```

Run the smaller-model configuration:

```bash
python train.py --model llama --mode quick
```

Run the paper configuration:

```bash
python train.py --model llama --mode paper
```

For quick mode, replace `llama` with `gemma` or `qwen`. Paper mode additionally
accepts `ministral`. Outputs contain the resolved configuration, metrics,
inference-ready checkpoints, and the adapter with the best validation loss
under `best/`.

To fold that adapter into a standalone model of the original base-model size:

```bash
python merge_adapter.py outputs/llama-3.1-8b-mask/best merged/llama-3.1-8b-mask
```

## What the paper configuration does

The source prompt remains visible and only response/EOS-padding positions are
eligible for masking. At every presentation of an example, an IID mask ratio
is sampled and a fresh corrupted response is constructed. Loss is calculated
only at corrupted answer and eligible padding positions. A rank-1024 LoRA is
trained on the query and value projections; base weights and normalization
layers remain frozen.

The exact common recipe is in [`configs/paper.yaml`](configs/paper.yaml), and
the four pinned model revisions are in
[`configs/models.yaml`](configs/models.yaml). The training dataset is pinned to
revision `6041513b684d6ca627879ffdb547b8629bb8b8de` of
[`Ruurd/LAD-training-1m-256`](https://huggingface.co/datasets/Ruurd/LAD-training-1m-256).
The saved configuration from the original Llama run is retained in
[`reference/`](reference/) for auditing.

Llama, Gemma, and Ministral are gated on Hugging Face. Accept their model
licenses and use a read-only token. Never commit that token.

## Reproducibility notes

- Dataset, tokenizer, and base-model revisions are pinned.
- Training data is shuffled deterministically with seed 42.
- Training corruption is resampled online; held-out corruption is deterministic.
- Every run writes `resolved_config.json`, `metrics.jsonl`, and test metrics.
- CUDA kernels and hardware can still introduce small numerical differences.

Run the lightweight repository checks with:

```bash
pip install -e '.[test]'
pytest -q
```
