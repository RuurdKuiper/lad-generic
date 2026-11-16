"""Budget forecasts must include validation, recovery transfers and headroom."""
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("rank_batch_budget", ROOT / "iclr2027_rebuttal/rank_ablation/batch_worker.py")
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


def test_slow_measurements_fail_the_full_study_time_allowance():
    slow = {str(rank): {"step": 250, "seconds_per_update": 1., "validation_seconds": 10., "checkpoint_seconds": 60.}
            for rank in (128, 512, 2048)}
    assert batch.forecast(slow) > 14 * 3600


def test_fast_measurements_leave_time_for_overhead_and_margin():
    fast = {str(rank): {"step": 250, "seconds_per_update": .3, "validation_seconds": 5., "checkpoint_seconds": 20.}
            for rank in (128, 512, 2048)}
    raw_training = sum((25000 - row["step"]) * row["seconds_per_update"] for row in fast.values())
    assert raw_training * 1.2 < batch.forecast(fast) < 14 * 3600


def test_timing_uses_points_from_the_current_resumed_process(tmp_path):
    points = [
        {"split": "train", "step": 100, "elapsed_seconds": 70.},
        {"split": "train", "step": 200, "elapsed_seconds": 120.},
        {"split": "train", "step": 300, "elapsed_seconds": 35.},
        {"split": "train", "step": 400, "elapsed_seconds": 85.},
        {"split": "train", "step": 500, "elapsed_seconds": 135.},
        {"split": "validation", "step": 500, "validation_seconds": 5.},
    ]
    (tmp_path / "metrics.jsonl").write_text("".join(json.dumps(row) + "\n" for row in points))
    (tmp_path / "runtime_metrics.jsonl").write_text(json.dumps({"step": 500, "save_seconds": 10., "upload_seconds": 20.}) + "\n")
    measured = batch.measurements(tmp_path)
    assert measured["step"] == 500
    assert measured["seconds_per_update"] == .5
    assert measured["checkpoint_seconds"] == 30.


def test_timeout_reservations_and_startup_buffer_fit_author_cap():
    gpu = (14 * 60 + 1) * .045833
    maximum_cpu_builds = 3 * (60 + 1) * .0005
    assert gpu + maximum_cpu_builds + 3.0 < 42.


def _launcher():
    spec = importlib.util.spec_from_file_location("rank_launch_budget", ROOT / "iclr2027_rebuttal/rank_ablation/hf_jobs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fresh_1024_reservation_fits_both_author_limits():
    launcher = _launcher()
    state = {"jobs": [{"role": "training", "reserved_usd": 38.27, "cost_upper_usd": 25.67048}]}
    seconds = launcher.rank1024_timeout(state)
    assert seconds == 5 * 3600
    reservation = (seconds / 60 + 1) * launcher.RATES["rtx-pro-6000"] + 2
    assert reservation < 17
    assert 25.67048 + reservation < 42


def test_1024_does_not_start_if_overall_remaining_funds_are_insufficient():
    import pytest

    with pytest.raises(RuntimeError, match="does not safely fit"):
        _launcher().rank1024_timeout({"jobs": [{"role": "training", "reserved_usd": 35.0, "cost_upper_usd": 35.0}]})


def test_1024_prior_attempts_count_toward_its_17_dollar_allowance():
    import pytest

    with pytest.raises(RuntimeError, match="does not safely fit"):
        _launcher().rank1024_timeout({"jobs": [{"role": "training-1024", "reserved_usd": 5., "cost_upper_usd": 5.}]})
