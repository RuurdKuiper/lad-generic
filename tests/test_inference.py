import json

import pytest

from diffusion_lm.inference import _safe_adapter_path, find_adapters


def test_adapter_discovery_only_lists_valid_saved_adapters(tmp_path):
    valid = tmp_path / "run-a" / "best"
    valid.mkdir(parents=True)
    (valid / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": "tiny"}))
    incomplete = tmp_path / "run-b" / "checkpoint-1"
    incomplete.mkdir(parents=True)
    assert find_adapters(tmp_path) == ["run-a/best"]
    assert _safe_adapter_path(tmp_path, "run-a/best") == valid.resolve()
    with pytest.raises(ValueError):
        _safe_adapter_path(tmp_path, "../outside")
