"""
test_rq1b_candidate_events_script.py
====================================
a2-rq1b: `scripts/rq1b_candidate_events.py`, the researcher's handle on `Working/discovery/candidate_events.py`.

    build     the candidate-event table of one recording, from the database opened READ-ONLY, written to disk
    queue     the stratified sample: a dry run by default; --apply saves the sample and creates the Review queue
    estimate  the precision estimates from the sample's answers so far (read-only)

The real database is named only with --real (the guard is `scripts/backfill_seed_entry_ids.py`'s: a --db naming it
by any other spelling is refused); a dry run writes nothing anywhere.

Run from the project root:
    python -m pytest tests/test_rq1b_candidate_events_script.py -q
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

from Working.database.schema import init_db
from Working.database import adjudications as adj
from Working.database import queries as q
from Working.database import vocabulary as v

SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "rq1b_candidate_events.py")
N = 100_000
T = "2026-10-18T00:00:00"


def _script():
    spec = importlib.util.spec_from_file_location("rq1b_candidate_events_script", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _db(tmp_path):
    """A small database: one recording, two detectors, 30 events, one of them already judged."""
    path = str(tmp_path / "annotations.sqlite")
    conn = init_db(path)
    v.seed_vocabulary(conn)
    rid = q.insert_recording(conn, "rec.mat", 0, 1.0, N, 0, "data/rec.mat/CH0.npy")
    sid = conn.execute("INSERT INTO discovery_sessions (name, source_file, channels_json, created_at, updated_at) "
                       "VALUES ('screen', 'rec.mat', '[]', ?, ?)", (T, T)).lastrowid
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
    q.insert_annotation(conn, rid, 2000, 2100, "interesting", source="library_review")
    conn.commit()
    conn.close()
    return path


def _run(mod, argv, capsys, real=None):
    code = mod.main(argv, real=real)
    out = capsys.readouterr().out
    return code, out


def test_build_writes_a_table_and_leaves_the_database_untouched(tmp_path, capsys):
    mod = _script()
    db = _db(tmp_path)
    before = _sha(db)
    out_dir = tmp_path / "tables"
    code, out = _run(mod, ["build", "--db", db, "--file", "rec.mat", "--out", str(out_dir), "--json"], capsys,
                     real=str(tmp_path / "the-real.sqlite"))
    assert code == 0
    report = json.loads(out)
    assert report["n_events"] == 30 and report["labels"]["interesting"] == 1
    assert os.path.isfile(os.path.join(report["table"], "events.parquet"))
    assert _sha(db) == before


def test_a_db_that_is_the_real_database_is_refused_without_real(tmp_path, capsys):
    mod = _script()
    db = _db(tmp_path)
    with pytest.raises(SystemExit):
        mod.main(["build", "--db", db, "--file", "rec.mat", "--out", str(tmp_path / "t")], real=db)


def test_queue_is_a_dry_run_until_apply_and_apply_twice_makes_one_queue(tmp_path, capsys):
    mod = _script()
    db = _db(tmp_path)
    real = str(tmp_path / "the-real.sqlite")
    code, out = _run(mod, ["build", "--db", db, "--file", "rec.mat", "--out", str(tmp_path / "t"), "--json"],
                     capsys, real=real)
    table = json.loads(out)["table"]
    before = _sha(db)
    code, out = _run(mod, ["queue", "--table", table, "--db", db, "--seed", "0", "--json"], capsys, real=real)
    dry = json.loads(out)
    assert code == 0 and dry["applied"] is False and dry["n_sampled"] == 29      # the judged event is not drawn
    assert _sha(db) == before
    assert not [p for p in os.listdir(table) if p.startswith("sample")]
    for _ in range(2):
        code, out = _run(mod, ["queue", "--table", table, "--db", db, "--seed", "0", "--apply", "--json"], capsys,
                         real=real)
        done = json.loads(out)
        assert code == 0 and done["applied"] is True
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM review_queues").fetchone()[0] == 1
    conn.close()
    assert os.path.isfile(os.path.join(done["sample"], "sample.parquet"))


def test_queue_apply_on_the_real_database_waits_for_the_bridge_code(tmp_path, capsys):
    """The queue's `order` filter is new: a bridge on older code raises on every queue read (the header's count
    included), so --real --apply is refused until the main checkout serves it."""
    mod = _script()
    db = _db(tmp_path)                                       # stands in for the real database
    for name, src in (("old_checkout", "# a bridge before a2-rq1b\n"), ("new_checkout", "QUEUE_ORDERS = ('listed',)\n")):
        d = tmp_path / name / "Working" / "review"
        d.mkdir(parents=True)
        (d / "queues.py").write_text(src, encoding="utf-8")
    _code, out = _run(mod, ["build", "--real", "--file", "rec.mat", "--out", str(tmp_path / "t"), "--json"], capsys,
                      real=db)
    table = json.loads(out)["table"]
    with pytest.raises(SystemExit):
        mod.main(["queue", "--table", table, "--real", "--apply"], real=db, checkout=str(tmp_path / "old_checkout"))
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM review_queues").fetchone()[0] == 0
    conn.close()
    assert mod.main(["queue", "--table", table, "--real", "--apply", "--json"], real=db,
                    checkout=str(tmp_path / "new_checkout")) == 0
    capsys.readouterr()
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM review_queues").fetchone()[0] == 1
    conn.close()


def test_estimate_reads_the_answers_given_so_far(tmp_path, capsys):
    mod = _script()
    db = _db(tmp_path)
    real = str(tmp_path / "the-real.sqlite")
    _code, out = _run(mod, ["build", "--db", db, "--file", "rec.mat", "--out", str(tmp_path / "t"), "--json"],
                      capsys, real=real)
    table = json.loads(out)["table"]
    _code, out = _run(mod, ["queue", "--table", table, "--db", db, "--seed", "0", "--apply", "--json"], capsys,
                      real=real)
    sample_dir = json.loads(out)["sample"]
    import pandas as pd
    first = int(pd.read_parquet(os.path.join(sample_dir, "sample.parquet")).sort_values("serve_rank")
                .detection_id.iloc[0])
    conn = init_db(db)
    adj.insert_adjudication(conn, first, "interesting")
    conn.close()
    code, out = _run(mod, ["estimate", "--sample", sample_dir, "--db", db, "--json", "--n-boot", "50"], capsys,
                     real=real)
    est = json.loads(out)
    assert code == 0 and est["answered"] == 1 and est["pending"] == 28
    assert est["groups"]["all"]["n_judged_before"] == 1
