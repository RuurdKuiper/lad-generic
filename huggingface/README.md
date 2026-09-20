# Publishing the BYOD models and demos

This directory packages the four original `best` checkpoints as public Hugging
Face adapter repositories and creates one fixed-model ZeroGPU Space per model.
Inference is BF16/unquantized; no 4-bit fallback is configured.

## Repositories

| Model repository | Space |
|---|---|
| `Ruurd/BYOD-Gemma-2-9B` | `Ruurd/byod-gemma-2-9b` |
| `Ruurd/BYOD-Llama-3.1-8B` | `Ruurd/byod-llama-3.1-8b` |
| `Ruurd/BYOD-Qwen2.5-7B` | `Ruurd/byod-qwen2.5-7b` |
| `Ruurd/BYOD-Ministral-8B` | `Ruurd/byod-ministral-8b` |

The model repositories contain only the trained adapters, tokenizer metadata,
normalization state, and resolved training configuration. Users must accept
the upstream terms for gated base models.

## Publish

Authenticate without putting a token in the repository:

```bash
hf auth login
```

Preview and validate all source files:

```bash
python huggingface/publish_byod.py
```

Create/update the public model repositories and Spaces:

```bash
python huggingface/publish_byod.py --execute
```

The four Spaces request the Hugging Face `zero-a10g` hardware tier (ZeroGPU).
Hugging Face currently permits two ZeroGPU Spaces for a free personal account
and up to ten for PRO. Existing ZeroGPU Spaces count toward the limit.

Gemma, Llama, and Ministral base weights may require authentication. Create a
separate read-only Hugging Face token and add it to each Space as the
`HF_TOKEN` secret in **Settings → Variables and secrets**. Do not put it in a
file, notebook, or Git commit.
