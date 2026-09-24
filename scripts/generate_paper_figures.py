#!/usr/bin/env python3
"""Generate paper figures directly from the maintained results workbook.

The script intentionally reads model and task labels rather than relying only
on column numbers.  This makes accidental column moves in Excel fail loudly or
resolve correctly instead of silently plotting the wrong model.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, FuncFormatter
import numpy as np
from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKBOOK = ROOT / "results" / "Results_training-20260924.xlsx"
DEFAULT_OUTPUT_DIR = ROOT / "iclr2027_submission" / "figures"

TASK_LABELS = {
    "arc_c": "ARC-C",
    "gpqa": "GPQA",
    "gsm8k": "GSM8K",
    "hellaswag": "HellaSwag",
    "humaneval": "HumanEval",
    "math": "MATH-500",
    "mbpp": "MBPP",
    "mmlu": "MMLU",
    "mmlu_pro": "MMLU-Pro",
}
TASK_ORDER = list(TASK_LABELS)

RADAR_GROUPS = {
    "llama_comparison": {
        "LLaDA (DLM)": "LLaDA-8B-Instruct (own validation)",
        "BYOD-Llama (DLM)": "llama-3.1-8b-mask",
        "Llama (AR)": "llama-3.1-8b-autoregressive",
    },
    "byod_families": {
        "BYOD-Gemma": "gemma-2-9b-mask",
        "BYOD-Llama": "llama-3.1-8b-mask",
        "BYOD-Qwen": "qwen-2.5-7b-mask",
        "BYOD-Ministral": "ministral-mask",
    },
}

COLORS = {
    "LLaDA (DLM)": "#009E73",
    "BYOD-Llama (DLM)": "#0072B2",
    "Llama (AR)": "#D55E00",
    "BYOD-Gemma": "#E69F00",
    "BYOD-Llama": "#0072B2",
    "BYOD-Qwen": "#009E73",
    "BYOD-Ministral": "#CC79A7",
    32: "#0072B2",
    64: "#D55E00",
    128: "#009E73",
}

OPEN_GENERATION_MODELS = {
    "BYOD-Gemma": ("gemma-2-9b-mask", "gemma-2-9b-autoregressive"),
    "BYOD-Qwen": ("qwen-2.5-7b-mask", "qwen-2.5-7b-autoregressive"),
    "BYOD-Ministral": ("ministral-mask", "ministral-autoregressive"),
    "BYOD-Llama-25k": ("llama-3.1-8b-mask", "llama-3.1-8b-autoregressive"),
    "BYOD-Llama-50k": ("llama-3.1-8b-mask-long", "llama-3.1-8b-autoregressive"),
    "LLaDA 8B Instruct": ("LLaDA-8B-Instruct (own validation)", None),
}

OPEN_GENERATION_STYLES = {
    "BYOD-Gemma": ("#E69F00", "-", "o"),
    "BYOD-Qwen": ("#009E73", "-", "s"),
    "BYOD-Ministral": ("#CC79A7", "-", "^"),
    "BYOD-Llama-25k": ("#0072B2", "-", "D"),
    "BYOD-Llama-50k": ("#004C7F", "--", "D"),
    "LLaDA 8B Instruct": ("#666666", "-", "P"),
}


def _numeric(value: Any, location: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError(f"Expected a finite number at {location}, found {value!r}")
    return float(value)


def _find_in_row(sheet: Any, row: int, value: str) -> int:
    matches = [cell.column for cell in sheet[row] if cell.value == value]
    if len(matches) != 1:
        raise ValueError(f"Expected one {value!r} in {sheet.title} row {row}, found {len(matches)}")
    return matches[0]


def load_radar_data(sheet: Any) -> dict[str, Any]:
    """Read the nine accuracy tasks and named comparison columns."""
    model_row = next(
        (row for row in range(1, sheet.max_row + 1) if sheet.cell(row, 2).value == "model"),
        None,
    )
    if model_row is None:
        raise ValueError(f"Could not find the model header in {sheet.title}")
    model_columns = {
        str(sheet.cell(model_row, column).value): column
        for column in range(1, sheet.max_column + 1)
        if sheet.cell(model_row, column).value is not None
    }
    task_rows = {
        str(sheet.cell(row, 2).value): row
        for row in range(model_row + 1, sheet.max_row + 1)
        if sheet.cell(row, 2).value in TASK_ORDER
    }
    missing_tasks = set(TASK_ORDER) - set(task_rows)
    if missing_tasks:
        raise ValueError(f"Missing benchmark rows: {sorted(missing_tasks)}")

    groups: dict[str, dict[str, list[float]]] = {}
    for group_name, series in RADAR_GROUPS.items():
        groups[group_name] = {}
        for display_name, workbook_name in series.items():
            if workbook_name not in model_columns:
                raise ValueError(f"Workbook has no model column {workbook_name!r}")
            column = model_columns[workbook_name]
            groups[group_name][display_name] = [
                _numeric(sheet.cell(task_rows[task], column).value, f"{sheet.title}!{sheet.cell(task_rows[task], column).coordinate}")
                for task in TASK_ORDER
            ]
    return {
        "tasks": TASK_ORDER,
        "task_labels": [TASK_LABELS[task] for task in TASK_ORDER],
        "groups": groups,
    }


def load_open_generation_data(sheet: Any) -> dict[str, Any]:
    """Read Table 4's PPL and Distinct-1 values by model name and NFE."""
    model_row = next(
        (row for row in range(1, sheet.max_row + 1) if sheet.cell(row, 2).value == "model"),
        None,
    )
    if model_row is None:
        raise ValueError(f"Could not find the model header in {sheet.title}")
    model_columns = {
        str(sheet.cell(model_row, column).value): column
        for column in range(1, sheet.max_column + 1)
        if sheet.cell(model_row, column).value is not None
    }

    ppl_start = next(
        (
            row
            for row in range(model_row + 1, sheet.max_row + 1)
            if str(sheet.cell(row, 1).value or "").startswith("Perplexity")
        ),
        None,
    )
    d1_header = next(
        (
            row
            for row in range(model_row + 1, sheet.max_row + 1)
            if str(sheet.cell(row, 2).value or "").startswith("Distinct-1")
        ),
        None,
    )
    if ppl_start is None or d1_header is None:
        raise ValueError(f"Could not find open-generation metric blocks in {sheet.title}")

    pattern = re.compile(r"128 tokens,\s*(32|64|128) iterations", re.IGNORECASE)

    def metric_rows(start: int) -> dict[int, int]:
        rows: dict[int, int] = {}
        for row in range(start, start + 3):
            match = pattern.search(str(sheet.cell(row, 2).value or ""))
            if match:
                rows[int(match.group(1))] = row
        if set(rows) != {32, 64, 128}:
            raise ValueError(f"Expected 32/64/128-NFE rows at {sheet.title}!B{start}:B{start + 2}")
        return rows

    ppl_rows = metric_rows(ppl_start)
    d1_rows = metric_rows(d1_header + 1)
    series: dict[str, Any] = {}
    for display_name, (diffusion_name, ar_name) in OPEN_GENERATION_MODELS.items():
        if diffusion_name not in model_columns:
            raise ValueError(f"Workbook has no model column {diffusion_name!r}")
        diffusion_column = model_columns[diffusion_name]
        points = {
            nfe: {
                "perplexity": _numeric(
                    sheet.cell(ppl_rows[nfe], diffusion_column).value,
                    f"{sheet.title}!{sheet.cell(ppl_rows[nfe], diffusion_column).coordinate}",
                ),
                "distinct_1": _numeric(
                    sheet.cell(d1_rows[nfe], diffusion_column).value,
                    f"{sheet.title}!{sheet.cell(d1_rows[nfe], diffusion_column).coordinate}",
                ),
            }
            for nfe in (32, 64, 128)
        }
        ar = None
        if ar_name is not None:
            if ar_name not in model_columns:
                raise ValueError(f"Workbook has no AR model column {ar_name!r}")
            ar_column = model_columns[ar_name]
            ppl_values = [
                _numeric(sheet.cell(ppl_rows[nfe], ar_column).value, f"{sheet.title}!{sheet.cell(ppl_rows[nfe], ar_column).coordinate}")
                for nfe in (32, 64, 128)
            ]
            d1_values = [
                _numeric(sheet.cell(d1_rows[nfe], ar_column).value, f"{sheet.title}!{sheet.cell(d1_rows[nfe], ar_column).coordinate}")
                for nfe in (32, 64, 128)
            ]
            if not np.allclose(ppl_values, ppl_values[0]) or not np.allclose(d1_values, d1_values[0]):
                raise ValueError(f"AR reference varies across NFE rows for {ar_name!r}")
            ar = {"perplexity": ppl_values[0], "distinct_1": d1_values[0]}
        series[display_name] = {"diffusion": points, "ar": ar}
    return {"nfe": [32, 64, 128], "series": series}


