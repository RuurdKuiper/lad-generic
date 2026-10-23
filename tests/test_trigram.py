from collections import Counter
import itertools
import math

import pytest
import torch

from diffusion_lm.bigram import (
    BigramScorer,
    BigramViterbiSelector,
    RepetitionPenalizedBigramSelector,
)
from diffusion_lm.trigram import (
    TrigramScorer,
    decode_second_order,
    sample_second_order,
    second_order_marginals,
    second_order_path_margins,
)


def scorers():
    sequences = [[0, 1, 2]] * 12 + [[0, 1, 3]] * 6 + [[2, 1, 2]] * 4 + [[3, 2, 1]]
    bigram = BigramScorer.from_sequences(sequences, 4)
    triples = Counter(
        (a * 4 + b) * 4 + c for s in sequences for a, b, c in zip(s, s[1:], s[2:])
    )
    prefixes = Counter(a * 4 + b for s in sequences for a, b, c in zip(s, s[1:], s[2:]))
    return bigram, TrigramScorer(
        4,
        sorted(triples),
        [triples[k] for k in sorted(triples)],
        sorted(prefixes),
        [prefixes[k] for k in sorted(prefixes)],
    )


def test_smoothed_correction_known_counts_unseen_rare_and_clipping():
    bigram, trigram = scorers()
    a, b, c = map(torch.tensor, [0, 1, 2])
    base = bigram.log_prob(b, c).exp().item()
    expected = math.log((12 + 50 * base) / (18 + 50)) - math.log(base)
    assert trigram.correction(
        a, b, c, bigram, min_count=5, clip=10.0
    ).item() == pytest.approx(expected, abs=1e-6)
    assert (
        trigram.correction(
            torch.tensor(3), torch.tensor(3), torch.tensor(3), bigram
        ).item()
        == 0.0
    )
    assert (
        trigram.correction(
            torch.tensor(3), torch.tensor(2), torch.tensor(1), bigram
        ).item()
        == 0.0
    )
    assert (
        abs(trigram.correction(a, b, c, bigram, min_count=1, clip=0.01).item())
        <= 0.010001
    )


def test_compact_checkpoint_rejects_unavailable_lower_count_threshold():
    bigram, trigram = scorers()
    trigram.metadata["storage_min_count"] = 2
    a, b, c = map(torch.tensor, [0, 1, 2])
    assert torch.isfinite(trigram.correction(a, b, c, bigram))
    with pytest.raises(ValueError, match="storage threshold"):
        trigram.correction(a, b, c, bigram, min_count=1)


def lattice(length=4):
    g = torch.Generator().manual_seed(4)
    ids = torch.tensor([[0, 1]] * length)
    unary = torch.randn(length, 2, generator=g)
    if length > 2:
        unary[1, 0] = -torch.inf
    edges = torch.randn(max(0, length - 1), 2, 2, generator=g)
    triples = torch.randn(max(0, length - 2), 2, 2, 2, generator=g)
    return ids, unary, edges, triples


def enumerated(unary, edges, triples):
    paths = list(itertools.product(range(unary.shape[1]), repeat=len(unary)))
    values = torch.tensor(
        [
            sum(unary[t, p[t]] for t in range(len(p)))
            + sum(edges[t, p[t], p[t + 1]] for t in range(len(p) - 1))
            + sum(triples[t, p[t], p[t + 1], p[t + 2]] for t in range(len(p) - 2))
            for p in paths
        ]
    )
    return paths, values


@pytest.mark.parametrize("length", [1, 2, 3, 4, 6])
def test_exact_second_order_viterbi_and_margins(length):
    ids, unary, edges, triples = lattice(length)
    paths, values = enumerated(unary, edges, triples)
    selected = decode_second_order(ids, unary, edges, triples)
    assert selected.tolist() == list(paths[int(values.argmax())])
    margins = second_order_path_margins(ids, unary, edges, triples, selected)
    for t in range(length):
        others = [float(v) for p, v in zip(paths, values) if p[t] != selected[t]]
        expected = float(values.max()) - max(others)
        if math.isinf(expected):
            assert math.isinf(margins[t])
        else:
            assert margins[t].item() == pytest.approx(expected, abs=2e-6)


