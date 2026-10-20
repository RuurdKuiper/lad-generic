## What carries over to LLaDA?

Under these shared app settings, the clearest LLaDA gains occur at 8 and 16 NFE. PMI wins per-answer PPL on 8/10 questions at both budgets. The large pooled reductions (97% and 86%) are amplified by catastrophic baseline failures: median answer PPL changes from 18.56 to 4.43 at 8 NFE and from 6.31 to 4.81 at 16 NFE. This is a broader improvement than a single outlier, but the pooled percentages should not be interpreted as percentages of answer-quality improvement.

At 32, 64, and 128 NFE, LLaDA's pooled PPL reductions are approximately 17%, 8%, and 4%. Their paired bootstrap intervals include a ratio of 1, so this small experiment does not establish a reliable pooled improvement at those budgets. The baseline is already much stronger there.

With the requested Distinct-1 metric, LLaDA improves at all five budgets. At 16 NFE its mean unique-token count rises from 28.6 to 58.8, and mean Distinct-1 rises from 0.297 to 0.467. For Gemma, Distinct-1 declines at 8 NFE, changes little at 16–32, and improves at 64–128. These statements use unigram diversity throughout; previous Distinct-2 interpretations should not be carried over unchanged.

PMI does not remove low-budget repetition or factual errors. LLaDA's 8-NFE search answer still loops on “web pages,” while its fluent 32-NFE Amsterdam answer names Red Square as a local landmark. At 128 NFE the baseline refrigerator answer loops on “cold air,” whereas PMI gives a sustained explanation. See the good, average, and bad examples in each model's report for the range of behavior.
