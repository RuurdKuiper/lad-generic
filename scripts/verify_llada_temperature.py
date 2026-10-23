#!/usr/bin/env python3
"""Check separate controls and default-equivalence on the hosted LLaDA Space."""

from html import unescape
import json
import os
from pathlib import Path
import re

from dotenv import load_dotenv
from gradio_client import Client
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/bigram/llada_temperature"
SPACE = "Ruurd/llada-8b-instruct"


def main():
    load_dotenv(ROOT / ".env")
    client = Client(SPACE, token=os.getenv("HF_TOKEN"), verbose=False)
    revision = HfApi().repo_info(SPACE, repo_type="space").sha
    props = [c.get("props", {}) for c in client.config["components"]]
    weight = next(p for p in props if p.get("label") == "Bigram weight")
    assert (
        weight["minimum"] == 0
        and weight["maximum"] == 5
        and weight["value"] == 1
        and weight.get("visible", True)
    )
    assert next(p for p in props if p.get("label") == "Temperature")["value"] == 1
    old = {
        r["case"]: r
        for r in json.loads(
            (
                ROOT
                / "artifacts/bigram/llada_sequence_sampling/hosted_verification.json"
            ).read_text()
        )
    }
    path = OUT / "hosted_verification.json"
    records = json.loads(path.read_text()) if path.exists() else []
    if any(r["revision"] != revision for r in records):
        raise RuntimeError("Saved results use different code")
    complete = {r["case"] for r in records}
    cases = [
        ("default_viterbi", {}, "original"),
        ("default_sampler", dict(sequence_sampling=True), "sample"),
        (
            "sampler_zero_temperature",
            dict(sequence_sampling=True, temperature=0.0),
            "original",
        ),
        ("viterbi_temperature_zero", dict(temperature=0.0), "original"),
        (
            "sample_other_seed",
            dict(sequence_sampling=True, generation_seed=5678),
            "sample_other_seed",
        ),
        ("sample_low_temperature", dict(sequence_sampling=True, temperature=0.5), None),
        ("sample_weight_zero", dict(sequence_sampling=True, bigram_weight=0.0), None),
        ("sample_weight_five", dict(sequence_sampling=True, bigram_weight=5.0), None),
        (
            "expected_penalty",
            dict(remasking_strategy="PMI Viterbi + Repetition Penalty"),
            "original_repetition",
        ),
    ]
    for name, overrides, reference in cases:
        if name in complete:
            continue
        settings = dict(old["original"]["settings"], temperature=1.0, bigram_weight=1.0)
        settings.update(overrides)
        job = client.submit(**settings, api_name="/generate")
        status, rendered = job.result()
        assert "masked at iteration" not in rendered
        text = unescape(
            re.search(r"<textarea[^>]*>(.*?)</textarea>", rendered, re.S)[1]
        )
        metrics = json.loads(status.split("Inference metrics: ")[1].splitlines()[0])
        assert metrics["denoising_forward_passes"] == len(job.outputs()) == 1
        if reference:
            assert (
                text == old[reference]["text"]
            ), f"Default-equivalence mismatch in {name}: {text}"
        record = dict(
            case=name, revision=revision, settings=settings, text=text, metrics=metrics
        )
        records.append(record)
        path.write_text(json.dumps(records, indent=2) + "\n")
        print(json.dumps(record), flush=True)
    print(
        "Hosted weight range, temperature-zero, default-equivalence, completeness and forward-count checks passed."
    )


if __name__ == "__main__":
    main()
