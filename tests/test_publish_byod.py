import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]


def _load_publish_module():
    path = ROOT / "huggingface" / "publish_byod.py"
    spec = importlib.util.spec_from_file_location("publish_byod", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_space_bundles_get_distinct_persistent_visitor_counters(tmp_path):
    publish_byod = _load_publish_module()
    counter_ids = set()

    for model in publish_byod.MODELS:
        destination = tmp_path / model.space_name
        destination.mkdir()
        publish_byod.make_space_bundle(model, "Example", destination)
        config = json.loads((destination / "space_model.json").read_text())
        counter_ids.add(config["visitor_counter_id"])

    assert counter_ids == {
        f"Example.{model.space_name}" for model in publish_byod.MODELS
    }


def test_space_template_renders_the_configured_visitor_badge():
    source = (ROOT / "huggingface" / "byod_space" / "app.py").read_text()

    assert 'SPACE.get("visitor_counter_id")' in source
    assert "https://visitor-badge.laobi.icu/badge?" in source
