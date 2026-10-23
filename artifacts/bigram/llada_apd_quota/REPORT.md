# APD minimum commitment quota per step

Deployed to [Ruurd/llada-8b-instruct](https://huggingface.co/spaces/Ruurd/llada-8b-instruct)
only. With APD ON, each block commits at least
`min(remaining_masked, ceil(block_length / allocated_block_steps))` rows per pass.
A 64-token block with 16 iterations commits at least 4 each pass; a 65-token block
has minimum 5 until fewer remain. This is a fixed per-step floor, not a cumulative
catch-up target that becomes smaller after an above-quota step.

## Selection and compatibility

1. Run the existing standard or sequence decoder and gather confidence in the
   selected token, unchanged by this feature.
2. Commit every threshold-qualified pending row under the existing ending-delay
   guard. The APD aggressiveness slider continues to set that threshold.
3. Fill any quota shortfall with highest-confidence remaining rows. Fixed rows
   cannot be selected. Finite scores rank ahead of nonfinite scores; stable
   ordering preserves deterministic tied-score fallback.
4. If ending retention is delayed, fill ordinary predictions first. Only fill
   endings once every pending ordinary row is selected in that step.
5. Keep final cleanup and early completed-block exit. Given the fixed minimum,
   the final pending count is at most the quota; no large low-confidence tail
   accumulates for the last step. Short/unequal blocks use their own length and
   allocated step budget. No new UI control is needed.

APD OFF remains unchanged. At aggressiveness zero, the original threshold curve
remains but this mandatory minimum intentionally changes commitment behavior.
The previous claim of identical full APD behavior at zero is historical. Scoring,
PMI, sampling, repetition risk/count modes and fading, ending-score adjustment,
retained constraints and APD aggressiveness are unchanged. There are no extra
model forwards, training changes or external scorer calls. Other Spaces were
not deployed.

## Local verification

22 new tests pass: low-confidence quotas at 64/16, 128/8, 65/16, 7/3, 3/8 and
1/1; no final pileup; more-than-quota commitments; best-confidence selection;
ending delay; nonfinite scores; fewer remaining rows; invalid quota inputs; and
actual native/adapter inference with standard, PMI, repetition, margins, sampled
risk+decay, unequal blocks and one model pass per step. Updated two prior low-
confidence tests to expect the intentional 2+2+1 pattern at length 5, NFE 3,
instead of the former 1+1+3.

113 focused tests passed. Full suite: 629 passed, 4 skipped and the same three
pre-existing training-config failures, with no new failures. APD OFF regression
and zero-default aggressiveness comparisons still pass.

Parent revision: `24666c5423a21f56df4cf18413276e6eb7dd5ef6`. Deployment: `942fb38c052759806f980b24ea8d4e231330bc54`.

## Hosted verification

Eight live cases passed, checking every streamed commitment count rather than
only the final output. Standard decoding at length 64, NFE 16, aggressiveness 0
commits exactly `[4,4,4,4,4,4,4,4,4,4,4,4,4,4,4,4]`, confirming the requested
minimum under actual model outputs. All methods meet their block-local floor,
with the last partial remainder capped by available masked rows. Threshold-based
commitments can exceed the floor and finish a block earlier.

The bound on remaining masks applies to the scheduled final iteration. An earlier
completed block can have a larger last commitment group if it meets threshold;
for example max-path risk decoding ends at step 13 after committing 11 qualified
rows. This is allowed parallel commitment, not deferral to mandatory final cleanup.

The unequal 65-token block at 16 NFE has quota 5 and completes in 13 passes.
With 65 tokens split into blocks 32/32/1, the assigned budgets are 6/5/5 and
quotas 6/7/1; the last block finishes in its first pass, giving 12 total forwards.
APD OFF exactly matches the pre-deployment output. Every case resolves masks and
reported/streamed forward counts match and stay within the configured NFE budget.
These are functional checks on one prompt/seed, not a representative quality study.
Repetition, punctuation and factual mistakes remain in some outputs; no universal
quality or speed improvement is established by the quota guarantee.

| Case | Actual forwards | Per-step commitments |
|---|---:|---|
| apd_off_unchanged | 16 | APD OFF |
| standard | 16 | 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4 |
| standard_aggressive | 6 | 23, 24, 7, 4, 4, 2 |
| risk_viterbi | 13 | 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 9, 4, 11 |
| risk_sampling | 16 | 4, 4, 4, 6, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 2 |
| risk_sampling_aggressive | 15 | 4, 4, 4, 8, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4 |
| uneven_length | 13 | 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5 |
| uneven_blocks | 12 | 6, 6, 6, 6, 6, 2, 7, 7, 7, 7, 4, 1 |

## Recorded outputs

### apd_off_unchanged

Amsterdam is the capital and largest city of the Netherlands. It is known for its picturesque canals, historic architecture, art museums, and vibrant nightlife.

### standard

Amsterdam is the capital and largest city of the Netherlands. It is known for its architecture, museums, canals, and vibrant cultural scene. Amsterdam is also a center for education, finance, and education. It has home to many famous figures such as Van Gogh, Rembrandt, and Anne Frank.

### standard_aggressive

Isterdam is a city city the Netherlands, it of the, capital of, culture, art, history, culture, history, cuisine, art, fashion, nightlife,, etc.

### risk_viterbi

Amsterdam is the capital and largest city of the Netherlands.

### risk_sampling

Amsterdam is a beautiful and vibrant city in the Netherlands. It's known for its picturesque canals, historic architecture, and rich culture. The city is home to many famous landmarks, museums, and galleries,. It's also famous for its nightlife,, which are among the safest and energetic in the world.

### risk_sampling_aggressive

Amsterdam is a beautiful and vibrant city in the Netherlands. It's known for its stunning architecture, picturesque canals, and rich history.. It's also home to numerous landmarks, museums, and parks.. Additionally, Amsterdam is famous for its vibrant culture scene, including art, music, and food festivals.

### uneven_length

Amsterdam is the capital and largest city of the Netherlands. It is known for its picturesque canals, museums, historic architecture,, and vibrant nightlife. The city has a rich history and is also known for its art, culture, and cultural scene. It is a popular destination for tourists, artists, and artists.

### uneven_blocks

Amsterdam is the capital of the Netherlands and is known for its vibrant history, picturesque canals, museums and nightlife. It is a home to the famous museums and landmarks such as Van Van Gogh Museum, Anne Frank House Anne Frank House, themuseummmuseum and Museum of the famous Anne Frank House.

