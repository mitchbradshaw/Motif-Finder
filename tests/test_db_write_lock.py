"""
test_db_write_lock.py
=====================
fixup-dblock: the intermittent ``sqlite3.OperationalError: database is locked``
500 on Library › Family *Send suspected artifacts to Review*
(`POST /api/library/family/F-130/suspected-artifacts`), seen on at least three
smoke walks (AG Part 2 twice, AI once).

The walk's sequence: AD's first state clicks *Classify across channels* on a
family the database already holds a classification for, so the flag line it
waits for is already drawn and the walk moves on while the classification job
is still running; two states later it presses *Send suspected artifacts*,
whose `create_queue` INSERT needs the write lock. SQLite allows one writer at
a time, and the job held the write lock across its slow work: the first
DELETE of a channel opened an implicit transaction, and every pair's chance
test (`_judge`, K random times on the sibling) ran inside it until the
channel's COMMIT. When that took longer than the connection's 5 s busy
timeout, the POST failed.

Three things, each pinned here:

1. the classifier computes outside any write transaction — its writes for a
   channel are applied together, after that channel is judged;
2. `init_db` on an up-to-date database takes no write lock (every bridge
   `RunManager` / `JobManager` call opens through it; two of its backfills
   wrote unconditionally, so each call queued behind any writer and, when the
   writer held on, failed the same way);
3. every connection waits for a writer longer than SQLite's default: the
   busy timeout is `schema.BUSY_TIMEOUT_S`.

The route-level reproduction is `tests/test_webui_db_lock.py`.
"""

import os
import sqlite3
import sys
import threading
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pytest

from Working.database import queries as q
from Working.database import runs as R
from Working.database import schema as S
from Working.database.schema import get_connection, init_db
from Working.library import matching

PULSE_N = 60


def _pulse():
    u = np.linspace(0.0, 2.0 * np.pi, PULSE_N)
    return -np.sin(u) * np.hanning(PULSE_N)


def _channel(n, plants, seed, noise=0.01):
    x = np.random.default_rng(seed).standard_normal(n) * noise
    for at in plants:
        x[at:at + PULSE_N] += _pulse()
    return x


@pytest.fixture
def db(tmp_path):
    """A file database in WAL mode, as the real one is (`Runtime._setup_project`)."""
    path = str(tmp_path / "annotations.sqlite")
    conn = init_db(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()
    return path


def _can_write_now(path):
    """True when another connection can take the write lock without waiting."""
    other = sqlite3.connect(path, timeout=0, isolation_level=None)
    try:
        other.execute("BEGIN IMMEDIATE")
        other.execute("ROLLBACK")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        other.close()


def test_classifying_a_family_holds_no_write_lock_while_it_judges(db, tmp_path, monkeypatch):
    """Every pair's chance test runs with the write lock free, so a request
    that writes while a classification job is running never waits on it."""
    conn = init_db(db)
    # ch0 and ch1: the same pulse at the same instant, a member on each (a pair);
    # ch2: the pulse with no member there (a co-occurrence without a member)
    recs = []
    for ch in range(3):
        npy = str(tmp_path / f"CH{ch}.npy")
        np.save(npy, _channel(4000, [1000], seed=ch))
        rid = q.insert_recording(conn, "syn.mat", ch, 1.0, 4000, 0, npy)
        conn.execute("UPDATE recordings SET units = 'mV' WHERE id = ?", (rid,))
        recs.append(rid)
    entry = R.insert_motif_entry(conn, recs[0], 990, 1070)
    a = R.get_or_create_motif_member(conn, entry, recs[0], 990, 1070)
    b = R.get_or_create_motif_member(conn, entry, recs[1], 990, 1070)
    conn.commit()

    seen = []
    real_judge = matching._judge

    def watching_judge(*args, **kwargs):
        seen.append(_can_write_now(db))
        return real_judge(*args, **kwargs)

    monkeypatch.setattr(matching, "_judge", watching_judge)
    try:
        out = matching.classify_family_across_channels(conn, [a, b])
    finally:
        conn.close()

    assert len(seen) >= 2, "the pair and the member-less sibling were both judged"
    assert all(seen), (f"{seen.count(False)} of {len(seen)} chance tests ran while this connection held the write "
                       "lock: a concurrent write would wait on them, and fail after the busy timeout")
    # the writes still land, and land whole
    assert out["pairs"] and out["pairs"][0]["edge_ids"]
    check = sqlite3.connect(db)
    try:
        assert check.execute("SELECT COUNT(*) FROM motif_edge WHERE classification_bin IS NOT NULL").fetchone()[0] >= 1
        assert check.execute("SELECT COUNT(*) FROM motif_member_cooccurrence").fetchone()[0] >= 1
    finally:
        check.close()


def test_init_db_on_an_up_to_date_database_takes_no_write_lock(db):
    """With another connection holding the write lock, `init_db` on a database
    it has already migrated returns at once instead of queueing for the lock."""
    holder = sqlite3.connect(db, isolation_level=None)
    holder.execute("BEGIN IMMEDIATE")
    result = {}

    def run():
        try:
            init_db(db).close()
            result["ok"] = True
        except Exception as e:          # noqa: BLE001 - reported below
            result["error"] = repr(e)

    t = threading.Thread(target=run, daemon=True)
    t0 = time.time()
    t.start()
    t.join(3.0)
    waited = time.time() - t0
    holder.execute("ROLLBACK")
    holder.close()
    t.join(60)
    assert result.get("ok") and waited < 3.0, (
        f"init_db waited {waited:.1f} s for the write lock on a database with nothing to migrate "
        f"({result.get('error', 'it was still waiting at 3 s')})")


def test_init_db_still_backfills_what_it_backfilled(tmp_path):
    """The guards are guards, not removals: a legacy unit-less recording of a
    known file still gets its unit, and stays idempotent."""
    from Working.units import RECORDING_UNITS_EVIDENCE
    source_file, (units, _note) = next(iter(RECORDING_UNITS_EVIDENCE.items()))
    path = str(tmp_path / "a.sqlite")
    conn = init_db(path)
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                 "VALUES (?, 0, 1.0, 10, 0, 'x.npy')", (source_file,))
    conn.commit()
    conn.close()
    conn = init_db(path)
    conn.close()
    conn = init_db(path)
    try:
        rows = conn.execute("SELECT units FROM recordings WHERE source_file = ?", (source_file,)).fetchall()
        assert [r[0] for r in rows] == [units]
    finally:
        conn.close()


def test_every_connection_waits_for_a_writer_longer_than_sqlites_default(db):
    assert S.BUSY_TIMEOUT_S >= 30
    for conn in (get_connection(db), init_db(db)):
        try:
            assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == int(S.BUSY_TIMEOUT_S * 1000)
        finally:
            conn.close()
