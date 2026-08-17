#!/usr/bin/env python
"""Launch the interactive denoising inference UI: python app.py"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import gradio as gr

from diffusion_lm.inference import denoise_stream, find_adapters, load_hosted_legacy_session, load_llada_session, load_local_legacy_session, load_session, release_session

load_dotenv(Path(__file__).resolve().parent / ".env")
OUTPUTS_DIR = os.getenv("DIFFUSION_LM_OUTPUTS_DIR", "outputs")
DEFAULT_LOCAL_LEGACY_CHECKPOINT = os.getenv(
    "DIFFUSION_LM_LEGACY_CHECKPOINT",
    str(Path(__file__).resolve().parent / "legacy/inference/diffusion-model-8B.pth"),
)
DEFAULT_LEGACY_CHECKPOINT_FILENAME = "diffusion-model-3B.pth"
DEFAULT_LLADA_REPOSITORY = "GSAI-ML/LLaDA-8B-Instruct"
SESSION = None


def _gradio_share_enabled() -> bool:
    """Use a reachable Gradio URL in Colab, with an explicit env override."""
    configured = os.getenv("DIFFUSION_LM_GRADIO_SHARE")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes", "on"}
    # These variables are inherited by `!python app.py` subprocesses in
    # Google Colab.  Ordinary local launches remain private by default.
    return bool(os.getenv("COLAB_RELEASE_TAG") or os.getenv("COLAB_GPU"))


def refresh_models():
    """Refresh the dropdown with loadable adapter directories under outputs/."""
    choices = find_adapters(OUTPUTS_DIR)
    return gr.Dropdown(choices=choices, value=choices[0] if choices else None)


def load_saved_adapter(selection, device, quantization):
    """Release any previous model and load a saved local/Drive LoRA adapter."""
    global SESSION
    if not selection:
        return "No saved adapter found. Train until at least one validation step saves `outputs/<run>/best/`."
    release_session(SESSION)
    SESSION = load_session(selection, OUTPUTS_DIR, device, quantization)
    model_name = SESSION.model.peft_config["default"].base_model_name_or_path
    return f"Loaded adapter `{selection}` on `{SESSION.device}` using `{SESSION.quantization}` inference with `{SESSION.compute_dtype}` compute from base model `{model_name}`."


def load_legacy_checkpoint(repo_id, checkpoint_filename, tokenizer_name, device):
    """Prefer the requested local legacy checkpoint, then use the trusted hosted copy."""
    global SESSION
    release_session(SESSION)
    configured_local_checkpoint = os.getenv("DIFFUSION_LM_LEGACY_CHECKPOINT")
    if configured_local_checkpoint:
        # An explicit environment setting is a full-path override.
        local_checkpoint = Path(configured_local_checkpoint).expanduser()
    else:
        # Otherwise, use the filename selected in the UI in the same directory
        # as the existing local 8B checkpoint.
        filename = (checkpoint_filename or DEFAULT_LEGACY_CHECKPOINT_FILENAME).strip()
        local_checkpoint = Path(DEFAULT_LOCAL_LEGACY_CHECKPOINT).expanduser().parent / filename
    if local_checkpoint.is_file():
        SESSION = load_local_legacy_session(local_checkpoint, tokenizer_name, device)
        source = f"local file `{SESSION.adapter_path}` (no checkpoint download)"
    else:
        SESSION = load_hosted_legacy_session(repo_id, checkpoint_filename, tokenizer_name, device)
        source = f"Hugging Face `{repo_id}/{checkpoint_filename}`"
    return f"Loaded legacy checkpoint from {source} on `{SESSION.device}` with `{SESSION.compute_dtype}` compute. It is using the current denoising loop."


def load_llada_model(repo_id, device):
    """Load LLaDA Instruct for this app's standard denoising controls."""
    global SESSION
    release_session(SESSION)
    SESSION = load_llada_session(repo_id, device)
    return f"Loaded LLaDA `{repo_id}` on `{SESSION.device}` with `{SESSION.compute_dtype}` compute. Generation uses this app's standard denoising loop and controls."


def run(question, system_prompt, max_new_tokens, num_steps, noise_level, temperature, top_k, seed, permanent_unmask, confidence_guided, proportional_unmask, early_stopping, confidence_eos_eot_inf):
    """Stream colored intermediate denoising states and the final answer to Gradio."""
    if SESSION is None:
        raise gr.Error("Choose and load a saved adapter first.")
    try:
        for step, (text, status, html) in enumerate(denoise_stream(SESSION, question, system_prompt, max_new_tokens, num_steps, noise_level, temperature, top_k, seed, permanent_unmask, confidence_guided, proportional_unmask, early_stopping, confidence_eos_eot_inf), start=1):
            yield status, html
    except ValueError as error:
        raise gr.Error(str(error)) from error


