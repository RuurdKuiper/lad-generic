"""Compare saved adapters' answers with matched generation and one independent scorer."""
from __future__ import annotations

import argparse
import datetime
import gc
from html import escape
import json
import os
from pathlib import Path
import time
import uuid

import torch
from huggingface_hub import HfApi
from transformers import AutoModelForCausalLM, AutoTokenizer

from compare_runs import compare_runs
from diffusion_lm.benchmarks import score_texts_with_model
from diffusion_lm.generation_prompts import DEFAULT_GENERATION_PROMPTS
from diffusion_lm.inference import load_session, release_session, select_device, llada_generate, _native_eot_token_id
from diffusion_lm.metrics import distinct_n


DEFAULT_SCORER = "Qwen/Qwen2.5-0.5B"
ROOT = Path(__file__).resolve().parent


def _synchronize(device):
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elif device.type == "mps":
        torch.mps.synchronize()


def _release_memory():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()


def _load_scorer(model_name, revision, device):
    dtype = torch.float16 if device.type in {"cuda", "mps"} else torch.float32
    kwargs = dict(revision=revision, cache_dir=str(ROOT / "base_models"), token=os.getenv("HF_TOKEN"))
    tokenizer = AutoTokenizer.from_pretrained(model_name, **kwargs)
    model = AutoModelForCausalLM.from_pretrained(model_name, dtype=dtype, **kwargs).to(device)
    model.eval()
    model.requires_grad_(False)
    return model, tokenizer


def _report_html(settings, summaries, answers):
    def number(value):
        return "n/a" if value is None else f"{value:.3f}"
    html = ["<h2>Generation comparison</h2>",
            f"<p>Checkpoint: {escape(settings['checkpoint'])}. Independent scorer: "
            f"{escape(settings['scorer_model'])}. Answer-only perplexity measures scorer likelihood, "
            "not factual correctness or instruction following. Lower perplexity can also accompany "
            "repetitive text; inspect diversity, answer length, and the answers together.</p>",
            "<table><tr><th>Run</th><th>Pooled PPL ↓</th><th>Median answer PPL ↓</th>"
            "<th>Distinct-2 ↑</th><th>Distinct-3 ↑</th><th>Mean tokens</th><th>Empty answers</th></tr>"]
    for name in ("baseline", "distilled"):
        row = summaries[name]
        html.append(f"<tr><td>{escape(name)}</td><td>{number(row['perplexity'])}</td>"
                    f"<td>{number(row['median_perplexity'])}</td><td>{number(row['mean_distinct_2'])}</td>"
                    f"<td>{number(row['mean_distinct_3'])}</td><td>{number(row['mean_tokens'])}</td>"
                    f"<td>{row['empty_answers']}</td></tr>")
    html.append("</table><p>Distinct-n is the fraction of unique overlapping token n-grams within "
                "each answer, averaged across answers. Empty/single-token texts without scoreable "
                "next-token targets have no perplexity and are counted separately in the JSON report.</p>")
    for index, prompt in enumerate(settings["prompts"]):
        html.append(f"<h3>{index + 1}. {escape(prompt)}</h3><table style='width:100%;table-layout:fixed'>"
                    "<tr><th>Denoising only</th><th>50/50 mixed</th></tr><tr>")
        for name in ("baseline", "distilled"):
            html.append("<td style='vertical-align:top;white-space:pre-wrap;overflow-wrap:anywhere'>"
                        + escape(answers[name][index]["answer"]) + "</td>")
        html.append("</tr></table>")
    return "\n".join(html)


