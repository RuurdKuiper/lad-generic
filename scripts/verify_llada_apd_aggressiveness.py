#!/usr/bin/env python3
"""Live APD threshold/forward-count checks, including legacy-zero equivalence."""

from html import unescape
import json
import os
from pathlib import Path
import re

from dotenv import load_dotenv
from gradio_client import Client
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
SPACE = "Ruurd/llada-8b-instruct"
OUT = ROOT / "artifacts/bigram/llada_apd_aggressiveness"


def main():
    load_dotenv(ROOT / ".env")
    client = Client(SPACE, token=os.getenv("HF_TOKEN"), verbose=False)
    revision = HfApi().repo_info(SPACE, repo_type="space").sha
    props = [c.get("props", {}) for c in client.config["components"]]
    slider = next(p for p in props if p.get("label") == "APD aggressiveness")
    assert slider["value"] == 0 and slider["minimum"] == 0 and slider["maximum"] == 1
    assert slider.get("visible", True) and slider["interactive"] is False
    prior = {
        r["case"]: r
        for r in json.loads(
            (
                ROOT
                / "artifacts/bigram/llada_repetition_decay/hosted_verification.json"
            ).read_text()
        )
    }
    path = OUT / "hosted_verification.json"
    records = json.loads(path.read_text()) if path.exists() else []
    if any(r["revision"] != revision for r in records):
        raise RuntimeError("Saved checks use a different revision")
    complete = {r["case"] for r in records}
    cases = [
        (
            "apd_off_ignores_control",
            dict(prior["fade_viterbi16"]["settings"], apd_aggressiveness=1.0),
            "fade_viterbi16",
        ),
        (
            "zero_preserves_previous",
            dict(prior["fade_sampling_apd8"]["settings"], apd_aggressiveness=0.0),
            "fade_sampling_apd8",
        ),
    ]
    for method in ["standard", "risk_sampling"]:
        for strength in [0.0, 0.5, 0.9, 1.0]:
            settings = dict(
                prior["fade_viterbi16"]["settings"],
                top_k=16,
                adaptive_parallel_decoding=True,
                apd_aggressiveness=strength,
                sequence_sampling=method == "risk_sampling",
            )
            if method == "standard":
                settings["remasking_strategy"] = "Confidence-guided"
            cases.append((f"{method}_{strength}", settings, None))
    for name, settings, reference in cases:
        if name in complete:
            continue
        job = client.submit(**settings, api_name="/generate")
        status, rendered = job.result()
        assert "masked at iteration" not in rendered
        text = unescape(
            re.search(r"<textarea[^>]*>(.*?)</textarea>", rendered, re.S)[1]
        )
        metrics = json.loads(status.split("Inference metrics: ")[1].splitlines()[0])
        forwards = metrics["denoising_forward_passes"]
        assert forwards == len(job.outputs()) <= settings["num_steps"]
        if reference:
            assert text == prior[reference]["text"], f"Compatibility regression: {name}"
        if (
            settings["adaptive_parallel_decoding"]
            and settings["apd_aggressiveness"] == 1.0
        ):
            assert forwards == 1
        record = dict(
            case=name,
            revision=revision,
            settings=settings,
            text=text,
            metrics=metrics,
            status=status,
        )
        records.append(record)
        path.write_text(json.dumps(records, indent=2) + "\n")
        print(json.dumps(record), flush=True)
    print(
        "All slider/default/OFF/zero/completeness/forward-budget/max-aggression checks passed."
    )


if __name__ == "__main__":
    main()
