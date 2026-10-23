#!/usr/bin/env python3
"""Resumable 1,800-run study and selected, paired sequence-sampling follow-up."""

import argparse
import hashlib
from html import unescape
import json
import os
from pathlib import Path
import re
import time

from evaluate_llada_ngram_settings import METHODS, SPACE, ROOT
from llada_full_study_tasks import tasks

OUT = ROOT / "artifacts/bigram/llada_ngram_settings_full"
BUDGETS = [4, 128, 8, 64, 16, 32]


def shared_settings():
    return dict(
        system_prompt="You are a helpful assistant.",
        max_new_tokens=128,
        block_length=128,
        temperature=0.7,
        top_k=16,
        pause_per_step=0.0,
        trajectory_color_mode="No coloring",
        revisable_tokens=False,
        ar_check_interval=4,
        early_stopping=False,
        generation_seed=42,
        measure_decoding=True,
        bigram_scoring_method="PMI bigram",
        pmi_min_count=1,
        pmi_clip=2.0,
        bigram_remasking_confidence="Diffusion probability",
        bigram_weight=1.0,
        repetition_penalty_strength=1.0,
        adaptive_parallel_decoding=False,
        sequence_sampling=False,
        count_all_candidate_bigrams=False,
        repetition_risk_penalty=False,
        decay_repetition_penalty=True,
    )


