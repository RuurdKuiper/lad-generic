# Simplified BYOD interface rollout

Complete on all eight Gemma, Llama, Qwen and Ministral demos across Ruurd and Dovelove. Each exposes Confidence-guided and BG + TG Viterbi (Gumbel), defaulting to the guided method. Temperature defaults to 0.7; zero is deterministic. Bigram weight defaults to 1 and remains independent of temperature. APD, early stopping and EOS/EOT retention are retained. Ending-delay strength is fixed to 10. Research controls, repetition strategies, checkpoint paths and evaluation sections are hidden.

## Model-specific scorer training

Each model uses its own exact tokenizer and padded output vocabulary. Trigram counts were built from all 980,000 original response-training documents with the original EOS/truncation policy. Reconstructed bigrams and unigrams match the existing deployed scorer exactly for every model. Counts never cross document boundaries. Full context totals include singletons; stored triples retain count>=2, correction clipping is ±2 and relative trigram weight is 0.5. These use the original BYOD response corpus, rather than the larger expanded English/code/math corpus used in the LLaDA study.

| Model | Training tokens | Retained triples | Matching bigram counts |
|---|---:|---:|---|
| gemma | 73,467,371 | 5,234,558 | Exact |
| llama | 71,088,258 | 5,746,261 | Exact |
| qwen | 72,705,486 | 5,600,583 | Exact |
| ministral | 73,214,218 | 5,609,705 | Exact |

## Deployment and checks

| Space | Two-method UI | Confidence smoke | BG+TG smoke |
|---|---|---|---|
| [Ruurd/byod-gemma-2-9b](https://huggingface.co/spaces/Ruurd/byod-gemma-2-9b) | Verified | Complete | Complete |
| [Ruurd/byod-llama-3.1-8b](https://huggingface.co/spaces/Ruurd/byod-llama-3.1-8b) | Verified | Complete | Complete |
| [Ruurd/byod-qwen2.5-7b](https://huggingface.co/spaces/Ruurd/byod-qwen2.5-7b) | Verified | Complete | Complete |
| [Ruurd/byod-ministral-8b](https://huggingface.co/spaces/Ruurd/byod-ministral-8b) | Verified | Complete | Complete |
| [Dovelove/byod-gemma-2-9b](https://huggingface.co/spaces/Dovelove/byod-gemma-2-9b) | Verified | Complete | Complete |
| [Dovelove/byod-llama-3.1-8b](https://huggingface.co/spaces/Dovelove/byod-llama-3.1-8b) | Verified | Complete | Complete |
| [Dovelove/byod-qwen2.5-7b](https://huggingface.co/spaces/Dovelove/byod-qwen2.5-7b) | Verified | Complete | Complete |
| [Dovelove/byod-ministral-8b](https://huggingface.co/spaces/Dovelove/byod-ministral-8b) | Verified | Complete | Complete |

Local tests: 243 passed, six CUDA-only cases skipped on this workstation. The live checks verified interface choices, hidden/retained controls, scorer defaults and preserved model/account configuration. Sixteen short 16-token, two-step generations exercised both methods on every Space; all finished with exactly two model forward passes and no unresolved masks. These are compatibility checks, not a comparative quality study.

No diffusion model weights were trained or changed. Each Space retains its existing model repository, links, visitor counter, visibility and credentials. The original bigram.pt files remain untouched. New scorer files are tokenizer-specific.

## Restoring research options

Set SHOW_LEGACY_DECODING_CONTROLS=True in app.py and redeploy to restore the old interface. The decoding implementations remain in the shared source. The model-backend flag is independent of the n-gram capability: BYOD models still run through their original BYOD inference path.

## Artifacts

- prepared.json records guarded parent revisions and prepared source/scorer hashes.
- deployment.json records the eight new revisions.
- hosted_verification.json retains the tiny smoke outputs and forward counts.
- scorer_verification.json checks the actual scorer files, fixed tokens and temperature-zero determinism.
- summary.json records final defaults and completion.
- ../byod_trigrams/<model>/complete.json records training provenance and exact-count verification.
