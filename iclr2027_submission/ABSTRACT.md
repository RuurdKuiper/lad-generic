# Abstract — quantitative working version

Diffusion language models (DLMs) permit parallel token updates and flexible generation orders, but leading systems rely on costly pretraining or continued full-model training. To our knowledge, we present the first systematic cross-architecture study of parameter-efficient AR-to-diffusion conversion. Build Your Own DLM (BYOD) exposes bidirectional attention and learns masked denoising through the same rank-1024 query/value LoRA intervention across Gemma 2 9B, Llama 3.1 8B, Qwen2.5 7B, and Ministral 8B, without architecture-specific tuning. The adapters comprise 4.1–5.8% of final parameters while every base-model parameter remains frozen; each 25,000-update conversion processes at most 102.4M token positions in 3.1–4.0 hours on one Google Colab GPU. All four models generate from fully masked sequences and retain substantial parent-model knowledge. BYOD-Gemma is the strongest BYOD conversion on our nine-task evaluation, reaching 50.6% average accuracy compared with 51.9% for LLaDA 8B Instruct in the same harness. Fluency remains the principal limitation: at 64 NFE, converted-model perplexity is 8.3–11.1 versus 4.1 for LLaDA and 2.2–3.0 for the AR parents, with generally lower Distinct-n scores as well. BYOD therefore establishes a practical, reproducible route for broad experimentation with diffusion generation while identifying the quality gap that efficient conversion must next close.

**Code:** [GitHub](https://github.com/RuurdKuiper/lad-generic) · **Live demos:** [Gemma](https://huggingface.co/spaces/Ruurd/byod-gemma-2-9b) · [Qwen](https://huggingface.co/spaces/Ruurd/byod-qwen2.5-7b) · [Ministral](https://huggingface.co/spaces/Ruurd/byod-ministral-8b) · [Llama](https://huggingface.co/spaces/Ruurd/byod-llama-3.1-8b)

## Evidence still needed before freezing the abstract

- Complete the remaining Ministral benchmark cells.
- Report uncertainty intervals for the completed benchmark evaluations.
- Add confidence intervals or repeated-seed uncertainty.
- Add measured conversion GPU-hours and inference latency/throughput; replace the token-position upper bound if exact counts become available.
- Confirm the exact dataset revision and category composition used by the original runs.
