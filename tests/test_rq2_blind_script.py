"""
test_rq2_blind_script.py
========================
`scripts/rq2_blind.py`: the blinded RQ2 panel (2026-10-26).

    build   samples seed matches, earlier-accepted re-judges and duration-matched random controls into ONE blind,
            shuffled Review queue over fresh machine detections; the key (which item came from where) is a file
            outside the database
    score   reads the queue's verdicts (carried copies excluded) and reports acceptance per source with Wilson
            intervals, each seed against its controls, and blind-vs-earlier agreement
    nulls   per seed per channel: matches under the cut against the surrogate matches at the same line

Everything here runs on a temp database made by `init_db`; the real one is never opened.

    python -m pytest tests/test_rq2_blind_script.py -q
"""

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

from Working.database.schema import init_db, get_connection  # noqa: E402
from Working.review import queues as rq  # noqa: E402

SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "rq2_blind.py")
N = 200_000


def _script():
    spec = importlib.util.spec_from_file_location("rq2_blind_script", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "t.sqlite")
    init_db(path)
    conn = get_connection(path)
    for ch in range(3):
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                     "VALUES ('M2_aug_concat_fs1.mat', ?, 1.0, ?, 0, 'x.npy')", (ch, N))
    conn.commit()
    yield conn, path
    conn.close()


def test_wilson_matches_the_textbook_values():
    s = _script()
    lo, hi = s.wilson(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-3) and hi == pytest.approx(0.5962, abs=1e-3)
    lo, hi = s.wilson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.2775, abs=1e-3)
    assert s.wilson(0, 0) == (None, None)


def test_null_counts_are_per_draw_at_the_same_line():
    s = _script()
    # 3 draws of k = 4: draw 0 has two at or below 1.0, draw 1 none, draw 2 one
    null = {"distances": [0.5, 1.0, 2.0, 3.0, 1.5, 2.0, 2.5, 3.0, 0.9, 1.1, 4.0, 5.0], "draws": 3}
    per = s.null_counts_per_draw(null, k=4, cut=1.0)
    assert list(per) == [2, 0, 1]
    row = s.null_row([0.2, 0.8, 1.2], null, k=4, cut=1.0)
    assert row["real"] == 2
    assert row["null_mean"] == pytest.approx(1.0)
    assert row["null_p95"] == pytest.approx(np.percentile([2, 0, 1], 95))


def test_controls_never_overlap_a_forbidden_span_or_each_other():
    s = _script()
    rng = np.random.default_rng(0)
    forbidden = {1: [(1000, 50_000)], 2: [(0, 100_000)]}
    got = s.sample_controls(rng, {1: 5, 2: 3}, length=300, n_samples={1: N, 2: N}, forbidden={k: list(v) for k, v in forbidden.items()},
                            ok=lambda rid, a, b: True)
    assert len(got) == 8
    by = {}
    for rid, a, b in got:
        assert b - a == 300 and 0 <= a and b <= N
        for fa, fb in forbidden.get(rid, []):
            assert b <= fa or a >= fb
        by.setdefault(rid, []).append((a, b))
    for spans in by.values():
        spans.sort()
        assert all(spans[i][1] <= spans[i + 1][0] for i in range(len(spans) - 1))


def test_allocation_is_proportional_and_sums():
    s = _script()
    got = s.allocate({"a": 60, "b": 30, "c": 10}, 10)
    assert sum(got.values()) == 10 and got == {"a": 6, "b": 3, "c": 1}


def _items():
    return [
        {"group": "drop30", "recording_id": 1, "channel": "CH1_A1", "start": 10_000, "end": 10_377},
        {"group": "drop30", "recording_id": 2, "channel": "CH2_A1", "start": 20_000, "end": 20_377},
        {"group": "control", "control_length": 377, "recording_id": 1, "channel": "CH1_A1",
         "start": 90_000, "end": 90_377},
        {"group": "rejudge_dip_id010", "recording_id": 2, "channel": "CH2_A1", "start": 5_000, "end": 5_105,
         "earlier": {"verdict": "interesting"}},
    ]


