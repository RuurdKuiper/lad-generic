# Quick Gemma perplexity comparison

Saved generations: 168/240; scored: 168/240.

Generation stopped at the user’s request. All completed question sets are retained below.

30 standard questions; one seed (1234); 64-token canvas; one block; delayed EOS/EOT retention; early stopping disabled. All generation and reference scoring runs on Hugging Face ZeroGPU.

Baseline: existing app confidence-guided sampler, temperature 0.7, top-k 3. Viterbi: PMI, diffusion confidence, temperature 2, top-k 16, fixed weight 0.5, minimum count 1, clipping ±2, ending-delay strength 10. This compares the practical setups, including their different sampling/ending settings; it does not isolate the effect of Viterbi or exactly replicate the paper.

Reference: microsoft/phi-4, NF4 with double quantization and BF16 compute. Standalone answers scored without question conditioning. Perplexity is exp(total negative log likelihood / total scored reference tokens). Only matched prompts are compared at each NFE.

| NFE | Paired prompts | Confidence PPL | PMI PPL | PMI / confidence | Paired 95% bootstrap interval |
|---:|---:|---:|---:|---:|---:|
| 8 | 21 | 27.63 | 11.45 | 0.415 | 0.265–0.602 |
| 16 | 21 | 16.82 | 8.45 | 0.502 | 0.397–0.616 |
| 32 | 21 | 8.11 | 4.76 | 0.587 | 0.473–0.711 |
| 64 | 21 | 4.83 | 3.34 | 0.692 | 0.584–0.812 |

Bootstrap: 10,000 paired prompt resamples, seed 1234. The interval captures prompt variability for these outputs; it does not capture variation across generation seeds.

Lower perplexity means more predictable text under Phi-4. Repetition and shorter or generic answers can also lower perplexity; it is not a correctness or factuality score. See saved answers for qualitative review.

| NFE | Confidence mean words | PMI mean words |
|---:|---:|---:|
| 8 | 30.5 | 40.0 |
| 16 | 35.7 | 45.9 |
| 32 | 42.0 | 45.3 |
| 64 | 44.0 | 48.4 |

Median per-answer perplexity and paired win counts supplement the token-pooled metric above. They help show whether the result is concentrated in a few failed answers. A win means lower per-answer PPL, not a manual quality judgment.

| NFE | Confidence median PPL | PMI median PPL | PMI PPL wins |
|---:|---:|---:|---:|
| 8 | 43.80 | 11.91 | 19/21 |
| 16 | 16.63 | 8.35 | 19/21 |
| 32 | 7.75 | 4.99 | 18/21 |
| 64 | 4.96 | 3.50 | 17/21 |

Distinct-1 (Gemma tokenizer) is the number of unique token types divided by the total number of tokens in the complete generated answer, excluding special tokens and the prompt. Each answer is measured separately; the table averages those ratios and unique-token counts across questions. Higher ratios indicate less token repetition. This is not a grammaticality score.

| NFE | Confidence Distinct-1 | PMI Distinct-1 | Confidence mean unique tokens | PMI mean unique tokens |
|---:|---:|---:|---:|---:|
| 8 | 0.578 | 0.543 | 19.3 | 24.7 |
| 16 | 0.623 | 0.615 | 24.9 | 32.1 |
| 32 | 0.624 | 0.670 | 29.5 | 34.0 |
| 64 | 0.671 | 0.688 | 33.2 | 37.6 |

## Spot checks while the experiment runs

These are examples, not an independent manual ranking of all 240 answers.

- Question 1, NFE 8: confidence-guided output repeats fragments such as “the the” and “Netherlands Netherlands.” PMI Viterbi produces more recognizable sentences but still repeats phrases about culture and canals.
- Question 4, NFE 32: confidence-guided output contains broken transitions (“and, and honest,” and “someone to to listen with”). PMI produces a more fluent paragraph, although “celebrate your successes and failures” remains an odd phrase.
- Question 13, NFE 8: PMI incorrectly says Earth is the center of the universe. Improving reference-model perplexity does not establish factual correctness.

PMI remains deterministic for fixed settings. The baseline uses a single sampling seed in this quick experiment; bootstrap intervals only describe variation across these questions.

