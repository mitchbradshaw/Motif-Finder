"""
test_unseen_exam.py
===================
The second unseen-recording test (2026-10-26, researcher-approved): Adamatzky's *Schizophyllum commune*, sat by the
frozen models exactly as the held-out M4 exam is, but on a recording that is NOT held out — so no lock, the same
discipline. `scripts/m4_exam_freeze.py` and `scripts/m4_exam_score.py` are generalised behind ``--recording`` /
``--manifest``; M4's own path is unchanged (tests/test_m4_exam_score.py, tests/test_candidate_events_exam.py).

In plain words: before the researcher sees a single candidate, we write down which models sit the test, which
detector runs made the candidates (the frozen candidate table), how the ~300 questions are drawn and how the answers
are marked; we fingerprint that page and log the fingerprint. The draw and the marking then refuse to run against any
other page, any other table, or a draw made with other settings.

Pinned:

* `candidate_events.verify_exam` opens an *unseen* exam (``exam: "unseen"``) of a recording that is not held out only
  when the manifest hashes right, names that recording, and its freeze is in the audit log under
  ``EXAM_UNSEEN_FROZEN``; the held-out recording still takes only a ``held_out`` manifest;
* the unseen exam's queue is blind and its drawing is audited once (``EXAM_UNSEEN_SAMPLE_DRAWN``);
* `rq1b_candidate_events.py queue --exam-manifest` on an unseen exam refuses a table that is not the manifest's frozen
  frame, and a seed or quota that is not the manifest's design;
* `m4_exam_freeze.py --recording` writes an ``unseen`` manifest naming the frame table, the session's runs and their
  config hashes, the models (R4 and the reference CNNs inline, in amendment 1's shape), the design, the metrics and the
  known risks, plus the audit body to POST; it refuses the held-out recording, a session with no runs, a table whose
  runs are not the session's, and an existing manifest;
* `m4_exam_score.py --manifest <unseen>` verifies the freeze, refuses a sample drawn under another manifest or a table
  that is not the frame, scores MiniRocket and the inline CNNs, and writes results + a findings page under the
  manifest's own slug; the database is untouched.

Run from the project root:
    python -m pytest tests/test_unseen_exam.py -q
"""

import hashlib
import importlib.util
import json
import os
import sqlite3
import sys

import numpy as np
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
from Working.review.verdicts import write_verdict

N = 200_000
T = "2026-10-26T00:00:00"
SRC = "Some fungus.txt"            # a space in the name, as "Schizophyllum commune.txt" has
SEED, PER_LEVEL, PER_FAMILY = 7, 20, 6


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(PROJECT_ROOT, *rel.split("/")))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _freeze_mod():
    return _load("m4_exam_freeze_unseen_t", "scripts/m4_exam_freeze.py")


def _score_mod():
    return _load("m4_exam_score_unseen_t", "scripts/m4_exam_score.py")


def _script_mod():
    return _load("rq1b_candidate_events_unseen_t", "scripts/rq1b_candidate_events.py")


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _populate(conn, source_file=SRC):
    """Two detectors (one selective) on one channel of `source_file`, 60 events far apart, in one session."""
    v.seed_vocabulary(conn)
    rid = q.insert_recording(conn, source_file, 0, 1.0, N, 0, f"data/{source_file}/CH0.npy")
    sid = conn.execute("INSERT INTO discovery_sessions (name, source_file, channels_json, created_at, updated_at) "
                       "VALUES ('x_rq4', ?, '[]', ?, ?)", (source_file, T, T)).lastrowid
    for k, (variant, spans) in enumerate([("noise_threshold", [(3000 * i, 3000 * i + 100) for i in range(50)]),
                                          ("drop_detection_v1", [(160_000 + 3000 * i, 160_000 + 3000 * i + 100)
                                                                 for i in range(10)])]):
        gid = conn.execute("INSERT INTO run_groups (created_at) VALUES (?)", (T,)).lastrowid
        cid = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES (?, '{}', ?)",
                           (f"c{k}{source_file}", T)).lastrowid
        run = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, "
                           "run_group_id) VALUES (?, ?, 0, ?, ?, 'completed', ?)", (cid, rid, N, T, gid)).lastrowid
        for s, e in spans:
            conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, 1.0)",
                         (run, s, e))
        conn.execute("INSERT INTO discovery_runs (session_id, run_key, kind, label, template_name, run_group_id, "
                     "status, created_at, updated_at) VALUES (?, ?, 'template', ?, ?, ?, 'done', ?, ?)",
                     (sid, f"k{k}{sid}", variant, variant, gid, T, T))
    conn.commit()
    return rid, sid


