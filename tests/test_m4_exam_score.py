"""
test_m4_exam_score.py
=====================
m4-exam (2026-10-26): `scripts/m4_exam_score.py`, the marker of the held-out exam, on a small synthetic database —
never the real one, and no verdict is written anywhere but this test's own in-memory/temp database.

Pinned:

* only the researcher's OWN verdicts given THROUGH the exam queue count: a carried copy (`carried_from`) and a verdict
  written outside the exam queue are excluded and reported;
* it refuses a manifest whose hash or freeze does not check out, and a sample drawn under another manifest;
* it computes the manifest's metrics (share of real candidates, agreement ladder, per-family precision, the model's
  AUC and balanced accuracy with intervals) and writes results.json + a findings page; the database is untouched.

Run from the project root:
    python -m pytest tests/test_m4_exam_score.py -q
"""

import hashlib
import importlib.util
import json
import os
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
from Working.database import adjudications as adj
from Working.database import queries as q
from Working.database import vocabulary as v
from Working.discovery import candidate_events as ce
from Working.registration.settings import append_audit
from Working.review.verdicts import write_verdict

N = 200_000
T = "2026-10-26T00:00:00"
M4 = HELD_OUT_RECORDING_FILE


def _script():
    spec = importlib.util.spec_from_file_location("m4_exam_score_script",
                                                  os.path.join(PROJECT_ROOT, "scripts", "m4_exam_score.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _exam_db(tmp_path):
    """An M4 stand-in: two detectors (one selective) on one channel, 60 events far apart; the manifest frozen."""
    db = str(tmp_path / "copy.sqlite")
    conn = init_db(db)
    v.seed_vocabulary(conn)
    rid = q.insert_recording(conn, M4, 0, 1.0, N, 0, f"data/{M4}/CH0.npy")
    sid = conn.execute("INSERT INTO discovery_sessions (name, source_file, channels_json, created_at, updated_at) "
                       "VALUES ('screen', ?, '[]', ?, ?)", (M4, T, T)).lastrowid
    for k, (variant, spans) in enumerate([("noise_threshold", [(3000 * i, 3000 * i + 100) for i in range(50)]),
                                          ("drop_detection_v1", [(160_000 + 3000 * i, 160_000 + 3000 * i + 100)
                                                                 for i in range(10)])]):
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
    man = str(tmp_path / "manifest.json")
    with open(man, "w", encoding="utf-8") as fh:
        json.dump({"exam": "held_out", "frozen": True, "source_file": M4,
                   "metrics": {"estimate_n_boot": 50, "estimate_seed": 0}}, fh)
    sha = _sha(man)
    append_audit(conn, ce.EXAM_AUDIT_KIND, f"{ce.EXAM_FROZEN} · {sha}", "Datasets", detail={"sha256": sha})
    exam = ce.ExamManifest(man, sha)
    events, members, meta = ce.build_table(conn, M4, exam=exam)
    table = ce.save_table(str(tmp_path / "tables"), events, members, meta)
    sample = ce.draw_sample(events, seed=5, per_level=20, per_family=6)
    qid = ce.create_sample_queue(conn, sample, name="exam", exam=exam)
    smeta = {"name": "sample_x", "table_key": meta["key"], "source_file": M4, "queue_id": qid,
             "exam": {"manifest": man, "sha256": sha}}
    where = ce.save_sample(table, sample, events[["event_id", "label", "label_kind", "label_basis", "label_refs",
                                                  "inside_interesting"]], smeta)
    return db, conn, exam, sample, qid, where


def _fake_scorer(conn, sample):
    """A model that is right on drop_detection_v1 anchors and noisy elsewhere: deterministic, no data read."""
    rng = np.random.default_rng(0)

    def score(rows):
        return rng.normal(0, 1, len(rows)), np.ones(len(rows), bool)
    return score


def test_only_own_verdicts_through_the_exam_queue_count(tmp_path):
    mod = _script()
    db, conn, exam, sample, qid, where = _exam_db(tmp_path)
    order = sample.sort_values("serve_rank")["detection_id"].astype(int).tolist()
    for i, d in enumerate(order[:12]):
        write_verdict(conn, qid, d, "interesting" if i % 2 else "not_interesting")
    write_verdict(conn, qid, order[12], "unsure")
    outside = order[13]
    adj.insert_adjudication(conn, outside, "interesting")                 # not through the exam queue
    carried = order[14]
    src = conn.execute("SELECT id FROM adjudications WHERE detection_id = ?", (order[0],)).fetchone()[0]
    conn.execute("INSERT INTO adjudications (detection_id, verdict, note, created_at, carried_from) "
                 "VALUES (?, 'interesting', 'carried', ?, ?)", (carried, T, src))
    conn.commit()
    got, report = mod.exam_verdicts(conn, sample, qid)
    assert set(got) == set(order[:13])
    assert report["excluded_carried"] == [carried] and report["excluded_not_via_exam_queue"] == [outside]
    res = mod.mark(conn, manifest_path=exam.path, manifest_sha=exam.sha256, sample_dir=where, queue_id=qid,
                   scorer=_fake_scorer(conn, sample), n_boot=50)
    assert res["answered"] == 12 and res["unsure"] == 1 and res["synthetic"] is False
    assert res["estimated_share_real"]["precision"] is not None
    assert res["agreement_ladder"] and any(k.startswith("family:drop_detection_v1") for k in res["per_family_precision"])
    m = res["minirocket"]["metrics"]
    assert m["n"] == 12 and m["auc"]["value"] is not None and len(m["auc"]["ci"]) == 2
    assert 0.0 <= m["balanced_accuracy"]["value"] <= 1.0
    rp, fp = mod._write(res, str(tmp_path / "out"), str(tmp_path / "findings"))
    with open(rp, encoding="utf-8") as fh:
        assert json.load(fh)["queue_id"] == qid
    assert "Agreement ladder" in open(fp, encoding="utf-8").read()


def test_the_dry_run_uses_synthetic_verdicts_and_leaves_the_database_untouched(tmp_path, capsys):
    mod = _script()
    db, conn, exam, sample, qid, where = _exam_db(tmp_path)
    conn.close()
    before = _sha(db)
    out = str(tmp_path / "dry")
    assert mod.main(["--dry-run", "--db", db, "--manifest", exam.path, "--sha256", exam.sha256, "--sample", where,
                     "--queue", str(qid), "--out", out, "--n-boot", "20"]) == 0
    with open(os.path.join(out, "results.json"), encoding="utf-8") as fh:
        res = json.load(fh)
    assert res["synthetic"] is True and res["answered"] > 0 and res["verdicts"]["n_own_exam_verdicts"] == 0
    assert _sha(db) == before


def test_a_bad_manifest_or_another_sample_is_refused(tmp_path):
    mod = _script()
    db, conn, exam, sample, qid, where = _exam_db(tmp_path)
    with pytest.raises(PermissionError):
        mod.mark(conn, manifest_path=exam.path, manifest_sha="0" * 64, sample_dir=where, queue_id=qid,
                 scorer=_fake_scorer(conn, sample))
    with pytest.raises(SystemExit):
        mod.mark(conn, manifest_path=exam.path, manifest_sha=exam.sha256, sample_dir=where, queue_id=qid + 1,
                 scorer=_fake_scorer(conn, sample))


# ── amendment 1 (2026-10-26): the frozen reference CNNs scored on the same exam events ──────────────────────────

def _amend(tmp_path, conn, exam, *, audit=True, manifest_sha=None):
    """A stand-in amendment: two fake checkpoint files fingerprinted, the frozen manifest referenced, its freeze
    audited as the real one is. Returns (path, sha256, checkpoints)."""
    ck = {}
    for name in ("GASF", "fusion"):
        p = tmp_path / f"{name}_fake.pth"
        p.write_bytes(name.encode() * 100)
        ck[name] = {"path": str(p), "image_type": name, "sha256": _sha(str(p))}
    am = {"amendment": 1, "amends": {"manifest": exam.path, "sha256": manifest_sha or exam.sha256},
          "added_before_judging": True, "models": {"reference_cnns": ck}, "code": {},
          "metrics": {"cut": 0.5, "n_boot": 50, "seed": 0}}
    path = str(tmp_path / "amendment-1.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(am, fh)
    sha = _sha(path)
    if audit:
        mod = _script()
        append_audit(conn, ce.EXAM_AUDIT_KIND, f"{mod.EXAM_AMENDED} (1) · {sha}", "Datasets", route="exam/M4",
                     detail={"sha256": sha, "amends": exam.sha256})
    return path, sha, ck


def _fake_cnns(names, seed=1):
    rng = np.random.default_rng(seed)

    def make():
        def score(rows):
            return rng.uniform(0, 1, len(rows)), np.ones(len(rows), bool)
        return score
    return {n: make() for n in names}


def _judge(conn, sample, qid, n=12):
    order = sample.sort_values("serve_rank")["detection_id"].astype(int).tolist()
    for i, d in enumerate(order[:n]):
        write_verdict(conn, qid, d, "interesting" if i % 2 else "not_interesting")


def test_the_amended_exam_scores_the_cnns_beside_minirocket(tmp_path):
    mod = _script()
    db, conn, exam, sample, qid, where = _exam_db(tmp_path)
    apath, asha, ck = _amend(tmp_path, conn, exam)
    _judge(conn, sample, qid)
    res = mod.mark(conn, manifest_path=exam.path, manifest_sha=exam.sha256, sample_dir=where, queue_id=qid,
                   scorer=_fake_scorer(conn, sample), n_boot=50, amendment=(apath, asha),
                   cnn_scorers=_fake_cnns(ck))
    assert res["amendment"]["sha256"] == asha and res["amendment"]["audit_id"]
    assert set(res["cnns"]) == {"GASF", "fusion"}
    for name, r in res["cnns"].items():
        m = r["metrics"]
        assert m["n"] == 12 and m["auc"]["value"] is not None and len(m["auc"]["ci"]) == 2
        assert 0.0 <= m["balanced_accuracy"]["value"] <= 1.0 and r["cut"] == 0.5
        d = r["auc_minus_minirocket"]
        assert d["n"] == 12 and len(d["ci"]) == 2
        assert d["value"] == pytest.approx(m["auc"]["value"] - res["minirocket"]["metrics"]["auc"]["value"])
    rp, fp = mod._write(res, str(tmp_path / "out"), str(tmp_path / "findings"))
    with open(rp, encoding="utf-8") as fh:
        assert set(json.load(fh)["cnns"]) == {"GASF", "fusion"}
    text = open(fp, encoding="utf-8").read()
    assert "Reference CNNs" in text and "GASF" in text


def test_a_changed_cnn_checkpoint_is_refused(tmp_path):
    mod = _script()
    db, conn, exam, sample, qid, where = _exam_db(tmp_path)
    apath, asha, ck = _amend(tmp_path, conn, exam)
    _judge(conn, sample, qid)
    with open(ck["GASF"]["path"], "ab") as fh:
        fh.write(b"retrained")
    with pytest.raises(SystemExit, match="GASF"):
        mod.mark(conn, manifest_path=exam.path, manifest_sha=exam.sha256, sample_dir=where, queue_id=qid,
                 scorer=_fake_scorer(conn, sample), n_boot=20, amendment=(apath, asha))


def test_an_amendment_unaudited_or_of_another_manifest_or_after_judging_is_refused(tmp_path):
    mod = _script()
    db, conn, exam, sample, qid, where = _exam_db(tmp_path)
    apath, asha, ck = _amend(tmp_path, conn, exam, audit=False)
    _judge(conn, sample, qid, n=4)
    conn.execute("UPDATE review_audit SET created_at = '2026-10-01T00:00:00.000000+00:00'")   # judged a while ago
    conn.commit()
    kw = dict(manifest_path=exam.path, manifest_sha=exam.sha256, sample_dir=where, queue_id=qid,
              scorer=_fake_scorer(conn, sample), n_boot=20, cnn_scorers=_fake_cnns(ck))
    with pytest.raises(SystemExit, match="audit"):                         # not in the audit log
        mod.mark(conn, amendment=(apath, asha), **kw)
    with pytest.raises(SystemExit, match="sha256"):                        # the file is not the audited one
        mod.mark(conn, amendment=(apath, "0" * 64), **kw)
    # audited only now, AFTER four verdicts were given: refused, it was not added before judging
    append_audit(conn, ce.EXAM_AUDIT_KIND, f"{mod.EXAM_AMENDED} (1) · {asha}", "Datasets",
                 detail={"sha256": asha, "amends": exam.sha256})
    with pytest.raises(SystemExit, match="before"):
        mod.mark(conn, amendment=(apath, asha), **kw)
    other = tmp_path / "other"
    other.mkdir()
    bpath, bsha, _ = _amend(other, conn, exam, manifest_sha="f" * 64)
    with pytest.raises(SystemExit, match="manifest"):
        mod.mark(conn, amendment=(bpath, bsha), **kw)


def test_the_dry_run_scores_synthetic_cnns_only(tmp_path):
    mod = _script()
    db, conn, exam, sample, qid, where = _exam_db(tmp_path)
    apath, asha, ck = _amend(tmp_path, conn, exam)
    conn.close()
    out = str(tmp_path / "dry")
    assert mod.main(["--dry-run", "--db", db, "--manifest", exam.path, "--sha256", exam.sha256, "--sample", where,
                     "--queue", str(qid), "--out", out, "--n-boot", "20", "--amendment", apath,
                     "--amendment-sha256", asha]) == 0
    with open(os.path.join(out, "results.json"), encoding="utf-8") as fh:
        res = json.load(fh)
    assert res["synthetic"] is True and set(res["cnns"]) == {"GASF", "fusion"}
    assert all(r["scores_synthetic"] for r in res["cnns"].values())
