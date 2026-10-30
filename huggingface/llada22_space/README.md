---
title: LLaDA2.2-mini
emoji: 🌊
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 5.49.1
python_version: "3.12"
app_file: app.py
pinned: false
license: apache-2.0
startup_duration_timeout: 1h
short_description: Live diffusion with native edits and BG + TG guidance
models:
- inclusionAI/LLaDA2.2-mini
---

# LLaDA2.2-mini

A companion to [Ruurd/llada-8b-instruct](https://huggingface.co/spaces/Ruurd/llada-8b-instruct),
with the same two-column prompt, controls, live token colors, hover information,
and copyable plain-text output. Loads the 16B-total / 1.4B-active MoE in BF16,
unquantized, on a large ZeroGPU allocation. Active parameters do not determine
weight memory: all 16B weights must fit. Transformers 5.2.0 is isolated from the
original Space's Transformers 4 environment.

Model, remote code and tokenizer are pinned to
`e4f77d25ab5ca86f2223c6cdc6a72b887e20c8a5`. The native block decoder is called
directly, with observation wrappers for live snapshots. These wrappers are
restored on completion, exception or cancellation; inference is serialized.
The upstream decoder is not copied or replaced.

## Editing semantics

The [technical report, section 3.1](https://github.com/inclusionAI/LLaDA2.X/blob/main/LLaDA2_2_tech_report.pdf)
and [pinned implementation](https://huggingface.co/inclusionAI/LLaDA2.2-mini/blob/e4f77d25ab5ca86f2223c6cdc6a72b887e20c8a5/modeling_llada2_moe.py)
agree on the following rules:

- MASK = 156895; DELETE = 156930; INSERT (named SPLIT in code) = 156931;
  EOS = 156892.
- DELETE removes the current position and shifts the suffix left.
- INSERT replaces a position with `[MASK, previous token]`, inserting **before**
  the old token rather than replacing it with two new predictions.
- Every edit is block-local. Overflow is truncated at the right edge and
  shortfalls are padded with fresh masks. Generated output therefore has a
  fixed maximum length, even though intermediate positions move.
- Original-mask tracking follows edits. Fresh insertion/padding masks are
  distinguished from original masks for the post-mask refinement budget.
- Prompt tokens are protected, including prompts ending inside a block.
  User-supplied reserved mask/edit tokens are rejected.
- Confidence gates, token rewrites, anti-loop resampling, post-mask refinement,
  final-round edit suppression, attention masks and EOS handling stay native.

Visualization metadata follows the same shifts/truncation/padding. Inserted
masks start with no prediction history; the carried token retains its history.
Deleted and truncated token metadata disappears. Hover probabilities are from
the full, unfiltered model distribution. The output is only marked complete
when the native decoder returns without unresolved mask/edit tokens; timeout
or iteration-cap failures are surfaced explicitly.

## Decoding methods

**Confidence-guided** uses the official generation algorithm unchanged.
The [model card](https://huggingface.co/inclusionAI/LLaDA2.2-mini) recommends
block length 32, temperature 0, unmasking threshold 0.5 and editing threshold 0.
`steps` controls a per-block unmasking floor, not an exact total forward budget.
Actual iterations include native refinement (default up to 16 post-mask steps).

**BG + TG Viterbi (Gumbel)** adds the existing sparse PMI + trigram selector to
ordinary-token prediction spans. Edit and mask predictions from native sampling
are barriers: they are never rescored, selected from the n-gram vocabulary, or
connected by n-gram edges. Reserved controls are excluded from ordinary-token
candidate sets. The selected tokens' confidence is gathered from the original
full-vocabulary logits before the native confidence gates. Mask-to-token
selection uses the requested Gumbel noise scale; native token-to-token edits
use deterministic guided selection. Final edit suppression and anti-loop
resampling remain native. This guided mode is an experimental extension, not
the official benchmark sampler. It adds no model forwards.

Bigram weight is independent of temperature, PMI minimum count is 1 and clip is
±2. Trigram correction uses relative weight 0.5, minimum count 2, backoff alpha
50 and clip ±2. The new scorers use this model's exact tokenizer and full
157184-output vocabulary. No LLaDA-8B or BYOD counts are reused.

The scorer corpus includes all 980000 original training responses plus 800M
newly retokenized tokens: 720M FineWeb-Edu, 40M Python-Edu and 40M FineMath.
Source revisions, file lists, counts, tokenizer fingerprint and checkpoint
SHA256 hashes are recorded in the scorer repository's training report.
N-grams never cross document boundaries. Trigram storage keeps count >=2;
required prefix totals still include singleton contributions.

The original APD/frozen-retention and EOS-delay switches are replaced by native
confidence/editing/refinement controls. Freezing retained positions would
prevent the rewrites required for structural editing. Early stopping means
stopping after a completed block contains EOS. The app limits combined prompt
and answer to 4096 tokens to bound its dense attention allocation; the model's
128K context capability is not exposed by this interactive demo.

## Local preparation

From the project root, download the pinned tokenizer into
`artifacts/llada22/tokenizer` (including its Python helper and chat template),
then run:

```bash
.venv/bin/python scripts/build_llada22_ngrams.py
.venv/bin/python huggingface/publish_llada22.py
```

Building uses the cached corpus from the original expanded-scorer build.
`--sources ... --count-only` supports independent source counting; completed
source counts resume only with matching plans and tokenizer fingerprints.
Publication is separate and never overwrites the original Space.

Block length is restricted to 32 or 64: the model's MoE router asserts that
forward windows are divisible by its configured 32-token routing block size.
The UI defaults to BG + TG, weight 1 and Gumbel temperature 0.7 to match the
original Space. For the authors' recommended native baseline, select
Confidence-guided and set temperature to 0.
