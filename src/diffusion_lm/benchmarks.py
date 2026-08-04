"""Small, reproducible benchmark adapters for pure diffusion evaluation."""
from __future__ import annotations

import json
import random
import re
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import torch


MC_TASKS = {"mmlu", "mmlu_pro", "hellaswag", "arc_c", "gpqa"}
ALL_TASKS = ["mmlu", "mmlu_pro", "hellaswag", "arc_c", "gsm8k", "math", "gpqa", "humaneval", "mbpp"]
OPEN_ENDED_TASK = "open_ended"
AVAILABLE_TASKS = [*ALL_TASKS, OPEN_ENDED_TASK]


def resolve_generation_settings(config: dict[str, Any], task: str, mode: str) -> dict[str, Any]:
    """Resolve generation settings for a task and corruption mode."""
    settings = dict(config.get("generation", {}))
    settings.update(config.get("generation_by_corruption", {}).get(mode, {}))
    settings.update(config.get("task_generation", {}).get(task, {}))
    settings.update(config.get("task_generation_by_corruption", {}).get(mode, {}).get(task, {}))
    if mode == "mask_only":
        # Mask-only training is evaluated with the full-remasking setup used
        # by the training-time generation validation.
        settings.update(noise_level=1.0, permanent_unmask=True, confidence_guided=True)
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


def _choice_prompt(question: str, choices: list[Any]) -> str:
    """Format a multiple-choice question using stable A/B/C/... labels."""
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return question.strip() + "\n\n" + "\n".join(f"{letters[i]}. {choice}" for i, choice in enumerate(choices)) + "\n\nAnswer with only the letter."


def _boxed(text: str) -> str:
    """Extract a final boxed/math answer when present."""
    matches = re.findall(r"\\boxed\{([^{}]+)\}|####\s*([^\n]+)", text or "")
    if not matches:
        return (text or "").strip()
    return (matches[-1][0] or matches[-1][1]).strip()


def load_benchmark(name: str, split: str, limit: int | None, cache_dir: str, token: str | None) -> list[BenchmarkExample]:
    """Download one configured benchmark split and normalize its records."""
    if name == OPEN_ENDED_TASK:
        prompts = OPEN_ENDED_PROMPTS if limit is None else OPEN_ENDED_PROMPTS[: min(int(limit), len(OPEN_ENDED_PROMPTS))]
        return [BenchmarkExample(name, str(index), prompt, "", "open_ended", {}) for index, prompt in enumerate(prompts)]
    from datasets import load_dataset
    specs = {
        "mmlu": ("cais/mmlu", "all", split),
        "mmlu_pro": ("TIGER-Lab/MMLU-Pro", None, split),
        "hellaswag": ("Rowan/hellaswag", None, split),
        "arc_c": ("allenai/ai2_arc", "ARC-Challenge", "test" if split == "test" else split),
        "gsm8k": ("openai/gsm8k", "main", split),
        "math": ("HuggingFaceH4/MATH-500", None, "test" if split == "test" else split),
        "gpqa": ("Idavidrein/gpqa", "gpqa_main", split),
        "humaneval": ("openai/openai_humaneval", None, split),
        "mbpp": ("google-research-datasets/mbpp", "sanitized", split),
    }
    if name not in specs:
        raise ValueError(f"Unknown benchmark {name}; available: {AVAILABLE_TASKS}")
    path, config, actual_split = specs[name]
    dataset = load_dataset(path, config, split=actual_split, cache_dir=cache_dir, token=token)
    if limit is not None:
        dataset = dataset.select(range(min(int(limit), len(dataset))))
    items = []
    for index, row in enumerate(dataset):
        if name in MC_TASKS:
            question = row.get("question", row.get("Question", row.get("query", row.get("ctx", ""))))
            choices = row.get("choices", row.get("options"))
            answer = row.get("answer", row.get("answerKey", row.get("label", row.get("answer_index"))))
            if name == "gpqa" and not choices:
                choices = [row["Correct Answer"], row["Incorrect Answer 1"], row["Incorrect Answer 2"], row["Incorrect Answer 3"]]
                correct = choices[0]
                random.Random(index).shuffle(choices)
                answer = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[choices.index(correct)]
            if isinstance(answer, int) or str(answer).isdigit():
                answer = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[int(answer)]
            items.append(BenchmarkExample(name, str(index), _choice_prompt(question, choices), str(answer).upper(), "multiple_choice", row))
        elif name == "gsm8k":
            items.append(BenchmarkExample(name, str(index), row["question"] + "\n\nSolve the problem and give the final answer.", _boxed(row["answer"]), "numeric", row))
        elif name == "math":
            problem = row.get("problem", row.get("question", ""))
            items.append(BenchmarkExample(name, str(index), problem + "\n\nSolve the problem and give the final answer.", _boxed(row.get("solution", row.get("answer", ""))), "numeric", row))
        elif name == "humaneval":
            items.append(BenchmarkExample(name, str(index), row["prompt"], row.get("canonical_solution", ""), "code", row))
        elif name == "mbpp":
            prompt = row.get("text", row.get("prompt", ""))
            items.append(BenchmarkExample(name, str(index), prompt + "\n\nWrite only the Python function implementation.", row.get("code", ""), "code", row))
    return items


def extract_answer(text: str, kind: str) -> str:
    """Extract a comparable answer from free-form model output."""
    if kind == "multiple_choice":
        match = re.search(r"(?<![A-Za-z])([A-Z])(?![A-Za-z])", text.upper())
        return match.group(1) if match else ""
    if kind == "numeric":
        return _boxed(text)
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
        return extract_answer(generated, example.kind) == example.answer
    if example.kind == "numeric":
        return extract_answer(generated, example.kind).replace(" ", "") == example.answer.replace(" ", "")
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
