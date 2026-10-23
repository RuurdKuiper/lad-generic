#!/usr/bin/env python3
"""Add a matched sampled BG+TG or temperature-zero confidence study arm."""

import argparse
import hashlib
from html import unescape
import json
import os
import re
import time

from evaluate_llada_full_study import OUT, ROOT, read_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-runs", type=int)
    parser.add_argument(
        "--configuration",
        choices=["trigram_sample", "confidence_zero"],
        default="trigram_sample",
    )
    args = parser.parse_args()
    zero = args.configuration == "confidence_zero"
    method = args.configuration
    base_method = "confidence" if zero else "trigram"
    phase = "confidence_zero" if zero else "sample"
    from dotenv import load_dotenv
    from gradio_client import Client
    from huggingface_hub import HfApi

    load_dotenv(ROOT / ".env")
    token = os.getenv("HF_TOKEN")
    api = HfApi(token=token)
    manifest = json.loads((OUT / "manifest.json").read_text())
    snapshot = json.loads((OUT / "stop_snapshot.json").read_text())
    assert (
        hashlib.sha256((OUT / "main/results.jsonl").read_bytes()).hexdigest()
        == snapshot["results_sha256"]
    )
    source = [
        r
        for r in read_rows(OUT / "matched_results.jsonl")
        if r["method"] == base_method
    ]
    assert len(source) == 282 and len({(r["task"], r["steps"]) for r in source}) == 282
    revision = api.repo_info(manifest["space"], repo_type="space").sha
    if revision != manifest["revision"]:
        raise RuntimeError(
            f"Space revision changed: expected {manifest['revision']}, found {revision}"
        )
    amendment = dict(
        configuration="trigram_sample",
        base_method="trigram",
        total=282,
        source="matched_results.jsonl",
        source_sha256=hashlib.sha256(
            (OUT / "matched_results.jsonl").read_bytes()
        ).hexdigest(),
        revision=revision,
        changes=dict(sequence_sampling=True, temperature=0.7),
        repetition_penalty=False,
        seed=42,
        scope="User-requested single additional arm, matched to all282 retained prompt/NFE cases; replaces the cancelled selected720-run follow-up.",
        selection="User chose BG+TG after inspecting main results; exploratory paired comparison, no held-out selection claim.",
    )
    if zero:
        prior = json.loads((OUT / "sample/run_state.json").read_text())
        if not prior.get("report_complete"):
            raise RuntimeError(
                "Finish sampled BG+TG generation and report before confidence-zero"
            )
        frozen_prior = OUT / "pre_confidence_zero_results.jsonl"
        if not frozen_prior.exists():
            assert len(read_rows(OUT / "combined_results.jsonl")) == 1692
            frozen_prior.write_bytes((OUT / "combined_results.jsonl").read_bytes())
        amendment = dict(
            configuration=method,
            base_method=base_method,
            total=282,
            source="matched_results.jsonl",
            source_sha256=hashlib.sha256(
                (OUT / "matched_results.jsonl").read_bytes()
            ).hexdigest(),
            revision=revision,
            changes=dict(temperature=0.0),
            seed=42,
            repetition_penalty=False,
            scope="User-requested confidence-guided temperature-zero arm on all282 retained cases; all other settings unchanged.",
            selection="Requested after inspecting earlier arms; exploratory paired comparison, one fixed seed.",
            prior_six_method_results_sha256=hashlib.sha256(
                frozen_prior.read_bytes()
            ).hexdigest(),
        )
    path = OUT / (
        "confidence_zero_amendment.json" if zero else "sampling_amendment.json"
    )
    if path.exists() and json.loads(path.read_text()) != amendment:
        raise RuntimeError("Sampling amendment differs; audit before resuming")
    path.write_text(json.dumps(amendment, indent=2) + "\n")
    folder = OUT / phase
    folder.mkdir(exist_ok=True)
    result = folder / "results.jsonl"
    completed = {r["key"] for r in read_rows(result)}
    expected = {f"{r['task']}/{r['steps']}/{method}" for r in source}
    if not completed <= expected:
        raise RuntimeError(
            "Sampling folder contains an unexpected configuration or case"
        )
    if completed == expected:
        print(
            json.dumps(dict(completed=282, total=282, status="already_complete")),
            flush=True,
        )
        return
    client = Client(manifest["space"], token=token, verbose=False)
    # One excluded warm-up for precisely the added decoding path.
    warmup = dict(
        source[0]["settings"],
        question="Reply with a short greeting.",
        max_new_tokens=16,
        block_length=16,
        num_steps=1,
        sequence_sampling=not zero,
        temperature=0.0 if zero else 0.7,
    )
    client.predict(**warmup, api_name="/generate")
    blocked = set()
    failed = []
    new = 0
    for original in source:
        key = f"{original['task']}/{original['steps']}/{method}"
        if key in completed or original["steps"] in blocked:
            continue
        if args.max_runs is not None and new >= args.max_runs:
            break
        options = (
            dict(original["settings"], temperature=0.0)
            if zero
            else dict(original["settings"], sequence_sampling=True, temperature=0.7)
        )
        assert options["remasking_strategy"] == (
            "Confidence-guided" if zero else "Bigram Viterbi"
        )
        assert options["ngram_guidance"] == (
            "Original bigram" if zero else "Expanded bigram + trigram"
        )
        assert not options["count_all_candidate_bigrams"]
        if api.repo_info(manifest["space"], repo_type="space").sha != revision:
            raise RuntimeError("Live Space revision changed")
        for attempt in range(2):
            try:
                started = time.perf_counter()
                job = client.submit(**options, api_name="/generate")
                status, rendered = job.result()
                elapsed = time.perf_counter() - started
                match = re.search(r"<textarea[^>]*>(.*?)</textarea>", rendered, re.S)
                if match is None:
                    raise RuntimeError("Missing final output")
                text = unescape(match[1])
                metrics = json.loads(
                    status.split("Inference metrics: ")[1].splitlines()[0]
                )
                decoding = (
                    json.loads(status.split("Decoding metrics: ")[1].splitlines()[0])
                    if "Decoding metrics: " in status
                    else None
                )
                steps = original["steps"]
                if (
                    metrics["denoising_forward_passes"] != steps
                    or len(job.outputs()) != steps
                    or (decoding and decoding["selector_calls"] != steps)
                ):
                    raise RuntimeError("NFE/selector mismatch")
                if "masked at iteration" in rendered:
                    raise RuntimeError("Unresolved masked output")
                row = dict(
                    original,
                    key=key,
                    method=method,
                    base_method=base_method,
                    phase=phase,
                    settings=options,
                    text=text,
                    status=status,
                    inference=metrics,
                    decoding=decoding,
                    client_wall_seconds=elapsed,
                    sha256=hashlib.sha256(text.encode()).hexdigest(),
                )
                with result.open("a") as f:
                    f.write(json.dumps(row) + "\n")
                completed.add(key)
                new += 1
                print(
                    json.dumps(
                        dict(
                            completed=len(completed),
                            total=282,
                            key=key,
                            server_ms=metrics["elapsed_ms"],
                        )
                    ),
                    flush=True,
                )
                break
            except Exception as exc:
                error = dict(
                    key=key, attempt=attempt + 1, error=str(exc), at=time.time()
                )
                with (folder / "errors.jsonl").open("a") as f:
                    f.write(json.dumps(error) + "\n")
                print(json.dumps(error), flush=True)
                if "quota" in str(exc).lower() or "exceeded" in str(exc).lower():
                    blocked.update(
                        n for n in manifest["budgets"] if n >= original["steps"]
                    )
                    break
                if attempt == 0:
                    time.sleep(3)
                else:
                    failed.append(key)
        state = dict(
            configuration=method,
            completed=len(completed),
            total=282,
            quota_blocked_budgets=sorted(blocked),
            failed=failed,
            status="complete" if len(completed) == 282 else "in_progress",
        )
        (folder / "run_state.json").write_text(json.dumps(state, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                completed=len(completed),
                total=282,
                blocked=sorted(blocked),
                failed=failed,
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
