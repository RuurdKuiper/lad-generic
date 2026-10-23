"""Shared full-precision ZeroGPU demo for BYOD adapters and native LLaDA."""
from __future__ import annotations

import json
from functools import lru_cache
import os
import secrets
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import gradio as gr
import spaces

sys.path.insert(0, str(Path(__file__).parent / "src"))

from diffusion_lm.bigram import BigramScorer, BigramViterbiSelector, RepetitionPenalizedBigramSelector
from diffusion_lm.bigram_evaluation import ProfiledBigramSelector
from diffusion_lm.trigram import TrigramScorer
from diffusion_lm.inference import denoise_stream, load_hub_adapter_session, load_llada_session, _ending_token_ids


SPACE = json.loads((Path(__file__).parent / "space_model.json").read_text())
BIGRAM_ENABLED = bool(SPACE.get("bigram_enabled", False))
TRIGRAM_ENABLED = bool(SPACE.get("trigram_enabled", SPACE.get("ngram_scorer_repo", False)))
SHOW_BIGRAM_EVALUATION_CONTROLS = bool(SPACE.get("show_bigram_evaluation_controls", False))
BIGRAM_PATH = os.getenv("BIGRAM_MODEL_PATH", str(Path(__file__).parent / "bigram.pt"))
# Bigram defaults: edit these here to change the hosted configuration.
# Scoring: "Conditional bigram" or "PMI bigram".
# Retention: "Diffusion probability" or "Viterbi path margin".
BIGRAM_SCORING_METHOD = "PMI bigram"
BIGRAM_REMASKING_CONFIDENCE = "Diffusion probability"
PMI_MIN_COUNT = 1
PMI_CLIP = 2.0
BIGRAM_ENDING_DELAY_STRENGTH = 10.0
# Set True to restore the legacy LLaDA controls. Implementations and API
# overrides remain available for reproducing the historical experiments.
SHOW_LEGACY_DECODING_CONTROLS = False
# Absolute iterations per block: full on iteration 1, zero from iteration 6.
REPETITION_FADE_ITERATIONS = 6
EXPANDED_BIGRAM_PATH = str(Path(__file__).parent / "bigram_expanded.pt")
TRIGRAM_PATH = str(Path(__file__).parent / "trigram_expanded.pt")
TRIGRAM_RELATIVE_WEIGHT = 0.5
TRIGRAM_MIN_COUNT = 2
TRIGRAM_CLIP = 2.0
if SPACE.get("ngram_scorer_repo"):
    from huggingface_hub import hf_hub_download
    # Download at startup, outside timed GPU inference; pin the artifact commit.
    EXPANDED_BIGRAM_PATH = hf_hub_download(SPACE["ngram_scorer_repo"], "bigram_expanded.pt", revision=SPACE["ngram_scorer_revision"])
    TRIGRAM_PATH = hf_hub_download(SPACE["ngram_scorer_repo"], "trigram_expanded.pt", revision=SPACE["ngram_scorer_revision"])
# Preserve the candidate pool and balance used in the matched Viterbi tests.
DEFAULT_TEMPERATURE = (0.7 if SPACE.get("model_backend") == "llada" else 0.3 if TRIGRAM_ENABLED else 2.0) if BIGRAM_ENABLED else 0.7
DEFAULT_TOP_K = 16 if BIGRAM_ENABLED else 3

MODEL_REPO_ID = os.getenv("MODEL_REPO_ID", SPACE["model_repo_id"])
DISPLAY_NAME = SPACE["display_name"]
SHOW_REPOSITORY_LINKS = bool(SPACE.get("show_repository_links", True))
SOURCE_URL = SPACE.get("source_url")
VISITOR_COUNTER_ID = SPACE.get("visitor_counter_id")


