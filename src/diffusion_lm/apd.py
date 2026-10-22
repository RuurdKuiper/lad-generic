"""Optional confidence-based token commitment, independent of token scoring."""
import math

import torch


def confidence_threshold(step: int, steps: int) -> float:
    """CAI-dLLM cosine shape, 15% warmup, endpoints 0.90 and 0.50.

    Normalize the discrete block's first/last steps to 0/1 so its final step
    reaches the requested endpoint. A one-step block uses the final threshold.
    """
    if steps < 1 or not 0 <= step < steps:
        raise ValueError("Expected a valid zero-based step within the block")
    if steps == 1:
        return 0.50
    progress = step / (steps - 1)
    phase = max(0.0, (progress - 0.15) / 0.85)
    return 0.50 + 0.20 * (1.0 + math.cos(math.pi * phase))


def selected_token_probabilities(logits, token_ids):
    """Full-vocabulary model probabilities, without top-k/temperature scaling."""
    scores = logits.float()
    return (scores.gather(1, token_ids[:, None]).squeeze(1) - scores.logsumexp(-1)).exp()


def resolve_mask_predictions(logits, selected, confidence, pending, mask_token_id):
    """Output-validity fallback if a decoder selects MASK itself.

    Use the same forward's highest-scoring non-mask token only for those rows.
    Ordinary sampled/Viterbi-selected tokens and their confidence stay unchanged.
    """
    invalid = pending & (selected == mask_token_id)
    if not bool(invalid.any()):
        return selected, confidence
    if logits.shape[-1] < 2:
        raise ValueError("APD cannot resolve a vocabulary containing only MASK")
    rows = invalid.nonzero(as_tuple=True)[0]
    top_ids = logits[rows].topk(2, dim=-1).indices
    alternative = torch.where(top_ids[:, 0] == mask_token_id, top_ids[:, 1], top_ids[:, 0])
    selected, confidence = selected.clone(), confidence.clone()
    selected[rows] = alternative
    confidence[rows] = selected_token_probabilities(logits[rows], alternative)
    return selected, confidence


def commitment_mask(confidence, pending, step, steps, *, endings=None, delay_endings=False):
    """Commit all qualifying pending positions; force progress and final cleanup.

    With ending retention delay, postpone endings while ordinary predictions
    would remain uncommitted. The fallback prefers an ordinary token in that
    case. No token budgets, position scaling, or grinding detector are used.
    """
    threshold = confidence_threshold(step, steps)
    if step == steps - 1:
        return pending.clone()
    finite = torch.isfinite(confidence)
    chosen = pending & finite & (confidence >= threshold)
    ordinary = pending if endings is None else pending & ~endings
    if delay_endings and endings is not None and bool((ordinary & ~chosen).any()):
        chosen &= ~endings
    if not bool(chosen.any()) and bool(pending.any()):
        pool = ordinary if delay_endings and bool(ordinary.any()) else pending
        scores = confidence.masked_fill(~pool | ~finite, -torch.inf)
        # If no finite score exists, choose the first eligible position safely.
        best = scores.argmax() if bool((pool & finite).any()) else pool.nonzero()[0, 0]
        chosen[best] = True
    return chosen
