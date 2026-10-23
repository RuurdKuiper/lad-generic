# Expanded bigram and optional trigram guidance for LLaDA

Training, deployment and hosted validation completed on 22 October 2026.

Live Space: [Ruurd/llada-8b-instruct](https://huggingface.co/spaces/Ruurd/llada-8b-instruct), revision `b31a17ae5d4b017ffad71798ea5f35949416e4d2`.
Scorer assets: [Ruurd/llada-ngram-guidance-877m](https://huggingface.co/Ruurd/llada-ngram-guidance-877m), pinned revision `5ad854a30691e137d78cac78a091f0834bd4ac8f`.

## Corpus

Both new scorers use exactly the same **877,064,287 LLaDA tokens**, about 11.38 times the original corpus. The added 800M tokens follow the revised 90/5/5 mix, emphasizing varied English text.

| Source | Tokens | Documents |
| --- | ---: | ---: |
| [FineWeb-Edu](https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu), sample/10BT | 720,000,000 | 693,604 |
| [Python-Edu text mirror](https://huggingface.co/datasets/Avelina/python-edu-cleaned) | 40,000,000 | 80,803 |
| [FineMath-4+](https://huggingface.co/datasets/HuggingFaceTB/finemath) | 40,000,000 | 25,512 |
| All original training responses | 77,064,287 | 980,000 |

Original responses are also publicly available in [Ruurd/LAD-training-1m-256-long](https://huggingface.co/datasets/Ruurd/LAD-training-1m-256-long). Anonymous checks confirmed all four sources are public and ungated; the first 50 public original-response rows matched the local corpus. No private corpus or model weights were published.

The Python mirror resolves text from the upstream Python-Edu metadata. New sources are sampled deterministically from pinned Parquet files, with exact within-source text duplicates skipped. Documents are tokenized separately; no n-grams cross document boundaries. Complete documents receive EOS, and the last document is truncated to the exact budget. Original response truncation/EOS handling is preserved. Source revisions, files, token counts and tokenizer fingerprint are in [training_report.json](training_report.json). These are contiguous file samples, not a random sample of the entire source datasets.

Counts contain 40,456,406 distinct bigrams and 225,720,542 distinct trigrams. The full local trigram checkpoint retains 62,357,916 triples observed at least twice and 40,423,307 full prefix totals, including singleton contributions. Local assets are approximately 464 MiB (bigram) and 1,176 MiB (trigram). Model weights are unchanged.

The Space has a 1 GB file limit. Scorers are therefore hosted in a separate Hugging Face model repository and downloaded from a pinned revision at startup, outside timed inference. The deployed trigram checkpoint retains **all 62,357,916 triples with count >=2**, and their 11,531,371 required contexts. Full context totals include singleton contributions. Removing unused contexts preserves exact corrections while shrinking this checkpoint to approximately 846 MiB. Bigram minimum count remains one; trigram minimum count is two. See [compaction.json](compaction.json) for 30,004 full-versus-compact correction checks. Raw aggregate counts also retain singleton triples for future experiments.

## Interface and scoring

The LLaDA Space gains an **N-gram guidance** dropdown: **Original bigram** (default), **Expanded bigram**, and **Expanded bigram + trigram**. Keeping both bigram choices lets users distinguish the corpus change from the extra trigram term. Independent diffusion ignores this setting.

The optional score is:

`sum log p_DLM + w sum PMI_bigram + 0.5 w sum delta_trigram - repetition_penalty`

`delta(a,b,c) = log P(c|a,b) - log P(c|b)`

`P(c|a,b) = [count(a,b,c) + 50 P(c|b)] / [count(a,b) + 50]`

The conditional backoff is the expanded bigram scorer's smoothed distribution. Trigram corrections require count >=2 and are clipped to [-2,2]. Unseen and singleton triples receive zero correction, preserving bigram backoff. Parameters are editable constants in app.py. Bigram weight zero disables both terms. Sequence temperature scales the complete sampling objective.

Exact second-order dynamic programming uses candidate pairs as states. Candidate dimensions are vectorized on the inference device; large top-k lookup batches are chunked. Complexity grows as O(B K^3), so parallel execution cannot guarantee unchanged latency. At B=64,K=16, the extra FP32 potential table is 1,015,808 bytes, excluding scorer tables and temporary buffers. Start with top-k 16.

Fixed positions remain singleton constraints. Trigrams are restricted to the current block; existing bigram boundary terms remain. Max decoding, exact sequence sampling, confidence margins and repetition-risk marginals include the trigram potentials. Existing repetition modes, decay and APD compose with the option without additional model forwards. Blocks of length 1–2 have no trigram term.

## Validation

- Focused tests: **33 passed**, including exhaustive small-lattice paths/marginals, sampling frequencies, fixed positions, zero-weight equivalence, numerical stability, chunked lookup equivalence, UI routing, APD/repetition composition, real external-count aggregation and rejecting thresholds below the stored counts.
- Full suite: **661 passed, 4 skipped, 3 pre-existing training-configuration failures**. Those failures concern unrelated training configuration expectations.
- Both full-size checkpoints loaded successfully with matching vocabulary, corpus size and tokenizer fingerprint; sample corrections were finite.
- `git diff --check` passed.

Local CPU microbenchmark (one thread, B=64,K=16,20 repetitions, precomputed random potentials):

| Decoder | Bigram median | Trigram median |
| --- | ---: | ---: |
| Viterbi | 1.012 ms | 1.862 ms |
| Sequence sampling | 2.455 ms | 3.211 ms |

This isolates dynamic programming and excludes sparse scorer lookups, model inference and GPU execution. See [dp_cpu_benchmark.json](dp_cpu_benchmark.json). Hosted measurements are required to establish practical overhead.

## Hosted validation and speed

All **14 timed runs passed**, each with exactly eight diffusion-model forwards and eight selector calls. Original bigram also reproduced the previously saved regression output exactly on the final deployment; see [original_verification.json](original_verification.json).

Settings: Amsterdam prompt, seed 1234, max length/block length 64, eight denoising steps, top-k 16, bigram weight 1, temperature 1, APD OFF, ending delay OFF and early stopping OFF. Trigram relative weight is 0.5, minimum count two and clip ±2. Asset downloads/loading and initial warmup are excluded. Max Viterbi and sequence sampling use two timed repeats each; sampling with repetition risk and fade uses one per expanded scorer. Times below are server inference medians, excluding client/network/queue overhead. Selector timings synchronize CUDA.

| Mode | Original bigram | Expanded bigram | Expanded + trigram | Trigram overhead versus expanded bigram |
| --- | ---: | ---: | ---: | ---: |
| Max Viterbi | 302.3 ms | 303.0 ms | 321.1 ms | +6.0% |
| Sequence sampling | 383.2 ms | 376.7 ms | 405.6 ms | +7.6% |
| Sampling + repetition risk + fade | — | 478.8 ms | 504.4 ms | +5.3% |

| Mode | Expanded bigram selector / forward | Expanded + trigram selector / forward |
| --- | ---: | ---: |
| Max Viterbi | 5.74 ms | 7.61 ms |
| Sequence sampling | 15.19 ms | 18.72 ms |
| Sampling + repetition risk + fade | 28.02 ms | 31.12 ms |

Raw outputs, settings and timings: [hosted_speed.json](hosted_speed.json), [speed_summary.json](speed_summary.json). These few runs establish compatibility and approximate overhead at K=16; they do not estimate a robust hardware-independent speed difference or show scaling at larger K. Warm startup downloads are larger with external scorers, and GPU memory usage also increases.

APD ON smoke checks at aggressiveness 0.5 completed both ordinary confidence-guided decoding (seven forwards) and sampled trigram decoding with repetition risk and fade (six forwards), within the eight-step budget. Both resolved the block without leftover masks; trigram selector calls equaled actual model forwards. See [apd_compatibility.json](apd_compatibility.json). These individual APD runs are compatibility checks, not matched quality/speed comparisons.

Example outputs for the identical Amsterdam prompt and seed:

- Max Viterbi, all three scorers: “Amsterdam is the capital and largest city of the Netherlands.”
- Original bigram sampling: “Amsterdam is the capital of the Netherlands and is known for its vibrant history, canals, and vibrant nightlife.”
- Expanded bigram sampling: “Isterdam is the capital of the Netherlands.”
- Expanded bigram + trigram sampling: “Amsterdam is the capital of the Netherlands.”

These examples show that expanding the corpus can also worsen individual generations. This is a speed/compatibility check, not a generation-quality study. More context statistics may improve local phrasing but do not verify facts or relevance to a question. Keep the original scorer available for comparisons and evaluate multiple prompts/seeds before drawing quality conclusions.
