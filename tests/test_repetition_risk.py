import ast
import itertools
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from diffusion_lm.bigram import (
    BigramScorer,
    BigramViterbiSelector,
    RepetitionPenalizedBigramSelector,
)
from diffusion_lm.repetition_risk import (
    chain_bigram_marginals,
    repetition_risk_penalties,
)


@pytest.mark.parametrize("temperature", [0.0, 0.4, 1.0, 2.0])
def test_joint_marginals_match_exact_enumeration_with_fixed_row(temperature):
    emissions = torch.tensor([[0.2, -0.1], [-torch.inf, 0.0], [0.3, -0.4], [0.0, 0.1]])
    edges = torch.tensor([[[0.7, -0.4], [-0.2, 0.5]]] * 3)
    actual = chain_bigram_marginals(emissions, edges, temperature)
    paths = list(itertools.product(range(2), repeat=4))
    scores = torch.tensor(
        [
            sum(emissions[t, p[t]] for t in range(4))
            + sum(edges[t, p[t], p[t + 1]] for t in range(3))
            for p in paths
        ]
    )
    probabilities = (scores / (temperature or 1.0)).softmax(0)
    expected = torch.zeros_like(actual)
    for p, prob in zip(paths, probabilities):
        for t in range(3):
            expected[t, p[t], p[t + 1]] += prob
    torch.testing.assert_close(actual, expected, atol=2e-6, rtol=2e-6)
    torch.testing.assert_close(actual.sum((1, 2)), torch.ones(3))


def test_joint_pmi_changes_risk_even_when_diffusion_probabilities_are_unchanged():
    ids = torch.tensor([[0, 1]] * 4)
    unary = torch.zeros(4, 2)
    neutral = torch.zeros(3, 2, 2)
    guided = neutral.clone()
    guided[:, 0, 0] = 4.0
    low = repetition_risk_penalties(ids, unary, neutral, 2)
    high = repetition_risk_penalties(ids, unary, guided, 2)
    assert high[1, 0, 0] > low[1, 0, 0]


def test_risk_multiplier_is_half_after_point_one_prior_probability_and_grows():
    p = math.sqrt(0.1)
    unary = torch.tensor([[math.log(p), math.log(1 - p)]] * 4)
    ids = torch.tensor([[0, 1]] * 4)
    edges = torch.zeros(3, 2, 2)
    penalties = repetition_risk_penalties(ids, unary, edges, 2)
    assert penalties[0].eq(0).all()
    assert penalties[1, 0, 0].exp().reciprocal().item() == pytest.approx(0.5, abs=1e-6)
    risk = 1 - (1 - 0.1) ** 2
    assert (-penalties[2, 0, 0]).exp().item() == pytest.approx(
        (1 - risk) / (1 - risk + 9 * risk), abs=1e-6
    )
    assert penalties[2, 0, 0] > penalties[1, 0, 0]


def test_ending_pairs_exempt_and_counts_reset_with_fixed_dummy_columns():
    ids = torch.tensor([[0, 0, 0], [1, 1, 1]] * 3)
    unary = torch.full((6, 3), -torch.inf)
    unary[:, 0] = 0.0
    edges = torch.zeros(5, 3, 3)
    actual = repetition_risk_penalties(ids, unary, edges, 2)
    assert actual[0].eq(0).all()
    assert torch.isfinite(actual).all()
    # Certain first pair is bounded, not inflated by the K duplicate columns.
    assert actual[2, 0, 0].item() == pytest.approx(
        math.log((1e-7 + 9 * (1 - 1e-7)) / 1e-7), abs=0.3
    )
    assert (
        repetition_risk_penalties(ids, unary, edges, 2, excluded_token_ids=(1,))
        .eq(0)
        .all()
    )
    assert torch.equal(actual, repetition_risk_penalties(ids, unary, edges, 2))


