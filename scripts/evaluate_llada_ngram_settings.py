#!/usr/bin/env python3
"""Small resumable, matched LLaDA NFE study; saves every output for review."""

import hashlib
from html import unescape
import json
import os
from pathlib import Path
import re
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/bigram/llada_ngram_settings"
SPACE = "Ruurd/llada-8b-instruct"
METHODS = [
    dict(
        id="confidence",
        label="Confidence guided",
        ngram="Original bigram",
        penalty=False,
    ),
    dict(id="bigram", label="Expanded bigram", ngram="Expanded bigram", penalty=False),
    dict(
        id="bigram_rep",
        label="Expanded bigram + fading repetition",
        ngram="Expanded bigram",
        penalty=True,
    ),
    dict(
        id="trigram",
        label="Expanded bigram + trigram",
        ngram="Expanded bigram + trigram",
        penalty=False,
    ),
    dict(
        id="trigram_rep",
        label="Expanded bigram + trigram + fading repetition",
        ngram="Expanded bigram + trigram",
        penalty=True,
    ),
]
TASKS = [
    dict(id="amsterdam", category="open", prompt="What do you know about Amsterdam?"),
    dict(
        id="sum_even",
        category="code",
        prompt="Write Python function sum_even(nums) returning the sum of even integers in nums. Handle an empty list. Return only concise Python code, without explanation or examples.",
    ),
    dict(
        id="algebra",
        category="math",
        prompt="Solve 3(x - 2) + 4 = 2x + 9. Show your steps briefly.",
    ),
    dict(id="sky", category="open", prompt="Why is the sky blue?"),
    dict(
        id="balanced",
        category="code",
        prompt="Write Python function balanced(s) checking balanced parentheses (), brackets [], and braces {}. Ignore other characters. Return only concise Python code, without explanation or examples.",
    ),
    dict(
        id="train",
        category="math",
        prompt="A train travels 120 km at 60 km/h and returns the same 120 km at 40 km/h. What is its average speed for the entire trip? Explain briefly.",
    ),
]
BUDGET_ORDER = [4, 128, 8, 64, 16, 32]


def main():
    from dotenv import load_dotenv
    from gradio_client import Client
    from huggingface_hub import HfApi

    load_dotenv(ROOT / ".env")
    token = os.getenv("HF_TOKEN")
    api = HfApi(token=token)
    info = api.repo_info(SPACE, repo_type="space")
    client = Client(SPACE, token=token, verbose=False)
    OUT.mkdir(parents=True, exist_ok=True)
    shared = dict(
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
    manifest = dict(
        space=SPACE,
        revision=info.sha,
        shared_settings=shared,
        tasks=TASKS,
        methods=METHODS,
        budgets=sorted(BUDGET_ORDER),
        execution_budget_order=BUDGET_ORDER,
        total=180,
        seed_policy="One fixed seed (42) for every matched run; no seed selection.",
        eos_policy="Open: delay retention ON and bigram ending strength 10. Code/math: delay OFF and strength 1.",
        fade_policy="Existing absolute six-iteration logistic fade; zero from iteration six, not stretched with NFE.",
        sampling_policy="UI-default deterministic Viterbi; sequence sampling OFF. Temperature .7 affects independent diffusion sampling, not MAP Viterbi.",
        budget_policy="APD and early stopping OFF; require exactly the requested model forwards, even if visible text ends earlier.",
        trigram_min_count=2,
        trigram_clip=2.0,
        trigram_relative_weight=0.5,
        scope="Two open, two code, two math prompts; exploratory settings comparison, not a representative benchmark.",
    )
    path = OUT / "manifest.json"
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise RuntimeError("Experiment revision or inputs changed")
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    results = OUT / "results.jsonl"
    rows = (
        [json.loads(s) for s in results.read_text().splitlines()]
        if results.exists()
        else []
    )
    completed = {r["key"] for r in rows}
    if len(completed) == manifest["total"]:
        print("All 180 runs already complete")
        return
    # Warm scorer tables and kernels before collecting server timings.
    for method in [METHODS[0], METHODS[1], METHODS[3]]:
        options = dict(
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
        )
        client.predict(**options, api_name="/generate")
    errors = []
    for bi, steps in enumerate(BUDGET_ORDER):
        for ti, task in enumerate(TASKS):
            offset = (bi + ti) % len(METHODS)
            for method in METHODS[offset:] + METHODS[:offset]:
                key = f"{task['id']}/{steps}/{method['id']}"
                if key in completed:
                    continue
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
                    bigram_eos_delay_penalty=(
                        10.0 if task["category"] == "open" else 1.0
                    ),
                    ngram_guidance=method["ngram"],
                )
                if api.repo_info(SPACE, repo_type="space").sha != info.sha:
                    raise RuntimeError("Live Space changed during study")
                for attempt in range(2):
                    try:
                        start = time.perf_counter()
                        job = client.submit(**options, api_name="/generate")
                        status, rendered = job.result()
                        wall = time.perf_counter() - start
                        match = re.search(
                            r"<textarea[^>]*>(.*?)</textarea>", rendered, re.S
                        )
                        if match is None:
                            raise RuntimeError("Missing final output")
                        text = unescape(match[1])
                        metrics = json.loads(
                            status.split("Inference metrics: ")[1].splitlines()[0]
                        )
                        assert (
                            metrics["denoising_forward_passes"] == steps
                            and len(job.outputs()) == steps
                        )
                        assert "masked at iteration" not in rendered
                        decoding = (
                            json.loads(
                                status.split("Decoding metrics: ")[1].splitlines()[0]
                            )
                            if "Decoding metrics: " in status
                            else None
                        )
                        if decoding is not None:
                            assert decoding["selector_calls"] == steps
                        row = dict(
                            key=key,
                            task=task["id"],
                            category=task["category"],
                            prompt=task["prompt"],
                            steps=steps,
                            method=method["id"],
                            settings=options,
                            revision=info.sha,
                            text=text,
                            status=status,
                            inference=metrics,
                            decoding=decoding,
                            client_wall_seconds=wall,
                            sha256=hashlib.sha256(text.encode()).hexdigest(),
                        )
                        with results.open("a") as f:
                            f.write(json.dumps(row) + "\n")
                        completed.add(key)
                        print(
                            json.dumps(
                                dict(
                                    completed=len(completed),
                                    total=180,
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
                        errors.append(error)
                        with (OUT / "errors.jsonl").open("a") as f:
                            f.write(json.dumps(error) + "\n")
                        print(json.dumps(error), flush=True)
                        if (
                            "quota" in str(exc).lower()
                            or "exceeded" in str(exc).lower()
                        ):
                            (OUT / "run_state.json").write_text(
                                json.dumps(
                                    dict(
                                        completed=len(completed),
                                        total=180,
                                        stopped="quota",
                                        last_error=error,
                                    ),
                                    indent=2,
                                )
                                + "\n"
                            )
                            return
                        if attempt == 0:
                            time.sleep(3)
                (OUT / "run_state.json").write_text(
                    json.dumps(dict(completed=len(completed), total=180), indent=2)
                    + "\n"
                )
    print(
        json.dumps(dict(completed=len(completed), total=180, errors=len(errors))),
        flush=True,
    )


if __name__ == "__main__":
    main()
