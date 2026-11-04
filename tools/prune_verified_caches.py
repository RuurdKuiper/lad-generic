#!/usr/bin/env python3
"""Remove only verified, untracked caches listed in a saved remote-source audit.

Defaults to a dry run. Locally built mixtures without matching remote manifests
and caches whose upstream source cannot be verified are always retained.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def candidates(records):
    targets = set()
    snapshots = {}
    for record in records:
        path = Path(record['path'])
        if path.is_absolute() or '..' in path.parts:
            raise ValueError(f'Unsafe audit path: {path}')
        if record['kind'] == 'snapshot':
            if len(path.parts) < 4 or path.parent.name != 'snapshots':
                raise ValueError(f'Invalid snapshot path: {path}')
            folder = path.parent.parent
            snapshots.setdefault(folder, []).append(record)
        elif record.get('verified') and record['kind'] == 'dataset_cache':
            if path.parts[:2] != ('data', 'huggingface') or len(path.parts) != 6:
                raise ValueError(f'Invalid dataset cache: {path}')
            targets.add(path)
        elif record.get('verified') and record['kind'] == 'prepared_dataset':
            if path.parts[:2] != ('data', 'byod-prepared') or len(path.parts) != 3:
                raise ValueError(f'Invalid prepared cache: {path}')
            targets.add(path)
    for folder, entries in snapshots.items():
        if not (folder.parts[0] == 'base_models' and len(folder.parts) == 2 or
                folder.parts[:2] == ('data', 'huggingface') and len(folder.parts) == 3 or
                folder.parts[:3] == ('data', 'huggingface', 'prepared-hub') and len(folder.parts) == 4):
            raise ValueError(f'Invalid Hub cache: {folder}')
        actual = {str(p.relative_to(ROOT)) for p in (ROOT / folder / 'snapshots').glob('*')}
        known = {entry['path'] for entry in entries}
        if all(entry.get('verified') for entry in entries) and actual <= known:
            targets.add(folder)
    return sorted(targets)


def validate_target(path, tracked):
    absolute = ROOT / path
    if absolute.is_symlink() or not absolute.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError(f'Cache resolves outside workspace: {path}')
    if any(name == str(path) or name.startswith(str(path) + '/') for name in tracked):
        raise ValueError(f'Cache contains tracked files: {path}')
    # Never follow a symlink to an external tree through a parent component.
    if any((ROOT / Path(*path.parts[:n])).is_symlink() for n in range(1, len(path.parts))):
        raise ValueError(f'Symlinked cache parent: {path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, default=ROOT / 'docs/maintenance/remote-sources.json')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    audit = json.loads(args.audit.read_text())
    targets = candidates(audit['records'])
    tracked = subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines()
    # Validate the complete plan before deleting any directory.
    for path in targets:
        validate_target(path, tracked)
    manifest = []
    for path in targets:
        absolute = ROOT / path
        if not absolute.is_dir():
            continue
        size = sum(p.stat().st_size for p in absolute.rglob('*') if p.is_file() and not p.is_symlink())
        print(f'{"REMOVE" if args.execute else "would remove"} {path}: {size / 1e9:.3f} GB', flush=True)
        manifest.append(dict(path=str(path), bytes=size))
    if args.execute:
        output = ROOT / 'docs/maintenance/removed-caches.json'
        if output.exists():
            raise FileExistsError('Preserving previous cleanup record; review it before another cleanup.')
        log = dict(created_at=datetime.now(timezone.utc).isoformat(), audit=str(args.audit.relative_to(ROOT)),
                   removed=[], planned=manifest)
        output.write_text(json.dumps(log, indent=2) + '\n')
        for item in manifest:
            shutil.rmtree(ROOT / item['path'])
            log['removed'].append(item)
            output.write_text(json.dumps(log, indent=2) + '\n')
    print(f'Total: {sum(item["bytes"] for item in manifest) / 1e9:.3f} GB')


if __name__ == '__main__':
    main()
