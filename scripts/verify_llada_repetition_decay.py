#!/usr/bin/env python3
"""Live constant/fading repetition comparisons at short and longer NFE budgets."""

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
OUT = ROOT / "artifacts/bigram/llada_repetition_decay"


def main():
    load_dotenv(ROOT / ".env")
    client = Client(SPACE, token=os.getenv("HF_TOKEN"), verbose=False)
    revision = HfApi().repo_info(SPACE, repo_type="space").sha
    props = [c.get("props", {}) for c in client.config["components"]]
    assert (
        next(
            p
            for p in props
            if p.get("label") == "Fade repetition penalty over early iterations"
        )["value"]
        is True
    )
    prior = {
        r["case"]: r
        for r in json.loads(
            (
                ROOT / "artifacts/bigram/llada_repetition_risk/hosted_verification.json"
            ).read_text()
        )
    }
    path = OUT / "hosted_verification.json"
    records = json.loads(path.read_text()) if path.exists() else []
    if any(r["revision"] != revision for r in records):
        raise RuntimeError("Saved tests use another revision")
    complete = {r["case"] for r in records}
    cases = [
        ("constant_one_step", dict(decay_repetition_penalty=False), "risk_viterbi"),
        ("fade_one_step", dict(decay_repetition_penalty=True), "risk_viterbi"),
        (
            "constant_sampling_apd8",
            dict(
                sequence_sampling=True,
                num_steps=8,
                adaptive_parallel_decoding=True,
                decay_repetition_penalty=False,
            ),
            "risk_sampling_apd",
        ),
        (
            "fade_sampling_apd8",
            dict(
                sequence_sampling=True,
                num_steps=8,
                adaptive_parallel_decoding=True,
                decay_repetition_penalty=True,
            ),
            None,
        ),
        (
            "constant_sampling16",
            dict(sequence_sampling=True, num_steps=16, decay_repetition_penalty=False),
            None,
        ),
        (
            "fade_sampling16",
            dict(sequence_sampling=True, num_steps=16, decay_repetition_penalty=True),
            None,
        ),
        (
            "constant_viterbi16",
            dict(num_steps=16, decay_repetition_penalty=False),
            None,
        ),
        ("fade_viterbi16", dict(num_steps=16, decay_repetition_penalty=True), None),
    ]
    for name, overrides, reference in cases:
        if name in complete:
            continue
        settings = dict(prior["risk_viterbi"]["settings"])
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
        if not settings.get("adaptive_parallel_decoding"):
            assert metrics["denoising_forward_passes"] == settings["num_steps"]
        if reference:
            assert text == prior[reference]["text"], f"Compatibility mismatch: {name}"
        record = dict(
            case=name, revision=revision, settings=settings, text=text, metrics=metrics
        )
        records.append(record)
        path.write_text(json.dumps(records, indent=2) + "\n")
        print(json.dumps(record), flush=True)
    print(
        "All live fade/default/constant/single-step/APD/forward-budget checks passed."
    )


if __name__ == "__main__":
    main()
