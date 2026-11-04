# BYOD research workspace

Code, results, and manuscript sources for **BYOD: Build Your Own DLM — Efficient
Autoregressive-to-Diffusion Language Model Conversion**.

## Start here

- **Train or reproduce the paper:** [standalone BYOD implementation](byod-reproducible/README.md),
  with Colab, quick/paper presets, evaluation, and reproduction notes.
- **Continue the ICLR submission:** [manuscript and source results](iclr2027_submission/).
- **Build the arXiv version:** [preprint instructions](arxiv_submission/README.md).
- **Understand completed experiments:** [findings and reproduction guide](docs/experiments.md).
- **Develop or publish the demos:** [Hugging Face guide](huggingface/README.md).
- **Use the original research pipeline:** [training and evaluation workflow](docs/research-workflow.md).

## Repository layout

| Path | Purpose |
| --- | --- |
| `byod-reproducible/` | Standalone paper training/evaluation package and notebook |
| `src/`, `configs/`, `tests/` | Broader research pipeline and regression checks |
| `scripts/` | Experiment generation, analysis, figure, and verification tools |
| `artifacts/` | Saved experiment outputs, grades, reports, and scorer provenance |
| `iclr2027_submission/` | Ongoing conference submission, figures, and source workbooks |
| `arxiv_submission/` | Preprint source and packaging tools |
| `huggingface/` | Hosted demo source and publishing tools |
| `tools/byod_data/` | Dataset building and publication tools |
| `docs/` | Research workflow, experiment index, announcement, and cleanup records |
| `legacy/` | [Historical training notebooks and inference app](legacy/README.md) |

## Development

The root package and standalone package both expose `diffusion_lm`. Use separate
virtual environments for them. For the research package, run from this directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
python -m pytest -q
```

Optional extras: `cuda` for bitsandbytes, `fp8` for Transformer Engine, `evaluation`
for benchmark scoring, `paper` for workbooks, `ngrams` for count aggregation, and
`media` for GIF capture/rendering. Training and hosted generation need suitable
GPU resources; CPU checks do not validate GPU training.

Downloaded models and datasets are local caches. Verified copies were removed
to free disk space; exact revisions, retained exceptions, and restore commands
are in [the cleanup record](docs/maintenance/README.md). Experiment outputs,
trained checkpoints, and the ongoing ICLR submission remain available.
