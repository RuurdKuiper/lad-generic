"""Same-position denoising objectives. No autoregressive shift is used."""
from __future__ import annotations
import torch
import torch.nn.functional as F


def masked_denoising_loss(logits, labels, loss_mask, sampled_t=None, normalization_mask=None):
    """Compute masked CE with optional LLaDA-style inverse-t weighting.

    Returns a differentiable scalar and aggregate metrics. Examples without selected
    tokens are excluded rather than changing another example's denominator. When
    sampled_t is provided, normalization_mask must represent the complete eligible
    response, not only the positions selected for corruption.
    """
    token_ce = F.cross_entropy(logits.transpose(1, 2), labels, reduction="none")
    counts = loss_mask.sum(dim=1)
    valid = counts > 0
    per_example = (token_ce * loss_mask).sum(dim=1) / counts.clamp_min(1)
    if sampled_t is None:
        weighted = per_example
    else:
        if normalization_mask is None:
            raise ValueError("normalization_mask is required when sampled_t is provided")
        response_lengths = normalization_mask.sum(dim=1).clamp_min(1)
        weighted = (token_ce * loss_mask).sum(dim=1) / sampled_t.to(logits.device).clamp_min(1e-8) / response_lengths
    loss = weighted[valid].mean() if valid.any() else logits.sum() * 0.0
    raw = token_ce[loss_mask].mean() if loss_mask.any() else logits.sum() * 0.0
    return loss, {"weighted_loss": loss.detach(), "unweighted_masked_token_ce": raw.detach(), "valid_examples": valid.sum().detach(), "supervised_tokens": counts.sum().detach()}
