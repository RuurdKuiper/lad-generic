#!/usr/bin/env python3
"""Coverage, locked development selection, paired prompt-bootstrap estimates."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics

from llada_full_study_review import OUT, load, review_id

METHODS = ["confidence", "bigram", "bigram_rep", "trigram", "trigram_rep"]
CATEGORIES = ["open", "code", "math"]


def collect():
    manifest, rows = load()
    reviews = (
        json.loads((OUT / "reviews.json").read_text())
        if (OUT / "reviews.json").exists()
        else {}
    )
    codes = (
        json.loads((OUT / "code_checks.json").read_text())
        if (OUT / "code_checks.json").exists()
        else {}
    )
    tasks = {t["id"]: t for t in manifest["tasks"]}
    scored = []
    pending = []
    assert len(rows) == len({r["key"] for r in rows})
    for row in rows:
        assert (
            row["revision"] == manifest["revision"]
            and row["split"] == tasks[row["task"]]["split"]
        )
        options = row["settings"]
        assert row["inference"]["denoising_forward_passes"] == row["steps"]
        zero = row["phase"] == "confidence_zero"
        assert (
            options["top_k"] == 16
            and options["temperature"] == (0.0 if zero else 0.7)
            and options["max_new_tokens"] == options["block_length"] == 128
        )
        if zero:
            assert (
                row["method"] == "confidence_zero"
                and row["base_method"] == "confidence"
            )
            assert (
                options["remasking_strategy"] == "Confidence-guided"
                and row["decoding"] is None
            )
        assert (
            options["bigram_weight"] == options["repetition_penalty_strength"] == 1.0
            and options["generation_seed"] == 42
        )
        assert (
            options["sequence_sampling"] == (row["phase"] == "sample")
            and options["decay_repetition_penalty"]
        )
        assert not any(
            options[k]
            for k in [
                "adaptive_parallel_decoding",
                "early_stopping",
                "count_all_candidate_bigrams",
                "repetition_risk_penalty",
                "revisable_tokens",
            ]
        )
        assert options["delay_eos_eot"] == (row["category"] == "open")
        assert options["bigram_eos_delay_penalty"] == (
            10.0 if row["category"] == "open" else 1.0
        )
        if row["decoding"]:
            assert row["decoding"]["selector_calls"] == row["steps"]
        review = (
            codes.get(row["key"])
            if row["category"] == "code"
            else reviews.get(review_id(row))
        )
        if review is None or review.get("score") is None:
            pending.append(row["key"])
            continue
        assert review["sha256"] == row["sha256"]
        score = (
            review["score"] / 3
            if row["category"] == "open"
            else (
                float(review["all_pass"])
                if row["category"] == "code"
                else float(review["answer_correct"])
            )
        )
        scored.append(
            dict(
                key=row["key"],
                task=row["task"],
                category=row["category"],
                split=row["split"],
                steps=row["steps"],
                method=row["method"],
                base_method=row["base_method"],
                phase=row["phase"],
                score=review["score"],
                normalized=score,
                fluency=review.get("fluency"),
                math_worked=review.get("worked_correct"),
                server_ms=row["inference"]["elapsed_ms"],
                sha256=row["sha256"],
                note=review.get(
                    "note",
                    f"{review.get('passed',0)}/{review.get('total',0)} tests; {review.get('status','')}.",
                ),
            )
        )
    return manifest, rows, scored, pending


def bootstrap(differences, repeats=4000):
    """Each category has per-prompt paired differences; equal category weight."""
    import numpy as np

    rng = np.random.default_rng(20261022)
    estimates = []
    means = []
    for values in differences:
        values = np.asarray(values, dtype=float)
        assert len(values) > 0
        means.append(values.mean())
        index = rng.integers(0, len(values), (repeats, len(values)))
        estimates.append(values[index].mean(-1))
    dist = np.stack(estimates).mean(0)
    return dict(
        delta=float(np.mean(means)),
        ci95=[float(x) for x in np.quantile(dist, [0.025, 0.975])],
        bootstrap_repeats=repeats,
    )


def choose(manifest, rows, scored, pending):
    main = [r for r in rows if r["phase"] == "main"]
    graded = [r for r in scored if r["phase"] == "main"]
    if len(main) != 1800 or len(graded) != 1800:
        raise RuntimeError(
            "Selection requires all1800 main outputs scored; no partial-data selection"
        )
    expected = {
        f"{t['id']}/{n}/{m}"
        for t in manifest["tasks"]
        for n in manifest["budgets"]
        for m in METHODS
    }
    assert {r["key"] for r in main} == expected
    by_budget = {}
    rankings = {}
    for n in manifest["budgets"]:
        ranks = []
        for method in METHODS[1:]:
            subset = [
                r
                for r in graded
                if r["steps"] == n
                and r["method"] == method
                and r["split"] == "development"
            ]
            components = {
                c: statistics.mean(
                    r["normalized"] for r in subset if r["category"] == c
                )
                for c in CATEGORIES
            }
            assert len(subset) == 30 and all(
                sum(r["category"] == c for r in subset) == 10 for c in CATEGORIES
            )
            ranks.append(
                dict(
                    method=method,
                    score=statistics.mean(components.values()),
                    components=components,
                    mean_server_ms=statistics.mean(r["server_ms"] for r in subset),
                )
            )
        ranks.sort(key=lambda r: (-r["score"], r["mean_server_ms"], r["method"]))
        by_budget[str(n)] = [r["method"] for r in ranks[:2]]
        rankings[str(n)] = ranks
    grade_fingerprint = hashlib.sha256(
        json.dumps(sorted(graded, key=lambda r: r["key"]), sort_keys=True).encode()
    ).hexdigest()
    record = dict(
        revision=manifest["revision"],
        methods_by_budget=by_budget,
        development_rankings=rankings,
        main_results_sha256=hashlib.sha256(
            (OUT / "main/results.jsonl").read_bytes()
        ).hexdigest(),
        main_grades_sha256=grade_fingerprint,
        rule=manifest["protocol"]["ranking"],
        planned_followup=720,
    )
    path = OUT / "selection.json"
    if path.exists() and json.loads(path.read_text()) != record:
        raise RuntimeError(
            "Locked selection differs; preserve it and audit changes before proceeding"
        )
    path.write_text(json.dumps(record, indent=2) + "\n")
    return record


def comparisons(manifest, scored):
    main = {r["key"]: r for r in scored if r["phase"] == "main"}
    result = []
    if len(main) == 1800:
        for split in ["all", "development", "validation"]:
            for method in METHODS[1:]:
                for budget in [None] + manifest["budgets"]:
                    differences = []
                    for category in CATEGORIES:
                        values = []
                        for task in manifest["tasks"]:
                            if task["category"] != category or (
                                split != "all" and task["split"] != split
                            ):
                                continue
                            budgets = (
                                manifest["budgets"] if budget is None else [budget]
                            )
                            # Averaging each prompt's whole budget vector before
                            # resampling preserves the repeated-prompt dependence.
                            values.append(
                                statistics.mean(
                                    main[f"{task['id']}/{n}/{method}"]["normalized"]
                                    - main[f"{task['id']}/{n}/confidence"]["normalized"]
                                    for n in budgets
                                )
                            )
                        differences.append(values)
                    result.append(
                        dict(
                            phase="main",
                            split=split,
                            method=method,
                            baseline="confidence",
                            budget=budget,
                            **bootstrap(differences),
                        )
                    )
    selectionpath = OUT / "selection.json"
    sample = {r["key"]: r for r in scored if r["phase"] == "sample"}
    if selectionpath.exists() and len(sample) == 720:
        selection = json.loads(selectionpath.read_text())
        for split in ["all", "development", "validation"]:
            for rank in [0, 1]:
                for budget in [None] + manifest["budgets"]:
                    differences = []
                    for category in CATEGORIES:
                        values = []
                        for task in manifest["tasks"]:
                            if task["category"] != category or (
                                split != "all" and task["split"] != split
                            ):
                                continue
                            budgets = (
                                manifest["budgets"] if budget is None else [budget]
                            )
                            delta = []
                            for n in budgets:
                                method = selection["methods_by_budget"][str(n)][rank]
                                delta.append(
                                    sample[f"{task['id']}/{n}/{method}_sample"][
                                        "normalized"
                                    ]
                                    - main[f"{task['id']}/{n}/{method}"]["normalized"]
                                )
                            values.append(statistics.mean(delta))
                        differences.append(values)
                    result.append(
                        dict(
                            phase="sample",
                            split=split,
                            selection_rank=rank + 1,
                            budget=budget,
                            **bootstrap(differences),
                        )
                    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--select", action="store_true")
    args = parser.parse_args()
    manifest, rows, scored, pending = collect()
    if args.select:
        print(json.dumps(choose(manifest, rows, scored, pending), indent=2))
    groups = []
    for phase in ["main", "sample"]:
        methods = sorted({r["method"] for r in rows if r["phase"] == phase})
        for split in ["all", "development", "validation"]:
            for n in manifest["budgets"]:
                for method in methods:
                    for category in CATEGORIES:
                        generated = [
                            r
                            for r in rows
                            if r["phase"] == phase
                            and r["steps"] == n
                            and r["method"] == method
                            and r["category"] == category
                            and (split == "all" or r["split"] == split)
                        ]
                        if not generated:
                            continue
                        group = [
                            r
                            for r in scored
                            if r["phase"] == phase
                            and r["steps"] == n
                            and r["method"] == method
                            and r["category"] == category
                            and (split == "all" or r["split"] == split)
                        ]
                        expected = 20 if split == "all" else 10
                        groups.append(
                            dict(
                                phase=phase,
                                split=split,
                                steps=n,
                                method=method,
                                category=category,
                                generated=len(generated),
                                graded=len(group),
                                expected=expected,
                                complete=len(group) == expected,
                                mean_normalized=(
                                    statistics.mean(r["normalized"] for r in group)
                                    if group
                                    else None
                                ),
                                mean_grade=(
                                    statistics.mean(r["score"] for r in group)
                                    if group
                                    else None
                                ),
                                mean_fluency=(
                                    statistics.mean(r["fluency"] for r in group)
                                    if group and category == "open"
                                    else None
                                ),
                                worked_correct=(
                                    sum(r["math_worked"] for r in group)
                                    if category == "math"
                                    else None
                                ),
                                mean_server_ms=(
                                    statistics.mean(r["server_ms"] for r in group)
                                    if group
                                    else None
                                ),
                            )
                        )
    summary = dict(
        main_generated=sum(r["phase"] == "main" for r in rows),
        sample_generated=sum(r["phase"] == "sample" for r in rows),
        graded=len(scored),
        pending_reviews=pending,
        groups=groups,
        paired_comparisons=comparisons(manifest, scored),
    )
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    if scored:
        with (OUT / "scores.csv").open("w") as f:
            w = csv.DictWriter(f, fieldnames=list(scored[0]))
            w.writeheader()
            w.writerows(scored)
    print(
        json.dumps(
            {
                k: v
                for k, v in summary.items()
                if k not in ["groups", "paired_comparisons", "pending_reviews"]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
