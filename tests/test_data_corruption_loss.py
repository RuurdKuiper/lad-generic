import torch
from diffusion_lm.data import DenoisingCollator
from diffusion_lm.loss import masked_denoising_loss


class ToyTokenizer:
    name_or_path = "toy-llama"
    eos_token_id = 2
    chat_template = "toy"
    def encode(self, text, add_special_tokens=False):
        table = {"MASK": [9], "<|start_header_id|>assistant<|end_header_id|>": [7, 8, 6], "\n": [5]}
        return table.get(text, [3 + (ord(c) % 4) for c in text])
    def decode(self, ids): return "MASK" if ids == [9] else str(ids)
    def apply_chat_template(self, messages, tokenize=True, add_generation_prompt=True): return [1, 4]


def row(index=0):
    # assistant header/newline, answer content, genuine EOS, EOS padding
    labels = [1, 7, 8, 6, 5, 3, 4, 2, 2, 2]
    stored = [1, 7, 8, 6, 9, 9, 4, 9, 9, 9]
    return {"labels": labels, "input_ids": stored, "instruction": "i", "input": "", "output": "ab", "_index": index}


def test_structured_uses_stored_inputs_and_excludes_delimiter_eos_padding():
    b = DenoisingCollator(ToyTokenizer(), "structured", 32, structured_loss_behavior="all_answer_tokens")([row()])
    assert b["input_ids"].tolist()[0] == row()["input_ids"]
    assert b["answer_mask"].tolist()[0] == [False, False, False, False, False, True, True, True, False, False]
    assert b["padding_mask"].tolist()[0] == [False] * 8 + [True, True]
    assert b["loss_mask"].equal(b["answer_mask"])


def test_structured_all_tokens_can_include_prompt_and_padding():
    b = DenoisingCollator(ToyTokenizer(), "structured", 32, structured_loss_behavior="all_tokens")([row()])
    assert b["loss_mask"].all()


def test_mask_only_starts_clean_and_never_changes_prompt_or_padding():
    b = DenoisingCollator(ToyTokenizer(), "mask_only", 32, seed=4, deterministic=True, t_min=1.0)([row()])
    # Source reconstruction, rather than the stored noised Llama IDs, is the clean input.
    assert b["labels"].tolist()[0] == [1, 4, 4, 5, 2]
    assert b["labels"].tolist()[0] != row()["input_ids"]
    changed = b["input_ids"] != b["labels"]
    assert torch.equal(changed, b["loss_mask"])
    assert not changed[0, :2].any()
    assert changed[0, 2:].all()


def test_deterministic_eval_and_training_resampling():
    c = DenoisingCollator(ToyTokenizer(), "mask_only", 32, seed=9, deterministic=True, t_min=.2)
    assert torch.equal(c([row(5)])["input_ids"], c([row(5)])["input_ids"])
    train = DenoisingCollator(ToyTokenizer(), "mask_only", 32, seed=9, deterministic=False, t_min=.2)
    seen = {tuple(train([row(5)])["input_ids"].flatten().tolist()) for _ in range(8)}
    assert len(seen) > 1


def test_every_usable_example_has_a_mask_and_multitoken_mask_is_rejected():
    b = DenoisingCollator(ToyTokenizer(), "mask_only", 32, seed=1, deterministic=True, t_min=0.0)([row()])
    assert b["loss_mask"].any()
    class BadTokenizer(ToyTokenizer):
        def encode(self, text, add_special_tokens=False):
            return [9, 10] if text == "MASK" else super().encode(text, add_special_tokens)
    try:
        DenoisingCollator(BadTokenizer(), "mask_only", 32)
    except ValueError as exc:
        assert "exactly one token" in str(exc)
    else:
        raise AssertionError("expected MASK validation failure")


def test_per_example_inverse_t_weighting_same_position():
    # p(correct)=e^-1 at row 0; p(correct)=e^-2 at row 1.
    logits = torch.tensor([[[0., 0.]], [[0., -2.]]])
    labels = torch.tensor([[1], [1]])
    mask = torch.tensor([[True], [True]])
    loss, metrics = masked_denoising_loss(logits, labels, mask, torch.tensor([.5, 1.]))
    ce0 = torch.logsumexp(torch.tensor([0., 0.]), 0)
    ce1 = -torch.tensor(-2.) + torch.logsumexp(torch.tensor([0., -2.]), 0)
    assert torch.allclose(loss, ((ce0 / .5) + ce1) / 2)
    assert torch.allclose(metrics["unweighted_masked_token_ce"], (ce0 + ce1) / 2)


def test_same_position_logits_not_shifted():
    labels = torch.tensor([[1, 0]])
    logits = torch.tensor([[[0., 8.], [8., 0.]]])
    mask = torch.tensor([[True, False]])
    loss, _ = masked_denoising_loss(logits, labels, mask)
    assert loss < .01
