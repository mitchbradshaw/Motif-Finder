"""
test_webui_review.py
====================
Route-level guarantees of the Review bridge (`webui/server/review.py`,
stage-3 Prompt 05). What the page cannot be trusted to catch:

* every route answers, with the keys `webui/client/src/api/review.ts` declares
  on `ItemDetail` — a missing key renders as `undefined`, which draws as an
  empty panel rather than as an error;
* a verdict written through the route lands in the table the queue's
  `writes_to` names **and nowhere else** — CLAUDE.md rule 5, checked by
  counting the *other* table's rows before and after;
* undo reverses the write;
* a batch of N is ONE `review_audit` row, not N indistinguishable ones;
* the held-out recording is refused.

FastAPI lives only in `webui/.venv`, so under the conda `pytest` this file
skips; run it with

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_review.py
"""

import json
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv; run this file with that interpreter")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from Working.database import queries as _queries  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.database.vocabulary import seed_vocabulary  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import HELD_OUT_FILE, Runtime  # noqa: E402

FS = 1.0
N_SAMPLES = 20000


def _write_channel(dir_path, name, n=N_SAMPLES):
    t = np.arange(n, dtype=float)
    x = 0.2 * np.sin(t / 97.0) + 0.02 * np.cos(t / 7.0)
    path = os.path.join(dir_path, f"{name}.npy")
    np.save(path, x.astype(np.float32))
    return path


def _seed(tmp_path):
    """One recording with two channels, one held-out recording, one run with
    six detections on each — enough for a discovery-run queue."""
    npy_dir = tmp_path / "npy"
    npy_dir.mkdir()
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))

    rec_ids = []
    for ch in range(2):
        path = _write_channel(str(npy_dir), f"norm_{ch}")
        rec_ids.append(conn.execute(
            "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
            "VALUES ('M2_aug_concat_fs1.mat', ?, ?, ?, 0, ?)", (ch, FS, N_SAMPLES, path)).lastrowid)
    held_path = _write_channel(str(npy_dir), "held")
    held_rec = conn.execute(
        "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
        "VALUES (?, 0, ?, ?, 0, ?)", (HELD_OUT_FILE, FS, N_SAMPLES, held_path)).lastrowid
    # A single-channel export whose FILE NAME names the electrode (CH14) while
    # `recordings.channel` is 0 — the case where a derived "CH{channel+1}"
    # label contradicts the file the reviewer is looking at.
    ch14_path = _write_channel(str(npy_dir), "ch14")
    ch14_rec = conn.execute(
        "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
        "VALUES ('Mushroom_260720_0509_4hrs_CH14_fs1.mat', 0, ?, ?, 0, ?)",
        (FS, N_SAMPLES, ch14_path)).lastrowid

    cfg = conn.execute(
        "INSERT INTO configs (config_hash, config_json, created_at) "
        "VALUES ('cfg-review', '{}', '2026-09-22T09:00:00')").lastrowid
    run_ids, det_ids = [], []
    for rid in rec_ids:
        run = conn.execute(
            "INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
            "VALUES (?, ?, 0, ?, '2026-09-22T09:00:00', 'ok')", (cfg, rid, N_SAMPLES)).lastrowid
        run_ids.append(run)
        for k in range(3):
            a = 1000 + k * 600
            det_ids.append(conn.execute(
                "INSERT INTO detections (run_id, start_idx, end_idx, score, meta_json) "
                "VALUES (?, ?, ?, ?, ?)", (run, a, a + 40, 0.9 - 0.01 * k, json.dumps({}))).lastrowid)
    held_run = conn.execute(
        "INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
        "VALUES (?, ?, 0, ?, '2026-09-22T09:00:00', 'ok')", (cfg, held_rec, N_SAMPLES)).lastrowid
    held_dets = [conn.execute(
        "INSERT INTO detections (run_id, start_idx, end_idx, score, meta_json) "
        "VALUES (?, ?, ?, 0.7, '{}')", (held_run, 500 + 200 * k, 560 + 200 * k)
    ).lastrowid for k in range(2)]
    ch14_run = conn.execute(
        "INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
        "VALUES (?, ?, 0, ?, '2026-09-22T09:00:00', 'ok')", (cfg, ch14_rec, N_SAMPLES)).lastrowid
    ch14_det = conn.execute(
        "INSERT INTO detections (run_id, start_idx, end_idx, score, meta_json) "
        "VALUES (?, 3000, 3060, 0.5, '{}')", (ch14_run,)).lastrowid

    # One catalogued sequence awaiting extraction, with the parent annotation
    # its extracted events must hang off. Its id is deliberately NOT its
    # annotation's id — the two stores number independently.
    seed_vocabulary(conn)
    parent_ann = _queries.insert_annotation(
        conn, rec_ids[0], 4000, 5000, "interesting", "imported_10min",
        note="the parent's own note", created_at="2026-09-22T09:00:00", commit=False)
    seq_id = conn.execute(
        "INSERT INTO sequences (sequence_key, origin, recording_id, channel, start_idx, "
        "end_idx, n_events, needs_extraction, annotation_id, created_at) "
        "VALUES ('seq-review-1', 'human', ?, 0, 4000, 5000, 3, 1, ?, '2026-09-22T09:00:00')",
        (rec_ids[0], parent_ann)).lastrowid
    conn.commit()
    conn.close()
    return {"db": str(db), "recordings": rec_ids, "held_recording": held_rec,
            "runs": run_ids, "detections": det_ids, "held_detection": held_dets[0],
            "held_detections": held_dets, "held_run": held_run,
            "ch14_recording": ch14_rec, "ch14_run": ch14_run, "ch14_detection": ch14_det,
            "sequence": seq_id, "parent_annotation": parent_ann}


