# Optional PMI Viterbi in the original LAD Space

Deployed to [Ruurd/lad](https://huggingface.co/spaces/Ruurd/lad), revision
`9f8b90edf869473ed00a4b14c1237fa51decff4b`, updating original revision `ffb072132fa8a88b47d022e7739e1ec3ff175900`.
The original model checkpoint and Space configuration were retained.
Source lives in `huggingface/lad_space`; publish with
`huggingface/publish_lad_viterbi.py` and verify with
`scripts/verify_lad_viterbi.py`.

## Correction semantics and defaults

LAD predicts corrections for every answer token at every iteration. Viterbi
therefore leaves every answer row editable, even without explicit re-noising
and even when the permanent-unmasking option excludes tokens from re-noising.
The prompt remains fixed and supplies left-boundary context. This differs from
the BYOD app, where previously retained tokens constrain the Viterbi path.

Sampling remains the default, with temperature 1 and top-k 3. Choosing PMI
Viterbi sets temperature 2 and candidates 16. Weight is fixed at 0.5, PMI minimum
count 1, clipping ±2; top-p is disabled for Viterbi. No extra forwards or scorer
training are required. The original EOS-bias control remains available; BYOD's
additional fading ending-delay penalty is not applied to this correction loop.
For direct correction without re-noising, set Noise start fraction to zero.

The BYOD-Llama scorer fingerprint matches the Space's
`meta-llama/Llama-3.2-3B` tokenizer exactly: 128,256 IDs. It uses all 980,000
BYOD training responses, rather than claiming to retrain on the paper's corpus.
Statistics and source remain available in `../llama.json`.

The integration also fixes confidence-guided noising to read answer-position
confidences rather than prompt positions and escapes generated text for HTML
rendering. At the existing sampling defaults, seeded selection still matches
the original sampler exactly when confidence-guided noising is off.

## Validation

- Local decoder/integration checks: 107 passed, 2 CUDA-only skips.
- Full suite: 393 passed, 3 skipped; the same 3 pre-existing training-config
  assertion failures reproduced before this change.
- Five successful live checks at 4 iterations: sampling without re-noising;
  Viterbi without re-noising; Viterbi with confidence-guided re-noising;
  Viterbi with confidence-guided/permanent unmasking; and Viterbi with
  uniform/permanent unmasking. Each completed all four prediction steps.
- Local tests verify visible-token correction without masks, fixed prompt
  boundaries, greedy limits, full-vocabulary confidence, correct confidence
  indexing, and one forward per iteration.

Saved records: `tokenizer_validation.json`, `deployment.json`,
`original_api.json`, `original_smoke.json`, `hosted_verification.json`, and
`interface_verification.json`. These are integration checks, not a quality
benchmark. Four-step Viterbi samples still show repetitions and factual errors;
no quality improvement is established by this smoke test.

## Repetition-penalty extension

The initial integration record above describes the first PMI deployment.
See [REPETITION_PENALTY.md](REPETITION_PENALTY.md) for the latest optional
probability-weighted repetition penalty, its deployment revision, and validation.

The current scoring formula is documented in
[TRANSITION_REPETITION_PENALTY.md](TRANSITION_REPETITION_PENALTY.md):
the repetition correction now applies directly to candidate transitions.
