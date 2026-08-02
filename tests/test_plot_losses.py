import json
import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location("plot_losses", Path(__file__).parents[1] / "plot_losses.py")
plot_losses = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(plot_losses)
loss_series = plot_losses.loss_series
moving_average = plot_losses.moving_average
read_metrics = plot_losses.read_metrics


def test_read_metrics_and_extract_loss_series(tmp_path):
    (tmp_path / "metrics.jsonl").write_text("\n".join([
        json.dumps({"split": "train", "step": 1, "weighted_loss": 4.0}),
        json.dumps({"split": "validation", "step": 2, "weighted_loss": 2.0}),
        json.dumps({"split": "train", "step": 3, "weighted_loss": 1.0}),
    ]))
    train, validation = loss_series(read_metrics(tmp_path))
    assert train == [(1, 4.0), (3, 1.0)]
    assert validation == [(2, 2.0)]
    assert moving_average([4.0, 2.0, 3.0], 2) == [4.0, 3.0, 2.5]
