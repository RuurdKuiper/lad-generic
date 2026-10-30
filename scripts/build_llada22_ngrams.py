#!/usr/bin/env python3
"""Build tokenizer-matched LLaDA2.2 scorers from the existing pinned corpus."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_MODULES_CACHE", str(ROOT / "artifacts/llada22/modules"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "huggingface/llada22_space"))
import build_mixed_ngrams as mixed
from streaming import MODEL_ID, MODEL_REVISION


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tokenizer", default=str(ROOT / "artifacts/llada22/tokenizer"))
    p.add_argument("--sources", nargs="+", choices=["english", "python", "math", "responses"])
    p.add_argument("--count-only", action="store_true")
    args = p.parse_args()
    if args.sources and not args.count_only:
        p.error("--sources requires --count-only")
    from transformers import AutoTokenizer
    from diffusion_lm.bigram import BigramScorer, tokenizer_fingerprint
    from diffusion_lm.trigram import TrigramScorer
    import torch
    torch.set_num_threads(4)
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, trust_remote_code=True,
                                            local_files_only=True)
    tokenizer.model_max_length = 10**12
    fingerprint = tokenizer_fingerprint(tokenizer)
    mixed.OUT = ROOT / "artifacts/llada22/ngrams"
    mixed.V = 157184
    mixed.OUT.mkdir(parents=True, exist_ok=True)
    reference = ROOT / "artifacts/bigram/llada_expanded_ngrams"
    prior = {s["name"]: s for s in json.loads((reference / "training_report.json").read_text())["sources"]}
    sources = [dict(s, files=prior[s["name"]]["files"], offline=True,
                    cache_dir=str(reference / "hf-cache"), tokenizer_sha256=fingerprint)
               for s in mixed.SOURCES]
    sources.append(dict(name="responses", local=str(ROOT / "data/lad-training-1m-256-long"),
                        tokens=None, tokenizer_sha256=fingerprint))
    (mixed.OUT / "plan.json").write_text(json.dumps(dict(model=MODEL_ID, revision=MODEL_REVISION,
                                                       sources=sources), indent=2) + "\n")
    metadata = [mixed.tokenize_source(s, tokenizer) for s in sources
                if not args.sources or s["name"] in args.sources]
    if args.count_only:
        return
    mixed.aggregate(metadata, tokenizer, tokenizer_id=MODEL_ID,
                    model_revision=MODEL_REVISION, compact_prefix=True)
    bg = BigramScorer.load(mixed.OUT / "bigram_expanded.pt", tokenizer=tokenizer)
    tg = TrigramScorer.load(mixed.OUT / "trigram_expanded.pt", bigram=bg)
    query = tg.triple_keys[::max(1, len(tg.triple_keys) // 10000)]
    correction = tg.correction(query // mixed.V**2, query // mixed.V % mixed.V,
                               query % mixed.V, bg, min_count=2, clip=2.0)
    assert torch.isfinite(correction).all() and (correction.abs() <= 2).all()
    report = json.loads((mixed.OUT / "training_report.json").read_text())
    report["assets"] = {}
    for name in ("bigram_expanded.pt", "trigram_expanded.pt"):
        path = mixed.OUT / name
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
                h.update(chunk)
        report["assets"][name] = dict(bytes=path.stat().st_size, sha256=h.hexdigest())
    report["validation_queries"] = len(query)
    (mixed.OUT / "complete.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(dict(complete=True, tokens=report["tokens"], assets=report["assets"])), flush=True)


if __name__ == "__main__":
    main()
