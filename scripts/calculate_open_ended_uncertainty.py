#!/usr/bin/env python3
"""Bootstrap uncertainty for the paper's open-ended generation results."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
from huggingface_hub import snapshot_download
from transformers import AutoTokenizer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from diffusion_lm.metrics import distinct_n


DEFAULT_DRIVE_ROOT = (
    Path.home()
    / "Library/CloudStorage/GoogleDrive-ruurd.kuiper@gmail.com/My Drive/lad-generic-results"
)
DEFAULT_OUTPUT = ROOT / "iclr2027_submission/source_results/open_ended_uncertainty.json"
RUNS = {
    "table": "20260918T135058.643507Z--colab-validation",
    "ministral_table": "20260921T131916.314780Z--colab-validation",
    "progression_32": "20260923T134029.046940Z--colab-validation",
    "progression_64": "20260923T190517.263478Z--colab-validation",
    "progression_128": "20260923T201036.622289Z--colab-validation",
    "llada_32": "20260918T112818.173051Z--colab-validation",
    "llada_64": "20260918T135058.643507Z--colab-validation",
    "llada_128": "20260918T145248.574217Z--colab-validation",
}

TABLE_MODELS = {
    "Gemma 2 9B, 25k|diffusion": ("table", "gemma-2-9b-mask-best", "diffusion"),
    "Gemma 2 9B, 25k|autoregressive": ("table", "google-gemma-2-9b-it", "autoregressive"),
    "Llama 3.1 8B, 25k|diffusion": ("table", "llama-3.1-8b-mask-best", "diffusion"),
    "Llama 3.1 8B, 25k|autoregressive": ("table", "meta-llama-llama-3.1-8b-instruct", "autoregressive"),
    "Llama 3.1 8B, 50k|diffusion": ("table", "llama-3.1-8b-mask-continued-best", "diffusion"),
    "Llama 3.1 8B, 50k|autoregressive": ("table", "meta-llama-llama-3.1-8b-instruct", "autoregressive"),
    "Qwen2.5 7B, 25k|diffusion": ("table", "qwen-2.5-7b-mask-best", "diffusion"),
    "Qwen2.5 7B, 25k|autoregressive": ("table", "qwen-qwen2.5-7b-instruct", "autoregressive"),
    "Ministral 8B, 25k|diffusion": ("ministral_table", "ministral-8b-mask-best", "diffusion"),
    "Ministral 8B, 25k|autoregressive": ("ministral_table", "mistralai-ministral-8b-instruct-2410", "autoregressive"),
    "LLaDA 8B Instruct|diffusion": ("table", "llada-gsai-ml-llada-8b-instruct", "diffusion"),
}

SELECTED_STEPS = {
    32: (1_000, 5_000, 10_000, 15_000, 20_000, 25_000, 30_000, 35_000, 40_000, 45_000, 50_000),
    64: (1_000, 5_000, 10_000, 15_000, 20_000, 25_000, 30_000, 35_000, 40_000, 45_000, 50_000),
    128: (1_000, 5_000, 10_000, 15_000, 20_000, 25_000, 30_000, 35_000, 40_000, 45_000, 50_000),
}


def _global_step(folder: str) -> int | None:
    try:
        local = int(folder.rsplit("checkpoint-", 1)[1])
    except (IndexError, ValueError):
        return None
    return local + 25_000 if folder.startswith("llama-3.1-8b-mask-continued-") else local


def _paths(root: Path, run_key: str, model_folder: str, method: str) -> tuple[Path, Path]:
    base = root / "validation/benchmark_runs" / RUNS[run_key] / "models" / model_folder / "open_ended" / method
    return base / "results.jsonl", base / "summary.json"


def _read_records(path: Path) -> list[dict[str, Any]]:
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not records:
        raise ValueError(f"No records in {path}")
    return records


def _bootstrap(
    records: list[dict[str, Any]],
    phi_tokenizer: Any,
    metric_tokenizer: Any | None,
    *,
    samples: int,
    seed: int,
) -> dict[str, Any]:
    perplexities = np.asarray([float(row["perplexity"]) for row in records], dtype=np.float64)
    token_counts = np.asarray([
        max(1, len(phi_tokenizer.encode(str(row["prediction"]), add_special_tokens=True)) - 1)
        for row in records
    ], dtype=np.float64)
    nlls = np.log(perplexities) * token_counts

    distinct: dict[int, np.ndarray] = {}
    for n in (1, 2, 3):
        field = f"distinct_{n}"
        values = []
        for row in records:
            value = row.get(field)
            if value is None:
                if metric_tokenizer is None:
                    raise ValueError(f"{field} is missing and no metric tokenizer was supplied")
                value = distinct_n(str(row["prediction"]), metric_tokenizer, n)
            values.append(float(value))
        distinct[n] = np.asarray(values, dtype=np.float64)

    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(records), size=(samples, len(records)))
    sampled_tokens = token_counts[indices].sum(axis=1)
    sampled_ppl = np.exp(nlls[indices].sum(axis=1) / sampled_tokens)

    def interval(values: np.ndarray) -> list[float]:
        return [float(value) for value in np.quantile(values, (0.025, 0.975))]

    point_ppl = float(math.exp(float(nlls.sum() / token_counts.sum())))
    result = {
        "n": len(records),
        "perplexity": {"value": point_ppl, "ci95": interval(sampled_ppl)},
    }
    for n, values in distinct.items():
        result[f"distinct_{n}"] = {
            "value": float(values.mean()),
            "ci95": interval(values[indices].mean(axis=1)),
        }
    return result


def _check_summary(point: dict[str, Any], summary_path: Path) -> None:
    summary = json.loads(summary_path.read_text())
    expected = float(summary["perplexity"])
    actual = float(point["perplexity"]["value"])
    if not math.isclose(actual, expected, rel_tol=2e-5, abs_tol=2e-5):
        raise ValueError(f"Reconstructed perplexity {actual} does not match {expected} in {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drive-root", type=Path, default=DEFAULT_DRIVE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--bootstrap-samples", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=2027)
    args = parser.parse_args()

    phi_path = snapshot_download("microsoft/phi-4", local_files_only=True)
    llama_path = args.drive_root / "outputs/llama-3.1-8b-mask/best"
    if not (llama_path / "tokenizer.json").is_file():
        raise FileNotFoundError(f"Llama tokenizer not found in {llama_path}")
    phi_tokenizer = AutoTokenizer.from_pretrained(phi_path, local_files_only=True)
    llama_tokenizer = AutoTokenizer.from_pretrained(
        llama_path, local_files_only=True
    )

    table = {}
    for offset, (label, (run_key, folder, method)) in enumerate(TABLE_MODELS.items()):
        results_path, summary_path = _paths(args.drive_root, run_key, folder, method)
        point = _bootstrap(
            _read_records(results_path),
            phi_tokenizer,
            None,
            samples=args.bootstrap_samples,
            seed=args.seed + offset,
        )
        _check_summary(point, summary_path)
        table[label] = point

    progression: dict[str, Any] = {}
    for nfe in (32, 64, 128):
        run_key = f"progression_{nfe}"
        models_root = args.drive_root / "validation/benchmark_runs" / RUNS[run_key] / "models"
        points = {}
        for folder_path in sorted(models_root.glob("llama-3.1-8b-mask*-checkpoint-*")):
            step = _global_step(folder_path.name)
            if step not in SELECTED_STEPS[nfe]:
                continue
            results_path = folder_path / "open_ended/diffusion/results.jsonl"
            summary_path = folder_path / "open_ended/diffusion/summary.json"
            if not results_path.is_file():
                continue
            point = _bootstrap(
                _read_records(results_path),
                phi_tokenizer,
                llama_tokenizer,
                samples=args.bootstrap_samples,
                seed=args.seed + nfe + step,
            )
            _check_summary(point, summary_path)
            points[str(step)] = point
        missing = set(SELECTED_STEPS[nfe]) - {int(step) for step in points}
        if missing:
            raise ValueError(f"Missing {nfe}-NFE progression steps: {sorted(missing)}")

        baseline_root = args.drive_root / "validation/benchmark_runs" / RUNS[f"llada_{nfe}"] / "models"
        baseline_folder = next(baseline_root.glob("llada-*/open_ended/diffusion"))
        baseline = _bootstrap(
            _read_records(baseline_folder / "results.jsonl"),
            phi_tokenizer,
            llama_tokenizer,
            samples=args.bootstrap_samples,
            seed=args.seed + 10_000 + nfe,
        )
        _check_summary(baseline, baseline_folder / "summary.json")
        progression[str(nfe)] = {"points": points, "llada": baseline}

    output = {
        "method": "prompt-level percentile bootstrap",
        "confidence_level": 0.95,
        "bootstrap_samples": args.bootstrap_samples,
        "seed": args.seed,
        "perplexity_aggregation": "exp(sum prompt NLL / sum prompt reference-token count)",
        "distinct_aggregation": "arithmetic mean across prompts",
        "runs": RUNS,
        "table_4": table,
        "figure_2": progression,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
