import json

import pytest
import torch

from diffusion_lm.training import (
    DEFAULT_GENERATION_PROMPTS,
    _available_output_dir,
    _build_learning_rate_scheduler,
    _generation_inference_settings,
    _generation_perplexity_interval,
    _load_generation_prompts,
    _resolve_fp8,
    _resolve_learning_rate,
    generation_validation,
)


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


def test_linear_scheduler_reaches_configured_nonzero_endpoint():
    parameter = torch.nn.Parameter(torch.tensor(1.0))
    optimizer = torch.optim.AdamW([parameter], lr=1e-5)
    scheduler = _build_learning_rate_scheduler(
        {"scheduler": "linear", "warmup_steps": 2, "end_learning_rate": 1e-6},
        optimizer,
        max_updates=10,
        initial_learning_rate=1e-5,
    )

    rates = []
    for _ in range(10):
        optimizer.step()
        scheduler.step()
        rates.append(optimizer.param_groups[0]["lr"])

    assert rates[1] == pytest.approx(1e-5)
    assert rates[-1] == pytest.approx(1e-6)
    assert rates[2:] == sorted(rates[2:], reverse=True)


def test_end_learning_rate_requires_linear_scheduler():
    parameter = torch.nn.Parameter(torch.tensor(1.0))
    optimizer = torch.optim.AdamW([parameter], lr=1e-5)

    with pytest.raises(ValueError, match="scheduler=linear"):
        _build_learning_rate_scheduler(
            {"scheduler": "cosine", "end_learning_rate": 1e-6},
            optimizer,
            max_updates=10,
            initial_learning_rate=1e-5,
        )


def test_llama_colab_long_run_uses_800k_samples_and_nonzero_linear_endpoint():
    from pathlib import Path
    import yaml

    config = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "configs/llama3_8b_mask_colab.yaml").read_text()
    )

    assert config["output_dir"] == "outputs/llama-3.1-8b-mask-long"
    assert config["max_updates"] * config["batch_size"] * config["gradient_accumulation_steps"] == 800_000
    assert config["scheduler"] == "linear"
    assert config["learning_rate"] == pytest.approx(1e-5)
    assert config["end_learning_rate"] == pytest.approx(1e-6)
    assert config["validation_steps"] == 500
    assert config["generation_perplexity"]["sampler"] == "llada_official"
    assert config["generation_perplexity"]["interval_steps"] % config["validation_steps"] == 0


def test_merged_full_finetuning_config_uses_low_memory_continuation():
    from pathlib import Path
    import yaml

    config = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "configs/llama3_8b_mask_colab_merged_full_finetune.yaml").read_text()
    )

    assert config["model_name_or_path"].endswith("/merged/llama-3.1-8b-mask")
    assert config["full_finetuning"] is True
    assert config["optimizer"] == "adamw8bit"
    assert config["quantization"] == "none"
    assert config["batch_size"] == 1
    assert config["gradient_accumulation_steps"] == 16
    assert config["gradient_checkpointing"] is True
    assert config["batch_size"] * config["gradient_accumulation_steps"] == 16
    assert config["resume_data_updates"] == 25000
    assert config["max_updates"] == 25000
    assert (config["resume_data_updates"] + config["max_updates"]) * 16 == 800_000
    assert config["checkpoint_steps"] == 5000
    assert config["save_best_model"] is False
    assert config["generation_perplexity"]["enabled"] is False
    assert "lora_r" not in config


@pytest.mark.parametrize("capability", [(8, 9), (9, 0), (10, 0), (12, 0)])
def test_fp8_is_enabled_only_on_supported_native_hardware(capability):
    resolved = _resolve_fp8(
        {"precision": "bf16", "fp8": {"enabled": True}},
        cuda_available=True,
        capability=capability,
        device_name="supported GPU",
        transformer_engine_available=True,
    )

    assert resolved["active"] is True
    assert resolved["mixed_precision"] == "fp8"
    assert resolved["notice"] is None