@pytest.fixture()
def seeded(tmp_path):
    info = _seed(tmp_path)
    rt = Runtime("sandbox", stamp="test-review", db_source=info["db"],
                 runtime_root=str(tmp_path / "runtime")).setup()
    app = create_app(rt)
    with TestClient(app) as client:
        yield client, rt, info
    rt.restore()


def _rows(rt, table):
    import sqlite3
    conn = sqlite3.connect(rt.db_path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _make_queue(client, info, **kw):
    body = {"name": "Discovery review test", "source_kind": "discovery-run",
            "source_ref": None}
    body.update(kw)
    r = client.post("/api/review/queues", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ── the routes answer ───────────────────────────────────────────────────────

def test_counts_and_queues_answer(seeded):
    client, rt, info = seeded
    counts = client.get("/api/review/counts")
    assert counts.status_code == 200, counts.text
    assert "need_you" in counts.json() and "by_queue" in counts.json()

    q = _make_queue(client, info)
    assert q["queue"]["writes_to"] == "adjudications"
    assert q["queue"]["unit"] == "detection"
    assert not q["queue"]["blind"]

    listing = client.get("/api/review/queues")
    assert listing.status_code == 200, listing.text
    assert any(str(x["id"]) == str(q["queue"]["id"]) for x in listing.json())

    one = client.get(f"/api/review/queues/{q['queue']['id']}")
    assert one.status_code == 200, one.text
    assert one.json()["rows"], "a discovery-run queue over a seeded run must resolve rows"


def test_item_detail_carries_the_client_shape(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    row = client.get(f"/api/review/queues/{qid}").json()["rows"][0]
    item = client.get(f"/api/review/queues/{qid}/items/{row['id']}")
    assert item.status_code == 200, item.text
    d = item.json()
    for key in ("entry", "queue", "context", "shape", "nearest", "medoids",
                "artifact", "evidence", "thumb"):
        assert key in d, f"ItemDetail.{key} missing: the panel would draw blank"
    assert "values" in d["context"] and "t0_s" in d["context"]
    assert d["context"]["values"], "context trace must be real decimated mV, never empty"


# ── rule 5: the verdict lands in one table and not the other ────────────────

def test_verdict_lands_in_adjudications_and_not_annotations(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    row = client.get(f"/api/review/queues/{qid}").json()["rows"][0]
    before_h = _rows(rt, "annotations")
    before_m = _rows(rt, "adjudications")

    r = client.post(f"/api/review/queues/{qid}/verdict",
                    json={"target_id": row["id"], "verdict": "interesting"})
    assert r.status_code == 200, r.text
    assert _rows(rt, "adjudications") == before_m + 1
    assert _rows(rt, "annotations") == before_h, "a machine adjudication must never become a human row"

    undo = client.post(f"/api/review/queues/{qid}/undo")
    assert undo.status_code == 200, undo.text
    assert _rows(rt, "adjudications") == before_m, "undo must reverse the write"


def test_batch_is_one_audit_row(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    rows = client.get(f"/api/review/queues/{qid}").json()["rows"]
    assert len(rows) >= 3
    before_audit = _rows(rt, "review_audit")
    targets = [x["id"] for x in rows[:3]]
    r = client.post(f"/api/review/queues/{qid}/batch",
                    json={"target_ids": targets, "verdict": "not_interesting"})
    assert r.status_code == 200, r.text
    assert _rows(rt, "review_audit") == before_audit + 1, "a batch is ONE audit row, not N"


def test_held_out_item_is_refused(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info, name="held")
    qid = q["queue"]["id"]
    item = client.get(f"/api/review/queues/{qid}/items/{info['held_detection']}")
    assert item.status_code in (200, 423), item.text
    if item.status_code == 200:
        assert item.json().get("refused"), "a held-out recording must be refused, not served"


# ── stage-2 fix round: the bridge findings the three critics wrote up ────────
#
# Each test below names the finding it pins. They are route-level on purpose:
# every one of these was invisible to `pytest` under conda (this file skips
# there) and to `npx tsc -b` (the payload is read through `any`), which is how
# they survived stage 1.

def _query(rt, sql, params=()):
    import sqlite3
    conn = sqlite3.connect(rt.db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _exec(rt, sql, params=()):
    import sqlite3
    conn = sqlite3.connect(rt.db_path)
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _extract_queue(client):
    r = client.post("/api/review/queues",
                    json={"name": "Library - extract events",
                          "source_kind": "extract-events"})
    assert r.status_code == 200, r.text
    return r.json()["queue"]["id"]


def _first_row(client, qid):
    rows = client.get(f"/api/review/queues/{qid}").json()["rows"]
    assert rows, "the queue resolved no rows"
    return rows[0]


# ── P0-3 · POST /extract lost the work and destroyed the parent's note ──────

def test_extract_writes_one_child_annotation_per_event(seeded):
    client, rt, info = seeded
    qid = _extract_queue(client)
    before = _rows(rt, "annotations")
    audit_before = _rows(rt, "review_audit")

    r = client.post(f"/api/review/queues/{qid}/extract",
                    json={"sequence_id": info["sequence"],
                          "events": [{"start_idx": 4100, "end_idx": 4160},
                                     {"start_idx": 4400, "end_idx": 4460}],
                          "complete": True})
    assert r.status_code == 200, r.text

    assert _rows(rt, "annotations") == before + 2, \
        "each extracted event is a NEW singular annotation, not a note on the parent"
    kids = _query(rt, "SELECT start_idx, end_idx FROM annotations "
                      "WHERE parent_annotation_id = ? ORDER BY start_idx",
                  (info["parent_annotation"],))
    assert [tuple(k) for k in kids] == [(4100, 4160), (4400, 4460)], \
        "every child must point at the parent SEQUENCE's annotation"
    parent = _query(rt, "SELECT note, verdict FROM annotations WHERE id = ?",
                    (info["parent_annotation"],))[0]
    assert parent[0] == "the parent's own note", \
        "an extraction must not overwrite the parent annotation's note"
    assert _query(rt, "SELECT needs_extraction FROM sequences WHERE id = ?",
                  (info["sequence"],))[0][0] == 0, \
        "complete=true clears needs_extraction or the item never leaves the queue"
    assert _rows(rt, "review_audit") == audit_before + 1, \
        "one gesture is ONE audit row, so one Ctrl-Z walks it back"


def test_extract_undo_removes_the_children_and_restores_the_flag(seeded):
    client, rt, info = seeded
    qid = _extract_queue(client)
    before = _rows(rt, "annotations")
    client.post(f"/api/review/queues/{qid}/extract",
                json={"sequence_id": info["sequence"],
                      "events": [{"start_idx": 4100, "end_idx": 4160}],
                      "complete": True})
    assert _rows(rt, "annotations") == before + 1, "nothing to undo: the extract wrote no child"
    assert _query(rt, "SELECT needs_extraction FROM sequences WHERE id = ?",
                  (info["sequence"],))[0][0] == 0
    undo = client.post(f"/api/review/queues/{qid}/undo")
    assert undo.status_code == 200, undo.text
    assert _rows(rt, "annotations") == before, "undo must remove the children it created"
    assert _query(rt, "SELECT needs_extraction FROM sequences WHERE id = ?",
                  (info["sequence"],))[0][0] == 1, \
        "undo must put the sequence back in the queue"


def test_extract_leaves_the_queue_when_it_is_complete(seeded):
    client, rt, info = seeded
    qid = _extract_queue(client)
    before = client.get(f"/api/review/queues/{qid}").json()
    assert any(r["id"] == str(info["sequence"]) for r in before["rows"])
    client.post(f"/api/review/queues/{qid}/extract",
                json={"sequence_id": info["sequence"],
                      "events": [{"start_idx": 4100, "end_idx": 4160}],
                      "complete": True})
    after = client.get(f"/api/review/queues/{qid}").json()
    assert all(r["id"] != str(info["sequence"]) for r in after["rows"]), \
        "an extracted sequence must drain out of the queue"


# ── P0-4 · artifact: null and nearest: [] crashed the whole workspace ───────

def test_artifact_is_a_typed_absence_and_never_null(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    row = _first_row(client, qid)
    d = client.get(f"/api/review/queues/{qid}/items/{row['id']}").json()

    assert d["artifact"] is not None, \
        "artifact: null is what `d.artifact.level` crashed on"
    assert d["artifact"]["computed"] is False, \
        "nothing computes artifact factors yet — say so, do not invent a number"
    for key in ("level", "p", "coherence"):
        assert d["artifact"][key] is None, \
            f"artifact.{key} must be an explicit absence, never a plausible value"
    for key in ("clipping", "stepChange", "electrodeFlag"):
        assert isinstance(d["artifact"][key], str) and d["artifact"][key], \
            f"artifact.{key} must render as words the reviewer can read"
    assert "reason" in d["artifact"]


def test_nearest_families_are_an_explicit_not_computed(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    row = _first_row(client, qid)
    d = client.get(f"/api/review/queues/{qid}/items/{row['id']}").json()
    assert isinstance(d["nearest"], list)
    assert d["nearestComputed"] is False, \
        "an empty `nearest` must be distinguishable from 'no families are near'"


# ── P1-6 · held-out recordings counted but never served ────────────────────

def test_held_out_rows_are_not_counted(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info, name="held only",
                    filters={"run_id": info["held_run"]})
    qid = q["queue"]["id"]
    data = client.get(f"/api/review/queues/{qid}").json()
    assert data["rows"] == [], "a held-out recording is refused, not listed"
    assert data["queue"]["total"] == 0, \
        "a row that is never served is not part of the question being put"
    assert data["queue"]["total"] == data["queue"]["judged"] + data["queue"]["remaining"]

    counts = client.get("/api/review/counts").json()
    per = {str(x["id"]): x["remaining"] for x in counts["by_queue"]}
    assert per[str(qid)] == 0, "'N need you' must never count an item nobody can be shown"
    assert counts["need_you"] == sum(x["remaining"] for x in counts["by_queue"])


def test_verdict_on_a_held_out_detection_is_refused(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info, name="held only",
                    filters={"run_id": info["held_run"]})
    qid = q["queue"]["id"]
    before = _rows(rt, "adjudications")
    r = client.post(f"/api/review/queues/{qid}/verdict",
                    json={"target_id": info["held_detection"],
                          "verdict": "interesting", "note": "should not land"})
    assert r.status_code == 409, r.text
    assert "held out (D6)" in r.text
    assert _rows(rt, "adjudications") == before, \
        "the read routes refuse a held-out item; the write route must agree"


def test_batch_and_promote_refuse_a_held_out_detection(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info, name="held only",
                    filters={"run_id": info["held_run"]})
    qid = q["queue"]["id"]
    before = _rows(rt, "adjudications")
    b = client.post(f"/api/review/queues/{qid}/batch",
                    json={"target_ids": info["held_detections"], "verdict": "seed"})
    assert b.status_code == 409, b.text
    p = client.post(f"/api/review/queues/{qid}/promote",
                    json={"target_id": info["held_detection"], "verdict": "seed"})
    assert p.status_code == 409, p.text
    assert _rows(rt, "adjudications") == before
    assert _rows(rt, "motif_member") == 0, "D6 must hold at the Library door too"


# ── P1-5 · no unpromote route, so a promotion could not be taken back ──────

def test_unpromote_route_reverses_both_halves(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    row = _first_row(client, qid)
    p = client.post(f"/api/review/queues/{qid}/promote",
                    json={"target_id": row["id"], "verdict": "seed"})
    assert p.status_code == 200, p.text
    got = p.json()

    u = client.post(f"/api/review/queues/{qid}/unpromote",
                    json={"audit_id": got["audit_id"]})
    assert u.status_code == 200, u.text
    assert _query(rt, "SELECT id FROM motif_entry WHERE id = ?", (got["entry_id"],)) == []
    assert _query(rt, "SELECT id FROM motif_member WHERE id = ?", (got["member_id"],)) == []
    assert _query(rt, "SELECT detection_id FROM adjudications WHERE detection_id = ?",
                  (int(row["id"]),)) == [], \
        "the verdict that created the Library row goes back with it"


def test_undo_of_a_promotion_takes_the_library_row_back(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    row = _first_row(client, qid)
    got = client.post(f"/api/review/queues/{qid}/promote",
                      json={"target_id": row["id"], "verdict": "seed"}).json()

    undo = client.post(f"/api/review/queues/{qid}/undo")
    assert undo.status_code == 200, undo.text
    assert _query(rt, "SELECT id FROM motif_member WHERE id = ?", (got["member_id"],)) == [], \
        "Ctrl-Z on a promotion must remove the Library row, not report a success it did not do"
    assert _query(rt, "SELECT detection_id FROM adjudications WHERE detection_id = ?",
                  (int(row["id"]),)) == []


# ── P2 · three cluster routes that could only ever 404 ─────────────────────

def test_cluster_routes_say_the_queue_has_no_clusters(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    for r in (client.get(f"/api/review/queues/{qid}/cluster/0"),
              client.post(f"/api/review/queues/{qid}/cluster/0/accept"),
              client.post(f"/api/review/queues/{qid}/cluster/0/reject")):
        assert r.status_code == 404, r.text
        assert "no clusters" in r.json()["detail"], \
            "say plainly that this queue kind produces no clusters: 'no cluster 0' reads as a bad number"


# ── P2 · tags: the bridge sent a list, both core writers expect a dict ─────

def test_tags_sent_as_a_list_are_written(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    row = _first_row(client, qid)
    r = client.post(f"/api/review/queues/{qid}/verdict",
                    json={"target_id": row["id"], "verdict": "seed",
                          "tags": ["sharkfin", "clean"]})
    assert r.status_code == 200, r.text
    assert _rows(rt, "adjudication_tags") == 2, "a tagged verdict must keep its tags"


def test_an_unknown_tag_is_a_400_and_writes_nothing(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    row = _first_row(client, qid)
    before = _rows(rt, "adjudications")
    r = client.post(f"/api/review/queues/{qid}/verdict",
                    json={"target_id": row["id"], "verdict": "seed",
                          "tags": ["not-in-the-vocabulary"]})
    assert r.status_code == 400, r.text
    assert _rows(rt, "adjudications") == before, "a refused tag must not half-write the verdict"


# ── P2 · a CHECK violation is a client input error, not a server fault ─────

def test_check_constraint_violation_is_a_400(seeded):
    client, rt, info = seeded
    r = client.post("/api/review/queues",
                    json={"name": "bad", "source_kind": "discovery-run",
                          "writes_to": "detections"})
    assert r.status_code == 400, r.text
    assert "writes_to" in r.text


# ── P3 · include_prior_judged was computed in the core and stranded there ──

def test_include_prior_judged_serves_the_rediscovery(seeded):
    client, rt, info = seeded
    det = info["detections"][0]
    span = _query(rt, "SELECT start_idx, end_idx FROM detections WHERE id = ?", (det,))[0]
    _exec(rt, "INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, "
              "source, created_at) VALUES (?, ?, ?, 'interesting', 'manual_ui', "
              "'2026-09-22T09:00:00')",
          (info["recordings"][0], span[0], span[1]))

    q = _make_queue(client, info, name="rediscovery",
                    filters={"run_id": info["runs"][0]})
    qid = q["queue"]["id"]
    default = client.get(f"/api/review/queues/{qid}").json()
    assert all(r["id"] != str(det) for r in default["rows"]), \
        "a rediscovery is not put to the researcher twice"

    asked = client.get(f"/api/review/queues/{qid}?include_prior_judged=1").json()
    hit = [r for r in asked["rows"] if r["id"] == str(det)]
    assert hit, "there must be a way to see what was auto-excluded"
    assert hit[0]["prior_verdict"] == "interesting"
    item = client.get(f"/api/review/queues/{qid}/items/{det}")
    assert item.status_code == 200, item.text


# ── P3 · the served channel contradicted the queue's own title ─────────────

def test_channel_label_agrees_with_the_source_file(seeded):
    client, rt, info = seeded
    q = _make_queue(client, info, name="drop_detection_v1 - Mushroom_260720 CH14",
                    filters={"run_id": info["ch14_run"]})
    rows = client.get(f"/api/review/queues/{q['queue']['id']}").json()["rows"]
    assert rows, "the CH14 run must resolve"
    assert rows[0]["channel"] == "CH14", \
        "a single-channel export names its electrode in the file; do not derive a different one"


def test_every_row_carries_the_run_id_and_its_rank(seeded):
    """fixup-a item 7: the inspector subtitle read
    `run undefined - rank undefined of 30 by score` on every item.

    `review_queues.source_ref` is NULL for a queue whose filters name the run
    (`{"run_id": 32}` in the live database), and nothing ever computed a rank,
    so both clauses printed the literal word `undefined` to a reader. The run
    id is on the item, and the rank is its 1-based position in the queue's own
    order - the same list `total` counts."""
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    body = client.get(f"/api/review/queues/{qid}").json()
    rows = body["rows"]
    assert rows
    assert [r["rank"] for r in rows] == list(range(1, len(rows) + 1))
    assert all(r.get("runId") for r in rows), "a detection knows the run that wrote it"
    assert max(r["rank"] for r in rows) <= body["queue"]["total"], "a rank outside its own denominator"

    one = client.get(f"/api/review/queues/{qid}/items/{rows[0]['id']}").json()
    assert one["entry"]["rank"] == rows[0]["rank"] and one["entry"]["runId"] == rows[0]["runId"]
    assert one["evidence"]["origin"]["runId"], "the provenance panel's run id was the same gap"


def test_the_queue_payload_carries_a_measured_pace(seeded):
    """fixup-a item 8: `paceS` was hardcoded null on the client, so "pace not
    yet measured" was permanent. It is measured off `review_audit` now, and it
    is still None until there are two gestures to measure between."""
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    assert q["queue"]["pace_s"] is None, "no judging yet: an unmeasured pace says so"
    rows = client.get(f"/api/review/queues/{qid}").json()["rows"]
    for row in rows[:3]:
        assert client.post(f"/api/review/queues/{qid}/verdict",
                           json={"target_id": row["id"], "verdict": "interesting"}).status_code == 200
    pace = client.get(f"/api/review/queues/{qid}").json()["queue"]["pace_s"]
    assert pace is not None and pace >= 0.0, "three verdicts are two intervals"


def test_a_tagged_verdict_comes_back_on_the_queue_row(seeded):
    """fixup-a item 9: the Annotate card's tags were a session label - no
    component passed them - and the round trip was not open either: a queue
    row's `tags` were always empty, so even a tag written through the route
    was invisible on the next read and the card lost it on reload."""
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    row = _first_row(client, qid)
    assert client.post(f"/api/review/queues/{qid}/verdict",
                       json={"target_id": row["id"], "verdict": "interesting",
                             "tags": ["sharkfin", "clean"]}).status_code == 200
    again = [r for r in client.get(f"/api/review/queues/{qid}").json()["rows"] if r["id"] == row["id"]]
    assert again, "the judged row is still in the queue (include_judged defaults to 1)"
    assert set(again[0]["tags"]) == {"sharkfin", "clean"}


def test_the_settings_vocabulary_route_serves_what_the_annotate_card_offers(seeded):
    """The card's suggestions must be terms the write path will accept: an
    unknown tag is a 400 that refuses the whole verdict, so offering a
    fixture-era word would make the verdict unwritable (fixup-a item 9)."""
    client, rt, info = seeded
    got = client.get("/api/settings/vocabulary")
    assert got.status_code == 200, got.text
    tags = got.json()["tags"]
    assert tags and all({"category", "value", "active"} <= set(t) for t in tags)
    assert "sharkfin" in {t["value"] for t in tags if t["active"]}


# ── fixup-b: Review draws millivolts off the declared unit ─────────────────

def test_the_candidate_context_is_millivolts_off_a_volts_recording(seeded):
    """The seed channel is `0.2 sin + 0.02 cos` stored as if volts, on
    `M2_aug_concat_fs1.mat` — declared volts by the schema backfill. The
    context the inspector draws is that x 1000; before fixup-b it was the
    stored volts under an "mV" axis."""
    client, rt, info = seeded
    q = _make_queue(client, info)
    qid = q["queue"]["id"]
    row = client.get(f"/api/review/queues/{qid}").json()["rows"][0]
    d = client.get(f"/api/review/queues/{qid}/items/{row['id']}").json()
    vals = [v for v in d["context"]["values"] if v is not None]
    assert vals and max(abs(v) for v in vals) > 10.0, "millivolts, not volts labelled mV"
    assert max(abs(v) for v in vals) <= 221.0, "and not converted twice (0.22 V peak -> 220 mV)"
