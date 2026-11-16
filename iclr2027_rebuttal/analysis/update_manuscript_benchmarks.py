"""Export the completed benchmark campaign for the revised manuscript, offline.

Only saved correctness flags are read: no generation, scoring changes, network
calls or execution of generated programs. Historical workbooks are not edited.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WORK = HERE.parent
PAPER = WORK / "paper"
sys.path.insert(0, str(HERE))
from final_evaluation_comparison import paired_bootstrap, wilson

TASKS = ["arc_c", "gpqa", "hellaswag", "mmlu", "mmlu_pro", "gsm8k", "math", "humaneval", "mbpp"]
MODELS = ["gemma_d", "gemma_ar", "qwen_d", "qwen_ar", "ministral_d", "ministral_ar",
          "llama_25k", "llama_50k", "llama_ar", "llada"]
LABELS = {"gemma_d": "BYOD-Gemma", "gemma_ar": "Gemma AR", "qwen_d": "BYOD-Qwen",
          "qwen_ar": "Qwen AR", "ministral_d": "BYOD-Ministral", "ministral_ar": "Ministral AR",
          "llama_25k": "BYOD-Llama-25k", "llama_50k": "BYOD-Llama-50k", "llama_ar": "Llama AR", "llada": "LLaDA"}
TASK_LABELS = {"arc_c": "ARC-C", "gpqa": "GPQA-Main", "hellaswag": "HellaSwag", "mmlu": "MMLU",
               "mmlu_pro": "MMLU-Pro", "gsm8k": "GSM8K", "math": "MATH-500", "humaneval": "HumanEval",
               "mbpp": "MBPP sanitized"}
PUBLISHED_LLADA = dict(zip(TASKS, [.885, .333, .746, .655, .370, .694, .319, .494, .410]))
REPLICATES = 20_000
SEED = 20261116


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    final_path = WORK / "evaluation/generation_diagnostic/nov15_gemma/assembled_results.jsonl"
    analysis_path = HERE / "final_evaluation_comparison.json"
    report = json.loads(analysis_path.read_text())
    assert sha(final_path) == report["inputs"][str(final_path.relative_to(WORK))]
    rows = [json.loads(line) for line in final_path.open() if line.strip()]
    assert len(rows) == report["final_outcomes"] == 21_640
    groups = defaultdict(list)
    for row in rows:
        assert isinstance(row["correct"], bool)
        groups[row["model_key"], row["task"]].append(row)
    assert len(groups) == 90
    cells, macro = {}, {}
    rng = np.random.default_rng(SEED)
    for key in MODELS:
        cells[key] = {}
        draws = np.zeros(REPLICATES)
        for task in TASKS:
            group = groups[key, task]
            n = len(group)
            assert n == (164 if task == "humaneval" else 250)
            fps = {r["fingerprint"] for r in group}
            assert len(fps) == n
            assert fps == {r["fingerprint"] for r in groups[MODELS[0], task]}
            k = sum(r["correct"] for r in group)
            lo, hi = wilson(k, n)
            cells[key][task] = {"k": k, "n": n, "accuracy": k/n, "wilson95": [lo, hi]}
            # Exact count representation of resampling n binary items with replacement.
            draws += rng.binomial(n, k/n, size=REPLICATES) / n / len(TASKS)
            previous = next(c["final"] for c in report["cells"] if c["model"] == key and c["task"] == task)
            assert (k, n) == (previous["k"], previous["n"])
        mean = sum(cells[key][t]["accuracy"] for t in TASKS) / len(TASKS)
        macro[key] = {"accuracy": mean, "bootstrap95": np.quantile(draws, [.025, .975]).tolist()}
    paired = [paired_bootstrap(rows, p["first"], p["second"]) for p in report["paired_macro_comparisons"]]
    assert paired == report["paired_macro_comparisons"]
    data = {
        "version": "completed_benchmarks_20261116_v1", "generator_sha256": sha(Path(__file__)),
        "sources": {str(p.relative_to(WORK)): sha(p) for p in [final_path, analysis_path]},
        "scoring_version": "final_answer_math_verify_0.8.0_v3",
        "selection_policy": sorted({r["selection_policy"] for r in rows}),
        "model_order": MODELS, "task_order": TASKS, "labels": LABELS, "task_labels": TASK_LABELS,
        "selected_outcomes": len(rows), "historical_outcomes": report["original_outcomes"],
        "net_added_selected_outcomes": len(rows)-report["original_outcomes"],
        "cells": cells, "macro": macro, "paired_macro": paired,
        "methods": {"individual": "Two-sided 95% Wilson score intervals, z=1.959963984540054, integer k/n.",
                    "macro": "Equal-weight mean of nine task accuracies; percentile item bootstrap separately within each task; binomial count representation of empirical resampling; tasks fixed.",
                    "macro_replicates": REPLICATES, "macro_seed": SEED,
                    "paired": "Same within-task item draws for both models (multinomial representation of -1/0/+1 differences); 20000 replicates, seed 20261115.",
                    "scope": "Nominal 95% intervals, no adjustment for multiple comparisons across five BYOD configurations or selection of the strongest conversion. No superiority claim. Item variation within selected tasks, not training-run uncertainty, subset-selection correction or unseen task families. Full HumanEval removes subsampling uncertainty for that fixed set; its Wilson interval describes an item-population interpretation."},
        "published_llada": {"accuracy": PUBLISHED_LLADA, "macro": sum(PUBLISHED_LLADA.values())/9,
                            "ci": None, "protocol": "Published results; per-question outputs not available for our uncertainty calculations."},
    }
    dest = PAPER / "source_results/benchmark_results_20261116.json"
    dest.write_text(json.dumps(data, indent=2)+"\n")
    write_main_table(data)
    write_interval_tables(data)
    update_radar(data, dest)
    lines = ["# Completed benchmark intervals for the revised manuscript", "",
             "Generated offline from the versioned per-question selection; historical workbooks are unchanged.", "",
             "| Model | Nine-task mean | Nominal 95% bootstrap interval |", "|---|---:|---:|"]
    for key in MODELS:
        m = macro[key]; lo, hi = m["bootstrap95"]
        lines.append(f"| {LABELS[key]} | {100*m['accuracy']:.2f}% | [{100*lo:.2f}, {100*hi:.2f}]% |")
    lines += ["", "20,000 percentile resamples within each of nine fixed tasks (seed 20261116); every task retains equal weight. Paired contrasts use shared item draws (seed 20261115), rather than subtracting marginal confidence limits.", "",
              "21,640 final selected outcomes versus 11,070 historical outcomes: net +10,570. Replacement generations and diagnostics are not counted as newly added selected items.", "",
              "Per-task intervals are 95% Wilson intervals from integer counts. All intervals are nominal/unadjusted and describe item variation, not variation across training seeds. They do not establish benchmark-wide representativeness or uncertainty over unseen task families."]
    (HERE / "manuscript_benchmark_intervals.md").write_text("\n".join(lines)+"\n")
    print("Exported 90 final cells, 10 macro intervals and 3 paired contrasts; regenerated benchmark radars.")


def marked(value, best, best_byod):
    s = f"{100*value:.1f}"
    if best_byod:
        s = r"\underline{"+s+"}"
    return r"\textbf{"+s+"}" if best else s


def write_main_table(data):
    cells = data["cells"]
    diff = [m for m in MODELS if m.endswith("_d") or m.startswith("llama_") and m != "llama_ar"] + ["llada"]
    byod = [m for m in diff if m != "llada"]
    lines = [r"% Generated by analysis/update_manuscript_benchmarks.py; do not edit values by hand.",
             r"\begin{tabular}{lrrrrrrrrrrr}", r"\toprule",
             r"& \multicolumn{2}{c}{Gemma} & \multicolumn{2}{c}{Qwen} & \multicolumn{2}{c}{Ministral} & \multicolumn{3}{c}{Llama} & \multicolumn{2}{c}{LLaDA} \\",
             r"Task & D & AR & D & AR & D & AR & D-25k & D-50k & AR & Ours & Published \\", r"\midrule"]
    for task in TASKS:
        if task in ("gsm8k", "humaneval"):
            lines.append(r"\midrule")
        best = max(cells[k][task]["accuracy"] for k in diff)
        best_byod = max(cells[k][task]["accuracy"] for k in byod)
        values = [marked(cells[k][task]["accuracy"], k in diff and cells[k][task]["accuracy"] == best,
                         k in byod and cells[k][task]["accuracy"] == best_byod) for k in MODELS]
        label = {"gpqa": "GPQA", "mbpp": "MBPP"}.get(task, TASK_LABELS[task])
        lines.append(label+" & "+" & ".join(values)+f" & {100*PUBLISHED_LLADA[task]:.1f}"+r" \\")
    lines.append(r"\midrule")
    best = max(data["macro"][k]["accuracy"] for k in diff)
    best_byod = max(data["macro"][k]["accuracy"] for k in byod)
    values = [marked(data["macro"][k]["accuracy"], k in diff and data["macro"][k]["accuracy"] == best,
                     k in byod and data["macro"][k]["accuracy"] == best_byod) for k in MODELS]
    lines += ["Average & "+" & ".join(values)+f" & {100*data['published_llada']['macro']:.1f}"+r" \\",
              "95\\% CI & "+" & ".join(f"[{100*data['macro'][k]['bootstrap95'][0]:.1f},{100*data['macro'][k]['bootstrap95'][1]:.1f}]" for k in MODELS)+r" & \na \\",
              r"\bottomrule", r"\end{tabular}"]
    (PAPER / "generated_benchmark_results.tex").write_text("\n".join(lines)+"\n")


def write_interval_tables(data):
    panels = [TASKS[:3], TASKS[3:6], TASKS[6:]]
    lines = ["% Generated from integer counts; 95% Wilson intervals, percentages."]
    for i, tasks in enumerate(panels, 1):
        lines += [r"\begin{table}[ht]",
                  r"\caption{Complete benchmark accuracy and nominal 95\% Wilson intervals (\%), panel "+str(i)+r" of 3. HumanEval uses all 164 items; every other task uses 250. The same items are used for all models.}",
                  r"\label{tab:benchmark-intervals-"+str(i)+"}", r"\centering", r"\small",
                  r"\begin{tabular}{lrrr}", r"\toprule",
                  "Model & "+" & ".join(TASK_LABELS[t] for t in tasks)+r" \\", r"\midrule"]
        for key in MODELS:
            texts = []
            for task in tasks:
                cell = data["cells"][key][task]; lo, hi = cell["wilson95"]
                texts.append(f"{100*cell['accuracy']:.1f} [{100*lo:.1f}, {100*hi:.1f}]")
            lines.append(LABELS[key]+" & "+" & ".join(texts)+r" \\")
        lines += [r"\bottomrule", r"\end{tabular}", r"\end{table}", ""]
    (PAPER / "generated_benchmark_intervals.tex").write_text("\n".join(lines))


def update_radar(data, source):
    # Reuse the established plot design, without regenerating unrelated PPL/loss figures.
    sys.path.insert(0, str(ROOT / "scripts"))
    import generate_paper_figures as figures
    mapping = {"LLaDA-8B-Instruct (own validation)": "llada", "llama-3.1-8b-mask": "llama_25k",
               "llama-3.1-8b-autoregressive": "llama_ar", "gemma-2-9b-mask": "gemma_d",
               "qwen-2.5-7b-mask": "qwen_d", "ministral-mask": "ministral_d"}
    radar = {"tasks": figures.TASK_ORDER, "task_labels": [figures.TASK_LABELS[t] for t in figures.TASK_ORDER],
             "groups": {group: {label: [data["cells"][mapping[model]][t]["accuracy"] for t in figures.TASK_ORDER]
                                for label, model in series.items()} for group, series in figures.RADAR_GROUPS.items()},
             "source": str(source.relative_to(WORK)), "source_sha256": sha(source),
             "evaluated_items": {t: data["cells"]["gemma_d"][t]["n"] for t in TASKS}}
    figures.plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "pdf.fonttype": 42, "ps.fonttype": 42})
    figures.plot_radar_panels(radar, PAPER / "figures")
    manifest_path = PAPER / "figures/figure_data.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["radar"] = radar
    manifest["benchmark_source"] = {"file": str(source.relative_to(WORK)), "sha256": sha(source)}
    manifest["accuracy_cells"] = "Versioned completed benchmark JSON, integer correct/evaluated counts; historical workbook not used for radar values."
    manifest["notes"] = [n for n in manifest["notes"] if "125 examples" not in n]
    note = "Benchmark radars use 250 shared questions/task and all 164 HumanEval items. Other figures retain their original independent measurements."
    if note not in manifest["notes"]:
        manifest["notes"].append(note)
    manifest_path.write_text(json.dumps(manifest, indent=2)+"\n")


if __name__ == "__main__":
    main()
