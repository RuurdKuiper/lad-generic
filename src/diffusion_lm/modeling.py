"""Causal-LM loading adapted for bidirectional denoising."""
from __future__ import annotations
from collections import Counter, OrderedDict
from typing import Any

import torch
import os
from pathlib import Path
from peft import LoraConfig, PeftModel, TaskType, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM


_ATTENTION_MASK_CACHE: OrderedDict[tuple[Any, ...], torch.Tensor] = OrderedDict()
_ATTENTION_MASK_CACHE_SIZE = 4
TRAINABLE_BASE_STATE_FILENAME = "trainable_base_state.pt"


def bidirectional_attention_mask(padding_mask: torch.Tensor, dtype: torch.dtype) -> torch.Tensor:
    """A 4-D additive full-attention mask accepted unchanged by Transformers >=5.

    `padding_mask` is retained for loss/padding bookkeeping, but padding is
    intentionally visible to attention. Repeated EOS padding is part of the
    configured context-width signal: real and padded queries can attend to all
    positions, allowing the model to learn concise answers under wide contexts.
    """
    # Every position is deliberately visible, so the additive mask is exactly
    # zero. Reuse the most recent shapes instead of allocating and clearing the
    # same dense tensor on every forward pass.
    shape = (padding_mask.shape[0], 1, padding_mask.shape[1], padding_mask.shape[1])
    # Inference tensors cannot later be saved by autograd, so training and
    # inference-mode allocations must occupy separate cache entries.
    key = (
        padding_mask.device.type,
        padding_mask.device.index,
        dtype,
        torch.is_inference_mode_enabled(),
        *shape,
    )
    mask = _ATTENTION_MASK_CACHE.get(key)
    if mask is None:
        mask = torch.zeros(shape, device=padding_mask.device, dtype=dtype)
        _ATTENTION_MASK_CACHE[key] = mask
        if len(_ATTENTION_MASK_CACHE) > _ATTENTION_MASK_CACHE_SIZE:
            _ATTENTION_MASK_CACHE.popitem(last=False)
    else:
        _ATTENTION_MASK_CACHE.move_to_end(key)
    return mask


def _target_modules(model: torch.nn.Module, requested: list[str]) -> list[str]:
    """Verify every requested LoRA projection exists in the loaded architecture."""
    available = {name.rsplit(".", 1)[-1] for name, _ in model.named_modules()}
    missing = [name for name in requested if name not in available]
    if missing:
        raise ValueError(f"LoRA target modules missing from {model.config.model_type}: {missing}; available suffixes include {sorted(available)[:40]}")
    return requested


def _transformer_layers(model: torch.nn.Module) -> torch.nn.ModuleList:
    """Return the ordered decoder blocks from a supported CausalLM/PEFT wrapper."""
    base = model.get_base_model() if hasattr(model, "get_base_model") else model
    candidates = (
        ("model", "layers"),
        ("transformer", "h"),
        ("gpt_neox", "layers"),
        ("model", "decoder", "layers"),
    )
    for path in candidates:
        value: Any = base
        for component in path:
            value = getattr(value, component, None)
            if value is None:
                break
        if isinstance(value, torch.nn.ModuleList):
            return value
    raise TypeError(
        f"Could not locate ordered transformer layers in {type(base).__name__}; "
        "train_last_n_layers is unsupported for this architecture"
    )


def _unfreeze_last_transformer_layers(model: torch.nn.Module, count: int) -> list[int]:
    """Unfreeze the final ``count`` complete decoder blocks."""
    if count < 0:
        raise ValueError("train_last_n_layers must be non-negative")
    if count == 0:
        return []
    layers = _transformer_layers(model)
    if count > len(layers):
        raise ValueError(
            f"train_last_n_layers={count} exceeds the model's {len(layers)} transformer layers"
        )
    indices = list(range(len(layers) - count, len(layers)))
    for index in indices:
        for parameter in layers[index].parameters():
            parameter.requires_grad = True
    return indices


def _unfreeze_output_head(model: torch.nn.Module, enabled: bool) -> int:
    """Optionally unfreeze the untied language-model output projection."""
    if not enabled:
        return 0
    base = model.get_base_model() if hasattr(model, "get_base_model") else model
    if not hasattr(base, "get_output_embeddings"):
        raise TypeError(f"{type(base).__name__} does not expose an output head")
    output_head = base.get_output_embeddings()
    input_embeddings = base.get_input_embeddings() if hasattr(base, "get_input_embeddings") else None
    if output_head is None:
        raise TypeError(f"{type(base).__name__} has no output head")
    input_parameter_ids = {id(parameter) for parameter in input_embeddings.parameters()} if input_embeddings else set()
    output_parameters = list(output_head.parameters())
    if any(id(parameter) in input_parameter_ids for parameter in output_parameters):
        raise ValueError("train_lm_head requires untied input and output embeddings")
    for parameter in output_parameters:
        parameter.requires_grad = True
    return sum(parameter.numel() for parameter in output_parameters)


