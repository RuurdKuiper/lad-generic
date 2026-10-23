#!/usr/bin/env python3
"""Audit coverage and summarize saved manual reviews and executable code tests."""

import csv
import json
import os
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/bigram/llada_ngram_settings"
METHODS = ["confidence", "bigram", "bigram_rep", "trigram", "trigram_rep"]


def plot(groups):
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/llada-ngram-mpl")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    styles = [
        ("Confidence", "#555555", "-", "o"),
        ("Bigram", "#1976b5", "-", "o"),
        ("Bigram + fade rep.", "#1976b5", "--", "x"),
        ("Bigram + trigram", "#9c3b9f", "-", "o"),
        ("Bigram + trigram + fade rep.", "#9c3b9f", "--", "x"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    for method, (label, color, line, marker) in zip(METHODS, styles):
        rows = sorted(
            (g for g in groups if g["method"] == method), key=lambda g: g["steps"]
        )
        x = [r["steps"] for r in rows]
        values = [
            [r["open_quality"] for r in rows],
            [r["code_pass"] + r["math_answer_correct"] for r in rows],
            [r["mean_server_ms"] / 1000 for r in rows],
        ]
        for ax, y in zip(axes, values):
            ax.plot(
                x,
                y,
                label=label,
                color=color,
                linestyle=line,
                marker=marker,
                markersize=5,
                linewidth=1.6,
            )
    for ax in axes:
        ax.set_xscale("log", base=2)
        ax.set_xticks(
            [4, 8, 16, 32, 64, 128], labels=["4", "8", "16", "32", "64", "128"]
        )
        ax.set_xlabel("Denoising iterations / 128-token block")
        ax.grid(alpha=0.2)
    axes[0].set(
        title="Open-ended quality (manual)", ylabel="Mean rating / 3", ylim=(-0.1, 3.1)
    )
    axes[1].set(
        title="Code passes + correct math answers", ylabel="Count / 4", ylim=(-0.1, 4.1)
    )
    axes[2].set(title="Mean server inference time", ylabel="Seconds")
    axes[2].set_yscale("log")
    axes[2].set_yticks([0.2, 0.5, 1, 2, 5], labels=["0.2", "0.5", "1", "2", "5"])
    axes[2].yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    fig.suptitle("LLaDA: six fixed prompts, one seed; exploratory results", fontsize=12)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0.08, 1, 0.94))
    fig.savefig(OUT / "comparison.png", dpi=180)
    fig.savefig(OUT / "comparison.svg")
    plt.close(fig)


