"""Interactive iterative denoising inference for saved LoRA adapters."""
from __future__ import annotations

import gc
from html import escape
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import torch
import torch.nn.functional as F
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from .data import validate_mask_token
from .legacy_compat import install_legacy_pickle_modules, patch_legacy_lora_modules, restore_legacy_pickle_modules
from .modeling import forward_bidirectional


def find_adapters(outputs_dir: str | Path = "outputs") -> list[str]:
    """Return adapter directories relative to outputs_dir, newest first."""
    root = Path(outputs_dir).resolve()
    if not root.exists():
        return []
    paths = [path for path in root.rglob("adapter_config.json") if path.parent.is_dir()]
    return [str(path.parent.relative_to(root)) for path in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)]


def _safe_adapter_path(outputs_dir: str | Path, selection: str) -> Path:
    """Resolve a selected adapter while preventing paths outside outputs_dir."""
    root = Path(outputs_dir).resolve()
    path = (root / selection).resolve()
    if root not in path.parents or not (path / "adapter_config.json").is_file():
        raise ValueError("Select a valid adapter directory below outputs/.")
    return path


def _precision_dtype(precision: str, device: torch.device) -> torch.dtype:
    """Map configured precision to a safe dtype for the selected device."""
    requested = {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}.get(precision, torch.float32)
    # CPU inference with low-precision weights is not generally supported; MPS
    # has better float32 compatibility for interactive single-request inference.
    if device.type == "cpu":
        return torch.float32
    # T4-class CUDA GPUs have no native BF16 Tensor Core support.  BF16
    # quantized compute there is substantially slower than FP16, so retain the
    # saved run's preference only where the hardware can execute it natively.
    if device.type == "cuda" and requested == torch.bfloat16 and not torch.cuda.is_bf16_supported():
        return torch.float16
    return requested


def select_device(requested: str = "auto") -> torch.device:
    """Choose an available CUDA, MPS, or CPU device from a UI selection."""
    if requested == "auto":
        requested = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    if requested == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but is unavailable.")
    if requested == "mps" and not torch.backends.mps.is_available():
        raise ValueError("MPS was requested but is unavailable.")
    return torch.device(requested)


@dataclass
class InferenceSession:
    model: torch.nn.Module
    tokenizer: Any
    device: torch.device
    adapter_path: Path
    config: dict[str, Any]
    mask_token_id: int
    quantization: str = "none"
    compute_dtype: str = "unknown"
    legacy_wrapper: bool = False
    prompt_format: str = "chat_template"


def load_session(adapter_selection: str, outputs_dir: str | Path = "outputs", device_name: str = "auto", quantization: str | None = None) -> InferenceSession:
    """Load a base model, saved LoRA adapter, tokenizer, and norm state."""
    adapter_path = _safe_adapter_path(outputs_dir, adapter_selection)
    run_config_path = adapter_path.parent / "resolved_config.json"
    run_config = json.loads(run_config_path.read_text()) if run_config_path.is_file() else {}
    adapter_config = json.loads((adapter_path / "adapter_config.json").read_text())
    base_model = adapter_config["base_model_name_or_path"]
    device = select_device(device_name)
    dtype = _precision_dtype(run_config.get("precision", "fp32"), device)
    requested_quantization = str(quantization or "auto").lower()
    resolved_quantization = str(run_config.get("quantization", "none") if requested_quantization == "auto" else requested_quantization).lower()
    if resolved_quantization in {"4-bit", "qlora"}:
        resolved_quantization = "4bit"
    if resolved_quantization not in {"none", "off", "false", "4bit"}:
        raise ValueError("Inference quantization must be 'auto', 'none', or '4bit'.")
    use_4bit = resolved_quantization == "4bit"
    compute_dtype = dtype
    cache_dir = run_config.get("base_model_cache_dir", "base_models")
    token = os.getenv("HF_TOKEN")
    tokenizer_name = run_config.get("tokenizer_name_or_path", base_model)
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name, use_fast=True, token=token, cache_dir=cache_dir, clean_up_tokenization_spaces=False)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    load_kwargs: dict[str, Any] = dict(dtype=dtype, token=token, cache_dir=cache_dir, trust_remote_code=False)
    if use_4bit:
        if device.type != "cuda":
            raise RuntimeError("4-bit inference requires an NVIDIA CUDA device.")
        try:
            from transformers import BitsAndBytesConfig
            import bitsandbytes  # noqa: F401
        except ImportError as exc:
            raise ImportError("4-bit inference requires bitsandbytes; install with `pip install -e '.[cuda]'`.") from exc
        compute_dtype = _precision_dtype(run_config.get("compute_dtype", run_config.get("precision", "bf16")), device)
        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=str(run_config.get("quantization_type", "nf4")),
            bnb_4bit_compute_dtype=compute_dtype,
            bnb_4bit_use_double_quant=bool(run_config.get("double_quant", True)),
        )
        # Quantized modules cannot subsequently be moved with model.to().
        load_kwargs["device_map"] = {"": device.index if device.index is not None else 0}
    base = AutoModelForCausalLM.from_pretrained(base_model, **load_kwargs)
    base.config.use_cache = False
    base.config.is_causal = False
    if hasattr(base.config, "use_bidirectional_attention"):
        base.config.use_bidirectional_attention = True
    model = PeftModel.from_pretrained(base, adapter_path, is_trainable=False)
    norm_path = adapter_path / "normalization_state.pt"
    if norm_path.is_file():
        model.load_state_dict(torch.load(norm_path, map_location="cpu", weights_only=True), strict=False)
    if not use_4bit:
        model.to(device)
    model.eval()
    mask_info = validate_mask_token(tokenizer)
    session = InferenceSession(model, tokenizer, device, adapter_path, run_config, mask_info["mask_token_id"], "4bit" if use_4bit else "none", str(compute_dtype).removeprefix("torch."))
    preflight_session(session)
    return session


