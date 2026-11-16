"""Complete the separate validation-only rank study with a fresh rank-1024 run."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

from huggingface_hub import HfApi, hf_hub_download
from batch_worker import forecast, measurements


def main():
    api = HfApi()
    repo = os.environ["RANK_REPO"]
    started = float(os.environ.get("RANK_BOOT_MONOTONIC", time.monotonic()))
    deadline = started + int(os.environ["RANK_GPU_SECONDS"]) - 600
    os.environ["RANK_DEADLINE_MONOTONIC"] = str(deadline)
    output_root = Path("/tmp/rank1024-study-output")
    output = output_root / "rank-1024"
    prefix = "fp8-checkpoint-v2/rank-1024"
    state = {"status": "initializing", "rank": 1024, "max_updates": 25000,
             "additional_cap_usd": 17., "run_prefix": prefix,
             "gpu_timeout_seconds": int(os.environ["RANK_GPU_SECONDS"]),
             "scope": "Separate rank experiment; benchmarked BYOD-Llama results unchanged"}

    def persist():
        state["elapsed_gpu_command_seconds"] = time.monotonic() - started
        api.upload_file(repo_id=repo, repo_type="dataset", path_or_fileobj=json.dumps(state, indent=2).encode(),
                        path_in_repo="rank1024_status.json", commit_message="Save separate rank-1024 training progress")
        print(json.dumps(state), flush=True)

    def run(stop=None):
        command = [sys.executable, "run_training.py", "--rank", "1024", "--repo", repo,
                   "--output-root", str(output_root)]
        if stop:
            command += ["--checkpoint-steps", "250", "--stop-after-checkpoint", str(stop)]
        subprocess.run(command, check=True, timeout=max(1, int(deadline - time.monotonic())))

    try:
        persist()
        files = api.list_repo_files(repo, repo_type="dataset")
        if prefix + "/final/adapter_config.json" in files:
            state["status"] = "already_complete"
            persist()
            return
        if prefix + "/runtime_metrics.jsonl" in files:
            # A later approved allocation can resume its committed state.
            output.mkdir(parents=True, exist_ok=True)
            for name in ("metrics.jsonl", "runtime_metrics.jsonl"):
                source = Path(hf_hub_download(repo, prefix + "/" + name, repo_type="dataset"))
                (output / name).write_bytes(source.read_bytes())
        else:
            state["status"] = "timing_first_250_updates"
            persist()
            # Same initial pause/resume as ranks 128 and 512. No adapter from
            # the historical benchmark model is loaded or used for training.
            run(250)
        measured = measurements(output)
        state["measurements"] = measured
        state["forecast_remaining_seconds_with_20pct_margin"] = forecast({"1024": measured})
        if state["forecast_remaining_seconds_with_20pct_margin"] > deadline - time.monotonic():
            state["status"] = "stopped_does_not_fit_budget"
            persist()
            return
        state["status"] = "training"
        persist()
        run()
        state["status"] = "complete" if (output / "final/adapter_config.json").is_file() else "stopped_at_saved_checkpoint"
        persist()
    except Exception as error:
        state.update(status="stopped_error", error=type(error).__name__, message=str(error)[:800])
        try:
            persist()
        finally:
            raise


if __name__ == "__main__":
    main()
