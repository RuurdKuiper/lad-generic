#!/usr/bin/env python3
"""Finalize the user-stopped study using only completely matched comparisons.

No generation, selection or network access. Preserve the original run manifest
and raw outputs; the stop snapshot defines the frozen analysis population.
"""

import collections
import csv
import hashlib
import json
import os
import statistics as st

from llada_full_study_review import OUT, review_id
from summarize_llada_full_study import CATEGORIES, METHODS, collect

LABELS = {
    "confidence": "Confidence",
    "bigram": "BG",
    "bigram_rep": "BG + R",
    "trigram": "BG + TG",
    "trigram_rep": "BG + TG + R",
}
BUDGETS = [4, 8, 16, 32, 64, 128]


def mean(values):
    return st.mean(list(values))


def paired_ci(rows, method, baseline, budget=None, category=None):
    """Stratified cluster bootstrap: resample prompts, preserving observed NFEs.

    Ratio-of-sums retains the reported case-weighted estimand despite missing
    prompt/budget pairs. Within each category, paired differences are calculated
    on exactly the same generated and graded cases for both methods.
    """
    import numpy as np

    lookup = {(r["task"], r["steps"], r["method"]): r for r in rows}
    rng = np.random.default_rng(20261022)
    distributions, effects, counts = [], [], {}
    for c in ([category] if category else CATEGORIES):
        clusters = collections.defaultdict(list)
        for r in rows:
            if r["category"] != c or r["method"] != method:
                continue
            if budget is not None and r["steps"] != budget:
                continue
            ref = lookup[(r["task"], r["steps"], baseline)]
            clusters[r["task"]].append(r["normalized"] - ref["normalized"])
        sums = np.array([sum(v) for v in clusters.values()])
        sizes = np.array([len(v) for v in clusters.values()])
        index = rng.integers(0, len(sums), size=(4000, len(sums)))
        distributions.append(sums[index].sum(1) / sizes[index].sum(1))
        effects.append(float(sums.sum() / sizes.sum()))
        counts[c] = dict(prompts=len(sums), cases=int(sizes.sum()))
    interval = np.quantile(np.stack(distributions).mean(0), [0.025, 0.975])
    return dict(
        method=method,
        baseline=baseline,
        budget=budget,
        category=category,
        delta=mean(effects),
        ci95=interval.tolist(),
        clusters=counts,
        bootstrap_repeats=4000,
    )


def table(headers, rows):
    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]
        + ["| " + " | ".join(map(str, row)) + " |" for row in rows]
    )


