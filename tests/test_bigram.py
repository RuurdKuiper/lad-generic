import itertools

import pytest
import torch

from diffusion_lm.bigram import BigramScorer, BigramViterbiSelector


def scorer():
    return BigramScorer.from_sequences([[0, 1, 2, 3]] * 20 + [[1, 1, 0]] * 3, 8)


def test_single_and_zero_weight():
    ids = torch.tensor([[1, 2], [3, 4]])
    logits = torch.tensor([[0., 1.], [2., -1.]])
    assert BigramViterbiSelector(scorer())(ids[:1], logits[:1]).tolist() == [2]
    assert BigramViterbiSelector(scorer(), 0)(ids, logits).tolist() == [2, 3]


@pytest.mark.parametrize('length', [1, 8, 32, 128, 256])
def test_lengths(length):
    torch.manual_seed(length)
    ids = torch.randint(0, 8, (length, 16))
    logits = torch.randn(length, 16)
    selected = BigramViterbiSelector(scorer())(ids, logits)
    assert selected.shape == (length,)
    assert (selected[:, None] == ids).any(-1).all()


def test_global_optimum_and_emissions_counted_once():
    ids = torch.tensor([[0, 1], [2, 3], [4, 5]])
    emissions = torch.tensor([[0., -0.3], [0., -1.], [0., -1.]])
    transitions = torch.tensor([[[-5., -5.], [0., -5.]], [[0., -5.], [-5., -5.]]])
    # Greedy commits to first candidate, but the optimal path starts with 1.
    path = BigramViterbiSelector.decode(ids, emissions, transitions, 0.5)
    assert path.tolist() == [1, 2, 4]
    for weight in [0.1, 0.5, 2.0]:
        paths = list(itertools.product(range(2), repeat=3))
        def objective(p):
            return sum(emissions[t, j] for t, j in enumerate(p)) + weight * sum(transitions[t, p[t], p[t+1]] for t in range(2))
        expected = max(paths, key=objective)
        actual = BigramViterbiSelector.decode(ids, emissions, transitions, weight)
        assert actual.tolist() == ids[torch.arange(3), torch.tensor(expected)].tolist()
    # Double-counting the first emission would flip this decision.
    two_ids = torch.tensor([[0, 1], [2, 3]])
    e = torch.tensor([[0., -1.], [0., -100.]])
    tr = torch.tensor([[[-1.5, -100.], [0., -100.]]])
    assert BigramViterbiSelector.decode(two_ids, e, tr, 1.).tolist() == [1, 2]


def test_sparse_backoff_normalizes_and_roundtrips(tmp_path):
    model = scorer()
    prev = torch.arange(8)[:, None]
    nxt = torch.arange(8)[None, :]
    probs = model.log_prob(prev, nxt).exp()
    assert torch.allclose(probs.sum(-1), torch.ones(8), atol=1e-6)
    assert torch.isfinite(probs).all() and (probs > 0).all()
    assert probs[0, 1] > probs[0, 7]  # Seen vs unseen/special token.
    path = tmp_path / 'model.pt'
    model.save(path)
    assert torch.equal(model.log_prob(prev, nxt), BigramScorer.load(path).log_prob(prev, nxt))
    assert model.pair_keys.numel() < 8**2
    with pytest.raises(FileNotFoundError, match='unavailable'):
        BigramScorer.load(tmp_path / 'missing.pt')
    class WrongTokenizer:
        def get_vocab(self):
            return {'wrong': 0}
    with pytest.raises(ValueError, match='tokenizer'):
        BigramScorer.load(path, tokenizer=WrongTokenizer())


def test_empty_counts_and_no_cross_document_pairs():
    empty = BigramScorer.from_sequences([], 8)
    assert empty.log_prob(torch.tensor(0), torch.arange(8)).exp().sum().item() == pytest.approx(1.)
    model = BigramScorer.from_sequences([[0, 1], [2, 3]], 8)
    assert (1 * 8 + 2) not in model.pair_keys
    with pytest.raises(ValueError, match='outside'):
        model.log_prob(torch.tensor(8), torch.tensor(0))


