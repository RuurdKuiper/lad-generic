"""Verify alignment, causality, teacher freezing, and the mixed training loop."""
import json

import pytest
import torch
import torch.nn.functional as F
from peft import LoraConfig, get_peft_model
from transformers import (
    LlamaConfig, LlamaForCausalLM, Qwen2Config, Qwen2ForCausalLM,
    Gemma2Config, Gemma2ForCausalLM, Gemma3TextConfig, Gemma3ForCausalLM,
    MistralConfig, MistralForCausalLM,
)

from diffusion_lm.distillation import (
    assert_frozen_teacher, causal_teacher_logits, resolve_distillation,
    selected_distillation_loss,
)
from diffusion_lm.modeling import forward_bidirectional, forward_bidirectional_selected


def tiny_model(family="llama", dropout=0.0, attention="eager"):
    torch.manual_seed(4)
    options = dict(vocab_size=32, hidden_size=16, intermediate_size=32,
                   num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2,
                   head_dim=8, attention_dropout=dropout, use_cache=False)
    classes = {
        "llama": (LlamaConfig, LlamaForCausalLM),
        "qwen": (Qwen2Config, Qwen2ForCausalLM),
        "gemma2": (Gemma2Config, Gemma2ForCausalLM),
        "gemma3": (Gemma3TextConfig, Gemma3ForCausalLM),
        "mistral": (MistralConfig, MistralForCausalLM),
    }
    config_class, model_class = classes[family]
    config = config_class(**options)
    if family in {"mistral", "gemma2", "gemma3"}:
        config.sliding_window = 3
    config._attn_implementation = attention
    base = model_class(config)
    for parameter in base.parameters():
        parameter.requires_grad = False
    return get_peft_model(base, LoraConfig(r=2, target_modules=["q_proj", "v_proj"], lora_dropout=dropout))


@pytest.mark.parametrize("family", ["llama", "qwen", "gemma2", "gemma3", "mistral"])
@pytest.mark.parametrize("attention", ["eager", "sdpa"])
def test_teacher_matches_original_causal_model_at_previous_position(family, attention):
    model = tiny_model(family, attention=attention)
    labels = torch.tensor([[1, 4, 5, 6, 2], [1, 7, 8, 2, 2]])
    selection = torch.tensor([[True, False, True, True, False], [False, True, False, True, True]])
    valid = selection.clone()
    valid[:, 0] = False
    rows, positions = valid.nonzero(as_tuple=True)
    model.eval()
    with torch.no_grad(), model.disable_adapter():
        expected = model(labels).logits[rows, positions - 1]
    # Simulate the student loader's attention flags.
    model.config.is_causal = False
    model.config.use_bidirectional_attention = True
    model.train()
    observed = causal_teacher_logits(model, labels, selection, chunk_size=2)
    assert torch.allclose(observed, expected, atol=1e-6), (observed - expected).abs().max()
    assert not observed.requires_grad
    assert model.training and model.config.is_causal is False
    assert model.config.use_bidirectional_attention is True
    # The experimental selected-logit student path must also preserve the
    # architecture's logit transformation (Gemma 2 softcapping in particular).
    model.eval()
    padding = torch.zeros_like(labels, dtype=torch.bool)
    full = forward_bidirectional(model, labels, padding)
    selected, _, _ = forward_bidirectional_selected(model, labels, padding, valid)
    assert torch.allclose(selected, full[valid], atol=1e-6)


@pytest.mark.parametrize("family", ["llama", "qwen", "gemma2", "gemma3", "mistral"])
def test_teacher_never_sees_current_or_future_label_and_ignores_trained_adapters(family):
    model = tiny_model(family, dropout=0.4)
    assert_frozen_teacher(model)
    labels = torch.tensor([[1, 4, 5, 6, 2]])
    mask = torch.tensor([[False, False, True, False, False]])
    model.train()
    before = causal_teacher_logits(model, labels, mask)
    changed = labels.clone()
    changed[:, 2:] = torch.tensor([10, 11, 12])
    with torch.no_grad():
        for name, parameter in model.named_parameters():
            if "lora_" in name:
                parameter.normal_(mean=1, std=0.1)
    after = causal_teacher_logits(model, changed, mask)
    assert torch.equal(before, after)
    changed[:, 1] = 13
    assert not torch.allclose(after, causal_teacher_logits(model, changed, mask))
    assert model.training
    assert all(parameter.requires_grad == ("lora_" in name) for name, parameter in model.named_parameters())


def test_teacher_context_restores_student_after_failure(monkeypatch):
    model = tiny_model()
    model.train()
    model.config.is_causal = False
    def fail(*args, **kwargs):
        raise RuntimeError("test failure")
    monkeypatch.setattr(model.get_base_model().model, "forward", fail)
    with pytest.raises(RuntimeError, match="test failure"):
        causal_teacher_logits(model, torch.tensor([[1, 2]]), torch.tensor([[False, True]]))
    assert model.training and model.config.is_causal is False
    assert not model.base_model.model.model.layers[0].self_attn.q_proj.disable_adapters


