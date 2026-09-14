# Experiment notes

## Structured-model regression investigation

The current `Ruurd/LAD-training-1m-256` mixture remains the 45% general, 18%
reasoning, 18% math, and 19% code baseline. The long-answer variant should use
70% general, 10% reasoning, 10% math, and 10% code and should not reject a
source row merely because its complete answer does not fit the training
context. Build it with `--truncate-long-answers --category-weights 0.70 0.10
0.10 0.10`. An answer cut off by the context limit deliberately receives no
terminating EOS; complete answers retain their genuine EOS.

This change needs an ablation against the current complete-example-only
builder. Track the raw and effective answer-length distributions, the fraction
of truncated rows, unique rows and repeat exposure per source, and generated
answer perplexity under one shared evaluation protocol.

Other high-priority confounds to isolate:

- Legacy structured corruption included the complete fixed-width region after
  the assistant header, including EOS padding. Current online structured
  corruption changes only genuine answer tokens, even when `all_tokens` and
  `eos_padding_loss` supervise clean prompt and padding positions.
- The legacy sampler repeatedly revised every answer position and reintroduced
  decreasing noise. Current structured generation validation uses the
  permanent-transfer `llada_official` mask-only sampler.
- Match optimizer updates and examples seen, not only epochs or nominal
  hyperparameters. Also match batch size, LoRA rank/targets, precision, weight
  decay, gradient clipping, and scheduler horizon.
- Perplexity is comparable only when the same generated prompts, sampler,
  generation budget, conditioning text, tokenizer, reference model, and
  aggregation method are used.
