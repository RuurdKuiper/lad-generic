from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from diffusion_lm.apd import commitment_mask, confidence_threshold, selected_token_probabilities
from diffusion_lm.bigram import BigramScorer, BigramViterbiSelector, RepetitionPenalizedBigramSelector
from diffusion_lm.inference import InferenceSession, denoise_stream


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
    def __init__(self, distribution="confident"):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.zeros(1))
        self.distribution = distribution
        self.inputs = []
        self.ar_calls = 0

    @contextmanager
    def disable_adapter(self):
        self.ar_calls += 1
        yield

    def forward(self, input_ids, **kwargs):
        self.inputs.append(input_ids.clone())
        logits = torch.zeros((*input_ids.shape, 8))
        if self.distribution == "confident":
            logits[..., 1] = 20.
        elif self.distribution == "mask":
            logits[..., 7] = 20.
            logits[..., 0] = 1.  # Unique best legal fallback, avoiding tied top-k IDs.
        elif self.distribution == "endings":
            logits[..., 1] = 20.
            logits[:, 3:, 1] = 0.
            logits[:, 3:, 4] = 20.
        return SimpleNamespace(logits=logits)


def session(native=False, distribution="confident"):
    return InferenceSession(Model(distribution), Tokenizer(), torch.device("cpu"), Path("."), {}, 7, llada=native)


def selector(method):
    if method not in {"conditional", "pmi", "repetition", "margin"}:
        return None
    base = BigramViterbiSelector(BigramScorer.from_sequences([[0, 1, 2, 3]] * 10, 8),
        scoring_method="conditional" if method == "conditional" else "pmi", min_count=1, pmi_clip=2.,
        remasking_confidence="viterbi_margin" if method == "margin" else "diffusion")
    return RepetitionPenalizedBigramSelector(base, 1., excluded_token_ids=(4, 5)) if method == "repetition" else base


def run(s, method="standard", **kwargs):
    settings = dict(permanent_unmask=True, confidence_guided=method == "standard",
        proportional_unmask=False, early_stopping=False, block_length=3,
        bigram_selector=selector(method), autoregressive_guided=method == "ar")
    settings.update(kwargs)
    return list(denoise_stream(s, "Q", "S", 6, 8, 1., 0., 3, 42, **settings))


def test_cosine_threshold_endpoints_warmup_and_monotonicity():
    values = [confidence_threshold(i, 101) for i in range(101)]
    assert values[0] == pytest.approx(.9)
    assert values[15] == pytest.approx(.9)
    assert values[-1] == pytest.approx(.5)
    assert all(a >= b for a, b in zip(values, values[1:]))
    assert confidence_threshold(0, 1) == .5


def test_commit_all_confident_positions_and_leave_others_masked():
    p = torch.tensor([.95, .89, .97, .99])
    pending = torch.tensor([True, True, True, False])
    assert commitment_mask(p, pending, 0, 8).tolist() == [True, False, True, False]


def test_progress_fallback_final_cleanup_and_nonfinite_scores():
    p = torch.tensor([.2, .3, .1])
    pending = torch.ones(3, dtype=torch.bool)
    assert commitment_mask(p, pending, 0, 8).tolist() == [False, True, False]
    assert commitment_mask(p, pending, 7, 8).all()
    assert commitment_mask(torch.full((3,), float("nan")), pending, 0, 8).sum() == 1
    assert not commitment_mask(p, ~pending, 0, 8).any()


