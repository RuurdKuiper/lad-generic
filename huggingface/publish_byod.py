#!/usr/bin/env python3
"""Publish the four BYOD adapters and their fixed-model ZeroGPU Spaces."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import HfApi


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUTS_ROOT = Path(
    os.getenv(
        "LAD_OUTPUT_ROOT",
        "/Users/rkuiper/Library/CloudStorage/GoogleDrive-ruurd.kuiper@gmail.com/"
        "My Drive/lad-generic-results/outputs",
    )
).expanduser()


@dataclass(frozen=True)
class ByodModel:
    source_run: str
    model_name: str
    space_name: str
    display_name: str
    base_model: str
    license_id: str
    license_name: str | None = None
    license_link: str | None = None
    source_checkpoint: str = "best"


MODELS = (
    ByodModel(
        "gemma-2-9b-mask",
        "BYOD-Gemma-2-9B",
        "byod-gemma-2-9b",
        "BYOD-Gemma-2-9B",
        "google/gemma-2-9b-it",
        "gemma",
    ),
    ByodModel(
        "llama-3.1-8b-mask-long",
        "BYOD-Llama-3.1-8B",
        "byod-llama-3.1-8b",
        "BYOD-Llama-3.1-8B",
        "meta-llama/Llama-3.1-8B-Instruct",
        "llama3.1",
        source_checkpoint="final",
    ),
    ByodModel(
        "qwen-2.5-7b-mask",
        "BYOD-Qwen2.5-7B",
        "byod-qwen2.5-7b",
        "BYOD-Qwen2.5-7B",
        "Qwen/Qwen2.5-7B-Instruct",
        "apache-2.0",
    ),
    ByodModel(
        "ministral-8b-mask",
        "BYOD-Ministral-8B",
        "byod-ministral-8b",
        "BYOD-Ministral-8B",
        "mistralai/Ministral-8B-Instruct-2410",
        "other",
        "mrl-0.1",
        "https://mistral.ai/licenses/MRL-0.1.md",
    ),
)


def _yaml_line(key: str, value: str | None) -> str:
    return f"{key}: {value}\n" if value else ""


def anonymous_inference_config(spec: ByodModel, run_config: dict) -> dict:
    """Keep only non-identifying fields required to reconstruct inference."""
    return {
        "model_name_or_path": spec.base_model,
        "tokenizer_name_or_path": run_config.get("tokenizer_name_or_path", spec.base_model),
        "mask_token": run_config.get("mask_token", "MASK"),
        "precision": run_config.get("precision", "bf16"),
        "quantization": "none",
    }


def model_card(spec: ByodModel, namespace: str, run_config: dict, anonymous_review: bool = False) -> str:
    model_repo_id = f"{namespace}/{spec.model_name}"
    space_repo_id = f"{namespace}/{spec.space_name}"
    steps = run_config.get("max_updates", "the configured number of")
    mask_token = run_config.get("mask_token", "MASK")
    source_note = "" if anonymous_review else f"""
## Loading

