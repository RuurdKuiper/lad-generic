#!/usr/bin/env python
"""Grid-search denoising parameters using autoregressive perplexity and repetition."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import torch
import yaml

from diffusion_lm.inference import denoise_stream, load_session


DEFAULT_PROMPTS = [
    "What do you know about Amsterdam?", "Tell me a story about a little dwarf.",
    "Explain why the seasons change.", "How does a bicycle work?",
    "Describe a memorable meal in vivid detail.", "What makes a good leader?",
    "Write a short mystery set in a library.", "How would you teach patience to a child?",
    "Explain the benefits and risks of renewable energy.", "Describe an imaginary planet and its inhabitants.",
]


def _repetition(text: str, n: int = 3) -> float:
    """Calculate repeated n-gram fraction while ignoring special tokens."""
    words = text.split()
    grams = [tuple(words[i:i + n]) for i in range(max(0, len(words) - n + 1))]
    return 0.0 if not grams else 1.0 - len(set(grams)) / len(grams)


@torch.no_grad()
def _perplexity(session, texts: list[str]) -> float:
    """Score generated text with the loaded model's autoregressive objective."""
    total_nll = 0.0; total_tokens = 0
    for text in texts:
        ids = session.tokenizer(text, return_tensors="pt").input_ids.to(session.device)
        if ids.shape[1] < 2: continue
        context = session.model.disable_adapter() if hasattr(session.model, "disable_adapter") else None
        with (context if context is not None else _NullContext()):
            logits = session.model(input_ids=ids, use_cache=False).logits[:, :-1].float()
        total_nll += float(torch.nn.functional.cross_entropy(logits.transpose(1, 2), ids[:, 1:], reduction="sum"))
        total_tokens += ids.shape[1] - 1
    return float(torch.exp(torch.tensor(total_nll / max(total_tokens, 1))))


class _NullContext:
    """No-op context manager."""
    def __enter__(self): return self
    def __exit__(self, *args): return False


def main() -> None:
    """Evaluate a configurable parameter grid and save the best candidate."""
    parser = argparse.ArgumentParser(); parser.add_argument("--config", required=True)
    args = parser.parse_args(); config = yaml.safe_load(Path(args.config).read_text())
    model_selection = config["model"]
    outputs_dir = Path(config.get("outputs_dir", "outputs"))
    try:
        session = load_session(model_selection, outputs_dir, config.get("device", "auto"))
    except ValueError as exc:
        available = sorted(str(path.parent.relative_to(outputs_dir)) for path in outputs_dir.glob("*/best/adapter_config.json"))
        raise ValueError(f"Invalid model selection {model_selection!r}. Set 'model' to a run name containing best/adapter_config.json. Available: {available or 'none'}") from exc
    settings = config.get("generation", {}); grid = config.get("search", {})
    prompts = config.get("prompts", DEFAULT_PROMPTS)[: int(config.get("num_prompts", 10))]
    keys = list(grid); values = [v if isinstance(v, list) else [v] for v in grid.values()]
    results = []
    combinations = list(itertools.product(*values))
    for candidate_index, combination in enumerate(combinations, start=1):
        candidate = dict(settings); candidate.update(dict(zip(keys, combination)))
        print(f"\nCandidate {candidate_index}/{len(combinations)}: {candidate}", flush=True)
        texts = []
        for repeat in range(int(config.get("repetitions", 5))):
            for index, prompt in enumerate(prompts):
                final = ""
                for final, _status, _html in denoise_stream(session, prompt, candidate.get("system_prompt", "You are a helpful assistant."), int(candidate.get("max_new_tokens", 256)), int(candidate.get("num_steps", 32)), float(candidate.get("noise_level", 1.0)), float(candidate.get("temperature", .7)), int(candidate.get("top_k", 20)), int(candidate.get("seed", 1234)) + repeat * 10000 + index, bool(candidate.get("permanent_unmask", False)), bool(candidate.get("confidence_guided", False)), bool(candidate.get("proportional_unmask", True))): pass
                texts.append(final)
                print(f"  sample {len(texts)}/{len(prompts) * int(config.get('repetitions', 5))} | prompt={prompt}\n  output={final}\n", flush=True)
        ppl = _perplexity(session, texts); repetition = sum(_repetition(t) for t in texts) / max(len(texts), 1)
        score = ppl + float(config.get("repetition_weight", 10.0)) * repetition
        results.append({"parameters": candidate, "perplexity": ppl, "ngram_repetition": repetition, "score": score})
        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
    results.sort(key=lambda x: x["score"]); output = Path(config.get("output", "outputs/generation_search.json")); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps({"best": results[0], "results": results}, indent=2, ensure_ascii=False))


if __name__ == "__main__": main()
