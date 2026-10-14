"""
test_webui_block_readout.py
===========================
A block's `derive` readout, shown on its block page, is computed on what the block is handed in a run
(the researcher's choice, 2026-10-14), not on the stored recording.

The bridge has served the readout since stage 3 (POST /api/blocks/derive) but always on the stored span,
and no page asked for it. Measured on real spans before this change: the noise-threshold block after
baseline removal would have printed sigma_n 8-20x too large and a cut near -500 mV where it cuts near
-6 mV, and the nine blocks that read an upstream typed value (drop detection, event shape, motif groups,
...) said "run X first" even straight after a run, because the route never handed them that value.

`server.readout.block_readout` walks the stages before the block the way `execute_recipe` does — the
signal carried through every Signal stage, the last typed value handed on as `value`, side inputs
resolved — reading a stage from the step cache when the cache holds it and re-running it in memory
otherwise, but only when its estimate fits the readout's budget. It writes nothing: no run row, no step
cache entry, no persisted artifact.

The two route tests need FastAPI (webui/.venv); under the conda pytest they skip with a message, the rest run:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_block_readout.py
"""

import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from Adapters.registry import discover_adapters, get_adapter  # noqa: E402

discover_adapters()

FS = 1.0
N = 36_000                                    # ten hours at 1 Hz
GAPS = ((8_000, 8_480), (20_000, 20_480))     # two holes: 960 missing samples, the first at 2:13:20

DETREND_600 = {"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean", "window_s": 600.0}}
MP_STEPS = [DETREND_600,
            {"stage": "detection", "algorithm": "matrix_profile", "params": {"window_min": 5.0}},
            {"stage": "detection", "algorithm": "mp_motifs", "params": {}}]


def _template(name):
    from server.templates import CANONICAL
    return [dict(s) for t in CANONICAL if t["name"] == name for s in t["steps"]]


DROP_STEPS = _template("drop_detection_v1")      # Baseline removal -> five-stage encoding -> drop detection
NOISE_STEPS = _template("noise_threshold")       # Baseline removal -> noise threshold


def _trace():
    """Volts, as the M2 exports are stored: a slow wander that baseline removal takes out, white noise,
    a sharp fall every two hours with its recovery, and two gaps."""
    rng = np.random.default_rng(1014)
    t = np.arange(N) / FS
    x = 0.05 * np.sin(2 * np.pi * t / 30_000.0) + 0.0005 * rng.standard_normal(N)
    for c in range(3_000, N - 2_000, 7_200):
        x[c:c + 60] -= np.linspace(0.0, 0.02, 60)
        x[c + 60:c + 1_260] -= 0.02 * np.exp(-np.arange(1_200) / 400.0)
    for a, b in GAPS:
        x[a:b] = np.nan
    return x


def _spec(step):
    return get_adapter(f"{step['stage']}.{step['algorithm']}")


def _params(step):
    return _spec(step).validate_params(step.get("params") or {})


def _source(rec, span=None):
    s0, s1 = span or (0, rec["n_samples"])
    return np.asarray(np.load(rec["npy_path"], mmap_mode="r")[s0:s1]), np.arange(s0, s1) / rec["fs"]


def _rows(rows):
    """A derive's rows in the route's JSON shape."""
    return [{"label": r[0], "value": str(r[1]), "severity": r[2] if len(r) > 2 else ""} for r in rows]


def _detrended(rec, span=None, step=DETREND_600):
    x, t = _source(rec, span)
    return _spec(step).run(x, t, FS, **_params(step)).value.x, t


def _never(*a, **k):
    raise AssertionError("the readout ran a stage it must not run")


def _table_counts(conn):
    names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    return {n: conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}


@pytest.fixture
def store(tmp_path):
    from server import corpus
    from Working.database.schema import init_db
    npy = tmp_path / "CH0.npy"
    np.save(npy, _trace())
    conn = init_db(str(tmp_path / "annotations.sqlite"))
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
                 "VALUES ('readout.mat', 0, ?, ?, 0, ?, 'V')", (FS, N, str(npy)))
    conn.commit()
    rec = corpus.recording_row(conn, conn.execute("SELECT id FROM recordings").fetchone()[0])
    try:
        yield conn, rec
    finally:
        conn.close()


# ── what the readout is computed on ─────────────────────────────────────────

def test_the_encoding_readout_is_computed_on_the_detrended_signal(store):
    from server import readout
    conn, rec = store
    step = DROP_STEPS[1]
    xd, t = _detrended(rec, step=DROP_STEPS[0])
    out = readout.block_readout(conn, rec, None, DROP_STEPS, 1)
    assert out["block"] == "detection.stage_encoding" and out["has_derive"] is True and out["skipped"] is None
    assert out["rows"] == _rows(_spec(step).derive(xd, t, FS, _params(step)))
    assert [(s["index"], s["name"], s["from"]) for s in out["input"]] == [(0, "preprocessing.detrend", "run")]