The standard causal `generate()` method is not the intended sampler. Use the
bidirectional inference code in
[`lad-generic`](https://github.com/RuurdKuiper/lad-generic).
"""
    return f"""---
base_model: {spec.base_model}
library_name: peft
pipeline_tag: text-generation
license: {spec.license_id}
{_yaml_line('license_name', spec.license_name)}{_yaml_line('license_link', spec.license_link)}tags:
- masked-diffusion
- discrete-diffusion
- diffusion-language-model
- lora
- byod
---

# {spec.display_name}

{spec.display_name} is a masked discrete-diffusion language model created by
converting [{spec.base_model}](https://huggingface.co/{spec.base_model}) with
LoRA. This repository contains the exact `{spec.source_checkpoint}` checkpoint
from the `{spec.source_run}` experiment, not a 4-bit or otherwise quantized
variant.

Try the [full-precision ZeroGPU demo](https://huggingface.co/spaces/{space_repo_id}).

## Method

The original autoregressive model was adapted for bidirectional denoising by
training rank-1024 LoRA adapters on the query and value projections. The model
predicts masked answer positions in parallel and iteratively refines its output.
The run configuration records a maximum of {steps} optimizer updates and uses
the `{mask_token}` mask token. An inference configuration is included; the full
resolved training configuration will accompany the archival release.

The adapter can be merged into the base model after training, so the parameter
increase is temporary. The resulting merged model has the same parameter count
as the original base model.

{source_note}

Access to the upstream base model may require accepting its license and using a
Hugging Face token. This adapter remains subject to the base model's terms.

## Limitations

This is a research model. It can produce inaccurate, repetitive, biased, or
unsafe text and should not be used for high-stakes decisions without independent
verification. It inherits the limitations of the base model and its datasets.
"""


def validate_source(spec: ByodModel, outputs_root: Path) -> tuple[Path, Path, dict]:
    run_dir = outputs_root / spec.source_run
    adapter_dir = run_dir / spec.source_checkpoint
    adapter_config_path = adapter_dir / "adapter_config.json"
    run_config_path = run_dir / "resolved_config.json"
    missing = [path for path in (adapter_config_path, run_config_path, adapter_dir / "adapter_model.safetensors") if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required BYOD artifact(s): " + ", ".join(map(str, missing)))
    adapter_config = json.loads(adapter_config_path.read_text())
    if adapter_config.get("base_model_name_or_path") != spec.base_model:
        raise ValueError(
            f"{spec.source_run} uses {adapter_config.get('base_model_name_or_path')!r}, "
            f"expected {spec.base_model!r}."
        )
    return adapter_dir, run_config_path, json.loads(run_config_path.read_text())


def make_space_bundle(spec: ByodModel, namespace: str, destination: Path, anonymous_review: bool = False) -> None:
    template_dir = REPO_ROOT / "huggingface" / "byod_space"
    shutil.copy2(template_dir / "app.py", destination / "app.py")
    shutil.copy2(template_dir / "requirements.txt", destination / "requirements.txt")
    readme = (template_dir / "README.md.template").read_text()
    readme = readme.replace("__TITLE__", spec.display_name).replace(
        "__MODEL_REPO_ID__", f"{namespace}/{spec.model_name}"
    )
    (destination / "README.md").write_text(readme)
    (destination / "space_model.json").write_text(
        json.dumps(
            {
                "display_name": spec.display_name,
                "model_repo_id": f"{namespace}/{spec.model_name}",
                "show_repository_links": not anonymous_review,
                "source_url": None if anonymous_review else "https://github.com/RuurdKuiper/lad-generic",
            },
            indent=2,
        )
        + "\n"
    )
    shutil.copytree(
        REPO_ROOT / "src" / "diffusion_lm",
        destination / "src" / "diffusion_lm",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )


def publish_model(
    api: HfApi,
    spec: ByodModel,
    namespace: str,
    adapter_dir: Path,
    config_path: Path,
    run_config: dict,
    anonymous_review: bool = False,
) -> None:
    repo_id = f"{namespace}/{spec.model_name}"
    print(f"Publishing model {repo_id} from {adapter_dir}")
    api.create_repo(repo_id, repo_type="model", private=anonymous_review, exist_ok=True)
    # Resumable-upload metadata in a checkpoint directory may refer to an older
    # Hub namespace, so use a fresh folder commit and ignore that local cache.
    api.upload_folder(
        repo_id=repo_id,
        repo_type="model",
        folder_path=adapter_dir,
        ignore_patterns=[".cache/**", "*.pyc", "__pycache__/**"],
        commit_message=f"Upload {spec.display_name} adapter artifacts",
    )
    if anonymous_review:
        api.upload_file(
            path_or_fileobj=(json.dumps(anonymous_inference_config(spec, run_config), indent=2) + "\n").encode(),
            path_in_repo="lad_run_config.json",
            repo_id=repo_id,
            repo_type="model",
            commit_message="Add anonymous inference configuration",
        )
    else:
        api.upload_file(
            path_or_fileobj=str(config_path),
            path_in_repo="resolved_config.json",
            repo_id=repo_id,
            repo_type="model",
            commit_message="Add resolved training configuration",
        )
    api.upload_file(
        path_or_fileobj=model_card(spec, namespace, run_config, anonymous_review).encode(),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="model",
        commit_message="Add BYOD model card",
    )


def publish_space(
    api: HfApi,
    spec: ByodModel,
    namespace: str,
    anonymous_review: bool = False,
    space_read_token: str | None = None,
) -> None:
    repo_id = f"{namespace}/{spec.space_name}"
    print(f"Publishing Space {repo_id}")
    api.create_repo(
        repo_id,
        repo_type="space",
        space_sdk="gradio",
        private=anonymous_review,
        exist_ok=True,
    )
    with tempfile.TemporaryDirectory(prefix="byod-space-") as temp_dir:
        bundle = Path(temp_dir)
        make_space_bundle(spec, namespace, bundle, anonymous_review)
        api.upload_folder(
            folder_path=bundle,
            repo_id=repo_id,
            repo_type="space",
            commit_message=f"Deploy {spec.display_name} full-precision demo",
        )
    if space_read_token:
        api.add_space_secret(
            repo_id,
            key="HF_TOKEN",
            value=space_read_token,
            description="Read-only access to private adapters and gated base models",
        )
    try:
        api.request_space_hardware(repo_id, hardware="zero-a10g")
    except Exception as exc:
        print(f"WARNING: could not assign ZeroGPU to {repo_id}: {exc}")
        print("Assign ZeroGPU manually in the Space settings after checking your account quota.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", default="Ruurd")
    parser.add_argument("--outputs-root", type=Path, default=DEFAULT_OUTPUTS_ROOT)
    parser.add_argument("--execute", action="store_true", help="Create/update Hub repositories. Default is validation-only.")
    parser.add_argument("--spaces-only", action="store_true", help="Update only the four demo Spaces; do not re-upload model repositories.")
    parser.add_argument("--models-only", action="store_true", help="Update only the four model repositories; do not update demo Spaces.")
    parser.add_argument(
        "--only",
        action="append",
        choices=[spec.model_name for spec in MODELS],
        help="Publish only the named model/Space. May be supplied more than once.",
    )
    parser.add_argument(
        "--anonymous-review",
        action="store_true",
        help="Keep model repositories and Spaces private while staging an anonymous review deployment.",
    )
    parser.add_argument(
        "--activate-protected",
        action="store_true",
        help="After upload, expose staged Spaces as protected (public app, private source). Requires a current huggingface_hub client.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.spaces_only and args.models_only:
        raise ValueError("--spaces-only and --models-only are mutually exclusive")
    selected_models = tuple(
        spec for spec in MODELS if not args.only or spec.model_name in args.only
    )
    artifacts = []
    for spec in selected_models:
        adapter_dir, config_path, run_config = validate_source(spec, args.outputs_root)
        artifacts.append((spec, adapter_dir, config_path, run_config))
        print(
            f"OK {spec.display_name}: {adapter_dir} -> "
            f"{args.namespace}/{spec.model_name} + {args.namespace}/{spec.space_name}"
        )
    if not args.execute:
        print("Validation complete. Re-run with --execute to publish.")
        return

    api = HfApi()
    identity = api.whoami()
    authenticated_name = identity.get("name", "unknown")
    print(f"Authenticated as {authenticated_name}")
    if authenticated_name.casefold() != args.namespace.casefold():
        raise RuntimeError(
            f"Authenticated as {authenticated_name!r}, but target namespace is {args.namespace!r}."
        )
    if args.activate_protected and not args.anonymous_review:
        raise ValueError("--activate-protected requires --anonymous-review")
    space_read_token = os.getenv("BYOD_SPACE_HF_TOKEN") if args.anonymous_review else None
    if args.anonymous_review and not space_read_token:
        print("WARNING: BYOD_SPACE_HF_TOKEN is unset; private model access must be configured before activation.")
    for spec, adapter_dir, config_path, run_config in artifacts:
        if not args.spaces_only:
            publish_model(
                api,
                spec,
                args.namespace,
                adapter_dir,
                config_path,
                run_config,
                args.anonymous_review,
            )
        if not args.models_only:
            publish_space(
                api,
                spec,
                args.namespace,
                args.anonymous_review,
                space_read_token,
            )
    if args.activate_protected:
        if not space_read_token:
            raise RuntimeError("Set BYOD_SPACE_HF_TOKEN to a read-only token before protected activation.")
        for spec in selected_models:
            api.update_repo_settings(
                f"{args.namespace}/{spec.space_name}",
                repo_type="space",
                visibility="protected",
            )
    print("Publication complete.")


if __name__ == "__main__":
    main()
