"""Sequence distribution and candidate-set counts, including native inference."""

import itertools
from collections import Counter

import pytest
import torch

from diffusion_lm.bigram import (
    BigramScorer,
    BigramViterbiSelector,
    RepetitionPenalizedBigramSelector,
    expected_bigram_repetition_penalties,
)


def test_sampling_matches_enumerated_joint_distribution_and_bigram_preference():
    ids = torch.tensor([[0, 1], [0, 1]])
    emissions = torch.tensor([[0.1, -0.2], [-0.3, 0.2]])
    edges = torch.tensor([[[2.0, -1.0], [-1.0, 2.0]]])
    paths = list(itertools.product(range(2), repeat=2))
    scores = torch.tensor(
        [emissions[0, a] + emissions[1, b] + edges[0, a, b] for a, b in paths]
    )
    expected = scores.softmax(0)
    torch.manual_seed(1234)
    draws = Counter(
        tuple(BigramViterbiSelector.sample_sequence(ids, emissions, edges).tolist())
        for _ in range(4000)
    )
    observed = torch.tensor([draws[p] / 4000 for p in paths])
    torch.testing.assert_close(observed, expected, atol=0.025, rtol=0.0)
    assert (
        observed[0] + observed[3] > 0.9
    )  # Joint transitions matter, not independent sampling.


@pytest.mark.parametrize("length", [1, 64, 256])
def test_sampling_stable_and_respects_singleton_constraints(length):
    ids = torch.tensor([[0, 1]] * length)
    emissions = torch.tensor([[10000.0, -10000.0]] * length)
    emissions[::2] = torch.tensor([-torch.inf, 0.0])
    edges = torch.full((length - 1, 2, 2), -10000.0)
    result = BigramViterbiSelector.sample_sequence(ids, emissions, edges)
    assert result[::2].eq(1).all()
    assert result[1::2].eq(0).all()


def test_candidate_occurrences_ignore_probability_and_deduplicate_fixed_rows():
    ids = torch.tensor([[0, 0, 0], [1, 2, 3]] * 3)
    p = torch.full(ids.shape, 0.000001)
    actual = expected_bigram_repetition_penalties(
        ids, p, 4, 2.0, count_mode="candidate_occurrences"
    )
    # The 0->1 pair appears once at edges 0,2,4, despite duplicate 0 columns.
    torch.testing.assert_close(actual[[0, 2, 4], 0, 0], torch.tensor([0.0, 2.0, 4.0]))
    excluded = expected_bigram_repetition_penalties(
        ids, p, 4, 2.0, excluded_token_ids=(1,), count_mode="candidate_occurrences"
    )
    assert excluded[:, :, 0][[0, 2, 4]].eq(0).all()
    assert excluded[4, 0, 1] == 4  # 0->2 is still counted.
    assert torch.equal(
        actual,
        expected_bigram_repetition_penalties(
            ids, p * 100, 4, 2.0, count_mode="candidate_occurrences"
        ),
    )


@pytest.mark.parametrize("sampling", [False, True])
def test_zero_penalty_identical_for_both_count_modes(sampling):
    scorer = BigramScorer.from_sequences([[0, 1, 2]] * 10, 3)
    selector = BigramViterbiSelector(
        scorer, scoring_method="pmi", min_count=1, sequence_sampling=sampling
    )
    logits = torch.tensor([[0.2, 0.3, 0.1]] * 6)
    outputs = []
    for mode in ["expected", "candidate_occurrences"]:
        torch.manual_seed(42)
        outputs.append(
            selector.select_block(
                logits,
                torch.zeros(6, dtype=torch.long),
                torch.ones(6, dtype=torch.bool),
                top_k=3,
                repetition_penalty_strength=0.0,
                repetition_count_mode=mode,
            )
        )
    for a, b in zip(*outputs):
        assert torch.equal(a, b)


