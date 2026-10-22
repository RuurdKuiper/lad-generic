from collections import defaultdict
import itertools

import pytest
import torch

from diffusion_lm.bigram import (
    BigramScorer,
    BigramViterbiSelector,
    expected_bigram_repetition_penalties,
)


def reference_penalties(ids, probabilities, strength):
    counts = defaultdict(float)
    penalties = probabilities.new_zeros((len(ids) - 1, ids.shape[1], ids.shape[1]))
    for t in range(len(ids) - 1):
        updates = defaultdict(float)
        for a, b in itertools.product(range(ids.shape[1]), repeat=2):
            key = int(ids[t, a]), int(ids[t + 1, b])
            q = float(probabilities[t, a]) * float(probabilities[t + 1, b])
            penalties[t, a, b] = strength * counts[key]
            updates[key] += q
        for key, q in updates.items():
            counts[key] += q
    return penalties


def test_first_occurrence_is_free_and_later_penalties_grow():
    ids = torch.zeros(5, 1, dtype=torch.long)
    probabilities = torch.full((5, 1), .5)  # Not renormalized to 1 over top-k.
    penalties = expected_bigram_repetition_penalties(ids, probabilities, 3, 2.)
    torch.testing.assert_close(penalties[:, 0, 0], torch.tensor([0., .5, 1., 1.5]))


def test_candidate_contributions_match_left_to_right_dictionary():
    ids = torch.tensor([[0, 1], [1, 0], [0, 1], [1, 0], [0, 1]])
    probabilities = torch.tensor([[.3, .2], [.4, .1], [.2, .5], [.1, .2], [.6, .3]])
    actual = expected_bigram_repetition_penalties(ids, probabilities, 128256, 1.7)
    torch.testing.assert_close(actual, reference_penalties(ids, probabilities, 1.7))


def test_current_pair_probability_does_not_dilute_transition_penalty():
    ids = torch.zeros(3, 1, dtype=torch.long)
    p = torch.tensor([[.5], [.5], [.001]])
    penalties = expected_bigram_repetition_penalties(ids, p, 2, 10.)
    assert penalties[0, 0, 0].item() == 0.
    assert penalties[1, 0, 0].item() == pytest.approx(2.5)  # 10 * previous q=.25.


def test_duplicates_in_fixed_rows_update_counts_only_after_the_current_edge():
    ids = torch.zeros(4, 3, dtype=torch.long)
    probabilities = torch.tensor([[1., 0., 0.]] * 4)
    penalties = expected_bigram_repetition_penalties(ids, probabilities, 2)
    torch.testing.assert_close(penalties, torch.tensor([0., 1., 2.])[:, None, None].expand(3, 3, 3))


def test_counts_reset_between_blocks_and_iterations():
    ids = torch.zeros(2, 1, dtype=torch.long)
    p = torch.ones(2, 1)
    for _ in range(3):
        assert torch.equal(expected_bigram_repetition_penalties(ids, p, 1), torch.zeros(1, 1, 1))
    together = expected_bigram_repetition_penalties(ids.repeat(2, 1), p.repeat(2, 1), 1)
    assert together[-1].item() == 2.


def test_eos_and_eot_pairs_neither_receive_penalties_nor_contribute_counts():
    ids = torch.tensor([[0, 1, 2]] * 5)
    p = torch.tensor([[.4, .3, .2]] * 5)
    # 1=EOS, 2=EOT. Only the ordinary pair (0,0) contributes any correction.
    actual = expected_bigram_repetition_penalties(ids, p, 3, excluded_token_ids=(1, 2))
    expected = expected_bigram_repetition_penalties(ids[:, :1], p[:, :1], 3)
    torch.testing.assert_close(actual[:, :1, :1], expected)
    assert torch.count_nonzero(actual[:, 1:, :]) == 0
    assert torch.count_nonzero(actual[:, :, 1:]) == 0
    all_endings = expected_bigram_repetition_penalties(ids[:, 1:], p[:, 1:], 3, excluded_token_ids=(1, 2))
    assert torch.count_nonzero(all_endings) == 0


