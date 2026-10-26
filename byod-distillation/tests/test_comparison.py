import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from compare_runs import compare_runs
from train import load_training_config


def write_run(path, weight, **overrides):
    path.mkdir()
    config = dict(model="llama", seed=42, batch_size=1, output_dir=str(path),
                  distillation={"enabled": weight > 0, "weight": weight}, **overrides)
    (path / "resolved_config.json").write_text(json.dumps(config))
    (path / "metrics.jsonl").write_text("\n".join(json.dumps(row) for row in [
        dict(split="train", step=1, weighted_loss=4.0, elapsed_seconds=1),
        dict(split="validation", step=2, weighted_loss=3.0, elapsed_seconds=4),
    ]))
    return path


def test_comparison_uses_only_original_validation_loss(tmp_path):
    baseline = write_run(tmp_path / "baseline", 0)
    distilled = write_run(tmp_path / "distilled", 0.5)
    figure = compare_runs(baseline, distilled)
    assert len(figure.axes) == 2
    assert list(figure.axes[0].lines[0].get_xdata()) == [2]
    assert list(figure.axes[0].lines[0].get_ydata()) == [3]
    assert list(figure.axes[1].lines[1].get_xdata()) == [4 / 60]
    plt.close(figure)


def test_comparison_rejects_different_training_data_or_budget(tmp_path):
    baseline = write_run(tmp_path / "baseline", 0, max_updates=2)
    distilled = write_run(tmp_path / "distilled", 0.5, max_updates=3)
    with pytest.raises(ValueError, match="max_updates"):
        compare_runs(baseline, distilled)


def test_baseline_and_distilled_configs_differ_only_in_distillation():
    root = Path(__file__).resolve().parents[1]
    baseline = load_training_config("llama", "quick", config_path=str(root / "configs/baseline.yaml"))
    distilled = load_training_config("llama", "quick", config_path=str(root / "configs/distillation.yaml"))
    assert baseline.pop("distillation")["enabled"] is False
    assert distilled.pop("distillation")["weight"] == 0.5
    assert baseline == distilled


def test_experimental_notebook_is_not_pointed_at_byod():
    root = Path(__file__).resolve().parents[1]
    notebook = json.loads((root / "notebooks/train_distillation.ipynb").read_text())
    source = "".join(notebook["cells"][2]["source"])
    assert 'REPOSITORY_URL = "https://github.com/RuurdKuiper/lad-generic.git"' in source
    assert 'EXPERIMENT_BRANCH = "experiment/ar-distillation"' in source
    assert 'PROJECT_DIR = REPOSITORY_DIR / "byod-distillation"' in source
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), "notebook-cell", "exec")
            assert not cell["outputs"] and cell["execution_count"] is None


def test_quick_comparison_matches_1000_update_settings(tmp_path):
    from run_comparison import comparison_configs
    configs = comparison_configs(tmp_path)
    baseline = configs["baseline"].copy()
    distilled = configs["distilled"].copy()
    assert baseline.pop("distillation")["weight"] == 0
    assert distilled.pop("distillation")["weight"] == 0.5
    assert baseline.pop("output_dir") != distilled.pop("output_dir")
    assert baseline == distilled
    assert baseline["max_updates"] == 1000
    assert baseline["batch_size"] == baseline["gradient_accumulation_steps"] == 1
    assert baseline["validation_samples"] == baseline["test_samples"] == 64
    assert baseline["model_name_or_path"] == "meta-llama/Llama-3.2-1B-Instruct"


