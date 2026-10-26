"""
test_candidate_events_exam.py
=============================
m4-exam (2026-10-26): the ONE deliberate door through which the held-out recording (M4_aug) becomes a candidate-event
table, a stratified sample and a blind Review queue — the researcher's one-shot exam.

In plain words: the builder refuses M4 by name. It still does, unless it is handed the exam's frozen manifest: a file
whose sha256 the caller names, that says it is the held-out exam for this very recording, and whose freeze is already
in the audit log (so the rules were written down before the sample was drawn). Creating the exam's queue writes an
audit entry of its own ("held-out exam: sample drawn"). Nothing else about the lock changes.

Pinned:

* without a manifest, or with a wrong hash, an edited file, a manifest for another recording, or no freeze row in the
  audit log, M4 is refused exactly as before (``PermissionError``);
* with a valid one, the table builds and its meta names the manifest;
* the sample's queue is refused for an M4 sample without the manifest, and with it is created blind and audited once;
* the script's ``build``/``queue`` take ``--exam-manifest``/``--exam-sha256`` and refuse M4 without them.

Run from the project root:
    python -m pytest tests/test_candidate_events_exam.py -q
"""

import hashlib
import importlib.util
import json
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

from Working.config import HELD_OUT_RECORDING_FILE
from Working.database.schema import init_db
from Working.database import queries as q
from Working.database import vocabulary as v
from Working.discovery import candidate_events as ce
from Working.registration.settings import append_audit
from Working.review import queues as qs

N = 100_000
T = "2026-10-26T00:00:00"
M4 = HELD_OUT_RECORDING_FILE


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _populate(conn, source_file=M4):
    v.seed_vocabulary(conn)
    rid = q.insert_recording(conn, source_file, 0, 1.0, N, 0, f"data/{source_file}/CH0.npy")
    sid = conn.execute("INSERT INTO discovery_sessions (name, source_file, channels_json, created_at, updated_at) "
                       "VALUES ('screen', ?, '[]', ?, ?)", (source_file, T, T)).lastrowid
    for k, (variant, spans) in enumerate([("noise_threshold", [(1000 * i, 1000 * i + 100) for i in range(30)]),
                                          ("drop_detection_v1", [(5000, 5100)])]):
        gid = conn.execute("INSERT INTO run_groups (created_at) VALUES (?)", (T,)).lastrowid
        cid = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES (?, '{}', ?)",
                           (f"c{k}", T)).lastrowid
        run = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, "
                           "run_group_id) VALUES (?, ?, 0, ?, ?, 'completed', ?)", (cid, rid, N, T, gid)).lastrowid
        for s, e in spans:
            conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, 1.0)",
                         (run, s, e))
        conn.execute("INSERT INTO discovery_runs (session_id, run_key, kind, label, template_name, run_group_id, "
                     "status, created_at, updated_at) VALUES (?, ?, 'template', ?, ?, ?, 'done', ?, ?)",
                     (sid, f"k{k}", variant, variant, gid, T, T))
    conn.commit()
    return rid


def _manifest(tmp_path, source_file=M4, **extra):
    path = str(tmp_path / "manifest.json")
    body = {"exam": "held_out", "frozen": True, "source_file": source_file, "frozen_at": T} | extra
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(body, fh)
    return path


def _freeze(conn, sha):
    return append_audit(conn, ce.EXAM_AUDIT_KIND, f"{ce.EXAM_FROZEN} · {sha}", "Datasets", route="exam/M4",
                        detail={"sha256": sha, "source_file": M4})


def _ready(tmp_path):
    conn = init_db(":memory:")
    _populate(conn)
    path = _manifest(tmp_path)
    sha = _sha(path)
    _freeze(conn, sha)
    return conn, ce.ExamManifest(path, sha)


# ── the builder ─────────────────────────────────────────────────────────────

def test_m4_is_still_refused_without_a_manifest():
    conn = init_db(":memory:")
    _populate(conn)
    with pytest.raises(PermissionError):
        ce.build_table(conn, M4)
    with pytest.raises(PermissionError):
        ce.load_sweep_detections(conn, M4)


def test_m4_is_accepted_with_the_frozen_manifest_and_the_table_names_it(tmp_path):
    conn, exam = _ready(tmp_path)
    events, members, meta = ce.build_table(conn, M4, exam=exam)
    assert len(events) == 30
    assert meta["exam"]["sha256"] == exam.sha256 and meta["exam"]["manifest"] == os.path.abspath(exam.path)


def test_a_wrong_hash_is_refused(tmp_path):
    conn, exam = _ready(tmp_path)
    with pytest.raises(PermissionError, match="sha256"):
        ce.build_table(conn, M4, exam=ce.ExamManifest(exam.path, "0" * 64))


