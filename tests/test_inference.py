import json

import pytest
import torch

from diffusion_lm.inference import _precision_dtype, _prompt_ids, _safe_adapter_path, find_adapters


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


def test_bf16_inference_falls_back_to_fp16_on_non_bf16_cuda(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_bf16_supported", lambda: False)
    assert _precision_dtype("bf16", torch.device("cuda")) == torch.float16
