"""
test_webui_span_edit.py
=======================
edit-span (2026-10-18): Review's *Edit span in Explore* opens a live editor
over `GET/POST /api/explore/span-edit/{id}`.

The save rule, which is the heart of this file (CLAUDE.md rule 5 — detections
are machine-only, annotations are human-only):

* the item is a Library **member** → a human `annotations` row with the
  corrected span, then a `motif_member_revision` pointing at it, made current;
* the item is a plain **detection** → a human `annotations` row with the
  corrected span and the item's verdict (``seed`` when it has none);
* in BOTH cases the `detections` row is byte-identical before and after.

FastAPI lives only in `webui/.venv`, so under the conda `pytest` this file
skips; run it with

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_span_edit.py
"""

import json
import os
import sqlite3
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

from Working.database.schema import init_db  # noqa: E402
from Working.library import revisions as revisions_mod  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import HELD_OUT_FILE, Runtime  # noqa: E402

FS = 1.0
N = 20000


def _channel(dir_path, name):
    t = np.arange(N, dtype=float)
    path = os.path.join(dir_path, f"{name}.npy")
    np.save(path, (0.2 * np.sin(t / 97.0)).astype(np.float32))
    return path


def _seed(tmp_path):
    npy = tmp_path / "npy"
    npy.mkdir()
    (tmp_path / "db").mkdir()
    db = tmp_path / "db" / "annotations.sqlite"
    conn = init_db(str(db))
    rec = conn.execute(
        "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
        "VALUES ('M2_aug_concat_fs1.mat', 0, ?, ?, 0, ?, 'mV')", (FS, N, _channel(str(npy), "c0"))).lastrowid
    held = conn.execute(
        "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
        "VALUES (?, 0, ?, ?, 0, ?, 'mV')", (HELD_OUT_FILE, FS, N, _channel(str(npy), "held"))).lastrowid
    cfg = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) "
                       "VALUES ('cfg-span-edit', '{}', '2026-10-18T09:00:00')").lastrowid

    def run(rid):
        return conn.execute(
            "INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
            "VALUES (?, ?, 0, ?, '2026-10-18T09:00:00', 'ok')", (cfg, rid, N)).lastrowid

    r = run(rec)
    det = lambda run_id, a, b: conn.execute(  # noqa: E731
        "INSERT INTO detections (run_id, start_idx, end_idx, score, meta_json) VALUES (?, ?, ?, 0.8, ?)",
        (run_id, a, b, json.dumps({"k": 1}))).lastrowid
    plain = det(r, 1000, 1040)          # a plain detection, judged 'interesting'
    unjudged = det(r, 3000, 3030)       # a plain detection nobody has judged
    member_det = det(r, 5000, 5050)     # a detection that is a Library member
    held_det = det(run(held), 700, 760)
    conn.execute("INSERT INTO adjudications (detection_id, verdict, note, created_at) "
                 "VALUES (?, 'interesting', NULL, '2026-10-18T09:00:00')", (plain,))
    entry = conn.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx, detection_id, created_at) "
                         "VALUES (?, 5000, 5050, ?, '2026-10-18T09:00:00')", (rec, member_det)).lastrowid
    member = conn.execute("INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx) "
                          "VALUES (?, ?, 5000, 5050)", (entry, rec)).lastrowid
    revisions_mod.add_revision(conn, member, origin="machine", start_idx=5000, end_idx=5050,
                               detection_id=member_det, commit=False)
    conn.commit()
    conn.close()
    return {"db": str(db), "rec": rec, "plain": plain, "unjudged": unjudged, "member_det": member_det,
            "member": member, "held_det": held_det}


@pytest.fixture()
def seeded(tmp_path):
    info = _seed(tmp_path)
    rt = Runtime("sandbox", stamp="test-span-edit", db_source=info["db"],
                 runtime_root=str(tmp_path / "runtime")).setup()
    app = create_app(rt)
    with TestClient(app) as client:
        yield client, rt, info
    rt.restore()


