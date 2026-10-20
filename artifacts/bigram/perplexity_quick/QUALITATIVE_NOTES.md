# Spot checks while the experiment runs

These are examples, not an independent manual ranking of all 240 answers.

- Question 1, NFE 8: confidence-guided output repeats fragments such as “the the” and “Netherlands Netherlands.” PMI Viterbi produces more recognizable sentences but still repeats phrases about culture and canals.
- Question 4, NFE 32: confidence-guided output contains broken transitions (“and, and honest,” and “someone to to listen with”). PMI produces a more fluent paragraph, although “celebrate your successes and failures” remains an odd phrase.
- Question 13, NFE 8: PMI incorrectly says Earth is the center of the universe. Improving reference-model perplexity does not establish factual correctness.

PMI remains deterministic for fixed settings. The baseline uses a single sampling seed in this quick experiment; bootstrap intervals only describe variation across these questions.
