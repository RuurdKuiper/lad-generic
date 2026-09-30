"""Shared full-precision ZeroGPU demo for the four BYOD models."""
from __future__ import annotations

import json
import os
import secrets
import sys
import time
from pathlib import Path

import gradio as gr
import spaces

sys.path.insert(0, str(Path(__file__).parent / "src"))

from diffusion_lm.inference import denoise_stream, load_hub_adapter_session


SPACE = json.loads((Path(__file__).parent / "space_model.json").read_text())
MODEL_REPO_ID = os.getenv("MODEL_REPO_ID", SPACE["model_repo_id"])
DISPLAY_NAME = SPACE["display_name"]
SHOW_REPOSITORY_LINKS = bool(SPACE.get("show_repository_links", True))
SOURCE_URL = SPACE.get("source_url")

# ZeroGPU recommends constructing and placing the root module on CUDA at module
# scope. No quantization is used: all four demos run with the saved BF16 setup.
print(f"Loading {MODEL_REPO_ID} in full precision...")
SESSION = load_hub_adapter_session(
    MODEL_REPO_ID,
    device_name="cuda",
    quantization="none",
    # A forward pass is only valid after @spaces.GPU has allocated hardware.
    preflight=False,
)
print(f"Loaded {DISPLAY_NAME} ({SESSION.compute_dtype}, unquantized).")


def _duration(*args) -> int:
    """Reserve enough GPU time for the requested number of denoising steps."""
    try:
        steps = int(args[3])
        pause_per_step = float(args[7])
        remasking_strategy = str(args[9])
        ar_check_interval = max(1, int(args[11]))
    except (IndexError, TypeError, ValueError):
        steps = 64
        pause_per_step = 0.0
        remasking_strategy = "Confidence-guided"
        ar_check_interval = 1
    seconds_per_step = 2.0 + (2.0 / ar_check_interval if remasking_strategy == "Autoregressive-confidence" else 0.0)
    return min(300, max(30, round(steps * (seconds_per_step + pause_per_step))))


@spaces.GPU(size="large", duration=_duration)
def generate(
    question: str,
    system_prompt: str,
    max_new_tokens: int,
    num_steps: int,
    block_length: int,
    temperature: float,
    top_k: int,
    pause_per_step: float,
    trajectory_color_mode: str,
    remasking_strategy: str,
    revisable_tokens: bool,
    ar_check_interval: int,
    delay_eos_eot: bool,
    early_stopping: bool,
):
    """Stream iterative masked-diffusion generation from the fixed model."""
    question = question.strip() or "What do you know about Amsterdam?"
    block_length = min(int(block_length), int(max_new_tokens))
    seed = secrets.randbelow(2**63 - 1)
    first_step = True
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
        permanent_unmask=not bool(revisable_tokens),
        confidence_guided=remasking_strategy == "Confidence-guided",
        proportional_unmask=False,
        early_stopping=bool(early_stopping),
        # This delays retention of predicted endings; it does not alter their
        # sampling probability. Keep it optional so answers can end naturally.
        confidence_eos_eot_inf=bool(delay_eos_eot),
        freeze_retained_tokens=True,
        repetition_penalty=1.0,
        eos_eot_prediction_penalty=1.0,
        include_pre_remask_prediction=False,
        block_length=block_length,
        trajectory_color_mode=trajectory_color_mode,
        autoregressive_guided=remasking_strategy == "Autoregressive-confidence",
        revisable_tokens=bool(revisable_tokens),
        autoregressive_check_interval=int(ar_check_interval),
    ):
        if not first_step and float(pause_per_step) > 0:
            # The sleep occurs inside this one decorated generator invocation,
            # so ZeroGPU remains allocated for the entire denoising run.
            time.sleep(float(pause_per_step))
        first_step = False
        yield status, trajectory_html


