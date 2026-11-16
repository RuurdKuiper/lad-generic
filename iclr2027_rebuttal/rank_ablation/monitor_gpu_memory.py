"""Record live Hugging Face job GPU telemetry without modifying the GPU job.

The Hub metrics SSE stream has no history. Recorded maxima are therefore sampled
maxima from this monitoring window, not instrumented whole-run peak allocations.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import time

from dotenv import load_dotenv
from huggingface_hub import HfApi
from huggingface_hub.utils import get_session
from requests.exceptions import RequestException


def summarize(records, job_id, stage):
    readings = []
    for record in records:
        for device, gpu in record["metrics"].get("gpus", {}).items():
            readings.append({"device": device, "observed_at_utc": record["observed_at_utc"], **gpu})
    used = [r["memory_used_bytes"] for r in readings if r.get("memory_used_bytes", 0) > 0]
    peak = max(readings, key=lambda r: r.get("memory_used_bytes", 0), default=None)
    return {
        "job_id": job_id, "job_stage": stage, "samples": len(records),
        "first_observation_utc": records[0]["observed_at_utc"] if records else None,
        "last_observation_utc": records[-1]["observed_at_utc"] if records else None,
        "latest_gpus": records[-1]["metrics"].get("gpus", {}) if records else {},
        "largest_observed_gpu_memory": peak,
        "median_nonzero_gpu_memory_bytes": statistics.median(used) if used else None,
        "scope": "Rank-1024 recovery allocation only; live telemetry has no earlier history.",
        "limitation": "Sampled device memory, including allocator/context overhead; not PyTorch max_memory_allocated or a guaranteed whole-run peak. Startup/validation/checkpoint phases may be included.",
        "api_reference": "https://huggingface.co/docs/hub/jobs-manage#monitor-resource-usage",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id")
    parser.add_argument("--namespace", default="Ruurd")
    parser.add_argument("--max-seconds", type=int, default=3600)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    load_dotenv(here.parents[1] / ".env")
    output = args.output or here / f"gpu_memory_{args.job_id}.jsonl"
    summary_path = output.with_suffix(".summary.json")
    records = [json.loads(line) for line in output.read_text().splitlines()] if output.exists() else []
    api = HfApi()
    headers = api._build_hf_headers()
    session = get_session()
    base = f"https://huggingface.co/api/jobs/{args.namespace}/{args.job_id}"
    started = time.monotonic()
    next_status = 0.0
    next_print = 0.0
    stage = "UNKNOWN"
    terminal = {"COMPLETED", "ERROR", "FAILED", "CANCELED", "DELETED"}
    print(json.dumps({"monitoring_job": args.job_id, "output": str(output)}), flush=True)
    while time.monotonic() - started < args.max_seconds:
        if time.monotonic() >= next_status:
            response = session.get(base, headers=headers, timeout=(10, 15))
            response.raise_for_status()
            stage = response.json()["status"]["stage"]
            next_status = time.monotonic() + 30
            summary_path.write_text(json.dumps(summarize(records, args.job_id, stage), indent=2) + "\n")
            print(json.dumps({"stage": stage, "samples": len(records)}), flush=True)
            if stage in terminal:
                break
        try:
            with session.get(base + "/metrics", headers=headers, stream=True, timeout=(10, 10)) as response:
                if response.status_code in {406, 500}:
                    time.sleep(3)
                    continue
                response.raise_for_status()
                response.encoding = "utf-8"
                for line in response.iter_lines(chunk_size=1, decode_unicode=True):
                    if time.monotonic() - started >= args.max_seconds or time.monotonic() >= next_status:
                        break
                    if not line or not line.startswith("data:"):
                        continue
                    metrics = json.loads(line.removeprefix("data:").strip())
                    if not isinstance(metrics, dict) or "gpus" not in metrics:
                        continue
                    record = {"observed_at_utc": datetime.now(timezone.utc).isoformat(), "metrics": metrics}
                    records.append(record)
                    with output.open("a") as handle:
                        handle.write(json.dumps(record) + "\n")
                    summary = summarize(records, args.job_id, stage)
                    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
                    if time.monotonic() >= next_print:
                        print(json.dumps({"samples": len(records), "latest_gpus": summary["latest_gpus"]}), flush=True)
                        next_print = time.monotonic() + 30
        except (RequestException, ValueError) as error:
            print(json.dumps({"telemetry_retry": type(error).__name__}), flush=True)
            time.sleep(3)
    summary_path.write_text(json.dumps(summarize(records, args.job_id, stage), indent=2) + "\n")


if __name__ == "__main__":
    main()
