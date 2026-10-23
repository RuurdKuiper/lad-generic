#!/usr/bin/env python3
"""Check pinned expanded assets, preserved config and both live decoding methods."""

import argparse, json, re, sys, time
from pathlib import Path
from html import unescape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "huggingface"))
from rollout_byod_simple_interface import accounts

OUT = ROOT / "artifacts/bigram/byod_expanded_rollout"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--smoke", action="store_true")
    a = p.parse_args()
    from huggingface_hub import hf_hub_download
    from gradio_client import Client

    apis = accounts()
    deployed = json.loads((OUT / "deployment.json").read_text())
    path = OUT / "hosted_verification.json"
    records = json.loads(path.read_text()) if path.exists() else {}
    for r in deployed:
        space = r["space"]
        api = apis[r["owner"]]
        if (
            records.get(space, {}).get("smoke_complete")
            and records[space]["revision"] == r["revision"]
        ):
            continue
        assert api.repo_info(space, repo_type="space").sha == r["revision"]
        for attempt in range(120):
            runtime = api.get_space_runtime(space)
            stage = str(runtime.stage)
            if stage == "RUNNING" and runtime.raw.get("sha") == r["revision"]:
                break
            if stage in ("RUNTIME_ERROR", "BUILD_ERROR", "PAUSED"):
                raise RuntimeError(space + ": " + stage)
            print(json.dumps(dict(space=space, stage=stage)), flush=True)
            time.sleep(10)
        else:
            raise RuntimeError("Startup timeout: " + space)
        config = json.loads(
            Path(
                hf_hub_download(
                    space,
                    "space_model.json",
                    repo_type="space",
                    revision=r["revision"],
                    token=api.token,
                )
            ).read_text()
        )
        assert config == r["config_after"]
        assert config == dict(
            r["config_before"],
            ngram_scorer_repo=r["asset_repo"],
            ngram_scorer_revision=r["asset_revision"],
        )
        assets = api.repo_info(
            r["asset_repo"],
            repo_type="model",
            revision=r["asset_revision"],
            files_metadata=True,
        )
        files = {x.rfilename: x for x in assets.siblings}
        for filename, expected in r["assets"].items():
            assert files[filename].lfs.sha256 == expected["sha256"]
        client = Client(space, token=apis["Ruurd"].token, verbose=False)
        props = [x["props"] for x in client.config["components"]]
        radio = next(x for x in props if x.get("label") == "Decoding method")
        assert [x[1] for x in radio["choices"]] == [
            "Confidence-guided",
            "BG + TG Viterbi (Gumbel)",
        ]
        item = dict(
            space=space,
            revision=r["revision"],
            runtime=stage,
            runtime_revision=runtime.raw.get("sha"),
            config_preserved=True,
            pinned_assets_verified=True,
            ui_verified=True,
            tokens=r["tokens"],
            smoke={},
        )
        if a.smoke:
            for method in ["Confidence-guided", "BG + TG Viterbi (Gumbel)"]:
                settings = dict(
                    question="Reply with one short greeting.",
                    system_prompt="You are a helpful assistant.",
                    max_new_tokens=16,
                    num_steps=2,
                    block_length=16,
                    temperature=0.7,
                    top_k=16,
                    pause_per_step=0.0,
                    trajectory_color_mode="No coloring",
                    remasking_strategy=method,
                    revisable_tokens=False,
                    ar_check_interval=4,
                    delay_eos_eot=False,
                    early_stopping=False,
                    generation_seed=42,
                    measure_decoding=True,
                    adaptive_parallel_decoding=False,
                    bigram_weight=1.0,
                )
                start = time.perf_counter()
                job = client.submit(**settings, api_name="/generate")
                status, html = job.result()
                inf = json.loads(status.split("Inference metrics: ")[1].splitlines()[0])
                assert inf["denoising_forward_passes"] == len(job.outputs()) == 2
                assert "masked at iteration" not in html
                text = unescape(
                    re.search(r"<textarea[^>]*>(.*?)</textarea>", html, re.S)[1]
                )
                if method.startswith("BG"):
                    dec = json.loads(
                        status.split("Decoding metrics: ")[1].splitlines()[0]
                    )
                    assert dec["selector_calls"] == 2
                item["smoke"][method] = dict(
                    text=text,
                    inference=inf,
                    client_wall_seconds=time.perf_counter() - start,
                )
                print(
                    json.dumps(dict(space=space, method=method, complete=True)),
                    flush=True,
                )
            item["smoke_complete"] = True
        records[space] = item
        path.write_text(json.dumps(records, indent=2) + "\n")
    print(json.dumps(dict(verified=len(records))), flush=True)


if __name__ == "__main__":
    main()
