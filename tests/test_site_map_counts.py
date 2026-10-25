"""
test_site_map_counts.py
=======================
site-map (2026-10-20), item 1, the core half: Discovery › Map's levels 2 and 1 were computed on every read, and on a
copy of the real database level 2 took 3.1 s (cold) / 1.8 s (warm) — 1.25 s of it in `_starts`, which fetched every
counted detection row into Python to histogram it, 896 times per read (56 rows x 16 channels).

Now a cell's count comes from `detection_map._counts`: an indexed ``COUNT(*)`` per (owned range x cell) where a range
spans few cells — every level-3 and level-2 cell — and the old fetch-and-histogram only where a range spans many
level-1 bins. Pinned here:

* `_counts` equals the histogram of `_starts` (the old answer) for every row and channel, at 1, 2, 4 and 8 slices
  and at level-1 bin widths, including runs whose detections are stored span-relative (legacy rows);
* `channel_map` at 1-8 slices fetches no detection row (only counts);
* `compute(db_path, exclude, view, ...)` returns ``(fingerprint, payload)`` for levels 2 and 1 — what the bridge's
  cache keeps — equal to `channel_map` / `timeline_map` and fingerprinted like the overview (tq-mapcache: the view is
  passed as a function; `compute_level`'s level string and args dict are gone).

Pure core, conda interpreter.
"""
import os
import sqlite3
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(PROJECT_ROOT, "tests")
for p in (PROJECT_ROOT, TESTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import perf_fixture  # noqa: E402
from Working.discovery import detection_map as DM  # noqa: E402

SMALL = dict(n_channels=3, hours=24.0, n_druns=4, n_detections=6_000, n_annotations=200, n_templates=3,
             queue_size=50, n_adjudications=10, n_reviewed=20, write_npy=False)


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("sitemap")
    info = perf_fixture.build(str(tmp / "map.sqlite"), **SMALL)
    c = sqlite3.connect(info["db"])
    try:
        # legacy span-relative rows: a run whose span starts late, its detections stored from 0 of the span
        rid = c.execute("SELECT MIN(id) FROM runs WHERE surrogate_of_run_id IS NULL").fetchone()[0]
        c.execute("UPDATE runs SET span_start = 20000, span_end = 60000 WHERE id = ?", (rid,))
        c.execute("UPDATE detections SET start_idx = start_idx % 30000, end_idx = (start_idx % 30000) + 5 "
                  "WHERE run_id = ? AND id % 2 = 0", (rid,))
        # a partial run (a section) on another row
        rid2 = c.execute("SELECT MAX(id) FROM runs WHERE surrogate_of_run_id IS NULL").fetchone()[0]
        c.execute("UPDATE runs SET span_start = 7000, span_end = 50000 WHERE id = ?", (rid2,))
        c.commit()
    finally:
        c.close()
    return info


def _conn(path):
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    return c


def _edges_sets(n):
    out = [[int(round(n * i / k)) for i in range(k + 1)] for k in DM.CHUNK_OPTIONS]
    for bin_s in (3600, 3 * 3600, 6 * 3600):
        nb = int(np.ceil(n / bin_s))
        e = [min(n, i * bin_s) for i in range(nb + 1)]
        e[-1] = n
        out.append(e)
    return out


def test_counts_equal_the_histogram_of_the_fetched_starts(db):
    c = _conn(db["db"])
    try:
        rows, by_row = DM._gather(c, ())
        checked = 0
        for row in rows:
            for rec_id, held in by_row.get(row["key"], {}).items():
                run_rows = list(held.values())
                claimed = DM._resolve(run_rows)
                n = int(c.execute("SELECT n_samples FROM recordings WHERE id = ?", (rec_id,)).fetchone()[0])
                starts = DM._starts(c, claimed, run_rows)
                for edges in _edges_sets(n):
                    want = np.histogram(starts, bins=np.asarray(edges, dtype=float))[0] if len(starts) \
                        else np.zeros(len(edges) - 1, dtype=int)
                    got = DM._counts(c, claimed, run_rows, edges)
                    assert list(map(int, got)) == list(map(int, want)), (row["key"], rec_id, len(edges) - 1)
                    checked += 1
        assert checked > 20
    finally:
        c.close()


def test_level_two_counts_without_fetching_a_detection_row(db):
    c = _conn(db["db"])
    seen = []
    c.set_trace_callback(seen.append)
    try:
        for k in DM.CHUNK_OPTIONS:
            DM.channel_map(c, perf_fixture.SOURCE_FILE, chunks=k)
    finally:
        c.set_trace_callback(None)
        c.close()
    fetches = [s for s in seen if s.lstrip().upper().startswith("SELECT START_IDX FROM DETECTIONS")]
    assert not fetches, f"{len(fetches)} detection fetches, e.g. {fetches[:1]}"


def test_compute_returns_a_levels_fingerprint_and_payload(db):
    c = _conn(db["db"])
    try:
        want2 = DM.channel_map(c, perf_fixture.SOURCE_FILE, chunks=4)
        ch = want2["channels"][0]["name"]
        want1 = DM.timeline_map(c, perf_fixture.SOURCE_FILE, ch, bin_h=3.0)
        want_fp = DM.overview_fingerprint(c, ())
    finally:
        c.close()
    fp2, got2 = DM.compute(db["db"], (), DM.channel_map, perf_fixture.SOURCE_FILE, chunks=4)
    fp1, got1 = DM.compute(db["db"], (), DM.timeline_map, perf_fixture.SOURCE_FILE, channel=ch, bin_h=3.0)
    assert got2 == want2 and got1 == want1
    assert fp2 == fp1 == want_fp

