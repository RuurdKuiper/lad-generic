"""Build the actual Gradio controls without loading models or requesting a GPU."""

import ast
from pathlib import Path
from types import SimpleNamespace
import pytest

SOURCE = Path(__file__).parents[1] / "huggingface/byod_space/app.py"


def build(legacy, monkeypatch, *, native=True, model_guidance=False):
    monkeypatch.setenv("GRADIO_ANALYTICS_ENABLED", "False")
    import gradio as gr

    tree = ast.parse(SOURCE.read_text())
    keep = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in [
            "generate",
            "show_loading",
        ]:
            node.decorator_list = []
            keep.append(node)
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id in {"MODERN_GUIDANCE", "SIMPLE_INTERFACE"}
            for t in node.targets
        ):
            keep.append(node)
        if (
            isinstance(node, ast.With)
            and isinstance(node.items[0].context_expr, ast.Call)
            and isinstance(node.items[0].context_expr.func, ast.Attribute)
            and node.items[0].context_expr.func.attr == "Blocks"
        ):
            keep.append(node)
    ns = dict(
        gr=gr,
        SESSION=SimpleNamespace(llada=native, ngram_guidance_enabled=model_guidance),
        DISPLAY_NAME="Test",
        BIGRAM_ENABLED=True,
        SHOW_LEGACY_DECODING_CONTROLS=legacy,
        SHOW_BIGRAM_EVALUATION_CONTROLS=True,
        BIGRAM_PATH="/app/bigram.pt",
        BIGRAM_SCORING_METHOD="PMI bigram",
        BIGRAM_REMASKING_CONFIDENCE="Diffusion probability",
        PMI_MIN_COUNT=1,
        PMI_CLIP=2.0,
        BIGRAM_ENDING_DELAY_STRENGTH=10.0,
        DEFAULT_TEMPERATURE=0.7,
        DEFAULT_TOP_K=16,
        REPETITION_FADE_ITERATIONS=6,
        SHOW_REPOSITORY_LINKS=False,
        VISITOR_COUNTER_ID=None,
        _visitor_badge=lambda _: "",
    )
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(SOURCE), "exec"), ns)
    return ns


@pytest.mark.parametrize("native", [True, False])
def test_simple_ui_only_two_methods_and_retains_requested_controls(monkeypatch, native):
    ns = build(False, monkeypatch, native=native, model_guidance=True)
    try:
        assert [x[1] for x in ns["remasking_strategy"].choices] == [
            "Confidence-guided",
            "BG + TG Viterbi (Gumbel)",
        ]
        assert ns["remasking_strategy"].value == "BG + TG Viterbi (Gumbel)"
        for name in [
            "ngram_guidance",
            "sequence_sampling",
            "count_all_candidate_bigrams",
            "repetition_risk_penalty",
            "decay_repetition_penalty",
            "repetition_penalty_strength",
            "bigram_model_path",
            "generation_seed",
            "measure_decoding",
            "bigram_eos_delay_penalty",
            "pause_per_step",
            "revisable_tokens",
            "ar_check_interval",
        ]:
            assert ns[name].visible is False, name
        for name in [
            "adaptive_parallel_decoding",
            "early_stopping",
            "delay_eos_eot",
            "bigram_weight",
        ]:
            assert ns[name].visible is True, name
        assert ns["bigram_eos_delay_penalty"].value == 10.0
        assert ns["ngram_guidance"].value == "Expanded bigram + trigram"
        assert ns["sequence_sampling"].value is False
        assert ns["decay_repetition_penalty"].value is False
        assert all(c["type"] != "accordion" for c in ns["demo"].config["components"])
    finally:
        ns["demo"].close()


def test_one_flag_restores_legacy_controls(monkeypatch):
    ns = build(True, monkeypatch)
    try:
        assert "PMI Viterbi + Repetition Penalty" in [
            x[1] for x in ns["remasking_strategy"].choices
        ]
        assert ns["ngram_guidance"].visible is True
        assert ns["sequence_sampling"].visible is True
        assert ns["bigram_model_path"].visible is True
    finally:
        ns["demo"].close()


@pytest.mark.parametrize("native", [True, False])
def test_simple_method_routes_to_expanded_trigrams_and_gumbel(monkeypatch, native):
    from test_trigram import scorers
    from diffusion_lm.bigram import BigramViterbiSelector

    ns = build(False, monkeypatch, native=native, model_guidance=True)
    bigram, trigram = scorers()
    captured = {}
    paths = []

    def load_scorer(path):
        paths.append(path)
        return bigram

    def stream(session, **kwargs):
        captured.update(kwargs)
        yield "text", "status", "html"

    ns.update(
        SESSION=SimpleNamespace(
            llada=native, ngram_guidance_enabled=True, device="cpu"
        ),
        EXPANDED_BIGRAM_PATH="expanded.pt",
        TRIGRAM_PATH="tri.pt",
        TRIGRAM_RELATIVE_WEIGHT=0.5,
        TRIGRAM_MIN_COUNT=2,
        TRIGRAM_CLIP=2.0,
        _bigram_scorer=load_scorer,
        _trigram_scorer=lambda *a: trigram,
        BigramViterbiSelector=BigramViterbiSelector,
        denoise_stream=stream,
    )
    try:
        list(
            ns["generate"](
                "Q",
                "S",
                32,
                8,
                32,
                0.7,
                16,
                0.0,
                "No coloring",
                "BG + TG Viterbi (Gumbel)",
                False,
                4,
                True,
                True,
                generation_seed=42,
                sequence_sampling=True,
                randomized_viterbi=False,
                bigram_eos_delay_penalty=1000.0,
                adaptive_parallel_decoding=True,
                bigram_weight=1.3,
            )
        )
        selector = captured["bigram_selector"]
        assert paths == ["expanded.pt"]
        assert selector.trigram_scorer is trigram
        assert selector.randomized_viterbi and not selector.sequence_sampling
        assert selector.weight == 1.3
        assert selector.independent_temperature
        assert captured["bigram_eos_delay_penalty"] == 10.0
        assert (
            captured["adaptive_parallel_decoding"]
            and captured["early_stopping"]
            and captured["confidence_eos_eot_inf"]
        )
    finally:
        ns["demo"].close()