def main():
    manifest, raw, scored, pending = collect()
    if any(r["phase"] == "sample" for r in raw):
        raise RuntimeError(
            "Sampled arm exists; use finalize_llada_sampled_study.py to preserve all six configurations"
        )
    snapshot = json.loads((OUT / "stop_snapshot.json").read_text())
    assert snapshot["status"] == "stopped_by_user"
    assert (
        hashlib.sha256((OUT / "main/results.jsonl").read_bytes()).hexdigest()
        == snapshot["results_sha256"]
    )
    groups = collections.defaultdict(list)
    for r in raw:
        assert r["phase"] == "main"
        groups[(r["task"], r["steps"])].append(r)
    retained = [
        r
        for group in groups.values()
        if {r["method"] for r in group} == set(METHODS) and len(group) == len(METHODS)
        for r in group
    ]
    keys = {r["key"] for r in retained}
    assert len(retained) == snapshot["matched_rows"] == 1410
    assert not (set(pending) & keys), "Finish grading every retained output first"
    rows = [r for r in scored if r["key"] in keys]
    assert len(rows) == len(retained)
    grades = {r["key"]: r for r in rows}
    assert {r["key"] for r in raw if r["key"] not in keys} == set(
        snapshot["excluded_keys"]
    )
    assert all(
        len([r for r in rows if r["category"] == c and r["method"] == m]) == 94
        for c in CATEGORIES
        for m in METHODS
    )
    # All generated tasks fit 128 tokens in the independent reference validation.
    reference = json.loads((OUT / "reference_validation.json").read_text())
    assert reference
    reports = []
    for budget in [None] + BUDGETS:
        for method in METHODS:
            group = [
                r
                for r in rows
                if r["method"] == method and (budget is None or r["steps"] == budget)
            ]
            component = {}
            for c in CATEGORIES:
                g = [r for r in group if r["category"] == c]
                component[c] = dict(
                    n=len(g),
                    mean_normalized=mean(r["normalized"] for r in g),
                    mean_grade=mean(r["score"] for r in g),
                )
                if c == "open":
                    component[c]["mean_fluency"] = mean(r["fluency"] for r in g)
                else:
                    component[c]["correct"] = sum(r["normalized"] for r in g)
                if c == "math":
                    component[c]["valid_working"] = sum(r["math_worked"] for r in g)
            sources = [
                r
                for r in retained
                if r["method"] == method and (budget is None or r["steps"] == budget)
            ]
            decoder = [r["decoding"] for r in sources if r["decoding"]]
            total_editable = sum(d["editable_predictions"] for d in decoder)
            component["latency_ms"] = mean(r["server_ms"] for r in group)
            component["selector_ms"] = (
                mean(d["selector_ms"] for d in decoder) if decoder else None
            )
            component["changed_fraction"] = (
                sum(d["changed_predictions"] for d in decoder) / total_editable
                if total_editable
                else None
            )
            component["macro_score"] = mean(
                component[c]["mean_normalized"] for c in CATEGORIES
            )
            reports.append(dict(budget=budget, method=method, **component))
    contrasts = []
    for method, baseline in [(m, "confidence") for m in METHODS[1:]] + [
        ("trigram", "bigram"),
        ("bigram_rep", "bigram"),
        ("trigram_rep", "trigram"),
    ]:
        for budget in [None] + BUDGETS:
            for category in [None] + CATEGORIES:
                contrasts.append(paired_ci(rows, method, baseline, budget, category))
    summary = dict(
        status="final_for_user_stopped_matched_subset",
        generated=len(raw),
        retained=len(rows),
        excluded=snapshot["excluded_keys"],
        planned_main=1800,
        planned_main_complete=False,
        retained_grading_complete=True,
        sequence_sampling="Not performed; cancelled at user request",
        stop_snapshot=snapshot,
        groups=reports,
        paired_comparisons=contrasts,
    )
    (OUT / "matched_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    # Replace the interim dashboard with an explicitly stopped-scope summary.
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (OUT / "matched_scores.csv").open("w") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "scores.csv").write_bytes((OUT / "matched_scores.csv").read_bytes())
    state_path = OUT / "main/run_state.json"
    state = json.loads(state_path.read_text())
    state.update(
        status="stopped_by_user",
        retained_for_analysis=len(rows),
        grading_complete_for_retained=True,
        sampling_cancelled=True,
    )
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    write_outputs(retained, grades)
    plot(reports)
    write_report(manifest, rows, retained, reports, contrasts, snapshot)
    print(
        json.dumps(
            dict(
                generated=len(raw),
                retained=len(rows),
                grading_complete=True,
                report=str(OUT / "REPORT.md"),
            ),
            indent=2,
        )
    )


