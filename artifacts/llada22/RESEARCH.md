# LLaDA2.2-mini adaptation notes (2026-10-27)

Sources reviewed before implementation:

- Model card: https://huggingface.co/inclusionAI/LLaDA2.2-mini
- Model/code pin: `e4f77d25ab5ca86f2223c6cdc6a72b887e20c8a5`
- Native implementation: https://huggingface.co/inclusionAI/LLaDA2.2-mini/blob/e4f77d25ab5ca86f2223c6cdc6a72b887e20c8a5/modeling_llada2_moe.py
- Configuration: https://huggingface.co/inclusionAI/LLaDA2.2-mini/blob/e4f77d25ab5ca86f2223c6cdc6a72b887e20c8a5/config.json
- Technical report, especially section 3.1: https://github.com/inclusionAI/LLaDA2.X/blob/main/LLaDA2_2_tech_report.pdf
- Existing Space source at `5f399f6c9ef9212d7dfeae6d4dcff311dc57581d`:
  https://huggingface.co/spaces/Ruurd/llada-8b-instruct

Key decisions and semantic differences are documented in
`huggingface/llada22_space/README.md`. In particular, insertion is before the
previous token; edits are padded/truncated inside fixed-size blocks, rather
than changing the total generation tensor length. Native model.generate
returns only answer tokens. Its attention blocks align to the whole prompt
plus answer, so the first generated block can include an immutable prompt
prefix. Editing/refinement can take more forwards than the steps argument.

The new tokenizer is not the original LLaDA tokenizer. User explicitly requested
new BG + TG scorer training, using the existing response and pinned raw-text
corpora with new tokenization. Model weights are not fine-tuned.

Architecture validation caught an additional restriction: the MoE block router
requires sequence lengths divisible by config.block_size=32. The app therefore
accepts generation block lengths 32 and 64, both tested using the actual model
class with a tiny synthetic 2-layer MoE under Transformers 5.2.0 / SDPA. Merely
testing the standalone decoder methods would not reveal this constraint.
