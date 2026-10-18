"""
test_windowed_explore.py
========================
Round A_2, P3, fix round (the critic's M1): a windowed application writes one ordinary run per window beside the
stitched run it is read as. The readers that pool every run of a recording — Explore's spans, ribbons, channel
summary, run list and coverage, the divergence when no run is picked, a review queue over a run group — read the
stitched run once and never its window runs (`queries.not_window_part`, beside `not_surrogate`); a window run asked
for by its id is still read.

The run history (`/api/runs`) is the bridge's: `tests/test_webui_discovery_windows.py`.

    PYTHONIOENCODING=utf-8 python -m pytest tests/test_windowed_explore.py -q -p no:cacheprovider
"""

import json
import os
import sqlite3
import sys

import numpy as np
import pytest
from scipy.signal import lfilter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import Working.config as cfg  # noqa: E402
from Adapters.registry import discover_adapters  # noqa: E402
from Working import run_groups as RG  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database import runs as R  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery import divergence as DIV  # noqa: E402
from Working.discovery import fanout  # noqa: E402
from Working.recipes import canonical_json, make_recipe, short_hash  # noqa: E402
from server import corpus  # noqa: E402

discover_adapters()

FS = 1.0
H = 3600
N = 12 * H
#: the critic's probe (probe_p3_explore.py): a 300 s baseline, a 3.5 sigma_n cut
NT = [{"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean", "window_s": 300.0}},
      {"stage": "detection", "algorithm": "noise_threshold",
       "params": {"k_sigma": 3.5, "direction": "below", "min_duration_s": 20.0, "merge_gap_s": 30.0}}]


def _coloured(seed, n=N):
    rng = np.random.default_rng(seed)
    x = lfilter([1.0], [1.0, -0.97], rng.standard_normal(n) * 0.001)
    x += 0.02 * np.sin(np.linspace(0, 3 * np.pi, n))
    for a in range(600, n - 600, 3000):
        x[a:a + 120] -= 0.03 * np.exp(-np.linspace(0, 3, 120))
    return x


@pytest.fixture
def applied(tmp_path, monkeypatch):
    """One whole-span run of the chain, then the same chain in 2-hour windows at 50 % (11 window runs)."""
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", str(tmp_path / "cache"))
    db = str(tmp_path / "annotations.sqlite")
    npy = tmp_path / "syn_CH0.npy"
    np.save(npy, _coloured(0))
    conn = init_db(db)
    try:
        rid = q.insert_recording(conn, "syn.mat", 0, FS, N, 0, str(npy), units="V")
        plan = fanout.plan(conn, steps=NT, recording_ids=[rid], span=(0, N), ceiling_s=1200)
    finally:
        conn.close()
    whole = fanout.start(plan, db_path=db)["run_ids"][0]
    conn = init_db(db)
    try:
        wplan = fanout.plan(conn, steps=NT, recording_ids=[rid], span=(0, N), ceiling_s=1200,
                            windows={"window_s": 2 * H})
    finally:
        conn.close()
    w = fanout.start(wplan, db_path=db)
    row = w["runs"][0]
    conn = init_db(db)
    try:
        n = {i: conn.execute("SELECT COUNT(*) FROM detections WHERE run_id = ?", (i,)).fetchone()[0]
             for i in [whole, row["run_id"], *row["window_run_ids"]]}
    finally:
        conn.close()
    assert n[whole] > 0 and n[row["run_id"]] > 0
    assert sum(n[i] for i in row["window_run_ids"]) > n[row["run_id"]], "the windows overlap: their raw sum is more"
    return {"db": db, "rid": rid, "whole": whole, "stitched": row["run_id"], "windows": row["window_run_ids"],
            "group": w["run_group_id"], "n": n}


def _conn(db):
    conn = init_db(db)
    conn.row_factory = sqlite3.Row
    return conn


def test_explores_pooled_readers_read_the_stitched_run_once_and_no_window_run(applied):
    """The critic's probe: after one windowed application beside one whole-span run, Explore read the 11 window runs
    beside the stitched run, so an event showed once per window that found it, and once more stitched."""
    a = applied
    expect = a["n"][a["whole"]] + a["n"][a["stitched"]]
    conn = _conn(a["db"])
    try:
        sp = corpus.spans(conn, a["rid"], 0.0, N / FS, FS)
        assert {d["run_id"] for d in sp["detections"]} == {a["whole"], a["stitched"]}
        assert len(sp["detections"]) == expect
        assert int(sum(corpus.ribbons(conn, a["rid"], FS, N)["detection_density"])) == expect
        assert corpus.channel_summary(conn, a["rid"]) == {"annotations": 0, "detections": expect,
                                                          "detection_runs": 2}
        rm = corpus.run_methods(conn, "syn.mat")
        assert [r["id"] for r in rm] == sorted([a["whole"], a["stitched"]], reverse=True), "newest first, as before"
        assert {r["id"]: r["n_detections"] for r in rm} == {a["whole"]: a["n"][a["whole"]],
                                                           a["stitched"]: a["n"][a["stitched"]]}
        assert all(r["method"] == "noise_threshold" for r in rm)
        cov = corpus.coverage(conn, "syn.mat")
        assert cov["rows"][0]["counts"]["detections"] == expect
        assert cov["n_detection_runs"] == 2
        assert cov["divergence"]["n_runs"] == 2 and cov["divergence"]["pooled"] is True
    finally:
        conn.close()


