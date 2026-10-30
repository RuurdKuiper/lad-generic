"""LLaDA2.2-mini ZeroGPU Space, matching the Ruurd live-diffusion layout."""
from pathlib import Path
import hashlib
import json
import sys
import time

import gradio as gr
import spaces
import torch
from huggingface_hub import hf_hub_download
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).parent / "src"))
from diffusion_lm.bigram import BigramScorer, BigramViterbiSelector
from diffusion_lm.trigram import TrigramScorer
from streaming import MODEL_ID, MODEL_REVISION, MASK, DELETE, INSERT, NativeStreamer, render

BASE = Path(__file__).parent
torch.set_num_threads(4)
CONFIG = json.loads((BASE / "space_model.json").read_text())
TOKENIZER = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION, trust_remote_code=True)
MODEL = AutoModelForCausalLM.from_pretrained(
    MODEL_ID, revision=MODEL_REVISION, trust_remote_code=True,
    dtype=torch.bfloat16, attn_implementation="sdpa",
).eval().to("cuda")
STREAMER = NativeStreamer(MODEL)
def scorer_path(name):
    revision = CONFIG["ngram_scorer_revision"]
    if not revision:
        return BASE / name  # local bundle validation before publication
    path = Path(hf_hub_download(CONFIG["ngram_scorer_repo"], name, revision=revision))
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    if h.hexdigest() != CONFIG["assets"][name]["sha256"]:
        raise RuntimeError(f"Scorer checksum mismatch: {name}")
    return path


BIGRAM = BigramScorer.load(scorer_path("bigram_expanded.pt"), tokenizer=TOKENIZER)
TRIGRAM = TrigramScorer.load(scorer_path("trigram_expanded.pt"), bigram=BIGRAM)


@spaces.GPU(size="large", duration=300)
def generate(question, system_prompt, max_new_tokens, steps, block_length, temperature,
             top_k, color_mode, method, bigram_weight, threshold, editing_threshold,
             max_post_steps, early_stopping, max_steps_per_block):
    if not question.strip():
        raise gr.Error("Enter a prompt first.")
    if int(block_length) not in (32, 64):
        raise gr.Error("Block length must be 32 or 64 for this model's 32-token MoE routing blocks.")
    messages = []
    if system_prompt.strip():
        messages.append(dict(role="system", content=system_prompt))
    messages.append(dict(role="user", content=question))
    encoded = TOKENIZER.apply_chat_template(messages, add_generation_prompt=True,
                                            tokenize=True, return_tensors="pt")
    inputs = encoded if isinstance(encoded, torch.Tensor) else encoded["input_ids"]
    if any(token in (MASK, DELETE, INSERT) for token in inputs[0].tolist()):
        raise gr.Error("Prompt contains a reserved mask/edit token. Remove it before generating.")
    # The demo bounds dense attention memory; the model itself supports 128K.
    if inputs.shape[1] + int(max_new_tokens) > 4096:
        raise gr.Error("This demo supports up to 4096 prompt + answer tokens.")
    inputs = inputs.to(MODEL.device)
    selector = None
    if method == "BG + TG Viterbi (Gumbel)":
        # CPU scorers use the existing candidate-transfer path and avoid holding
        # potentially gigabytes of count buffers in a transient GPU allocation.
        selector = BigramViterbiSelector(
            BIGRAM, weight=float(bigram_weight), scoring_method="pmi", min_count=1,
            pmi_clip=2.0, independent_temperature=True, randomized_viterbi=True,
            trigram_scorer=TRIGRAM, trigram_weight=.5, trigram_min_count=2, trigram_clip=2.0,
        )
        selector = CPUSelector(selector)
    start = time.monotonic()
    try:
        for frame in STREAMER.stream(
            inputs, selector=selector, gen_length=int(max_new_tokens), steps=int(steps),
            block_length=int(block_length), temperature=float(temperature),
            top_k=int(top_k) or None, top_p=None, threshold=float(threshold),
            editing_threshold=float(editing_threshold), max_post_steps=int(max_post_steps),
            eos_early_stop=bool(early_stopping), max_steps_per_block=int(max_steps_per_block),
        ):
            status = f"{'Complete' if frame.done else 'Denoising'} · {frame.iteration} forwards · {time.monotonic()-start:.1f}s"
            yield status, render(frame, TOKENIZER, color_mode)
    except RuntimeError as exc:
        raise gr.Error(str(exc)) from exc