def _visitor_badge(counter_id: str | None) -> str:
    """Return a persistent, client-loaded visit counter for this Space."""
    if not counter_id:
        return ""
    query = urlencode(
        {
            "page_id": counter_id,
            "left_text": "visitors",
            "left_color": "#4b5563",
            "right_color": "#6d28d9",
        }
    )
    return f"![Visitor count](https://visitor-badge.laobi.icu/badge?{query})"

# ZeroGPU recommends constructing and placing the root module on CUDA at module
# scope. The models are loaded without quantization.
print(f"Loading {MODEL_REPO_ID} in full precision...")
if SPACE.get("model_backend", "byod") == "llada":
    SESSION = load_llada_session(
        MODEL_REPO_ID, device_name="cuda", revision=SPACE["model_revision"], preflight=False,
    )
else:
    SESSION = load_hub_adapter_session(
        MODEL_REPO_ID,
        device_name="cuda",
        quantization="none",
        # A forward pass is only valid after @spaces.GPU allocates hardware.
        preflight=False,
    )
print(f"Loaded {DISPLAY_NAME} ({SESSION.compute_dtype}, unquantized).")
# Capability is separate from model backend: BYOD retains its own inference loop.
SESSION.ngram_guidance_enabled = TRIGRAM_ENABLED


@lru_cache(maxsize=2)
def _bigram_scorer(path):
    # weights_only loading and tokenizer validation happen once per checkpoint.
    return BigramScorer.load(path, tokenizer=SESSION.tokenizer)


