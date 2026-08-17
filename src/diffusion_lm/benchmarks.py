"""Small, reproducible benchmark adapters for pure diffusion evaluation."""
from __future__ import annotations

import json
import math
import random
import re
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

import torch


MC_TASKS = {"mmlu", "mmlu_pro", "hellaswag", "arc_c", "gpqa"}
ALL_TASKS = ["mmlu", "mmlu_pro", "hellaswag", "arc_c", "gsm8k", "math", "gpqa", "humaneval", "mbpp"]
OPEN_ENDED_TASK = "open_ended"
AVAILABLE_TASKS = [*ALL_TASKS, OPEN_ENDED_TASK]

# Published pure-diffusion settings for LLaDA-8B-Instruct (paper Appendix B.4
# and the official OpenCompass reproduction configs).  The paper profiles use
# one full generation block, so they contain no semi-autoregressive decoding.
LLADA_INSTRUCT_TASK_SETTINGS: dict[str, dict[str, Any]] = {
    "mmlu": {"max_new_tokens": 3, "num_steps": 3, "block_length": 3},
    "mmlu_pro": {"max_new_tokens": 256, "num_steps": 256, "block_length": 256},
    "hellaswag": {"max_new_tokens": 3, "num_steps": 3, "block_length": 3},
    "arc_c": {"max_new_tokens": 512, "num_steps": 512, "block_length": 512},
    "gsm8k": {"max_new_tokens": 512, "num_steps": 512, "block_length": 512, "confidence_eos_eot_inf": True},
    "math": {"max_new_tokens": 512, "num_steps": 512, "block_length": 512, "confidence_eos_eot_inf": True},
    "gpqa": {"max_new_tokens": 64, "num_steps": 64, "block_length": 64, "confidence_eos_eot_inf": True},
    "humaneval": {"max_new_tokens": 512, "num_steps": 512, "block_length": 512, "logits_eos_inf": True},
    "mbpp": {"max_new_tokens": 256, "num_steps": 256, "block_length": 256, "confidence_eos_eot_inf": True},
}


def _path_slug(value: str) -> str:
    """Turn a model/task label into a stable, filesystem-safe component."""
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-.").lower()
    return slug or "unnamed"


class BenchmarkRunReporter:
    """Write one benchmark invocation into an isolated, structured directory."""

    schema_version = 1

    def __init__(self, results_dir: str | Path, config: dict[str, Any], run_name: str | None = None):
        self.started_at = datetime.now(timezone.utc)
        timestamp = self.started_at.strftime("%Y%m%dT%H%M%S.%fZ")
        self.run_id = timestamp + (f"--{_path_slug(run_name)}" if run_name else "")
        self.path = Path(results_dir) / self.run_id
        self.path.mkdir(parents=True, exist_ok=False)
        self.config = config
        self.summaries: list[dict[str, Any]] = []
        self._write_manifest("running")

    def _write_json(self, path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + "\n")

    def _write_manifest(self, status: str, completed_at: str | None = None) -> None:
        manifest = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "status": status,
            "started_at": self.started_at.isoformat(),
            "completed_at": completed_at,
            "config": self.config,
        }
        self._write_json(self.path / "run.json", manifest)

    def group_path(self, model: str, task: str, method: str) -> Path:
        """Return the directory for one model/task/method result group."""
        return self.path / "models" / _path_slug(model) / _path_slug(task) / _path_slug(method)

    def save_result(self, result: dict[str, Any]) -> None:
        """Append one example only to its model/task/method result file."""
        path = self.group_path(result["model"], result["task"], result["method"]) / "results.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        save_result(path, result)

    def save_summary(self, summary: dict[str, Any]) -> None:
        """Save a group summary and retain it for run/model rollups."""
        self.summaries.append(summary)
        path = self.group_path(summary["model"], summary["task"], summary["method"]) / "summary.json"
        self._write_json(path, summary)

    def complete(self) -> Path:
        """Write model and run rollups, then mark the invocation complete."""
        by_model: dict[str, list[dict[str, Any]]] = {}
        for summary in self.summaries:
            by_model.setdefault(str(summary["model"]), []).append(summary)
        models = []
        for model, summaries in by_model.items():
            model_summary = {"model": model, "results": summaries}
            models.append(model_summary)
            self._write_json(self.path / "models" / _path_slug(model) / "summary.json", model_summary)
        completed_at = datetime.now(timezone.utc).isoformat()
        self._write_json(self.path / "summary.json", {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": completed_at,
            "models": models,
        })
        self._write_manifest("completed", completed_at)
        return self.path


