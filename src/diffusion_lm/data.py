"""Dataset compatibility checks, answer-span recovery, and dynamic batching."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import torch


LLAMA_ASSISTANT_HEADER = "<|start_header_id|>assistant<|end_header_id|>"


@dataclass
class DataStats:
    malformed: int = 0
    dropped: int = 0
    empty_answer: int = 0
    truncated: int = 0


def find_subsequence(sequence: list[int], needle: list[int]) -> int | None:
    """Return the first position of needle in sequence, or None when absent."""
    if not needle:
        return None
    for i in range(len(sequence) - len(needle) + 1):
        if sequence[i : i + len(needle)] == needle:
            return i
    return None


def validate_mask_token(tokenizer: Any) -> dict[str, Any]:
    """Validate and describe the tokenizer-specific one-token literal MASK."""
    ids = tokenizer.encode("MASK", add_special_tokens=False)
    if len(ids) != 1:
        raise ValueError(
            f"'MASK' must encode to exactly one token for {tokenizer.name_or_path}; received {ids}. "
            "Choose an existing single-token ordinary-vocabulary alternative; do not resize the vocabulary."
        )
    return {"tokenizer": tokenizer.name_or_path, "mask_token_id": ids[0], "mask_ids": ids, "decoded": tokenizer.decode(ids)}


def llama_stored_ids_compatible(example: dict[str, Any], tokenizer: Any) -> bool:
    """Check the stored clean IDs contain this tokenizer's Llama assistant header."""
    marker = tokenizer.encode(LLAMA_ASSISTANT_HEADER, add_special_tokens=False)
    return bool(marker) and find_subsequence(list(example["labels"]), marker) is not None


def source_to_tokens(example: dict[str, Any], tokenizer: Any) -> tuple[list[int], int]:
    """Retokenize source fields and return clean IDs plus the first answer-content index.

    The dataset supplies instruction/input/output, so non-Llama models never consume Llama IDs.
    """
    instruction, user_input, output = (example.get(k) or "" for k in ("instruction", "input", "output"))
    if not output:
        raise ValueError("empty output")
    user = instruction if not user_input else f"{instruction}\n\n{user_input}"
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": user},
    ]
    if not getattr(tokenizer, "chat_template", None):
        raise ValueError(f"Tokenizer {tokenizer.name_or_path} has no chat_template for source retokenization")
    prefix = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
    if isinstance(prefix, str):
        prefix = tokenizer.encode(prefix, add_special_tokens=False)
    elif hasattr(prefix, "input_ids"):
        prefix = prefix.input_ids
    if prefix and isinstance(prefix[0], list):
        prefix = prefix[0]
    answer = tokenizer.encode(output, add_special_tokens=False)
    eos = tokenizer.eos_token_id
    if eos is None:
        raise ValueError(f"Tokenizer {tokenizer.name_or_path} has no eos_token_id")
    return list(prefix) + list(answer) + [eos], len(prefix)


def stored_to_tokens(example: dict[str, Any], tokenizer: Any) -> tuple[list[int], list[int], int]:
    """Recover Llama stored clean/noised IDs and answer-content start without hard-coded IDs."""
    labels, inputs = list(example["labels"]), list(example["input_ids"])
    if len(labels) != len(inputs):
        raise ValueError("stored input_ids and labels have different lengths")
    marker = tokenizer.encode(LLAMA_ASSISTANT_HEADER, add_special_tokens=False)
    marker_start = find_subsequence(labels, marker)
    if marker_start is None:
        raise ValueError("Llama assistant header absent from stored labels")
    start = marker_start + len(marker)
    # The published Llama rows have a newline between header and content. Detect it
    # tokenically instead of assuming an ID.
    newline = tokenizer.encode("\n", add_special_tokens=False)
    if newline and labels[start : start + len(newline)] == newline:
        start += len(newline)
    return inputs, labels, start


def stored_example_usable(example: dict[str, Any], tokenizer: Any, max_sequence_length: int, include_answer_eos: bool = True) -> bool:
    """Cheap preflight predicate used to remove rows that cannot form a loss-bearing batch."""
    try:
        _, labels, start = stored_to_tokens(example, tokenizer)
        labels = labels[:max_sequence_length]
        answer, _, _ = build_masks(labels, min(start, len(labels)), tokenizer.eos_token_id, include_answer_eos)
        return any(answer)
    except (ValueError, IndexError):
        return False