@lru_cache(maxsize=1)
def _trigram_scorer(path, bigram_path):
    return TrigramScorer.load(path, bigram=_bigram_scorer(bigram_path))


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
    bigram_model_path: str = BIGRAM_PATH,
    bigram_scoring_method: str = BIGRAM_SCORING_METHOD,
    pmi_min_count: int = PMI_MIN_COUNT,
    pmi_clip: float = PMI_CLIP,
    generation_seed: int = -1,
    measure_decoding: bool = False,
    bigram_eos_delay_penalty: float = BIGRAM_ENDING_DELAY_STRENGTH,
    bigram_remasking_confidence: str = BIGRAM_REMASKING_CONFIDENCE,
    repetition_penalty_strength: float = 1.0,
    adaptive_parallel_decoding: bool = False,
    sequence_sampling: bool = False,
    count_all_candidate_bigrams: bool = False,
    bigram_weight: float = 1.0,
    repetition_risk_penalty: bool = False,
    decay_repetition_penalty: bool = False,
    apd_aggressiveness: float = 0.0,
    ngram_guidance: str = "Original bigram",
    randomized_viterbi: bool | None = None,
):
    """Stream iterative masked-diffusion generation from the fixed model."""
    modern_guidance = bool(getattr(SESSION, "llada", False) or getattr(SESSION, "ngram_guidance_enabled", False))
    if remasking_strategy == "BG + TG Viterbi (Gumbel)":
        remasking_strategy = "Bigram Viterbi"
        ngram_guidance = "Expanded bigram + trigram"
        sequence_sampling = False
        randomized_viterbi = True
        bigram_eos_delay_penalty = BIGRAM_ENDING_DELAY_STRENGTH
    question = question.strip() or "What do you know about Amsterdam?"
    block_length = min(int(block_length), int(max_new_tokens))
    seed = secrets.randbelow(2**63 - 1) if int(generation_seed) < 0 else int(generation_seed)
    selector = None
    if remasking_strategy in {"Bigram Viterbi", "PMI Viterbi + Repetition Penalty"}:
        if not BIGRAM_ENABLED:
            raise gr.Error("Bigram Viterbi is not enabled for this Space.")
        try:
            trigram_options = {}
            if ngram_guidance not in {"Original bigram", "Expanded bigram", "Expanded bigram + trigram"}:
                raise ValueError("Unknown n-gram guidance option")
            if ngram_guidance != "Original bigram":
                if not modern_guidance:
                    raise ValueError("Expanded n-gram checkpoints require tokenizer-matched scorer configuration")
                bigram_model_path = EXPANDED_BIGRAM_PATH
            if ngram_guidance == "Expanded bigram + trigram":
                trigram_options = dict(
                    trigram_scorer=_trigram_scorer(TRIGRAM_PATH, bigram_model_path).to(SESSION.device),
                    trigram_weight=TRIGRAM_RELATIVE_WEIGHT,
                    trigram_min_count=TRIGRAM_MIN_COUNT, trigram_clip=TRIGRAM_CLIP,
                )
            selector = BigramViterbiSelector(
                _bigram_scorer(bigram_model_path).to(SESSION.device),
                float(bigram_weight) if modern_guidance else 0.5,
                scoring_method=("pmi" if remasking_strategy == "PMI Viterbi + Repetition Penalty" else
                    {"Conditional bigram": "conditional", "PMI bigram": "pmi"}.get(bigram_scoring_method, "")),
                min_count=int(pmi_min_count), pmi_clip=float(pmi_clip),
                sequence_sampling=bool(sequence_sampling),
                randomized_viterbi=(
                    not bool(sequence_sampling) and
                    (True if randomized_viterbi is None else bool(randomized_viterbi))
                ) if modern_guidance else False,
                independent_temperature=modern_guidance,
                remasking_confidence={"Diffusion probability": "diffusion", "Viterbi path margin": "viterbi_margin"}.get(bigram_remasking_confidence, ""),
                **trigram_options,
            )
            if remasking_strategy == "PMI Viterbi + Repetition Penalty":
                selector = RepetitionPenalizedBigramSelector(
                    selector, float(repetition_penalty_strength),
                    excluded_token_ids=_ending_token_ids(SESSION.tokenizer),
                    decay_steps=(REPETITION_FADE_ITERATIONS if decay_repetition_penalty and getattr(SESSION, "llada", False) else 0),
                    count_mode=("risk" if repetition_risk_penalty else
                        "candidate_occurrences" if count_all_candidate_bigrams else "expected"),
                )
            if measure_decoding:
                selector = ProfiledBigramSelector(selector)
        except (FileNotFoundError, ValueError) as exc:
            raise gr.Error(str(exc)) from exc
    first_step = True
    inference_started = time.perf_counter() if measure_decoding else None
    forward_passes = 0
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
        confidence_guided=remasking_strategy in {"Confidence-guided", "Bigram Viterbi", "PMI Viterbi + Repetition Penalty"},
        proportional_unmask=False,
        early_stopping=bool(early_stopping),
        # Bigram mode also fades an ending-prediction penalty to counter its
        # deterministic tendency to choose the same short ending repeatedly.
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
        bigram_selector=selector,
        bigram_eos_delay_penalty=float(bigram_eos_delay_penalty),
        adaptive_parallel_decoding=bool(adaptive_parallel_decoding),
        apd_aggressiveness=float(apd_aggressiveness),
    ):
        if not first_step and float(pause_per_step) > 0:
            # The sleep occurs inside this one decorated generator invocation,
            # so ZeroGPU remains allocated for the entire denoising run.
            time.sleep(float(pause_per_step))
        first_step = False
        forward_passes += 1
        if measure_decoding:
            status += "\n\nInference metrics: " + json.dumps(dict(
                denoising_forward_passes=forward_passes, elapsed_ms=(time.perf_counter() - inference_started) * 1000,
                adaptive_parallel_decoding=bool(adaptive_parallel_decoding),
            ))
        if measure_decoding and selector is not None:
            status += "\n\nDecoding metrics: " + json.dumps(selector.metrics())
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


MODERN_GUIDANCE = SESSION.llada or getattr(SESSION, "ngram_guidance_enabled", False)
SIMPLE_INTERFACE = MODERN_GUIDANCE and not SHOW_LEGACY_DECODING_CONTROLS

