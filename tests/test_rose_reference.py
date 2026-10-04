"""
test_rose_reference.py
======================
fixup-AE item 5 (Round 10): the slope that reads 45° on a rose is **the median
steepest slope over human-accepted Library motifs** (accepted by the one
verdict resolver), so sharp noise and artifacts do not skew it.

* one core function computes it; it is stored as Settings › Analysis defaults
  keys WITH the population it came from (n, date), and recomputed only on an
  explicit act;
* until at least N motifs are accepted (a Settings key, default 30) it falls
  back to the median over every Library motif ABOVE the noise floor, and says
  so — never silently to 1.0 mV/s (`gradients.py:89`);
* `interrogation.event_shape`'s default reads it.

Fixture: six members on one 1 Hz recording, windows labelling members 1-3
interesting. Steepest slopes (event shape, mV/s): 1: -2, 2: -4, 3: -6,
4: -100 (an artifact-sharp spike, NOT accepted), 5: -8 (sub-floor: depth 0.05),
6: -10.
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
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as q  # noqa: E402
from Working.database import vocabulary as vocab  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.library import features as F  # noqa: E402
from Working.registration.settings import get_settings, put_settings  # noqa: E402

SLOPES = {1: -2.0, 2: -4.0, 3: -6.0, 4: -100.0, 5: -8.0, 6: -10.0}
DEPTHS = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 0.05, 6: 1.0}


@pytest.fixture
def conn():
    c = init_db(":memory:")
    c.row_factory = sqlite3.Row
    vocab.seed_vocabulary(c)
    rec = q.insert_recording(c, "R.mat", 0, 1.0, 100_000, 0, "DATA/derived/channels/R/CH0.npy")
    now = datetime.datetime.now().isoformat()
    rows = []
    for mid in SLOPES:
        a = 1000 * mid + 100
        c.execute("INSERT INTO motif_entry (id, recording_id, start_idx, end_idx, content_hash, source_kind, fs, "
                  "created_at) VALUES (?, ?, ?, ?, ?, 'event_store', 1.0, ?)", (mid, rec, a, a + 50, f"{mid:032d}", now))
        c.execute("INSERT INTO motif_member (id, entry_id, recording_id, start_idx, end_idx, content_hash) "
                  "VALUES (?, ?, ?, ?, ?, ?)", (mid, mid, rec, a, a + 50, f"{mid:032d}"))
        rows.append({"content_hash": f"{mid:032d}", "fs": 1.0, "measures": {"max_slope_mv_s": SLOPES[mid]},
                     "detector": {"drop_depth_mv": DEPTHS[mid]}})
        if mid <= 3:      # members 1-3 sit in a window a person labelled interesting
            q.insert_annotation(c, rec, 1000 * mid, 1000 * mid + 600, "interesting", q.SOURCE_IMPORTED_10MIN,
                                created_at=now)
    F.write_features(c, rows)
    c.commit()
    yield c
    c.close()


def test_with_too_few_accepted_it_falls_back_to_every_motif_above_the_floor_and_says_so(conn):
    from Working.library import rose_reference as RR
    r = RR.compute(conn)                                   # 3 accepted < the default 30
    assert r["population"] == RR.POP_ABOVE_FLOOR
    assert r["n"] == 5                                     # member 5 is sub-floor
    assert r["value_mv_s"] == pytest.approx(6.0)           # median |slope| of 2, 4, 6, 10, 100
    assert r["n_accepted"] == 3 and r["min_accepted"] == 30
    assert "fallback" in r["text"] and "n = 5" in r["text"]


def test_with_enough_accepted_it_is_the_median_over_accepted_motifs_only(conn):
    from Working.library import rose_reference as RR
    put_settings(conn, RR.SETTINGS_PAGE, {RR.MIN_ACCEPTED_KEY: 3})
    r = RR.compute(conn)
    assert r["population"] == RR.POP_ACCEPTED
    assert r["n"] == 3 and r["value_mv_s"] == pytest.approx(4.0)   # the -100 spike never skews it
    assert "accepted" in r["text"] and "n = 3" in r["text"]


def test_it_is_stored_with_its_population_only_on_an_explicit_act(conn):
    from Working.library import rose_reference as RR
    assert RR.SETTINGS_PAGE == "analysis-defaults"
    assert RR.VALUE_KEY not in get_settings(conn, RR.SETTINGS_PAGE)
    cur = RR.current(conn)                                 # nothing stored: computed, and says it is not stored
    assert cur["stored"] is False and cur["value_mv_s"] == pytest.approx(6.0)
    assert RR.VALUE_KEY not in get_settings(conn, RR.SETTINGS_PAGE), "reading never writes"
    RR.recompute(conn, actor="test")
    saved = get_settings(conn, RR.SETTINGS_PAGE)
    assert saved[RR.VALUE_KEY] == pytest.approx(6.0)
    assert saved[RR.POPULATION_KEY] == RR.POP_ABOVE_FLOOR and saved[RR.N_KEY] == 5 and saved[RR.COMPUTED_AT_KEY]
    put_settings(conn, RR.SETTINGS_PAGE, {RR.MIN_ACCEPTED_KEY: 3})
    assert RR.current(conn)["value_mv_s"] == pytest.approx(6.0), "a stored value holds until recomputed"
    assert RR.current(conn)["stored"] is True


def test_it_never_silently_uses_one_mV_per_s():
    from Working.library import rose_reference as RR
    c = init_db(":memory:")
    r = RR.compute(c)
    assert r["value_mv_s"] is None and r["n"] == 0 and "no" in r["text"]
    c.close()


def test_event_shape_reads_the_stored_reference_by_default(conn, monkeypatch):
    from Working.library import rose_reference as RR
    from Adapters import interrogation_event_shape as A
    spec = {p.name: p for p in A.SPEC.params}["rose_reference_mv_s"]
    assert spec.default == RR.USE_STORED, "the default is the Library's reference, not a constant"
    RR.recompute(conn, actor="test")
    assert RR.resolve(RR.USE_STORED, conn=conn)["value_mv_s"] == pytest.approx(6.0)
    assert RR.resolve(2.5, conn=conn)["value_mv_s"] == 2.5 and RR.resolve(2.5, conn=conn)["population"] == "stated"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
