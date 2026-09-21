"""Deterministic in-place infilling diagnostics for bidirectional denoisers."""
from __future__ import annotations

from contextlib import contextmanager
import math
from pathlib import Path
from typing import Any, Iterator

import torch
import torch.nn.functional as F

from .inference import _prompt_ids, forward_denoising


def _encode(tokenizer: Any, text: str) -> list[int]:
    """Encode one deliberately boundary-aware benchmark segment."""
    return list(tokenizer.encode(text, add_special_tokens=False))


def _encoded_example(session: Any, example: Any) -> tuple[list[int], list[int], list[int]]:
    """Return chat/prefix IDs, clean target IDs, and visible suffix IDs."""
    chat = _prompt_ids(session.tokenizer, example.prompt, "", session.prompt_format)
    answer_prefix = _encode(session.tokenizer, str(example.metadata["answer_prefix"]))
    target = _encode(session.tokenizer, str(example.metadata["target_text"]))
    suffix = _encode(session.tokenizer, str(example.metadata["answer_suffix"]))
    if not target:
        raise ValueError(f"Infilling example {example.example_id} has an empty tokenized target")
    return chat + answer_prefix, target, suffix


@torch.inference_mode()
def score_bidirectional_example(session: Any, example: Any) -> dict[str, Any]:
    """Score one masked span with and without its visible right context."""
    left, target, suffix = _encoded_example(session, example)
    target_start = len(left)
    masked_target = [int(session.mask_token_id)] * len(target)

    def score(input_ids: list[int]) -> tuple[list[int], float, int]:
        tokens = torch.tensor([input_ids], dtype=torch.long, device=session.device)
        padding = torch.zeros_like(tokens, dtype=torch.bool)
        logits = forward_denoising(session, tokens, padding)[0, target_start:target_start + len(target)].float()
        labels = torch.tensor(target, dtype=torch.long, device=logits.device)
        nll = float(F.cross_entropy(logits, labels, reduction="sum").cpu())
        predicted = logits.argmax(dim=-1).tolist()
        correct = sum(int(actual == expected) for actual, expected in zip(predicted, target))
        return predicted, nll, correct

    predicted, nll, correct = score(left + masked_target + suffix)
    prefix_predicted, prefix_nll, prefix_correct = score(left + masked_target)
    return {
        "target_ids": target,
        "prediction_ids": predicted,
        "prediction": session.tokenizer.decode(predicted, skip_special_tokens=True).strip(),
        "target": str(example.metadata["target_text"]).strip(),
        "target_tokens": len(target),
        "correct_tokens": correct,
        "exact_match": predicted == target,
        "nll": nll,
        "prefix_only_prediction_ids": prefix_predicted,
        "prefix_only_prediction": session.tokenizer.decode(prefix_predicted, skip_special_tokens=True).strip(),
        "prefix_only_correct_tokens": prefix_correct,
        "prefix_only_exact_match": prefix_predicted == target,
        "prefix_only_nll": prefix_nll,
    }


@contextmanager
def original_base_causal(session: Any) -> Iterator[None]:
    """Temporarily restore the untouched causal parent of a PEFT session."""
    model = session.model
    if not hasattr(model, "disable_adapter"):
        raise TypeError("An autoregressive infilling baseline requires an unmerged PEFT adapter")
    trained_norms = {
        name: parameter.detach().cpu().clone()
        for name, parameter in model.named_parameters()
        if "norm" in name.lower()
    }
    initial_path = Path(session.adapter_path) / "normalization_initial_state.pt"
    initial_norms = (
        torch.load(initial_path, map_location="cpu", weights_only=True)
        if initial_path.is_file() else trained_norms
    )
    config = model.config
    original_config = {
        name: getattr(config, name)
        for name in ("use_cache", "is_causal", "use_bidirectional_attention")
        if hasattr(config, name)
    }
    named = dict(model.named_parameters())
    try:
        config.use_cache = False
        if hasattr(config, "is_causal"):
            config.is_causal = True
        if hasattr(config, "use_bidirectional_attention"):
            config.use_bidirectional_attention = False
        for name, value in initial_norms.items():
            if name in named:
                named[name].data.copy_(value.to(named[name].device, dtype=named[name].dtype))
        with model.disable_adapter():
            yield
    finally:
        for name, value in original_config.items():
            setattr(config, name, value)
        for name, value in trained_norms.items():
            if name in named:
                named[name].data.copy_(value.to(named[name].device, dtype=named[name].dtype))


@torch.inference_mode()
def score_causal_example(session: Any, example: Any) -> dict[str, Any]:
    """Teacher-force the target under the causal parent without its suffix.

    Teacher forcing is intentionally favorable to the AR baseline: later target
    tokens receive earlier gold target tokens.  The decisive suffix remains to
    the right of every target position and is therefore unavailable.
    """
    left, target, _suffix = _encoded_example(session, example)
    clean = left + target
    tokens = torch.tensor([clean], dtype=torch.long, device=session.device)
    outputs = session.model(input_ids=tokens, use_cache=False)
    logits = outputs.logits if hasattr(outputs, "logits") else outputs["logits"]
    start = len(left) - 1
    selected = logits[0, start:start + len(target)].float()
    labels = torch.tensor(target, dtype=torch.long, device=selected.device)
    nll = float(F.cross_entropy(selected, labels, reduction="sum").cpu())
    predicted = selected.argmax(dim=-1).tolist()
    correct = sum(int(actual == expected) for actual, expected in zip(predicted, target))
    return {
        "target_ids": target,
        "prediction_ids": predicted,
        "prediction": session.tokenizer.decode(predicted, skip_special_tokens=True).strip(),
        "target": str(example.metadata["target_text"]).strip(),
        "target_tokens": len(target),
        "correct_tokens": correct,
        "exact_match": predicted == target,
        "nll": nll,
    }


def summarize_infilling(results: list[dict[str, Any]], *, include_prefix_control: bool) -> dict[str, Any]:
    """Aggregate exact-match, token accuracy, and token-weighted likelihood."""
    examples = len(results)
    tokens = sum(int(result["target_tokens"]) for result in results)
    nll = sum(float(result["nll"]) for result in results)
    summary = {
        "accuracy": sum(int(result["exact_match"]) for result in results) / max(examples, 1),
        "exact_match": sum(int(result["exact_match"]) for result in results) / max(examples, 1),
        "token_accuracy": sum(int(result["correct_tokens"]) for result in results) / max(tokens, 1),
        "mean_nll": nll / max(tokens, 1),
        "perplexity": math.exp(min(nll / max(tokens, 1), 80.0)),
        "correct": sum(int(result["exact_match"]) for result in results),
        "total": examples,
        "tokens": tokens,
    }
    if include_prefix_control:
        prefix_nll = sum(float(result["prefix_only_nll"]) for result in results)
        prefix_accuracy = sum(int(result["prefix_only_exact_match"]) for result in results) / max(examples, 1)
        prefix_token_accuracy = sum(int(result["prefix_only_correct_tokens"]) for result in results) / max(tokens, 1)
        summary.update({
            "prefix_only_exact_match": prefix_accuracy,
            "prefix_only_token_accuracy": prefix_token_accuracy,
            "prefix_only_mean_nll": prefix_nll / max(tokens, 1),
            "prefix_only_perplexity": math.exp(min(prefix_nll / max(tokens, 1), 80.0)),
            "suffix_gain_exact_match": summary["exact_match"] - prefix_accuracy,
            "suffix_gain_token_accuracy": summary["token_accuracy"] - prefix_token_accuracy,
            "suffix_nll_reduction": (prefix_nll - nll) / max(tokens, 1),
        })
    return summary
