#!/usr/bin/env python3
"""Count model-specific trigrams on the complete original BYOD response corpus.

Verify reconstructed bigrams/unigrams against the deployed checkpoint before
publishing any triples. Bounded shards preserve per-document EOS policy.
"""

import argparse, hashlib, json, os, time
from pathlib import Path

os.environ.setdefault("RAYON_NUM_THREADS", "2")
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import torch
from build_mixed_ngrams import valid_parquet

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/bigram/byod_trigrams"
SPECS = dict(
    gemma=("google/gemma-2-9b-it", "gemma.pt"),
    llama=("meta-llama/Llama-3.1-8B-Instruct", "llama.pt"),
    qwen=("Qwen/Qwen2.5-7B-Instruct", "qwen.pt"),
    ministral=("mistralai/Ministral-8B-Instruct-2410", "ministral.pt"),
)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", choices=list(SPECS), required=True)
    args = p.parse_args()
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from diffusion_lm.bigram import BigramScorer, tokenizer_fingerprint
    from diffusion_lm.trigram import TrigramScorer
    from transformers import AutoTokenizer
    from datasets import load_from_disk
    import duckdb

    torch.set_num_threads(2)
    name = args.model
    tokenizer_name, checkpoint = SPECS[name]
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)
    if (folder / "complete.json").exists() and (
        folder / "trigram_expanded.pt"
    ).is_file():
        record = json.loads((folder / "complete.json").read_text())
        if (
            hashlib.sha256((folder / "trigram_expanded.pt").read_bytes()).hexdigest()
            != record["checkpoint_sha256"]
        ):
            raise ValueError(
                "Existing trigram checkpoint does not match its training report"
            )
        print(json.dumps(record))
        return
    bg = BigramScorer.load(ROOT / "artifacts/bigram" / checkpoint)
    snapshots = list(
        (
            ROOT
            / "base_models"
            / ("models--" + tokenizer_name.replace("/", "--"))
            / "snapshots"
        ).glob("*")
    )
    assert len(snapshots) == 1, "Select the exact pinned tokenizer snapshot"
    tokenizer = AutoTokenizer.from_pretrained(
        snapshots[0],
        local_files_only=True,
        **({"fix_mistral_regex": True} if name == "ministral" else {}),
    )
    tokenizer.model_max_length = 10**12
    assert tokenizer_fingerprint(tokenizer) == bg.metadata["tokenizer_sha256"]
    source = ROOT / "data/lad-training-1m-256-long"
    data = load_from_disk(str(source))["train"]
    assert len(data) == bg.metadata["documents"] == 980000
    shards = folder / "shards"
    shards.mkdir(exist_ok=True)
    counted = folder / "counted.json"
    start = time.time()
    counts_available = all(
        valid_parquet(folder / f"counts-{order}.parquet")
        or (
            (files := list(shards.glob(f"{order}-*.parquet")))
            and all(valid_parquet(file) for file in files)
        )
        for order in (2, 3)
    )
    if not (
        counted.exists() and (folder / "unigrams.npy").is_file() and counts_available
    ):
        counted.unlink(missing_ok=True)
        for f in shards.glob("*.parquet"):
            f.unlink()
        uni = np.zeros(bg.vocab_size, dtype=np.int64)
        pairs = []
        triples = []
        tokens = 0
        docs = 0
        buffered = 0
        chunk = 0

        def flush():
            nonlocal chunk, buffered
            for order, arrays in [(2, pairs), (3, triples)]:
                values = (
                    np.concatenate(arrays) if arrays else np.array([], dtype=np.int64)
                )
                keys, counts = np.unique(values, return_counts=True)
                pq.write_table(
                    pa.table({"key": keys, "count": counts.astype(np.int64)}),
                    shards / f"{order}-{chunk:05d}.parquet",
                    compression="zstd",
                )
                arrays.clear()
            chunk += 1
            buffered = 0

        for batch in data.select_columns(["output", "answer_truncated"]).iter(
            batch_size=256
        ):
            encoded = tokenizer(batch["output"], add_special_tokens=False)["input_ids"]
            for sequence, truncated in zip(encoded, batch["answer_truncated"]):
                if not truncated:
                    sequence.append(tokenizer.eos_token_id)
                ids = np.asarray(sequence, dtype=np.int64)
                if len(ids) and (ids.min() < 0 or ids.max() >= bg.vocab_size):
                    raise ValueError("Tokenizer ID out of model vocabulary")
                np.add.at(uni, ids, 1)
                pairs.append(ids[:-1] * bg.vocab_size + ids[1:])
                triples.append(
                    (ids[:-2] * bg.vocab_size + ids[1:-1]) * bg.vocab_size + ids[2:]
                )
                tokens += len(ids)
                buffered += len(ids)
                docs += 1
                if buffered >= 2_000_000:
                    flush()
                    print(
                        json.dumps(
                            dict(
                                model=name,
                                phase="count",
                                documents=docs,
                                tokens=tokens,
                                seconds=round(time.time() - start),
                            )
                        ),
                        flush=True,
                    )
        if buffered:
            flush()
        np.save(folder / "unigrams.npy", uni)
        counted.write_text(
            json.dumps(
                dict(
                    documents=docs,
                    tokens=tokens,
                    source="data/lad-training-1m-256-long",
                    tokenizer_sha256=tokenizer_fingerprint(tokenizer),
                ),
                indent=2,
            )
            + "\n"
        )
    report = json.loads(counted.read_text())
    assert report["tokenizer_sha256"] == bg.metadata["tokenizer_sha256"]
    db = duckdb.connect(str(folder / "counts.duckdb"))
    db.execute("SET memory_limit='512MB'")
    db.execute("SET threads=2")
    spill = folder / "spill"
    spill.mkdir(exist_ok=True)
    db.execute("SET temp_directory=?", [str(spill)])
    for order in [2, 3]:
        target = folder / f"counts-{order}.parquet"
        if not valid_parquet(target):
            db.execute(
                "COPY (SELECT key,sum(count)::BIGINT AS count FROM read_parquet(?) GROUP BY key ORDER BY key) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
                [str(shards / f"{order}-*.parquet"), str(target)],
            )
        print(json.dumps(dict(model=name, phase="aggregate", order=order)), flush=True)

    def arrays(path):
        t = pq.read_table(path)
        return np.asarray(t["key"]).copy(), np.asarray(t["count"]).copy()

    keys, counts = arrays(folder / "counts-2.parquet")
    assert np.array_equal(keys, bg.pair_keys.numpy()) and np.array_equal(
        counts, bg.pair_counts.numpy()
    ), "Reconstructed bigrams differ from deployed corpus/tokenization"
    assert np.array_equal(
        np.load(folder / "unigrams.npy"), bg.unigram_counts.numpy()
    ), "Unigram mismatch"
    del keys, counts
    prefix = folder / "prefix.parquet"
    filtered = folder / "retained.parquet"
    compact = folder / "compact-prefix.parquet"
    if not valid_parquet(prefix):
        db.execute(
            "COPY (SELECT key // ? AS key,sum(count)::BIGINT AS count FROM read_parquet(?) GROUP BY 1 ORDER BY 1) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [bg.vocab_size, str(folder / "counts-3.parquet"), str(prefix)],
        )
    if not valid_parquet(filtered):
        db.execute(
            "COPY (SELECT * FROM read_parquet(?) WHERE count>=2 ORDER BY key) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [str(folder / "counts-3.parquet"), str(filtered)],
        )
    if not valid_parquet(compact):
        db.execute(
            "COPY (SELECT p.key,p.count FROM read_parquet(?) p INNER JOIN (SELECT DISTINCT key // ? AS key FROM read_parquet(?)) t ON p.key=t.key ORDER BY p.key) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [str(prefix), bg.vocab_size, str(filtered), str(compact)],
        )
    db.close()
    keys, counts = arrays(filtered)
    pk, pc = arrays(compact)
    meta = dict(
        bg.metadata,
        storage_min_count=2,
        training_tokens=report["tokens"],
        document_boundaries_preserved=True,
        original_bigram_counts_verified=True,
        source_bigram_sha256=hashlib.sha256(
            (ROOT / "artifacts/bigram" / checkpoint).read_bytes()
        ).hexdigest(),
    )
    target = folder / "trigram_expanded.pt"
    torch.save(
        dict(
            version=1,
            vocab_size=bg.vocab_size,
            triple_keys=torch.from_numpy(keys),
            triple_counts=torch.from_numpy(counts.astype(np.float32)),
            prefix_keys=torch.from_numpy(pk),
            prefix_counts=torch.from_numpy(pc.astype(np.float32)),
            alpha=50.0,
            metadata=meta,
        ),
        target,
    )
    tri = TrigramScorer.load(target, bigram=bg)
    query = tri.triple_keys[:: max(1, len(tri.triple_keys) // 10000)]
    result = tri.correction(
        query // bg.vocab_size**2,
        query // bg.vocab_size % bg.vocab_size,
        query % bg.vocab_size,
        bg,
        min_count=2,
        clip=2.0,
    )
    assert torch.isfinite(result).all() and (result.abs() <= 2).all()
    report.update(
        model=name,
        vocab_size=bg.vocab_size,
        retained_trigrams=len(keys),
        retained_prefixes=len(pk),
        checkpoint_bytes=target.stat().st_size,
        checkpoint_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        exact_bigram_match=True,
        exact_unigram_match=True,
        correction_queries=len(query),
        seconds=round(time.time() - start, 1),
    )
    (folder / "complete.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
