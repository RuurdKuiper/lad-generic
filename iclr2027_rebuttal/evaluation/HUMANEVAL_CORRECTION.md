# Priority HumanEval correction — 15 November

**COMPLETED:** actual GPU job is COMPLETED and worker progress is `complete`, 328/328 outcomes, with no blocked models. Corrected Qwen AR is **133/164 (81.10%)**, versus the faulty eager full-set 110/164 (67.07%); its historical 95 contribute 83 successes and its 69 replacements contribute 50. Fresh Gemma is **49/164 (29.88%)**, comprising 47/125 initial and 2/39 added. Historical Gemma was 32/125 (25.6%). Both full corrected cohorts are now adopted, and all ten model/task cells have 164 selected HumanEval outcomes. Nine-task summaries are available; other benchmarks remain incomplete. The old controller's cached `provider_paused` field is stale; actual job status and complete saved progress establish completion. The startup observations below remain as history.

Author instruction: resolve HumanEval before continuing the remaining benchmark expansion. All older benchmark campaigns remain stopped.

**Subsequent authorization:** the user now also requests running the remaining samples in parallel. Two separate, capped non-HumanEval queues have been started; this HumanEval plan and its budget are unchanged. See [parallel execution and cumulative budget](PARALLEL_COMPLETION.md). Latest verified snapshot: Qwen complete at 164/164, Gemma 47/164, actual GPU RUNNING. Earlier benchmark controllers remain stopped.

Controller: https://huggingface.co/jobs/Ruurd/6af9794429dd05ff0368776c

Actual GPU worker: https://huggingface.co/jobs/Ruurd/6af9795123985fb9cd832052

Verified read-only startup checkpoint: GPU **RUNNING**, worker progress **running**, 129/328 outcomes saved (95 historical Qwen plus 34 replacements), no blocked models. The Qwen replay gate has been passed, since new generation has proceeded.

**Monitoring caveat:** the original controller stopped monitoring when the provider returned `SCHEDULING`, leaving its cached `provider_paused` status. The GPU itself continued normally. Local controller code now recognizes `SCHEDULING` as active, with a regression test. Automatic approval review rejected replacing the active controller's cloud snapshot because of state/budget overwrite risk; no such write or observer job was executed. Use read-only actual-job/progress checks below. Current worker checkpointing is independent of the controller and continues; automatic chaining is not active for this already-submitted job. If it ends incomplete, reconcile the terminal job's observed usage before resuming rather than assuming its full reservation was spent.

Plan: `23df4ab50ba12c30ac5d673db707ea2f5ad2996787942e744153178e8433c5ce`.

Immutable inputs: private dataset `Ruurd/iclr2027-rebuttal-eval`, revision `da01145525f780cdf9dd5f058a6710472297639b`.

## Why HumanEval was temporarily excluded

- The added Qwen AR answers were generated with the eager backend that reproduced known arithmetic/code errors. SDPA corrected the tested HumanEval failures; those 69 eager additions require replacement. The original 95 answers remain reuse candidates, subject to a new two-question HumanEval replay check.
- Gemma's fresh eight-task cohort did not include HumanEval. To follow the author's adopted fresh-cohort policy, generate all 164 Gemma HumanEval answers in the current environment instead of mixing its historical 125 with other fresh tasks.
- The original code-scoring audit found no shared harness defect: 164/164 canonical solutions pass and all 1,601 saved HumanEval flags reproduce. Other models' declines contain actual semantic/syntax errors and some diffusion answers exhaust their canvas. This run does not change their scores or assume those failures were grading mistakes.

## Scope

Only `qwen_ar` and `gemma_d`, only HumanEval. Target 328 scored outcomes: 95 reused Qwen candidates, 69 replacement Qwen generations, 164 fresh Gemma generations. No other benchmark tasks are scheduled.

Pinned original model/adapter assets and the existing greedy decoding/sampler settings are retained: Qwen AR 1,024 output tokens, Gemma diffusion 256-token canvas / 256 NFE with its original termination settings. Both use the tested SDPA configurations. No prompt edits, syntax repairs, extra sampling attempts, longer budgets, or selection by test correctness.

The worker uploads durable progress/results and preserves per-question continuation. Qwen replay disagreement stops Qwen for review; a model's partial HumanEval correction is not adopted into final result assembly. Fresh Gemma replaces historical Gemma only when the complete 164-question cohort is available.

## Budget and commands

Additional phase cap **$6**, including its controller. Prior observed/conservative reservations total $71.760949, carried into the new ledger. Therefore this phase's cumulative ceiling is $77.760949, below the overall $93 cap. Do not add the old controllers' prior costs again: they are already included in this cumulative ledger.

```sh
.venv/bin/python iclr2027_rebuttal/evaluation/watch_humaneval.py --once
.venv/bin/python iclr2027_rebuttal/evaluation/campaign.py status --staging iclr2027_rebuttal/evaluation/humaneval_staging.json
.venv/bin/python iclr2027_rebuttal/evaluation/campaign.py resume --staging iclr2027_rebuttal/evaluation/humaneval_staging.json
```

Private cloud files: `campaigns/<plan-id>/progress.json`, `results.jsonl`, `replays.jsonl`, `controller.json`, `report.json`.

After downloading that run's `results.jsonl` and verifying its pinned revision/plan, adopt it explicitly:

```sh
.venv/bin/python iclr2027_rebuttal/evaluation/assemble_results.py --humaneval-results iclr2027_rebuttal/evaluation/humaneval_runs/latest/results.jsonl
```

The assembler checks the HumanEval plan ID, backend provenance, unique question identities and full 164-question coverage per model before adopting replacements. It retains Qwen's verified historical answers, replaces all Gemma HumanEval outcomes with the fresh cohort, and rejects incomplete/duplicate or mismatched cohorts. Its audit includes the new input file hash and plan ID. Only after all selected HumanEval task cells reach 164 does it emit a separate `summary_nine_tasks`; eight-task summaries remain distinct. Other unfinished benchmark targets still require completion later.

69 targeted checks pass after this integration and the scheduling-state regression fix. Run outputs and scores remain pending until cloud completion; no new nine-task superiority claim is made now.
