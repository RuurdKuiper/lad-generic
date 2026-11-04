#!/usr/bin/env python3
"""Restore one verified source from the pre-cleanup audit at its exact revision."""
import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', required=True, help='Exact record path from remote-sources.json')
    parser.add_argument('--tokenizer-only', action='store_true', help='Restore tokenizer files without model weights')
    args = parser.parse_args()
    audit = json.loads((ROOT / 'docs/maintenance/remote-sources.json').read_text())
    matches = [r for r in audit['records'] if r['path'] == args.path and r.get('verified')]
    if len(matches) != 1:
        parser.error('Choose one verified record path from the audit.')
    record = matches[0]
    relative = Path(record['path'])
    if relative.is_absolute() or '..' in relative.parts:
        parser.error('Unsafe path in audit.')
    load_dotenv(ROOT / '.env')
    token = os.getenv('HF_TOKEN')
    if record['kind'] == 'snapshot':
        patterns = record['checked_files']
        if args.tokenizer_only:
            patterns = [p for p in patterns if p.endswith(('.json', '.txt', '.model', '.tiktoken', '.jinja'))
                        and not p.endswith('.safetensors.index.json')]
        cache = ROOT / relative.parent.parent.parent
        restored = Path(snapshot_download(record['repo'], repo_type=record['repo_type'], revision=record['revision'],
                                         cache_dir=cache, allow_patterns=patterns, token=token))
        expected = ROOT / relative
        if restored != expected and not expected.exists():
            # The old Meta-Llama repository name redirects to the canonical name.
            expected.parent.mkdir(parents=True, exist_ok=True)
            expected.symlink_to(os.path.relpath(restored, expected.parent), target_is_directory=True)
        print(restored)
    elif record['kind'] in {'dataset_cache', 'prepared_dataset'}:
        if args.tokenizer_only:
            parser.error('--tokenizer-only requires a model snapshot record.')
        from datasets import load_dataset
        data = load_dataset(record['repo'], record.get('config', record.get('profile')),
                            revision=record['revision'], cache_dir=str(ROOT / 'data/huggingface'), token=token)
        if record['kind'] == 'prepared_dataset':
            destination = ROOT / relative
            if destination.exists():
                raise FileExistsError(f'Preserving existing preparation: {destination}')
            data.save_to_disk(str(destination))
            metadata = audit['preserved_metadata'][str(relative / 'publication.json')]
            (destination / 'publication.json').write_text(json.dumps(metadata, indent=2) + '\n')
        print(data)
    else:
        parser.error('This source was retained locally; no automatic restore is provided.')


if __name__ == '__main__':
    main()