def test_panel_is_one_blind_listed_queue_over_fresh_detections(db, tmp_path):
    conn, _ = db
    s = _script()
    rng = np.random.default_rng(1)
    items = s.shuffle(rng, _items())
    out = s.write_panel(conn, items, stamp="20261026-000000", key_dir=str(tmp_path / "key"))
    q = rq.get_queue(conn, out["queue_id"])
    assert q["source_kind"] == "discovery-run" and int(q["blind"]) == 1
    assert q["filters"]["order"] == "listed"
    served = rq.queue_items(conn, out["queue_id"], include_judged=True)
    assert [it["detection_id"] for it in served] == [it["panel_detection_id"] for it in out["items"]]
    assert all("score" not in it for it in served)
    # the detection ids rise with the serving rank, so an id says nothing about where an item came from
    ids = [it["detection_id"] for it in served]
    assert ids == sorted(ids)
    # nothing in the database names a source
    names = {r[0] for r in conn.execute("SELECT name FROM runs WHERE id IN (SELECT run_id FROM detections)")}
    assert names == {s.PANEL_RUN_NAME}
    for r in conn.execute("SELECT score, meta_json FROM detections"):
        assert r[0] is None and r[1] is None
    assert "drop30" not in (q["name"] + (q["note"] or "")) and "control" not in (q["name"] + (q["note"] or ""))
    key = json.load(open(out["key_path"]))
    assert key["queue_id"] == out["queue_id"] and len(key["items"]) == 4


def test_score_excludes_carried_and_reports_wilson(db, tmp_path):
    conn, path = db
    s = _script()
    out = s.write_panel(conn, s.shuffle(np.random.default_rng(2), _items()), stamp="x",
                        key_dir=str(tmp_path / "key"))
    by = {it["group"] + str(it["start"]): it["panel_detection_id"] for it in out["items"]}
    conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at) VALUES (?, 'interesting', 't')",
                 (by["drop3010000"],))
    first = conn.execute("SELECT id FROM adjudications").fetchone()[0]
    conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at, carried_from) "
                 "VALUES (?, 'interesting', 't', ?)", (by["drop3020000"], first))
    conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at) VALUES (?, 'not_interesting', 't')",
                 (by["control90000"],))
    conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at) VALUES (?, 'not_interesting', 't')",
                 (by["rejudge_dip_id0105000"],))
    conn.commit()
    key = json.load(open(out["key_path"]))
    res = s.score(conn, key)
    g = res["groups"]
    assert g["drop30"]["judged"] == 1 and g["drop30"]["carried_excluded"] == 1 and g["drop30"]["accepted"] == 1
    assert g["control"]["accepted"] == 0 and g["control"]["judged"] == 1
    assert res["agreement"]["n"] == 1 and res["agreement"]["still_accepted"] == 0


def test_synthetic_verdicts_never_touch_the_database(db, tmp_path):
    conn, path = db
    s = _script()
    out = s.write_panel(conn, s.shuffle(np.random.default_rng(3), _items()), stamp="y",
                        key_dir=str(tmp_path / "key"))
    key = json.load(open(out["key_path"]))
    before = conn.execute("SELECT COUNT(*) FROM adjudications").fetchone()[0]
    res = s.score(conn, key, synthetic={"drop30": 1.0, "control": 0.0, "rejudge_dip_id010": 1.0}, seed=0)
    assert conn.execute("SELECT COUNT(*) FROM adjudications").fetchone()[0] == before
    assert res["synthetic"] is True and res["groups"]["drop30"]["accepted"] == 2


def test_kappa_is_undefined_when_one_look_never_varies():
    s = _script()
    assert s.kappa([[38, 13], [0, 0]]) is None
    assert s.kappa([[10, 0], [0, 10]]) == pytest.approx(1.0)
