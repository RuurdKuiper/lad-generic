# Credit-limited pilot outcome

The A100 Job [6af05e99e6320c66fad74a2a](https://huggingface.co/jobs/Ruurd/6af05e99e6320c66fad74a2a) completed normally. The worker stopped at its planned time limit; final progress and results were saved. No new Job was launched during this check.

- 728 new Gemma AR generations saved; mean generation time 8.27 seconds.
- 3,268 total scored outcomes saved, including 2,540 outcomes carried forward from the first run.
- Zero duplicate model/question identities.
- Gemma AR now has 206 scored questions on each of ARC-C, GPQA, HellaSwag, MMLU, MMLU-Pro, GSM8K and MATH; HumanEval has 131 and MBPP 130. The 250-target suite is unfinished.
- No new Gemma diffusion, LLaDA or other-model generations were reached. Diffusion timing and checkpoint replay validation remain outstanding.
- Thirteen historical correctness flags changed under the frozen scorer; review those changes before propagating final paper results.

Downloaded outputs and the pinned source commit are preserved locally in `pilot_runs/6af05e99e6320c66fad74a2a/`. Original historical files and the separate pre-expansion backup remain unchanged. This check confirms saved data and normal execution, not final scientific validation or a measured billing total.

Scoring-change counts (model, task, old flag, new flag):

- ('gemma_ar', 'math', True, False): 4
- ('gemma_d', 'math', True, False): 9
