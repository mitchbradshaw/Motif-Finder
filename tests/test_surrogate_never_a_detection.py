"""
test_surrogate_never_a_detection.py
====================================
fixup-T, Part A. A paired surrogate run is a real `runs` row
(`surrogate_of_run_id` set) and the executor writes its spans to `detections`
like any other run's. The PRD promises that "nothing surrogate-derived can
enter the library"; until this prompt nothing enforced the wider version of
that. Measured on the real database, 2026-10-03: 6 surrogate runs carrying 30
of its 1,205 detections, counted and drawn by Explore, servable to Review, and
read by the divergence query as "the machine found something here".

The fixture (fs = 1 Hz, one recording of 10 000 samples)
--------------------------------------------------------
real run R       D1 [ 100,  200)   D2 [ 300,  400)
surrogate of R   S1 [5000, 5100)   S2 [ 300,  400)   S3 [7000, 7100)
annotations      A1 [ 100,  200)   overlapped by D1            -> the machine found it
                 A2 [5000, 5100)   overlapped ONLY by S1       -> the machine did not

So every reader that means "what the machine found" must see 2 detections
(D1, D2) on 1 run, and A2 must read as "human says yes, machine said nothing".

The exclusion has ONE home in the core (`queries.not_surrogate`), and the last
test here keeps it that way: a file that reads `detections` either goes
through the predicate or is on a short list of readers that have a stated
reason not to.

Runnable standalone:  python tests/test_surrogate_never_a_detection.py
"""

import io
import os
import re
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from Working.database import queries as q  # noqa: E402
from Working.database.adjudications import insert_adjudication  # noqa: E402
from Working.database import runs as run_db  # noqa: E402
from Working.database.schema import init_db  # noqa: E402

REAL = [(100, 200), (300, 400)]
SURROGATE = [(5000, 5100), (300, 400), (7000, 7100)]


def _run(conn, recording_id, steps, span=(0, 10_000)):
    config_id, _ = run_db.get_or_create_config(conn, {"steps": steps})
    return run_db.insert_run(conn, config_id, recording_id, span[0], span[1],
                             started_at="2026-09-20T00:00:00", status="completed")


@pytest.fixture()
def db(tmp_path):
    conn = init_db(str(tmp_path / "t.sqlite"))
    rec = q.insert_recording(conn, "fixture.mat", 0, 1.0, 10_000, 0, str(tmp_path / "CH0.npy"))
    detect = {"stage": "detection", "algorithm": "threshold", "params": {}}
    null = {"stage": "preprocessing", "algorithm": "surrogate",
            "params": {"method": "phase_randomize", "seed": 0}}
    group = run_db.create_run_group(conn)
    real = _run(conn, rec, [detect])
    surrogate = _run(conn, rec, [null, detect])
    run_db.update_run(conn, real, run_group_id=group)
    run_db.update_run(conn, surrogate, run_group_id=group, surrogate_of_run_id=real)
    real_ids = [run_db.insert_detection(conn, real, a, b, score=1.0) for a, b in REAL]
    surrogate_ids = [run_db.insert_detection(conn, surrogate, a, b, score=1.0) for a, b in SURROGATE]
    a1 = q.insert_annotation(conn, rec, 100, 200, "interesting", source="manual_ui")
    a2 = q.insert_annotation(conn, rec, 5000, 5100, "interesting", source="manual_ui")
    yield {"conn": conn, "rec": rec, "group": group, "real": real, "surrogate": surrogate,
           "real_ids": real_ids, "surrogate_ids": surrogate_ids, "a1": a1, "a2": a2}
    conn.close()


# ── the predicate ────────────────────────────────────────────────────────────

def test_the_exclusion_has_one_home_and_it_is_a_sql_predicate(db):
    clause = q.not_surrogate("r")
    n = db["conn"].execute(
        "SELECT COUNT(*) FROM detections d JOIN runs r ON r.id = d.run_id WHERE " + clause).fetchone()[0]
    assert n == len(REAL)
    # and under another alias, for a query that already calls its runs something else
    n = db["conn"].execute("SELECT COUNT(*) FROM runs x WHERE " + q.not_surrogate("x")).fetchone()[0]
    assert n == 1


def test_a_run_can_be_asked_whether_it_is_a_null(db):
    assert q.is_surrogate_run(db["conn"], db["surrogate"]) is True
    assert q.is_surrogate_run(db["conn"], db["real"]) is False


# ── the core's readers ───────────────────────────────────────────────────────

def test_a_recordings_detections_are_the_real_runs_only(db):
    rows = run_db.list_detections_for_recording(db["conn"], db["rec"])
    assert sorted(r["id"] for r in rows) == sorted(db["real_ids"])


