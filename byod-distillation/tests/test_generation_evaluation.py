"""Exercise saved-run evaluation without downloads or GPU allocation."""
import json
from pathlib import Path
from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest
import torch
from transformers import LlamaConfig, LlamaForCausalLM

import evaluate_generation as evaluation
from diffusion_lm.benchmarks import score_texts_with_model


def saved_pair(root):
    for name, weight in (("baseline", 0.0), ("distilled", 0.5)):
        run = root / name
        (run / "best").mkdir(parents=True)
        (run / "best/adapter_config.json").write_text("{}")
        (run / "resolved_config.json").write_text(json.dumps(dict(
            model_name_or_path="teacher", seed=42, output_dir=str(run),
            distillation={"enabled": weight > 0, "weight": weight},
        )))
        (run / "metrics.jsonl").write_text(json.dumps(dict(
            split="validation", step=1000, weighted_loss=3., elapsed_seconds=12.,
        )) + "\n")


class Tokenizer:
    all_special_ids = []
    def encode(self, text, add_special_tokens=False):
        return [3 + (ord(character) % 12) for character in text]
    def __call__(self, text, **kwargs):
        return {"input_ids": torch.tensor([self.encode(text)], dtype=torch.long)}


def install_fakes(monkeypatch):
    calls, releases, scorer_calls = [], [], []
    monkeypatch.setattr(evaluation, "select_device", lambda requested: torch.device("cpu"))
    monkeypatch.setattr(evaluation, "HfApi", lambda: SimpleNamespace(
        model_info=lambda model, revision=None: SimpleNamespace(sha="a" * 40),
    ))
    monkeypatch.setattr(evaluation, "_native_eot_token_id", lambda tokenizer: None)
    monkeypatch.setattr(evaluation, "load_session", lambda adapter, root, device: SimpleNamespace(
        adapter=adapter, tokenizer=Tokenizer(),
    ))
    monkeypatch.setattr(evaluation, "release_session", lambda session: releases.append(session.adapter))
    def generate(session, prompt, **kwargs):
        assert not torch.is_grad_enabled()
        calls.append((session.adapter, prompt, kwargs))
        return "hello world" if session.adapter.startswith("baseline") else "hello hello"
    monkeypatch.setattr(evaluation, "llada_generate", generate)
    model = LlamaForCausalLM(LlamaConfig(vocab_size=32, hidden_size=16, intermediate_size=32,
        num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2))
    def load_scorer(name, revision, device):
        scorer_calls.append((name, revision, device))
        # Generation models have already been released before the scorer loads.
        assert releases == ["baseline/best", "distilled/best"]
        return model, Tokenizer()
    monkeypatch.setattr(evaluation, "_load_scorer", load_scorer)
    return calls, releases, scorer_calls


def test_saved_adapters_share_prompts_seeds_scorer_and_scoring_protocol(tmp_path, monkeypatch):
    saved_pair(tmp_path)
    calls, releases, scorer_calls = install_fakes(monkeypatch)
    destination = evaluation.evaluate_generation(tmp_path, num_prompts=2, max_new_tokens=8, num_steps=4)
    assert len(calls) == 4 and len(scorer_calls) == 1
    assert scorer_calls[0][0] == evaluation.DEFAULT_SCORER
    assert scorer_calls[0][1] == "a" * 40
    assert calls[0][1:] == calls[2][1:] and calls[1][1:] == calls[3][1:]
    assert calls[0][2]["seed"] == 1234 and calls[1][2]["seed"] == 1235
    summary = json.loads((destination / "summary.json").read_text())
    assert summary["settings"]["checkpoint"] == "best"
    for name in ("baseline", "distilled"):
        assert summary["models"][name]["perplexity"] > 0
        assert summary["models"][name]["mean_tokens"] == 11
        assert summary["models"][name]["empty_answers"] == 0
        records = [json.loads(line) for line in (destination / f"{name}.jsonl").read_text().splitlines()]
        assert len(records) == 2 and all(record["perplexity"] > 0 for record in records)
    html = (destination / "report.html").read_text()
    assert "Denoising only" in html and "50/50 mixed" in html
    assert "hello world" in html and "hello hello" in html
    # Re-evaluation preserves the previous report rather than overwriting it.
    previous = (destination / "summary.json").read_bytes()
    calls.clear()
    releases.clear()
    second = evaluation.evaluate_generation(tmp_path, num_prompts=2, max_new_tokens=8, num_steps=4)
    assert second != destination and (destination / "summary.json").read_bytes() == previous


