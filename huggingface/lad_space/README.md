---
title: Lad
emoji: ⚡
colorFrom: pink
colorTo: red
sdk: gradio
sdk_version: 5.46.1
app_file: app.py
pinned: false
license: other
short_description: DLM
---

LAD is a LoRA-adapted diffusion model trained with masking and structural
corruption. Every answer position can be corrected at every iteration, including
when **Noise start fraction** is zero. Re-noising remains optional.

## Decoding

The interface offers **Sampling** and **BG + TG Viterbi (Gumbel)**. **Sampling**
is the default, with temperature **0.7** and top-k **16**. Optional BG+TG guidance
has bigram weight **1**.
It uses the same expanded, tokenizer-matched bigram/trigram scorers as BYOD-Llama.
Both files are pinned to an immutable revision in `ngram_assets.json` and fetched
at startup, outside GPU inference. No additional training or model forward passes
are required.

Temperature controls randomness independently of bigram weight. For BG+TG,
zero selects the best sequence deterministically; positive values add
`temperature * Gumbel(0,1)` to editable diffusion unary log-scores before the
shared fast Viterbi decoder. This is an approximate structured sampler, not the
exact sequence sampler. Sampling uses ordinary temperature scaling. Changing
methods preserves the selected temperature and candidate count. Top-p applies
only to Sampling.

**Bigram weight** ranges from 0 to 5. Weight 0 disables n-gram guidance; weight 1
gives equal diffusion and PMI bigram coefficients. The trigram correction has
relative weight 0.5. PMI uses minimum count 1 and clipping +/-2. Trigrams retain
counts >=2, including count two, and clip corrections to +/-2.

The expanded scorer corpus contains all 980,000 original response documents
plus 800M added Llama-tokenized tokens: 90% FineWeb-Edu, 5% Python-Edu and
5% FineMath. It totals 871,088,258 tokens. Counts never cross document boundaries.
The tokenizer fingerprint is checked against LAD's tokenizer; the paired scorers
also require matching vocabulary and training-token metadata.

## LAD controls

Noise fraction, noise decay, confidence-guided noising, permanent unmasking,
noise clipping, generation length/EOS bias, semi-autoregressive token addition,
context window, iteration count, pause and multi-turn controls remain available.
All answer positions stay editable, including tokens excluded from re-noising
by permanent unmasking. The prompt remains fixed and supplies left context.
Confidence-guided noising uses the selected token's full-vocabulary diffusion
probability after the existing EOS bias, without Gumbel perturbations or top-k
renormalization.

The model weights, prompt format, noising schedule and three-iteration
convergence check are unchanged. Previous PMI-only and repetition strategies
remain available through the existing programmatic arguments. To restore them
in the interface, set `SHOW_LEGACY_DECODING_CONTROLS = True` in `app.py`.

Paper: [LAD: LoRA-Adapted Diffusion](https://aclanthology.org/2025.emnlp-demos.8/).