def _load_legacy_checkpoint_session(checkpoint: str | Path, tokenizer_name_or_path: str, device_name: str = "auto", source_config: dict[str, Any] | None = None) -> InferenceSession:
    """Load one trusted legacy full-object checkpoint from a local path."""
    checkpoint = Path(checkpoint).expanduser().resolve()
    if not checkpoint.is_file():
        raise ValueError(f"Legacy checkpoint does not exist: {checkpoint}")
    if not tokenizer_name_or_path.strip():
        raise ValueError("Legacy loading requires a tokenizer name or local tokenizer path.")
    # A full-object checkpoint can execute pickle code.  This loader is for
    # checkpoints the user trusts, including their locally archived model.
    previous_modules = install_legacy_pickle_modules()
    try:
        model = torch.load(checkpoint, map_location="cpu", weights_only=False)
    finally:
        restore_legacy_pickle_modules(previous_modules)
    if not isinstance(model, torch.nn.Module):
        raise ValueError(f"{checkpoint} is not a full torch.nn.Module checkpoint.")
    patch_legacy_lora_modules(model)

    token = os.getenv("HF_TOKEN")
    device = select_device(device_name)
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name_or_path.strip(), use_fast=True, token=token, clean_up_tokenization_spaces=False)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model.to(device).eval()
    mask_info = validate_mask_token(tokenizer)
    session = InferenceSession(
        model=model,
        tokenizer=tokenizer,
        device=device,
        adapter_path=checkpoint,
        config=source_config or {"model_source": "local_legacy", "checkpoint": str(checkpoint), "tokenizer_name_or_path": tokenizer_name_or_path.strip()},
        mask_token_id=mask_info["mask_token_id"],
        quantization="none",
        compute_dtype=str(next((parameter.dtype for parameter in model.parameters() if parameter.is_floating_point()), torch.float32)).removeprefix("torch."),
        legacy_wrapper=True,
        prompt_format="legacy_llama",
    )
    preflight_session(session)
    return session


def load_local_legacy_session(checkpoint_path: str | Path, tokenizer_name_or_path: str, device_name: str = "auto") -> InferenceSession:
    """Load and preflight a trusted local legacy full-model checkpoint."""
    return _load_legacy_checkpoint_session(checkpoint_path, tokenizer_name_or_path, device_name)


def load_hosted_legacy_session(repo_id: str, filename: str, tokenizer_name_or_path: str, device_name: str = "auto") -> InferenceSession:
    """Load the trusted legacy full-model checkpoint hosted on Hugging Face.

    This exists for controlled comparisons: the checkpoint uses its original
    wrapper to construct full bidirectional attention, while decoding uses the
    current project's prompt and denoising loop.  Pickled checkpoints are only
    safe to load from a repository you trust.
    """
    if not repo_id.strip() or not filename.strip() or not tokenizer_name_or_path.strip():
        raise ValueError("Hosted legacy loading requires a repository ID, checkpoint filename, and tokenizer name.")
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise ImportError("Hosted model loading requires huggingface_hub, installed with transformers.") from exc

    token = os.getenv("HF_TOKEN")
    checkpoint = hf_hub_download(repo_id=repo_id.strip(), filename=filename.strip(), token=token)
    return _load_legacy_checkpoint_session(
        checkpoint,
        tokenizer_name_or_path,
        device_name,
        {"model_source": "huggingface_legacy", "repo_id": repo_id.strip(), "filename": filename.strip(), "tokenizer_name_or_path": tokenizer_name_or_path.strip()},
    )


