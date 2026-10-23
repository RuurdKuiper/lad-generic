import pytest
import torch
from diffusion_lm.bigram import BigramScorer, BigramViterbiSelector
from test_trigram import scorers


def test_gumbel_transform_fixed_rows_and_extreme_uniforms(monkeypatch):
    u = torch.tensor([[0.0, -1.0], [0.0, -torch.inf], [1.0, 2.0]])
    editable = torch.tensor([True, False, True])
    uniform = torch.tensor([[0.0, 1.0], [0.1, 0.9], [0.25, 0.75]])
    monkeypatch.setattr(torch, "rand_like", lambda _: uniform.clone())
    result = BigramViterbiSelector.perturb_unaries(u, editable, 0.7)
    eps = torch.finfo(u.dtype).eps
    expected = u - 0.7 * torch.log(
        -torch.log(uniform.clamp(torch.finfo(u.dtype).tiny, 1 - eps))
    )
    torch.testing.assert_close(result[editable], expected[editable])
    assert torch.equal(result[~editable], u[~editable])
    assert torch.isfinite(result[editable]).all()


@pytest.mark.parametrize("trigrams", [False, True])
@pytest.mark.parametrize("temperature", [0.0, 0.7])
def test_randomized_seed_zero_equivalence_fixed_tokens_and_diffusion_confidence(
    trigrams, temperature
):
    bigram, tri = scorers()
    opts = dict(
        weight=1.0,
        scoring_method="pmi",
        min_count=1,
        independent_temperature=True,
        trigram_scorer=tri if trigrams else None,
    )
    base = BigramViterbiSelector(bigram, **opts)
    randomized = BigramViterbiSelector(bigram, **opts, randomized_viterbi=True)
    logits = torch.randn(12, 4, generator=torch.Generator().manual_seed(8))
    current = torch.full((12,), 2)
    editable = torch.arange(12) % 3 != 1
    torch.manual_seed(42)
    state = torch.get_rng_state().clone()
    a, confidence = randomized.select_block(
        logits, current, editable, top_k=4, temperature=temperature
    )
    if temperature == 0:
        assert torch.equal(state, torch.get_rng_state())
        b, c = base.select_block(
            logits, current, editable, top_k=4, temperature=temperature
        )
        assert torch.equal(a, b) and torch.equal(c, confidence)
    torch.manual_seed(42)
    b, _ = randomized.select_block(
        logits, current, editable, top_k=4, temperature=temperature
    )
    assert torch.equal(a, b)
    assert torch.equal(a[~editable], current[~editable])
    torch.testing.assert_close(
        confidence, logits.softmax(-1).gather(1, a[:, None]).squeeze(1)
    )


def test_randomized_path_varies_with_seed_and_works_at_zero_ngram_weight():
    scorer = BigramScorer.from_sequences([[0, 1, 2]], 3)
    selector = BigramViterbiSelector(
        scorer, weight=0.0, randomized_viterbi=True, independent_temperature=True
    )
    outputs = set()
    for seed in range(8):
        torch.manual_seed(seed)
        ids, _ = selector.select_block(
            torch.zeros(8, 3),
            torch.zeros(8, dtype=torch.long),
            torch.ones(8, dtype=torch.bool),
            top_k=3,
            temperature=0.7,
        )
        outputs.add(tuple(ids.tolist()))
    assert len(outputs) > 1


def test_conflicting_sampling_modes_rejected():
    with pytest.raises(ValueError, match="either"):
        BigramViterbiSelector(
            BigramScorer.from_sequences([[0, 1]], 2),
            sequence_sampling=True,
            randomized_viterbi=True,
        )


@pytest.mark.parametrize(
    "native,exact,override,expected",
    [
        (True, False, None, True),
        (True, True, None, False),
        (True, True, True, False),
        (True, False, False, False),
        (True, False, True, True),
        (False, False, None, False),
    ],
)
def test_app_temperature_defaults_and_explicit_legacy_overrides(
    native, exact, override, expected
):
    import ast
    from pathlib import Path
    from types import SimpleNamespace

    source = Path(__file__).parents[1] / "huggingface/byod_space/app.py"
    tree = ast.parse(source.read_text())
    fn = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "generate"
    )
    fn.decorator_list = []
    bigram, _ = scorers()
    captured = {}

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
        SESSION=SimpleNamespace(device="cpu", llada=native),
        _bigram_scorer=lambda p: bigram,
        BigramViterbiSelector=BigramViterbiSelector,
        denoise_stream=stream,
    )
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "app", "exec"), ns)
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
            "Bigram Viterbi",
            False,
            4,
            True,
            False,
            generation_seed=42,
            sequence_sampling=exact,
            randomized_viterbi=override,
        )
    )
    selector = captured["bigram_selector"]
    assert selector.randomized_viterbi is expected
    assert selector.sequence_sampling is exact
    assert captured["temperature"] == 0.7
