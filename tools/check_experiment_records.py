#!/usr/bin/env python3
"""Verify canonical decoding evidence and the frozen historical source archive."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    sys.path.insert(0, str(ROOT / 'scripts'))
    from analyze_decoding_study import analyze, STUDY
    from research_archive import verify, MANIFEST
    result = analyze(STUDY)
    archive = verify()
    names = subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, text=True
    ).splitlines()
    checksums = {}
    for name in names:
        if name.startswith(('artifacts/', 'scripts/', 'src/', 'huggingface/', 'archives/')):
            path = ROOT / name
            if path.is_file():
                checksums[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    result.pop('descriptive_groups')
    result.update(historical_archive_files=len(archive['files']),
                  archive_manifest=str(MANIFEST.relative_to(ROOT)), retained_file_sha256=checksums)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
