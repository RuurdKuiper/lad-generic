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
