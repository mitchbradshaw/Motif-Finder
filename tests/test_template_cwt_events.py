"""
test_template_cwt_events.py
=============================
The `cwt_events` TEMPLATE (W1-C): `detection.cwt_ridges` -> `interrogation.event_shape`
-> `interrogation.intervals`, run end to end through `execute_recipe` on a
synthetic recording in a temporary database.

The template is defined here as a module-level constant; the manager moves it
into `webui/server/templates.py::CANONICAL` (the prompt's integration step), so
this file does not import it from there.

Pinned: the chain runs with its default parameters on a 1 Hz recording; every
injected event comes out once, with the CWT block's scale and polarity AND
Event shape's measures AND Intervals' timing on the same row; the detector's
spans are written to `detections` once (a feature block does not re-detect);
the ridge's own polarity survives Event shape (which re-measures `polarity`);
both blocks are set to drops, so they agree on every event (critic F3).

Runnable standalone:  python tests/test_template_cwt_events.py
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

TEMPLATE = {
    "name": "cwt_events", "kind": "interrogation", "version": 1,
    "description": "Drops (troughs) at every duration: CWT ridges (Du, Kibbe & Lin 2006: troughs at every scale "
                   "at once, each with its own duration; no detrend window) -> Event shape (amplitude, width, "
                   "FWHM, recovery, slopes, measured as drops like the ridge) -> Intervals (per-event interval, "
                   "CV, trend, drift). Both blocks are set to drops so the two agree on every event (Event "
                   "shape's auto polarity let the drift's slope decide); a spike variant can come later. "
                   "Tune min_snr first; keep max_scale_s below the usual spacing of events.",
    "steps": [
        {"stage": "detection", "algorithm": "cwt_ridges", "params": {"polarity": "drop"}},
        {"stage": "interrogation", "algorithm": "event_shape", "params": {"polarity": "drop"}},
        {"stage": "interrogation", "algorithm": "intervals", "params": {}},
    ],
}

FS = 1.0
SIG = 2.0 * np.sqrt(2.0 * np.log(2.0))
# (centre s, FWHM s, polarity): a 12 h recording in volts, two of each family
EVENTS = [(1800, 24, +1), (5400, 480, -1), (9000, 24, -1), (14400, 2580, +1), (21600, 480, +1),
          (27000, 24, +1), (33000, 2580, -1), (39600, 480, -1)]


def recording(seed=0):
    n = 12 * 3600
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    x = 1.5e-4 * rng.standard_normal(n) + 4e-3 * (t / n) + 3e-3 * (t / n - 0.4) ** 2
    for c, w, p in EVENTS:
        x += p * 1e-3 * np.exp(-0.5 * ((t - c) / (w / SIG)) ** 2)
    return x


@pytest.fixture
def db():
    tmp = tempfile.mkdtemp(prefix="cwt_tpl_")
    x = recording()
    npy = os.path.join(tmp, "CH0.npy")
    np.save(npy, x)
    path = os.path.join(tmp, "t.sqlite")
    conn = init_db(path)
    q.insert_recording(conn, "synthetic.mat", 0, FS, len(x), 0, npy)
    conn.close()
    import Working.config as cfg
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    try:
        yield path, x
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def test_the_template_is_an_interrogation_chain_of_three_known_blocks():
    from Adapters.registry import discover_adapters, get_adapter
    from server.templates import kind_for_steps
    discover_adapters()
    for s in TEMPLATE["steps"]:
        get_adapter(f"{s['stage']}.{s['algorithm']}")
    assert kind_for_steps(TEMPLATE["steps"]) == TEMPLATE["kind"] == "interrogation"
    assert kind_for_steps(TEMPLATE["steps"][:1]) == "detection"


def test_the_template_runs_end_to_end_and_measures_every_event_once(db):
    path, x = db
    recipe = apply_template(None, TEMPLATE, recording_id=1)
    out = execute_recipe(recipe, db_path=path, force=True)
    ss = out["result"].value
    f = ss.features
    assert out["result"].output_kind == "spanset"
    for col in ("best_scale_s", "cwt_duration_s", "snr", "ridge_polarity", "edge_flag",   # CWT ridges
                "event_amplitude_mv", "fwhm_s", "onset_idx", "extremum_idx",           # Event shape
                "interval_before_s", "interval_after_s"):                              # Intervals
        assert col in f.columns, col
    assert set(f["ridge_polarity"]) == {"drop"}, "the template is the drop variant"
    drops = [(c, w) for c, w, p in EVENTS if p < 0]
    for c, w in drops:
        rows = f[np.abs(f["peak_idx"] - c) <= max(0.5 * w, 30)]
        assert len(rows) == 1, f"the {w} s drop at {c} s: {len(rows)} rows"
        assert 1 / 1.5 <= rows["cwt_duration_s"].iloc[0] / w <= 1.5, "the scale's duration survives Event shape"
        assert rows["event_amplitude_mv"].iloc[0] == pytest.approx(1.0, rel=0.35), "Event shape measured it"
        assert rows["polarity"].iloc[0] == -1, "Event shape measured it as a drop, as the ridge did"
    unmarked = f[~(f["edge_flag"] | f["step_pair"])]
    assert len(unmarked) == len(drops), "nothing extra goes unmarked"
    conn = init_db(path)
    try:
        rows = list_detections(conn, out["run_id"])
    finally:
        conn.close()
    assert len(rows) == len(ss.starts) == out["detections_written"], "the detector's spans are written once"
    assert sorted((r["start_idx"], r["end_idx"]) for r in rows) == sorted(zip(ss.starts, ss.ends))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
