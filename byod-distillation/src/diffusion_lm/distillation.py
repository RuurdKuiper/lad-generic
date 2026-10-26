"""Frozen causal teacher and full-vocabulary KL for a masked diffusion student."""
from __future__ import annotations

from contextlib import contextmanager
import math

import torch
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint

from .loss import _finish_selected_loss, _separate_answer_padding_loss


def resolve_distillation(config):
    settings = config.get("distillation", {}) or {}
    if not isinstance(settings, dict):
        raise ValueError("distillation must be a mapping")
    enabled = settings.get("enabled", False)
    weight = float(settings.get("weight", 0.5))
    temperature = float(settings.get("temperature", 1.0))
    chunk_size = settings.get("chunk_size", 64)
    if not isinstance(enabled, bool):
        raise ValueError("distillation.enabled must be true or false")
    if not math.isfinite(weight) or not 0 <= weight <= 1:
        raise ValueError("distillation.weight must be between zero and one")
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("distillation.temperature must be positive and finite")
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size < 1:
        raise ValueError("distillation.chunk_size must be a positive integer")
    active = enabled and weight > 0
    if active and config.get("train_normalization_layers", True):
        raise ValueError("A shared frozen teacher requires train_normalization_layers=false")
    return dict(enabled=active, weight=weight if active else 0.0,
                temperature=temperature, chunk_size=chunk_size)


def assert_frozen_teacher(model):
    """Adapter-free inference must use weights that never receive updates."""
    if not hasattr(model, "disable_adapter"):
        raise ValueError("The shared teacher requires a PEFT LoRA model")
    unexpected = [name for name, parameter in model.named_parameters()
                  if parameter.requires_grad and "lora_" not in name]
    if unexpected:
        raise ValueError(f"Teacher base weights must be frozen: {unexpected[:5]}")
    head = model.get_output_embeddings()
    if any(parameter.requires_grad for parameter in head.parameters()):
        raise ValueError("The shared teacher requires a frozen output head")


@contextmanager
def frozen_causal_teacher(model):
    """Restore student attention, dropout, and adapters even if the teacher fails.

    Restore native causal masking, including architecture-specific sliding
    windows: the student's loader marks its base noncausal. The teacher uses
    the backbone's ordinary causal-mask construction rather than the student's
    supplied bidirectional 4-D mask.
    No parameter data is modified, so gradient checkpointing remains safe.
    """
    training_states = [(module, module.training) for module in model.modules()]
    attributes = []
    seen = set()
    for module in model.modules():
        candidates = [module, getattr(module, "config", None)]
        config = getattr(module, "config", None)
        candidates.append(getattr(config, "text_config", None))
        for candidate in candidates:
            if candidate is None or id(candidate) in seen:
                continue
            seen.add(id(candidate))
            for name, value in (("is_causal", True), ("use_bidirectional_attention", False)):
                if hasattr(candidate, name):
                    attributes.append((candidate, name, getattr(candidate, name)))
                    setattr(candidate, name, value)
    try:
        model.eval()
        with model.disable_adapter(), torch.no_grad():
            yield
    finally:
        for candidate, name, value in reversed(attributes):
            setattr(candidate, name, value)
        for module, training in training_states:
            module.training = training


@torch.no_grad()
def causal_teacher_logits(model, labels, selection_mask, chunk_size=64):
    """Predict token t from clean positions <t, never from the masked inputs.

    Rows follow selection_mask.nonzero() order. Position zero has no preceding
    token and is omitted. Only the chosen rows reach the vocabulary head;
    every vocabulary entry is retained (no top-k approximation).
    Repeated EOS padding is causal context, as in ordinary teacher forcing.
    """
    selection_mask = selection_mask.clone()
    selection_mask[:, 0] = False
    example_ids, token_ids = selection_mask.nonzero(as_tuple=True)
    base = model.get_base_model()
    head = base.get_output_embeddings()
    if not len(token_ids):
        return head.weight.new_empty((0, head.weight.shape[0]))
    with frozen_causal_teacher(model):
        hidden = base.model(input_ids=labels[:, :-1],
                            use_cache=False).last_hidden_state
        selected = hidden[example_ids, token_ids - 1]
        chunks = []
        for chunk in selected.split(chunk_size):
            logits = head(chunk)
            # Gemma 2 applies this after its frozen LM head in the official
            # CausalLM forward. Preserve it in our selected-position path.
            cap = getattr(base.config, "final_logit_softcapping", None)
            if cap is not None:
                logits = torch.tanh(logits / cap) * cap
            chunks.append(logits)
        return torch.cat(chunks, dim=0).detach()


def _kl_chunk(student, teacher, temperature):
    student_logp = F.log_softmax(student.float() / temperature, dim=-1)
    teacher_logp = F.log_softmax(teacher.detach().float() / temperature, dim=-1)
    return F.kl_div(student_logp, teacher_logp, reduction="none", log_target=True).sum(-1) * temperature**2


def selected_distillation_loss(student, teacher, batch, settings, *,
                               use_t_weighting, answer_padding_weights, eos_padding_loss=False):
    """Reduce per-token KL using the same region/masking weights as hard CE.

    Student rows initially include all ordinary loss positions. Drop position
    zero on both sides of the KL because causal next-token targets start at 1.
    Checkpoint only small KL chunks to avoid retaining several dense FP32
    probability tensors for the complete sequence until backward.
    """
    example_ids, token_ids = batch["loss_mask"].nonzero(as_tuple=True)
    student = student[token_ids > 0]
    example_ids, token_ids = example_ids[token_ids > 0], token_ids[token_ids > 0]
    if student.shape != teacher.shape:
        raise ValueError(f"Teacher/student alignment mismatch: {teacher.shape} vs {student.shape}")
    if not len(token_ids):
        return student.sum() * 0.0
    values = []
    for student_chunk, teacher_chunk in zip(student.split(settings["chunk_size"]),
                                             teacher.split(settings["chunk_size"])):
        if torch.is_grad_enabled() and student.requires_grad:
            values.append(checkpoint(_kl_chunk, student_chunk, teacher_chunk,
                                     settings["temperature"], use_reentrant=False))
        else:
            values.append(_kl_chunk(student_chunk, teacher_chunk, settings["temperature"]))
    token_kl = torch.cat(values)
    mask = batch["loss_mask"].clone()
    mask[:, 0] = False
    counts = mask.sum(1)
    sampled_t = batch["sampled_t"] if use_t_weighting else None
    token_weights = (batch["token_loss_weights"][example_ids, token_ids]
                     if use_t_weighting and "token_loss_weights" in batch else None)
    if answer_padding_weights is not None:
        answer = batch["answer_mask"] & ~batch["padding_mask"]
        padding = batch["padding_mask"].clone()
        answer[:, 0] = False
        padding[:, 0] = False
        loss, _ = _separate_answer_padding_loss(
            token_kl, example_ids, counts, sampled_t, token_weights,
            answer[example_ids, token_ids], padding[example_ids, token_ids],
            answer.sum(1), padding.sum(1), answer_padding_weights, False,
        )
    else:
        eligible = batch["answer_mask"] | batch["padding_mask"] if eos_padding_loss else batch["answer_mask"]
        eligible = eligible.clone()
        eligible[:, 0] = False
        weighted = token_kl if token_weights is None else token_kl * token_weights
        sums = token_kl.new_zeros(counts.shape).scatter_add(0, example_ids, weighted)
        loss, _ = _finish_selected_loss(sums, token_kl.sum(), counts, sampled_t, eligible, False)
    return loss