def load_progression_data(
    sheet: Any,
    header_row: int = 42,
    *,
    value_name: str = "perplexity",
    required: bool = True,
) -> dict[str, Any] | None:
    """Read a manually maintained 32/64/128-NFE checkpoint block."""
    if sheet.cell(header_row, 3).value != "Training iterations":
        if not required:
            return None
        raise ValueError(
            f"Expected 'Training iterations' at {sheet.title}!C{header_row}; "
            f"found {sheet.cell(header_row, 3).value!r}"
        )
    step_columns = {
        cell.column: int(cell.value)
        for cell in sheet[header_row]
        if isinstance(cell.value, (int, float)) and 1_000 <= int(cell.value) <= 50_000
    }
    if not step_columns:
        raise ValueError(f"No checkpoint steps found in {sheet.title} row {header_row}")

    series: dict[int, dict[str, Any]] = {}
    pattern = re.compile(r"\((32|64|128)\s+it\.\)", re.IGNORECASE)
    # The first row below the header is a free-form block subtitle; the next
    # three rows are the fixed 32/64/128-NFE series.
    for row in range(header_row + 2, min(header_row + 4, sheet.max_row) + 1):
        label = sheet.cell(row, 3).value
        match = pattern.search(str(label)) if label is not None else None
        if not match:
            continue
        nfe = int(match.group(1))
        points = []
        for column, step in step_columns.items():
            value = sheet.cell(row, column).value
            if value is not None:
                points.append({"step": step, value_name: _numeric(value, f"{sheet.title}!{sheet.cell(row, column).coordinate}")})

        baseline = None
        baseline_label = None
        for column in range(max(step_columns) + 1, sheet.max_column):
            candidate_label = sheet.cell(row, column).value
            candidate_value = sheet.cell(row, column + 1).value
            if isinstance(candidate_label, str) and "llada" in candidate_label.lower() and candidate_value is not None:
                baseline_label = candidate_label
                baseline = _numeric(candidate_value, f"{sheet.title}!{sheet.cell(row, column + 1).coordinate}")
                break
        if baseline is None:
            raise ValueError(f"No LLaDA baseline found for {nfe} NFE in row {row}")
        ar_label = None
        ar_value = None
        for column in range(max(step_columns) + 1, sheet.max_column):
            candidate_label = sheet.cell(row, column).value
            candidate_value = sheet.cell(row, column + 1).value
            if isinstance(candidate_label, str) and candidate_label.endswith(" AR") and candidate_value is not None:
                ar_label = candidate_label
                ar_value = _numeric(candidate_value, f"{sheet.title}!{sheet.cell(row, column + 1).coordinate}")
                break
        if ar_value is None:
            raise ValueError(f"No Llama AR reference found for {nfe} NFE in row {row}")
        series[nfe] = {
            "label": str(label),
            "points": points,
            "llada_label": baseline_label,
            "llada": baseline,
            "ar_label": ar_label,
            "ar": ar_value,
        }

    if set(series) != {32, 64, 128}:
        raise ValueError(f"Expected progression rows for 32/64/128 NFE, found {sorted(series)}")
    return {"all_steps": sorted(step_columns.values()), "series": series}


