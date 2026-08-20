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