class CPUSelector:
    """Transfer the small block logits for exact CPU n-gram candidate scoring."""
    def __init__(self, selector):
        self.selector = selector

    def select_block(self, logits, current_ids, editable, **kwargs):
        # These blocks are at most 64 x 157184 floats; no extra model forwards.
        tokens, confidence = self.selector.select_block(
            logits.cpu(), current_ids.cpu(), editable.cpu(), **kwargs)
        return tokens.to(logits.device), confidence.to(logits.device)


with gr.Blocks(title="LLaDA2.2-mini · masked diffusion") as demo:
    gr.Markdown("# LLaDA2.2-mini\nFull-precision diffusion with native token rewriting, insertion and deletion.")
    with gr.Row():
        with gr.Column(scale=3):
            question = gr.Textbox(label="Prompt", value="What do you know about Amsterdam?", lines=4)
            run = gr.Button("Generate", variant="primary")
            status = gr.Markdown("Ready")
            trajectory = gr.HTML(label="Live denoising")
        with gr.Column(scale=2):
            system = gr.Textbox(label="System prompt", value="You are a helpful assistant.", lines=2)
            length = gr.Slider(1, 512, value=64, step=1, label="New tokens")
            steps = gr.Slider(1, 128, value=32, step=1, label="Denoising steps per block",
                              info="Controls the minimum unmasking schedule. Refinement may add more iterations.")
            block = gr.Dropdown([32, 64], value=32, label="Block length",
                                info="Must align to the model's 32-token MoE routing blocks.")
            temperature = gr.Slider(0, 2, value=.7, step=.05, label="Temperature",
                                   info="0 is deterministic. Native mode samples masked tokens; BG + TG adds Gumbel noise to ordinary-token paths.")
            weight = gr.Slider(0, 5, value=1, step=.05, label="Bigram weight")
            top_k = gr.Slider(0, 100, value=16, step=1, label="Top-k",
                             info="0 means all tokens in native mode; BG + TG uses 16 candidates when set to 0.")
            color = gr.Radio(["No coloring", "Prediction probability", "Prediction iteration"],
                             value="Prediction iteration", label="Token coloring")
            method = gr.Radio(["Confidence-guided", "BG + TG Viterbi (Gumbel)"],
                              value="BG + TG Viterbi (Gumbel)", label="Decoding method")
            early = gr.Checkbox(value=True, label="Early stopping",
                                info="Stop after a completed block contains EOS. Blocks may converge sooner when stable.")
            with gr.Accordion("Native editing controls", open=False):
                threshold = gr.Slider(0, 1, value=.5, step=.05, label="Unmasking confidence threshold")
                editing = gr.Slider(0, 1, value=0, step=.05, label="Rewrite confidence threshold")
                post = gr.Slider(0, 32, value=16, step=1, label="Maximum post-mask refinement steps")
                cap = gr.Slider(32, 1000, value=256, step=1, label="Safety cap per block")
    gr.Markdown(
        "INSERT opens a mask before the previous token; DELETE shifts tokens left. "
        "Blocks retain their size by truncating or padding with masks. "
        "BG + TG guides ordinary text; structural edit predictions remain native.\n\n"
        f"[Model card](https://huggingface.co/{MODEL_ID}) · "
        "[Source code](https://github.com/RuurdKuiper/lad-generic)"
    )
    inputs = [question, system, length, steps, block, temperature, top_k, color, method,
              weight, threshold, editing, post, early, cap]
    event = run.click(lambda: ("Allocating GPU…", ""), outputs=[status, trajectory], queue=False)
    event.then(generate, inputs, [status, trajectory], api_name="generate", concurrency_limit=1)
    method.change(lambda value: gr.update(interactive=value == "BG + TG Viterbi (Gumbel)"),
                  method, weight, queue=False)

demo.queue(default_concurrency_limit=1, max_size=8)
if __name__ == "__main__":
    demo.launch()
