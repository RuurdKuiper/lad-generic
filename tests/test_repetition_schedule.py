import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from diffusion_lm.bigram import (
    BigramScorer,
    BigramViterbiSelector,
    RepetitionPenalizedBigramSelector,
)
from diffusion_lm.bigram_evaluation import ProfiledBigramSelector
from diffusion_lm.repetition_schedule import repetition_strength_factor


def test_logistic_endpoints_monotonicity_and_absolute_window():
    factors = [repetition_strength_factor(i) for i in range(128)]
    assert factors[0] == 1.0
    assert all(0 <= f <= 1 for f in factors)
    assert all(a >= b for a, b in zip(factors, factors[1:]))
    assert factors[4] > 0 and factors[5:] == [0.0] * 123
    assert factors[1] > 0.9 and factors[3] < 0.4
    assert all(repetition_strength_factor(i, 0) == 1.0 for i in range(128))
    assert (
        repetition_strength_factor(0, 2) == 1.0
        and repetition_strength_factor(1, 2) == 0.0
    )


@pytest.mark.parametrize("step,window", [(-1, 6), (0, 1), (0, -1), (0, 2.5)])
def test_invalid_schedule(step, window):
    with pytest.raises(ValueError):
        repetition_strength_factor(step, window)


@pytest.mark.parametrize("sampling", [False, True])
@pytest.mark.parametrize("mode", ["expected", "candidate_occurrences", "risk"])
def test_zero_tail_matches_original_and_constant_schedule_preserves_existing(
    sampling, mode
):
    base = BigramViterbiSelector(
        BigramScorer.from_sequences([[0, 1, 2]] * 10, 3),
        weight=1.0,
        scoring_method="pmi",
        min_count=1,
        sequence_sampling=sampling,
        independent_temperature=True,
    )
    logits = torch.tensor([[0.3, 0.2, 0.1]] * 6)
    ids = torch.zeros(6, dtype=torch.long)
    editable = torch.ones(6, dtype=torch.bool)
    fading = RepetitionPenalizedBigramSelector(
        base, 2.0, count_mode=mode, decay_steps=6
    )
    constant = RepetitionPenalizedBigramSelector(base, 2.0, count_mode=mode)
    fading.set_step_context(0, 128)
    assert fading.effective_strength == 2.0
    torch.manual_seed(3)
    first = fading.select_block(logits, ids, editable, top_k=3)
    torch.manual_seed(3)
    old = constant.select_block(logits, ids, editable, top_k=3)
    assert all(torch.equal(a, b) for a, b in zip(first, old))
    for t in [5, 63, 127]:
        fading.set_step_context(t, 128)
        assert fading.effective_strength == 0.0
        torch.manual_seed(3)
        actual = fading.select_block(logits, ids, editable, top_k=3)
        torch.manual_seed(3)
        expected = base.select_block(logits, ids, editable, top_k=3)
        assert all(torch.equal(a, b) for a, b in zip(actual, expected))
    # Reusing for a new block restores full strength.
    fading.set_step_context(0, 1)
    assert fading.effective_strength == 2.0
    constant.set_step_context(127, 128)
    assert constant.effective_strength == 2.0


@pytest.mark.parametrize("sampling", [False, True])
@pytest.mark.parametrize("mode", ["expected", "candidate_occurrences", "risk"])
@pytest.mark.parametrize("apd", [False, True])
def test_native_loop_sets_block_context_through_profiler_without_extra_forwards(
    sampling, mode, apd
):
    from test_apd import session
    from diffusion_lm.inference import denoise_stream

    s = session(native=True, distribution="uniform")
    strengths = []

    class RecordingSelector(BigramViterbiSelector):
        def select_block(self, *args, **kwargs):
            strengths.append(kwargs["repetition_penalty_strength"])
            return super().select_block(*args, **kwargs)

    base = RecordingSelector(
        BigramScorer.from_sequences([[1, 2, 3]] * 10, 8),
        weight=1.0,
        scoring_method="pmi",
        min_count=1,
        sequence_sampling=sampling,
        independent_temperature=True,
    )
    wrapper = RepetitionPenalizedBigramSelector(
        base, 2.0, count_mode=mode, decay_steps=6, excluded_token_ids=(4, 5)
    )
    selector = ProfiledBigramSelector(wrapper)
    states = list(
        denoise_stream(
            s,
            "Q",
            "S",
            6,
            16,
            1.0,
            1.0,
            3,
            42,
            permanent_unmask=True,
            confidence_guided=True,
            proportional_unmask=False,
            early_stopping=False,
            block_length=3,
            bigram_selector=selector,
            adaptive_parallel_decoding=apd,
        )
    )
    per_block = 3 if apd else 8
    expected = [2 * repetition_strength_factor(i) for i in range(per_block)] * 2
    assert strengths == pytest.approx(expected)
    assert (
        len(states)
        == len(s.model.inputs)
        == len(strengths)
        == selector.metrics()["selector_calls"]
    )
    assert "masked at iteration" not in states[-1][2]


def test_hosted_generator_routes_fade_and_preserves_api_default():
    source = Path(__file__).parents[1] / "huggingface/byod_space/app.py"
    tree = ast.parse(source.read_text())
    function = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "generate"
    )
    function.decorator_list = []
    captured = {}

    def stream(session, **kwargs):
        captured.update(kwargs)
        yield "text", "status", "html"

    scorer = BigramScorer.from_sequences([[0, 1]], 3)
    ns = dict(
        BIGRAM_PATH="x",
        BIGRAM_ENABLED=True,
        BIGRAM_SCORING_METHOD="PMI bigram",
        BIGRAM_REMASKING_CONFIDENCE="Diffusion probability",
        PMI_MIN_COUNT=1,
        PMI_CLIP=2.0,
        BIGRAM_ENDING_DELAY_STRENGTH=10.0,
        REPETITION_FADE_ITERATIONS=6,
        SESSION=SimpleNamespace(device="cpu", llada=True, tokenizer=object()),
        _bigram_scorer=lambda path: scorer,
        _ending_token_ids=lambda tok: {2},
        BigramViterbiSelector=BigramViterbiSelector,
        RepetitionPenalizedBigramSelector=RepetitionPenalizedBigramSelector,
        denoise_stream=stream,
    )
    exec(compile(ast.Module(body=[function], type_ignores=[]), "app", "exec"), ns)
    args = (
        "Q",
        "S",
        32,
        8,
        32,
        1.0,
        16,
        0.0,
        "No coloring",
        "PMI Viterbi + Repetition Penalty",
        False,
        4,
        True,
        False,
    )
    list(ns["generate"](*args, generation_seed=1))
    assert captured["bigram_selector"].decay_steps == 0
    list(ns["generate"](*args, generation_seed=1, decay_repetition_penalty=True))
    assert captured["bigram_selector"].decay_steps == 6
