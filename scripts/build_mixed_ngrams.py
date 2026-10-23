#!/usr/bin/env python3
"""Train bounded-memory, document-local bigram/trigram counts on a pinned HF mix."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

os.environ.setdefault("RAYON_NUM_THREADS", "8")
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/bigram/llada_expanded_ngrams"
V = 126464
SOURCES = [
    dict(
        name="english",
        repo="HuggingFaceFW/fineweb-edu",
        revision="87f09149ef4734204d70ed1d046ddc9ca3f2b8f9",
        prefix="sample/10BT/",
        tokens=720_000_000,
    ),
    dict(
        name="python",
        repo="Avelina/python-edu-cleaned",
        revision="3fedf55e02e72dd1fd68963f991f5e91adcb0f8d",
        prefix="data/",
        tokens=40_000_000,
        upstream="HuggingFaceTB/smollm-corpus/python-edu",
    ),
    dict(
        name="math",
        repo="HuggingFaceTB/finemath",
        revision="e92b25a616738fe95dc186b64dfb19f9c8525594",
        prefix="finemath-4plus/",
        tokens=40_000_000,
    ),
]


def valid_parquet(path):
    """A partial COPY output must not be treated as a completed aggregation."""
    try:
        pq.ParquetFile(path).metadata
    except (OSError, pa.ArrowInvalid):
        return False
    return True


def write_chunk(folder, index, arrays2, arrays3):
    for order, arrays in [(2, arrays2), (3, arrays3)]:
        values = np.concatenate(arrays) if arrays else np.array([], dtype=np.int64)
        keys, counts = np.unique(values, return_counts=True)
        pq.write_table(
            pa.table({"key": keys, "count": counts.astype(np.int64)}),
            folder / f"{order}-{index:05d}.parquet",
            compression="zstd",
        )


def tokenize_source(spec, tokenizer):
    from huggingface_hub import HfApi, hf_hub_download

    folder = OUT / "count-shards" / spec["name"]
    folder.mkdir(parents=True, exist_ok=True)
    done = folder / "complete.json"
    if done.exists():
        record = json.loads(done.read_text())
        if any(
            record.get(k) != spec.get(k)
            for k in ["repo", "revision", "prefix", "tokens", "local"]
        ):
            raise RuntimeError(
                f"Completed source differs from requested plan: {spec['name']}"
            )
        if (folder / "unigrams.npy").is_file() and all(
            (files := list(folder.glob(f"{order}-*.parquet")))
            and all(valid_parquet(f) for f in files)
            for order in (2, 3)
        ):
            return record
    # A source is atomic for resume: partial counts are task-owned rebuildables.
    done.unlink(missing_ok=True)
    for file in folder.glob("*.parquet"):
        file.unlink()
    metadata = dict(
        spec,
        documents=0,
        actual_tokens=0,
        pairs=0,
        triples=0,
        skipped_duplicates=0,
        files=[],
        eos_appended=0,
    )
    metadata["started_at"] = time.time()
    seen = set()
    uni = np.zeros(V, dtype=np.int64)
    arrays2 = []
    arrays3 = []
    buffered = 0
    chunk = 0

    def consume(sequences):
        nonlocal buffered, chunk
        for sequence in sequences:
            ids = np.asarray(sequence, dtype=np.int64)
            if spec.get("tokens") is not None:
                remaining = spec["tokens"] - metadata["actual_tokens"]
                if remaining <= 0:
                    return True
                ids = ids[:remaining]
            if not len(ids):
                continue
            np.add.at(uni, ids, 1)
            metadata["eos_appended"] += int(ids[-1] == tokenizer.eos_token_id)
            arrays2.append(ids[:-1] * V + ids[1:])
            arrays3.append((ids[:-2] * V + ids[1:-1]) * V + ids[2:])
            metadata["actual_tokens"] += len(ids)
            metadata["documents"] += 1
            metadata["pairs"] += max(0, len(ids) - 1)
            metadata["triples"] += max(0, len(ids) - 2)
            buffered += len(ids)
            if buffered >= 2_000_000:
                write_chunk(folder, chunk, arrays2, arrays3)
                arrays2.clear()
                arrays3.clear()
                buffered = 0
                chunk += 1
                print(
                    json.dumps(
                        dict(
                            source=spec["name"],
                            tokens=metadata["actual_tokens"],
                            documents=metadata["documents"],
                            seconds=round(time.time() - metadata["started_at"], 1),
                        )
                    ),
                    flush=True,
                )
        return False

    if "local" in spec:
        from datasets import load_from_disk, DatasetDict

        data = load_from_disk(spec["local"])
        data = data["train"] if isinstance(data, DatasetDict) else data
        for batch in data.select_columns(["output", "answer_truncated"]).iter(
            batch_size=256
        ):
            encoded = tokenizer(batch["output"], add_special_tokens=False)["input_ids"]
            for ids, truncated in zip(encoded, batch["answer_truncated"]):
                if not truncated:
                    ids.append(tokenizer.eos_token_id)
            consume(encoded)
    else:
        api = HfApi()
        files = spec.get("files") or sorted(
            f
            for f in api.list_repo_files(
                spec["repo"], repo_type="dataset", revision=spec["revision"]
            )
            if f.startswith(spec["prefix"]) and f.endswith(".parquet")
        )
        stop = False
        for file in files:
            local = hf_hub_download(
                spec["repo"],
                file,
                repo_type="dataset",
                revision=spec["revision"],
                cache_dir=spec.get("cache_dir", OUT / "hf-cache"),
                local_files_only=spec.get("offline", False),
            )
            metadata["files"].append(file)
            parquet = pq.ParquetFile(local)
            column = "text" if "text" in parquet.schema.names else "content"
            for batch in parquet.iter_batches(batch_size=128, columns=[column]):
                texts = []
                for text in batch.column(0).to_pylist():
                    if not isinstance(text, str) or len(text) < 80:
                        continue
                    digest = hashlib.blake2b(text.encode(), digest_size=16).digest()
                    if digest in seen:
                        metadata["skipped_duplicates"] += 1
                        continue
                    seen.add(digest)
                    texts.append(text)
                encoded = (
                    tokenizer(texts, add_special_tokens=False)["input_ids"]
                    if texts
                    else []
                )
                for ids in encoded:
                    ids.append(tokenizer.eos_token_id)
                stop = consume(encoded)
                if stop or metadata["actual_tokens"] >= spec["tokens"]:
                    stop = True
                    break
            if stop:
                break
        if metadata["actual_tokens"] < spec["tokens"]:
            raise RuntimeError("Source exhausted before token target")
    if arrays2 or arrays3:
        write_chunk(folder, chunk, arrays2, arrays3)
    np.save(folder / "unigrams.npy", uni)
    metadata["seconds"] = time.time() - metadata["started_at"]
    done.write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def aggregate(metadata, tokenizer):
    import duckdb
    import torch
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from diffusion_lm.bigram import BigramScorer, tokenizer_fingerprint

    db = duckdb.connect(str(OUT / "counts.duckdb"))
    db.execute("SET memory_limit='4GB'")
    db.execute("SET threads=6")
    spill = OUT / "spill"
    spill.mkdir(exist_ok=True)
    db.execute("SET temp_directory=?", [str(spill)])
    reports = {}
    for order in [2, 3]:
        dest = OUT / f"counts-{order}.parquet"
        if not valid_parquet(dest):
            glob = [
                str(OUT / "count-shards" / s["name"] / f"{order}-*.parquet")
                for s in metadata
            ]
            db.execute(
                "COPY (SELECT key, sum(count)::BIGINT AS count FROM read_parquet(?) GROUP BY key ORDER BY key) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
                [glob, str(dest)],
            )
        reports[order] = dict(
            rows=db.execute(
                "SELECT count(*) FROM read_parquet(?)", [str(dest)]
            ).fetchone()[0]
        )
        print(json.dumps(dict(aggregated_order=order, **reports[order])), flush=True)
    # Prefix totals include all triples, including singletons filtered from storage.
    prefix = OUT / "prefix-totals.parquet"
    if not valid_parquet(prefix):
        db.execute(
            "COPY (SELECT key // ? AS key,sum(count)::BIGINT AS count FROM read_parquet(?) GROUP BY 1 ORDER BY 1) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [V, str(OUT / "counts-3.parquet"), str(prefix)],
        )
    filtered = OUT / "trigrams-min2.parquet"
    if not valid_parquet(filtered):
        db.execute(
            "COPY (SELECT * FROM read_parquet(?) WHERE count>=2 ORDER BY key) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [str(OUT / "counts-3.parquet"), str(filtered)],
        )
    db.close()

    def arrays(path):
        table = pq.read_table(path)
        return np.asarray(table["key"]).copy(), np.asarray(table["count"]).copy()

    uni = sum(
        (np.load(OUT / "count-shards" / s["name"] / "unigrams.npy") for s in metadata),
        np.zeros(V, dtype=np.int64),
    )
    meta = dict(
        tokenizer="GSAI-ML/LLaDA-8B-Instruct",
        tokenizer_sha256=tokenizer_fingerprint(tokenizer),
        model_revision="08b83a6feb34df1a6011b80c3c00c7563e963b07",
        sources=[
            dict(s, local="data/lad-training-1m-256-long") if "local" in s else s
            for s in metadata
        ],
        tokens=int(uni.sum()),
        model_vocab_size=V,
        document_boundaries_preserved=True,
        raw_documents_eos=True,
        new_corpus_mix="90% FineWeb-Edu / 5% Python-Edu / 5% FineMath by LLaDA tokens; plus original responses",
    )
    keys, counts = arrays(OUT / "counts-2.parquet")
    scorer = BigramScorer(V, keys, counts, uni, metadata=meta)
    scorer.save(OUT / "bigram_expanded.pt")
    del keys, counts, scorer
    keys, counts = arrays(filtered)
    prefix_keys, prefix_counts = arrays(prefix)
    torch.save(
        dict(
            version=1,
            vocab_size=V,
            triple_keys=torch.from_numpy(keys),
            triple_counts=torch.from_numpy(counts.astype(np.float32)),
            prefix_keys=torch.from_numpy(prefix_keys),
            prefix_counts=torch.from_numpy(prefix_counts.astype(np.float32)),
            alpha=50.0,
            metadata=dict(meta, storage_min_count=2),
        ),
        OUT / "trigram_expanded.pt",
    )
    meta.update(
        aggregate_rows=reports,
        stored_trigrams=len(keys),
        stored_prefixes=len(prefix_keys),
        new_tokens=sum(
            s["actual_tokens"] for s in metadata if s["name"] != "responses"
        ),
    )
    (OUT / "training_report.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps({k: v for k, v in meta.items() if k != "sources"}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-original", action="store_true")
    parser.add_argument(
        "--sources", nargs="+", choices=["english", "python", "math", "responses"]
    )
    parser.add_argument("--count-only", action="store_true")
    args = parser.parse_args()
    from dotenv import load_dotenv
    from transformers import AutoTokenizer

    load_dotenv(ROOT / ".env")
    OUT.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(
        ROOT
        / "base_models/models--GSAI-ML--LLaDA-8B-Instruct/snapshots/08b83a6feb34df1a6011b80c3c00c7563e963b07",
        local_files_only=True,
    )
    tokenizer.model_max_length = 10**12
    sources = list(SOURCES)
    if not args.skip_original:
        sources.append(
            dict(
                name="responses",
                local=str(ROOT / "data/lad-training-1m-256-long"),
                tokens=None,
            )
        )
    if args.sources and not args.count_only:
        parser.error("--sources requires --count-only")
    if args.sources:
        sources = [s for s in sources if s["name"] in args.sources]
    if not args.count_only:
        (OUT / "plan.json").write_text(json.dumps(sources, indent=2) + "\n")
    metadata = [tokenize_source(spec, tokenizer) for spec in sources]
    if not args.count_only:
        aggregate(metadata, tokenizer)


if __name__ == "__main__":
    main()
