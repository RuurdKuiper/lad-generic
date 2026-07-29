"""Small, reproducible benchmark adapters for pure diffusion evaluation."""
from __future__ import annotations

import json
import random
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


MC_TASKS = {"mmlu", "mmlu_pro", "hellaswag", "arc_c", "gpqa"}
ALL_TASKS = ["mmlu", "mmlu_pro", "hellaswag", "arc_c", "gsm8k", "math", "gpqa", "humaneval", "mbpp"]


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
        raise ValueError(f"Unknown benchmark {name}; available: {ALL_TASKS}")
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
