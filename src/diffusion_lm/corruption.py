"""Online corruption; validation is deterministic by seed and example index."""
from __future__ import annotations
import torch


def apply_corruption(batch, mask_token_id, mode, structured_loss_behavior, t_min, seed, deterministic):
    """Apply configured corruption and choose the positions used for loss."""
    answer = batch["answer_mask"] & ~batch["padding_mask"]
    if mode == "structured":
        if structured_loss_behavior == "all_answer_tokens":
            loss_mask = answer
        elif structured_loss_behavior == "corrupted_answer_tokens":
            loss_mask = answer & (batch["input_ids"] != batch["labels"])
        elif structured_loss_behavior == "all_tokens":
            # Explicit opt-in to the legacy full-sequence objective, including
            # prompt/formatting positions and EOS padding positions.
            loss_mask = torch.ones_like(batch["labels"], dtype=torch.bool)
        else:
            raise ValueError(f"Unknown structured_loss_behavior={structured_loss_behavior}; expected all_answer_tokens, corrupted_answer_tokens, or all_tokens")
        batch["loss_mask"] = loss_mask
        batch["sampled_t"] = torch.full((answer.shape[0],), float("nan"))
        return batch
    noised = batch["labels"].clone()
    selected = torch.zeros_like(answer)
    ts = []
    for row, index in enumerate(batch["example_index"].tolist()):
        generator = None
        if deterministic:
            generator = torch.Generator(device="cpu").manual_seed(seed + index)
        t = torch.empty((), dtype=torch.float32).uniform_(t_min, 1.0, generator=generator).item()
        eligible = torch.where(answer[row])[0]
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
        batch["loss_mask"] = torch.ones_like(answer, dtype=torch.bool)
    elif structured_loss_behavior in {"all_answer_tokens", "corrupted_answer_tokens"}:
        # mask_only's historical objective supervises the positions actually
        # corrupted in the input; both names retain that behavior here.
        batch["loss_mask"] = selected & answer
    else:
        raise ValueError(f"Unknown structured_loss_behavior={structured_loss_behavior}; expected all_answer_tokens, corrupted_answer_tokens, or all_tokens")
    batch["sampled_t"] = torch.tensor(ts, dtype=torch.float32)
    return batch
