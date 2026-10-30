"""Observe the pinned native decoder without replacing its sampling/edit logic."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
import time

import torch

MODEL_ID = "inclusionAI/LLaDA2.2-mini"
MODEL_REVISION = "e4f77d25ab5ca86f2223c6cdc6a72b887e20c8a5"
MASK, DELETE, INSERT, EOS = 156895, 156930, 156931, 156892


@dataclass(frozen=True)
class Mark:
    probability: float = 0.0
    iteration: int = 0


@dataclass
class Frame:
    tokens: list[int]
    marks: list[Mark]
    iteration: int
    deletes: int = 0
    inserts: int = 0
    done: bool = False


def move_marks(written, old, marks, probabilities, iteration, length):
    """Mirror native DELETE / [MASK, old token] INSERT and fixed-block resizing."""
    result = []
    for i, token in enumerate(written):
        if token == DELETE:
            continue
        if token == INSERT:
            result.extend([Mark(), marks[i]])
        else:
            result.append(marks[i] if token == old[i] else Mark(probabilities[i], iteration))
    return (result + [Mark()] * length)[:length]


class NativeStreamer:
    def __init__(self, model):
        self.model = model
        self.lock = Lock()

    def stream(self, input_ids, *, timeout=240, selector=None, **options):
        """Run unchanged model.generate; send CPU snapshots after native edit operations.

        A bounded queue applies backpressure. Cancellation and errors restore instance methods
        before another request can enter; no patched global classes or retained GPU frames.
        """
        queue = Queue(maxsize=2)
        cancel = Event()

        def send(item):
            while not cancel.is_set():
                try:
                    queue.put(item, timeout=.1)
                    return
                except Full:
                    pass

        def work():
            try:
                with self.lock, torch.inference_mode():
                    if cancel.is_set():
                        return
                    self._run(input_ids, options, send, cancel, timeout, selector)
            except BaseException as exc:
                send(exc)
            finally:
                send(None)

        thread = Thread(target=work, daemon=True)
        thread.start()
        try:
            while True:
                try:
                    item = queue.get(timeout=.1)
                except Empty:
                    if not thread.is_alive():
                        break
                    continue
                if item is None:
                    break
                if isinstance(item, BaseException):
                    raise item
                yield item
        finally:
            cancel.set()
            thread.join()

    def _run(self, inputs, options, send, cancel, timeout, selector):
        model = self.model
        start = time.monotonic()
        prompt_length = inputs.shape[1]
        state = dict(iteration=0, deletes=0, inserts=0, marks=[], logits=None)
        # Save instance attributes separately: restoring a bound method onto an instance
        # would shadow its original class descriptor indefinitely.
        names = ("_joint_decode_block", "_apply_edit_operations_with_tracking", "_diffusion_sample")
        saved = {name: model.__dict__.get(name) for name in names}
        present = {name: name in model.__dict__ for name in names}
        joint = model._joint_decode_block
        edit = model._apply_edit_operations_with_tracking
        sample = model._diffusion_sample

        def guided_sample(logits, temperature=1.0, top_k=None, top_p=None):
            tokens, probabilities = sample(logits, temperature, top_k, top_p)
            state["sample_calls"] += 1
            initial_calls = 2 if options["temperature"] != 0 else 1
            if selector is None or state["sample_calls"] > initial_calls:
                return tokens, probabilities
            old = state["x"][0, state["block_start"]:state["block_end"]]
            # Edit decisions remain native. Guide only contiguous ordinary-token
            # predictions, without scoring any edge across a structural operation.
            allowed = (tokens != DELETE) & (tokens != INSERT) & (tokens != MASK)
            positions = torch.arange(len(tokens), device=tokens.device) + state["block_start"]
            allowed &= positions >= prompt_length
            begin = 0
            while begin < len(tokens):
                if not allowed[begin]:
                    begin += 1
                    continue
                end = begin + 1
                while end < len(tokens) and allowed[end]:
                    end += 1
                scores = logits[begin:end].clone()
                scores[:, [MASK, DELETE, INSERT]] = -torch.inf
                absolute = state["block_start"] + begin
                left_id = None
                # Only completed blocks or immutable prompt tokens supply a
                # boundary. Never bridge an edit barrier inside the active block.
                if absolute > 0 and (begin == 0 or absolute == prompt_length):
                    previous = state["x"][0, absolute - 1].item()
                    if previous not in (MASK, DELETE, INSERT):
                        left_id = previous
                selected, _ = selector.select_block(
                    scores, old[begin:end], torch.ones(end-begin, dtype=torch.bool, device=tokens.device),
                    top_k=top_k or 16, temperature=temperature, left_id=left_id,
                )
                tokens[begin:end] = selected
                begin = end
            # Confidence gates always use the full, unmodified model distribution.
            probabilities = logits.float().softmax(-1).gather(-1, tokens[:, None]).squeeze(-1)
            return tokens, probabilities

        def before_forward(module, args, kwargs):
            if cancel.is_set():
                raise RuntimeError("Generation cancelled")
            if time.monotonic() - start > timeout:
                raise RuntimeError("GPU time budget reached; generation is incomplete. Try fewer tokens or refinement steps.")

        def after_forward(module, args, output):
            state["logits"] = output.logits
            state["sample_calls"] = 0

        def observe_block(x, block_start, block_end, *args, **kwargs):
            state.update(x=x, block_start=block_start, block_end=block_end)
            if not state["marks"]:
                state["marks"] = [Mark()] * x.shape[1]
            return joint(x, block_start, block_end, *args, **kwargs)

        def observe_edit(written, old, tracking, mask_id, block_length, delete_token_id, split_token_id):
            result, new_tracking = edit(written, old, tracking, mask_id, block_length,
                                        delete_token_id, split_token_id)
            state["iteration"] += 1
            lo, hi = state["block_start"], state["block_end"]
            logits = state["logits"][0, lo:hi].float()
            ids = torch.tensor(written, device=logits.device).unsqueeze(-1)
            probabilities = logits.softmax(-1).gather(-1, ids).squeeze(-1).tolist()
            state["logits"] = None
            state["marks"][lo:hi] = move_marks(written, old, state["marks"][lo:hi],
                                               probabilities, state["iteration"], block_length)
            state["deletes"] += written.count(DELETE)
            state["inserts"] += written.count(INSERT)
            tokens = state["x"][0].tolist()
            tokens[lo:hi] = result
            end = prompt_length + options["gen_length"]
            send(Frame(tokens[prompt_length:end], list(state["marks"][prompt_length:end]),
                       state["iteration"], state["deletes"], state["inserts"]))
            return result, new_tracking

        try:
            model._joint_decode_block = observe_block
            model._apply_edit_operations_with_tracking = observe_edit
            model._diffusion_sample = guided_sample
            # Native decoder calls self.forward directly, bypassing Module.__call__ hooks.
            original_forward = model.forward
            forward_present = "forward" in model.__dict__
            saved_forward = model.__dict__.get("forward")
            def observed_forward(*args, **kwargs):
                before_forward(model, args, kwargs)
                output = original_forward(*args, **kwargs)
                after_forward(model, args, output)
                return output
            model.forward = observed_forward
            try:
                output = model.generate(inputs=inputs, **options)
            finally:
                if forward_present:
                    model.forward = saved_forward
                else:
                    del model.forward
            tokens = output[0].tolist()
            if any(token in (MASK, DELETE, INSERT) for token in tokens):
                raise RuntimeError("Native decoder reached its iteration cap with unresolved tokens. Increase the cap or reduce output length.")
            send(Frame(tokens, list(state["marks"][prompt_length:prompt_length + len(tokens)]),
                       state["iteration"], state["deletes"], state["inserts"], done=True))
        finally:
            for name in names:
                if present[name]:
                    setattr(model, name, saved[name])
                else:
                    delattr(model, name)


def render(frame, tokenizer, color_mode="Prediction iteration"):
    tokens = frame.tokens
    if EOS in tokens:
        tokens = tokens[:tokens.index(EOS)]
    pieces = []
    for i, token in enumerate(tokens):
        mark = frame.marks[i] if i < len(frame.marks) else Mark()
        text = "mask" if token == MASK else tokenizer.decode([token], skip_special_tokens=False)
        if token == MASK:
            style = "background:#d1d5db;color:#4b5563;border-radius:4px;padding:0 4px;margin:0 1px"
        elif color_mode == "Prediction probability":
            style = f"color:hsl({int(mark.probability * 120)},90%,30%)"
        elif color_mode == "Prediction iteration":
            lightness = 72 - round(42 * mark.iteration / max(frame.iteration, 1))
            style = f"color:hsl(210,90%,{lightness}%)"
        else:
            style = "color:inherit"
        title = f"position {i} · predicted at iteration {mark.iteration} · model probability {mark.probability:.1%}"
        pieces.append(f'<span style="{style}" title="{title}">{escape(text)}</span>')
    # Decode contiguous spans, preserving whitespace and multi-byte token sequences.
    spans, pending = [], []
    for token in tokens + [MASK]:
        if token == MASK:
            spans.append(tokenizer.decode(pending, skip_special_tokens=True, clean_up_tokenization_spaces=False))
            spans.append("[MASK]")
            pending = []
        else:
            pending.append(token)
    plain = "".join(spans[:-1])
    return ("<div style='font-family:system-ui;padding:14px;border:1px solid #d1d5db;"
            "border-radius:9px;background:#fafafa'>"
            f"<div style='font-weight:700;color:#2563eb'>Denoising iteration {frame.iteration} · "
            f"{len(tokens)} output positions · {frame.inserts} insertions · {frame.deletes} deletions</div>"
            f"<div style='line-height:2;font-size:15px;white-space:pre-wrap'>{''.join(pieces)}</div>"
            "<div style='font-size:11px;color:#6b7280'>Gray chips are masks. Hover for prediction details. "
            "Inserted and surviving tokens carry their prediction history as positions shift.</div>"
            "<details style='margin-top:10px'><summary>Plain text / copy code</summary>"
            "<textarea readonly aria-label='Plain text output' spellcheck='false' "
            "style='width:100%;min-height:9em;white-space:pre;font-family:monospace'>"
            f"{escape(plain)}</textarea></details></div>")
