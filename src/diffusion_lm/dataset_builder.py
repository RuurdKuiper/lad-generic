"""Build a split-safe, length-bounded instruction-tuning mixture."""
from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from .data import apply_neutral_chat_template


DEFAULT_WEIGHTS = {"general": 0.45, "reasoning": 0.18, "math": 0.18, "code": 0.19}
DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."
SYSTEM_PROMPTS = {
    "general": [
        "Respond helpfully, accurately, and clearly.",
        "You are a knowledgeable assistant. Give a direct and useful response.",
        "You are a thoughtful assistant. Follow the user's instructions carefully.",
    ],
    "reasoning": [
        "You are a careful reasoning assistant. Answer accurately and follow the requested format.",
        "Analyze the question carefully and select the best-supported answer.",
    ],
    "math": [
        "You are a careful mathematics tutor. Explain the solution clearly.",
        "Solve mathematical problems accurately and show the relevant reasoning.",
    ],
    "code": [
        "You are an expert programming assistant. Produce correct and readable code.",
        "Help with programming tasks using robust, clear solutions.",
    ],
}


@dataclass
class BuildConfig:
    tokenizer_name: str = "meta-llama/Llama-3.1-8B-Instruct"
    total_examples: int = 500_000
    max_prompt_tokens: int = 256
    max_sequence_tokens: int = 512
    validation_fraction: float = 0.01
    test_fraction: float = 0.01
    seed: int = 42
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    cache_dir: str = "data/huggingface"


