"""Checks for the experiment's token weighting and matched-prompt comparison."""
import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / 'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location('quick_perplexity', scripts/'evaluate_quick_perplexity.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'OUT', tmp_path)
    return module


def test_token_pooled_perplexity_and_paired_bootstrap(experiment):
    for prompt, count, loss in [(1,1,1.), (2,3,9.)]:
        for method in ['confidence','pmi_diffusion']:
            key = f'{prompt}/{method}'
            experiment.append(experiment.OUT/'results.jsonl', dict(key=key, prompt_id=prompt,
                method=method, steps=8, prompt='Question?', text='Some answer.'))
            experiment.append(experiment.OUT/'scores.jsonl', dict(key=key, tokens=count,
                nll=loss if method=='confidence' else loss/2))
    experiment.summarize()
    groups = json.loads((experiment.OUT/'summary.json').read_text())['groups']
    assert groups[0]['perplexity'] == pytest.approx(math.exp(10/4))
    assert groups[1]['perplexity'] == pytest.approx(math.exp(5/4))
    assert groups[1]['paired_ppl_ratio_ci95'][1] < 1


def test_unpaired_answers_are_not_compared(experiment):
    experiment.append(experiment.OUT/'results.jsonl', dict(key='only', prompt_id=1,
        method='confidence', steps=8, prompt='Question?', text='Unmatched answer.'))
    experiment.append(experiment.OUT/'scores.jsonl', dict(key='only', tokens=2, nll=4))
    experiment.summarize()
    summary = json.loads((experiment.OUT/'summary.json').read_text())
    assert summary['groups'] == []
    assert summary['scored'] == 1


def test_128_token_experiment_runs_all_five_budgets(experiment):
    class Client:
        def submit(self, **kwargs):
            assert kwargs['max_new_tokens'] == kwargs['block_length'] == 128
            steps = kwargs['num_steps']
            status = f'Denoising step {steps}/{steps}'
            if kwargs['remasking_strategy'] == 'Bigram Viterbi':
                status += '\nDecoding metrics: ' + json.dumps({'selector_calls':steps})
            return SimpleNamespace(result=lambda **_: (status, '<textarea>A saved answer.</textarea>'))
    api = SimpleNamespace(repo_info=lambda *a, **kw: SimpleNamespace(sha='test-revision'))
    experiment.generate(Client(), api, None, questions=2, max_new_tokens=128,
                        steps_list=[8,16,32,64,128])
    rows = experiment.read_rows(experiment.OUT/'results.jsonl')
    assert len(rows) == 20
    assert len({r['key'] for r in rows}) == 20
    assert {r['steps'] for r in rows} == {8,16,32,64,128}