def test_empty_answers_are_unscorable_and_do_not_get_perplexity_one(tmp_path, monkeypatch):
    saved_pair(tmp_path)
    install_fakes(monkeypatch)
    monkeypatch.setattr(evaluation, "llada_generate", lambda *args, **kwargs: "")
    destination = evaluation.evaluate_generation(tmp_path, num_prompts=1)
    summary = json.loads((destination / "summary.json").read_text())
    for row in summary["models"].values():
        assert row["perplexity"] is None and row["mean_nll"] is None
        assert row["empty_answers"] == row["unscorable_answers"] == 1
    assert "n/a" in (destination / "report.html").read_text()


def test_generation_failure_releases_adapter_and_does_not_start_second(tmp_path, monkeypatch):
    saved_pair(tmp_path)
    calls, releases, _ = install_fakes(monkeypatch)
    def fail(*args, **kwargs):
        raise RuntimeError("generation failed")
    monkeypatch.setattr(evaluation, "llada_generate", fail)
    with pytest.raises(RuntimeError, match="generation failed"):
        evaluation.evaluate_generation(tmp_path, num_prompts=1)
    assert releases == ["baseline/best"]


def test_missing_checkpoint_fails_before_any_model_download(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, "HfApi", lambda: pytest.fail("Should not access model metadata"))
    with pytest.raises(FileNotFoundError, match="baseline/best"):
        evaluation.evaluate_generation(tmp_path)


def test_teacher_cannot_be_used_as_independent_scorer(tmp_path):
    saved_pair(tmp_path)
    with pytest.raises(ValueError, match="independent scorer"):
        evaluation.evaluate_generation(tmp_path, scorer_model="teacher")


def test_generated_html_escapes_model_text_and_prompts():
    settings = dict(checkpoint="best", scorer_model="reference", prompts=["<question>"])
    row = dict(perplexity=None, median_perplexity=None, mean_distinct_2=0, mean_distinct_3=0,
               mean_tokens=0, empty_answers=1)
    report = evaluation._report_html(settings, {"baseline": row, "distilled": row}, {
        "baseline": [{"answer": "<script>alert('x')</script>"}], "distilled": [{"answer": "<b>answer</b>"}],
    })
    assert "<script>" not in report and "<b>answer</b>" not in report
    assert "&lt;question&gt;" in report and "&lt;script&gt;" in report


def test_scorer_perplexity_is_shifted_token_weighted_causal_likelihood():
    model = LlamaForCausalLM(LlamaConfig(vocab_size=32, hidden_size=16, intermediate_size=32,
        num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2))
    model.eval()
    tokenizer = Tokenizer()
    texts = ["abc", "a longer text"]
    scores = score_texts_with_model(model, tokenizer, torch.device("cpu"), texts)
    total, count = 0., 0
    with torch.no_grad():
        for text in texts:
            ids = tokenizer(text)["input_ids"]
            logits = model(ids).logits[:, :-1]
            total += torch.nn.functional.cross_entropy(logits.flatten(0, 1), ids[:, 1:].flatten(), reduction="sum").item()
            count += ids.shape[1] - 1
    assert scores["tokens"] == count
    assert scores["perplexity"] == pytest.approx(torch.exp(torch.tensor(total / count)).item())


def test_final_notebook_cell_evaluates_existing_runs_without_training(tmp_path, monkeypatch):
    import subprocess
    import IPython.display
    root = Path(__file__).resolve().parents[1]
    notebook = json.loads((root / "notebooks/compare_distillation.ipynb").read_text())
    source = "".join(notebook["cells"][-1]["source"]).replace(
        'SAVED_COMPARISON_DIR = ""', f"SAVED_COMPARISON_DIR = {str(tmp_path)!r}",
    )
    calls, displays = [], []
    def run(command, **kwargs):
        calls.append(command)
        destination = tmp_path / "generation-evaluations/example"
        destination.mkdir(parents=True)
        (destination / "report.html").write_text("<p>comparison</p>")
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(IPython.display, "display", displays.append)
    namespace = {"PROJECT_DIR": root}
    exec(compile(source, "generation-evaluation-cell", "exec"), namespace)
    assert len(calls) == 1
    assert str(root / "evaluate_generation.py") in calls[0]
    assert str(tmp_path) in calls[0]
    assert calls[0][calls[0].index("--num-prompts") + 1] == "20"
    assert not any(argument.endswith("train.py") for argument in calls[0])
    assert displays[0].data == "<p>comparison</p>"
