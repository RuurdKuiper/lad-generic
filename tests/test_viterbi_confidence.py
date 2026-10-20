import itertools
from pathlib import Path

import pytest
import torch

from diffusion_lm.bigram import BigramScorer, BigramViterbiSelector
from diffusion_lm.bigram_evaluation import ProfiledBigramSelector
from diffusion_lm.inference import InferenceSession, denoise_stream


def test_path_margins_match_exhaustive_complete_paths_with_constraints():
    ids = torch.tensor([[0, 1, 2], [3, 3, 3], [4, 5, 6]])
    emissions = torch.tensor([[-.1, -.2, -.3], [0., -torch.inf, -torch.inf], [-.1, -.5, -.8]])
    torch.manual_seed(42)
    transitions = torch.randn(2, 3, 3)
    selected = BigramViterbiSelector.decode(ids, emissions, transitions, .7)
    margins = BigramViterbiSelector.path_margins(ids, emissions, transitions, selected, .7)
    paths = list(itertools.product(range(3), repeat=3))
    def score(p):
        return sum(emissions[t, p[t]] for t in range(3)) + .7 * sum(transitions[t, p[t], p[t+1]] for t in range(2))
    for t in range(3):
        best = max(score(p) for p in paths if ids[t, p[t]] == selected[t])
        others = [score(p) for p in paths if ids[t, p[t]] != selected[t]]
        expected = best - max(others) if others else torch.tensor(torch.inf)
        assert margins[t].item() == pytest.approx(float(expected), abs=1e-6)
    assert torch.isinf(margins[1])  # Duplicate fixed IDs are not alternatives.
    shifted = emissions + torch.tensor([100., -1000., 500.])[:, None]
    assert torch.allclose(margins, BigramViterbiSelector.path_margins(ids, shifted, transitions, selected, .7), atol=1e-4)


def test_single_position_ties_and_single_candidate():
    ids = torch.tensor([[1, 2]])
    zero_edges = torch.empty(0, 2, 2)
    assert BigramViterbiSelector.path_margins(ids, torch.tensor([[3., 1.]]), zero_edges, torch.tensor([1])).item() == 2.
    assert BigramViterbiSelector.path_margins(ids, torch.zeros(1, 2), zero_edges, torch.tensor([1])).item() == 0.
    assert torch.isinf(BigramViterbiSelector.path_margins(ids[:, :1], torch.zeros(1, 1), torch.empty(0, 1, 1), torch.tensor([1]))).all()


class MatrixScorer:
    def __init__(self):
        self.matrix = torch.zeros(5, 5)
        self.matrix[0, 2], self.matrix[0, 3] = -1.5, 0.
        self.matrix[1, 2], self.matrix[1, 3] = -11.5, -11.5
    def transition_score(self, previous, following, **kwargs):
        return self.matrix[previous, following]
    def __call__(self, ids, emissions, **kwargs):
        return self.transition_score(ids[:-1, :, None], ids[1:, None, :])


def example_logits():
    return torch.tensor([[0., -.1, -100., -100., -100.], [-100., -100., 0., -2., -100.]])


def test_joint_path_margin_ranking_can_reverse_diffusion_confidence():
    selector = BigramViterbiSelector(MatrixScorer(), 1., remasking_confidence='viterbi_margin')
    selected, probability = selector.select_block(example_logits(), torch.tensor([4, 4]), torch.ones(2, dtype=torch.bool), top_k=2)
    assert selected.tolist() == [0, 2]
    assert probability[0] < probability[1]
    assert torch.allclose(selector.last_path_margins, torch.tensor([10.1, .5]), atol=1e-5)