def test_fixed_tokens_and_both_boundaries_are_real_adjacencies():
    model = scorer()
    selector = BigramViterbiSelector(model, 0.7)
    logits = torch.tensor([[1., 0., 0., 0., 0., 0., 0., 0.]] * 3)
    current = torch.tensor([7, 2, 7])
    editable = torch.tensor([True, False, True])
    selected, confidence = selector.select_block(logits, current, editable, top_k=8, left_id=0, right_id=3)
    assert selected[1] == 2
    emissions = logits.log_softmax(-1)
    def objective(path):
        seq = torch.tensor([0, *path, 3])
        return emissions[0, path[0]] + emissions[2, path[2]] + 0.7 * model.log_prob(seq[:-1], seq[1:]).sum()
    expected = max(([a, 2, c] for a in range(8) for c in range(8)), key=objective)
    assert selected.tolist() == expected
    assert torch.allclose(confidence, emissions.gather(1, selected[:, None]).squeeze(1).exp())
    fixed, _ = selector.select_block(logits, current, torch.zeros(3, dtype=torch.bool))
    assert torch.equal(fixed, current)


def test_zero_weight_full_logits_is_argmax_with_constraints():
    torch.manual_seed(7)
    logits = torch.randn(8, 8)
    current = torch.arange(8)
    editable = current % 2 == 0
    selected, _ = BigramViterbiSelector(scorer(), 0).select_block(logits, current, editable)
    assert torch.equal(selected, torch.where(editable, logits.argmax(-1), current))


@pytest.mark.parametrize('method', ['conditional', 'pmi'])
@pytest.mark.skipif(not torch.cuda.is_available(), reason='CUDA unavailable')
def test_cpu_cuda_agree(method):
    torch.manual_seed(10)
    model = scorer()
    ids, emissions = torch.randint(0, 8, (128, 16)), torch.randn(128, 16)
    expected = BigramViterbiSelector(model, scoring_method=method)(ids, emissions)
    transitions = model(ids, emissions, scoring_method=method)
    model = model.to('cuda')
    assert torch.allclose(model(ids.cuda(), emissions.cuda(), scoring_method=method).cpu(), transitions, atol=1e-5)
    assert torch.equal(BigramViterbiSelector(model, scoring_method=method)(ids.cuda(), emissions.cuda()).cpu(), expected)


@pytest.mark.parametrize('method', ['conditional', 'pmi'])
def test_denoising_preserves_fixed_context_and_forward_count(method):
    from pathlib import Path
    from diffusion_lm.inference import InferenceSession, denoise_stream
    class Tokenizer:
        eos_token_id = 2
        chat_template = 'template'
        name_or_path = 'toy'
        def apply_chat_template(self, *_args, **_kwargs):
            return [1]
        def decode(self, ids, **kwargs):
            return ' '.join(map(str, ids))
    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.zeros(1))
            self.inputs = []
        def forward(self, input_ids, **kwargs):
            self.inputs.append(input_ids.clone())
            logits = torch.zeros((*input_ids.shape, 8))
            logits[..., 3 if len(self.inputs) % 2 else 4] = 4.
            return type('Output', (), dict(logits=logits))()
    class RecordingSelector(BigramViterbiSelector):
        def __init__(self):
            super().__init__(scorer(), 0.5, scoring_method=method)
            self.calls = []
        def select_block(self, logits, current_ids, editable, **kwargs):
            result = super().select_block(logits, current_ids, editable, **kwargs)
            self.calls.append((current_ids.clone(), editable.clone(), kwargs, result[0].clone()))
            return result
    model, selector = Model(), RecordingSelector()
    session = InferenceSession(model, Tokenizer(), torch.device('cpu'), Path('.'), {}, 7)
    states = list(denoise_stream(session, 'Q', 'S', 5, 6, 1., .7, 3, 123,
                                permanent_unmask=True, block_length=3, bigram_selector=selector))
    assert len(states) == len(model.inputs) == len(selector.calls) == 6
    assert [len(c[0]) for c in selector.calls] == [3, 3, 3, 2, 2, 2]
    for current, editable, kwargs, selected in selector.calls:
        assert torch.equal(current[~editable], selected[~editable])
    assert (~selector.calls[1][1]).any()  # A token is frozen after the first step.
    assert all(call[2]['top_k'] == 3 and call[2]['temperature'] == .7 for call in selector.calls)
    assert selector.calls[0][2]['left_id'] == 1  # Prompt boundary.
    assert selector.calls[3][2]['left_id'] == int(model.inputs[3][0, 3])
    assert selector.calls[0][2]['right_id'] is None  # No transition to future masks.