def test_a_window_run_asked_for_by_its_id_is_still_read(applied):
    a = applied
    w0 = a["windows"][0]
    conn = _conn(a["db"])
    try:
        assert [r["id"] for r in DIV.real_runs(conn, a["rid"])] == sorted([a["whole"], a["stitched"]])
        assert [r["id"] for r in DIV.real_runs(conn, a["rid"], run_ids=[w0])] == [w0], "asked for, it is read"
        cov = corpus.coverage(conn, "syn.mat", run_ids=[w0])
        assert cov["rows"][0]["counts"]["detections"] == a["n"][w0]
    finally:
        conn.close()


def test_a_queue_over_the_applications_run_group_holds_the_stitched_set_only(applied):
    """A run group holds its windows too (each window run joins the application's group); a queue over the group
    put every window's view of an event in front of the researcher beside the stitched one."""
    a = applied
    conn = _conn(a["db"])
    try:
        rows = q.queue_candidates(conn, run_group_id=a["group"], limit=10_000)
        assert {int(r["run_id"]) for r in rows} == {a["stitched"]}
        assert len(rows) == a["n"][a["stitched"]]
        by_id = q.queue_candidates(conn, run_id=a["windows"][0], limit=10_000)
        assert len(by_id) == a["n"][a["windows"][0]], "a window run asked for by its id is still its own queue"
    finally:
        conn.close()


def _bulk_application(db, k):
    """The rows a windowed application of ``k`` windows writes (each window run with one null draw, two detections a
    window, the stitched run and its provenance), in bulk — the critic's probe_p3_scale.py."""
    conn = init_db(db)
    try:
        n = 600 * (k + 1)
        rid = q.insert_recording(conn, "bulk.mat", 0, FS, n, 0, "none.npy", units="V")
        base = dict(make_recipe(rid, NT, span=(0, 1200)), surrogate=True)
        now = "2026-10-18T00:00:00+00:00"
        spans = [(600 * i, 600 * i + 1200) for i in range(k)]
        cfgs = []
        for a, b in spans:
            r = dict(base, span=[a, b])
            d = RG.surrogate_recipe(r, {"method": "phase_randomize", "seed": 0})
            cfgs += [(short_hash(r), canonical_json(r), now), (short_hash(d), canonical_json(d), now)]
        conn.executemany("INSERT INTO configs (config_hash, config_json, created_at) VALUES (?, ?, ?)", cfgs)
        ids = {h: i for i, h in conn.execute("SELECT id, config_hash FROM configs")}
        cur = conn.cursor()
        windows, dets = [], []
        for i, (a, b) in enumerate(spans):
            cur.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
                        "VALUES (?, ?, ?, ?, ?, 'completed')", (ids[cfgs[2 * i][0]], rid, a, b, now))
            real = cur.lastrowid
            cur.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, "
                        "surrogate_of_run_id) VALUES (?, ?, ?, ?, ?, 'completed', ?)",
                        (ids[cfgs[2 * i + 1][0]], rid, a, b, now, real))
            windows.append(real)
            dets += [(real, a + 100, a + 160), (real, a + 700, a + 760), (cur.lastrowid, a + 300, a + 330)]
        conn.executemany("INSERT INTO detections (run_id, start_idx, end_idx) VALUES (?, ?, ?)", dets)
        st = {"recording_id": rid, "span": [0, n], "steps": NT, "surrogate": True,
              "windows": {"kind": "windows", "window_s": 1200.0, "overlap_frac": 0.5}}
        conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES (?, ?, ?)",
                     (short_hash(st), canonical_json(st), now))
        cur.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
                    "VALUES ((SELECT id FROM configs WHERE config_hash = ?), ?, 0, ?, ?, 'completed')",
                    (short_hash(st), rid, n, now))
        stitched = cur.lastrowid
        conn.executemany("INSERT INTO detections (run_id, start_idx, end_idx, meta_json) VALUES (?, ?, ?, ?)",
                         [(stitched, a + 100, a + 160, json.dumps({"window": i})) for i, (a, b) in enumerate(spans)])
        conn.executemany("INSERT INTO stitched_windows (run_id, window_index, window_run_id, span_start, span_end, "
                         "core_start, core_end, found, kept) VALUES (?, ?, ?, ?, ?, ?, ?, 2, 1)",
                         [(stitched, i, windows[i], a, b, a, a + 600) for i, (a, b) in enumerate(spans)])
        conn.commit()
        return rid, stitched
    finally:
        conn.close()


def test_the_run_list_is_read_in_a_few_statements_whatever_the_windows(tmp_path):
    """`run_methods` walked every run in the database and, for each on the recording, counted its detections and
    loaded its recipe: 2.26 s at 20,000 windows (the critic's measure). It is one query now, its recipes loaded once
    per config, the window runs left out in SQL."""
    db = str(tmp_path / "bulk.sqlite")
    rid, stitched = _bulk_application(db, 2000)
    conn = _conn(db)
    statements = []
    conn.set_trace_callback(statements.append)
    try:
        rm = corpus.run_methods(conn, "bulk.mat")
    finally:
        conn.set_trace_callback(None)
        conn.close()
    assert [r["id"] for r in rm] == [stitched] and rm[0]["n_detections"] == 2000
    assert len(statements) < 10, f"{len(statements)} statements for one recording's run list"
