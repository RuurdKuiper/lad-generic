from diffusion_lm.benchmarks import load_benchmark


def test_open_ended_benchmark_has_reproducible_thirty_prompt_suite():
    examples = load_benchmark("open_ended", "test", None, "unused", None)

    assert len(examples) == 30
    assert examples[0].example_id == "0"
    assert examples[0].kind == "open_ended"
    assert examples[0].prompt == "What do you know about Amsterdam?"


def test_open_ended_benchmark_respects_limit():
    examples = load_benchmark("open_ended", "test", 3, "unused", None)

    assert len(examples) == 3
