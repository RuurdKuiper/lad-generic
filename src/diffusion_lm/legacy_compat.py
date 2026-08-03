"""Compatibility classes for trusted full-model checkpoints from the legacy app."""
from __future__ import annotations

import sys
import types

import torch
import torch.nn as nn
from transformers import PreTrainedModel, PretrainedConfig


class LegacyCustomTransformerConfig(PretrainedConfig):
    """Pickle-compatible replacement for ``model_config.CustomTransformerConfig``."""

    def __init__(self, vocab_size=128256, hidden_size=4096, num_layers=32, num_heads=32,
                 prediction_chunk=256, dropout=0, max_position_embeddings=4096,
                 masking_type="bidirectional", **kwargs):
        super().__init__(**kwargs)
        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.dropout = dropout
        self.prediction_chunk = prediction_chunk
        self.max_position_embeddings = max_position_embeddings
        self.input_size = prediction_chunk
        self.masking_type = masking_type


class LegacyCustomTransformerModel(PreTrainedModel):
    """Pickle-compatible legacy wrapper that supplies full bidirectional attention."""

    config_class = LegacyCustomTransformerConfig

    def forward(self, input_ids, labels=None, **kwargs):
        batch_size, seq_len = input_ids.shape
        masking_type = getattr(self.config, "masking_type", "bidirectional")
        if masking_type == "bidirectional":
            base_mask = torch.ones(seq_len, seq_len, dtype=torch.bool, device=input_ids.device)
        elif masking_type == "bidirectional_masked":
            base_mask = torch.ones(seq_len, seq_len, dtype=torch.bool, device=input_ids.device)
            base_mask.fill_diagonal_(False)
        elif masking_type == "unidirectional":
            base_mask = torch.tril(torch.ones(seq_len, seq_len, dtype=torch.bool, device=input_ids.device))
        else:
            raise ValueError(f"Unknown masking type: {masking_type}")
        attention_mask = base_mask.unsqueeze(0).unsqueeze(1).expand(batch_size, 1, seq_len, seq_len).to(dtype=torch.float32)
        outputs = self.llama(input_ids, attention_mask=attention_mask, output_hidden_states=True, use_cache=False, **kwargs)
        logits = outputs.logits[:, :, :self.config.vocab_size].view(batch_size, seq_len, self.config.vocab_size)
        if labels is None:
            return {"logits": logits}
        loss = nn.CrossEntropyLoss()(logits.view(-1, self.config.vocab_size), labels.view(-1))
        return {"loss": loss, "logits": logits}


_MISSING = object()


def install_legacy_pickle_modules() -> dict[str, object]:
    """Temporarily register the historical class locations expected by torch.load."""
    previous: dict[str, object] = {name: sys.modules.get(name) for name in ("model_config", "models")}
    config_module = types.ModuleType("model_config")
    config_module.CustomTransformerConfig = LegacyCustomTransformerConfig
    model_module = types.ModuleType("models")
    model_module.CustomTransformerModel = LegacyCustomTransformerModel
    sys.modules["model_config"] = config_module
    sys.modules["models"] = model_module
    # Some notebook-created full checkpoints pickle these classes under
    # ``__main__`` rather than their original source modules.
    main_module = sys.modules["__main__"]
    for name, value in {
        "CustomTransformerConfig": LegacyCustomTransformerConfig,
        "CustomTransformerModel": LegacyCustomTransformerModel,
    }.items():
        previous[f"__main__.{name}"] = getattr(main_module, name, _MISSING)
        setattr(main_module, name, value)
    return previous


def restore_legacy_pickle_modules(previous: dict[str, object]) -> None:
    """Restore module registrations changed for one trusted checkpoint load."""
    for name in ("model_config", "models"):
        module = previous[name]
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module  # type: ignore[assignment]
    main_module = sys.modules["__main__"]
    for name in ("CustomTransformerConfig", "CustomTransformerModel"):
        previous_value = previous[f"__main__.{name}"]
        if previous_value is _MISSING:
            delattr(main_module, name)
        else:
            setattr(main_module, name, previous_value)
