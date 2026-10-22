# APD implementation and live checks

APD is live and defaults OFF on Ruurd Gemma and native LLaDA. It is a separate commitment layer after the selected decoder; sampling, conditional/PMI transition scores and repetition penalties remain unchanged. No model weights or dependencies were changed.

## Algorithm

For a block with S>1 planned steps, use progress t/(S-1), warmup w=0.15, u=max(0,(progress-w)/(1-w)), and threshold 0.50 + 0.20*(1+cos(pi*u)). Thus the first/last thresholds are exactly 0.90/0.50. A one-step block uses 0.50 and final cleanup. This is the requested fixed-endpoint subset inspired by [CAI-dLLM, Box 3](https://arxiv.org/pdf/2608.22646), rather than its full controller.

Each iteration commits every pending selected token meeting the threshold using its original full-vocabulary model probability. Viterbi confidence is for its selected ID, rather than argmax or path margin. Ordinary predictions are prioritized when EOS/EOT retention delay is on. If no token qualifies, commit the highest-confidence pending candidate; the final planned block step resolves all remaining masks. A rare MASK-selection validity fallback uses the same logits to select a legal non-mask token. Committed values are fixed; completed blocks stop independently of the legacy convergence checkbox. Whole-answer EOS/EOT stopping remains controlled by Early stopping.

APD overrides retention policies under Random/AR confidence and disables revision of committed tokens. It does not invoke the optional AR confidence forward; standard sampling is unchanged. No per-token budgets, position factors, first-step difficulty controller, or grinding-phase detection is implemented.

## Validation

Local APD tests: 38 passed, covering both adapter/native forward paths, all existing methods, Viterbi-selected confidence, path-margin independence, fallback progress, MASK validity, block/final-step completeness, ending behavior, unchanged OFF traces and absence of additional AR/model forwards. Existing relevant inference tests also passed. Full suite: 514 passed, 4 skipped, with the same three pre-existing training-config assertion failures.

Live checks: one Amsterdam prompt, seed 1234, 16-token maximum, two 8-token blocks, 16 total planned denoising evaluations, temperature 2, top-k 16, delayed endings enabled, ending strength 10, and legacy early stopping OFF. Repetition strength is 1 where applicable. These tiny capped answers test integration and completeness, not answer quality.

All 22 ON/OFF checks completed. All 11 OFF outputs match their saved pre-deployment outputs exactly. Final visible output contains no MASK placeholders. Denoising-forward counts are bounded by the original budget. Sampling/Random/AR are equivalent retention policies under APD given the same sampling settings; AR has additional confidence passes only when APD is OFF.

## Forward counts and latency

One short standard-decoding warmup per model was discarded. Server time is measured inside the GPU-decorated generator after selector initialization; it excludes queue/allocation and initial scorer loading, and includes rendering/profiling overhead. Client wall time, including queueing, is retained in JSON. Each table entry is a single run, not a latency estimate with uncertainty; ZeroGPU conditions varied markedly.

| Model | Method | Forwards OFF → ON | Server ms OFF → ON |
|---|---|---:|---:|
| Gemma | Confidence-guided | 16 → 16 | 904 → 815 |
| Gemma | Conditional Viterbi | 16 → 13 | 814 → 661 |
| Gemma | PMI Viterbi | 16 → 12 | 820 → 614 |
| Gemma | PMI + repetition | 16 → 12 | 851 → 602 |
| Gemma | Random retention | 16 → 16 | 795 → 764 |
| Gemma | AR confidence | 16 → 16 | 985 → 772 |
| LLaDA | Confidence-guided | 16 → 13 | 464 → 392 |
| LLaDA | Conditional Viterbi | 16 → 15 | 509 → 454 |
| LLaDA | PMI Viterbi | 16 → 13 | 1010 → 975 |
| LLaDA | PMI + repetition | 16 → 13 | 1104 → 987 |
| LLaDA | Random retention | 16 → 13 | 1022 → 948 |

PMI and PMI + repetition reduced denoising evaluations from 16 to 12 on Gemma and from 16 to 13 on LLaDA in this single example. Standard sampling used the full budget on Gemma. These results verify operation and show possible step savings; they do not establish general speed or quality preservation.

## Deployment revisions

| Space | Revision |
|---|---|
| [Ruurd/byod-gemma-2-9b](https://huggingface.co/spaces/Ruurd/byod-gemma-2-9b) | `1f739e48ed998a6b2d682efff479eb0b3fc5f500` |
| [Ruurd/llada-8b-instruct](https://huggingface.co/spaces/Ruurd/llada-8b-instruct) | `1473488432400a2509e118f3aacc16e18f9dd6ba` |

Raw records: `before.json`, `prepared.json`, `deployment.json`, `hosted_verification.json`. Shared implementation: `src/diffusion_lm/apd.py`, opt-in integration in `inference.py`, and the checkbox in `huggingface/byod_space/app.py`.

## Saved outputs

### Ruurd/byod-gemma-2-9b / Confidence-guided / APD OFF

```text
Amsterdam is a city located in the Netherlands, which is the capital of the Netherlands
```

### Ruurd/byod-gemma-2-9b / Confidence-guided / APD ON

```text
Amsterdam is the capital of Netherlands, one of the most popular cities in the world
```

### Ruurd/byod-gemma-2-9b / Conditional Viterbi / APD OFF

```text
It is the capital of the Netherlands, and is known for its canals, museums
```

### Ruurd/byod-gemma-2-9b / Conditional Viterbi / APD ON

```text
It is the capital of the Netherlands, and is known for its canals, museums
```

### Ruurd/byod-gemma-2-9b / PMI Viterbi / APD OFF

```text
Amsterdam is the capital of the Netherlands, and is known for its canals, museums
```

### Ruurd/byod-gemma-2-9b / PMI Viterbi / APD ON

```text
Amsterdam is the capital of the Netherlands, and is known for its canals, museums
```

### Ruurd/byod-gemma-2-9b / PMI + repetition / APD OFF

```text
Amsterdam is the capital of the Netherlands, and is known for its canals, museums
```

### Ruurd/byod-gemma-2-9b / PMI + repetition / APD ON

```text
Amsterdam is the capital of the Netherlands, and is known for its canals, museums
```

### Ruurd/byod-gemma-2-9b / Random retention / APD OFF

```text
Amsterdam's the a major hub of business and is well to a bike system
```

### Ruurd/byod-gemma-2-9b / Random retention / APD ON

```text
Amsterdam is the capital of Netherlands, one of the most popular cities in the world
```

### Ruurd/byod-gemma-2-9b / AR confidence / APD OFF

```text
Amsterdam is a major capital city and the center- city of Netherlands. It is
```

### Ruurd/byod-gemma-2-9b / AR confidence / APD ON

```text
Amsterdam is the capital of Netherlands, one of the most popular cities in the world
```

### Ruurd/llada-8b-instruct / Confidence-guided / APD OFF

```text
I don't know anything about it. I'm eager to learn.
```

### Ruurd/llada-8b-instruct / Confidence-guided / APD ON

```text
I don't know anything about it. How can I assist you?
```

### Ruurd/llada-8b-instruct / Conditional Viterbi / APD OFF

```text
I don't have personal experiences, but I can provide information about it.
```

### Ruurd/llada-8b-instruct / Conditional Viterbi / APD ON

```text
I don't have personal experiences, but I can provide information about it.
```

### Ruurd/llada-8b-instruct / PMI Viterbi / APD OFF

```text
I don't have personal experiences, but I can provide information about Amsterdam.
```

### Ruurd/llada-8b-instruct / PMI Viterbi / APD ON

```text
I don't have personal experiences, but I can provide information about Amsterdam.
```

### Ruurd/llada-8b-instruct / PMI + repetition / APD OFF

```text
I don't have personal experiences, but I can provide information about Amsterdam.
```

### Ruurd/llada-8b-instruct / PMI + repetition / APD ON

```text
I don't have personal experiences, but I can provide information about Amsterdam.
```

### Ruurd/llada-8b-instruct / Random retention / APD OFF

```text
I never end up with that place and instead stayed in your beautiful city.
```

### Ruurd/llada-8b-instruct / Random retention / APD ON

```text
I don't know anything about it. How can I assist you?
```
