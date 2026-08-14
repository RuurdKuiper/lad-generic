from datasets import Dataset, concatenate_datasets

from diffusion_lm.dataset_builder import BuildConfig, _repeat_dataset, _take, _targets, choose_system_prompt, format_hellaswag, format_mc, format_tulu, prompt_hash


class TinyTokenizer:
    eos_token_id = 99
    name_or_path = "tiny"

    def apply_chat_template(self, messages, tokenize, add_generation_prompt, truncation=False, max_length=None):
        size = sum(len(m["content"].split()) for m in messages)
        ids = list(range(size + int(add_generation_prompt)))
        return ids[:max_length] if truncation else ids

    def __call__(self, text, add_special_tokens=False, truncation=False, max_length=None):
        ids = list(range(20, 20 + len(text.split())))
        return {"input_ids": ids[:max_length] if truncation else ids}


class FailingTokenizer(TinyTokenizer):
    def apply_chat_template(self, *args, **kwargs):
        raise AssertionError("extreme text should be rejected before tokenization")


def test_default_targets_are_exact_and_match_requested_mix():
    assert _targets(100, BuildConfig().weights) == {"general": 45, "reasoning": 18, "math": 18, "code": 19}


def test_formatters_reject_bad_mc_and_keep_final_tulu_exchange():
    assert format_mc("q", ["x", "y"], 1)["output"] == "B: y"
    assert format_mc("q", ["x"], 4) is None
    row = {"messages": [{"role": "user", "content": "first"}, {"role": "assistant", "content": "one"},
                        {"role": "user", "content": "second"}, {"role": "assistant", "content": "two"}]}
    result = format_tulu(row)
    assert result["output"] == "two"
    assert "first" in result["input"] and "second" in result["input"]


def test_hellaswag_asks_an_explicit_continuation_question():
    result = format_hellaswag({"ctx": "A person opens a door.", "endings": ["They enter.", "The moon explodes."], "label": "0"})
    assert "What most plausibly happens next?" in result["input"]
    assert result["output"] == "A: They enter."


def test_native_system_is_preserved_and_generated_variation_is_deterministic():
    assert choose_system_prompt({"system": "Be a pirate."}, "general:tulu-3", "0" * 64) == "Be a pirate."
    first = choose_system_prompt({}, "math:orca", "7" * 64)
    assert first == choose_system_prompt({}, "math:orca", "7" * 64)
    assert first != "You are a helpful assistant."


def test_take_filters_heldout_and_lengths_and_stores_clean_ids_twice():
    rows = [{"q": "held out", "a": "no"}, {"q": "one two three four", "a": "too long"}, {"q": "usable", "a": "answer"}]
    formatter = lambda x: {"instruction": "", "input": x["q"], "output": x["a"]}
    config = BuildConfig(total_examples=1, max_prompt_tokens=8, max_sequence_tokens=9)
    result = _take(rows, formatter, 1, TinyTokenizer(), config, {prompt_hash("held out")}, "general:test")
    assert len(result) == 1
    assert result[0]["input"] == "usable"
    assert result[0]["input_ids"] == result[0]["labels"]
    assert result[0]["labels"][-1] == TinyTokenizer.eos_token_id


def test_take_rejects_pathological_text_before_normalization_and_tokenization():
    config = BuildConfig(total_examples=1, max_prompt_tokens=2, max_sequence_tokens=4)
    rows = [{"q": "x" * 101, "a": "answer"}]
    formatter = lambda x: {"instruction": "", "input": x["q"], "output": x["a"]}
    assert _take(rows, formatter, 1, FailingTokenizer(), config, set(), "general:test") == []


def test_repeat_dataset_uses_every_unique_row_before_balanced_repeats():
    source = Dataset.from_dict({"value": [0, 1, 2]})
    repeated = _repeat_dataset(source, 8, 42, concatenate_datasets)
    values = repeated["value"]
    assert len(values) == 8
    assert values[:6] == [0, 1, 2, 0, 1, 2]
    assert max(values.count(x) for x in range(3)) - min(values.count(x) for x in range(3)) <= 1
