#!/usr/bin/env python3
"""Expand each BYOD scorer with 800M pinned mixed-corpus tokens, offline/resumable."""

import argparse, hashlib, json, os, sys, time
from pathlib import Path

os.environ.setdefault("RAYON_NUM_THREADS", "2")
import numpy as np
import pyarrow.parquet as pq
import torch
import build_mixed_ngrams as mixed
from build_byod_trigrams import SPECS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", choices=SPECS, required=True)
    a = p.parse_args()
    from transformers import AutoTokenizer
    from diffusion_lm.bigram import BigramScorer, tokenizer_fingerprint
    from diffusion_lm.trigram import TrigramScorer
    import duckdb

    torch.set_num_threads(2)
    start = time.time()
    name = a.model
    out = ROOT / "artifacts/bigram/byod_expanded_ngrams" / name
    out.mkdir(parents=True, exist_ok=True)
    if (out / "complete.json").exists() and all(
        (out / f).is_file() for f in ("bigram_expanded.pt", "trigram_expanded.pt")
    ):
        record = json.loads((out / "complete.json").read_text())
        for filename, asset in record["assets"].items():
            if digest(out / filename) != asset["sha256"]:
                raise ValueError(
                    "Checkpoint does not match its training report: " + filename
                )
        print(json.dumps(record))
        return
    original = ROOT / "artifacts/bigram/byod_trigrams" / name
    old = BigramScorer.load(ROOT / "artifacts/bigram" / SPECS[name][1])
    v = old.vocab_size
    snapshots = list(
        (
            ROOT
            / "base_models"
            / ("models--" + SPECS[name][0].replace("/", "--"))
            / "snapshots"
        ).glob("*")
    )
    assert len(snapshots) == 1
    tok = AutoTokenizer.from_pretrained(
        snapshots[0],
        local_files_only=True,
        **({"fix_mistral_regex": True} if name == "ministral" else {}),
    )
    tok.model_max_length = 10**12
    fingerprint = tokenizer_fingerprint(tok)
    assert fingerprint == old.metadata["tokenizer_sha256"]
    del old
    reference = ROOT / "artifacts/bigram/llada_expanded_ngrams"
    reference_sources = {
        s["name"]: s
        for s in json.loads((reference / "training_report.json").read_text())["sources"]
    }
    mixed.OUT = out
    mixed.V = v
    sources = []
    for source in mixed.SOURCES:
        prior = reference_sources[source["name"]]
        spec = dict(
            source,
            files=prior["files"],
            offline=True,
            cache_dir=str(reference / "hf-cache"),
        )
        sources.append(mixed.tokenize_source(spec, tok))
    # Tokenization can run in parallel; large external aggregations share disk.
    import fcntl

    aggregation_lock = open(out.parent / "aggregation.lock", "a")
    fcntl.flock(aggregation_lock, fcntl.LOCK_EX)
    db = duckdb.connect(str(out / "counts.duckdb"))
    db.execute("SET memory_limit='8GB'")
    db.execute("SET threads=4")
    spill = out / "spill"
    spill.mkdir(exist_ok=True)
    db.execute("SET temp_directory=?", [str(spill)])
    for order in (2, 3):
        dest = out / f"counts-{order}.parquet"
        if not mixed.valid_parquet(dest):
            files = [
                str(out / "count-shards" / s["name"] / f"{order}-*.parquet")
                for s in sources
            ] + [str(original / f"counts-{order}.parquet")]
            db.execute(
                "COPY (SELECT key,sum(count)::BIGINT AS count FROM read_parquet(?) GROUP BY key ORDER BY key) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
                [files, str(dest)],
            )
        print(json.dumps(dict(model=name, phase="aggregate", order=order)), flush=True)
    prefix = out / "prefix.parquet"
    retained = out / "retained.parquet"
    compact = out / "compact-prefix.parquet"
    if not mixed.valid_parquet(prefix):
        db.execute(
            "COPY (SELECT key // ? AS key,sum(count)::BIGINT AS count FROM read_parquet(?) GROUP BY 1 ORDER BY 1) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [v, str(out / "counts-3.parquet"), str(prefix)],
        )
    if not mixed.valid_parquet(retained):
        db.execute(
            "COPY (SELECT * FROM read_parquet(?) WHERE count>=2 ORDER BY key) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [str(out / "counts-3.parquet"), str(retained)],
        )
    if not mixed.valid_parquet(compact):
        db.execute(
            "COPY (SELECT p.key,p.count FROM read_parquet(?) p JOIN (SELECT DISTINCT key // ? AS key FROM read_parquet(?)) t ON p.key=t.key ORDER BY p.key) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [str(prefix), v, str(retained), str(compact)],
        )
    # Validate integer sums before converting stored counts to float32.
    original_report = json.loads((original / "counted.json").read_text())
    uni = np.load(original / "unigrams.npy")
    for s in sources:
        uni += np.load(out / "count-shards" / s["name"] / "unigrams.npy")
    assert int(uni.sum()) == original_report["tokens"] + 800_000_000
    pairs = int(
        db.execute(
            "SELECT sum(count) FROM read_parquet(?)", [str(out / "counts-2.parquet")]
        ).fetchone()[0]
    )
    expected_pairs = sum(s["pairs"] for s in sources) + int(
        pq.read_table(original / "counts-2.parquet", columns=["count"])["count"]
        .to_numpy()
        .sum()
    )
    assert pairs == expected_pairs
    triples = int(
        db.execute(
            "SELECT sum(count) FROM read_parquet(?)", [str(out / "counts-3.parquet")]
        ).fetchone()[0]
    )
    expected_triples = sum(s["triples"] for s in sources) + int(
        pq.read_table(original / "counts-3.parquet", columns=["count"])["count"]
        .to_numpy()
        .sum()
    )
    assert triples == expected_triples
    db.close()

    def arrays(path):
        table = pq.read_table(path)
        return table["key"].to_numpy().copy(), table["count"].to_numpy().copy()

    meta = dict(
        tokenizer=SPECS[name][0],
        tokenizer_sha256=fingerprint,
        model_vocab_size=v,
        tokens=int(uni.sum()),
        document_boundaries_preserved=True,
        original_documents=980000,
        original_tokens=original_report["tokens"],
        added_tokens=800_000_000,
        new_corpus_mix="90% FineWeb-Edu / 5% Python-Edu / 5% FineMath by tokenizer-specific tokens; plus all original responses",
        sources=[
            {k: val for k, val in s.items() if k not in ("cache_dir", "started_at")}
            for s in sources
        ],
    )
    keys, counts = arrays(out / "counts-2.parquet")
    bg = BigramScorer(v, keys, counts, uni, metadata=meta)
    bg.save(out / "bigram_expanded.pt")
    del keys, counts
    keys, counts = arrays(retained)
    pk, pc = arrays(compact)
    torch.save(
        dict(
            version=1,
            vocab_size=v,
            triple_keys=torch.from_numpy(keys),
            triple_counts=torch.from_numpy(counts.astype(np.float32)),
            prefix_keys=torch.from_numpy(pk),
            prefix_counts=torch.from_numpy(pc.astype(np.float32)),
            alpha=50.0,
            metadata=dict(meta, storage_min_count=2),
        ),
        out / "trigram_expanded.pt",
    )
    tri = TrigramScorer.load(out / "trigram_expanded.pt", bigram=bg)
    query = tri.triple_keys[:: max(1, len(tri.triple_keys) // 10000)]
    result = tri.correction(
        query // v**2, query // v % v, query % v, bg, min_count=2, clip=2.0
    )
    assert torch.isfinite(result).all() and (result.abs() <= 2).all()
    report = dict(
        meta,
        model=name,
        retained_trigrams=len(keys),
        retained_prefixes=len(pk),
        pair_count_sum=pairs,
        triple_count_sum=triples,
        validation_queries=len(query),
        seconds=round(time.time() - start, 1),
        assets={
            f: dict(bytes=(out / f).stat().st_size, sha256=digest(out / f))
            for f in ("bigram_expanded.pt", "trigram_expanded.pt")
        },
    )
    (out / "complete.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)
    # Only remove reproducible intermediates owned by this completed expansion, to bound disk use.
    for file in (out / "count-shards").glob("*/*.parquet"):
        file.unlink()
    for file in out.glob("*.parquet"):
        file.unlink()
    for file in out.glob("*.duckdb*"):
        file.unlink()


if __name__ == "__main__":
    main()
