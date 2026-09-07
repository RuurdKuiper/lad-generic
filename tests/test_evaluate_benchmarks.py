import importlib.util
from pathlib import Path
from types import SimpleNamespace

import torch

EVALUATOR_PATH = Path(__file__).resolve().parents[1] / "evaluate_benchmarks.py"
SPEC = importlib.util.spec_from_file_location("evaluate_benchmarks", EVALUATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
EVALUATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVALUATOR)
_generate_ar = EVALUATOR._generate_ar
_generate_diffusion = EVALUATOR._generate_diffusion


def test_autoregressive_generation_passes_attention_mask_and_pad_token(monkeypatch):
    from diffusion_lm import data

    monkeypatch.setattr(data, "apply_neutral_chat_template", lambda *args, **kwargs: [10, 11])

    class Model:
        config = SimpleNamespace(use_cache=False)

        def named_parameters(self):
            return []

        def generate(self, **kwargs):
            self.generate_kwargs = kwargs
            return torch.tensor([[10, 11, 12]])

    model = Model()
    tokenizer = SimpleNamespace(
        pad_token_id=None,
        eos_token_id=2,
        decode=lambda tokens, skip_special_tokens: "answer",
    )
    session = SimpleNamespace(
        model=model,
        tokenizer=tokenizer,
        device="cpu",
        adapter_path=Path("unused"),
    )

    assert _generate_ar(session, "Question", 2048, original_base=False) == "answer"
    assert torch.equal(model.generate_kwargs["attention_mask"], torch.ones((1, 2), dtype=torch.long))
    assert model.generate_kwargs["pad_token_id"] == tokenizer.eos_token_id
    assert model.generate_kwargs["max_new_tokens"] == 2048
    assert model.generate_kwargs["do_sample"] is False


def test_denoise_stream_sampler_receives_all_configured_controls(monkeypatch):
    captured = {}

    def fake_denoise_stream(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        yield "answer", "done", ""

    monkeypatch.setattr(EVALUATOR, "denoise_stream", fake_denoise_stream)
    session = SimpleNamespace()
    settings = {
        "sampler": "denoise_stream",
        "system_prompt": "System",
        "max_new_tokens": 128,
        "num_steps": 64,
        "noise_level": 0.75,
        "temperature": 0.6,
        "top_k": 7,
        "seed": 99,
        "permanent_unmask": False,
        "confidence_guided": True,
        "proportional_unmask": True,
        "early_stopping": True,
        "confidence_eos_eot_inf": True,
        "freeze_retained_tokens": False,
    }

    assert _generate_diffusion(session, "Question", settings, "structured") == "answer"
    assert captured["args"][:4] == (session, "Question", "System", 128)
    assert captured["args"][4:] == (64, 0.75, 0.6, 7, 99)
    assert captured["kwargs"] == {
        "permanent_unmask": False,
        "confidence_guided": True,
        "proportional_unmask": True,
        "early_stopping": True,
        "confidence_eos_eot_inf": True,
        "freeze_retained_tokens": False,
    }
