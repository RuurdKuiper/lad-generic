#!/usr/bin/env python3
"""Live optional-risk, zero-gamma, OFF equivalence and APD smoke checks."""

from html import unescape
import json
import os
from pathlib import Path
import re

from dotenv import load_dotenv
from gradio_client import Client
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/bigram/llada_repetition_risk"
SPACE = "Ruurd/llada-8b-instruct"


def main():
    load_dotenv(ROOT / ".env")
    client = Client(SPACE, token=os.getenv("HF_TOKEN"), verbose=False)
    revision = HfApi().repo_info(SPACE, repo_type="space").sha
    props = [c.get("props", {}) for c in client.config["components"]]
    checkbox = next(p for p in props if p.get("label") == "Repetition-risk penalty")
    assert checkbox["value"] is False and checkbox.get("visible", True)
    old = {
        r["case"]: r
        for r in json.loads(
            (
                ROOT / "artifacts/bigram/llada_temperature/hosted_verification.json"
            ).read_text()
        )
    }
    path = OUT / "hosted_verification.json"
    records = json.loads(path.read_text()) if path.exists() else []
    if any(r["revision"] != revision for r in records):
        raise RuntimeError("Saved results use another code revision")
    complete = {r["case"] for r in records}
    cases = [
        ("risk_off_viterbi", {}, "default_viterbi"),
        ("risk_off_sampling", dict(sequence_sampling=True), "default_sampler"),
        (
            "risk_off_expected_penalty",
            dict(remasking_strategy="PMI Viterbi + Repetition Penalty"),
            "expected_penalty",
        ),
        (
            "risk_zero_gamma_viterbi",
            dict(repetition_risk_penalty=True, repetition_penalty_strength=0.0),
            "default_viterbi",
        ),
        (
            "risk_zero_gamma_sampling",
            dict(
                repetition_risk_penalty=True,
                repetition_penalty_strength=0.0,
                sequence_sampling=True,
            ),
            "default_sampler",
        ),
        ("risk_viterbi", dict(repetition_risk_penalty=True), None),
        (
            "risk_sampling",
            dict(repetition_risk_penalty=True, sequence_sampling=True),
            None,
        ),
        (
            "risk_sampling_apd",
            dict(
                repetition_risk_penalty=True,
                sequence_sampling=True,
                adaptive_parallel_decoding=True,
                num_steps=8,
            ),
            None,
        ),
        (
            "risk_viterbi_gamma10",
            dict(repetition_risk_penalty=True, repetition_penalty_strength=10.0),
            None,
        ),
    ]
    for name, overrides, reference in cases:
        if name in complete:
            continue
        settings = dict(old["default_viterbi"]["settings"])
        if "risk_" in name and not name.startswith("risk_off"):
            settings["remasking_strategy"] = "PMI Viterbi + Repetition Penalty"
        settings.update(overrides)
        job = client.submit(**settings, api_name="/generate")
        status, rendered = job.result()
        assert "masked at iteration" not in rendered
        text = unescape(
            re.search(r"<textarea[^>]*>(.*?)</textarea>", rendered, re.S)[1]
        )
        metrics = json.loads(status.split("Inference metrics: ")[1].splitlines()[0])
        assert (
            metrics["denoising_forward_passes"]
            == len(job.outputs())
            <= settings["num_steps"]
        )
        if reference:
            assert (
                text == old[reference]["text"]
            ), f"OFF/zero-strength regression: {name}"
        record = dict(
            case=name, revision=revision, settings=settings, text=text, metrics=metrics
        )
        records.append(record)
        path.write_text(json.dumps(records, indent=2) + "\n")
        print(json.dumps(record), flush=True)
    print("All risk/OFF/zero-strength/APD/completeness/forward-budget checks passed.")


if __name__ == "__main__":
    main()
