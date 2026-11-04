# Maintained research tools

Run these from the repository root. Completed-study runners, report-integration
scripts, and old feature-verification scripts are in the
[research archive](../archives/README.md), together with their source/results.

| Purpose | Active tools |
| --- | --- |
| Canonical eight-method analysis | `analyze_decoding_study.py` |
| Paper figures/statistics | `generate_paper_figures.py`, `estimate_paper_compute.py`, `calculate_open_ended_uncertainty.py`, `import_progression_results.py` |
| Capture paper/demo visuals | `capture_demo_trajectories.py`, `capture_byod_daily_gif.py`, `render_byod_daily_gif.py` |
| Scorer building/compaction | `build_bigram.py`, `build_byod_trigrams.py`, `build_byod_expanded_ngrams.py`, `build_mixed_ngrams.py`, `build_llada22_ngrams.py`, `compact_llada_trigram.py` |
| Scorer publishing | `publish_byod_expanded_ngrams.py`, `publish_llada_ngram_assets.py` |
| Deployment verification | `verify_byod_expanded_rollout.py`, `verify_lad_trigram.py`, `verify_llada22.py` |
| Reusable small evaluations | `evaluate_quick_perplexity.py`, `evaluate_ending_controls.py` |
| Local decoder benchmarks | `benchmark_bigram.py`, `benchmark_trigram_dp.py` |

Generation tools can contact hosted models; publisher tools can update remote
repositories. The canonical analysis command only reads local saved evidence.
New GIF captures and quick-perplexity runs default to temporary directories.
Use explicit new output paths for experiments instead of writing into a frozen
study folder. The original commands/defaults remain recoverable in the archive.
