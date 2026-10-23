#!/usr/bin/env python3
"""Summarize matched LLaDA speed checks; never modify the larger study."""

import csv
import json
import statistics as stats

from review_llada_ngram_speedup import OUT, ROOT, code_checks, load, reviews, rid

STAGES = ["before", "after_k16", "after_k8", "after_host_k16", "after_host_k8"]
LABELS = [
    "Original K16",
    "Factored scorer K16",
    "Factored scorer K8",
    "CPU MAP K16",
    "CPU MAP K8",
]


def main():
    rows = load()
    tasks = {
        t["id"]: t
        for t in json.loads(
            (
                ROOT / "artifacts/bigram/llada_ngram_settings_full/manifest.json"
            ).read_text()
        )["tasks"]
    }
    code_checks(rows, tasks)
    checks = json.loads((OUT / "code_checks.json").read_text())
    manual = reviews()
    primary = [r for r in rows if r["trial"] == 0]
    assert all(
        rid(r) in manual for r in primary if r["category"] != "code"
    ), "Manual reviews missing"
    summary = {}
    flat = []
    for stage, label in zip(STAGES, LABELS):
        group = [r for r in primary if r["stage"] == stage]
        if not group:
            continue
        item = dict(
            label=label,
            cases=len(group),
            revision=group[0]["revision"],
            nfe={},
            quality={},
            repeats={},
        )
        assert len(group) == 18, "Incomplete stage"
        for n in [8, 32, 64]:
            subset = [r for r in group if r["steps"] == n]
            item["nfe"][n] = dict(
                total_ms=stats.mean(r["inference"]["elapsed_ms"] for r in subset),
                selector_ms=stats.mean(r["decoding"]["selector_ms"] for r in subset),
            )
        item["total_ms"] = stats.mean(r["inference"]["elapsed_ms"] for r in group)
        item["selector_ms"] = stats.mean(r["decoding"]["selector_ms"] for r in group)
        item["identical_to_original"] = sum(
            r.get("same_as_before", True) for r in group
        )
        all_stage = [r for r in rows if r["stage"] == stage]
        assert len(all_stage) == 24
        assert len({(r["task"], r["steps"], r["trial"]) for r in all_stage}) == 24
        item["all_runs"] = len(all_stage)
        item["all_identical_to_original"] = sum(
            r.get("same_as_before", True) for r in all_stage
        )
        if stage == "after_host_k8":
            device = {
                (r["task"], r["steps"], r["trial"]): r
                for r in rows
                if r["stage"] == "after_k8"
            }
            item["identical_to_device_k8"] = sum(
                r["sha256"] == device[(r["task"], r["steps"], r["trial"])]["sha256"]
                for r in all_stage
            )
            assert item["identical_to_device_k8"] == len(all_stage)
        if stage.endswith("_k16"):
            assert item["all_identical_to_original"] == len(all_stage)
        for cat in ["open", "code", "math"]:
            subset = [r for r in group if r["category"] == cat]
            judged = []
            for r in subset:
                judge = (
                    checks[f"{stage}/{r['task']}/{r['steps']}/0"]
                    if cat == "code"
                    else manual[rid(r)]
                )
                judged.append(judge)
                flat.append(
                    dict(
                        stage=stage,
                        task=r["task"],
                        category=cat,
                        nfe=r["steps"],
                        total_ms=r["inference"]["elapsed_ms"],
                        selector_ms=r["decoding"]["selector_ms"],
                        sha256=r["sha256"],
                        score=judge["score"],
                        correct=judge.get("all_pass", judge.get("answer_correct", "")),
                        same_as_before=r.get("same_as_before", True),
                    )
                )
            item["quality"][cat] = dict(
                n=len(subset), mean_score=stats.mean(j["score"] for j in judged)
            )
            if cat == "code":
                item["quality"][cat]["correct"] = sum(
                    j["all_pass"] is True for j in judged
                )
            if cat == "math":
                item["quality"][cat]["correct"] = sum(
                    j["answer_correct"] for j in judged
                )
        for task in ["amsterdam", "balanced", "mean"]:
            repeated = [
                r
                for r in rows
                if r["stage"] == stage and r["task"] == task and r["steps"] == 32
            ]
            assert len(repeated) == 3
            times = [r["inference"]["elapsed_ms"] for r in repeated]
            item["repeats"][task] = dict(
                median_ms=stats.median(times),
                minimum_ms=min(times),
                maximum_ms=max(times),
                same_text=len({r["sha256"] for r in repeated}) == 1,
            )
        summary[stage] = item
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (OUT / "cases.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(flat[0]))
        w.writeheader()
        w.writerows(flat)
    report = [
        "# LLaDA BG+TG decoding speed check",
        "",
        "Small matched screen on `Ruurd/llada-8b-instruct`: two open questions, two coding tasks, and two math tasks at NFE 8, 32, and 64. Max output/block length 128; seed 42; temperature 0.7; deterministic MAP; bigram weight 1; trigram weight 0.5; PMI min-count 1/clip 2; trigram min-count 2/clip 2. Repetition penalty, APD, sequence sampling, revisable tokens, and early stopping OFF. Open answers use EOS delay with strength 10; coding/math disable it. All measured runs used their exact requested NFE.",
        "",
        "Each version has 18 primary cases plus six extra timing repeats: three runs total for one prompt per domain at NFE 32. A short warmup is excluded. Server elapsed times exclude HTTP/queue delays; selector time is the app's decoding metric. All raw responses, settings, hashes, metrics and deployed revisions are saved alongside this report.",
        "",
        "## Primary timing results",
        "",
        "| Version | Total mean (ms) | Selector mean (ms) | Total reduction vs original | Identical answers |",
        "|---|---:|---:|---:|---:|",
    ]
    base = summary["before"]["total_ms"]
    for stage, item in summary.items():
        report.append(
            f"| {item['label']} | {item['total_ms']:.1f} | {item['selector_ms']:.1f} | {100*(1-item['total_ms']/base):.1f}% | {item['identical_to_original']}/18 |"
        )
    report += [
        "",
        "All timings are measured sequentially on shared ZeroGPU hardware, so small differences are not reliable speedups. K8 reduces the nominal trigram table from 516,096 entries to 64,512 per 128-token block (8×), but does not reduce the 126 sequential recurrence steps. Lower memory/arithmetic cost does not imply an 8× end-to-end speedup.",
        "",
        "| Version | NFE 8 total/selector (ms) | NFE 32 total/selector (ms) | NFE 64 total/selector (ms) |",
        "|---|---:|---:|---:|",
    ]
    for item in summary.values():
        cells = [
            f"{item['nfe'][n]['total_ms']:.1f}/{item['nfe'][n]['selector_ms']:.1f}"
            for n in [8, 32, 64]
        ]
        report.append("| " + item["label"] + " | " + " | ".join(cells) + " |")
    report += [
        "",
        "## Quality screen",
        "",
        "Manual judgments reuse the previous study rubric and exact-text reviews: open quality 0–3; math answer correctness requires score ≥2 (3 also requires correct explanation). Newly seen texts were reviewed without stage/NFE labels. Code uses the previous restricted executable tests and prompt constraints. Repeated runs are excluded from quality counts. These are six cases per domain, from only two distinct prompts each: useful as a regression screen, insufficient to rank general quality.",
        "",
        "| Version | Open quality /3 | Coding passes /6 | Math correct /6 |",
        "|---|---:|---:|---:|",
    ]
    for item in summary.values():
        q = item["quality"]
        report.append(
            f"| {item['label']} | {q['open']['mean_score']:.2f} | {q['code']['correct']} | {q['math']['correct']} |"
        )
    report += [
        "",
        "K8 changed seven of the eighteen primary answers. Coding pass counts stayed the same. On the pipes question at NFE 8, K16 correctly concluded two hours, while K8 stopped after the combined rate and omitted the requested filling time. Other changes traded fluency and detail. This screen does not support promising unchanged quality from reducing K.",
        "",
        "## Repeated timing checks",
        "",
        "| Version | Amsterdam median [min,max] ms | Balanced brackets median [min,max] ms | Mean problem median [min,max] ms |",
        "|---|---:|---:|---:|",
    ]
    for item in summary.values():
        cells = [
            f"{d['median_ms']:.0f} [{d['minimum_ms']:.0f}, {d['maximum_ms']:.0f}]"
            for d in item["repeats"].values()
        ]
        report.append("| " + item["label"] + " | " + " | ".join(cells) + " |")
    report += [
        "",
        "## Implementation and validation",
        "",
        "- The first optimization factors trigram prefix/backoff lookups from K³ to K², retaining the full triple lookup. GPU traceback uses tensor gathers to avoid scalar index synchronization. It reproduced all 24 original K16 outputs, but the approximately 2% mean total improvement is too small to call a useful speedup.",
        "- The second optimization runs the deterministic small-chain MAP recurrence on CPU, after normalization on the original device and one packed host transfer. It preserves float32 addition order, max reduction and first-index tie breaking, then returns only the selected indices to the GPU. CUDA lattices up to 256 positions and K≤16 use this path; larger lattices and positive-temperature sequence sampling retain their existing route. No model weights, score formulas, generation defaults or number of forward passes change.",
        "- Local validation: 136 passed, six CUDA-only cases skipped because this workstation has no CUDA. Tests cover direct versus factored counts, fixed positions, exhaustive best paths and ties, random lattices up to 256×16, numerical extremes, sampling distributions, shared controls and integration without extra model forwards. Hosted exact-output checks supplement the local tests; they are not exhaustive GPU numerical equivalence proofs.",
        "",
        "## Revisions and reproducibility",
        "",
    ]
    for item in summary.values():
        report.append(f"- {item['label']}: `{item['revision']}`.")
    report += [
        "",
        "The earlier 1,974-output study and its pinned revision/data are unchanged. `before.jsonl` and `after_*.jsonl` contain every output; `summary.json` and `cases.csv` contain calculated metrics; `reviews.json` and `code_checks.json` retain judgments. Timing repeats remain separate from primary quality results. Historical CPU microbenchmarks in this folder are diagnostic, not substitutes for these hosted measurements.",
        "",
    ]
    if "after_host_k16" in summary and "after_host_k8" in summary:
        a = summary["after_host_k16"]
        b = summary["before"]
        k = summary["after_host_k8"]
        recommendation = [
            "## Recommendation and deployed result",
            "",
            f"Keep top-k **16**. The CPU MAP version reduced primary-case mean server time from **{b['total_ms']:.1f} ms to {a['total_ms']:.1f} ms ({100*(1-a['total_ms']/b['total_ms']):.1f}% less elapsed time)**, with selector time down **{100*(1-a['selector_ms']/b['selector_ms']):.1f}%**. All **24/24** K16 outputs, including repeats, matched the original exactly. K8 on the same implementation averaged **{k['total_ms']:.1f} ms**, another **{100*(1-k['total_ms']/a['total_ms']):.1f}%** less than optimized K16. This small extra saving came with changed text and one lost correct math answer in this screen. K8 CPU results also matched all **24/24** device K8 results, further checking that changing the recurrence device preserves its decisions.",
            "",
            f"The optimized module is live at revision `{a['revision']}`. Top-k, temperature, scoring weights and all interface defaults were left unchanged. The small speed screen supports this implementation improvement; it does not establish that K8 is better or that CPU decoding will be faster on every hardware/batch/length combination. Larger candidate pools retain the GPU path. Positive-temperature BG+TG sequence sampling was **not** optimized in this task.",
            "",
        ]
        pos = report.index("## Primary timing results")
        report[pos:pos] = recommendation
    (OUT / "REPORT.md").write_text("\n".join(report))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
