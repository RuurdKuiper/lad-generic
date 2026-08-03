#!/usr/bin/env python
"""Launch the interactive denoising inference UI: python app.py"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import gradio as gr

from diffusion_lm.inference import denoise_stream, find_adapters, load_hosted_legacy_session, load_session, release_session

load_dotenv(Path(__file__).resolve().parent / ".env")
OUTPUTS_DIR = os.getenv("DIFFUSION_LM_OUTPUTS_DIR", "outputs")
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


def load_model(source, selection, device, quantization, repo_id, checkpoint_filename, tokenizer_name):
    """Release any previous model and load the user-selected inference adapter."""
    global SESSION
    if source == "Saved adapter" and not selection:
        return "No saved adapter found. Train until at least one validation step saves `outputs/<run>/best/`."
    release_session(SESSION)
    if source == "Saved adapter":
        SESSION = load_session(selection, OUTPUTS_DIR, device, quantization)
        model_name = SESSION.model.peft_config["default"].base_model_name_or_path
        return f"Loaded adapter `{selection}` on `{SESSION.device}` using `{SESSION.quantization}` inference with `{SESSION.compute_dtype}` compute from base model `{model_name}`."
    SESSION = load_hosted_legacy_session(repo_id, checkpoint_filename, tokenizer_name, device)
    return f"Loaded trusted hosted legacy checkpoint `{repo_id}/{checkpoint_filename}` on `{SESSION.device}` with `{SESSION.compute_dtype}` compute. It is using the current denoising loop."


def run(question, system_prompt, max_new_tokens, num_steps, noise_level, temperature, top_k, seed, permanent_unmask, confidence_guided, proportional_unmask):
    """Stream colored intermediate denoising states and the final answer to Gradio."""
    if SESSION is None:
        raise gr.Error("Choose and load a saved adapter first.")
    try:
        for step, (text, status, html) in enumerate(denoise_stream(SESSION, question, system_prompt, max_new_tokens, num_steps, noise_level, temperature, top_k, seed, permanent_unmask, confidence_guided, proportional_unmask), start=1):
            yield status, html
    except ValueError as error:
        raise gr.Error(str(error)) from error


choices = find_adapters(OUTPUTS_DIR)
with gr.Blocks(title="Diffusion LM inference") as demo:
    gr.Markdown("# Diffusion LM inference\nLoad a saved `best/` adapter from `outputs/`, then iteratively denoise an answer.")
    with gr.Row():
        source = gr.Dropdown(["Saved adapter", "Hugging Face legacy checkpoint"], value="Saved adapter", label="Model source")
        adapter = gr.Dropdown(choices=choices, value=choices[0] if choices else None, label="Saved adapter")
        device = gr.Dropdown(["auto", "mps", "cuda", "cpu"], value="auto", label="Device")
        quantization = gr.Dropdown(["auto", "4bit", "none"], value="auto", label="Inference quantization")
        refresh = gr.Button("Refresh models")
        load = gr.Button("Load model", variant="primary")
    with gr.Row():
        legacy_repo = gr.Textbox(value="ruurd/tini_model", label="Legacy Hugging Face repository")
        legacy_filename = gr.Textbox(value="diffusion-model-8B.pth", label="Legacy checkpoint filename")
        legacy_tokenizer = gr.Textbox(value="meta-llama/Llama-3.2-3B", label="Legacy tokenizer/base model")
    status = gr.Markdown("Choose a saved adapter and click **Load model**.")
    question = gr.Textbox(label="Question", lines=4, value="What do you know about Amsterdam?")
    system_prompt = gr.Textbox(label="System prompt", value="You are a helpful assistant.")
    with gr.Row():
        max_new_tokens = gr.Slider(1, 512, value=128, step=1, label="Answer tokens")
        num_steps = gr.Slider(1, 128, value=32, step=1, label="Denoising steps")
        noise_level = gr.Slider(0, 1, value=.5, step=.05, label="Initial re-mask probability")
        temperature = gr.Slider(.1, 2, value=.7, step=.05, label="Temperature")
        top_k = gr.Slider(1, 100, value=20, step=1, label="Top-k")
        seed = gr.Number(value=42, precision=0, label="Seed")
    with gr.Row():
        permanent_unmask = gr.Checkbox(label="Permanently retain selected tokens", value=False)
        confidence_guided = gr.Checkbox(label="Use confidence-guided retention", value=False)
        proportional_unmask = gr.Checkbox(label="Proportional unmasking", value=True)
    generate = gr.Button("Denoise", variant="primary")
    detail = gr.Markdown()
    intermediate = gr.HTML(label="Intermediate denoising states")
    refresh.click(refresh_models, outputs=adapter)
    load.click(load_model, inputs=[source, adapter, device, quantization, legacy_repo, legacy_filename, legacy_tokenizer], outputs=status)
    generate.click(run, inputs=[question, system_prompt, max_new_tokens, num_steps, noise_level, temperature, top_k, seed, permanent_unmask, confidence_guided, proportional_unmask], outputs=[detail, intermediate])


if __name__ == "__main__":
    demo.launch(share=_gradio_share_enabled())