@pytest.mark.parametrize("temperature", [0.4, 1.0, 2.0])
def test_second_order_joint_pair_marginals_match_enumeration(temperature):
    _, unary, edges, triples = lattice(4)
    paths, values = enumerated(unary, edges, triples)
    probabilities = (values / temperature).softmax(0)
    expected = torch.zeros_like(edges)
    for path, prob in zip(paths, probabilities):
        for t in range(3):
            expected[t, path[t], path[t + 1]] += prob
    actual = second_order_marginals(unary, edges, triples, temperature)
    torch.testing.assert_close(actual, expected, atol=2e-6, rtol=2e-6)


def test_second_order_sampling_matches_enumerated_distribution_and_seed():
    ids, unary, edges, triples = lattice(3)
    paths, values = enumerated(unary, edges, triples)
    expected = values.softmax(0)
    torch.manual_seed(5)
    counts = Counter(
        tuple(sample_second_order(ids, unary, edges, triples).tolist())
        for _ in range(2000)
    )
    observed = torch.tensor([counts[p] / 2000 for p in paths])
    torch.testing.assert_close(observed, expected, atol=0.035, rtol=0.0)
    assert torch.equal(
        sample_second_order(ids, unary, edges, triples, 0.0),
        decode_second_order(ids, unary, edges, triples),
    )


@pytest.mark.parametrize("sampling", [False, True])
@pytest.mark.parametrize("length", [1, 2, 8, 64, 256])
def test_zero_trigram_weight_is_exact_and_fixed_rows_remain_fixed(sampling, length):
    bigram, trigram = scorers()
    base = BigramViterbiSelector(
        bigram,
        weight=1.0,
        scoring_method="pmi",
        min_count=1,
        sequence_sampling=sampling,
        independent_temperature=True,
    )
    new = BigramViterbiSelector(
        bigram,
        weight=1.0,
        scoring_method="pmi",
        min_count=1,
        sequence_sampling=sampling,
        independent_temperature=True,
        trigram_scorer=trigram,
        trigram_weight=0.0,
    )
    logits = torch.randn(length, 4, generator=torch.Generator().manual_seed(8))
    current = torch.zeros(length, dtype=torch.long)
    editable = torch.arange(length) % 3 != 1
    torch.manual_seed(9)
    old = base.select_block(logits, current, editable, top_k=3)
    torch.manual_seed(9)
    actual = new.select_block(logits, current, editable, top_k=3)
    assert all(torch.equal(a, b) for a, b in zip(old, actual))
    new.trigram_weight = 0.5
    selected, confidence = new.select_block(logits, current, editable, top_k=3)
    assert torch.equal(selected[~editable], current[~editable])
    torch.testing.assert_close(
        confidence, logits.softmax(-1).gather(1, selected[:, None]).squeeze(1)
    )


@pytest.mark.parametrize("mode", ["expected", "candidate_occurrences", "risk"])
@pytest.mark.parametrize("sampling", [False, True])
def test_trigrams_compose_with_repetition_fade_apd_quota_and_no_extra_forwards(
    mode, sampling
):
    from test_apd import session
    from diffusion_lm.inference import denoise_stream

    s = session(native=True, distribution="uniform")
    sequences = [[1, 2, 3]] * 10
    bigram = BigramScorer.from_sequences(sequences, 8)
    tri = TrigramScorer(8, [(1 * 8 + 2) * 8 + 3], [10], [1 * 8 + 2], [10])
    base = BigramViterbiSelector(
        bigram,
        weight=1.0,
        scoring_method="pmi",
        min_count=1,
        sequence_sampling=sampling,
        independent_temperature=True,
        trigram_scorer=tri,
    )
    selector = RepetitionPenalizedBigramSelector(
        base, 1.0, count_mode=mode, decay_steps=6, excluded_token_ids=(4, 5)
    )
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
            bigram_selector=selector,
            adaptive_parallel_decoding=True,
        )
    )
    assert len(states) == len(s.model.inputs) == 4
    assert "masked at iteration" not in states[-1][2]


