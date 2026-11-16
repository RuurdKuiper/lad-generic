"""Optional confidence-based token commitment, independent of token scoring."""
import math

import torch


def confidence_threshold(step: int, steps: int, aggressiveness: float = 0.0) -> float:
    """CAI-dLLM cosine shape, 15% warmup, endpoints 0.90 and 0.50.

    Normalize the discrete block's first/last steps to 0/1 so its final step
    reaches the requested endpoint. A one-step block uses the final threshold.
    Aggressiveness scales both endpoints by (1-a): 0 preserves the old schedule,
    1 admits every finite-confidence candidate. Commitment guards still apply.
    """
    aggressiveness = float(aggressiveness)
    if not math.isfinite(aggressiveness) or not 0.0 <= aggressiveness <= 1.0:
        raise ValueError("APD aggressiveness must be finite and between 0 and 1")
    if steps < 1 or not 0 <= step < steps:
        raise ValueError("Expected a valid zero-based step within the block")
    if steps == 1:
        return 0.50 * (1.0 - aggressiveness)
    progress = step / (steps - 1)
    phase = max(0.0, (progress - 0.15) / 0.85)
    original = 0.50 + 0.20 * (1.0 + math.cos(math.pi * phase))
    return original if aggressiveness == 0 else original * (1.0 - aggressiveness)


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


def commitment_mask(confidence, pending, step, steps, *, endings=None, delay_endings=False, aggressiveness=0.0, minimum_tokens=1):
    """Commit all qualifying pending positions; force progress and final cleanup.

    With ending retention delay, postpone endings while ordinary predictions
    would remain uncommitted. The fallback prefers an ordinary token in that
    case. Fill a minimum per-step quota using highest-confidence pending rows.
    Ordinary rows precede endings when ending retention is delayed.
    """
    if not isinstance(minimum_tokens, int) or minimum_tokens < 1:
        raise ValueError("APD minimum tokens must be a positive integer")
    threshold = confidence_threshold(step, steps, aggressiveness)
    if step == steps - 1:
        return pending.clone()
    finite = torch.isfinite(confidence)
    chosen = pending & finite & (confidence >= threshold)
    ordinary = pending if endings is None else pending & ~endings
    if delay_endings and endings is not None and bool((ordinary & ~chosen).any()):
        chosen &= ~endings
    required = min(minimum_tokens, int(pending.sum()))
    needed = max(0, required - int(chosen.sum()))
    if needed:
        # Preserve the old ending delay while satisfying the mandatory quota:
        # exhaust ordinary rows before filling from endings. Nonfinite scores
        # rank last; stable ordering retains the old first-index fallback.
        pools = [ordinary, pending & ~ordinary] if delay_endings and endings is not None else [pending]
        for pool in pools:
            indices = (pool & ~chosen).nonzero(as_tuple=True)[0]
            count = min(needed, len(indices))
            if count:
                scores = confidence[indices].masked_fill(~finite[indices], -torch.inf)
                ranked = scores.argsort(descending=True, stable=True)
                chosen[indices[ranked[:count]]] = True
                needed -= count
            if needed == 0:
                break
    return chosen