def resolve_generation_settings(config: dict[str, Any], task: str, mode: str) -> dict[str, Any]:
    """Resolve generation settings for a task and corruption mode."""
    settings = dict(config.get("generation", {}))
    mode_settings = config.get("generation_by_corruption", {}).get(mode, {})
    if mode == "legacy" and not mode_settings:
        mode_settings = config.get("generation_by_corruption", {}).get("structured", {})
    settings.update(mode_settings)
    settings.update(config.get("task_generation", {}).get(task, {}))
    settings.update(config.get("task_generation_by_corruption", {}).get(mode, {}).get(task, {}))
    if mode == "mask_only":
        # Mask-only training is evaluated with the full-remasking setup used
        # by the training-time generation validation.
        settings.update(noise_level=1.0, permanent_unmask=True, confidence_guided=True)
    return settings


def resolve_llada_generation_settings(config: dict[str, Any], task: str) -> dict[str, Any]:
    """Resolve official LLaDA-8B-Instruct decoding and per-task paper settings."""
    settings = resolve_generation_settings(config, task, "mask_only")
    for unused in ("noise_level", "top_k", "permanent_unmask", "confidence_guided", "early_stopping", "system_prompt"):
        settings.pop(unused, None)
    profile = LLADA_INSTRUCT_TASK_SETTINGS.get(task, {})
    settings.update(profile)
    settings.update({
        "sampler": "llada_official",
        "temperature": 0.0,
        "cfg_scale": 0.0,
        "remasking": "low_confidence",
        "logits_eos_inf": bool(profile.get("logits_eos_inf", False)),
        "confidence_eos_eot_inf": bool(profile.get("confidence_eos_eot_inf", False)),
        "proportional_unmask": False,
    })
    settings.update(config.get("llada_generation", {}))
    settings.update(config.get("llada_task_generation", {}).get(task, {}))
    settings["block_length"] = int(settings.get("block_length", settings.get("max_new_tokens", 128)))
    return settings

# Fixed prompts make comparisons between runs reproducible.  `limit` can be
# used to evaluate a smaller prefix, while the default benchmark config uses
# all 30 questions.
OPEN_ENDED_PROMPTS = [
    "What do you know about Amsterdam?",
    "Why is the sky blue?",
    "How do plants convert sunlight into energy?",
    "What makes a good friend?",
    "Explain how a refrigerator keeps food cold.",
    "Why do we have different seasons on Earth?",
    "How does vaccination help protect a population?",
    "What is the difference between weather and climate?",
    "Explain the basic idea behind supply and demand.",
    "How does a search engine find relevant web pages?",
    "What causes a rainbow?",
    "How does the human heart circulate blood?",
    "Why do objects fall toward the ground?",
    "Explain what machine learning is in simple terms.",
    "What are the main benefits of regular exercise?",
    "How does the water cycle work?",
    "Why is sleep important for people?",
    "Explain the difference between renewable and nonrenewable energy.",
    "How do trees communicate or share resources?",
    "What is inflation and how does it affect households?",
    "Why do leaves change color in autumn?",
    "How does a bicycle stay balanced while moving?",
    "What are practical ways to reduce household waste?",
    "Explain how an electric battery stores and releases energy.",
    "What is the purpose of the scientific method?",
    "How do languages change over time?",
    "Why are oceans important to the global climate?",
    "What makes an explanation clear and persuasive?",
    "How can someone evaluate whether an online claim is reliable?",
    "Tell a short story about a traveler who learns an unexpected lesson.",
]


