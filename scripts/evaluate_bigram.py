#!/usr/bin/env python3
"""Evaluate held-out response likelihood under sparse bigram and unigram backoff."""
import argparse
import json
import math
import sys
from pathlib import Path

import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from diffusion_lm.bigram import BigramScorer


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--dataset', type=Path, required=True)
    p.add_argument('--split', default='validation')
    p.add_argument('--text-column', default='output')
    p.add_argument('--tokenizer', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    from datasets import load_from_disk
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, local_files_only=True)
    model = BigramScorer.load(args.checkpoint, tokenizer=tokenizer)
    torch.set_num_threads(1)
    response_eos = model.metadata.get('response_eos', False)
    columns = [args.text_column] + (['answer_truncated'] if response_eos else [])
    data = load_from_disk(str(args.dataset))[args.split].select_columns(columns)
    bigram_nll = unigram_nll = 0.
    count = unseen = 0
    with torch.inference_mode():
        for batch in data.iter(batch_size=256):
            sequences = tokenizer(batch[args.text_column], add_special_tokens=False)['input_ids']
            if response_eos:
                sequences = [ids if truncated else ids + [tokenizer.eos_token_id]
                             for ids, truncated in zip(sequences, batch['answer_truncated'])]
            previous = torch.tensor([i for seq in sequences for i in seq[:-1]])
            following = torch.tensor([i for seq in sequences for i in seq[1:]])
            if not len(previous):
                continue
            bigram_nll -= float(model.log_prob(previous, following).double().sum())
            unigram_nll -= float(model.unigram[following].log().double().sum())
            count += len(previous)
            query = previous * model.vocab_size + following
            index = torch.searchsorted(model.pair_keys, query).clamp_max(len(model.pair_keys)-1)
            unseen += int((model.pair_keys[index] != query).sum())
    report = dict(split=args.split, response_eos=response_eos, documents=len(data), transitions=count,
        bigram_nll_per_token=bigram_nll/count, unigram_nll_per_token=unigram_nll/count,
        bigram_perplexity=math.exp(bigram_nll/count), unigram_perplexity=math.exp(unigram_nll/count),
        unseen_fraction=unseen/count, note='Response likelihood evaluates the scorer; it is not a diffusion generation quality metric.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
