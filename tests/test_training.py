from diffusion_lm.training import _generation_inference_settings


def test_mask_only_generation_uses_full_remasking_and_permanent_retention():
    settings = _generation_inference_settings({
        "corruption_mode": "mask_only",
        "generation_perplexity": {
            "noise_level": 0.35,
            "permanent_unmask": False,
            "num_steps": 12,
        },
    })

    assert settings["noise_level"] == 1.0
    assert settings["permanent_unmask"] is True
    assert settings["num_steps"] == 12


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