def test_eos_tail_remains_unchanged_by_repetition_penalty():
    scorer = BigramScorer.from_sequences([[0, 1, 1, 1]] * 10, 2)
    selector = BigramViterbiSelector(scorer, scoring_method="pmi")
    logits = torch.tensor([[0., .1]] * 8)
    current, editable = torch.ones(8, dtype=torch.long), torch.ones(8, dtype=torch.bool)
    selected, _ = selector.select_block(logits, current, editable, repetition_penalty_strength=100.,
                                        repetition_excluded_token_ids=(1,))
    assert selected.tolist() == [1] * 8


@pytest.mark.parametrize("length", [1, 8, 64, 256])
@pytest.mark.parametrize("temperature", [0., 1., 2.])
@pytest.mark.parametrize("confidence", ["diffusion", "viterbi_margin"])
@pytest.mark.parametrize("dtype", [torch.float32, torch.bfloat16])
def test_zero_strength_exactly_matches_original_selection_confidence_and_margins(length, temperature, confidence, dtype):
    scorer = BigramScorer.from_sequences([[0, 1, 2, 3]] * 5, 4)
    selector = BigramViterbiSelector(scorer, scoring_method="pmi", min_count=1, pmi_clip=2., remasking_confidence=confidence)
    logits = torch.randn(length, 4, generator=torch.Generator().manual_seed(4)).to(dtype)
    current = torch.full((length,), 3)
    editable = torch.arange(length) % 3 != 1
    kwargs = dict(top_k=3, temperature=temperature, left_id=2, right_id=1)
    original, original_confidence = selector.select_block(logits, current, editable, **kwargs)
    original_margins = selector.last_path_margins
    selected, selected_confidence = selector.select_block(logits, current, editable, repetition_penalty_strength=0., **kwargs)
    assert torch.equal(selected, original)
    assert torch.equal(selected_confidence, original_confidence)
    if original_margins is not None:
        assert torch.equal(selector.last_path_margins, original_margins)


def test_adjusted_transitions_use_original_probabilities_and_leave_unaries_unchanged(monkeypatch):
    scorer = BigramScorer.from_sequences([[0, 1, 0, 1]] * 20 + [[2, 2]] * 8, 3)
    selector = BigramViterbiSelector(scorer, .5, scoring_method="pmi", min_count=1, pmi_clip=2.)
    logits = torch.tensor([[.2, 0., -.1], [.1, .3, 0.], [.2, 0., -.1], [.1, .3, 0.]])
    current = torch.tensor([2, 1, 2, 2])
    editable = torch.tensor([True, False, True, True])
    captured = []
    decode = selector.decode

    def record(ids, unaries, transitions, weight):
        captured.append((ids.clone(), unaries.clone(), transitions.clone(), weight))
        return decode(ids, unaries, transitions, weight)

    monkeypatch.setattr(selector, "decode", record)
    selector.select_block(logits, current, editable, top_k=3, temperature=.6, left_id=0, right_id=1)
    selected, confidence = selector.select_block(logits, current, editable, top_k=3, temperature=.6,
                                                left_id=0, right_id=1, repetition_penalty_strength=3.)
    ids, original, transitions, weight = captured[0]
    probabilities = logits.softmax(-1).gather(1, ids)
    probabilities[1] = torch.tensor([1., 0., 0.])
    expected = reference_penalties(ids, probabilities, 3.)
    assert torch.equal(captured[1][1], original)
    torch.testing.assert_close(captured[1][2], weight * transitions - expected)
    assert captured[1][3] == 1.
    assert selected[1] == current[1]
    torch.testing.assert_close(confidence, logits.softmax(-1).gather(1, selected[:, None]).squeeze(1))


@pytest.mark.parametrize("confidence", ["diffusion", "viterbi_margin"])
def test_penalty_can_change_path_even_when_pmi_weight_is_zero(confidence):
    scorer = BigramScorer.from_sequences([[0, 1, 0, 1]], 2)
    selector = BigramViterbiSelector(scorer, 0., scoring_method="pmi", remasking_confidence=confidence)
    logits = torch.tensor([[.1, 0.]] * 4)
    selected, _ = selector.select_block(logits, torch.zeros(4, dtype=torch.long), torch.ones(4, dtype=torch.bool),
                                        top_k=2, repetition_penalty_strength=10.)
    assert selected.tolist() != [0, 0, 0, 0]


