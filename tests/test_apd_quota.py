import math

import pytest
import torch

from diffusion_lm.apd import commitment_mask


@pytest.mark.parametrize(
    "length,steps", [(64, 16), (128, 8), (65, 16), (7, 3), (3, 8), (1, 1)]
)
def test_low_confidence_commits_quota_without_a_final_step_pileup(length, steps):
    quota = math.ceil(length / steps)
    pending = torch.ones(length, dtype=torch.bool)
    confidence = torch.linspace(0.01, 0.02, length)
    counts = []
    for step in range(steps):
        before = int(pending.sum())
        chosen = commitment_mask(confidence, pending, step, steps, minimum_tokens=quota)
        assert not (chosen & ~pending).any()
        count = int(chosen.sum())
        counts.append(count)
        assert count >= min(quota, before)
        pending &= ~chosen
        if not pending.any():
            break
    assert not pending.any()
    assert counts[-1] <= quota
    if length == 64 and steps == 16:
        assert counts == [4] * 16


def test_quota_adds_best_remaining_selected_token_confidences_and_never_caps_threshold():
    confidence = torch.tensor([0.95, 0.8, 0.7, 0.6, 0.5, 0.99])
    pending = torch.tensor([True, True, True, True, True, False])
    chosen = commitment_mask(confidence, pending, 0, 16, minimum_tokens=4)
    assert chosen.tolist() == [True, True, True, True, False, False]
    # Quota is a floor; every above-threshold row can still commit together.
    assert (
        commitment_mask(
            torch.full((8,), 0.95),
            torch.ones(8, dtype=torch.bool),
            0,
            16,
            minimum_tokens=4,
        ).sum()
        == 8
    )


def test_delay_endings_prioritizes_ordinary_tokens_but_still_meets_quota():
    confidence = torch.tensor([0.1, 0.2, 0.99, 0.98, 0.97])
    pending = torch.ones(5, dtype=torch.bool)
    endings = torch.tensor([False, False, True, True, True])
    chosen = commitment_mask(
        confidence, pending, 0, 8, minimum_tokens=3, endings=endings, delay_endings=True
    )
    assert chosen.tolist() == [True, True, True, False, False]
    ordinary_left = pending & ~endings & ~chosen
    assert not ordinary_left.any()


def test_quota_nonfinite_scores_and_few_pending_rows_are_safe():
    confidence = torch.tensor([float("nan"), 0.1, float("inf"), 0.2, float("-inf")])
    pending = torch.ones(5, dtype=torch.bool)
    assert commitment_mask(confidence, pending, 0, 8, minimum_tokens=3).tolist() == [
        True,
        True,
        False,
        True,
        False,
    ]
    pending = torch.tensor([True, False, False, True, False])
    assert torch.equal(
        commitment_mask(confidence, pending, 0, 8, minimum_tokens=4), pending
    )


@pytest.mark.parametrize("value", [0, -1, 1.5])
def test_invalid_quota(value):
    with pytest.raises(ValueError, match="minimum tokens"):
        commitment_mask(
            torch.ones(2), torch.ones(2, dtype=torch.bool), 0, 8, minimum_tokens=value
        )


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize(
    "method", ["standard", "pmi", "repetition", "margin", "sample_risk"]
)
def test_actual_loop_applies_block_quota_and_respects_model_budget(
    native, method, monkeypatch
):
    from test_apd import session, selector
    from diffusion_lm.inference import denoise_stream
    import diffusion_lm.inference as inference
    from diffusion_lm.bigram import (
        BigramScorer,
        BigramViterbiSelector,
        RepetitionPenalizedBigramSelector,
    )

    s = session(native=native, distribution="uniform")
    decoder = selector(method)
    if method == "sample_risk":
        base = BigramViterbiSelector(
            BigramScorer.from_sequences([[1, 2, 3]] * 10, 8),
            weight=1.0,
            scoring_method="pmi",
            min_count=1,
            sequence_sampling=True,
            independent_temperature=True,
        )
        decoder = RepetitionPenalizedBigramSelector(
            base, 1.0, count_mode="risk", decay_steps=6, excluded_token_ids=(4, 5)
        )
    observed = []
    real = inference.commitment_mask

    def checked(confidence, pending, step, steps, **kwargs):
        chosen = real(confidence, pending, step, steps, **kwargs)
        quota = kwargs["minimum_tokens"]
        assert int(chosen.sum()) >= min(int(pending.sum()), quota)
        observed.append((step, steps, len(pending), quota, int(chosen.sum())))
        return chosen

    monkeypatch.setattr(inference, "commitment_mask", checked)
    states = list(
        denoise_stream(
            s,
            "Q",
            "S",
            10,
            4,
            1.0,
            1.0,
            3,
            42,
            permanent_unmask=True,
            confidence_guided=True,
            early_stopping=False,
            block_length=6,
            bigram_selector=decoder,
            adaptive_parallel_decoding=True,
        )
    )
    assert len(states) == len(s.model.inputs) == 4
    assert observed == [
        (0, 2, 6, 3, 3),
        (1, 2, 6, 3, 3),
        (0, 2, 4, 2, 2),
        (1, 2, 4, 2, 2),
    ]
    assert "masked at iteration" not in states[-1][2]
