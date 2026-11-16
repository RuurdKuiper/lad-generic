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
                            "improvement_512_to_1024": first, "improvement_1024_to_2048": second,
                            "improvement_per_added_rank_512_to_1024": first / 512,
                            "improvement_per_added_rank_1024_to_2048": second / 1024})
    latest = comparisons[-1]
    times = {rank: row["median_seconds_per_update"] for rank, row in resources.items()}
    finished = all(max(rows) == 25000 for rows in series.values())
    verification_path = HERE / "final_run_verification.json"
    verification = json.loads(verification_path.read_text()) if verification_path.exists() else {}
    jobs = verification.get("jobs", [])
    artifact_status = {
        "rank1024_final_adapter_saved": bool(verification.get("rank1024_final_files")),
        "latest_provider_job_stage": jobs[-1]["status"]["stage"] if jobs else None,
        "verification_file": "final_run_verification.json",
    }
    summary = {"metric": "weighted_loss = 0.9 * answer_loss + 0.1 * padding_loss",
               "matched_update": common_steps[-1], "latest_matched_comparison": latest,
               "rank1024_finished_25k": max(series[1024]) == 25000,
               "slower_2048_vs_512_percent": 100 * (times["2048"] / times["512"] - 1),
               "slower_2048_vs_1024_percent": 100 * (times["2048"] / times["1024"] - 1),
               "adapter_state_parameter_ratio_2048_to_1024": resources["2048"]["lora_parameters"] / resources["1024"]["lora_parameters"],
               "resources": resources, "sources": sources,
               "memory_evidence": "Parameter counts are measured; increased adapter/gradient/Adam-state storage is inferred under identical precision/optimizer. There is no common four-rank peak-VRAM comparison. Live device-memory samples for the 1024 recovery are retained separately, not reported as instrumented whole-run peaks.",
               "timing_method": "Median clean logged intervals, excluding validation/checkpoint boundaries and process-clock resets. Training-update times are not end-to-end job durations.",
               "limits": "One parent, one seed, validation loss only; no globally optimal rank or downstream quality improvement established. Diminishing returns refers to loss reduction per added rank/adapter parameter, not necessarily smaller absolute reductions.",
               "all_ranks_finished_25k": finished,
               "artifact_status": artifact_status,
               "original_rank_selection": "Balance validation quality with single-A100 feasibility in the original implementation: per-device batch 16 on the 80GB variant or batch 8 on the 40GB variant. The controlled rank study uses RTX PRO 6000 hardware; no cross-rank A100 memory benchmark is claimed."}
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
    per_rank_first = smaller / 512
    per_rank_second = larger / 1024
    normalized_reduction = 100 * (1 - per_rank_second / per_rank_first)
    endpoint_note = ("All four ranks have completed the matched 25,000-update budget." if finished
                     else "The rank-1024 run is incomplete; these are matched-step results, not four final endpoints.")
    report = f"""# Rank trade-off evidence — {'completed 25k comparison' if finished else 'provisional snapshot'}

All comparisons use the fresh controlled runs and their actual 90/10 validation objective. The historical rank-1024 curve is excluded. Main benchmark models and results are unchanged.

At **{common_steps[-1]:,} matched updates**, losses are 128: **{latest['loss_128']:.6f}**, 512: **{latest['loss_512']:.6f}**, 1024: **{latest['loss_1024']:.6f}**, 2048: **{latest['loss_2048']:.6f}**. The 512→1024 reduction is **{smaller:.6f}**; 1024→2048 is **{larger:.6f}**. {endpoint_note}

The rank increases differ: 512 additional rank units versus 1,024. Loss reduction per added rank unit is **{per_rank_first:.8f}** versus **{per_rank_second:.8f}**, a **{normalized_reduction:.1f}%** smaller return for the latter increase. Adapter parameter count scales linearly with rank in this fixed-backbone/Q/V experiment. This is the diminishing-return comparison; it must not be confused with a smaller absolute loss reduction.

| Rank | LoRA parameters | Median seconds/update | Clean 100-update intervals | Validation through update |
|---|---:|---:|---:|---:|
{resource_rows}

Rank 2048 is **{summary['slower_2048_vs_512_percent']:.2f}%** slower per update than 512 and **{summary['slower_2048_vs_1024_percent']:.2f}%** slower than 1024 in the available timing intervals. These are training-update timings on the same GPU family and recipe, with validation/checkpoint work excluded. The first three ranks shared one GPU allocation; rank 1024 uses separate allocations of the same hardware type. These timings are not full end-to-end run durations or repeated-run confidence intervals.

## Memory evidence

Rank 1024 was selected to balance validation quality with single-A100 feasibility: per-device batch size 16 on an 80GB A100, or 8 on a 40GB A100, in the original implementation. This is the author's reported configuration rationale, not a new controlled hardware comparison. The rank study uses RTX PRO 6000 GPUs. Memory requirements depend on the implementation and configuration.

The four-rank logs contain no common peak-VRAM comparison. Rank 2048 has twice the adapter parameters of 1024 (872.4M vs 436.2M), and four times those of 512. At fixed precision and optimizer, adapter parameters, gradients and Adam moments scale with this count. This is an inferred increase in adapter-related training-state storage, **not a measured doubling of total peak GPU memory**. Live device-memory samples from the rank-1024 recovery are retained separately in `gpu_memory_*.jsonl`; they do not establish peaks for the other ranks.

## Interpretation and remaining work

Rank 1024 offers a practical quality/resource compromise under the original single-GPU constraint; rank 2048 still gives lower validation loss. {endpoint_note} The resource-normalized return is the relevant comparison, not a claim that the absolute 1024→2048 gain is always smaller. The CSV retains every shared step. One seed/parent and a validation-only objective do not establish downstream benchmark accuracy, generation quality or a universally optimal rank.

The author reports earlier exploratory trials with MLP adapters, other attention-projection targets and learning rates. These guided the shared recipe but were not retained as a systematic controlled sweep. Treat them as author-reported design motivation, without numerical superiority or optimality claims. Rank, target modules, learning rate and backbone can interact. The present experiment isolates rank under fixed choices; focused module/LR sensitivity controls remain separate from an exhaustive joint sweep.

## Artifact status

All four loss histories reach 25k: **{finished}**. The latest provider job stage is **{artifact_status['latest_provider_job_stage']}**, and the rank-1024 final adapter is present: **{artifact_status['rank1024_final_adapter_saved']}**. Training completion and successful model persistence are separate checks. See `final_run_verification.json` and `rank1024_recovery_diagnosis.json`. The final recovery saved its 25k validation result but encountered a Hub storage/billing 403 when uploading the final recovery checkpoint; its 22.5k recovery state remains available. No recharge or storage deletion is authorized by this report.

## Reproduce

After refreshing the logs, run `python iclr2027_rebuttal/rank_ablation/summarize_rank_tradeoff.py`. The adjacent JSON contains source hashes, available Hub revisions and each retained timing interval; the CSV contains every shared-step loss comparison, including reductions normalized by added rank.
"""
    (HERE / "RANK_TRADEOFF.md").write_text(report)
    print(json.dumps({key: value for key, value in summary.items() if key not in {"resources", "sources"}}, indent=2))


if __name__ == "__main__":
    main()
