"""Summarize matched-step validation gains and measured training-update times."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    series, resources, sources = {}, {}, {}
    for rank in (128, 512, 1024, 2048):
        folder = ROOT / f"outputs/rank-ablation/fp8-checkpoint-v2/rank-{rank}"
        path = folder / "metrics.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        config = json.loads((folder / "resolved_config.json").read_text())
        assert config["gradient_accumulation_steps"] == 1
        validation_every = config["validation_steps"]
        validation = {row["step"]: row for row in rows if row.get("split") == "validation"}
        assert all(math.isclose(row["weighted_loss"], .9 * row["answer_loss"] + .1 * row["padding_loss"], rel_tol=1e-6)
                   for row in validation.values())
        series[rank] = validation
        train = [row for row in rows if row.get("split") == "train" and "elapsed_seconds" in row]
        intervals = []
        for left, right in zip(train, train[1:]):
            first_boundary = math.ceil(left["step"] / validation_every) * validation_every
            delta = right["elapsed_seconds"] - left["elapsed_seconds"]
            # A train record is emitted before validation at the same step.
            # An interval includes work after its left endpoint but excludes
            # work after its right endpoint: boundaries are [left, right).
            if (right["step"] - left["step"] == config["logging_steps"]
                    and delta > 0 and first_boundary >= right["step"]):
                intervals.append({"from": left["step"], "to": right["step"],
                                  "seconds_per_update": delta / (right["step"] - left["step"])})
        audit = json.loads((folder / "parameter_audit.json").read_text())
        resources[str(rank)] = {
            "validation_through_update": max(validation),
            "lora_parameters": audit["lora_parameters"],
            "median_seconds_per_update": statistics.median(row["seconds_per_update"] for row in intervals),
            "mean_seconds_per_update": statistics.mean(row["seconds_per_update"] for row in intervals),
            "clean_100_update_intervals": len(intervals),
            "intervals": intervals,
            "gpu_model": config.get("fp8_device_name"),
            "peak_vram_bytes": None,
        }
        sources[str(rank)] = {"file": path.relative_to(ROOT).as_posix(),
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        meta = ROOT / f"outputs/rank-ablation/.cache/huggingface/download/fp8-checkpoint-v2/rank-{rank}/metrics.jsonl.metadata"
        if meta.exists():
            sources[str(rank)]["hub_revision"] = meta.read_text().splitlines()[0]

    common_steps = sorted(set.intersection(*(set(rows) for rows in series.values())))
    comparisons = []
    for step in common_steps:
        losses = {str(rank): series[rank][step]["weighted_loss"] for rank in series}
        first = losses["512"] - losses["1024"]
        second = losses["1024"] - losses["2048"]
        comparisons.append({"step": step, **{f"loss_{rank}": value for rank, value in losses.items()},
                            "improvement_512_to_1024": first, "improvement_1024_to_2048": second})
    latest = comparisons[-1]
    times = {rank: row["median_seconds_per_update"] for rank, row in resources.items()}
    summary = {"metric": "weighted_loss = 0.9 * answer_loss + 0.1 * padding_loss",
               "matched_update": common_steps[-1], "latest_matched_comparison": latest,
               "rank1024_finished_25k": max(series[1024]) == 25000,
               "slower_2048_vs_512_percent": 100 * (times["2048"] / times["512"] - 1),
               "slower_2048_vs_1024_percent": 100 * (times["2048"] / times["1024"] - 1),
               "adapter_state_parameter_ratio_2048_to_1024": resources["2048"]["lora_parameters"] / resources["1024"]["lora_parameters"],
               "resources": resources, "sources": sources,
               "memory_evidence": "Parameter counts are measured; increased adapter/gradient/Adam-state storage is inferred under identical precision/optimizer. Peak GPU VRAM was not recorded.",
               "timing_method": "Median clean logged intervals, excluding validation/checkpoint boundaries and process-clock resets. Training-update times are not end-to-end job durations.",
               "limits": "One parent, one seed, validation loss only. Diminishing returns and the rank-1024 compromise remain provisional until its matched 25k endpoint."}
    (HERE / "rank_tradeoff_snapshot.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (HERE / "rank_tradeoff_matched_steps.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(latest))
        writer.writeheader()
        writer.writerows(comparisons)

    resource_rows = "\n".join(
        f"| {rank} | {row['lora_parameters'] / 1e6:.1f}M | {row['median_seconds_per_update']:.4f} | {row['clean_100_update_intervals']} | {row['validation_through_update']:,} |"
        for rank, row in resources.items())
    smaller = latest["improvement_512_to_1024"]
    larger = latest["improvement_1024_to_2048"]
    report = f"""# Rank trade-off evidence — provisional snapshot