def test_a_manifest_edited_after_its_freeze_is_refused(tmp_path):
    conn, exam = _ready(tmp_path)
    with open(exam.path, "a", encoding="utf-8") as fh:
        fh.write(" ")
    with pytest.raises(PermissionError):
        ce.build_table(conn, M4, exam=exam)


def test_a_manifest_whose_freeze_is_not_in_the_audit_log_is_refused(tmp_path):
    conn = init_db(":memory:")
    _populate(conn)
    path = _manifest(tmp_path)
    with pytest.raises(PermissionError, match="audit"):
        ce.build_table(conn, M4, exam=ce.ExamManifest(path, _sha(path)))


@pytest.mark.parametrize("extra", [{"source_file": "M2_aug_concat_fs1.mat"}, {"frozen": False}, {"exam": "demo"}])
def test_a_manifest_for_another_exam_is_refused(tmp_path, extra):
    conn = init_db(":memory:")
    _populate(conn)
    path = _manifest(tmp_path, **extra)
    sha = _sha(path)
    _freeze(conn, sha)
    with pytest.raises(PermissionError):
        ce.build_table(conn, M4, exam=ce.ExamManifest(path, sha))


def test_another_recording_needs_no_manifest():
    conn = init_db(":memory:")
    _populate(conn, source_file="rec.mat")
    events, _members, meta = ce.build_table(conn, "rec.mat")
    assert len(events) == 30 and meta.get("exam") is None


# ── the queue ───────────────────────────────────────────────────────────────

def test_an_m4_sample_s_queue_is_refused_without_the_manifest(tmp_path):
    conn, exam = _ready(tmp_path)
    events, _m, _meta = ce.build_table(conn, M4, exam=exam)
    s = ce.draw_sample(events, seed=1, per_level=10, per_family=5)
    with pytest.raises(PermissionError):
        ce.create_sample_queue(conn, s, name="exam")
    assert conn.execute("SELECT COUNT(*) FROM review_queues").fetchone()[0] == 0


def test_the_exam_queue_is_blind_and_its_drawing_is_audited_once(tmp_path):
    conn, exam = _ready(tmp_path)
    events, _m, _meta = ce.build_table(conn, M4, exam=exam)
    s = ce.draw_sample(events, seed=1, per_level=10, per_family=5)
    qid = ce.create_sample_queue(conn, s, name="exam", exam=exam)
    queue = qs.get_queue(conn, qid)
    assert queue["blind"] == 1
    rows = conn.execute("SELECT what, detail_json FROM audit_log WHERE kind = ? AND what LIKE ?",
                        (ce.EXAM_AUDIT_KIND, ce.EXAM_SAMPLE_DRAWN + "%")).fetchall()
    assert len(rows) == 1
    detail = json.loads(rows[0][1])
    assert detail["queue_id"] == qid and detail["sha256"] == exam.sha256 and detail["n_items"] == len(s)
    assert ce.create_sample_queue(conn, s, name="exam", exam=exam) == qid
    assert conn.execute("SELECT COUNT(*) FROM audit_log WHERE what LIKE ?",
                        (ce.EXAM_SAMPLE_DRAWN + "%",)).fetchone()[0] == 1


# ── the script ──────────────────────────────────────────────────────────────

def _script():
    spec = importlib.util.spec_from_file_location("rq1b_candidate_events_exam_script",
                                                  os.path.join(PROJECT_ROOT, "scripts", "rq1b_candidate_events.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_script_builds_and_queues_m4_only_with_the_manifest(tmp_path, capsys):
    db = str(tmp_path / "copy.sqlite")
    conn = init_db(db)
    _populate(conn)
    path = _manifest(tmp_path)
    sha = _sha(path)
    _freeze(conn, sha)
    conn.close()
    mod = _script()
    real = str(tmp_path / "the-real.sqlite")
    out = str(tmp_path / "tables")
    with pytest.raises(PermissionError):
        mod.main(["build", "--db", db, "--file", M4, "--out", out], real=real)
    capsys.readouterr()
    assert mod.main(["build", "--db", db, "--file", M4, "--out", out, "--exam-manifest", path, "--exam-sha256", sha,
                     "--json"], real=real) == 0
    table = json.loads(capsys.readouterr().out)["table"]
    with pytest.raises(PermissionError):
        mod.main(["queue", "--table", table, "--db", db, "--apply", "--per-level", "5", "--per-family", "2"],
                 real=real)
    capsys.readouterr()
    assert mod.main(["queue", "--table", table, "--db", db, "--apply", "--per-level", "5", "--per-family", "2",
                     "--exam-manifest", path, "--exam-sha256", sha, "--json"], real=real) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["queue_id"] is not None
    c = sqlite3.connect(db)
    assert c.execute("SELECT COUNT(*) FROM audit_log WHERE what LIKE ?",
                     (ce.EXAM_SAMPLE_DRAWN + "%",)).fetchone()[0] == 1
    c.close()
