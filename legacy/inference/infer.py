import torch
import torch.nn.functional as F
import numpy as np
import time
import random
import importlib
import torch.nn as nn
import os
from IPython.display import display, HTML, Markdown, clear_output

from transformers import AutoTokenizer

rng = np.random.default_rng()

def disable_dropout(model):
    for name, module in model.named_modules():
        if isinstance(module, nn.Dropout):
            setattr(model, name, nn.Identity())  # Replace Dropout with Identity
    return model

def load_trained_model(checkpoint_path: str, base_model_name: str = "meta-llama/Llama-3.2-3B"):
    # Load tokenizer + config from saved dir
    hf_token = os.getenv("HF_TOKEN")

    tokenizer = AutoTokenizer.from_pretrained(base_model_name, 
    use_fast=True, 
    token=hf_token, 
    torch_dtype=torch.float32)

    # Step 5: Load the model safely
    model = torch.load(checkpoint_path, map_location=torch.device('cpu'), weights_only=False)

    # Disable dropout
    model = disable_dropout(model)

    print("✅ Model successfully loaded from checkpoint:", checkpoint_path)

    # Move to correct device
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available()  else "cpu"
    # model = model.to(torch.float32)
    model.to(device)
    model.eval()

    return model, tokenizer

def filter_logits(logits, top_k=0, top_p=1.0, temperature=1.0):
    """
    Vectorized top-k and/or top-p (nucleus) filtering with temperature scaling.
    Accepts logits of shape (seq_len, vocab_size) or (1, seq_len, vocab_size),
    and returns logits in the same shape.
    """
    original_shape = logits.shape
    if logits.dim() == 3:
        logits = logits.squeeze(0)  # shape: (seq_len, vocab_size)

    logits = logits.clone()

    # --- Temperature scaling ---
    if temperature != 1.0:
        logits = logits / temperature

    # --- Top-k filtering ---
    if top_k > 0 and top_k < logits.size(-1):
        topk_vals, _ = torch.topk(logits, top_k, dim=-1)
        thresholds = topk_vals[:, -1].unsqueeze(-1)
        logits = torch.where(logits < thresholds, torch.full_like(logits, float("-inf")), logits)

    # --- Top-p filtering ---
    if top_p > 0.0 and top_p < 1.0:
        sorted_logits, sorted_indices = torch.sort(logits, descending=True, dim=-1)
        probs = torch.softmax(sorted_logits, dim=-1)
        cum_probs = probs.cumsum(dim=-1)

        mask = cum_probs > top_p
        mask[:, 0] = False  # always keep top token

        scatter_mask = torch.zeros_like(logits, dtype=torch.bool).scatter(dim=-1, index=sorted_indices, src=mask)
        logits = torch.where(scatter_mask, torch.full_like(logits, float("-inf")), logits)

    # Restore original shape
    if original_shape[0] == 1:
        logits = logits.unsqueeze(0)

    return logits

# --- Utility Functions ---
def decode_tokens_safe(token_ids, tokenizer):
    return tokenizer.decode(token_ids, skip_special_tokens=True).replace("\n", " ")

def find_answer_start(input_ids, marker_ids):
    for i in range(len(input_ids) - len(marker_ids) + 1):
        if input_ids[i:i + len(marker_ids)] == marker_ids:
            return i + len(marker_ids)
    return None

def get_noising_schedule(i, max_it, sharpness=5.0):
    x = i / max_it
    return (np.exp(-sharpness * x) - np.exp(-sharpness)) / (1 - np.exp(-sharpness))