def test_large_log_scores_and_single_legal_path_are_stable():
    from diffusion_lm.trigram import _decode_second_order_host

    ids, unary, edges, triples = lattice(64)
    unary[:] = torch.tensor([10000.0, -torch.inf])
    edges *= 10000
    triples *= 10000
    assert decode_second_order(ids, unary, edges, triples).eq(0).all()
    assert _decode_second_order_host(ids, unary, edges, triples).eq(0).all()
    assert sample_second_order(ids, unary, edges, triples, 0.01).eq(0).all()
    marginals = second_order_marginals(unary, edges, triples, 0.01)
    assert torch.isfinite(marginals).all()
    assert marginals[:, 0, 0].eq(1).all()


@pytest.mark.parametrize(
    "choice", ["Original bigram", "Expanded bigram", "Expanded bigram + trigram"]
)
def test_hosted_app_routes_optional_corpus_and_trigram_without_loading_model(choice):
    import ast
    from pathlib import Path
    from types import SimpleNamespace

    source = Path(__file__).parents[1] / "huggingface/byod_space/app.py"
    tree = ast.parse(source.read_text())
    function = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "generate"
    )
    function.decorator_list = []
    bigram, trigram = scorers()
    captured = {}
    paths = []

    def get_scorer(path):
        paths.append(path)
        return bigram

    def stream(session, **kwargs):
        captured.update(kwargs)
        yield "text", "status", "html"

    ns = dict(
        BIGRAM_PATH="old.pt",
        BIGRAM_ENABLED=True,
        BIGRAM_SCORING_METHOD="PMI bigram",
        BIGRAM_REMASKING_CONFIDENCE="Diffusion probability",
        PMI_MIN_COUNT=1,
        PMI_CLIP=2.0,
        BIGRAM_ENDING_DELAY_STRENGTH=10.0,
        EXPANDED_BIGRAM_PATH="expanded.pt",
        TRIGRAM_PATH="tri.pt",
        TRIGRAM_RELATIVE_WEIGHT=0.5,
        TRIGRAM_MIN_COUNT=2,
        TRIGRAM_CLIP=2.0,
        SESSION=SimpleNamespace(device="cpu", llada=True),
        _bigram_scorer=get_scorer,
        _trigram_scorer=lambda *a: trigram,
        BigramViterbiSelector=BigramViterbiSelector,
        denoise_stream=stream,
    )
    exec(compile(ast.Module(body=[function], type_ignores=[]), "app", "exec"), ns)
    list(
        ns["generate"](
            "Q",
            "S",
            32,
            8,
            32,
            1.0,
            16,
            0.0,
            "No coloring",
            "Bigram Viterbi",
            False,
            4,
            True,
            False,
            generation_seed=1,
            ngram_guidance=choice,
        )
    )
    selector = captured["bigram_selector"]
    assert paths == ["old.pt" if choice == "Original bigram" else "expanded.pt"]
    assert (selector.trigram_scorer is trigram) == (
        choice == "Expanded bigram + trigram"
    )


def test_chunked_sparse_lookups_match_full_lattice(monkeypatch):
    import diffusion_lm.trigram as module

    bigram, trigram = scorers()
    ids = torch.tensor([[0, 1, 2], [1, 2, 3], [2, 3, 0], [0, 1, 2], [1, 2, 3]])
    expected = trigram.lattice_corrections(ids, bigram, min_count=1)
    monkeypatch.setattr(module, "MAX_TRIGRAM_LOOKUP_ELEMENTS", 1)
    assert torch.equal(trigram.lattice_corrections(ids, bigram, min_count=1), expected)