def test_review_is_never_served_a_surrogate_detection(db):
    conn = db["conn"]
    everything = q.queue_candidates(conn, limit=1000)
    assert sorted(r["id"] for r in everything) == sorted(db["real_ids"])
    # the run group holds the surrogate too (fixup-L found 249 beside 74 real)
    by_group = q.queue_candidates(conn, run_group_id=db["group"], limit=1000)
    assert sorted(r["id"] for r in by_group) == sorted(db["real_ids"])
    # asking for the null run by name is still a queue over nothing
    assert q.queue_candidates(conn, run_id=db["surrogate"], limit=1000) == []
    assert q.queue_candidates(conn, run_ids=[db["real"], db["surrogate"]], limit=1000)[-1]["id"] in db["real_ids"]
    assert q.queue_candidates(conn, detection_ids=db["surrogate_ids"], limit=1000) == []


def test_a_surrogate_overlap_is_not_the_machine_finding_something(db):
    """A2 is overlapped only by a surrogate span: human yes, machine nothing."""
    missing = q.divergence_annotations_without_detection(db["conn"], db["rec"])
    assert [r["id"] for r in missing] == [db["a2"]]


def test_a_rejected_surrogate_span_is_not_a_machine_false_positive(db):
    conn = db["conn"]
    insert_adjudication(conn, db["surrogate_ids"][0], "not_interesting")
    insert_adjudication(conn, db["real_ids"][1], "not_interesting")
    rejected = q.divergence_rejected_detections(conn, db["rec"])
    assert [r["id"] for r in rejected] == [db["real_ids"][1]]


def test_a_surrogate_span_cannot_be_promoted_from_review(db):
    from Working.review import promotion

    conn = db["conn"]
    conn.execute(
        "INSERT INTO review_queues (name, unit, source_kind, writes_to, filters_json, created_at) "
        "VALUES ('t', 'detection', 'discovery-run', 'adjudications', '{}', '2026-10-03T00:00:00')")
    conn.commit()
    qid = conn.execute("SELECT id FROM review_queues").fetchone()[0]
    with pytest.raises(ValueError, match="surrogate"):
        promotion.resolve_target(conn, qid, db["surrogate_ids"][0])


# ── the bridge's readers (plain functions; no FastAPI) ───────────────────────

def test_explores_counts_and_spans_are_the_real_runs_only(db):
    from server import corpus

    conn = db["conn"]
    summary = corpus.channel_summary(conn, db["rec"])
    assert summary["detections"] == len(REAL)
    assert summary["detection_runs"] == 1

    drawn = corpus.spans(conn, db["rec"], 0.0, 10_000.0, 1.0)
    assert sorted(d["id"] for d in drawn["detections"]) == sorted(db["real_ids"])

    density = corpus.ribbons(conn, db["rec"], 1.0, 10_000, buckets=10)["detection_density"]
    assert sum(density) == len(REAL)


def test_explores_corpus_map_counts_the_real_runs_only(db):
    from server import corpus

    cov = corpus.coverage(db["conn"], "fixture.mat", bins=10)
    row = cov["rows"][0]
    assert row["counts"]["detections"] == len(REAL)
    assert sum(row["detections"]) == len(REAL)
    assert cov["n_detection_runs"] == 1
    # disagree = A2 (no real detection over it) + D2 (no annotation over it)
    assert row["counts"]["disagree"] == 2


def test_the_method_filter_does_not_offer_a_null_as_a_method(db):
    from server import corpus

    listed = corpus.run_methods(db["conn"], "fixture.mat")
    assert [r["id"] for r in listed] == [db["real"]]


# ── and it stays in one home ─────────────────────────────────────────────────

#: Readers of `detections` that do NOT go through `not_surrogate`, and why.
REASONED = {
    "Working/database/schema.py": "migrations rewrite rows of every run, null or not",
    "Working/discovery/scoreboard.py": "the scoreboard is the reader that WANTS the null's count",
    "Working/discovery/fanout.py": "counts per explicitly-named real run (members filtered above it)",
    "webui/server/jobs.py": "one job's own run id",
}
_READS = re.compile(r"\b(FROM|JOIN)\s+detections\b", re.IGNORECASE)


def test_every_reader_of_detections_goes_through_the_predicate():
    offenders = []
    for top in ("Working", "webui/server", "Adapters"):
        for root, _dirs, names in os.walk(os.path.join(PROJECT_ROOT, top)):
            for name in names:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(root, name)
                rel = os.path.relpath(path, PROJECT_ROOT).replace(os.sep, "/")
                src = io.open(path, encoding="utf-8", errors="replace").read()
                if not _READS.search(src) or rel in REASONED:
                    continue
                if "not_surrogate(" not in src and "is_surrogate_run(" not in src:
                    offenders.append(rel)
    assert offenders == [], (
        "these files read `detections` without `queries.not_surrogate` — a surrogate run's spans "
        f"would be counted as detections: {offenders}")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
