#!/usr/bin/env python3
"""Small resumable APD ON/OFF completeness, forward-count and latency check."""
import argparse
from html import unescape
import json
import os
from pathlib import Path
import re
import time

from dotenv import load_dotenv
from gradio_client import Client
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
SPACES = ("Ruurd/byod-gemma-2-9b", "Ruurd/llada-8b-instruct")
METHODS = (
    ("standard", "Confidence-guided", "PMI bigram"),
    ("conditional", "Bigram Viterbi", "Conditional bigram"),
    ("pmi", "Bigram Viterbi", "PMI bigram"),
    ("repetition", "PMI Viterbi + Repetition Penalty", "PMI bigram"),
    ("random", "Random", "PMI bigram"),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/bigram/apd_rollout")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    api = HfApi()
    args.output.mkdir(parents=True, exist_ok=True)
    result_path = args.output / ("before.json" if args.baseline else "hosted_verification.json")
    records = json.loads(result_path.read_text()) if result_path.exists() else []
    complete = {(r["space"], r["method"], r["apd"]) for r in records}
    before = {} if args.baseline else {(r["space"], r["method"]): r for r in json.loads((args.output / "before.json").read_text())}
    for space in SPACES:
        client = Client(space, token=os.getenv("HF_TOKEN"), verbose=False)
        revision = api.repo_info(space, repo_type="space").sha
        if not args.baseline:
            props = [c.get("props", {}) for c in client.config["components"]]
            checkbox = next(p for p in props if p.get("label") == "Adaptive Parallel Decoding (APD)")
            assert checkbox["value"] is False
            # Discard a short warmup; report in-function latency separately from
            # client wall time, which includes ZeroGPU allocation and queueing.
            client.predict("What do you know about Amsterdam?", "You are a helpful assistant.",
                8, 2, 8, 2., 16, 0., "No coloring", "Confidence-guided", False, 4, True, False,
                generation_seed=1234, adaptive_parallel_decoding=False, api_name="/generate")
        methods = list(METHODS)
        if "gemma" in space:
            methods.append(("ar", "Autoregressive-confidence", "PMI bigram"))
        for name, strategy, scoring in methods:
            for apd in ([False] if args.baseline else [False, True]):
                if (space, name, apd) in complete:
                    continue
                settings = dict(question="What do you know about Amsterdam?", system_prompt="You are a helpful assistant.",
                    max_new_tokens=16, num_steps=16, block_length=8, temperature=2., top_k=16,
                    pause_per_step=0., trajectory_color_mode="No coloring", remasking_strategy=strategy,
                    revisable_tokens=False, ar_check_interval=4, delay_eos_eot=True, early_stopping=False,
                    bigram_scoring_method=scoring, generation_seed=1234, measure_decoding=True,
                    repetition_penalty_strength=1.)
                if not args.baseline:
                    settings["adaptive_parallel_decoding"] = apd
                start = time.perf_counter()
                job = client.submit(**settings, api_name="/generate")
                status, rendered = job.result()
                elapsed = time.perf_counter() - start
                frames = job.outputs()
                count = len(frames)
                assert count <= 16 and count >= 2
                assert "masked at iteration" not in rendered, f"Unresolved output: {space}/{name}/{apd}"
                match = re.search(r"<textarea[^>]*>(.*?)</textarea>", rendered, re.S)
                assert match is not None
                text = unescape(match[1])
                inference = None
                if not args.baseline:
                    inference = json.loads(status.split("Inference metrics: ")[1].splitlines()[0])
                    assert inference["denoising_forward_passes"] == count
                if not apd:
                    assert count == 16
                    if not args.baseline:
                        assert text == before[space, name]["text"], f"OFF regression: {space}/{name}"
                record = dict(space=space, revision=revision, method=name, apd=apd, settings=settings,
                    text=text, denoising_forward_passes=count, client_elapsed_seconds=elapsed,
                    inference_metrics=inference, status=status)
                records.append(record)
                result_path.write_text(json.dumps(records, indent=2) + "\n")
                print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
