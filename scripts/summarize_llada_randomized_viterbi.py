#!/usr/bin/env python3
"""Matched progress/final summaries without rewriting the seven-arm study."""

import argparse, csv, hashlib, json, statistics as st
from review_llada_randomized_viterbi import OUT, STUDY, base, read, rid, reviews
from finalize_llada_full_study import paired_ci, table
from evaluate_llada_randomized_viterbi import historical

METHODS = [
    "confidence",
    "confidence_zero",
    "bigram",
    "bigram_rep",
    "trigram",
    "trigram_rep",
    "trigram_sample",
    "trigram_randomized",
]
LABELS = dict(
    zip(
        METHODS,
        [
            "Confidence T=.7",
            "Confidence T=0",
            "BG",
            "BG + R",
            "BG + TG",
            "BG + TG + R",
            "BG + TG exact sampling .7",
            "BG + TG randomized .7",
        ],
    )
)
BUDGETS = [4, 8, 16, 32, 64, 128]
CATS = ["open", "code", "math"]


def collect():
    raw = read(OUT / "results.jsonl")
    judged = reviews()
    p = OUT / "code_checks.json"
    checks = json.loads(p.read_text()) if p.exists() else {}
    new = []
    pending = []
    for row in raw:
        q = (
            checks.get(row["key"])
            if row["category"] == "code"
            else judged.get(rid(row))
        )
        if q is None or q.get("score") is None:
            pending.append(row["key"])
            continue
        assert q["sha256"] == row["sha256"]
        normalized = (
            q["score"] / 3
            if row["category"] == "open"
            else (
                float(q["all_pass"])
                if row["category"] == "code"
                else float(q["answer_correct"])
            )
        )
        new.append(
            dict(
                key=row["key"],
                task=row["task"],
                steps=row["steps"],
                category=row["category"],
                method=row["method"],
                score=q["score"],
                normalized=normalized,
                fluency=q.get("fluency"),
                math_worked=q.get("worked_correct"),
                server_ms=row["inference"]["elapsed_ms"],
                sha256=row["sha256"],
                note=q.get("note", q.get("status", "")),
            )
        )
    with historical("combined_scores.csv").open() as f:
        old = list(csv.DictReader(f))
    for row in old:
        for k in ["steps", "score"]:
            row[k] = int(row[k])
        for k in ["normalized", "server_ms"]:
            row[k] = float(row[k])
        if row["fluency"] != "":
            row["fluency"] = int(row["fluency"])
    keys = {(r["task"], r["steps"]) for r in new}
    matched = [r for r in old if (r["task"], r["steps"]) in keys] + new
    return raw, new, matched, pending


