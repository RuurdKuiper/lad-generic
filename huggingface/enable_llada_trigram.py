#!/usr/bin/env python3
"""Publish expanded bigram/trigram counts as optional LLaDA guidance."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from enable_repetition_penalty import ROOT, make_bundle

SPACE = "Ruurd/llada-8b-instruct"
OUT = ROOT / "artifacts/bigram/llada_expanded_ngrams"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(2**20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    from dotenv import load_dotenv
    from huggingface_hub import HfApi, hf_hub_download

    load_dotenv(ROOT / ".env")
    api = HfApi()
    if api.whoami()["name"].casefold() != "ruurd":
        raise RuntimeError("Requires Ruurd account")
    manifest = OUT / "prepared.json"
    if args.execute:
        record = json.loads(manifest.read_text())
        if (
            record["space"] != SPACE
            or api.repo_info(SPACE, repo_type="space").sha != record["parent_revision"]
        ):
            raise RuntimeError(
                "Space changed since preparation; review before deployment"
            )
        for filename, info in record["assets"].items():
            if digest(Path(record["asset_paths"][filename])) != info["sha256"]:
                raise RuntimeError("Checkpoint changed since preparation")
        commit = api.upload_folder(
            repo_id=SPACE,
            repo_type="space",
            folder_path=record["bundle"],
            parent_commit=record["parent_revision"],
            delete_patterns=["bigram_expanded.pt", "trigram_expanded.pt"],
            commit_message="Add optional expanded-corpus bigram and exact trigram guidance",
        )
        record["revision"] = commit.oid
        (OUT / "deployment.json").write_text(json.dumps(record, indent=2) + "\n")
    else:
        report = json.loads((OUT / "training_report.json").read_text())
        if report["new_tokens"] < 800_000_000:
            raise RuntimeError("Expanded corpus training is incomplete")
        asset_paths = {
            "bigram_expanded.pt": OUT / "bigram_expanded.pt",
            "trigram_expanded.pt": OUT / "deployment-assets/trigram_expanded.pt",
        }
        assets = {
            name: dict(sha256=digest(path), bytes=path.stat().st_size)
            for name, path in asset_paths.items()
        }
        model = json.loads((OUT / "model_deployment.json").read_text())
        if model["assets"] != assets:
            raise RuntimeError(
                "Published scorer assets differ from prepared local files"
            )
        revision = api.repo_info(SPACE, repo_type="space").sha

        def read(name):
            return Path(
                hf_hub_download(
                    SPACE, name, repo_type="space", revision=revision, token=api.token
                )
            ).read_text()

        config = json.loads(read("space_model.json"))
        if config.get("model_backend") != "llada" or not config.get("bigram_enabled"):
            raise RuntimeError("Unexpected LLaDA setup")
        # Preserve any Space-side edits instead of silently replacing unknown code.
        old_snapshot = (
            OUT / "bundle/app.py"
            if (OUT / "deployment.json").exists()
            else ROOT / "artifacts/bigram/llada_apd_quota/bundle/app.py"
        )
        if old_snapshot.exists() and read("app.py") != old_snapshot.read_text():
            raise RuntimeError("Review Space-side app edits before replacing app.py")
        config.update(
            ngram_scorer_repo=model["repo"], ngram_scorer_revision=model["revision"]
        )
        readme = (
            read("README.md")
            .split("## Optional expanded-corpus bigram and trigram guidance")[0]
            .rstrip()
            + """

## Optional expanded-corpus bigram and trigram guidance

**N-gram guidance** defaults to **Original bigram**, preserving the existing
checkpoint and behavior. **Expanded bigram** uses the new corpus; **Expanded
bigram + trigram** adds a second-order correction to that same expanded bigram.
These choices apply to both bigram decoding strategies, including sequence
sampling, repetition penalties/risk/decay, APD and its minimum quota. Ordinary
independent diffusion ignores this setting. Existing weights and model settings
are unchanged; no extra diffusion-model forwards or language model are needed.

The new corpus adds 800M LLaDA-tokenized tokens: 720M FineWeb-Edu English,
40M educational Python and 40M FineMath-4+, plus all original training responses.
The added-token ratio is 90% / 5% / 5%, not the initially proposed 50/25/25 mix.
Exact per-source text duplicates are skipped. Document boundaries are preserved;
EOS is appended to complete raw documents and nontruncated original responses.
The final sampled raw document may be cut to its exact token budget. Both new
scorers use the same corpus and exact tokenizer, not separately sampled data.

Sources and attribution:
- [FineWeb-Edu](https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu), sample-10BT.
- [Python-Edu](https://huggingface.co/datasets/HuggingFaceTB/smollm-corpus), via the
  [text-resolved mirror](https://huggingface.co/datasets/Avelina/python-edu-cleaned).
  The upstream publishes blob metadata, not file text; the mirror resolves it.
- [FineMath-4+](https://huggingface.co/datasets/HuggingFaceTB/finemath).
Pinned revisions, exact file paths, token/document counts and hashes accompany
these checkpoints in the local experiment/training records.

Score: sum log p_t + w*sum(PMI bigram) + 0.5*w*sum(delta trigram) - repetition.
Delta = log P(c|a,b) - log P(c|b), with alpha=50 bigram-backoff smoothing,
minimum trigram count 2, and delta clipped to [-2,2]. Unseen/singleton triples give
zero correction (backoff), never forbidden transitions. All bigram counts are
retained (PMI minimum count 1). The deployed trigram checkpoint stores triples
observed at least twice and their required contexts, retaining full prefix totals
including singleton contributions. Scorers are downloaded at startup from a
pinned model-repository revision, avoiding the Space's 1 GB storage limit.
The conditional bigram is the same smoothed backoff model used by the bigram
checkpoint. Edit TRIGRAM_RELATIVE_WEIGHT/MIN_COUNT/CLIP in app.py to tune it.

Trigrams are evaluated only wholly inside the current block; existing bigram
boundary terms remain. Fixed positions are singleton constraints. Exact max-path,
forward/backward sampling, path margins and joint bigram marginals use the
second-order chain. In risk mode, earlier-repetition estimates include trigram
scores as well as diffusion and PMI. Sequence temperature scales the complete
score; bigram weight 0 disables both n-gram corrections. For blocks of 1–2 tokens
there is no trigram term. The default Original bigram path is unchanged.

GPU candidate dimensions are vectorized, but trigram cost grows as K^3 rather
than K^2. Start at Top-k 16. At K=16, B=64 the extra FP32 trigram-potential table
is about 1 MiB; checkpoints and temporary buffers add memory. Longer corpus
matching does not check factual relevance to the question. Quality benefits and
latency overhead must be evaluated rather than assumed.
"""
        )
        bundle = OUT / "bundle"
        make_bundle(bundle, config, readme, apd=True)
        for name in assets:
            if (bundle / name).exists():
                (bundle / name).unlink()
        (bundle / "ngram_training_report.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        record = dict(
            space=SPACE,
            parent_revision=revision,
            bundle=str(bundle),
            assets=assets,
            asset_paths={name: str(path) for name, path in asset_paths.items()},
            scorer_repository=model,
        )
        manifest.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