def write_outputs(raw, grades, checks=None):
    ordered = sorted(
        raw,
        key=lambda r: (
            r["steps"],
            CATEGORIES.index(r["category"]),
            r["task"],
            METHODS.index(r["method"]),
        ),
    )
    all_text = [
        "# All retained outputs",
        "",
        f"Exact stored text; only cases completed by all {len(METHODS)} methods. No output repair.",
        "",
    ]
    for r in ordered:
        g = grades[r["key"]]
        all_text.extend(
            [
                f"## {r['key']}",
                "",
                f"**Prompt:** {r['prompt']}",
                "",
                f"**Grade:** {g['score']}; **Review:** {g['note']}",
                "",
                "````text",
                r["text"],
                "````",
                "",
            ]
        )
    (OUT / "ALL_OUTPUTS.md").write_text("\n".join(all_text))
    text = [
        "# Representative outputs",
        "",
        "For every method, NFE and domain: highest grade, middle-ranked grade, and lowest grade. "
        "Ties use task ID. These labels describe relative ranks within the group; a “best” answer "
        "can still be incorrect. Outputs are exact, without corrections. Coding ranks use all-tests "
        "pass first and individual-test fraction second; math ranks use the 0–3 correctness/working grade.",
        "",
    ]
    if checks is None:
        checks = json.loads((OUT / "code_checks.json").read_text())
    for n in BUDGETS:
        for method in METHODS:
            text.extend([f"## NFE {n} — {LABELS[method]}", ""])
            for c in CATEGORIES:
                group = [
                    r
                    for r in raw
                    if r["steps"] == n and r["method"] == method and r["category"] == c
                ]

                def rank(r):
                    g = grades[r["key"]]
                    fraction = (
                        checks[r["key"]].get("passed", 0)
                        / max(checks[r["key"]].get("total", 1), 1)
                        if c == "code"
                        else 0
                    )
                    return (g["score"], fraction, r["task"])

                group.sort(key=rank)
                for label, r in [
                    ("Best", group[-1]),
                    ("Middle", group[len(group) // 2]),
                    ("Worst", group[0]),
                ]:
                    g = grades[r["key"]]
                    text.extend(
                        [
                            f"### {c} — {label}: {r['task']}",
                            "",
                            f"**Prompt:** {r['prompt']}",
                            "",
                            f"**Grade:** {g['score']}. {g['note']}",
                            "",
                            "````text",
                            r["text"],
                            "````",
                            "",
                        ]
                    )
    (OUT / "EXAMPLES.md").write_text("\n".join(text))


def plot(groups):
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/llada-study-matplotlib")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.7), constrained_layout=True)
    colors = [
        "#555555",
        "#0072B2",
        "#009E73",
        "#D55E00",
        "#CC79A7",
        "#009999",
        "#9B5D00",
        "#7A3DB8",
    ]
    if len(METHODS) > len(colors):
        raise ValueError("Provide a distinct plot style for every method")
    for c, ax in zip(CATEGORIES, axes):
        for method, color in zip(METHODS, colors):
            data = [
                next(g for g in groups if g["budget"] == n and g["method"] == method)
                for n in BUDGETS
            ]
            y = [
                g[c]["mean_grade"] if c == "open" else 100 * g[c]["mean_normalized"]
                for g in data
            ]
            ax.plot(
                BUDGETS,
                y,
                marker="o",
                label=LABELS[method],
                color=color,
                linewidth=1.6,
                markersize=4,
            )
        ax.set_xscale("log", base=2)
        ax.set_xticks(BUDGETS, labels=BUDGETS)
        ax.set_xlabel("NFE (maximum output 128 tokens)")
        ax.grid(alpha=0.2)
        ax.set_title(
            {
                "open": "Open-ended quality (0–3)",
                "code": "Coding: all tests pass (%)",
                "math": "Math: final answers correct (%)",
            }[c]
        )
        ax.set_ylim((0, 3.15) if c == "open" else (0, 105))
    axes[0].legend(fontsize=8)
    fig.savefig(OUT / "quality_by_nfe.png", dpi=180)
    fig.savefig(OUT / "quality_by_nfe.svg")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 3.8), constrained_layout=True)
    for method, color in zip(METHODS, colors):
        y = [
            next(
                g["latency_ms"] / 1000
                for g in groups
                if g["budget"] == n and g["method"] == method
            )
            for n in BUDGETS
        ]
        ax.plot(BUDGETS, y, marker="o", label=LABELS[method], color=color)
    ax.set_xscale("log", base=2)
    ax.set_xticks(BUDGETS, labels=BUDGETS)
    ax.set_xlabel("NFE")
    ax.set_ylabel("Mean server generation time (seconds)")
    if "trigram_randomized" in METHODS:
        ax.set_title("Recorded runtimes; Gumbel arm uses optimized MAP", fontsize=9)
    ax.grid(alpha=0.2)
    ax.legend(fontsize=8)
    fig.savefig(OUT / "latency_by_nfe.png", dpi=180)
    plt.close(fig)


