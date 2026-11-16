"""Block-local repetition risk estimated from an unpenalized chain distribution."""

import math

import torch


def chain_bigram_marginals(emissions, edges, temperature=1.0):
    """P(candidate_t=i, candidate_(t+1)=j) from sum-product DP.

    Includes fixed-row constraints and boundary scores already in emissions.
    Zero temperature uses a T=1 soft surrogate for deterministic decoding;
    positive temperatures follow the sequence sampler. No model calls or RNG.
    """
    if emissions.ndim != 2 or min(emissions.shape) < 1:
        raise ValueError("Expected nonempty emissions [B,K]")
    length, k = emissions.shape
    if edges.shape != (length - 1, k, k):
        raise ValueError("Expected edges [B-1,K,K]")
    temperature = float(temperature)
    if not math.isfinite(temperature) or temperature < 0:
        raise ValueError("Temperature must be finite and nonnegative")
    if length == 1:
        return emissions.new_zeros((0, k, k), dtype=torch.float32)
    scale = max(temperature, 1e-6) if temperature else 1.0
    unary = emissions.float()
    unary = (unary - unary.amax(-1, keepdim=True)) / scale
    edges = edges.float()
    edges = (edges - edges.amax((1, 2), keepdim=True)) / scale
    forward = torch.empty_like(unary)
    backward = torch.empty_like(unary)
    forward[0] = unary[0]
    for t in range(1, length):
        row = unary[t] + torch.logsumexp(forward[t - 1, :, None] + edges[t - 1], 0)
        forward[t] = row - row.max()
    backward[-1] = 0.0
    for t in range(length - 2, -1, -1):
        row = torch.logsumexp(
            edges[t] + unary[t + 1, None, :] + backward[t + 1, None, :], 1
        )
        backward[t] = row - row.max()
    scores = forward[:-1, :, None] + edges + unary[1:, None, :] + backward[1:, None, :]
    return scores.flatten(1).softmax(-1).reshape_as(edges)


def repetition_risk_penalties(
    token_ids,
    emissions,
    edges,
    vocab_size,
    strength=1.0,
    excluded_token_ids=(),
    temperature=1.0,
    marginals=None,
):
    """gamma*log((1-r+9r)/(1-r)), r≈1-prod_(earlier edges)(1-q).

    q comes from the unpenalized joint diffusion+PMI distribution. Occurrences
    are approximated as independent, not an exact conditional repetition chance.
    State resets per call/block. Endings neither count nor receive penalties.
    A 1e-7 survival floor bounds the correction at effectively certain risk.
    Legal rows have unique tokens (fixed rows have one finite-emission column).
    """
    strength = float(strength)
    if not math.isfinite(strength) or strength < 0:
        raise ValueError("Repetition penalty strength must be finite and nonnegative")
    if (
        token_ids.shape != emissions.shape
        or token_ids.ndim != 2
        or min(token_ids.shape) < 1
    ):
        raise ValueError("Expected candidates/emissions [B,K]")
    length, k = token_ids.shape
    if edges.shape != (length - 1, k, k):
        raise ValueError("Expected edges [B-1,K,K]")
    penalties = emissions.new_zeros(edges.shape, dtype=torch.float32)
    if strength == 0 or length == 1:
        return penalties
    if strength > torch.finfo(torch.float32).max / (4 * length * 20):
        raise ValueError("Repetition penalty strength is too large for this block")
    q = (
        chain_bigram_marginals(emissions, edges, temperature)
        if marginals is None
        else marginals
    )
    if q.shape != edges.shape:
        raise ValueError("Invalid repetition-risk marginal shape")
    eligible = torch.ones_like(token_ids, dtype=torch.bool)
    if excluded_token_ids:
        excluded = torch.as_tensor(
            tuple(excluded_token_ids), device=token_ids.device, dtype=torch.long
        )
        eligible = ~torch.isin(token_ids, excluded)
    eligible_edges = eligible[:-1, :, None] & eligible[1:, None, :]
    q = q * eligible_edges
    keys = token_ids[:-1, :, None] * vocab_size + token_ids[1:, None, :]
    unique, inverse = torch.unique(keys.reshape(-1), return_inverse=True)
    indices = inverse.reshape_as(keys)
    log_survival = emissions.new_zeros(unique.numel(), dtype=torch.float32)
    floor = math.log(1e-7)
    for t in range(length - 1):
        previous = log_survival[indices[t]].clamp_min(floor)
        log_risk = (-torch.expm1(previous)).log()
        correction = torch.logaddexp(previous, math.log(9.0) + log_risk) - previous
        penalties[t] = strength * correction * eligible_edges[t]
        # Update only after scoring: the first potential occurrence is free.
        # Fixed-row dummy columns have zero marginal and contribute nothing.
        log_survival.scatter_add_(
            0,
            indices[t].reshape(-1),
            torch.log1p(-q[t].clamp_max(1.0 - 1e-7)).reshape(-1),
        )
        log_survival.clamp_min_(floor)
    return penalties
