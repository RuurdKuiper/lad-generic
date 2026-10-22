#!/usr/bin/env python3
"""Smoke-test LAD sampling and PMI Viterbi, with and without re-noising."""
import argparse
import json
import os
from pathlib import Path
import re
import time

from dotenv import load_dotenv
from gradio_client import Client
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/bigram/lad_space/hosted_verification.json")
    parser.add_argument("--repetition-only", action="store_true", help="Compare original PMI, new gamma=0, and new gamma=1 without re-noising")
    parser.add_argument("--iterations", type=int, default=4)
    parser.add_argument("--include-gamma-ten", action="store_true", help="Also check the repetition decoder at gamma=10")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    api = HfApi()
    revision = api.repo_info("Ruurd/lad", repo_type="space").sha
    client = Client("Ruurd/lad", token=os.getenv("HF_TOKEN"), verbose=False)
    interface = client.view_api(return_format="dict", print_info=False)
    parameters = interface["named_endpoints"]["/on_generate"]["parameters"]
    if "decoding_strategy" not in {p["parameter_name"] for p in parameters}:
        raise RuntimeError("The updated LAD interface is not running yet")
    if args.repetition_only and "repetition_penalty_strength" not in {p["parameter_name"] for p in parameters}:
        raise RuntimeError("The repetition-penalty interface is not running yet")
    records = []
    configurations = [
        ("sampling_no_noise", "Sampling", 0., False, False),
        ("viterbi_no_noise", "PMI Viterbi", 0., False, False),
        ("viterbi_confidence_noise", "PMI Viterbi", .5, True, False),
        ("viterbi_confidence_permanent", "PMI Viterbi", .5, True, True),
        ("viterbi_uniform_permanent", "PMI Viterbi", .5, False, True),
    ]
    if args.repetition_only:
        configurations = [
            ("reference_pmi", "PMI Viterbi", 0., False, False),
            ("repetition_zero", "PMI Viterbi + Repetition Penalty", 0., False, False),
            ("repetition_one", "PMI Viterbi + Repetition Penalty", 0., False, False),
        ]
        if args.include_gamma_ten:
            configurations.append(("repetition_ten", "PMI Viterbi + Repetition Penalty", 0., False, False))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for name, strategy, noise, guided, permanent in configurations:
        settings = dict(
            question="What do you know about Amsterdam?", multiturn_on=False,
            max_it=args.iterations, pause_length=0, eos_bias=0, sharpness=1, noise_start=noise,
            use_confidence_noising=guided, use_permanent_unmasking=permanent,
            noise_clipping=.01, top_p=1, top_k=16 if strategy.startswith("PMI Viterbi") else 3,
            added_tokens=64, context_window=128, decoding_strategy=strategy,
            temperature=2. if strategy.startswith("PMI Viterbi") else 1.,
        )
        if args.repetition_only:
            settings["repetition_penalty_strength"] = 0. if name == "repetition_zero" else 10. if name == "repetition_ten" else 1.
        start = time.monotonic()
        job = client.submit(**settings, api_name="/on_generate")
        result = job.result()
        outputs = job.outputs()
        prediction_steps = []
        for output in outputs:
            text = output if isinstance(output, str) else output[-1]
            match = re.search(r"Iteration (\d+)/\d+ \(after generation\)", text)
            if match:
                prediction_steps.append(int(match[1]))
        if not isinstance(result, str) or "Final Output" not in result:
            raise RuntimeError(f"Missing final output for {name}")
        record = dict(name=name, settings=settings, elapsed_seconds=time.monotonic() - start,
                      prediction_steps=prediction_steps, output=result)
        records.append(record)
        args.output.write_text(json.dumps(dict(space="Ruurd/lad", revision=revision, runs=records), indent=2) + "\n")
        print(json.dumps(record), flush=True)
    if args.repetition_only:
        if records[0]["output"] != records[1]["output"]:
            raise AssertionError("Gamma=0 did not reproduce the original PMI result")
        print("Verified: gamma=0 exactly matches the original PMI output.", flush=True)


if __name__ == "__main__":
    main()
