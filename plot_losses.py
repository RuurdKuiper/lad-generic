#!/usr/bin/env python
"""Plot training and validation loss curves from one or more LAD output runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_metrics(run_dir: str | Path) -> list[dict[str, Any]]:
    """Read valid JSONL metric records from one training output directory."""
    path = Path(run_dir) / "metrics.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"No metrics.jsonl found in {Path(run_dir).resolve()}")
    records = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path}:{line_number}") from exc
        if "step" in record and "weighted_loss" in record:
            records.append(record)
    return records


def loss_series(records: list[dict[str, Any]]) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Return logged train and validation loss points, ordered by update step."""
    train = [(int(record["step"]), float(record["weighted_loss"])) for record in records if record.get("split") == "train"]
    # Older/short runs may only contain the interval average at validation.
    if not train:
        train = [(int(record["step"]), float(record["weighted_loss"])) for record in records if record.get("split") == "train_interval"]
    validation = [(int(record["step"]), float(record["weighted_loss"])) for record in records if record.get("split") == "validation"]
    return sorted(train), sorted(validation)


def moving_average(values: list[float], window: int) -> list[float]:
    """Compute a trailing moving average without adding a NumPy dependency."""
    if window <= 1:
        return values
    total = 0.0
    result = []
    for index, value in enumerate(values):
        total += value
        if index >= window:
            total -= values[index - window]
        result.append(total / min(index + 1, window))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", help="Output run directories containing metrics.jsonl")
    parser.add_argument("--labels", nargs="*", help="Optional labels, in the same order as runs")
    parser.add_argument("--smooth", type=int, default=10, help="Trailing-average window for training loss (default: 10; use 1 for raw)")
    parser.add_argument("--output", default="losses.png", help="PNG/PDF/SVG output path (default: losses.png)")
    parser.add_argument("--log-y", action="store_true", help="Use a logarithmic loss axis")
    args = parser.parse_args()
    if args.smooth < 1:
        parser.error("--smooth must be at least 1")
    if args.labels and len(args.labels) != len(args.runs):
        parser.error("--labels must provide exactly one label per run")

    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise SystemExit("Plotting requires matplotlib. Install it with `python -m pip install matplotlib`.") from exc

    figure, axis = plt.subplots(figsize=(10, 6))
    plotted = False
    for index, run in enumerate(args.runs):
        run_path = Path(run)
        label = args.labels[index] if args.labels else run_path.name
        train, validation = loss_series(read_metrics(run_path))
        color = f"C{index % 10}"
        if train:
            steps, losses = zip(*train)
            axis.plot(steps, moving_average(list(losses), args.smooth), color=color, linewidth=1.7, label=f"{label} — train")
            plotted = True
        if validation:
            steps, losses = zip(*validation)
            axis.plot(steps, losses, color=color, linestyle="--", marker="o", markersize=4, linewidth=1.5, label=f"{label} — validation")
            plotted = True
        if not train and not validation:
            print(f"Warning: {run_path} has no train or validation loss records.")
    if not plotted:
        raise SystemExit("No plottable loss records found.")

    axis.set(title="Training and validation loss", xlabel="Gradient update step", ylabel="Weighted denoising loss")
    if args.log_y:
        axis.set_yscale("log")
    axis.grid(True, alpha=.25)
    axis.legend()
    figure.tight_layout()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=180)
    print(f"Saved loss plot to {output.resolve()}")


if __name__ == "__main__":
    main()
