#!/usr/bin/env python3
"""One matched randomized BG+TG arm, Gumbel scale .7, all282 prior cases."""

import argparse, hashlib, json, os, re, time
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "artifacts/bigram/llada_ngram_settings_full"
OUT = STUDY / "randomized"


def read(p):
    return [json.loads(s) for s in p.read_text().splitlines()] if p.exists() else []


def historical(name):
    frozen = STUDY / ("pre_randomized_" + name)
    return frozen if frozen.exists() else STUDY / name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-runs", type=int)
    args = parser.parse_args()
    from dotenv import load_dotenv
    from huggingface_hub import HfApi
    from gradio_client import Client

    load_dotenv(ROOT / ".env")
    api = HfApi(token=os.getenv("HF_TOKEN"))
    deploy = json.loads((OUT / "deployment.json").read_text())
    space = deploy["space"]
    revision = deploy["revision"]
    source = [
        r for r in read(STUDY / "matched_results.jsonl") if r["method"] == "trigram"
    ]
    assert len(source) == 282
    amendment = dict(
        configuration="trigram_randomized",
        source_sha256=hashlib.sha256(
            (STUDY / "matched_results.jsonl").read_bytes()
        ).hexdigest(),
        comparison_sha256=hashlib.sha256(
            historical("combined_results.jsonl").read_bytes()
        ).hexdigest(),
        revision=revision,
        space=space,
        total=282,
        seed=42,
        changes=dict(randomized_viterbi=True, sequence_sampling=False, temperature=0.7),
        noise="independent unit Gumbels on editable candidate unary log scores, multiplied by .7, redrawn every iteration",
        caveat="Approximate perturb-and-MAP, not an exact T=.7 sequence sample",
        repetition_penalty=False,
    )
    manifest = OUT / "amendment.json"
    if manifest.exists():
        assert json.loads(manifest.read_text()) == amendment
    else:
        manifest.write_text(json.dumps(amendment, indent=2) + "\n")
    result = OUT / "results.jsonl"
    rows = read(result)
    completed = {r["key"] for r in rows}
    expected = {f"{r['task']}/{r['steps']}/trigram_randomized" for r in source}
    assert completed <= expected and len(rows) == len(completed)
    assert all(r["revision"] == revision for r in rows)
    if completed == expected:
        print("already complete")
        return
    assert api.repo_info(space, repo_type="space").sha == revision
    client = Client(space, token=api.token, verbose=False)
    warm = dict(
        source[0]["settings"],
        question="Reply with a short greeting.",
        max_new_tokens=16,
        block_length=16,
        num_steps=1,
        randomized_viterbi=True,
        sequence_sampling=False,
        temperature=0.7,
    )
    client.predict(**warm, api_name="/generate")
    new = 0
    for original in source:
        key = f"{original['task']}/{original['steps']}/trigram_randomized"
        if key in completed:
            continue
        if args.max_runs is not None and new >= args.max_runs:
            break
        assert api.repo_info(space, repo_type="space").sha == revision
        opts = dict(
            original["settings"],
            randomized_viterbi=True,
            sequence_sampling=False,
            temperature=0.7,
        )
        for attempt in range(2):
            try:
                started = time.perf_counter()
                job = client.submit(**opts, api_name="/generate")
                status, rendered = job.result()
                wall = time.perf_counter() - started
                text = unescape(
                    re.search(r"<textarea[^>]*>(.*?)</textarea>", rendered, re.S)[1]
                )
                inf = json.loads(status.split("Inference metrics: ")[1].splitlines()[0])
                dec = json.loads(status.split("Decoding metrics: ")[1].splitlines()[0])
                assert (
                    inf["denoising_forward_passes"]
                    == dec["selector_calls"]
                    == len(job.outputs())
                    == original["steps"]
                )
                assert "masked at iteration" not in rendered
                row = dict(
                    original,
                    key=key,
                    method="trigram_randomized",
                    base_method="trigram",
                    phase="randomized",
                    revision=revision,
                    settings=opts,
                    text=text,
                    status=status,
                    inference=inf,
                    decoding=dec,
                    client_wall_seconds=wall,
                    sha256=hashlib.sha256(text.encode()).hexdigest(),
                )
                with result.open("a") as f:
                    f.write(json.dumps(row) + "\n")
                completed.add(key)
                new += 1
                state = dict(
                    completed=len(completed),
                    total=282,
                    status="complete" if len(completed) == 282 else "running",
                )
                (OUT / "run_state.json").write_text(json.dumps(state, indent=2) + "\n")
                print(
                    json.dumps(dict(**state, key=key, server_ms=inf["elapsed_ms"])),
                    flush=True,
                )
                break
            except Exception as exc:
                error = dict(
                    key=key, attempt=attempt + 1, error=str(exc), at=time.time()
                )
                with (OUT / "errors.jsonl").open("a") as f:
                    f.write(json.dumps(error) + "\n")
                print(json.dumps(error), flush=True)
                if (
                    attempt == 1
                    or "quota" in str(exc).lower()
                    or "exceeded" in str(exc).lower()
                ):
                    raise
                time.sleep(3)


if __name__ == "__main__":
    main()
