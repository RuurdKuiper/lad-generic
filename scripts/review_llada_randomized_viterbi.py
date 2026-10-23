#!/usr/bin/env python3
"""Anonymous manual review and restricted code checks for randomized Viterbi."""

import argparse, json
import review_llada_ngram_speedup as base
from evaluate_llada_randomized_viterbi import OUT, STUDY, read

base.OUT = OUT
base.load = lambda: read(OUT / "results.jsonl")
save = base.save
rid = base.rid
reviews = base.reviews


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--code", action="store_true")
    p.add_argument("--category", choices=["open", "math"])
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--offset", type=int, default=0)
    args = p.parse_args()
    rows = base.load()
    tasks = {
        t["id"]: t for t in json.loads((STUDY / "manifest.json").read_text())["tasks"]
    }
    if args.code:
        base.code_checks(rows, tasks)
        return
    judged = reviews()
    pending = {
        rid(r): r
        for r in rows
        if r["category"] != "code"
        and rid(r) not in judged
        and (not args.category or r["category"] == args.category)
    }
    print(
        json.dumps(
            dict(
                generated=len(rows),
                pending=len(pending),
                reviewed=sum(rid(r) in judged for r in rows if r["category"] != "code"),
            )
        )
    )
    for key, row in sorted(pending.items())[args.offset : args.offset + args.limit]:
        t = tasks[row["task"]]
        print(
            json.dumps(
                dict(
                    id=key,
                    task=row["task"],
                    prompt=t["prompt"],
                    reference=t["reference"],
                    text=row["text"],
                ),
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
