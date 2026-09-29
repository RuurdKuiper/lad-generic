import pytest
import torch
from types import SimpleNamespace
from transformers import LlamaConfig, LlamaForCausalLM, MistralConfig, MistralForCausalLM
from peft import LoraConfig, PeftModel, get_peft_model
from diffusion_lm.modeling import (
    TRAINABLE_BASE_STATE_FILENAME,
    _unfreeze_last_transformer_layers,
    _unfreeze_output_head,
    bidirectional_attention_mask,
    load_trainable_base_state,
    load_denoising_model,
    parameter_audit,
)


def test_4d_mask_is_noncausal_and_padding_is_visible():
    mask = bidirectional_attention_mask(torch.tensor([[False, False, True]]), torch.float32)
    assert mask.shape == (1, 1, 3, 3)
    assert mask[0, 0, 0, 1] == 0  # earlier query sees later key
    assert mask[0, 0, 0, 2] == 0  # real queries can read padded EOS keys
    assert mask[0, 0, 2, 0] == 0  # padded EOS queries can read real context


def test_identical_bidirectional_attention_masks_are_cached():
    padding = torch.tensor([[False, False, True]])
    first = bidirectional_attention_mask(padding, torch.float32)
    second = bidirectional_attention_mask(padding.clone(), torch.float32)
    assert first.data_ptr() == second.data_ptr()


def test_tiny_llama_earlier_logits_depend_on_later_visible_token():
    torch.manual_seed(2)
    model = LlamaForCausalLM(LlamaConfig(vocab_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2))
    model.eval()
    from diffusion_lm.modeling import forward_bidirectional
    a = torch.tensor([[3, 4, 5]])
    b = torch.tensor([[3, 4, 6]])
    padding = torch.zeros_like(a, dtype=torch.bool)
    assert not torch.allclose(forward_bidirectional(model, a, padding)[:, 0], forward_bidirectional(model, b, padding)[:, 0])


def test_tiny_mistral_earlier_logits_depend_on_later_visible_token():
    torch.manual_seed(2)
    model = MistralForCausalLM(MistralConfig(vocab_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2, head_dim=8, sliding_window=8))
    model.eval()
    from diffusion_lm.modeling import forward_bidirectional
    a = torch.tensor([[3, 4, 5]])
    b = torch.tensor([[3, 4, 6]])
    padding = torch.zeros_like(a, dtype=torch.bool)
    assert not torch.allclose(forward_bidirectional(model, a, padding)[:, 0], forward_bidirectional(model, b, padding)[:, 0])


def test_selected_lm_head_logits_and_gradients_match_full_forward():
    torch.manual_seed(3)
    base = LlamaForCausalLM(LlamaConfig(vocab_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2))
    model = get_peft_model(base, LoraConfig(r=2, target_modules=["q_proj", "v_proj"], bias="none"))
    model.eval()
    from diffusion_lm.modeling import forward_bidirectional, forward_bidirectional_selected

    input_ids = torch.tensor([[3, 4, 5], [6, 7, 8]])
    padding = torch.zeros_like(input_ids, dtype=torch.bool)
    selection = torch.tensor([[True, False, True], [False, True, False]])
    labels = torch.tensor([[1, 2, 3], [4, 5, 6]])

    full_logits = forward_bidirectional(model, input_ids, padding)
    full_loss = torch.nn.functional.cross_entropy(full_logits[selection], labels[selection])
    full_loss.backward()
    full_gradients = {
        name: parameter.grad.detach().clone()
        for name, parameter in model.named_parameters()
        if parameter.requires_grad and parameter.grad is not None
    }
    model.zero_grad(set_to_none=True)

    selected_logits, example_ids, token_ids = forward_bidirectional_selected(
        model, input_ids, padding, selection
    )
    selected_loss = torch.nn.functional.cross_entropy(
        selected_logits, labels[example_ids, token_ids]
    )
    selected_loss.backward()

    assert torch.allclose(selected_logits, full_logits[selection])
    assert torch.allclose(selected_loss, full_loss)
    for name, expected in full_gradients.items():
        assert torch.allclose(dict(model.named_parameters())[name].grad, expected), name


