from diffusion_lm.training import _available_output_dir, _generation_inference_settings


def test_available_output_dir_adds_incrementing_suffixes(tmp_path):
    base = tmp_path / "run"
    base.mkdir()
    (tmp_path / "run_1").mkdir()
    (tmp_path / "run_3").mkdir()

    assert _available_output_dir(base) == tmp_path / "run_2"


def test_available_output_dir_keeps_unused_path(tmp_path):
    path = tmp_path / "new-run"

    assert _available_output_dir(path) == path


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