def load_validation_loss_data(sheet: Any) -> dict[str, Any]:
    """Read the uninterrupted long-run validation-loss snapshot."""
    expected_headers = {
        "Training update": "step",
        "Weighted validation loss": "weighted_loss",
        "Unweighted masked-token CE": "unweighted_masked_token_ce",
    }
    columns = {
        str(cell.value): cell.column
        for cell in sheet[1]
        if cell.value is not None
    }
    missing = set(expected_headers) - set(columns)
    if missing:
        raise ValueError(f"Missing validation-loss columns in {sheet.title}: {sorted(missing)}")

    points = []
    for row in range(2, sheet.max_row + 1):
        step_value = sheet.cell(row, columns["Training update"]).value
        if step_value is None:
            continue
        point = {
            output_name: _numeric(
                sheet.cell(row, columns[header]).value,
                f"{sheet.title}!{sheet.cell(row, columns[header]).coordinate}",
            )
            for header, output_name in expected_headers.items()
        }
        point["step"] = int(point["step"])
        points.append(point)
    if not points:
        raise ValueError(f"No validation-loss rows found in {sheet.title}")
    points.sort(key=lambda point: point["step"])
    return {"source_sheet": sheet.title, "points": points}


def _configure_radar(ax: Any, labels: list[str], title: str) -> np.ndarray:
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False)
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels, fontsize=8)
    ax.tick_params(axis="x", pad=8)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], fontsize=7, color="#555555")
    ax.set_rlabel_position(8)
    ax.grid(color="#C8C8C8", linewidth=0.6)
    ax.spines["polar"].set_color("#999999")
    ax.set_title(title, fontsize=10, fontweight="bold", pad=18)
    return angles