def build_masks(labels: list[int], answer_start: int, eos_id: int, include_answer_eos: bool = True) -> tuple[list[bool], list[bool], bool]:
    """Return answer mask, padding mask, and whether no ending EOS made the row truncated."""
    n = len(labels)
    answer_end_eos = next((i for i in range(answer_start, n) if labels[i] == eos_id), None)
    truncated = answer_end_eos is None
    content_end = n if truncated else answer_end_eos
    answer = [False] * n
    for i in range(answer_start, content_end):
        answer[i] = True
    if answer_end_eos is not None and include_answer_eos:
        answer[answer_end_eos] = True
    padding = [False] * n
    if answer_end_eos is not None:
        for i in range(answer_end_eos + 1, n):
            padding[i] = True
    return answer, padding, truncated


@dataclass
class DenoisingCollator:
    tokenizer: Any
    corruption_mode: str
    max_sequence_length: int
    include_answer_eos: bool = True
    pad_to_multiple_of: int | None = None
    structured_loss_behavior: str = "all_answer_tokens"
    seed: int = 0
    deterministic: bool = False
    t_min: float = 0.1

    def __post_init__(self) -> None:
        """Validate collator configuration and cache this tokenizer's MASK token."""
        self.mask_info = validate_mask_token(self.tokenizer)
        self.stats = DataStats()
        if self.corruption_mode not in {"structured", "mask_only"}:
            raise ValueError(f"Unknown corruption mode: {self.corruption_mode}")

    def _prepare(self, feature: dict[str, Any]) -> dict[str, Any] | None:
        """Construct clean/noised IDs and masks for one unpadded dataset row."""
        try:
            if self.corruption_mode == "structured":
                if not llama_stored_ids_compatible(feature, self.tokenizer):
                    raise ValueError(
                        "Structured inputs are Llama-tokenized and cannot be used with this tokenizer. "
                        "Use corruption_mode=mask_only or provide tokenizer-specific structured preprocessing."
                    )
                inputs, labels, start = stored_to_tokens(feature, self.tokenizer)
            else:
                labels, start = source_to_tokens(feature, self.tokenizer)
                inputs = list(labels)
            answer, padding, truncated = build_masks(labels, start, self.tokenizer.eos_token_id, self.include_answer_eos)
            if truncated:
                self.stats.truncated += 1
            if not any(answer):
                self.stats.empty_answer += 1
                self.stats.dropped += 1
                return None
            if len(labels) > self.max_sequence_length:
                self.stats.truncated += 1
                labels, inputs = labels[: self.max_sequence_length], inputs[: self.max_sequence_length]
                answer, padding = answer[: self.max_sequence_length], padding[: self.max_sequence_length]
                if not any(answer):
                    self.stats.dropped += 1
                    return None
            return {"input_ids": inputs, "labels": labels, "answer_mask": answer, "padding_mask": padding, "example_index": int(feature.get("_index", 0))}
        except ValueError:
            self.stats.malformed += 1
            raise

    def __call__(self, features: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
        """Prepare, dynamically pad, and corrupt a list of dataset rows."""
        prepared = [x for feature in features if (x := self._prepare(feature)) is not None]
        if not prepared:
            raise ValueError("Batch has no usable examples")
        max_len = max(len(x["labels"]) for x in prepared)
        if self.pad_to_multiple_of:
            m = self.pad_to_multiple_of
            max_len = (max_len + m - 1) // m * m
        pad = self.tokenizer.eos_token_id
        batch: dict[str, list[list[int] | list[bool] | int]] = {k: [] for k in ("input_ids", "labels", "answer_mask", "padding_mask", "example_index")}
        for x in prepared:
            extra = max_len - len(x["labels"])
            batch["input_ids"].append(x["input_ids"] + [pad] * extra)
            batch["labels"].append(x["labels"] + [pad] * extra)
            batch["answer_mask"].append(x["answer_mask"] + [False] * extra)
            batch["padding_mask"].append(x["padding_mask"] + [True] * extra)
            batch["example_index"].append(x["example_index"])
        result = {
            "input_ids": torch.tensor(batch["input_ids"], dtype=torch.long),
            "labels": torch.tensor(batch["labels"], dtype=torch.long),
            "answer_mask": torch.tensor(batch["answer_mask"], dtype=torch.bool),
            "padding_mask": torch.tensor(batch["padding_mask"], dtype=torch.bool),
            "example_index": torch.tensor(batch["example_index"], dtype=torch.long),
        }
        from .corruption import apply_corruption
        return apply_corruption(result, self.mask_info["mask_token_id"], self.corruption_mode, self.structured_loss_behavior, self.t_min, self.seed, self.deterministic)