@pytest.mark.parametrize("length", [1, 64, 256])
def test_extreme_scores_are_finite_and_singleton_lattices_work(length):
    ids = torch.tensor([[0, 1]] * length)
    unary = torch.tensor([[10000.0, -10000.0]] * length)
    edges = torch.full((length - 1, 2, 2), -10000.0)
    penalties = repetition_risk_penalties(
        ids, unary, edges, 2, 10.0, temperature=1e-300
    )
    assert torch.isfinite(penalties).all()
    single = repetition_risk_penalties(ids[:, :1], unary[:, :1], edges[:, :1, :1], 2)
    assert torch.isfinite(single).all()


@pytest.mark.parametrize("sampling", [False, True])
def test_risk_zero_strength_matches_original_and_fixed_tokens_survive(sampling):
    base = BigramViterbiSelector(
        BigramScorer.from_sequences([[0, 1, 2]] * 10, 3),
        weight=1.0,
        scoring_method="pmi",
        min_count=1,
        sequence_sampling=sampling,
        independent_temperature=True,
    )
    logits = torch.tensor([[0.3, 0.2, 0.1]] * 6)
    current = torch.tensor([0, 1, 2, 0, 1, 2])
    editable = torch.tensor([1, 0, 1, 1, 0, 1], dtype=torch.bool)
    torch.manual_seed(5)
    expected = base.select_block(logits, current, editable, top_k=3)
    torch.manual_seed(5)
    actual = RepetitionPenalizedBigramSelector(
        base, 0.0, count_mode="risk"
    ).select_block(logits, current, editable, top_k=3)
    assert all(torch.equal(a, b) for a, b in zip(actual, expected))
    selected, confidence = RepetitionPenalizedBigramSelector(
        base, 1.0, count_mode="risk"
    ).select_block(logits, current, editable, top_k=3)
    assert torch.equal(selected[~editable], current[~editable])
    torch.testing.assert_close(
        confidence, logits.softmax(-1).gather(1, selected[:, None]).squeeze(1)
    )


@pytest.mark.parametrize("sampling", [False, True])
@pytest.mark.parametrize("apd", [False, True])
def test_native_inference_no_extra_model_passes_or_unresolved_tokens(sampling, apd):
    from test_apd import session
    from diffusion_lm.inference import denoise_stream

    s = session(native=True, distribution="uniform")
    base = BigramViterbiSelector(
        BigramScorer.from_sequences([[1, 2, 3]] * 10, 8),
        weight=1.0,
        scoring_method="pmi",
        min_count=1,
        sequence_sampling=sampling,
        independent_temperature=True,
    )
    selector = RepetitionPenalizedBigramSelector(
        base, 1.0, count_mode="risk", excluded_token_ids=(4, 5)
    )
    states = list(
        denoise_stream(
            s,
            "Q",
            "S",
            6,
            4,
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
    assert len(states) == len(s.model.inputs) == 4
    assert "masked at iteration" not in states[-1][2]


def test_app_routes_optional_risk_and_gives_it_precedence_over_candidate_counts():
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
    namespace = dict(
        BIGRAM_PATH="x",
        BIGRAM_ENABLED=True,
        BIGRAM_SCORING_METHOD="PMI bigram",
        BIGRAM_REMASKING_CONFIDENCE="Diffusion probability",
        PMI_MIN_COUNT=1,
        PMI_CLIP=2.0,
        BIGRAM_ENDING_DELAY_STRENGTH=10.0,
        SESSION=SimpleNamespace(device="cpu", llada=True, tokenizer=object()),
        _bigram_scorer=lambda path: scorer,
        _ending_token_ids=lambda tok: {2},
        BigramViterbiSelector=BigramViterbiSelector,
        RepetitionPenalizedBigramSelector=RepetitionPenalizedBigramSelector,
        denoise_stream=stream,
    )
    exec(
        compile(ast.Module(body=[function], type_ignores=[]), "app", "exec"), namespace
    )
    list(
        namespace["generate"](
            "Q",
            "S",
            32,
            4,
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
            generation_seed=1,
            repetition_risk_penalty=True,
            count_all_candidate_bigrams=True,
        )
    )
    assert captured["bigram_selector"].count_mode == "risk"
