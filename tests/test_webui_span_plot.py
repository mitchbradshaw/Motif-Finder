"""
test_webui_span_plot.py
=======================
span-plot (docs/prompts/changes/explore-span-plot.md) — the bridge half.

The pile at t = 0. Explore › Signal read the whole channel's spans once (``GET /spans?t0=0&t1=<duration>``)
and, since ``getSignalDemo`` became the live read, treated that payload as the channel's detection list: the
overview's density ribbon and the second band push were built from it. ``corpus.spans`` caps a read at 5 000
rows sorted by start, so on a channel with more detections than that the copy held only the FIRST 5 000 —
every one of them near the start of the signal. These tests pin the bridge side of that: a capped read says so
and which part of the window it covers, the ribbon counts every detection, and ``_absolute`` is the one rule in
``Working.discovery.spans`` (not a second copy). Run with the webui venv interpreter.
"""

import logging
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi")

from Working.database import queries as q  # noqa: E402
from Working.database import runs as R  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery import spans as S  # noqa: E402
from server import corpus  # noqa: E402

FS = 1.0
N = 100_000


def _db(tmp_path):
    conn = init_db(str(tmp_path / "span_plot.sqlite"))
    rec = q.insert_recording(conn, "F.mat", 0, FS, N, 0, str(tmp_path / "c0.npy"))
    return conn, rec


def _run(conn, rec, span_start, span_end, started_at=None, algorithm="threshold"):
    cfg, _ = R.get_or_create_config(conn, {"recording_id": rec, "span": [span_start, span_end], "salt": started_at or "now",
                                           "steps": [{"stage": "detection", "algorithm": algorithm, "params": {}}]})
    return R.insert_run(conn, cfg, rec, span_start, span_end, status="completed", started_at=started_at)


def test_absolute_is_the_one_rule():
    """One rule, imported — corpus kept a second copy of `absolute_bounds` that its docstring said delegated."""
    assert corpus._absolute is S.absolute_bounds


def test_every_detection_lies_in_its_span_at_the_right_second(tmp_path):
    """(a) a legacy relative row in a non-ambiguous spanned run, (b) a whole-channel run, and a post-fix absolute
    row: after the read every detection lies inside its run's span, at its absolute second."""
    conn, rec = _db(tmp_path)
    legacy = _run(conn, rec, 50_000, 52_000, "2026-08-01T00:00:00+00:00")
    conn.execute("INSERT INTO detections (run_id, start_idx, end_idx) VALUES (?, 500, 600)", (legacy,))
    whole = _run(conn, rec, 0, N)
    R.insert_detection(conn, whole, 70_000, 70_100)
    post = _run(conn, rec, 80_000, 82_000)
    R.insert_detection(conn, post, 81_000, 81_050)
    conn.commit()
    out = corpus.spans(conn, rec, 0, N / FS, FS)
    conn.close()
    got = {d["run_id"]: (d["start_s"], d["end_s"]) for d in out["detections"]}
    assert got[legacy] == (50_500.0, 50_600.0)
    assert got[whole] == (70_000.0, 70_100.0)
    assert got[post] == (81_000.0, 81_050.0)
    for rid, (span0, span1) in ((legacy, (50_000, 52_000)), (whole, (0, N)), (post, (80_000, 82_000))):
        a, b = got[rid]
        assert span0 <= a < b <= span1


def test_an_ambiguous_legacy_run_is_warned_about_by_the_read(tmp_path, caplog):
    """(a) the run the database cannot resolve: the read names it once (detector and date) and draws it by the
    existing heuristic — the migration is proposed in the report, not guessed here."""
    conn, rec = _db(tmp_path)
    amb = _run(conn, rec, 1_000, 3_000, "2026-08-01T00:00:00+00:00", algorithm="cwt_ridges")
    conn.execute("INSERT INTO detections (run_id, start_idx, end_idx) VALUES (?, 1500, 1600)", (amb,))
    conn.commit()
    S._AMBIGUOUS_REPORTED.discard(amb)
    with caplog.at_level(logging.WARNING):
        corpus.spans(conn, rec, 0, N / FS, FS)
        corpus.spans(conn, rec, 0, N / FS, FS)
    conn.close()
    hits = [r for r in caplog.records if ("run %d" % amb) in r.getMessage()]
    assert len(hits) == 1
    assert "cwt_ridges" in hits[0].getMessage()
    S._AMBIGUOUS_REPORTED.discard(amb)


def test_a_capped_read_says_where_its_detections_stop(tmp_path):
    """THE PILE. 12 000 detections spread evenly over the channel; a whole-channel read returns the first 5 000 by
    start — all inside the first ~42 % of the channel. The payload must say it was capped AND up to which second
    its detections are complete, so no reader can mistake the prefix for the channel."""
    conn, rec = _db(tmp_path)
    run = _run(conn, rec, 0, N)
    starts = np.linspace(0, N - 10, 12_000).astype(int)
    conn.executemany("INSERT INTO detections (run_id, start_idx, end_idx) VALUES (?, ?, ?)",
                     [(run, int(s), int(s) + 5) for s in starts])
    conn.commit()
    out = corpus.spans(conn, rec, 0, N / FS, FS)
    rib = corpus.ribbons(conn, rec, FS, N, buckets=10)
    conn.close()
    assert out["detections_capped"] is True and len(out["detections"]) == 5_000
    last = out["detections"][-1]["start_s"]
    assert last < 0.45 * N, "the capped prefix is the start of the channel — the pile"
    assert out["detections_complete_to_s"] == pytest.approx(last), "the read says where its detections stop"
    # the overview's ribbon is the full count, spread over the whole channel
    assert sum(rib["detection_density"]) == 12_000
    assert min(rib["detection_density"]) > 0.08 * 12_000