@dataclass
class BenchmarkExample:
    """Normalized benchmark item consumed by both diffusion and AR evaluators."""
    task: str
    example_id: str
    prompt: str
    answer: str
    kind: str
    metadata: dict[str, Any]


def _choice_prompt(name: str, question: str, choices: list[Any]) -> str:
    """Match the multiple-choice instruction and input format used for training."""
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    options = "\n".join(f"{letters[i]}: {choice}" for i, choice in enumerate(choices))
    if name == "hellaswag":
        instruction = "Choose the option that most plausibly continues the described event."
        task_input = f"Beginning of the event:\n{question.strip()}\n\nWhat most plausibly happens next?\n{options}"
    else:
        instruction = "Answer the following multiple-choice question."
        task_input = f"{question.strip()}\n\n{options}"
    return f"{instruction}\n\n{task_input}"


def _multiple_choice_fields(name: str, row: dict[str, Any], index: int) -> tuple[str, list[Any], str]:
    """Normalize task-specific question, choice, and answer schemas."""
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if name == "hellaswag":
        question = row.get("ctx", "")
        choices = row.get("endings")
        answer = row.get("label")
    elif name == "arc_c":
        question = row.get("question", "")
        choice_group = row.get("choices") or {}
        choices = choice_group.get("text") if isinstance(choice_group, dict) else choice_group
        labels = [str(label) for label in choice_group.get("label", [])] if isinstance(choice_group, dict) else []
        answer_key = str(row.get("answerKey", ""))
        answer = letters[labels.index(answer_key)] if answer_key in labels else answer_key
    elif name == "gpqa" and not row.get("choices") and not row.get("options"):
        question = row.get("Question", row.get("question", ""))
        choices = [row["Correct Answer"], row["Incorrect Answer 1"], row["Incorrect Answer 2"], row["Incorrect Answer 3"]]
        correct = choices[0]
        random.Random(index).shuffle(choices)
        answer = letters[choices.index(correct)]
    else:
        question = row.get("question", row.get("Question", row.get("query", row.get("ctx", ""))))
        choices = row.get("choices", row.get("options"))
        answer = row.get("answer", row.get("answerKey", row.get("label", row.get("answer_index"))))
    if not isinstance(choices, (list, tuple)) or not choices:
        raise ValueError(f"{name} example {index} has no usable answer choices")
    if isinstance(answer, int) or str(answer).isdigit():
        answer_index = int(answer)
        if not 0 <= answer_index < len(choices):
            raise ValueError(f"{name} example {index} has out-of-range answer index {answer_index}")
        answer = letters[answer_index]
    return str(question), list(choices), str(answer).upper()


def _boxed(text: str) -> str:
    """Extract a final boxed/math answer when present."""
    matches = re.findall(r"\\boxed\{([^{}]+)\}|####\s*([^\n]+)", text or "")
    if not matches:
        return (text or "").strip()
    return (matches[-1][0] or matches[-1][1]).strip()


def _last_number(text: str) -> str:
    """Extract the final numeric candidate, following common GSM8K evaluation."""
    candidates = re.findall(r"[-+]?(?:\d[\d,]*\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", text or "")
    return candidates[-1].replace(",", "").rstrip(".") if candidates else ""


def _normalize_math_answer(text: str) -> str:
    """Normalize a generated or reference final MATH answer for comparison."""
    value = _boxed(text).strip()
    answer_match = re.search(r"(?is)(?:final\s+answer|answer)\s*(?:is|:)\s*(.+)$", value)
    if answer_match:
        value = answer_match.group(1).strip()
    value = re.sub(r"^\$|\$$", "", value.strip())
    value = value.rstrip(".。;,!").strip()
    value = value.replace("\\left", "").replace("\\right", "")
    value = re.sub(r"\s+", "", value).replace(",", "")
    return value


def _numeric_answers_equal(left: str, right: str) -> bool:
    """Compare normalized decimal answers exactly when both are numeric."""
    try:
        return Decimal(left) == Decimal(right)
    except InvalidOperation:
        return False


