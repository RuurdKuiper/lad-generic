import json
import math

import pytest
import torch

from diffusion_lm.training import DEFAULT_GENERATION_PROMPTS, _available_output_dir, _generation_inference_settings, _generation_perplexity_interval, _load_generation_prompts, _resolve_learning_rate, generation_validation
from diffusion_lm.training import _build_learning_rate_scheduler


@pytest.mark.parametrize("schedule_name", ["cosine", "linear"])
@pytest.mark.parametrize("peak", [1e-5, 4e-5])
def test_learning_rate_warms_up_then_stays_above_one_tenth_of_peak(schedule_name, peak):
    parameter = torch.nn.Parameter(torch.zeros(()))
    optimizer = torch.optim.SGD([parameter], lr=peak)
    scheduler = _build_learning_rate_scheduler(
        {"scheduler": schedule_name, "warmup_steps": 25}, optimizer, 1000, peak,
    )
    rates = [optimizer.param_groups[0]["lr"]]
    for step in range(1100):
        optimizer.step()
        scheduler.step()
        rates.append(optimizer.param_groups[0]["lr"])
    assert rates[0] == 0
    assert rates[25] == pytest.approx(peak)
    assert min(rates[25:]) == pytest.approx(peak / 10)
    assert rates[1000] == rates[1100] == pytest.approx(peak / 10)
    assert all(a >= b for a, b in zip(rates[25:], rates[26:]))
    progress = (500 - 25) / (1000 - 25)
    decay = (1 + math.cos(math.pi * progress)) / 2 if schedule_name == "cosine" else 1 - progress
    assert rates[500] == pytest.approx(peak / 10 + 0.9 * peak * decay)


@pytest.mark.parametrize("endpoint", [1e-6, 3e-6])
def test_explicit_learning_rate_endpoint_is_supported_for_cosine(endpoint):
    optimizer = torch.optim.SGD([torch.nn.Parameter(torch.zeros(()))], lr=1e-5)
    scheduler = _build_learning_rate_scheduler(
        {"scheduler": "cosine", "end_learning_rate": endpoint}, optimizer, 10, 1e-5,
    )
    for step in range(10):
        optimizer.step()
        scheduler.step()
    assert optimizer.param_groups[0]["lr"] == pytest.approx(endpoint)


@pytest.mark.parametrize("endpoint", [0, 1e-7, 2e-5, float("nan")])
def test_endpoint_more_than_tenfold_below_peak_is_rejected(endpoint):
    optimizer = torch.optim.SGD([torch.nn.Parameter(torch.zeros(()))], lr=1e-5)
    with pytest.raises(ValueError, match="one tenth"):
        _build_learning_rate_scheduler({"scheduler": "cosine", "end_learning_rate": endpoint}, optimizer, 1000, 1e-5)


def test_available_output_dir_adds_incrementing_suffixes(tmp_path):
    base = tmp_path / "run"
    base.mkdir()
    (tmp_path / "run_1").mkdir()
    (tmp_path / "run_3").mkdir()

    assert _available_output_dir(base) == tmp_path / "run_2"


def test_available_output_dir_keeps_unused_path(tmp_path):
    path = tmp_path / "new-run"

    assert _available_output_dir(path) == path


def test_shared_generation_prompts_are_loaded_in_stable_order(tmp_path):
    prompt_file = tmp_path / "prompts.txt"
    prompt_file.write_text("# fixed set\nFirst prompt\n\nSecond prompt\n")

    assert _load_generation_prompts(prompt_file) == ("First prompt", "Second prompt")
    assert len(DEFAULT_GENERATION_PROMPTS) == 100
    from diffusion_lm.benchmarks import OPEN_ENDED_PROMPTS
    assert list(DEFAULT_GENERATION_PROMPTS) == OPEN_ENDED_PROMPTS
    assert DEFAULT_GENERATION_PROMPTS[:2] == (
        "What do you know about Amsterdam?",
        "Why is the sky blue?",
    )


def test_generation_perplexity_interval_defaults_to_validation_interval():
    assert _generation_perplexity_interval({"validation_steps": 500}) == 500


def test_generation_perplexity_interval_can_run_less_often_than_validation():
    config = {
        "validation_steps": 500,
        "generation_perplexity": {"interval_steps": 1000},
    }

    assert _generation_perplexity_interval(config) == 1000


def test_generation_perplexity_interval_must_align_with_validation():
    config = {
        "validation_steps": 500,
        "generation_perplexity": {"interval_steps": 750},
    }

    with pytest.raises(ValueError, match="must be a multiple"):
        _generation_perplexity_interval(config)


def test_learning_rate_scaling_is_off_by_default():
    learning_rate, effective_batch_size, scale = _resolve_learning_rate({
        "learning_rate": 1e-5,
        "batch_size": 16,
        "gradient_accumulation_steps": 1,
    })

    assert learning_rate == 1e-5
    assert effective_batch_size == 16
    assert scale == 1.0


