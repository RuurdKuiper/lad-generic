#!/usr/bin/env python3
"""Verify each deployed BYOD config/UI and briefly exercise both methods."""

import argparse, json, sys, time, re
from pathlib import Path
from html import unescape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "huggingface"))
from rollout_byod_simple_interface import accounts, OUT


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--smoke", action="store_true")
    args = p.parse_args()
    from gradio_client import Client
    from huggingface_hub import hf_hub_download

    apis = accounts()
    deployed = json.loads((OUT / "deployment.json").read_text())
    prepared = {r["space"]: r for r in json.loads((OUT / "prepared.json").read_text())}
    assert len(deployed) == 8
    path = OUT / "hosted_verification.json"
    records = json.loads(path.read_text()) if path.exists() else {}
    clients = {}
    pending = list(deployed)
    for round in range(90):
        for record in pending[:]:
            space = record["space"]
            api = apis[record["owner"]]
            assert api.repo_info(space, repo_type="space").sha == record["revision"], (
                "Revision changed: " + space
            )
            runtime = api.get_space_runtime(space)
            stage = str(runtime.stage)
            if stage in ["BUILD_ERROR", "RUNTIME_ERROR", "PAUSED"]:
                raise RuntimeError(space + ": " + stage)
            if stage != "RUNNING":
                continue
            # Public demos use the user's replenished Ruurd inference quota; repository
            # checks/writes still use the separately verified owner credentials.
            client = Client(space, token=apis["Ruurd"].token, verbose=False)
            clients[space] = client
            props = [x["props"] for x in client.config["components"]]
            radio = next(x for x in props if x.get("label") == "Decoding method")
            assert [x[1] for x in radio["choices"]] == [
                "Confidence-guided",
                "BG + TG Viterbi (Gumbel)",
            ]
            assert radio["value"] == "BG + TG Viterbi (Gumbel)"
            for label in [
                "Bigram weight",
                "Early stopping",
                "Delay EOS/EOT retention (longer answers)",
                "Adaptive Parallel Decoding (APD)",
            ]:
                assert next(x for x in props if x.get("label") == label).get(
                    "visible", True
                )
            for label in [
                "N-gram guidance",
                "Use exact sequence sampling (slower)",
                "Repetition penalty strength (γ)",
                "Count every candidate bigram occurrence",
                "Repetition-risk penalty",
                "Fade repetition penalty over early iterations",
                "Bigram checkpoint path",
                "Bigram ending delay strength",
                "Reproducible evaluation",
                "Allow revising retained tokens",
                "AR check interval",
            ]:
                assert not any(
                    x.get("label") == label and x.get("visible", True) for x in props
                ), (space, label)
            assert not any(
                x["type"] == "accordion" for x in client.config["components"]
            )
            info = client.view_api(return_format="dict", print_info=False)
            params = {
                x["parameter_name"]: x
                for x in info["named_endpoints"]["/generate"]["parameters"]
            }
            assert params["temperature"]["parameter_default"] == 0.7
            assert params["bigram_weight"]["parameter_default"] == 1.0
            assert params["bigram_eos_delay_penalty"]["parameter_default"] == 10.0
            assert (
                params["ngram_guidance"]["parameter_default"]
                == "Expanded bigram + trigram"
            )
            cfg = json.loads(
                Path(
                    hf_hub_download(
                        space,
                        "space_model.json",
                        repo_type="space",
                        revision=record["revision"],
                        token=api.token,
                    )
                ).read_text()
            )
            original = json.loads(prepared[space]["config_before"])
            assert cfg == dict(original, trigram_enabled=True)
            item = records.get(space, {})
            item.update(
                space=space,
                revision=record["revision"],
                runtime=stage,
                ui_verified=True,
                config_preserved=True,
                original_bigram_sha256=prepared[space]["original_bigram_sha256"],
                tokenizer=prepared[space]["model"],
            )
            records[space] = item
            path.write_text(json.dumps(records, indent=2) + "\n")
            pending.remove(record)
            print(
                json.dumps(dict(space=space, ui="verified", remaining=len(pending))),
                flush=True,
            )
        if not pending:
            break
        print(
            json.dumps(dict(waiting_for_startup=[r["space"] for r in pending])),
            flush=True,
        )
        time.sleep(10)
    else:
        raise RuntimeError("Space startup timeout")
    if args.smoke:
        for r in deployed:
            space = r["space"]
            client = clients[space]
            item = records[space]
            for method in ["Confidence-guided", "BG + TG Viterbi (Gumbel)"]:
                if method in item.get("smoke", {}):
                    continue
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
                item.setdefault("smoke", {})[method] = dict(
                    text=text,
                    inference=inf,
                    client_wall_seconds=time.perf_counter() - start,
                )
                path.write_text(json.dumps(records, indent=2) + "\n")
                print(
                    json.dumps(dict(space=space, method=method, complete=True)),
                    flush=True,
                )
    print(
        json.dumps(
            dict(
                spaces=len(records),
                ui_verified=all(x["ui_verified"] for x in records.values()),
                smoke_complete=all(
                    len(x.get("smoke", {})) == 2 for x in records.values()
                ),
            )
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
