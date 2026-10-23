#!/usr/bin/env python3
"""Update matched LLaDA results with sampled BG+TG and optional zero-T confidence."""

import argparse
import csv
import hashlib
import json
import re
import statistics as st

import finalize_llada_full_study as base
from llada_full_study_review import OUT
from summarize_llada_full_study import collect

METHODS = base.METHODS + ["trigram_sample"]
LABELS = dict(base.LABELS, trigram_sample="BG + TG sampled")


def main():
    global METHODS, LABELS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-confidence-zero", action="store_true")
    args = parser.parse_args()
    randomized = OUT / "randomized/run_state.json"
    if randomized.exists() and json.loads(randomized.read_text()).get(
        "report_complete"
    ):
        from integrate_llada_randomized_report import main as integrate

        integrate()
        return
    zero = args.include_confidence_zero
    if zero:
        METHODS = METHODS + ["confidence_zero"]
        LABELS = dict(
            LABELS, confidence="Confidence T=0.7", confidence_zero="Confidence T=0"
        )
    manifest, raw, scored, pending = collect()
    if not zero and any(r["phase"] == "confidence_zero" for r in raw):
        raise RuntimeError(
            "Use --include-confidence-zero to preserve the new seventh arm"
        )
    amendment = json.loads((OUT / "sampling_amendment.json").read_text())
    snapshot = json.loads((OUT / "stop_snapshot.json").read_text())
    assert (
        hashlib.sha256((OUT / "main/results.jsonl").read_bytes()).hexdigest()
        == snapshot["results_sha256"]
    )
    assert (
        hashlib.sha256((OUT / "matched_results.jsonl").read_bytes()).hexdigest()
        == amendment["source_sha256"]
    )
    main_rows = [
        json.loads(s) for s in (OUT / "matched_results.jsonl").read_text().splitlines()
    ]
    main_keys = {r["key"] for r in main_rows}
    sampled = [r for r in raw if r["phase"] == "sample"]
    expected = {(r["task"], r["steps"]) for r in main_rows}
    assert len(expected) == len(sampled) == 282, "Finish all282 new generations first"
    assert {(r["task"], r["steps"]) for r in sampled} == expected
    originals = {
        (r["task"], r["steps"]): r for r in main_rows if r["method"] == "trigram"
    }
    for r in sampled:
        assert r["method"] == "trigram_sample" and r["base_method"] == "trigram"
        assert r["revision"] == amendment["revision"] == manifest["revision"]
        original = originals[(r["task"], r["steps"])]
        assert r["settings"] == dict(
            original["settings"], sequence_sampling=True, temperature=0.7
        )
        assert r["settings"]["remasking_strategy"] == "Bigram Viterbi"
    retained = main_rows + sampled
    zero_amendment = None
    if zero:
        zero_amendment = json.loads(
            (OUT / "confidence_zero_amendment.json").read_text()
        )
        assert (
            hashlib.sha256(
                (OUT / "pre_confidence_zero_results.jsonl").read_bytes()
            ).hexdigest()
            == zero_amendment["prior_six_method_results_sha256"]
        )
        zeros = [r for r in raw if r["phase"] == "confidence_zero"]
        assert (
            len(zeros) == 282 and {(r["task"], r["steps"]) for r in zeros} == expected
        )
        refs = {
            (r["task"], r["steps"]): r for r in main_rows if r["method"] == "confidence"
        }
        for r in zeros:
            assert r["method"] == "confidence_zero" and r["base_method"] == "confidence"
            assert r["settings"] == dict(
                refs[(r["task"], r["steps"])]["settings"], temperature=0.0
            )
            assert r["revision"] == zero_amendment["revision"] == manifest["revision"]
        retained += zeros
    total = 1974 if zero else 1692
    keys = {r["key"] for r in retained}
    assert len(keys) == len(retained) == total
    assert not (set(pending) & keys), "Finish every retained review/code check first"
    rows = [r for r in scored if r["key"] in keys]
    assert len(rows) == total
    assert all(
        sum(r["method"] == m and r["category"] == c for r in rows) == 94
        for m in METHODS
        for c in base.CATEGORIES
    )
    grades = {r["key"]: r for r in rows}
    groups = []
    for n in [None] + base.BUDGETS:
        for m in METHODS:
            subset = [
                r for r in rows if r["method"] == m and (n is None or r["steps"] == n)
            ]
            entry = dict(budget=n, method=m)
            for c in base.CATEGORIES:
                g = [r for r in subset if r["category"] == c]
                entry[c] = dict(
                    n=len(g),
                    mean_normalized=st.mean(r["normalized"] for r in g),
                    mean_grade=st.mean(r["score"] for r in g),
                )
                if c == "open":
                    entry[c]["mean_fluency"] = st.mean(r["fluency"] for r in g)
                else:
                    entry[c]["correct"] = sum(r["normalized"] for r in g)
                if c == "math":
                    entry[c]["valid_working"] = sum(r["math_worked"] for r in g)
            entry["macro_score"] = st.mean(
                entry[c]["mean_normalized"] for c in base.CATEGORIES
            )
            entry["latency_ms"] = st.mean(r["server_ms"] for r in subset)
            decoder = [
                r["decoding"]
                for r in retained
                if r["method"] == m and (n is None or r["steps"] == n) and r["decoding"]
            ]
            total_editable = sum(d["editable_predictions"] for d in decoder)
            entry["selector_ms"] = (
                st.mean(d["selector_ms"] for d in decoder) if decoder else None
            )
            entry["changed_fraction"] = (
                sum(d["changed_predictions"] for d in decoder) / total_editable
                if total_editable
                else None
            )
            groups.append(entry)
    pairs = [(m, "confidence") for m in METHODS[1:]] + [
        ("trigram", "bigram"),
        ("bigram_rep", "bigram"),
        ("trigram_rep", "trigram"),
        ("trigram_sample", "trigram"),
    ]
    if zero:
        pairs += [
            (m, "confidence_zero")
            for m in METHODS
            if m not in {"confidence", "confidence_zero"}
        ]
    contrasts = [
        base.paired_ci(rows, m, b, n, c)
        for m, b in pairs
        for n in [None] + base.BUDGETS
        for c in [None] + base.CATEGORIES
    ]
    wins = []
    lookup = {(r["task"], r["steps"], r["method"]): r for r in rows}
    for n in [None] + base.BUDGETS:
        for c in base.CATEGORIES:
            subset = [
                r
                for r in rows
                if r["method"] == "trigram_sample"
                and r["category"] == c
                and (n is None or r["steps"] == n)
            ]
            differences = [
                r["normalized"]
                - lookup[(r["task"], r["steps"], "trigram")]["normalized"]
                for r in subset
            ]
            wins.append(
                dict(
                    budget=n,
                    category=c,
                    n=len(subset),
                    improved=sum(d > 0 for d in differences),
                    tied=sum(d == 0 for d in differences),
                    worse=sum(d < 0 for d in differences),
                )
            )
    summary = dict(
        status=(
            "final_seven_method_matched_study"
            if zero
            else "final_six_method_matched_study"
        ),
        generated=len(raw),
        retained=total,
        main_retained=1410,
        sampling_generated=282,
        retained_grading_complete=True,
        excluded_main_keys=snapshot["excluded_keys"],
        sampling_amendment=amendment,
        groups=groups,
        paired_comparisons=contrasts,
        sampling_win_tie_loss=wins,
    )
    if zero:
        summary.update(
            confidence_zero_generated=282, confidence_zero_amendment=zero_amendment
        )
        if not (OUT / "PRE_CONFIDENCE_ZERO_REPORT.md").exists():
            text = (OUT / "REPORT.md").read_text()
            for image in ["quality_by_nfe.png", "latency_by_nfe.png"]:
                dest = "six_method_" + image
                (OUT / dest).write_bytes((OUT / image).read_bytes())
                text = text.replace("](" + image + ")", "](" + dest + ")")
            (OUT / "PRE_CONFIDENCE_ZERO_REPORT.md").write_text(text)
            (OUT / "pre_confidence_zero_summary.json").write_bytes(
                (OUT / "combined_summary.json").read_bytes()
            )
            (OUT / "pre_confidence_zero_scores.csv").write_bytes(
                (OUT / "combined_scores.csv").read_bytes()
            )
    for filename in ["combined_summary.json", "summary.json"]:
        (OUT / filename).write_text(json.dumps(summary, indent=2) + "\n")
    with (OUT / "combined_scores.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (OUT / "scores.csv").write_bytes((OUT / "combined_scores.csv").read_bytes())
    (OUT / "combined_results.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in retained)
    )
    # Keep the stopped main study reproducible while updating the current report.
    previous = OUT / "PRE_SAMPLING_REPORT.md"
    if not previous.exists():
        historical = (OUT / "REPORT.md").read_text()
        for image in ["quality_by_nfe.png", "latency_by_nfe.png"]:
            target = "main_" + image
            (OUT / target).write_bytes((OUT / image).read_bytes())
            historical = historical.replace("](" + image + ")", "](" + target + ")")
        previous.write_text(historical)
    base.METHODS = METHODS
    base.LABELS = LABELS
    base.write_outputs(retained, grades)
    base.plot(groups)
    write_report(manifest, groups, contrasts, wins)
    update_math_analysis(retained, grades)
    if zero:
        update_zero_math_analysis(retained, grades)
    state = json.loads((OUT / "sample/run_state.json").read_text())
    state.update(status="complete", graded=282, report_complete=True)
    (OUT / "sample/run_state.json").write_text(json.dumps(state, indent=2) + "\n")
    if zero:
        state = json.loads((OUT / "confidence_zero/run_state.json").read_text())
        state.update(status="complete", graded=282, report_complete=True)
        (OUT / "confidence_zero/run_state.json").write_text(
            json.dumps(state, indent=2) + "\n"
        )
    audit(retained, rows, manifest)
    print(
        json.dumps(
            dict(
                retained=total,
                sampling=282,
                confidence_zero=282 if zero else 0,
                all_graded=True,
                report=str(OUT / "REPORT.md"),
            ),
            indent=2,
        )
    )


def audit(raw, scored, manifest):
    assert len(raw) == len(scored) == 282 * len(METHODS)
    cases = {}
    for r in raw:
        assert hashlib.sha256(r["text"].encode()).hexdigest() == r["sha256"]
        assert r["revision"] == manifest["revision"]
        assert r["inference"]["denoising_forward_passes"] == r["steps"]
        cases.setdefault((r["task"], r["steps"]), set()).add(r["method"])
    assert len(cases) == 282 and all(v == set(METHODS) for v in cases.values())
    summaries = json.loads((OUT / "combined_summary.json").read_text())
    assert summaries["retained"] == len(raw)
    assert len(list(csv.DictReader((OUT / "combined_scores.csv").open()))) == len(raw)
    assert (OUT / "scores.csv").read_bytes() == (
        OUT / "combined_scores.csv"
    ).read_bytes()
    assert (OUT / "summary.json").read_bytes() == (
        OUT / "combined_summary.json"
    ).read_bytes()
    for filename in [
        "REPORT.md",
        "PRE_SAMPLING_REPORT.md",
        "PRE_CONFIDENCE_ZERO_REPORT.md",
    ]:
        p = OUT / filename
        if not p.exists():
            continue
        for link in re.findall(r"\]\(([^)]+)\)", p.read_text()):
            assert (OUT / link).exists(), (filename, link)
    examples = 54 * len(METHODS)
    assert (OUT / "EXAMPLES.md").read_text().count("### ") == examples
    assert (OUT / "ALL_OUTPUTS.md").read_text().count("\n## ") == len(raw)
    record = dict(
        retained=len(raw),
        matched_cases=282,
        methods=METHODS,
        cases_per_domain_method=94,
        representative_examples=examples,
        main_raw_unchanged=True,
        source_subset_unchanged=True,
        all_report_links_valid=True,
        forward_counts_match=True,
        all_graded=True,
    )
    (OUT / "analysis_audit.json").write_text(json.dumps(record, indent=2) + "\n")


def write_report(manifest, groups, contrasts, wins):
    zero = "confidence_zero" in METHODS
    lookup = {(g["budget"], g["method"]): g for g in groups}

    def get(n, m):
        return lookup[(n, m)]

    def rate(v):
        return f"{int(v['correct'])}/{v['n']} ({100*v['mean_normalized']:.1f}%)"

    def effect(b, c=None, n=None):
        v = next(
            x
            for x in contrasts
            if x["method"] == "trigram_sample"
            and x["baseline"] == b
            and x["category"] == c
            and x["budget"] == n
        )
        scale = 3 if c == "open" else 100
        unit = "grade" if c == "open" else "pp"
        return f"{scale*v['delta']:+.2f} {unit} [{scale*v['ci95'][0]:+.2f}, {scale*v['ci95'][1]:+.2f}]"

    sampled = get(None, "trigram_sample")
    det = get(None, "trigram")
    winners = {}
    for c in base.CATEGORIES:
        best = max(get(None, m)[c]["mean_normalized"] for m in METHODS)
        winners[c] = ", ".join(
            LABELS[m] for m in METHODS if get(None, m)[c]["mean_normalized"] == best
        )
    latency_change = 100 * (sampled["latency_ms"] / det["latency_ms"] - 1)
    out = [
        f"# LLaDA decoding study — {'seven' if zero else 'six'} matched configurations",
        "",
        (
            f"**{1974 if zero else 1692:,} graded outputs: 282 matched prompt/NFE cases × {'seven' if zero else 'six'} configurations.** "
        )
        + "The original stopped study contributes 1,410 outputs; the user-requested sampled "
        "bigram + trigram configuration adds 282. "
        + ("Temperature-zero confidence adds another 282. " if zero else "")
        + "Three original outputs from one incomplete "
        "comparison remain excluded. Every method uses precisely the same cases.",
        "",
        "## Added configuration",
        "",
        "**BG + TG sampled** uses Sample bigram-guided sequences ON, temperature **0.7**, "
        "and **no repetition penalty**. All other request settings, prompts, seeds, NFE budgets "
        "and the Space revision match the deterministic BG + TG counterpart. This samples "
        "from the existing joint diffusion-plus-n-gram sequence distribution; it is not "
        "independent token sampling or random perturbation of logits. One excluded warm-up "
        "request used the same sampled decoding path.",
        "",
        "This replaces the earlier cancelled plan for a 720-run selected follow-up. The new "
        "282-run arm was chosen by the user after viewing the main results, so the comparison "
        "is exploratory. The earlier 1,800-run main study was not resumed.",
        "",
        "## Findings",
        "",
        f"- The highest observed pooled open-ended quality belongs to **{winners['open']}**; "
        f"coding pass rate to **{winners['code']}**; math final-answer accuracy to **{winners['math']}**.",
        f"- Sampling changes open quality by **{sampled['open']['mean_grade']-det['open']['mean_grade']:+.3f}/3**, "
        f"coding successes by **{int(sampled['code']['correct']-det['code']['correct']):+d}/94**, and math successes "
        f"by **{int(sampled['math']['correct']-det['math']['correct']):+d}/94**, relative to deterministic BG + TG.",
        f"- Sampled sequence decoding has **{latency_change:+.1f}%** measured pooled server latency "
        "relative to deterministic BG + TG. These runs were performed later, so hardware/service variation may contribute.",
        "- Use the NFE tables and paired intervals below to assess the trade-offs. Pooled rankings "
        "alone can hide opposite low- and high-budget effects, especially in math.",
        "",
        "In the comparison with sequence sampling, **deterministic BG + TG performs better overall in this fixed-seed study**: "
        "sampling has lower observed open-ended quality, four fewer coding successes and "
        "the same number of correct final math answers, with higher measured inference time. "
        "Math answers with valid working also fall from 32/94 to 27/94. This does not measure "
        "whether sampling is preferable when answer variety is the objective, nor its performance "
        "over multiple seeds.",
        "",
        "## Overall metrics",
        "",
        base.table(
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
        "Each domain has 94 prompt/NFE cases per configuration, drawn from 20 distinct prompts "
        "(60 prompts total). These are not 94 independent prompts: a prompt is repeated "
        "across available NFE budgets. Open quality combines coherence, relevance, grammar, "
        "repetition and substantive factual accuracy; fluency is scored separately. Coding "
        "requires all independent tests and explicit constraints to pass. Math final accuracy "
        "requires all requested answers; correct working additionally rejects invalid or "
        "contradictory equations and missing requested explanation.",
        "",
        "## What sequence sampling changes",
        "",
        base.table(
            [
                "Sampled BG + TG versus",
                "Open quality change [95% CI]",
                "Coding change [95% CI]",
                "Math change [95% CI]",
            ],
            [
                [LABELS[b]] + [effect(b, c) for c in base.CATEGORIES]
                for b in ["trigram", "confidence"]
            ],
        ),
        "",
        base.table(
            ["Domain", "Improved vs deterministic BG + TG", "Tied", "Worse"],
            [
                [c]
                + [
                    next(
                        w[k] for w in wins if w["budget"] is None and w["category"] == c
                    )
                    for k in ["improved", "tied", "worse"]
                ]
                for c in base.CATEGORIES
            ],
        ),
        "",
        "Improvement/tie/worse uses the reported open quality grade and binary coding/math "
        "correctness. It does not imply that tied texts are identical. The same seed is "
        "matched across requests; only one generation was run per prompt/NFE/configuration. "
        "This evaluates the sampled configuration, not its across-seed variance.",
        "",
        "## Results by NFE",
        "",
        "![Quality by NFE](quality_by_nfe.png)",
        "",
        base.table(
            ["NFE", "Open cases/method", "Coding cases/method", "Math cases/method"],
            [
                [n] + [get(n, "confidence")[c]["n"] for c in base.CATEGORIES]
                for n in base.BUDGETS
            ],
        ),
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
                base.table(
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
                        for n in base.BUDGETS
                    ],
                ),
                "",
            ]
        )
    out.extend(
        [
            "### Sampled versus deterministic BG + TG: paired effects",
            "",
            base.table(
                [
                    "NFE",
                    "Open quality change [95% CI]",
                    "Coding change [95% CI]",
                    "Math change [95% CI]",
                ],
                [
                    [n] + [effect("trigram", c, n) for c in base.CATEGORIES]
                    for n in base.BUDGETS
                ],
            ),
            "",
            "See the [high-NFE math audit](HIGH_NFE_MATH_ANALYSIS.md) for exact comparisons "
            "on the arithmetic failures discussed after the original study, now including sampled outputs. "
            "At 128 NFE the sampled answer repairs the mean problem, reaching 10/15 math successes "
            "versus deterministic 9/15 and confidence 12/15. At 64 NFE it stays at 9/16 versus "
            "confidence 12/16. Sampling therefore reduces one observed high-budget failure without "
            "closing the gap.",
            "",
            "## Latency and prediction changes",
            "",
            "![Latency by NFE](latency_by_nfe.png)",
            "",
            base.table(
                ["NFE"] + [LABELS[m] + " (ms)" for m in METHODS],
                [
                    [n] + [f"{get(n,m)['latency_ms']:.0f}" for m in METHODS]
                    for n in base.BUDGETS
                ],
            ),
            "",
            base.table(
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
            "Latency is measured server generation time, excluding queue/network overhead. Sampling "
            "runs were executed later than the deterministic runs on shared Hugging Face hardware, "
            "so latency differences include possible service variation. No added model forwards "
            "were used: every retained request has exactly the requested NFE and selector-call "
            "count. The changed fraction aggregates editable predictions across all iterations "
            "relative to the current diffusion argmax; it is not final text disagreement across runs.",
            "",
            "## Settings and grading",
            "",
            "- Model: `GSAI-ML/LLaDA-8B-Instruct`; Space: `Ruurd/llada-8b-instruct`.",
            f"- Space revision: `{manifest['revision']}`.",
            "- Max output/block 128; NFE 4, 8, 16, 32, 64, 128; seed 42; top-k/candidates 16.",
            "- Bigram weight 1; trigram relative weight 0.5; PMI count minimum 1 and clip ±2; trigram minimum 2 and clip ±2.",
            (
                "- Temperature 0.7 except the explicit Confidence T=0 arm. Confidence T=0.7 independently samples; deterministic Viterbi ignores temperature; sampled BG + TG samples the joint sequence distribution at 0.7."
                if zero
                else "- Temperature 0.7. Confidence independently samples; deterministic Viterbi ignores temperature; sampled BG + TG samples the joint sequence distribution at 0.7."
            ),
            "- Repetition OFF for sampled BG + TG and the confidence arms. Existing R arms retain strength 1 and the absolute six-step fade.",
            "- Open-ended: EOS/EOT retention delay ON, ending strength 10. Coding/math: both OFF (neutral strength 1).",
            "- APD OFF; early stopping OFF; revisable tokens OFF; count-every-candidate OFF; risk alternative OFF.",
            "- Diffusion-probability remasking throughout; no training or production inference changes.",
            "",
            "Open/math answers were inspected by the assistant with configuration/NFE labels hidden. "
            "Existing judgments were reused only for exact matching text within the same prompt. "
            "Each follow-up adds one arm, so omitting labels from its review packets is not full blinding. "
            "The coding checker uses the original independent edge tests in isolated restricted "
            "workers; correct reference implementations pass all 199 tests and fit 128 tokens. "
            "This is assistant review, not independent human or multi-rater evaluation.",
            "",
            "## Interpretation limits",
            "",
            "- Bootstrap intervals use 4,000 paired replicates, resampling prompts within domains "
            "while preserving each prompt’s observed NFE vector. Ratio-of-sums estimates retain "
            "case weighting under incomplete NFE coverage. Intervals are exploratory and unadjusted "
            "for multiple comparisons, optional stopping, or selecting the sampled configuration "
            "after seeing the main study. Zero-width paired intervals occur when every observed "
            "pair ties; these reflect the empirical bootstrap and do not demonstrate equivalence "
            "on new prompts.",
            "- The main-study development/validation split is preserved, but this full-set comparison "
            "is not a held-out confirmation. Twenty prompts per domain and one seed do not establish "
            "global optimality or sampling reliability.",
            "- Different NFE rows contain slightly different prompt subsets. Methods within a row "
            "are exactly paired; cross-budget comparisons need caution.",
            "- Open-ended comparisons include ending-delay differences: guided decoding additionally "
            "uses the ending-logit penalty, while confidence uses retention delay. This confound "
            "does not apply to coding/math.",
            "- The 128-token cap can truncate otherwise promising solutions. A missing required "
            "answer counts as unsolved. Coding tasks are short functions, and math tasks are small "
            "arithmetic/algebra problems.",
            "",
            "## Files",
            "",
            "- [All current configurations: raw outputs](combined_results.jsonl), [scores CSV](combined_scores.csv), [summary and paired bootstrap results](combined_summary.json).",
            "- [Every retained output with its judgment](ALL_OUTPUTS.md); [best, middle and worst examples by configuration/NFE/domain](EXAMPLES.md).",
            "- [Original five-method report](PRE_SAMPLING_REPORT.md); [high-NFE math audit](HIGH_NFE_MATH_ANALYSIS.md).",
            "- [Sampling timing discussion: existing measurements and implementation deductions](TIMING_NOTES.md). No new timing benchmark or sampling optimization was performed for that discussion.",
            "- [Original manifest](manifest.json), [protocol and amendment](PROTOCOL.md), [sampling amendment](sampling_amendment.json), [original stop snapshot](stop_snapshot.json).",
            "- [Original retained outputs](matched_results.jsonl), [original scores](matched_scores.csv), [original main summary](matched_summary.json), [new sampled outputs](sample/results.jsonl).",
            "- [Manual judgments](reviews.json), [coding checks](code_checks.json), [reference validation](reference_validation.json).",
            "",
            "The original raw files and stop snapshot remain immutable historical records. "
            "`summary.json` and `scores.csv` now mirror the current matched analysis.",
            "",
        ]
    )
    if zero:
        z = get(None, "confidence_zero")
        old = get(None, "confidence")

        def z_effect(m, b, c, n=None):
            v = next(
                x
                for x in contrasts
                if x["method"] == m
                and x["baseline"] == b
                and x["category"] == c
                and x["budget"] == n
            )
            scale = 3 if c == "open" else 100
            unit = "grade" if c == "open" else "pp"
            return f"{scale*v['delta']:+.2f} {unit} [{scale*v['ci95'][0]:+.2f}, {scale*v['ci95'][1]:+.2f}]"

        section = [
            "## Temperature-zero confidence comparison",
            "",
            "After the sampled BG + TG run and its six-configuration report were completed, "
            "the user requested **Confidence T=0** on the identical 282 cases. Only temperature "
            "changes from the original confidence request: 0.7 → 0. All other settings, including "
            "top-k 16, seed 42, prompt/NFE, ending controls and model revision, are preserved. "
            "At temperature zero the independent selector uses argmax; top-k does not introduce "
            "randomness. There is no Viterbi or repetition penalty in this new baseline. "
            "One warm-up request is excluded.",
            "",
            f"Relative to Confidence T=0.7, T=0 changes pooled open quality by "
            f"**{z['open']['mean_grade']-old['open']['mean_grade']:+.3f}/3**, coding successes by "
            f"**{int(z['code']['correct']-old['code']['correct']):+d}/94**, and math successes by "
            f"**{int(z['math']['correct']-old['math']['correct']):+d}/94**. These are observations "
            "from one matched fixed-seed run, not evidence of a globally optimal temperature.",
            "",
            base.table(
                [
                    "Comparison",
                    "Open quality change [95% CI]",
                    "Coding change [95% CI]",
                    "Math change [95% CI]",
                ],
                [
                    [f"{LABELS[m]} vs {LABELS[b]}"]
                    + [z_effect(m, b, c) for c in base.CATEGORIES]
                    for m, b in [
                        ("confidence_zero", "confidence"),
                        ("trigram", "confidence_zero"),
                        ("trigram_sample", "confidence_zero"),
                    ]
                ],
            ),
            "",
            "### Deterministic BG + TG versus Confidence T=0, by NFE",
            "",
            base.table(
                [
                    "NFE",
                    "Open quality change [95% CI]",
                    "Coding change [95% CI]",
                    "Math change [95% CI]",
                ],
                [
                    [n]
                    + [
                        z_effect("trigram", "confidence_zero", c, n)
                        for c in base.CATEGORIES
                    ]
                    for n in base.BUDGETS
                ],
            ),
            "",
            "This comparison removes the independent-token sampling difference between the "
            "original confidence baseline and deterministic Viterbi. Their denoising trajectories "
            "can still diverge as committed tokens change the model context. Open-ended comparisons "
            "retain the existing ending-control package difference.",
            "",
            "In coding, Confidence T=0 ties deterministic BG + TG at NFE 64 and128, and scores "
            "one more success at32. BG + TG retains the observed advantage at8 NFE (7/16 "
            "versus4/16) and16 NFE (8/16 versus7/16). Thus much of the earlier high-budget "
            "coding advantage over confidence is explained by its sampling temperature. "
            "Open-ended BG + TG still scores higher overall. On math, changing the baseline "
            "to T=0 removes the observed 64-NFE accuracy gap because both methods score9/16 "
            "(Confidence T=0.7 scores12/16). A128-NFE gap remains: Confidence T=0 scores11/15 "
            "and deterministic BG + TG scores9/15.",
            "",
            "The [completed six-configuration report](PRE_CONFIDENCE_ZERO_REPORT.md) is preserved. "
            "The [confidence-zero amendment](confidence_zero_amendment.json) records the frozen "
            "source and prior-result hashes; [new raw outputs](confidence_zero/results.jsonl) "
            "remain separate from both earlier generation phases.",
            "",
        ]
        index = out.index("## Overall metrics")
        out[index:index] = section
        index = out.index("## Added configuration") + 2
        out[index:index] = [
            "The experiment now includes two follow-up configurations: sampled BG + TG "
            "and temperature-zero confidence. The sampled run and report were finished first.",
            "",
        ]
    (OUT / "REPORT.md").write_text("\n".join(out))


def update_math_analysis(raw, grades):
    path = OUT / "HIGH_NFE_MATH_ANALYSIS.md"
    text = path.read_text().split("\n## Added sequence-sampling comparison")[0]
    lookup = {(r["task"], r["steps"], r["method"]): r for r in raw}
    lines = [
        "",
        "## Added sequence-sampling comparison",
        "",
        "Same retained cases, BG + TG without repetition, sequence sampling ON at temperature0.7. "
        "These answers were generated after the original audit.",
        "",
        base.table(
            [
                "NFE",
                "Confidence correct",
                "Deterministic BG + TG correct",
                "Sampled BG + TG correct",
            ],
            [
                [n]
                + [
                    f"{sum(grades[r['key']]['normalized'] for r in raw if r['method']==m and r['category']=='math' and r['steps']==n):.0f}/"
                    f"{sum(r['method']==m and r['category']=='math' and r['steps']==n for r in raw)}"
                    for m in ["confidence", "trigram", "trigram_sample"]
                ]
                for n in [64, 128]
            ],
        ),
        "",
    ]
    for n in [64, 128]:
        for r in sorted(raw, key=lambda r: r["task"]):
            if (
                r["method"] != "trigram_sample"
                or r["category"] != "math"
                or r["steps"] != n
            ):
                continue
            original = lookup[(r["task"], n, "trigram")]
            baseline = lookup[(r["task"], n, "confidence")]
            if (
                grades[baseline["key"]]["normalized"]
                == grades[original["key"]]["normalized"]
                == grades[r["key"]]["normalized"]
            ):
                continue
            g = grades[r["key"]]
            lines.extend(
                [
                    f"### NFE {n}: {r['task']} — sampled output",
                    "",
                    f"**Grade:** {g['score']}. {g['note']}",
                    "",
                    "````text",
                    r["text"],
                    "````",
                    "",
                ]
            )
    path.write_text(text + "\n" + "\n".join(lines))


def update_zero_math_analysis(raw, grades):
    path = OUT / "HIGH_NFE_MATH_ANALYSIS.md"
    text = path.read_text().split("\n## Added temperature-zero confidence comparison")[
        0
    ]
    selected = ["confidence", "confidence_zero", "trigram", "trigram_sample"]
    lines = [
        "",
        "## Added temperature-zero confidence comparison",
        "",
        "A further matched independent argmax baseline, temperature0, was run after the sampled arm and its report completed.",
        "",
        base.table(
            ["NFE"] + [LABELS[m] for m in selected],
            [
                [n]
                + [
                    f"{sum(grades[r['key']]['normalized'] for r in raw if r['method']==m and r['category']=='math' and r['steps']==n):.0f}/"
                    f"{sum(r['method']==m and r['category']=='math' and r['steps']==n for r in raw)}"
                    for m in selected
                ]
                for n in [64, 128]
            ],
        ),
        "",
    ]
    for r in sorted(raw, key=lambda r: (r["steps"], r["task"])):
        if (
            r["method"] == "confidence_zero"
            and r["category"] == "math"
            and r["steps"] in [64, 128]
        ):
            g = grades[r["key"]]
            lines.extend(
                [
                    f"### NFE {r['steps']}: {r['task']} — Confidence T=0",
                    "",
                    f"**Grade:** {g['score']}. {g['note']}",
                    "",
                    "````text",
                    r["text"],
                    "````",
                    "",
                ]
            )
    path.write_text(text + "\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
