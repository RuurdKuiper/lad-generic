# Corrected Qwen and fresh Gemma evaluation

**Latest 15 November reporting decision:** the runs below have stopped. The user explicitly selected the fresh Gemma cohort for the eight rerun tasks, including both improved and worsened answers; historical outcomes remain separate. MBPP is **74/156 (47.4%)**, with 61/125 on the fresh initial subset. Describe historical-to-current comparisons as rerun plus expansion, not a pure sample-size effect. An intermediate original-retention assembly was archived before regeneration. HumanEval remains deferred/historical. MATH answers also require the corrected final-answer symbolic rescorer; frozen worker flags are superseded for reporting. See [the discrepancy register](DISCREPANCY_LOG.md), [detailed fixes](gemma_math_mbpp_investigation.md), and `assemble_results.py`. The original immutable plans and all raw answers remain unchanged.

Controller: https://huggingface.co/jobs/Ruurd/6af16147e6320c66fad7e6ab

First GPU block: https://huggingface.co/jobs/Ruurd/6af1614fe6320c66fad7e6b9

Verified startup checkpoint: Qwen's **16/16 historical replay correctness flags match**, with **13/16 byte-identical output texts**. The worker has saved 1,000 historical Qwen outcomes and its first eight corrected new answers, with no blocked models. Gemma's fresh cohort follows the first bounded Qwen batch; completion is not yet established.

Immutable inputs: private dataset `Ruurd/iclr2027-rebuttal-eval`, revision `e4a64b8157d5a6dd710baafbef859ff8dec4dc85`.

Plan: `28f51c173d7dc462d2c3a90199f3ddabedac01eaf77bae9abcc5608885d8a9ad`.

The original campaign continues independently for the other models. It uses its original pinned input revision even though the dataset's current input files now hold the corrected plan. Its generated Qwen AR outcomes must not supersede the corrected cohort. No original outputs are deleted or silently changed.

- **Qwen AR:** SDPA, BF16, greedy decoding, unchanged inherited repetition penalty and intentional 1,024-token cap (2,048 for MMLU-Pro). Replace all newly generated eight-task outcomes from the eager cohort, not just its failures. Up to 1,000 historical outcomes remain candidates for reuse, with an explicit 16-question AR replay gate (two per included task). Replay text is now saved, not only match booleans. Any score mismatch pauses Qwen for review.
- **Gemma diffusion:** verified original weights, explicit SDPA, same sampler and output budgets. Fresh generation of all 2,000 outcomes across the eight included tasks, with no historical predictions mixed into this cohort. The old historical-mismatch gate cannot block a cohort with no historical outcomes to reuse. This is explicit cohort separation, not an invented replay pass.
- **HumanEval:** excluded from this correction plan as requested. Existing full-set outputs are retained. Qwen's HumanEval scores remain affected/provisional; the tested fix is in code but a corrected full rerun has not been performed. Gemma HumanEval remains historical-only.

Target: 4,000 scored outcomes, including 1,000 historical Qwen reuse candidates and 3,000 new generations. Questions/prompt/target fingerprints are unchanged from the frozen source. Per-question fsync and periodic private checkpoint uploads preserve continuation after interruptions. Reports from this cohort alone cannot provide a nine-task mean because HumanEval is deferred. Do not silently calculate a new eight-task mean and compare it to a nine-task historical mean.

Private outputs are under `campaigns/<plan-id>/` as before. Keep cohort tables separate until each corrected task is complete and validated. Merge by `(model_key, task, fingerprint)` only with explicit cohort precedence; never pool two answers to one question or select by correctness.

```sh
.venv/bin/python iclr2027_rebuttal/evaluation/campaign.py status --staging iclr2027_rebuttal/evaluation/corrections_staging.json
.venv/bin/python iclr2027_rebuttal/evaluation/campaign.py resume --staging iclr2027_rebuttal/evaluation/corrections_staging.json
```

The controller refuses overlapping jobs for this plan, resumes saved answers, stops on errors/replay review, and automatically chains bounded GPU blocks after normal time limits. Resuming retains the existing budget ledger.

**Budget:** the correction controller has an $18 total ceiling, which includes conservative upper reservations of $1.916682 for the completed generation probe and $0.005177 for the HumanEval CPU audit, plus controller and correction GPU costs. The first correction startup failed before generation because the old scheduler always injected LLaDA; its $0.083334 GPU upper cost and $0.37 CPU reservation are also carried forward in the current $2.375193 prior reservation. A regression check now verifies subset scheduling. Together with the original controller's $75 ceiling, the aggregate maximum is $93. No additional untracked diagnostics should be launched outside this accounting. It may stop at its budget limit before completing all targets; check saved progress rather than assuming completion.

Validation before the corrected restart: 16 offline campaign/protocol checks passed; the prepared plan hash and all source/data hashes passed `worker.verify`. Diagnostic replays corrected all four selected new Qwen failures with only the backend changed, and Gemma's three disputed outputs were identical on repeat runs and across both tested backends. Expanded corrected benchmark scores remain pending.
