"""
test_block_cost_api.py
======================
tq-worker (2026-10-25): `Working.block_cost` times a model and stores it through two public pieces, so a caller that
times in another process (the web bridge's calibration child) needs none of the module's privates:

* `time_model(name, n, fs, *, prewarm)` — pure: times the model on the synthetic signal and RETURNS ``(key, entry)``,
  writing nothing; ``prewarm`` runs the block's warm-up and one untimed synthetic call first (a fresh interpreter's
  cold start, fix round F1);
* `store_entries(entries, path)` — the locked read-merge-write of the calibration file;
* `calibrate()` is a loop over the two, its file byte-for-byte what it always wrote.

    python -m pytest tests/test_block_cost_api.py
"""
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working import block_cost  # noqa: E402

NAME = "tq.fake_model"


@pytest.fixture
def model(tmp_path, monkeypatch):
    calls = {"run": [], "warm": 0}

    def run_once(x, fs):
        calls["run"].append(len(x))

    def warm():
        calls["warm"] += 1
    monkeypatch.setitem(block_cost.MODELS, NAME, (1.0, run_once))
    monkeypatch.setitem(block_cost.WARM_UPS, NAME, warm)
    monkeypatch.setattr(block_cost, "CALIBRATION_PATH", str(tmp_path / "block_calibration.json"))
    return calls


def test_time_model_returns_the_key_and_entry_and_writes_nothing(model, tmp_path):
    key, entry = block_cost.time_model(NAME, n=500)
    assert json.loads(key)["block"] == NAME
    assert set(entry) == {"k", "exponent", "n", "elapsed_s", "calibrated_at"}
    assert entry["n"] == 500 and entry["exponent"] == 1.0 and entry["k"] >= 0
    assert model["run"] == [500] and model["warm"] == 1, "the block's own warm-up runs untimed, as calibrate's did"
    assert list(tmp_path.iterdir()) == [], "time_model wrote a file"


def test_prewarm_adds_one_untimed_synthetic_call_before_the_timed_one(model):
    block_cost.time_model(NAME, n=500, prewarm=True)
    assert model["run"] == [1000, 500], "one untimed call on a small synthetic series, then the timed one"


def test_store_entries_merges_into_the_file_and_keeps_the_others(model, tmp_path):
    path = str(tmp_path / "cal.json")
    block_cost.store_entries({"other": {"k": 1.0}}, path)
    key, entry = block_cost.time_model(NAME, n=100)
    block_cost.store_entries({key: entry}, path)
    data = json.load(open(path, encoding="utf-8"))
    assert data["other"] == {"k": 1.0} and data[key] == entry


def test_calibrate_writes_byte_for_byte_what_it_always_wrote(model, tmp_path, monkeypatch):
    ticks = iter([10.0, 10.5])
    monkeypatch.setattr(block_cost.time, "perf_counter", lambda: next(ticks))
    monkeypatch.setattr(block_cost.time, "strftime", lambda fmt: "2026-10-25T12:00:00")
    path = tmp_path / "cal.json"
    assert block_cost.calibrate([NAME], n=1000, path=str(path)) == {NAME: 0.5 / 1000}
    (key,) = json.loads(path.read_text(encoding="utf-8"))
    assert json.loads(key)["block"] == NAME
    expected = {key: {"k": 0.5 / 1000, "exponent": 1.0, "n": 1000, "elapsed_s": 0.5,
                                        "calibrated_at": "2026-10-25T12:00:00"}}
    assert path.read_text(encoding="utf-8") == json.dumps(expected, indent=2, sort_keys=True)
    # a second call finds the key and times nothing (force=False)
    assert block_cost.calibrate([NAME], n=1000, path=str(path)) == {NAME: 0.5 / 1000}
    assert model["run"] == [1000]