@pytest.mark.parametrize("dashboard", [False, True])
def test_comparison_runs_both_objectives_and_writes_report(tmp_path, monkeypatch, dashboard):
    import yaml
    import run_comparison as runner
    from diffusion_lm import notebook

    calls = []
    def train(command, *args, **kwargs):
        config = yaml.safe_load(Path(command[command.index("--config") + 1]).read_text())
        run = Path(config["output_dir"])
        calls.append(run.name)
        run.mkdir()
        (run / "resolved_config.json").write_text(json.dumps(config))
        (run / "metrics.jsonl").write_text(json.dumps(dict(
            split="validation", step=2, weighted_loss=3., elapsed_seconds=4.,
        )) + "\n")
        (run / "test_metrics.json").write_text(json.dumps({"weighted_loss": 3.1}))
        (run / "runtime_environment.json").write_text(json.dumps({"device_type": "test"}))
    monkeypatch.setattr(runner.subprocess, "run", train)
    monkeypatch.setattr(notebook, "run_with_dashboard", train)
    summary = runner.run_comparison(tmp_path / "comparison", updates=2, dashboard=dashboard)
    assert calls == ["baseline", "distilled"]
    assert summary["baseline"]["final_test"]["weighted_loss"] == 3.1
    assert (tmp_path / "comparison/comparison.png").is_file()
    assert json.loads((tmp_path / "comparison/summary.json").read_text()) == summary
    with pytest.raises(FileExistsError):
        runner.run_comparison(tmp_path / "comparison", updates=2, dashboard=dashboard)
    assert calls == ["baseline", "distilled"]


def test_comparison_interrupt_does_not_start_the_second_run(tmp_path, monkeypatch):
    from diffusion_lm import notebook
    from run_comparison import run_comparison
    calls = []
    def interrupt(command, *args):
        calls.append(command)
        raise KeyboardInterrupt
    monkeypatch.setattr(notebook, "run_with_dashboard", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run_comparison(tmp_path, dashboard=True)
    assert len(calls) == 1
    assert not (tmp_path / "distilled.yaml").exists()


def test_comparison_notebook_defaults_and_training_cell(tmp_path, monkeypatch):
    import importlib
    from types import SimpleNamespace
    import sys
    import run_comparison as runner
    from diffusion_lm import notebook as helpers

    root = Path(__file__).resolve().parents[1]
    notebook = json.loads((root / "notebooks/compare_distillation.ipynb").read_text())
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), "comparison-cell", "exec")
            assert not cell["outputs"] and cell["execution_count"] is None
    settings = {}
    exec("".join(notebook["cells"][6]["source"]), settings)
    assert settings["UPDATES"] == 1000 and settings["EVALUATION_SAMPLES"] == 64
    assert settings["SAVE_TO_DRIVE"] is True
    settings["SAVE_TO_DRIVE"] = False
    monkeypatch.setattr(importlib, "reload", lambda module: module)
    monkeypatch.setattr(helpers, "remove_unused_transformer_engine", lambda: None)
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=SimpleNamespace(
        is_available=lambda: True, get_device_name=lambda index: "Test GPU",
    )))
    calls = []
    monkeypatch.setattr(runner, "run_comparison", lambda *args, **kwargs: calls.append((args, kwargs)))
    source = "".join(notebook["cells"][8]["source"]).replace(
        'Path("/content/BYOD-distillation-comparisons")', f"Path({str(tmp_path)!r})",
    )
    exec(compile(source, "comparison-training", "exec"), settings)
    assert len(calls) == 1
    assert calls[0][1] == dict(updates=1000, evaluation_samples=64, validation_steps=100, dashboard=True, batch_size=1)
    assert settings["output_root"].parent == tmp_path


def test_batch_size_eight_is_used_for_both_training_runs(tmp_path):
    from run_comparison import comparison_configs
    configs = comparison_configs(tmp_path, batch_size=8)
    for config in configs.values():
        assert config["batch_size"] == 8
        assert config["gradient_accumulation_steps"] == 1
        assert config["max_updates"] == 1000


@pytest.mark.parametrize("batch_size", [0, -1, 1.5, True])
def test_invalid_batch_size_is_rejected(tmp_path, batch_size):
    from run_comparison import comparison_configs
    with pytest.raises(ValueError, match="batch_size"):
        comparison_configs(tmp_path, batch_size=batch_size)
