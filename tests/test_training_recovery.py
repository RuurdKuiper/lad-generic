"""Recovery must retain logs and a usable checkpoint when a run is interrupted."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from diffusion_lm.training import _checkpoint_limit, _prune_checkpoints, _resume_metrics


def test_retention_preserves_metrics_models_and_incomplete_checkpoints(tmp_path):
    metrics = tmp_path / "metrics.jsonl"
    metrics.write_text('{"step": 1}\n')
    for step in (1000, 2000, 3000, 4000):
        path = tmp_path / f"checkpoint-{step}"
        path.mkdir()
        (path / "state.json").write_text(json.dumps({"step": step}))
    (tmp_path / "checkpoint-5000").mkdir()  # Interrupted save.
    (tmp_path / "final").mkdir()
    _prune_checkpoints(tmp_path, 2, 4000)
    assert sorted(path.name for path in tmp_path.glob("checkpoint-*")) == [
        "checkpoint-3000", "checkpoint-4000", "checkpoint-5000",
    ]
    assert metrics.read_text() == '{"step": 1}\n'
    assert (tmp_path / "final").is_dir()


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "2"])
def test_invalid_checkpoint_retention_is_rejected(limit):
    with pytest.raises(ValueError, match="positive integer"):
        _checkpoint_limit({"checkpoint_total_limit": limit})


def test_resume_keeps_original_history_and_repairs_interrupted_tail(tmp_path):
    path = tmp_path / "metrics.jsonl"
    original = '\n'.join([
        json.dumps({"split": "validation", "step": 250, "weighted_loss": 3.}),
        json.dumps({"split": "validation", "step": 500, "weighted_loss": 2.}),
        json.dumps({"split": "validation", "step": 750, "weighted_loss": 1.}),
        '{"split": "valida',
    ])
    path.write_text(original)
    _resume_metrics(path, 500)
    assert [json.loads(line)["step"] for line in path.read_text().splitlines()] == [250, 500]
    assert (tmp_path / "metrics.before-resume-500.jsonl").read_text() == original
    _resume_metrics(path, 500)  # A second restart doesn't damage the backup.
    assert (tmp_path / "metrics.before-resume-500.jsonl").read_text() == original


def test_malformed_interior_metrics_are_not_silently_discarded(tmp_path):
    path = tmp_path / "metrics.jsonl"
    path.write_text('broken\n{"step": 250, "weighted_loss": 2}\n')
    with pytest.raises(ValueError, match="Malformed metrics"):
        _resume_metrics(path, 500)


def test_resume_handles_training_microsteps_with_accumulation(tmp_path):
    path = tmp_path / "metrics.jsonl"
    rows = [{"split": split, "step": step, "weighted_loss": 2.} for split, step in (
        ("train", 500), ("validation", 250), ("train", 502), ("validation", 251),
    )]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    _resume_metrics(path, 250, gradient_accumulation_steps=2)
    assert [json.loads(line) for line in path.read_text().splitlines()] == rows[:2]


def test_tiny_training_recovers_optimizer_logs_and_best_loss(tmp_path, monkeypatch):
    import torch
    from datasets import Dataset, DatasetDict
    from transformers import LlamaConfig, LlamaForCausalLM
    from peft import LoraConfig, get_peft_model
    from test_data_corruption_loss import ToyTokenizer
    from diffusion_lm import training

    for name in ("LAD_STORAGE", "LAD_OUTPUT_ROOT"):
        monkeypatch.delenv(name, raising=False)
    tokenizer = ToyTokenizer()
    tokenizer.pad_token_id = tokenizer.eos_token_id
    dataset = Dataset.from_list([{"instruction": "Answer", "input": "", "output": "abcd"} for _ in range(8)])
    monkeypatch.setattr("datasets.load_dataset", lambda *args, **kwargs: DatasetDict(
        train=dataset, validation=dataset.select(range(2)), test=dataset.select(range(2)),
    ))
    monkeypatch.setattr(training.AutoTokenizer, "from_pretrained", lambda *args, **kwargs: tokenizer)

    def load_model(config):
        torch.manual_seed(42)
        model = get_peft_model(LlamaForCausalLM(LlamaConfig(
            vocab_size=16, hidden_size=16, intermediate_size=32, num_hidden_layers=1,
            num_attention_heads=2, num_key_value_heads=2,
        )), LoraConfig(r=2, target_modules=["q_proj", "v_proj"], bias="none"))
        return model, {}

    monkeypatch.setattr(training, "load_denoising_model", load_model)
    saved = []
    monkeypatch.setattr(training, "_save_adapter", lambda model, tokenizer, path, norms: saved.append(path.name))
    evaluations = iter([3., 2., 9.])
    monkeypatch.setattr(training, "evaluate", lambda *args: {"weighted_loss": next(evaluations)})
    config = dict(
        corruption_mode="mask_only", structured_loss_behavior="corrupted_answer_tokens",
        dataset_name="tiny-local", model_name_or_path="tiny-local",
        output_dir=str(tmp_path / "output"), cache_dir=str(tmp_path / "cache"),
        base_model_cache_dir=str(tmp_path / "models"), prepared_data_cache_dir=str(tmp_path / "prepared"),
        precision="fp32", batch_size=2, max_updates=4, max_sequence_length=32,
        learning_rate=.01, scheduler="constant", logging_steps=1, validation_steps=1,
        checkpoint_mode="every_checkpoint", checkpoint_steps=1, checkpoint_total_limit=2,
        save_best_model=False, num_workers=0, preprocessing_num_workers=1,
    )

    def interrupt(event, output, artifact):
        if event == "metrics" and len([line for line in (output / "metrics.jsonl").read_text().splitlines()
                                       if json.loads(line)["split"] == "validation"]) == 3:
            raise RuntimeError("simulated interruption after validation")

    with pytest.raises(RuntimeError, match="simulated interruption"):
        training.run_training(dict(config), artifact_callback=interrupt)
    output = tmp_path / "output"
    checkpoint = output / "checkpoint-2"
    assert json.loads((checkpoint / "state.json").read_text())["best_validation_loss"] == 2.
    assert (checkpoint / "optimizer.bin").exists()
    # Resume with worse validation scores. The historical best must survive.
    evaluations = iter([8., 7.])
    result = training.run_training({**config, "resume_from_checkpoint": str(checkpoint), "run_final_test": False})
    assert result == {}
    assert not (output / "test_metrics.json").exists()
    assert saved == ["final"]
    assert sorted(path.name for path in output.glob("checkpoint-*")) == ["checkpoint-3", "checkpoint-4"]
    assert json.loads((output / "checkpoint-4/state.json").read_text())["best_validation_loss"] == 2.
    optimizer = torch.load(output / "checkpoint-4/optimizer.bin", map_location="cpu", weights_only=True)
    assert optimizer["state"]
    assert all(int(state["step"]) == 4 for state in optimizer["state"].values())
    validation = [json.loads(line) for line in (output / "metrics.jsonl").read_text().splitlines()
                  if json.loads(line)["split"] == "validation"]
    assert [(row["step"], row["weighted_loss"]) for row in validation] == [(1, 3.), (2, 2.), (3, 8.), (4, 7.)]
    assert (output / "metrics.before-resume-2.jsonl").exists()


def test_hub_retention_waits_for_new_upload_and_preserves_other_ranks(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "rank_worker", Path(__file__).parents[1] / "iclr2027_rebuttal/rank_ablation/run_training.py",
    )
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)

    class API:
        fail = True
        deleted = []

        def repo_info(self, **kwargs):
            return SimpleNamespace(private=True)

        def upload_folder(self, **kwargs):
            if Path(kwargs["folder_path"]).name == "checkpoint-3000" and self.fail:
                raise RuntimeError("upload interrupted")

        def list_repo_files(self, **kwargs):
            return [f"{rank}/checkpoint-{step}/{name}" for rank in ("rank-128", "rank-512")
                    for step in (1000, 2000, 3000) for name in ("state.json", "optimizer.bin")]

        def create_commit(self, **kwargs):
            self.deleted.extend(op.path_in_repo for op in kwargs["operations"])

        def upload_file(self, **kwargs):
            pass

    api = API()
    store = worker.HubArtifacts(api, "test/private", "rank-128", keep=2)
    checkpoint = tmp_path / "checkpoint-3000"
    checkpoint.mkdir()
    (checkpoint / "state.json").write_text(json.dumps({"step": 3000, "save_seconds": 1.}))
    with pytest.raises(RuntimeError, match="upload interrupted"):
        store("checkpoint", tmp_path, checkpoint)
    assert api.deleted == []
    api.fail = False
    store("checkpoint", tmp_path, checkpoint)
    assert sorted(api.deleted) == ["rank-128/checkpoint-1000/optimizer.bin", "rank-128/checkpoint-1000/state.json"]


def test_fp8_recovery_save_keeps_extra_state_and_validation_calibration(tmp_path):
    import torch
    from accelerate import Accelerator
    from diffusion_lm.training import _save_recovery_state

    class CalibratedLinear(torch.nn.Linear):
        # TE returns empty extra state after BF16 validation unless its
        # fp8_checkpoint flag explicitly requests retaining calibration.
        def __init__(self, value):
            super().__init__(2, 2)
            self.fp8_meta = {"scaling_fwd": True, "fp8_checkpoint": False}
            self.calibration = torch.tensor([value], dtype=torch.uint8)

        def get_extra_state(self):
            return self.calibration if self.fp8_meta["fp8_checkpoint"] else torch.empty(0, dtype=torch.uint8)

        def set_extra_state(self, state):
            self.calibration = state.clone()

    model = torch.nn.Sequential(CalibratedLinear(17), CalibratedLinear(23))
    accelerator = Accelerator()
    model = accelerator.prepare(model)
    _save_recovery_state(accelerator, model, tmp_path, fp8_active=True)
    assert (tmp_path / "pytorch_model.bin").is_file()
    assert not (tmp_path / "model.safetensors").exists()
    for layer in model:
        assert layer.fp8_meta["fp8_checkpoint"] is False
        layer.calibration.zero_()
    accelerator.load_state(tmp_path)
    assert [layer.calibration.item() for layer in model] == [17, 23]
