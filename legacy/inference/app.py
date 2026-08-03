import gradio as gr
import torch
import numpy as np
import json
import time
from html import escape as html_escape
from transformers import AutoTokenizer
import os
import importlib
import os
from huggingface_hub import hf_hub_download

import spaces
from dotenv import load_dotenv
from infer import (
    load_trained_model,
    find_answer_start,
    get_noising_schedule,
    noisify_answer,
    filter_logits,
    confidence_guided_noising,
    noisify_answer_without_remasking
)
from models import CustomTransformerModel
from model_config import CustomTransformerConfig

# Load .env only when running locally
if os.getenv("HF_TOKEN") is None:
    load_dotenv()

hf_token = os.getenv("HF_TOKEN")

if hf_token is None:
    raise ValueError("HF_TOKEN is not set")

rng = np.random.default_rng()

def _generate_step(input_ids, top_p, top_k, eos_bias=0.0):
    """Single diffusion inference step. Must be called inside a @spaces.GPU context."""
    with torch.no_grad():
        input_tensor = torch.tensor([input_ids], dtype=torch.long).to(model.device)
        with torch.autocast(device_type=model.device.type, dtype=torch.float16):
            logits = model(input_ids=input_tensor)["logits"]

        # Apply eos_bias
        if eos_bias != 0.0:
            logits[0, :, eos_token_id] += eos_bias

        logits = filter_logits(logits, top_k=top_k, top_p=top_p)
        logits = logits.clamp(min=-1e8, max=1e4)
        probs = torch.nn.functional.softmax(logits, dim=-1)[0]
        probs = torch.clamp(probs, min=1e-8, max=1.0)
        assert torch.all(torch.isfinite(probs)), "Non-finite values in probs!"
        assert (probs >= 0).all(), "Negative probs!"
        sampled = torch.multinomial(probs, num_samples=1).squeeze(-1).tolist()

        # Extract confidence of selected tokens
        conf = probs[range(len(sampled)), sampled].cpu().numpy()
    return sampled, conf


