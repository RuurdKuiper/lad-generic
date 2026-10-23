# Optional sequence sampling and candidate-occurrence counts

Deployed only to [Ruurd/llada-8b-instruct](https://huggingface.co/spaces/Ruurd/llada-8b-instruct).
Both new checkboxes default OFF. Existing decoding, temperature weighting, gamma
units, checkpoints and model settings are preserved. Gemma and LAD were not deployed.

## Behavior

- **Sample bigram-guided sequences**: exact forward-filter/backward sampling from
  `P(y) ∝ exp(S(y))`, using the existing complete-path score. PMI, diffusion,
  boundary scores and optional repetition penalties remain in the distribution.
  There are no random score perturbations or extra model calls. This applies to
  either bigram strategy; ordinary diffusion ignores it.
- **Count every candidate bigram occurrence**: in the repetition strategy,
  `C_t(a,b) = sum_{s<t} 1[a in K_s and b in K_(s+1)]`. Each earlier candidate-set
  occurrence contributes 1, regardless of probability. Duplicate dummy columns
  representing fixed tokens count once. Scoring precedes count updates. EOS/EOT
  pairs are excluded and counts reset every block/iteration. This counts candidate
  occurrences, not occurrences in the selected path.
- Each switch works independently, including with APD. The penalty remains
  `gamma*C`, subtracted in raw log-score units, rather than a percentage remapping.

## Validation

160 focused tests passed, 1 skipped. Full suite: 530 passed, 4 skipped, and the
same 3 pre-existing training-config failures, unrelated to decoding. Tests check
sampling frequencies against an enumerated joint distribution, bigram influence,
seed reproducibility/diversity, extreme log-scores, fixed tokens, EOS exemption,
probability-independent candidate counts, duplicate handling, zero-strength
identity, and APD combinations with one forward per iteration.

Eight live cases passed: both OFF outputs exactly match pre-deployment baselines;
same-seed sampling matches; all generations contain no unresolved masks; reported
forward counts match streamed steps and stay within the requested budget. These
are functional smoke checks, not a generation-quality benchmark. No universal
quality improvement is established. At top-k 100, gamma 10, counting all candidate
occurrences strongly penalizes common transitions even when they were never
selected, and the one-step examples become short/awkward. Sampling alone also
remains poor at this very low budget. EOS is exempt and can be selected early.

Parent revision: `1473488432400a2509e118f3aacc16e18f9dd6ba`. Deployed revision: `a9be260175255963c01e91c05eb5c5074b9fa331`.

## Recorded outputs

All cases ask “What do you know about Amsterdam?”, max length/block 32, T=2,
top-k=100, delay EOS OFF, early stopping OFF, seed 1234 unless specified.
Cases use 1 NFE, except APD uses 8.

### original

Amsterdam is the city of the city of the city known for its history, and canals, and canals, and canals, you know about it?

Denoising forwards: 1; server time: 609.0 ms.

### original_repetition

Amsterdam is the city of the city of the city known for its history, and canals, and canals, you would like you know about it?

Denoising forwards: 1; server time: 70.5 ms.

### sample

I'm so the city of the history with rich and its city of canals canals of its culture history history for something with something you in the city?

Denoising forwards: 1; server time: 137.4 ms.

### sample_repeat_seed

I'm so the city of the history with rich and its city of canals canals of its culture history history for something with something you in the city?

Denoising forwards: 1; server time: 37.7 ms.

### sample_other_seed

Amsterdam is a city beautiful about that information Netherlands., vibrant and its rich know beautiful city known city, you with.

Denoising forwards: 1; server time: 37.8 ms.

### candidate_counts

I don't capital city research and culture.

Denoising forwards: 1; server time: 54.1 ms.

### sample_candidate_counts

I'm so to share of data.

Denoising forwards: 1; server time: 39.5 ms.

### sample_candidate_counts_apd

I don't have personal experiences or desires,'ll help you try some-based information If you
 about attractions. aspect you get you explore you better?

Denoising forwards: 8; server time: 319.8 ms.

Timings are single trials with startup/warmup variation; no speed comparison is inferred.
