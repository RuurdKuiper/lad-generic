import pytest
import torch
import torch.nn.functional as F

from diffusion_lm.corruption import apply_corruption
from diffusion_lm.data import DenoisingCollator
from diffusion_lm.loss import masked_denoising_loss, selected_denoising_loss
from test_data_corruption_loss import ToyTokenizer


def make_batch(rows=1, length=128, prefix=8, padding=4):
    labels = torch.full((rows, prefix + length + padding), 3, dtype=torch.long)
    answer = torch.zeros_like(labels, dtype=torch.bool)
    answer[:, prefix:prefix + length] = True
    pads = torch.zeros_like(answer)
    if padding:
        pads[:, -padding:] = True
        labels[:, -padding:] = 2
    return dict(labels=labels, input_ids=labels.clone(), answer_mask=answer,
                padding_mask=pads, example_index=torch.arange(rows))


def corrupt(batch, probability=1.0, eos_padding_loss=False, seed=123):
    return apply_corruption(batch, 9, "mask_only", "corrupted_answer_tokens",
                            eos_padding_loss, 0.001, seed, True,
                            frontier_masking_probability=probability)


def test_disabled_frontier_preserves_original_iid_rng_and_forced_mask():
    batch = corrupt(make_batch(rows=50, length=3), probability=0.0)
    for row in range(50):
        generator = torch.Generator().manual_seed(123 + row)
        t = torch.empty(()).uniform_(0.001, 1.0, generator=generator).item()
        expected = torch.rand(3, generator=generator) < t
        if not expected.any():
            expected[torch.randint(3, (1,), generator=generator)] = True
        assert batch["sampled_t"][row] == t
        assert torch.equal(batch["loss_mask"][row, 8:11], expected)
    assert "token_loss_weights" not in batch


@pytest.mark.parametrize("padding_loss", [False, True])
def test_frontier_respects_eligibility_and_is_independent_of_prompt_length(padding_loss):
    short = corrupt(make_batch(rows=20, prefix=2), eos_padding_loss=padding_loss)
    long = corrupt(make_batch(rows=20, prefix=20), eos_padding_loss=padding_loss)
    assert torch.equal(short["input_ids"][:, 2:], long["input_ids"][:, 20:])
    eligible = short["answer_mask"] | short["padding_mask"] if padding_loss else short["answer_mask"]
    assert torch.equal(short["input_ids"][~eligible], short["labels"][~eligible])
    assert torch.equal(short["input_ids"] != short["labels"], short["loss_mask"])
    assert not (short["loss_mask"] & ~eligible).any()
    assert short["loss_mask"][short["padding_mask"]].any().item() == padding_loss
    repeat = corrupt(make_batch(rows=20, prefix=2), eos_padding_loss=padding_loss)
    for key in short:
        assert torch.equal(short[key], repeat[key])


def test_frontier_has_visible_prefix_and_masked_suffix_with_exceptions():
    batch = corrupt(make_batch(rows=1000))
    middle = (batch["sampled_t"] > 0.4) & (batch["sampled_t"] < 0.6)
    early = batch["loss_mask"][middle, 8:28].float().mean().item()
    late = batch["loss_mask"][middle, 116:136].float().mean().item()
    assert 0.01 < early < 0.06
    assert 0.94 < late < 0.99


@pytest.mark.parametrize("padding_loss", [False, True])
def test_short_answer_frontier_is_unchanged_by_two_hundred_padding_tokens(padding_loss):
    unpadded = make_batch(rows=100, length=5, padding=0)
    padded = make_batch(rows=100, length=5, padding=200)
    # The fifth answer token is the genuine EOS, not padding.
    unpadded["labels"][:, 12] = 2
    padded["labels"][:, 12] = 2
    short = corrupt(unpadded, eos_padding_loss=padding_loss)
    long = corrupt(padded, eos_padding_loss=padding_loss)
    assert torch.equal(short["sampled_t"], long["sampled_t"])
    for key in ("input_ids", "loss_mask", "token_loss_weights"):
        assert torch.equal(short[key], long[key][:, :13]), key
    assert long["loss_mask"][:, 12].any()  # Genuine EOS still participates.
    if padding_loss:
        assert not torch.equal(long["token_loss_weights"][:, 13:], torch.ones(100, 200))
    else:
        assert torch.equal(long["token_loss_weights"][:, 13:], torch.ones(100, 200))
        assert not long["loss_mask"][:, 13:].any()