def _q(rt, sql, args=()):
    conn = sqlite3.connect(rt.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return [tuple(r) for r in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def _detections(rt):
    """Every detections row, every column — the byte-identical check."""
    return _q(rt, "SELECT * FROM detections ORDER BY id")


# ── GET ──────────────────────────────────────────────────────────────────────

def test_get_plain_detection_has_no_member_and_carries_its_verdict(seeded):
    client, rt, info = seeded
    r = client.get(f"/api/explore/span-edit/{info['plain']}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["recording_id"] == info["rec"]
    assert d["fs"] == FS
    assert d["detection"] == {"start_idx": 1000, "end_idx": 1040}
    assert d["member"] is None
    assert d["verdict"] == "interesting"
    # the context is ±2 lengths of the span (40 samples → 80 either side), with its time axis
    ctx = d["context_trace"]
    assert ctx["t0_s"] == pytest.approx(920.0) and ctx["t1_s"] == pytest.approx(1120.0)
    assert ctx["v"] and len(ctx["t"]) == len(ctx["v"])


def test_get_member_detection_returns_the_member_and_its_current_revision(seeded):
    client, rt, info = seeded
    r = client.get(f"/api/explore/span-edit/{info['member_det']}")
    assert r.status_code == 200, r.text
    m = r.json()["member"]
    assert m is not None
    assert m["ref"] == f"m-{info['member']}"
    assert m["current"] == {"start_idx": 5000, "end_idx": 5050, "revision_no": 1}
    assert r.json()["verdict"] is None


def test_get_by_member_ref_answers_the_same_member(seeded):
    client, rt, info = seeded
    r = client.get(f"/api/explore/span-edit/m-{info['member']}")
    assert r.status_code == 200, r.text
    assert r.json()["member"]["ref"] == f"m-{info['member']}"


def test_get_unknown_and_held_out_are_refused(seeded):
    client, rt, info = seeded
    assert client.get("/api/explore/span-edit/999999").status_code == 404
    held = client.get(f"/api/explore/span-edit/{info['held_det']}")
    assert held.status_code == 423, held.text
    assert "held out" in held.json()["detail"]


# ── POST: the save rule ──────────────────────────────────────────────────────

def test_post_on_member_writes_a_revision_and_never_the_detection(seeded):
    client, rt, info = seeded
    before = _detections(rt)
    n_ann = _q(rt, "SELECT COUNT(*) FROM annotations")[0][0]
    r = client.post(f"/api/explore/span-edit/{info['member_det']}",
                    json={"start_idx": 4995, "end_idx": 5060, "note": "onset was late"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["kind"] == "revision"
    assert out["revision"]["revision_no"] == 2
    assert out["revision"]["start_idx"] == 4995 and out["revision"]["end_idx"] == 5060

    conn = sqlite3.connect(rt.db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = revisions_mod.current_revision(conn, info["member"])
        assert (cur["revision"], cur["start_idx"], cur["end_idx"], cur["origin"]) == (2, 4995, 5060, "human")
        assert cur["detection_id"] is None and cur["annotation_id"] is not None
        assert revisions_mod.matching_revision(conn, info["member"])["start_idx"] == 5000  # rev 1 kept
    finally:
        conn.close()
    # the human claim behind the revision is an annotation (rule 5). The member had no verdict, and a span
    # correction is not one: `unsure` (seed is not a member's question, and would judge it "yes" by extent)
    ann = _q(rt, "SELECT start_idx, end_idx, verdict, source, note FROM annotations ORDER BY id DESC LIMIT 1")[0]
    assert ann[:4] == (4995, 5060, "unsure", "review-span-edit")
    assert ann[4].startswith("onset was late")
    assert _q(rt, "SELECT COUNT(*) FROM annotations")[0][0] == n_ann + 1
    assert _detections(rt) == before, "rule 5: a span edit must never touch the detections row"

    # and GET now reads the new current revision
    again = client.get(f"/api/explore/span-edit/{info['member_det']}").json()
    assert again["member"]["current"] == {"start_idx": 4995, "end_idx": 5060, "revision_no": 2}


def test_post_on_plain_detection_writes_an_annotation_with_its_verdict(seeded):
    client, rt, info = seeded
    before = _detections(rt)
    n_rev = _q(rt, "SELECT COUNT(*) FROM motif_member_revision")[0][0]
    r = client.post(f"/api/explore/span-edit/{info['plain']}", json={"start_idx": 998, "end_idx": 1045, "note": None})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["kind"] == "annotation"
    assert out["annotation"]["verdict"] == "interesting"
    ann = _q(rt, "SELECT recording_id, start_idx, end_idx, verdict, source FROM annotations WHERE id = ?",
             (out["annotation"]["id"],))[0]
    assert ann == (info["rec"], 998, 1045, "interesting", "review-span-edit")
    assert _detections(rt) == before, "rule 5: a span edit must never touch the detections row"
    assert _q(rt, "SELECT COUNT(*) FROM motif_member_revision")[0][0] == n_rev


def test_post_on_unjudged_detection_writes_seed(seeded):
    client, rt, info = seeded
    r = client.post(f"/api/explore/span-edit/{info['unjudged']}", json={"start_idx": 2990, "end_idx": 3035})
    assert r.status_code == 200, r.text
    assert r.json()["annotation"]["verdict"] == "seed"


@pytest.mark.parametrize("span, word", [
    ((-5, 40), "outside"),
    ((19990, 20010), "outside"),
    ((1000, 1001), "two samples"),
    ((1040, 1000), "two samples"),
])
def test_post_refuses_bad_spans(seeded, span, word):
    client, rt, info = seeded
    before = _q(rt, "SELECT COUNT(*) FROM annotations")[0][0]
    r = client.post(f"/api/explore/span-edit/{info['plain']}", json={"start_idx": span[0], "end_idx": span[1]})
    assert r.status_code == 422, r.text
    assert word in r.json()["detail"]
    assert _q(rt, "SELECT COUNT(*) FROM annotations")[0][0] == before


def test_post_refuses_held_out(seeded):
    client, rt, info = seeded
    before = _q(rt, "SELECT COUNT(*) FROM annotations")[0][0]
    r = client.post(f"/api/explore/span-edit/{info['held_det']}", json={"start_idx": 700, "end_idx": 770})
    assert r.status_code == 423, r.text
    assert _q(rt, "SELECT COUNT(*) FROM annotations")[0][0] == before


def test_post_member_span_not_overlapping_rev1_is_refused_and_writes_nothing(seeded):
    client, rt, info = seeded
    n_ann = _q(rt, "SELECT COUNT(*) FROM annotations")[0][0]
    n_rev = _q(rt, "SELECT COUNT(*) FROM motif_member_revision")[0][0]
    r = client.post(f"/api/explore/span-edit/{info['member_det']}", json={"start_idx": 8000, "end_idx": 8050})
    assert r.status_code == 422, r.text
    assert _q(rt, "SELECT COUNT(*) FROM annotations")[0][0] == n_ann
    assert _q(rt, "SELECT COUNT(*) FROM motif_member_revision")[0][0] == n_rev


# ── critic round (2026-10-18) ────────────────────────────────────────────────

def _write(rt, sql, args=()):
    conn = sqlite3.connect(rt.db_path)
    try:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def test_an_unjudged_member_edit_leaves_the_member_unjudged(seeded):
    """Redrawing a span is not a verdict: the member the Library and Review counted unjudged stays so."""
    from Working.library import verdicts as LV

    client, rt, info = seeded
    r = client.post(f"/api/explore/span-edit/m-{info['member']}", json={"start_idx": 4998, "end_idx": 5052})
    assert r.status_code == 200, r.text
    assert r.json()["annotation"]["verdict"] == "unsure"
    conn = sqlite3.connect(rt.db_path)
    conn.row_factory = sqlite3.Row
    try:
        got = LV.member_verdicts(conn, [{"member_id": info["member"], "recording_id": info["rec"],
                                         "start_idx": 5000, "end_idx": 5050}])
    finally:
        conn.close()
    assert got[info["member"]]["judged"] is False
    # no seed row: nothing enters the Explore spans queue
    assert _q(rt, "SELECT COUNT(*) FROM annotations WHERE verdict = 'seed'")[0][0] == 0


def test_a_member_of_an_entry_is_not_given_the_entrys_detection(seeded):
    """`motif_entry.detection_id` is the detection the ENTRY came from. Another member of that entry,
    somewhere else on the channel, is not that detection: it must not borrow its span, its verdict, or
    write it as the provenance of its machine rev 1."""
    client, rt, info = seeded
    _write(rt, "INSERT INTO adjudications (detection_id, verdict, note, created_at) "
               "VALUES (?, 'not_interesting', NULL, '2026-10-18T09:00:00')", (info["member_det"],))
    entry = _q(rt, "SELECT entry_id FROM motif_member WHERE id = ?", (info["member"],))[0][0]
    other = _write(rt, "INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx) "
                       "VALUES (?, ?, 12000, 12050)", (entry, info["rec"]))
    d = client.get(f"/api/explore/span-edit/m-{other}").json()
    assert d["detection_id"] is None and d["detection"] is None
    assert d["verdict"] is None
    assert d["member"]["current"] == {"start_idx": 12000, "end_idx": 12050, "revision_no": 0}
    r = client.post(f"/api/explore/span-edit/m-{other}", json={"start_idx": 11990, "end_idx": 12060})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["seeded_rev1"] is True and out["revision"]["revision_no"] == 2
    assert out["annotation"]["verdict"] == "unsure"
    rev1 = _q(rt, "SELECT origin, detection_id, start_idx, end_idx FROM motif_member_revision "
                  "WHERE member_id = ? AND revision = 1", (other,))[0]
    assert rev1 == ("machine", None, 12000, 12050)


def test_a_legacy_span_relative_detection_is_read_and_saved_channel_absolute(seeded):
    """A detection written by a spanned run before 2026-09-21 is span-relative; the editor must open it
    where Explore and Review draw it."""
    client, rt, info = seeded
    cfg = _q(rt, "SELECT id FROM configs LIMIT 1")[0][0]
    run = _write(rt, "INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
                     "VALUES (?, ?, 10000, 15000, '2026-10-18T09:00:00', 'ok')", (cfg, info["rec"]))
    det = _write(rt, "INSERT INTO detections (run_id, start_idx, end_idx, score, meta_json) "
                     "VALUES (?, 500, 540, 0.5, '{}')", (run,))
    d = client.get(f"/api/explore/span-edit/{det}").json()
    assert d["detection"] == {"start_idx": 10500, "end_idx": 10540}
    assert d["context_trace"]["t0_s"] == pytest.approx(10420.0)
    before = _detections(rt)
    r = client.post(f"/api/explore/span-edit/{det}", json={"start_idx": 10498, "end_idx": 10545})
    assert r.status_code == 200, r.text
    assert _q(rt, "SELECT start_idx, end_idx FROM annotations WHERE id = ?",
              (r.json()["annotation"]["id"],))[0] == (10498, 10545)
    assert _detections(rt) == before


def test_a_second_member_save_is_revision_three(seeded):
    client, rt, info = seeded
    for a, b in ((4995, 5060), (4990, 5055)):
        r = client.post(f"/api/explore/span-edit/{info['member_det']}", json={"start_idx": a, "end_idx": b})
        assert r.status_code == 200, r.text
    assert r.json()["revision"]["revision_no"] == 3
    got = client.get(f"/api/explore/span-edit/m-{info['member']}").json()["member"]["current"]
    assert got == {"start_idx": 4990, "end_idx": 5055, "revision_no": 3}
