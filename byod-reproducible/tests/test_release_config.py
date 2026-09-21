import json
from pathlib import Path

import pytest
import yaml

from train import load_training_config


@pytest.mark.parametrize("model", ["llama", "gemma", "qwen", "ministral"])
def test_paper_presets_keep_the_original_recipe(model):
    config = load_training_config(model)
    assert config["dataset_name"] == "Ruurd/LAD-training-1m-256"
    assert config["max_updates"] == 25_000
    assert config["batch_size"] == 16
    assert config["lora_r"] == config["lora_alpha"] == 1024
    assert config["corruption_mode"] == "mask_only"
    assert config["structured_loss_behavior"] == "corrupted_answer_tokens"
    assert config["frontier_masking_probability"] == 0.0
    assert config["answer_padding_loss"]["enabled"] is False
    assert config["quantization"] == "none"


def test_quick_mode_is_explicitly_smaller():
    config = load_training_config("llama", "quick")
    assert config["run_mode"] == "quick"
    assert config["max_updates"] == 50
    assert config["lora_r"] == config["lora_alpha"] == 128
    assert config["model_name_or_path"] == "meta-llama/Llama-3.2-1B-Instruct"
    assert config["quantization"] == "none"
    assert config["generation_perplexity"]["enabled"] is False


@pytest.mark.parametrize(
    ("model", "expected_model", "quantization"),
    [
        ("llama", "meta-llama/Llama-3.2-1B-Instruct", "none"),
        ("gemma", "google/gemma-3-1b-it", "none"),
        ("qwen", "Qwen/Qwen2.5-1.5B-Instruct", "none"),
    ],
)
def test_quick_mode_selects_smaller_compatible_models(model, expected_model, quantization):
    config = load_training_config(model, "quick")
    assert config["model_name_or_path"] == expected_model
    assert config["quantization"] == quantization
    assert config["lora_r"] == config["lora_alpha"] == 128


def test_ministral_is_available_only_for_paper_reproduction():
    with pytest.raises(ValueError, match="no quick preset"):
        load_training_config("ministral", "quick")
    assert load_training_config("ministral", "paper")["model_name_or_path"] == (
        "mistralai/Ministral-8B-Instruct-2410"
    )


def test_llama_paper_config_matches_saved_original_run():
    root = Path(__file__).parents[1]
    reference = json.loads(
        (root / "reference/llama-3.1-8b-mask.resolved_config.json").read_text()
    )
    config = load_training_config("llama")
    runtime_fields = {
        "effective_batch_size", "fp8_active", "fp8_compute_capability",
        "fp8_device_name", "fp8_requested", "learning_rate_scale",
        "resolved_learning_rate", "resolved_training_precision",
        "structured_marker_dropped", "training_sample_limit",
        "training_samples_used", "validation_samples_used", "output_dir",
    }
    for key, value in reference.items():
        if key not in runtime_fields:
            assert config[key] == value


def test_every_external_input_is_revision_pinned():
    root = Path(__file__).parents[1]
    models = yaml.safe_load((root / "configs/models.yaml").read_text())
    paper = yaml.safe_load((root / "configs/paper.yaml").read_text())
    assert len(paper["dataset_revision"]) == 40
    assert all(len(preset["model_revision"]) == 40 for preset in models.values())
    assert all(
        len(preset["quick"]["model_revision"]) == 40
        for preset in models.values()
        if "quick" in preset
    )
