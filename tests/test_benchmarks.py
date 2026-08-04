from diffusion_lm.benchmarks import load_benchmark, resolve_generation_settings


def test_open_ended_benchmark_has_reproducible_thirty_prompt_suite():
    examples = load_benchmark("open_ended", "test", None, "unused", None)

    assert len(examples) == 30
    assert examples[0].example_id == "0"
    assert examples[0].kind == "open_ended"
    assert examples[0].prompt == "What do you know about Amsterdam?"


def test_open_ended_benchmark_respects_limit():
    examples = load_benchmark("open_ended", "test", 3, "unused", None)

    assert len(examples) == 3


def test_generation_settings_use_corruption_specific_overrides():
    config = {
        "generation": {"temperature": 0.7, "top_k": 20},
        "generation_by_corruption": {
            "structured": {"temperature": 0.9},
            "mask_only": {"temperature": 0.5, "noise_level": 0.8},
        },
    }

    structured = resolve_generation_settings(config, "open_ended", "structured")
    masked = resolve_generation_settings(config, "open_ended", "mask_only")

    assert structured["temperature"] == 0.9
    assert masked["temperature"] == 0.5
    assert masked["noise_level"] == 1.0
    assert masked["permanent_unmask"] is True
    assert masked["confidence_guided"] is True


def test_legacy_generation_settings_fall_back_to_structured_settings():
    config = {"generation": {"temperature": 0.7}, "generation_by_corruption": {"structured": {"temperature": 0.9}}}

    settings = resolve_generation_settings(config, "open_ended", "legacy")

    assert settings["temperature"] == 0.9
