"""Offline token preparation for maintaining the published BYOD datasets."""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any
import torch
from transformers import AutoTokenizer
from diffusion_lm.data import (llama_stored_ids_compatible, prepare_mask_only_cache_record, stored_example_usable)

def prepare_training_data(config: dict[str, Any], train_sample_limit: int | None, accelerator=None):
    """Prepare deterministic clean tokens once; keep corruption online at training time."""
    from contextlib import nullcontext
    main_process_first = accelerator.main_process_first if accelerator is not None else nullcontext
    from datasets import load_dataset
    cache_dir = Path(config.get("cache_dir", "data/huggingface")); cache_dir.mkdir(parents=True, exist_ok=True)
    hf_token = os.getenv("HF_TOKEN")
    # Defer raw downloads entirely when a prepared cache is available.
    raw = None
    def raw_dataset():
        nonlocal raw
        if raw is None:
            raw = load_dataset(
                config["dataset_name"], config.get("dataset_config"),
                revision=config.get("dataset_revision"),
                cache_dir=str(cache_dir), token=hf_token,
            )
        return raw
    split_names = config.get("splits", {"train": "train", "validation": "validation", "test": "test"})
    token_name = config.get("tokenizer_name_or_path", config["model_name_or_path"])
    model_cache = Path(config.get("base_model_cache_dir", "base_models")); model_cache.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(
        token_name,
        revision=config.get("model_revision"),
        use_fast=True,
        token=os.getenv("HF_TOKEN"),
        cache_dir=str(model_cache),
        clean_up_tokenization_spaces=False,
    )
    if tokenizer.pad_token_id is None: tokenizer.pad_token = tokenizer.eos_token
    seed = int(config.get("seed", 42)); torch.manual_seed(seed)
    def indexed(ds):
        """Attach stable original indices for deterministic evaluation corruption."""
        return ds.map(lambda _, index: {"_index": index}, with_indices=True)
    def get_split(spec):
        """Resolve either a named split or a Hugging Face split expression."""
        source = raw_dataset()
        if spec in source:
            return source[spec]
        # Hugging Face split expressions (e.g. train[:8]) are valid smoke-test inputs.
        return load_dataset(
            config["dataset_name"],
            config.get("dataset_config"),
            revision=config.get("dataset_revision"),
            split=spec,
            cache_dir=str(cache_dir),
            token=hf_token,
        )
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

    from diffusion_lm.prepared_cache import preparation_metadata, preparation_key, load_published_prepared_data
    prep_key = preparation_key(preparation_metadata(config, tokenizer, train_sample_limit))
    prep_root = Path(config.get("prepared_data_cache_dir", "data/prepared")) / prep_key
    from diffusion_lm.prepared_cache import cache_complete, restore_prepared_cache, persist_prepared_cache
    persistent_dir = config.get("prepared_data_persistent_cache_dir")
    persistent_root = Path(persistent_dir) / prep_key if persistent_dir else None
    with main_process_first():
        restore_prepared_cache(prep_root, persistent_root)
    prepared_cache_loaded = False
    with main_process_first():
        if cache_complete(prep_root):
            from datasets import load_from_disk
            train_data, val_data, test_data = (load_from_disk(str(prep_root / split)) for split in ("train", "validation", "test"))
            prepared_cache_loaded = True
            print(f"Reusing tokenized data: {prep_root}", flush=True)
        else:
            published = load_published_prepared_data(config, tokenizer, train_sample_limit)
            if published is not None:
                train_data, val_data, test_data = (published[split] for split in ("train", "validation", "test"))
                prep_root.mkdir(parents=True, exist_ok=True)
                for split, dataset in zip(("train", "validation", "test"), (train_data, val_data, test_data)):
                    dataset.save_to_disk(str(prep_root / split))
                prepared_cache_loaded = True
            else:
                train_data, val_data, test_data = (indexed(get_split(split_names[k])) for k in ("train", "validation", "test"))
    if config["corruption_mode"] == "structured" and prepared_cache_loaded and train_sample_limit is not None and len(train_data) > train_sample_limit:
        train_data = train_data.shuffle(seed=int(config.get("seed", 42))).select(range(train_sample_limit))
    if config["corruption_mode"] != "structured" and not prepared_cache_loaded:
        print(f"Preparing tokenized data (first use): {prep_root}", flush=True)
        # The published dataset contains a small number of rows with missing
        # or empty outputs. Remove them before collation, otherwise a worker
        # would fail mid-epoch instead of skipping malformed examples.
        has_output = lambda row: bool((row.get("output") or "").strip())
        train_data = bounded_filter(train_data.shuffle(seed=int(config.get("seed", 42))), has_output, train_sample_limit)
        val_data = val_data.filter(has_output)
        test_data = test_data.filter(has_output)
        preprocessing_workers = int(config.get("preprocessing_num_workers", config.get("num_workers", 1)))
        if preprocessing_workers < 1:
            raise ValueError("preprocessing_num_workers must be positive")
        with main_process_first():
            for key, dataset in (("train", train_data), ("validation", val_data), ("test", test_data)):
                original_columns = dataset.column_names
                dataset = dataset.map(
                    lambda row: prepare_mask_only_cache_record(
                        row,
                        tokenizer,
                        int(config["max_sequence_length"]),
                        bool(config.get("include_answer_eos", True)),
                    ),
                    remove_columns=original_columns,
                    num_proc=preprocessing_workers if preprocessing_workers > 1 else None,
                    writer_batch_size=int(config.get("preprocessing_writer_batch_size", 128)),
                    desc=f"Tokenizing {key} split",
                )
                if key == "train": train_data = dataset
                elif key == "validation": val_data = dataset
                else: test_data = dataset
            prep_root.mkdir(parents=True, exist_ok=True)
            train_data.save_to_disk(str(prep_root / "train"))
            val_data.save_to_disk(str(prep_root / "validation"))
            test_data.save_to_disk(str(prep_root / "test"))
    marker_dropped = {}
    if config["corruption_mode"] == "structured" and not prepared_cache_loaded:
        model_name = token_name.lower()
        if not any(name in model_name for name in ("llama", "meta-llama")):
            raise ValueError("structured mode is supported only for Llama-tokenized data; use mask_only for Qwen/Gemma")
        marker_dropped = {}
        with main_process_first():
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
    with main_process_first():
        persist_prepared_cache(prep_root, persistent_root)
    return tokenizer, train_data, val_data, test_data, marker_dropped

