#!/usr/bin/env python3
"""Prepare or publish one native LLaDA-Instruct ZeroGPU Space on Ruurd's account."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
MODEL_ID = 'GSAI-ML/LLaDA-8B-Instruct'
MODEL_REVISION = '08b83a6feb34df1a6011b80c3c00c7563e963b07'
SPACE_ID = 'Ruurd/llada-8b-instruct'


def make_space_bundle(destination: Path, checkpoint: Path = ROOT/'artifacts/bigram/llada.pt') -> None:
    """Use the same app and decoder, with a native-model loader and its own scorer."""
    if not checkpoint.is_file():
        raise FileNotFoundError(f'Build the LLaDA-tokenized bigram checkpoint first: {checkpoint}')
    destination.mkdir(parents=True, exist_ok=True)
    template = ROOT/'huggingface/byod_space'
    shutil.copy2(template/'app.py', destination/'app.py')
    requirements = (template/'requirements.txt').read_text().replace('transformers>=4.57.6,<5', 'transformers==4.57.6')
    (destination/'requirements.txt').write_text(requirements)
    shutil.copy2(checkpoint, destination/'bigram.pt')
    if checkpoint.with_suffix('.json').exists():
        shutil.copy2(checkpoint.with_suffix('.json'), destination/'bigram.json')
    shutil.copytree(ROOT/'src/diffusion_lm', destination/'src/diffusion_lm', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'))
    config = dict(model_backend='llada', model_repo_id=MODEL_ID, model_revision=MODEL_REVISION,
                  display_name='LLaDA-8B-Instruct', bigram_enabled=True, show_repository_links=True,
                  source_url='https://github.com/RuurdKuiper/lad-generic', visitor_counter_id='Ruurd.llada-8b-instruct')
    (destination/'space_model.json').write_text(json.dumps(config, indent=2)+'\n')
    (destination/'README.md').write_text(f'''---
title: LLaDA-8B-Instruct
emoji: 🌊
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 5.49.1
python_version: "3.12"
app_file: app.py
pinned: false
license: other
startup_duration_timeout: 1h
short_description: Native LLaDA with diffusion and PMI Viterbi decoding
models:
- {MODEL_ID}
---

# LLaDA-8B-Instruct

Loads the official [{MODEL_ID}](https://huggingface.co/{MODEL_ID}) directly in
BF16 on ZeroGPU. Model and tokenizer revision: `{MODEL_REVISION}`.

The interface shares the BYOD Gemma demo's decoding controls: temperature,
top-k, block diffusion, confidence-guided or random retention, PMI Viterbi,
ending delay, early stopping, and the live token visualization. The model
uses its native bidirectional forward pass, chat template, and mask token
126336. This is a comparison using the shared app decoder, not a claim to
reproduce the official benchmark sampler.

PMI uses a separate scorer trained on all 980,000 responses in the existing
training split, retokenized with LLaDA's tokenizer. It covers all 126,464
model output IDs, including output padding beyond the tokenizer vocabulary.
Scoring is PMI, retention confidence is diffusion probability, minimum count
is 1, and clipping is ±2. Edit the constants near the top of `app.py` to
change these defaults. Temperature and top-k are shared controls; bigram
weight is fixed at 0.5. Ending-delay strength remains adjustable.

LLaDA's available strategies are confidence-guided, random, and PMI Viterbi.
The adapter-based autoregressive confidence strategy applies to BYOD models.
The first request may take longer while ZeroGPU allocates hardware.
''')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/bigram/llada_space/bundle')
    parser.add_argument('--execute', action='store_true', help='Create and publish the new private Space; otherwise prepare files only')
    args = parser.parse_args()
    make_space_bundle(args.output)
    if not args.execute:
        print(json.dumps(dict(bundle=str(args.output), space=SPACE_ID, model=MODEL_ID, revision=MODEL_REVISION)))
        return
    from dotenv import load_dotenv
    from huggingface_hub import HfApi
    load_dotenv(ROOT/'.env')
    api = HfApi()
    if api.whoami()['name'].casefold() != 'ruurd':
        raise RuntimeError('Publishing requires the Ruurd account')
    # This command creates one new Space; it never overwrites existing Spaces.
    api.create_repo(SPACE_ID, repo_type='space', space_sdk='gradio', private=True, exist_ok=False)
    commit = api.upload_folder(repo_id=SPACE_ID, repo_type='space', folder_path=str(args.output),
                               commit_message='Deploy native LLaDA-Instruct with shared diffusion and PMI Viterbi controls')
    runtime = api.request_space_hardware(SPACE_ID, hardware='zero-a10g')
    record = dict(space=SPACE_ID, commit=commit.oid, model=MODEL_ID, model_revision=MODEL_REVISION,
                  requested_hardware='zero-a10g', visibility='private', stage=str(runtime.stage), bundle=str(args.output))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    (args.output.parent/'deployment.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
