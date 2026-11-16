# HumanEval decline: diagnostic findings (9 November)

**15 November priority update:** the author now requests HumanEval correction before any remaining benchmark expansion. A [HumanEval-only run](HUMANEVAL_CORRECTION.md) has been submitted: replace 69 faulty Qwen AR additions under SDPA, reuse its historical 95 after replay checks, and generate a fresh 164-question Gemma cohort. Original decoding limits remain unchanged. Other models' existing 164 outcomes remain; the earlier CPU audit did not find a common harness defect. Scores and nine-task comparisons are pending completion. The earlier decision to defer HumanEval below is superseded by this explicit priority instruction.

The CPU scoring audit found no shared scoring regression in the saved answers. Full-suite HumanEval scores should be retained. Unequal question subsets and generation limitations help explain the decline; their causal shares are not established. Qwen AR's separate runtime investigation remains open.

## Reproducible scoring check

Input results revision: `ca1698d0028b236b634f58272f7f24d7ba4bbe2d` in the private evaluation dataset. Used the immutable campaign input source and the same Python-test assembly, extraction and resource limits as the running campaign. Generated code ran only in unprivileged Linux child processes, with no Hub token in the child environment; this is a resource-limited subprocess, not a complete network sandbox.

- All **164/164 canonical reference solutions pass** their tests.
- All **1,601 saved HumanEval predictions** were tested again: **zero pass/fail disagreements** with stored campaign flags, including historical reused outputs.
- No missing-package/import-error failures were identified. Most added-answer failures are assertion failures, syntax errors or ordinary runtime errors such as undefined variables and wrong types. A small number of saved answers time out; one historical Collatz implementation exhausts memory while appending to a nonterminating sequence. These do not indicate a widespread harness dependency problem.
- Private error traces and per-answer outcomes: `humaneval_diagnostic/audit.json`, also uploaded to `diagnostics/humaneval/<results-revision>/audit.json` in the private dataset. Static inspection: `humaneval_diagnostic/static.json`.
- CPU-only job: https://huggingface.co/jobs/Ruurd/6af15cd30e0338d1bb852593 (completed). Thirty-minute provider cap; maximum compute reservation **$0.005177**, to count against the overall budget before any subsequent campaign resume. No new answers were generated and the GPU campaign was not modified.

## Fixed dataset order matters

HumanEval was sampled as a prefix, not randomly: `load_benchmark` only requests shuffled selection for subject-category tasks, not HumanEval. Most historical runs covered indices 0–124; added questions are 125–163. Historical Gemma AR had only 0–49 and Qwen AR 0–94, so their "added" subsets differ from the other models.

| Model | Questions 0–49 | Questions 50–124 | Questions 125–163 |
| --- | ---: | ---: | ---: |
| Gemma diffusion | 38.0% (19/50) | 17.3% (13/75) | Not generated |
| Gemma AR | 74.0% (37/50) | 54.7% (41/75) | 51.3% (20/39) |
| LLaDA | 58.0% (29/50) | 28.0% (21/75) | 17.9% (7/39) |
| Qwen diffusion | 32.0% (16/50) | 28.0% (21/75) | 5.1% (2/39) |
| Qwen AR | 96.0% (48/50) | 62.7% (47/75) | 38.5% (15/39) |
| Ministral diffusion | 50.0% (25/50) | 25.3% (19/75) | 10.3% (4/39) |
| Ministral AR | 94.0% (47/50) | 80.0% (60/75) | 71.8% (28/39) |
| Llama diffusion 25k | 50.0% (25/50) | 18.7% (14/75) | 5.1% (2/39) |
| Llama diffusion 50k | 42.0% (21/50) | 18.7% (14/75) | 10.3% (4/39) |
| Llama AR | 48.0% (24/50) | 61.3% (46/75) | 35.9% (14/39) |

For LLaDA and BYOD models, the first two columns were both generated historically. Their decline within that historical data predates the cloud expansion, supporting a question-composition contribution. This does not prove a universal difficulty ordering, nor rule out runtime differences. Gemma AR's middle column is entirely new; Qwen AR's middle column mixes old and new answers and cannot isolate a runtime effect.

The median canonical body lengths are 112 characters (0–49), 133 (50–94), 235.5 (95–124) and 191 (125–163). Later questions also have longer median specifications. Length is descriptive, not an independent measure of task difficulty.

## Individual failure mechanisms

- **Incorrect algorithms / missed edge cases:** HumanEval/125 `split_words` asks for whitespace splitting, then comma splitting if no whitespace, then a character count if neither delimiter exists. Llama AR and Ministral diffusion test `if not txt.split()`, which does not implement the comma fallback for a nonempty string. Qwen diffusion counts odd ASCII codes rather than odd zero-based alphabet positions. These are genuine implementation errors.
- **Incorrect duplicate handling:** HumanEval/126 `is_sorted` allows two occurrences but not three. Llama AR requires every element to be unique; Ministral diffusion checks ordering but omits the multiplicity rule. These answers can look plausible while failing official tests.
- **Invalid Python:** added-answer execution reports syntax/indentation errors for Qwen diffusion (16/39), Ministral diffusion (20/39), Llama-25k (14/39) and Llama-50k (16/39). Qwen AR has 10/69; Gemma AR has 1/114; Ministral AR and Llama AR have none in their added 39 questions. This reinforces the need for a separate Qwen AR matched replay.
- **Some diffusion answers exhaust their 256-token canvas while copying the specification:** HumanEval/129 is a clear example for Ministral diffusion and both Llama adapters: the saved answer ends inside a copied triple-quoted docstring before reaching a complete implementation. Llama-50k /127 ends at `intersection = max(interval`. This is a real budget/output-allocation limitation.
- **Reaching the canvas is not itself proof of truncating useful code:** many diffusion answers already contain a closed function, followed by repetitive Markdown fences. Qwen diffusion /125 is one example: the extracted function is intact but wrong. Increasing length cannot be assumed to fix these answers.

Decoded retokenized lengths are approximate diagnostics, not exact generated token counts. LLaDA's tokenizer was unavailable to the offline static pass, so no LLaDA length claim is made. All AR answers inspected remain well below the intentionally longer 1,024-token cap.

## Decisions and remaining work

1. Preserve the completed 164-question results and use the common full test set once protocol review is resolved; do not drop HumanEval because scores decreased.
2. Do not generate further HumanEval samples or reruns now. No scoring fix is supported by this audit.
3. Keep Qwen AR provisional pending a same-question runtime replay (see `qwen_investigation.md`). A shared scorer defect has not been found, but CPU retesting cannot validate the GPU generation environment.
4. If later evaluating longer diffusion canvases or prompts discouraging docstring copying, label this as a separate decoding/prompt ablation and apply it consistently. Do not merge changed-protocol scores into the frozen run or silently replace failures.
5. Report actual sample counts and selection order. The old prefix and added tail are not interchangeable random samples; their difference is not an estimate of a causal runtime effect. Full-set HumanEval avoids the old prefix-coverage limitation.

Scripts: `diagnose_humaneval.py` executes the frozen harness in the cloud; `inspect_humaneval.py` performs local static checks only.
