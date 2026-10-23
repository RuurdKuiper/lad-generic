#!/usr/bin/env python3
"""Resumable live smoke checks; records outputs, settings and server forward counts."""

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
OUT = ROOT / "artifacts/bigram/llada_sequence_sampling"
SPACE = "Ruurd/llada-8b-instruct"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    client = Client(SPACE, token=os.getenv("HF_TOKEN"), verbose=False)
    revision = HfApi().repo_info(SPACE, repo_type="space").sha
    path = OUT / ("before.json" if args.baseline else "hosted_verification.json")
    records = json.loads(path.read_text()) if path.exists() else []
    if records and any(r["revision"] != revision for r in records):
        raise RuntimeError("Saved checks use a different revision")
    complete = {r["case"] for r in records}
    cases = [
        ("original", {}),
        (
            "original_repetition",
            dict(remasking_strategy="PMI Viterbi + Repetition Penalty"),
        ),
    ]
    if not args.baseline:
        props = [c.get("props", {}) for c in client.config["components"]]
        for label in [
            "Sample bigram-guided sequences",
            "Count every candidate bigram occurrence",
        ]:
            checkbox = next(p for p in props if p.get("label") == label)
            assert checkbox["value"] is False and checkbox.get("visible", True)
        cases += [
            ("sample", dict(sequence_sampling=True)),
            ("sample_repeat_seed", dict(sequence_sampling=True)),
            ("sample_other_seed", dict(sequence_sampling=True, generation_seed=5678)),
            (
                "candidate_counts",
                dict(
                    remasking_strategy="PMI Viterbi + Repetition Penalty",
                    count_all_candidate_bigrams=True,
                    repetition_penalty_strength=10.0,
                ),
            ),
            (
                "sample_candidate_counts",
                dict(
                    remasking_strategy="PMI Viterbi + Repetition Penalty",
                    count_all_candidate_bigrams=True,
                    sequence_sampling=True,
                    repetition_penalty_strength=10.0,
                ),
            ),
            (
                "sample_candidate_counts_apd",
                dict(
                    remasking_strategy="PMI Viterbi + Repetition Penalty",
                    count_all_candidate_bigrams=True,
                    sequence_sampling=True,
                    repetition_penalty_strength=10.0,
                    adaptive_parallel_decoding=True,
                    num_steps=8,
                ),
            ),
        ]
    for name, overrides in cases:
        if name in complete:
            continue
        settings = dict(
            question="What do you know about Amsterdam?",
            system_prompt="You are a helpful assistant.",
            max_new_tokens=32,
            num_steps=1,
            block_length=32,
            temperature=2.0,
            top_k=100,
            pause_per_step=0.0,
            trajectory_color_mode="No coloring",
            remasking_strategy="Bigram Viterbi",
            revisable_tokens=False,
            ar_check_interval=4,
            delay_eos_eot=False,
            early_stopping=False,
            generation_seed=1234,
            measure_decoding=True,
            repetition_penalty_strength=1.0,
            adaptive_parallel_decoding=False,
        )
        settings.update(overrides)
        started = time.perf_counter()
        job = client.submit(**settings, api_name="/generate")
        status, rendered = job.result()
        assert "masked at iteration" not in rendered
        match = re.search(r"<textarea[^>]*>(.*?)</textarea>", rendered, re.S)
        assert match
        text = unescape(match[1])
        metrics = json.loads(status.split("Inference metrics: ")[1].splitlines()[0])
        assert (
            metrics["denoising_forward_passes"]
            == len(job.outputs())
            <= settings["num_steps"]
        )
        record = dict(
            case=name,
            revision=revision,
            settings=settings,
            text=text,
            metrics=metrics,
            client_seconds=time.perf_counter() - started,
        )
        records.append(record)
        path.write_text(json.dumps(records, indent=2) + "\n")
        print(json.dumps(record), flush=True)
    if not args.baseline:
        before = {r["case"]: r for r in json.loads((OUT / "before.json").read_text())}
        after = {r["case"]: r for r in records}
        for name in before:
            assert (
                after[name]["text"] == before[name]["text"]
            ), f"OFF regression: {name}"
        assert after["sample"]["text"] == after["sample_repeat_seed"]["text"]
        print(
            "All live completeness, forward-budget, OFF regression and seed checks passed.",
            flush=True,
        )


if __name__ == "__main__":
    main()
