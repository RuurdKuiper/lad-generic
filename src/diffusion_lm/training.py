"""Accelerate training/evaluation with reproducible denoising validation."""
from __future__ import annotations
import json
import atexit
import hashlib
import os
from pathlib import Path
from typing import Any

import torch
from tqdm.auto import tqdm
from accelerate import Accelerator
from torch.optim import AdamW
from torch.utils.data import DataLoader
from transformers import AutoTokenizer, get_scheduler

from .data import DenoisingCollator, llama_stored_ids_compatible, stored_example_usable
from .loss import masked_denoising_loss
from .modeling import forward_bidirectional, load_denoising_model
from .inference import InferenceSession, denoise_stream


def _write_json(path: Path, value: Any) -> None:
    """Write one structured artifact with deterministic formatting."""
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")


def _append_jsonl(path: Path, value: Any) -> None:
    """Append one metrics record to a JSON Lines file."""
    with path.open("a") as f:
        f.write(json.dumps(value, default=float) + "\n")


def _save_adapter(model, tokenizer, path: Path, initial_norms: dict[str, torch.Tensor] | None = None) -> None:
    """Save LoRA plus independently-unfrozen norm parameters for inference."""
    model.save_pretrained(path, safe_serialization=True, save_embedding_layers=False)
    norm_state = {name: parameter.detach().cpu() for name, parameter in model.named_parameters() if "norm" in name.lower()}
    torch.save(norm_state, path / "normalization_state.pt")
    if initial_norms is not None:
        torch.save(initial_norms, path / "normalization_initial_state.pt")
    tokenizer.save_pretrained(path)


def _loader(dataset, collator, batch_size, shuffle, seed, workers):
    """Build a reproducibly shuffled DataLoader using the supplied collator."""
    generator = torch.Generator().manual_seed(seed)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, collate_fn=collator, num_workers=workers, generator=generator, pin_memory=torch.cuda.is_available())


def _normalization_state(model: torch.nn.Module) -> dict[str, torch.Tensor]:
    """Clone all normalization parameters so base-model evaluation can restore them."""
    return {name: parameter.detach().cpu().clone() for name, parameter in model.named_parameters() if "norm" in name.lower()}


def _load_normalization_state(model: torch.nn.Module, state: dict[str, torch.Tensor]) -> None:
    """Copy a saved normalization state into a model without changing adapters."""
    current = dict(model.named_parameters())
    for name, value in state.items():
        if name in current:
            current[name].data.copy_(value.to(current[name].device, dtype=current[name].dtype))


@torch.no_grad()
def _base_perplexity(model: torch.nn.Module, tokenizer: Any, texts: list[str], initial_norms: dict[str, torch.Tensor], device: torch.device) -> dict[str, float]:
    """Score generated answer text with the original base model, excluding LoRA and trained norms."""
    trained_norms = _normalization_state(model)
    model.eval()
    total_nll = 0.0
    total_tokens = 0
    try:
        _load_normalization_state(model, initial_norms)
        with model.disable_adapter():
            for text in texts:
                encoded = tokenizer(text, return_tensors="pt", add_special_tokens=True)
                input_ids = encoded["input_ids"].to(device)
                if input_ids.shape[1] < 2:
                    continue
                outputs = model(input_ids=input_ids, use_cache=False)
                logits = outputs.logits[:, :-1].float()
                labels = input_ids[:, 1:]
                nll = torch.nn.functional.cross_entropy(logits.transpose(1, 2), labels, reduction="sum")
                total_nll += float(nll.cpu())
                total_tokens += int(labels.numel())
    finally:
        _load_normalization_state(model, trained_norms)
    mean_nll = total_nll / max(total_tokens, 1)
    return {"generation_perplexity": float(torch.exp(torch.tensor(mean_nll))), "generation_mean_nll": mean_nll, "generation_tokens": total_tokens}


