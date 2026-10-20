# Publishing the BYOD models and demos

This directory packages the selected checkpoints as Hugging Face adapter
repositories and creates one fixed-model ZeroGPU Space per model. Gemma, Qwen,
and Ministral use their original `best` checkpoints; Llama uses the final
checkpoint of its uninterrupted 50k-update run. Inference is BF16/unquantized;
no 4-bit fallback is configured.

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

To update only the demo code without re-uploading the model repositories:

```bash
python huggingface/publish_byod.py --spaces-only --execute
```

To replace only the Llama adapter without redeploying the Space:

```bash
python huggingface/publish_byod.py --namespace Dovelove --anonymous-review \
  --models-only --only BYOD-Llama-3.1-8B --execute
```

The four Spaces request the Hugging Face `zero-a10g` hardware tier (ZeroGPU).
Hugging Face currently permits two ZeroGPU Spaces for a free personal account
and up to ten for PRO. Existing ZeroGPU Spaces count toward the limit.

Gemma, Llama, and Ministral base weights may require authentication. Create a
separate read-only Hugging Face token and add it to each Space as the
`HF_TOKEN` secret in **Settings → Variables and secrets**. Do not put it in a
file, notebook, or Git commit.

### BYOD Viterbi decoding controls

The Ruurd and Dovelove BYOD Spaces use the same `temperature` and `top_k` inputs for
sampling and Viterbi. The hosted bigram weight is fixed at 0.5; the separate
`bigram_weight` and `bigram_top_k` API inputs have been removed.

For Viterbi, temperature scales diffusion emissions relative to bigrams:
`log_softmax(logits / temperature) + 0.5 * bigram_score`. Implementation uses
the equivalent, stable objective `log_softmax(logits) + 0.5 * temperature *
bigram_score`. Temperature 1 preserves the former weight-0.5 path selection;
0 ignores bigram scores and uses greedy predictions on the current logits.
Existing ending penalties and delayed retention still apply. Viterbi remains
deterministic. Its diffusion retention confidence uses full-vocabulary probabilities
from the selection logits (including any ending-delay adjustment); path margins use the stable objective's
score gaps. No extra model evaluations are required.

Top-k limits the candidate count for either strategy. Top-k 1 leaves only
the model argmax candidate at editable positions, so bigrams cannot change
the selected tokens. Retained tokens remain fixed constraints.

Hosted evaluation scripts now submit these shared controls. Historical result
folders retain their original manifests and source revisions; they describe
the earlier independent controls. `evaluate_decoding_quality.py` records the
control scheme and refuses to resume results with a different revision or
configuration. Its paper profile (temperature 0, top-k 1) now removes bigram
influence; use positive temperature and top-k greater than 1 to compare
Viterbi's transition methods.

Each interface defaults to PMI bigrams with diffusion-probability
retention, minimum bigram count 1, and clipping bound 2. Edit
`BIGRAM_SCORING_METHOD`, `BIGRAM_REMASKING_CONFIDENCE`, `PMI_MIN_COUNT`, and
`PMI_CLIP` near the top of `huggingface/byod_space/app.py` to change these
settings. Their interface controls are hidden; programmatic evaluation can
still override them. Ending-delay strength is fixed at the editable
`BIGRAM_ENDING_DELAY_STRENGTH = 10.0` default. Its control, checkpoint path,
seed, and decoding measurements are hidden from the interface; the API retains
evaluation overrides.

The shared controls default to temperature 2 and top-k 16, matching the
preferred configuration in the recent comparisons. Ending
suppression affects both path selection and diffusion retention probabilities.
The retention probabilities are normalized over the full vocabulary after
the fading ending penalty. An audit found that changing them to probabilities
before that penalty worsened the tested 16-step Amsterdam answers; the prior
calculation is retained.

The publisher includes a separate full-corpus scorer for each tokenizer:
`artifacts/bigram/gemma.pt`, `llama.pt`, `ministral.pt`, and `qwen.pt`.
Build each from `data/lad-training-1m-256-long` with `--text-column output
--response-eos`, its exact backbone tokenizer, and `--vocab-size` matching the
backbone output vocabulary. Qwen requires 152,064 output IDs, including padded
IDs beyond its tokenizer vocabulary. Missing per-model checkpoints stop
publication rather than reusing another model's statistics. Other namespaces
retain their existing interface without automatically bundling these scorers.

### Native LLaDA-Instruct comparison Space

`huggingface/publish_llada.py` prepares the same interface for the official
`GSAI-ML/LLaDA-8B-Instruct` model with its native bidirectional forward pass,
chat template, and mask ID 126336. It pins model/tokenizer revision
`08b83a6feb34df1a6011b80c3c00c7563e963b07` and Transformers 4.57.6. The native
loader can defer inference preflight until a GPU allocation is available.

Build the separate scorer from the full existing training split:

```bash
.venv/bin/python scripts/build_bigram.py \
  --tokenizer GSAI-ML/LLaDA-8B-Instruct --vocab-size 126464 \
  --saved-dataset data/lad-training-1m-256-long --text-column output \
  --response-eos --output artifacts/bigram/llada.pt
```

The output vocabulary includes 115 IDs beyond the tokenizer's 126,349 entries;
the scorer covers all 126,464 model outputs. The scorer uses response text
retokenized with LLaDA, preserving document boundaries and the training split.
Existing Gemma statistics cannot be reused.

Prepare the bundle with `python huggingface/publish_llada.py`; add `--execute`
to create the private `Ruurd/llada-8b-instruct` Space and request ZeroGPU.
Publication refuses to overwrite an existing repository. Public activation
of the corpus-derived scorer requires explicit user approval. The available
strategies are confidence-guided, random, and PMI Viterbi; autoregressive
adapter confidence applies to BYOD models. This publisher updates no existing
BYOD Spaces.
