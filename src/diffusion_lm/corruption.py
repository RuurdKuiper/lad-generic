"""Online corruption; validation is deterministic by seed and example index."""
from __future__ import annotations
import torch


def apply_corruption(batch, mask_token_id, mode, structured_loss_behavior, eos_padding_loss, t_min, seed, deterministic):
    """Apply configured corruption and choose the positions used for loss."""
    answer = batch["answer_mask"] & ~batch["padding_mask"]
    eos_padding = batch["padding_mask"]
    supervised = answer | eos_padding if eos_padding_loss else answer
    if mode == "structured":
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
