# LLaDA BG+TG decoding speed check

Small matched screen on `Ruurd/llada-8b-instruct`: two open questions, two coding tasks, and two math tasks at NFE 8, 32, and 64. Max output/block length 128; seed 42; temperature 0.7; deterministic MAP; bigram weight 1; trigram weight 0.5; PMI min-count 1/clip 2; trigram min-count 2/clip 2. Repetition penalty, APD, sequence sampling, revisable tokens, and early stopping OFF. Open answers use EOS delay with strength 10; coding/math disable it. All measured runs used their exact requested NFE.

Each version has 18 primary cases plus six extra timing repeats: three runs total for one prompt per domain at NFE 32. A short warmup is excluded. Server elapsed times exclude HTTP/queue delays; selector time is the app's decoding metric. All raw responses, settings, hashes, metrics and deployed revisions are saved alongside this report.

## Recommendation and deployed result

Keep top-k **16**. The CPU MAP version reduced primary-case mean server time from **1790.0 ms to 1504.9 ms (15.9% less elapsed time)**, with selector time down **59.8%**. All **24/24** K16 outputs, including repeats, matched the original exactly. K8 on the same implementation averaged **1438.9 ms**, another **4.4%** less than optimized K16. This small extra saving came with changed text and one lost correct math answer in this screen. K8 CPU results also matched all **24/24** device K8 results, further checking that changing the recurrence device preserves its decisions.

The optimized module is live at revision `aee543d748b7250f21d01f462b8fb36ae783eb04`. Top-k, temperature, scoring weights and all interface defaults were left unchanged. The small speed screen supports this implementation improvement; it does not establish that K8 is better or that CPU decoding will be faster on every hardware/batch/length combination. Larger candidate pools retain the GPU path. Positive-temperature BG+TG sequence sampling was **not** optimized in this task.

## Primary timing results

| Version | Total mean (ms) | Selector mean (ms) | Total reduction vs original | Identical answers |
|---|---:|---:|---:|---:|
| Original K16 | 1790.0 | 497.4 | 0.0% | 18/18 |
| Factored scorer K16 | 1752.1 | 478.0 | 2.1% | 18/18 |
| Factored scorer K8 | 1846.8 | 535.9 | -3.2% | 11/18 |
| CPU MAP K16 | 1504.9 | 200.1 | 15.9% | 18/18 |
| CPU MAP K8 | 1438.9 | 147.6 | 19.6% | 11/18 |

All timings are measured sequentially on shared ZeroGPU hardware, so small differences are not reliable speedups. K8 reduces the nominal trigram table from 516,096 entries to 64,512 per 128-token block (8×), but does not reduce the 126 sequential recurrence steps. Lower memory/arithmetic cost does not imply an 8× end-to-end speedup.

| Version | NFE 8 total/selector (ms) | NFE 32 total/selector (ms) | NFE 64 total/selector (ms) |
|---|---:|---:|---:|
| Original K16 | 414.5/109.1 | 1644.7/449.6 | 3310.9/933.5 |
| Factored scorer K16 | 424.3/115.6 | 1600.7/426.7 | 3231.2/891.8 |
| Factored scorer K8 | 434.7/121.7 | 1700.1/492.2 | 3405.5/993.6 |
| CPU MAP K16 | 366.7/49.8 | 1367.1/178.1 | 2781.0/372.4 |
| CPU MAP K8 | 331.8/34.6 | 1336.8/137.3 | 2648.0/271.0 |

## Quality screen

Manual judgments reuse the previous study rubric and exact-text reviews: open quality 0–3; math answer correctness requires score ≥2 (3 also requires correct explanation). Newly seen texts were reviewed without stage/NFE labels. Code uses the previous restricted executable tests and prompt constraints. Repeated runs are excluded from quality counts. These are six cases per domain, from only two distinct prompts each: useful as a regression screen, insufficient to rank general quality.

| Version | Open quality /3 | Coding passes /6 | Math correct /6 |
|---|---:|---:|---:|
| Original K16 | 2.17 | 2 | 4 |
| Factored scorer K16 | 2.17 | 2 | 4 |
| Factored scorer K8 | 2.17 | 2 | 3 |
| CPU MAP K16 | 2.17 | 2 | 4 |
| CPU MAP K8 | 2.17 | 2 | 3 |

K8 changed seven of the eighteen primary answers. Coding pass counts stayed the same. On the pipes question at NFE 8, K16 correctly concluded two hours, while K8 stopped after the combined rate and omitted the requested filling time. Other changes traded fluency and detail. This screen does not support promising unchanged quality from reducing K.

## Repeated timing checks

| Version | Amsterdam median [min,max] ms | Balanced brackets median [min,max] ms | Mean problem median [min,max] ms |
|---|---:|---:|---:|
| Original K16 | 1644 [1627, 1658] | 1720 [1658, 1721] | 1680 [1656, 1705] |
| Factored scorer K16 | 1610 [1597, 1631] | 1580 [1568, 1620] | 1617 [1608, 1648] |
| Factored scorer K8 | 1755 [1750, 2531] | 1674 [1672, 1678] | 1678 [1652, 1685] |
| CPU MAP K16 | 1360 [1353, 1363] | 1371 [1371, 1379] | 1373 [1363, 1383] |
| CPU MAP K8 | 1317 [1316, 1322] | 1344 [1320, 1440] | 1327 [1316, 1340] |

## Implementation and validation

- The first optimization factors trigram prefix/backoff lookups from K³ to K², retaining the full triple lookup. GPU traceback uses tensor gathers to avoid scalar index synchronization. It reproduced all 24 original K16 outputs, but the approximately 2% mean total improvement is too small to call a useful speedup.
- The second optimization runs the deterministic small-chain MAP recurrence on CPU, after normalization on the original device and one packed host transfer. It preserves float32 addition order, max reduction and first-index tie breaking, then returns only the selected indices to the GPU. CUDA lattices up to 256 positions and K≤16 use this path; larger lattices and positive-temperature sequence sampling retain their existing route. No model weights, score formulas, generation defaults or number of forward passes change.
- Local validation: 136 passed, six CUDA-only cases skipped because this workstation has no CUDA. Tests cover direct versus factored counts, fixed positions, exhaustive best paths and ties, random lattices up to 256×16, numerical extremes, sampling distributions, shared controls and integration without extra model forwards. Hosted exact-output checks supplement the local tests; they are not exhaustive GPU numerical equivalence proofs.

## Revisions and reproducibility

- Original K16: `b31a17ae5d4b017ffad71798ea5f35949416e4d2`.
- Factored scorer K16: `945f6480fc0ce5f42f660a3cc803700de001ce0d`.
- Factored scorer K8: `945f6480fc0ce5f42f660a3cc803700de001ce0d`.
- CPU MAP K16: `aee543d748b7250f21d01f462b8fb36ae783eb04`.
- CPU MAP K8: `aee543d748b7250f21d01f462b8fb36ae783eb04`.

The earlier 1,974-output study and its pinned revision/data are unchanged. `before.jsonl` and `after_*.jsonl` contain every output; `summary.json` and `cases.csv` contain calculated metrics; `reviews.json` and `code_checks.json` retain judgments. Timing repeats remain separate from primary quality results. Historical CPU microbenchmarks in this folder are diagnostic, not substitutes for these hosted measurements.
