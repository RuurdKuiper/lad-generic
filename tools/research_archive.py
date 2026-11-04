#!/usr/bin/env python3
"""Verify or extract the frozen historical decoding workspace into a new folder."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'archives/decoding-studies-2026-11-04.tar.gz'
MANIFEST = ROOT / 'archives/decoding-studies-2026-11-04.manifest.json'


def verify():
    manifest = json.loads(MANIFEST.read_text())
    if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != manifest['archive_sha256']:
        raise ValueError('Research archive checksum mismatch')
    seen = set()
    with tarfile.open(ARCHIVE, 'r:gz') as bundle:
        for member in bundle:
            path = Path(member.name)
            if not member.isfile() or path.is_absolute() or '..' in path.parts or '.git' in path.parts or member.name in seen:
                raise ValueError(f'Unsafe or duplicate archive member: {member.name}')
            expected = manifest['files'][member.name]
            data = bundle.extractfile(member).read()
            if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']:
                raise ValueError(f'Archive member checksum mismatch: {member.name}')
            seen.add(member.name)
    if seen != set(manifest['files']):
        raise ValueError('Missing research archive members')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', type=Path, help='New destination; existing directories are never overwritten')
    args = parser.parse_args()
    manifest = verify()
    if args.extract:
        args.extract.mkdir(parents=True, exist_ok=False)
        with tarfile.open(ARCHIVE, 'r:gz') as bundle:
            for member in bundle:
                target = args.extract / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(bundle.extractfile(member).read())
        print(f'Extracted {len(manifest["files"])} verified files to {args.extract}')
    else:
        print(f'Verified {len(manifest["files"])} historical files in {ARCHIVE.name}')


if __name__ == '__main__':
    main()
