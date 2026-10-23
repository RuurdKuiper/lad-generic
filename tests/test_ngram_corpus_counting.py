"""Document-local source counting and exact budgets for expanded BYOD training."""

import importlib.util
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest


def test_cached_source_counts_budget_dedup_and_boundaries(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "mixed_counts_test",
        Path(__file__).resolve().parents[1] / "scripts/build_mixed_ngrams.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "OUT", tmp_path / "output")
    monkeypatch.setattr(module, "V", 10)
    parquet = tmp_path / "source.parquet"
    pq.write_table(
        pa.table({"text": ["a" * 80, "a" * 80, "b" * 80, "c" * 80]}), parquet
    )
    import huggingface_hub

    def cached_download(*args, **kwargs):
        assert kwargs["local_files_only"] is True
        return str(parquet)

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", cached_download)

    class Tokenizer:
        eos_token_id = 9

        def __call__(self, texts, **kwargs):
            return {
                "input_ids": [[1, 2] if t.startswith("a") else [3, 4] for t in texts]
            }

    plan = dict(
        name="english",
        repo="fixture",
        revision="pinned",
        prefix="data/",
        tokens=5,
        files=["data/source.parquet"],
        offline=True,
    )
    report = module.tokenize_source(plan, Tokenizer())
    # First document [1,2,EOS], then [3,4] truncated to the remaining budget.
    folder = module.OUT / "count-shards" / "english"
    pairs = pq.read_table(folder / "2-00000.parquet").to_pydict()
    triples = pq.read_table(folder / "3-00000.parquet").to_pydict()
    assert dict(zip(pairs["key"], pairs["count"])) == {12: 1, 29: 1, 34: 1}
    assert dict(zip(triples["key"], triples["count"])) == {129: 1}
    assert np.load(folder / "unigrams.npy").sum() == 5
    assert report["documents"] == 2
    assert report["skipped_duplicates"] == 1
    assert report["eos_appended"] == 1
    assert module.tokenize_source(plan, Tokenizer()) == report
    with pytest.raises(RuntimeError, match="differs"):
        module.tokenize_source(dict(plan, tokens=6), Tokenizer())

    # Reports survive in Git while their rebuildable cache files do not.
    for name in ["unigrams.npy", "2-00000.parquet", "3-00000.parquet"]:
        (folder / name).unlink()
        restored = module.tokenize_source(plan, Tokenizer())
        assert restored["actual_tokens"] == 5
        assert np.load(folder / "unigrams.npy").sum() == 5
        assert (folder / name).is_file()