def _generation_inference_settings(config: dict[str, Any]) -> dict[str, Any]:
    """Resolve generation settings, including corruption-mode-specific inference."""
    settings = dict(config.get("generation_perplexity", {}))
    if config.get("corruption_mode") == "mask_only":
        # Mask-only training learns to reconstruct fully masked answers. Use a
        # fixed LLaDA-style evaluation setup: begin fully masked and retain the
        # most confident recovered tokens between refinement steps.
        settings.update(
            max_new_tokens=64,
            num_steps=32,
            noise_level=1.0,
            temperature=1.0,
            top_k=100,
            permanent_unmask=True,
            confidence_guided=True,
        )
    return settings


def _available_output_dir(path: Path) -> Path:
    """Return path or the next unused suffixed sibling without modifying it."""
    if not path.exists():
        return path
    suffix = 1
    while True:
        candidate = path.parent / f"{path.name}_{suffix}"
        if not candidate.exists():
            return candidate
        suffix += 1


def generation_validation(model: torch.nn.Module, tokenizer: Any, mask_token_id: int, config: dict[str, Any], initial_norms: dict[str, torch.Tensor], device: torch.device, output: Path, step: int) -> dict[str, float]:
    """Generate fixed prompts step-by-step, save trajectories, and calculate base perplexity."""
    settings = _generation_inference_settings(config)
    prompts = settings.get("prompts", ["What do you know about Amsterdam?", "Tell me a story about a little dwarf.", "Why is the sky blue?", "Explain how plants grow.", "What makes a good friend?"])
    session = InferenceSession(model, tokenizer, device, output, config, mask_token_id, str(config.get("quantization", "none")))
    trajectories = []
    finals = []
    model.eval()
    for prompt_index, prompt in enumerate(prompts[: int(settings.get("num_prompts", 5))]):
        states = []
        for generated_text, status, _html in denoise_stream(session, prompt, settings.get("system_prompt", "You are a helpful assistant."), int(settings.get("max_new_tokens", 128)), int(settings.get("num_steps", 32)), float(settings.get("noise_level", .5)), float(settings.get("temperature", .7)), int(settings.get("top_k", 20)), int(settings.get("seed", 1234)) + prompt_index, bool(settings.get("permanent_unmask", False)), bool(settings.get("confidence_guided", False)), bool(settings.get("proportional_unmask", True)), bool(settings.get("early_stopping", False))):
            states.append(generated_text)
        finals.append(states[-1] if states else "")
        final_text = finals[-1]
        trajectories.append({"step": step, "prompt_index": prompt_index, "unigram_repetition": _ngram_repetition(final_text, tokenizer, 1), "bigram_repetition": _ngram_repetition(final_text, tokenizer, 2), "trigram_repetition": _ngram_repetition(final_text, tokenizer, 3), "prompt": prompt, "final": final_text, "states": states})
    generation_metrics = _base_perplexity(model, tokenizer, finals, initial_norms, device)
    for trajectory in trajectories:
        # Rebuild the mapping to keep the JSONL field order stable/readable.
        trajectory["generation_perplexity"] = generation_metrics["generation_perplexity"]
        ordered = {"step": trajectory["step"], "prompt_index": trajectory["prompt_index"], "unigram_repetition": trajectory["unigram_repetition"], "bigram_repetition": trajectory["bigram_repetition"], "trigram_repetition": trajectory["trigram_repetition"], "generation_perplexity": trajectory["generation_perplexity"], "prompt": trajectory["prompt"], "final": trajectory["final"], "states": trajectory["states"]}
        trajectory.clear(); trajectory.update(ordered)
    generation_path = output / "generation_metrics.jsonl"
    with generation_path.open("a") as stream:
        for trajectory in trajectories:
            stream.write(json.dumps(trajectory, ensure_ascii=False) + "\n")
    return generation_metrics


def _ngram_repetition(text: str, tokenizer: Any, n: int = 3) -> float:
    """Return the fraction of n-gram occurrences repeated beyond their first use."""
    tokens = [token for token in tokenizer.encode(text, add_special_tokens=False) if token not in set(getattr(tokenizer, "all_special_ids", []))]
    if len(tokens) < n:
        return 0.0
    # Compare non-overlapping chunks: [A B] vs [C D], not [A B] vs [B C].
    grams = [tuple(tokens[i : i + n]) for i in range(0, len(tokens) - n + 1, n)]
    return float(1.0 - len(set(grams)) / len(grams))


