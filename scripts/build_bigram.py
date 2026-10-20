#!/usr/bin/env python3
"""Build sparse bigrams from tokenized JSONL or text JSONL with the exact backbone tokenizer."""
import argparse
import json
import sys
from itertools import islice
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from diffusion_lm.bigram import BigramScorer, tokenizer_fingerprint


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tokenizer", default="google/gemma-2-9b-it")
    p.add_argument("--vocab-size", type=int, help="Model output vocabulary size, if padded beyond the tokenizer vocabulary")
    p.add_argument("--cache-dir", default="base_models")
    p.add_argument("--input", type=Path, help='JSONL containing input_ids or text; document boundaries are preserved')
    p.add_argument("--response-eos", action="store_true", help="Match BYOD response targets: append EOS only to nontruncated saved-dataset responses")
    p.add_argument("--saved-dataset", type=Path, help="Local datasets.save_to_disk directory; retokenizes --text-column, ignoring stored IDs")
    p.add_argument("--arrow", type=Path, help="Existing local Arrow dataset (input_ids or text column)")
    p.add_argument("--local-files-only", action="store_true")
    p.add_argument("--dataset", default="wikitext", help="HF text dataset when --input is omitted")
    p.add_argument("--dataset-config", default="wikitext-2-raw-v1")
    p.add_argument("--split", default="train")
    p.add_argument("--text-column", default="text")
    p.add_argument("--max-documents", type=int, default=None, help="Default: all rows in the training split")
    p.add_argument("--alpha", type=float, default=10.0)
    p.add_argument("--beta", type=float, default=0.1)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    from transformers import AutoTokenizer
    tokenizer_kwargs = {"fix_mistral_regex": True} if "mistral" in args.tokenizer.lower() else {}
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, cache_dir=args.cache_dir,
                                            local_files_only=args.local_files_only, **tokenizer_kwargs)
    vocab_size = len(tokenizer) if args.vocab_size is None else args.vocab_size
    if vocab_size < len(tokenizer):
        p.error("--vocab-size cannot be smaller than the tokenizer vocabulary")
    metadata = dict(model_vocab_size=vocab_size, tokenizer=args.tokenizer, tokenizer_sha256=tokenizer_fingerprint(tokenizer),
                    source=str(args.input or args.arrow or args.saved_dataset) if (args.input or args.arrow or args.saved_dataset) else f"{args.dataset}/{args.dataset_config}",
                    split=args.split, max_documents=args.max_documents, text_column=args.text_column, response_eos=args.response_eos)
    if args.response_eos and not args.saved_dataset:
        p.error("--response-eos requires --saved-dataset")
    if args.max_documents is not None and args.max_documents < 1:
        p.error("--max-documents must be positive")
    def sequences():
        if args.saved_dataset:
            from datasets import load_from_disk, DatasetDict
            from tqdm import tqdm
            data = load_from_disk(str(args.saved_dataset))
            if isinstance(data, DatasetDict):
                data = data[args.split]
            if args.max_documents is not None:
                data = data.select(range(min(len(data), args.max_documents)))
            columns = [args.text_column] + (["answer_truncated"] if args.response_eos else [])
            data = data.select_columns(columns)
            metadata['documents'] = len(data)
            # Batched fast tokenization is much faster on the full corpus.
            for batch in tqdm(data.iter(batch_size=256), total=(len(data) + 255) // 256):
                encoded = tokenizer(batch[args.text_column], add_special_tokens=False)['input_ids']
                if args.response_eos:
                    if tokenizer.eos_token_id is None:
                        raise ValueError('The response tokenizer must have an EOS token')
                    for ids, truncated in zip(encoded, batch['answer_truncated']):
                        yield ids if truncated else ids + [tokenizer.eos_token_id]
                else:
                    yield from encoded
            return
        if args.input:
            with args.input.open() as f:
                for line in islice(f, args.max_documents):
                    row = json.loads(line)
                    yield row["input_ids"] if "input_ids" in row else tokenizer.encode(row[args.text_column], add_special_tokens=False)
        elif args.arrow:
            from datasets import Dataset
            data = Dataset.from_file(str(args.arrow))
            for row in islice(data, args.max_documents):
                yield row["input_ids"] if "input_ids" in row else tokenizer.encode(row[args.text_column], add_special_tokens=False)
        else:
            from datasets import load_dataset
            data = load_dataset(args.dataset, args.dataset_config, split=args.split, streaming=True)
            for row in islice(data, args.max_documents):
                yield tokenizer.encode(row[args.text_column], add_special_tokens=False)
    scorer = BigramScorer.from_sequences(sequences(), vocab_size, alpha=args.alpha, beta=args.beta, metadata=metadata)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    scorer.save(args.output)
    report = dict(path=str(args.output), checkpoint_version=2,
                  successor_tokens=int(scorer.successor_counts.double().sum()),
                  successor_marginal="additive-beta-smoothed successor counts from observed pairs", observed_pairs=len(scorer.pair_keys), tokens=int(scorer.unigram_counts.double().sum()), **metadata)
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
