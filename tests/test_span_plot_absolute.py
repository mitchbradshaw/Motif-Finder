"""
test_span_plot_absolute.py
==========================
span-plot (docs/prompts/changes/explore-span-plot.md): "all detections cluster into the start of the signal".

The prompt named three suspects in the read path. Each is built here as a fixture and settled:

(a) a legacy span-relative row whose ``start_idx >= span_start`` — the run is *ambiguous*
    (``span_length > span_start``), so its relative rows can pass for absolute ones. The database cannot tell
    them apart by value; it CAN tell that the run is ambiguous and that it was written before the executor
    began adding the offset (2026-09-21). The rule stays the existing heuristic (it is not guessed at in the
    read path) and the run is named, once, in a warning — the prompt's "say so", with the one-time migration
    proposed in the report.
(b) a run whose ``span_start`` is NULL — the schema refuses it (``runs.span_start INTEGER NOT NULL``), and the
    rule reads a missing offset as a whole-channel run.
(c) a detector that decimates internally (``Working/Detection/cwt_ridges.py``) — its decimation is of the
    noise estimate only; the indices it returns are at the input rate.

None of the three is the pile. The bridge-side test of what is (a whole-channel span read capped at 5 000
rows, time-sorted, so the client's copy of it held only the channel's first detections) is in
``tests/test_webui_span_plot.py``. Conda interpreter; no FastAPI.
"""

import logging
import os
import sqlite3
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery import spans as S  # noqa: E402


def _db():
    path = os.path.join(tempfile.mkdtemp(prefix="span_plot_"), "a.sqlite")
    conn = init_db(path)
    rec = q.insert_recording(conn, "fixture.mat", 0, 1.0, 100_000, 0, "fixture_CH0.npy")
    return conn, rec


def _run(conn, rec, span_start, span_end, started_at):
    cfg = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES (?, ?, ?)",
                       ("c-%s-%s-%s" % (span_start, span_end, started_at), "{}", started_at)).lastrowid
    rid = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
                       "VALUES (?, ?, ?, ?, ?, 'completed')", (cfg, rec, span_start, span_end, started_at)).lastrowid
    conn.commit()
    return rid


# ------------------------------------------------------------------ (a) ----

def test_a_non_ambiguous_legacy_row_is_shifted_into_its_span():
    """Span [10 000, 12 000): a relative row at 500 belongs at 10 500, inside the span."""
    a, b = S.absolute_bounds(500, 600, 10_000)
    assert (a, b) == (10_500, 10_600)
    assert 10_000 <= a < b <= 12_000


def test_an_ambiguous_legacy_run_is_named_and_left_to_the_heuristic():
    """Span [1 000, 3 000) is 2 000 long, longer than its offset: a relative row at 1 500 (really 2 500) and an
    absolute row at 1 500 are the same number. The read path does not guess: the row stays where the heuristic
    puts it, and the run is reported as one the database cannot resolve — before the executor fix only."""
    assert S.absolute_bounds(1_500, 1_600, 1_000) == (1_500, 1_600)
    assert S.legacy_ambiguous(1_000, 3_000, "2026-08-01T00:00:00+00:00") is True
    # after the executor began adding the offset, an ambiguous-looking span is absolute by construction
    assert S.legacy_ambiguous(1_000, 3_000, "2026-10-01T00:00:00+00:00") is False
    # a span shorter than its offset cannot be ambiguous; a whole-channel run never is
    assert S.legacy_ambiguous(10_000, 12_000, "2026-08-01T00:00:00+00:00") is False
    assert S.legacy_ambiguous(0, 100_000, "2026-08-01T00:00:00+00:00") is False


def test_an_ambiguous_legacy_run_is_warned_about_once(caplog):
    S._AMBIGUOUS_REPORTED.discard(987654)
    with caplog.at_level(logging.WARNING, logger=S.__name__):
        for _ in range(3):
            S.warn_if_ambiguous(987654, 1_000, 3_000, "2026-08-01T00:00:00+00:00", algorithm="detection.threshold")
    hits = [r for r in caplog.records if "987654" in r.getMessage()]
    assert len(hits) == 1, "one warning per run per process, not one per read"
    msg = hits[0].getMessage()
    assert "detection.threshold" in msg and "2026-08-01" in msg, "the run is named by detector and date"
    S._AMBIGUOUS_REPORTED.discard(987654)


def test_ambiguous_legacy_runs_lists_them_by_detector_and_date():
    """What the report's migration proposal would act on: every pre-fix run whose rows the heuristic cannot
    place, with its detector (the recipe's last algorithm) and its start date."""
    conn, rec = _db()
    amb = _run(conn, rec, 1_000, 3_000, "2026-08-01T00:00:00+00:00")
    conn.execute("UPDATE configs SET config_json = ? WHERE id = (SELECT config_id FROM runs WHERE id = ?)",
                 ('{"steps": [{"stage": "detection", "algorithm": "threshold", "params": {}}]}', amb))
    conn.execute("INSERT INTO detections (run_id, start_idx, end_idx) VALUES (?, 1500, 1600)", (amb,))
    fine = _run(conn, rec, 10_000, 12_000, "2026-08-01T00:00:00+00:00")
    conn.execute("INSERT INTO detections (run_id, start_idx, end_idx) VALUES (?, 500, 600)", (fine,))
    later = _run(conn, rec, 1_000, 3_000, "2026-10-01T00:00:00+00:00")
    conn.execute("INSERT INTO detections (run_id, start_idx, end_idx) VALUES (?, 1500, 1600)", (later,))
    conn.commit()
    rows = S.ambiguous_legacy_runs(conn)
    conn.close()
    assert [r["run_id"] for r in rows] == [amb]
    assert rows[0]["detector"] == "threshold" and rows[0]["started_at"].startswith("2026-08-01")
    assert rows[0]["n"] == 1 and rows[0]["n_at_or_above_span_start"] == 1


# ------------------------------------------------------------------ (b) ----

def test_b_a_run_cannot_have_a_null_span_start():
    conn, rec = _db()
    cfg = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES ('n', '{}', 'x')").lastrowid
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
                     "VALUES (?, ?, NULL, 100, 'x', 'completed')", (cfg, rec))
    conn.close()


def test_b_a_missing_offset_reads_as_a_whole_channel_run():
    assert S.absolute_bounds(70_000, 70_100, None) == (70_000, 70_100)
    assert S.absolute_bounds(70_000, 70_100, 0) == (70_000, 70_100)


# ------------------------------------------------------------------ (c) ----

def test_c_cwt_ridges_returns_indices_at_the_input_rate():
    """The detector decimates its noise estimate, not its output: a bump at sample 3 000 of a 1 Hz span is found
    at sample ~3 000, not at 3 000 / k."""
    from Working.Detection.cwt_ridges import detect
    rng = np.random.default_rng(0)
    n = 6_000
    t = np.arange(n, dtype=float)
    x = 0.02 * rng.standard_normal(n) + 5.0 * np.exp(-0.5 * ((t - 3_000) / 40.0) ** 2)
    res = detect(x, 1.0, min_scale_s=10.0, max_scale_s=400.0, n_scales=16, polarity="spike", noise_window_s=2_000.0)
    peaks = [e["peak_idx"] for e in res.events]
    assert peaks, "the bump must be found"
    best = min(peaks, key=lambda p: abs(p - 3_000))
    assert abs(best - 3_000) <= 40, f"peak at {best}, expected ~3000 (a decimated index would sit near 3000/k)"
