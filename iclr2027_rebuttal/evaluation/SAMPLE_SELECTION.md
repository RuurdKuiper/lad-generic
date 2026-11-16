# Actual question selection — verified 15 November 2026

The completed evaluation was **not uniformly randomly sampled from every full benchmark**. This is verified in the frozen `campaign_bundle/code/src/diffusion_lm/benchmarks.py`, the preparation script, and saved question fingerprints, rather than inferred from the current code alone.

| Task | Actual selection |
|---|---|
| MMLU | Shuffle the full selected test split with seed 1234, then retain the first 250 unique prompt/target fingerprints |
| MMLU-Pro | Same seeded shuffle procedure; no explicit subject stratification |
| ARC-Challenge | First 250 unique items in the released test-set order |
| HellaSwag | First 250 unique items in labeled validation-set order |
| GSM8K | First 250 unique items in test-set order |
| MATH | First 250 unique items in the MATH-500 test-set order; not a random draw from the full original MATH test set |
| GPQA | First 250 unique items in GPQA-Main release order; its evaluation pool is stored under a split named `train` |
| MBPP | First 250 unique items in the sanitized test-set order (257 available) |
| HumanEval | All 164 items; the historical first-125 subset followed release order |

Preparation loaded up to 270 candidates, removed exact duplicate prompt/target fingerprints and retained up to 250 unique items. The full split was shuffled before limiting only for MMLU/MMLU-Pro. For the other tasks, adding examples generally extended the existing prefix rather than drawing new random IDs. A dataset publisher may already have randomized its release order, but this evaluation did not establish that as a sampling guarantee.

LLaDA's historical 125 fingerprints match the first 125 frozen items on all nine tasks. All final model configurations use the same selected question identities for each task, with 250 items or all 164 HumanEval items.

## Interpretation and remaining work

**Follow-up:** comparison with every remaining item found a clear HellaSwag source-order effect, more reassuring measured distributions for GSM8K/ARC/MATH, a possible GPQA difficulty difference, and only seven MBPP items missing. See the [released-order audit](DATASET_ORDER_AUDIT.md) for quantitative evidence and limits.

The manually reviewed LLaDA failures remain genuine. However, the decrease cannot be attributed solely to random sampling variation: an ordered prefix can differ from the rest of a benchmark in difficulty or subject composition. MATH's added half contains 69 level-4/5 items versus 55 in the original half. This is one observed composition difference, not proof of the cause of the full score decrease.

Wilson and item-bootstrap intervals do not correct systematic selection bias from ordered prefixes. The finite-population precision calculations in the original sampling plan assumed simple random sampling and must not be represented as a guarantee for these prefix subsets. Paired comparisons remain comparisons on the shared evaluated items; extrapolation to whole benchmarks needs a sampling justification.

Before finalizing manuscript claims, document actual selection, qualify the intervals, and decide whether to complete small sets or add a prespecified matched random/stratified sample of unused items. Retaining the fixed prefix in a combined sample does not turn the whole set into a simple random sample. Do not select replacements based on observed correctness. This audit changes no answers or scores and launches no additional runs.