def _sample(logits: torch.Tensor, temperature: float, top_k: int, generator: torch.Generator | None) -> tuple[torch.Tensor, torch.Tensor]:
    """Top-k sample token IDs and return their normalized sampling confidence."""
    logits = logits / max(temperature, 1e-5)
    vocab_size = logits.shape[-1]
    k = min(max(int(top_k), 1), vocab_size)
    values, indices = torch.topk(logits, k, dim=-1)
    probabilities = F.softmax(values, dim=-1)
    picked_local = torch.multinomial(probabilities, 1, generator=generator)
    picked = indices.gather(-1, picked_local).squeeze(-1)
    confidence = probabilities.gather(-1, picked_local).squeeze(-1)
    return picked, confidence


def forward_denoising(session: InferenceSession, input_ids: torch.Tensor, padding_mask: torch.Tensor) -> torch.Tensor:
    """Return denoising logits for either the current or legacy model wrapper."""
    if session.legacy_wrapper:
        # The archived CustomTransformerModel builds its own full-attention
        # 4-D mask and passes use_cache=False to its inner Peft model. Passing
        # either argument here would duplicate the wrapper's keyword.
        outputs = session.model(input_ids=input_ids)
        return outputs["logits"] if isinstance(outputs, dict) else outputs.logits
    return forward_bidirectional(session.model, input_ids, padding_mask)


@torch.inference_mode()
def preflight_session(session: InferenceSession) -> tuple[int, int]:
    """Run one real forward pass and fail early if a loaded model is unusable."""
    prefix = _prompt_ids(session.tokenizer, "Reply with OK.", "You are a helpful assistant.", session.prompt_format)
    input_ids = torch.tensor([prefix + [session.mask_token_id]], device=session.device, dtype=torch.long)
    padding = torch.zeros_like(input_ids, dtype=torch.bool)
    try:
        logits = forward_denoising(session, input_ids, padding)
    except Exception as exc:
        source = "legacy hosted checkpoint" if session.legacy_wrapper else "saved adapter"
        raise RuntimeError(f"Inference preflight failed for {source}; the model was not loaded for generation: {exc}") from exc
    if logits.ndim != 3 or logits.shape[:2] != input_ids.shape:
        raise RuntimeError(f"Inference preflight returned invalid logits shape {tuple(logits.shape)} for input shape {tuple(input_ids.shape)}")
    if not torch.isfinite(logits[:, -1]).all():
        raise RuntimeError("Inference preflight produced non-finite final-token logits.")
    return int(input_ids.shape[1]), int(logits.shape[-1])


def _prompt_ids(tokenizer: Any, question: str, system_prompt: str, prompt_format: str = "chat_template") -> list[int]:
    """Render system/user messages through a tokenizer’s native chat template."""
    if not question.strip():
        raise ValueError("Enter a question or prompt.")
    if prompt_format == "legacy_llama":
        # The hosted historical checkpoint used a base Llama tokenizer with no
        # chat_template. Match the prompt layout from its original app while
        # still running the current project's denoising/sampling loop.
        prompt = (
            "<|begin_of_text|>\n"
            "<|start_header_id|>system<|end_header_id|>\n"
            f"{system_prompt}\n"
            "<|start_header_id|>user<|end_header_id|>\n"
            f"{question.strip()}\n"
            "<|start_header_id|>assistant<|end_header_id|>\n"
        )
        return list(tokenizer.encode(prompt, add_special_tokens=False))
    if prompt_format != "chat_template":
        raise ValueError(f"Unknown prompt format: {prompt_format}")
    if not getattr(tokenizer, "chat_template", None):
        raise ValueError(f"{tokenizer.name_or_path} has no chat template; inference needs one to identify the answer boundary.")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]
    try:
        rendered = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    except Exception as exc:
        # Gemma's official template rejects a separate system role; preserve
        # the prompt by folding it into the user message, as training does.
        if exc.__class__.__name__ != "TemplateError" or "System role not supported" not in str(exc):
            raise
        rendered = tokenizer.apply_chat_template([
            {"role": "user", "content": f"{system_prompt}\n\n{question}"},
        ], tokenize=True, add_generation_prompt=True)
    if isinstance(rendered, str):
        rendered = tokenizer.encode(rendered, add_special_tokens=False)
    elif hasattr(rendered, "input_ids"):
        rendered = rendered.input_ids
    if rendered and isinstance(rendered[0], list):
        rendered = rendered[0]
    if not all(isinstance(token, int) for token in rendered):
        raise ValueError(f"Tokenizer returned a non-integer chat-template encoding: {type(rendered).__name__}")
    return list(rendered)