@torch.no_grad()
def evaluate(model, loader, accelerator, mode: str, all_tokens: bool = False, eos_padding_loss: bool = False) -> dict[str, float]:
    """Evaluate deterministic denoising loss and aggregate metrics across ranks."""
    model.eval()
    totals = {"weighted_loss_sum": 0.0, "unweighted_ce_sum": 0.0, "valid_examples": 0, "supervised_tokens": 0, "eligible_answer_tokens": 0, "masked_tokens": 0, "t_sum": 0.0, "t_count": 0}
    for batch in loader:
        logits = forward_bidirectional(model, batch["input_ids"], batch["padding_mask"])
        t = batch["sampled_t"] if mode == "mask_only" and not all_tokens else None
        normalization_mask = batch["answer_mask"] | batch["padding_mask"] if eos_padding_loss else batch["answer_mask"]
        loss, m = masked_denoising_loss(logits, batch["labels"], batch["loss_mask"], t, normalization_mask)
        valid = int(m["valid_examples"])
        tokens = int(m["supervised_tokens"])
        totals["weighted_loss_sum"] += float(loss) * valid
        totals["unweighted_ce_sum"] += float(m["unweighted_masked_token_ce"]) * tokens
        totals["valid_examples"] += valid
        totals["supervised_tokens"] += tokens
        totals["eligible_answer_tokens"] += int((batch["answer_mask"] & ~batch["padding_mask"]).sum())
        totals["masked_tokens"] += int(batch["loss_mask"].sum())
        if mode == "mask_only":
            totals["t_sum"] += float(torch.nansum(batch["sampled_t"]))
            totals["t_count"] += len(batch["sampled_t"])
    totals = accelerator.reduce(torch.tensor([totals[k] for k in totals], device=accelerator.device), reduction="sum").tolist()
    keys = ["weighted_loss_sum", "unweighted_ce_sum", "valid_examples", "supervised_tokens", "eligible_answer_tokens", "masked_tokens", "t_sum", "t_count"]
    d = dict(zip(keys, totals))
    d["weighted_loss"] = d["weighted_loss_sum"] / max(d["valid_examples"], 1)
    d["unweighted_masked_token_ce"] = d["unweighted_ce_sum"] / max(d["supervised_tokens"], 1)
    d["realized_masked_fraction"] = d["masked_tokens"] / max(d["eligible_answer_tokens"], 1)
    if mode == "mask_only": d["mean_sampled_t"] = d["t_sum"] / max(d["t_count"], 1)
    return d