def test_ending_delay_prefers_ordinary_predictions_and_releases_endings():
    pending = torch.ones(3, dtype=torch.bool)
    endings = torch.tensor([False, True, True])
    p = torch.tensor([.2, .99, .99])
    assert commitment_mask(p, pending, 0, 8, endings=endings, delay_endings=True).tolist() == [True, False, False]
    assert commitment_mask(p, torch.tensor([False, True, True]), 1, 8,
                           endings=endings, delay_endings=True).tolist() == [False, True, True]


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("method", ["standard", "random", "ar", "conditional", "pmi", "repetition", "margin"])
def test_apd_finishes_blocks_early_without_extra_forwards(native, method):
    s = session(native)
    states = run(s, method, adaptive_parallel_decoding=True)
    assert len(s.model.inputs) == len(states) == 2  # One forward per block, rather than eight.
    assert s.model.ar_calls == 0
    assert "7" not in states[-1][0].split()
    assert "forwards 2" in states[-1][1] and "block committed" in states[-1][1]
    assert s.model.inputs[1][0].tolist() == [0, 1, 1, 1, 7, 7, 7]


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("method", ["standard", "random", "ar", "conditional", "pmi", "repetition", "margin"])
def test_apd_off_matches_existing_default(native, method):
    a, b = session(native), session(native)
    original = run(a, method)
    off = run(b, method, adaptive_parallel_decoding=False)
    assert original == off
    assert len(a.model.inputs) == len(b.model.inputs)
    assert all(torch.equal(x, y) for x, y in zip(a.model.inputs, b.model.inputs))
    if method == "ar":
        assert a.model.ar_calls == b.model.ar_calls > 0
    else:
        assert len(b.model.inputs) == 8


@pytest.mark.parametrize("distribution", ["uniform", "mask"])
def test_low_confidence_and_mask_predictions_resolve_by_final_step(distribution):
    s = session(distribution=distribution)
    states = list(denoise_stream(s, "Q", "S", 5, 3, 1., 0., 1, 42,
        adaptive_parallel_decoding=True, early_stopping=True))
    assert len(states) == len(s.model.inputs) == 3
    assert s.model.inputs[1][0].tolist() == [0, 0, 7, 7, 7, 7]
    assert s.model.inputs[2][0].tolist() == [0, 0, 0, 7, 7, 7]
    assert "7" not in states[-1][0].split()


def test_unequal_final_block_and_single_step_blocks():
    s = session()
    states = list(denoise_stream(s, "Q", "S", 7, 5, 1., 0., 1, 42,
        adaptive_parallel_decoding=True, block_length=3))
    assert len(states) == len(s.model.inputs) == 3
    assert states[-1][0].split() == ["1"] * 7


def test_apd_committed_ending_still_stops_the_whole_answer_when_enabled():
    s = session(distribution="endings")
    states = run(s, adaptive_parallel_decoding=True, early_stopping=True, confidence_eos_eot_inf=True)
    assert len(states) == 1
    assert "remaining blocks skipped" in states[-1][1]
    assert states[-1][0].split() == ["1", "1"]


def test_standard_top_k_one_does_not_artificially_give_apd_confidence_one():
    s = session(distribution="uniform")
    states = list(denoise_stream(s, "Q", "S", 3, 3, 1., 1., 1, 42, adaptive_parallel_decoding=True))
    assert len(states) == 3  # Actual model p=1/8, not top-k-normalized p=1.


def test_apd_uses_probability_of_viterbi_selected_token_and_ignores_path_margin():
    s = session(distribution="uniform")

    class JointSelection:
        last_path_margins = None

        def select_block(self, logits, current, editable, **kwargs):
            self.last_path_margins = torch.tensor([100., 0., 100.])
            selected = torch.full((3,), 2)
            return selected, selected_token_probabilities(logits, selected)

    def forward(input_ids, **kwargs):
        s.model.inputs.append(input_ids.clone())
        logits = torch.zeros(1, 4, 8)
        logits[..., 1] = 10.
        logits[0, 2, 1] = 0.
        logits[0, 2, 2] = 10.
        if len(s.model.inputs) > 1:
            logits[..., 1] = 0.
            logits[..., 2] = 10.
        return SimpleNamespace(logits=logits)

    s.model.forward = forward
    states = list(denoise_stream(s, "Q", "S", 3, 4, 1., 2., 3, 42,
        adaptive_parallel_decoding=True, bigram_selector=JointSelection()))
    assert len(states) == 2
    assert s.model.inputs[1][0].tolist() == [0, 7, 2, 7]
    assert "Viterbi-margin remasking" not in states[-1][1]
