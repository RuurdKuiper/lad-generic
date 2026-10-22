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

Choose **PMI Viterbi** under **Decoding strategy** to jointly select the answer
tokens from the diffusion logits. Selecting it sets temperature 2 and top-k /
candidates 16. Weight is fixed at 0.5, minimum pair count is 1, and PMI is clipped
to ±2. Expert defaults are editable near the top of `app.py`. The existing
**Sampling** mode remains the default; selecting it restores temperature 1 and
top-k 3. Top-p applies only to sampling.

**PMI Viterbi + Repetition Penalty** adds an expected-count penalty to
the decoder's transitions. Its strength γ defaults to 1.0; γ=0
matches **PMI Viterbi** exactly. For each adjacent candidate pair, use the
original full-vocabulary probabilities to compute `q = p(a) * p(b)`. Subtract
`γ * C(a,b)` from that candidate pair's transition score, then add q to the
cumulative expected count C. The current q does not scale the penalty. Counts are updated
only after all penalties at that edge are computed. They start empty for each
iteration/block and exclude prompt-boundary transitions. The PMI component and
the diffusion probabilities used for confidence-guided noising stay unchanged.
Pairs containing EOS or end-of-turn tokens are excluded from both the repetition
penalty and cumulative counts, so repeated ending tokens remain unpenalized.
The combined edge score is `0.5 * temperature * PMI(a,b) - γ * C(a,b)`.
Diffusion unary scores are unchanged. At temperature zero, the new option still
applies its repetition penalty while ignoring PMI transitions.

Viterbi adds no model forward passes. All answer positions remain editable,
including tokens excluded from re-noising by **Use permanent unmasking**. That
option controls masking, rather than preventing direct token corrections.
Temperature changes the balance between diffusion logits and PMI; Viterbi
selection itself is deterministic. Confidence-guided noising uses selected
tokens' full-vocabulary diffusion probabilities after the existing EOS bias.

The sparse scorer is the BYOD-Llama scorer, trained on 980,000 training responses.
Its token-ID fingerprint matches this Space's Llama tokenizer exactly. The
checkpoint is loaded once and tokenizer-validated; original model weights,
prompt formatting, re-noising schedules, and three-iteration convergence check
are retained. The existing generation-length control continues to adjust EOS.

Paper: [LAD: LoRA-Adapted Diffusion](https://aclanthology.org/2025.emnlp-demos.8/).