def test_an_uncapped_read_is_complete_to_its_window(tmp_path):
    conn, rec = _db(tmp_path)
    run = _run(conn, rec, 0, N)
    R.insert_detection(conn, run, 1_000, 1_010)
    out = corpus.spans(conn, rec, 0, N / FS, FS)
    conn.close()
    assert out["detections_capped"] is False
    assert out["detections_complete_to_s"] == N / FS


def test_the_annotation_verdict_is_served_uncollapsed(tmp_path):
    """The bands read the verdict: interesting and not-interesting must arrive as themselves, not as one
    'annotated' kind."""
    conn, rec = _db(tmp_path)
    for i, v in enumerate(("interesting", "not_interesting", "unsure", "artifact", "seed")):
        q.insert_annotation(conn, rec, 1_000 * (i + 1), 1_000 * (i + 1) + 50, v, "manual_ui")
    out = corpus.spans(conn, rec, 0, N / FS, FS)
    conn.close()
    assert [a["verdict"] for a in out["annotations"]] == ["interesting", "not_interesting", "unsure", "artifact", "seed"]


# ---------------------------------------------------------------- critic round: the span view's own read
# The span view draws its bands from the VIEWPORT's read (useViewport -> GET /spans?t0&t1), not the whole-channel
# copy. That read is capped the same way: a view holding more than 5 000 detections (any view wider than ~12 h on
# a channel with 300k detections) got the first 5 000 by start, so every band piled into the left of the view —
# the researcher's "all detections cluster into the start of the signal". `spread` asks for a capped read thinned
# evenly across the window instead, which is what a plot needs; the default (a prefix) is unchanged for the
# readers that walk rows in order.

def _busy(tmp_path, n_det=12_000):
    conn, rec = _db(tmp_path)
    run = _run(conn, rec, 0, N)
    starts = np.linspace(0, N - 10, n_det).astype(int)
    conn.executemany("INSERT INTO detections (run_id, start_idx, end_idx) VALUES (?, ?, ?)",
                     [(run, int(s), int(s) + 5) for s in starts])
    conn.commit()
    return conn, rec


def test_a_spread_read_covers_its_whole_window(tmp_path):
    conn, rec = _busy(tmp_path)
    out = corpus.spans(conn, rec, 0, N / FS, FS, spread=True)
    conn.close()
    dets = out["detections"]
    assert out["detections_capped"] is True and len(dets) == 5_000
    assert out["detections_spread"] is True and out["detections_total"] == 12_000
    starts = np.array([d["start_s"] for d in dets])
    assert np.all(np.diff(starts) >= 0), "still in time order"
    assert starts[0] < 0.01 * N and starts[-1] > 0.99 * N, "from the window's start to its end"
    hist, _ = np.histogram(starts, bins=10, range=(0, N))
    assert hist.min() > 0.08 * 5_000, f"thinned evenly, not piled: {hist.tolist()}"
    assert out["detections_complete_to_s"] == N / FS or out["detections_complete_to_s"] is None


def test_a_spread_read_inside_a_zoomed_window(tmp_path):
    """The view at hour ~20 of a 27.8 h channel: the bands of a spread read stay inside the view and fill it."""
    conn, rec = _busy(tmp_path, n_det=40_000)
    t0, t1 = 60_000.0, 90_000.0
    out = corpus.spans(conn, rec, t0, t1, FS, spread=True)
    conn.close()
    starts = np.array([d["start_s"] for d in out["detections"]])
    assert out["detections_capped"] is True and len(starts) == 5_000
    assert starts.min() >= t0 - 10 and starts.max() < t1
    hist, _ = np.histogram(starts, bins=10, range=(t0, t1))
    assert hist.min() > 0.08 * 5_000, hist.tolist()


def test_an_uncapped_spread_read_is_the_plain_read(tmp_path):
    conn, rec = _busy(tmp_path, n_det=300)
    a = corpus.spans(conn, rec, 0, N / FS, FS, spread=True)
    b = corpus.spans(conn, rec, 0, N / FS, FS)
    conn.close()
    assert a["detections"] == b["detections"] and a["detections_spread"] is False
    assert a["detections_total"] == 300


def test_the_spans_route_takes_spread(tmp_path):
    pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")
    from fastapi.testclient import TestClient
    from server.app import create_app
    from server.runtime import Runtime
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    npy = tmp_path / "c0.npy"
    np.save(npy, np.zeros(N, dtype=np.float32))
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
                 "VALUES ('F.mat', 0, 1.0, ?, 0, ?, 'V')", (N, str(npy)))
    rec = conn.execute("SELECT id FROM recordings").fetchone()[0]
    run = _run(conn, rec, 0, N)
    starts = np.linspace(0, N - 10, 12_000).astype(int)
    conn.executemany("INSERT INTO detections (run_id, start_idx, end_idx) VALUES (?, ?, ?)",
                     [(run, int(s), int(s) + 5) for s in starts])
    conn.commit(); conn.close()
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261018-spanplot", db_source=str(db), runtime_root=str(tmp_path / "runtime"),
                 client_dist=str(dist))
    rt.setup()
    try:
        with TestClient(create_app(rt)) as c:
            plain = c.get(f"/api/channels/{rec}/spans?t0=0&t1={N}").json()
            spread = c.get(f"/api/channels/{rec}/spans?t0=0&t1={N}&spread=1").json()
    finally:
        rt.restore()
    assert plain["detections"][-1]["start_s"] < 0.45 * N, "the default read is still the prefix"
    assert spread["detections_spread"] is True and spread["detections"][-1]["start_s"] > 0.99 * N
