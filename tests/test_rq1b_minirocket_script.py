"""
test_rq1b_minirocket_script.py
==============================
a2-rq1b (R4, 2026-10-20): `scripts/rq1b_minirocket.py`, a MiniRocket classifier of the researcher's own verdicts,
interesting versus not.

What is pinned, and why each one is silent when broken:

* **Only the researcher's own judgements are labels.** A verdict Review carried to another run's detection of the
  same event (`adjudications.carried_from`) is that event again: counting it would weigh one judgement many times. A
  seed is interesting (Q41); unsure is no answer; artifact is "kept out of training", as Review says. The held-out
  exam (M4_aug) and the reishi pieces (Fig2A) never enter.
* **One event once.** Two judged spans that overlap by half the shorter are one event: kept once when they agree,
  dropped (and counted) when they disagree. An event is never merged into a window that holds it.
* **Recordings of one experiment are one group** (a 10 Hz recording and its 2 Hz copy), so a held-out recording is
  really unseen.
* **One input shape for every span:** the span with a quarter of its length of context on each side, in millivolts,
  reduced to a fixed length by bin means (never by picking samples, which aliases noise).
* **The model learns the classes on unseen recordings** (synthetic), and a saved model scores as it did when trained.

Run from the project root:
    python -m pytest tests/test_rq1b_minirocket_script.py -q
"""

import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.config import HELD_OUT_RECORDING_FILE
from Working.database.schema import init_db
from Working.database import queries as q
from Working.database import vocabulary as v

SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "rq1b_minirocket.py")
T = "2026-10-20T00:00:00"


def _script():
    spec = importlib.util.spec_from_file_location("rq1b_minirocket_script", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _recording(conn, tmp_path, source_file, channel=0, fs=1.0, units="V", x=None):
    x = np.zeros(20_000) if x is None else np.asarray(x, dtype=float)
    path = tmp_path / f"{source_file}_{channel}.npy"
    np.save(path, x)
    return q.insert_recording(conn, source_file, channel, fs, len(x), 0, str(path), units=units)


def _detection(conn, rid, s, e):
    cid = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES (?, '{}', ?)",
                       (f"c{rid}-{s}-{e}", T)).lastrowid
    run = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
                       "VALUES (?, ?, 0, 20000, ?, 'completed')", (cid, rid, T)).lastrowid
    return conn.execute("INSERT INTO detections (run_id, start_idx, end_idx) VALUES (?, ?, ?)", (run, s, e)).lastrowid


def _adjudicate(conn, det, verdict, carried_from=None):
    conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at, carried_from) VALUES (?, ?, ?, ?)",
                 (det, verdict, T, carried_from))


@pytest.fixture
def db(tmp_path):
    conn = init_db(str(tmp_path / "a.sqlite"))
    v.seed_vocabulary(conn)
    return conn


# ── labels ─────────────────────────────────────────────────────────────────

def test_only_the_researcher_s_own_verdicts_are_labels(db, tmp_path):
    mod = _script()
    rid = _recording(db, tmp_path, "rec.mat")
    held = _recording(db, tmp_path, HELD_OUT_RECORDING_FILE)
    fig = _recording(db, tmp_path, "Fig2A_dt0p1.csv")
    verdicts = {"interesting": (100, 200), "seed": (1000, 1100), "not_interesting": (2000, 2100),
                "artifact": (3000, 3100), "unsure": (4000, 4100)}
    dets = {k: _detection(db, rid, *span) for k, span in verdicts.items()}
    for k, d in dets.items():
        _adjudicate(db, d, k)
    carried = _detection(db, rid, 5000, 5100)
    _adjudicate(db, carried, "interesting", carried_from=1)
    _adjudicate(db, _detection(db, held, 100, 200), "interesting")
    _adjudicate(db, _detection(db, fig, 100, 200), "interesting")
    q.insert_annotation(db, rid, 6000, 6100, "not_interesting", source="library_review")
    q.insert_annotation(db, rid, 7000, 7600, "interesting", source="imported_10min")
    db.commit()
    labels, counts = mod.collect_labels(db, with_windows=False)
    got = sorted(zip(labels["start"], labels["label"], labels["source"]))
    assert got == [(100, 1, "adjudication"), (1000, 1, "adjudication"), (2000, 0, "adjudication"),
                   (6000, 0, "library_review")]
    assert counts["artifact"] == 1 and counts["unsure"] == 1 and counts["carried"] == 1
    assert counts["held_out_or_excluded_recording"] == 2
    with_windows, _ = mod.collect_labels(db, with_windows=True)
    assert (7000, 1, "window") in set(zip(with_windows["start"], with_windows["label"], with_windows["kind"]))


def test_recordings_of_one_experiment_are_one_group():
    mod = _script()
    assert mod.group_of("L_LM_Jul_26_J_raw.mat") == mod.group_of("L_LM_Jul_26_J_raw_fs2.mat")
    assert mod.group_of("M2_aug_concat_fs1.mat") == mod.group_of("M2_aug_concat_fs2.mat")
    assert mod.group_of("M2_concat_fs1.mat") != mod.group_of("M2_aug_concat_fs1.mat")
    assert mod.group_of("CO_fs2.mat") != mod.group_of("LM_fs2.mat")


def _rows(rows):
    """Label rows: (group, channel, start_s, end_s, label, source, kind)."""
    return pd.DataFrame([{"group": g, "channel": c, "t0": a, "t1": b, "label": lab, "source": s, "kind": k,
                          "start": int(a), "end": int(b), "fs": 1.0} for g, c, a, b, lab, s, k in rows])