@pytest.mark.parametrize('method', ['conditional', 'pmi'])
@pytest.mark.parametrize('length', [1, 8, 32, 128, 256])
def test_new_confidence_preserves_selected_ids_probabilities_and_fixed_tokens(method, length):
    model = BigramScorer.from_sequences([[0, 1, 2, 3]] * 10, 8)
    torch.manual_seed(length)
    logits = torch.randn(length, 8)
    current = torch.arange(length) % 8
    editable = torch.arange(length) % 3 != 1
    baseline = BigramViterbiSelector(model, .5, scoring_method=method)
    margin = BigramViterbiSelector(model, .5, scoring_method=method, remasking_confidence='viterbi_margin')
    expected = baseline.select_block(logits, current, editable, left_id=0, right_id=3)
    actual = margin.select_block(logits, current, editable, left_id=0, right_id=3)
    assert torch.equal(expected[0], actual[0]) and torch.equal(expected[1], actual[1])
    assert torch.equal(actual[0][~editable], current[~editable])
    assert torch.isinf(margin.last_path_margins[~editable]).all()
    assert (margin.last_path_margins[editable] >= 0).all()
    assert baseline.last_path_margins is None


@pytest.mark.parametrize('top_k', [1, 2, 8])
def test_zero_weight_keeps_exact_argmax_with_tied_logits(top_k):
    model = BigramScorer.from_sequences([], 8)
    selector = BigramViterbiSelector(model, 0., remasking_confidence='viterbi_margin')
    logits = torch.ones(4, 8, dtype=torch.bfloat16)
    current, editable = torch.tensor([7, 7, 7, 7]), torch.tensor([True, False, True, True])
    selected, probability = selector.select_block(logits, current, editable, top_k=top_k, left_id=1)
    assert torch.equal(selected, torch.where(editable, logits.argmax(-1), current))
    assert torch.allclose(probability, torch.full((4,), 1/8))
    assert torch.isinf(selector.last_path_margins[~editable]).all()
    if top_k == 1:
        assert torch.isinf(selector.last_path_margins).all()
    else:
        assert (selector.last_path_margins[editable] == 0).all()


@pytest.mark.parametrize('profile', [False, True])
def test_inference_retains_by_selected_confidence_without_extra_forwards(profile):
    class Tokenizer:
        eos_token_id = 3
        name_or_path = 'toy'
        chat_template = 'template'
        def apply_chat_template(self, *args, **kwargs): return [1]
        def decode(self, ids, **kwargs): return ' '.join(map(str, ids))
    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__(); self.weight = torch.nn.Parameter(torch.zeros(1)); self.inputs = []
        def forward(self, input_ids, **kwargs):
            self.inputs.append(input_ids.clone())
            logits = torch.zeros(1, 3, 5); logits[0, 1:] = example_logits()
            return type('Output', (), dict(logits=logits))()
    for mode, expected in [('diffusion', [1, 4, 2]), ('viterbi_margin', [1, 0, 4])]:
        model = Model()
        session = InferenceSession(model, Tokenizer(), torch.device('cpu'), Path('.'), {}, 4)
        selector = BigramViterbiSelector(MatrixScorer(), 1., remasking_confidence=mode)
        if profile: selector = ProfiledBigramSelector(selector)
        states = list(denoise_stream(session, 'Q', 'S', 2, 2, 1., 1., 2, 42,
            permanent_unmask=True, proportional_unmask=False, bigram_selector=selector, bigram_top_k=2))
        assert len(model.inputs) == len(states) == 2
        assert model.inputs[1].tolist() == [expected]
        if mode == 'viterbi_margin':
            assert 'sampling probability 52.5%' in states[0][2]  # Display stays a probability, not a margin.


def test_invalid_confidence_option():
    with pytest.raises(ValueError, match='Remasking confidence'):
        BigramViterbiSelector(MatrixScorer(), remasking_confidence='wrong')


@pytest.mark.skipif(not torch.cuda.is_available(), reason='CUDA unavailable')
def test_cpu_cuda_path_margins_agree():
    torch.manual_seed(7)
    ids = torch.arange(16).reshape(4, 4)
    unary = torch.randn(4, 4)
    transitions = torch.randn(3, 4, 4)
    selected = BigramViterbiSelector.decode(ids, unary, transitions)
    expected = BigramViterbiSelector.path_margins(ids, unary, transitions, selected)
    actual = BigramViterbiSelector.path_margins(ids.cuda(), unary.cuda(), transitions.cuda(), selected.cuda()).cpu()
    assert torch.allclose(expected, actual, atol=1e-5)
