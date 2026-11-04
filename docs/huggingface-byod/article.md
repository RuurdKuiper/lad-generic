# BYOD: Build your own diffusion language model in Google Colab

Can an existing instruction model learn to generate text through diffusion in a few hours on one GPU?

In [BYOD: Build Your Own DLM](https://arxiv.org/html/2610.41574v1), we convert **Gemma 2 9B, Llama 3.1 8B, Qwen2.5 7B, and Ministral 8B** into bidirectional masked-diffusion language models. Every pretrained weight stays frozen: training updates only LoRA adapters, representing **4.1–5.8% of the final model parameters**. The four primary conversions each took **3.1–4.0 hours on one GPU in Google Colab**.

We want other people to be able to train, inspect, and experiment with these models too. The training notebook and interactive demos are available now.

## Train your own model

**[Open the training notebook in Google Colab](https://colab.research.google.com/github/RuurdKuiper/BYOD/blob/main/notebooks/train_diffusion.ipynb)** · [Code and instructions](https://github.com/RuurdKuiper/BYOD)

The notebook takes you from selecting a model to trying your own trained adapter:

1. Choose a model and a training profile.
2. Use the provided tokenized training data, or configure your own instruction–response dataset.
3. Train while watching the loss curves, with optional Google Drive storage.
4. Open the interactive inference interface in **step 6** and watch your model denoise its answers. You can also load a saved interrupted run.

**Quick mode** uses smaller Llama, Gemma, or Qwen models and rank-128 LoRA for initial experiments. **Paper mode** uses the original 7B–9B models and rank-1024 adapters; our paper runs used a **96 GB NVIDIA RTX PRO 6000**. Quick mode does not reproduce the paper scores, and available Colab hardware determines which profile you can run.

## Try the models before training

These demos run directly in your browser:

| Model | Interactive demo |
| --- | --- |
| Gemma 2 9B | [Try BYOD-Gemma](https://huggingface.co/spaces/Ruurd/byod-gemma-2-9b) |
| Llama 3.1 8B | [Try BYOD-Llama](https://huggingface.co/spaces/Ruurd/byod-llama-3.1-8b) |
| Qwen2.5 7B | [Try BYOD-Qwen](https://huggingface.co/spaces/Ruurd/byod-qwen2.5-7b) |
| Ministral 8B | [Try BYOD-Ministral](https://huggingface.co/spaces/Ruurd/byod-ministral-8b) |

Instead of appending one token at a time, the model starts with a masked answer and fills multiple positions through successive denoising steps. Try the same prompt with different step budgets and watch where tokens appear.

![A BYOD-Gemma answer about Amsterdam, with retained tokens colored by their sampling probability.](https://arxiv.org/html/2610.41574v1/figures/demo_gemma_confidence_64steps_64tokens_probability.png)

*From Figure 7 of the paper: BYOD-Gemma generation at 64 denoising steps on a 64-token canvas. Greener tokens had higher sampling probability when retained.*

For related demos, try [our earlier LAD model](https://huggingface.co/spaces/Ruurd/lad), [LLaDA-8B-Instruct](https://huggingface.co/spaces/Ruurd/llada-8b-instruct), and [LLaDA2.2-mini](https://huggingface.co/spaces/Ruurd/llada2.2-mini). LLaDA2.2 is an additional demo, outside this paper’s evaluation. The hosted demos also include experimental decoding options beyond the paper’s evaluation settings.

## What did we find?

**The same conversion recipe works across all four families.** All four generate from fully masked answers and use information to the right of a masked position in our controlled attention test.

**BYOD-Gemma comes within 1.3 percentage points of LLaDA on our nine-task average:** 50.6% versus 51.9%, evaluated in the same harness. The unchanged AR parents still perform better on average, with particularly large conversion gaps in mathematics and code.

![Task accuracy radar plots comparing BYOD-Llama with LLaDA and its AR parent, and comparing the four BYOD conversions.](https://arxiv.org/html/2610.41574v1/benchmark_radar_panels.svg)

*Figure 1: Task-level accuracy in the matched evaluation. Performance depends on both the task and the converted model family.*

**Open-ended generation remains the main challenge.** At 64 denoising steps for 128 output tokens, externally scored perplexity is 8.3–11.1 for BYOD, versus 4.1 for LLaDA and 2.2–3.0 for the AR parents. Increasing the denoising budget generally helps, but a low-cost conversion still leaves a quality gap.

![External perplexity and token diversity across 32, 64, and 128 denoising evaluations, with AR-parent references.](https://arxiv.org/html/2610.41574v1/open_generation_budget.svg)

*Figure 3: Generation quality across inference budgets. Lower perplexity and higher Distinct-1 are better; crosses mark the AR parents.*

We hope BYOD makes diffusion-model experiments easier to start: change a backbone, try different training data, inspect a denoising trajectory, and see what improves.

**[Start with the Colab notebook](https://colab.research.google.com/github/RuurdKuiper/BYOD/blob/main/notebooks/train_diffusion.ipynb)** · [Read the paper](https://arxiv.org/html/2610.41574v1) · [Get the code](https://github.com/RuurdKuiper/BYOD)
