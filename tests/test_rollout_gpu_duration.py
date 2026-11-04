"""Exercise rollout patches and preflight checks without contacting the Hub."""
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def rollout(monkeypatch):
    folder = Path(__file__).resolve().parents[1] / "huggingface"
    monkeypatch.syspath_prepend(str(folder))
    spec = importlib.util.spec_from_file_location("rollout_gpu_duration", folder / "rollout_gpu_duration.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("decorator", ["@spaces.GPU", "@spaces.GPU(size='large', duration=_duration)"])
def test_patch_preserves_app_and_existing_duration_helper(rollout, decorator):
    source = (
        "def _duration(*args):\n    return 300\n\n"
        f"{decorator}\ndef generate():\n    return _duration()\n"
    )
    patched = rollout.shorten_duration(source)
    assert "duration=30" in patched
    if "size=" in decorator:
        assert "size='large'" in patched
    else:
        assert "size=" not in patched
    assert "def _duration(*args):\n    return 300" in patched
    assert "return _duration()" in patched
    assert rollout.shorten_duration(patched) == patched


@pytest.mark.parametrize("source", ["x = 1\n", "@spaces.GPU\ndef a(): pass\n@spaces.GPU\ndef b(): pass\n"])
def test_patch_requires_one_gpu_entry_point(rollout, source):
    with pytest.raises(ValueError, match="Expected one GPU entry point"):
        rollout.shorten_duration(source)


@pytest.mark.parametrize("changed", ["patch", "revision"])
def test_execute_rejects_changed_patch_or_parent_before_any_commit(rollout, tmp_path, monkeypatch, changed):
    source = "@spaces.GPU\ndef generate(): pass\n"
    before = tmp_path / "before.py"
    before.write_text(source)
    staged = tmp_path / "app.py"
    staged.write_text("# modified\n" + rollout.shorten_duration(source) if changed == "patch"
                      else rollout.shorten_duration(source))
    manifest = [{"owner": "Example", "space": "Example/demo", "parent": "reviewed", "path": str(staged)}]
    (tmp_path / "prepared.json").write_text(json.dumps(manifest))
    commits = []
    api = SimpleNamespace(
        repo_info=lambda *args, **kwargs: SimpleNamespace(sha="changed"),
        create_commit=lambda **kwargs: commits.append(kwargs),
    )
    monkeypatch.setattr(rollout, "accounts", lambda: {"Example": api})
    monkeypatch.setattr(sys, "argv", ["rollout_gpu_duration.py", "--execute", "--output", str(tmp_path)])
    with pytest.raises(ValueError, match="Staged patch changed|Remote revision changed"):
        rollout.main()
    assert not commits
