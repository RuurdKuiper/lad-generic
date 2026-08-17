#!/usr/bin/env python
"""Evaluate selected saved adapters: python evaluate_benchmarks.py --config ..."""
from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import sys

import yaml
from dotenv import load_dotenv
from tqdm.auto import tqdm

# Prefer this checkout over a stale non-editable package in site-packages when
# the script is run directly in Colab.
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from diffusion_lm.benchmarks import ALL_TASKS, BenchmarkRunReporter, extract_answer, load_benchmark, resolve_generation_settings, resolve_llada_generation_settings, resolve_mask_only_generation_settings, score_prediction, score_texts_with_model
from diffusion_lm.inference import denoise_stream, find_adapters, llada_generate, load_hosted_legacy_session, load_llada_session, load_local_legacy_session, load_session, release_session, select_device

load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_PERPLEXITY_MODEL = "microsoft/phi-4"


def _generate_ar(session, prompt: str, max_new_tokens: int, original_base: bool = True) -> str:
    """Generate one autoregressive answer from a loaded adapter."""
    from diffusion_lm.data import apply_neutral_chat_template
    prefix = apply_neutral_chat_template(session.tokenizer, [{"role": "user", "content": prompt}], tokenize=True, add_generation_prompt=True)
    if isinstance(prefix, str):
        prefix = session.tokenizer.encode(prefix, add_special_tokens=False)
    elif hasattr(prefix, "input_ids"):
        prefix = prefix.input_ids
    if prefix and isinstance(prefix[0], list):
        prefix = prefix[0]
    import torch
    context = session.model.disable_adapter() if original_base else None
    trained = {name: parameter.detach().cpu().clone() for name, parameter in session.model.named_parameters() if "norm" in name.lower()}
    config = session.model.config
    original_config = {
        name: getattr(config, name)
        for name in ("use_cache", "is_causal", "use_bidirectional_attention")
        if hasattr(config, name)
    }
    try:
        # load_session prepares this shared model instance for denoising. Put
        # it back in causal generation mode for the untouched base baseline.
        config.use_cache = True
        if hasattr(config, "is_causal"):
            config.is_causal = True
        if hasattr(config, "use_bidirectional_attention"):
            config.use_bidirectional_attention = False
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
        for name, value in original_config.items():
            setattr(config, name, value)
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
    if settings.get("sampler") == "llada_official":
        return llada_generate(
            session,
            prompt,
            gen_length=int(settings.get("max_new_tokens", 128)),
            steps=int(settings.get("num_steps", settings.get("max_new_tokens", 128))),
            block_length=int(settings.get("block_length", settings.get("max_new_tokens", 128))),
            temperature=float(settings.get("temperature", 0.0)),
            cfg_scale=float(settings.get("cfg_scale", 0.0)),
            remasking=str(settings.get("remasking", "low_confidence")),
            logits_eos_inf=bool(settings.get("logits_eos_inf", False)),
            confidence_eos_eot_inf=bool(settings.get("confidence_eos_eot_inf", False)),
            eot_token_id=settings.get("eot_token_id"),
            system_prompt=str(settings.get("system_prompt", "")),
            seed=int(settings.get("seed", 1234)),
        )
    structured = mode in {"structured", "legacy"}
    # Mask-only (LLaDA-style) evaluation always begins with the answer fully
    # masked; configured noise levels remain applicable to structured runs.
    noise_level = 1.0 if mode == "mask_only" else float(settings.get("noise_level", .5))
    final = ""
    for final, _status, _html in denoise_stream(session, prompt, settings.get("system_prompt", "You are a helpful assistant."), int(settings.get("max_new_tokens", 256)), int(settings.get("num_steps", settings.get("max_new_tokens", 256))), noise_level, float(settings.get("temperature", .7)), int(settings.get("top_k", 20)), int(settings.get("seed", 1234)), bool(settings.get("permanent_unmask", structured)), bool(settings.get("confidence_guided", structured)), bool(settings.get("proportional_unmask", True))):
        pass
    return final


def _native_eot_token_id(tokenizer) -> int | None:
    """Find the model-native end-of-turn token used for delayed transfer."""
    unknown = getattr(tokenizer, "unk_token_id", None)
    vocabulary_size = len(tokenizer)
    for token in ("<|eot_id|>", "<end_of_turn>", "<|end_of_turn|>"):
        token_id = tokenizer.convert_tokens_to_ids(token)
        if token_id is not None and token_id != unknown and 0 <= int(token_id) < vocabulary_size:
            return int(token_id)
    return None


