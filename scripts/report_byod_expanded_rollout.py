#!/usr/bin/env python3
"""Summarize completed expanded BYOD training and hosted verification."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/bigram/byod_expanded_rollout"


def main():
    deployments = json.loads((OUT / "deployment.json").read_text())
    verified = json.loads((OUT / "hosted_verification.json").read_text())
    assert len(deployments) == len(verified) == 8
    assert all(
        x["smoke_complete"] and x["runtime_revision"] == x["revision"]
        for x in verified.values()
    )
    models = {
        name: json.loads(
            (
                ROOT / "artifacts/bigram/byod_expanded_ngrams" / name / "complete.json"
            ).read_text()
        )
        for name in ["gemma", "llama", "qwen", "ministral"]
    }
    lines = [
        "# Expanded BYOD bigram/trigram rollout",
        "",
        "All eight BYOD Spaces now use expanded, tokenizer-specific scorers. The smaller-corpus rollout is retained as historical evidence in `../byod_simple_rollout/`.",
        "",
        "## Training corpus",
        "",
        "Count training ran locally on CPU using cached source files; smoke generation ran on the hosted Hugging Face Spaces.",
        "",
        "Each model uses all 980,000 original response documents plus exactly 800,000,000 added tokens, measured with its own tokenizer: 720M FineWeb-Edu, 40M Python-Edu and 40M FineMath. Source revisions are pinned; raw-source texts are deduplicated within each source and counts never cross document boundaries. Original responses keep their original EOS/truncation policy. The last added document can be truncated to meet the exact budget.",
        "",
        "All bigram counts are retained. Trigrams retain count >=2, including count two; compact prefix totals include singleton contributions. PMI uses successor-token marginals. Trigram backoff is 50, minimum count two, clip +/-2 and relative weight 0.5.",
        "",
        "| Model | Original tokens | Total tokens | Retained trigrams | BG MiB | TG MiB |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, r in models.items():
        lines.append(
            f"| {name} | {r['original_tokens']:,} | {r['tokens']:,} | {r['retained_trigrams']:,} | {r['assets']['bigram_expanded.pt']['bytes']/2**20:.1f} | {r['assets']['trigram_expanded.pt']['bytes']/2**20:.1f} |"
        )
    lines += [
        "",
        "Exact source files, counts, tokenizer fingerprints and checkpoint hashes are in `../byod_expanded_ngrams/<model>/complete.json`. Corpus additions use the same pinned sources and 90/5/5 mix as the expanded LLaDA scorer; each tokenizer reaches its own token budget, so final document cutoffs differ.",
        "",
        "## Deployment",
        "",
        "Each account owns its own scorer repositories. Spaces pin immutable asset revisions, avoiding the Space per-file size limit. Config updates and removal of superseded small expanded files occur atomically. Legacy `bigram.pt` remains. Asset hashes were checked after upload. `huggingface/byod_ngram_assets.json` preserves pins for future ordinary republishes.",
        "",
        "Model weights, backend, identity, links, hardware, secrets and generation settings were preserved. The interface remains Confidence-guided / BG + TG Viterbi (Gumbel), temperature 0.7, top-k 16, bigram weight 1, ending-delay strength 10, with APD, early stopping and EOS retention available.",
        "",
        "| Space | Live revision | Asset revision |",
        "|---|---|---|",
    ]
    for r in deployments:
        lines.append(
            f"| [{r['space']}](https://huggingface.co/spaces/{r['space']}) | `{r['revision']}` | `{r['asset_revision']}` |"
        )
    lines += [
        "",
        "## Verification",
        "",
        "- 88 local checks passed; 6 CUDA-only tests skipped (83 decoding/interface tests, one source-counting test and four publisher tests).",
        "- All four expanded pairs have matching tokenizer/vocabulary/token-count metadata, verified integer count totals and finite clipped correction queries.",
        "- All eight Spaces are RUNNING at their new commit, with preserved configuration and the same two-method interface.",
        "- Both methods were exercised on every Space: 16 short smoke generations, 16 output positions and two denoising steps each. Every call used exactly two denoising forward passes and left no unresolved masks.",
        "",
        "These are deployment/correctness checks, not a generation-quality study or matched speed benchmark. `hosted_verification.json` records texts and timings; cold downloads happen at startup, outside timed GPU inference. `deployment.json` records before/after configuration, asset hashes and rollback revisions.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n")
    (OUT / "summary.json").write_text(
        json.dumps(
            dict(
                spaces=8,
                expanded_assets=True,
                hosted_smoke_generations=16,
                local_tests_passed=88,
                local_tests_skipped=6,
                models={
                    n: dict(tokens=r["tokens"], assets=r["assets"])
                    for n, r in models.items()
                },
            ),
            indent=2,
        )
        + "\n"
    )
    print(str(OUT / "REPORT.md"))


if __name__ == "__main__":
    main()