def test_the_noise_threshold_readout_reads_what_baseline_removal_left(store):
    """The case that decided it: the stored span's spread is the drift's, not the noise's."""
    from server import readout
    conn, rec = store
    step = NOISE_STEPS[1]
    x, t = _source(rec)
    xd, _ = _detrended(rec, step=NOISE_STEPS[0])
    raw, real = (_rows(_spec(step).derive(v, t, FS, _params(step))) for v in (x, xd))
    assert raw != real, "the trace must tell the stored span from the block's input"
    assert readout.block_readout(conn, rec, None, NOISE_STEPS, 1)["rows"] == real


def test_drop_detection_is_handed_the_encoders_letters(store):
    """Before: "Letters · run the five-stage encoding first" (warn), even straight after a run."""
    from server import readout
    conn, rec = store
    xd, t = _detrended(rec, step=DROP_STEPS[0])
    enc = _spec(DROP_STEPS[1]).run(xd, t, FS, **_params(DROP_STEPS[1]))
    out = readout.block_readout(conn, rec, None, DROP_STEPS, 2)
    want = _rows(_spec(DROP_STEPS[2]).derive(xd, t, FS, _params(DROP_STEPS[2]), value=enc.value))
    assert out["rows"] == want
    letters = [r for r in out["rows"] if r["label"] == "Letters"]
    assert letters and letters[0]["severity"] == "" and letters[0]["value"].endswith("fast falls")
    assert [(s["index"], s["from"]) for s in out["input"]] == [(0, "run"), (1, "run")]


def test_a_gap_in_the_span_is_a_warn_row_on_both_drop_blocks(store):
    from server import readout
    conn, rec = store
    for index in (1, 2):
        gap = [r for r in readout.block_readout(conn, rec, None, DROP_STEPS, index)["rows"] if r["label"] == "Missing samples"]
        assert len(gap) == 1 and gap[0]["severity"] == "warn", index
        assert gap[0]["value"].startswith("960 in 2 gaps · first at 2:13:20"), gap[0]["value"]


def test_a_span_is_read_on_the_channels_own_clock(store):
    from server import readout
    conn, rec = store
    span = (10_000, 30_000)
    step = DROP_STEPS[1]
    xd, t = _detrended(rec, span, step=DROP_STEPS[0])
    out = readout.block_readout(conn, rec, span, DROP_STEPS, 1)
    assert out["rows"] == _rows(_spec(step).derive(xd, t, FS, _params(step)))
    gap = [r for r in out["rows"] if r["label"] == "Missing samples"]
    assert gap and gap[0]["value"].startswith("480 in 1 gap · first at 5:33:20"), gap


def test_the_first_block_reads_the_source_span(store):
    from server import readout
    conn, rec = store
    steps = NOISE_STEPS[1:]
    x, t = _source(rec)
    out = readout.block_readout(conn, rec, None, steps, 0)
    assert out["rows"] == _rows(_spec(steps[0]).derive(x, t, FS, _params(steps[0])))
    assert out["input"] == []


def test_a_block_without_a_readout_runs_nothing(store, monkeypatch):
    from server import readout
    conn, rec = store
    out = readout.block_readout(conn, rec, None, DROP_STEPS, 0)     # Baseline removal declares no derive
    assert out["has_derive"] is False and out["rows"] == [] and out["input"] == []


# ── what the readout will not do ────────────────────────────────────────────

def test_a_slow_stage_the_cache_does_not_hold_is_not_run(store, monkeypatch):
    from server import readout
    conn, rec = store
    mp = get_adapter("detection.matrix_profile")
    monkeypatch.setattr(mp, "run", _never)
    monkeypatch.setattr(mp, "estimate", lambda *a, **k: 3600.0)
    out = readout.block_readout(conn, rec, None, MP_STEPS, 2)
    assert out["rows"] == [] and out["skipped"], out
    assert "02 Matrix profile" in out["skipped"] and "run the chain once" in out["skipped"], out["skipped"]


def test_a_stage_whose_time_is_unknown_is_not_run(store, monkeypatch):
    from server import readout
    conn, rec = store
    mp = get_adapter("detection.matrix_profile")
    monkeypatch.setattr(mp, "run", _never)
    monkeypatch.setattr(mp, "estimate", lambda *a, **k: None)      # uncalibrated on this machine
    out = readout.block_readout(conn, rec, None, MP_STEPS, 2)
    assert out["rows"] == [] and "02 Matrix profile" in out["skipped"] and "unknown" in out["skipped"], out