All comparisons use the fresh controlled runs and their actual 90/10 validation objective. The historical rank-1024 curve is excluded. Main benchmark models and results are unchanged.

At **{common_steps[-1]:,} matched updates**, losses are 512: **{latest['loss_512']:.6f}**, 1024: **{latest['loss_1024']:.6f}**, 2048: **{latest['loss_2048']:.6f}**. The 512→1024 reduction is **{smaller:.6f}**; 1024→2048 is **{larger:.6f}**. Compare the same training step, not finished 25k models against a partially trained 1024.

| Rank | LoRA parameters | Median seconds/update | Clean 100-update intervals | Validation through update |
|---|---:|---:|---:|---:|
{resource_rows}

Rank 2048 is **{summary['slower_2048_vs_512_percent']:.2f}%** slower per update than 512 and **{summary['slower_2048_vs_1024_percent']:.2f}%** slower than the current 1024 timing estimate. The 1024 estimate is provisional while training continues. These are training-update timings on the same GPU family and recipe, with validation/checkpoint work excluded. The first three ranks shared one GPU allocation; the fresh 1024 uses another allocation of the same hardware type. These timings are not full end-to-end run durations or repeated-run confidence intervals.

## Memory evidence

Our training logs contain no peak-VRAM measurement. Rank 2048 has twice the adapter parameters of 1024 (872.4M vs 436.2M), and four times those of 512. At fixed precision and optimizer, adapter parameters, gradients and Adam moments scale with this count. This is an inferred increase in adapter-related training-state storage, **not a measured doubling of total peak GPU memory**. Frozen backbone storage, activations, workspaces and allocator behavior also contribute to the peak. No GPU rerun is required or proposed solely to measure memory.

## Interpretation and remaining work

The current matched-step curves suggest diminishing validation-loss gains and make rank 1024 a candidate practical compromise under this recipe. They do not yet establish a final-endpoint result or a globally optimal rank. The pattern need not hold at every early update: the CSV includes all shared steps, including points with a larger 1024→2048 gain. Keep the endpoint claim pending until 1024 reaches 25k; then regenerate this summary and compare all four final losses. One seed/parent and a validation-only objective do not establish downstream benchmark accuracy or generation quality.

The author reports earlier exploratory trials with MLP adapters, other attention-projection targets and learning rates. These guided the shared recipe but were not retained as a systematic controlled sweep. Treat them as author-reported design motivation, without numerical superiority or optimality claims. Rank, target modules, learning rate and backbone can interact. The present experiment isolates rank under fixed choices; focused module/LR sensitivity controls remain separate from an exhaustive joint sweep.

## Reproduce

After refreshing the logs, run `python iclr2027_rebuttal/rank_ablation/summarize_rank_tradeoff.py`. The adjacent JSON contains source hashes, available Hub revisions and each retained timing interval; the CSV contains every shared-step loss comparison. Regeneration after further 1024 progress updates this snapshot.
"""
    (HERE / "RANK_TRADEOFF.md").write_text(report)
    print(json.dumps({key: value for key, value in summary.items() if key not in {"resources", "sources"}}, indent=2))


if __name__ == "__main__":
    main()