def test_quantized_like_model_uses_a_floating_attention_mask_dtype():
    class QuantizedLikeModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.quantized_weight = torch.nn.Parameter(torch.zeros(1, dtype=torch.uint8), requires_grad=False)
            self.compute_weight = torch.nn.Parameter(torch.zeros(1, dtype=torch.float16), requires_grad=False)

        def forward(self, input_ids, attention_mask, use_cache):
            self.mask_dtype = attention_mask.dtype
            return SimpleNamespace(logits=torch.zeros((*input_ids.shape, 4)))

    from diffusion_lm.modeling import forward_bidirectional
    model = QuantizedLikeModel()
    forward_bidirectional(model, torch.tensor([[1, 2]]), torch.tensor([[False, False]]))
    assert model.mask_dtype == torch.float16


def test_only_lora_and_norms_are_trainable():
    base = LlamaForCausalLM(LlamaConfig(vocab_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2))
    for p in base.parameters(): p.requires_grad = False
    model = get_peft_model(base, LoraConfig(r=2, target_modules=["q_proj", "v_proj", "o_proj"], bias="none"))
    for name, p in model.named_parameters():
        if "norm" in name.lower(): p.requires_grad = True
    audit = parameter_audit(model)
    assert audit["lora_parameters"] > 0 and audit["normalization_parameters"] > 0
    assert audit["other_trainable_parameters"] == 0


def test_full_finetuning_audit_requires_every_parameter_trainable():
    model = LlamaForCausalLM(LlamaConfig(
        vocab_size=32,
        hidden_size=16,
        intermediate_size=32,
        num_hidden_layers=1,
        num_attention_heads=2,
        num_key_value_heads=2,
    ))

    audit = parameter_audit(model, full_finetuning=True)
    assert audit["full_finetuning"] is True
    assert audit["trainable_percentage"] == 100.0
    assert audit["total_trainable_parameters"] == audit["total_model_parameters"]

    next(model.parameters()).requires_grad = False
    with pytest.raises(AssertionError, match="unexpected_frozen_full_model_parameters"):
        parameter_audit(model, full_finetuning=True)


def test_full_finetuning_loader_does_not_attach_lora(monkeypatch, tmp_path):
    import diffusion_lm.modeling as modeling

    model = LlamaForCausalLM(LlamaConfig(
        vocab_size=32,
        hidden_size=16,
        intermediate_size=32,
        num_hidden_layers=1,
        num_attention_heads=2,
        num_key_value_heads=2,
    ))
    monkeypatch.setattr(modeling.AutoModelForCausalLM, "from_pretrained", lambda *args, **kwargs: model)

    loaded, audit = load_denoising_model({
        "model_name_or_path": "merged-model",
        "base_model_cache_dir": str(tmp_path / "models"),
        "precision": "bf16",
        "quantization": "none",
        "full_finetuning": True,
        "gradient_checkpointing": False,
    })

    assert loaded is model
    assert not isinstance(loaded, PeftModel)
    assert all(parameter.requires_grad for parameter in loaded.parameters())
    assert audit["resolved_lora_targets"] == []


