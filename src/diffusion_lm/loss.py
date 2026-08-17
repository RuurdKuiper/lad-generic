"""Same-position denoising objectives. No autoregressive shift is used."""
from __future__ import annotations
import torch
import torch.nn.functional as F


def masked_denoising_loss(
    logits,
    labels,
    loss_mask,
    sampled_t=None,
    normalization_mask=None,
    *,
    compute_unweighted_metric=True,
    sparse_positions=True,
):
    """Compute masked CE with optional LLaDA-style inverse-t weighting.

    Returns a differentiable scalar and aggregate metrics. Examples without selected
    tokens are excluded rather than changing another example's denominator. When
    sampled_t is provided, normalization_mask must represent the complete eligible
    response, not only the positions selected for corruption.
    """
    counts = loss_mask.sum(dim=1)
    valid = counts > 0

    if sparse_positions:
        # Computing CE over [batch, sequence, vocabulary] wastes a large softmax
        # on positions excluded from the objective. Reuse one set of selected
        # indices for the logits, labels, and per-example reduction.
        example_ids, token_ids = loss_mask.nonzero(as_tuple=True)
        selected_ce = F.cross_entropy(
            logits[example_ids, token_ids], labels[example_ids, token_ids], reduction="none"
        )
        selected_ce_sums = torch.zeros(
            logits.shape[0], device=logits.device, dtype=selected_ce.dtype
        ).scatter_add(0, example_ids, selected_ce)
        selected_ce_total = selected_ce.sum()
    else:
        # Structured all-token training has nothing to compact; avoid copying
        # the entire logits tensor through advanced indexing in that mode.
        token_ce = F.cross_entropy(logits.transpose(1, 2), labels, reduction="none")
        selected_ce_sums = (token_ce * loss_mask).sum(dim=1)
        selected_ce_total = selected_ce_sums.sum()
    per_example = selected_ce_sums / counts.clamp_min(1)
    if sampled_t is None:
        weighted = per_example
    else:
        if normalization_mask is None:
            raise ValueError("normalization_mask is required when sampled_t is provided")
        response_lengths = normalization_mask.sum(dim=1).clamp_min(1)
        weighted = selected_ce_sums / sampled_t.to(logits.device).clamp_min(1e-8) / response_lengths

    # Avoid Python conditions on CUDA tensors: converting valid.any() to bool
    # synchronizes the device on every training step. The clamped denominator
    # also retains the existing differentiable zero-loss behavior for empty masks.
    valid_count = valid.sum()
    loss = (weighted * valid).sum() / valid_count.clamp_min(1)
    metrics = {
        "weighted_loss": loss.detach(),
        "valid_examples": valid_count.detach(),
        "supervised_tokens": counts.sum().detach(),
    }
    if compute_unweighted_metric:
        metrics["unweighted_masked_token_ce"] = (
            selected_ce_total / counts.sum().clamp_min(1)
        ).detach()
    return loss, metrics
