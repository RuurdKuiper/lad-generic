"""Run a measured, sequential rank study under one bounded GPU allocation."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

from huggingface_hub import HfApi

LATEST_STATE = {}

def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measurements(output):
    rows = read_rows(output / "metrics.jsonl")
    train = [row for row in rows if row.get("split") == "train"]
    # Use the two most recent within-process points; a resume resets elapsed time.
    right, left = train[-1], train[-2]
    seconds_per_update = (right["elapsed_seconds"] - left["elapsed_seconds"]) / (right["step"] - left["step"])
    if not math.isfinite(seconds_per_update) or seconds_per_update <= 0:
        raise RuntimeError("Invalid measured training speed")
    validation = [row for row in rows if row.get("split") == "validation"][-1]
    checkpoint = read_rows(output / "runtime_metrics.jsonl")[-1]
    return {"step": checkpoint["step"], "seconds_per_update": seconds_per_update,
            "validation_seconds": validation["validation_seconds"],
            "checkpoint_seconds": checkpoint["save_seconds"] + checkpoint["upload_seconds"]}


def forecast(measured, *, slow_margin=1.2):
    """Conservative remaining time; include future validation, saves and finalization."""
    remaining = 0.
    for item in measured.values():
        updates = 25000 - item["step"]
        remaining += updates * item["seconds_per_update"] * slow_margin
        remaining += math.ceil(updates / 250) * item["validation_seconds"] * slow_margin
        remaining += math.ceil(updates / 2500) * item["checkpoint_seconds"] * slow_margin
        remaining += 300  # Model reload, final adapter export and transfer.
    return remaining


def main():
    global LATEST_STATE
    started = float(os.environ.get("RANK_BOOT_MONOTONIC", time.monotonic()))
    deadline = started + int(os.environ["RANK_GPU_SECONDS"]) - 600
    os.environ["RANK_DEADLINE_MONOTONIC"] = str(deadline)
    repo = os.environ["RANK_REPO"]
    api = HfApi()
    output_root = Path("/tmp/rank-study-output")
    state = {"status": "gpu_preflight", "cap_usd": 42., "ranks": [128, 512, 2048],
             "run_prefix": "fp8-checkpoint-v2",
             "max_updates": 25000, "gpu_timeout_seconds": int(os.environ["RANK_GPU_SECONDS"]),
             "gpu_rate_usd_per_hour": 2.74998, "completed": []}
    LATEST_STATE = state

    def persist():
        state["elapsed_gpu_command_seconds"] = time.monotonic() - started
        state["remaining_seconds_before_reserve"] = deadline - time.monotonic()
        api.upload_file(repo_id=repo, repo_type="dataset", path_or_fileobj=json.dumps(state, indent=2).encode(),
                        path_in_repo="study_status.json", commit_message="Save bounded rank-study progress")
        print(json.dumps(state), flush=True)

    def run(rank, stop=None):
        command = [sys.executable, "run_training.py", "--rank", str(rank), "--repo", repo,
                   "--output-root", str(output_root)]
        if stop:
            command += ["--checkpoint-steps", "250", "--stop-after-checkpoint", str(stop)]
        print(json.dumps({"starting_rank": rank, "pause_step": stop}), flush=True)
        subprocess.run(command, check=True, timeout=max(1, int(deadline - time.monotonic())))

    persist()
    # These are the first updates of the actual 25k runs, using their full data
    # prefix and schedule. All saved work is reused if the full-study gate passes.
    state["status"] = "timing_and_recovery"
    persist()
    run(2048, 250)
    run(2048, 500)  # New process downloads and loads full recovery state.
    import torch

    optimizer = torch.load(output_root / "rank-2048/checkpoint-500/optimizer.bin", map_location="cpu", weights_only=True)
    if not optimizer["state"] or any(int(item["step"]) != 500 for item in optimizer["state"].values()):
        raise RuntimeError("FP8 recovery check did not preserve optimizer update count")
    del optimizer
    state["fp8_recovery_verified"] = True
    persist()
    run(128, 250)
    run(512, 250)
    measured = {str(rank): measurements(output_root / f"rank-{rank}") for rank in (128, 512, 2048)}
    state["measurements"] = measured
    state["forecast_remaining_seconds_with_20pct_margin"] = forecast(measured)
    if state["forecast_remaining_seconds_with_20pct_margin"] > deadline - time.monotonic():
        state["status"] = "stopped_does_not_fit_budget"
        persist()
        return
    state["status"] = "training"
    persist()
    for rank in (128, 512, 2048):
        state["active_rank"] = rank
        persist()
        run(rank)
        output = output_root / f"rank-{rank}"
        if not (output / "final/adapter_config.json").is_file():
            state["status"] = "stopped_at_budget_checkpoint"
            persist()
            return
        state["completed"].append(rank)
        measured[str(rank)] = measurements(output)
        unfinished = {key: item for key, item in measured.items() if int(key) not in state["completed"]}
        state["forecast_remaining_seconds_with_20pct_margin"] = forecast(unfinished)
        if forecast(unfinished) > deadline - time.monotonic():
            state["status"] = "stopped_remaining_runs_do_not_fit_budget"
            persist()
            return
        persist()
    state["status"] = "complete"
    persist()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        LATEST_STATE.update(status="stopped_error", error=type(error).__name__, message=str(error)[:800])
        print(json.dumps(LATEST_STATE), flush=True)
        try:
            HfApi().upload_file(repo_id=os.environ["RANK_REPO"], repo_type="dataset",
                                path_or_fileobj=json.dumps(LATEST_STATE, indent=2).encode(),
                                path_in_repo="study_status.json", commit_message="Stop rank study after error")
        except Exception:
            pass
        raise