@pytest.mark.parametrize("sampling", [False, True])
@pytest.mark.parametrize("mode", ["expected", "candidate_occurrences"])
@pytest.mark.parametrize("apd", [False, True])
def test_native_inference_combinations_use_one_forward_per_step_and_preserve_fixed_tokens(
    sampling, mode, apd
):
    from test_apd import session
    from diffusion_lm.inference import denoise_stream

    s = session(native=True, distribution="uniform")

    class CheckedSelector(BigramViterbiSelector):
        def select_block(self, logits, current, editable, **kwargs):
            selected, confidence = super().select_block(
                logits, current, editable, **kwargs
            )
            assert torch.equal(selected[~editable], current[~editable])
            assert torch.isfinite(confidence).all()
            return selected, confidence

    base = CheckedSelector(
        BigramScorer.from_sequences([[1, 2, 3]] * 10, 8),
        scoring_method="pmi",
        min_count=1,
        sequence_sampling=sampling,
    )
    selector = RepetitionPenalizedBigramSelector(
        base, 10.0, count_mode=mode, excluded_token_ids=(4, 5)
    )
    result = list(
        denoise_stream(
            s,
            "Q",
            "S",
            6,
            4,
            1.0,
            2.0,
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
    assert len(result) == len(s.model.inputs) == 4
    assert "masked at iteration" not in result[-1][2]


def test_sampling_seed_reproducibility_and_diversity():
    ids = torch.tensor([[0, 1]] * 8)
    emissions = torch.zeros(8, 2)
    edges = torch.zeros(7, 2, 2)
    results = []
    for seed in [1, 1, 2, 3]:
        torch.manual_seed(seed)
        results.append(BigramViterbiSelector.sample_sequence(ids, emissions, edges))
    assert torch.equal(results[0], results[1])
    assert len({tuple(r.tolist()) for r in results}) > 1


@pytest.mark.parametrize("temperature", [0.4, 2.0])
def test_path_temperature_matches_enumerated_distribution(temperature):
    ids = torch.tensor([[0, 1], [0, 1]])
    unary = torch.tensor([[0.4, -0.1], [-0.3, 0.2]])
    edges = torch.tensor([[[0.8, -0.2], [-0.2, 0.8]]])
    paths = list(itertools.product(range(2), repeat=2))
    expected = torch.tensor(
        [(unary[0, a] + unary[1, b] + edges[0, a, b]) / temperature for a, b in paths]
    ).softmax(0)
    torch.manual_seed(5)
    draws = Counter(
        tuple(
            BigramViterbiSelector.sample_sequence(
                ids, unary, edges, temperature=temperature
            ).tolist()
        )
        for _ in range(3000)
    )
    torch.testing.assert_close(
        torch.tensor([draws[p] / 3000 for p in paths]), expected, atol=0.03, rtol=0.0
    )


def test_zero_temperature_is_maximum_path():
    ids = torch.tensor([[0, 1]] * 4)
    unary = torch.tensor([[0.0, 0.2]] * 4)
    edges = torch.tensor([[[1.0, 0.0], [0.0, 1.0]]] * 3)
    assert torch.equal(
        BigramViterbiSelector.sample_sequence(ids, unary, edges, temperature=0),
        BigramViterbiSelector.decode(ids, unary, edges, 1.0),
    )


def test_independent_weight_and_temperature_preserve_scoring_and_raw_confidence(
    monkeypatch,
):
    scorer = BigramScorer.from_sequences([[0, 1, 0, 1]] * 20 + [[2, 2]] * 5, 3)
    logits = torch.tensor([[0.3, 0.2, 0.1]] * 4)
    current = torch.zeros(4, dtype=torch.long)
    editable = torch.ones(4, dtype=torch.bool)
    captured = []
    real_sample = BigramViterbiSelector.sample_sequence

    def capture(ids, unary, edges, weight=1.0, temperature=1.0):
        captured.append((unary.clone(), edges.clone(), temperature))
        return real_sample(ids, unary, edges, weight, temperature)

    monkeypatch.setattr(BigramViterbiSelector, "sample_sequence", staticmethod(capture))
    selector = BigramViterbiSelector(
        scorer,
        weight=1.0,
        scoring_method="pmi",
        min_count=1,
        sequence_sampling=True,
        independent_temperature=True,
    )
    for temp in [0.5, 1.0, 2.0]:
        selected, confidence = selector.select_block(
            logits,
            current,
            editable,
            top_k=3,
            temperature=temp,
            repetition_penalty_strength=2.0,
        )
        torch.testing.assert_close(
            confidence, logits.softmax(-1).gather(1, selected[:, None]).squeeze(1)
        )
    for unary, edges, _ in captured[1:]:
        assert torch.equal(unary, captured[0][0])
        assert torch.equal(edges, captured[0][1])
    assert [r[2] for r in captured] == [0.5, 1.0, 2.0]


def test_independent_viterbi_ignores_temperature_and_weight_zero_keeps_repetition():
    scorer = BigramScorer.from_sequences([[0, 1]] * 20, 2)
    logits = torch.tensor([[0.0, 0.1]] * 6)
    current = torch.zeros(6, dtype=torch.long)
    editable = torch.ones(6, dtype=torch.bool)
    selector = BigramViterbiSelector(
        scorer,
        weight=1.0,
        scoring_method="pmi",
        min_count=1,
        independent_temperature=True,
    )
    results = [
        selector.select_block(logits, current, editable, top_k=2, temperature=t)[0]
        for t in [0.0, 1.0, 2.0]
    ]
    assert all(torch.equal(results[0], r) for r in results)
    selector.weight = 0.0
    selected, _ = selector.select_block(
        logits,
        current,
        editable,
        top_k=2,
        temperature=1.0,
        repetition_penalty_strength=10.0,
    )
    assert not torch.equal(selected, logits.argmax(-1))


def test_unseen_pmi_is_neutral_not_a_forbidden_transition():
    scorer = BigramScorer.from_sequences([[0, 1]] * 10, 3)
    a, b = torch.tensor([1]), torch.tensor([2])
    assert (
        scorer.transition_score(a, b, scoring_method="pmi", min_count=1).item() == 0.0
    )
    assert torch.isfinite(scorer.log_prob(a, b)).all()
