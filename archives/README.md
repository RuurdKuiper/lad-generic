# Frozen decoding research workspace

`decoding-studies-2026-11-04.tar.gz` preserves the historical study source,
experiment outputs, judgments, intermediate analyses, and deployment records
that were removed from the active tree. It is 10.09 MB compressed and contains
1,298 files, including local deployment source snapshots. This is one shared
source snapshot, with each study at its original
`artifacts/bigram/<study>/` path, avoiding duplicate code bundles per study.

The adjacent manifest records a SHA-256 for every member and for the archive.
All members were read back and verified before active files were removed.
The snapshot includes uncommitted work at cleanup time; its base Git commit
alone does not describe all archived content. No Git history was rewritten.

## Recover a historical experiment

From the repository root:

```sh
python tools/research_archive.py
python tools/research_archive.py --extract /tmp/byod-decoding-history
```

The destination must not already exist. Extraction verifies all checksums and
rejects links, duplicate paths, and path traversal. It never overlays the active
checkout or deploys anything. Install the original root dependencies into an
environment, then run the original commands from the extracted directory.
The old detailed deployment guide is `huggingface/README.md` inside the archive.

To regenerate the final randomized analysis and integrated eight-method report:

```sh
cd /tmp/byod-decoding-history
python scripts/summarize_llada_randomized_viterbi.py --final
python scripts/integrate_llada_randomized_report.py
```

These commands recalculate summaries/intervals and rewrite derived files only
inside the extracted snapshot. No new model generation or grading is performed.
Human judgments and code-check results are frozen inputs. For a smaller,
read-only check of the canonical study in the active tree, run
`python scripts/analyze_decoding_study.py` from the active checkout.

## Evidence retained

The archive includes raw outputs for every method and the three excluded
incomplete-comparison rows, reviews, code checks, task manifests, source versions,
and historical reports for all archived studies. It also includes the original
evaluation, review, analysis, and report-integration scripts; historical deployment
patches and their source dependencies; local deployment source snapshots;
root runtime code/configs/tests; and the
earlier selected system-guided GIF capture. It excludes model weights, downloaded
datasets, secrets, environments, and exploratory GIF attempt batches.

Fresh generation additionally needs the recorded model/scorer assets, source
revisions, dependencies, and GPU environment. Some old study endpoints have since
changed; use the recorded historical Space revision in an isolated environment.
The archive does not claim to provide every model/data dependency or exact
cross-hardware timing reproduction. See the
[experiment guide](../docs/experiments.md) and
[cache recovery record](../docs/maintenance/README.md).

The active tree keeps canonical eight-method evidence, final reports for earlier
studies, and current scorer/deployment provenance. Older report links that point
here refer to files available at their original paths after extraction. The full,
unmodified historical reports remain in the archive.
