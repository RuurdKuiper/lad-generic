import pytest

from diffusion_lm.benchmarks import _multiple_choice_fields, _sample_indices, load_benchmark, resolve_generation_settings


def test_open_ended_benchmark_has_reproducible_thirty_prompt_suite():
    examples = load_benchmark("open_ended", "test", None, "unused", None)

    assert len(examples) == 30
    assert examples[0].example_id == "0"
    assert examples[0].kind == "open_ended"
    assert examples[0].prompt == "What do you know about Amsterdam?"


def test_open_ended_benchmark_respects_limit():
    examples = load_benchmark("open_ended", "test", 3, "unused", None)

    assert len(examples) == 3


def test_open_ended_benchmark_supports_fractional_smoke_suite():
    examples = load_benchmark("open_ended", "test", None, "unused", None, limit_fraction=0.05)

    assert len(examples) == 2
    assert [example.example_id for example in examples] == ["0", "15"]


def test_fractional_sampling_is_evenly_spaced_and_rounded_up():
    assert _sample_indices(101, limit_fraction=0.05) == [0, 16, 33, 50, 67, 84]


def test_benchmark_limits_are_mutually_exclusive():
    with pytest.raises(ValueError, match="either limit or limit_fraction"):
        _sample_indices(100, limit=5, limit_fraction=0.05)


def test_hellaswag_uses_endings_as_answer_choices():
    row = {"ctx": "A person starts cooking.", "endings": ["A", "B", "C", "D"], "label": "2"}

    question, choices, answer = _multiple_choice_fields("hellaswag", row, 0)

    assert question == "A person starts cooking."
    assert choices == ["A", "B", "C", "D"]
    assert answer == "C"


def test_arc_maps_dataset_choice_labels_to_output_letters():
    row = {
        "question": "Which answer is correct?",
        "choices": {"text": ["First", "Second", "Third", "Fourth"], "label": ["1", "2", "3", "4"]},
        "answerKey": "3",
    }

    question, choices, answer = _multiple_choice_fields("arc_c", row, 0)

    assert question == "Which answer is correct?"
    assert choices == ["First", "Second", "Third", "Fourth"]
    assert answer == "C"


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
