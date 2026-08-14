"""Online corruption; validation is deterministic by seed and example index."""
from __future__ import annotations
import torch


def _legacy_structural_noise(tokens: torch.Tensor, mask_token_id: int, generator: torch.Generator | None = None) -> torch.Tensor:
    """Apply the historical LAD answer corruption to one unpadded answer."""
    corrupted = tokens.clone()
    length = len(corrupted)
    if not length:
        return corrupted
    # One in ten examples starts from an entirely masked answer.
    if torch.rand((), generator=generator).item() < 0.1:
        return torch.full_like(corrupted, mask_token_id)
    noise_prob = torch.rand((), generator=generator).item()
    # The original routine applies this independent masking block half the time.
    if torch.rand((), generator=generator).item() < 0.5:
        mask_fraction = torch.rand((), generator=generator).item() * 0.5
        count = int(length * mask_fraction)
        if count:
            indices = torch.randperm(length, generator=generator)[:count]
            corrupted[indices] = mask_token_id
    if length <= 2:
        return corrupted
    swap_mask = torch.rand(length - 1, generator=generator) < (noise_prob / 4)
    for index in torch.where(swap_mask)[0].tolist():
        value = corrupted[index].clone()
        corrupted[index] = corrupted[index + 1]
        corrupted[index + 1] = value
    duplicate_mask = torch.rand(length, generator=generator) < (noise_prob / 4)
    duplicate_indices = torch.where(duplicate_mask)[0]
    if len(duplicate_indices):
        directions = torch.randint(0, 2, (len(duplicate_indices),), generator=generator)
        backward = duplicate_indices[(directions == 0) & (duplicate_indices > 0)]
        forward = duplicate_indices[(directions == 1) & (duplicate_indices < length - 1)]
        # NumPy advanced indexing copies the RHS for each assignment. The
        # legacy code applies backward copies first, then forward copies.
        corrupted[backward] = corrupted[backward - 1]
        corrupted[forward] = corrupted[forward + 1]
    if torch.rand((), generator=generator).item() < (noise_prob / 4):
        span_length = int(torch.randint(1, min(3, length) + 1, (), generator=generator).item())
        shift = int(torch.randint(1, 5, (), generator=generator).item())
        direction = -1 if torch.randint(0, 2, (), generator=generator).item() == 0 else 1
        start = int(torch.randint(0, length - span_length + 1, (), generator=generator).item())
        span = corrupted[start : start + span_length].clone()
        target = max(0, start - shift) if direction == -1 else min(length - span_length, start + shift)
        corrupted[target : target + span_length] = span
    return corrupted


def apply_corruption(batch, mask_token_id, mode, structured_loss_behavior, eos_padding_loss, t_min, seed, deterministic):
    """Apply configured corruption and choose the positions used for loss."""
    answer = batch["answer_mask"] & ~batch["padding_mask"]
    eos_padding = batch["padding_mask"]
    supervised = answer | eos_padding if eos_padding_loss else answer
    if mode == "structured":
        online = batch.pop("structured_online", torch.zeros(answer.shape[0], dtype=torch.bool))
        for row, needs_noise in enumerate(online.tolist()):
            if not needs_noise:
                continue
            generator = None
            if deterministic:
                generator = torch.Generator(device="cpu").manual_seed(seed + int(batch["example_index"][row]))
            positions = torch.where(answer[row])[0]
            batch["input_ids"][row, positions] = _legacy_structural_noise(
                batch["labels"][row, positions], mask_token_id, generator
            )
        if structured_loss_behavior == "all_answer_tokens":
            loss_mask = supervised
        elif structured_loss_behavior == "corrupted_answer_tokens":
            loss_mask = supervised & (batch["input_ids"] != batch["labels"])
        elif structured_loss_behavior == "all_tokens":
            # EOS padding is controlled separately so it can be compared with
            # answer-only objectives without changing the primary loss mode.
            loss_mask = ~batch["padding_mask"] | eos_padding if eos_padding_loss else ~batch["padding_mask"]
        else:
            raise ValueError(f"Unknown structured_loss_behavior={structured_loss_behavior}; expected all_answer_tokens, corrupted_answer_tokens, or all_tokens")
        batch["loss_mask"] = loss_mask
        batch["sampled_t"] = torch.full((answer.shape[0],), float("nan"))
        return batch
    batch.pop("structured_online", None)
    noised = batch["labels"].clone()
    # When selected for loss, EOS padding is a real denoising target:
    # it must sometimes be replaced by MASK so the same-position loss teaches
    # the model to *produce* EOS rather than merely copy a visible one.  Other
    # mask-only objectives do not supervise padding and therefore leave it
    # untouched.
    eligible_mask_only = supervised
    selected = torch.zeros_like(eligible_mask_only)
    ts = []
    for row, index in enumerate(batch["example_index"].tolist()):
        generator = None
        if deterministic:
            generator = torch.Generator(device="cpu").manual_seed(seed + index)
        t = torch.empty((), dtype=torch.float32).uniform_(t_min, 1.0, generator=generator).item()
        eligible = torch.where(eligible_mask_only[row])[0]
        if len(eligible):
            draw = torch.rand(len(eligible), generator=generator) < t
            if not draw.any():
                pick = torch.randint(len(eligible), (1,), generator=generator)
                draw[pick] = True
            selected[row, eligible[draw]] = True
        ts.append(t)
    noised[selected] = mask_token_id
    batch["input_ids"] = noised
    if structured_loss_behavior == "all_tokens":
        # Keep mask-only's stochastic inputs, but train against every target
        # position just like the legacy full-sequence objective. In this mode
        # training.py also disables inverse-t weighting.
        batch["loss_mask"] = ~batch["padding_mask"] | eos_padding if eos_padding_loss else ~batch["padding_mask"]
    elif structured_loss_behavior in {"all_answer_tokens", "corrupted_answer_tokens"}:
        # mask_only's historical objective supervises the positions actually
        # corrupted in the input; both names retain that behavior here.
        batch["loss_mask"] = selected & supervised
    else:
        raise ValueError(f"Unknown structured_loss_behavior={structured_loss_behavior}; expected all_answer_tokens, corrupted_answer_tokens, or all_tokens")
    batch["sampled_t"] = torch.tensor(ts, dtype=torch.float32)
    return batch