def noisify_answer(input_ids, answer_start, tokenizer, threshold=1.0, clustering=0, noise_start = 1.0):
    noised = input_ids.copy()
    answer_len = len(noised) - answer_start
    num_to_noise = int(threshold * answer_len * noise_start)
    mask_token_id = tokenizer.encode('MASK', add_special_tokens = False)[0]

    if num_to_noise == 0:
        return noised, []

    num_clusters = max(1, int((1 - clustering) * num_to_noise))
    cluster_size = max(1, int(num_to_noise / num_clusters))

    noised_indices = set()
    for _ in range(num_clusters):
        center = rng.integers(answer_start, len(noised))
        span_start = max(answer_start, center - cluster_size // 2)
        span_end = min(len(noised), span_start + cluster_size)
        noised_indices.update(range(span_start, span_end))

    noised_indices = sorted(list(noised_indices))[:num_to_noise]

    for idx in noised_indices:
        noised[idx] = mask_token_id

    return noised, noised_indices

import torch.nn.functional as F

def noisify_answer_without_remasking(input_ids, answer_start, tokenizer, threshold=1.0, noise_start=1.0, unmasked_mask=None):
    noised = input_ids.copy()
    mask_token_id = tokenizer.encode('MASK', add_special_tokens=False)[0]

    eligible_indices = list(range(answer_start, len(noised)))

    if unmasked_mask is not None:
        eligible_indices = [i for i in eligible_indices if not unmasked_mask[i]]

    answer_len = len(noised) - answer_start
    num_to_noise = int(threshold * answer_len * noise_start)
    
    if num_to_noise == 0 or len(eligible_indices) == 0:
        return noised, []

    selected = rng.choice(eligible_indices, size=num_to_noise, replace=False).tolist()

    for idx in selected:
        noised[idx] = mask_token_id

    return noised, selected

def confidence_guided_noising(input_ids, answer_start, tokenizer, confidences, noise_clipping, threshold=1.0, noise_start=1.0, unmasked_mask=None):
    noised = input_ids.copy()
    answer_len = len(input_ids) - answer_start
    num_to_noise = int(threshold * answer_len * noise_start)
    mask_token_id = tokenizer.encode('MASK', add_special_tokens=False)[0]
    eos_token_id = tokenizer.eos_token_id
    if num_to_noise == 0:
        return noised, []

    all_indices = np.arange(answer_start, len(input_ids))

    if unmasked_mask is not None:
        all_indices = [i for i in all_indices if not unmasked_mask[i]]

    eos_indices = [i for i in all_indices if input_ids[i] == eos_token_id]
    non_eos_indices = [i for i in all_indices if input_ids[i] != eos_token_id]

    # Proportionally split how many to noise
    num_non_eos_to_noise = int(num_to_noise * len(non_eos_indices) / (len(non_eos_indices) + len(eos_indices) + 1e-5))
    num_eos_to_noise = num_to_noise - num_non_eos_to_noise

    noised_indices = []

    # --- Non-EOS ---
    if non_eos_indices:
        raw_weights = 1.0 - np.array([confidences[i - answer_start] for i in non_eos_indices])
        raw_weights = np.clip(raw_weights, a_min=noise_clipping, a_max=None)
        weights = raw_weights / raw_weights.sum()

        chosen = rng.choice(non_eos_indices, size=min(num_non_eos_to_noise, len(non_eos_indices)), replace=False, p=weights)
        noised_indices.extend(chosen.tolist())

    # --- EOS ---
    if eos_indices and num_eos_to_noise > 0:
        raw_weights = 1.0 - np.array([confidences[i - answer_start] for i in eos_indices])
        raw_weights = np.clip(raw_weights, a_min=noise_clipping, a_max=None)
        weights = raw_weights / raw_weights.sum()

        chosen = rng.choice(eos_indices, size=min(num_eos_to_noise, len(eos_indices)), replace=False, p=weights)
        noised_indices.extend(chosen.tolist())

    for idx in noised_indices:
        noised[idx] = mask_token_id

    noised_indices = sorted(noised_indices)
    return noised, noised_indices

def generate_diffusion_text(model, input_ids, answer_start, top_k=0, top_p=1.0, temperature=1.0, 
                            eos_token_id=None, eos_boost=0.0):
    model.eval()
    with torch.no_grad(), torch.autocast(device_type='cuda', dtype=torch.bfloat16):
        input_tensor = torch.tensor([input_ids], dtype=torch.long).to(model.device)
        logits = model(input_ids=input_tensor)["logits"]  # (1, seq_len, vocab_size)

        # Optionally boost or suppress EOS token
        if eos_token_id is not None and eos_boost != 0.0:
            logits[:, :, eos_token_id] += eos_boost

        # Filter and sample
        filtered_logits = filter_logits(logits, top_k=top_k, top_p=top_p, temperature=temperature)
        probs = F.softmax(filtered_logits, dim=-1).squeeze()  # (seq_len, vocab_size)
        probs = torch.clamp(probs, min=1e-8, max=1.0)
        sampled = torch.multinomial(probs, num_samples=1).squeeze(-1)
        confidences = probs.gather(1, sampled.unsqueeze(-1)).squeeze(-1)

    return input_ids[:answer_start] + sampled[answer_start:].tolist(), confidences


def calculate_answer_perplexity(prompt, answer, model_name='gpt2-large'):
    from transformers import AutoTokenizer, AutoModelForCausalLM
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name).eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available()  else "cpu")
    model.to(device)

    full_input = prompt + answer
    enc = tokenizer(full_input, return_tensors="pt")
    input_ids = enc.input_ids.to(device)

    with torch.no_grad():
        labels = input_ids.clone()
        prompt_len = len(tokenizer(prompt, add_special_tokens=False)["input_ids"])
        labels[0, :prompt_len] = -100
        loss = model(input_ids, labels=labels).loss
        return torch.exp(loss).item()
    

