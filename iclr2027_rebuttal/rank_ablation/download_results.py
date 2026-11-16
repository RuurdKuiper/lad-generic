"""Download persistent rank-study loss logs for plotting locally, without a GPU."""
import argparse
from pathlib import Path


def main():
    from dotenv import load_dotenv
    from huggingface_hub import snapshot_download

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/rank-ablation"))
    parser.add_argument("--include-final-models", action="store_true")
    args = parser.parse_args()
    prefix = "fp8-checkpoint-v2/"
    patterns = [f"{prefix}rank-*/metrics*.jsonl*", f"{prefix}rank-*/runtime_metrics.jsonl", f"{prefix}rank-*/resolved_config.json",
                f"{prefix}rank-*/parameter_audit.json", "study_status.json"]
    if args.include_final_models:
        patterns.append(f"{prefix}rank-*/final/*")
    result = snapshot_download("Ruurd/iclr2027-rank-ablation", repo_type="dataset", local_dir=args.output,
                               allow_patterns=patterns)
    print(f"Saved rank-study logs to {Path(result).resolve()}")


if __name__ == "__main__":
    main()
