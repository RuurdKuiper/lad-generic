#!/usr/bin/env python3
"""Read-only audit of remote sources before removing local Hugging Face caches.

Records exact revisions and local metadata. Never deletes or uploads anything.
Run from the research repository with HF_TOKEN set (or stored in .env).
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import HfApi, get_hf_file_metadata, hf_hub_url
import requests

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/maintenance/remote-sources.json')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f'Preserving existing audit: {args.output}; choose another --output.')
    load_dotenv(ROOT / '.env')
    token = os.getenv('HF_TOKEN')
    api = HfApi(token=token)
    records = []
    metadata = {}
    # Hub snapshot paths preserve exact upstream filenames and revisions.
    for cache in (ROOT / 'base_models', ROOT / 'data/huggingface', ROOT / 'data/huggingface/prepared-hub'):
        for folder in sorted(cache.glob('*--*')):
            if not (folder / 'snapshots').is_dir():
                continue
            kind, owner, name = folder.name.split('--', 2)
            for snapshot in sorted((folder / 'snapshots').iterdir()):
                records.append(dict(path=str(snapshot.relative_to(ROOT)), repo=f'{owner}/{name}',
                                    repo_type='dataset' if kind == 'datasets' else 'model',
                                    revision=snapshot.name, kind='snapshot'))
    # Arrow cache directories use upstream repository commit hashes.
    for info_path in sorted((ROOT / 'data/huggingface').glob('*/*/*/*/dataset_info.json')):
        relative = info_path.relative_to(ROOT)
        owner, name = relative.parts[2].split('___', 1)
        info = json.loads(info_path.read_text())
        # Cache folder names normalize case; canonical IDs are returned by the Hub.
        records.append(dict(path=str(info_path.parent.relative_to(ROOT)), repo=f'{owner}/{name}',
                            repo_type='dataset', revision=info_path.parent.name,
                            config=relative.parts[3], kind='dataset_cache'))
        metadata[str(relative)] = info
    for folder in sorted((ROOT / 'data').glob('lad-training-*')):
        if not folder.is_dir():
            continue
        records.append(dict(path=str(folder.relative_to(ROOT)), repo='Ruurd/LAD-training-' + folder.name.removeprefix('lad-training-'),
                            repo_type='dataset', revision='main', kind='saved_dataset'))
        # Preserve all small, local dataset metadata before removing any payloads.
        for p in folder.rglob('*.json'):
            metadata[str(p.relative_to(ROOT))] = json.loads(p.read_text())
    for p in (ROOT / 'data').glob('byod-prepared/*/publication.json'):
        prepared = json.loads(p.read_text())
        metadata[str(p.relative_to(ROOT))] = prepared
        records.append(dict(path=str(p.parent.relative_to(ROOT)), repo='Ruurd/BYOD-tokenized-256',
                            repo_type='dataset', revision='2c9d2d97e2b45302cd3f3267fd1c232ff9e9b1a3',
                            kind='prepared_dataset', profile=prepared['profile']))
    publication = ROOT / 'data/byod-tokenized-publication.json'
    if publication.exists():
        metadata[str(publication.relative_to(ROOT))] = json.loads(publication.read_text())

    def verify(record):
        record = dict(record)
        try:
            info = api.repo_info(record['repo'], repo_type=record['repo_type'],
                                 revision=record['revision'], files_metadata=True, timeout=30)
            record.update(repo=info.id, revision=info.sha,
                          url=f'https://huggingface.co/{"datasets/" if record["repo_type"] == "dataset" else ""}{info.id}/tree/{info.sha}')
            files = {f.rfilename: f for f in info.siblings}
            payloads = [n for n in files if n.endswith(('.parquet', '.arrow', '.safetensors', '.bin'))]
            if payloads:
                # Check download authorization, not just public repository metadata.
                payload = payloads[0]
                get_hf_file_metadata(hf_hub_url(info.id, payload, repo_type=record['repo_type'],
                                               revision=info.sha), token=token, timeout=30)
                record['accessible_payload'] = payload
            if record['kind'] == 'snapshot':
                checked = []
                mismatches = []
                snapshot = ROOT / record['path']
                for path in sorted(snapshot.rglob('*')):
                    if not path.is_file():
                        continue
                    name = str(path.relative_to(snapshot))
                    remote = files.get(name)
                    if remote is None or remote.size != path.stat().st_size:
                        mismatches.append(name)
                        continue
                    # Cache blob names are upstream content identifiers. Check the
                    # mapping as well as size so similarly named revisions cannot pass.
                    expected = remote.lfs.sha256 if remote.lfs else remote.blob_id
                    if path.is_symlink() and path.resolve().name == expected:
                        checked.append(name)
                    else:
                        content = path.read_bytes()
                        digest = hashlib.sha256(content).hexdigest() if remote.lfs else hashlib.sha1(
                            f'blob {len(content)}\0'.encode() + content).hexdigest()
                        (checked if digest == expected else mismatches).append(name)
                record.update(verified=bool(checked) and not mismatches, checked_files=checked, mismatches=mismatches)
            elif record['kind'] == 'prepared_dataset':
                name = f'prepared/{record["profile"]}.json'
                url = hf_hub_url(info.id, name, repo_type='dataset', revision=info.sha)
                response = requests.get(url, headers={'Authorization': f'Bearer {token}'} if token else {}, timeout=30)
                response.raise_for_status()
                record['publication_matches'] = response.json() == metadata[record['path'] + '/publication.json']
                record['verified'] = record['publication_matches'] and bool(payloads)
            else:
                payloads = [n for n in files if n.endswith(('.parquet', '.arrow'))]
                record.update(verified=bool(payloads), payload_files=payloads)
                if record['kind'] == 'saved_dataset':
                    record['remote_dataset_info'] = (info.card_data.to_dict() if info.card_data else {}).get('dataset_info')
                    manifest_url = f'https://huggingface.co/datasets/{info.id}/resolve/{info.sha}/manifest.json'
                    response = requests.get(manifest_url, headers={'Authorization': f'Bearer {token}'} if token else {}, timeout=30)
                    local = json.loads((ROOT / record['path'] / 'manifest.json').read_text())
                    record['manifest_matches'] = response.status_code == 200 and response.json() == local
                    record['manifest_http_status'] = response.status_code
                    record['verified'] = record['verified'] and record['manifest_matches']
            print(f'{record["path"]}: {"verified" if record["verified"] else "KEEP"}', flush=True)
        except Exception as exc:
            # Avoid exception URLs/headers that could contain credentials.
            record.update(verified=False, error_type=type(exc).__name__)
            print(f'{record["path"]}: KEEP ({type(exc).__name__})', flush=True)
        return record

    with ThreadPoolExecutor(max_workers=4) as pool:
        verified = list(pool.map(verify, records))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(checked_at=datetime.now(timezone.utc).isoformat(),
                                          records=verified, preserved_metadata=metadata), indent=2) + '\n')
    print(f'Recorded {len(verified)} sources in {args.output}')


if __name__ == '__main__':
    main()