def _draw_radar(ax: Any, labels: list[str], series: dict[str, list[float]], title: str) -> None:
    angles = _configure_radar(ax, labels, title)
    closed_angles = np.r_[angles, angles[0]]
    for name, values in series.items():
        closed_values = np.r_[values, values[0]]
        color = COLORS[name]
        ax.plot(closed_angles, closed_values, color=color, linewidth=1.8, marker="o", markersize=3.2, label=name)
        ax.fill(closed_angles, closed_values, color=color, alpha=0.055)


def _save(fig: Any, stem: Path) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(stem.with_suffix(".png"), dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_radar_panels(data: dict[str, Any], output_dir: Path) -> None:
    labels = data["task_labels"]
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 5.2), subplot_kw={"projection": "polar"})
    _draw_radar(axes[0], labels, data["groups"]["llama_comparison"], "(a) Matched Llama and LLaDA comparison")
    _draw_radar(axes[1], labels, data["groups"]["byod_families"], "(b) BYOD backbone comparison")
    for ax in axes:
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), frameon=False, fontsize=8, ncol=2)
    fig.subplots_adjust(wspace=0.35, bottom=0.22, top=0.88)
    _save(fig, output_dir / "benchmark_radar_panels")

    for filename, group_name, title in (
        ("benchmark_radar_llama", "llama_comparison", "Matched Llama and LLaDA comparison"),
        ("benchmark_radar_byod_families", "byod_families", "BYOD backbone comparison"),
    ):
        fig, ax = plt.subplots(figsize=(6.2, 5.5), subplot_kw={"projection": "polar"})
        _draw_radar(ax, labels, data["groups"][group_name], title)
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), frameon=False, fontsize=8, ncol=2)
        fig.subplots_adjust(bottom=0.2, top=0.88)
        _save(fig, output_dir / filename)


