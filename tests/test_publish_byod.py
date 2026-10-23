import importlib.util
import json
import sys
from pathlib import Path

import pytest


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


def test_owner_spaces_bundle_their_own_tokenizer_scorer(tmp_path, monkeypatch):
    publish_byod = _load_publish_module()
    checkpoint_dir = tmp_path / 'source' / 'artifacts' / 'bigram'
    checkpoint_dir.mkdir(parents=True)
    for filename in publish_byod.BIGRAM_CHECKPOINTS.values():
        (checkpoint_dir / filename).write_bytes(filename.encode())
    source = tmp_path / 'source'
    (source / 'huggingface').mkdir()
    (source / 'huggingface' / 'byod_space').symlink_to(ROOT / 'huggingface' / 'byod_space', target_is_directory=True)
    (source / 'src').symlink_to(ROOT / 'src', target_is_directory=True)
    pins = {
        f'{owner}/{publish_byod.MODELS[index].space_name}': {
            'trigram_enabled': True,
            'ngram_scorer_repo': f'{owner}/expanded-{index}',
            'ngram_scorer_revision': 'a' * 40,
        }
        for owner in ['Ruurd', 'Dovelove'] for index in range(4)
    }
    (source / 'huggingface/byod_ngram_assets.json').write_text(json.dumps(pins))
    monkeypatch.setattr(publish_byod, 'REPO_ROOT', source)
    cases = [(namespace, i, True) for namespace in ['Ruurd','Dovelove'] for i in range(4)] + [('Example', 0, False)]
    for namespace, index, expected in cases:
        dest = tmp_path / f'{namespace}-{index}'
        dest.mkdir()
        publish_byod.make_space_bundle(publish_byod.MODELS[index], namespace, dest)
        publish_byod.make_space_bundle(publish_byod.MODELS[index], namespace, dest)
        config = json.loads((dest / 'space_model.json').read_text())
        assert config['bigram_enabled'] is expected
        for key, value in pins.get(f'{namespace}/{publish_byod.MODELS[index].space_name}', {}).items():
            assert config[key] == value
        assert (dest / 'bigram.pt').exists() is expected
        if expected:
            expected_name = publish_byod.BIGRAM_CHECKPOINTS[publish_byod.MODELS[index].space_name]
            assert (dest / 'bigram.pt').read_bytes() == expected_name.encode()
        if index == 1:
            assert 'exact `final` LoRA checkpoint' in (dest/'README.md').read_text()


def test_missing_model_specific_scorer_cannot_publish(tmp_path, monkeypatch):
    module = _load_publish_module()
    source = tmp_path/'source'
    (source/'huggingface').mkdir(parents=True)
    (source/'huggingface/byod_space').symlink_to(ROOT/'huggingface/byod_space', target_is_directory=True)
    monkeypatch.setattr(module, 'REPO_ROOT', source)
    destination=tmp_path/'bundle'; destination.mkdir()
    with pytest.raises(FileNotFoundError, match='qwen.pt'):
        module.make_space_bundle(module.MODELS[2], 'Ruurd', destination)