def _math_answers_equal(prediction: str, target: str) -> bool:
    """Use symbolic MATH verification when installed, with a strict fallback."""
    normalized_prediction = _normalize_math_answer(prediction)
    normalized_target = _normalize_math_answer(target)
    if normalized_prediction == normalized_target or _numeric_answers_equal(normalized_prediction, normalized_target):
        return True
    try:
        from math_verify import parse, verify

        return bool(verify(parse(target), parse(prediction)))
    except (ImportError, TypeError, ValueError):
        return False


def _sample_indices(size: int, limit: int | None = None, limit_fraction: float | None = None) -> list[int]:
    """Select a deterministic prefix or an evenly-spaced dataset fraction."""
    if limit is not None and limit_fraction is not None:
        raise ValueError("Set either limit or limit_fraction, not both")
    if limit_fraction is not None:
        fraction = float(limit_fraction)
        if not 0.0 < fraction <= 1.0:
            raise ValueError("limit_fraction must be greater than 0 and at most 1")
        count = min(size, max(1, math.ceil(size * fraction))) if size else 0
        return [(index * size) // count for index in range(count)]
    if limit is not None:
        count = int(limit)
        if count < 1:
            raise ValueError("limit must be positive")
        return list(range(min(count, size)))
    return list(range(size))


def _benchmark_spec(name: str, split: str) -> tuple[str, str | None, str]:
    """Resolve the dataset configuration and locally scoreable task split."""
    specs = {
        "mmlu": ("cais/mmlu", "all", split),
        "mmlu_pro": ("TIGER-Lab/MMLU-Pro", None, split),
        # HellaSwag's public test labels are withheld, so validation is the
        # standard locally-scoreable evaluation split.
        "hellaswag": ("Rowan/hellaswag", None, "validation" if split == "test" else split),
        "arc_c": ("allenai/ai2_arc", "ARC-Challenge", "test" if split == "test" else split),
        "gsm8k": ("openai/gsm8k", "main", split),
        "math": ("HuggingFaceH4/MATH-500", None, "test" if split == "test" else split),
        # The Hugging Face GPQA release exposes its 448 benchmark examples as
        # `train`; they are the evaluation set, not model-training data here.
        "gpqa": ("Idavidrein/gpqa", "gpqa_main", "train"),
        "humaneval": ("openai/openai_humaneval", None, split),
        "mbpp": ("google-research-datasets/mbpp", "sanitized", split),
    }
    if name not in specs:
        raise ValueError(f"Unknown benchmark {name}; available: {AVAILABLE_TASKS}")
    return specs[name]


def load_benchmark(name: str, split: str, limit: int | None, cache_dir: str, token: str | None, limit_fraction: float | None = None) -> list[BenchmarkExample]:
    """Download one configured benchmark split and normalize its records."""
    if name == OPEN_ENDED_TASK:
        indices = _sample_indices(len(OPEN_ENDED_PROMPTS), limit, limit_fraction)
        return [BenchmarkExample(name, str(index), OPEN_ENDED_PROMPTS[index], "", "open_ended", {}) for index in indices]
    from datasets import load_dataset
    path, config, actual_split = _benchmark_spec(name, split)
    dataset = load_dataset(path, config, split=actual_split, cache_dir=cache_dir, token=token)
    indices = _sample_indices(len(dataset), limit, limit_fraction)
    if len(indices) != len(dataset):
        dataset = dataset.select(indices)
    items = []
    for index, row in enumerate(dataset):
        if name in MC_TASKS:
            question, choices, answer = _multiple_choice_fields(name, row, index)
            answer_index = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".index(answer)
            target = f"{answer}: {choices[answer_index]}"
            items.append(BenchmarkExample(name, str(index), _choice_prompt(name, question, choices), target, "multiple_choice", row))
        elif name == "gsm8k":
            prompt = "Solve the following math problem step by step.\n\n" + row["question"].strip()
            items.append(BenchmarkExample(name, str(index), prompt, row["answer"].strip(), "gsm8k", row))
        elif name == "math":
            problem = row.get("problem", row.get("question", ""))
            solution = row.get("solution", row.get("answer", ""))
            prompt = "Solve the following math problem step by step.\n\n" + problem.strip()
            items.append(BenchmarkExample(name, str(index), prompt, solution.strip(), "math", row))
        elif name == "humaneval":
            items.append(BenchmarkExample(name, str(index), row["prompt"], row.get("canonical_solution", ""), "code", row))
        elif name == "mbpp":
            prompt = row.get("text", row.get("prompt", ""))
            items.append(BenchmarkExample(name, str(index), prompt + "\n\nWrite only the Python function implementation.", row.get("code", ""), "code", row))
    return items


def extract_answer(text: str, kind: str) -> str:
    """Extract a comparable answer from free-form model output."""
    if kind == "multiple_choice":
        # Training targets begin `A: ...`; score that leading label rather than
        # an arbitrary later capital letter in an explanation.
        match = re.match(r"\s*([A-Z])(?=\s*(?::|[.)-]|$))", text.upper())
        return match.group(1) if match else ""
    if kind == "gsm8k":
        return _last_number(_boxed(text))
    if kind == "math":
        return _normalize_math_answer(text)
    return text.strip()


def _run_code(candidate: str, example: BenchmarkExample, timeout: float = 10.0) -> bool:
    """Execute one generated code answer with its benchmark tests in a timeout."""
    metadata = example.metadata
    candidate = re.sub(r"^```(?:python)?\s*|\s*```$", "", candidate.strip(), flags=re.IGNORECASE | re.DOTALL)
    if example.task == "humaneval":
        program = candidate + "\n\n" + metadata["test"] + f"\ncheck({metadata['entry_point']})\n"
    else:
        tests = metadata.get("test_list", [])
        setup = metadata.get("test_setup_code", "")
        program = setup + "\n" + candidate + "\n" + "\n".join(tests)
    with tempfile.TemporaryDirectory(prefix="diffusion-lm-eval-") as directory:
        path = Path(directory) / "candidate.py"
        path.write_text(program)
        try:
            result = subprocess.run([sys.executable, "-I", str(path)], capture_output=True, timeout=timeout, cwd=directory)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, OSError):
            return False