def write_report(manifest, rows, raw, groups, contrasts, snapshot):
    lookup = {(g["budget"], g["method"]): g for g in groups}

    def get(n, m):
        return lookup[(n, m)]

    def rate(v):
        return f"{int(v['correct'])}/{v['n']} ({100*v['mean_normalized']:.1f}%)"

    def effect(m, b, c=None, n=None):
        v = next(
            x
            for x in contrasts
            if x["method"] == m
            and x["baseline"] == b
            and x["category"] == c
            and x["budget"] == n
        )
        scale = 3 if c == "open" else 100
        unit = " grade" if c == "open" else " pp"
        return f"{v['delta']*scale:+.2f}{unit} [{v['ci95'][0]*scale:+.2f}, {v['ci95'][1]*scale:+.2f}]"

    out = [
        "# LLaDA n-gram decoding study — final matched results",
        "",
        "Finalized 22 October 2026 after the user requested stopping generation. "
        "**1,413 outputs were saved; 1,410 are included.** The three excluded outputs belong to "
        "one incomplete five-method comparison. Every included output has been graded. "
        "**Sequence sampling was not run.** The originally planned 1,800-run main study and "
        "720-run sampling follow-up were deliberately stopped, not completed.",
        "",
        "## Findings",
        "",
        "- **Open-ended answers:** BG + TG + R has the highest pooled quality (1.98/3), "
        "closely followed by BG + TG (1.96). Both improve over confidence (1.39). "
        "The extra repetition penalty does not provide a consistent improvement over trigrams alone.",
        "- **Coding:** BG and BG + TG each solve 49/94 cases (52.1%), versus 36/94 (38.3%) "
        "for confidence. Adding the fading penalty reduces either guided variant to 48/94. "
        "Trigrams offer no pooled coding advantage over bigrams in this sample.",
        "- **Math:** BG + R is highest pooled at 53/94 (56.4%), followed by BG + TG at 52/94 "
        "(55.3%). However, **confidence has higher observed accuracy at NFE 64 and 128**. "
        "Guidance helps more at low budgets; some high-budget guided solutions remain fluent "
        "despite incorrect arithmetic.",
        "- **Practical choice:** try BG + TG without repetition as a general open-ended option; "
        "BG without repetition is the cheaper coding option. For math, BG + R is promising "
        "at 4–32 NFE, while confidence is preferable in these 64–128 NFE results. "
        "These are exploratory choices among tested packages, not established optimal settings.",
        "",
        "## Scope and fair comparison",
        "",
        "There are 20 distinct prompts per domain (60 total), with one fixed seed. Interruption "
        "leaves **94 prompt/NFE cases per domain**, or 282 cases per method. Each retained case "
        "contains all five methods at the same prompt, NFE and requested settings. A case is a "
        "prompt/NFE pair, not a new independent prompt. No missing result is imputed. "
        "The original manifest, raw outputs and reviews are preserved.",
        "",
        table(
            [
                "NFE",
                "Open-ended cases/method",
                "Coding cases/method",
                "Math cases/method",
            ],
            [[n] + [get(n, "confidence")[c]["n"] for c in CATEGORIES] for n in BUDGETS],
        ),
        "",
        "The incomplete comparison is exercise prompt `open_15`, NFE 4: only BG, BG + R, "
        "and BG + TG finished. All three are excluded. Their text remains in the raw archive.",
        "",
        "Methods: **Confidence** = independent confidence-guided diffusion; **BG** = expanded "
        "PMI bigram Viterbi; **TG** = additional trigram guidance; **R** = probability-weighted "
        "repetition penalty with the existing fade. All n-gram methods use the same expanded corpus.",
        "",
        "## Overall metrics",
        "",
        table(
            [
                "Method",
                "Open quality /3",
                "Open fluency /3",
                "Coding solved",
                "Math final correct",
                "Math correct + valid working",
            ],
            [
                [
                    LABELS[m],
                    f"{get(None,m)['open']['mean_grade']:.3f}",
                    f"{get(None,m)['open']['mean_fluency']:.3f}",
                    rate(get(None, m)["code"]),
                    rate(get(None, m)["math"]),
                    f"{get(None,m)['math']['valid_working']}/94",
                ]
                for m in METHODS
            ],
        ),
        "",
        "Open quality measures coherence, relevance, grammar, repetition and material factual errors. "
        "Fluency is scored separately, so fluent factual mistakes do not count as fully correct answers. "
        "Math final-answer accuracy requires all requested answers, with correct labels; valid working "
        "is stricter and also rejects corrupted equations, contradictions and missing requested reasoning.",
        "",
        "## Results by NFE",
        "",
        "![Quality by NFE](quality_by_nfe.png)",
        "",
    ]
    for c, title in [
        ("open", "Open-ended quality /3"),
        ("code", "Coding: all tests pass"),
        ("math", "Math: final-answer accuracy"),
    ]:
        out.extend(
            [
                f"### {title}",
                "",
                table(
                    ["NFE"] + [LABELS[m] for m in METHODS],
                    [
                        [n]
                        + [
                            (
                                f"{get(n,m)[c]['mean_grade']:.2f}"
                                if c == "open"
                                else rate(get(n, m)[c])
                            )
                            for m in METHODS
                        ]
                        for n in BUDGETS
                    ],
                ),
                "",
            ]
        )
    out.extend(
        [
            "At four steps, open-ended text remains mostly unusable even with guidance, "
            "and coding success is at most 1/15. The gains do not make this regime reliable. "
            "At 8–16 steps, guidance produces the clearest coding gains. At 128 steps coding "
            "ties across methods. Open quality converges, while guided math remains worse than confidence.",
            "",
            "### What the repetition penalty and trigrams add",
            "",
            table(
                [
                    "Change",
                    "Open quality change [95% CI]",
                    "Coding change [95% CI]",
                    "Math change [95% CI]",
                ],
                [
                    [f"{LABELS[m]} vs {LABELS[b]}"]
                    + [effect(m, b, c) for c in CATEGORIES]
                    for m, b in [
                        ("trigram", "bigram"),
                        ("bigram_rep", "bigram"),
                        ("trigram_rep", "trigram"),
                    ]
                ],
            ),
            "",
            "The penalty helps low-budget bigram math, especially at four steps (6/16 versus 3/16). "
            "It does not improve coding here and does not consistently improve trigrams. "
            "The fade is absolute: approximately 1, 0.932, 0.697, 0.303, 0.068, 0; "
            "zero from step six onward. Consequently high-NFE differences reflect trajectories "
            "changed early, not a penalty active throughout decoding.",
            "",
            "## Uncertainty",
            "",
            table(
                [
                    "Method vs confidence",
                    "Open quality change [95% CI]",
                    "Coding change [95% CI]",
                    "Math change [95% CI]",
                ],
                [
                    [LABELS[m]] + [effect(m, "confidence", c) for c in CATEGORIES]
                    for m in METHODS[1:]
                ],
            ),
            "",
            "Intervals use 4,000 paired bootstrap replicates, resampling prompts within each domain "
            "and retaining each sampled prompt’s entire available NFE vector. Ratios of total "
            "differences to total cases preserve the reported case-weighted means despite incomplete "
            "budget coverage. These are exploratory, unadjusted intervals across many comparisons. "
            "They capture prompt variation in this small set, not seed variation or reviewer uncertainty. "
            "A confidence interval spanning zero does not establish an advantage.",
            "",
            "## Speed and decoding changes",
            "",
            "![Generation latency by NFE](latency_by_nfe.png)",
            "",
            table(
                ["NFE"] + [LABELS[m] + " (ms)" for m in METHODS],
                [
                    [n] + [f"{get(n,m)['latency_ms']:.0f}" for m in METHODS]
                    for n in BUDGETS
                ],
            ),
            "",
            table(
                [
                    "Method",
                    "Pooled mean server ms",
                    "Overhead vs confidence",
                    "Selector ms/run",
                    "Changed editable predictions",
                ],
                [
                    [
                        LABELS[m],
                        f"{get(None,m)['latency_ms']:.0f}",
                        f"{100*(get(None,m)['latency_ms']/get(None,'confidence')['latency_ms']-1):+.1f}%",
                        (
                            f"{get(None,m)['selector_ms']:.1f}"
                            if get(None, m)["selector_ms"] is not None
                            else "—"
                        ),
                        (
                            f"{100*get(None,m)['changed_fraction']:.1f}%"
                            if get(None, m)["changed_fraction"] is not None
                            else "—"
                        ),
                    ]
                    for m in METHODS
                ],
            ),
            "",
            "Latency is the measured server generation time, excluding client queue/network overhead; "
            "three warm-up requests are excluded. These are single executions on shared Hugging Face "
            "infrastructure, not repeated microbenchmarks. Selector time is an instrumented portion "
            "of the same request. The change fraction compares selected predictions against independent "
            "diffusion argmax at editable positions **over all denoising iterations**; it is not final "
            "output disagreement between separately generated answers. Counts aggregate positions "
            "before taking the ratio. All retained runs used exactly the requested NFE; no added "
            "model forwards, APD or early stopping.",
            "",
            "## Settings and reproducibility",
            "",
            "- Model: `GSAI-ML/LLaDA-8B-Instruct`; Space: `Ruurd/llada-8b-instruct`.",
            f"- Space revision: `{manifest['revision']}`.",
            "- Output length/block length 128; NFE 4, 8, 16, 32, 64, 128; seed 42.",
            "- Top-k/candidates 16; temperature 0.7; bigram weight 1; repetition strength 1.",
            "- PMI minimum count 1, clip ±2; trigram minimum count 2, clip ±2, relative weight 0.5.",
            "- Open-ended: Delay EOS/EOT ON, ending-delay strength 10. Coding/math: delay OFF, strength 1 (neutral).",
            "- APD OFF; sequence sampling OFF; count-every-candidate OFF; risk alternative OFF.",
            "- Fading enabled in the repetition methods; diffusion-probability remasking retained.",
            "",
            "The current MAP Viterbi path is deterministic and ignores temperature while sequence "
            "sampling is OFF; the independent confidence baseline samples with temperature 0.7. "
            "This compares the existing method packages. Temperature was not tuned, and the "
            "unperformed sequence-sampling follow-up cannot be inferred from these results.",
            "",
            "The frozen dataset includes 20 open questions from the standard question list, 20 "
            "small Python assignments and 20 arithmetic/algebra/word problems. Correct reference "
            "code passes all 199 independent edge tests and fits the same 128-token cap. Coding "
            "counts as solved only if all tests and explicit constraints pass. There are no "
            "pending code-safety review blocks. Open/math judgments were made by the assistant "
            "through explicit inspection of anonymous text, with method/NFE labels hidden; "
            "exact duplicates within a prompt share one judgment. This is not independent human "
            "or multi-rater evaluation. Some repetition-heavy review displays used exact consecutive "
            "substring compression with explicit repeat counts; stored outputs were not altered.",
            "",
            "## Limits and interpretation",
            "",
            "- Twenty prompts per domain and one seed do not establish a global optimum. The NFE "
            "curve also uses slightly different available prompt subsets at different budgets; "
            "compare methods within a row, and treat cross-budget differences cautiously.",
            "- The decision to stop was made after inspecting intermediate results; confidence "
            "intervals are descriptive and do not correct for this optional stopping or multiple comparisons.",
            "- Open-ended guided methods additionally apply the ending-logit penalty of ten, "
            "while confidence uses retention delay. Open gains therefore concern the full package, "
            "not isolated PMI effects. Coding/math disable both ending controls.",
            "- The 128-token cap can truncate a valid solution before its final answer, which "
            "counts as unsolved. Results do not generalize to long programs or difficult math.",
            "- The development/validation split remains in the archive, but no method was selected "
            "and no follow-up was run. All pooled results here are exploratory; there is no claim "
            "of held-out confirmation for the practical recommendations.",
            "",
            "## Outputs and audit files",
            "",
            "- [Best, middle and worst examples for every method, NFE and domain](EXAMPLES.md).",
            "- [Every retained output, prompt and judgment](ALL_OUTPUTS.md).",
            "- [Matched scores CSV](matched_scores.csv), [summary and bootstrap comparisons](matched_summary.json).",
            "- [Frozen run manifest](manifest.json), [original protocol](PROTOCOL.md), [stop snapshot](stop_snapshot.json).",
            "- [Raw main outputs, including the three excluded rows](main/results.jsonl), [retained raw outputs](matched_results.jsonl).",
            "- [Manual reviews](reviews.json), [code checks](code_checks.json), [reference validation](reference_validation.json).",
            "",
            "The original protocol describes the larger planned study. This report and the stop "
            "snapshot document the user-authorized change in scope. No Space settings, model weights "
            "or production code were changed while finalizing this analysis.",
            "",
        ]
    )
    (OUT / "REPORT.md").write_text("\n".join(out))


if __name__ == "__main__":
    main()
