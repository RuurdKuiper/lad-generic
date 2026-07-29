#!/usr/bin/env python
"""Evaluate selected saved adapters: python evaluate_benchmarks.py --config ..."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from tqdm.auto import tqdm

from diffusion_lm.benchmarks import ALL_TASKS, load_benchmark, save_result, score_prediction
from diffusion_lm.inference import denoise_stream, find_adapters, load_session

load_dotenv(Path(__file__).resolve().parent / ".env")


def _generate_ar(session, prompt: str, max_new_tokens: int, original_base: bool = True) -> str:
    """Generate one autoregressive answer from a loaded adapter."""
    prefix = session.tokenizer.apply_chat_template([{"role": "user", "content": prompt}], tokenize=True, add_generation_prompt=True)
    if isinstance(prefix, str):
        prefix = session.tokenizer.encode(prefix, add_special_tokens=False)
    elif hasattr(prefix, "input_ids"):
        prefix = prefix.input_ids
    if prefix and isinstance(prefix[0], list):
        prefix = prefix[0]
    import torch
    context = session.model.disable_adapter() if original_base else None
    trained = {name: parameter.detach().cpu().clone() for name, parameter in session.model.named_parameters() if "norm" in name.lower()}
    try:
        with torch.inference_mode(), (context if context is not None else _null_context()):
            if original_base:
                initial_path = session.adapter_path / "normalization_initial_state.pt"
                if initial_path.is_file():
                    initial = torch.load(initial_path, map_location="cpu", weights_only=True)
                    named = dict(session.model.named_parameters())
                    for name, value in initial.items():
                        if name in named:
                            named[name].data.copy_(value.to(named[name].device, dtype=named[name].dtype))
            generated = session.model.generate(torch.tensor([prefix], device=session.device), max_new_tokens=max_new_tokens, do_sample=False, use_cache=True)
    finally:
        named = dict(session.model.named_parameters())
        for name, value in trained.items():
            if name in named:
                named[name].data.copy_(value.to(named[name].device, dtype=named[name].dtype))
    return session.tokenizer.decode(generated[0, len(prefix):], skip_special_tokens=True).strip()


class _null_context:
    """Minimal no-op context manager for optional adapter disabling."""
    def __enter__(self):
        """Enter without modifying model state."""
        return self
    def __exit__(self, *args):
        """Leave without suppressing exceptions."""
        return False


def _generate_diffusion(session, prompt: str, settings: dict, mode: str) -> str:
    """Generate one pure-diffusion answer using the run's corruption strategy."""
    structured = mode == "structured"
    # Mask-only (LLaDA-style) evaluation always begins with the answer fully
    # masked; configured noise levels remain applicable to structured runs.
    noise_level = 1.0 if mode == "mask_only" else float(settings.get("noise_level", .5))
    final = ""
    for final, _status, _html in denoise_stream(session, prompt, settings.get("system_prompt", "You are a helpful assistant."), int(settings.get("max_new_tokens", 256)), int(settings.get("num_steps", settings.get("max_new_tokens", 256))), noise_level, float(settings.get("temperature", .7)), int(settings.get("top_k", 20)), int(settings.get("seed", 1234)), bool(settings.get("permanent_unmask", structured)), bool(settings.get("confidence_guided", structured)), bool(settings.get("proportional_unmask", True))):
        pass
    return final


def main() -> None:
    """Load configured benchmark data and evaluate selected best adapters."""
    parser = argparse.ArgumentParser(); parser.add_argument("--config", required=True)
    args = parser.parse_args()
    with open(args.config) as stream:
        config = yaml.safe_load(stream)
    outputs = Path(config.get("outputs_dir", "outputs"))
    selections = config.get("models") or find_adapters(outputs)
    if not selections:
        raise SystemExit("No adapter directories found. Train at least one model to create outputs/<run>/best/.")
    if config.get("tasks") is None:
        config["tasks"] = ALL_TASKS
    token = os.getenv("HF_TOKEN")
    cache = config.get("cache_dir", "data/huggingface")
    result_path = Path(config.get("results_path", "outputs/benchmark_results.jsonl")); result_path.parent.mkdir(parents=True, exist_ok=True)
    summaries = []
    for selection in selections:
        selection = str(selection)
        adapter_path = outputs / selection
        run_config_path = adapter_path.parent / "resolved_config.json"
        run_config = json.loads(run_config_path.read_text())
        mode = run_config.get("corruption_mode", "mask_only")
        session = load_session(selection, outputs, config.get("device", "auto"))
        for task in config["tasks"]:
            examples = load_benchmark(task, config.get("split", "test"), config.get("limit"), cache, token)
            task_settings = dict(config.get("generation", {})); task_settings.update(config.get("task_generation", {}).get(task, {}))
            correct = 0; ar_correct = 0
            total = len(examples)
            print(f"\n[{selection}] {task}: {total} validation samples (diffusion)", flush=True)
            # Complete the diffusion pass before switching to the optional
            # autoregressive baseline, avoiding per-example model switching.
            diffusion_progress = tqdm(examples, desc=f"{selection}/{task} diffusion", unit="sample")
            for index, example in enumerate(diffusion_progress, start=1):
                diffusion_text = _generate_diffusion(session, example.prompt, task_settings, mode)
                diffusion_ok = score_prediction(example, diffusion_text)
                record = {"model": selection, "corruption_mode": mode, "task": task, "example_id": example.example_id, "method": "diffusion", "prompt": example.prompt, "prediction": diffusion_text, "target": example.answer, "correct": diffusion_ok}
                save_result(result_path, record); correct += int(diffusion_ok)
                diffusion_progress.set_postfix(correct=f"{correct}/{index}", accuracy=f"{correct / index:.3f}")
            if config.get("include_autoregressive", False):
                print(f"[{selection}] {task}: {total} validation samples (autoregressive)", flush=True)
                ar_progress = tqdm(examples, desc=f"{selection}/{task} autoregressive", unit="sample")
                for index, example in enumerate(ar_progress, start=1):
                    ar_text = _generate_ar(session, example.prompt, int(task_settings.get("max_new_tokens", 256)), original_base=True)
                    ar_ok = score_prediction(example, ar_text); ar_correct += int(ar_ok)
                    save_result(result_path, {"model": selection, "corruption_mode": mode, "task": task, "example_id": example.example_id, "method": "autoregressive", "prompt": example.prompt, "prediction": ar_text, "target": example.answer, "correct": ar_ok})
                    ar_progress.set_postfix(correct=f"{ar_correct}/{index}", accuracy=f"{ar_correct / index:.3f}")
            summary = {"model": selection, "corruption_mode": mode, "task": task, "method": "diffusion", "accuracy": correct / max(len(examples), 1), "correct": correct, "total": len(examples)}
            summaries.append(summary)
            message = f"{selection} | {task} | diffusion accuracy={summary['accuracy']:.4f} ({correct}/{len(examples)})"
            if config.get("include_autoregressive", False):
                ar_summary = {"model": selection, "corruption_mode": mode, "task": task, "method": "autoregressive", "accuracy": ar_correct / max(len(examples), 1), "correct": ar_correct, "total": len(examples)}
                summaries.append(ar_summary)
                message += f" | autoregressive accuracy={ar_summary['accuracy']:.4f} ({ar_correct}/{len(examples)})"
            print(message)
    (result_path.parent / (result_path.stem + "_summary.json")).write_text(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