def normalized_prompt(text: str) -> str:
    """Normalize a prompt for conservative exact-match decontamination."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (text or "").casefold())).strip()


def prompt_hash(text: str) -> str:
    return hashlib.sha256(normalized_prompt(text).encode()).hexdigest()


def format_mc(question: str, choices: list[Any], answer: int | str) -> dict[str, str] | None:
    labels = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[: len(choices)])
    if isinstance(answer, str) and answer in labels:
        index = labels.index(answer)
    else:
        try:
            index = int(answer)
        except (TypeError, ValueError):
            return None
    if not 0 <= index < len(choices):
        return None
    options = "\n".join(f"{label}: {choice}" for label, choice in zip(labels, choices))
    return {
        "instruction": "Answer the following multiple-choice question.",
        "input": f"{question.strip()}\n\n{options}",
        "output": f"{labels[index]}: {choices[index]}",
    }


def format_tulu(row: dict[str, Any]) -> dict[str, str] | None:
    """Convert the final user/assistant exchange; include short prior turns as context."""
    # Tulu is itself a broad mixture. Keep its explicit math/code subsets out of
    # the general bucket because those categories are independently controlled.
    source = str(row.get("source", "")).casefold()
    if "math" in source or "code" in source:
        return None
    messages = [m for m in row.get("messages", []) if (m.get("content") or "").strip()]
    assistant_positions = [i for i, m in enumerate(messages) if m.get("role") == "assistant" and i]
    if not assistant_positions:
        return None
    end = assistant_positions[-1]
    user = next((i for i in range(end - 1, -1, -1) if messages[i].get("role") == "user"), None)
    if user is None:
        return None
    native_system = next((m["content"].strip() for m in messages if m.get("role") == "system"), "")
    history = [m for m in messages[:user] if m.get("role") != "system"]
    history_text = "\n\n".join(f"{m.get('role', 'user').title()}: {m['content'].strip()}" for m in history)
    question = messages[user]["content"].strip()
    return {
        "system": native_system,
        "instruction": "Continue the conversation helpfully." if history_text else "",
        "input": f"Conversation so far:\n{history_text}\n\nUser: {question}" if history_text else question,
        "output": messages[end]["content"].strip(),
    }


def format_hellaswag(row: dict[str, Any]) -> dict[str, str] | None:
    """Make HellaSwag's sentence/event-completion task explicit."""
    choices = row.get("endings", [])
    formatted = format_mc(row.get("ctx", ""), choices, row.get("label"))
    if formatted is None:
        return None
    options = "\n".join(f"{label}: {choice}" for label, choice in zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", choices))
    return {
        "instruction": "Choose the option that most plausibly continues the described event.",
        "input": (
            f"Beginning of the event:\n{row.get('ctx', '').strip()}\n\n"
            f"What most plausibly happens next?\n{options}"
        ),
        "output": formatted["output"],
    }


def choose_system_prompt(item: dict[str, str], source: str, prompt_key: str) -> str:
    """Preserve native systems; otherwise vary a compatible prompt deterministically."""
    native = (item.get("system") or "").strip()
    if native:
        return native
    category = source.split(":", 1)[0]
    digest = int(prompt_key[:16], 16)
    # Retain the established default for 70% of generated rows. The remaining
    # rows use safe category-specific wording that does not conflict with the
    # expected response style.
    if digest % 10 < 7:
        return DEFAULT_SYSTEM_PROMPT
    variants = SYSTEM_PROMPTS[category]
    return variants[(digest // 10) % len(variants)]


def _targets(total: int, weights: dict[str, float]) -> dict[str, int]:
    if set(weights) != set(DEFAULT_WEIGHTS) or any(v < 0 for v in weights.values()):
        raise ValueError(f"weights must contain exactly {sorted(DEFAULT_WEIGHTS)} with non-negative values")
    scale = sum(weights.values())
    if scale <= 0:
        raise ValueError("at least one mixture weight must be positive")
    targets = {key: int(total * value / scale) for key, value in weights.items()}
    targets[max(targets, key=targets.get)] += total - sum(targets.values())
    return targets


def _take(rows: Iterable[dict[str, Any]], formatter: Callable[[dict[str, Any]], dict[str, str] | None], count: int,
          tokenizer: Any, config: BuildConfig, blocked: set[str], source: str,
          progress: Any | None = None) -> list[dict[str, Any]]:
    accepted = []
    scanned = 0
    for row in rows:
        scanned += 1
        if progress is not None and scanned % 500 == 0:
            progress.set_postfix_str(f"{source}, scanned={scanned:,}", refresh=True)
        item = formatter(row)
        if not item or not item["output"].strip():
            continue
        user = "\n\n".join(x for x in (item["instruction"].strip(), item["input"].strip()) if x)
        # Reject pathological upstream records before regex normalization or
        # hashing. One observed prompt contains more than a million tokens;
        # running Unicode regexes over it can look like a hung process.
        if len(user) > config.max_prompt_tokens * 50 or len(item["output"]) > config.max_sequence_tokens * 50:
            continue
        key = prompt_hash(user)
        # Compare both the raw task text and its instruction-wrapped form: held-out
        # benchmark hashes contain the raw question, while general datasets vary.
        if key in blocked or prompt_hash(item["input"]) in blocked:
            continue
        system = choose_system_prompt(item, source, key)
        if len(system) > config.max_prompt_tokens * 50:
            continue
        prompt_messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        # Tokenize to one token beyond the prompt limit. This proves that a row
        # is oversized without creating enormous arrays or triggering the
        # model's max-length warning.
        prompt_ids = apply_neutral_chat_template(
            tokenizer, prompt_messages, tokenize=True, add_generation_prompt=True,
            truncation=True, max_length=config.max_prompt_tokens + 1,
        )
        if len(prompt_ids) > config.max_prompt_tokens:
            continue
        # Do not render and tokenize the prompt a second time. The generation
        # prefix already ends immediately before assistant content, so append
        # answer IDs and the tokenizer's EOS/EOT marker directly. This matches
        # the representation consumed by source_to_tokens in the trainer.
        answer_limit = config.max_sequence_tokens - len(prompt_ids) - 1
        if answer_limit < 1:
            continue
        answer_ids = tokenizer(
            item["output"].strip(), add_special_tokens=False, truncation=True,
            max_length=answer_limit + 1,
        )["input_ids"]
        if len(answer_ids) > answer_limit:
            continue
        if tokenizer.eos_token_id is None:
            raise ValueError(f"Tokenizer {tokenizer.name_or_path} has no eos_token_id")
        full_ids = list(prompt_ids) + list(answer_ids) + [tokenizer.eos_token_id]
        # Share one immutable-in-practice Python list while rows are buffered;
        # Dataset.from_list materializes the two required Arrow columns later.
        # Keeping two Python list copies here roughly doubles peak preparation
        # memory and causes severe slowdown from memory pressure on Colab.
        clean_ids = list(full_ids)
        accepted.append({**item, "system": system, "input_ids": clean_ids, "labels": clean_ids, "category": source.split(":", 1)[0], "source": source})
        if progress is not None:
            progress.update(1)
        if len(accepted) >= count:
            break
    return accepted


def _evaluation_hashes(load: Callable[..., Any]) -> set[str]:
    """Hash held-out prompts from every benchmark represented in the mixture."""
    blocked: set[str] = set()
    specs = [
        ("allenai/ai2_arc", "ARC-Easy", ("validation", "test"), "question"),
        ("allenai/ai2_arc", "ARC-Challenge", ("validation", "test"), "question"),
        ("cais/mmlu", "all", ("validation", "test"), "question"),
        ("Rowan/hellaswag", None, ("validation", "test"), "ctx"),
        ("openai/gsm8k", "main", ("test",), "question"),
        ("google-research-datasets/mbpp", "sanitized", ("validation", "test"), "prompt"),
    ]
    for path, name, splits, field_name in specs:
        for split in splits:
            for row in load(path, name, split=split):
                blocked.add(prompt_hash(row.get(field_name, "")))
    return blocked


def _repeat_dataset(dataset: Any, count: int, seed: int, concatenate: Callable) -> Any:
    """Return exactly ``count`` rows, cycling the full unique pool before repeats.

    Arrow datasets are concatenated without expanding repeated rows into a
    giant Python list.  A shuffled partial cycle prevents always favoring the
    beginning of the pool when the target is not an exact multiple.
    """
    if not len(dataset):
        raise RuntimeError("cannot oversample an empty category")
    if len(dataset) >= count:
        return dataset.select(range(count))
    cycles, remainder = divmod(count, len(dataset))
    pieces = [dataset] * cycles
    if remainder:
        pieces.append(dataset.shuffle(seed=seed).select(range(remainder)))
    return concatenate(pieces)


def build_dataset(config: BuildConfig, token: str | None = None):
    """Download, normalize, balance, split, and return a DatasetDict."""
    from datasets import Dataset, DatasetDict, Features, Sequence, Value, concatenate_datasets, load_dataset
    from transformers import AutoTokenizer
    from tqdm.auto import tqdm

    cache = config.cache_dir
    load = lambda path, name=None, **kw: load_dataset(path, name, cache_dir=cache, token=token, **kw)
    tokenizer = AutoTokenizer.from_pretrained(config.tokenizer_name, token=token, cache_dir=cache)
    targets = _targets(config.total_examples, config.weights)
    print(f"Building {config.total_examples:,} examples with category targets: {targets}")
    output_features = Features({
        "system": Value("string"), "instruction": Value("string"), "input": Value("string"), "output": Value("string"),
        # All supported vocabularies fit int32. The collator converts these
        # lists to torch.long, so training behavior is unchanged.
        "input_ids": Sequence(Value("int32")), "labels": Sequence(Value("int32")),
        "category": Value("string"), "source": Value("string"),
    })
    print("Loading held-out benchmark prompts for decontamination...", flush=True)
    blocked = _evaluation_hashes(load)
    print(f"Loaded {len(blocked):,} held-out prompt hashes.", flush=True)
    rng = random.Random(config.seed)

    def shuffled(path: str, name: str | None = None, split: str = "train"):
        return load(path, name, split=split).shuffle(seed=config.seed)

    print("Loading source datasets (cached sources should open without downloading)...", flush=True)
    sources: dict[str, list[tuple[str, Iterable[dict[str, Any]], Callable, float]]] = {
        "general": [
            ("general:clean-instruct", shuffled("crumb/Clean-Instruct-3M", split="train"), lambda x: {"instruction": x.get("instruction", ""), "input": x.get("input", ""), "output": x.get("output", "")}, .40),
            ("general:tulu-3", shuffled("allenai/tulu-3-sft-mixture"), format_tulu, .35),
            ("general:alpaca-gpt4", shuffled("vicgalle/alpaca-gpt4"), lambda x: {k: x.get(k, "") for k in ("instruction", "input", "output")}, .20),
            ("general:alpaca", shuffled("tatsu-lab/alpaca"), lambda x: {k: x.get(k, "") for k in ("instruction", "input", "output")}, .05),
        ],
        "reasoning": [
            ("reasoning:mmlu", shuffled("cais/mmlu", "all", "auxiliary_train"), lambda x: format_mc(x["question"], x["choices"], x["answer"]), .73),
            ("reasoning:hellaswag", shuffled("Rowan/hellaswag"), format_hellaswag, .25),
            ("reasoning:arc-easy", shuffled("allenai/ai2_arc", "ARC-Easy"), lambda x: format_mc(x["question"], x["choices"]["text"], x["choices"]["label"].index(x["answerKey"]) if x["answerKey"] in x["choices"]["label"] else -1), .02),
        ],
        "math": [
            ("math:orca", shuffled("microsoft/orca-math-word-problems-200k"), lambda x: {"instruction": "Solve the following math problem step by step.", "input": x.get("question", ""), "output": x.get("answer", "")}, .95),
            ("math:gsm8k", shuffled("openai/gsm8k", "main"), lambda x: {"instruction": "Solve the following math problem step by step.", "input": x.get("question", ""), "output": x.get("answer", "")}, .05),
        ],
        "code": [
            ("code:opencoder", shuffled("OpenCoder-LLM/opc-sft-stage2", "educational_instruct"), lambda x: {"instruction": x.get("instruction", ""), "input": "", "output": x.get("output", "")}, .997),
            ("code:mbpp", shuffled("google-research-datasets/mbpp", "sanitized"), lambda x: {"instruction": "Write Python code to solve the following task.", "input": x.get("prompt", ""), "output": x.get("code", "")}, .003),
        ],
    }
    print("Source datasets loaded; formatting and tokenization are starting.", flush=True)
    groups = []
    for category, entries in sources.items():
        wanted = targets[category]
        progress = tqdm(total=wanted, desc=f"Preparing {category}", unit="rows")
        allocations = [int(wanted * share) for *_, share in entries]
        allocations[0] += wanted - sum(allocations)
        rows = []
        # Keep iterators alive after the preferred-share pass. This lets a
        # larger source contribute additional unused rows when a smaller source
        # cannot meet its allocation, without rescanning or duplicating rows.
        prepared = [(source, data, formatter, iter(data)) for source, data, formatter, _ in entries]
        for (source, _, formatter, iterator), count in zip(prepared, allocations):
            rows.extend(_take(iterator, formatter, count, tokenizer, config, blocked, source, progress))
        if len(rows) < wanted:
            # Exhaust still-unused rows from the largest sources first. Dataset
            # size is only a priority heuristic; exact token filtering remains
            # authoritative.
            for source, data, formatter, iterator in sorted(prepared, key=lambda item: len(item[1]), reverse=True):
                rows.extend(_take(iterator, formatter, wanted - len(rows), tokenizer, config, blocked, source, progress))
                if len(rows) >= wanted:
                    break
        unique_count = len(rows)
        if not unique_count:
            raise RuntimeError(f"{category}: no rows survived filtering")
        rng.shuffle(rows)
        group = Dataset.from_list(rows, features=output_features)
        if unique_count < wanted:
            print(
                f"{category}: {unique_count:,} unique eligible rows; oversampling to {wanted:,} "
                f"({wanted / unique_count:.2f}x exposure)"
            )
            progress.update(wanted - unique_count)
        progress.set_postfix_str(f"{unique_count:,} unique", refresh=True)
        progress.close()
        groups.append(_repeat_dataset(group, wanted, config.seed, concatenate_datasets))
    combined = concatenate_datasets(groups).shuffle(seed=config.seed)
    heldout = config.validation_fraction + config.test_fraction
    if not 0 < heldout < 1:
        raise ValueError("validation_fraction + test_fraction must be between zero and one")
    first = combined.train_test_split(test_size=heldout, seed=config.seed)
    second = first["test"].train_test_split(test_size=config.test_fraction / heldout, seed=config.seed)
    return DatasetDict(train=first["train"], validation=second["train"], test=second["test"])


def write_manifest(dataset: Any, config: BuildConfig, path: str | Path) -> None:
    counts: dict[str, dict[str, int]] = {}
    for split, rows in dataset.items():
        counts[split] = {name: rows["category"].count(name) for name in DEFAULT_WEIGHTS}
    Path(path).write_text(json.dumps({"config": config.__dict__, "rows": counts}, indent=2, sort_keys=True) + "\n")