def score_prediction(example: BenchmarkExample, generated: str) -> bool:
    """Score one normalized prediction with exact-match or benchmark tests."""
    if example.kind == "multiple_choice":
        return extract_answer(generated, example.kind) == extract_answer(example.answer, example.kind)
    if example.kind == "gsm8k":
        prediction = extract_answer(generated, example.kind)
        target = extract_answer(example.answer, example.kind)
        return prediction == target or _numeric_answers_equal(prediction, target)
    if example.kind == "math":
        return _math_answers_equal(generated, example.answer)
    return _run_code(generated, example)


def save_result(path: Path, result: dict[str, Any]) -> None:
    """Append one per-example benchmark result as JSONL."""
    with path.open("a") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")


def _ngram_repetition(text: str, tokenizer: Any, n: int) -> float:
    """Return the fraction of non-overlapping n-gram occurrences repeated."""
    special_ids = set(getattr(tokenizer, "all_special_ids", []))
    tokens = [token for token in tokenizer.encode(text, add_special_tokens=False) if token not in special_ids]
    grams = [tuple(tokens[index : index + n]) for index in range(0, len(tokens) - n + 1, n)]
    return float(1.0 - len(set(grams)) / len(grams)) if grams else 0.0


@torch.no_grad()
def score_texts_with_model(model: Any, tokenizer: Any, device: torch.device, texts: list[str]) -> dict[str, Any]:
    """Score texts with one fixed causal reference model.

    This deliberately does not disable adapters or restore normalization
    parameters: the supplied model is the shared perplexity reference model.
    """
    import torch.nn.functional as F

    total_nll = 0.0
    total_tokens = 0
    per_text = []
    model.eval()
    for text in texts:
        encoded = tokenizer(text, return_tensors="pt", add_special_tokens=True)
        input_ids = encoded["input_ids"].to(device)
        if input_ids.shape[1] < 2:
            perplexity = None
        else:
            outputs = model(input_ids=input_ids, use_cache=False)
            labels = input_ids[:, 1:]
            logits = outputs.logits[:, :-1].float()
            nll = F.cross_entropy(logits.transpose(1, 2), labels, reduction="sum")
            text_nll = float(nll.cpu())
            text_tokens = int(labels.numel())
            total_nll += text_nll
            total_tokens += text_tokens
            perplexity = float(torch.exp(torch.tensor(text_nll / text_tokens)))
        per_text.append({
            "perplexity": perplexity,
            "unigram_repetition": _ngram_repetition(text, tokenizer, 1),
            "bigram_repetition": _ngram_repetition(text, tokenizer, 2),
            "trigram_repetition": _ngram_repetition(text, tokenizer, 3),
        })
    mean_nll = total_nll / max(total_tokens, 1)
    return {"perplexity": float(torch.exp(torch.tensor(mean_nll))), "mean_nll": mean_nll, "tokens": total_tokens, "per_text": per_text}