def test_learning_rate_uses_sqrt_effective_batch_scaling():
    learning_rate, effective_batch_size, scale = _resolve_learning_rate({
        "learning_rate": 1e-5,
        "batch_size": 16,
        "gradient_accumulation_steps": 2,
        "learning_rate_scaling": {"enabled": True, "reference_batch_size": 8},
    }, num_processes=2)

    assert effective_batch_size == 64
    assert scale == pytest.approx(64 ** 0.5 / 8 ** 0.5)
    assert learning_rate == pytest.approx(1e-5 * scale)


def test_learning_rate_uses_linear_effective_batch_scaling():
    learning_rate, effective_batch_size, scale = _resolve_learning_rate({
        "learning_rate": 1e-5,
        "batch_size": 16,
        "gradient_accumulation_steps": 2,
        "learning_rate_scaling": {
            "enabled": True,
            "mode": "linear",
            "reference_batch_size": 8,
        },
    }, num_processes=2)

    assert effective_batch_size == 64
    assert scale == 8.0
    assert learning_rate == pytest.approx(8e-5)


def test_learning_rate_scaling_rejects_unknown_mode():
    with pytest.raises(ValueError, match="mode must be 'sqrt' or 'linear'"):
        _resolve_learning_rate({
            "learning_rate": 1e-5,
            "batch_size": 8,
            "learning_rate_scaling": {"enabled": True, "mode": "cubic"},
        })


@pytest.mark.parametrize("reference", [0, -1])
def test_learning_rate_scaling_rejects_invalid_reference_batch_size(reference):
    with pytest.raises(ValueError, match="reference_batch_size must be positive"):
        _resolve_learning_rate({
            "learning_rate": 1e-5,
            "batch_size": 8,
            "learning_rate_scaling": {
                "enabled": True,
                "reference_batch_size": reference,
            },
        })


@pytest.mark.parametrize("mode", ["mask_only", "structured"])
def test_generation_defaults_match_open_ended_protocol(mode):
    settings = _generation_inference_settings({"corruption_mode": mode})
    assert settings["sampler"] == "llada_official"
    assert settings["num_prompts"] == 100
    assert settings["permanent_unmask"] is True
    assert settings["confidence_guided"] is True
    assert settings["proportional_unmask"] is False
    assert settings["confidence_eos_eot_inf"] is True
    assert settings["max_new_tokens"] == settings["block_length"] == 128
    assert settings["num_steps"] == 64
    assert settings["temperature"] == 0.7
    assert settings["system_prompt"] == ""


def test_generation_allows_explicit_smoke_budgets():
    settings = _generation_inference_settings({"generation_perplexity": {
        "max_new_tokens": 16, "block_length": 16, "num_steps": 2, "num_prompts": 1,
    }})
    assert settings["max_new_tokens"] == settings["block_length"] == 16
    assert settings["num_steps"] == 2
    assert settings["num_prompts"] == 1


def test_generation_metrics_store_only_the_final_output(tmp_path, monkeypatch):
    class Model:
        def eval(self):
            return self

    class Tokenizer:
        all_special_ids = []

        def encode(self, text, add_special_tokens=False):
            return list(range(len(text.split())))

    def fake_generate(_session, prompt, **kwargs):
        assert prompt == "Prompt"
        assert kwargs == {
            "gen_length": 128, "steps": 64, "block_length": 128,
            "temperature": 0.7, "remasking": "low_confidence",
            "confidence_eos_eot_inf": True, "eot_token_id": None,
            "system_prompt": "", "seed": 1234,
        }
        return "final answer"

    scored = []

    def fake_perplexity(_model, _tokenizer, texts, _initial_norms, _device):
        scored.extend(texts)
        return {
            "generation_perplexity": 2.0,
            "generation_mean_nll": 0.5,
            "generation_tokens": 2,
            "_per_text_perplexities": [2.0],
        }

    monkeypatch.setattr("diffusion_lm.training.llada_generate", fake_generate)
    monkeypatch.setattr("diffusion_lm.training._base_perplexity", fake_perplexity)
    metrics = generation_validation(
        Model(), Tokenizer(), 99,
        {"corruption_mode": "structured", "quantization": "none", "generation_perplexity": {"prompts": ["Prompt"], "num_prompts": 1}},
        {}, torch.device("cpu"), tmp_path, 100,
    )

    record = json.loads((tmp_path / "generation_metrics.jsonl").read_text())
    assert scored == ["final answer"]
    assert record["final"] == "final answer"
    assert "states" not in record
    assert record["distinct_1"] == 1.0
    assert record["distinct_2"] == 1.0
    assert record["distinct_3"] == 0.0
    assert "unigram_repetition" not in record
    assert metrics["generation_perplexity"] == 2.0
    assert metrics["generation_mean_perplexity"] == 2.0
    assert metrics["generation_median_perplexity"] == 2.0
    assert metrics["generation_mean_distinct_1"] == 1.0


