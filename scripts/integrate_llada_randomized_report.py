#!/usr/bin/env python3
"""Publish the completed eighth arm into the original LLaDA report and plots.

No inference. Freeze seven-arm inputs before updating derived current artifacts.
"""

import csv, hashlib, json
from pathlib import Path
import statistics as st
import finalize_llada_full_study as charts
import finalize_llada_sampled_study as report
from summarize_llada_randomized_viterbi import collect
from evaluate_llada_randomized_viterbi import STUDY, OUT, read, historical


def main():
    amendment = json.loads((OUT / "amendment.json").read_text())
    # Preserve exact seven-arm bytes and historical figures before any overwrite.
    names = [
        "combined_results.jsonl",
        "combined_scores.csv",
        "combined_summary.json",
        "summary.json",
        "scores.csv",
        "quality_by_nfe.png",
        "quality_by_nfe.svg",
        "latency_by_nfe.png",
        "latency_by_nfe.svg",
        "analysis_audit.json",
    ]
    for name in names:
        source = STUDY / name
        target = STUDY / ("pre_randomized_" + name)
        if source.exists() and not target.exists():
            target.write_bytes(source.read_bytes())
    assert (
        hashlib.sha256(historical("combined_results.jsonl").read_bytes()).hexdigest()
        == amendment["comparison_sha256"]
    )
    previous = STUDY / "PRE_RANDOMIZED_REPORT.md"
    if not previous.exists():
        text = (STUDY / "REPORT.md").read_text()
        for name in ["quality_by_nfe.png", "latency_by_nfe.png"]:
            text = text.replace("](" + name + ")", "](pre_randomized_" + name + ")")
        previous.write_text(text)
    raw_new, new, rows, pending = collect()
    assert len(raw_new) == len(new) == 282 and not pending
    old_raw = read(historical("combined_results.jsonl"))
    raw = old_raw + raw_new
    assert len(raw) == len(rows) == 2256 and len({r["key"] for r in raw}) == 2256
    prior = json.loads(historical("combined_summary.json").read_text())
    methods = list(dict.fromkeys(g["method"] for g in prior["groups"])) + [
        "trigram_randomized"
    ]
    assert len(methods) == 8
    labels = dict(
        report.LABELS,
        confidence="Confidence T=0.7",
        confidence_zero="Confidence T=0",
        trigram_sample="BG + TG exact sampler",
        trigram_randomized="BG + TG Gumbel T=0.7",
    )
    lookup_raw = {r["key"]: r for r in raw}
    for r in rows:
        original = lookup_raw[r["key"]]
        for k in ["split", "base_method", "phase"]:
            r[k] = original[k]
        if isinstance(r.get("math_worked"), str):
            r["math_worked"] = r["math_worked"] == "True" if r["math_worked"] else None
        if r.get("fluency") == "":
            r["fluency"] = None
    groups = []
    for n in [None] + charts.BUDGETS:
        for m in methods:
            subset = [
                r for r in rows if r["method"] == m and (n is None or r["steps"] == n)
            ]
            g = dict(budget=n, method=m)
            for c in charts.CATEGORIES:
                a = [r for r in subset if r["category"] == c]
                g[c] = dict(
                    n=len(a),
                    mean_grade=st.mean(r["score"] for r in a),
                    mean_normalized=st.mean(r["normalized"] for r in a),
                )
                if c == "open":
                    g[c]["mean_fluency"] = st.mean(r["fluency"] for r in a)
                else:
                    g[c]["correct"] = sum(r["normalized"] for r in a)
                if c == "math":
                    g[c]["valid_working"] = sum(bool(r["math_worked"]) for r in a)
            g["macro_score"] = st.mean(
                g[c]["mean_normalized"] for c in charts.CATEGORIES
            )
            g["latency_ms"] = st.mean(r["server_ms"] for r in subset)
            decoder = [
                r["decoding"]
                for r in raw
                if r["method"] == m and (n is None or r["steps"] == n) and r["decoding"]
            ]
            editable = sum(d["editable_predictions"] for d in decoder)
            g["selector_ms"] = (
                st.mean(d["selector_ms"] for d in decoder) if decoder else None
            )
            g["changed_fraction"] = (
                sum(d["changed_predictions"] for d in decoder) / editable
                if editable
                else None
            )
            groups.append(g)
    extra = json.loads((OUT / "summary.json").read_text())
    summary = dict(
        prior,
        status="final_eight_method_matched_study",
        generated=prior["generated"] + 282,
        retained=2256,
        randomized_generated=282,
        randomized_amendment=amendment,
        groups=groups,
        paired_comparisons=prior["paired_comparisons"] + extra["contrasts"],
        historical_seven_method_results="pre_randomized_combined_results.jsonl",
        timing_caveat="Randomized arm uses optimized MAP; earlier arms predate that optimization.",
    )
    (STUDY / "combined_results.jsonl").write_bytes(
        historical("combined_results.jsonl").read_bytes()
        + (OUT / "results.jsonl").read_bytes()
    )
    fields = [
        "key",
        "task",
        "category",
        "split",
        "steps",
        "method",
        "base_method",
        "phase",
        "score",
        "normalized",
        "fluency",
        "math_worked",
        "server_ms",
        "sha256",
        "note",
    ]
    with (STUDY / "combined_scores.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    (STUDY / "scores.csv").write_bytes((STUDY / "combined_scores.csv").read_bytes())
    for name in ["combined_summary.json", "summary.json"]:
        (STUDY / name).write_text(json.dumps(summary, indent=2) + "\n")
    charts.METHODS = report.METHODS = methods
    charts.LABELS = report.LABELS = labels
    checks = json.loads((STUDY / "code_checks.json").read_text())
    checks.update(json.loads((OUT / "code_checks.json").read_text()))
    grades = {r["key"]: r for r in rows}
    charts.write_outputs(raw, grades, checks=checks)
    charts.plot(groups)
    manifest = json.loads((STUDY / "manifest.json").read_text())
    report.write_report(
        manifest, groups, summary["paired_comparisons"], prior["sampling_win_tie_loss"]
    )
    path = STUDY / "REPORT.md"
    text = path.read_text()
    text = (
        text.replace("seven matched configurations", "eight matched configurations")
        .replace("1,974 graded outputs", "2,256 graded outputs")
        .replace("× seven configurations", "× eight configurations")
    )
    text = text.replace(
        "Temperature-zero confidence adds another 282. ",
        "Temperature-zero confidence adds another 282; randomized BG+TG adds a further 282. ",
    )
    text = text.replace(
        "The experiment now includes two follow-up configurations: sampled BG + TG and temperature-zero confidence. The sampled run and report were finished first.",
        "The experiment includes three follow-ups: exact sampled BG+TG, temperature-zero confidence, and Gumbel-randomized BG+TG. They were completed sequentially; prior outputs remain unchanged.",
    )
    text = text.replace(
        "- Diffusion-probability remasking throughout; no training or production inference changes.",
        "- Diffusion-probability remasking throughout; no training changes or additional model forwards. The production temperature default was updated after the study; historical deterministic arms remain deterministic.",
    )
    text = text.replace(
        f"- Space revision: `{manifest['revision']}`.",
        f"- Historical seven-arm Space revision: `{manifest['revision']}`; randomized arm: `{amendment['revision']}`.",
    )
    text = text.replace(
        "relative to the current diffusion argmax;",
        "relative to the current diffusion argmax;",
    )
    # Put the added arm, its calibrated interpretation and timing caveat up front.
    intro = """## Standard temperature decoding and the new eighth arm

**BG + TG Gumbel T=0.7** adds independent unit Gumbel noise scaled by0.7 to
editable unary token log-scores, then uses optimized Viterbi with unchanged BG/TG
transitions. It is the new standard LLaDA BG/BG+TG temperature behavior:
**temperature0 is deterministic; positive temperatures add variation**. The
exact sampler remains available as an optional slower alternative. The recorded
historical BG/BG+TG arms used deterministic Viterbi despite their0.7 temperature
setting; do not reinterpret them as randomized runs.

The randomized arm scored **1.915/3 open quality,48/94 coding,45/94 math**;
its macro score0.543 is close to exact sampling0.544 and below deterministic
BG+TG0.576. Paired intervals versus both guided alternatives include zero;
this is not evidence of equivalence or a globally best temperature. The
Gumbel0.7 scale is not calibrated to exact-samplerT=0.7. Noise affects only
unary scores; retention uses the original diffusion probabilities.

**Timing figures combine implementation versions:** the randomized arm uses
optimized CPU MAP, whereas the historical guided arms predate that optimization.
Their displayed timing gap is not caused solely by randomization. On14 matching
saved optimized cases, deterministic averaged1514ms and randomized1482ms;
the small difference is within shared-hardware variation. No new inference
was run to rebuild this report.

See the [randomized extension](randomized/REPORT.md) for the math error audit,
paired intervals and separate seed-variation check. The [seven-configuration
report](PRE_RANDOMIZED_REPORT.md) and pre_randomized_* data/figures preserve
all previous results. The original stopped main-study files remain immutable.

"""
    pos = text.index("## Added configuration")
    text = text[:pos] + intro + text[pos:]
    # Add its matched effect table; all ordinary metric/NFE/latency tables already
    # contain the eighth arm through the shared report writer.
    effects = extra["contrasts"]
    text += (
        "\n\n## Randomized Viterbi: paired changes\n\n"
        + charts.table(
            [
                "Compared with",
                "Open grade change [95% CI]",
                "Coding pp [95% CI]",
                "Math pp [95% CI]",
            ],
            [
                [labels[b]]
                + [
                    next(
                        f"{q['delta']*(3 if c=='open' else 100):+.2f} [{q['ci95'][0]*(3 if c=='open' else 100):+.2f}, {q['ci95'][1]*(3 if c=='open' else 100):+.2f}]"
                        for q in effects
                        if q["baseline"] == b
                        and q["budget"] is None
                        and q["category"] == c
                    )
                    for c in charts.CATEGORIES
                ]
                for b in ["trigram", "trigram_sample", "confidence"]
            ],
        )
        + "\n"
    )
    text += "\nNew arm reviews and code checks are in [randomized/reviews.json](randomized/reviews.json) and [randomized/code_checks.json](randomized/code_checks.json); historical review files remain unchanged.\n"
    path.write_text(text)
    # Audit each method against its actual experiment revision, not UI defaults.
    cases = {}
    for r in raw:
        assert r["revision"] == (
            amendment["revision"]
            if r["method"] == "trigram_randomized"
            else manifest["revision"]
        )
        assert r["inference"]["denoising_forward_passes"] == r["steps"]
        assert hashlib.sha256(r["text"].encode()).hexdigest() == r["sha256"]
        cases.setdefault((r["task"], r["steps"]), set()).add(r["method"])
    assert len(cases) == 282 and all(v == set(methods) for v in cases.values())
    assert all(
        sum(r["method"] == m and r["category"] == c for r in raw) == 94
        for m in methods
        for c in charts.CATEGORIES
    )
    assert (STUDY / "EXAMPLES.md").read_text().count("### ") == 54 * 8
    assert (STUDY / "ALL_OUTPUTS.md").read_text().count("\n## ") == 2256
    audit = dict(
        retained=2256,
        matched_cases=282,
        methods=methods,
        cases_per_domain_method=94,
        representative_examples=432,
        all_graded=True,
        forward_counts_match=True,
        historical_seven_arm_sha256=amendment["comparison_sha256"],
        figures_include_all_methods=True,
    )
    (STUDY / "analysis_audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