@spaces.GPU
def run_diffusion_loop(input_ids, answer_start, max_it, pause_length, eos_bias,
                       sharpness, noise_start, use_confidence_noising,
                       use_permanent_unmasking, noise_clipping, top_p, top_k, added_tokens, context_window):
    """Full diffusion loop held inside a single GPU context to avoid repeated re-acquisition."""
    ori_input_tokens = input_ids[:]

    current_tokens, just_noised_indices = noisify_answer(
        input_ids, answer_start, tokenizer, threshold=1.0, noise_start=1.0
    )
    yield render_html("Iteration 0 (initial noise)",
                      highlight_tokens(current_tokens[answer_start:], answer_start, just_noised_indices, color="red")), None
    if pause_length > 0:
        time.sleep(pause_length)

    last_tokens = []
    prev_decoded = []
    unmasked_mask = [False] * len(current_tokens)
    current_tokens = current_tokens[:answer_start]

    for i in range(max_it):
        current_tokens = current_tokens + [mask_token_id] * added_tokens
        current_tokens = current_tokens[:context_window]
        generated_tokens, confidences = _generate_step(current_tokens, top_p, top_k, eos_bias=eos_bias)
        current_tokens = ori_input_tokens[:answer_start] + generated_tokens[answer_start:]

        new_decoded = tokenizer.convert_ids_to_tokens(current_tokens[answer_start:])
        diff_indices = {
            answer_start + j for j, tok in enumerate(new_decoded)
            if j >= len(prev_decoded) or tok != prev_decoded[j]
        }
        prev_decoded = new_decoded

        yield render_html(f"Iteration {i+1}/{max_it} (after generation)",
                          highlight_tokens(current_tokens[answer_start:], answer_start, diff_indices, color="green")), None
        if pause_length > 0:
            time.sleep(pause_length)

        last_tokens.append(current_tokens)
        if len(last_tokens) > 3:
            last_tokens.pop(0)
        if len(last_tokens) == 3 and last_tokens[0] == last_tokens[1] == last_tokens[2]:
            yield render_html("Stopped early", f"After {i+1} iterations."), None
            break

        if i < max_it - 1:
            threshold = get_noising_schedule(i, max_it, sharpness=sharpness)

            if use_confidence_noising:
                noised_answer, just_noised_indices = confidence_guided_noising(
                    current_tokens, answer_start, tokenizer, confidences, noise_clipping,
                    threshold=threshold, noise_start=noise_start, unmasked_mask=unmasked_mask if use_permanent_unmasking else None
                )
            elif use_permanent_unmasking:
                noised_answer, just_noised_indices = noisify_answer_without_remasking(
                    current_tokens, answer_start, tokenizer, threshold=threshold,
                    noise_start=noise_start, unmasked_mask=unmasked_mask
                )
            else:
                noised_answer, just_noised_indices = noisify_answer(
                    current_tokens, answer_start, tokenizer,
                    threshold=threshold, noise_start=noise_start
                )

            for idx in range(answer_start, len(current_tokens)):
                if noised_answer[idx] != mask_token_id:
                    unmasked_mask[idx] = True

            if use_permanent_unmasking:
                permanently_unmasked = {idx for idx in range(answer_start, len(current_tokens)) if unmasked_mask[idx]}
                yield render_html(f"Iteration {i+1}/{max_it} (after noising)",
                                  highlight_tokens(noised_answer[answer_start:], answer_start, permanently_unmasked, color="green")), None
            else:
                yield render_html(f"Iteration {i+1}/{max_it} (after noising)",
                                  highlight_tokens(noised_answer[answer_start:], answer_start, just_noised_indices, color="red")), None
            if pause_length > 0:
                time.sleep(pause_length)

            current_tokens = ori_input_tokens[:answer_start] + noised_answer[answer_start:]

    answer_ids = current_tokens[answer_start:]
    # Strip trailing EOS and MASK tokens before decoding
    while answer_ids and answer_ids[-1] in (eos_token_id, mask_token_id):
        answer_ids = answer_ids[:-1]
    try:
        final_ids = answer_ids[:answer_ids.index(eos_token_id)]
    except ValueError:
        final_ids = answer_ids

    final_output = tokenizer.decode(final_ids, skip_special_tokens=True).lstrip()
    yield render_html(f"Final Output ({len(final_ids)} tokens after {i+1} iterations)", final_output), final_output  # type: ignore

def format_chat_prompt(question):
    return (
        "<|begin_of_text|>\n"
        "<|start_header_id|>system<|end_header_id|>\n"
        "You are a helpful assistant.\n"
        "<|start_header_id|>user<|end_header_id|>\n"
        f"{question}\n"
        "<|start_header_id|>assistant<|end_header_id|>\n"
    )


def format_multiturn_prompt(history, question):
    parts = [
        "<|begin_of_text|>\n"
        "<|start_header_id|>system<|end_header_id|>\n"
        "You are a helpful assistant.\n"
    ]
    for q, a in history:
        parts.append(f"<|start_header_id|>user<|end_header_id|>\n{q}\n")
        parts.append(f"<|start_header_id|>assistant<|end_header_id|>\n{a}\n")
    parts.append(f"<|start_header_id|>user<|end_header_id|>\n{question}\n")
    parts.append("<|start_header_id|>assistant<|end_header_id|>\n")
    return "".join(parts)

def render_html(label, text):
    return f"<b>{label}</b><br><div style='white-space: pre-wrap; line-height:1.8'>{text.lstrip()}</div>"