def test_one_event_is_kept_once_and_a_disagreement_is_dropped():
    mod = _script()
    df = _rows([("A", 0, 100, 200, 1, "library_review", "event"),
                ("A", 0, 110, 200, 1, "adjudication", "event"),        # the same event, agreeing
                ("A", 0, 1000, 1100, 1, "adjudication", "event"),
                ("A", 0, 1020, 1100, 0, "adjudication", "event"),       # the same event, disagreeing
                ("A", 1, 100, 200, 0, "adjudication", "event"),         # another channel
                ("A", 0, 0, 600, 1, "window", "window"),                # a window holding the first event
                ("A", 0, 0, 600, 1, "window", "window"),                # the same window, judged twice
                ("A", 0, 200, 800, 0, "window", "window")])             # an overlapping grid window stays
    out, counts = mod.dedupe(df)
    events = out[out.kind == "event"]
    assert sorted(zip(events.channel, events.t0, events.source)) == [(0, 110, "adjudication"), (1, 100, "adjudication")]
    assert counts["conflicting_events"] == 2 and counts["duplicate_events"] == 1
    windows = out[out.kind == "window"]
    assert sorted(zip(windows.t0, windows.label)) == [(0, 1), (200, 0)]


# ── the input ──────────────────────────────────────────────────────────────

def test_resampling_takes_bin_means_down_and_interpolates_up():
    mod = _script()
    x = np.repeat([0.0, 10.0], 500)                       # a step, 1000 samples
    y = mod.resample(x, 10)
    assert y.shape == (10,) and np.allclose(y[:5], 0) and np.allclose(y[5:], 10)
    noisy = np.tile([1.0, -1.0], 500)                     # picking every 100th sample would read all +1
    assert np.allclose(mod.resample(noisy, 10), 0)
    up = mod.resample(np.array([0.0, 1.0, 2.0]), 5)
    assert np.allclose(up, [0, 0.5, 1, 1.5, 2])


def test_a_span_is_read_with_context_in_millivolts(db, tmp_path):
    mod = _script()
    x = np.zeros(20_000)
    x[1000:1100] = 0.002                                  # 2 mV in volts
    rid = _recording(db, tmp_path, "volts.mat", x=x, units="V")
    rid_mv = _recording(db, tmp_path, "mv.mat", x=x * 1000, units="mV")
    rows = pd.DataFrame([{"recording_id": rid, "start": 1000, "end": 1100},
                         {"recording_id": rid_mv, "start": 1000, "end": 1100},
                         {"recording_id": rid, "start": 0, "end": 40}])          # context clipped at the start
    M, side, keep = mod.extract(db, rows, length=150)
    assert keep.all() and M.shape == (3, 150)
    assert np.isclose(M[0].max(), 2.0) and np.isclose(M[1].max(), 2.0)
    assert np.isclose(M[0][:25].max(), 0.0) and np.isclose(M[0][-25:].max(), 0.0)  # a quarter each side
    assert np.allclose(side.loc[0, ["duration_s", "p2p_mv"]], [100.0, 2.0])


def test_a_span_mostly_missing_is_left_out(db, tmp_path):
    mod = _script()
    x = np.zeros(20_000)
    x[1000:1100] = np.nan
    rid = _recording(db, tmp_path, "gappy.mat", x=x)
    M, side, keep = mod.extract(db, pd.DataFrame([{"recording_id": rid, "start": 1000, "end": 1100}]), length=64)
    assert not keep[0]


# ── learning ───────────────────────────────────────────────────────────────

def _synthetic(n_per=60, groups=("G1", "G2", "G3"), seed=0, length=128):
    """Bumps (interesting) against pure noise (not) of the same size, per group."""
    rng = np.random.default_rng(seed)
    t = np.linspace(-1, 1, length)
    rows, M = [], []
    for g in groups:
        for i in range(n_per):
            lab = i % 2
            sig = rng.normal(0, 0.3, length) + (np.exp(-(t / 0.15) ** 2) * 3 if lab else 0)
            M.append(sig)
            rows.append({"group": g, "channel": i % 3, "label": lab, "kind": "event"})
    side = pd.DataFrame({"duration_s": np.full(len(rows), 100.0), "p2p_mv": [np.ptp(m) for m in M],
                         "noise_mv": np.full(len(rows), 0.3), "snr": [np.ptp(m) / 0.3 for m in M]})
    return pd.DataFrame(rows), np.asarray(M), side


def test_the_model_learns_the_classes_on_unseen_recordings_and_scores_the_same_after_saving(tmp_path):
    mod = _script()
    rows, M, side = _synthetic()
    res = mod.evaluate(rows, M, side, split="recording", n_features=840)
    assert res["pooled"]["balanced_accuracy"] > 0.9 and res["pooled"]["auc"] > 0.95
    assert {f["held_out"] for f in res["folds"]} == {"G1", "G2", "G3"}
    model = mod.fit_model(rows, M, side, n_features=840)
    path = mod.save_model(model, tmp_path / "m")
    again = mod.load_model(path)
    assert np.allclose(mod.decision(model, M[:10], side.iloc[:10]), mod.decision(again, M[:10], side.iloc[:10]))
    p = mod.probability(again, M[:10], side.iloc[:10])
    assert ((p >= 0) & (p <= 1)).all()
