"""tq-rules (2026-10-25): server-side rules written once.

1. The legacy span-relative shift (detections written by a spanned run before 2026-09-21 are relative to the
   span; a start below the run's `span_start` marks one) was stated as SQL three times beside its Python
   definition, `Working.discovery.spans.absolute_bounds`. `spans.absolute_sql` is the one SQL form; this file
   checks it agrees with `absolute_bounds` on legacy span-relative rows, absolute rows, unspanned runs (NULL and
   0) and surrogate runs, and that the three readers use it.
2. `_library_detections`' numpy interval merge is `spans.merged_rows`, checked against
   `Working.database.queries.merge_intervals` (touching spans merge in both).
3. `unwritten_counts` and `queue_counts` share one detection-count helper.
"""

import inspect
import random
import sqlite3
from pathlib import Path

import pytest

from Working.database.queries import merge_intervals
from Working.discovery import spans
from Working.discovery.spans import absolute_bounds

ROOT = Path(__file__).resolve().parents[1]


def _db():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE runs (id INTEGER PRIMARY KEY, span_start INTEGER, span_end INTEGER, "
                 "surrogate_of_run_id INTEGER)")
    conn.execute("CREATE TABLE detections (id INTEGER PRIMARY KEY, run_id INTEGER, start_idx INTEGER, "
                 "end_idx INTEGER)")
    runs = [
        (1, None, None, None),        # unspanned, NULL
        (2, 0, 5000, None),           # whole channel, 0
        (3, 1000, 1600, None),        # spanned: legacy relative rows below 1000, absolute rows at/above
        (4, 1000, 1600, 3),           # a surrogate of run 3, same span
        (5, 7, 20, None),             # a tiny offset: rows straddle it
    ]
    conn.executemany("INSERT INTO runs VALUES (?, ?, ?, ?)", runs)
    rows, did = [], 0
    for rid, *_ in runs:
        for s, e in [(0, 5), (3, 9), (6, 7), (7, 8), (12, 40), (500, 600), (999, 1001), (1000, 1010),
                     (1200, 1300), (1599, 1700)]:
            did += 1
            rows.append((did, rid, s, e))
    conn.executemany("INSERT INTO detections VALUES (?, ?, ?, ?)", rows)
    return conn


def test_absolute_sql_agrees_with_absolute_bounds_on_every_kind_of_run():
    conn = _db()
    a, b = spans.absolute_sql("d", "r")
    got = conn.execute(f"SELECT d.id, {a}, {b} FROM detections d JOIN runs r ON r.id = d.run_id").fetchall()
    raw = {r[0]: r[1:] for r in conn.execute(
        "SELECT d.id, d.start_idx, d.end_idx, r.span_start FROM detections d JOIN runs r ON r.id = d.run_id")}
    assert len(got) == 50
    shifted = 0
    for did, sa, sb in got:
        s, e, o = raw[did]
        assert (sa, sb) == absolute_bounds(s, e, o), (did, s, e, o)
        shifted += (sa, sb) != (s, e)
    assert shifted > 0                      # the fixture does exercise the shift


def test_absolute_sql_takes_the_callers_aliases():
    conn = _db()
    a, b = spans.absolute_sql("x", "u")
    got = conn.execute(f"SELECT {a}, {b} FROM detections x JOIN runs u ON u.id = x.run_id "
                       "WHERE x.id = 26").fetchone()        # run 3, (500, 600): a legacy row
    assert tuple(got) == (1500, 1600)


def test_merged_rows_agrees_with_merge_intervals():
    rng = random.Random(7)
    assert spans.merged_rows([]) == []
    for _ in range(200):
        rows = []
        for _ in range(rng.randint(1, 40)):
            s = rng.randint(0, 200)
            rows.append((s, s + rng.randint(0, 15)))
        assert spans.merged_rows(rows) == merge_intervals(rows)
    assert spans.merged_rows([(0, 5), (5, 9)]) == [(0, 9)]          # touching spans merge, as in merge_intervals


@pytest.mark.parametrize("rel", ["webui/server/library.py", "webui/server/corpus.py", "webui/server/discovery.py"])
def test_the_readers_state_the_shift_through_absolute_sql(rel):
    src = (ROOT / rel).read_text(encoding="utf-8")
    assert "absolute_sql(" in src
    assert "THEN d.start_idx + " not in src and "span_start, 0) != 0" not in src


def test_library_detections_has_no_merge_of_its_own():
    src = (ROOT / "webui/server/library.py").read_text(encoding="utf-8")
    assert "np.maximum.accumulate" not in src
    assert "merged_rows(" in src


def test_both_send_n_count_paths_share_one_detection_count():
    from Working.review import queues
    assert callable(getattr(queues, "_detection_counts", None))
    for fn in (queues.queue_counts, queues.unwritten_counts):
        src = inspect.getsource(fn)
        assert "_detection_counts(" in src
        assert "FROM adjudications" not in src
