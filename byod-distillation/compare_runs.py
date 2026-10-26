"""Compare ordinary validation loss versus updates and elapsed training time."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def compare_runs(baseline_run, distilled_run):
    import matplotlib.pyplot as plt

    paths = [Path(baseline_run), Path(distilled_run)]
    configs = [json.loads((path / "resolved_config.json").read_text()) for path in paths]
    # Reject accidental comparisons across changed data, models, or budgets.
    # Output paths, timing, and distillation settings deliberately differ.
    ignored = {"output_dir", "distillation"}
    differences = sorted(key for key in configs[0].keys() | configs[1].keys()
                         if key not in ignored and configs[0].get(key) != configs[1].get(key))
    if differences:
        raise ValueError(f"Runs have different comparison settings: {', '.join(differences)}")
    if configs[0].get("distillation", {}).get("weight", 0) != 0:
        raise ValueError("The baseline must have teacher weight zero")
    if configs[1].get("distillation", {}).get("weight", 0) <= 0:
        raise ValueError("The distilled run must have a positive teacher weight")
    environments = [path / "runtime_environment.json" for path in paths]
    if all(path.exists() for path in environments):
        if json.loads(environments[0].read_text()) != json.loads(environments[1].read_text()):
            raise ValueError("Runs used different hardware or PyTorch versions; timing is not comparable")
    curves = []
    for path in paths:
        rows = [json.loads(line) for line in (path / "metrics.jsonl").read_text().splitlines() if line.strip()]
        rows = [row for row in rows if row.get("split") == "validation"]
        if not rows or any("elapsed_seconds" not in row for row in rows):
            raise ValueError(f"No timed validation records found in {path}")
        curves.append(rows)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for name, rows in zip(("Baseline", "Frozen AR teacher"), curves):
        axes[0].plot([row["step"] for row in rows], [row["weighted_loss"] for row in rows], marker=".", label=name)
        axes[1].plot([row["elapsed_seconds"] / 60 for row in rows], [row["weighted_loss"] for row in rows], marker=".", label=name)
    for axis, xlabel in zip(axes, ("Optimizer updates", "Elapsed training minutes (includes validation)")):
        axis.set(xlabel=xlabel, ylabel="Original validation denoising loss")
        axis.legend()
        axis.grid(alpha=0.2)
    return fig


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline")
    parser.add_argument("distilled")
    parser.add_argument("--output", default="comparison.png")
    args = parser.parse_args()
    figure = compare_runs(args.baseline, args.distilled)
    figure.savefig(args.output, dpi=160)
    print(args.output)