def pmi_scorer():
    # Singleton documents count toward ordinary unigrams but never successors.
    return BigramScorer.from_sequences([[0, 1]] * 5 + [[2, 1]] * 15 + [[0, 2]] * 10 + [[3]] * 1000,
                                       4, alpha=2., beta=.5)


def test_pmi_known_probabilities_use_successor_marginal():
    model = pmi_scorer()
    assert model.successor_counts.tolist() == [0., 20., 10., 0.]
    assert torch.allclose(model.successor_unigram, torch.tensor([.5, 20.5, 10.5, .5]) / 32)
    assert torch.isfinite(model.successor_unigram.log()).all()
    expected_conditional = torch.log(torch.tensor((5 + 2 * 20.5 / 1062) / 17))
    expected_pmi = expected_conditional - torch.log(torch.tensor(20.5 / 32))
    actual = model.transition_score(torch.tensor(0), torch.tensor(1), scoring_method='pmi')
    assert actual.item() == pytest.approx(expected_pmi.item())
    assert model.log_prob(torch.tensor(0), torch.tensor(1)).item() == pytest.approx(expected_conditional.item())
    assert not torch.allclose(model.unigram, model.successor_unigram)


def test_pmi_rare_unseen_threshold_and_two_sided_clipping():
    model = pmi_scorer()
    previous, following = torch.tensor([0, 0, 2]), torch.tensor([1, 2, 2])
    raw = model.transition_score(previous, following, scoring_method='pmi')
    assert raw[0] < -.1 and raw[1] > .1 and raw[2] == 0
    clipped = model.transition_score(previous, following, scoring_method='pmi', pmi_clip=.1)
    assert torch.allclose(clipped, torch.tensor([-.1, .1, 0.]))
    guarded = model.transition_score(previous, following, scoring_method='pmi', min_count=6)
    assert guarded[0] == 0 and guarded[1] != 0 and guarded[2] == 0  # Exactly five is eligible by default.
    assert model.transition_score(torch.tensor(2), torch.tensor(2), scoring_method='pmi', min_count=0) == 0
    rare = BigramScorer.from_sequences([[0, 1]] * 4, 4)
    assert rare.transition_score(torch.tensor(0), torch.tensor(1), scoring_method='pmi') == 0
    empty = BigramScorer.from_sequences([], 4)
    assert empty.transition_score(torch.tensor(0), torch.tensor(1), scoring_method='pmi') == 0


def test_v1_checkpoint_reconstructs_exact_successor_counts_without_changing_conditionals(tmp_path):
    model = pmi_scorer()
    old = dict(version=1, vocab_size=4, pair_keys=model.pair_keys, pair_counts=model.pair_counts,
               unigram_counts=model.unigram_counts, alpha=2., beta=.5, metadata={})
    old_path, new_path = tmp_path / 'old.pt', tmp_path / 'new.pt'
    torch.save(old, old_path)
    restored = BigramScorer.load(old_path)
    restored.save(new_path)
    new = BigramScorer.load(new_path)
    a, b = torch.arange(4)[:, None], torch.arange(4)[None, :]
    original_formula = (model._lookup_counts(a, b) + 2 * model.unigram[b]).log() - (model.row_totals[a] + 2).log()
    for candidate in [restored, new]:
        assert torch.equal(candidate.log_prob(a, b), original_formula)
        assert torch.equal(candidate.successor_counts, model.successor_counts)
        assert torch.equal(candidate.transition_score(a, b, scoring_method='pmi'), model.transition_score(a, b, scoring_method='pmi'))
    state = torch.load(new_path, weights_only=True)
    assert state['version'] == 2 and 'unigram_counts' in state and 'successor_counts' in state


