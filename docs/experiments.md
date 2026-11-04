# Experiment results and reproduction

The research workspace contains the paper experiments and later decoding
studies. Their outputs, judgments, configurations, and scripts are retained in canonical
evidence files or the [verified historical archive](../archives/README.md).
Older study runners and intermediate files were removed from the active tree.
The ongoing [ICLR submission](../iclr2027_submission/) and
[arXiv submission](../arxiv_submission/README.md) remain separate source trees.
Later hosted-demo experiments are not additional results of the submitted paper.

## Paper experiments

Use [the standalone implementation](../byod-reproducible/README.md), its
[reproduction notes](../byod-reproducible/REPRODUCIBILITY.md), and
[paper preset](../byod-reproducible/configs/paper.yaml) for conversion and
evaluation. The [research workflow](research-workflow.md) documents the older
training, continuation, and evaluation experiments in the root package.

The maintained paper workbooks and derived uncertainty estimates are in
[`iclr2027_submission/source_results/`](../iclr2027_submission/source_results/).
Generate figures into a scratch directory first:

```sh
pip install -e '.[paper]'
python scripts/generate_paper_figures.py \
  --workbook iclr2027_submission/source_results/Results_training-20260924.xlsx \
  --output-dir /tmp/byod-paper-figures \
  --distinct-table-output /tmp/byod-distinct-results.tex
```

The script's historical default workbook is in ignored `results/`, so the
explicit tracked input above matters on a fresh checkout. The local workbook
and tracked workbook differ; selecting either is a provenance decision. Compare
generated figures against the manuscript before replacing them. The uncertainty
script also depends on historical evaluation runs in Drive; the saved estimates
alone do not replace those per-example inputs.

## Decoding studies

These are exploratory studies with the prompts, seeds, settings, and limitations
in their individual reports. Their exact text and grades remain available.

| Study | Finding and interpretation | Preserved record | Historical scripts (in archive unless still active) |
| --- | --- | --- | --- |
| Initial quality and coding comparisons | Compared complete decoding settings bundles, before later temperature controls; do not interpret as isolated Viterbi effects. | [Quality](../artifacts/bigram/quality_experiment/REPORT.md), [coding](../artifacts/bigram/coding_paper_settings/REPORT.md) | `evaluate_decoding_quality.py`, `summarize_decoding_quality.py`, `render_decoding_quality_review.py` |
| Quick Gemma perplexity | Stopped early with 168/240 outputs. PMI settings reduced measured Phi-4 perplexity on matched prompts; this is not a factuality measure. | [Report](../artifacts/bigram/perplexity_quick/REPORT.md) | `evaluate_quick_perplexity.py`, `compare_perplexity_studies.py` |
| Gemma/LLaDA transfer | PMI settings lowered reference perplexity; distinctness, length, and examples qualify that result. | [Report](../artifacts/bigram/perplexity_models/REPORT.md), [Gemma 128](../artifacts/bigram/perplexity_128/REPORT.md), [LLaDA 128](../artifacts/bigram/perplexity_llada_128/REPORT.md) | `evaluate_quick_perplexity.py`, `compare_perplexity_studies.py`, `render_perplexity_examples.py` |
| Six-prompt n-gram screen | Bigram was a provisional mixed-task choice under the tested settings. Too small to establish a general optimum. | [Report](../artifacts/bigram/llada_ngram_settings/REPORT.md) | `evaluate_llada_ngram_settings.py`, `summarize_llada_ngram_settings.py` |
| Eight-arm matched LLaDA study | Deterministic BG+TG outperformed exact sampling descriptively overall in the fixed-seed comparison. Gains varied by task and NFE. | [Final report](../artifacts/bigram/llada_ngram_settings_full/REPORT.md), [math analysis](../artifacts/bigram/llada_ngram_settings_full/HIGH_NFE_MATH_ANALYSIS.md) | Active: `analyze_decoding_study.py`; original generation/review scripts in archive |
| Randomized BG+TG extension | Adds 282 cases; the combined archive has 2,256 outputs. Uncertainty intervals do not establish superiority or equivalence to deterministic or exact sampled decoding. | [Report](../artifacts/bigram/llada_ngram_settings_full/randomized/REPORT.md) | `evaluate_llada_randomized_viterbi.py`, `summarize_llada_randomized_viterbi.py`, `check_llada_randomized_diversity.py` |
| Decoder speed | CPU MAP K16 reduced observed mean end-to-end time by 15.9%, preserving 18/18 primary outputs. K8 changed 7/18; shared hardware limits timing conclusions. | [Report](../artifacts/bigram/llada_ngram_speed/REPORT.md) | `evaluate_llada_ngram_speedup.py`, `summarize_llada_ngram_speedup.py`, `benchmark_trigram_dp.py` |
| Retention-confidence audit | An unsuccessful confidence-policy experiment was reverted. Preserve this negative result and its historical patch. | [Report](../artifacts/bigram/viterbi_audit/REPORT.md) | `evaluate_viterbi_confidence.py`, `evaluate_ending_controls.py` |
| Scorer expansion | Records tokenizer-specific counts, corpus revisions, document boundaries, and asset hashes; establishes scorer provenance rather than general model-quality gains. | [LLaDA](../artifacts/bigram/llada_expanded_ngrams/REPORT.md), [BYOD rollout](../artifacts/bigram/byod_expanded_rollout/REPORT.md) | `build_bigram.py`, `build_mixed_ngrams.py`, `build_byod_trigrams.py`, `build_byod_expanded_ngrams.py` |
| LLaDA2.2 integration | Companion implementation with distinct block/edit semantics, not a matched quality comparison with the paper models. | [Research notes](../artifacts/llada22/RESEARCH.md), [implementation](../huggingface/llada22_space/README.md) | `build_llada22_ngrams.py`, `verify_llada22.py` |