def read_rows(path):
    return (
        [json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["main", "sample"], default="main")
    parser.add_argument("--max-runs", type=int)
    args = parser.parse_args()
    from dotenv import load_dotenv
    from gradio_client import Client
    from huggingface_hub import HfApi

    load_dotenv(ROOT / ".env")
    token = os.getenv("HF_TOKEN")
    api = HfApi(token=token)
    info = api.repo_info(SPACE, repo_type="space")
    client = Client(SPACE, token=token, verbose=False)
    OUT.mkdir(parents=True, exist_ok=True)
    all_tasks = tasks()
    shared = shared_settings()
    manifest = dict(
        space=SPACE,
        revision=info.sha,
        tasks=all_tasks,
        methods=METHODS,
        budgets=sorted(BUDGETS),
        shared_settings=shared,
        main_total=1800,
        sampling_planned_total=720,
        seed=42,
        protocol=dict(
            selection="Top two n-gram methods per NFE, using development prompts only.",
            ranking="Equal average of open mean manual grade/3, code all-tests pass rate, and math final-answer accuracy. Tie-break: lower mean server latency, then method id.",
            uncertainty="Paired bootstrap resampling prompts within each task category; preserve all budgets for a prompt in overall estimates.",
            followup="Sequence sampling ON at temperature .7; same selected settings and all60 prompts. Primary paired follow-up interpretation uses untouched validation half.",
            split="Predefined stratified random split: 10 development and10 validation prompts per category, seed20261022.",
            grading="Open manual assistant inspection with method/budget labels hidden; code fixed independent edge tests; math answer and reasoning inspection. Exact duplicates share judgments.",
            eos="Open retention delay ON and bigram ending strength10; code/math delayOFF, strength1.",
            fade="Existing absolute six-iteration fade; zero from iteration6.",
            temperature="Main Viterbi deterministic, samplingOFF; independent baseline samples at .7. Follow-up samples full n-gram-guided sequences at .7.",
            provenance="Six original prompts plus54 new; all generations run fresh; no pilot outputs imported.",
            scope="60 prompts, one fixed seed. Confidence baseline retained. Exploratory multiple-method/NFE comparison.",
        ),
    )
    # JSON normalization also stabilizes tuple/list test-case representations.
    manifest = json.loads(json.dumps(manifest))
    mp = OUT / "manifest.json"
    if mp.exists() and json.loads(mp.read_text()) != manifest:
        raise RuntimeError("Study inputs or Space revision changed")
    mp.write_text(json.dumps(manifest, indent=2) + "\n")
    selection = None
    if args.phase == "sample":
        selection = json.loads((OUT / "selection.json").read_text())
        if selection["revision"] != info.sha:
            raise RuntimeError("Selection uses another revision")
        if len(read_rows(OUT / "main/results.jsonl")) != 1800:
            raise RuntimeError("Finish main study before sampling follow-up")
    folder = OUT / args.phase
    folder.mkdir(exist_ok=True)
    result = folder / "results.jsonl"
    rows = read_rows(result)
    complete = {r["key"] for r in rows}
    cases = []
    # Rotate budgets across triples so any interrupted prefix covers categories
    # and NFE regimes, rather than filling just one budget first.
    for bi in range(6):
        for ti, task in enumerate(all_tasks):
            steps = BUDGETS[(bi + ti // 3 + ti % 3) % 6]
            methods = (
                METHODS
                if selection is None
                else [
                    m
                    for m in METHODS
                    if m["id"] in selection["methods_by_budget"][str(steps)]
                ]
            )
            offset = (bi + ti) % len(methods)
            for method in methods[offset:] + methods[:offset]:
                cases.append((task, steps, method))
    total = len(cases)
    assert total == (1800 if args.phase == "main" else 720)
    if len(complete) == total:
        print(f"{args.phase}: already complete ({total})")
        return
    for method in [METHODS[0], METHODS[1], METHODS[3]]:
        client.predict(
            **dict(
                shared,
                question="What do you know about Amsterdam?",
                max_new_tokens=16,
                block_length=16,
                num_steps=1,
                remasking_strategy=(
                    "Confidence-guided"
                    if method["id"] == "confidence"
                    else "Bigram Viterbi"
                ),
                delay_eos_eot=False,
                bigram_eos_delay_penalty=1.0,
                ngram_guidance=method["ngram"],
                sequence_sampling=args.phase == "sample",
            ),
            api_name="/generate",
        )
    blocked = set()
    new = 0
    failed = []
    for task, steps, method in cases:
        method_id = method["id"] + ("_sample" if args.phase == "sample" else "")
        key = f"{task['id']}/{steps}/{method_id}"
        if key in complete or steps in blocked:
            continue
        if args.max_runs is not None and new >= args.max_runs:
            break
        options = dict(
            shared,
            question=task["prompt"],
            num_steps=steps,
            remasking_strategy=(
                "Confidence-guided"
                if method["id"] == "confidence"
                else (
                    "PMI Viterbi + Repetition Penalty"
                    if method["penalty"]
                    else "Bigram Viterbi"
                )
            ),
            delay_eos_eot=task["category"] == "open",
            bigram_eos_delay_penalty=10.0 if task["category"] == "open" else 1.0,
            ngram_guidance=method["ngram"],
            sequence_sampling=args.phase == "sample",
        )
        if api.repo_info(SPACE, repo_type="space").sha != info.sha:
            raise RuntimeError("Live Space revision changed")
        for attempt in range(2):
            try:
                started = time.perf_counter()
                job = client.submit(**options, api_name="/generate")
                status, rendered = job.result()
                wall = time.perf_counter() - started
                match = re.search(r"<textarea[^>]*>(.*?)</textarea>", rendered, re.S)
                if match is None:
                    raise RuntimeError("Missing final output")
                text = unescape(match[1])
                metrics = json.loads(
                    status.split("Inference metrics: ")[1].splitlines()[0]
                )
                if (
                    metrics["denoising_forward_passes"] != steps
                    or len(job.outputs()) != steps
                ):
                    raise RuntimeError("NFE mismatch")
                if "masked at iteration" in rendered:
                    raise RuntimeError("Unresolved masked output")
                decoding = (
                    json.loads(status.split("Decoding metrics: ")[1].splitlines()[0])
                    if "Decoding metrics: " in status
                    else None
                )
                if decoding and decoding["selector_calls"] != steps:
                    raise RuntimeError("Selector call mismatch")
                row = dict(
                    key=key,
                    task=task["id"],
                    category=task["category"],
                    split=task["split"],
                    prompt=task["prompt"],
                    steps=steps,
                    method=method_id,
                    base_method=method["id"],
                    phase=args.phase,
                    settings=options,
                    revision=info.sha,
                    text=text,
                    status=status,
                    inference=metrics,
                    decoding=decoding,
                    client_wall_seconds=wall,
                    sha256=hashlib.sha256(text.encode()).hexdigest(),
                )
                with result.open("a") as f:
                    f.write(json.dumps(row) + "\n")
                complete.add(key)
                new += 1
                print(
                    json.dumps(
                        dict(
                            phase=args.phase,
                            completed=len(complete),
                            total=total,
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
                    # A long reservation may be refused while shorter budgets
                    # remain available. Try those; never purchase GPU credits.
                    blocked.update(n for n in BUDGETS if n >= steps)
                    break
                if attempt == 0:
                    time.sleep(3)
                else:
                    failed.append(key)
        state = dict(
            phase=args.phase,
            completed=len(complete),
            total=total,
            new=new,
            quota_blocked_budgets=sorted(blocked),
            failed=failed,
        )
        (folder / "run_state.json").write_text(json.dumps(state, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                phase=args.phase,
                completed=len(complete),
                total=total,
                quota_blocked_budgets=sorted(blocked),
                failed=failed,
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
