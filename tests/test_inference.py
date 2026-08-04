import json
from pathlib import Path

import pytest
import torch

from diffusion_lm.inference import InferenceSession, _precision_dtype, _prompt_ids, _remask_offsets, _safe_adapter_path, denoise_stream, find_adapters, forward_denoising, load_local_legacy_session, preflight_session
from diffusion_lm.legacy_compat import LegacyCustomTransformerConfig, LegacyCustomTransformerModel, install_legacy_pickle_modules, patch_legacy_lora_modules, restore_legacy_pickle_modules


def test_adapter_discovery_only_lists_valid_saved_adapters(tmp_path):
    valid = tmp_path / "run-a" / "best"
    valid.mkdir(parents=True)
    (valid / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": "tiny"}))
    incomplete = tmp_path / "run-b" / "checkpoint-1"
    incomplete.mkdir(parents=True)
    assert find_adapters(tmp_path) == ["run-a/best"]
    assert _safe_adapter_path(tmp_path, "run-a/best") == valid.resolve()
    with pytest.raises(ValueError):
        _safe_adapter_path(tmp_path, "../outside")


def test_prompt_ids_falls_back_for_systemless_chat_template():
    class SystemlessTokenizer:
        chat_template = "gemma-like"
        name_or_path = "test/gemma-like"

        def __init__(self):
            self.calls = []

        def apply_chat_template(self, messages, **_):
            self.calls.append(messages)
            if any(message["role"] == "system" for message in messages):
                class TemplateError(Exception):
                    pass
                raise TemplateError("System role not supported")
            return [3, 4]

    tokenizer = SystemlessTokenizer()
    assert _prompt_ids(tokenizer, "What?", "Be brief.") == [3, 4]
    assert tokenizer.calls[1] == [{"role": "user", "content": "Be brief.\n\nWhat?"}]


def test_legacy_prompt_ids_do_not_require_a_chat_template():
    class BaseLlamaTokenizer:
        name_or_path = "base-llama"
        chat_template = None

        def encode(self, text, **_):
            self.prompt = text
            return [1, 2]

    tokenizer = BaseLlamaTokenizer()
    assert _prompt_ids(tokenizer, "What?", "Be brief.", "legacy_llama") == [1, 2]
    assert "<|start_header_id|>assistant<|end_header_id|>" in tokenizer.prompt
    assert "<|start_header_id|>system<|end_header_id|>\nBe brief.\n<|start_header_id|>user" in tokenizer.prompt


def test_bf16_inference_falls_back_to_fp16_on_non_bf16_cuda(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_bf16_supported", lambda: False)
    assert _precision_dtype("bf16", torch.device("cuda")) == torch.float16


def test_confidence_guided_remasking_targets_the_least_confident_tokens():
    confidence = torch.tensor([.9, .2, .7, .1])
    assert _remask_offsets(confidence, .5, True).tolist() == [3, 1]


def test_legacy_wrapper_uses_its_own_forward_without_duplicate_keywords():
    class InnerModel(torch.nn.Module):
        def forward(self, input_ids, attention_mask, output_hidden_states, use_cache):
            self.called = {"input_ids": input_ids, "attention_mask": attention_mask, "output_hidden_states": output_hidden_states, "use_cache": use_cache}
            return type("Output", (), {"logits": torch.zeros((*input_ids.shape, 3))})()

    class LegacyPeftOuter(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.base_model = InnerModel()

        def forward(self, *_args, **_kwargs):
            raise AssertionError("version-sensitive PeftModel.forward should be bypassed")

    class LegacyModel(LegacyCustomTransformerModel):
        def __init__(self):
            super().__init__(LegacyCustomTransformerConfig(vocab_size=3))
            self.llama = LegacyPeftOuter()

    model = LegacyModel()
    session = InferenceSession(model, None, torch.device("cpu"), Path("."), {}, 0, legacy_wrapper=True)
    logits = forward_denoising(session, torch.tensor([[1, 2]]), torch.zeros((1, 2), dtype=torch.bool))
    assert logits.shape == (1, 2, 3)
    assert model.llama.base_model.called["use_cache"] is False


def test_legacy_pickle_compatibility_registers_main_module_aliases():
    import __main__
    previous = install_legacy_pickle_modules()
    try:
        assert hasattr(__main__, "CustomTransformerModel")
        assert hasattr(__main__, "CustomTransformerConfig")
    finally:
        restore_legacy_pickle_modules(previous)


def test_legacy_lora_patch_enables_the_current_peft_vanilla_branch():
    class OldLoraLinear(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.lora_A = torch.nn.ModuleDict()

    model = torch.nn.Sequential(OldLoraLinear(), OldLoraLinear())
    assert patch_legacy_lora_modules(model) == 2
    assert all(module.lora_variant == {} for module in model)


def test_local_legacy_loader_rejects_missing_checkpoint(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        load_local_legacy_session(tmp_path / "missing.pth", "tokenizer", "cpu")


def test_preflight_runs_a_real_forward_pass():
    class Tokenizer:
        eos_token_id = 2
        chat_template = "template"
        name_or_path = "toy"

        def apply_chat_template(self, *_args, **_kwargs):
            return [1, 2]

    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.zeros(1))

        def forward(self, input_ids, attention_mask, use_cache):
            return type("Output", (), {"logits": torch.zeros((*input_ids.shape, 4))})()

    session = InferenceSession(Model(), Tokenizer(), torch.device("cpu"), Path("."), {}, 3)
    assert preflight_session(session) == (3, 4)


def test_early_stopping_requires_three_identical_complete_predictions():
    class Tokenizer:
        eos_token_id = 2
        chat_template = "template"
        name_or_path = "toy"

        def apply_chat_template(self, *_args, **_kwargs):
            return [1, 2]

        def decode(self, token_ids, **_kwargs):
            return " ".join(map(str, token_ids))

    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.zeros(1))

        def forward(self, input_ids, attention_mask, use_cache):
            logits = torch.full((*input_ids.shape, 4), -100.0)
            logits[..., 1] = 100.0
            return type("Output", (), {"logits": logits})()

    session = InferenceSession(Model(), Tokenizer(), torch.device("cpu"), Path("."), {}, 3)
    states = list(denoise_stream(session, "Test", "System", 2, 6, .5, 1., 1, 1234, early_stopping=True))
    assert len(states) == 3
    assert "stopped early" in states[-1][1]
    assert "2 output tokens" in states[-1][1]


def test_llada_session_uses_the_app_denoising_loop():
    class Tokenizer:
        eos_token_id = 2
        name_or_path = "toy-llada"

        def apply_chat_template(self, messages, **_kwargs):
            self.messages = messages
            return [1]

        def decode(self, token_ids, **_kwargs):
            return " ".join(map(str, token_ids))

    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.weight = torch.nn.Parameter(torch.zeros(1))

        def forward(self, input_ids, attention_mask):
            self.attention_mask = attention_mask
            self.inference_mode = torch.is_inference_mode_enabled()
            logits = torch.full((*input_ids.shape, 10), -100.0)
            logits[..., 3] = 100.0
            return type("Output", (), {"logits": logits})()

    tokenizer = Tokenizer()
    model = Model()
    session = InferenceSession(model, tokenizer, torch.device("cpu"), Path("."), {}, 9, llada=True, prompt_format="llada")
    states = list(denoise_stream(session, "Question", "System", 3, 2, .5, 0., 20, 1234))

    assert len(states) == 2
    assert states[-1][0] == "3 3 3"
    assert "Denoising step 1/2" in states[0][1]
    assert tokenizer.messages == [{"role": "user", "content": "System\n\nQuestion"}]
    assert model.attention_mask.dtype == torch.long
    assert model.inference_mode is True