Deployment checks, default changes, APD and repetition controls are indexed in
the [artifact guide](../artifacts/bigram/README.md) and
[deployment guide](../huggingface/README.md). These are operational records,
not independent benchmark results. Earlier `PRE_*` reports are historical stages;
use the final report when citing a study.

## Reproduce analysis versus rerun generation

The active eight-method study has one canonical raw JSONL file, one scored CSV,
one final summary, and the original judgment/configuration inputs. Validate it
and independently recompute all 56 descriptive method/NFE groups:

```sh
python scripts/analyze_decoding_study.py
python scripts/analyze_decoding_study.py --output /tmp/byod-descriptive-summary.json
```

This checks all 2,256 text hashes, judgment hashes/scores, recorded timing,
forward budgets, and matched coverage, then compares the recomputed means with
the saved final summary. It does not regrade outputs or recalculate bootstrap
intervals. To regenerate the historical intervals and full final report, use
the [archive extraction and analysis commands](../archives/README.md).

The archive retains every older study's source, raw outputs, judgments, and
intermediate reports. Three original incomplete-comparison outputs remain
archived and excluded, as documented in the final report. All compared methods'
retained cases remain in the active canonical evidence; no poor-performing arm
was removed. Human judgments are preserved inputs, not automatically reproducible
assessments.

Fresh generation additionally requires the recorded model, tokenizer, scorer
assets, dependencies, and **Space source revision**, not merely today's live
Space URL. Extract the original study scripts and use the historical Space
source in an isolated environment. Calling a changed live endpoint is a new
experiment. Shared GPU timings need not reproduce exactly across hardware.

The retained scorer builders require their pinned tokenizer snapshots and
`data/lad-training-1m-256-long`; mixed-corpus expansion additionally requires
recorded corpus/count assets. Those inputs were preserved. Restore deleted
upstream tokenizer caches using the [recovery commands](maintenance/README.md).

The older unavailable `crumb/clean-instruct-3_m` source blocks a fully online
reconstruction of any experiment that used it. Its cached data is retained,
as are potentially unique trained checkpoints and source workbooks. No
unverified Drive backup was assumed to exist.

For an integrated evidence and archive checksum check:

```sh
python tools/check_experiment_records.py > /tmp/byod-experiment-validation.json
```
