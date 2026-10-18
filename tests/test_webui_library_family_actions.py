"""
test_webui_library_family_actions.py
====================================
library-family-actions (2026-10-19): the rose reference LINE. Every rose draws a
line at the median steepest slope over the human-accepted Library motifs of the
same unit (verdict interesting or seed, by the one resolver), labelled with its
value and n. The bridge computes it live — not the stored 45° of Settings ›
Analysis defaults, which only moves on an explicit act — and caches it by the
adjudication fingerprint, so a new verdict moves it on the next read.

Fixture: `test_webui_library.py`'s seeded library with steepest slopes written
for four members (hash0 -1, hash1 -2, hash2 -3, hash3 -4 mV/s). Nobody has
judged any of them, so the line starts absent (n 0).

Runs under webui/.venv (FastAPI); skipped elsewhere, like its siblings.
"""

import datetime
import os
import sqlite3
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui"), os.path.dirname(os.path.abspath(__file__))):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv; run this file with that interpreter")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from test_webui_library import _bridge, _ok  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.library import features as F  # noqa: E402

SLOPES = {"hash0": -1.0, "hash1": -2.0, "hash2": -3.0, "hash3": -4.0}


@pytest.fixture
def lib(tmp_path):
    rt, app, held, gid, member_ids = _bridge(tmp_path, "sandbox")
    try:
        with TestClient(app) as client:
            _ok(client.get("/api/library/counts"))             # schema ensured
            conn = sqlite3.connect(rt.db_path)
            F.write_features(conn, [{"content_hash": h, "fs": 1.0, "measures": {"max_slope_mv_s": s},
                                     "detector": {"drop_depth_mv": 0.5, "fall_duration_s": 20.0, "is_pure": 1}}
                                    for h, s in SLOPES.items()])
            conn.close()
            yield client, rt
    finally:
        rt.restore()


def _accept(rt, content_hash, label="interesting"):
    """A person's verdict on the window holding one member (the resolver's reviewed-windows rule)."""
    conn = sqlite3.connect(rt.db_path)
    try:
        rec, a, b = conn.execute("SELECT recording_id, start_idx, end_idx FROM motif_member WHERE content_hash = ?",
                                 (content_hash,)).fetchone()
        q.insert_annotation(conn, rec, max(0, a - 5), b + 5, label, q.SOURCE_IMPORTED_10MIN,
                            created_at=datetime.datetime.now().isoformat())
        conn.commit()
    finally:
        conn.close()


def test_a_unit_with_no_accepted_motifs_has_n_0_and_no_line(lib):
    client, _ = lib
    r = _ok(client.get("/api/library/rose-reference?unit=motifs"))
    assert r["n"] == 0
    assert r["median_slope"] is None, "no accepted motif: no line, never a fallback population"
    assert r["computed_from"] and "accepted" in r["computed_from"]
    assert r["unit"] == "motifs"


def test_it_is_the_median_over_accepted_motifs_and_moves_after_a_verdict(lib):
    client, rt = lib
    assert _ok(client.get("/api/library/rose-reference?unit=motifs"))["n"] == 0   # cached at n 0 ...
    _accept(rt, "hash1")
    one = _ok(client.get("/api/library/rose-reference?unit=motifs"))              # ... and the verdict moves it
    assert one["n"] == 1 and one["median_slope"] == pytest.approx(2.0)
    _accept(rt, "hash3", "seed")
    two = _ok(client.get("/api/library/rose-reference?unit=motifs"))
    assert two["n"] == 2 and two["median_slope"] == pytest.approx(3.0)            # median of |-2|, |-4|
    assert "n = 2" in two["computed_from"]


def test_a_rejected_verdict_does_not_count(lib):
    client, rt = lib
    _accept(rt, "hash0", "artifact")
    r = _ok(client.get("/api/library/rose-reference?unit=motifs"))
    assert r["n"] == 0 and r["median_slope"] is None


def test_an_unknown_unit_is_refused_in_words(lib):
    client, _ = lib
    r = client.get("/api/library/rose-reference?unit=sequences")
    assert r.status_code == 400
    assert "motifs" in r.text


def test_the_stored_45_degree_read_is_unchanged_without_a_unit(lib):
    client, _ = lib
    r = _ok(client.get("/api/library/rose-reference"))
    assert {"value_mv_s", "population", "stored", "text"} <= set(r)
    assert "median_slope" not in r


def test_a_verdict_changed_in_place_moves_the_line(lib):
    """Review re-judges by UPDATE in place (family_queue / verdicts / artifact_queue: `UPDATE annotations SET
    verdict = ?`), so the row count and max id do not move. The line must still move (critic round)."""
    client, rt = lib
    _accept(rt, "hash1")
    assert _ok(client.get("/api/library/rose-reference?unit=motifs"))["n"] == 1
    conn = sqlite3.connect(rt.db_path)
    try:
        conn.execute("UPDATE annotations SET verdict = 'artifact'")
        conn.commit()
    finally:
        conn.close()
    r = _ok(client.get("/api/library/rose-reference?unit=motifs"))
    assert r["n"] == 0 and r["median_slope"] is None, "a verdict changed in place left the cached line stale"


def test_the_line_is_cached_until_the_adjudications_move(lib, monkeypatch):
    client, rt = lib
    import server.library as L
    calls = []
    real = L.rose_mod.compute
    monkeypatch.setattr(L.rose_mod, "compute", lambda *a, **k: calls.append(1) or real(*a, **k))
    L._ROSE_LINE_CACHE.clear()
    for _ in range(3):
        _ok(client.get("/api/library/rose-reference?unit=motifs"))
    assert len(calls) == 1, "three reads with nothing judged in between must compute once"
    _accept(rt, "hash2")
    assert _ok(client.get("/api/library/rose-reference?unit=motifs"))["median_slope"] == pytest.approx(3.0)
    assert len(calls) == 2


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