def render_denoising_step(tokens: list[int], confidences: list[float], answer_start: int, tokenizer: Any, mask_token_id: int, step: int, total_steps: int, frozen: dict[int, int] | None = None) -> str:
    """Render a confidence-colored HTML view of one denoising state."""
    eos_id = tokenizer.eos_token_id
    pieces = []
    answer = tokens[answer_start:]
    output_token_count = 0
    for offset, token in enumerate(answer):
        if token == eos_id:
            break
        output_token_count += 1
        token_text = escape(tokenizer.decode([token], skip_special_tokens=False)).replace("\n", "↵ ")
        if token == mask_token_id:
            style, token_text = "background:#d1d5db;color:#111827;border-radius:3px;padding:1px 4px", "MASK"
        elif frozen and offset in frozen:
            style = "color:#1d4ed8;font-weight:700"
        else:
            confidence = max(0.0, min(1.0, float(confidences[offset]))) if offset < len(confidences) else 0.0
            hue = int(confidence * 120)
            style = f"color:hsl({hue},90%,30%);font-weight:{'600' if confidence > .8 else '400'}"
        pieces.append(f"<span style='{style}' title='position {offset}'>{token_text}</span>")
    pct = int(100 * step / max(total_steps, 1))
    return (f"<div style='font-family:system-ui;padding:14px;border:1px solid #d1d5db;border-radius:9px;background:#fafafa'>"
            f"<div style='font-weight:700;color:#2563eb;margin-bottom:7px'>Denoising step {step}/{total_steps} · {output_token_count} output tokens</div>"
            f"<div style='background:#e5e7eb;border-radius:4px;height:7px;margin-bottom:10px'><div style='background:#2563eb;width:{pct}%;height:7px;border-radius:4px'></div></div>"
            f"<div style='line-height:2;font-size:15px;white-space:pre-wrap'>{''.join(pieces)}</div>"
            f"<div style='font-size:11px;color:#6b7280;margin-top:8px'>Green/blue hues indicate confidence; gray tokens are MASK; blue tokens are permanently retained.</div></div>")


