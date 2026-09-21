#!/usr/bin/env python3
"""Reproduce the training-compute estimates used in the ICLR manuscript.

The estimator follows C = 6 N D FLOPs and converts FLOPs to accelerator-hours
using a specified dense BF16 peak and model FLOPs utilization (MFU).  It also
computes the MFU implied by papers that report accelerator-hours.

Run:
    python scripts/estimate_paper_compute.py \
        --output iclr2027_submission/source_results/compute_estimates.csv
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


ASSUMED_MFU = 0.40
H100_DENSE_BF16_TFLOPS = 989.0


@dataclass(frozen=True)
class Run:
    system: str
    parameters: int
    tokens: int
    peak_tflops: float
    reported_gpu_hours: float | None = None
    note: str = ""


def training_flops(parameters: int, tokens: int) -> float:
    return 6.0 * parameters * tokens


def predicted_gpu_hours(run: Run, mfu: float = ASSUMED_MFU) -> float:
    return training_flops(run.parameters, run.tokens) / (
        mfu * run.peak_tflops * 1e12 * 3600.0
    )


def implied_mfu(run: Run) -> float | None:
    if run.reported_gpu_hours is None:
        return None
    return training_flops(run.parameters, run.tokens) / (
        run.reported_gpu_hours * run.peak_tflops * 1e12 * 3600.0
    )


# Rows whose GPU-hours are estimated in the main resource table.  All use the
# manuscript's common H100-equivalent peak so that the estimates are comparable.
ESTIMATED_RUNS = (
    Run("DiffuLLaMA 7B", 7_000_000_000, 65_000_000_000, H100_DENSE_BF16_TFLOPS),
    Run("Dream 7B", 7_000_000_000, 580_000_000_000, H100_DENSE_BF16_TFLOPS),
    Run("iLLaDA 8B", 8_000_000_000, 12_000_000_000_000, H100_DENSE_BF16_TFLOPS),
    Run("Efficient-DLM 8B", 8_000_000_000, 500_000_000_000, H100_DENSE_BF16_TFLOPS),
)


# Calibration rows with reported elapsed accelerator-hours.  LLaDA uses the
# H100 dense-BF16 peak as an H800 proxy.  Fast-dLLM uses the A100 SXM dense-BF16
# peak and the exact 2,500 * 256 * 2,048 = 1.31072B token count in its appendix.
CALIBRATION_RUNS = (
    Run(
        "LLaDA 8B",
        8_000_000_000,
        2_300_000_000_000,
        989.0,
        130_000.0,
        "H800; 989 TFLOP/s dense-BF16 H100-class proxy",
    ),
    Run(
        "Fast-dLLM v2 7B",
        7_000_000_000,
        2_500 * 256 * 2_048,
        312.0,
        64.0 * 12.0,
        "64 A100 GPUs for 12 h; 312 TFLOP/s dense-BF16 peak",
    ),
)


def rows() -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for kind, runs in (("table_estimate", ESTIMATED_RUNS), ("calibration", CALIBRATION_RUNS)):
        for run in runs:
            predicted = predicted_gpu_hours(run)
            effective = implied_mfu(run)
            result.append(
                {
                    "kind": kind,
                    "system": run.system,
                    "parameters": str(run.parameters),
                    "tokens": str(run.tokens),
                    "peak_tflops": f"{run.peak_tflops:.0f}",
                    "assumed_mfu": f"{ASSUMED_MFU:.4f}",
                    "predicted_gpu_hours": f"{predicted:.3f}",
                    "reported_gpu_hours": (
                        "" if run.reported_gpu_hours is None else f"{run.reported_gpu_hours:.3f}"
                    ),
                    "reported_over_predicted": (
                        ""
                        if run.reported_gpu_hours is None
                        else f"{run.reported_gpu_hours / predicted:.3f}"
                    ),
                    "implied_mfu": "" if effective is None else f"{effective:.6f}",
                    "note": run.note,
                }
            )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="Optional CSV output path")
    args = parser.parse_args()

    data = rows()
    fieldnames = list(data[0])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

    print("system\tpredicted_gpu_h\treported_gpu_h\timplied_mfu")
    for row in data:
        print(
            f"{row['system']}\t{row['predicted_gpu_hours']}\t"
            f"{row['reported_gpu_hours'] or '-'}\t{row['implied_mfu'] or '-'}"
        )


if __name__ == "__main__":
    main()
