import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def cleanup(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / 'tools/prune_verified_caches.py'
    spec = importlib.util.spec_from_file_location('prune_verified_caches', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    return module


def test_cleanup_retains_unverified_sources_and_saved_mixtures(cleanup):
    records = [
        dict(path='data/huggingface/missing/default/0.0.0/abc', kind='dataset_cache', verified=False),
        dict(path='data/lad-training-1m-256-long', kind='saved_dataset', verified=True),
        dict(path='data/byod-prepared/profile', kind='prepared_dataset', verified=True),
    ]
    assert cleanup.candidates(records) == [Path('data/byod-prepared/profile')]


@pytest.mark.parametrize('path', ['/tmp/cache', '../cache', 'iclr2027_submission', 'data/../../iclr2027_submission'])
def test_cleanup_rejects_paths_outside_cache_allowlist(cleanup, path):
    with pytest.raises(ValueError):
        cleanup.candidates([dict(path=path, kind='dataset_cache', verified=True)])


def test_cleanup_keeps_model_cache_with_unverified_or_new_snapshot(cleanup):
    folder = cleanup.ROOT / 'base_models/models--owner--model/snapshots'
    (folder / 'known').mkdir(parents=True)
    (folder / 'new').mkdir()
    record = dict(path='base_models/models--owner--model/snapshots/known', kind='snapshot', verified=True)
    assert cleanup.candidates([record]) == []
    assert cleanup.candidates([record, dict(record, path=str(Path(record['path']).with_name('new')), verified=False)]) == []


def test_cleanup_rejects_tracked_files_and_symlinked_parents(cleanup, tmp_path):
    path = Path('data/byod-prepared/cache')
    with pytest.raises(ValueError, match='tracked'):
        cleanup.validate_target(path, ['data/byod-prepared/cache/result.json'])
    outside = tmp_path / 'other'
    outside.mkdir()
    (tmp_path / 'data').mkdir()
    (tmp_path / 'data/byod-prepared').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='Symlinked'):
        cleanup.validate_target(path, [])
