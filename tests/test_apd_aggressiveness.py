import math

import pytest
import torch

from diffusion_lm.apd import confidence_threshold, commitment_mask


def original_threshold(step, steps):
    if steps == 1:
        return 0.5
    phase = max(0.0, (step / (steps - 1) - 0.15) / 0.85)
    return 0.5 + 0.2 * (1.0 + math.cos(math.pi * phase))


@pytest.mark.parametrize("steps", [1, 8, 64, 128])
def test_zero_preserves_exact_threshold_and_larger_aggressiveness_lowers_it(steps):
    for step in range(steps):
        original = original_threshold(step, steps)
        assert (
            confidence_threshold(step, steps)
            == confidence_threshold(step, steps, 0.0)
            == original
        )
        assert confidence_threshold(step, steps, 0.5) == original * 0.5
        assert confidence_threshold(step, steps, 0.9) == original * (1.0 - 0.9)
        assert confidence_threshold(step, steps, 1.0) == 0.0


def test_commitment_set_expands_and_keeps_fixed_rows_untouched():
    confidence = torch.tensor([0.95, 0.7, 0.5, 0.3, 0.1])
    pending = torch.tensor([True, True, False, True, True])
    masks = [
        commitment_mask(confidence, pending, 0, 8, aggressiveness=a)
        for a in [0.0, 0.25, 0.5, 0.9, 1.0]
    ]
    assert all(not m[2] for m in masks)
    assert all((~a | b).all() for a, b in zip(masks, masks[1:]))
    assert torch.equal(masks[-1], pending)


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf")])
def test_invalid_aggressiveness_rejected_before_forward(value):
    from test_apd import session, run

    s = session(native=True)
    with pytest.raises(ValueError, match="aggressiveness"):
        run(s, adaptive_parallel_decoding=True, apd_aggressiveness=value)
    assert s.model.inputs == []


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize(
    "method", ["standard", "random", "conditional", "pmi", "repetition", "margin", "ar"]
)
def test_more_aggressive_apd_reduces_passes_without_extra_calls_or_masks(
    native, method
):
    from test_apd import session, run

    baseline = session(native=native, distribution="uniform")
    aggressive = session(native=native, distribution="uniform")
    old = run(baseline, method, adaptive_parallel_decoding=True)
    fast = run(
        aggressive, method, adaptive_parallel_decoding=True, apd_aggressiveness=0.9
    )
    assert len(fast) == len(aggressive.model.inputs) == 2
    assert len(old) == len(baseline.model.inputs) == 6
    assert aggressive.model.ar_calls == 0
    assert "masked at iteration" not in fast[-1][2]


@pytest.mark.parametrize("method", ["standard", "pmi", "repetition"])
def test_apd_off_ignores_aggressiveness_and_default_zero_is_exact(method):
    from test_apd import session, run

    a = session(native=True, distribution="uniform")
    b = session(native=True, distribution="uniform")
    assert run(a, method) == run(b, method, apd_aggressiveness=1.0)
    c = session(native=True, distribution="uniform")
    d = session(native=True, distribution="uniform")
    assert run(c, method, adaptive_parallel_decoding=True) == run(
        d, method, adaptive_parallel_decoding=True, apd_aggressiveness=0.0
    )


def test_ending_delay_and_fallback_survive_lower_thresholds():
    confidence = torch.tensor([0.5, 0.01, 0.9])
    pending = torch.ones(3, dtype=torch.bool)
    endings = torch.tensor([False, False, True])
    selected = commitment_mask(
        confidence,
        pending,
        0,
        8,
        endings=endings,
        delay_endings=True,
        aggressiveness=0.5,
    )
    assert selected.tolist() == [True, False, False]
    assert commitment_mask(
        confidence,
        pending,
        0,
        8,
        endings=endings,
        delay_endings=True,
        aggressiveness=1.0,
    ).all()
    assert (
        commitment_mask(
            torch.full((3,), float("nan")), pending, 0, 8, aggressiveness=1.0
        ).sum()
        == 1
    )
    assert commitment_mask(confidence, pending, 7, 8, aggressiveness=0.5).all()


@pytest.mark.parametrize("aggressiveness", [0.5, 1.0])
def test_sequence_sampling_risk_and_repetition_decay_compose_with_aggressive_apd(
    aggressiveness,
):
    from test_apd import session
    from diffusion_lm.inference import denoise_stream
    from diffusion_lm.bigram import (
        BigramScorer,
        BigramViterbiSelector,
        RepetitionPenalizedBigramSelector,
    )

    s = session(native=True, distribution="uniform")
    base = BigramViterbiSelector(
        BigramScorer.from_sequences([[1, 2, 3]] * 10, 8),
        weight=1.0,
        scoring_method="pmi",
        min_count=1,
        sequence_sampling=True,
        independent_temperature=True,
    )
    selector = RepetitionPenalizedBigramSelector(
        base, 1.0, count_mode="risk", decay_steps=6, excluded_token_ids=(4, 5)
    )
    states = list(
        denoise_stream(
            s,
            "Q",
            "S",
            6,
            8,
            1.0,
            1.0,
            3,
            42,
            permanent_unmask=True,
            confidence_guided=True,
            early_stopping=False,
            block_length=3,
            bigram_selector=selector,
            adaptive_parallel_decoding=True,
            apd_aggressiveness=aggressiveness,
        )
    )
    assert len(states) == len(s.model.inputs) <= 8
    assert "masked at iteration" not in states[-1][2]
