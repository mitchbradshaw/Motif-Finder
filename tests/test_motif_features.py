"""
test_motif_features.py
========================
`motif_features` (fixup-d, seam 5; Q-I1 / Q-I4 / Q14): per-event features are
stored ON THE MOTIF, keyed by content hash, recomputable from the snippet and
never authoritative. Cross-event comparisons are never stored.

What these tests hold the table to:

* `init_db()` creates it, additively and idempotently;
* the features for a Library entry are measured on the SAME samples its content
  hash was taken over — the store's `detrended_mv` snippet (the importer's
  stated waveform) — so a feature row keyed by hash H describes H's waveform;
* the detector's own `drop_depth_mv` is carried where a detector produced one
  (the Library import dropped it; Q-X2.5's floor filter needs it);
* rewriting replaces rather than duplicates, and a backfill that finds the
  features present computes nothing;
* the Library rows themselves are untouched.

Runnable standalone:  python tests/test_motif_features.py
"""

import csv
import datetime
import os
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.library import features as F  # noqa: E402
from Working.library.identity import content_hash  # noqa: E402

SEED_REL = "DATA/library_seed/drop_motifs5/motifs"
SEED = os.path.join(PROJECT_ROOT, *SEED_REL.split("/"))
EVENT = "id001_r1_1213252"

needs_seed = pytest.mark.skipif(not os.path.isfile(os.path.join(SEED, "events.csv")),
                                reason="the tracked seed store is not on this machine")


def _seed_row(event_id):
    with open(os.path.join(SEED, "events.csv"), newline="", encoding="utf-8") as f:
        return next(r for r in csv.DictReader(f) if r["event_id"] == event_id)


@pytest.fixture
def conn():
    d = tempfile.mkdtemp(prefix="motif_feat_")
    c = init_db(os.path.join(d, "t.sqlite"))
    yield c
    c.close()


def test_init_db_creates_the_table_and_is_idempotent():
    d = tempfile.mkdtemp(prefix="motif_feat_")
    path = os.path.join(d, "t.sqlite")
    init_db(path).close()
    c = init_db(path)
    cols = {r[1] for r in c.execute("PRAGMA table_info(motif_features)")}
    assert {"content_hash", "fs", "source", "feature", "value", "rule_version", "computed_at"} <= cols
    c.close()


@needs_seed
def test_features_are_measured_on_the_waveform_the_hash_was_taken_over():
    rows = F.features_from_event_store(SEED, event_ids=[EVENT])
    assert len(rows) == 1
    r = rows[0]
    from Working.Detection.drop_motifs import store as S
    snip = S.load_snippets(SEED)[EVENT]["detrended_mv"]
    assert r["content_hash"] == content_hash(snip)
    assert r["fs"] == 1.0
    m = r["measures"]
    for k in ("event_amplitude_mv", "event_width_s", "fwhm_s", "recovery_time_s", "max_slope_mv_s", "polarity"):
        assert k in m
    assert m["polarity"] == -1


@needs_seed
def test_the_detectors_own_depth_is_carried():
    r = F.features_from_event_store(SEED, event_ids=[EVENT])[0]
    seed = _seed_row(EVENT)
    assert r["detector"]["drop_depth_mv"] == pytest.approx(float(seed["drop_depth_mv"]))
    assert r["detector"]["fall_duration_s"] == pytest.approx(float(seed["fall_duration_s"]))
    # max_slope_raw is V/s with fs applied once: mV/s = raw * 1000, no second fs factor
    assert r["detector"]["max_slope_mv_s"] == pytest.approx(float(seed["max_slope_raw"]) * 1000.0)


def test_write_and_read_back_by_hash_and_rewrite_replaces(conn):
    row = {"content_hash": "a" * 32, "fs": 1.0, "measures": {"event_amplitude_mv": 3.0, "fwhm_s": 4.0},
           "detector": {"drop_depth_mv": 2.5}}
    assert F.write_features(conn, [row]) == 3
    got = F.read_features(conn, ["a" * 32])
    assert got["a" * 32]["event_amplitude_mv"] == 3.0
    assert got["a" * 32]["detector_drop_depth_mv"] == 2.5
    row["measures"]["event_amplitude_mv"] = 7.0
    F.write_features(conn, [row])
    assert F.read_features(conn, ["a" * 32])["a" * 32]["event_amplitude_mv"] == 7.0
    assert conn.execute("SELECT COUNT(*) FROM motif_features").fetchone()[0] == 3


def test_nan_is_stored_as_null_and_read_back_as_nan(conn):
    F.write_features(conn, [{"content_hash": "b" * 32, "fs": 10.0, "measures": {"recovery_time_s": float("nan")},
                             "detector": {}}])
    v = F.read_features(conn, ["b" * 32])["b" * 32]["recovery_time_s"]
    assert v is None or np.isnan(v)


def _entry(conn, *, source_kind, source_store, source_ref, digest):
    rid = q.insert_recording(conn, "M2_aug_concat_fs1.mat", 0, 1.0, 10, 0, "nowhere.npy")
    now = datetime.datetime.now().isoformat()
    cur = conn.execute(
        "INSERT INTO motif_entry (recording_id, start_idx, end_idx, content_hash, source_kind, source_store, "
        "source_ref, fs, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 1.0, ?)",
        (rid, 1, 5 + len(source_ref), digest, source_kind, source_store, source_ref, now))
    conn.commit()
    return cur.lastrowid


@needs_seed
def test_the_backfill_fills_a_library_entry_and_leaves_the_row_alone(conn):
    from Working.Detection.drop_motifs import store as S
    digest = content_hash(S.load_snippets(SEED)[EVENT]["detrended_mv"])
    eid = _entry(conn, source_kind="event_store", source_store=SEED_REL, source_ref=EVENT, digest=digest)
    _entry(conn, source_kind="annotation", source_store=None, source_ref="ann-1", digest="c" * 32)
    before = conn.execute("SELECT * FROM motif_entry WHERE id = ?", (eid,)).fetchone()
    report = F.backfill_library(conn, repo_root=PROJECT_ROOT)
    assert report["measured"] == 1
    assert report["skipped"].get("no_store_snippet") == 1
    got = F.read_features(conn, [digest])[digest]
    assert got["detector_drop_depth_mv"] == pytest.approx(float(_seed_row(EVENT)["drop_depth_mv"]))
    assert "event_amplitude_mv" in got
    assert tuple(conn.execute("SELECT * FROM motif_entry WHERE id = ?", (eid,)).fetchone()) == tuple(before)
    again = F.backfill_library(conn, repo_root=PROJECT_ROOT)
    assert again["measured"] == 0 and again["already_present"] == 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
