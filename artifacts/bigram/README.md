# Decoding evidence and scorer provenance

The active tree keeps current scorer provenance, canonical matched-study evidence,
and final study reports. Intermediate outputs, duplicate summaries, progress
snapshots, and one-off research/deployment scripts are in the
[verified research archive](../../archives/README.md), with their original paths.
The archive preserves all compared methods and negative results.

## Final eight-method study

[`llada_ngram_settings_full/`](llada_ngram_settings_full/REPORT.md) contains:

- `combined_results.jsonl`: all 2,256 matched generated outputs.
- `combined_scores.csv`: the corresponding scores, text hashes, and review notes.
- `combined_summary.json`: final descriptive statistics and paired intervals.
- Original task/settings manifests, amendments, reviews, and code checks.
- Final report, figures, examples, math analysis, and timing notes.

These are the canonical files; duplicate `scores.csv`/`summary.json`
entry points and earlier `pre_*` analysis stages are no longer active files.
Recompute and validate descriptive results without generating or rewriting:

```sh
python scripts/analyze_decoding_study.py
```

Use the archive to regenerate the historical bootstrap intervals/full report or
rerun earlier study scripts. The [experiment guide](../../docs/experiments.md)
summarizes findings and limitations across studies. Earlier final reports remain
readable in their original folders; links to archived evidence lead to recovery
instructions.

## Current scorer inputs and deployment records

- [`byod_expanded_ngrams/`](byod_expanded_ngrams/): tokenizer-specific corpus/count
  reports, source revisions, and asset hashes.
- [`byod_trigrams/`](byod_trigrams/): original response-corpus count provenance.
- [`llada_expanded_ngrams/`](llada_expanded_ngrams/REPORT.md): LLaDA expansion,
  compaction records, and pinned source files.
- [`byod_expanded_rollout/`](byod_expanded_rollout/REPORT.md) and
  [`lad_trigram_rollout/`](lad_trigram_rollout/REPORT.md): current asset/deployment
  records used by maintained publishing and verification tools.
- [Pinned BYOD assets](../../huggingface/byod_ngram_assets.json).

The guided score uses diffusion unary scores plus weighted PMI bigram and
trigram corrections. Positive temperature adds Gumbel noise before Viterbi;
this is approximate perturb-and-MAP, not exact sequence sampling. See
[PMI details](PMI.md) and the [demo guide](../../huggingface/README.md).

Checkpoint, corpus, and count-cache payloads are ignored by Git and remain local;
old ignored deployment bundles moved to `local_cache/deployment-bundles/` with
their binaries preserved. Their source snapshots are also in the research archive.
verified upstream model/tokenization caches were removed. Restore the exact
required tokenizer before an offline builder using the
[source recovery guide](../../docs/maintenance/README.md). No potentially unique
scorer/count asset was deleted in this consolidation.
