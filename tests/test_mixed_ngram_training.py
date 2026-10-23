"""Small actual DuckDB aggregation verifies boundaries and singleton backoff totals."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest
import torch

from diffusion_lm.bigram import BigramScorer
from diffusion_lm.trigram import TrigramScorer


def test_external_aggregation_preserves_document_boundaries_and_all_prefix_counts(
    tmp_path,
):
    pytest.importorskip("duckdb")
    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location(
        "mixed_training", root / "scripts/build_mixed_ngrams.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = tmp_path
    module.V = 8
    folder = tmp_path / "count-shards" / "fixture"
    folder.mkdir(parents=True)
    sequences = [
        np.array(s, dtype=np.int64) for s in [[0, 1, 2], [0, 1, 2], [0, 1, 3], [4]]
    ]
    pairs = [s[:-1] * 8 + s[1:] for s in sequences]
    triples = [(s[:-2] * 8 + s[1:-1]) * 8 + s[2:] for s in sequences]
    module.write_chunk(folder, 0, pairs[:2], triples[:2])
    module.write_chunk(folder, 1, pairs[2:], triples[2:])
    unigrams = np.bincount(np.concatenate(sequences), minlength=8)
    np.save(folder / "unigrams.npy", unigrams)

    class Tokenizer:
        def get_vocab(self):
            return {str(i): i for i in range(8)}

    # Interrupted COPY outputs must be rebuilt instead of accepted as caches.
    (tmp_path / "counts-2.parquet").write_bytes(b"partial")
    (tmp_path / "counts-3.parquet").touch()
    module.aggregate([dict(name="fixture", actual_tokens=10, documents=4)], Tokenizer())
    bigram = BigramScorer.load(tmp_path / "bigram_expanded.pt")
    trigram = TrigramScorer.load(tmp_path / "trigram_expanded.pt", bigram=bigram)
    assert bigram.unigram_counts.sum() == 10
    assert bigram.pair_counts.sum() == 6  # No 2->0, 3->4 cross-document edges.
    assert trigram.triple_keys.tolist() == [(0 * 8 + 1) * 8 + 2]
    assert trigram.triple_counts.tolist() == [2.0]
    assert trigram.prefix_keys.tolist() == [1]
    assert trigram.prefix_counts.tolist() == [
        3.0
    ]  # Includes the omitted singleton 0,1,3.
    expected = BigramScorer.from_sequences([s.tolist() for s in sequences], 8)
    assert torch.equal(bigram.pair_keys, expected.pair_keys)
    assert torch.equal(bigram.pair_counts, expected.pair_counts)