@pytest.mark.parametrize("length,k", [(3, 1), (8, 4), (128, 16), (256, 8)])
@pytest.mark.parametrize("min_count,clip", [(1, 2.0), (2, 0.0), (5, 0.1)])
def test_factored_lattice_is_identical_to_direct_triple_scores(
    length, k, min_count, clip
):
    bigram, trigram = scorers()
    ids = torch.randint(4, (length, k), generator=torch.Generator().manual_seed(19))
    # Repeated candidates model singleton fixed rows without dropping their
    # actual sequence positions or their context contributions.
    ids[1::3] = ids[1::3, :1]
    direct = trigram.correction(
        ids[:-2, :, None, None],
        ids[1:-1, None, :, None],
        ids[2:, None, None, :],
        bigram,
        min_count=min_count,
        clip=clip,
    )
    actual = trigram.lattice_corrections(ids, bigram, min_count=min_count, clip=clip)
    assert torch.equal(actual, direct)


@pytest.mark.parametrize("length", [1, 2, 3, 4, 6])
@pytest.mark.parametrize("seed", [2, 6, 19])
def test_traceback_matches_exhaustive_optimum_and_original_tie_order(length, seed):
    g = torch.Generator().manual_seed(seed)
    k = 3
    ids = torch.arange(k).expand(length, -1)
    unary = torch.randint(-2, 3, (length, k), generator=g).float()
    edges = torch.randint(-2, 3, (max(0, length - 1), k, k), generator=g).float()
    triples = torch.randint(-2, 3, (max(0, length - 2), k, k, k), generator=g).float()
    # Fix some positions to a nonzero candidate, including consecutive rows.
    for t in range(length):
        if t % 3 != 0:
            unary[t, :2] = -torch.inf
    paths, values = enumerated(unary, edges, triples)
    best = [p for p, v in zip(paths, values) if v == values.max()]
    # The old decoder first chose the lowest final pair, then the lowest
    # predecessor on each right-to-left traceback step.
    key = lambda p: p if length < 3 else (p[-2], p[-1], *reversed(p[:-2]))
    expected = min(best, key=key)
    assert decode_second_order(ids, unary, edges, triples).tolist() == list(expected)
    from diffusion_lm.trigram import _decode_second_order_host

    assert _decode_second_order_host(ids, unary, edges, triples).tolist() == list(
        expected
    )
    if length >= 2:
        from diffusion_lm.trigram import _potentials, _forward, _traceback_device

        # Exercise the GPU-oriented tensor-only path even on CPU test hosts.
        u, e, t = _potentials(unary, edges, triples)
        forward, back = _forward(u, e, t, maximum=True)
        actual = _traceback_device(back, forward[-1].reshape(-1).argmax(), k)
        assert ids.gather(1, actual[:, None]).squeeze(1).tolist() == list(expected)


@pytest.mark.parametrize(
    "length,k", [(1, 1), (2, 16), (8, 4), (128, 8), (128, 16), (256, 16)]
)
@pytest.mark.parametrize("device", ["cpu", "cuda"])
def test_host_map_matches_original_device_recurrence(length, k, device):
    if device == "cuda" and not torch.cuda.is_available():
        pytest.skip("CUDA unavailable")
    from diffusion_lm.trigram import (
        _decode_second_order_host,
        _potentials,
        _forward,
        _traceback_device,
    )

    for seed in range(12):
        g = torch.Generator().manual_seed(seed)
        ids = torch.arange(length * k).reshape(length, k).to(device)
        u = torch.randn(length, k, generator=g).to(device)
        e = torch.randn(length - 1, k, k, generator=g).to(device)
        tri = torch.randn(max(0, length - 2), k, k, k, generator=g).to(device)
        u[1::3, 1:] = -torch.inf
        unary, edges, triples = _potentials(u, e, tri)
        if length == 1:
            expected = ids.gather(1, unary.argmax(-1, keepdim=True)).squeeze(1)
        else:
            forward, back = _forward(unary, edges, triples, maximum=True)
            path = _traceback_device(back, forward[-1].reshape(-1).argmax(), k)
            expected = ids.gather(1, path[:, None]).squeeze(1)
        assert torch.equal(_decode_second_order_host(ids, u, e, tri), expected)
