# LAD: expanded BG + TG Gumbel decoding

The original [Ruurd/lad Space](https://huggingface.co/spaces/Ruurd/lad) now exposes **Sampling** and **BG + TG Viterbi (Gumbel)**. **Sampling is the default, at temperature 0.7**. BG+TG remains optional. Historical PMI-only and repetition strategies are retained in the implementation and can be restored in the UI with `SHOW_LEGACY_DECODING_CONTROLS=True`.

## Settings and behavior

- Temperature defaults to **0.7**. For BG+TG it scales unary Gumbel noise; zero chooses the deterministic best path for that inference pass. Ordinary Sampling keeps its existing temperature semantics. LAD noising can still introduce randomness between passes.
- Bigram weight is independent of temperature, defaults to **1**, and ranges from 0 to 5. Weight zero disables n-gram guidance. The trigram correction has relative weight 0.5.
- Top-k defaults to **16**, with the same maximum of 100 as the BYOD guided interface. Method changes preserve the chosen temperature and candidate count. Top-p is enabled for Sampling only.
- The shared objective combines diffusion log-probabilities, weighted PMI bigrams, weighted trigram corrections and temperature-scaled Gumbel noise. This approximate perturb-and-MAP sampler uses the existing fast Viterbi implementation.
- All answer positions remain directly editable, including visible/permanently unmasked tokens. Prompt tokens stay fixed and supply left boundary context. Confidence uses full-vocabulary selected-token diffusion probabilities after EOS bias, without Gumbel noise or top-k renormalization.

## LAD behavior preserved

The following 12 controls were compared with the pre-update source and verified on the live UI; their values, ranges and steps remain intact:

- Multi-turn dialog
- Number of iterations: ↑ = more iterations
- Pause between iterations ↑ = longer pause
- Generation length: ↑ = more output tokens by decreasing eos token probability
- Noise decay sharpness: ↓ = more noise in later iterations
- Noise start fraction: ↑ = more noise
- Use confidence-guided noising
- Use permanent unmasking
- Noise clipping: ↓ = more confidence guidance
- Top-p: ↑ = more random answers
- Semi-autoregressive generation: number of added tokens per iteration
- Context window: ↑ = longer sequences

The prompt format, model weights/loading, noising schedule, token-addition loop, multi-turn history and three-iteration convergence check were retained. `infer.py`, `models.py`, `model_config.py` and requirements are byte-identical to the previous live revision. Space hardware is unchanged.

## Scorers

The expanded BYOD-Llama pair is reused without further training. The original LAD bigram checkpoint exactly matched the original BYOD-Llama checkpoint. The expanded scorer matches that tokenizer/vocabulary; loading validates the tokenizer fingerprint and paired corpus metadata.
Training corpus: **871,088,258 tokens**, comprising all 980,000 original responses plus 800M added tokens (90% FineWeb-Edu, 5% Python-Edu, 5% FineMath). All bigrams are retained; trigram counts >=2 are retained, including count two. Prefix totals include singleton contributions. PMI minimum count is 1, both corrections clip to +/-2, and trigram backoff strength is 50.

Asset repository: `Ruurd/byod-llama-ngram-guidance-expanded` at `6063da3df9412f0becd6ed553c0025c42ee3c00c`. Both files download at startup, outside GPU inference. The original local `bigram.pt` remains for legacy decoding.

## Validation

- **112 tests passed, 6 CUDA-only checks skipped.** Tests cover shared BG+TG behavior, deterministic zero-temperature guidance, positive-temperature variation, independent weight, prompt preservation, editable visible tokens, noising-confidence alignment and one model forward per iteration.
- The public UI and API defaults are checked against the running deployment commit. The initial BG+TG deployment checks are archived separately; the current default is Sampling at temperature 0.7.
- On the initial BG+TG deployment, three short hosted cases completed two iterations each: Sampling at T=0.3, BG+TG at T=0.3, and BG+TG at T=0 with no re-noising and permanent unmasking enabled.
- The final no-re-noising case tests LAD correction compatibility; it does not turn LAD into masked-only diffusion.
- These are correctness/deployment smoke checks, not a quality study or a matched timing benchmark.

| Method | Temperature | Noise fraction | Output |
|---|---:|---:|---|
| Sampling | 0.3 | 0.5 | Hello! |
| BG + TG Viterbi (Gumbel) | 0.3 | 0.5 | Hello! How |
| BG + TG Viterbi (Gumbel) | 0.0 | 0.0 | Hello! |

## Deployment
- Previous revision: `a51224e831820c03732595608ddee8c0e7356bc4`.
- Initial BG+TG revision: `7ea16d7a1ff9638f5c153da81dd31e19da060f40`.
- Current Sampling-default revision: `419caab327584fa2e7bf51254a450e326fc1ae23`.
- [Current deployment](deployment.json), [current defaults verification](hosted_verification.json), [initial BG+TG smoke outputs](bg_tg_initial_hosted_verification.json), [tokenizer/scorer verification](scorer_verification.json), [initial state](initial_state.json).

Rebuild/publish using `huggingface/publish_lad_viterbi.py`; verify using `python scripts/verify_lad_trigram.py --smoke`. Completed smoke cases are retained for the same revision, so repeated verification does not regenerate them.