@torch.no_grad()
def score_open_ended_generations(session: Any, texts: list[str]) -> dict[str, Any]:
    """Score generated texts with base-model perplexity and repetition metrics.

    Perplexity is measured with adapters disabled and the saved initial
    normalization weights restored, matching training-time generation
    perplexity.  The aggregate perplexity is token-weighted; each text also
    receives its own perplexity in ``per_text``.
    """
    import torch.nn.functional as F

    model = session.model
    tokenizer = session.tokenizer
    trained_norms = {name: parameter.detach().cpu().clone() for name, parameter in model.named_parameters() if "norm" in name.lower()}
    initial_path = Path(session.adapter_path) / "normalization_initial_state.pt"
    initial_norms = torch.load(initial_path, map_location="cpu", weights_only=True) if initial_path.is_file() else trained_norms
    total_nll = 0.0
    total_tokens = 0
    per_text = []
    try:
        named = dict(model.named_parameters())
        for name, value in initial_norms.items():
            if name in named:
                named[name].data.copy_(value.to(named[name].device, dtype=named[name].dtype))
        adapter_context = model.disable_adapter() if hasattr(model, "disable_adapter") else nullcontext()
        with adapter_context:
            for text in texts:
                encoded = tokenizer(text, return_tensors="pt", add_special_tokens=True)
                input_ids = encoded["input_ids"].to(session.device)
                if input_ids.shape[1] < 2:
                    perplexity = None
                else:
                    outputs = model(input_ids=input_ids) if getattr(session, "llada", False) else model(input_ids=input_ids, use_cache=False)
                    labels = input_ids[:, 1:]
                    logits = outputs.logits[:, :-1].float()
                    nll = F.cross_entropy(logits.transpose(1, 2), labels, reduction="sum")
                    text_nll = float(nll.cpu())
                    text_tokens = int(labels.numel())
                    total_nll += text_nll
                    total_tokens += text_tokens
                    perplexity = float(torch.exp(torch.tensor(text_nll / text_tokens)))
                per_text.append({
                    "perplexity": perplexity,
                    "unigram_repetition": _ngram_repetition(text, tokenizer, 1),
                    "bigram_repetition": _ngram_repetition(text, tokenizer, 2),
                    "trigram_repetition": _ngram_repetition(text, tokenizer, 3),
                })
    finally:
        named = dict(model.named_parameters())
        for name, value in trained_norms.items():
            if name in named:
                named[name].data.copy_(value.to(named[name].device, dtype=named[name].dtype))
    mean_nll = total_nll / max(total_tokens, 1)
    return {
        "perplexity": float(torch.exp(torch.tensor(mean_nll))),
        "mean_nll": mean_nll,
        "tokens": total_tokens,
        "per_text": per_text,
    }
