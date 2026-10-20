# Interpretation and spot checks

The low-NFE perplexity improvement must not be read as an equal improvement in answer quality. At 8 NFE, the PMI Amsterdam answer contains “Netherlands” **45 times**, yet Phi-4 assigns it perplexity **2.24**. The much more fluent PMI answer at 128 NFE scores **3.88** on the same question. Predictable repetition can beat useful prose on this metric.

At 32 NFE, the PMI answer about a good friend also develops a long loop of “They are willing…” phrases. These examples show that repetition is not confined to the lowest budget.

The generated answers and token-level Distinct-1 are saved alongside perplexity. Spot checks are illustrative, not a full manual ranking of all 100 answers. The two settings bundles differ in temperature, top-k and ending prediction delay, so these results do not isolate the effect of Viterbi alone.
