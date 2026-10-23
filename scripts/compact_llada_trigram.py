#!/usr/bin/env python3
"""Remove unused trigram contexts while preserving exact count>=2 corrections."""

import json
from pathlib import Path
import sys
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from diffusion_lm.bigram import BigramScorer
from diffusion_lm.trigram import TrigramScorer


def main():
    torch.set_num_threads(4)
    out = ROOT / "artifacts/bigram/llada_expanded_ngrams"
    bg = BigramScorer.load(out / "bigram_expanded.pt")
    full = TrigramScorer.load(out / "trigram_expanded.pt", bigram=bg)
    retained = full.triple_counts >= 2
    keys = full.triple_keys[retained]
    counts = full.triple_counts[retained]
    prefixes = torch.unique_consecutive(keys // full.vocab_size).clone()
    locations = torch.searchsorted(full.prefix_keys, prefixes)
    assert torch.equal(full.prefix_keys[locations], prefixes)
    state = dict(
        version=1,
        vocab_size=full.vocab_size,
        triple_keys=keys,
        triple_counts=counts,
        prefix_keys=prefixes,
        prefix_counts=full.prefix_counts[locations],
        alpha=full.alpha,
        metadata=dict(
            full.metadata, storage_min_count=2, compacted_for_space_storage=True
        ),
    )
    dest = out / "deployment-assets/trigram_expanded.pt"
    dest.parent.mkdir(exist_ok=True)
    torch.save(state, dest)
    compact = TrigramScorer.load(dest, bigram=bg)
    # Check retained, pruned and random unseen triples against the full scorer.
    torch.manual_seed(42)
    query = torch.cat(
        (
            keys[:: max(1, len(keys) // 10000)],
            full.triple_keys[:: max(1, len(full.triple_keys) // 10000)],
            torch.randint(full.vocab_size**3, (10000,)),
        )
    )
    a = query // full.vocab_size**2
    b = query // full.vocab_size % full.vocab_size
    c = query % full.vocab_size
    assert torch.equal(
        full.correction(a, b, c, bg, min_count=2),
        compact.correction(a, b, c, bg, min_count=2),
    )
    report = dict(
        storage_min_count=2,
        triples=len(keys),
        prefixes=len(prefixes),
        bytes=dest.stat().st_size,
        checked_triples=len(query),
        exact_correction_equivalence=True,
    )
    (out / "compaction.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
