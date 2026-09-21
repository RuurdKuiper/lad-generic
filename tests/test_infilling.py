from types import SimpleNamespace

import pytest
import torch

from diffusion_lm.infilling import score_bidirectional_example, score_causal_example, summarize_infilling


class Tokenizer:
    def encode(self, text, add_special_tokens=False):
        mapping = {
            "left": [1],
            " target": [2],
            " suffix target": [4, 2],
        }
        return mapping[text]

    def decode(self, ids, skip_special_tokens=True):
        return " ".join(str(token) for token in ids)


def example():
    return SimpleNamespace(
        example_id="example",
        prompt="instruction",
        metadata={
            "answer_prefix": "left",
            "target_text": " target",
            "answer_suffix": " suffix target",
        },
    )


def test_bidirectional_score_reports_suffix_gain(monkeypatch):
    import diffusion_lm.infilling as module

    monkeypatch.setattr(module, "_prompt_ids", lambda *_args: [10])

    def forward(_session, input_ids, _padding):
        logits = torch.zeros((1, input_ids.shape[1], 8))
        # Full context predicts target ID 2; the prefix-only control predicts 0.
        logits[0, 2, 2 if input_ids.shape[1] == 5 else 0] = 10.0
        return logits

    monkeypatch.setattr(module, "forward_denoising", forward)
    session = SimpleNamespace(
        tokenizer=Tokenizer(), prompt_format="test", mask_token_id=7,
        device=torch.device("cpu"),
    )

    result = score_bidirectional_example(session, example())

    assert result["exact_match"] is True
    assert result["prefix_only_exact_match"] is False
    summary = summarize_infilling([result], include_prefix_control=True)
    assert summary["exact_match"] == 1.0
    assert summary["prefix_only_exact_match"] == 0.0
    assert summary["suffix_gain_exact_match"] == 1.0
    assert summary["suffix_nll_reduction"] > 0.0


def test_causal_score_uses_shifted_teacher_forced_logits(monkeypatch):
    import diffusion_lm.infilling as module

    monkeypatch.setattr(module, "_encoded_example", lambda *_args: ([10, 1], [2, 3], [4]))

    class Model:
        def __call__(self, input_ids, use_cache=False):
            logits = torch.zeros((1, input_ids.shape[1], 8))
            logits[0, 1, 2] = 10.0
            logits[0, 2, 3] = 10.0
            return SimpleNamespace(logits=logits)

    session = SimpleNamespace(model=Model(), tokenizer=Tokenizer(), device=torch.device("cpu"))
    result = score_causal_example(session, example())

    assert result["prediction_ids"] == [2, 3]
    assert result["exact_match"] is True
    assert result["correct_tokens"] == 2


def test_infilling_summary_is_token_weighted():
    results = [
        {"exact_match": True, "correct_tokens": 1, "target_tokens": 1, "nll": 1.0},
        {"exact_match": False, "correct_tokens": 1, "target_tokens": 3, "nll": 7.0},
    ]

    summary = summarize_infilling(results, include_prefix_control=False)

    assert summary["exact_match"] == 0.5
    assert summary["token_accuracy"] == 0.5
    assert summary["mean_nll"] == 2.0
    assert summary["perplexity"] == pytest.approx(torch.exp(torch.tensor(2.0)).item())
