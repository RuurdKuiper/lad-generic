import json
from types import SimpleNamespace

from diffusion_lm.benchmarks import BenchmarkExample
from diffusion_lm.judging import judge_open_ended_groups


def _groups(count=3):
    examples = [
        BenchmarkExample("open_ended", "0", "Prompt zero", "", "open_ended", {}),
        BenchmarkExample("open_ended", "1", "Prompt one", "", "open_ended", {}),
    ]
    return [
        {
            "model": f"model-{index}",
            "method": "diffusion",
            "task": "open_ended",
            "examples": examples,
            "texts": [f"answer {index}-0", f"answer {index}-1"],
        }
        for index in range(count)
    ]


class _FakeResponses:
    def __init__(self):
        self.requests = []

    def create(self, **request):
        self.requests.append(request)
        labels = request["text"]["format"]["schema"]["properties"]["ranking"]["items"]["enum"]
        return SimpleNamespace(output_text=json.dumps({"ranking": labels, "reason": "Ordered as presented."}))


def test_judge_awards_unique_n_minus_one_to_zero_scores_blindly():
    responses = _FakeResponses()
    client = SimpleNamespace(responses=responses)

    result = judge_open_ended_groups(
        _groups(3),
        {"model": "gpt-5", "methods": ["diffusion"], "seed": 7},
        client=client,
    )

    assert len(result["comparisons"]) == 2
    assert sum(row["judge_total_score"] for row in result["leaderboard"]) == 6
    for prompt_index in range(2):
        assert {
            result["per_group"][group_index][prompt_index]["judge_score"]
            for group_index in range(3)
        } == {0, 1, 2}
    assert all("model-" not in request["input"][1]["content"] for request in responses.requests)
    assert all(request["store"] is False for request in responses.requests)


def test_judge_skips_when_only_one_selected_group_exists():
    result = judge_open_ended_groups(
        _groups(1),
        {"model": "gpt-5", "methods": ["diffusion"]},
    )

    assert result["candidate_count"] == 1
    assert "skipped_reason" in result


def test_judge_method_filter_excludes_autoregressive_groups():
    groups = _groups(2)
    autoregressive = dict(groups[0], model="base", method="autoregressive")
    responses = _FakeResponses()

    result = judge_open_ended_groups(
        [*groups, autoregressive],
        {"methods": ["diffusion"]},
        client=SimpleNamespace(responses=responses),
    )

    assert result["candidate_count"] == 2
    assert set(result["per_group"]) == {0, 1}