def show_loading():
    """Immediately acknowledge a request while ZeroGPU prepares generation."""
    return (
        "⏳ Requesting a GPU and loading the model…",
        "<div style='font-family:system-ui;padding:14px;border:1px solid #d1d5db;"
        "border-radius:9px;background:#fafafa;color:#4b5563'>"
        "Preparing generation… The first request may take a little longer while "
        "the model is loaded.</div>",
    )


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
            status = gr.Markdown("Ready")
            trajectory = gr.HTML(label="Live denoising")
        with gr.Column(scale=2):
            system_prompt = gr.Textbox(
                label="System prompt",
                value="You are a helpful assistant.",
                lines=2,
            )
            max_new_tokens = gr.Slider(16, 512, value=64, step=16, label="New tokens")
            num_steps = gr.Slider(1, 512, value=64, step=1, label="Denoising steps")
            block_length = gr.Slider(16, 512, value=64, step=16, label="Block length")
            temperature = gr.Slider(0.0, 2.0, value=0.7, step=0.05, label="Temperature")
            top_k = gr.Slider(1, 100, value=3, step=1, label="Top-k")
            pause_per_step = gr.Slider(
                0.0,
                1.0,
                value=0.0,
                step=0.05,
                label="Pause between denoising steps (seconds)",
                info="Slows the visualization while keeping one GPU allocation for the full run.",
            )
            trajectory_color_mode = gr.Radio(
                choices=["No coloring", "Prediction probability", "Prediction iteration"],
                value="Prediction iteration",
                label="Token coloring",
                info="Hover over any token to see its position, prediction iteration, and probability.",
            )
            remasking_strategy = gr.Radio(
                choices=["Confidence-guided", "Autoregressive-confidence", "Random"],
                value="Confidence-guided",
                label="Remasking strategy",
                info="Rank tokens with diffusion confidence, the original causal model, or random selection.",
            )
            revisable_tokens = gr.Checkbox(
                value=False,
                label="Allow revising retained tokens",
                info="When enabled, previously visible tokens can be re-masked on later iterations.",
                interactive=False,
            )
            ar_check_interval = gr.Slider(
                1,
                16,
                value=4,
                step=1,
                label="AR check interval",
                info="Use the original causal model every N denoising steps; diffusion confidence is used between checks.",
                interactive=False,
            )
            delay_eos_eot = gr.Checkbox(
                value=True,
                label="Delay EOS/EOT retention (longer answers)",
                info="Preferentially re-masks predicted endings; it does not lower their prediction probability.",
            )
            early_stopping = gr.Checkbox(
                value=True,
                label="Early stopping",
                info="Stop after the visible answer is unchanged for two consecutive iterations.",
            )
    footer = "The first request may take longer while the base model and adapter are loaded."
    if SHOW_REPOSITORY_LINKS:
        footer += f" [Model card](https://huggingface.co/{MODEL_REPO_ID})"
        if SOURCE_URL:
            footer += f" · [Source code]({SOURCE_URL})"
    gr.Markdown(footer)

    inputs = [
        question,
        system_prompt,
        max_new_tokens,
        num_steps,
        block_length,
        temperature,
        top_k,
        pause_per_step,
        trajectory_color_mode,
        remasking_strategy,
        revisable_tokens,
        ar_check_interval,
        delay_eos_eot,
        early_stopping,
    ]
    def update_ar_controls(strategy):
        """Expose AR-only controls and clear revision when another strategy is selected."""
        enabled = strategy == "Autoregressive-confidence"
        return gr.update(interactive=enabled, value=False), gr.update(interactive=enabled)

    remasking_strategy.change(
        update_ar_controls,
        inputs=[remasking_strategy],
        outputs=[revisable_tokens, ar_check_interval],
        queue=False,
    )
    run_event = run.click(show_loading, outputs=[status, trajectory], queue=False)
    run_event.then(generate, inputs=inputs, outputs=[status, trajectory])
    submit_event = question.submit(show_loading, outputs=[status, trajectory], queue=False)
    submit_event.then(generate, inputs=inputs, outputs=[status, trajectory])

demo.queue(default_concurrency_limit=1).launch(ssr_mode=False)
