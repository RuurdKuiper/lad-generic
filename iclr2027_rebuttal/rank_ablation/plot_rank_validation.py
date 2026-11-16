"""Plot the common validation metric for all four ranks, with a late-stage inset."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, NullLocator


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
METRIC = "unweighted_masked_token_ce"
RUNS = {
    128: ROOT / "outputs/rank-ablation/fp8-checkpoint-v2/rank-128",
    512: ROOT / "outputs/rank-ablation/fp8-checkpoint-v2/rank-512",
    1024: HERE / "reference_1024",
    2048: ROOT / "outputs/rank-ablation/fp8-checkpoint-v2/rank-2048",
}
STYLES = {
    128: dict(color="#0072B2", linestyle="-", marker="o"),
    512: dict(color="#D58000", linestyle=(0, (7, 3)), marker="s"),
    1024: dict(color="#A44891", linestyle=(0, (1.5, 2)), marker="D"),
    2048: dict(color="#008260", linestyle=(0, (6, 2, 1.5, 2)), marker="^"),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objective", action="store_true", help="Plot the actual 90/10 objective, using the fresh rank-1024 run")
    args = parser.parse_args()
    axes_only = args.objective
    metric = "weighted_loss" if args.objective else METRIC
    runs = dict(RUNS)
    if args.objective:
        runs[1024] = ROOT / "outputs/rank-ablation/fp8-checkpoint-v2/rank-1024"
    output = HERE / "figures"
    output.mkdir(exist_ok=True)
    data = {}
    sources = {}
    csv_rows = []
    signatures = set()
    for rank, folder in runs.items():
        path = folder / "metrics.jsonl"
        content = path.read_bytes()
        rows = [json.loads(line) for line in content.decode().splitlines() if line.strip()]
        rows = sorted((row for row in rows if row.get("split") == "validation"), key=lambda row: row["step"])
        assert rows and len({row["step"] for row in rows}) == len(rows), f"Missing or duplicated validation points: {rank}"
        if args.objective:
            config = json.loads((folder / "resolved_config.json").read_text())
            assert config["answer_padding_loss"] == {"enabled": True, "answer_weight": .9, "padding_weight": .1}
            assert all(math.isclose(row["weighted_loss"], .9 * row["answer_loss"] + .1 * row["padding_loss"], rel_tol=1e-6)
                       for row in rows), f"Stored objective does not match the component losses: {rank}"
        data[rank] = [(int(row["step"]), float(row[metric])) for row in rows]
        assert all(value > 0 for _, value in data[rank]), "Log scaling requires positive values"
        signatures.update((row["valid_examples"], row["supervised_tokens"], row["mean_sampled_t"]) for row in rows)
        sources[str(rank)] = {
            "file": path.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(content).hexdigest(), "points": len(rows),
            "last_update": rows[-1]["step"], "last_loss": rows[-1][metric],
        }
        csv_rows.extend({"rank": rank, "update": step, "metric": metric, "loss": value}
                        for step, value in data[rank])
    assert len(signatures) == 1, "The logs do not share the same validation counts and corruption summary"

    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11.5,
        "axes.spines.top": False, "axes.spines.right": False,
        "pdf.fonttype": 42, "ps.fonttype": 42,
    })
    figure = plt.figure(figsize=(10, 6.1) if axes_only else (12.8, 7.8), facecolor="white")
    axis = figure.add_axes([0.095, 0.13, 0.88, 0.84] if axes_only else [0.085, 0.18, 0.86, 0.66])
    handles = []
    labels = []
    for rank, points in data.items():
        steps, values = zip(*points)
        line, = axis.plot(
            steps, values, **STYLES[rank], linewidth=2.2, markersize=5.3,
            markevery=(rank % 5, 10), markerfacecolor="white", markeredgewidth=1.3,
        )
        handles.append(line)
        suffix = "" if args.objective else " (historical)"
        labels.append(f"Rank {rank:,}" + (suffix if rank == 1024 else ""))
        axis.plot(steps[-1], values[-1], marker=STYLES[rank]["marker"],
                  color=STYLES[rank]["color"], markersize=6, linestyle="none")
        if args.objective and steps[-1] < 25000 and not axes_only:
            axis.annotate(f"{steps[-1]:,} updates", (steps[-1], values[-1]), xytext=(-8, -27),
                          textcoords="offset points", ha="right", color=STYLES[rank]["color"],
                          fontsize=10.5, arrowprops=dict(arrowstyle="-", color=STYLES[rank]["color"], lw=.8))

    axis.set_yscale("log")
    all_values = [value for points in data.values() for _, value in points]
    axis.set_ylim(min(all_values) * .985, max(all_values) * 1.035)
    axis.set_xlim(0, 25500)
    axis.set_yticks([1.1, 1.2, 1.3, 1.5, 1.8, 2.2] if args.objective else [1.0, 1.1, 1.2, 1.4, 1.6, 1.8])
    axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
    axis.yaxis.set_minor_locator(NullLocator())
    axis.set_xticks([0, 5000, 10000, 15000, 20000, 25000])
    axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value / 1000:g}k" if value else "0"))
    axis.set_xlabel("Optimizer updates", labelpad=10)
    axis.set_ylabel("Weighted denoising validation loss (log scale)" if args.objective else "Unweighted masked-token cross-entropy (log scale)", labelpad=12)
    axis.grid(True, color="#D8DEE5", linewidth=.8, alpha=.75)
    axis.set_axisbelow(True)

    inset = axis.inset_axes([.54, .42, .42, .52])
    inset.set_facecolor("#FAFBFD")
    late = []
    inset_ranks = [rank for rank in data if data[rank][-1][0] >= 18000] if args.objective else [1024, 2048]
    for rank in inset_ranks:
        points = [(step, value) for step, value in data[rank] if step >= 18000]
        steps, values = zip(*points)
        late.extend(values)
        inset.plot(steps, values, **STYLES[rank], linewidth=1.9, markersize=4.5,
                   markevery=(0, 5), markerfacecolor="white", markeredgewidth=1.2)
        inset.plot(steps[-1], values[-1], marker=STYLES[rank]["marker"],
                   color=STYLES[rank]["color"], markersize=5, linestyle="none")
        if not axes_only:
            inset.annotate(f"{values[-1]:.4f}", (steps[-1], values[-1]), xytext=(-8, 12),
                           textcoords="offset points", ha="right", color=STYLES[rank]["color"],
                           fontsize=10.5, fontweight="bold",
                           bbox=dict(facecolor="white", edgecolor="none", alpha=.8, pad=1))
    padding = max(.0007, (max(late) - min(late)) * .18)
    inset.set_ylim(min(late) - padding, max(late) + padding)
    inset.set_xlim(18000, 25500)
    inset.set_xticks([18000, 20000, 22500, 25000])
    inset.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value / 1000:g}k"))
    inset.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.3f}" if args.objective else f"{value:.4f}"))
    inset.tick_params(labelsize=9.5)
    inset.set_ylabel("Loss (linear scale)", fontsize=9.5, labelpad=7)
    if not axes_only:
        inset.set_title("Late-training zoom · available curves" if args.objective else "Ranks 1,024 and 2,048 · late-training zoom", fontsize=10.5, pad=10)
    inset.grid(True, color="#D8DEE5", linewidth=.6, alpha=.8)
    for spine in inset.spines.values():
        spine.set_visible(True)
        spine.set_color("#BAC4D0")

    if not axes_only:
        figure.text(.085, .955, "Validation loss of the training objective" if args.objective else "Validation loss by LoRA rank", fontsize=19, fontweight="bold")
        subtitle = "0.9 × answer loss + 0.1 × padding loss · lower is better · no smoothing" if args.objective else "Common logged metric · lower is better · raw values, no smoothing"
        figure.text(.085, .919, subtitle, color="#505E6F", fontsize=11.5)
        figure.legend(handles, labels, loc="upper left", bbox_to_anchor=(.077, .9), ncol=4,
                      frameon=False, handlelength=3.1, columnspacing=1.8, fontsize=11.5)
        last_step = data[1024 if args.objective else 2048][-1][0]
        progress_rank = "Rank 1,024" if args.objective else "Rank 2,048"
        progress_note = "All curves extend through 25,000 updates." if last_step == 25000 else f"{progress_rank}: snapshot through {last_step:,} updates; other curves reach 25,000."
        note = "Same 200 validation examples and matched recipe; answer/padding losses are separately normalized and noise-corrected." if args.objective else "Same 200 validation examples. Rank 1,024 is a historical reference; its training-objective settings may differ."
        figure.text(.085, .073, note,
                    color="#505E6F", fontsize=10.2)
        figure.text(.085, .045, progress_note, color="#505E6F", fontsize=10.2)

    stem = output / ("rank_validation_training_objective" if args.objective else "rank_validation_common_ce")
    for suffix in ("png", "pdf", "svg"):
        figure.savefig(stem.with_suffix(f".{suffix}"), dpi=200, facecolor="white")
    plt.close(figure)
    with stem.with_suffix(".csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("rank", "update", "metric", "loss"))
        writer.writeheader()
        writer.writerows(csv_rows)
    manifest = {
        "metric": metric, "sources": sources,
        "objective_weights": {"answer": .9, "padding": .1} if args.objective else None,
        "validation_signature": list(next(iter(signatures))),
        "main_axis": "logarithmic, full observed range", "inset_axis": f"linear, >=18000 updates, ranks {inset_ranks}",
        "smoothing": False,
        "presentation": "Only axis labels and tick numbers; rank key in manuscript caption" if axes_only else "Annotated historical comparison",
        "limitation": ("One parent and seed; validation loss alone does not establish downstream quality. Historical 1024 is excluded."
                       if all(source["last_update"] == 25000 for source in sources.values())
                       else "Fresh rank-1024 curve is partial until 25k updates; historical 1024 is not included.")
                      if args.objective else "The historical rank-1024 run has incompletely documented training loss weighting; this is not a fully controlled four-rank experiment.",
    }
    stem.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"figure": str(stem.with_suffix('.png')), "validation_points": len(csv_rows),
                      "last_updates": {rank: source["last_update"] for rank, source in sources.items()}}, indent=2))


if __name__ == "__main__":
    main()
