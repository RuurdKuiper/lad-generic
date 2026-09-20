"""Shared full-precision ZeroGPU demo for the four BYOD models."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import gradio as gr
import spaces

sys.path.insert(0, str(Path(__file__).parent / "src"))

from diffusion_lm.inference import denoise_stream, load_hub_adapter_session


SPACE = json.loads((Path(__file__).parent / "space_model.json").read_text())
MODEL_REPO_ID = os.getenv("MODEL_REPO_ID", SPACE["model_repo_id"])
DISPLAY_NAME = SPACE["display_name"]

# ZeroGPU recommends constructing and placing the root module on CUDA at module
# scope. No quantization is used: all four demos run with the saved BF16 setup.
print(f"Loading {MODEL_REPO_ID} in full precision...")
SESSION = load_hub_adapter_session(
    MODEL_REPO_ID,
    device_name="cuda",
    quantization="none",
)
print(f"Loaded {DISPLAY_NAME} ({SESSION.compute_dtype}, unquantized).")


def _duration(*args) -> int:
    """Reserve enough GPU time for the requested number of denoising steps."""
    try:
        steps = int(args[3])
    except (IndexError, TypeError, ValueError):
        steps = 64
    return min(300, max(30, steps * 2))


@spaces.GPU(size="large", duration=_duration)
def generate(
    question: str,
    system_prompt: str,
    max_new_tokens: int,
    num_steps: int,
    block_length: int,
    temperature: float,
    top_k: int,
    seed: int,
    show_trajectory: bool,
):
    """Stream iterative masked-diffusion generation from the fixed model."""
    question = question.strip() or "What do you know about Amsterdam?"
    block_length = min(int(block_length), int(max_new_tokens))
    latest = ("", "Starting…", "")
    for text, status, trajectory_html in denoise_stream(
        SESSION,
        question=question,
        system_prompt=system_prompt,
        max_new_tokens=int(max_new_tokens),
        num_steps=int(num_steps),
        noise_level=1.0,
        temperature=float(temperature),
        top_k=int(top_k),
        seed=int(seed),
        permanent_unmask=True,
        confidence_guided=True,
        proportional_unmask=False,
        early_stopping=False,
        confidence_eos_eot_inf=True,
        freeze_retained_tokens=True,
        repetition_penalty=1.0,
        eos_eot_prediction_penalty=1.0,
        include_pre_remask_prediction=show_trajectory,
        block_length=block_length,
    ):
        latest = (text, status, trajectory_html if show_trajectory else "")
        yield latest


with gr.Blocks(title=f"{DISPLAY_NAME} · masked diffusion") as demo:
    gr.Markdown(
        f"# {DISPLAY_NAME}\n"
        "A full-precision masked-diffusion model converted from an "
        "autoregressive language model with LoRA. This demo uses the exact "
        "best training checkpoint and does **not** use 4-bit quantization."
    )
    with gr.Row():
        with gr.Column(scale=3):
            question = gr.Textbox(
                label="Prompt",
                value="What do you know about Amsterdam?",
                lines=4,
            )
            run = gr.Button("Generate", variant="primary")
            output = gr.Textbox(label="Current answer", lines=12)
            status = gr.Markdown("Ready")
        with gr.Column(scale=2):
            system_prompt = gr.Textbox(
                label="System prompt",
                value="You are a helpful assistant.",
                lines=2,
            )
            max_new_tokens = gr.Slider(16, 512, value=128, step=16, label="New tokens")
            num_steps = gr.Slider(1, 512, value=64, step=1, label="Denoising steps")
            block_length = gr.Slider(16, 512, value=128, step=16, label="Block length")
            temperature = gr.Slider(0.0, 2.0, value=0.7, step=0.05, label="Temperature")
            top_k = gr.Slider(1, 100, value=3, step=1, label="Top-k")
            seed = gr.Number(value=1234, precision=0, label="Seed")
            show_trajectory = gr.Checkbox(value=False, label="Show inference trajectory")
    trajectory = gr.HTML(label="Token trajectory", visible=True)
    gr.Markdown(
        "The first request may take longer while the base model and adapter are loaded. "
        f"[Model card](https://huggingface.co/{MODEL_REPO_ID}) · "
        "[Source code](https://github.com/RuurdKuiper/lad-generic)"
    )

    inputs = [
        question,
        system_prompt,
        max_new_tokens,
        num_steps,
        block_length,
        temperature,
        top_k,
        seed,
        show_trajectory,
    ]
    run.click(generate, inputs=inputs, outputs=[output, status, trajectory])
    question.submit(generate, inputs=inputs, outputs=[output, status, trajectory])

demo.queue(default_concurrency_limit=1).launch(ssr_mode=False)
