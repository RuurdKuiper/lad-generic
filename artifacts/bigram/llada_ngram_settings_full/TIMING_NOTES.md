# Why sampled BG + TG costs more: deductions from the existing implementation

No new timing benchmark or profiler was run for this discussion. No sampling optimization was implemented. The measurements below come from the completed deterministic/sampled study.

| Mean per generation | Deterministic BG + TG | Sampled BG + TG |
| --- | ---: | ---: |
| Server generation time | 2195 ms | 3190 ms |
| Instrumented selector time | 618 ms | 1610 ms |
| Server time minus selector time | 1577 ms | 1580 ms |

Approximately 992 of the 995 ms difference appears inside the sequence selector. This locates the observed cost increase in decoding; it does not isolate individual kernels, and the arms ran at different times on shared hardware.

The deterministic forward recurrence takes a maximum over predecessors. The sampling forward recurrence uses logsumexp, which requires more arithmetic and reductions. Both process the same general O(block length × candidate count cubed) second-order lattice; the sampler does not enumerate complete sequences.

Backward Viterbi follows stored predecessor pointers. The exact sampler instead performs a softmax and torch.multinomial for every conditional choice. A full length128 chain has127 categorical sampling calls per denoising iteration, or16256 calls across128 iterations. These are small distributions, so many separate GPU launches and potentially synchronization can be expensive relative to their arithmetic. The current full-width lattice also persists after many positions are fixed, even though each fixed row has only one valid candidate.

The strongest optimization candidates are:

1. Generate independent uniform random numbers in one batch, then use a compiled/fused conditional backward sampler. This can preserve the target joint sampling distribution while reducing PyTorch/kernel-launch overhead. Exact seeded outputs may change even when the distribution is unchanged.
2. Exploit fixed positions: avoid random draws for known tokens, shrink their candidate state spaces, and split trigram chains at two consecutive fixed positions while preserving the two-token boundary context. Do not concatenate nonadjacent editable positions, which would invent n-grams.
3. Fuse the forward recurrence's reductions, additions, scaling and normalization. This reduces operations launched from Python while retaining the same chain computation.

Reducing top-k also reduces lattice arithmetic, but changes the candidate support and may affect quality. It may not reduce launch overhead proportionally. Independent per-position sampling would change the modelled joint distribution and lose sequence-level guidance.

The code supports substantial optimization opportunities, but the achievable speedup and the relative costs of forward summation versus categorical draws require later profiling. There are no additional DLM model forward passes in the sampler.

Implementation references: src/diffusion_lm/trigram.py (_forward, decode_second_order, sample_second_order) and src/diffusion_lm/bigram.py (selector dispatch and fixed-position emissions).
