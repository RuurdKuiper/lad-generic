import torch
from transformers import LlamaConfig, LlamaForCausalLM
from peft import LoraConfig, get_peft_model
from diffusion_lm.modeling import bidirectional_attention_mask, parameter_audit


def test_4d_mask_is_noncausal_and_blocks_padding():
    mask = bidirectional_attention_mask(torch.tensor([[False, False, True]]), torch.float32)
    assert mask.shape == (1, 1, 3, 3)
    assert mask[0, 0, 0, 1] == 0  # earlier query sees later key
    assert mask[0, 0, 0, 2] < -1e20
    assert mask[0, 0, 2, 0] < -1e20


def test_tiny_llama_earlier_logits_depend_on_later_visible_token():
    torch.manual_seed(2)
    model = LlamaForCausalLM(LlamaConfig(vocab_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2))
    model.eval()
    from diffusion_lm.modeling import forward_bidirectional
    a = torch.tensor([[3, 4, 5]])
    b = torch.tensor([[3, 4, 6]])
    padding = torch.zeros_like(a, dtype=torch.bool)
    assert not torch.allclose(forward_bidirectional(model, a, padding)[:, 0], forward_bidirectional(model, b, padding)[:, 0])


def test_only_lora_and_norms_are_trainable():
    base = LlamaForCausalLM(LlamaConfig(vocab_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2))
    for p in base.parameters(): p.requires_grad = False
    model = get_peft_model(base, LoraConfig(r=2, target_modules=["q_proj", "v_proj", "o_proj"], bias="none"))
    for name, p in model.named_parameters():
        if "norm" in name.lower(): p.requires_grad = True
    audit = parameter_audit(model)
    assert audit["lora_parameters"] > 0 and audit["normalization_parameters"] > 0
    assert audit["other_trainable_parameters"] == 0
