# Released-order audit — 15 November 2026

**Author's reporting decision:** retain this audit in internal records. The manuscript and rebuttal will state that comparisons use the same fixed question subsets across models, without a separate discussion of dataset ordering. The observations and methodological limits below remain recorded; this decision does not establish representativeness or authorize additional runs.

**HellaSwag has a clear source-ordering problem for our subset.** The other prefix tasks do not all show the same problem. Some look similar on available metadata; GPQA has a possible difficulty difference; MBPP is nearly complete. No metadata audit can establish absence of every performance-related selection bias.

The analysis used the exact cached dataset revisions in the frozen campaign plan, reconstructed prompts/targets and matched saved fingerprints. For all six partial unshuffled tasks, the selected 250 are exactly the first 250 unique released items. There were no duplicate prompt/target pairs in these six evaluation pools.

| Task | Observed comparison of selected 250 with unused items | Interpretation |
|---|---|---|
| HellaSwag | All 250 are ActivityNet; full validation has 3,243 ActivityNet and 6,799 WikiHow items (32.29%/67.71%). The entire first 3,243 rows are ActivityNet; WikiHow follows. Selected contexts average 23.15 words versus 40.56 in the remainder; endings average 12.29 versus 25.71 words. | Clearly unrepresentative of the full source mix, with substantial length differences. Actual model-score bias and its direction cannot be quantified without outcomes from the missing source. |
| GSM8K | Question length 46.26 versus 46.25 words; annotated calculation count 3.12 versus 3.28; reference length 51.60 versus 53.06 words. | No large discrepancy detected on these features. These are proxies, not complete difficulty labels. |
| ARC-Challenge | Similar question/choice lengths, number of choices and source-ID-prefix distribution. Question length 22.07 versus 22.80 words. | No strong ordering discrepancy detected on available checks; subject/difficulty are not exhaustively captured by source IDs or length. |
| MATH-500 | Subjects closely match. Level-4/5 items are 124/250 (49.6%) versus 138/250 (55.2%); mean level 3.35 versus 3.53. Problem/reference lengths are similar. | No strong mismatch detected between the evaluated half and the remaining half on these features. This does not prove the prefix was randomly selected. |
| GPQA-Main | Similar domain/subdomain and writer-rated difficulty distributions. Expert validation accuracy averages 77.0% versus 68.2%; non-expert accuracy 29.2% versus 31.8%. | Possible difficulty difference: experts performed better on the evaluated prefix. This is not a measured model-performance bias. |
| MBPP sanitized | 250/257 test items included (97.28%). IDs are sorted; omitted IDs are 473–479, all from one source notebook. | Source order is non-random, but only seven items remain. Completing them removes subset-selection uncertainty for this fixed test set. Any full-set accuracy differs from the current accuracy by at most 7/257 = 2.724 percentage points, regardless of their outcomes. |

HumanEval is now complete at 164 items; there is no remaining item-subset selection problem for that fixed benchmark. MMLU/MMLU-Pro used seeded full-split shuffling and are not part of this ordered-prefix audit.

## Methods and statistical limits

Reproduce with `.venv/bin/python iclr2027_rebuttal/analysis/dataset_order_audit.py`. Aggregated counts, means, dataset revisions and cached-data hashes are saved in [the machine-readable audit](../analysis/dataset_order_audit.json). The script needs only existing local dataset caches, not a GPU or network access.

There are 29 exploratory metadata comparisons. Categorical checks use total variation distance between subset and remainder, with multivariate-hypergeometric draws under simple random sampling without replacement. Numerical checks use absolute mean differences under random subsets, conditioning on observed non-missing counts. All use 9,999 simulations, fixed seed 20261115 and the add-one Monte Carlo p-value. Global Holm correction covers all 29 tests. The lowest attainable Monte Carlo p-value is 0.0001, not zero.

HellaSwag's source/activity and length differences remain clear after correction (adjusted p=0.0029); MBPP's source-notebook concentration does too (adjusted p=0.005). GPQA expert-validation accuracy has unadjusted p=0.0024 and adjusted p=0.0576. Treat it as an exploratory warning rather than a definitive corrected significance finding. The other tested differences do not survive correction. Failure to reject does not establish equivalence, random release order, or negligible model-score bias. Multiple metadata features may be correlated, and unobserved task characteristics remain possible.

The diagnostics compare covariates, not unobserved model outcomes. With HellaSwag, even a reweighting of current predictions cannot recover WikiHow performance, because there are no WikiHow outcomes in the selected set. Shared item IDs across models do not correct source-selection bias in benchmark-wide comparisons.

## Dataset construction sources

- The [HellaSwag dataset card](https://huggingface.co/datasets/Rowan/hellaswag) documents its `source_id`, activity and split metadata. Counts and source-block ordering above were computed from our pinned validation data, not inferred from the card's default training preview.
- The [MATH-500 card](https://huggingface.co/datasets/HuggingFaceH4/MATH-500/raw/main/README.md) identifies its source as OpenAI's 500-problem subset. The [original split documentation](https://github.com/openai/prm800k#math-splits) says the 500 problems were selected uniformly from MATH. This supports the construction of the 500-item pool, but does not by itself guarantee that our first 250 have random order.
- The [GSM8K repository](https://github.com/openai/grade-school-math) explains its question/answer and calculation-annotation fields; it does not establish a random-prefix guarantee.
- The [GPQA repository](https://github.com/idavidrein/gpqa) documents the dataset and baseline evaluation options, including answer-choice shuffling. Shuffling answer choices is separate from randomly selecting questions.
- The [MBPP repository](https://github.com/google-research/google-research/tree/master/mbpp) specifies task-ID-based train/test splits and says the sanitized subset inherits these assignments. These assignments do not guarantee randomized test order.

## Action implied by the findings

Prioritize a properly sampled HellaSwag subset drawn from the full validation pool. Freeze its IDs independently of scores and evaluate the same IDs for all models, reusing exact matches where available. Preserve the old ActivityNet-only results as a separate cohort. Replacing a subset should be disclosed rather than silently substituting the new scores. Adding a small WikiHow batch to the existing prefix does not automatically create a simple random sample of the full benchmark.

Completing the last seven MBPP items is a small, concrete way to remove that benchmark's residual subset-selection issue. For GPQA, a full-set completion or a documented sampling design would address the remaining concern more directly than treating a non-significant adjusted test as proof of no bias. GSM8K, ARC and MATH need accurate disclosure and qualified uncertainty; this audit alone does not demand discarding all their existing results.

This audit launched no jobs, changed no budgets, and modified no selected answers, correctness flags or benchmark score tables. All current sample targets remain complete under their original definition; HellaSwag's representativeness remains an unresolved methodological issue.
