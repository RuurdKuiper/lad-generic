#!/usr/bin/env python
"""Train one approved rank run, persisting curves and recovery state privately.

This is a worker entry point, not a paid-job launcher. Its Hub dataset must
already exist and be private. Each rank owns a separate repository directory.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import time
from pathlib import Path


class PauseAfterCheckpoint(Exception):
    """An intentional stop after recovery state is durably committed."""


class HubArtifacts:
    """Commit completed artifacts before removing older recovery checkpoints."""

    LOG_FILES = (
        "metrics.jsonl", "metrics.before-resume-*.jsonl*", "resolved_config.json",
        "parameter_audit.json", "mask_token.json", "test_metrics.json",
        "runtime_metrics.jsonl",
    )

    def __init__(self, api, repo: str, prefix: str, keep: int = 2):
        if not api.repo_info(repo_id=repo, repo_type="dataset").private:
            raise ValueError("Rank-study artifacts must be saved to a private dataset repository")
        self.api, self.repo, self.prefix, self.keep = api, repo, prefix, keep

    def _completed(self) -> dict[int, str]:
        pattern = re.compile(re.escape(self.prefix) + r"/(checkpoint-(\d+))/state\.json$")
        completed = {}
        for name in self.api.list_repo_files(repo_id=self.repo, repo_type="dataset"):
            if match := pattern.fullmatch(name):
                completed[int(match[2])] = f"{self.prefix}/{match[1]}"
        return completed

    def restore(self, output: Path) -> Path | None:
        """Download the newest completed checkpoint together with the full logs."""
        from huggingface_hub import snapshot_download

        completed = self._completed()
        if not completed:
            return None
        step = max(completed)
        cache = output.parent / f".{output.name}-restore"
        snapshot_download(
            repo_id=self.repo, repo_type="dataset", local_dir=cache,
            allow_patterns=[
                f"{completed[step]}/*",
                *(f"{self.prefix}/{name}" for name in self.LOG_FILES),
            ],
        )
        import shutil

        output.mkdir(parents=True, exist_ok=True)
        shutil.copytree(cache / self.prefix, output, dirs_exist_ok=True)
        checkpoint = output / f"checkpoint-{step}"
        state = json.loads((checkpoint / "state.json").read_text())
        if state.get("step") != step:
            raise ValueError("Remote checkpoint step does not match its completion marker")
        # The downloaded 8B base/optimizer state need not occupy disk twice.
        shutil.rmtree(cache)
        return checkpoint

    def __call__(self, event: str, output: Path, artifact: Path | None) -> None:
        started = time.monotonic()
        self.api.upload_folder(
            repo_id=self.repo, repo_type="dataset", folder_path=output,
            path_in_repo=self.prefix, allow_patterns=list(self.LOG_FILES),
            commit_message=f"{self.prefix}: {event} logs",
        )
        if event not in {"checkpoint", "final"}:
            return
        if artifact is None or not artifact.is_dir():
            raise ValueError(f"Missing {event} artifact")
        self.api.upload_folder(
            repo_id=self.repo, repo_type="dataset", folder_path=artifact,
            path_in_repo=f"{self.prefix}/{artifact.name}",
            commit_message=f"{self.prefix}: completed {artifact.name}",
        )
        if event == "checkpoint":
            # upload_folder commits the entire new directory atomically. Only
            # after that succeeds may older committed checkpoints be removed.
            from huggingface_hub import CommitOperationDelete

            current_step = int(artifact.name.removeprefix("checkpoint-"))
            completed = self._completed()
            eligible = sorted((step for step in completed if step <= current_step), reverse=True)
            old = [completed[step] for step in eligible[self.keep:]]
            files = self.api.list_repo_files(repo_id=self.repo, repo_type="dataset")
            operations = [CommitOperationDelete(path_in_repo=name) for name in files
                          if any(name.startswith(prefix + "/") for prefix in old)]
            if operations:
                self.api.create_commit(
                    repo_id=self.repo, repo_type="dataset", operations=operations,
                    commit_message=f"{self.prefix}: retain latest {self.keep} recovery checkpoints",
                )
            state = json.loads((artifact / "state.json").read_text())
            record = {"step": current_step, "save_seconds": state.get("save_seconds", 0.),
                      "upload_seconds": time.monotonic() - started}
            path = output / "runtime_metrics.jsonl"
            with path.open("a") as handle:
                handle.write(json.dumps(record) + "\n")
            self.api.upload_file(repo_id=self.repo, repo_type="dataset", path_or_fileobj=path,
                                 path_in_repo=f"{self.prefix}/runtime_metrics.jsonl",
                                 commit_message=f"{self.prefix}: checkpoint timing")
            if current_step == getattr(self, "stop_after", None):
                raise PauseAfterCheckpoint()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rank", type=int, required=True, choices=(128, 512, 1024, 2048))
    parser.add_argument("--repo", required=True, help="Existing private Hub dataset for artifacts")
    parser.add_argument("--output-root", type=Path, default=Path("outputs/rank-ablation"))
    parser.add_argument("--checkpoint-steps", type=int, help="Recovery cadence override for the initial timing/restart check")
    parser.add_argument("--stop-after-checkpoint", type=int, help="Intentionally pause after this checkpoint is uploaded")
    parser.add_argument("--study-prefix", default="fp8-checkpoint-v2", help="Separate corrected runs from the archived format-check attempt")
    args = parser.parse_args()

    from huggingface_hub import HfApi
    import yaml
    from diffusion_lm.training import _resolve_fp8, run_training

    config_path = Path(__file__).parent / "configs" / f"rank_{args.rank}.yaml"
    config = yaml.safe_load(config_path.read_text())
    if args.checkpoint_steps is not None:
        if args.checkpoint_steps < 1:
            raise ValueError("Checkpoint cadence must be positive")
        config["checkpoint_steps"] = args.checkpoint_steps
    if not _resolve_fp8(config)["active"]:
        raise RuntimeError("This rank study requires native FP8; choose the approved FP8 GPU/runtime before training")
    rank_name = f"rank-{args.rank}"
    prefix = f"{args.study_prefix}/{rank_name}" if args.study_prefix else rank_name
    output = (args.output_root / rank_name).resolve()
    artifacts = HubArtifacts(HfApi(), args.repo, prefix, config["checkpoint_total_limit"])
    artifacts.stop_after = args.stop_after_checkpoint
    if checkpoint := artifacts.restore(output):
        original = json.loads((output / "resolved_config.json").read_text())
        # Changes affecting the model, data, objective, or optimizer must start
        # a new study, rather than silently continuing an incompatible run.
        for name, value in config.items():
            if name not in {"output_dir", "save_best_model", "checkpoint_total_limit", "checkpoint_steps"} and original.get(name) != value:
                raise ValueError(f"Cannot resume: configuration changed for {name}")
        config["resume_from_checkpoint"] = str(checkpoint)
    config["output_dir"] = str(output)
    def persist(event, run_output, artifact):
        artifacts(event, run_output, artifact)
        if event == "metrics":
            validation = [json.loads(line) for line in (run_output / "metrics.jsonl").read_text().splitlines()
                          if json.loads(line).get("split") == "validation"][-1]
            if not math.isfinite(validation["weighted_loss"]):
                raise RuntimeError("Non-finite validation loss; stopping paid training")
            deadline = float(os.environ.get("RANK_DEADLINE_MONOTONIC", "inf"))
            if deadline - time.monotonic() < 900:
                # Save at this validation boundary before the provider timeout.
                config["checkpoint_steps"] = validation["step"]
                artifacts.stop_after = validation["step"]
    try:
        run_training(config, artifact_callback=persist)
    except PauseAfterCheckpoint:
        print(json.dumps({"status": "paused_after_saved_checkpoint", "rank": args.rank,
                          "step": artifacts.stop_after}), flush=True)


if __name__ == "__main__":
    main()
