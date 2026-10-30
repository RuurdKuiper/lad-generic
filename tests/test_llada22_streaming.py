"""Edit-aware UI invariants, plus parity with the pinned upstream decoder.

Set LLADA22_NATIVE_SOURCE to the pinned modeling_llada2_moe.py for model-free
integration checks using its actual methods and scripted forward logits.
"""
import ast
import importlib.util
import logging
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "huggingface/llada22_space"))
from streaming import MASK, DELETE, INSERT, EOS, Mark, Frame, NativeStreamer, move_marks, render


def test_marks_follow_insert_delete_truncation_and_padding():
    marks = [Mark(.1, 1), Mark(.2, 2), Mark(.3, 3), Mark(.4, 4)]
    assert move_marks([INSERT, DELETE, 12, 13], [10, 11, 12, 13], marks,
                      [.9]*4, 5, 4) == [Mark(), marks[0], marks[2], marks[3]]
    assert move_marks([DELETE, 11, 12, 13], [10, 11, 12, 13], marks,
                      [.9]*4, 5, 4) == marks[1:] + [Mark()]
    assert move_marks([INSERT, 11, 12, 13], [10, 11, 12, 13], marks,
                      [.9]*4, 5, 4) == [Mark(), *marks[:3]]
    assert move_marks([14], [10], marks[:1], [.7], 5, 1) == [Mark(.7, 5)]


class Tokenizer:
    def decode(self, ids, **kwargs):
        return "".join({1: "<script>", 2: "\n  code", EOS: ""}.get(i, str(i)) for i in ids)


def test_render_escapes_and_preserves_copyable_whitespace():
    html = render(Frame([1, 2, MASK, EOS, 1], [Mark(.8, 1)]*5, 2), Tokenizer())
    assert "<script>" not in html
    assert "&lt;script&gt;\n  code[MASK]</textarea>" in html
    assert "position 4" not in html


@pytest.fixture
def native_model():
    path = os.getenv("LLADA22_NATIVE_SOURCE")
    if not path:
        pytest.skip("Set LLADA22_NATIVE_SOURCE for pinned-upstream integration tests")
    source = Path(path).read_text()
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "LLaDA2MoeModelLM")
    names = {"_top_k_logits", "_top_p_logits", "_diffusion_sample", "_get_num_transfer_tokens",
             "_apply_edit_operations_with_tracking", "_resample_to_escape_loop", "_joint_decode_block", "generate"}
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(methods) == len(names)
    generated = ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(
        name="Native", bases=[], keywords=[], body=methods, decorator_list=[])], type_ignores=[]))
    namespace = dict(torch=torch, F=F, Optional=__import__("typing").Optional,
                     logger=logging.getLogger("llada22-test"))
    namespace["logger"].warning_once = namespace["logger"].warning
    exec(compile(generated, str(path), "exec"), namespace)
    native = namespace["Native"]

    class Model(native):
        device = torch.device("cpu")
        def __init__(self):
            self.calls = 0
            self.modes = []
        def forward(self, x, **kwargs):
            self.modes.append(torch.is_inference_mode_enabled())
            self.calls += 1
            ids = x.clone()
            ids[ids == MASK] = 3
            # Explicitly exercise both structural edits, then settle.
            if self.calls == 2:
                ids[0, -1] = INSERT
                ids[0, -2] = DELETE
            logits = torch.full((*x.shape, INSERT + 1), -20.)
            logits.scatter_(-1, ids.unsqueeze(-1), 20.)
            return SimpleNamespace(logits=logits)
    return Model


@pytest.mark.parametrize("prompt_length", [1, 4, 5])
@pytest.mark.parametrize("post_steps", [0, 2])
def test_stream_matches_native_with_partial_prompt_blocks(native_model, prompt_length, post_steps):
    inputs = torch.full((1, prompt_length), 7, dtype=torch.long)
    options = dict(gen_length=9, block_length=4, steps=2, temperature=0., max_post_steps=post_steps,
                   threshold=.5, editing_threshold=0., eos_early_stop=True, max_steps_per_block=32)
    plain = native_model()
    torch.manual_seed(42)
    expected = plain.generate(inputs=inputs, **options)
    observed = native_model()
    torch.manual_seed(42)
    frames = list(NativeStreamer(observed).stream(inputs, **options))
    assert frames[-1].done
    assert frames[-1].tokens == expected[0].tolist()
    assert plain.calls == observed.calls
    assert all(observed.modes)
    assert not {"forward", "_joint_decode_block", "_apply_edit_operations_with_tracking", "_diffusion_sample"} & observed.__dict__.keys()
    assert all(not set(frame.tokens) & {DELETE, INSERT} for frame in frames)
    if post_steps:
        assert frames[-1].inserts > 0
        assert frames[-1].deletes > 0


def test_error_and_cancel_restore_methods(native_model):
    model = native_model()
    streamer = NativeStreamer(model)
    options = dict(gen_length=8, block_length=4, steps=2, temperature=0., max_post_steps=2)
    with pytest.raises(RuntimeError, match="time budget"):
        list(streamer.stream(torch.tensor([[7]]), timeout=-1, **options))
    assert "forward" not in model.__dict__
    frames = streamer.stream(torch.tensor([[7]]), **options)
    next(frames)
    frames.close()
    assert "forward" not in model.__dict__
    assert streamer.lock.acquire(blocking=False)
    streamer.lock.release()


def test_guidance_never_scores_structural_candidates(native_model):
    class Selector:
        def __init__(self):
            self.calls = 0
        def select_block(self, scores, old, editable, **kwargs):
            self.calls += 1
            assert torch.isneginf(scores[:, [MASK, DELETE, INSERT]]).all()
            return scores.argmax(-1), torch.ones(len(scores))
    selector = Selector()
    model = native_model()
    frames = list(NativeStreamer(model).stream(torch.tensor([[7]]), selector=selector,
                  gen_length=8, block_length=4, steps=2, temperature=0., max_post_steps=2))
    assert selector.calls > 0
    assert frames[-1].inserts > 0 and frames[-1].deletes > 0


def test_unresolved_masks_are_reported_as_incomplete(native_model):
    class NeverResolves(native_model):
        def forward(self, x, **kwargs):
            logits = torch.full((*x.shape, INSERT + 1), -20.)
            logits[..., MASK] = 20
            return SimpleNamespace(logits=logits)
    model = NeverResolves()
    with pytest.raises(RuntimeError, match="unresolved"):
        list(NativeStreamer(model).stream(torch.tensor([[7]]), gen_length=8,
             block_length=4, steps=2, temperature=0., max_post_steps=0, max_steps_per_block=2))
    assert "forward" not in model.__dict__


def test_native_eos_stops_without_generating_future_blocks(native_model):
    class Ends(native_model):
        def forward(self, x, **kwargs):
            output = super().forward(x, **kwargs)
            output.logits[0, 1] = -20
            output.logits[0, 1, EOS] = 20
            return output
    model = Ends()
    frames = list(NativeStreamer(model).stream(torch.tensor([[7]]), gen_length=9,
                  block_length=4, steps=2, temperature=0., max_post_steps=0, eos_early_stop=True))
    assert frames[-1].tokens == [EOS]
    assert model.calls == 1
