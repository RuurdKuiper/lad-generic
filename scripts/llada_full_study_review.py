#!/usr/bin/env python3
"""Create anonymous review packets and propagate judgments to exact duplicates."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/bigram/llada_ngram_settings_full"


def review_id(row):
    return hashlib.sha256((row["task"] + ":" + row["sha256"]).encode()).hexdigest()[:12]


def load():
    manifest = json.loads((OUT / "manifest.json").read_text())
    rows = []
    for phase in ["main", "sample", "confidence_zero"]:
        p = OUT / phase / "results.jsonl"
        if p.exists():
            lines = p.read_text().splitlines()
            for i, line in enumerate(lines):
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    if i != len(lines) - 1:
                        raise
    return manifest, rows


def save_reviews(updates):
    """Persist explicit manual (score, fluency, note) judgments by anonymous id."""
    _, rows = load()
    lookup = {review_id(r): r for r in rows if r["category"] != "code"}
    p = OUT / "reviews.json"
    reviews = json.loads(p.read_text()) if p.exists() else {}
    for rid, (score, fluency, note) in updates.items():
        row = lookup[rid]
        assert score in (0, 1, 2, 3) and note
        record = dict(
            category=row["category"], sha256=row["sha256"], score=score, note=note
        )
        if row["category"] == "open":
            assert fluency in (0, 1, 2, 3)
            record["fluency"] = fluency
        else:
            record.update(answer_correct=score >= 2, worked_correct=score == 3)
        if rid in reviews and reviews[rid] != record:
            with (OUT / "review_edits.jsonl").open("a") as f:
                f.write(
                    json.dumps(dict(id=rid, before=reviews[rid], after=record)) + "\n"
                )
        reviews[rid] = record
    temp = p.with_suffix(".tmp")
    temp.write_text(json.dumps(reviews, indent=2) + "\n")
    temp.replace(p)
    print(json.dumps(dict(saved=len(updates), unique_reviews=len(reviews))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", choices=["open", "math"])
    parser.add_argument("--task")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()
    manifest, rows = load()
    tasks = {t["id"]: t for t in manifest["tasks"]}
    p = OUT / "reviews.json"
    reviews = json.loads(p.read_text()) if p.exists() else {}
    unique = {}
    for row in rows:
        if row["category"] == "code":
            continue
        rid = review_id(row)
        if rid in reviews:
            r = reviews[rid]
            assert (
                r["sha256"] == row["sha256"]
                and r["category"] == row["category"]
                and 0 <= r["score"] <= 3
                and r["note"]
            )
            if row["category"] == "open":
                assert 0 <= r["fluency"] <= 3
            else:
                assert isinstance(r["answer_correct"], bool) and isinstance(
                    r["worked_correct"], bool
                )
            continue
        if args.category and row["category"] != args.category:
            continue
        if args.task and row["task"] != args.task:
            continue
        task = tasks[row["task"]]
        unique[rid] = dict(
            review_id=rid,
            category=row["category"],
            prompt=task["prompt"],
            reference=task["reference"],
            sha256=row["sha256"],
            text=row["text"],
        )
    status = dict(
        generated=len(rows),
        noncode_generated=sum(r["category"] != "code" for r in rows),
        unique_reviews_saved=len(reviews),
        reviewed_rows=sum(
            review_id(r) in reviews for r in rows if r["category"] != "code"
        ),
        unique_pending_matching_filter=len(unique),
    )
    print(json.dumps(status))
    if not args.status:
        for key in sorted(unique)[: args.limit]:
            print(json.dumps(unique[key], ensure_ascii=False))
    # Anonymous ids intentionally omit method, NFE and development/validation split.
    (OUT / "review_status.json").write_text(json.dumps(status, indent=2) + "\n")


if __name__ == "__main__":
    main()