@pytest.mark.parametrize("capability", [(7, 5), (8, 0), (8, 6)])
def test_fp8_unsupported_gpu_falls_back_to_bf16_with_notice(capability):
    resolved = _resolve_fp8(
        {"precision": "fp16", "fp8": {"enabled": True}},
        cuda_available=True,
        capability=capability,
        device_name="unsupported GPU",
        transformer_engine_available=False,
    )

    assert resolved["active"] is False
    assert resolved["model_precision"] == "bf16"
    assert resolved["mixed_precision"] == "bf16"
    assert "falling back to BF16" in resolved["notice"]


def test_fp8_without_cuda_falls_back_before_checking_backend():
    resolved = _resolve_fp8(
        {"precision": "fp16", "fp8": {"enabled": True}},
        cuda_available=False,
        transformer_engine_available=False,
    )
    assert resolved["active"] is False
    assert resolved["mixed_precision"] == "bf16"
    assert "no CUDA GPU" in resolved["notice"]


def test_fp8_supported_gpu_requires_transformer_engine():
    with pytest.raises(ImportError, match="Transformer Engine is not installed"):
        _resolve_fp8(
            {"precision": "bf16", "fp8": {"enabled": True}},
            cuda_available=True,
            capability=(12, 0),
            device_name="G4",
            transformer_engine_available=False,
        )


@pytest.mark.parametrize("mode", ["mask_only", "structured"])
def test_generation_defaults_match_open_ended_protocol(mode):
    settings = _generation_inference_settings({"corruption_mode": mode})
    assert settings["sampler"] == "llada_official"
    assert settings["num_prompts"] == 30
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
    generation_validation(model, tokenizer, 99, {"corruption_mode": "mask_only"},
                          norms, torch.device("cpu"), tmp_path, 1000)
    assert calls == [(prompt, 1234 + i) for i, prompt in enumerate(DEFAULT_GENERATION_PROMPTS[:30])]
    records = [json.loads(line) for line in (tmp_path / "generation_metrics.jsonl").read_text().splitlines()]
    assert len(records) == 30
    assert [record["prompt"] for record in records] == list(DEFAULT_GENERATION_PROMPTS[:30])


def test_shipped_training_and_benchmark_configs_share_open_ended_settings():
    from pathlib import Path
    import yaml
    from diffusion_lm.benchmarks import (
        resolve_generation_settings, resolve_llada_generation_settings,
        resolve_mask_only_generation_settings,
    )

    root = Path(__file__).resolve().parents[1]
    expected = _generation_inference_settings({})
    keys = ("sampler", "temperature", "max_new_tokens", "num_steps", "block_length",
            "confidence_eos_eot_inf", "proportional_unmask")
    for path in (root / "configs").glob("*colab*.yaml"):
        config = yaml.safe_load(path.read_text())
        actual = _generation_inference_settings(config)
        assert actual["num_prompts"] == 30
        assert {key: actual[key] for key in keys} == {key: expected[key] for key in keys}
        if config["corruption_mode"] == "mask_only":
            assert 0.0 <= float(config.get("frontier_masking_probability", 0.0)) <= 1.0
    benchmark = yaml.safe_load((root / "configs/benchmarks.yaml").read_text())
    for actual in (
        resolve_generation_settings(benchmark, "open_ended", "structured"),
        resolve_llada_generation_settings(benchmark, "open_ended"),
        resolve_mask_only_generation_settings(benchmark, "open_ended"),
    ):
        assert {key: actual[key] for key in keys} == {key: expected[key] for key in keys}


def test_last_layer_and_lm_head_experiment_matches_long_run_except_for_declared_changes():
    from pathlib import Path
    import yaml

    root = Path(__file__).resolve().parents[1]
    original = yaml.safe_load((root / "configs/llama3_8b_mask_colab.yaml").read_text())
    experiment = yaml.safe_load((root / "configs/llama3_8b_mask_colab_lastlayer_lmhead.yaml").read_text())

    assert experiment.pop("train_last_n_layers") == 1
    assert experiment.pop("lora_targets") == ["q_proj", "v_proj", "lm_head"]
    assert experiment.pop("checkpoint_steps") == 5000
    assert experiment.pop("output_dir") == "outputs/llama-3.1-8b-mask-long-lastlayer-lmhead"
    original.pop("lora_targets")
    original.pop("output_dir")
    original.pop("checkpoint_steps")
    assert experiment == original