choices = find_adapters(OUTPUTS_DIR)
with gr.Blocks(title="Diffusion LM inference") as demo:
    gr.Markdown("# Diffusion LM inference\nLoad a saved adapter, LLaDA, or a legacy checkpoint, then iteratively denoise an answer. The legacy loader prefers its local checkpoint and falls back to Hugging Face.")
    with gr.Row():
        gr.Markdown("### Saved adapter")
    with gr.Row():
        adapter = gr.Dropdown(choices=choices, value=choices[0] if choices else None, label="Saved adapter")
        adapter_device = gr.Dropdown(["auto", "mps", "cuda", "cpu"], value="auto", label="Device")
        adapter_quantization = gr.Dropdown(["auto", "4bit", "none"], value="auto", label="Inference quantization")
        refresh = gr.Button("Refresh models")
        load_adapter = gr.Button("Load saved adapter", variant="primary")
    with gr.Row():
        gr.Markdown("### Legacy checkpoint (local preferred, Hugging Face fallback)")
    with gr.Row():
        legacy_repo = gr.Textbox(value="ruurd/tini_model", label="Fallback Hugging Face repository")
        legacy_filename = gr.Textbox(value=DEFAULT_LEGACY_CHECKPOINT_FILENAME, label="Local/Hugging Face checkpoint filename")
        legacy_tokenizer = gr.Textbox(value="meta-llama/Llama-3.2-3B", label="Legacy tokenizer/base model")
        legacy_device = gr.Dropdown(["auto", "mps", "cuda", "cpu"], value="auto", label="Device")
        load_legacy = gr.Button("Load legacy checkpoint", variant="primary")
    with gr.Row():
        gr.Markdown("### Official LLaDA Instruct (CUDA preferred; MPS experimental; app denoising loop)")
    with gr.Row():
        llada_repo = gr.Textbox(value=DEFAULT_LLADA_REPOSITORY, label="LLaDA Hugging Face repository")
        llada_device = gr.Dropdown(["auto", "cuda", "mps"], value="auto", label="Device")
        load_llada = gr.Button("Load LLaDA", variant="primary")
    status = gr.Markdown("Choose a saved adapter and click **Load model**.")
    question = gr.Textbox(label="Question", lines=4, value="What do you know about Amsterdam?")
    system_prompt = gr.Textbox(label="System prompt", value="You are a helpful assistant.")
    with gr.Row():
        max_new_tokens = gr.Slider(1, 512, value=128, step=1, label="Answer tokens")
        num_steps = gr.Slider(1, 128, value=32, step=1, label="Denoising steps")
        noise_level = gr.Slider(0, 1, value=.5, step=.05, label="Initial re-mask probability")
        temperature = gr.Slider(0, 2, value=.7, step=.05, label="Temperature")
        top_k = gr.Slider(1, 100, value=20, step=1, label="Top-k")
        seed = gr.Number(value=42, precision=0, label="Seed")
    with gr.Row():
        permanent_unmask = gr.Checkbox(label="Permanently retain selected tokens", value=False)
        confidence_guided = gr.Checkbox(label="Use confidence-guided retention", value=False)
        proportional_unmask = gr.Checkbox(label="Proportional unmasking", value=True)
        early_stopping = gr.Checkbox(label="Early stop after 3 identical predictions", value=False)
        confidence_eos_eot_inf = gr.Checkbox(label="Delay EOS/EOT using lowest confidence (LLaDA-style)", value=False)
    generate = gr.Button("Denoise", variant="primary")
    detail = gr.Markdown()
    intermediate = gr.HTML(label="Intermediate denoising states")
    refresh.click(refresh_models, outputs=adapter)
    load_adapter.click(load_saved_adapter, inputs=[adapter, adapter_device, adapter_quantization], outputs=status)
    load_legacy.click(load_legacy_checkpoint, inputs=[legacy_repo, legacy_filename, legacy_tokenizer, legacy_device], outputs=status)
    load_llada.click(load_llada_model, inputs=[llada_repo, llada_device], outputs=status)
    generate.click(run, inputs=[question, system_prompt, max_new_tokens, num_steps, noise_level, temperature, top_k, seed, permanent_unmask, confidence_guided, proportional_unmask, early_stopping, confidence_eos_eot_inf], outputs=[detail, intermediate])


if __name__ == "__main__":
    demo.launch(share=_gradio_share_enabled())