@pytest.mark.parametrize("temperature", [0., .6, 2.])
@pytest.mark.parametrize("confidence_mode", ["diffusion", "viterbi_margin"])
def test_transition_objective_and_margins_match_exhaustive_paths(temperature, confidence_mode):
    scorer = BigramScorer.from_sequences([[0, 1, 0, 2, 3]] * 20 + [[2, 1, 2]] * 8, 4)
    selector = BigramViterbiSelector(scorer, .5, scoring_method="pmi", min_count=1, pmi_clip=2.,
                                    remasking_confidence=confidence_mode)
    logits = torch.tensor([[.2, 0., -.1, -.3], [.1, .3, 0., -.2], [.2, 0., -.1, -.3], [.1, .3, 0., -.2]])
    current, editable = torch.tensor([2, 1, 2, 2]), torch.tensor([True, False, True, True])
    selected, _ = selector.select_block(logits, current, editable, top_k=4, temperature=temperature,
                                        left_id=0, right_id=2, repetition_penalty_strength=3.,
                                        repetition_excluded_token_ids=(3,))
    p = logits.softmax(-1)
    p[1] = torch.tensor([0., 1., 0., 0.])
    p[:, 3] = 0.  # Exclude EOS pairs without redistributing its probability mass.
    penalties = reference_penalties(torch.arange(4).expand(4, 4), p, 3.)
    log_p = logits.log_softmax(-1)

    def score(path):
        sequence = torch.tensor([0, *path, 2])
        pmi = scorer.transition_score(sequence[:-1], sequence[1:], scoring_method="pmi", min_count=1, pmi_clip=2.)
        return (sum(log_p[t, path[t]] for t in [0, 2, 3]) + .5 * temperature * pmi.sum()
                - sum(penalties[t, path[t], path[t + 1]] for t in range(3)))

    paths = [[a, 1, b, c] for a, b, c in itertools.product(range(4), repeat=3)]
    best = max(paths, key=score)
    assert selected.tolist() == best
    if confidence_mode == "viterbi_margin":
        assert torch.isinf(selector.last_path_margins[1])
        for t in [0, 2, 3]:
            alternative = max(score(path) for path in paths if path[t] != best[t])
            assert selector.last_path_margins[t].item() == pytest.approx(float(score(best) - alternative), abs=2e-6)


@pytest.mark.parametrize("dtype", [torch.float32, torch.float16, torch.bfloat16])
def test_extreme_logits_zero_probability_candidates_and_fixed_rows_are_stable(dtype):
    scorer = BigramScorer.from_sequences([[0, 1, 2]] * 8, 4)
    selector = BigramViterbiSelector(scorer, scoring_method="pmi", remasking_confidence="viterbi_margin")
    logits = torch.tensor([[10000., -10000., 0., -10000.]] * 256, dtype=dtype)
    current = torch.full((256,), 3)
    editable = torch.arange(256) % 3 != 1
    selected, confidence = selector.select_block(logits, current, editable, top_k=4, repetition_penalty_strength=1e6)
    assert torch.equal(selected[~editable], current[~editable])
    assert torch.isfinite(confidence).all()
    assert not torch.isnan(selector.last_path_margins).any()


@pytest.mark.parametrize("strength", [-1., float("nan"), float("inf"), 1e300])
def test_invalid_or_overflowing_strength_has_clear_error(strength):
    with pytest.raises(ValueError, match="strength"):
        expected_bigram_repetition_penalties(torch.zeros(3, 1, dtype=torch.long), torch.ones(3, 1), 1, strength)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA unavailable")
def test_expected_penalty_cuda_matches_cpu():
    ids = torch.tensor([[0, 1], [1, 0], [0, 1], [1, 0]])
    p = torch.tensor([[.3, .2], [.4, .1], [.2, .5], [.1, .2]])
    expected = expected_bigram_repetition_penalties(ids, p, 2)
    torch.testing.assert_close(expected_bigram_repetition_penalties(ids.cuda(), p.cuda(), 2).cpu(), expected)
