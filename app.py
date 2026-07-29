#!/usr/bin/env python
"""Launch the interactive denoising inference UI: python app.py"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import gradio as gr

from diffusion_lm.inference import denoise_stream, find_adapters, load_session, release_session

load_dotenv(Path(__file__).resolve().parent / ".env")
OUTPUTS_DIR = os.getenv("DIFFUSION_LM_OUTPUTS_DIR", "outputs")
SESSION = None


def refresh_models():
    """Refresh the dropdown with loadable adapter directories under outputs/."""
    choices = find_adapters(OUTPUTS_DIR)
    return gr.Dropdown(choices=choices, value=choices[0] if choices else None)


def load_model(selection, device):
    """Release any previous model and load the user-selected inference adapter."""
    global SESSION
    if not selection:
        return "No saved adapter found. Train until at least one validation step saves `outputs/<run>/best/`."
    release_session(SESSION)
    SESSION = load_session(selection, OUTPUTS_DIR, device)
    return f"Loaded `{selection}` on `{SESSION.device}` from base model `{SESSION.model.peft_config['default'].base_model_name_or_path}`."


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
        adapter = gr.Dropdown(choices=choices, value=choices[0] if choices else None, label="Saved adapter")
        device = gr.Dropdown(["auto", "mps", "cuda", "cpu"], value="auto", label="Device")
        refresh = gr.Button("Refresh models")
        load = gr.Button("Load model", variant="primary")
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
    load.click(load_model, inputs=[adapter, device], outputs=status)
    generate.click(run, inputs=[question, system_prompt, max_new_tokens, num_steps, noise_level, temperature, top_k, seed, permanent_unmask, confidence_guided, proportional_unmask], outputs=[detail, intermediate])


if __name__ == "__main__":
    demo.launch()