def _write_manifest(tmp_path, body):
    path = str(tmp_path / "manifest.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(body, fh)
    return path


def _freeze_audit(conn, sha, source_file=SRC):
    return append_audit(conn, ce.EXAM_AUDIT_KIND, f"{ce.EXAM_UNSEEN_FROZEN} · {source_file} · sha256 {sha}",
                        "Datasets", route="exam/x", detail={"sha256": sha, "source_file": source_file})


def _fake_ckpt(tmp_path, name):
    p = tmp_path / f"{name}_fake.pth"
    p.write_bytes(name.encode() * 100)
    return {"path": str(p), "image_type": name, "sha256": _sha(str(p))}


def _exam_db(tmp_path, *, cnns=True):
    """The unseen recording's table built and frozen into a manifest (as the freeze script would), the freeze
    audited, the sample drawn through the script's door. Returns (db, conn, exam, sample, qid, where, table)."""
    db = str(tmp_path / "copy.sqlite")
    conn = init_db(db)
    _populate(conn)
    events, members, meta = ce.build_table(conn, SRC)
    table = ce.save_table(str(tmp_path / "tables"), events, members, meta)
    body = {"exam": "unseen", "frozen": True, "source_file": SRC, "name": "Some fungus unseen-recording exam",
            "slug": "x-exam", "frame": {"table_key": meta["key"]},
            "sampling_design": {"seed": SEED, "per_level": PER_LEVEL, "per_family": PER_FAMILY},
            "metrics": {"estimate_n_boot": 50, "estimate_seed": 0}}
    if cnns:
        body["cnns"] = {"models": {"reference_cnns": {"GASF": _fake_ckpt(tmp_path, "GASF")}}, "code": {},
                        "metrics": {"cut": 0.5}}
    man = _write_manifest(tmp_path, body)
    sha = _sha(man)
    _freeze_audit(conn, sha)
    exam = ce.ExamManifest(man, sha)
    sample = ce.draw_sample(events, seed=SEED, per_level=PER_LEVEL, per_family=PER_FAMILY)
    qid = ce.create_sample_queue(conn, sample, name="exam", exam=exam)
    smeta = {"name": "sample_x", "table_key": meta["key"], "source_file": SRC, "queue_id": qid,
             "exam": {"manifest": man, "sha256": sha}}
    where = ce.save_sample(table, sample, events[["event_id", "label", "label_kind", "label_basis", "label_refs",
                                                  "inside_interesting"]], smeta)
    return db, conn, exam, sample, qid, where, table


def _fake_scorer():
    rng = np.random.default_rng(0)

    def score(rows):
        return rng.normal(0, 1, len(rows)), np.ones(len(rows), bool)
    return score


def _fake_cnns(names, seed=1):
    rng = np.random.default_rng(seed)

    def make():
        def score(rows):
            return rng.uniform(0, 1, len(rows)), np.ones(len(rows), bool)
        return score
    return {n: make() for n in names}


# ── the door ────────────────────────────────────────────────────────────────

def test_an_unseen_exam_opens_only_with_its_frozen_audited_manifest(tmp_path):
    conn = init_db(":memory:")
    _populate(conn)
    path = _write_manifest(tmp_path, {"exam": "unseen", "frozen": True, "source_file": SRC})
    sha = _sha(path)
    with pytest.raises(PermissionError, match="audit"):
        ce.verify_exam(conn, ce.ExamManifest(path, sha), SRC)
    # a HELD-OUT freeze row does not open an unseen exam: the sentence is the unseen one
    append_audit(conn, ce.EXAM_AUDIT_KIND, f"{ce.EXAM_FROZEN} · {sha}", "Datasets", detail={"sha256": sha})
    with pytest.raises(PermissionError, match="audit"):
        ce.verify_exam(conn, ce.ExamManifest(path, sha), SRC)
    _freeze_audit(conn, sha)
    assert ce.verify_exam(conn, ce.ExamManifest(path, sha), SRC)["exam"] == "unseen"
    with pytest.raises(PermissionError, match="sha256"):
        ce.verify_exam(conn, ce.ExamManifest(path, "0" * 64), SRC)
    with pytest.raises(PermissionError):
        ce.verify_exam(conn, ce.ExamManifest(path, sha), "other.mat")


def test_the_held_out_recording_still_takes_only_a_held_out_manifest(tmp_path):
    conn = init_db(":memory:")
    _populate(conn, source_file=HELD_OUT_RECORDING_FILE)
    path = _write_manifest(tmp_path, {"exam": "unseen", "frozen": True, "source_file": HELD_OUT_RECORDING_FILE})
    sha = _sha(path)
    _freeze_audit(conn, sha, HELD_OUT_RECORDING_FILE)
    with pytest.raises(PermissionError):
        ce.build_table(conn, HELD_OUT_RECORDING_FILE, exam=ce.ExamManifest(path, sha))


def test_a_held_out_manifest_does_not_open_an_unseen_recording(tmp_path):
    conn = init_db(":memory:")
    _populate(conn)
    path = _write_manifest(tmp_path, {"exam": "held_out", "frozen": True, "source_file": SRC})
    sha = _sha(path)
    append_audit(conn, ce.EXAM_AUDIT_KIND, f"{ce.EXAM_FROZEN} · {sha}", "Datasets", detail={"sha256": sha})
    with pytest.raises(PermissionError):
        ce.verify_exam(conn, ce.ExamManifest(path, sha), SRC)


def test_the_unseen_exam_queue_is_blind_and_audited_once(tmp_path):
    db, conn, exam, sample, qid, where, table = _exam_db(tmp_path)
    assert qs.get_queue(conn, qid)["blind"] == 1
    rows = conn.execute("SELECT detail_json FROM audit_log WHERE kind = ? AND what LIKE ?",
                        (ce.EXAM_AUDIT_KIND, ce.EXAM_UNSEEN_SAMPLE_DRAWN + "%")).fetchall()
    assert len(rows) == 1
    d = json.loads(rows[0][0])
    assert d["queue_id"] == qid and d["sha256"] == exam.sha256 and d["n_items"] == len(sample)
    assert ce.create_sample_queue(conn, sample, name="exam", exam=exam) == qid
    assert conn.execute("SELECT COUNT(*) FROM audit_log WHERE what LIKE ?",
                        (ce.EXAM_UNSEEN_SAMPLE_DRAWN + "%",)).fetchone()[0] == 1


def test_an_unseen_sample_queue_with_an_unfrozen_manifest_is_refused(tmp_path):
    conn = init_db(":memory:")
    _populate(conn)
    events, _m, _meta = ce.build_table(conn, SRC)
    s = ce.draw_sample(events, seed=1, per_level=5, per_family=2)
    path = _write_manifest(tmp_path, {"exam": "unseen", "frozen": True, "source_file": SRC})
    with pytest.raises(PermissionError):
        ce.create_sample_queue(conn, s, name="exam", exam=ce.ExamManifest(path, _sha(path)))
    assert conn.execute("SELECT COUNT(*) FROM review_queues").fetchone()[0] == 0


# ── the draw (scripts/rq1b_candidate_events.py) ─────────────────────────────

def _frozen_table(tmp_path, **design):
    db = str(tmp_path / "copy.sqlite")
    conn = init_db(db)
    _populate(conn)
    events, members, meta = ce.build_table(conn, SRC)
    table = ce.save_table(str(tmp_path / "tables"), events, members, meta)
    body = {"exam": "unseen", "frozen": True, "source_file": SRC, "frame": {"table_key": meta["key"]},
            "sampling_design": {"seed": SEED, "per_level": PER_LEVEL, "per_family": PER_FAMILY} | design}
    man = _write_manifest(tmp_path, body)
    sha = _sha(man)
    _freeze_audit(conn, sha)
    conn.close()
    return db, table, man, sha


def test_the_draw_refuses_another_design_and_takes_the_manifests(tmp_path, capsys):
    db, table, man, sha = _frozen_table(tmp_path)
    mod = _script_mod()
    real = str(tmp_path / "the-real.sqlite")
    exam = ["--exam-manifest", man, "--exam-sha256", sha]
    with pytest.raises(SystemExit, match="seed"):
        mod.main(["queue", "--table", table, "--db", db, "--apply", "--seed", "0", "--per-level", str(PER_LEVEL),
                  "--per-family", str(PER_FAMILY)] + exam, real=real, checkout=PROJECT_ROOT)
    with pytest.raises(SystemExit, match="per_level"):
        mod.main(["queue", "--table", table, "--db", db, "--apply", "--seed", str(SEED), "--per-level", "100",
                  "--per-family", str(PER_FAMILY)] + exam, real=real, checkout=PROJECT_ROOT)
    capsys.readouterr()
    assert mod.main(["queue", "--table", table, "--db", db, "--apply", "--seed", str(SEED), "--per-level",
                     str(PER_LEVEL), "--per-family", str(PER_FAMILY), "--json"] + exam,
                    real=real, checkout=PROJECT_ROOT) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["queue_id"] is not None
    with open(os.path.join(report["sample"], "meta.json"), encoding="utf-8") as fh:
        assert json.load(fh)["exam"]["sha256"] == sha
    c = sqlite3.connect(db)
    assert c.execute("SELECT COUNT(*) FROM audit_log WHERE what LIKE ?",
                     (ce.EXAM_UNSEEN_SAMPLE_DRAWN + "%",)).fetchone()[0] == 1
    c.close()


def test_the_draw_refuses_a_table_that_is_not_the_frozen_frame(tmp_path):
    db, table, man, sha = _frozen_table(tmp_path)
    with open(os.path.join(table, "meta.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    meta["key"] = meta["key"] + "_other"
    with open(os.path.join(table, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)
    mod = _script_mod()
    with pytest.raises(SystemExit, match="frame"):
        mod.main(["queue", "--table", table, "--db", db, "--apply", "--seed", str(SEED), "--per-level",
                  str(PER_LEVEL), "--per-family", str(PER_FAMILY), "--exam-manifest", man, "--exam-sha256", sha],
                 real=str(tmp_path / "the-real.sqlite"), checkout=PROJECT_ROOT)


# ── the freeze (scripts/m4_exam_freeze.py --recording) ──────────────────────

def _freeze_args(tmp_path, db, sid, table, **kw):
    out = str(tmp_path / "exam_out")
    docs = str(tmp_path / "exam_docs")
    args = ["--db", db, "--recording", SRC, "--session", str(sid), "--table", table, "--slug", "x",
            "--out", out, "--docs", docs, "--seed", str(SEED)]
    for k, val in kw.items():
        args += [f"--{k.replace('_', '-')}", str(val)]
    return args, out, docs


def test_the_freeze_writes_an_unseen_manifest_over_the_frozen_frame(tmp_path, capsys):
    db = str(tmp_path / "copy.sqlite")
    conn = init_db(db)
    rid, sid = _populate(conn)
    events, members, meta = ce.build_table(conn, SRC)
    table = ce.save_table(str(tmp_path / "tables"), events, members, meta)
    conn.close()
    before = _sha(db)
    mod = _freeze_mod()
    args, out, docs = _freeze_args(tmp_path, db, sid, table)
    assert mod.main(args) == 0
    assert _sha(db) == before                                              # read-only
    man_path = os.path.join(out, "manifest.json")
    with open(man_path, encoding="utf-8") as fh:
        man = json.load(fh)
    assert man["exam"] == "unseen" and man["frozen"] is True and man["source_file"] == SRC
    assert man["recording_ids"] == [rid] and man["slug"] == "x-exam"
    assert man["frame"]["table_key"] == meta["key"] and man["frame"]["n_events"] == meta["n_events"]
    assert man["detectors"]["n_real_runs"] == 2 and man["detectors"]["sha256"]
    assert set(man["detectors"]["variants"]) == {"noise_threshold", "drop_detection_v1"}
    assert man["sampling_design"]["seed"] == SEED and man["sampling_design"]["per_level"] == 40 \
        and man["sampling_design"]["per_family"] == 15
    assert "minirocket_R4" in man["models"]
    assert set(man["cnns"]["models"]["reference_cnns"]) == {"GASF", "GADF", "recurrence", "fusion"}
    assert man["known_risks"] and "units" in json.dumps(man["known_risks"])
    assert man["judging"]["lock"] is None or "not held out" in json.dumps(man["judging"])
    with open(os.path.join(out, "audit_body.json"), encoding="utf-8") as fh:
        body = json.load(fh)
    sha = _sha(man_path)
    assert body["kind"] == ce.EXAM_AUDIT_KIND and body["what"].startswith(ce.EXAM_UNSEEN_FROZEN)
    assert body["detail"]["sha256"] == sha and body["detail"]["source_file"] == SRC
    assert os.path.isfile(os.path.join(docs, "x-exam-manifest.json"))
    with pytest.raises(SystemExit, match="exists"):                        # never rewritten
        mod.main(args)


def test_the_freeze_refuses_the_held_out_recording_an_empty_session_and_a_foreign_table(tmp_path):
    db = str(tmp_path / "copy.sqlite")
    conn = init_db(db)
    rid, sid = _populate(conn)
    events, members, meta = ce.build_table(conn, SRC)
    table = ce.save_table(str(tmp_path / "tables"), events, members, meta)
    empty = conn.execute("INSERT INTO discovery_sessions (name, source_file, channels_json, created_at, updated_at) "
                         "VALUES ('empty', ?, '[]', ?, ?)", (SRC, T, T)).lastrowid
    conn.commit()
    conn.close()
    mod = _freeze_mod()
    args, _o, _d = _freeze_args(tmp_path, db, empty, table)
    with pytest.raises(SystemExit, match="runs"):
        mod.main(args)
    args, _o, _d = _freeze_args(tmp_path, db, sid, table)
    args[args.index("--recording") + 1] = HELD_OUT_RECORDING_FILE
    with pytest.raises(SystemExit, match="held out"):
        mod.main(args)
    with open(os.path.join(table, "meta.json"), encoding="utf-8") as fh:
        m = json.load(fh)
    m["runs"].append({"run_id": 9999, "variant": "noise_threshold", "recording_id": rid, "n_detections": 1})
    with open(os.path.join(table, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(m, fh)
    args, _o, _d = _freeze_args(tmp_path, db, sid, table)
    with pytest.raises(SystemExit, match="9999"):
        mod.main(args)


# ── the marking (scripts/m4_exam_score.py --manifest) ───────────────────────

def _judge(conn, sample, qid, n=12):
    order = sample.sort_values("serve_rank")["detection_id"].astype(int).tolist()
    for i, d in enumerate(order[:n]):
        write_verdict(conn, qid, d, "interesting" if i % 2 else "not_interesting")


def test_the_unseen_exam_is_marked_with_minirocket_and_the_inline_cnns(tmp_path):
    mod = _score_mod()
    db, conn, exam, sample, qid, where, table = _exam_db(tmp_path)
    _judge(conn, sample, qid)
    res = mod.mark(conn, manifest_path=exam.path, manifest_sha=exam.sha256, sample_dir=where, queue_id=qid,
                   scorer=_fake_scorer(), n_boot=50, cnn_scorers=_fake_cnns(["GASF"]))
    assert res["exam"] == "Some fungus unseen-recording exam" and res["answered"] == 12
    assert res["minirocket"]["metrics"]["n"] == 12 and res["agreement_ladder"]
    assert set(res["cnns"]) == {"GASF"} and res["cnns"]["GASF"]["metrics"]["n"] == 12
    assert "amendment" not in res
    rp, fp = mod._write(res, str(tmp_path / "out"), str(tmp_path / "findings"))
    assert os.path.basename(fp).startswith("x-exam-")
    text = open(fp, encoding="utf-8").read()
    assert "Some fungus unseen-recording exam" in text and "Reference CNNs" in text and "M4" not in text


def test_the_unseen_marking_refuses_another_frame_or_a_changed_checkpoint(tmp_path):
    mod = _score_mod()
    db, conn, exam, sample, qid, where, table = _exam_db(tmp_path)
    _judge(conn, sample, qid)
    kw = dict(manifest_path=exam.path, manifest_sha=exam.sha256, sample_dir=where, queue_id=qid,
              scorer=_fake_scorer(), n_boot=20, cnn_scorers=_fake_cnns(["GASF"]))
    with pytest.raises(PermissionError):
        mod.mark(conn, **(kw | {"manifest_sha": "0" * 64}))
    with open(json.load(open(exam.path, encoding="utf-8"))["cnns"]["models"]["reference_cnns"]["GASF"]["path"],
              "ab") as fh:
        fh.write(b"retrained")
    with pytest.raises(SystemExit, match="GASF"):
        mod.mark(conn, **kw)


def test_the_unseen_marking_refuses_a_verdict_given_before_the_freeze(tmp_path):
    mod = _score_mod()
    db, conn, exam, sample, qid, where, table = _exam_db(tmp_path)
    _judge(conn, sample, qid, n=3)
    conn.execute("UPDATE review_audit SET created_at = '2026-10-01T00:00:00.000000+00:00'")
    conn.commit()
    with pytest.raises(SystemExit, match="before"):
        mod.mark(conn, manifest_path=exam.path, manifest_sha=exam.sha256, sample_dir=where, queue_id=qid,
                 scorer=_fake_scorer(), n_boot=20, cnn_scorers=_fake_cnns(["GASF"]))


def test_the_unseen_dry_run_is_synthetic_and_leaves_the_database_untouched(tmp_path):
    mod = _score_mod()
    db, conn, exam, sample, qid, where, table = _exam_db(tmp_path)
    conn.close()
    before = _sha(db)
    out = str(tmp_path / "dry")
    assert mod.main(["--dry-run", "--db", db, "--manifest", exam.path, "--sha256", exam.sha256, "--sample", where,
                     "--queue", str(qid), "--out", out, "--n-boot", "20"]) == 0
    with open(os.path.join(out, "results.json"), encoding="utf-8") as fh:
        res = json.load(fh)
    assert res["synthetic"] is True and set(res["cnns"]) == {"GASF"}
    assert all(r["scores_synthetic"] for r in res["cnns"].values())
    assert _sha(db) == before