def evaluate_generation(comparison_root, *, checkpoint="best", num_prompts=20, max_new_tokens=64,
                        num_steps=32, temperature=0.7, seed=1234, device_name="auto",
                        scorer_model=DEFAULT_SCORER, scorer_revision=None):
    """Generate with each saved adapter, free it, then score all answers once.

    No training is launched. By default both best-validation adapters answer
    the same 20 bundled prompts with identical seeds and generation budgets.
    """
    if checkpoint not in {"best", "final"}:
        raise ValueError("checkpoint must be 'best' or 'final'")
    if not 1 <= num_prompts <= len(DEFAULT_GENERATION_PROMPTS) or min(max_new_tokens, num_steps) < 1:
        raise ValueError("Use a positive generation budget and a valid number of bundled prompts")
    comparison_root = Path(comparison_root).expanduser().resolve()
    for name in ("baseline", "distilled"):
        if not (comparison_root / name / checkpoint / "adapter_config.json").is_file():
            raise FileNotFoundError(f"No saved {name}/{checkpoint} adapter under {comparison_root}")
    # Check model, data, training settings, and hardware match before comparing.
    import matplotlib.pyplot as plt
    figure = compare_runs(comparison_root / "baseline", comparison_root / "distilled")
    plt.close(figure)
    configs = {name: json.loads((comparison_root / name / "resolved_config.json").read_text())
               for name in ("baseline", "distilled")}
    if scorer_model in {config.get("model_name_or_path") for config in configs.values()}:
        raise ValueError("Use an independent scorer rather than the distillation teacher")
    # Resolve once, then pin model and tokenizer to the exact same commit.
    scorer_revision = HfApi().model_info(scorer_model, revision=scorer_revision).sha
    device = select_device(device_name)
    settings = dict(checkpoint=checkpoint, prompts=list(DEFAULT_GENERATION_PROMPTS[:num_prompts]),
                    max_new_tokens=max_new_tokens, num_steps=num_steps, temperature=temperature,
                    seed=seed, scorer_model=scorer_model, scorer_revision=scorer_revision,
                    scoring="answer-only causal next-token likelihood", device=str(device),
                    sampler="llada_official", block_length=max_new_tokens,
                    remasking="low_confidence", confidence_eos_eot_inf=True, system_prompt="")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    destination = comparison_root / "generation-evaluations" / f"{stamp}-{uuid.uuid4().hex[:6]}"
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")
    answers = {}
    for name in ("baseline", "distilled"):
        print(f"Generating {num_prompts} answers: {name}/{checkpoint}", flush=True)
        session = load_session(f"{name}/{checkpoint}", comparison_root, str(device))
        records = []
        try:
            for index, prompt in enumerate(settings["prompts"]):
                _synchronize(device)
                started = time.perf_counter()
                with torch.inference_mode():
                    text = llada_generate(session, prompt, gen_length=max_new_tokens, steps=num_steps,
                        block_length=max_new_tokens, temperature=temperature, seed=seed + index,
                        confidence_eos_eot_inf=True, eot_token_id=_native_eot_token_id(session.tokenizer),
                        system_prompt="", remasking="low_confidence")
                _synchronize(device)
                record = dict(prompt_index=index, prompt=prompt, answer=text,
                              generation_seconds=time.perf_counter() - started,
                              token_count=len(session.tokenizer.encode(text, add_special_tokens=False)),
                              **{f"distinct_{n}": distinct_n(text, session.tokenizer, n) for n in (1, 2, 3)})
                records.append(record)
                with (destination / f"{name}.jsonl").open("a") as stream:
                    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                print(f"  {name}: {index + 1}/{num_prompts}", flush=True)
        finally:
            release_session(session)
            del session
        answers[name] = records
    print(f"Scoring both groups with independent {scorer_model} @ {scorer_revision[:8]}", flush=True)
    model, tokenizer = _load_scorer(scorer_model, scorer_revision, device)
    summaries = {}
    try:
        for name, records in answers.items():
            scores = score_texts_with_model(model, tokenizer, device, [row["answer"] for row in records])
            per_text = scores.pop("per_text")
            if not scores["tokens"]:
                scores.update(perplexity=None, mean_nll=None)
            for record, score in zip(records, per_text):
                record["perplexity"] = score["perplexity"]
            summaries[name] = dict(scores, checkpoint=checkpoint, num_prompts=num_prompts,
                unscorable_answers=sum(row["perplexity"] is None for row in records),
                empty_answers=sum(not row["answer"].strip() for row in records),
                mean_tokens=sum(row["token_count"] for row in records) / num_prompts,
                mean_generation_seconds=sum(row["generation_seconds"] for row in records) / num_prompts,
                **{f"mean_distinct_{n}": sum(row[f"distinct_{n}"] for row in records) / num_prompts for n in (1, 2, 3)})
            with (destination / f"{name}.jsonl").open("w") as stream:
                for record in records:
                    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    finally:
        del model
        _release_memory()
    (destination / "summary.json").write_text(json.dumps(dict(settings=settings, models=summaries), indent=2) + "\n")
    (destination / "report.html").write_text(_report_html(settings, summaries, answers))
    print(f"Generation evaluation saved to {destination}", flush=True)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comparison_root")
    parser.add_argument("--num-prompts", type=int, default=20)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--num-steps", type=int, default=32)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    evaluate_generation(args.comparison_root, num_prompts=args.num_prompts,
                        max_new_tokens=args.max_new_tokens, num_steps=args.num_steps, device_name=args.device)
