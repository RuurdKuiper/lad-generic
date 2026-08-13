from diffusion_lm.dataset_builder import BuildConfig, _take, _targets, format_mc, format_tulu, prompt_hash


class TinyTokenizer:
    def apply_chat_template(self, messages, tokenize, add_generation_prompt):
        size = sum(len(m["content"].split()) for m in messages)
        return list(range(size + int(add_generation_prompt)))


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


def test_take_filters_heldout_and_lengths_and_stores_clean_ids_twice():
    rows = [{"q": "held out", "a": "no"}, {"q": "one two three four", "a": "too long"}, {"q": "usable", "a": "answer"}]
    formatter = lambda x: {"instruction": "", "input": x["q"], "output": x["a"]}
    config = BuildConfig(total_examples=1, max_prompt_tokens=8, max_sequence_tokens=8)
    result = _take(rows, formatter, 1, TinyTokenizer(), config, {prompt_hash("held out")}, "general:test")
    assert len(result) == 1
    assert result[0]["input"] == "usable"
    assert result[0]["input_ids"] == result[0]["labels"]
