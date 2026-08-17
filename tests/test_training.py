import pytest

from diffusion_lm.training import DEFAULT_GENERATION_PROMPTS, _available_output_dir, _generation_inference_settings, _generation_perplexity_interval, _load_generation_prompts, _resolve_learning_rate


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
    assert len(DEFAULT_GENERATION_PROMPTS) == 20
    assert DEFAULT_GENERATION_PROMPTS[:2] == (
        "What do you know about Amsterdam?",
        "Tell me a story about a little dwarf.",
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


def test_mask_only_generation_uses_full_remasking_and_permanent_retention():
    settings = _generation_inference_settings({
        "corruption_mode": "mask_only",
        "generation_perplexity": {
            "noise_level": 0.35,
            "permanent_unmask": False,
            "confidence_guided": False,
            "max_new_tokens": 128,
            "temperature": 0.7,
            "top_k": 20,
            "num_steps": 12,
        },
    })

    assert settings["noise_level"] == 1.0
    assert settings["permanent_unmask"] is True
    assert settings["confidence_guided"] is True
    assert settings["max_new_tokens"] == 64
    assert settings["num_steps"] == 32
    assert settings["temperature"] == 1.0
    assert settings["top_k"] == 100


def test_structured_generation_keeps_configured_inference_settings():
    settings = _generation_inference_settings({
        "corruption_mode": "structured",
        "generation_perplexity": {
            "noise_level": 0.35,
            "permanent_unmask": False,
        },
    })

    assert settings["noise_level"] == 0.35
    assert settings["permanent_unmask"] is False
