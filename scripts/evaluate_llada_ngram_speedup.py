#!/usr/bin/env python3
"""Matched hosted speed/output checks for a trigram implementation and top-k."""

import argparse
import hashlib
from html import unescape
import json
import os
import re
import time

from evaluate_llada_full_study import ROOT, shared_settings

OUT = ROOT / "artifacts/bigram/llada_ngram_speed"
TASKS = ["amsterdam", "open_14", "balanced", "binary_search", "mean", "pipes"]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--stage",
        choices=["before", "after_k16", "after_k8", "after_host_k16", "after_host_k8"],
        required=True,
    )
    args = p.parse_args()
    from dotenv import load_dotenv
    from gradio_client import Client
    from huggingface_hub import HfApi

    load_dotenv(ROOT / ".env")
    api = HfApi(token=os.getenv("HF_TOKEN"))
    plan = json.loads((OUT / "deployment_plan.json").read_text())
    space = plan["space"]
    revision = api.repo_info(space, repo_type="space").sha
    deployment = (
        "deployment_host.json"
        if args.stage.startswith("after_host")
        else "deployment.json"
    )
    expected = (
        plan["parent_revision"]
        if args.stage == "before"
        else json.loads((OUT / deployment).read_text())["revision"]
    )
    if revision != expected:
        raise RuntimeError("Space revision differs from benchmark stage")
    study = json.loads(
        (ROOT / "artifacts/bigram/llada_ngram_settings_full/manifest.json").read_text()
    )
    tasks = {t["id"]: t for t in study["tasks"]}
    k = 8 if args.stage.endswith("_k8") else 16
    cases = [(task, n, 0) for n in [8, 32, 64] for task in TASKS]
    # Two extra repeats for one prompt/domain at32 NFE; three timed runs total.
    cases += [
        (task, 32, trial)
        for trial in [1, 2]
        for task in ["amsterdam", "balanced", "mean"]
    ]
    path = OUT / (args.stage + ".jsonl")
    rows = (
        [json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []
    )
    done = {(r["task"], r["steps"], r["trial"]) for r in rows}
    assert all(r["revision"] == revision for r in rows)
    client = Client(space, token=api.token, verbose=False)
    shared = dict(
        shared_settings(),
        remasking_strategy="Bigram Viterbi",
        ngram_guidance="Expanded bigram + trigram",
        top_k=k,
        sequence_sampling=False,
    )
    client.predict(
        **dict(
            shared,
            question="Reply with a short greeting.",
            num_steps=1,
            max_new_tokens=16,
            block_length=16,
            delay_eos_eot=False,
            bigram_eos_delay_penalty=1.0,
        ),
        api_name="/generate",
    )
    reference = {}
    if args.stage != "before":
        reference = {
            (r["task"], r["steps"], r["trial"]): r
            for r in map(json.loads, (OUT / "before.jsonl").read_text().splitlines())
        }
    for task, n, trial in cases:
        if (task, n, trial) in done:
            continue
        options = dict(
            shared,
            question=tasks[task]["prompt"],
            num_steps=n,
            delay_eos_eot=tasks[task]["category"] == "open",
            bigram_eos_delay_penalty=10.0 if tasks[task]["category"] == "open" else 1.0,
        )
        if api.repo_info(space, repo_type="space").sha != revision:
            raise RuntimeError("Live Space changed during benchmark")
        start = time.perf_counter()
        job = client.submit(**options, api_name="/generate")
        status, rendered = job.result()
        wall = time.perf_counter() - start
        text = unescape(
            re.search(r"<textarea[^>]*>(.*?)</textarea>", rendered, re.S)[1]
        )
        inf = json.loads(status.split("Inference metrics: ")[1].splitlines()[0])
        dec = json.loads(status.split("Decoding metrics: ")[1].splitlines()[0])
        assert (
            inf["denoising_forward_passes"]
            == dec["selector_calls"]
            == len(job.outputs())
            == n
        )
        assert "masked at iteration" not in rendered
        row = dict(
            stage=args.stage,
            task=task,
            category=tasks[task]["category"],
            steps=n,
            trial=trial,
            revision=revision,
            settings=options,
            text=text,
            sha256=hashlib.sha256(text.encode()).hexdigest(),
            inference=inf,
            decoding=dec,
            client_wall_seconds=wall,
        )
        if reference:
            ref = reference[(task, n, trial)]
            row["same_as_before"] = row["sha256"] == ref["sha256"]
        with path.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(
            json.dumps(
                dict(
                    stage=args.stage,
                    task=task,
                    nfe=n,
                    trial=trial,
                    server_ms=inf["elapsed_ms"],
                    selector_ms=dec["selector_ms"],
                    same_as_before=row.get("same_as_before"),
                )
            ),
            flush=True,
        )
        if args.stage.endswith("_k16") and not row["same_as_before"]:
            raise RuntimeError(
                "Exact-output regression; investigate before continuing or changing top-k"
            )
    print(
        json.dumps(dict(stage=args.stage, complete=True, runs=len(cases))), flush=True
    )


if __name__ == "__main__":
    main()