def test_frontier_continues_through_padding_without_changing_answer_draws():
    disabled = corrupt(make_batch(rows=1000, length=5, padding=200))
    enabled = corrupt(make_batch(rows=1000, length=5, padding=200), eos_padding_loss=True)
    assert torch.equal(disabled["loss_mask"][:, :13], enabled["loss_mask"][:, :13])
    # Padding immediately follows the genuine answer in frontier coordinates;
    # positions far into its tail approach the 1-epsilon masking ceiling.
    near = enabled["loss_mask"][:, 13:16].float().mean().item()
    far = enabled["loss_mask"][:, -100:].float().mean().item()
    assert 0.70 < near < 0.90
    assert 0.96 < far < 0.98


def test_frontier_padding_uses_matching_inverse_probability_weights():
    batch = corrupt(make_batch(rows=20, length=5, padding=10), eos_padding_loss=True)
    t = batch["sampled_t"][:, None]
    offsets = torch.arange(5, 15, dtype=torch.float32)
    frontier = 5 * (1.0 - t)
    probabilities = 0.03 + 0.94 * torch.sigmoid((offsets - frontier) / 3.0)
    expected = t / probabilities
    assert torch.allclose(batch["token_loss_weights"][:, 13:], expected)


def test_frontier_mixture_is_sampled_per_example():
    batch = corrupt(make_batch(rows=1000), probability=0.75)
    frontier_rows = (batch["token_loss_weights"] != 1).any(dim=1)
    assert 0.70 < frontier_rows.float().mean().item() < 0.80
    assert torch.equal(batch["token_loss_weights"][~frontier_rows],
                       torch.ones_like(batch["token_loss_weights"][~frontier_rows]))


@pytest.mark.parametrize("setting,value", [
    ("frontier_masking_probability", -0.1), ("frontier_masking_probability", 1.1),
    ("frontier_masking_epsilon", 0), ("frontier_masking_epsilon", 0.5),
    ("frontier_masking_tau", 0), ("frontier_masking_tau", float("nan")),
])
def test_invalid_frontier_settings_fail_early(setting, value):
    with pytest.raises(ValueError, match=setting):
        DenoisingCollator(ToyTokenizer(), "mask_only", 32, **{setting: value})


def test_frontier_weights_match_position_weighted_loss_and_gradients():
    # Mix an IID row (unit corrections) with a frontier row (t/p corrections).
    generator = torch.Generator().manual_seed(12)
    logits = torch.randn(2, 4, 5, generator=generator, requires_grad=True)
    labels = torch.tensor([[1, 2, 3, 4], [2, 1, 4, 0]])
    mask = torch.tensor([[False, True, False, True], [True, False, True, False]])
    t = torch.tensor([0.5, 0.4])
    probabilities = torch.tensor([[0.5] * 4, [0.03, 0.2, 0.7, 0.97]])
    weights = t[:, None] / probabilities
    normalization = torch.ones_like(mask)
    ce = F.cross_entropy(logits.transpose(1, 2), labels, reduction="none")
    expected = ((ce * mask / probabilities).sum(dim=1) / 4).mean()
    expected_grad, = torch.autograd.grad(expected, logits, retain_graph=True)
    ids, positions = mask.nonzero(as_tuple=True)
    for sparse in (True, False):
        loss, metrics = masked_denoising_loss(
            logits, labels, mask, t, normalization,
            sparse_positions=sparse, token_weights=weights,
        )
        assert torch.allclose(loss, expected)
        assert torch.allclose(metrics["unweighted_masked_token_ce"], ce[mask].mean())
        gradient, = torch.autograd.grad(loss, logits, retain_graph=True)
        assert torch.allclose(gradient, expected_grad)
    selected, metrics = selected_denoising_loss(
        logits[ids, positions], labels[ids, positions], ids, mask.sum(dim=1),
        t, normalization, token_weights=weights[ids, positions],
    )
    assert torch.allclose(selected, expected)
    gradient, = torch.autograd.grad(selected, logits)
    assert torch.allclose(gradient, expected_grad)


def test_empty_frontier_draw_has_finite_zero_loss_and_gradients():
    logits = torch.randn(1, 3, 5, requires_grad=True)
    loss, metrics = masked_denoising_loss(
        logits, torch.zeros(1, 3, dtype=torch.long), torch.zeros(1, 3, dtype=torch.bool),
        torch.tensor([0.01]), torch.ones(1, 3, dtype=torch.bool),
        token_weights=torch.ones(1, 3),
    )
    loss.backward()
    assert loss.item() == 0
    assert metrics["valid_examples"] == 0
    assert torch.equal(logits.grad, torch.zeros_like(logits))