def test_final_transformer_layers_can_be_trained_with_lora():
    base = LlamaForCausalLM(LlamaConfig(
        vocab_size=32,
        hidden_size=16,
        intermediate_size=32,
        num_hidden_layers=3,
        num_attention_heads=2,
        num_key_value_heads=2,
    ))
    for parameter in base.parameters():
        parameter.requires_grad = False
    model = get_peft_model(base, LoraConfig(r=2, target_modules=["q_proj", "v_proj"], bias="none"))

    assert _unfreeze_last_transformer_layers(model, 2) == [1, 2]
    audit = parameter_audit(model, train_last_n_layers=2)

    assert audit["trainable_transformer_layer_indices"] == [1, 2]
    assert audit["transformer_layer_parameters"] > 0
    assert audit["other_trainable_parameters"] == 0
    assert not model.base_model.model.model.layers[0].self_attn.o_proj.weight.requires_grad
    assert model.base_model.model.model.layers[1].self_attn.o_proj.weight.requires_grad
    assert model.base_model.model.model.layers[2].mlp.down_proj.weight.requires_grad
    assert not model.base_model.model.model.embed_tokens.weight.requires_grad
    assert not model.base_model.model.lm_head.weight.requires_grad


def test_trainable_base_state_is_restored(tmp_path):
    base = LlamaForCausalLM(LlamaConfig(
        vocab_size=32,
        hidden_size=16,
        intermediate_size=32,
        num_hidden_layers=2,
        num_attention_heads=2,
        num_key_value_heads=2,
    ))
    for parameter in base.parameters():
        parameter.requires_grad = False
    model = get_peft_model(base, LoraConfig(r=2, target_modules=["q_proj"], bias="none"))
    _unfreeze_last_transformer_layers(model, 1)
    name, parameter = next(
        (name, parameter)
        for name, parameter in model.named_parameters()
        if "layers.1.mlp.down_proj.weight" in name
    )
    expected = torch.full_like(parameter, 0.25)
    torch.save({name: expected}, tmp_path / TRAINABLE_BASE_STATE_FILENAME)
    parameter.data.zero_()

    assert load_trainable_base_state(model, tmp_path) == 1
    assert torch.equal(parameter, expected)


def test_output_head_can_be_trained_while_embeddings_stay_frozen():
    base = LlamaForCausalLM(LlamaConfig(
        vocab_size=32,
        hidden_size=16,
        intermediate_size=32,
        num_hidden_layers=1,
        num_attention_heads=2,
        num_key_value_heads=2,
        tie_word_embeddings=False,
    ))
    for parameter in base.parameters():
        parameter.requires_grad = False
    model = get_peft_model(base, LoraConfig(r=2, target_modules=["q_proj"], bias="none"))

    assert _unfreeze_output_head(model, True) == 32 * 16
    audit = parameter_audit(model, train_lm_head=True)

    assert audit["lm_head_parameters"] == 32 * 16
    assert model.base_model.model.lm_head.weight.requires_grad
    assert not model.base_model.model.model.embed_tokens.weight.requires_grad
    assert audit["other_trainable_parameters"] == 0


def test_output_head_lora_keeps_base_head_frozen_and_survives_reload(tmp_path):
    config = LlamaConfig(
        vocab_size=32,
        hidden_size=16,
        intermediate_size=32,
        num_hidden_layers=1,
        num_attention_heads=2,
        num_key_value_heads=2,
        tie_word_embeddings=False,
    )
    base = LlamaForCausalLM(config)
    for parameter in base.parameters():
        parameter.requires_grad = False
    model = get_peft_model(
        base,
        LoraConfig(r=2, target_modules=["q_proj", "v_proj", "lm_head"], bias="none"),
    )

    audit = parameter_audit(model)
    assert audit["lm_head_parameters"] == 0
    assert audit["lora_parameters"] > 0
    assert not model.base_model.model.lm_head.base_layer.weight.requires_grad
    output_lora = {
        name: parameter.detach().clone()
        for name, parameter in model.named_parameters()
        if "lm_head.lora_" in name
    }
    assert output_lora

    model.save_pretrained(tmp_path, safe_serialization=True, save_embedding_layers=False)
    reloaded_base = LlamaForCausalLM(config)
    reloaded = PeftModel.from_pretrained(reloaded_base, tmp_path)
    reloaded_parameters = dict(reloaded.named_parameters())
    for name, expected in output_lora.items():
        assert name in reloaded_parameters
        assert torch.equal(reloaded_parameters[name], expected)
