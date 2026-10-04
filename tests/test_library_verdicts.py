"""
test_library_verdicts.py
========================
fixup-AE item 4 (L7): a Library member's verdict comes from THE one resolver,
`Working/discovery/divergence.py`, in its order — a Review verdict on the
member's detection first, then the event-shaped row it matches (§4.6), then the
reviewed windows it falls in (centre rule by default, Settings' containment
mode). That replaces exact span equality, which matched 0.0 % on every family.

Fixture (one channel, 1 Hz):

    windows (imported_10min)  W1 [0, 600) interesting   W2 [600, 1200) not_interesting
    event rows (excel)        E1 [700, 800) interesting
    a run over [0, 2000) with detection D1 [900, 1000), adjudicated interesting

    member  span            how it resolves
    m1      [100, 300)      W1 holds its centre             -> yes, containment
    m2      [700, 795)      matches E1 under §4.6           -> yes, extent (W2 says no; extent comes first)
    m3      [900, 1000)     its detection D1 was adjudicated -> yes, adjudication (W2 says no)
    m4      [1300, 1400)    no human near it                -> unjudged
    m5      [1000, 1100)    W2 holds its centre             -> no, containment
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

from Working.database import adjudications as adj  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database import runs as run_db  # noqa: E402
from Working.database import vocabulary as vocab  # noqa: E402
from Working.database.schema import init_db  # noqa: E402

BEFORE = "2026-09-01T00:00:00"
SPANS = {1: (100, 300), 2: (700, 795), 3: (900, 1000), 4: (1300, 1400), 5: (1000, 1100)}


@pytest.fixture
def db():
    conn = init_db(":memory:")
    conn.row_factory = sqlite3.Row
    vocab.seed_vocabulary(conn)
    rec = q.insert_recording(conn, "fixture.mat", 0, 1.0, 10_000, 0, "fixture_CH0.npy")
    q.insert_annotation(conn, rec, 0, 600, "interesting", q.SOURCE_IMPORTED_10MIN, created_at=BEFORE)
    q.insert_annotation(conn, rec, 600, 1200, "not_interesting", q.SOURCE_IMPORTED_10MIN, created_at=BEFORE)
    q.insert_annotation(conn, rec, 700, 800, "interesting", "excel_catalog", created_at=BEFORE)
    config_id, _ = run_db.get_or_create_config(
        conn, {"steps": [{"stage": "detection", "algorithm": "threshold", "params": {}}]})
    run = run_db.insert_run(conn, config_id, rec, 0, 2000, started_at=BEFORE, status="completed")
    d1 = run_db.insert_detection(conn, run, 900, 1000, score=0.9)
    adj.insert_adjudication(conn, d1, "interesting")
    now = datetime.datetime.now().isoformat()
    for mid, (a, b) in SPANS.items():
        conn.execute("INSERT INTO motif_entry (id, recording_id, start_idx, end_idx, content_hash, source_kind, "
                     "detection_id, fs, created_at) VALUES (?, ?, ?, ?, ?, 'event_store', ?, 1.0, ?)",
                     (mid, rec, a, b, f"{mid:032d}", d1 if mid == 3 else None, now))
        conn.execute("INSERT INTO motif_member (id, entry_id, recording_id, start_idx, end_idx, content_hash) "
                     "VALUES (?, ?, ?, ?, ?, ?)", (mid, mid, rec, a, b, f"{mid:032d}"))
    conn.commit()
    yield {"conn": conn, "rec": rec, "run": run, "d1": d1}
    conn.close()


def _members(conn):
    return [dict(r) for r in conn.execute(
        "SELECT id AS member_id, entry_id, recording_id, start_idx, end_idx FROM motif_member ORDER BY id")]


def test_the_resolver_resolves_any_span_in_its_own_order(db):
    from Working.discovery import divergence as dv
    spans = [SPANS[i] for i in (1, 2, 3, 4, 5)]
    out = dv.resolve_spans(db["conn"], db["rec"], spans, detection_ids=[None, None, db["d1"], None, None])
    assert [(o["side"], o["by"]) for o in out] == [
        ("yes", "containment"), ("yes", "extent"), ("yes", "adjudication"), (None, None), ("no", "containment")]
    assert out[3]["why"]                                      # an unresolved span says why


def test_a_detection_span_resolves_as_channel_divergence_resolves_it(db):
    from Working.discovery import divergence as dv
    item = next(i for i in dv.channel_divergence(db["conn"], db["rec"], [db["run"]])["items"]
                if i["kind"] == "detection")
    got = dv.resolve_spans(db["conn"], db["rec"], [(900, 1000)], detection_ids=[db["d1"]])[0]
    assert (got["by"], "machine_yes_human_" + got["side"]) == (item["by"], item["cell"])


def test_library_members_take_their_verdicts_from_the_resolver(db):
    from Working.library import verdicts as V
    got = V.member_verdicts(db["conn"], _members(db["conn"]))
    assert got[1]["verdict"] == "interesting" and got[1]["by"] == "containment"
    assert got[2]["by"] == "extent"
    assert got[3]["by"] == "adjudication"
    assert got[4]["judged"] is False and got[4]["verdict"] == "unjudged"
    assert got[5]["verdict"] == "not_interesting" and got[5]["side"] == "no"
    assert sum(v["judged"] for v in got.values()) == 4, "exact span equality matched none of these"


def test_the_rule_is_printed_with_the_containment_mode(db):
    from Working.library import verdicts as V
    text = V.rule_text(db["conn"])
    assert "Review" in text and "event" in text and "centre" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
