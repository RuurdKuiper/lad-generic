import ast
import itertools
import math
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from diffusion_lm.bigram import BigramScorer, BigramViterbiSelector


@pytest.mark.parametrize('method', ['conditional', 'pmi'])
@pytest.mark.parametrize('mode', ['diffusion', 'viterbi_margin'])
@pytest.mark.parametrize('temperature', [.2, 1., 2.])
def test_tempered_path_matches_exhaustive_objective_with_fixed_token_and_boundaries(method, mode, temperature):
    model = BigramScorer.from_sequences([[0, 1, 2, 3]] * 20 + [[0, 2, 2, 1]] * 8, 4)
    selector = BigramViterbiSelector(model, .5, scoring_method=method, min_count=1,
                                    pmi_clip=2., remasking_confidence=mode)
    logits = torch.tensor([[.2, -.3, .7, -.1], [.9, .1, -.1, .5], [.1, .6, -.1, -.4]])
    current, editable = torch.tensor([0, 2, 0]), torch.tensor([True, False, True])
    selected, confidence = selector.select_block(logits, current, editable, top_k=4,
                                                temperature=temperature, left_id=3, right_id=1)
    tempered = (logits / temperature).log_softmax(-1)
    def score(path):
        seq = torch.tensor([3, *path, 1])
        edges = model.transition_score(seq[:-1], seq[1:], scoring_method=method, min_count=1, pmi_clip=2.)
        return tempered[0, path[0]] + tempered[2, path[2]] + .5 * edges.sum()
    paths = [[a, 2, b] for a, b in itertools.product(range(4), repeat=2)]
    expected = max(paths, key=score)
    assert selected.tolist() == expected
    torch.testing.assert_close(confidence, logits.softmax(-1).gather(1, selected[:, None]).squeeze(1))
    if mode == 'viterbi_margin':
        for t in [0, 2]:
            other = max(score(path) for path in paths if path[t] != selected[t])
            # Stable score units multiply the tempered objective by T.
            assert selector.last_path_margins[t].item() == pytest.approx(float(temperature * (score(expected) - other)), abs=2e-6)
        assert math.isinf(selector.last_path_margins[1])


class PairReward:
    def transition_score(self, a, b, **kwargs):
        return ((a == 1) & (b == 1)).float() * 2

    def __call__(self, ids, emissions, **kwargs):
        return self.transition_score(ids[:-1, :, None], ids[1:, None, :])


@pytest.mark.parametrize('mode', ['diffusion', 'viterbi_margin'])
def test_temperature_changes_path_at_fixed_weight(mode):
    selector = BigramViterbiSelector(PairReward(), .5, remasking_confidence=mode)
    logits = torch.tensor([[.4, 0.], [.4, 0.]])
    current, editable = torch.zeros(2, dtype=torch.long), torch.ones(2, dtype=torch.bool)
    assert selector.select_block(logits, current, editable, top_k=2, temperature=.25)[0].tolist() == [0, 0]
    assert selector.select_block(logits, current, editable, top_k=2, temperature=1.)[0].tolist() == [1, 1]
    assert selector.weight == .5


@pytest.mark.parametrize('mode', ['diffusion', 'viterbi_margin'])
@pytest.mark.parametrize('length', [1, 32, 64, 128, 256])
@pytest.mark.parametrize('temperature,top_k', [(0., 2), (1e-300, 2), (2., 1)])
def test_greedy_limits_and_bfloat16_ties_keep_fixed_tokens(mode, length, temperature, top_k):
    selector = BigramViterbiSelector(PairReward(), .5, remasking_confidence=mode)
    logits = torch.ones(length, 4, dtype=torch.bfloat16)
    logits[:, 0] = 2.
    if temperature == 0. or top_k == 1:
        logits[:, 1] = 2.  # Tie must agree with raw full-vocabulary argmax.
    current = torch.full((length,), 3)
    editable = torch.arange(length) % 3 != 1
    selected, confidence = selector.select_block(logits, current, editable, top_k=top_k,
                                                temperature=temperature, left_id=1, right_id=1)
    assert torch.equal(selected, torch.where(editable, logits.argmax(-1), current))
    torch.testing.assert_close(confidence, logits.float().softmax(-1).gather(1, selected[:, None]).squeeze(1))
    if mode == 'viterbi_margin':
        assert not torch.isnan(selector.last_path_margins).any()
        assert torch.isinf(selector.last_path_margins[~editable]).all()


@pytest.mark.parametrize('temperature', [-1., float('nan'), float('inf')])
def test_invalid_temperature(temperature):
    selector = BigramViterbiSelector(PairReward())
    with pytest.raises(ValueError, match='temperature'):
        selector.select_block(torch.ones(1, 2), torch.tensor([0]), torch.tensor([True]), temperature=temperature)


def test_hosted_generate_routes_shared_controls_and_fixed_weight_without_loading_model():
    source = Path(__file__).parents[1] / 'huggingface/byod_space/app.py'
    tree = ast.parse(source.read_text())
    generate = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'generate')
    generate.decorator_list = []
    assert not {'bigram_weight', 'bigram_top_k'} & {a.arg for a in generate.args.args}
    captured = {}
    def stream(session, **kwargs):
        captured.update(kwargs)
        yield 'status', 'text', 'html'
    scorer = SimpleNamespace(to=lambda device: PairReward())
    namespace = dict(BIGRAM_PATH='test.pt', BIGRAM_ENABLED=True, SESSION=SimpleNamespace(device='cpu'),
                     _bigram_scorer=lambda path: scorer, BigramViterbiSelector=BigramViterbiSelector,
                     denoise_stream=stream)
    settings = {'BIGRAM_SCORING_METHOD', 'BIGRAM_REMASKING_CONFIDENCE', 'PMI_MIN_COUNT', 'PMI_CLIP', 'BIGRAM_ENDING_DELAY_STRENGTH'}
    namespace.update({n.targets[0].id: ast.literal_eval(n.value) for n in tree.body
                      if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                      and n.targets[0].id in settings})
    exec(compile(ast.Module(body=[generate], type_ignores=[]), str(source), 'exec'), namespace)
    actual = list(namespace['generate']('Q', 'S', 128, 32, 128, .25, 7, 0., 'No coloring',
                                       'Bigram Viterbi', False, 4, False, False, generation_seed=42))
    assert actual == [('text', 'html')]
    assert captured['temperature'] == .25 and captured['top_k'] == 7
    selector = captured['bigram_selector']
    assert selector.weight == .5
    assert selector.scoring_method == 'pmi' and selector.remasking_confidence == 'diffusion'
    assert selector.min_count == 1 and selector.pmi_clip == 2.
    assert 'bigram_top_k' not in captured