def load_trainable_base_state(model: torch.nn.Module, adapter_path: str | Path) -> int:
    """Restore separately saved, non-LoRA trainable base parameters."""
    state_path = Path(adapter_path) / TRAINABLE_BASE_STATE_FILENAME
    if not state_path.is_file():
        return 0
    state = torch.load(state_path, map_location="cpu", weights_only=True)
    parameters = dict(model.named_parameters())
    missing = sorted(name for name in state if name not in parameters)
    mismatched = sorted(
        name for name, value in state.items()
        if name in parameters and parameters[name].shape != value.shape
    )
    if missing or mismatched:
        raise ValueError(
            "The saved trainable base state does not match the adapter/base model: "
            f"missing={missing[:5]}, shape_mismatch={mismatched[:5]}"
        )
    for name, value in state.items():
        parameter = parameters[name]
        parameter.data.copy_(value.to(parameter.device, dtype=parameter.dtype))
    return len(state)


def parameter_audit(
    model: torch.nn.Module,
    train_last_n_layers: int = 0,
    train_lm_head: bool = False,
    full_finetuning: bool = False,
) -> dict[str, Any]:
    """Assert the intended trainable set and return parameter-count diagnostics."""
    named = list(model.named_parameters())
    trainable = [(name, p) for name, p in named if p.requires_grad]
    total = sum(p.numel() for _, p in named)
    if full_finetuning:
        frozen = [name for name, parameter in named if not parameter.requires_grad]
        if frozen:
            raise AssertionError({"unexpected_frozen_full_model_parameters": frozen[:20]})
        return {
            "full_finetuning": True,
            "full_model_parameters": total,
            "lora_parameters": 0,
            "normalization_parameters": 0,
            "transformer_layer_parameters": 0,
            "lm_head_parameters": 0,
            "other_trainable_parameters": 0,
            "train_last_n_layers": 0,
            "train_lm_head": False,
            "trainable_transformer_layer_indices": [],
            "total_trainable_parameters": total,
            "total_model_parameters": total,
            "trainable_percentage": 100.0,
            "trainable_names": [name for name, _ in trainable],
        }
    selected_layers = list(_transformer_layers(model)[-train_last_n_layers:]) if train_last_n_layers else []
    parameter_names = {id(parameter): name for name, parameter in named}
    selected_parameter_ids = {
        id(parameter)
        for layer in selected_layers
        for parameter in layer.parameters()
        if "lora_" not in parameter_names.get(id(parameter), "")
    }
    base = model.get_base_model() if hasattr(model, "get_base_model") else model
    output_head = base.get_output_embeddings() if hasattr(base, "get_output_embeddings") else None
    output_head_parameter_ids = {id(parameter) for parameter in output_head.parameters()} if output_head else set()
    categories = Counter()
    unexpected = []
    for name, p in trainable:
        if "lora_" in name:
            categories["lora"] += p.numel()
        elif id(p) in output_head_parameter_ids and train_lm_head:
            categories["lm_head"] += p.numel()
        elif id(p) in selected_parameter_ids:
            categories["transformer_layers"] += p.numel()
        elif "norm" in name.lower():
            categories["norm"] += p.numel()
        else:
            categories["other"] += p.numel()
            unexpected.append(name)
    frozen_embedding = all(not p.requires_grad for n, p in named if any(x in n.lower() for x in ("embed_tokens", "embed_tokens", "wte")))
    # An output head targeted by LoRA contains trainable adapter parameters even
    # when its original projection remains frozen. Only enforce the requested
    # state on non-LoRA parameters belonging to the head.
    non_lora_output_parameters = [
        parameter
        for name, parameter in named
        if id(parameter) in output_head_parameter_ids and "lora_" not in name
    ]
    lm_head_trainability_correct = bool(non_lora_output_parameters) and all(
        parameter.requires_grad == train_lm_head
        for parameter in non_lora_output_parameters
    )
    if not frozen_embedding or not lm_head_trainability_correct or unexpected:
        raise AssertionError({"embeddings_frozen": frozen_embedding, "lm_head_trainability_correct": lm_head_trainability_correct, "unexpected_trainable": unexpected})
    frozen_selected = [
        name for name, parameter in named
        if id(parameter) in selected_parameter_ids and not parameter.requires_grad
    ]
    if frozen_selected:
        raise AssertionError({"unexpected_frozen_last_layer_parameters": frozen_selected[:20]})
    trainable_count = sum(p.numel() for _, p in trainable)
    layer_count = len(_transformer_layers(model)) if train_last_n_layers else 0
    return {"lora_parameters": categories["lora"], "normalization_parameters": categories["norm"], "transformer_layer_parameters": categories["transformer_layers"], "lm_head_parameters": categories["lm_head"], "other_trainable_parameters": categories["other"], "train_last_n_layers": train_last_n_layers, "train_lm_head": train_lm_head, "trainable_transformer_layer_indices": list(range(layer_count - train_last_n_layers, layer_count)) if train_last_n_layers else [], "total_trainable_parameters": trainable_count, "total_model_parameters": total, "trainable_percentage": 100 * trainable_count / total, "trainable_names": [n for n, _ in trainable]}


