## BYOD: Train and try your own diffusion language model

We’re sharing **BYOD: Build Your Own DLM**, a recipe for converting existing instruction models into bidirectional masked-diffusion language models using only LoRA training.

Our Gemma 2 9B, Llama 3.1 8B, Qwen2.5 7B, and Ministral 8B conversions each took **3.1–4.0 hours on one Colab GPU**, with every pretrained weight frozen.

**Want to train one yourself? [Open our Google Colab notebook](https://colab.research.google.com/github/RuurdKuiper/BYOD/blob/main/notebooks/train_diffusion.ipynb).** Select a model, train while watching the loss curves, then open the live inference interface in step 6. You can use the provided data or configure your own instruction–response dataset. Quick mode offers smaller models for experiments; paper mode needs a high-memory GPU, and our runs used 96 GB. Quick mode does not reproduce the paper scores.

**Try the trained models in your browser:** [Gemma](https://huggingface.co/spaces/Ruurd/byod-gemma-2-9b) · [Llama](https://huggingface.co/spaces/Ruurd/byod-llama-3.1-8b) · [Qwen](https://huggingface.co/spaces/Ruurd/byod-qwen2.5-7b) · [Ministral](https://huggingface.co/spaces/Ruurd/byod-ministral-8b)

![BYOD-Gemma generation, colored by retained-token sampling probability.](https://arxiv.org/html/2610.41574v1/figures/demo_gemma_confidence_64steps_64tokens_probability.png)

*BYOD-Gemma at 64 denoising steps, from Figure 7. Try changing the step budget in the demos.*

BYOD-Gemma reaches **50.6%** average accuracy across nine tasks, compared with **51.9%** for LLaDA-8B-Instruct in the same harness. The AR parents remain stronger on average, and open-ended fluency is still a clear limitation.

![Task-level accuracy profiles for the matched Llama/LLaDA comparison and the four BYOD families.](https://arxiv.org/html/2610.41574v1/benchmark_radar_panels.svg)

*Figure 1: Matched benchmark results. The largest gaps with AR occur in mathematics and code.*

We hope the notebook and demos make it easier for others to explore diffusion training, new backbones, and better decoding.

[Paper](https://arxiv.org/html/2610.41574v1) · [Code](https://github.com/RuurdKuiper/BYOD) · **[Train in Colab](https://colab.research.google.com/github/RuurdKuiper/BYOD/blob/main/notebooks/train_diffusion.ipynb)**
