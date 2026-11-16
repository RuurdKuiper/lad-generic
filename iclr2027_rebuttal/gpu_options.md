# GPU rental options for unattended evaluation

Prices checked 8 November 2026 in USD. These are listed hourly rates, not confirmed capacity or a reservation. No instance or paid job has been launched.

## Current scope

The latest author-selected plan is **250 total/task across all ten configurations**, then extra matched samples for Gemma/Gemma AR/LLaDA if funds remain. The approximately €100 budget remains binding. Earlier 375-item workload scenarios below are historical comparisons, not the current first-stage allocation.

## Recommendation

Start with **one 80–96 GB GPU**, running model/checkpoint evaluations sequentially. My first choices are RunPod H100 PCIe 80 GB for a flexible server, or Hugging Face Jobs RTX PRO 6000 96 GB for managed batch execution. A100 80 GB is a lower-hourly-price alternative. The fastest GPU is not necessarily the cheapest per completed benchmark; measure a fixed pilot.

The memory recommendation is an inference from the local model sizes and full-precision evaluation needs, not a measured peak-memory result. BYOD-Gemma's reported adapter-loaded 10.732B parameters require about 21.5 GB for BF16 weights alone, before activations/logits/workspace and batches. A 48 GB device may work at small batch sizes; 80–96 GB gives more headroom. Keep evaluation precision unchanged when extending the old runs. FP8 training does not imply that evaluation should use FP8 or weight quantization.

## Listed options and budget scenarios

| Option | VRAM | USD/hour | 24 GPU-hours | 72 GPU-hours | Fit for this task |
|---|---:|---:|---:|---:|---|
| RunPod A100 PCIe | 80 GB | $1.79 | $42.96 | $128.88 | Lower hourly cost, ample memory |
| RunPod RTX PRO 6000 | 96 GB | $2.49 | $59.76 | $179.28 | Memory headroom; same named GPU family as reported conversion runs |
| RunPod H100 PCIe | 80 GB | $2.89 | $69.36 | $208.08 | My flexible-server starting choice |
| Hugging Face Jobs A100 | 80 GB | $2.50 | $60.00 | $180.00 | Managed batch job within the HF ecosystem |
| Hugging Face Jobs RTX PRO 6000 | 96 GB | $2.75 | $66.00 | $198.00 | My HF batch starting choice |

RunPod rates: [official Pod pricing](https://www.runpod.io/pricing). Hugging Face rates: [Jobs pricing](https://huggingface.co/docs/hub/jobs-pricing). The 24/72-hour columns are simple rate × time arithmetic, **not predictions of job duration**. Storage, taxes, plan charges and any transfer charges are outside these compute-only scenarios. Actual offers and account access must be checked when choosing the instance.

A cheaper possible pilot option is RunPod L40S 48 GB at a listed $1.09/hour; memory/batching should be measured first. [Official pricing](https://www.runpod.io/pricing).

## Hugging Face service choice

For this work use **Jobs**, which accepts batch workloads, rather than building a model-serving Inference Endpoint. A batch evaluation can run after submission without maintaining a browser session. See [Jobs overview](https://huggingface.co/docs/hub/jobs-overview).

Set a deliberate timeout: the documented default is 30 minutes. Persist results outside the ephemeral job filesystem and make the task resumable by completed item ID before a long run. See [Jobs configuration](https://huggingface.co/docs/hub/jobs-configuration#timeout). This requires packaging the evaluation and arranging access to the exact parent checkpoints, adapters and gated data; that work is pending.

For a rented server, run the worker in a detached process/session or service and write each completed item to durable storage. Closing the local browser/SSH connection should not own the job lifetime. Keep model downloads cached, record timing and failures, and stop the GPU allocation after the queue completes.

## Workload and runtime uncertainty

The selected plan is 3,046 unique questions/model across nine tasks, with **1,921 additional** if every original 125/task result is reusable. For ten columns that is **19,210 additional model–question evaluations**. The Gemma / Gemma-AR / LLaDA first-pass subset is **5,763 additional**. Changed protocols or failed provenance checks can require rerunning old questions as well.

For illustration only, if the measured end-to-end average were 5, 15 or 30 seconds per added model–question evaluation, the ten-column incremental workload would take about **26.7, 80.0 or 160.1 GPU-hours**, respectively, before setup and extra reruns. On the $2.89/hour H100 quote those scenarios cost roughly **$77, $231 or $463**. These are conditional arithmetic, not measured throughput. The three-column first pass under the same hypothetical averages would take about 8, 24 or 48 hours.

Measure representative multiple-choice, math and code cases on the actual GPU. Diffusion's repeated full-sequence passes, prompt length, NFE, batching and code-execution overhead make model size or training time alone an unreliable predictor. Use the timing evidence to select the GPU and budget before the full queue.

## Other provider checked

Lambda's public instance page currently labels its displayed rates as effective **16 November 2026**, after this check date, and directs users to log in for current rates. Those future prices are not used as current quotes here. [Official Lambda page](https://lambda.com/instances).

## Budget constraint: approximately €100 total

The author has set an approximately €100 total budget. This supersedes treating the full ten-column expansion as the immediate target. No provider or paid allocation has been selected.

Recommended allocation: cap compute at roughly **US$75**, and retain the remaining budget for storage, billing conversion/taxes and contingency. Treating one dollar as one euro is a conservative planning simplification here, not a verified FX quote; check the actual all-in charge before booking. At the listed rates, 40 A100 hours cost $71.60 and 25 H100 PCIe hours cost $72.25. Pilot time counts against this cap.

Prioritize the same added questions on BYOD-Gemma, its unchanged AR parent and LLaDA: 5,763 additional model–question evaluations under the reusable-first-125 assumption. Keep original 125-item results for other models explicitly separate from the expanded paired three-model comparison. Do not claim all four families were expanded if they were not. Correct mismatched MMLU-Pro settings before combining results; affected old items may need reruns.

Start with a 1–2-hour A100 80 GB pilot, including loading/setup and representative long/short tasks. This is a budget-oriented starting recommendation, not proof that A100 is cheaper per completed evaluation. H100 costs about 1.615 times as much per hour; it is cheaper per completed item if measured throughput exceeds A100 by that factor. A 48 GB L40S is another possible lower-rate option, but its memory fit and throughput have not been measured.

The goal is complete 375-item comparisons for the three priority columns, with full HumanEval/sanitized-MBPP sets. Completion within the cap is **not guaranteed**. If the pilot projects an overrun, predeclare a smaller balanced scope shared by all three models before looking at new accuracy results, or stop at a documented common item boundary. Save each result immediately; enforce an elapsed-time stop plus an external billing/termination safeguard, rather than relying on the browser remaining open or an unattended balance running out. No GPU has been rented.

## Latest 250-item first stage

Current counts supersede the earlier 375-item starting scope: 2,164/model in total, 1,039/model additional, or 10,390 additional across ten columns (about 54% of the earlier incremental question count). Runtime will not fall in exactly that ratio because model loading, task mix and setup matter. The user prefers breadth first, then further depth for Gemma/Gemma AR/LLaDA if budget remains. Do not promise completion within €100 before timing the pilot. A follow-up cap of 375 for the trio adds 2,646 evaluations. No instance or job has been started.
