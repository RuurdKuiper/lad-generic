# Hosted demos and publishing

This directory maintains the BYOD, native LLaDA, LAD, and LLaDA2.2 demo sources.
Historical feature patches and rollout guides are in the
[verified research archive](../archives/README.md), including the original
version of this guide. This page covers maintained entry points.

## BYOD adapters and Spaces

`publish_byod.py` packages selected checkpoints and current `byod_space/` source.
Gemma, Qwen, and Ministral use their original best checkpoints; Llama uses the
final checkpoint of its uninterrupted 50k-update run. The four Spaces run
BF16/full-precision inference. Model weights and upstream licenses remain separate
from this source repository.

| Model repository | Space |
| --- | --- |
| `Ruurd/BYOD-Gemma-2-9B` | `Ruurd/byod-gemma-2-9b` |
| `Ruurd/BYOD-Llama-3.1-8B` | `Ruurd/byod-llama-3.1-8b` |
| `Ruurd/BYOD-Qwen2.5-7B` | `Ruurd/byod-qwen2.5-7b` |
| `Ruurd/BYOD-Ministral-8B` | `Ruurd/byod-ministral-8b` |

Prepare bundles locally, inspect them, then publish if intended:

```sh
python huggingface/publish_byod.py
python huggingface/publish_byod.py --spaces-only --execute
```

Omit `--spaces-only` to publish the adapters too. Use `--namespace` and
`--anonymous-review` for the review namespace. Paper links are suppressed for
anonymous releases and Dovelove. `--only` selects one model. Check `--help` for
source/output paths; upstream base models may require accepted terms and an
HF_TOKEN secret in the Space settings. Keep tokens out of source and bundles.

The simplified interface offers Confidence-guided and BG + TG Viterbi (Gumbel),
with APD, early stopping, EOS retention, and bigram weight controls. Temperature
zero is deterministic; positive temperature adds unary Gumbel noise. This is
approximate structured sampling, not exact sequence sampling. The scorer
repositories/revisions are pinned in `byod_ngram_assets.json`. Newer demo decoding
options are separate from the settings evaluated in the submitted paper.

The 30-second GPU reservation is also a hard timeout. Reduce generation budgets
or visualization pauses if a run times out. `rollout_gpu_duration.py` prepares
revision-guarded duration-only patches; `--execute` applies a reviewed plan.
Account checks shared by current tools live in `hub_accounts.py`.

## Other demos

- [`lad_space/`](lad_space/README.md): original structural-correction LAD app.
  Prepare with `python huggingface/publish_lad_viterbi.py`; deployment requires
  `--execute --expected-revision <reviewed-space-commit>`. Verify with
  `python scripts/verify_lad_trigram.py --smoke`.
- `publish_llada.py`: prepares the native LLaDA 8B app using shared BYOD source
  and its own tokenizer-matched scorer. Its execute mode creates a **new private
  Space** and refuses to overwrite an existing repository. It is not an updater
  for the existing production Space.
- [`llada22_space/`](llada22_space/README.md): LLaDA2.2 companion and native block/
  edit semantics. `publish_llada22.py` prepares a bundle; inspect its CLI options
  before publishing. Verify with `python scripts/verify_llada22.py`.
- [`perplexity_worker/`](perplexity_worker/README.md): shared reference-scoring app.
- `publish_review_datasets.py`: prepares/publishes review-namespace datasets.
- `enable_repetition_penalty.py`: retained shared bundle/update utility with
  regression coverage. The other historical `enable_*` patches are archived;
  their full source and original deployment records can be extracted together.

## Scorer building and verification

Current build, compaction, publishing, and verification tools are indexed in
[`scripts/README.md`](../scripts/README.md). Counts preserve document boundaries,
use the exact backbone tokenizer, and reject incompatible tokenizer fingerprints.
Offline builders require restored pinned tokenizer files and the retained local
response/corpus/count inputs; see [source recovery](../docs/maintenance/README.md).

[Current scorer provenance](../artifacts/bigram/README.md) retains original source
revisions and asset hashes. Historical deployment logs are evidence of what ran;
they are not instructions to apply every old patch to the current app. To
reproduce an older experiment, use its recorded Space revision and the archived
workspace in isolation.

## Results and historical research

Use the [experiment guide](../docs/experiments.md) for findings, limitations, and
canonical analysis commands. Old evaluation/review/finalization scripts and their
inputs are preserved together in the [archive](../archives/README.md). Raw
outputs for every arm of the final eight-method study remain in the active tree.