def main():
    from transformers import AutoTokenizer

    manifest = json.loads((OUT / "manifest.json").read_text())
    rows = [json.loads(s) for s in (OUT / "results.jsonl").read_text().splitlines()]
    manual = json.loads((OUT / "manual_reviews.json").read_text())
    code = json.loads((OUT / "code_checks.json").read_text())
    expected = {
        f"{t['id']}/{n}/{m['id']}"
        for t in manifest["tasks"]
        for n in manifest["budgets"]
        for m in manifest["methods"]
    }
    assert (
        len(rows) == len({r["key"] for r in rows}) == 180
        and {r["key"] for r in rows} == expected
    )
    assert len(manual) == 120 and len(code) == 60
    tokenizer = AutoTokenizer.from_pretrained(
        ROOT
        / "base_models/models--GSAI-ML--LLaDA-8B-Instruct/snapshots/08b83a6feb34df1a6011b80c3c00c7563e963b07",
        local_files_only=True,
    )
    scored = []
    lookup = {}
    for r in rows:
        review = code[r["key"]] if r["category"] == "code" else manual[r["key"]]
        assert review["sha256"] == r["sha256"] and r["revision"] == manifest["revision"]
        assert r["inference"]["denoising_forward_passes"] == r["steps"]
        settings = r["settings"]
        assert (
            settings["top_k"] == 16
            and settings["temperature"] == 0.7
            and settings["max_new_tokens"] == settings["block_length"] == 128
        )
        assert (
            settings["bigram_weight"] == settings["repetition_penalty_strength"] == 1.0
        )
        assert not any(
            settings[k]
            for k in [
                "adaptive_parallel_decoding",
                "sequence_sampling",
                "count_all_candidate_bigrams",
                "repetition_risk_penalty",
                "early_stopping",
            ]
        )
        assert settings["decay_repetition_penalty"] and settings["delay_eos_eot"] == (
            r["category"] == "open"
        )
        assert settings["bigram_eos_delay_penalty"] == (
            10.0 if r["category"] == "open" else 1.0
        )
        if r["decoding"]:
            assert r["decoding"]["selector_calls"] == r["steps"]
        ids = tokenizer.encode(r["text"], add_special_tokens=False)
        note = (
            (
                f"{review['passed']}/{review['total']} fixed tests passed."
                + (f" {review['error']}" if review.get("error") else "")
            )
            if r["category"] == "code"
            else review["note"]
        )
        row = dict(
            key=r["key"],
            task=r["task"],
            category=r["category"],
            steps=r["steps"],
            method=r["method"],
            score=review["score"],
            fluency=review.get("fluency"),
            code_all_pass=review.get("all_pass"),
            math_answer_correct=review.get("answer_correct"),
            math_worked_correct=review.get("worked_correct"),
            visible_tokens=len(ids),
            unique_tokens=len(set(ids)),
            distinct_1=len(set(ids)) / len(ids) if ids else 0.0,
            server_ms=r["inference"]["elapsed_ms"],
            selector_ms_per_forward=(
                r["decoding"]["mean_selector_ms"] if r["decoding"] else None
            ),
            note=note,
        )
        scored.append(row)
        lookup[r["key"]] = row
    with (OUT / "scores.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(scored[0]))
        writer.writeheader()
        writer.writerows(scored)
    groups = []
    for n in manifest["budgets"]:
        for method in METHODS:
            group = [r for r in scored if r["steps"] == n and r["method"] == method]
            opens = [r for r in group if r["category"] == "open"]
            codes = [r for r in group if r["category"] == "code"]
            maths = [r for r in group if r["category"] == "math"]
            groups.append(
                dict(
                    steps=n,
                    method=method,
                    n=len(group),
                    open_quality=statistics.mean(r["score"] for r in opens),
                    open_fluency=statistics.mean(r["fluency"] for r in opens),
                    code_pass=sum(r["code_all_pass"] for r in codes),
                    math_answer_correct=sum(r["math_answer_correct"] for r in maths),
                    math_worked_correct=sum(r["math_worked_correct"] for r in maths),
                    mean_server_ms=statistics.mean(r["server_ms"] for r in group),
                    median_server_ms=statistics.median(r["server_ms"] for r in group),
                    open_mean_tokens=statistics.mean(
                        r["visible_tokens"] for r in opens
                    ),
                    open_distinct_1=statistics.mean(r["distinct_1"] for r in opens),
                )
            )
    raw = {r["key"]: r for r in rows}
    paired = []
    for n in manifest["budgets"]:
        for base in ["bigram", "trigram"]:
            pairs = [
                (lookup[f"{t['id']}/{n}/{base}"], lookup[f"{t['id']}/{n}/{base}_rep"])
                for t in manifest["tasks"]
            ]
            paired.append(
                dict(
                    steps=n,
                    base=base,
                    n=6,
                    identical_outputs=sum(
                        raw[a["key"]]["sha256"] == raw[b["key"]]["sha256"]
                        for a, b in pairs
                    ),
                    improved=sum(b["score"] > a["score"] for a, b in pairs),
                    tied=sum(b["score"] == a["score"] for a, b in pairs),
                    worsened=sum(b["score"] < a["score"] for a, b in pairs),
                    mean_ms_change=statistics.mean(
                        b["server_ms"] - a["server_ms"] for a, b in pairs
                    ),
                )
            )
    summary = dict(
        complete=True,
        total=180,
        manual_reviews=120,
        code_checks=60,
        groups=groups,
        repetition_pairs=paired,
        error_count=(
            len((OUT / "errors.jsonl").read_text().splitlines())
            if (OUT / "errors.jsonl").exists()
            else 0
        ),
    )
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    labels = {m["id"]: m["label"] for m in manifest["methods"]}
    outputs = [
        "# All generated outputs",
        "",
        f"Space revision: `{manifest['revision']}`. Seed 42 throughout. Exact prompts/settings are in manifest.json.",
        "",
        "Open/math grades are assistant manual judgments, not an independent human review or external judge-model score. Code grades are from fixed execution tests. Exact duplicate text shares the same manual judgment.",
        "",
    ]
    for n in manifest["budgets"]:
        outputs.extend([f"## {n} iterations", ""])
        for task in manifest["tasks"]:
            outputs.extend([f"### {task['id']}", "", task["prompt"], ""])
            for method in METHODS:
                key = f"{task['id']}/{n}/{method}"
                r = raw[key]
                s = lookup[key]
                outputs.extend(
                    [
                        f"#### {labels[method]}",
                        "",
                        f"Key: `{key}` · grade {s['score']}/3 · {s['server_ms']:.1f} ms · {s['visible_tokens']} visible tokens",
                        "",
                        s["note"],
                        "",
                        "````text",
                        r["text"],
                        "````",
                        "",
                    ]
                )
    (OUT / "outputs.md").write_text("\n".join(outputs) + "\n")
    plot(groups)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
