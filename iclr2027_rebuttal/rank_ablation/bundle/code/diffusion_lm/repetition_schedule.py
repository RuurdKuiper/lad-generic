"""A short absolute-iteration schedule, independent of the total NFE budget."""

import math


def repetition_strength_factor(block_step, fade_iterations=6):
    """Normalized logistic: full at step 0, exactly zero at step fade_iterations-1.

    Steps are zero-based within each block. A single-step block keeps its full
    penalty; extending the NFE budget never stretches the early penalty window.
    fade_iterations=0 disables decay. The logistic slope is fixed at 1.6 and its
    midpoint is the middle of the active window. No random numbers are used.
    """
    if not isinstance(block_step, int) or block_step < 0:
        raise ValueError("Block step must be a nonnegative integer")
    if (
        not isinstance(fade_iterations, int)
        or fade_iterations < 0
        or fade_iterations == 1
    ):
        raise ValueError("Fade iterations must be 0 or an integer of at least 2")
    if fade_iterations == 0 or block_step == 0:
        return 1.0
    last = fade_iterations - 1
    if block_step >= last:
        return 0.0
    midpoint = last / 2.0

    def sigmoid(step):
        x = 1.6 * (step - midpoint)
        # Stable decreasing logistic even for a large configured window.
        z = math.exp(-abs(x))
        return z / (1.0 + z) if x >= 0 else 1.0 / (1.0 + z)

    first, final = sigmoid(0), sigmoid(last)
    return (sigmoid(block_step) - final) / (first - final)
