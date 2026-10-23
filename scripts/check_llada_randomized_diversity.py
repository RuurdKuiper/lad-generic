#!/usr/bin/env python3
"""Small separate seed-variation check; never pool into main quality metrics."""

import hashlib, json, os, re, time
from html import unescape
from evaluate_llada_randomized_viterbi import OUT, ROOT, read


def main():
    from dotenv import load_dotenv
    from gradio_client import Client
    from huggingface_hub import HfApi

    load_dotenv(ROOT / ".env")
    api = HfApi(token=os.getenv("HF_TOKEN"))
    deployment = json.loads((OUT / "deployment.json").read_text())
    space = deployment["space"]
    revision = deployment["revision"]
    assert api.repo_info(space, repo_type="space").sha == revision
    source = read(OUT / "results.jsonl")
    assert len(source) == 282
    targets = [
        r for r in source if r["steps"] == 32 and r["task"] in ["open_14", "fibonacci"]
    ]
    assert len(targets) == 2
    path = OUT / "diversity.jsonl"
    existing = read(path)
    done = {(r["task"], r["seed"]) for r in existing}
    client = Client(space, token=api.token, verbose=False)
    for r in targets:
        for seed in [43, 44]:
            if (r["task"], seed) in done:
                continue
            settings = dict(r["settings"], generation_seed=seed)
            start = time.perf_counter()
            job = client.submit(**settings, api_name="/generate")
            status, rendered = job.result()
            text = unescape(
                re.search(r"<textarea[^>]*>(.*?)</textarea>", rendered, re.S)[1]
            )
            inf = json.loads(status.split("Inference metrics: ")[1].splitlines()[0])
            assert inf["denoising_forward_passes"] == len(job.outputs()) == 32
            row = dict(
                task=r["task"],
                seed=seed,
                steps=32,
                revision=revision,
                settings=settings,
                text=text,
                sha256=hashlib.sha256(text.encode()).hexdigest(),
                inference=inf,
                wall_seconds=time.perf_counter() - start,
            )
            with path.open("a") as f:
                f.write(json.dumps(row) + "\n")
            print(
                json.dumps(
                    dict(
                        task=r["task"],
                        seed=seed,
                        same_as_seed42=row["sha256"] == r["sha256"],
                    )
                ),
                flush=True,
            )
    check = {}
    for r in targets:
        hashes = [r["sha256"]] + [
            x["sha256"] for x in read(path) if x["task"] == r["task"]
        ]
        assert len(hashes) == 3
        check[r["task"]] = dict(
            seeds=[42, 43, 44], unique_outputs=len(set(hashes)), total=3
        )
    (OUT / "diversity_summary.json").write_text(json.dumps(check, indent=2) + "\n")
    print(json.dumps(check))


if __name__ == "__main__":
    main()
