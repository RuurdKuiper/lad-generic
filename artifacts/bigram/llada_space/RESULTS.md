# Native LLaDA-Instruct Space

Created: [Ruurd/llada-8b-instruct](https://huggingface.co/spaces/Ruurd/llada-8b-instruct), public; anonymous access verified.

Loads the official GSAI-ML/LLaDA-8B-Instruct checkpoint directly in BF16, pinned to revision 08b83a6feb34df1a6011b80c3c00c7563e963b07. Uses the same interface and decoding policies, native LLaDA forward attention, chat template, and mask/EOT IDs. Scoring remains PMI, diffusion-probability retention, minimum count 1, clipping ±2, and shared temperature/top-k with fixed weight 0.5. The adapter-only autoregressive confidence strategy is hidden for this model.

A separate scorer was trained on all 980,000 existing training responses (77,064,287 LLaDA tokens; 5,109,347 pairs). It preserves document boundaries and covers all 126,464 model output IDs, with a verified tokenizer fingerprint. The padded vocabulary is larger than the 126,349 tokenizer entries.

Local validation: 193 tests passed with 3 CUDA-only skips; the LLaDA-specific suite then passed 5 tests, including two additional account/privacy guards. The official model code also passed a tiny CPU bidirectional forward test with Transformers 4.57.6. Live checks passed for confidence-guided generation, PMI generation, open-ended generation with nonzero PMI changes, and blockwise native-EOT stopping. No existing Spaces were updated.

The initial public upload was rejected by automatic approval review because public disclosure of the corpus-derived scorer was not explicitly authorized. The user subsequently explicitly approved public activation, including the scorer. The Space is now public, and anonymous access to its generation API has been verified.

Records: [deployment](deployment.json), [native compatibility](native_compatibility.json), [scorer validation](scorer_validation.json), [GPU smoke tests](hosted_verification.json), [open-ended and block tests](feature_smoke.json), [summary](result.json).