@pytest.mark.parametrize('length', [1, 8, 32, 128, 256])
@pytest.mark.parametrize('method', ['conditional', 'pmi'])
def test_both_scoring_modes_lengths_and_zero_weight(length, method):
    torch.manual_seed(length)
    model = scorer()
    logits = torch.randn(length, 8)
    current = torch.zeros(length, dtype=torch.long)
    editable = torch.ones(length, dtype=torch.bool)
    selected, _ = BigramViterbiSelector(model, .5, scoring_method=method).select_block(logits, current, editable)
    assert selected.shape == (length,)
    independent, _ = BigramViterbiSelector(model, 0., scoring_method=method).select_block(
        logits, current, editable, left_id=1, right_id=2)
    assert torch.equal(independent, logits.argmax(-1))


def test_pmi_fixed_tokens_and_boundary_objective():
    model = pmi_scorer()
    logits = torch.tensor([[.2, 0., 0., 0.]] * 3)
    current, editable = torch.tensor([0, 1, 0]), torch.tensor([True, False, True])
    selected, _ = BigramViterbiSelector(model, .5, scoring_method='pmi').select_block(
        logits, current, editable, top_k=4, left_id=0, right_id=2)
    def objective(path):
        seq = torch.tensor([0, *path, 2])
        return logits[0, path[0]] + logits[2, path[2]] + .5 * model.transition_score(seq[:-1], seq[1:], scoring_method='pmi').sum()
    expected = max(([a, 1, b] for a in range(4) for b in range(4)), key=objective)
    assert selected.tolist() == expected


@pytest.mark.parametrize('kwargs', [dict(scoring_method='wrong'), dict(min_count=-1), dict(min_count=1.5),
                                   dict(pmi_clip=-1), dict(pmi_clip=float('nan'))])
def test_invalid_pmi_configuration(kwargs):
    with pytest.raises(ValueError):
        BigramViterbiSelector(scorer(), **kwargs)


def test_profiled_selector_counts_only_editable_same_logit_changes():
    from diffusion_lm.bigram_evaluation import ProfiledBigramSelector
    model = scorer()
    logits = torch.tensor([[1., 0., 0., 0., 0., 0., 0., 0.]] * 3)
    current, editable = torch.tensor([0, 7, 0]), torch.tensor([True, False, True])
    selector = BigramViterbiSelector(model, .5, scoring_method='pmi')
    measured = ProfiledBigramSelector(selector)
    expected = selector.select_block(logits, current, editable)
    actual = measured.select_block(logits, current, editable)
    assert torch.equal(expected[0], actual[0]) and torch.equal(expected[1], actual[1])
    metrics = measured.metrics()
    assert metrics['selector_calls'] == 1 and metrics['editable_predictions'] == 2
    assert metrics['changed_predictions'] == int(((actual[0] != logits.argmax(-1)) & editable).sum())
    assert metrics['changed_fraction'] == metrics['changed_predictions'] / 2
    assert metrics['selector_ms'] >= 0
    measured = ProfiledBigramSelector(BigramViterbiSelector(model, 0., scoring_method='pmi'))
    measured.select_block(logits, current, editable)
    assert measured.metrics()['changed_fraction'] == 0


def test_checkpoint_rejects_inconsistent_saved_successor_counts(tmp_path):
    model = pmi_scorer()
    path = tmp_path / 'bad.pt'
    model.save(path)
    state = torch.load(path, weights_only=True)
    state['successor_counts'][0] += 1
    torch.save(state, path)
    with pytest.raises(ValueError, match='Successor counts'):
        BigramScorer.load(path)


@pytest.mark.parametrize('method', ['conditional', 'pmi'])
def test_zero_weight_matches_full_argmax_for_bfloat16_ties(method):
    logits = torch.ones(8, 8, dtype=torch.bfloat16)
    current = torch.full((8,), 7, dtype=torch.long)
    editable = torch.arange(8) % 2 == 0
    selected, _ = BigramViterbiSelector(scorer(), 0., scoring_method=method).select_block(
        logits, current, editable, top_k=4, left_id=2, right_id=3)
    assert torch.equal(selected, torch.where(editable, logits.argmax(-1), current))
