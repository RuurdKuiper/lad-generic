#!/usr/bin/env python3
"""Compare the original decoder and optional repetition penalty on two Spaces."""
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/bigram/repetition_rollout")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    api = HfApi()
    records = []
    output = args.output / ("before.json" if args.baseline else "hosted_verification.json")
    before = {} if args.baseline else {r["space"]: r for r in json.loads((args.output / "before.json").read_text())}
    for space in SPACES:
        client = Client(space, token=os.getenv("HF_TOKEN"), verbose=False)
        revision = api.repo_info(space, repo_type="space").sha
        if not args.baseline:
            api_info = client.view_api(return_format="dict", print_info=False)
            params = api_info["named_endpoints"]["/generate"]["parameters"]
            if "repetition_penalty_strength" not in {p["parameter_name"] for p in params}:
                raise RuntimeError(f"Updated interface is not running: {space}")
            props = [c.get("props", {}) for c in client.config["components"]]
            gamma = next(p for p in props if p.get("label") == "Repetition penalty strength (γ)")
            assert gamma["value"] == 1 and gamma["visible"] is False
            assert next(p for p in props if p.get("label") == "Bigram ending delay strength")["value"] == 10
            assert any(p.get("label") == "Reproducible evaluation" for p in props)
            assert client.predict("PMI Viterbi + Repetition Penalty", api_name="/update_repetition_control")["visible"]
        cases = [("original", "Bigram Viterbi", None)]
        if not args.baseline:
            cases += [("gamma_zero", "PMI Viterbi + Repetition Penalty", 0.),
                      ("gamma_one", "PMI Viterbi + Repetition Penalty", 1.),
                      ("gamma_ten", "PMI Viterbi + Repetition Penalty", 10.)]
        originals = {}
        for name, strategy, gamma in cases:
            settings = dict(question="What do you know about Amsterdam?", system_prompt="You are a helpful assistant.",
                max_new_tokens=32, num_steps=4, block_length=16, temperature=2., top_k=16,
                pause_per_step=0., trajectory_color_mode="No coloring", remasking_strategy=strategy,
                revisable_tokens=False, ar_check_interval=4, delay_eos_eot=True, early_stopping=False,
                generation_seed=1234, measure_decoding=True)
            if gamma is not None:
                settings["repetition_penalty_strength"] = gamma
            start = time.monotonic()
            status, rendered = client.predict(**settings, api_name="/generate")
            match = re.search(r"<textarea[^>]*>(.*?)</textarea>", rendered, re.S)
            if match is None:
                raise RuntimeError(f"Missing plain-text output: {space}/{name}")
            text = unescape(match[1])
            metrics = json.loads(status.split("Decoding metrics: ")[-1])
            assert metrics["selector_calls"] == 4
            record = dict(space=space, revision=revision, case=name, settings=settings,
                elapsed_seconds=time.monotonic() - start, text=text, status=status, metrics=metrics)
            if name == "original":
                originals[space] = text
                if not args.baseline:
                    assert text == before[space]["text"], f"Original decoder changed: {space}"
            if name == "gamma_zero":
                assert text == originals[space], f"Gamma zero mismatch: {space}"
            records.append(record)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(records, indent=2) + "\n")
            print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