def test_generation_validation_scores_configured_thirty_prompt_prefix(tmp_path, monkeypatch):
    class Model:
        def eval(self):
            return self

    class Tokenizer:
        unk_token_id = -1
        all_special_ids = []

        def convert_tokens_to_ids(self, token):
            return 42 if token == "<|eot_id|>" else -1

        def encode(self, text, **_kwargs):
            return [1, 2]

    calls = []
    model, tokenizer, norms = Model(), Tokenizer(), {}

    def generate(session, prompt, **kwargs):
        assert session.model is model
        assert kwargs["eot_token_id"] == 42
        calls.append((prompt, kwargs["seed"]))
        return f"Answer {len(calls)}"

    def score(actual_model, actual_tokenizer, texts, actual_norms, device):
        assert actual_model is model and actual_tokenizer is tokenizer
        assert actual_norms is norms
        assert texts == [f"Answer {i}" for i in range(1, 31)]
        return {"generation_perplexity": 2.0, "generation_mean_nll": 0.7,
                "generation_tokens": 60, "_per_text_perplexities": [2.0] * 30}

    monkeypatch.setattr("diffusion_lm.training.llada_generate", generate)
    monkeypatch.setattr("diffusion_lm.training._base_perplexity", score)
    generation_validation(model, tokenizer, 99, {"corruption_mode": "mask_only", "generation_perplexity": {"num_prompts": 30}},
                          norms, torch.device("cpu"), tmp_path, 1000)
    assert calls == [(prompt, 1234 + i) for i, prompt in enumerate(DEFAULT_GENERATION_PROMPTS[:30])]
    records = [json.loads(line) for line in (tmp_path / "generation_metrics.jsonl").read_text().splitlines()]
    assert len(records) == 30
    assert [record["prompt"] for record in records] == list(DEFAULT_GENERATION_PROMPTS[:30])


def test_final_evaluation_profile_uses_the_full_suite_and_same_sampler_for_baseline():
    from pathlib import Path
    import yaml
    from diffusion_lm.benchmarks import (
        resolve_llada_generation_settings, resolve_mask_only_generation_settings,
    )

    root = Path(__file__).resolve().parents[1]
    benchmark = yaml.safe_load((root / "configs/open_ended.yaml").read_text())
    assert benchmark["limit"] == len(DEFAULT_GENERATION_PROMPTS) == 100
    for actual in (
        resolve_llada_generation_settings(benchmark, "open_ended"),
        resolve_mask_only_generation_settings(benchmark, "open_ended"),
    ):
        assert actual["temperature"] == 0.7
        assert actual["max_new_tokens"] == actual["block_length"] == 128
        assert actual["num_steps"] == 64
        assert actual["sampler"] == "llada_official"


@pytest.mark.parametrize("requested,expected", [(0, 0), (1, 1), (4, 2)])
def test_worker_count_respects_runtime_cpu_affinity(monkeypatch, requested, expected):
    from diffusion_lm import training
    monkeypatch.setattr(training.os, "sched_getaffinity", lambda pid: {0, 1}, raising=False)
    assert training._worker_count(requested) == expected


def test_worker_count_without_affinity_uses_cpu_count(monkeypatch):
    from diffusion_lm import training
    monkeypatch.delattr(training.os, "sched_getaffinity", raising=False)
    monkeypatch.setattr(training.os, "cpu_count", lambda: 1)
    assert training._worker_count(4) == 1
    with pytest.raises(ValueError, match="num_workers"):
        training._worker_count(-1)


@pytest.mark.parametrize("model,mode", [("llama", "quick"), ("gemma", "quick"), ("qwen", "quick"),
                                         ("llama", "paper"), ("gemma", "paper"), ("qwen", "paper"), ("ministral", "paper")])
def test_shipped_generation_budgets_match_the_64_token_diagnostic(model, mode):
    from train import load_training_config
    settings = _generation_inference_settings(load_training_config(model, mode))
    assert settings["max_new_tokens"] == settings["block_length"] == 64
    assert settings["num_steps"] == 32


@pytest.mark.parametrize("budgets", [
    {"max_new_tokens": 64, "block_length": 128},
    {"max_new_tokens": 64, "block_length": 16, "num_steps": 3},
    {"max_new_tokens": 0}, {"block_length": 0},
])
def test_invalid_generation_budgets_fail_before_sampling(budgets):
    with pytest.raises(ValueError, match="Generation requires"):
        _generation_inference_settings({"generation_perplexity": budgets})
