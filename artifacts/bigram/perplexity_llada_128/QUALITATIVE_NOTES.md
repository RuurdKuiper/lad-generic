# Interpretation and spot checks

PMI substantially reduces pooled perplexity at 8 and 16 NFE under these transferred settings. The baseline often collapses into long function-word loops at those budgets; one 8-NFE photosynthesis answer scores 1577.97 per-answer perplexity. Per-question wins and medians are included to show how broad the improvement is beyond large outliers.

PMI still degenerates at low NFE: the 8-NFE search answer repeatedly emits “web pages,” and the friendship answer loops on “understanding.” At 32 NFE, the PMI Amsterdam answer incorrectly lists Red Square as an Amsterdam landmark. At 64 NFE, the PMI seasons answer contradicts the hemispheric explanation by assigning winter to a Southern Hemisphere tilted toward the Sun. Lower perplexity is not a factuality score.

At 128 NFE the baseline refrigerator answer still loops on “cold air,” while the PMI refrigerator answer gives a sustained explanation. Most other 128-NFE answers from both methods are fluent. The pooled gains at 32–128 NFE are smaller, and their paired bootstrap intervals include no gain in this 10-question, one-seed sample.

Delay EOS/EOT retention is on for both methods. PMI additionally uses ending prediction delay strength 10; the baseline has that penalty disabled. The 8-NFE baseline Amsterdam answer ends after “It” despite retention delay, showing that the option does not enforce a minimum answer length. This is a settings-bundle comparison in the shared app sampler, not an isolated Viterbi ablation or the official LLaDA benchmark sampler.
