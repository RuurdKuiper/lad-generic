"""Compare the frozen evaluated subsets with unused, cached benchmark items.

No network calls, generation, or execution of benchmark candidate programs.
Permutation diagnostics are exploratory; non-rejection is not equivalence.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from datasets import Dataset
import datasets

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EVAL = HERE.parent / "evaluation"
sys.path.insert(0, str(ROOT / "src"))
from diffusion_lm.benchmarks import load_benchmark

SEED = 20261115
REPLICATES = 9999
FILES = {
    "arc_c": "allenai___ai2_arc/ARC-Challenge/**/ai2_arc-test.arrow",
    "hellaswag": "Rowan___hellaswag/**/hellaswag-validation.arrow",
    "gsm8k": "openai___gsm8k/**/gsm8k-test.arrow",
    "math": "HuggingFaceH4___math-500/**/math-500-test.arrow",
    "gpqa": "Idavidrein___gpqa/gpqa_main/**/gpqa-train.arrow",
    "mbpp": "google-research-datasets___mbpp/sanitized/**/mbpp-test.arrow",
}


def fingerprint(ex):
    value = json.dumps([ex.task, ex.prompt, ex.answer], sort_keys=True,
                       ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(value.encode()).hexdigest()


def words(value):
    return len(str(value).split())


def features(task, row):
    if task == "math":
        return {"subject": row["subject"], "difficulty_level": str(row["level"])}, {
            "problem_words": words(row["problem"]),
            "reference_words": words(row["solution"]),
            "difficulty_level_numeric": row["level"],
        }
    if task == "gsm8k":
        return {}, {"question_words": words(row["question"]),
                    "reference_words": words(row["answer"]),
                    "annotated_calculation_count": row["answer"].count("<<")}
    if task == "gpqa":
        return {"domain": row["High-level domain"], "subdomain": row["Subdomain"],
                "writer_difficulty": row["Writer's Difficulty Estimate"]}, {
            "question_words": words(row["Question"]),
            "expert_validator_accuracy": row["Expert Validator Accuracy"],
            "nonexpert_validator_accuracy": row["Non-Expert Validator Accuracy"],
        }
    if task == "hellaswag":
        return {"source": row["source_id"].split("~")[0],
                "activity": row["activity_label"], "split_type": row["split_type"],
                "answer_label": str(row["label"])}, {
            "context_words": words(row["ctx"]),
            "mean_ending_words": sum(words(x) for x in row["endings"]) / len(row["endings"]),
        }
    if task == "arc_c":
        source = "Mercury_SC" if row["id"].startswith("Mercury_SC_") else (
            "Mercury" if row["id"].startswith("Mercury_") else row["id"].split("_")[0])
        return {"source_id_prefix": source, "answer_label": str(row["answerKey"]),
                "choice_count": str(len(row["choices"]["text"]))}, {
            "question_words": words(row["question"]),
            "mean_choice_words": sum(words(x) for x in row["choices"]["text"]) / len(row["choices"]["text"]),
        }
    if task == "mbpp":
        return {"source_file": row["source_file"]}, {
            "description_words": words(row["prompt"]),
            "reference_code_lines": len(row["code"].splitlines()),
            "test_count": len(row["test_list"]),
        }
    raise ValueError(task)


def categorical_test(values, selected, rng):
    labels = sorted({"<missing>" if v is None else str(v) for v in values})
    counts = np.array([sum(("<missing>" if v is None else str(v)) == label for v in values) for label in labels])
    first = np.array([sum(("<missing>" if v is None else str(v)) == label and take
                         for v, take in zip(values, selected)) for label in labels])
    n, total = int(selected.sum()), len(selected)
    observed = float(np.abs(first / n - (counts - first) / (total - n)).sum() / 2)
    draws = rng.multivariate_hypergeometric(counts, n, size=REPLICATES)
    null = np.abs(draws / n - (counts - draws) / (total - n)).sum(axis=1) / 2
    return {"kind": "categorical", "total_variation": observed,
            "p": float((1 + np.count_nonzero(null >= observed - 1e-12)) / (REPLICATES + 1)),
            "counts": {label: {"selected": int(a), "remainder": int(c-a), "full": int(c)}
                       for label, a, c in zip(labels, first, counts)}}


def numeric_test(values, selected, rng):
    array = np.array([np.nan if v is None else float(v) for v in values])
    valid = np.isfinite(array)
    array, mask = array[valid], selected[valid]
    n, total = int(mask.sum()), len(array)
    first, rest = array[mask], array[~mask]
    observed = float(first.mean() - rest.mean())
    total_sum = array.sum()
    extreme = 0
    for _ in range(REPLICATES):
        sample_sum = array[rng.choice(total, n, replace=False)].sum()
        diff = sample_sum / n - (total_sum - sample_sum) / (total - n)
        extreme += abs(diff) >= abs(observed) - 1e-12
    sd = float(array.std(ddof=1))
    return {"kind": "numeric", "selected_n": n, "remainder_n": total-n,
            "selected_mean": float(first.mean()), "remainder_mean": float(rest.mean()),
            "full_mean": float(array.mean()), "mean_difference": observed,
            "standardized_difference": observed / sd if sd else 0,
            "p": (1 + int(extreme)) / (REPLICATES + 1)}


def main():
    frozen = [json.loads(line) for line in (EVAL / "campaign_bundle/examples.jsonl").open()]
    plan = json.loads((EVAL / "campaign_bundle/plan.json").read_text())
    rng = np.random.default_rng(SEED)
    result = {"seed": SEED, "replicates": REPLICATES, "tasks": {}, "tests": []}
    for task, pattern in FILES.items():
        path = next((EVAL / "cache/datasets").glob(pattern))
        data = Dataset.from_file(str(path))
        original_loader = datasets.load_dataset
        try:
            datasets.load_dataset = lambda *args, **kwargs: data
            examples = load_benchmark(task, "test", None, "unused", None)
        finally:
            datasets.load_dataset = original_loader
        # Match the preparation's unit: unique prompt/target pairs.
        seen = set()
        unique = []
        for row, ex in zip(data, examples):
            fp = fingerprint(ex)
            if fp not in seen:
                unique.append((fp, row))
                seen.add(fp)
        wanted = {r["fingerprint"] for r in frozen if r["task"] == task}
        assert wanted <= seen
        mask = np.array([fp in wanted for fp, _ in unique])
        assert int(mask.sum()) == 250
        assert all(mask[:250]) and not any(mask[250:]), "Saved subset differs from unique prefix"
        raw = [row for _, row in unique]
        cats_nums = [features(task, row) for row in raw]
        out = {"raw_size": len(data), "unique_size": len(unique), "selected_size": int(mask.sum()),
               "dataset_spec": plan["datasets"][task],
               "cached_arrow_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "features": {}}
        for kind, keys in [(0, cats_nums[0][0]), (1, cats_nums[0][1])]:
            for key in keys:
                values = [pair[kind][key] for pair in cats_nums]
                check = categorical_test(values, mask, rng) if kind == 0 else numeric_test(values, mask, rng)
                out["features"][key] = check
                result["tests"].append({"task": task, "feature": key, "p": check["p"]})
        if task == "hellaswag":
            sources = [r["source_id"].split("~")[0] for r in raw]
            out["source_transition_indices"] = [i for i in range(1, len(sources)) if sources[i] != sources[i-1]]
        if task == "mbpp":
            ids = [r["task_id"] for r in raw]
            out["task_ids_sorted"] = ids == sorted(ids)
            out["omitted_task_ids"] = ids[250:]
            out["worst_case_full_score_distance_pp"] = 100 * (len(raw)-250) / len(raw)
        result["tasks"][task] = out
        print(task, "audited", len(raw), "unique items", flush=True)
    # One global Holm correction across the exploratory metadata tests.
    ordered = sorted(result["tests"], key=lambda x: x["p"])
    adjusted = 0.0
    for i, test in enumerate(ordered):
        adjusted = max(adjusted, min(1.0, test["p"] * (len(ordered)-i)))
        test["holm_p"] = adjusted
        result["tasks"][test["task"]]["features"][test["feature"]]["holm_p"] = adjusted
    target = HERE / "dataset_order_audit.json"
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    for test in ordered:
        print(test)
    print("Saved", target)


if __name__ == "__main__":
    main()
