import json

import pytest

from diffusion_lm.benchmarks import BenchmarkExample, BenchmarkRunReporter, _benchmark_spec, _choice_prompt, _multiple_choice_fields, _sample_indices, extract_answer, load_benchmark, resolve_generation_settings, resolve_llada_generation_settings, resolve_mask_only_generation_settings, score_prediction


def test_benchmark_reporter_isolates_and_structures_each_run(tmp_path):
    reporter = BenchmarkRunReporter(tmp_path, {"tasks": ["arc_c"]}, "smoke run")
    record = {"model": "llada:GSAI-ML/LLaDA-8B-Instruct", "task": "arc_c", "method": "diffusion", "prediction": "A"}
    summary = {"model": record["model"], "task": "arc_c", "method": "diffusion", "accuracy": 1.0}

    reporter.save_result(record)
    reporter.save_summary(summary)
    run_path = reporter.complete()

    assert run_path.parent == tmp_path
    assert run_path.name.endswith("--smoke-run")
    assert json.loads((run_path / "run.json").read_text())["status"] == "completed"
    assert json.loads((run_path / "summary.json").read_text())["models"][0]["results"] == [summary]
    group = run_path / "models" / "llada-gsai-ml-llada-8b-instruct" / "arc_c" / "diffusion"
    assert json.loads((group / "results.jsonl").read_text()) == record
    assert json.loads((group / "summary.json").read_text()) == summary


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


def test_multiple_choice_prompt_and_target_match_training_contract():
    prompt = _choice_prompt("mmlu", "Question?", ["First", "Second"])
    example = BenchmarkExample("mmlu", "0", prompt, "B: Second", "multiple_choice", {})

    assert prompt == "Answer the following multiple-choice question. Start your response with the correct option label followed by a colon, for example `A:`.\n\nQuestion?\n\nA: First\nB: Second"
    assert score_prediction(example, "B: Second")
    assert score_prediction(example, "B. Second")
    assert score_prediction(example, "The correct answer is B: Second")
    assert score_prediction(example, "The answer is B: Second")
    assert score_prediction(example, "I would select option B.")
    assert not score_prediction(example, "I considered A and B, but the latter seems stronger.")


def test_multiple_choice_extraction_ignores_unmarked_letters_in_explanations():
    assert extract_answer("After considering A and B, the latter is stronger.", "multiple_choice") == ""
    assert extract_answer("The correct answer is B: 12.", "multiple_choice") == "B"


def test_hellaswag_uses_training_prompt_and_labelled_validation_split():
    prompt = _choice_prompt("hellaswag", "A person opens a door.", ["They enter.", "They leave."])

    assert prompt.startswith("Choose the option that most plausibly continues the described event. Start your response with the correct option label followed by a colon")
    assert _benchmark_spec("hellaswag", "test")[2] == "validation"


def test_gpqa_uses_its_published_train_named_evaluation_split():
    assert _benchmark_spec("gpqa", "test")[2] == "train"


def test_gsm8k_scores_the_last_numeric_answer_from_a_rationale():
    example = BenchmarkExample("gsm8k", "0", "problem", "work shown\n#### 3", "gsm8k", {})

    assert extract_answer(example.answer, "gsm8k") == "3"
    assert score_prediction(example, "Two blue plus one white gives 3 bolts.")
    assert not score_prediction(example, "A robe takes 2 bolts and then 1 bolt.")


def test_math_ignores_terminal_punctuation_for_final_answer():
    example = BenchmarkExample("math", "0", "problem", "Therefore, $\\boxed{27}$.", "math", {})

    assert extract_answer(example.answer, "math") == "27"
    assert score_prediction(example, "27.")


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


def test_llada_uses_published_task_specific_inference_settings():
    gsm8k = resolve_llada_generation_settings({"generation": {"temperature": 0.7}}, "gsm8k")
    humaneval = resolve_llada_generation_settings({}, "humaneval")

    assert gsm8k["sampler"] == "llada_official"
    assert gsm8k["max_new_tokens"] == gsm8k["num_steps"] == gsm8k["block_length"] == 512
    assert gsm8k["temperature"] == 0.0
    assert gsm8k["confidence_eos_eot_inf"] is True
    assert gsm8k["eot_token_id"] == 126348
    assert gsm8k["proportional_unmask"] is False
    assert humaneval["logits_eos_inf"] is True
    assert humaneval["confidence_eos_eot_inf"] is False


def test_mask_only_adapters_use_the_same_official_task_sampler():
    gsm8k = resolve_mask_only_generation_settings({}, "gsm8k")
    overridden = resolve_mask_only_generation_settings(
        {"mask_only_task_generation": {"gsm8k": {"block_length": 8}}}, "gsm8k"
    )

    assert gsm8k["sampler"] == "llada_official"
    assert gsm8k["max_new_tokens"] == gsm8k["num_steps"] == gsm8k["block_length"] == 512
    assert gsm8k["temperature"] == 0.0
    assert gsm8k["confidence_eos_eot_inf"] is True
    assert gsm8k["proportional_unmask"] is False
    assert overridden["block_length"] == 8
