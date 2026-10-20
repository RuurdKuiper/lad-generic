import pytest
import torch

from diffusion_lm.inference import _sample, _sampling_token_confidence


@pytest.mark.parametrize('top_k', [1, 3, 16])
def test_greedy_selection_preserves_full_vocab_retention_ranking(top_k):
    # All rows have the same argmax, but very different model confidence.
    logits = torch.tensor([[1., 0., 0.], [6., 0., 0.], [0., 0., 0.]])
    selected, confidence = _sample(logits, 0., top_k, None)
    assert selected.tolist() == [0, 0, 0]
    expected = logits.softmax(-1)[:, 0]
    torch.testing.assert_close(confidence, expected)
    assert confidence.argsort(descending=True).tolist() == [1, 0, 2]
    existing = _sampling_token_confidence(logits, torch.tensor([1, 0, 2]), 0., top_k)
    torch.testing.assert_close(existing, logits.softmax(-1)[torch.arange(3), [1, 0, 2]])


def test_positive_temperature_top_k_behavior_unchanged():
    logits = torch.tensor([[1., 2., 3.]])
    selected, confidence = _sample(logits, 0.7, 1, None)
    assert selected.item() == 2
    assert confidence.item() == 1.


def test_greedy_bfloat16_ties_use_full_argmax_and_float32_confidence():
    logits = torch.tensor([[5., 5., 5., 1.]], dtype=torch.bfloat16)
    selected, confidence = _sample(logits, 0., 1, None)
    assert torch.equal(selected, logits.argmax(-1))
    assert confidence.dtype == torch.float32
    torch.testing.assert_close(confidence, logits.float().softmax(-1)[:, 0])