def plot_open_generation_budget(data: dict[str, Any], output_dir: Path) -> None:
    """Plot Table 4 as inference-budget curves with separate AR reference markers."""
    nfe = data["nfe"]
    x = np.arange(len(nfe), dtype=float)
    ar_x = 3.35
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.5))
    metrics = (
        ("perplexity", "Perplexity (↓)", "(a) Perplexity", True),
        ("distinct_1", "Distinct-1 (↑)", "(b) Distinct-1", False),
    )
    for ax, (metric, ylabel, title, log_scale) in zip(axes, metrics):
        observed = []
        for name, item in data["series"].items():
            color, linestyle, marker = OPEN_GENERATION_STYLES[name]
            scale = 100.0 if metric == "distinct_1" else 1.0
            values = [scale * item["diffusion"][step][metric] for step in nfe]
            observed.extend(values)
            ax.plot(
                x,
                values,
                color=color,
                linestyle=linestyle,
                marker=marker,
                linewidth=2.0,
                markersize=5.0,
                label=f"{name} (dashed)" if name == "BYOD-Llama-50k" else name,
            )
            if item["ar"] is not None:
                ar_value = scale * item["ar"][metric]
                observed.append(ar_value)
                # Llama-25k and Llama-50k share one parent; avoid drawing its
                # identical reference marker twice.
                if name != "BYOD-Llama-50k":
                    ax.scatter(
                        [ar_x],
                        [ar_value],
                        color=color,
                        marker="X",
                        s=55,
                        edgecolor="white",
                        linewidth=0.6,
                        zorder=5,
                    )
        ax.axvline(2.68, color="#B5B5B5", linewidth=0.8, linestyle=(0, (2, 3)))
        ax.set_xticks([*x, ar_x], ["32", "64", "128", "AR parent"])
        ax.set_xlim(-0.18, 3.62)
        ax.set_xlabel("Denoising NFE (diffusion models)")
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=10, fontweight="bold")
        ax.grid(axis="y", color="#D7D7D7", linewidth=0.6)
        ax.spines[["top", "right"]].set_visible(False)
        if log_scale:
            ax.set_yscale("log")
            ax.set_ylim(min(observed) * 0.84, max(observed) * 1.16)
            ticks = [tick for tick in (2, 3, 4, 5, 6, 8, 10, 15, 20, 25) if ax.get_ylim()[0] <= tick <= ax.get_ylim()[1]]
            ax.yaxis.set_major_locator(FixedLocator(ticks))
            ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _position: f"{value:g}"))
        else:
            ax.set_ylim(max(0.0, min(observed) - 4.0), min(100.0, max(observed) + 4.0))

    handles, labels = axes[0].get_legend_handles_labels()
    ar_handle = Line2D(
        [0], [0], marker="X", color="none", markerfacecolor="#555555",
        markeredgecolor="white", markersize=7, label="Paired AR parent",
    )
    fig.legend(
        [*handles, ar_handle],
        [*labels, "Paired AR parent"],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.005),
        frameon=False,
        ncol=4,
        fontsize=8,
    )
    fig.subplots_adjust(left=0.075, right=0.985, top=0.91, bottom=0.24, wspace=0.27)
    _save(fig, output_dir / "open_generation_budget")


