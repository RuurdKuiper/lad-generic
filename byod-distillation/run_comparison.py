"""Run matched Llama 3.2 1B baseline/distillation trials in fresh processes."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import yaml

from train import load_training_config


ROOT = Path(__file__).resolve().parent


def comparison_configs(output_root, updates=1000, evaluation_samples=64, validation_steps=100):
    common = load_training_config("llama", "quick", config_path=str(ROOT / "configs/distillation.yaml"),
                                  max_updates=updates)
    common.update(batch_size=1, eval_batch_size=1, gradient_accumulation_steps=1,
                  validation_samples=evaluation_samples, test_samples=evaluation_samples,
                  validation_steps=validation_steps, checkpoint_steps=validation_steps,
                  num_workers=0, logging_steps=10,
                  base_model_cache_dir=str(ROOT / "base_models"),
                  cache_dir=str(ROOT / "data/huggingface"),
                  prepared_data_cache_dir=str(ROOT / "data/prepared"))
    result = {}
    for name, weight in (("baseline", 0.0), ("distilled", 0.5)):
        config = dict(common, output_dir=str(output_root / name),
                      distillation=dict(enabled=weight > 0, weight=weight, temperature=1.0, chunk_size=64))
        result[name] = config
    return result


def run_comparison(output_root, updates=1000, evaluation_samples=64, validation_steps=100, *, dashboard=False):
    """Run both objectives sequentially, with an optional live Colab dashboard."""
    if min(updates, evaluation_samples, validation_steps) < 1:
        raise ValueError("Update and evaluation budgets must be positive")
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    configs = comparison_configs(output_root, updates, evaluation_samples, validation_steps)
    for config in configs.values():
        if Path(config["output_dir"]).exists():
            raise FileExistsError(f"Run directory already exists: {config['output_dir']}")
    environment = dict(os.environ, USE_TF="0", USE_TORCH="1", TOKENIZERS_PARALLELISM="false",
                       PYTHONPATH=str(ROOT / "src"), HF_HUB_DISABLE_PROGRESS_BARS="1")
    for name, config in configs.items():
        path = output_root / f"{name}.yaml"
        path.write_text(yaml.safe_dump(config))
        log_path = output_root / f"{name}.log"
        print(f"Starting {name}: {updates} optimizer updates", flush=True)
        started = time.monotonic()
        command = [sys.executable, "-u", str(ROOT / "train.py"), "--model", "llama", "--mode", "quick", "--config", str(path)]
        if dashboard:
            from diffusion_lm.notebook import run_with_dashboard
            run_with_dashboard(command, config["output_dir"], updates)
        else:
            print(f"Full log: {log_path}", flush=True)
            with log_path.open("w") as log:
                subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        print(f"Finished {name} in {time.monotonic() - started:.1f}s", flush=True)
    from compare_runs import compare_runs
    figure = compare_runs(output_root / "baseline", output_root / "distilled")
    figure.savefig(output_root / "comparison.png", dpi=160)
    import matplotlib.pyplot as plt
    plt.close(figure)
    summary = {}
    for name in configs:
        records = [json.loads(line) for line in (output_root / name / "metrics.jsonl").read_text().splitlines()]
        validation = [row for row in records if row["split"] == "validation"]
        summary[name] = dict(final_validation=validation[-1],
                             best_validation=min(validation, key=lambda row: row["weighted_loss"]),
                             final_test=json.loads((output_root / name / "test_metrics.json").read_text()),
                             environment=json.loads((output_root / name / "runtime_environment.json").read_text()))
    (output_root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Comparison saved to {output_root}", flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--updates", type=int, default=1000)
    parser.add_argument("--evaluation-samples", type=int, default=64)
    parser.add_argument("--validation-steps", type=int, default=100)
    args = parser.parse_args()
    run_comparison(args.output_root, args.updates, args.evaluation_samples, args.validation_steps)


if __name__ == "__main__":
    main()
