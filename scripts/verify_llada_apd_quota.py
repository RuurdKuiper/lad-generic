#!/usr/bin/env python3
"""Check live per-step APD minimums from streamed commitment counts."""

from html import unescape
import json
import math
import os
from pathlib import Path
import re

from dotenv import load_dotenv
from gradio_client import Client
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
SPACE = "Ruurd/llada-8b-instruct"
OUT = ROOT / "artifacts/bigram/llada_apd_quota"


def main():
    load_dotenv(ROOT / ".env")
    client = Client(SPACE, token=os.getenv("HF_TOKEN"), verbose=False)
    revision = HfApi().repo_info(SPACE, repo_type="space").sha
    prior = {
        r["case"]: r
        for r in json.loads(
            (
                ROOT
                / "artifacts/bigram/llada_apd_aggressiveness/hosted_verification.json"
            ).read_text()
        )
    }
    path = OUT / "hosted_verification.json"
    records = json.loads(path.read_text()) if path.exists() else []
    if any(r["revision"] != revision for r in records):
        raise RuntimeError("Saved checks use another revision")
    complete = {r["case"] for r in records}
    cases = [
        (
            "apd_off_unchanged",
            prior["apd_off_ignores_control"]["settings"],
            "apd_off_ignores_control",
        )
    ]
    base = dict(
        prior["risk_sampling_0.0"]["settings"],
        max_new_tokens=64,
        num_steps=16,
        block_length=64,
    )
    for name, changes in [
        ("standard", dict(remasking_strategy="Confidence-guided")),
        (
            "standard_aggressive",
            dict(remasking_strategy="Confidence-guided", apd_aggressiveness=0.9),
        ),
        ("risk_viterbi", dict(sequence_sampling=False)),
        ("risk_sampling", {}),
        ("risk_sampling_aggressive", dict(apd_aggressiveness=0.5)),
        ("uneven_length", dict(max_new_tokens=65, block_length=65)),
        ("uneven_blocks", dict(max_new_tokens=65, block_length=32)),
    ]:
        cases.append((name, dict(base, **changes), None))
    for name, settings, reference in cases:
        if name in complete:
            continue
        job = client.submit(**settings, api_name="/generate")
        status, rendered = job.result()
        assert "masked at iteration" not in rendered
        frames = job.outputs()
        metrics = json.loads(status.split("Inference metrics: ")[1].splitlines()[0])
        assert (
            len(frames) == metrics["denoising_forward_passes"] <= settings["num_steps"]
        )
        text = unescape(
            re.search(r"<textarea[^>]*>(.*?)</textarea>", rendered, re.S)[1]
        )
        commits = []
        quotas = []
        if settings["adaptive_parallel_decoding"]:
            length = settings["max_new_tokens"]
            block = settings["block_length"]
            lengths = [min(block, length - start) for start in range(0, length, block)]
            budget, extra = divmod(settings["num_steps"], len(lengths))
            block_quotas = [
                math.ceil(n / (budget + int(i < extra))) for i, n in enumerate(lengths)
            ]
            index = 0
            pending = lengths[0]
            for frame_status, _ in frames:
                count = int(re.search(r"committed (\d+)", frame_status)[1])
                quota = block_quotas[index]
                assert (
                    min(quota, pending) <= count <= pending
                ), f"Quota violation: {name}: {count} < {quota}"
                commits.append(count)
                quotas.append(quota)
                pending -= count
                if pending == 0:
                    index += 1
                    if index < len(lengths):
                        pending = lengths[index]
            assert index == len(lengths) and pending == 0
        if reference:
            assert text == prior[reference]["text"], "APD OFF regression"
        record = dict(
            case=name,
            revision=revision,
            settings=settings,
            text=text,
            commits=commits,
            quotas=quotas,
            metrics=metrics,
        )
        records.append(record)
        path.write_text(json.dumps(records, indent=2) + "\n")
        print(json.dumps(record), flush=True)
    print(
        "All per-step quota, completion, unequal-block, forward-budget and APD-OFF checks passed."
    )


if __name__ == "__main__":
    main()
