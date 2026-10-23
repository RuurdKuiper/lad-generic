#!/usr/bin/env python3
"""Verify LAD's live BG+TG interface, retained controls, and short generations."""

import argparse
import ast
import json
import re
import time
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OUT = ROOT / "artifacts/bigram/lad_trigram_rollout"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    from gradio_client import Client
    from huggingface_hub import HfApi, hf_hub_download
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    api = HfApi()
    assert api.whoami()["name"].casefold() == "ruurd"
    deployment = json.loads((OUT / "deployment.json").read_text())
    space, revision = deployment["space"], deployment["revision"]
    assert api.repo_info(space, repo_type="space").sha == revision
    for attempt in range(100):
        runtime = api.get_space_runtime(space)
        stage = str(runtime.stage)
        if stage == "RUNNING" and runtime.raw.get("sha") == revision:
            break
        if stage in ["RUNTIME_ERROR", "BUILD_ERROR", "PAUSED"]:
            raise RuntimeError(stage)
        print(json.dumps(dict(stage=stage)), flush=True)
        time.sleep(10)
    else:
        raise RuntimeError("LAD startup timeout")

    initial = json.loads((OUT / "initial_state.json").read_text())
    unchanged_files = ["infer.py", "models.py", "model_config.py", "requirements.txt"]
    for filename in unchanged_files:
        old = Path(
            hf_hub_download(
                space,
                filename,
                repo_type="space",
                revision=deployment["parent_revision"],
                token=api.token,
            )
        ).read_bytes()
        current = Path(
            hf_hub_download(
                space, filename, repo_type="space", revision=revision, token=api.token
            )
        ).read_bytes()
        assert old == current, "LAD model/loading code changed: " + filename
    assert runtime.raw["hardware"] == initial["runtime"]["hardware"]

    client = Client(space, token=api.token, verbose=False)
    props = {
        x["props"].get("label"): x["props"]
        for x in client.config["components"]
        if x["props"].get("label")
    }
    radio = props["Decoding strategy"]
    assert [c[1] for c in radio["choices"]] == ["Sampling", "BG + TG Viterbi (Gumbel)"]
    assert radio["value"] == "Sampling"
    assert props["Temperature"]["value"] == 0.7
    assert props["Top-p: ↑ = more random answers"]["interactive"]
    assert not props["Bigram weight"]["interactive"]
    assert props["Bigram weight"]["value"] == 1.0
    assert props["Bigram weight"]["maximum"] == 5.0
    assert props["Top-k / Viterbi candidates"]["value"] == 16
    assert not props["Repetition penalty strength (γ)"]["visible"]

    # Compare original LAD-specific sliders/checkboxes to the saved pre-update source.
    before = OUT / "before/app.py"
    if not before.exists():
        before.parent.mkdir(exist_ok=True)
        before.write_bytes(
            Path(
                hf_hub_download(
                    space,
                    "app.py",
                    repo_type="space",
                    revision=deployment["parent_revision"],
                    token=api.token,
                )
            ).read_bytes()
        )
    preserved = []
    for call in ast.walk(ast.parse(before.read_text())):
        if (
            not isinstance(call, ast.Call)
            or not isinstance(call.func, ast.Attribute)
            or call.func.attr not in ["Slider", "Checkbox"]
        ):
            continue
        keywords = {k.arg: k.value for k in call.keywords}
        if "label" not in keywords:
            continue
        label = ast.literal_eval(keywords["label"])
        if label in [
            "Temperature",
            "Top-k / Viterbi candidates",
            "Repetition penalty strength (γ)",
        ]:
            continue
        current = props[label]
        if "value" in keywords:
            assert current["value"] == ast.literal_eval(keywords["value"]), label
        assert current.get("visible", True), label
        for name, node in zip(["minimum", "maximum"], call.args[:2]):
            assert current[name] == ast.literal_eval(node), label
        if "step" in keywords:
            assert current["step"] == ast.literal_eval(keywords["step"]), label
        preserved.append(label)

    pin = json.loads(
        Path(
            hf_hub_download(
                space,
                "ngram_assets.json",
                repo_type="space",
                revision=revision,
                token=api.token,
            )
        ).read_text()
    )
    source_pin = json.loads(
        (ROOT / "huggingface/lad_space/ngram_assets.json").read_text()
    )
    assert pin == source_pin
    asset_info = api.repo_info(
        pin["repo"], revision=pin["revision"], files_metadata=True
    )
    asset_files = {f.rfilename: f for f in asset_info.siblings}
    expected = json.loads((OUT / "scorer_verification.json").read_text())["assets"]
    for filename, item in expected.items():
        assert asset_files[filename].lfs.sha256 == item["sha256"]

    info = client.view_api(return_format="dict", print_info=False)
    endpoint = next(
        name
        for name, spec in info["named_endpoints"].items()
        if {"decoding_strategy", "bigram_weight", "noise_start"}.issubset(
            {p["parameter_name"] for p in spec["parameters"]}
        )
    )
    parameters = {
        p["parameter_name"]: p for p in info["named_endpoints"][endpoint]["parameters"]
    }
    assert parameters["temperature"]["parameter_default"] == 0.7
    assert parameters["decoding_strategy"]["parameter_default"] == "Sampling"
    assert parameters["bigram_weight"]["parameter_default"] == 1.0
    record = dict(
        space=space,
        revision=revision,
        runtime_revision=runtime.raw["sha"],
        methods=[c[1] for c in radio["choices"]],
        temperature=0.7,
        default_method="Sampling",
        bigram_weight=1.0,
        preserved_controls=preserved,
        unchanged_model_files=unchanged_files,
        hardware_preserved=True,
        pinned_assets=pin,
        asset_hashes_verified=True,
        endpoint=endpoint,
        smoke=[],
    )
    report_path = OUT / "hosted_verification.json"
    if report_path.exists():
        previous = json.loads(report_path.read_text())
        if previous.get("revision") == revision:
            record["smoke"] = previous.get("smoke", [])
    report_path.write_text(json.dumps(record, indent=2) + "\n")
    if args.smoke:
        # Keep these short; the unit tests separately count actual model forwards.
        cases = [
            ("Sampling", 0.3, 0.5, False),
            ("BG + TG Viterbi (Gumbel)", 0.3, 0.5, False),
            ("BG + TG Viterbi (Gumbel)", 0.0, 0.0, True),
        ]
        for method, temperature, noise_start, permanent in cases:
            settings = dict(
                question="Reply with one short greeting.",
                multiturn_on=False,
                max_it=2,
                pause_length=0.0,
                eos_bias=0.0,
                sharpness=1.0,
                noise_start=noise_start,
                use_confidence_noising=True,
                use_permanent_unmasking=permanent,
                noise_clipping=0.01,
                top_p=1.0,
                top_k=16,
                added_tokens=32,
                context_window=96,
                decoding_strategy=method,
                temperature=temperature,
                repetition_penalty_strength=0.0,
                bigram_weight=1.0,
            )
            if any(case["settings"] == settings for case in record["smoke"]):
                continue
            started = time.perf_counter()
            job = client.submit(**settings, api_name=endpoint)
            result = job.result()
            html = result if isinstance(result, str) else result[-1]
            assert "Final Output" in html
            updates = [
                update if isinstance(update, str) else update[-1]
                for update in job.outputs()
            ]
            assert re.search(r"after 2 iterations", html)
            # Gradio may coalesce rapid intermediate yields; the final status
            # records completed iterations even when an update was skipped.
            generation_updates = sum(
                "(after generation)" in update for update in updates
            )
            text = unescape(re.sub("<[^>]+>", "", html))
            record["smoke"].append(
                dict(
                    settings=settings,
                    text=text,
                    completed_generation_iterations=2,
                    observed_generation_updates=generation_updates,
                    client_wall_seconds=time.perf_counter() - started,
                )
            )
            report_path.write_text(json.dumps(record, indent=2) + "\n")
            print(
                json.dumps(
                    dict(
                        method=method,
                        temperature=temperature,
                        noise_start=noise_start,
                        complete=True,
                    )
                ),
                flush=True,
            )
    print(
        json.dumps(
            dict(
                verified=True,
                preserved_controls=len(preserved),
                smoke_generations=len(record["smoke"]),
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