def test_a_stage_the_cache_holds_is_read_from_it_not_rerun(store, monkeypatch, tmp_path):
    """After a run the slow stage is in the step cache: the readout reads it there, under the run's own key."""
    from server import chain, readout
    from Working.database.runs import insert_step_artifact
    from Working.execution import _recipe_prefix_hash
    from Working.types import Scores
    conn, rec = store
    mp = get_adapter("detection.matrix_profile")
    monkeypatch.setattr(mp, "run", _never)
    monkeypatch.setattr(mp, "estimate", lambda *a, **k: 3600.0)
    profile = np.r_[np.linspace(1.0, 2.0, N - 299), np.full(299, np.nan)]     # m = 300: the NaN tail + 1
    cached = tmp_path / "step_cache" / "1"
    Scores(values=profile, fs=FS).to_path(str(cached))
    recipe = chain.build_recipe(rec["id"], None, MP_STEPS)                    # the recipe POST /api/runs builds
    insert_step_artifact(conn, _recipe_prefix_hash(recipe, 1), 1, str(cached))
    out = readout.block_readout(conn, rec, None, MP_STEPS, 2)
    assert out["skipped"] is None
    assert out["rows"][0] == {"label": "Window m", "value": "300 samples · 300 s", "severity": ""}
    assert [(s["index"], s["from"]) for s in out["input"]] == [(0, "run"), (1, "cache")]


def test_a_stage_before_the_block_that_refuses_the_span_names_itself(store):
    """A linear detrend refuses a span with gaps; the run would fail there too, so the readout says where."""
    from server import readout
    conn, rec = store
    linear = [{"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "linear"}}, DROP_STEPS[1]]
    with pytest.raises(readout.ReadoutRefused, match="01"):
        readout.block_readout(conn, rec, None, linear, 1)


def test_the_readout_writes_nothing(store, monkeypatch, tmp_path):
    import Working.config as cfg
    from server import readout
    conn, rec = store
    monkeypatch.setattr(cfg, "STEP_CACHE_ROOT", str(tmp_path / "step_cache_written"))
    monkeypatch.setattr(cfg, "STEP_CACHE_WRITE_THRESHOLD_S", 0.0)        # what a sandbox bridge sets
    before = _table_counts(conn)
    for steps, index in ((DROP_STEPS, 1), (DROP_STEPS, 2), (NOISE_STEPS, 1)):
        readout.block_readout(conn, rec, None, steps, index)
    assert _table_counts(conn) == before
    assert not os.path.exists(tmp_path / "step_cache_written")


# ── the route ───────────────────────────────────────────────────────────────

@pytest.fixture
def bridge(tmp_path):
    # skipped here, not at module level: a module-level skip would take the readout tests above with it
    pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv; run this file with that interpreter")
    pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")
    from fastapi.testclient import TestClient
    from server.app import create_app
    from server.runtime import HELD_OUT_FILE, Runtime
    from Working.database.schema import init_db
    npy = tmp_path / "CH0.npy"
    np.save(npy, _trace())
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    conn = init_db(str(db_dir / "annotations.sqlite"))
    for name in ("readout.mat", HELD_OUT_FILE):
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
                     "VALUES (?, 0, ?, ?, 0, ?, 'V')", (name, FS, N, str(npy)))
    conn.commit()
    rid, held = (conn.execute("SELECT id FROM recordings WHERE source_file = ?", (n,)).fetchone()[0]
                 for n in ("readout.mat", HELD_OUT_FILE))
    conn.close()
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261014-readout", db_source=str(db_dir / "annotations.sqlite"),
                 runtime_root=str(tmp_path / "runtime"), client_dist=str(dist))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as client:
            yield client, rid, held
    finally:
        rt.restore()


def _post(client, rid, **body):
    return client.post("/api/blocks/derive", json={"recording_id": rid, "span": [0, N], **body})


def test_the_route_serves_a_blocks_readout_on_its_input(bridge):
    client, rid, _ = bridge
    r = _post(client, rid, steps=DROP_STEPS, index=2)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["block"] == "detection.drop_detection" and body["has_derive"] is True and body["skipped"] is None
    letters = [row for row in body["rows"] if row["label"] == "Letters"]
    assert letters and letters[0]["severity"] == "" and letters[0]["value"].endswith("fast falls"), body["rows"]
    gap = [row for row in body["rows"] if row["label"] == "Missing samples"]
    assert gap and gap[0]["severity"] == "warn"
    assert [(s["index"], s["from"]) for s in body["input"]] == [(0, "run"), (1, "run")]


def test_the_route_refuses_what_a_run_would_refuse(bridge):
    client, rid, held = bridge
    assert _post(client, rid, steps=DROP_STEPS, index=3).status_code == 422          # there is no stage 04
    loose = [DROP_STEPS[0], dict(DROP_STEPS[1], params={**DROP_STEPS[1]["params"], "slope_sigma": 0.1}), DROP_STEPS[2]]
    r = _post(client, rid, steps=loose, index=2)                                      # slope_sigma's minimum is 0.5
    assert r.status_code == 422 and "02" in r.json()["detail"], r.text
    linear = [{"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "linear"}}, DROP_STEPS[1]]
    r = _post(client, rid, steps=linear, index=1)                                     # a linear fit refuses the gaps
    assert r.status_code == 422 and "01" in r.json()["detail"], r.text
    assert _post(client, rid, steps=[{"stage": "detection", "algorithm": "no_such_block"}], index=0).status_code == 404
    assert _post(client, held, steps=DROP_STEPS, index=1).status_code == 423