def run_training(config: dict[str, Any]) -> dict[str, Any]:
    """Execute model setup, training, validation, selection, and final testing."""
    storage_root = os.getenv("LAD_STORAGE")
    if storage_root:
        # Relative configured paths become node-local; absolute paths preserve
        # their existing local-execution meaning.
        for key, default in {
            "output_dir": "outputs", "cache_dir": "data/huggingface",
            "base_model_cache_dir": "base_models",
            "prepared_data_cache_dir": "data/prepared",
            "resume_from_checkpoint": None, "resume_from_adapter": None,
        }.items():
            value = config.get(key, default)
            if value and not Path(value).is_absolute():
                config[key] = str(Path(storage_root) / value)
    output_root = os.getenv("LAD_OUTPUT_ROOT")
    if output_root and config.get("output_dir"):
        output_path = Path(config["output_dir"])
        if not output_path.is_absolute():
            config["output_dir"] = str(Path(output_root) / output_path)
    output = Path(config["output_dir"])
    if not config.get("resume_from_checkpoint") and not config.get("resume_from_adapter"):
        output = _available_output_dir(output)
        config["output_dir"] = str(output)
    output.mkdir(parents=True, exist_ok=True)
    configured_updates_hint = config.get("max_updates")
    if configured_updates_hint is None:
        configured_updates_hint = config.get("max_steps")
    train_sample_limit = None
    if configured_updates_hint is not None:
        configured_updates_hint = int(configured_updates_hint)
        if configured_updates_hint < 1:
            raise ValueError("max_updates must be a positive number of gradient updates")
        train_sample_limit = configured_updates_hint * int(config.get("gradient_accumulation_steps", 1)) * int(config.get("batch_size", 1))
    accelerator = Accelerator(gradient_accumulation_steps=int(config.get("gradient_accumulation_steps", 1)), mixed_precision=None if config.get("precision", "fp32") == "fp32" else config["precision"])
    # Ensure NCCL process groups are released when a worker is interrupted
    # (for example with Ctrl-C or a scheduler pre-emption signal).
    def _cleanup_process_group() -> None:
        """Destroy the distributed process group during interpreter shutdown."""
        import torch.distributed as dist
        if dist.is_available() and dist.is_initialized():
            dist.destroy_process_group()
    atexit.register(_cleanup_process_group)
    checkpoint_mode = config.get("checkpoint_mode", "only_best_model")
    if checkpoint_mode not in {"only_best_model", "every_checkpoint", "every_model"}:
        raise ValueError("checkpoint_mode must be 'only_best_model', 'every_model', or 'every_checkpoint'")
    from datasets import load_dataset
    cache_dir = Path(config.get("cache_dir", "data/huggingface")); cache_dir.mkdir(parents=True, exist_ok=True)
    hf_token = os.getenv("HF_TOKEN")
    # Serialize the initial dataset download/cache population so distributed
    # workers do not all perform the expensive preparation concurrently.
    with accelerator.main_process_first():
        raw = load_dataset(config["dataset_name"], config.get("dataset_config"), cache_dir=str(cache_dir), token=hf_token)
    split_names = config.get("splits", {"train": "train", "validation": "validation", "test": "test"})
    token_name = config.get("tokenizer_name_or_path", config["model_name_or_path"])
    model_cache = Path(config.get("base_model_cache_dir", "base_models")); model_cache.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(token_name, use_fast=True, token=os.getenv("HF_TOKEN"), cache_dir=str(model_cache), clean_up_tokenization_spaces=False)
    if tokenizer.pad_token_id is None: tokenizer.pad_token = tokenizer.eos_token
    seed = int(config.get("seed", 42)); torch.manual_seed(seed)
    def indexed(ds):
        """Attach stable original indices for deterministic evaluation corruption."""
        return ds.map(lambda _, index: {"_index": index}, with_indices=True)
    def get_split(spec):
        """Resolve either a named split or a Hugging Face split expression."""
        if spec in raw:
            return raw[spec]
        # Hugging Face split expressions (e.g. train[:8]) are valid smoke-test inputs.
        return load_dataset(config["dataset_name"], config.get("dataset_config"), split=spec, cache_dir=str(cache_dir), token=hf_token)
    def bounded_filter(dataset, predicate, limit: int | None):
        """Filter only as many source rows as needed for a capped run."""
        if limit is None or len(dataset) <= limit:
            return dataset.filter(predicate)
        from datasets import concatenate_datasets
        chunks = []
        kept = 0
        chunk_size = 2048
        for start in range(0, len(dataset), chunk_size):
            chunk = dataset.select(range(start, min(start + chunk_size, len(dataset))))
            filtered = chunk.filter(predicate)
            if len(filtered):
                chunks.append(filtered)
                kept += len(filtered)
            if kept >= limit:
                break
        if not chunks:
            return dataset.select([])
        result = concatenate_datasets(chunks)
        return result.select(range(min(limit, len(result))))

    prep_key = hashlib.sha256(json.dumps({"dataset": config["dataset_name"], "config": config.get("dataset_config"), "tokenizer": token_name, "mode": config["corruption_mode"], "max_length": int(config["max_sequence_length"]), "include_answer_eos": bool(config.get("include_answer_eos", True)), "train_sample_limit": train_sample_limit}, sort_keys=True).encode()).hexdigest()[:16]
    prep_root = Path(config.get("prepared_data_cache_dir", "data/prepared")) / prep_key
    prepared_cache_loaded = False
    with accelerator.main_process_first():
        if config["corruption_mode"] == "structured" and all((prep_root / split).is_dir() for split in ("train", "validation", "test")):
            from datasets import load_from_disk
            train_data, val_data, test_data = (load_from_disk(str(prep_root / split)) for split in ("train", "validation", "test"))
            prepared_cache_loaded = True
        else:
            train_data, val_data, test_data = (indexed(get_split(split_names[k])) for k in ("train", "validation", "test"))
    if config["corruption_mode"] == "structured" and prepared_cache_loaded and train_sample_limit is not None and len(train_data) > train_sample_limit:
        train_data = train_data.shuffle(seed=int(config.get("seed", 42))).select(range(train_sample_limit))
    if config["corruption_mode"] != "structured":
        # The published dataset contains a small number of rows with missing
        # or empty outputs. Remove them before collation, otherwise a worker
        # would fail mid-epoch instead of skipping malformed examples.
        has_output = lambda row: bool((row.get("output") or "").strip())
        train_data = bounded_filter(train_data.shuffle(seed=int(config.get("seed", 42))), has_output, train_sample_limit)
        val_data = val_data.filter(has_output)
        test_data = test_data.filter(has_output)
    marker_dropped = {}
    if config["corruption_mode"] == "structured" and not prepared_cache_loaded:
        model_name = token_name.lower()
        if not any(name in model_name for name in ("llama", "meta-llama")):
            raise ValueError("structured mode is supported only for Llama-tokenized data; use mask_only for Qwen/Gemma")
        marker_dropped = {}
        with accelerator.main_process_first():
            if train_sample_limit is not None and len(train_data) > train_sample_limit:
                train_data = train_data.shuffle(seed=int(config.get("seed", 42)))
            for key, dataset in (("train", train_data), ("validation", val_data), ("test", test_data)):
                before = len(dataset)
                limit = train_sample_limit if key == "train" else None
                dataset = bounded_filter(dataset, lambda row: llama_stored_ids_compatible(row, tokenizer) and stored_example_usable(row, tokenizer, int(config["max_sequence_length"]), bool(config.get("include_answer_eos", True))), limit)
                marker_dropped[key] = before - len(dataset)
                if key == "train": train_data = dataset
                elif key == "validation": val_data = dataset
                else: test_data = dataset
            prep_root.mkdir(parents=True, exist_ok=True)
            train_data.save_to_disk(str(prep_root / "train"))
            val_data.save_to_disk(str(prep_root / "validation"))
            test_data.save_to_disk(str(prep_root / "test"))
    validation_limit = config.get("validation_samples", 200)
    if validation_limit is not None:
        validation_limit = min(int(validation_limit), len(val_data))
        val_data = val_data.select(range(validation_limit))
    common = dict(tokenizer=tokenizer, corruption_mode=config["corruption_mode"], max_sequence_length=int(config["max_sequence_length"]), include_answer_eos=bool(config.get("include_answer_eos", True)), pad_to_multiple_of=config.get("pad_to_multiple_of"), structured_loss_behavior=config.get("structured_loss_behavior", "all_answer_tokens"), eos_padding_loss=config.get("eos_padding_loss"), seed=seed, t_min=float(config.get("t_min", .1)), multi_turn_prob=float(config.get("multi_turn_prob", 0.0)), max_history_turns=int(config.get("max_history_turns", 2)))
    train_collator = DenoisingCollator(**common, deterministic=False)
    # Keep validation single-turn by default; multi-turn can be enabled
    # explicitly when comparing models on conversational context.
    eval_collator = DenoisingCollator(**common, deterministic=True)
    train_loader = _loader(train_data.shuffle(seed=seed), train_collator, int(config["batch_size"]), True, seed, int(config.get("num_workers", 0)))
    val_loader = _loader(val_data, eval_collator, int(config.get("eval_batch_size", config["batch_size"])), False, seed, int(config.get("num_workers", 0)))
    test_loader = _loader(test_data, eval_collator, int(config.get("eval_batch_size", config["batch_size"])), False, seed, int(config.get("num_workers", 0)))
    model, audit = load_denoising_model(config)
    initial_norms = _normalization_state(model)
    resolved = dict(config); resolved["eos_padding_loss"] = train_collator.eos_padding_loss; resolved["training_samples_used"] = len(train_data); resolved["training_sample_limit"] = train_sample_limit; resolved["validation_samples_used"] = len(val_data); resolved["structured_marker_dropped"] = marker_dropped if config["corruption_mode"] == "structured" else {}
    _write_json(output / "resolved_config.json", resolved); _write_json(output / "parameter_audit.json", audit); _write_json(output / "mask_token.json", train_collator.mask_info)
    trainable_parameters = (p for p in model.parameters() if p.requires_grad)
    optimizer_name = str(config.get("optimizer", "adamw")).lower()
    if optimizer_name in {"adamw8bit", "8bit_adamw", "paged_adamw8bit"}:
        try:
            import bitsandbytes as bnb
        except ImportError as exc:
            raise ImportError("optimizer=adamw8bit requires bitsandbytes; install it on CUDA Linux with `pip install bitsandbytes`") from exc
        optimizer = bnb.optim.AdamW8bit(trainable_parameters, lr=float(config["learning_rate"]), weight_decay=float(config.get("weight_decay", 0.0)))
    elif optimizer_name == "adamw":
        optimizer = AdamW(trainable_parameters, lr=float(config["learning_rate"]), weight_decay=float(config.get("weight_decay", 0.0)))
    else:
        raise ValueError(f"Unknown optimizer={optimizer_name}; expected adamw or adamw8bit")
    grad_accumulation = int(config.get("gradient_accumulation_steps", 1))
    max_grad_norm = config.get("max_grad_norm")
    if max_grad_norm is not None and float(max_grad_norm) <= 0:
        raise ValueError("max_grad_norm must be positive when set")
    # `max_updates` is deliberately expressed in optimizer/gradient updates,
    # rather than dataloader batches. Keep max_steps as a backwards-compatible
    # alias for existing configurations.
    configured_updates = config.get("max_updates")
    if configured_updates is None:
        configured_updates = config.get("max_steps")
    if configured_updates is not None and int(configured_updates) < 1:
        raise ValueError("max_updates must be a positive number of gradient updates")
    max_updates = int(configured_updates) if configured_updates is not None else (len(train_loader) * int(config.get("epochs", 1)) + grad_accumulation - 1) // grad_accumulation
    max_steps = max_updates * grad_accumulation
    scheduler = get_scheduler(config.get("scheduler", "linear"), optimizer, int(config.get("warmup_steps", 0)), max_updates)
    model, optimizer, train_loader, val_loader, test_loader, scheduler = accelerator.prepare(model, optimizer, train_loader, val_loader, test_loader, scheduler)
    start_step = 0
    if resume := config.get("resume_from_checkpoint"):
        accelerator.load_state(resume)
        state = json.loads((Path(resume) / "state.json").read_text()); start_step = int(state["step"])
        train_loader = accelerator.skip_first_batches(train_loader, start_step * int(config.get("gradient_accumulation_steps", 1)))
    best = float("inf"); metrics_path = output / "metrics.jsonl"
    model.train()
    progress = tqdm(total=max_updates, initial=start_step, desc="training", unit="update", disable=not accelerator.is_local_main_process)
    interval_loss_sum = 0.0
    interval_examples = 0
    update_step = start_step
    for microstep, batch in enumerate(train_loader, start=start_step * grad_accumulation + 1):
        step = microstep
        if step > max_steps: break
        with accelerator.accumulate(model):
            logits = forward_bidirectional(model, batch["input_ids"], batch["padding_mask"])
            use_t_weighting = config["corruption_mode"] == "mask_only" and config.get("structured_loss_behavior", "all_answer_tokens") != "all_tokens"
            normalization_mask = batch["answer_mask"] | batch["padding_mask"] if bool(config.get("eos_padding_loss", False)) else batch["answer_mask"]
            loss, info = masked_denoising_loss(logits, batch["labels"], batch["loss_mask"], batch["sampled_t"] if use_t_weighting else None, normalization_mask)
            accelerator.backward(loss)
            # Clip only after all gradient-accumulation microbatches have
            # contributed, matching Trainer's max_grad_norm behavior.
            if accelerator.sync_gradients and max_grad_norm is not None:
                accelerator.clip_grad_norm_(model.parameters(), float(max_grad_norm))
            optimizer.step(); scheduler.step(); optimizer.zero_grad()
        loss_value = float(loss.detach().cpu())
        batch_examples = int(info["valid_examples"])
        interval_loss_sum += loss_value * batch_examples
        interval_examples += batch_examples
        if accelerator.sync_gradients:
            update_step += 1
            progress.update(1)
            progress.set_postfix(train_loss=f"{loss_value:.4f}", train_avg=f"{interval_loss_sum / max(interval_examples, 1):.4f}")
        if not accelerator.sync_gradients:
            continue
        if accelerator.is_main_process and step % int(config.get("logging_steps", 10)) == 0:
            _append_jsonl(metrics_path, {"split": "train", "step": step, "weighted_loss": loss_value, "supervised_tokens": int(info["supervised_tokens"])})
        if update_step % int(config.get("validation_steps", 100)) == 0 or update_step == max_updates:
            metrics = evaluate(model, val_loader, accelerator, config["corruption_mode"], config.get("structured_loss_behavior") == "all_tokens", bool(config.get("eos_padding_loss", False)))
            if accelerator.is_main_process:
                generation_settings = config.get("generation_perplexity", {})
                if generation_settings.get("enabled", False):
                    unwrapped = accelerator.unwrap_model(model)
                    metrics.update(generation_validation(unwrapped, tokenizer, train_collator.mask_info["mask_token_id"], config, initial_norms, accelerator.device, output, step))
                metrics.update({"split": "validation", "step": update_step}); _append_jsonl(metrics_path, metrics)
                generation_note = f" | generation_ppl={metrics['generation_perplexity']:.4f}" if "generation_perplexity" in metrics else ""
                train_avg = interval_loss_sum / max(interval_examples, 1)
                progress.write(f"step {update_step}/{max_updates} | train_loss_avg={train_avg:.4f} | validation_loss={metrics['weighted_loss']:.4f}{generation_note}")
                if accelerator.is_main_process:
                    _append_jsonl(metrics_path, {"split": "train_interval", "step": update_step, "weighted_loss": train_avg, "examples": interval_examples})
                interval_loss_sum = 0.0
                interval_examples = 0
                if metrics["weighted_loss"] < best:
                    best = metrics["weighted_loss"]; unwrapped = accelerator.unwrap_model(model); _save_adapter(unwrapped, tokenizer, output / "best", initial_norms)
            accelerator.wait_for_everyone()
            model.train()
        if checkpoint_mode in {"every_checkpoint", "every_model"} and (update_step % int(config.get("checkpoint_steps", 500)) == 0 or update_step == max_updates):
            checkpoint = output / f"checkpoint-{update_step}"
            if checkpoint_mode == "every_checkpoint":
                accelerator.save_state(checkpoint, safe_serialization=True, save_embedding_layers=False)
                if accelerator.is_main_process:
                    _write_json(checkpoint / "state.json", {"step": update_step, "best_validation_loss": best})
            elif accelerator.is_main_process:
                # Inference-ready snapshot without optimizer/scheduler/RNG
                # state; it can also warm-start through resume_from_adapter.
                _save_adapter(accelerator.unwrap_model(model), tokenizer, checkpoint, initial_norms)
    progress.close()
    accelerator.wait_for_everyone()
    if accelerator.is_main_process and checkpoint_mode == "every_checkpoint":
        unwrapped = accelerator.unwrap_model(model); _save_adapter(unwrapped, tokenizer, output / "final", initial_norms)
    elif accelerator.is_main_process and checkpoint_mode == "every_model":
        unwrapped = accelerator.unwrap_model(model); _save_adapter(unwrapped, tokenizer, output / "final", initial_norms)
    # Test is deliberately after best-model selection/finalization.
    test_metrics = evaluate(model, test_loader, accelerator, config["corruption_mode"], config.get("structured_loss_behavior") == "all_tokens", bool(config.get("eos_padding_loss", False)))
    if accelerator.is_main_process: _write_json(output / "test_metrics.json", test_metrics)
    accelerator.end_training()
    return test_metrics