@pytest.mark.parametrize("temperature", [1.0, 2.5])
@pytest.mark.parametrize("region_weighting", [False, True])
def test_full_vocab_kl_and_gradient_match_dense_reference(temperature, region_weighting):
    torch.manual_seed(3)
    logits = torch.randn(5, 13, requires_grad=True)
    teacher = torch.randn_like(logits, requires_grad=True)
    mask = torch.tensor([[False, True, True, True], [False, False, True, True]])
    answer = torch.tensor([[False, True, True, False], [False, True, True, False]])
    padding = torch.tensor([[False, False, False, True], [False, False, False, True]])
    batch = dict(loss_mask=mask, answer_mask=answer, padding_mask=padding,
                 sampled_t=torch.tensor([0.5, 0.8]), token_loss_weights=torch.tensor([[1., 1., 0.7, 1.], [1., 1., 1.2, 1.]]))
    settings = dict(temperature=temperature, chunk_size=2)
    loss = selected_distillation_loss(logits, teacher, batch, settings, use_t_weighting=True,
                                      answer_padding_weights=(0.9, 0.1) if region_weighting else None,
                                      eos_padding_loss=True)
    rows, positions = mask.nonzero(as_tuple=True)
    p = F.softmax(teacher.detach() / temperature, -1)
    q_log = F.log_softmax(logits / temperature, -1)
    kl = (p * (p.log() - q_log)).sum(-1) * temperature**2
    weighted = kl * batch["token_loss_weights"][rows, positions] / batch["sampled_t"][rows]
    expected = 0
    if region_weighting:
        for region, coefficient in ((answer, 0.9), (padding, 0.1)):
            expected += coefficient * sum(
                weighted[(rows == row) & region[rows, positions]].sum() / region[row].sum()
                for row in range(2)) / 2
    else:
        expected = sum(weighted[rows == row].sum() / (answer | padding)[row].sum() for row in range(2)) / 2
    gradient = torch.autograd.grad(expected, logits, retain_graph=True)[0]
    loss.backward()
    assert torch.allclose(loss, expected, atol=1e-6)
    assert torch.allclose(logits.grad, gradient, atol=1e-6)
    assert teacher.grad is None


def test_no_preceding_position_produces_differentiable_zero():
    logits = torch.randn(1, 8, requires_grad=True)
    batch = {"loss_mask": torch.tensor([[True]])}
    loss = selected_distillation_loss(logits, torch.empty(0, 8), batch,
                                      dict(chunk_size=2, temperature=1),
                                      use_t_weighting=False, answer_padding_weights=None)
    loss.backward()
    assert loss == 0 and torch.equal(logits.grad, torch.zeros_like(logits))


@pytest.mark.parametrize("settings", [dict(weight=-1), dict(weight=1.1), dict(temperature=0),
                                    dict(temperature=float("nan")), dict(chunk_size=0), dict(enabled="yes")])
def test_invalid_settings_fail_early(settings):
    with pytest.raises(ValueError):
        resolve_distillation({"distillation": settings})


def test_weight_zero_is_baseline_and_trainable_base_is_rejected():
    assert resolve_distillation({"distillation": dict(enabled=True, weight=0)})["enabled"] is False
    with pytest.raises(ValueError, match="train_normalization_layers"):
        resolve_distillation({"distillation": dict(enabled=True)})
    model = tiny_model()
    model.get_base_model().model.norm.weight.requires_grad = True
    with pytest.raises(ValueError, match="frozen"):
        assert_frozen_teacher(model)


@pytest.mark.parametrize("selected_logits", [False, True])
@pytest.mark.parametrize("weight", [0.0, 0.5, 1.0])
def test_actual_training_loop_mixes_losses_and_only_updates_lora(tmp_path, monkeypatch, weight, selected_logits):
    from datasets import Dataset
    from test_data_corruption_loss import ToyTokenizer, row
    from diffusion_lm import training
    from train import load_training_config

    model = tiny_model()
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    original = {name: p.detach().clone() for name, p in model.named_parameters()}
    class Tokenizer(ToyTokenizer):
        def save_pretrained(self, path):
            pass
    data = Dataset.from_list([row(i) for i in range(4)])
    monkeypatch.setattr(training, "load_training_data", lambda *args: (Tokenizer(), data, data, data))
    monkeypatch.setattr(training, "load_denoising_model", lambda config: (model, {}))
    calls = []
    original_teacher = training.causal_teacher_logits
    def teacher(*args, **kwargs):
        calls.append(True)
        return original_teacher(*args, **kwargs)
    monkeypatch.setattr(training, "causal_teacher_logits", teacher)
    config = load_training_config("llama", "quick", output_dir=str(tmp_path / "run"), max_updates=2)
    config.update(precision="fp32", batch_size=1, eval_batch_size=1, num_workers=0,
                  gradient_accumulation_steps=2, validation_steps=2, checkpoint_steps=2,
                  validation_samples=2, logging_steps=1, learning_rate=1e-3,
                  max_sequence_length=16, warmup_steps=0, selected_logit_optimization=selected_logits,
                  generation_perplexity={"enabled": False},
                  distillation=dict(enabled=True, weight=weight, temperature=1.0, chunk_size=2))
    result = training.run_training(config)
    records = [json.loads(line) for line in (tmp_path / "run/metrics.jsonl").read_text().splitlines()]
    records = [record for record in records if record["split"] == "train"]
    assert len(calls) == (4 if weight else 0)
    assert len(records) == 2 and result["weighted_loss"] > 0
    for record in records:
        assert record["weighted_loss"] == pytest.approx(
            (1 - weight) * record["denoising_loss"] + weight * record["distillation_loss"])
        assert record["elapsed_seconds"] > 0
    for name, parameter in model.named_parameters():
        if "lora_" not in name:
            assert torch.equal(parameter, original[name]), name
            assert parameter.grad is None
    assert any(not torch.equal(parameter, original[name]) for name, parameter in model.named_parameters() if "lora_" in name)
    assert (tmp_path / "run/best/adapter_config.json").is_file()
