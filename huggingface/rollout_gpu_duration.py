#!/usr/bin/env python3
"""Patch only GPU reservations in the existing demos; preserve deployed code."""
import argparse
import ast
import json
from pathlib import Path

from hub_accounts import accounts, NAMES


def shorten_duration(source):
    tree = ast.parse(source)
    edits = []
    found = 0
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            call = decorator.func if isinstance(decorator, ast.Call) else decorator
            if ast.unparse(call) != 'spaces.GPU':
                continue
            found += 1
            start, end = decorator.lineno - 1, decorator.end_lineno
            if isinstance(decorator, ast.Call):
                decorator.keywords = [k for k in decorator.keywords if k.arg != 'duration']
                decorator.keywords.append(ast.keyword(arg='duration', value=ast.Constant(30)))
            else:
                decorator = ast.Call(func=call, args=[], keywords=[ast.keyword(arg='duration', value=ast.Constant(30))])
            edits.append((start, end, ['@' + ast.unparse(decorator) + '\n']))
    if found != 1:
        raise ValueError(f'Expected one GPU entry point, found {found}')
    lines = source.splitlines(keepends=True)
    for start, end, replacement in sorted(edits, reverse=True):
        lines[start:end] = replacement
    result = ''.join(lines)
    compile(result, 'app.py', 'exec')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('/tmp/lad-zerogpu-30s'))
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    from huggingface_hub import CommitOperationAdd, hf_hub_download
    apis = accounts()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = args.output / 'prepared.json'
    if not args.execute:
        records = []
        targets = [(owner, f'{owner}/{name}') for owner in apis for name in NAMES]
        targets += [('Ruurd', f'Ruurd/{name}') for name in ('lad', 'llada-8b-instruct', 'llada2.2-mini')]
        for owner, repo in targets:
            api = apis[owner]
            info = api.repo_info(repo, repo_type='space')
            source = Path(hf_hub_download(repo, 'app.py', repo_type='space', revision=info.sha,
                                         token=api.token, cache_dir=args.output / 'cache')).read_text()
            folder = args.output / repo
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'before.py').write_text(source)
            (folder / 'app.py').write_text(shorten_duration(source))
            records.append(dict(owner=owner, space=repo, parent=info.sha, path=str(folder / 'app.py')))
            print(f'Prepared {repo}: 30s', flush=True)
        manifest.write_text(json.dumps(records, indent=2) + '\n')
    else:
        records = json.loads(manifest.read_text())
        # Check every parent and staged patch before making any remote changes.
        for record in records:
            path = Path(record['path'])
            if path.read_text() != shorten_duration(path.with_name('before.py').read_text()):
                raise ValueError(f'Staged patch changed: {path}; prepare the rollout again.')
            current = apis[record['owner']].repo_info(record['space'], repo_type='space').sha
            if current != record['parent']:
                raise ValueError(f'Remote revision changed: {record["space"]}; prepare the rollout again.')
        deployed = []
        for record in records:
            commit = apis[record['owner']].create_commit(
                repo_id=record['space'], repo_type='space', parent_commit=record['parent'],
                operations=[CommitOperationAdd(path_in_repo='app.py', path_or_fileobj=record['path'])],
                commit_message='Use a 30-second ZeroGPU reservation for interactive generation')
            deployed.append(dict(space=record['space'], revision=commit.oid, duration=30))
            (args.output / 'deployment.json').write_text(json.dumps(deployed, indent=2) + '\n')
            print(f'Updated {record["space"]}: {commit.oid}', flush=True)


if __name__ == '__main__':
    main()