def denoise_stream(session: InferenceSession, question: str, system_prompt: str, max_new_tokens: int, num_steps: int, noise_level: float, temperature: float, top_k: int, seed: int, permanent_unmask: bool = False, confidence_guided: bool = False, proportional_unmask: bool = True, early_stopping: bool = False):
    """Yield intermediate denoising states, optionally stopping after three identical predictions."""
    prefix = _prompt_ids(session.tokenizer, question, system_prompt, session.prompt_format)
    max_new_tokens, num_steps = int(max_new_tokens), int(num_steps)
    if max_new_tokens < 1 or num_steps < 1:
        raise ValueError("max_new_tokens and num_steps must both be at least 1.")
    ids = prefix + [session.mask_token_id] * max_new_tokens
    answer_start = len(prefix)
    # Use the device's default RNG so this works consistently on CUDA, MPS, and
    # CPU; seed it once per request for reproducible interactive runs.
    torch.manual_seed(int(seed))
    if session.device.type == "cuda":
        torch.cuda.manual_seed_all(int(seed))
    padding = torch.zeros((1, len(ids)), device=session.device, dtype=torch.bool)
    last_confidence = 0.0
    frozen: dict[int, int] = {}
    last_predictions: list[tuple[int, ...]] = []
    for step in range(num_steps):
        tokens = torch.tensor([ids], device=session.device, dtype=torch.long)
        with torch.inference_mode():
            logits = forward_denoising(session, tokens, padding)[0, answer_start:]
            sampled, confidence = _sample(logits, float(temperature), int(top_k), None)
        ids[answer_start:] = sampled.tolist()
        for offset, token in frozen.items():
            ids[answer_start + offset] = token
        last_confidence = float(confidence.mean().cpu())
        # Match the legacy application's criterion: compare complete sampled
        # answer token sequences before the next iteration's re-masking.  This
        # includes EOS/padding tokens, so a changing invisible tail does not
        # count as convergence.
        last_predictions.append(tuple(ids[answer_start:]))
        if len(last_predictions) > 3:
            last_predictions.pop(0)
        stopped_early = early_stopping and len(last_predictions) == 3 and len(set(last_predictions)) == 1
        # Progressively reduce corruption. Re-mask independently, retaining the
        # legacy schedule's initial noise_level and ending with a clean sample.
        if step + 1 < num_steps and not stopped_early:
            mask_probability = max(0.0, min(1.0, float(noise_level) * (1.0 - (step + 1) / num_steps)))
            if permanent_unmask:
                keep_count = min(max_new_tokens, max(0, round((1.0 - mask_probability) * max_new_tokens)))
                needed = keep_count - len(frozen)
                candidates = [i for i in range(max_new_tokens) if i not in frozen]
                if needed > 0 and candidates:
                    if proportional_unmask:
                        eos_positions = [i for i in range(max_new_tokens) if ids[answer_start + i] == session.tokenizer.eos_token_id]
                        boundary = min(eos_positions) if eos_positions else max_new_tokens
                        pools = [[i for i in candidates if i < boundary], [i for i in candidates if i >= boundary]]
                        target_normal = round(keep_count * boundary / max_new_tokens)
                        target_counts = [max(0, target_normal - sum(i < boundary for i in frozen)), max(0, keep_count - target_normal - sum(i >= boundary for i in frozen))]
                        chosen = []
                        for pool, target in zip(pools, target_counts):
                            if not pool or target <= 0:
                                continue
                            if confidence_guided:
                                order = torch.argsort(confidence, descending=True).tolist()
                                chosen.extend([i for i in order if i in pool][:target])
                            else:
                                order = torch.randperm(len(pool), device=session.device)[:target].tolist()
                                chosen.extend(pool[i] for i in order)
                        if len(chosen) < needed:
                            remainder = [i for i in candidates if i not in chosen]
                            chosen.extend(remainder[: needed - len(chosen)])
                    elif confidence_guided:
                        confidence_order = torch.argsort(confidence, descending=True).tolist()
                        chosen = [i for i in confidence_order if i in candidates][:needed]
                    else:
                        chosen = torch.randperm(len(candidates), device=session.device)[:needed].tolist()
                        chosen = [candidates[i] for i in chosen]
                    for offset in chosen:
                        frozen[offset] = ids[answer_start + offset]
                for offset in range(max_new_tokens):
                    if offset not in frozen:
                        ids[answer_start + offset] = session.mask_token_id
            else:
                remask = torch.rand(max_new_tokens, device=session.device) < mask_probability
                for offset in torch.where(remask)[0].tolist():
                    ids[answer_start + offset] = session.mask_token_id
        current_answer = ids[answer_start:]
        if session.tokenizer.eos_token_id in current_answer:
            current_answer = current_answer[:current_answer.index(session.tokenizer.eos_token_id)]
        current_text = session.tokenizer.decode(current_answer, skip_special_tokens=True).strip()
        status = f"Denoising step {step + 1}/{num_steps} · {len(current_answer)} output tokens · mean confidence {last_confidence:.3f}"
        if stopped_early:
            status += " · stopped early (same prediction for 3 iterations)"
        html = render_denoising_step(ids, confidence.tolist(), answer_start, session.tokenizer, session.mask_token_id, step + 1, num_steps, frozen if permanent_unmask else None)
        yield current_text, status, html
        if stopped_early:
            break
    answer = ids[answer_start:]
    if session.tokenizer.eos_token_id in answer:
        answer = answer[:answer.index(session.tokenizer.eos_token_id)]
    text = session.tokenizer.decode(answer, skip_special_tokens=True).strip()
    suffix = f" · permanently retained {len(frozen)} tokens" if permanent_unmask else ""
    return


def denoise(session: InferenceSession, question: str, system_prompt: str, max_new_tokens: int, num_steps: int, noise_level: float, temperature: float, top_k: int, seed: int, permanent_unmask: bool = False, confidence_guided: bool = False, proportional_unmask: bool = True, early_stopping: bool = False, progress: Callable[[float, str], None] | None = None) -> tuple[str, str]:
    """Run denoising to completion and return only the final text and status."""
    result = ("", "")
    for step, (text, status, _html) in enumerate(denoise_stream(session, question, system_prompt, max_new_tokens, num_steps, noise_level, temperature, top_k, seed, permanent_unmask, confidence_guided, proportional_unmask, early_stopping), start=1):
        result = (text, status)
        if progress:
            progress(step / int(num_steps), status)
    return result


def release_session(session: InferenceSession | None) -> None:
    """Free a loaded inference model and release backend allocator caches."""
    if session is None:
        return
    del session.model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
