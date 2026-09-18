# Abstract — quantitative working version

Masked diffusion language models permit parallel token updates and flexible generation orders, but leading systems require costly pretraining or continued full-model training. We ask whether diffusion generation can instead be added to existing instruction-tuned autoregressive models with one generic parameter-efficient recipe. LAD-Generic replaces causal attention with bidirectional attention and trains rank-1024 query/value LoRA adapters under a masked denoising objective, leaving 94.2–95.9% of parameters frozen. Applied without architecture-specific tuning to Gemma 2 9B, Llama 3.1 8B, Qwen2.5 7B, and Ministral 8B, each 25,000-update conversion sees 400,000 examples, or at most 102.4M token positions, and runs on one GPU in a Google Colab environment. On our preliminary nine-task evaluation, Gemma is the strongest converted model with 56.4% macro accuracy, compared with 55.1% for LLaDA 8B Instruct in the same harness. Continued Llama training from 25k to 50k updates does not improve the nine-task macro average (51.3% to 48.9%), but preliminarily improves the parallel decoding regime, where the number of denoising network evaluations (NFE) is smaller than the 128-token output length: 32-step generation perplexity falls from 30.05 to 16.80 and 64-step perplexity from 10.50 to 8.71. Across all four families, the converted models generate coherent answers from fully masked sequences, demonstrating an accessible alternative to diffusion pretraining from scratch.

## Evidence still needed before freezing the abstract

- Complete all autoregressive benchmark cells for Gemma, Llama, Qwen, and Ministral.
- Choose and report a single predeclared aggregation rule; current workbook values mix 50- and 250-example estimates.
- Add confidence intervals or repeated-seed uncertainty.
- Add measured conversion GPU-hours and inference latency/throughput; replace the token-position upper bound if exact counts become available.
- Confirm the exact dataset revision and category composition used by the original runs.