def groups(rows):
    result = []
    for n in [None] + BUDGETS:
        for m in METHODS:
            subset = [
                r for r in rows if r["method"] == m and (n is None or r["steps"] == n)
            ]
            if not subset:
                continue
            g = dict(
                budget=n,
                method=m,
                n=len(subset),
                latency_ms=st.mean(r["server_ms"] for r in subset),
            )
            for c in CATS:
                a = [r for r in subset if r["category"] == c]
                if a:
                    g[c] = dict(
                        n=len(a),
                        mean_grade=st.mean(r["score"] for r in a),
                        mean_normalized=st.mean(r["normalized"] for r in a),
                        correct=(
                            sum(r["normalized"] for r in a) if c != "open" else None
                        ),
                    )
            if all(c in g for c in CATS):
                g["macro_score"] = st.mean(g[c]["mean_normalized"] for c in CATS)
            result.append(g)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--final", action="store_true")
    args = p.parse_args()
    raw, new, matched, pending = collect()
    gs = groups(matched)
    summary = dict(
        status="complete" if args.final else "partial",
        generated=len(raw),
        target=282,
        graded=len(new),
        pending=len(pending),
        category_generated={c: sum(r["category"] == c for r in raw) for c in CATS},
        groups=gs,
    )
    (OUT / "progress.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "groups"}))
    for g in gs:
        if g["budget"] is None and g["method"] in [
            "confidence",
            "trigram",
            "trigram_sample",
            "trigram_randomized",
        ]:
            print(json.dumps(g))
    if not args.final:
        return
    amendment = json.loads((OUT / "amendment.json").read_text())
    assert len(raw) == len(new) == 282 and not pending
    assert len(matched) == 2256 and len({r["key"] for r in matched}) == 2256
    assert (
        hashlib.sha256(historical("combined_results.jsonl").read_bytes()).hexdigest()
        == amendment["comparison_sha256"]
    )
    source = {
        (r["task"], r["steps"]): r
        for r in read(STUDY / "matched_results.jsonl")
        if r["method"] == "trigram"
    }
    for r in raw:
        assert r["revision"] == amendment["revision"]
        assert r["settings"] == dict(
            source[(r["task"], r["steps"])]["settings"],
            randomized_viterbi=True,
            sequence_sampling=False,
            temperature=0.7,
        )
        assert (
            r["inference"]["denoising_forward_passes"]
            == r["decoding"]["selector_calls"]
            == r["steps"]
        )
    for m in METHODS:
        assert all(
            sum(r["method"] == m and r["category"] == c for r in matched) == 94
            for c in CATS
        )
    contrasts = [
        paired_ci(matched, "trigram_randomized", b, n, c)
        for b in ["confidence", "trigram", "trigram_sample"]
        for n in [None] + BUDGETS
        for c in [None] + CATS
    ]
    summary.update(contrasts=contrasts, amendment=amendment)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    fields = [
        "key",
        "task",
        "category",
        "steps",
        "method",
        "score",
        "normalized",
        "server_ms",
        "sha256",
        "note",
    ]
    with (OUT / "combined_scores.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(matched)
    oldraw = read(historical("combined_results.jsonl"))
    with (OUT / "combined_results.jsonl").open("w") as f:
        for r in oldraw + raw:
            f.write(json.dumps(r) + "\n")
    lookup = {(g["budget"], g["method"]): g for g in gs}
    text = [
        "# Randomized BG+TG Viterbi: matched study extension",
        "",
        "Adds one configuration to all 282 previously retained prompt/NFE cases (94 each open, coding and math). The seven historical arms are frozen; the combined eight-arm archive has 2,256 outputs. NFE 4, 8, 16, 32, 64, 128; max/block length 128; top-k 16; bigram weight 1; trigram relative weight .5; PMI count≥1/clip±2; trigram count≥2/clip±2; seed 42; no repetition penalty/APD/early stopping. Open answers delay EOS/EOT with strength 10; coding/math do not. All other settings copy the original BG+TG cases exactly.",
        "",
        "## What temperature .7 means",
        "",
        "Each denoising iteration adds independent unit Gumbel noise multiplied by .7 to editable candidate unary log-scores. Then the existing optimized deterministic Viterbi decoder selects a path with unchanged BG/TG transitions. Fixed tokens and candidate support remain unchanged; confidence uses original diffusion probabilities. Noise is redrawn each iteration, using the existing seeded RNG. During the experiment this was an explicit option, default OFF. The current LLaDA interface now uses it as standard temperature behavior; temperature 0 consumes no extra random numbers and reproduces deterministic decoding. Exact sequence sampling and randomized Viterbi are mutually exclusive.",
        "",
        "**This is approximate perturb-and-MAP, not exact sampling from exp(S/.7).** A noise scale of .7 does not guarantee the same entropy or distribution as the exact .7 sampler. This study tests usefulness of that explicit setting. One seed per case cannot establish the full output distribution or optimal noise strength.",
        "",
        "## Overall results",
        "",
        table(
            [
                "Method",
                "Open quality /3",
                "Coding passes /94",
                "Math correct /94",
                "Macro score",
            ],
            [
                [
                    LABELS[m],
                    f"{lookup[None,m]['open']['mean_grade']:.3f}",
                    int(lookup[None, m]["code"]["correct"]),
                    int(lookup[None, m]["math"]["correct"]),
                    f"{lookup[None,m]['macro_score']:.3f}",
                ]
                for m in METHODS
            ],
        ),
        "",
    ]
    for c, title in [
        ("open", "Open quality /3"),
        ("code", "Coding correct"),
        ("math", "Math correct"),
    ]:
        selected = [
            "confidence",
            "confidence_zero",
            "trigram",
            "trigram_sample",
            "trigram_randomized",
        ]
        text += [
            "## " + title,
            "",
            table(
                ["NFE", "Cases"] + [LABELS[m] for m in selected],
                [
                    [n, lookup[n, "trigram"][c]["n"]]
                    + [
                        (
                            f"{lookup[n,m][c]['mean_grade']:.2f}"
                            if c == "open"
                            else f"{int(lookup[n,m][c]['correct'])}/{lookup[n,m][c]['n']}"
                        )
                        for m in selected
                    ]
                    for n in BUDGETS
                ],
            ),
            "",
        ]
    scores = {(r["task"], r["steps"], r["method"]): r for r in matched}
    flips = []
    for r in new:
        if r["category"] != "math":
            continue
        ref = scores[r["task"], r["steps"], "trigram_sample"]
        if ref["normalized"] != r["normalized"]:
            flips.append(
                dict(
                    task=r["task"],
                    nfe=r["steps"],
                    exact_correct=bool(ref["normalized"]),
                    randomized_correct=bool(r["normalized"]),
                )
            )
    summary["math_flips_vs_exact"] = flips
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    text += [
        "## Interpreting the math difference",
        "",
        "The exact sampler got 52/94 math answers correct, versus45/94 for randomized Viterbi: 10 cases changed from correct to incorrect, while3 changed from incorrect to correct. Some losses retain a correct setup and then choose a wrong digit/result (for example fraction_equation at NFE16 reaches5x=30 but answersx=-1; mean at NFE128 subtracts70-48 as20). Other losses are malformed low-NFE output or contradictory final answers. These are observed error patterns, not proof of a specific causal mechanism.",
        "",
        "The .7 scale was a principled starting point from independent categorical Gumbel-max sampling, **not an empirically calibrated equivalence to the coupled sampler**. The exact sampler uses exp(S/.7); this method maximizes S+.7*sum(token-Gumbels). Overlapping sequences share token noises, so their perturbations are correlated and have a different distribution from independent sequence-level Gumbels. BG/TG tables are computed first; only unary token log-scores receive additive noise immediately before MAP. No transition probabilities or retention probabilities are perturbed.",
        "",
        "A lower noise scale might reduce disruptive math changes, but this run cannot establish that .7 overshot, nor identify an equivalent exact-sampler temperature. Approximation bias and single-seed variation are alternative explanations. No noise-strength sweep was performed.",
        "",
        table(
            ["Task", "NFE", "Exact sampler correct", "Randomized correct"],
            [
                [x["task"], x["nfe"], x["exact_correct"], x["randomized_correct"]]
                for x in flips
            ],
        ),
        "",
    ]
    text += [
        "## Paired uncertainty",
        "",
        "Exploratory post-hoc comparisons on the same cases, using the existing prompt-cluster bootstrap (4,000 repeats). Repeated NFEs for a prompt stay in one cluster; missing cases remain matched. Intervals do not account for method selection after inspecting earlier results or manual grading uncertainty. Macro averages open grade/3, coding pass fraction and math answer-correct fraction equally.",
        "",
        table(
            ["Randomized minus", "Macro delta [95% CI]"],
            [
                [
                    LABELS[b],
                    next(
                        f"{q['delta']:+.3f} [{q['ci95'][0]:+.3f}, {q['ci95'][1]:+.3f}]"
                        for q in contrasts
                        if q["baseline"] == b
                        and q["budget"] is None
                        and q["category"] is None
                    ),
                ]
                for b in ["confidence", "trigram", "trigram_sample"]
            ],
        ),
        "",
        "## Timing",
        "",
        "The randomized arm uses the optimized CPU MAP implementation. Historical deterministic/exact-sampler timings were collected before that optimization, at different times on shared ZeroGPU hardware. They are retained below for context, not a controlled measurement of randomization overhead. No additional model forwards are used.",
        "",
        table(
            [
                "NFE",
                "Historical BG+TG ms",
                "Historical exact sample ms",
                "Randomized BG+TG ms",
                "Randomized selector ms",
            ],
            [
                [
                    n,
                    round(lookup[n, "trigram"]["latency_ms"]),
                    round(lookup[n, "trigram_sample"]["latency_ms"]),
                    round(lookup[n, "trigram_randomized"]["latency_ms"]),
                    round(
                        st.mean(
                            r["decoding"]["selector_ms"] for r in raw if r["steps"] == n
                        )
                    ),
                ]
                for n in BUDGETS
            ],
        ),
        "",
    ]
    fast = read(STUDY.parent / "llada_ngram_speed/after_host_k16.jsonl")
    fast = [r for r in fast if r["trial"] == 0]
    random_lookup = {(r["task"], r["steps"]): r for r in raw}
    fast = [r for r in fast if (r["task"], r["steps"]) in random_lookup]
    if fast:
        det = st.mean(r["inference"]["elapsed_ms"] for r in fast)
        rnd = st.mean(
            random_lookup[r["task"], r["steps"]]["inference"]["elapsed_ms"]
            for r in fast
        )
        text += [
            f"On the {len(fast)} cases overlapping the saved **optimized** K16 timing screen, deterministic generation averaged {det:.1f} ms and randomized generation {rnd:.1f} ms ({100*(rnd/det-1):+.1f}%). These also ran at different times; small differences should not be attributed to noise generation alone.",
            "",
        ]
    text += [
        "## Validation and artifacts",
        "",
        "Local implementation checks: 143 passed, six CUDA cases skipped on this CPU workstation. Checks include Gumbel transform/endpoints, seeded reproducibility and variation, zero-temperature equivalence without RNG consumption, fixed tokens, unperturbed confidence, and existing trigram/sampling/shared-control behavior. Hosted logs verify requested NFE and selector counts and complete outputs for every case.",
        "",
        "Manual open/math reviews reuse the original rubric and exact-text judgments; new texts were shown without method/NFE labels. Math score 2 means correct answer but faulty/incomplete explanation; score 3 also requires correct working. Code uses the existing restricted executable tests. `reviews.json`, `code_checks.json`, `results.jsonl`, `combined_scores.csv`, `summary.json` and `EXAMPLES.md` preserve outputs and evidence.",
        "",
        f"Space revision: `{amendment['revision']}`. Only app.py and bigram.py changed; optimized trigram.py, model configuration and weights were retained. Deployment/source hashes and before/after diffs are saved beside this report. No conclusion here establishes general superiority beyond these prompts/settings.",
        "",
    ]
    conclusion = [
        "## Findings",
        "",
        "At noise scale .7, randomized Viterbi achieves almost the same aggregate score as exact sampling (0.543 versus0.544), with higher open quality (1.915 versus1.798), more coding passes (48 versus45), and fewer correct math answers (45 versus52). Deterministic BG+TG remains descriptively ahead overall (0.576). Paired uncertainty intervals overlap zero versus both BG+TG alternatives, so these data do not establish superiority or equivalence.",
        "",
        "The fast recurrence is retained, with no clear additional total-time cost in the saved optimized comparison. The user adopted Gumbel Viterbi as standard temperature behavior to provide fast variation. This interface decision does not establish a quality improvement over deterministic decoding. Temperature 0 remains deterministic. To reproduce this arm: expanded BG+TG, exact sequence sampling OFF, temperature .7, all other settings as above; API evaluations can explicitly set randomized_viterbi=True.",
        "",
    ]
    if (OUT / "diversity_summary.json").exists():
        diversity = json.loads((OUT / "diversity_summary.json").read_text())
        summary["seed_check"] = diversity
        text += [
            "## Seed-variation check",
            "",
            "A separate check used seeds42,43,44 at NFE32 for the machine-learning explanation and Fibonacci coding task. Both produced three distinct text outputs. Seed42 is from the main study; the four extra runs are saved in diversity.jsonl and excluded from every main quality/timing metric. This demonstrates variation on these two prompts, not distributional equivalence or diverse-code correctness.",
            "",
        ]
        (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    pos = text.index("## What temperature .7 means")
    text[pos:pos] = conclusion
    (OUT / "REPORT.md").write_text("\n".join(text))
    # Examples are relative within each category/budget, not promises of quality.
    docs = [
        "# Representative randomized Viterbi outputs",
        "",
        "For each NFE/domain: highest, middle and lowest grade in that pool, tie-broken by task ID. Labels are relative; pools can have ties or no correct outputs. One seed per case.",
        "",
    ]
    score = {r["key"]: r for r in new}
    for n in BUDGETS:
        for c in CATS:
            pool = sorted(
                [r for r in raw if r["steps"] == n and r["category"] == c],
                key=lambda r: (
                    score[r["key"]]["normalized"],
                    score[r["key"]]["score"],
                    r["task"],
                ),
            )
            for label, r in [
                ("Good", pool[-1]),
                ("Average", pool[len(pool) // 2]),
                ("Bad", pool[0]),
            ]:
                q = score[r["key"]]
                docs += [
                    f"## NFE {n} · {c} · {label} (relative)",
                    "",
                    f"**Prompt:** {r['prompt']}",
                    "",
                    f"**Grade:** {q['score']}/3. {q['note']}",
                    "",
                    r["text"],
                    "",
                ]
    (OUT / "EXAMPLES.md").write_text("\n".join(docs))


if __name__ == "__main__":
    main()
