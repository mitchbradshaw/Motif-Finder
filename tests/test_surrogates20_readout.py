"""The 20-draw read-out (Chapter 6): each variant's real count on a channel against that channel's own 20
phase-randomised draws, read straight from the returned task records."""
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts", "thesis"))

import surrogates20_readout as S  # noqa: E402


def _task(root, job, task, channel, real, draws, complete=True):
    d = os.path.join(root, f"{job}_16ch_0-2595600_abc123_out", "return", f"task{task}")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "result.json"), "w", encoding="utf-8") as fh:
        json.dump({"kind": "detection_chain_result", "task": task, "channelName": channel, "complete": complete,
                   "run": {"detections": real}, "draws": {"asked": len(draws), "drawn": len(draws),
                                                          "detections": list(draws)}}, fh)


def test_a_channel_is_ranked_against_its_own_draws():
    row = S.channel_stats(real=10, draws=[1] * 19 + [10])
    assert row["p_high"] == pytest.approx(2 / 21)       # one draw ties the real count: (1 + 1) / 21
    assert row["p_low"] == pytest.approx(1.0)
    assert row["beats_all"] is False and row["below_all"] is False
    top = S.channel_stats(real=50, draws=list(range(20)))
    assert top["p_high"] == pytest.approx(1 / 21) and top["beats_all"] is True
    assert top["ratio"] == pytest.approx(50 / 9.5)


def test_a_variant_counts_channels_beyond_every_draw_against_chance(tmp_path):
    root = str(tmp_path)
    for ch in range(16):
        _task(root, "drop_detection_v1", ch, f"CH{ch + 1}", real=40, draws=[ch % 3] * 20)
    out = S.read_out(root)
    v = out["variants"]["drop_detection_v1"]
    assert v["channels"] == 16 and v["beats_all"] == 16 and v["below_all"] == 0
    assert v["p_channels_high"] < 1e-15                   # 16 of 16 beyond every draw, chance 1/21 each
    assert v["pooled"]["real"] == 640 and v["pooled"]["p_high"] == pytest.approx(1 / 21)


def test_a_detector_that_fires_more_on_its_draws_is_read_the_other_way(tmp_path):
    root = str(tmp_path)
    for ch in range(16):
        _task(root, "wavelet_encoded__level_5", ch, f"CH{ch + 1}", real=5, draws=[100 + d for d in range(20)])
    v = S.read_out(root)["variants"]["wavelet_encoded__level_5"]
    assert v["beats_all"] == 0 and v["below_all"] == 16
    assert v["pooled"]["ratio"] < 0.1 and v["pooled"]["p_low"] == pytest.approx(1 / 21)


def test_an_incomplete_task_is_refused_not_counted(tmp_path):
    root = str(tmp_path)
    _task(root, "drop_detection_v1", 0, "CH1", real=4, draws=[1] * 20)
    _task(root, "drop_detection_v1", 1, "CH2", real=4, draws=[1] * 20, complete=False)
    with pytest.raises(ValueError, match="incomplete"):
        S.read_out(root)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