def render_chat_history(history):
    if not history:
        return ""
    parts = []
    for q, a in history:
        parts.append(
            f'<div style="display:flex;justify-content:flex-end;margin:6px 0 6px 15%">'
            f'<div style="background:#0084ff;color:#fff;border-radius:18px 18px 4px 18px;'
            f'padding:10px 14px;word-wrap:break-word;white-space:pre-wrap;line-height:1.6">'
            f'{html_escape(q.strip())}</div></div>'
        )
        parts.append(
            f'<div style="display:flex;justify-content:flex-start;margin:6px 15% 6px 0">'
            f'<div style="background:#f0f0f0;color:#222;border-radius:18px 18px 18px 4px;'
            f'padding:10px 14px;word-wrap:break-word;white-space:pre-wrap;line-height:1.6">'
            f'{html_escape(a.strip())}</div></div>'
        )
    content = "".join(parts)
    return (
        f'<div id="chat-box" style="height:450px;overflow-y:auto;padding:12px;'
        f'background:#fff;border:1px solid #ddd;border-radius:8px">'
        f'{content}</div>'
        f'<script>(function(){{var c=document.getElementById("chat-box");if(c)c.scrollTop=c.scrollHeight;}})();</script>'
    )

def highlight_tokens(token_ids, answer_start, changed_indices, color):
    # Strip trailing EOS and MASK tokens so the tail is invisible
    end = len(token_ids)
    while end > 0 and token_ids[end - 1] in (eos_token_id, mask_token_id):
        end -= 1
    token_ids = token_ids[:end]
    tokens = tokenizer.convert_ids_to_tokens(token_ids)
    highlighted = []
    for j, tok in enumerate(tokens):
        tok_id = tokenizer.convert_tokens_to_ids(tok)
        if tok_id == eos_token_id:
            continue
        if tok_id == mask_token_id:
            highlighted.append('<span style="display:inline-block;background:#ccc;color:#666;border-radius:3px;padding:0 3px;font-size:0.8em;margin:0 1px;">mask</span>')
            continue
        tok_str = tokenizer.convert_tokens_to_string([tok])
        if (answer_start + j) in changed_indices:
            highlighted.append(f'<span style="color:{color}">{tok_str}</span>')
        else:
            highlighted.append(tok_str)
    return "".join(highlighted)

def on_generate(question, history, multiturn_on, max_it, pause_length, eos_bias,
                sharpness, noise_start, use_confidence_noising,
                use_permanent_unmasking, noise_clipping, top_p, top_k, added_tokens, context_window):

    eos_bias = -eos_bias
    q = question.strip() or "What do you know about the city of Amsterdam?"

    prompt = format_multiturn_prompt(history, q) if (multiturn_on and history) else format_chat_prompt(q)
    input_ids = tokenizer.encode(prompt, add_special_tokens=False)
    answer_start = find_answer_start(input_ids, assistant_marker_ids)
    if answer_start is None:
        yield history, render_html("Error", "Could not find Assistant marker in input.")
        return

    input_ids = (input_ids + [mask_token_id] * (context_window - len(input_ids)))[:context_window]

    history_html = render_chat_history(history) if multiturn_on and history else ""
    final_answer = None
    last_step_html = ""

    for step_html, final in run_diffusion_loop(
        input_ids, answer_start, max_it, pause_length, eos_bias,
        sharpness, noise_start, use_confidence_noising,
        use_permanent_unmasking, noise_clipping, top_p, top_k, added_tokens, context_window
    ):
        if final is not None:
            final_answer = final
        last_step_html = step_html
        yield history, history_html + step_html

    # Generation complete — update history and switch to chat view if multi-turn
    if multiturn_on and final_answer is not None:
        new_history = history + [(q, final_answer)]
        yield new_history, render_chat_history(new_history)
    else:
        yield history, last_step_html


def is_running_on_spaces():
    return os.getenv("SPACE_ID") is not None

print("Loading model...")

if is_running_on_spaces():
    # Load from Hugging Face Hub
    ckpt_path = hf_hub_download(
        repo_id="ruurd/tini_model",
        filename="diffusion-model-8B.pth",
        token=os.getenv("HF_TOKEN")
    )
else:
    # Load from local path
    ckpt_path = "diffusion-model-8B.pth"  # change to your actual local path

