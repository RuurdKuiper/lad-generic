import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

from diffusion_lm.inference import load_llada_session


@pytest.mark.parametrize('preflight', [False, True])
def test_llada_loader_pins_model_and_tokenizer_and_defers_gpu_forward(monkeypatch, preflight):
    import diffusion_lm.inference as inference
    calls = []
    tokenizer = SimpleNamespace(pad_token_id=126081)
    class Model:
        def to(self, device):
            calls.append(('device', str(device)))
            return self
        def eval(self):
            return self
    def load_tokenizer(repo, **kwargs):
        calls.append(('tokenizer', repo, kwargs))
        return tokenizer
    def load_model(repo, **kwargs):
        calls.append(('model', repo, kwargs))
        return Model()
    monkeypatch.setattr(inference, 'select_device', lambda device: torch.device('cuda'))
    monkeypatch.setattr(inference, '_precision_dtype', lambda *args: torch.bfloat16)
    monkeypatch.setattr(inference.AutoTokenizer, 'from_pretrained', load_tokenizer)
    monkeypatch.setattr(inference.AutoModel, 'from_pretrained', load_model)
    monkeypatch.setattr(inference, 'preflight_session', lambda session: calls.append(('forward',)))
    session = load_llada_session('official/model', 'cuda', revision='pinned-revision', preflight=preflight)
    assert [c[0] for c in calls].count('forward') == int(preflight)
    assert session.llada and session.prompt_format == 'llada' and session.mask_token_id == 126336
    assert session.config['revision'] == 'pinned-revision'
    assert tokenizer.padding_side == 'left'
    for kind in ['tokenizer', 'model']:
        request = next(c for c in calls if c[0] == kind)
        assert request[2]['revision'] == 'pinned-revision' and request[2]['trust_remote_code']


def test_llada_space_bundle_uses_native_model_and_separate_scorer(tmp_path):
    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location('publish_llada', root/'huggingface/publish_llada.py')
    publish = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(publish)
    checkpoint = tmp_path/'llada.pt';checkpoint.write_bytes(b'llada-tokenized-scorer')
    destination = tmp_path/'bundle'
    publish.make_space_bundle(destination, checkpoint)
    cfg = json.loads((destination/'space_model.json').read_text())
    assert cfg['model_backend'] == 'llada' and cfg['model_repo_id'] == 'GSAI-ML/LLaDA-8B-Instruct'
    assert cfg['model_revision'] == publish.MODEL_REVISION and cfg['bigram_enabled']
    assert (destination/'bigram.pt').read_bytes() == b'llada-tokenized-scorer'
    assert 'transformers==4.57.6' in (destination/'requirements.txt').read_text()
    assert not (destination/'adapter_model.safetensors').exists()
    assert 'load_llada_session' in (destination/'app.py').read_text()


@pytest.mark.parametrize('account', ['Ruurd', 'different-account'])
def test_publisher_creates_only_new_private_space_and_checks_account(tmp_path, monkeypatch, account):
    import sys
    import dotenv
    import huggingface_hub
    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location('publish_llada_guarded', root/'huggingface/publish_llada.py')
    publish = importlib.util.module_from_spec(spec);spec.loader.exec_module(publish)
    writes = []
    class Api:
        def whoami(self): return {'name': account}
        def create_repo(self, repo, **kwargs): writes.append(('create', repo, kwargs))
        def upload_folder(self, **kwargs):
            writes.append(('upload', kwargs['repo_id'], kwargs))
            return SimpleNamespace(oid='new-commit')
        def request_space_hardware(self, repo, **kwargs):
            writes.append(('hardware', repo, kwargs))
            return SimpleNamespace(stage='BUILDING')
    destination = tmp_path/'bundle'
    monkeypatch.setattr(sys, 'argv', ['publish_llada', '--output', str(destination), '--execute'])
    monkeypatch.setattr(dotenv, 'load_dotenv', lambda *args, **kwargs: None)
    monkeypatch.setattr(huggingface_hub, 'HfApi', Api)
    monkeypatch.setattr(publish, 'make_space_bundle', lambda path: path.mkdir())
    if account != 'Ruurd':
        with pytest.raises(RuntimeError, match='Ruurd account'): publish.main()
        assert not writes
        return
    publish.main()
    assert all(call[1]=='Ruurd/llada-8b-instruct' for call in writes)
    assert writes[0][2]['private'] is True and writes[0][2]['exist_ok'] is False
    assert writes[-1][2]['hardware']=='zero-a10g'
    record=json.loads((tmp_path/'deployment.json').read_text())
    assert record['visibility']=='private' and record['commit']=='new-commit'
