"""Build the final internal before/after report from preserved per-item results.

No generation, network calls, or execution of generated programs. Tests of
old/new item cohorts are diagnostic exchangeability checks, not causal tests.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
EVAL = HERE.parent / "evaluation"
TASKS = ["arc_c", "gpqa", "hellaswag", "mmlu", "mmlu_pro", "gsm8k", "math", "mbpp", "humaneval"]
LABELS = {"arc_c": "ARC-Challenge", "gpqa": "GPQA-Main", "hellaswag": "HellaSwag",
          "mmlu": "MMLU", "mmlu_pro": "MMLU-Pro", "gsm8k": "GSM8K", "math": "MATH-500",
          "mbpp": "MBPP sanitized", "humaneval": "HumanEval"}
MODELS = {"gemma_d": "BYOD-Gemma", "gemma_ar": "Gemma AR", "llada": "LLaDA",
          "qwen_d": "BYOD-Qwen", "qwen_ar": "Qwen AR", "ministral_d": "BYOD-Ministral",
          "ministral_ar": "Ministral AR", "llama_25k": "BYOD-Llama 25k",
          "llama_50k": "BYOD-Llama 50k", "llama_ar": "Llama AR"}


def load_rows(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def logcomb(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher(k1, n1, k2, n2):
    """Two-sided Fisher exact p: sum tables no more likely than observed."""
    successes, total = k1 + k2, n1 + n2
    def logpmf(k):
        return logcomb(successes, k) + logcomb(total-successes, n1-k) - logcomb(total, n1)
    observed = logpmf(k1)
    support = range(max(0, n1-(total-successes)), min(n1, successes)+1)
    return min(1.0, sum(math.exp(logpmf(k)) for k in support if logpmf(k) <= observed + 1e-10))


def mcnemar(gains, losses):
    discordant = gains + losses
    if not discordant:
        return 1.0
    return min(1.0, 2 * sum(math.exp(logcomb(discordant, k) - discordant*math.log(2))
                           for k in range(min(gains, losses)+1)))


def holm(rows, field="p", out="holm_p"):
    adjusted = 0.0
    for i, row in enumerate(sorted(rows, key=lambda r: r[field])):
        adjusted = max(adjusted, min(1.0, row[field]*(len(rows)-i)))
        row[out] = adjusted


def wilson(k, n):
    z = 1.959963984540054
    p = k/n
    denominator = 1+z*z/n
    center = (p+z*z/(2*n))/denominator
    radius = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
    return center-radius, center+radius


def difference_interval(k1, n1, k2, n2):
    """Newcombe-Wilson interval for added minus initial proportions."""
    p1, p2 = k1/n1, k2/n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    return [100*((p2-p1)-math.sqrt((p2-l2)**2+(u1-p1)**2)),
            100*((p2-p1)+math.sqrt((u2-p2)**2+(p1-l1)**2))]


def stat(rows, field="correct"):
    k = sum(bool(row[field]) for row in rows)
    return {"k": k, "n": len(rows), "pct": 100*k/len(rows)}


def count_text(s):
    return f"{s['k']}/{s['n']} ({s['pct']:.1f}%)"


def ptext(value):
    return f"{value:.2g}" if value < .001 else f"{value:.4f}"


def signed(value):
    return f"{value:+.2f}"


def paired_bootstrap(rows, first, second, replicates=20000):
    rng = np.random.default_rng(20261115)
    means = np.zeros(replicates)
    effect = 0.0
    ns = []
    for task in TASKS:
        a = {r['fingerprint']: r for r in rows if r['model_key'] == first and r['task'] == task}
        b = {r['fingerprint']: r for r in rows if r['model_key'] == second and r['task'] == task}
        assert a.keys() == b.keys()
        differences = [int(a[fp]['correct'])-int(b[fp]['correct']) for fp in sorted(a)]
        counts = np.array([differences.count(v) for v in [-1, 0, 1]])
        draws = rng.multinomial(len(differences), counts/len(differences), size=replicates)
        means += (draws[:, 2]-draws[:, 0])/len(differences)/len(TASKS)
        effect += sum(differences)/len(differences)/len(TASKS)
        ns.append(len(differences))
    return {"first": first, "second": second, "difference_pp": effect*100,
            "ci95_pp": (np.quantile(means, [.025, .975])*100).tolist(),
            "replicates": replicates, "seed": 20261115, "task_counts": ns}


def write_report(data):
    cells = data['cells']
    lines = ["# Final evaluation status and before/after comparison", "",
        "Internal working report, 15 November 2026. All differences are percentage points (pp), not relative percentage changes.", "",
        "## Summary of the main changes", "",
        "- **All current sample targets are complete:** 21,640 selected outcomes, ten model configurations, 250 questions on each of eight tasks and all 164 HumanEval questions. The historical comparison contains 11,070 available outcomes. The net increase of 10,570 selected outcomes excludes replacement generations and diagnostics.",
        "- **BYOD-Gemma's nine-task mean rises from 50.58% originally recorded to 52.43% (+1.85 pp).** This combines scoring-policy changes, a fresh rerun and added questions. Under the current scorer, its historical mean is 50.58%; rerunning those same questions gives 53.51%; adding the remaining questions brings this to 52.43%. It would be incorrect to attribute the gain entirely to sample expansion.",
        "- **HumanEval is the main cluster of declines.** Gemma AR falls from 74.0% on its historical 50 questions to 59.8% on all 164. BYOD-Gemma's fresh initial 125 score 37.6%, but the added 39 score only 5.1%; this is the one old-versus-added cohort difference that survives correction across all 90 model–task comparisons. Its final 29.9% remains above its historically recorded 25.6% because the initial questions were rerun.",
        "- **The new failure analysis gives a partial explanation for Gemma HumanEval:** 11/39 added programs are invalid Python, including six unfinished docstrings, but 26 further answers are syntactically valid and wrong. The added specifications are longer; all their canonical answer bodies still fit the 256-token canvas if the specification is not copied. Length alone does not explain the gap.",
        "- **LLaDA's largest drop is MATH: 34.4% → 26.0% (−8.4 pp).** Its added questions score 17.6%, versus 34.4% originally. This is unusual in an isolated test, but does not survive the 90-comparison correction. Manual inspection of 12 added LLaDA answers found no scoring error; its earlier 18 replay controls all matched historical correctness.",
        "- **BYOD-Gemma's MBPP gain is mainly a rerun effect:** historical 36.8% → fresh same-question 48.8% → final 43.6%. Both MBPP and HumanEval have 20 gains and five losses on their original 125 questions; these matched rerun changes survive a separate nine-task correction. The cause of historical generation drift remains unresolved.",
        "- **Qwen AR's large intermediate collapse was repaired, not retained.** Its final GSM8K is 92.4% and HumanEval 81.1%. Known faulty new eager-attention outputs were replaced under SDPA, while verified historical predictions were reused.",
        "- **MATH presentation follow-up completed (v3):** whole numeric answers with stray escapes, complete scalar final statements and reference-aware percent units are now handled consistently. Nine historical decisions and four final decisions are restored; their old flags and scorer are archived. BYOD-Gemma and LLaDA final scores are unchanged. [Correction policy and exact impact](MATH_PRESENTATION_CORRECTION.md).", "",
        "## How to read the comparisons", "",
        "The before column uses the preserved `recorded_correct` flags from the latest compatible historical per-question results, not the first cloud campaign's incomplete/exact-only rescoring. It is a recovered historical baseline, not an assertion that every value exactly reproduces an older printed manuscript table. The final column uses the adopted fresh-Gemma/corrected-Qwen selection and the current uniform MATH scorer.", "",
        "Each benchmark table separates **historical**, **current results on those same question IDs**, **new question IDs**, and **final combined**. `Net Δ` is final minus originally recorded. `Added Δ` is final minus the current same-ID score, isolating the arithmetic effect of adding questions after the selected cohort/scorer is fixed. It is not a causal estimate of a runtime or training effect. For MATH, the additional scoring table separates historical rescoring from generation changes.", "",
        "Historical denominators are 125 except Gemma AR HumanEval/MBPP (50 each) and Qwen AR HumanEval (95). Therefore their added subsets contain 114, 200 and 69 questions respectively, rather than 39 or 125. All final configurations share the same question IDs for a task. BYOD-Gemma uses a complete fresh cohort, including its original questions, uniformly across tasks and regardless of whether answers improved or worsened.", "",
        "## Nine-task averages and decomposition", "",
        "Each task has equal weight. The following components add to the net change before rounding: historical rescoring, changed generations on the original IDs, and then adding question IDs. The original-ID denominators differ between models where historical files were incomplete.", "",
        "| Model | Historical mean | Scoring Δ | Rerun Δ | Added Δ | Final mean | Net Δ |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for v in data['averages']:
        lines.append(f"| {MODELS[v['model']]} | {v['original']:.2f}% | {signed(v['scoring_delta'])} | {signed(v['rerun_delta'])} | {signed(v['expansion_delta'])} | {v['final']:.2f}% | {signed(v['total_delta'])} |")
    lines += ["", "### Largest net individual-score changes", "",
        "These rank changes from originally recorded to final scores. They are not automatically sample-size effects or statistically significant differences.", "",
        "| Model | Task | Historical | Final | Net Δ |",
        "|---|---|---:|---:|---:|"]
    for c in sorted(cells, key=lambda c: abs(c['total_delta']), reverse=True)[:12]:
        lines.append(f"| {MODELS[c['model']]} | {LABELS[c['task']]} | {c['original']['pct']:.1f}% | {c['final']['pct']:.1f}% | {signed(c['total_delta'])} |")
    lines += ["", "## Benchmark-by-benchmark results", "",
        "Cells with counts show `correct / evaluated (accuracy)`. The same-ID column is the selected current outcome, not necessarily the historical generation. Both delta columns use percentage points."]
    for task in TASKS:
        lines += ["", f"### {LABELS[task]}", "",
            "| Model | Historical | Same IDs, now | Added IDs only | Final | Net Δ | Added Δ |",
            "|---|---:|---:|---:|---:|---:|---:|"]
        for c in [c for c in cells if c['task'] == task]:
            lines.append(f"| {MODELS[c['model']]} | {count_text(c['original'])} | {count_text(c['same_ids'])} | {count_text(c['added'])} | {count_text(c['final'])} | {signed(c['total_delta'])} | {signed(c['expansion_delta'])} |")
        if task == 'math':
            lines += ["", "Historical MATH rescoring of the **same saved text**, before any rerun or added questions:", "",
                "| Model | Originally recorded | Current scorer on historical answers | Change |",
                "|---|---:|---:|---:|"]
            for c in [c for c in cells if c['task'] == task]:
                lines.append(f"| {MODELS[c['model']]} | {count_text(c['original'])} | {count_text(c['rescored'])} | {signed(c['scoring_delta'])} |")
            lines += ["", "For example, Gemma AR's historical record is 75/125 (60.0%), the first cloud exact-only rescore was 71/125 (56.8%), and the strict v2 scorer gave 74/125 (59.2%), and the presentation-corrected v3 scorer restores 75/125 (60.0%). These are different scoring versions of the same historical answers. The earlier 56.8% value must not be presented as the original recorded baseline. See the completed presentation correction below."]
    lines += ["", "## Are any changes larger than expected?", "",
        "A final 250-question score contains the original questions, so treating historical and final scores as independent would give the wrong comparison. Instead, compare **current outcomes on original IDs against disjoint added IDs**, after fixing scorer and cohort. For each of the 90 model–task cells, use a two-sided Fisher exact test of equal success probabilities; apply Holm correction across all 90. This is an exploratory check for cohort differences under an exchangeability model, not proof that the subsets are random or a test of whether software changed.", "",
        f"There are **{sum(c['p'] < .05 for c in cells)} nominal p<0.05 differences**. After Holm correction at 0.05, the number flagged is **{sum(c['holm_p'] < .05 for c in cells)}**. Non-significance is not equivalence or proof that a discrepancy is harmless. Shared task composition can produce correlated changes across models.", "",
        "| Model / task | Original IDs, current cohort | Added IDs | Added minus original (pp) | Nominal 95% interval (pp) | Exact p | Holm-adjusted p |",
        "|---|---:|---:|---:|---:|---:|---:|"]
    for c in sorted(cells, key=lambda c: c['p'])[:12]:
        lo, hi = c['cohort_ci95_pp']
        lines.append(f"| {MODELS[c['model']]} / {LABELS[c['task']]} | {count_text(c['same_ids'])} | {count_text(c['added'])} | {signed(c['cohort_difference'])} | [{signed(lo)}, {signed(hi)}] | {ptext(c['p'])} | {ptext(c['holm_p'])} |")
    lines += ["", "The intervals are nominal 95% Newcombe-Wilson intervals for the difference of two disjoint proportions; they are not simultaneous 90-comparison intervals. They are not obtained by inverting Fisher's exact test, so their zero-crossing and the exact p-value can differ near a threshold, as for Ministral MBPP. The Holm-adjusted p column provides the multiple-comparison decision. These calculations do not measure training-seed variance or remove systematic differences between question subsets.", "",
        "**BYOD-Gemma HumanEval is the clearest remaining discrepancy.** Its added cohort is only 2/39 correct, versus 47/125 on the fresh original IDs: −32.47 pp between cohorts, adjusted p≈0.00363. Adding that small low-scoring cohort lowers the fresh score from 37.6% to 29.88%, even though comparison with the historical 25.6% still shows a gain. BYOD-Llama 25k HumanEval is borderline after the global correction (adjusted p≈0.0509). The other HumanEval declines form a coherent pattern worth documenting; none should be discarded solely because its individual adjusted p is above 0.05.", "",
        "HumanEval's earlier CPU audit reproduced all 1,601 saved scores and passed all 164 reference solutions. Added answers contain real algorithmic/runtime failures and, for some diffusion models, outputs that exhaust their 256-token canvas while copying a docstring. The fresh Gemma cohort was generated after that earlier audit; that audit is supporting harness evidence, not an exhaustive execution audit of every final fresh Gemma answer. Static inspection and a current-runtime investigation would be appropriate if further diagnosis is desired. No common scoring repair has been established from the cohort statistics alone.", "",
        "**LLaDA MATH remains an observed decline, not a demonstrated bug.** The added subset scores 22/125 versus 43/125 initially; exact p≈0.00374 before adjustment and 0.321 after adjustment. The added half contains more level-4/5 items (69 versus 55). The [manual check](LLADA_MANUAL_CHECK.md) found genuine errors in sampled answers, and rescoring all 375 added MATH/GSM8K/MMLU-Pro answers reproduced their flags. None of this proves that question difficulty fully explains the decrease.", "",
        "### Matched historical-versus-fresh Gemma checks", "",
        "This is a separate question from sample expansion. Compare the same 125 question IDs before and after rerunning Gemma, using the current scorer on both sets. Exact two-sided McNemar tests use the gained/lost pairs; Holm correction covers Gemma's nine tasks.", "",
        "| Task | Incorrect → correct | Correct → incorrect | Exact p | Holm-adjusted p |",
        "|---|---:|---:|---:|---:|"]
    for g in data['gemma_paired_checks']:
        lines.append(f"| {LABELS[g['task']]} | {g['gains']} | {g['losses']} | {ptext(g['p'])} | {ptext(g['holm_p'])} |")
    lines += ["", "MBPP and HumanEval each have 20 gains and five losses (+12 pp on the original questions), adjusted p≈0.0367. These indicate meaningful historical/current generation differences on those fixed items under this diagnostic. They do not establish a training improvement or identify the cause. Original weights/tokenizer were checked, and selected current-runtime answers reproduced across repeat runs and tested backends; the exact historical environment was not fully logged.", "",
        "### Current paired model comparisons", "",
        "For context, the following equal-weight nine-task differences use paired item bootstrap intervals, stratified by task (20,000 replicates, seed 20261115). Both models always use identical IDs. These are nominal 95% intervals, not part of the 90 cohort-discrepancy tests and not adjusted across these contrasts. They describe empirical item variation on the selected tasks, not training runs or unseen task families.", "",
        "| Comparison | Difference (pp) | Nominal 95% interval (pp) |",
        "|---|---:|---:|"]
    for c in data['paired_macro_comparisons']:
        lo, hi = c['ci95_pp']
        lines.append(f"| {MODELS[c['first']]} minus {MODELS[c['second']]} | {signed(c['difference_pp'])} | [{signed(lo)}, {signed(hi)}] |")
    lines += ["", "The current Gemma–LLaDA interval excludes zero on these selected questions. This is narrower and different from the earlier incomplete eight-task interval; neither its values nor the earlier eight-task point estimate should be carried over unchanged. Gemma remains substantially below its AR parent, while the Llama 50k/25k comparison remains unresolved. These derived comparisons include the completed v3 MATH presentation correction.", "",
        "## What changed in evaluation and code", "",
        "1. **Historical data recovery and sample matching.** We selected the latest compatible saved answer for each exact model/task/prompt/target, not the highest-scoring answer. Partial historical denominators remain explicit. Frozen question fingerprints and dataset/model revisions support exact reuse. Raw originals and the pre-expansion backup were retained.",
        "2. **Expanded coverage.** Eight tasks now have 250 unique questions per configuration; HumanEval has its full 164. New queues skip completed IDs and checkpoint each answer locally, with periodic private uploads. Parallel queues were disjoint; all original adapter assets were verified rather than silently replaced with public alternatives.",
        "3. **Qwen AR attention fix.** A matched A100 probe reproduced four selected bad GSM8K/HumanEval answers under eager attention; SDPA corrected all four while holding the model, BF16, greedy decoding, output caps and repetition penalty fixed. The adopted Qwen AR path uses SDPA. A separate historical replay passed 16/16 correctness comparisons, with 13 identical texts. All faulty new eager outputs were excluded regardless of whether they happened to pass. Its originally faulty full HumanEval score was 110/164 (67.07%), versus the corrected 133/164 (81.10%). [Investigation](qwen_investigation.md).",
        "4. **Fresh BYOD-Gemma cohort.** Historical replays disagreed despite matching weight/tokenizer checks. Three selected current-runtime outputs repeated exactly and did not change between the tested eager/SDPA paths. We did not identify a model-loading bug or recover the exact historical environment. The author chose a complete fresh cohort, applied consistently to all tasks and both gains/losses. All 2,164 final Gemma answers are fresh generations; the historical cohort remains separate. [Investigation](gemma_replay_investigation.md).",
        "5. **MATH dependency and final-answer scorer.** The first cloud bundle lacked `math-verify`; normalized exact comparison rejected equivalent expressions. Pinned `math-verify[antlr4_13_2]==0.8.0` and added a startup guard. The current comparator normalizes final answers, respects `FINAL:`, avoids accepting correct intermediate values when the declared final is wrong, and uses bounded symbolic parsing/verification without a permissive whole-rationale fallback. We rescored historical and final answers consistently. Original recorded flags, intermediate cloud flags, strict v2 flags and corrected v3 flags are retained. The v3 rules repair complete scalar presentation and interpret percent units using the reference, without searching rationales for a matching number. See [the completed correction](MATH_PRESENTATION_CORRECTION.md). [Investigation](gemma_math_mbpp_investigation.md).",
        "6. **Code-harness investigations.** HumanEval's CPU audit reproduced 1,601 saved predictions with zero score disagreements, and all 164 reference solutions passed. A separate Gemma MBPP audit reproduced all 281 old/fresh saved flags and passed all 250 reference solutions. No broad code-test harness defect was found. Generated code was executed only in resource-limited cloud children for these audits, not on the laptop. The code extractor handles full functions, canonical body completions, and incomplete/trailing Markdown fences; these paths were audited rather than assumed to explain every decline.",
        "7. **Budgets and decoding deliberately preserved.** AR keeps the author's longer caps (1,024 tokens, or 2,048 for MMLU-Pro). Diffusion retains its task-specific 64/128/256-token canvases, full-NFE decoding, temperature zero and the frozen transfer settings. There was no new low-NFE benchmark condition, matched extra-AR training control, or retraining of BYOD checkpoints. Changes in generation implementation/runtime must not be mistaken for changes to trained weights.",
        "8. **Assembly, uncertainty and restart safeguards.** Assembly rejects wrong plan IDs, overlapping continuation lanes and changed saved predictions, requires the chosen provenance, and verifies every target count. Controller fixes recognize provider scheduling states and normal shutdown margins; bounded queues can resume without duplicating answers. All 75 targeted campaign/protocol/scoring tests pass after the v3 presentation correction; this report adds offline comparison checks and no new generation. Statistical summaries distinguish nine-task means from older eight-task means and use the correct paired/disjoint comparisons.", "",
        "### Completed MATH presentation correction (v3)", "",
        "The previously listed numeric-escape, scalar-prose and percent-unit cases are now implemented, tested and uniformly rescored. See [the correction policy, validation and old/new counts](MATH_PRESENTATION_CORRECTION.md). The former scorer and labels remain archived. All 21,640 prediction texts, settings and question identities are unchanged; four final MATH flags and nine historical-baseline flags change from false to true. This is a scoring correction, not new generation or selective answer replacement. Malformed symbolic/truncated answers outside these narrow rules remain subject to the existing final-answer policy.", "",
        "## Internal sampling and interpretation record", "",
        "As agreed with the author, detailed ordering diagnostics remain internal. All models share the same selected questions. The [ordering audit](DATASET_ORDER_AUDIT.md) records the ActivityNet-only HellaSwag subset, more reassuring measured distributions for some other tasks, and limits of the checks. Matched questions support within-subset comparisons; the cohort tests and item intervals do not remove systematic selection effects or certify benchmark-wide representativeness. Full HumanEval removes item-subsampling uncertainty for that fixed test set under deterministic decoding, not uncertainty about future problems.", "",
        "## Completion, provenance and reproduction", "",
        f"The final checkpoint was verified at dataset revision `{data['source_revision']}`. All three GPU workers are COMPLETED. Both parallel controllers report complete; HumanEval's controller label is stale (`provider_paused`), but its actual worker and saved 328/328 correction outcomes are complete. `all_sample_targets_complete` and `all_humaneval_complete` are true.", "",
        "- Final selected outcomes and scoring audit: `generation_diagnostic/nov15_gemma/assembled_results.jsonl` and `assembled_audit.json`.",
        "- Preserved historical/intermediate results: `generation_diagnostic/nov15/main_results.jsonl`; original September flags are `recorded_correct`, while `correct` in that file is an intermediate cloud rescore.",
        "- Final checkpoints and pinned source/hash records: `parallel_runs/gemma/`, `parallel_runs/others/`, and `humaneval_runs/latest/`.",
        "- Reproducible numerical comparison: [analysis script](../analysis/final_evaluation_comparison.py) and [JSON with all 90 cells, exact tests, decomposition and input hashes](../analysis/final_evaluation_comparison.json).",
        "- Earlier policy decisions, investigations and immutable inputs remain available through [the discrepancy register](DISCREPANCY_LOG.md). Its older progress paragraphs are historical; this final report supersedes them for current counts and scores.", "",
        "Regenerate this document and the numerical artifact with:", "", "```sh",
        ".venv/bin/python iclr2027_rebuttal/analysis/explain_final_discrepancies.py",
        ".venv/bin/python iclr2027_rebuttal/analysis/final_evaluation_comparison.py", "```", "",
        "This analysis launched no jobs, changed no cloud state or budgets, and did not update manuscript numerical tables."]
    notes = EVAL/'DISCREPANCY_EXPLANATIONS_AND_REVISION_PLAN.md'
    insertion = lines.index('## Completion, provenance and reproduction')
    lines[insertion:insertion] = [notes.read_text().strip(), '']
    (EVAL/'FINAL_EVALUATION_STATUS.md').write_text('\n'.join(lines)+'\n')


def main():
    # Elementary exact-probability checks, independent of the data.
    assert abs(fisher(10, 10, 0, 10)-2/math.comb(20, 10)) < 1e-12
    assert abs(fisher(5, 10, 5, 10)-1) < 1e-12
    assert abs(fisher(0, 10, 0, 10)-1) < 1e-12
    assert abs(mcnemar(5, 0)-.0625) < 1e-12
    original_path = EVAL / "generation_diagnostic/nov15/main_results.jsonl"
    final_path = EVAL / "generation_diagnostic/nov15_gemma/assembled_results.jsonl"
    audit_path = final_path.with_name("assembled_audit.json")
    original = load_rows(original_path)
    baseline = [r for r in original if r['source'] == 'legacy_rescored']
    final = load_rows(final_path)
    audit = json.loads(audit_path.read_text())
    assert audit['all_sample_targets_complete'] and audit['all_humaneval_complete']
    explanations_path = HERE/'final_discrepancy_explanations.json'
    explanations = json.loads(explanations_path.read_text())
    assert explanations['final_results_sha256'] == hashlib.sha256(final_path.read_bytes()).hexdigest(), 'Rerun explain_final_discrepancies.py on the current final results'
    math_baseline = {(r['model_key'], r['fingerprint']): r['after']
                     for r in audit['math_scoring_audit'] if r['group'] == 'baseline'}
    baseline_corrected = [dict(r, correct=math_baseline[(r['model_key'], r['fingerprint'])])
                          if r['task'] == 'math' else dict(r) for r in baseline]
    corrected_lookup = {(r['model_key'], r['fingerprint']): r for r in baseline_corrected}
    cells = []
    for key in MODELS:
        for task in TASKS:
            old = [r for r in baseline if r['model_key'] == key and r['task'] == task]
            old_corrected = [r for r in baseline_corrected if r['model_key'] == key and r['task'] == task]
            current = [r for r in final if r['model_key'] == key and r['task'] == task]
            ids = {r['fingerprint'] for r in old}
            same = [r for r in current if r['fingerprint'] in ids]
            added = [r for r in current if r['fingerprint'] not in ids]
            assert len(same) == len(old) == len(ids)
            old_lookup = {r['fingerprint']: r for r in old}
            if key != 'gemma_d':
                assert all(r['prediction'] == old_lookup[r['fingerprint']]['prediction'] for r in same)
            assert len(current) == (164 if task == 'humaneval' else 250)
            c = {'model': key, 'task': task, 'original': stat(old, 'recorded_correct'),
                 'rescored': stat(old_corrected), 'same_ids': stat(same), 'added': stat(added), 'final': stat(current)}
            assert c['rescored']['k'] == audit['summary_nine_tasks'][key]['before']['tasks'][task]['correct']
            assert c['final']['k'] == audit['summary_nine_tasks'][key]['after']['tasks'][task]['correct']
            c.update(scoring_delta=c['rescored']['pct']-c['original']['pct'],
                     rerun_delta=c['same_ids']['pct']-c['rescored']['pct'],
                     expansion_delta=c['final']['pct']-c['same_ids']['pct'],
                     total_delta=c['final']['pct']-c['original']['pct'],
                     cohort_difference=c['added']['pct']-c['same_ids']['pct'])
            assert abs(c['scoring_delta']+c['rerun_delta']+c['expansion_delta']-c['total_delta']) < 1e-9
            c['p'] = fisher(c['same_ids']['k'], c['same_ids']['n'], c['added']['k'], c['added']['n'])
            c['cohort_ci95_pp'] = difference_interval(c['same_ids']['k'], c['same_ids']['n'], c['added']['k'], c['added']['n'])
            c['paired_gains'] = sum(r['correct'] and not corrected_lookup[(key, r['fingerprint'])]['correct'] for r in same)
            c['paired_losses'] = sum(not r['correct'] and corrected_lookup[(key, r['fingerprint'])]['correct'] for r in same)
            cells.append(c)
    holm(cells)
    gemma = [dict(model=c['model'], task=c['task'], gains=c['paired_gains'], losses=c['paired_losses'],
                  p=mcnemar(c['paired_gains'], c['paired_losses'])) for c in cells if c['model'] == 'gemma_d']
    holm(gemma)
    # Check that unexpected historical answer replacements have not crept in.
    assert all(c['paired_gains'] == c['paired_losses'] == 0 for c in cells if c['model'] != 'gemma_d')
    averages = []
    for key in MODELS:
        group = [c for c in cells if c['model'] == key]
        values = {name: sum(c[name]['pct'] for c in group)/9
                  for name in ['original', 'rescored', 'same_ids', 'final']}
        values.update(model=key, scoring_delta=values['rescored']-values['original'],
                      rerun_delta=values['same_ids']-values['rescored'],
                      expansion_delta=values['final']-values['same_ids'],
                      total_delta=values['final']-values['original'])
        averages.append(values)
    comparisons = [paired_bootstrap(final, a, b) for a, b in
                   [('gemma_d', 'llada'), ('gemma_d', 'gemma_ar'), ('llama_50k', 'llama_25k')]]
    artifact = {'analysis_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'inputs': {str(p.relative_to(HERE.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in [original_path, final_path, audit_path, explanations_path,
                                     EVAL/'DISCREPANCY_EXPLANATIONS_AND_REVISION_PLAN.md']},
                'source_revision': json.loads((EVAL/'parallel_runs/final_status.json').read_text())['revision'],
                'original_outcomes': len(baseline), 'final_outcomes': len(final), 'cells': cells,
                'averages': averages, 'gemma_paired_checks': gemma, 'paired_macro_comparisons': comparisons}
    (HERE/'final_evaluation_comparison.json').write_text(json.dumps(artifact, indent=2)+'\n')
    write_report(artifact)
    print('Original/final outcomes',len(baseline),len(final))
    print('Nominal / Holm outliers',sum(c['p']<.05 for c in cells),sum(c['holm_p']<.05 for c in cells))
    for c in sorted(cells, key=lambda c: c['p'])[:12]:
        print(c['model'], c['task'], count_text(c['same_ids']), count_text(c['added']), 'p',c['p'],'Holm',c['holm_p'])
    print('Gemma paired checks',gemma)
    print('Macro comparisons',comparisons)
    for row in averages: print('MEAN',row)


if __name__ == '__main__':
    main()