def _show_open_ended_answer(progress, method: str, index: int, total: int, prompt: str, answer: str) -> None:
    """Print one completed open-ended generation without disrupting tqdm."""
    progress.write(
        f"\n[{method} {index}/{total}] Prompt:\n{prompt}\n"
        f"Final answer:\n{answer or '[empty response]'}\n"
    )
    print(f"[{method} {index}/{total}] sample complete", flush=True)


def _load_perplexity_reference(config: dict):
    """Load the single model used for all benchmark perplexity scores."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    settings = dict(config.get("perplexity", {}))
    model_name = settings.get("model_name_or_path", DEFAULT_PERPLEXITY_MODEL)
    tokenizer_name = settings.get("tokenizer_name_or_path", model_name)
    device = select_device(settings.get("device", config.get("device", "auto")))
    cache_dir = settings.get("cache_dir", "base_models")
    token = os.getenv("HF_TOKEN")
    precision = str(settings.get("precision", "fp16" if device.type == "cuda" else "fp32")).lower()
    dtype = torch.bfloat16 if precision == "bf16" else torch.float16 if precision == "fp16" and device.type != "cpu" else torch.float32
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_name, token=token, cache_dir=cache_dir, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    load_kwargs = {"torch_dtype": dtype, "token": token, "cache_dir": cache_dir}
    if str(settings.get("quantization", "none")).lower() in {"4bit", "4-bit", "qlora"}:
        if device.type != "cuda":
            raise RuntimeError("Perplexity 4-bit quantization requires CUDA.")
        from transformers import BitsAndBytesConfig
        load_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type=str(settings.get("quantization_type", "nf4")),
            bnb_4bit_compute_dtype=dtype,
            bnb_4bit_use_double_quant=True,
        )
        load_kwargs["device_map"] = {"": device.index if device.index is not None else 0}
    model = AutoModelForCausalLM.from_pretrained(model_name, **load_kwargs)
    if "device_map" not in load_kwargs:
        model.to(device)
    model.eval()
    return model, tokenizer, device, {"model_name_or_path": model_name, "tokenizer_name_or_path": tokenizer_name, "device": str(device), "quantization": str(settings.get("quantization", "none")), "precision": precision}


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
    if "results_path" in config and "results_dir" not in config:
        legacy_path = Path(config["results_path"])
        results_dir = legacy_path.parent / "benchmark_runs"
        print(f"results_path is deprecated; this run will be isolated under {results_dir}", flush=True)
    else:
        results_dir = Path(config.get("results_dir", "outputs/benchmark_runs"))
    reporter = BenchmarkRunReporter(results_dir, config, config.get("run_name"))
    print(f"Benchmark run: {reporter.run_id}\nResults: {reporter.path}", flush=True)
    show_open_ended_answers = bool(config.get("show_open_ended_answers", False))
    open_ended_pending = []
    for selection in selections:
        selection = str(selection)
        if selection.startswith("llada:"):
            model_name = selection.split(":", 1)[1].strip() or "GSAI-ML/LLaDA-8B-Instruct"
            model_label = f"llada:{model_name}"
            run_config = {"model_source": "llada", "repo_id": model_name}
            mode = "mask_only"
            session = load_llada_session(model_name, config.get("device", "auto"))
            supports_autoregressive = False
        elif selection.startswith("legacy:"):
            checkpoint = selection.split(":", 1)[1].strip()
            if not checkpoint:
                raise ValueError("Legacy model entries must use legacy:/path/to/checkpoint.pth")
            tokenizer_name = config.get("legacy_tokenizer_name_or_path", "meta-llama/Llama-3.2-3B")
            model_label = f"legacy:{checkpoint}"
            run_config = {"model_source": "local_legacy", "checkpoint": checkpoint, "tokenizer_name_or_path": tokenizer_name}
            mode = "structured"
            session = load_local_legacy_session(checkpoint, tokenizer_name, config.get("device", "auto"))
            supports_autoregressive = False
        elif selection.startswith("legacy-hf:"):
            descriptor = selection.split(":", 1)[1].strip()
            try:
                repo_id, filename = [part.strip() for part in descriptor.split("|", 1)]
            except ValueError as exc:
                raise ValueError("Hosted legacy entries must use legacy-hf:repo_id|filename.pth") from exc
            tokenizer_name = config.get("legacy_tokenizer_name_or_path", "meta-llama/Llama-3.2-3B")
            model_label = f"legacy-hf:{repo_id}/{filename}"
            run_config = {"model_source": "huggingface_legacy", "repo_id": repo_id, "filename": filename, "tokenizer_name_or_path": tokenizer_name}
            mode = "structured"
            session = load_hosted_legacy_session(repo_id, filename, tokenizer_name, config.get("device", "auto"))
            supports_autoregressive = False
        else:
            model_label = selection
            adapter_path = outputs / selection
            run_config_path = adapter_path.parent / "resolved_config.json"
            run_config = json.loads(run_config_path.read_text())
            mode = run_config.get("corruption_mode", "mask_only")
            session = load_session(selection, outputs, config.get("device", "auto"), config.get("quantization"))
            supports_autoregressive = True
        ar_model_name = str(run_config.get("model_name_or_path", run_config.get("repo_id", model_label)))
        for task in config["tasks"]:
            examples = load_benchmark(task, config.get("split", "test"), config.get("limit"), cache, token, config.get("limit_fraction"))
            if session.llada:
                task_settings = resolve_llada_generation_settings(config, task)
            elif mode == "mask_only":
                task_settings = resolve_mask_only_generation_settings(config, task)
            else:
                task_settings = resolve_generation_settings(config, task, mode)
            if task_settings.get("sampler") == "llada_official" and "eot_token_id" not in task_settings:
                task_settings["eot_token_id"] = _native_eot_token_id(session.tokenizer)
            if task == "open_ended":
                print(f"\n[{model_label}] {task}: {len(examples)} validation samples (diffusion)", flush=True)
                diffusion_texts = []
                diffusion_progress = tqdm(examples, desc=f"{model_label}/{task} diffusion", unit="sample")
                for index, example in enumerate(diffusion_progress, start=1):
                    if show_open_ended_answers:
                        print(f"\n[diffusion {index}/{len(examples)}] generating: {example.prompt}", flush=True)
                    text = _generate_diffusion(session, example.prompt, task_settings, mode)
                    diffusion_texts.append(text)
                    if show_open_ended_answers:
                        _show_open_ended_answer(diffusion_progress, "diffusion", index, len(examples), example.prompt, text)
                open_ended_pending.append({"model": model_label, "corruption_mode": mode, "task": task, "method": "diffusion", "examples": examples, "texts": diffusion_texts, "inference_settings": task_settings})
                message = f"{model_label} | {task} | diffusion generation complete; perplexity will be scored with the shared reference model at the end"
                if config.get("include_autoregressive", False) and supports_autoregressive:
                    print(f"[{model_label}] {task}: {len(examples)} validation samples (autoregressive)", flush=True)
                    ar_texts = []
                    ar_progress = tqdm(examples, desc=f"{model_label}/{task} autoregressive", unit="sample")
                    for index, example in enumerate(ar_progress, start=1):
                        if show_open_ended_answers:
                            print(f"\n[autoregressive {index}/{len(examples)}] generating: {example.prompt}", flush=True)
                        text = _generate_ar(session, example.prompt, int(task_settings.get("max_new_tokens", 256)), original_base=True)
                        ar_texts.append(text)
                        if show_open_ended_answers:
                            _show_open_ended_answer(ar_progress, "autoregressive", index, len(examples), example.prompt, text)
                    open_ended_pending.append({"model": model_label, "evaluation_model": ar_model_name, "model_variant": "original_base", "corruption_mode": mode, "task": task, "method": "autoregressive", "examples": examples, "texts": ar_texts, "inference_settings": {"max_new_tokens": int(task_settings.get("max_new_tokens", 256))}})
                    message += " | autoregressive generation complete"
                if config.get("include_autoregressive", False) and not supports_autoregressive:
                    message += " | autoregressive comparison skipped"
                print(message)
                continue
            correct = 0; ar_correct = 0
            total = len(examples)
            print(f"\n[{model_label}] {task}: {total} validation samples (diffusion)", flush=True)
            # Complete the diffusion pass before switching to the optional
            # autoregressive baseline, avoiding per-example model switching.
            diffusion_progress = tqdm(examples, desc=f"{model_label}/{task} diffusion", unit="sample")
            for index, example in enumerate(diffusion_progress, start=1):
                diffusion_text = _generate_diffusion(session, example.prompt, task_settings, mode)
                diffusion_ok = score_prediction(example, diffusion_text)
                record = {"model": model_label, "corruption_mode": mode, "task": task, "example_id": example.example_id, "method": "diffusion", "prompt": example.prompt, "prediction": diffusion_text, "target": example.answer, "correct": diffusion_ok, "inference_settings": task_settings}
                if example.kind != "code":
                    record.update(extracted_prediction=extract_answer(diffusion_text, example.kind), extracted_target=extract_answer(example.answer, example.kind))
                reporter.save_result(record); correct += int(diffusion_ok)
                diffusion_progress.set_postfix(correct=f"{correct}/{index}", accuracy=f"{correct / index:.3f}")
            if config.get("include_autoregressive", False) and supports_autoregressive:
                print(f"[{model_label}] {task}: {total} validation samples (autoregressive)", flush=True)
                ar_progress = tqdm(examples, desc=f"{model_label}/{task} autoregressive", unit="sample")
                for index, example in enumerate(ar_progress, start=1):
                    ar_text = _generate_ar(session, example.prompt, int(task_settings.get("max_new_tokens", 256)), original_base=True)
                    ar_ok = score_prediction(example, ar_text); ar_correct += int(ar_ok)
                    record = {"model": model_label, "evaluation_model": ar_model_name, "model_variant": "original_base", "corruption_mode": mode, "task": task, "example_id": example.example_id, "method": "autoregressive", "prompt": example.prompt, "prediction": ar_text, "target": example.answer, "correct": ar_ok, "inference_settings": {"max_new_tokens": int(task_settings.get("max_new_tokens", 256))}}
                    if example.kind != "code":
                        record.update(extracted_prediction=extract_answer(ar_text, example.kind), extracted_target=extract_answer(example.answer, example.kind))
                    reporter.save_result(record)
                    ar_progress.set_postfix(correct=f"{ar_correct}/{index}", accuracy=f"{ar_correct / index:.3f}")
            summary = {"model": model_label, "corruption_mode": mode, "task": task, "method": "diffusion", "inference_settings": task_settings, "accuracy": correct / max(len(examples), 1), "correct": correct, "total": len(examples)}
            reporter.save_summary(summary)
            message = f"{model_label} | {task} | diffusion accuracy={summary['accuracy']:.4f} ({correct}/{len(examples)})"
            if config.get("include_autoregressive", False):
                if not supports_autoregressive:
                    message += " | autoregressive comparison skipped"
                    print(message)
                    continue
                ar_summary = {"model": model_label, "evaluation_model": ar_model_name, "model_variant": "original_base", "corruption_mode": mode, "task": task, "method": "autoregressive", "inference_settings": {"max_new_tokens": int(task_settings.get("max_new_tokens", 256))}, "accuracy": ar_correct / max(len(examples), 1), "correct": ar_correct, "total": len(examples)}
                reporter.save_summary(ar_summary)
                message += f" | autoregressive accuracy={ar_summary['accuracy']:.4f} ({ar_correct}/{len(examples)})"
            print(message)
        print(f"Released generation model for {model_label}; clearing GPU memory before the next model.", flush=True)
        release_session(session)
        del session
    # Generation models are no longer needed; release the last session before
    # loading the shared reference model to keep peak GPU memory manageable.
    if open_ended_pending:
        print("\nLoading shared perplexity reference model...", flush=True)
        reference_model, reference_tokenizer, reference_device, reference_info = _load_perplexity_reference(config)
        print(f"Scoring {len(open_ended_pending)} open-ended result groups with {reference_info['model_name_or_path']}...", flush=True)
        for group in open_ended_pending:
            scores = score_texts_with_model(reference_model, reference_tokenizer, reference_device, group["texts"])
            for example, text, per_text in zip(group["examples"], group["texts"], scores["per_text"]):
                reporter.save_result({
                    "model": group["model"], "corruption_mode": group["corruption_mode"], "task": group["task"],
                    "example_id": example.example_id, "method": group["method"],
                    "prompt": example.prompt, "prediction": text,
                    "inference_settings": group["inference_settings"],
                    "perplexity_reference": reference_info,
                    **per_text,
                    **({"evaluation_model": group["evaluation_model"], "model_variant": group["model_variant"]} if "evaluation_model" in group else {}),
                })
            summary = {
                "model": group["model"], "corruption_mode": group["corruption_mode"], "task": group["task"],
                "method": group["method"], "total": len(group["examples"]),
                "inference_settings": group["inference_settings"],
                "perplexity_reference": reference_info,
                "perplexity": scores["perplexity"], "median_perplexity": scores["median_perplexity"], "mean_nll": scores["mean_nll"], "tokens": scores["tokens"],
                "mean_unigram_repetition": sum(item["unigram_repetition"] for item in scores["per_text"]) / max(len(scores["per_text"]), 1),
                "mean_bigram_repetition": sum(item["bigram_repetition"] for item in scores["per_text"]) / max(len(scores["per_text"]), 1),
                "mean_trigram_repetition": sum(item["trigram_repetition"] for item in scores["per_text"]) / max(len(scores["per_text"]), 1),
                **({"evaluation_model": group["evaluation_model"], "model_variant": group["model_variant"]} if "evaluation_model" in group else {}),
            }
            reporter.save_summary(summary)
            print(f"{group['model']} | {group['method']} | median perplexity={summary['median_perplexity']:.4f} | pooled perplexity={summary['perplexity']:.4f} | trigram repetition={summary['mean_trigram_repetition']:.4f}", flush=True)
        del reference_model
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
    run_path = reporter.complete()
    print(f"\nStructured benchmark report written to {run_path}", flush=True)


if __name__ == "__main__":
    main()