def load_denoising_model(config: dict[str, Any]) -> tuple[torch.nn.Module, dict[str, Any]]:
    """Load either a full model or a LoRA-adapted CausalLM and audit it."""
    checkpoint = config["model_name_or_path"]
    precision = config.get("precision", "bf16")
    dtype = {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}.get(precision)
    if dtype is None:
        raise ValueError(f"Unknown precision {precision}")
    # No device_map: accelerate owns device placement in distributed runs.
    model_cache = Path(config.get("base_model_cache_dir", "base_models")); model_cache.mkdir(parents=True, exist_ok=True)
    quantization = str(config.get("quantization", "none")).lower()
    full_finetuning = bool(config.get("full_finetuning", False))
    train_last_n_layers = int(config.get("train_last_n_layers", 0) or 0)
    train_lm_head = bool(config.get("train_lm_head", False))
    if train_last_n_layers < 0:
        raise ValueError("train_last_n_layers must be non-negative")
    if (full_finetuning or train_last_n_layers or train_lm_head) and quantization not in {"none", "off", "false"}:
        raise ValueError("training full base-model layers or the LM head requires an unquantized base model")
    if full_finetuning and config.get("resume_from_adapter"):
        raise ValueError("full_finetuning starts from model_name_or_path and cannot use resume_from_adapter")
    if full_finetuning and (train_last_n_layers or train_lm_head):
        raise ValueError("train_last_n_layers/train_lm_head are redundant with full_finetuning")
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
    # PEFT's CAUSAL_LM task type only describes adapter integration; it does
    # not control attention direction. Make the base-model intent explicit as
    # well as supplying the prepared 4-D mask in forward_bidirectional().
    model.config.is_causal = False
    if hasattr(model.config, "use_bidirectional_attention"):
        model.config.use_bidirectional_attention = True
    if full_finetuning:
        for parameter in model.parameters():
            parameter.requires_grad = True
        if config.get("gradient_checkpointing", False):
            model.gradient_checkpointing_enable()
            model.enable_input_require_grads()
        audit = parameter_audit(model, full_finetuning=True)
        audit.update({"model_name": checkpoint, "resolved_lora_targets": []})
        return model, audit
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
        load_trainable_base_state(model, adapter_path)
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
                # Accelerate's FP16 GradScaler cannot unscale FP16 gradients.
                # Keep trainable normalization parameters in FP32 so their
                # gradients are scaler-compatible; frozen base weights remain
                # in the configured compute dtype.
                if precision == "fp16" and parameter.dtype == torch.float16:
                    parameter.data = parameter.data.float()
    trained_layer_indices = _unfreeze_last_transformer_layers(model, train_last_n_layers)
    _unfreeze_output_head(model, train_lm_head)
    if config.get("gradient_checkpointing", False):
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()
    audit = parameter_audit(model, train_last_n_layers=train_last_n_layers, train_lm_head=train_lm_head)
    audit.update({"model_name": checkpoint, "resolved_lora_targets": targets, "trainable_transformer_layer_indices": trained_layer_indices})
    return model, audit


def forward_bidirectional(model: torch.nn.Module, input_ids: torch.Tensor, padding_mask: torch.Tensor):
    """Run a CausalLM with the project’s explicit bidirectional padding mask."""
    # 4-bit bitsandbytes weights are stored as uint8, which cannot represent
    # the floating additive attention mask.  Use the first floating parameter
    # (normally a LoRA or normalization parameter) as the compute dtype.
    dtype = getattr(model, "_lad_attention_mask_dtype", None)
    if dtype is None:
        dtype = next((parameter.dtype for parameter in model.parameters() if parameter.is_floating_point()), torch.float32)
        model._lad_attention_mask_dtype = dtype
    return model(input_ids=input_ids, attention_mask=bidirectional_attention_mask(padding_mask, dtype), use_cache=False).logits


def forward_bidirectional_selected(
    model: torch.nn.Module,
    input_ids: torch.Tensor,
    padding_mask: torch.Tensor,
    selection_mask: torch.Tensor,
):
    """Run the frozen LM head only at positions participating in the objective."""
    dtype = getattr(model, "_lad_attention_mask_dtype", None)
    if dtype is None:
        dtype = next((parameter.dtype for parameter in model.parameters() if parameter.is_floating_point()), torch.float32)
        model._lad_attention_mask_dtype = dtype

    unwrapped = model.module if hasattr(model, "module") else model
    causal_lm = unwrapped.get_base_model() if hasattr(unwrapped, "get_base_model") else unwrapped
    backbone = getattr(causal_lm, "model", None)
    output_head = causal_lm.get_output_embeddings() if hasattr(causal_lm, "get_output_embeddings") else None
    if backbone is None or output_head is None:
        raise TypeError(f"Selected-logit optimization is unsupported for {type(causal_lm).__name__}")

    outputs = backbone(
        input_ids=input_ids,
        attention_mask=bidirectional_attention_mask(padding_mask, dtype),
        use_cache=False,
    )
    example_ids, token_ids = selection_mask.nonzero(as_tuple=True)
    selected_logits = output_head(outputs.last_hidden_state[example_ids, token_ids])
    return selected_logits, example_ids, token_ids
