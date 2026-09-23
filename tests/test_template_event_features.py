"""
test_template_event_features.py
=================================
The feature chains (fixup-d): `drop_event_features` and `spike_event_features`
in `webui/server/templates.py::CANONICAL`, the first templates of kind
`interrogation` — the kind `BLOCK_INTEGRATION.md` reserved for exactly these
blocks. Run end to end through `execute_recipe`:

* the drop chain's last block annotates the detector's spans with features and
  intervals, and the executor writes those spans to `detections` ONCE — a
  SpanSet -> SpanSet block measures the spans it was given, it does not detect
  them again;
* the spike chain inverts first, finds the same events on the inverted trace,
  and reports them as spikes;
* nothing a chain computes is persisted as a comparison (`motif_features` stays
  empty: the Library's features are measured on the Library's own hashed
  waveform, never on a chain's).

Runnable standalone:  python tests/test_template_event_features.py
"""

import os
import shutil
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from Working.database import queries as q  # noqa: E402
from Working.database.runs import list_detections  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.templates import apply_template  # noqa: E402
from server.templates import canonical, kind_for_steps  # noqa: E402

FS = 10.0


def sharkfin(seconds=60.0, period=10.0, fs=FS, seed=0):
    n = int(seconds * fs)
    t = np.arange(n) / fs
    phase = (t % period) / period
    x = np.where(phase < 0.85, phase / 0.85, 1.0 - (phase - 0.85) / 0.15) * 0.01
    x += 0.00002 * np.random.default_rng(seed).standard_normal(n)
    return x


@pytest.fixture
def scratch():
    tmp = tempfile.mkdtemp(prefix="feat_tpl_")
    import Working.config as cfg
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    try:
        yield tmp
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def _db(tmp, x):
    npy = os.path.join(tmp, "CH0.npy"); np.save(npy, x)
    db = os.path.join(tmp, "t.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, "synthetic.mat", 0, FS, len(x), 0, npy)
    conn.close()
    return db


def _tuned(name):
    """The canonical chain, with the detrend window and segment length a 10 Hz, 10 s-period
    synthetic needs (the same tuning `test_template_drop_detection.py` applies)."""
    tpl = canonical(name)
    for s in tpl["steps"]:
        if s["algorithm"] == "detrend":
            s["params"]["window_s"] = 12.0
        if s["algorithm"] == "stage_encoding":
            s["params"]["segment_seconds"] = 0.5
    return tpl


def _run(db, name, x, force=True):
    recipe = apply_template(None, _tuned(name), recording_id=1, span=(0, len(x)))
    return execute_recipe(recipe, db_path=db, force=force)


def test_the_two_feature_templates_are_interrogation_chains():
    drop = canonical("drop_event_features")
    spike = canonical("spike_event_features")
    assert drop["kind"] == spike["kind"] == "interrogation"
    assert [f"{s['stage']}.{s['algorithm']}" for s in drop["steps"]] == [
        "preprocessing.detrend", "detection.stage_encoding", "detection.drop_detection",
        "interrogation.event_shape", "interrogation.intervals"]
    assert [f"{s['stage']}.{s['algorithm']}" for s in spike["steps"]] == [
        "preprocessing.invert", "preprocessing.detrend", "detection.stage_encoding", "detection.drop_detection",
        "interrogation.event_shape", "interrogation.intervals"]
    assert spike["steps"][4]["params"]["upstream_inverted"] is True


def test_a_chain_ending_in_an_interrogation_block_is_kind_interrogation():
    steps = canonical("drop_event_features")["steps"]
    assert kind_for_steps(steps) == "interrogation"
    assert kind_for_steps(steps[:3]) == "detection"


def test_the_drop_chain_measures_every_detected_event_once(scratch):
    x = sharkfin()
    db = _db(scratch, x)
    out = _run(db, "drop_event_features", x)
    ss = out["result"].value
    f = ss.features
    assert len(f) == len(ss.starts) >= 4
    for col in ("event_amplitude_mv", "event_width_s", "fwhm_s", "recovery_time_s", "max_slope_mv_s",
                "interval_before_s"):
        assert col in f.columns
    assert (f["polarity"] == -1).all()
    assert np.nanmedian(f["interval_before_s"]) == pytest.approx(10.0, abs=0.5)
    conn = init_db(db)
    try:
        dets = list_detections(conn, out["run_id"])
        assert len(dets) == len(ss.starts), "a SpanSet -> SpanSet block re-wrote the detector's spans"
        assert conn.execute("SELECT COUNT(*) FROM motif_features").fetchone()[0] == 0
    finally:
        conn.close()


def test_the_spike_chain_finds_the_inverted_events_as_spikes(scratch):
    x = -sharkfin()
    db = _db(scratch, x)
    out = _run(db, "spike_event_features", x)
    f = out["result"].value.features
    assert len(f) >= 4
    assert (f["polarity"] == 1).all()
    assert (f["max_slope_mv_s"] > 0).all()


def test_the_features_survive_the_step_cache(scratch):
    """The second run restores every step from the cache; the features must come back with the spans."""
    import Working.config as cfg
    x = sharkfin()
    db = _db(scratch, x)
    old = cfg.STEP_CACHE_WRITE_THRESHOLD_S
    cfg.STEP_CACHE_WRITE_THRESHOLD_S = 0.0
    try:
        first = _run(db, "drop_event_features", x)["result"].value
        again = _run(db, "drop_event_features", x)
        second = again["result"].value
    finally:
        cfg.STEP_CACHE_WRITE_THRESHOLD_S = old
    assert all(v == 0.0 for v in again["step_timings"].values()), "the second run did not come from the cache"
    assert second.features is not None
    assert second == first


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
