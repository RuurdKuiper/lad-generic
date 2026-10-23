# LLaDA: independent bigram weight and sequence temperature

Live on [Ruurd/llada-8b-instruct](https://huggingface.co/spaces/Ruurd/llada-8b-instruct).
Other Spaces were not deployed. This supersedes temperature-dependent PMI weighting
for this Space only; historical experiment formulas remain historical.

## Scoring and controls

`S(y) = sum(log p_t(y_t)) + w*sum(PMI(y_t,y_(t+1))) - gamma*sum(C_t)`.

- Bigram weight w ranges 0–5, default 1. Weight 1 means equal coefficients,
  not necessarily equal numerical influence; zero disables PMI only.
- With sequence sampling ON, `P(y) ∝ exp(S(y)/T)`. Temperature controls global
  sequence entropy rather than the relative scoring weights. T=0 chooses the
  maximum-score path. Positive T is floored at 1e-6 for numerical stability.
- Maximum-path Viterbi ignores temperature. Standard diffusion retains its
  existing temperature behavior. Top-k still chooses the candidate lattice.
- Default T=1 and w=1 represent the previous default score/distribution at
  T=2, fixed weight 0.5. Live examples exactly reproduce those outputs.
- Expected counts, APD and retention confidence still use full-vocabulary model
  probabilities before sequence temperature. EOS/EOT exemption, fixed positions,
  APD compatibility, no-extra-forward behavior and optional candidate counts remain.

## Unseen pairs and weak early repetition corrections

PMI assigns unseen pairs correction 0: neutral multiplicative factor 1, not
zero probability or forbidden transitions. Conditional mode uses unigram smoothing
to yield finite log probabilities. In PMI mode, low-count pairs are also neutral,
and eligible PMI corrections are clipped to [-2,2] under current settings.

Expected repetition counts use `C_t(a,b)=sum_(s<t) p_s(a)*p_(s+1)(b)` and subtract
`gamma*C_t`. Early diffuse predictions can give tiny counts: two 0.01 candidates
contribute 0.0001, yielding a 0.001 log correction at gamma=10 for that prior
occurrence. This does not count repetitions in the actually selected path. The
penalty was not changed as part of this control separation.

## Verification

Full suite: 537 passed, 4 skipped, and the same three pre-existing training-config
failures. Updated the former fixed-weight UI assertion to check native LLaDA's
new adjustable coefficient and the unchanged non-native backend. Statistical
tests check exp(S/T) against enumerated distributions at T=0.4 and T=2, zero-T
maximum-path behavior, unmodified scoring weights across temperatures, raw token
confidence, independent Viterbi, and finite/unseen scoring. Prior repetition,
APD and fixed-token tests also pass.

Nine live cases pass: correct slider range/defaults, old/default-equivalent
maximum and sampled paths, temperature-zero equivalence, expected-penalty
output equivalence, no unresolved masks, and exactly one model pass per case.
Single-prompt smoke outputs below do not establish quality improvements.

Parent: `a9be260175255963c01e91c05eb5c5074b9fa331`. Deployment: `35914ffa96f3e2687f06de44f1dee45078f61d8a`.

## Outputs

### default_viterbi

Amsterdam is the city of the city of the city known for its history, and canals, and canals, and canals, you know about it?

### default_sampler

I'm so the city of the history with rich and its city of canals canals of its culture history history for something with something you in the city?

### sampler_zero_temperature

Amsterdam is the city of the city of the city known for its history, and canals, and canals, and canals, you know about it?

### viterbi_temperature_zero

Amsterdam is the city of the city of the city known for its history, and canals, and canals, and canals, you know about it?

### sample_other_seed

Amsterdam is a city beautiful about that information Netherlands., vibrant and its rich know beautiful city known city, you with.

### sample_low_temperature

Amsterdam is the city of the city,, and its history, and its history, and its history, you would like you about the city?

### sample_weight_zero

I'm knowledge to in. you. with to on its in of canals the, It the history. specific and with the you

### sample_weight_five

I'm so the city of the city known for its rich in a specific cultural history of the vibrant history? I do you like you with its culture.

### expected_penalty

Amsterdam is the city of the city of the city known for its history, and canals, and canals, you would like you know about it?