def _plot_progression_panel(
    ax: Any,
    data: dict[str, Any],
    *,
    value_name: str,
    ylabel: str,
    title: str,
) -> None:
    scale = 100.0 if value_name.startswith("distinct_") else 1.0
    for nfe in (32, 64, 128):
        item = data["series"][nfe]
        steps = [point["step"] for point in item["points"]]
        values = [scale * point[value_name] for point in item["points"]]
        color = COLORS[nfe]
        ax.plot(steps, values, color=color, marker="o", linewidth=2, markersize=4.5, label=f"{nfe} NFE")
        baseline = scale * item["llada"]
        ax.axhline(baseline, color=color, linestyle=(0, (4, 3)), linewidth=1.4, alpha=0.9)

    ar_reference = scale * data["series"][32]["ar"]
    ax.axhline(ar_reference, color="#555555", linestyle=(0, (1, 2)), linewidth=1.7, alpha=0.95)

    ax.set_xlabel("Training iterations")
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.set_xticks(data["all_steps"])
    ax.set_xticklabels([f"{step // 1000}k" for step in data["all_steps"]], fontsize=8)
    ax.set_xlim(min(data["all_steps"]) - 1_500, max(data["all_steps"]) + 1_500)
    if value_name == "perplexity":
        observed = [
            point[value_name]
            for item in data["series"].values()
            for point in item["points"]
        ]
        observed.extend(item["llada"] for item in data["series"].values())
        observed.append(data["series"][32]["ar"])
        ax.set_yscale("log")
        ax.set_ylim(min(observed) * 0.85, 35.0)
        ticks = [
            tick
            for tick in (3, 4, 5, 6, 8, 10, 15, 20, 25, 30, 35)
            if ax.get_ylim()[0] <= tick <= ax.get_ylim()[1]
        ]
        ax.yaxis.set_major_locator(FixedLocator(ticks))
        ax.yaxis.set_major_formatter(
            FuncFormatter(lambda value, _position: f"{value:g}")
        )
    else:
        ax.set_ylim(bottom=0)
    ax.grid(axis="y", color="#D0D0D0", linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    nfe_legend = ax.legend(frameon=False, loc="upper right", fontsize=8)
    ax.add_artist(nfe_legend)
    style_handles = [
        Line2D([0], [0], color="#333333", marker="o", linewidth=2, label="BYOD-Llama"),
        Line2D([0], [0], color="#333333", linestyle=(0, (4, 3)), linewidth=1.4, label="LLaDA"),
        Line2D([0], [0], color="#555555", linestyle=(0, (1, 2)), linewidth=1.7, label="Llama"),
    ]
    ax.legend(handles=style_handles, frameon=False, loc="upper center", fontsize=8)

    if value_name == "distinct_1":
        observed = [
            scale * point[value_name]
            for item in data["series"].values()
            for point in item["points"]
        ]
        observed.extend(scale * item["llada"] for item in data["series"].values())
        observed.append(ar_reference)
        ax.set_ylim(max(0.0, min(observed) - 10.0), min(100.0, max(observed) + 10.0))


def _plot_pending_distinct_panel(ax: Any, all_steps: list[int]) -> None:
    ax.set_title("(b) Distinct-1", fontsize=10, fontweight="bold")
    ax.set_xlabel("Training iterations")
    ax.set_ylabel("Distinct-1 (↑)")
    ax.set_xticks(all_steps)
    ax.set_xticklabels([f"{step // 1000}k" for step in all_steps], fontsize=8)
    ax.set_xlim(min(all_steps) - 1_500, max(all_steps) + 1_500)
    ax.set_ylim(0, 1)
    ax.grid(axis="y", color="#D0D0D0", linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(
        0.5,
        0.52,
        "Checkpoint Distinct-1 results pending",
        ha="center",
        va="center",
        transform=ax.transAxes,
        color="#555555",
        fontsize=10,
    )


def _plot_validation_loss_panel(ax: Any, data: dict[str, Any], *, title: str) -> None:
    steps = [point["step"] for point in data["points"]]
    losses = [point["weighted_loss"] for point in data["points"]]
    ax.plot(steps, losses, color="#7B3294", linewidth=1.8, alpha=0.9)
    ax.scatter(steps, losses, color="#7B3294", s=10, zorder=3)
    ax.set_xlabel("Training iterations")
    ax.set_ylabel("Validation loss (↓)")
    ax.set_title(title, fontsize=10, fontweight="bold")
    tick_stop = int(math.ceil(max(steps) / 10_000.0) * 10_000)
    ticks = list(range(0, tick_stop + 1, 10_000))
    ax.set_xticks(ticks)
    ax.set_xticklabels(["0" if step == 0 else f"{step // 1000}k" for step in ticks], fontsize=8)
    ax.set_xlim(0, max(steps) + 1_500)
    loss_range = max(losses) - min(losses)
    ax.set_ylim(
        bottom=max(0.0, min(losses) - 0.1),
        top=max(losses) + max(0.02, 0.05 * loss_range),
    )
    ax.grid(axis="y", color="#D0D0D0", linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
def plot_training_progression(
    perplexity_data: dict[str, Any],
    distinct_data: dict[str, Any] | None,
    validation_loss_data: dict[str, Any],
    output_dir: Path,
) -> None:
    # Retain the original single-panel artifact for slides and backwards compatibility.
    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    _plot_progression_panel(
        ax,
        perplexity_data,
        value_name="perplexity",
        ylabel="Perplexity (↓)",
        title="Perplexity",
    )
    fig.tight_layout()
    _save(fig, output_dir / "llama_training_perplexity")

    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    _plot_validation_loss_panel(ax, validation_loss_data, title="Validation loss")
    fig.tight_layout()
    _save(fig, output_dir / "llama_training_validation_loss")

    fig = plt.figure(figsize=(11.2, 8.0))
    grid = fig.add_gridspec(2, 4, height_ratios=(1.0, 1.0), hspace=0.38, wspace=0.28)
    axes = (fig.add_subplot(grid[0, 0:2]), fig.add_subplot(grid[0, 2:4]))
    validation_ax = fig.add_subplot(grid[1, 1:3])
    _plot_progression_panel(
        axes[0],
        perplexity_data,
        value_name="perplexity",
        ylabel="Perplexity (↓)",
        title="(a) Perplexity",
    )
    if distinct_data is None:
        _plot_pending_distinct_panel(axes[1], perplexity_data["all_steps"])
    else:
        _plot_progression_panel(
            axes[1],
            distinct_data,
            value_name="distinct_1",
            ylabel="Distinct-1 (↑)",
            title="(b) Distinct-1",
        )
    _plot_validation_loss_panel(
        validation_ax,
        validation_loss_data,
        title="(c) Validation loss",
    )
    fig.subplots_adjust(left=0.08, right=0.985, top=0.96, bottom=0.075)
    _save(fig, output_dir / "llama_training_diagnostics")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--progression-header-row", type=int, default=42)
    parser.add_argument(
        "--distinct-progression-header-row",
        type=int,
        default=49,
        help="Optional Distinct-1 checkpoint block; a missing block produces a clearly marked placeholder panel.",
    )
    args = parser.parse_args()

    workbook = args.workbook.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    if not workbook.is_file():
        raise FileNotFoundError(workbook)
    wb = load_workbook(workbook, data_only=True, read_only=True)
    sheet = wb["Primary outcomes"]
    radar = load_radar_data(sheet)
    open_generation = load_open_generation_data(sheet)
    progression = load_progression_data(sheet, args.progression_header_row)
    distinct_progression = load_progression_data(
        sheet,
        args.distinct_progression_header_row,
        value_name="distinct_1",
        required=False,
    )
    validation_loss = load_validation_loss_data(wb["Long validation loss"])
    if distinct_progression is None:
        distinct_progression = {
            "all_steps": progression["all_steps"],
            "series": {
                nfe: {
                    "label": progression["series"][nfe]["label"],
                    "points": [],
                    "llada_label": progression["series"][nfe]["llada_label"],
                    "llada": 0.0,
                    "ar_label": progression["series"][nfe]["ar_label"],
                    "ar": 0.0,
                }
                for nfe in (32, 64, 128)
            },
        }
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.labelsize": 9,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })
    plot_radar_panels(radar, output_dir)
    plot_open_generation_budget(open_generation, output_dir)
    plot_training_progression(progression, distinct_progression, validation_loss, output_dir)

    manifest = {
        "source_workbook": str(workbook),
        "source_sheet": sheet.title,
        "accuracy_cells": "model names from row 5; tasks from rows 7--15",
        "progression_cells": f"rows {args.progression_header_row}--{args.progression_header_row + 4}",
        "distinct_progression_cells": (
            f"rows {args.distinct_progression_header_row}--{args.distinct_progression_header_row + 4}"
            if distinct_progression is not None
            else "pending: add an equivalent Training iterations block beginning at C49"
        ),
        "radar": radar,
        "open_generation_budget": open_generation,
        "training_progression": progression,
        "distinct_1_progression": distinct_progression,
        "validation_loss": validation_loss,
        "notes": [
            "Blank checkpoint cells are omitted; lines connect only recorded values.",
            "Dashed horizontal lines are the LLaDA values stored beside each NFE row.",
            "Both radar panels use 125 examples per task.",
            "No uncertainty ribbons are displayed; horizontal dotted gray lines are the 100-prompt Llama AR reference.",
            "All radar spokes share the same absolute 0--100% scale; per-task min/max normalization is intentionally avoided.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "figure_data.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Generated figures in {output_dir}")


if __name__ == "__main__":
    main()