model, tokenizer = load_trained_model(checkpoint_path=ckpt_path)
print("✅ Model loaded.")

vocab_size = len(tokenizer)
eos_token_id = tokenizer.eos_token_id
mask_token_id = tokenizer.encode('MASK', add_special_tokens=False)[0]
assistant_marker_ids = tokenizer.encode("<|start_header_id|>assistant<|end_header_id|>", add_special_tokens=False)

with gr.Blocks(title="Diffusion Language Model Chat") as demo:
    chat_history_state = gr.State([])

    gr.Markdown("## Diffusion Language Model Chat")
    gr.Markdown("A diffusion-based language model that generates answers progressively.")

    with gr.Row():
        with gr.Column(scale=1):
            question_input = gr.Textbox(
                label="User Question", lines=2,
                placeholder="What do you know about the city of Amsterdam?"
            )
            with gr.Row():
                submit_btn = gr.Button("Generate", variant="primary")
                stop_btn   = gr.Button("Stop")
                clear_btn  = gr.Button("Clear Chat")
            multiturn_checkbox = gr.Checkbox(label="Multi-turn dialog", value=False)

            max_it_slider         = gr.Slider(1, 512, value=64,   step=1,    label="Number of iterations: ↑ = more iterations")
            pause_slider          = gr.Slider(0, 5,   value=0.01, step=0.01, label="Pause between iterations ↑ = longer pause")
            eos_bias_slider       = gr.Slider(-5.0, 5.0, value=0.0, step=0.1, label="Generation length: ↑ = more output tokens by decreasing eos token probability")
            sharpness_slider      = gr.Slider(1.0, 20.0, value=1.0, step=0.5, label="Noise decay sharpness: ↓ = more noise in later iterations")
            noise_start_slider    = gr.Slider(0.0, 1.0, value=0.5, step=0.05, label="Noise start fraction: ↑ = more noise")
            confidence_noising_cb = gr.Checkbox(value=False, label="Use confidence-guided noising")
            permanent_unmasking_cb= gr.Checkbox(value=False, label="Use permanent unmasking")
            noise_clipping_slider = gr.Slider(0.01, 1.0, value=0.01, step=0.01, label="Noise clipping: ↓ = more confidence guidance")
            topk_slider           = gr.Slider(1, 1000, value=3,   step=1,    label="Top-k: ↑ = more random answers")
            topp_slider           = gr.Slider(0.0, 1.0, value=1.0, step=0.01, label="Top-p: ↑ = more random answers")
            added_tokens_slider   = gr.Slider(1, 256, value=256,  step=1,    label="Semi-autoregressive generation: number of added tokens per iteration")
            context_window_slider = gr.Slider(128, 2048, value=256, step=1, label="Context window: ↑ = longer sequences")

        with gr.Column(scale=1):
            output_html = gr.HTML(label="Output")

    all_inputs = [
        question_input, chat_history_state, multiturn_checkbox,
        max_it_slider, pause_slider, eos_bias_slider, sharpness_slider,
        noise_start_slider, confidence_noising_cb, permanent_unmasking_cb,
        noise_clipping_slider, topp_slider, topk_slider, added_tokens_slider, context_window_slider,
    ]
    all_outputs = [chat_history_state, output_html]

    gen_event  = submit_btn.click(on_generate, inputs=all_inputs, outputs=all_outputs)
    sub_event  = question_input.submit(on_generate, inputs=all_inputs, outputs=all_outputs)
    stop_btn.click(fn=None, inputs=None, outputs=None, cancels=[gen_event, sub_event])

    def on_clear():
        return [], ""

    clear_btn.click(on_clear, inputs=[], outputs=[chat_history_state, output_html])

    def on_toggle(multiturn_on, history):
        return render_chat_history(history) if multiturn_on else ""

    multiturn_checkbox.change(
        on_toggle,
        inputs=[multiturn_checkbox, chat_history_state],
        outputs=[output_html]
    )

demo.launch(share=True, allowed_paths=["."], ssr_mode=False)