with gr.Blocks(title=f"{DISPLAY_NAME} · masked diffusion") as demo:
    gr.Markdown(
        f"# {DISPLAY_NAME}\n"
        "A full-precision masked-diffusion model converted from an "
        "autoregressive language model with LoRA. This demo uses the exact "
        "published training checkpoint and does **not** use 4-bit quantization."
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
            max_new_tokens = gr.Slider(1, 512, value=64, step=16, label="New tokens")
            num_steps = gr.Slider(1, 512, value=64, step=1, label="Denoising steps")
            block_length = gr.Slider(1, 512, value=64, step=1, label="Block length")
            temperature = gr.Slider(0.0, 2.0, value=DEFAULT_TEMPERATURE, step=0.05, label="Temperature",
                info=("For BG and BG+TG: 0 selects the best sequence; higher values add randomness using fast Gumbel Viterbi. Bigram weight controls n-gram influence independently."
                    if MODERN_GUIDANCE else "In Viterbi, lower values favor diffusion predictions over bigrams; 0 ignores bigram scores. Viterbi remains deterministic.") if BIGRAM_ENABLED else None)
            bigram_weight = gr.Slider(0.0, 5.0, value=1.0, step=0.05, label="Bigram weight",
                visible=MODERN_GUIDANCE and BIGRAM_ENABLED,
                info="PMI coefficient: 0 disables PMI; 1 gives equal diffusion and PMI score coefficients. Independent of temperature.")
            top_k = gr.Slider(1, 100, value=DEFAULT_TOP_K, step=1, label="Top-k",
                info="Number of candidate tokens per position for sampling or Viterbi. At 1, only the model’s highest-scoring token is available." if BIGRAM_ENABLED else None)
            pause_per_step = gr.Slider(
                0.0,
                1.0,
                value=0.0,
                step=0.05,
                label="Pause between denoising steps (seconds)",
                visible=not SIMPLE_INTERFACE,
                info="Slows the visualization while keeping one GPU allocation for the full run.",
            )
            trajectory_color_mode = gr.Radio(
                choices=["No coloring", "Prediction probability", "Prediction iteration"],
                value="Prediction iteration",
                label="Token coloring",
                info="Hover over any token to see its position, prediction iteration, and probability.",
            )
            remasking_strategy = gr.Radio(
                choices=(["Confidence-guided"] + (["BG + TG Viterbi (Gumbel)"] if BIGRAM_ENABLED else [])) if SIMPLE_INTERFACE else
                    ["Confidence-guided"] + ([] if SESSION.llada else ["Autoregressive-confidence"]) + ["Random"] + (["Bigram Viterbi", "PMI Viterbi + Repetition Penalty"] if BIGRAM_ENABLED else []),
                value=("BG + TG Viterbi (Gumbel)" if SIMPLE_INTERFACE else "Bigram Viterbi") if BIGRAM_ENABLED else "Confidence-guided",
                label="Decoding method" if SIMPLE_INTERFACE else "Remasking strategy",
            )
            ngram_guidance = gr.Dropdown(
                choices=["Original bigram", "Expanded bigram", "Expanded bigram + trigram"],
                value="Expanded bigram + trigram" if SIMPLE_INTERFACE else "Original bigram", label="N-gram guidance",
                visible=not SIMPLE_INTERFACE and MODERN_GUIDANCE and BIGRAM_ENABLED,
                info="For bigram decoding strategies. Compare the original corpus with expanded English/code/math counts and optional trigram corrections. Trigrams cost more at large Top-k; start at 16.")
            repetition_penalty_strength = gr.Slider(
                0.0, 10.0, value=1.0, step=0.1, label="Repetition penalty strength (γ)",
                visible=False, info="Penalize repeated bigram transitions; EOS/EOT are exempt. At 0, disables the repetition penalty.",
            )
            sequence_sampling = gr.Checkbox(value=False, visible=not SIMPLE_INTERFACE and MODERN_GUIDANCE and BIGRAM_ENABLED,
                label="Use exact sequence sampling (slower)",
                info="Optional alternative to standard temperature-controlled Gumbel Viterbi. Samples the joint sequence distribution exactly on the candidate lattice.")
            # Keep the API override for reproducible historical evaluations;
            # normal UI use automatically follows Temperature.
            randomized_viterbi = gr.Checkbox(value=True, visible=False)
            count_all_candidate_bigrams = gr.Checkbox(value=False, visible=not SIMPLE_INTERFACE and MODERN_GUIDANCE and BIGRAM_ENABLED,
                label="Count every candidate bigram occurrence",
                info="For repetition penalty: count each earlier adjacent candidate-list occurrence as 1, regardless of probability. EOS/EOT are exempt.")
            repetition_risk_penalty = gr.Checkbox(value=False, visible=not SIMPLE_INTERFACE and MODERN_GUIDANCE and BIGRAM_ENABLED,
                label="Repetition-risk penalty",
                info="For the repetition strategy: estimate risk from joint diffusion + PMI probabilities. Overrides candidate-count mode; EOS/EOT are exempt.")
            decay_repetition_penalty = gr.Checkbox(value=not SIMPLE_INTERFACE, visible=not SIMPLE_INTERFACE and MODERN_GUIDANCE and BIGRAM_ENABLED,
                label="Fade repetition penalty over early iterations",
                info=f"For repetition decoding: logistic fade, full on iteration 1 and zero from iteration {REPETITION_FADE_ITERATIONS}. Resets per block. Turn off for constant strength.")
            if SHOW_BIGRAM_EVALUATION_CONTROLS and BIGRAM_ENABLED and not SIMPLE_INTERFACE:
                with gr.Group():
                    bigram_eos_delay_penalty = gr.Number(value=BIGRAM_ENDING_DELAY_STRENGTH, minimum=1,
                        label="Bigram ending delay strength",
                        info="With Delay EOS/EOT enabled, discourages ending predictions early and fades to 1 at the final block step. Set 1 for retention-only delay.")
                    bigram_model_path = gr.Textbox(value=BIGRAM_PATH, label="Bigram checkpoint path")
                    with gr.Accordion("Reproducible evaluation", open=False):
                        generation_seed = gr.Number(value=-1, minimum=-1, maximum=2**31-1, precision=0, label="Seed (-1 for random)")
                        measure_decoding = gr.Checkbox(value=False, label="Measure decoding time and changes from argmax")
            revisable_tokens = gr.Checkbox(
                value=False,
                label="Allow revising retained tokens",
                visible=not SIMPLE_INTERFACE and not SESSION.llada,
                info="When enabled, previously visible tokens can be re-masked on later iterations.",
                interactive=False,
            )
            ar_check_interval = gr.Slider(
                1,
                16,
                value=4,
                step=1,
                label="AR check interval",
                visible=not SIMPLE_INTERFACE and not SESSION.llada,
                info="Use the original causal model every N denoising steps; diffusion confidence is used between checks.",
                interactive=False,
            )
            delay_eos_eot = gr.Checkbox(
                value=True,
                label="Delay EOS/EOT retention (longer answers)",
                info="Retains ending tokens last to give the answer room to develop.",
            )
            early_stopping = gr.Checkbox(
                value=True,
                label="Early stopping",
                info="Converge a block after two matching answers; stop all remaining blocks when EOS/EOT is finalized with a complete preceding answer.",
            )
            adaptive_parallel_decoding = gr.Checkbox(
                value=False, label="Adaptive Parallel Decoding (APD)",
                info="Commit confident tokens together, with at least ceil(block length / block iterations) per step. Finish blocks as soon as all positions are resolved.",
            )
            apd_aggressiveness = gr.Slider(0.0, 1.0, value=0.0, step=0.05,
                label="APD aggressiveness", visible=MODERN_GUIDANCE, interactive=False,
                info="0 preserves APD's current thresholds. Higher values commit lower-confidence tokens sooner; 1 commits all positions in one pass per block. May reduce quality.")
    footer = "The first request may take longer while the model is loaded."
    if SHOW_REPOSITORY_LINKS:
        footer += f" [Model card](https://huggingface.co/{MODEL_REPO_ID})"
        if SOURCE_URL:
            footer += f" · [Source code]({SOURCE_URL})"
    visitor_badge = _visitor_badge(VISITOR_COUNTER_ID)
    if visitor_badge:
        footer += f"\n\n{visitor_badge}"
    gr.Markdown(footer)

    # Hidden inputs preserve programmatic evaluation overrides. The interface
    # uses the editable defaults above without exposing expert controls.
    bigram_scoring_method = gr.Textbox(value=BIGRAM_SCORING_METHOD, visible=False)
    bigram_remasking_confidence = gr.Textbox(value=BIGRAM_REMASKING_CONFIDENCE, visible=False)
    pmi_min_count = gr.Number(value=PMI_MIN_COUNT, precision=0, visible=False)
    pmi_clip = gr.Number(value=PMI_CLIP, visible=False)
    if not (SHOW_BIGRAM_EVALUATION_CONTROLS and BIGRAM_ENABLED and not SIMPLE_INTERFACE):
        bigram_eos_delay_penalty = gr.Number(value=BIGRAM_ENDING_DELAY_STRENGTH, visible=False)
        bigram_model_path = gr.Textbox(value=BIGRAM_PATH, visible=False)
        generation_seed = gr.Number(value=-1, precision=0, visible=False)
        measure_decoding = gr.Checkbox(value=False, visible=False)

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
        bigram_model_path,
        bigram_scoring_method,
        pmi_min_count,
        pmi_clip,
        generation_seed,
        measure_decoding,
        bigram_eos_delay_penalty,
        bigram_remasking_confidence,
        repetition_penalty_strength,
        adaptive_parallel_decoding,
        sequence_sampling,
        count_all_candidate_bigrams,
        bigram_weight,
        repetition_risk_penalty,
        decay_repetition_penalty,
        apd_aggressiveness,
        ngram_guidance,
        randomized_viterbi,
    ]
    def update_ar_controls(strategy, apd=False):
        """Expose AR-only controls and clear revision when another strategy is selected."""
        enabled = strategy == "Autoregressive-confidence" and not apd
        return gr.update(interactive=enabled, value=False), gr.update(interactive=enabled)

    remasking_strategy.change(
        update_ar_controls,
        inputs=[remasking_strategy, adaptive_parallel_decoding],
        outputs=[revisable_tokens, ar_check_interval],
        queue=False,
    )
    adaptive_parallel_decoding.change(
        update_ar_controls, inputs=[remasking_strategy, adaptive_parallel_decoding],
        outputs=[revisable_tokens, ar_check_interval], queue=False,
    )
    def update_apd_aggressiveness(enabled):
        return gr.update(interactive=bool(enabled))

    adaptive_parallel_decoding.change(
        update_apd_aggressiveness, inputs=[adaptive_parallel_decoding],
        outputs=[apd_aggressiveness], queue=False,
    )
    def update_repetition_control(strategy):
        return gr.update(visible=strategy == "PMI Viterbi + Repetition Penalty")

    remasking_strategy.change(
        update_repetition_control, inputs=[remasking_strategy],
        outputs=[repetition_penalty_strength], queue=False,
    )
    run_event = run.click(show_loading, outputs=[status, trajectory], queue=False)
    run_event.then(generate, inputs=inputs, outputs=[status, trajectory])
    submit_event = question.submit(show_loading, outputs=[status, trajectory], queue=False)
    submit_event.then(generate, inputs=inputs, outputs=[status, trajectory])

demo.queue(default_concurrency_limit=1).launch(ssr_mode=False)
