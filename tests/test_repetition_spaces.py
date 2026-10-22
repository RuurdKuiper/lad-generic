import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

import diffusion_lm.bigram as bigram_module
from diffusion_lm.bigram import BigramScorer, BigramViterbiSelector, RepetitionPenalizedBigramSelector
from diffusion_lm.bigram_evaluation import ProfiledBigramSelector
from diffusion_lm.inference import InferenceSession, denoise_stream

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("gamma", [0., 1., 10.])
def test_shared_diffusion_loop_preserves_fixed_rows_block_resets_and_forward_budget(native, gamma, monkeypatch):
    calls = []
    real_penalties = bigram_module.expected_bigram_repetition_penalties

    def penalties(ids, p, *args, **kwargs):
        result = real_penalties(ids, p, *args, **kwargs)
        calls.append(len(ids))
        assert torch.count_nonzero(result[0]) == 0  # No earlier-block counts.
        return result

    monkeypatch.setattr(bigram_module, "expected_bigram_repetition_penalties", penalties)

    class Tokenizer:
        eos_token_id = 4
        unk_token_id = 6
        chat_template = "template"

        def apply_chat_template(self, *args, **kwargs):
            return [0]

        def convert_tokens_to_ids(self, token):
            return 5 if token == "<|eot_id|>" else 6

        def decode(self, ids, **kwargs):
            return " ".join(map(str, ids))

    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.zeros(1))
            self.calls = 0

        def forward(self, input_ids, **kwargs):
            self.calls += 1
            logits = torch.full((*input_ids.shape, 8), -20.)
            logits[..., 1:4] = torch.tensor([.8, .7, .5] if self.calls % 2 else [.7, .8, .5])
            return SimpleNamespace(logits=logits)

    class RecordingSelector(BigramViterbiSelector):
        def select_block(self, logits, current, editable, **kwargs):
            selected, confidence = super().select_block(logits, current, editable, **kwargs)
            assert torch.equal(selected[~editable], current[~editable])
            self.seen_fixed |= bool((~editable).any())
            return selected, confidence

    def run(use_wrapper):
        model = Model()
        session = InferenceSession(model, Tokenizer(), torch.device("cpu"), Path("."), {}, 7, llada=native)
        base = RecordingSelector(BigramScorer.from_sequences([[1, 2, 3]] * 10, 8),
                                 scoring_method="pmi", min_count=1, pmi_clip=2.)
        base.seen_fixed = False
        selector = RepetitionPenalizedBigramSelector(base, gamma, excluded_token_ids=(4, 5)) if use_wrapper else base
        selector = ProfiledBigramSelector(selector)
        states = list(denoise_stream(session, "Q", "S", 6, 4, 1., 2., 3, 42,
            permanent_unmask=True, confidence_guided=True, proportional_unmask=False,
            early_stopping=False, block_length=3, bigram_selector=selector))
        assert model.calls == selector.metrics()["selector_calls"] == len(states) == 4
        assert base.seen_fixed
        return states

    actual = run(True)
    if gamma == 0:
        assert actual == run(False)
        assert calls == []
    else:
        assert calls == [3, 3, 3, 3]


@pytest.mark.parametrize("strategy,gamma", [("Bigram Viterbi", 10.), ("PMI Viterbi + Repetition Penalty", 0.),
                                           ("PMI Viterbi + Repetition Penalty", 10.)])
def test_hosted_generator_routes_new_option_without_changing_original(strategy, gamma):
    tree = ast.parse((ROOT / "huggingface/byod_space/app.py").read_text())
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "generate")
    function.decorator_list = []
    captured = {}

    def stream(session, **kwargs):
        captured.update(kwargs)
        yield "text", "status", "html"

    scorer = BigramScorer.from_sequences([[0, 1]], 3)
    namespace = dict(BIGRAM_PATH="x.pt", BIGRAM_ENABLED=True,
        BIGRAM_SCORING_METHOD="PMI bigram", BIGRAM_REMASKING_CONFIDENCE="Diffusion probability",
        PMI_MIN_COUNT=1, PMI_CLIP=2., BIGRAM_ENDING_DELAY_STRENGTH=10.,
        SESSION=SimpleNamespace(device="cpu", tokenizer=object()),
        _bigram_scorer=lambda path: scorer, _ending_token_ids=lambda tokenizer: {1, 2},
        BigramViterbiSelector=BigramViterbiSelector, RepetitionPenalizedBigramSelector=RepetitionPenalizedBigramSelector,
        denoise_stream=stream)
    exec(compile(ast.Module(body=[function], type_ignores=[]), "shared_app", "exec"), namespace)
    assert list(namespace["generate"]("Q", "S", 64, 8, 32, 2., 16, 0., "No coloring", strategy,
        False, 4, True, False, generation_seed=42, repetition_penalty_strength=gamma)) == [("status", "html")]
    selector = captured["bigram_selector"]
    assert captured["confidence_guided"] and captured["freeze_retained_tokens"]
    if strategy == "Bigram Viterbi":
        assert isinstance(selector, BigramViterbiSelector)
    else:
        assert selector.strength == gamma and selector.excluded_token_ids == (1, 2)
        assert selector.selector.scoring_method == "pmi"


def test_rollout_preserves_configuration_and_leaves_weights_and_dependencies_in_place(tmp_path):
    spec = importlib.util.spec_from_file_location("rollout", ROOT / "huggingface/enable_repetition_penalty.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = dict(model_repo_id="test/model", model_revision="pinned", visitor_counter_id="counter",
                  model_backend="llada", bigram_enabled=True)
    module.make_bundle(tmp_path, config, "Original model card")
    import json
    saved = json.loads((tmp_path / "space_model.json").read_text())
    assert saved == dict(config, show_bigram_evaluation_controls=True)
    assert "PMI Viterbi + Repetition Penalty" in (tmp_path / "app.py").read_text()
    assert (tmp_path / "README.md").read_text().startswith("Original model card")
    assert not (tmp_path / "bigram.pt").exists()
    assert not (tmp_path / "requirements.txt").exists()
