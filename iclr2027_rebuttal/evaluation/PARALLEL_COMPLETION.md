# Parallel completion of the remaining benchmarks — 15 November

The user authorized continuing the remaining samples and requested approximately twice the expected time/cash as hard limits, then asked about three GPU instances. Execution now uses **three A100-80GB instances in total while HumanEval is active**: the existing HumanEval worker plus two additional, disjoint continuation queues. It does not launch three additional GPUs or multiply one queue's budget by three.

## Queues and immutable inputs

| Queue | Pending generations at submission | Saved outcomes reused | Controller | GPU worker |
| --- | ---: | ---: | --- | --- |
| Gemma, eight non-HumanEval tasks | 739 | 1,261 | [6af9812b29dd05ff03687f61](https://huggingface.co/jobs/Ruurd/6af9812b29dd05ff03687f61) | [6af9813429dd05ff03687f67](https://huggingface.co/jobs/Ruurd/6af9813429dd05ff03687f67) |
| Other seven incomplete models, eight tasks | 919 | 13,081 | [6af9812823985fb9cd832785](https://huggingface.co/jobs/Ruurd/6af9812823985fb9cd832785) | [6af9812f23985fb9cd83278b](https://huggingface.co/jobs/Ruurd/6af9812f23985fb9cd83278b) |
| HumanEval only, already running | 233 new generations initially | 95 Qwen candidates | See [HumanEval execution note](HUMANEVAL_CORRECTION.md) | [6af9795123985fb9cd832052](https://huggingface.co/jobs/Ruurd/6af9795123985fb9cd832052) |

Verified startup: all three GPU workers **RUNNING**. New queues imported exactly their 1,261 and 13,081 saved outcomes and have no blocked models. At that checkpoint HumanEval had completed Qwen 164/164 and Gemma 47/164. These are timestamped startup observations, not final completion claims.

Private dataset: `Ruurd/iclr2027-rebuttal-eval`.

- Gemma plan `78228989046f2f731ff00bbf9414758d87ea456c484f5e5a68d1fee543bdb587`; input revision `682a97d1c93dbbe8b4c665b3617def9f18cbb045`.
- Others plan `a68c4180c556e52b8aefde565db3816d06c38121552d49aa80fbb5b98fb1acdc`; input revision `49ce9721dca6cf2e2e17fb93793b3af97303db3c`.

`prepare_remaining.py` identifies exact missing fingerprints from the adopted fresh-Gemma/corrected-Qwen/consistent-MATH assembly. `prepare_parallel.py` splits these by model and verifies disjoint outcomes, task/settings compatibility, source/data hashes and resume counts. Gemma AR and Qwen AR's already completed non-HumanEval tasks are excluded from generation. No historical questions are regenerated just to fill a queue, and no HumanEval task enters these two queues. New Gemma outputs extend its selected fresh cohort, not its historical one.

## Estimates and enforced caps

Saved per-model/task generation timings predict 2.33 GPU-hours for Gemma and 1.90 for the other models: **4.24 GPU-hours total generation**, approximately **5 GPU-hours with loading/checkpoint overhead**. Two balanced workers should finish the remaining queues in roughly **2.5–3 elapsed hours** if hardware is available. Expected incremental compute is approximately $12–14; parallel startup/download overhead means cost is not exactly identical to a single GPU.

Each queue has an independent **$12.75 cash ceiling**, **five aggregate allocated GPU-hours** and an **eight-hour controller wall timeout**. The two static allocations sum to **$25.50 and ten GPU-hours**. They are not $25.50 per instance. Per-job GPU blocks remain at most four hours, and the controller chains a further bounded block only when remaining time and money permit. Counting allocated time conservatively also prevents released cash from silently expanding the runtime cap. Controllers and per-job billing-rounding reservations are included in the cash cap.

The existing HumanEval phase's cumulative ceiling, including all earlier observed/reserved costs, is $77.760949. Adding the two new queues produces an overall compute ceiling of **$103.260949**. At the [ECB's 13 November reference rate](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html), EUR 1 = USD 1.1052, this is approximately **€93.43**, within the user's original €100 compute budget. This is a compute reservation/upper bound, not the current bill. The old $93 dollar planning cap is superseded by the user's latest authorization and this documented budget, not by an uncapped extension.

Machine-readable allocation, source revisions and reference conversion: ignored `parallel_runs/budget_and_sources.json`. Current per-plan controller ledgers remain separate cloud files; neither new controller edits HumanEval's active controller state. The previously rejected active-state overwrite was not retried.

## Checkpoints, restart and result assembly

Each worker fsyncs each answer and periodically uploads private checkpoints. An interrupted job can resume from saved question IDs. Complete answers are skipped. Errors, replay issues, price changes and caps stop work rather than triggering unbounded retries. An expired model-loading shutdown margin is now recorded as a normal time limit, so the controller can continue instead of falsely declaring scientific review needed. `SCHEDULING` is recognized as an active provider status in these new controllers.

```sh
.venv/bin/python iclr2027_rebuttal/evaluation/campaign.py status --staging iclr2027_rebuttal/evaluation/parallel_gemma_staging.json
.venv/bin/python iclr2027_rebuttal/evaluation/campaign.py status --staging iclr2027_rebuttal/evaluation/parallel_others_staging.json
```

Use the corresponding `resume` command only after a queue's active jobs have ended; the CLI refuses overlap and retains its ledger. No automatic budget increases or transfers between queues occur.

After downloading pinned snapshots of all three result files, assemble them explicitly:

```sh
.venv/bin/python iclr2027_rebuttal/evaluation/assemble_results.py \
  --humaneval-results iclr2027_rebuttal/evaluation/humaneval_runs/latest/results.jsonl \
  --remaining-results iclr2027_rebuttal/evaluation/parallel_runs/gemma/results.jsonl \
  --remaining-results iclr2027_rebuttal/evaluation/parallel_runs/others/results.jsonl
```

Assembly verifies plan IDs and fingerprints, rejects overlapping queues, wrong-model/task data and any changed previously saved prediction, requires Gemma's fresh SDPA provenance, and rescales no benchmark weights. It reapplies the same MATH scorer to all outcomes and separately reports eight-task/nine-task means and whether **all** targets reached 250/task (164 for HumanEval). Queue reports alone omit other queues' models, so do not treat a single lane's report as the full benchmark table.

72 targeted tests pass, including cumulative runtime caps independent of cash refunds, normal shutdown-margin handling and duplicate/provenance-safe merging. Final verification now confirms all 21,640 selected outcomes and every sample target complete; see [final completion status](FINAL_EVALUATION_STATUS.md).
