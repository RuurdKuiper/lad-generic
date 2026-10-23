#!/usr/bin/env python3
"""Reuse the study rubric and restricted code tests for the small speed screen."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from evaluate_llada_ngram_speedup import OUT, ROOT
from check_llada_full_study_code import extract, validate

STUDY = ROOT / "artifacts/bigram/llada_ngram_settings_full"


def load():
    rows = []
    for stage in ["before", "after_k16", "after_k8", "after_host_k16", "after_host_k8"]:
        path = OUT / (stage + ".jsonl")
        if path.exists():
            rows += [json.loads(s) for s in path.read_text().splitlines()]
    return rows


def rid(row):
    return hashlib.sha256((row["task"] + ":" + row["sha256"]).encode()).hexdigest()[:12]


def reviews():
    result = json.loads((STUDY / "reviews.json").read_text())
    p = OUT / "reviews.json"
    if p.exists():
        result.update(json.loads(p.read_text()))
    return result


def save(updates):
    p = OUT / "reviews.json"
    saved = json.loads(p.read_text()) if p.exists() else {}
    lookup = {rid(r): r for r in load()}
    for key, (score, fluency, note) in updates.items():
        row = lookup[key]
        assert score in [0, 1, 2, 3] and note
        value = dict(
            category=row["category"], sha256=row["sha256"], score=score, note=note
        )
        if row["category"] == "open":
            assert fluency in [0, 1, 2, 3]
            value["fluency"] = fluency
        else:
            value.update(answer_correct=score >= 2, worked_correct=score == 3)
        saved[key] = value
    p.write_text(json.dumps(saved, indent=2) + "\n")
    print("saved", len(updates))


def code_checks(rows, tasks):
    old = json.loads((STUDY / "code_checks.json").read_text())
    path = OUT / "code_checks.json"
    records = json.loads(path.read_text()) if path.exists() else {}
    cache = {(r["task"], r["sha256"]): r for r in [*old.values(), *records.values()]}
    for row in rows:
        if row["category"] != "code":
            continue
        key = (
            row["key"]
            if "key" in row
            else f"{row['stage']}/{row['task']}/{row['steps']}/{row['trial']}"
        )
        ck = (row["task"], row["sha256"])
        if ck in cache and cache[ck]["status"] != "policy_blocked":
            records[key] = cache[ck]
            continue
        code = extract(row["text"])
        task = tasks[row["task"]]
        result = dict(
            task=row["task"],
            sha256=row["sha256"],
            all_pass=False,
            passed=0,
            total=len(task["cases"]),
        )
        try:
            validate(code, task["function"])
        except SyntaxError:
            result.update(status="syntax_error", score=0)
        except LookupError:
            result.update(status="missing_function", score=0)
        except PermissionError as exc:
            result.update(
                status="policy_blocked", score=None, all_pass=None, error=str(exc)
            )
        else:
            try:
                payload = dict(
                    code=code,
                    function=task["function"],
                    cases=task["cases"],
                    forbidden_calls=task["forbidden_calls"],
                )
                with tempfile.TemporaryDirectory(prefix="llada-speed-code-") as tmp:
                    run = subprocess.run(
                        [
                            sys.executable,
                            "-I",
                            str(ROOT / "scripts/check_llada_full_study_code.py"),
                            "--worker",
                        ],
                        input=json.dumps(payload),
                        capture_output=True,
                        text=True,
                        cwd=tmp,
                        env={"PATH": "/usr/bin:/bin"},
                        timeout=5,
                    )
                if run.returncode:
                    raise RuntimeError(run.stderr[-500:])
                data = json.loads(run.stdout)
                passed = sum(c["passed"] for c in data["checks"])
                passed_all = (
                    passed == len(task["cases"]) and not data["constraint_violations"]
                )
                result.update(
                    status="executed",
                    passed=passed,
                    all_pass=passed_all,
                    score=3 if passed_all else 2 if passed else 1,
                    **data,
                )
            except subprocess.TimeoutExpired:
                result.update(status="timeout", score=0)
            except Exception as exc:
                result.update(status="runtime_error", score=0, error=str(exc))
        records[key] = result
        cache[ck] = result
    path.write_text(json.dumps(records, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                code_outputs=len(records),
                all_pass=sum(r["all_pass"] is True for r in records.values()),
                pending_policy=sum(r["score"] is None for r in records.values()),
            )
        )
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--code", action="store_true")
    args = p.parse_args()
    rows = load()
    tasks = {
        t["id"]: t for t in json.loads((STUDY / "manifest.json").read_text())["tasks"]
    }
    if args.code:
        code_checks(rows, tasks)
        return
    seen = reviews()
    pending = {
        rid(r): r for r in rows if r["category"] != "code" and rid(r) not in seen
    }
    print("pending unique manual reviews", len(pending))
    for key, row in sorted(pending.items()):
        task = tasks[row["task"]]
        print(
            json.dumps(
                dict(
                    id=key,
                    task=row["task"],
                    prompt=task["prompt"],
                    reference=task["reference"],
                    text=row["text"],
                ),
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
