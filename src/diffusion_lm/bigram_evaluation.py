"""Opt-in selector measurements; never runs an additional model forward pass."""
import time

import torch


class ProfiledBigramSelector:
    """Wrap a selector to measure GPU-completed time and same-logit argmax changes.

    Explicit synchronization and metric collection add benchmark overhead. This
    wrapper is not used during normal generation. Frozen positions are excluded
    from the change fraction; each editable prediction at each step is counted.
    """
    def __init__(self, selector):
        self.selector = selector
        self.calls = self.changed = self.editable = 0
        self.elapsed_ms = 0.0

    def set_step_context(self, block_step, block_steps):
        setter = getattr(self.selector, 'set_step_context', None)
        if setter is not None:
            setter(block_step, block_steps)

    def select_block(self, logits, current_ids, editable, **kwargs):
        if logits.device.type == 'cuda':
            torch.cuda.synchronize(logits.device)
        start = time.perf_counter()
        result = self.selector.select_block(logits, current_ids, editable, **kwargs)
        if logits.device.type == 'cuda':
            torch.cuda.synchronize(logits.device)
        self.elapsed_ms += (time.perf_counter() - start) * 1000
        self.calls += 1
        self.changed += int(((result[0] != logits.argmax(-1)) & editable).sum())
        self.editable += int(editable.sum())
        return result

    @property
    def last_path_margins(self):
        return self.selector.last_path_margins

    def metrics(self):
        return dict(selector_calls=self.calls, editable_predictions=self.editable,
                    changed_predictions=self.changed,
                    changed_fraction=self.changed / max(1, self.editable),
                    selector_ms=self.elapsed_ms,
                    mean_selector_ms=self.elapsed_ms / max(1, self.calls))
