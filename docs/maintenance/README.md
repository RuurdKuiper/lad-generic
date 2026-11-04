# Cleanup and source recovery

On 4 November 2026, cached upstream models and datasets were checked against
Hugging Face before removal. No Drive backup was assumed or used. The ongoing
ICLR submission, source workbooks, all experiment outputs and judgments, scorer
checkpoints/corpus caches, and trained adapters/checkpoints were preserved.

## What was checked and removed

[`remote-sources.json`](remote-sources.json) records 43 source checks, exact
repository revisions, payload filenames, URLs, and preserved local metadata.
[`removed-caches.json`](removed-caches.json) records each removed directory and
its size: **72.503 GB** of regular-file payloads (decimal GB; symlinks excluded).
This is an inventory size, not a measurement of physical free space or filesystem
compression. The tracked experiment results were not deleted.

- Model snapshots: upstream filenames and sizes matched; cache blob identifiers
  matched upstream LFS SHA-256/Git blob IDs. Nonstandard files were hashed.
  Authenticated access to an upstream payload was also checked. Large model
  weights were not downloaded again or rehashed in full when the cached blob
  identifiers matched.
- Processed dataset caches: exact upstream commits still existed, with accessible
  Arrow/Parquet payloads. The transformed local Arrow caches were not compared
  byte for byte with upstream Parquet files; they are regenerable caches.
- Seven prepared training profiles: local publication manifests matched the
  published manifests at the pinned BYOD-tokenized-256 revision.

The read-only audit tool is `tools/verify_cleanup_sources.py`. It refuses to
overwrite an existing report. Future audits should use a new `--output` path.
`tools/prune_verified_caches.py` defaults to a dry run, restricts deletion to
known cache locations, rejects tracked files and symlinked parents, and retains
unknown or unverified sources. The saved deletion log is not overwritten.

## Retained exceptions

| Local material | Reason retained |
| --- | --- |
| `data/huggingface/crumb___clean-instruct-3_m/` | Original repository/revision could not be found with the available account. Do not delete without verifying another copy. |
| `data/lad-training-1m-256-long/` | Remote payloads exist, but no published build manifest was found to establish an exact match. Also an input to scorer builders. |
| `data/lad-training-1m-256-long-epoch2/` | Remote payloads exist, but no matching published manifest was found. |
| `data/lad-training-2m-256-long/` | Remote payloads exist, but no matching published manifest was found. |
| `data/prepared/9c39c0f8f5a823b3/` | Older preparation cache lacks sufficient recorded source metadata to establish an exact reconstruction. |
| `outputs/`, `legacy/` checkpoints, `byod-distillation/` | Potentially unique trained assets or ongoing work; outside this verified cache deletion. |

The three local mixture build manifests, split schemas/state metadata, cached
upstream dataset metadata, and publication records are embedded in the audit.
Deleting a cache is not a claim that the experiment can be reconstructed without
its retained manifests, reviews, or historical hosted source.

## Restore a verified source

Run from the repository root with dependencies installed and `HF_TOKEN` available
for gated repositories. Accept the parent model's terms if needed. The restore
tool downloads only the selected source at the recorded revision.

Restore the exact LLaDA tokenizer snapshot required by offline n-gram builders:

```sh
python tools/restore_cleanup_sources.py --tokenizer-only \
  --path base_models/models--GSAI-ML--LLaDA-8B-Instruct/snapshots/08b83a6feb34df1a6011b80c3c00c7563e963b07
```

Omit `--tokenizer-only` to restore the originally cached model files too. Restore
another model by selecting its `path` from `remote-sources.json`. Models that had
only tokenizer files cached will restore only those files; the normal loader
downloads any additional weights it needs.

Restore a dataset cache from its exact upstream commit:

```sh
python tools/restore_cleanup_sources.py \
  --path data/huggingface/Ruurd___lad-training-1m-256/default/0.0.0/6041513b684d6ca627879ffdb547b8629bb8b8de
```

Restore a published tokenization profile:

```sh
python tools/restore_cleanup_sources.py --path data/byod-prepared/47d6443fab78782b
```

Training also downloads the profiles automatically through the standalone
package. Recreated processed datasets can have different cache fingerprints
across library versions; the source revision is fixed by the restore tool.

## Source-tree cleanup

The root README is now a short entry point. Its detailed instructions were
preserved in [`docs/research-workflow.md`](../research-workflow.md), and study
findings and reproduction requirements are indexed in [`docs/experiments.md`](../experiments.md).
The initial cache cleanup retained all study runners and evidence. The later
artifact consolidation moved historical scripts and intermediate files into the
[verified archive](../../archives/README.md); current publishing helpers were
separated from retired rollout scripts. Raw results and judgments remain
available in canonical files or the archive.

The unused `iclr2027_template/` files were removed; no source references to that
directory were found. The ongoing `iclr2027_submission/` was left unchanged.
Recover the old template if needed from the pre-cleanup commit:

```sh
git restore --source=b6be0a4fd6e56296d02a1ac64b3dabc7ab6719f2 -- iclr2027_template
```

No Git history was rewritten. Ignored local model/data directories may be
recreated by future runs.

## Validation

- Root CPU suite after test maintenance: 722 passed, 20 skipped.
- Standalone paper package after test maintenance: 238 passed.
- Saved study validation: 2,256 graded matched outputs pass text/review hash
  and coverage checks; the three historical incomplete-comparison exclusions
  are preserved.
- The pinned LLaDA tokenizer was downloaded again with the restore tool and
  loaded with `local_files_only=True`. Its small files remain in `base_models/`
  as a recovery smoke test; model weights remain removed.
- Local documentation links and `git diff --check` pass. No files under
  `iclr2027_submission/` or `arxiv_submission/` changed. The standalone
  implementation is unchanged; its release-configuration tests were simplified
  in the subsequent test maintenance pass.

## Test maintenance

The root and standalone suites remain independent. Within each suite, redundant
quick-preset assertions were consolidated, static README/badge checks removed,
and tests freezing historical experimental hyperparameters retired. The paper
recipe, historical reference, revision pins, and CLI override tests remain.

Decoder coverage retains singleton and maximum-width cases for the elementwise
greedy branch instead of repeating intermediate widths. Existing scoring-mode
tests now cover fixed-token constraints too, replacing a separate zero-weight
check. Distinct loss, attention, EOS, sampling, and checkpoint regressions remain.
This removes 27 collected cases (25 root, two standalone) and seven test
functions, without changing application code.

## Artifact consolidation

The subsequent cleanup reduced `scripts/` from 63 to 23 active tools and the GIF
folder to four files. The selected GIF/capture checksums are unchanged; exploratory
GIF batches and redundant exports were deleted. The canonical final study keeps
every compared method's outputs and judgments. Older source, intermediate files,
and local deployment source snapshots are retained in a 10.09 MB archive with
1,298 verified members. Ignored deployment bundles moved to
`local_cache/deployment-bundles/`; their binaries were preserved.

The archive was extracted to a scratch workspace. Running the original final
analysis and report integration reproduced `combined_results.jsonl` and
`combined_scores.csv` byte for byte, and reproduced `combined_summary.json`
including its paired intervals exactly. The new read-only analysis independently
matches all 56 descriptive method/NFE groups and verifies text/judgment hashes.
The GIF renderer was run from the retained capture and produces no redundant
sidecars by default. See [`artifact-cleanup.json`](artifact-cleanup.json) for
the removed/relocated path inventory and regeneration results.