def format_token_colored_inline(token_id, conf, tokenizer, mask_token_id=128000):
    token_str = tokenizer.decode([token_id]).replace("\n", "<br>")
    # token_str = token_str.replace(" ", "&nbsp;")  # Preserve spaces for inline display
    # token_str = token_str.replace("\t", "&nbsp;&nbsp;&nbsp;&nbsp;")  # Replace tabs with spaces
    
    if token_id == mask_token_id:
        color = "black"
    else:
        color = f"hsl({int(conf * 120)}, 100%, 25%)"
        
    return f"<span style='color:{color}' title='Conf: {conf:.2f}'>{token_str}</span>"


def display_diffusion_output(i, max_it, question, ori_input_tokens, generated_tokens, confidences, answer_start, tokenizer):
    clear_output(wait=True)
    display(Markdown(f"### Iteration {i}/{max_it-1}"))
    display(Markdown(f"**Question:** {tokenizer.decode(ori_input_tokens[:answer_start])}"))
    mask_token_id = tokenizer.encode('MASK', add_special_tokens=False)[0]

    output_html = ''.join([
        format_token_colored_inline(tok, conf, tokenizer, mask_token_id)
        for tok, conf in zip(generated_tokens[answer_start:], confidences[answer_start:])
        if tok != 128001  # skip EOT
    ])
    output_html = f"<div style='white-space: pre-wrap'>{output_html}</div>"

    html = HTML(f"<b>Diffusion Output with Confidence:</b><br><div style='line-height:1.8; white-space: pre-wrap'>{output_html}</div>")
    display(html)

    return output_html

def save_html_colored_output(filename, html_content):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: sans-serif; line-height: 1.6; }}
                span {{ padding: 0 2px; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """)


def generate_answer(question: str, model, tokenizer, max_it=16, noise_start=0.5, 
                    noising_sharpness=5.0, max_length=256, top_k=100, top_p=1.0, 
                    temperature=1.0, eos_token_id = None, eos_boost = 0.0) -> str:
    
    if eos_token_id is None:
        eos_token_id = tokenizer.eos_token_id
    # Format prompt with LLaMA 3 chat template
    prompt = (
        "<|begin_of_text|>\n"
        "<|start_header_id|>system<|end_header_id|>\n"
        "You are a helpful assistant.\n"
        "<|eot_id|>\n"
        "<|start_header_id|>user<|end_header_id|>\n"
        f"{question.strip()}\n"
        "<|start_header_id|>assistant<|end_header_id|>\n"
    )
    input_ids = tokenizer.encode(prompt, add_special_tokens=False)
    marker = tokenizer.encode("<|start_header_id|>assistant<|end_header_id|>\n", add_special_tokens=False)

    def find_answer_start(ids, marker):
        for i in range(len(ids) - len(marker) + 1):
            if ids[i:i+len(marker)] == marker:
                return i + len(marker)
        return None

    answer_start = find_answer_start(input_ids, marker)
    if answer_start is None:
        raise ValueError("Assistant marker not found in prompt.")

    # Pad to max length
    pad_token = tokenizer.eos_token_id
    mask_token = tokenizer.encode("MASK", add_special_tokens=False)[0]
    input_ids = input_ids[:max_length]
    if len(input_ids) < max_length:
        input_ids += [mask_token] * (max_length - len(input_ids))

    ori_tokens = input_ids
    current_tokens = noisify_answer(ori_tokens, answer_start, tokenizer, threshold=1.0)

    last_tokens = []
    for step in range(max_it):
        # Generate a new prediction
        current_tokens, confidence_scores = generate_diffusion_text(
            model, current_tokens, answer_start,
            top_k=top_k, top_p=top_p, temperature=temperature,
            eos_token_id=eos_token_id, eos_boost=eos_boost
        )

        # Display for debugging / tracking
        display_diffusion_output(
            step, max_it, question,
            ori_tokens, current_tokens, confidence_scores,
            answer_start, tokenizer
        )

        # Early stopping
        last_tokens.append(current_tokens)
        if len(last_tokens) > 4:
            last_tokens.pop(0)
            if all(t == last_tokens[0] for t in last_tokens):
                break

        # Re-apply noise for next iteration
        if step < max_it - 1:
            threshold = noise_start * get_noising_schedule(step, max_it, sharpness=noising_sharpness)
            current_tokens = noisify_answer(current_tokens, answer_start, tokenizer, threshold=threshold)

    return tokenizer.decode(current_tokens[answer_start:], skip_special_tokens=True).strip()
