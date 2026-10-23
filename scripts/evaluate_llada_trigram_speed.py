#!/usr/bin/env python3
"""Hosted same-budget corpus/trigram speed comparison, with saved output examples."""

from html import unescape
import json
import os
from pathlib import Path
import re
import statistics
import time

from dotenv import load_dotenv
from gradio_client import Client
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
SPACE = "Ruurd/llada-8b-instruct"
OUT = ROOT / "artifacts/bigram/llada_expanded_ngrams"
CHOICES = ["Original bigram", "Expanded bigram", "Expanded bigram + trigram"]


def main():
    load_dotenv(ROOT / ".env")
    client = Client(SPACE, token=os.getenv("HF_TOKEN"), verbose=False)
    revision = HfApi().repo_info(SPACE, repo_type="space").sha
    props = [c.get("props", {}) for c in client.config["components"]]
    dropdown = next(p for p in props if p.get("label") == "N-gram guidance")
    assert dropdown["value"] == "Original bigram"
    path = OUT / "hosted_speed.json"
    records = json.loads(path.read_text()) if path.exists() else []
    if any(r["revision"] != revision for r in records):
        raise RuntimeError("Saved benchmark uses another revision")
    complete = {(r["choice"], r["mode"], r["trial"]) for r in records}
    baseline = json.loads(
        (ROOT / "artifacts/bigram/llada_apd_quota/hosted_verification.json").read_text()
    )[0]
    verification = OUT / "original_verification.json"
    if (
        not verification.exists()
        or json.loads(verification.read_text())["revision"] != revision
    ):
        settings = dict(baseline["settings"], ngram_guidance="Original bigram")
        status, rendered = client.predict(**settings, api_name="/generate")
        text = unescape(
            re.search(r"<textarea[^>]*>(.*?)</textarea>", rendered, re.S)[1]
        )
        assert text == baseline["text"], "Original scorer output regression"
        verification.write_text(
            json.dumps(
                dict(revision=revision, settings=settings, text=text, status=status),
                indent=2,
            )
            + "\n"
        )
    for mode in ["viterbi", "sample", "sample_risk"]:
        for choice in CHOICES:
            if mode == "sample_risk" and choice == "Original bigram":
                continue
            for trial in ([0, 1] if mode != "sample_risk" else [0]):
                if (choice, mode, trial) in complete:
                    continue
                settings = dict(
                    question="What do you know about Amsterdam?",
                    system_prompt="You are a helpful assistant.",
                    max_new_tokens=64,
                    num_steps=8,
                    block_length=64,
                    temperature=1.0,
                    top_k=16,
                    pause_per_step=0.0,
                    trajectory_color_mode="No coloring",
                    remasking_strategy=(
                        "PMI Viterbi + Repetition Penalty"
                        if mode == "sample_risk"
                        else "Bigram Viterbi"
                    ),
                    revisable_tokens=False,
                    ar_check_interval=4,
                    delay_eos_eot=False,
                    early_stopping=False,
                    generation_seed=1234,
                    measure_decoding=True,
                    repetition_penalty_strength=1.0,
                    adaptive_parallel_decoding=False,
                    bigram_weight=1.0,
                    sequence_sampling=mode != "viterbi",
                    repetition_risk_penalty=mode == "sample_risk",
                    decay_repetition_penalty=True,
                    ngram_guidance=choice,
                )
                if trial == 0:
                    # Exclude scorer load, CUDA warmup and first kernels from timing.
                    client.predict(
                        **dict(
                            settings, max_new_tokens=16, block_length=16, num_steps=1
                        ),
                        api_name="/generate",
                    )
                start = time.perf_counter()
                job = client.submit(**settings, api_name="/generate")
                status, rendered = job.result()
                wall = time.perf_counter() - start
                assert "masked at iteration" not in rendered
                text = unescape(
                    re.search(r"<textarea[^>]*>(.*?)</textarea>", rendered, re.S)[1]
                )
                inference = json.loads(
                    status.split("Inference metrics: ")[1].splitlines()[0]
                )
                decoding = json.loads(
                    status.split("Decoding metrics: ")[1].splitlines()[0]
                )
                assert (
                    len(job.outputs())
                    == inference["denoising_forward_passes"]
                    == decoding["selector_calls"]
                    == 8
                )
                row = dict(
                    choice=choice,
                    mode=mode,
                    trial=trial,
                    revision=revision,
                    settings=settings,
                    text=text,
                    inference=inference,
                    decoding=decoding,
                    client_wall_seconds=wall,
                )
                records.append(row)
                path.write_text(json.dumps(records, indent=2) + "\n")
                print(json.dumps(row), flush=True)
    summary = []
    for mode in ["viterbi", "sample", "sample_risk"]:
        for choice in CHOICES:
            group = [r for r in records if r["choice"] == choice and r["mode"] == mode]
            if not group:
                continue
            summary.append(
                dict(
                    mode=mode,
                    choice=choice,
                    runs=len(group),
                    forwards=8,
                    median_server_ms=statistics.median(
                        r["inference"]["elapsed_ms"] for r in group
                    ),
                    median_selector_ms_per_forward=statistics.median(
                        r["decoding"]["mean_selector_ms"] for r in group
                    ),
                )
            )
    (OUT / "speed_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
