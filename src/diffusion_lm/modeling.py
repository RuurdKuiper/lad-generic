"""Causal-LM loading adapted for bidirectional denoising."""
from __future__ import annotations
from collections import Counter
from typing import Any

import torch
import os
from pathlib import Path
from peft import LoraConfig, PeftModel, TaskType, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM


def bidirectional_attention_mask(padding_mask: torch.Tensor, dtype: torch.dtype) -> torch.Tensor:
    """A 4-D additive full-attention mask accepted unchanged by Transformers >=5.

    `padding_mask` is retained for loss/padding bookkeeping, but padding is
    intentionally visible to attention. Repeated EOS padding is part of the
    configured context-width signal: real and padded queries can attend to all
    positions, allowing the model to learn concise answers under wide contexts.
    """
    allowed = torch.ones(
        (padding_mask.shape[0], 1, padding_mask.shape[1], padding_mask.shape[1]),
        device=padding_mask.device,
        dtype=torch.bool,
    )
    mask = torch.zeros(allowed.shape, device=padding_mask.device, dtype=dtype)
    return mask.masked_fill(~allowed, torch.finfo(dtype).min)


def _target_modules(model: torch.nn.Module, requested: list[str]) -> list[str]:
    """Verify every requested LoRA projection exists in the loaded architecture."""
    available = {name.rsplit(".", 1)[-1] for name, _ in model.named_modules()}
    missing = [name for name in requested if name not in available]
    if missing:
        raise ValueError(f"LoRA target modules missing from {model.config.model_type}: {missing}; available suffixes include {sorted(available)[:40]}")
    return requested


def parameter_audit(model: torch.nn.Module) -> dict[str, Any]:
    """Assert the intended trainable set and return parameter-count diagnostics."""
    named = list(model.named_parameters())
    trainable = [(name, p) for name, p in named if p.requires_grad]
    total = sum(p.numel() for _, p in named)
    categories = Counter()
    unexpected = []
    for name, p in trainable:
        if "lora_" in name:
            categories["lora"] += p.numel()
        elif "norm" in name.lower():
            categories["norm"] += p.numel()
        else:
            categories["other"] += p.numel()
            unexpected.append(name)
    frozen_embedding = all(not p.requires_grad for n, p in named if any(x in n.lower() for x in ("embed_tokens", "embed_tokens", "wte")))
    frozen_lm_head = all(not p.requires_grad for n, p in named if "lm_head" in n)
    if not frozen_embedding or not frozen_lm_head or unexpected:
        raise AssertionError({"embeddings_frozen": frozen_embedding, "lm_head_frozen": frozen_lm_head, "unexpected_trainable": unexpected})
    trainable_count = sum(p.numel() for _, p in trainable)
    return {"lora_parameters": categories["lora"], "normalization_parameters": categories["norm"], "other_trainable_parameters": categories["other"], "total_trainable_parameters": trainable_count, "total_model_parameters": total, "trainable_percentage": 100 * trainable_count / total, "trainable_names": [n for n, _ in trainable]}


def load_denoising_model(config: dict[str, Any]) -> tuple[torch.nn.Module, dict[str, Any]]:
    """Load a base CausalLM, attach LoRA, unfreeze norms, and audit it."""
    checkpoint = config["model_name_or_path"]
    precision = config.get("precision", "bf16")
    dtype = {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}.get(precision)
    if dtype is None:
        raise ValueError(f"Unknown precision {precision}")
    # No device_map: accelerate owns device placement in distributed runs.
    model_cache = Path(config.get("base_model_cache_dir", "base_models")); model_cache.mkdir(parents=True, exist_ok=True)
    quantization = str(config.get("quantization", "none")).lower()
    load_kwargs = dict(dtype=dtype, trust_remote_code=False, token=os.getenv("HF_TOKEN"), cache_dir=str(model_cache))
    if quantization in {"4bit", "4-bit", "qlora"}:
        try:
            from transformers import BitsAndBytesConfig
            import bitsandbytes  # noqa: F401
        except ImportError as exc:
            raise ImportError("quantization=4bit requires CUDA bitsandbytes; install with `pip install -e '.[cuda]'`") from exc
        if not torch.cuda.is_available():
            raise RuntimeError("4-bit bitsandbytes quantization requires an NVIDIA CUDA device")
        compute_dtype = {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}.get(str(config.get("compute_dtype", precision)), dtype)
        load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type=str(config.get("quantization_type", "nf4")), bnb_4bit_compute_dtype=compute_dtype, bnb_4bit_use_double_quant=bool(config.get("double_quant", True)))
    elif quantization not in {"none", "off", "false"}:
        raise ValueError("quantization must be 'none' or '4bit'")
    model = AutoModelForCausalLM.from_pretrained(checkpoint, **load_kwargs)
    model.config.use_cache = False
    if quantization in {"4bit", "4-bit", "qlora"}:
        model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=bool(config.get("gradient_checkpointing", False)))
    for parameter in model.parameters():
        parameter.requires_grad = False
    targets = _target_modules(model, list(config.get("lora_targets", ["q_proj", "v_proj", "o_proj"])))
    lora_config = LoraConfig(r=int(config.get("lora_r", 16)), lora_alpha=int(config.get("lora_alpha", 32)), lora_dropout=float(config.get("lora_dropout", 0.05)), target_modules=targets, bias="none", task_type=TaskType.CAUSAL_LM)
    resume_adapter = config.get("resume_from_adapter")
    if resume_adapter:
        adapter_path = Path(resume_adapter)
        if not (adapter_path / "adapter_config.json").is_file():
            raise ValueError(f"resume_from_adapter is not a saved adapter directory: {adapter_path}")
        model = PeftModel.from_pretrained(model, adapter_path, is_trainable=True)
        norm_state_path = adapter_path / "normalization_state.pt"
        if norm_state_path.is_file():
            norm_state = torch.load(norm_state_path, map_location="cpu", weights_only=True)
            named = dict(model.named_parameters())
            for name, value in norm_state.items():
                if name in named:
                    named[name].data.copy_(value.to(named[name].device, dtype=named[name].dtype))
    else:
        model = get_peft_model(model, lora_config)
    if config.get("train_normalization_layers", True):
        for name, parameter in model.named_parameters():
            if "norm" in name.lower():
                parameter.requires_grad = True
    if config.get("gradient_checkpointing", False):
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()
    audit = parameter_audit(model)
    audit.update({"model_name": checkpoint, "resolved_lora_targets": targets})
    return model, audit


def forward_bidirectional(model: torch.nn.Module, input_ids: torch.Tensor, padding_mask: torch.Tensor):
    """Run a CausalLM with the project’s explicit bidirectional padding mask."""
    return model(input_ids=input_ids, attention_mask=bidirectional_attention_mask(padding_mask, next(model.parameters()).dtype), use_cache=False).logits
