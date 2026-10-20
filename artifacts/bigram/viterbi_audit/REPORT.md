# Viterbi implementation and quality audit

The temperature-aware Viterbi calculation matches the previous implementation at temperature 1 and an identical candidate count. The simplified interface's four hidden defaults match the requested PMI / diffusion probability / minimum count 1 / clipping bound 2. No new selector regression was found at the user's explicit temperature 1 and top-k 16 settings. This is a focused audit, not a repeat of the full 30-question benchmark.

## Findings and final changes

1. Merging controls unintentionally changed the default Viterbi candidate pool from 16 to 3. Temperature 0.7, previously ignored by Viterbi, also became an effective bigram weight of 0.35. The Gemma defaults are restored to temperature 1 and top-k 16. These defaults do not explain the user's explicitly supplied T1/K16 output.
2. Ending suppression affects both selection and the full-vocabulary probabilities used for diffusion-confidence retention. Earlier descriptions saying those were the original unmodified model probabilities were inaccurate when ending suppression was active. The documentation and interface description now state the actual behavior.
3. A proposed correction using probabilities before ending suppression was implemented, tested, and tried on the user's prompt. It worsened the 16-step answers and left the 32-step answers unchanged. That experimental behavior was reverted. The established inference implementation is restored byte-for-byte; the experimental patch and its deployment records remain available for review.
4. Temperature 2 doubles the effective transition weight from 0.5 to 1.0 and remains deterministic. It produced a cleaner 32-step Amsterdam answer in this check. Both temperatures still produced defects at 16 steps. The stronger-ending-delay checks were run on the experimental policy and only lengthened its weak 16-step outputs; they do not establish the effect under the retained policy.

Final deployment: `ec764e8524e9c26e379d94cb3ee08ad4bc017a7b` on `Ruurd/byod-gemma-2-9b`. Only app.py and inference.py were deployed during the audit; no model or bigram checkpoints were changed. The four PMI settings remain hidden and ending-delay strength stays adjustable.

## Correctness evidence

- Live app.py, inference.py, and bigram.py matched the workspace at the start of the audit.
- Forty selector comparisons against the pre-temperature implementation were bit-identical for both selected IDs and probabilities at T1. Coverage includes conditional and PMI scoring, float32 and BF16, block lengths 1–256, top-k 3/16, fixed tokens, and both boundary contexts.
- A previously saved hosted weather/climate answer at 64 steps was reproduced verbatim with T1/K16 and the original ending policy. Its result at the accidental T0.7/K3 defaults had repeated and malformed phrases.
- Final targeted validation: 190 tests passed, three CUDA-only tests skipped locally. Checks include exhaustive path objectives, temperature scaling, top-k, PMI safeguards, retained tokens, endings, and actual model-forward counts.
- The final retention regression test explicitly captures policy-adjusted full-vocabulary probabilities and retention order at ending strengths 1, 10, and 1000. This preserves established decoding behavior; it does not assert that this confidence policy is universally optimal.

## User-prompt reproduction

Prompt: What do you know about Amsterdam?

Common settings: 64 new tokens, one 64-token block, top-k 16, PMI minimum count 1, clip ±2, diffusion-probability retention, seed 42. Delayed retention and early stopping are on. Ending strength 10 is the current default and was assumed because the user did not specify its value. Requested budgets are 16/32 steps; actual calls are recorded in the raw data. Conditional scoring is included as a comparison with the former interface default, not as the user's confirmed earlier choice.

| Requested steps | Temperature | Established policy | Raw-confidence experiment |
|---:|---:|---|---|
| 16 | 1 | Repetition and malformed phrases | Worse; experiment reverted |
| 16 | 2 | More fluent than T1, still defective | Worse; experiment reverted |
| 32 | 1 | Mostly fluent; one of of repetition | Same output |
| 32 | 2 | Fluent generic answer | Same output |

These observations support the user's preference for T2 on this prompt, not a universal temperature recommendation or an explanation of a historical Amsterdam output that was not saved. The prior all-budget quality rankings should not be extrapolated to every prompt or new setting.

## Records

- [Verbatim Amsterdam outputs](answers.md)
- [Raw Amsterdam runs](amsterdam_comparison.jsonl)
- [Manual observations](manual_observations.json)
- [Initial source/default/parity checks](implementation_audit.json)
- [Historical hosted-output comparison](hosted_comparison.jsonl)
- [Experimental raw-confidence patch, reverted](unbiased_retention_experiment.patch)
- [Final deployment](deployment.json)
- [Final live verification](hosted_verification.json)
- [Final interface generation check](final_interface_smoke.json)
