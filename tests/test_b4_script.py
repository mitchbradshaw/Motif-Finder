"""
test_b4_script.py
=================
Cross-channel explorer S1 (D24): `scripts/thesis/b4_cross_channel.py` writes B4's tables and figures from the STORED
census (never recomputing it), with the census hash printed on each, into `docs/thesis/data/ch10_b4/` by default.
The database is opened read-only; the held-out recording is never read; lag against distance is drawn only when
every channel's position is known, and otherwise a note says why.
"""

import csv
import json
import os
import sqlite3
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "tests"), os.path.join(PROJECT_ROOT, "scripts", "thesis")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _cross_census_synthetic as syn  # noqa: E402
from Working import config  # noqa: E402
from Working import cross_census as cc  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.registration.settings import HELD_OUT_FILE  # noqa: E402

M2 = "M2_aug_census_s.mat"


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STEP_CACHE_ROOT", str(tmp_path / "step_cache"))
    path = tmp_path / "b4.sqlite"
    conn = init_db(str(path))
    onsets = syn.every(8, 7200.0)
    plant = {0: [(t, k) for k, t in enumerate(onsets)], 1: [(t + 12.0, k) for k, t in enumerate(onsets)]}
    syn.build(conn, tmp_path, M2, 16, plant, hours=20)
    out = cc.run_census(conn, M2)
    # a census row naming the held-out file (as if one had been written by hand): the script must not read it
    conn.execute("INSERT INTO cross_census (source_file, detector, hash, run_ids_json, layout_json, rule_json, "
                 "consts_json, status, summary_json, created_at) VALUES (?, 'drop_detection_v1', 'x', '[]', '{}', "
                 "'{}', '{}', 'done', '{}', '2026-10-28')", (HELD_OUT_FILE,))
    conn.commit()
    conn.close()
    return path, out["hash"]


def test_the_script_writes_its_tables_and_figures_from_the_stored_census(db, tmp_path):
    import b4_cross_channel as b4

    path, h = db
    out = tmp_path / "ch10_b4"
    before = os.path.getmtime(path)
    assert b4.main(["--db", str(path), "--out", str(out)]) == 0
    assert os.path.getmtime(path) == before                       # read-only

    summary = json.loads((out / "b4_summary.json").read_text(encoding="utf-8"))
    (entry,) = summary["censuses"]
    assert entry["source_file"] == M2 and entry["hash"] == h
    assert HELD_OUT_FILE not in json.dumps(summary["censuses"])
    assert any(HELD_OUT_FILE in s for s in summary["skipped"])

    with open(out / "b4_pairs.csv", newline="", encoding="utf-8") as f:
        pairs = list(csv.DictReader(f))
    assert pairs and all(r["census_hash"] == h for r in pairs)
    top = max(pairs, key=lambda r: int(r["n"]))
    assert int(top["n"]) == 8 and abs(float(top["timetable_L_s"]) - 12.0) <= 1.0

    with open(out / "b4_bins.csv", newline="", encoding="utf-8") as f:
        bins = {r["bin"]: r for r in csv.DictReader(f) if r["source_file"] == M2}
    assert int(bins["propagation"]["count"]) == 8 and bins["propagation"]["census_hash"] == h

    pngs = sorted(p.name for p in out.glob("*.png"))
    assert "b4_bins.png" in pngs and any(n.startswith("b4_lag_hist_") for n in pngs)
    note = (out / "b4_lag_vs_distance_NOTE.txt").read_text(encoding="utf-8")
    assert "position" in note and M2 in note
    assert not (out / "b4_lag_vs_distance.png").exists()


def test_the_script_opens_the_database_read_only(db, tmp_path, monkeypatch):
    import b4_cross_channel as b4

    seen = []
    real = sqlite3.connect

    def spy(target, *a, **k):
        seen.append((str(target), k.get("uri")))
        return real(target, *a, **k)

    monkeypatch.setattr(b4.sqlite3, "connect", spy)
    b4.main(["--db", str(db[0]), "--out", str(tmp_path / "o")])
    assert seen and all("mode=ro" in t and uri for t, uri in seen)


# ── fix round (the critic, 2026-10-28): a stale census never reaches the thesis unmarked ─────────────────────

def test_fix6_a_fresh_census_is_marked_fresh_in_every_output(db, tmp_path):
    import b4_cross_channel as b4

    out = tmp_path / "fresh"
    b4.main(["--db", str(db[0]), "--out", str(out)])
    (entry,) = json.loads((out / "b4_summary.json").read_text(encoding="utf-8"))["censuses"]
    assert entry["stale"] is False and entry["staleWhy"] == []
    for name in ("b4_pairs.csv", "b4_bins.csv"):
        with open(out / name, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert rows and all(r["stale"] == "False" and r["stale_why"] == "" for r in rows)


def test_fix6_a_stale_census_says_so_in_the_summary_and_the_csvs(db, tmp_path):
    import b4_cross_channel as b4
    from Working import cross_channel as xc
    from Working.registration.settings import put_settings

    conn = init_db(str(db[0]))
    put_settings(conn, xc.SETTINGS_PAGE, {xc.SETTINGS_KEYS["min_abs_r"]: 0.7})
    conn.close()
    out = tmp_path / "stale"
    b4.main(["--db", str(db[0]), "--out", str(out)])
    (entry,) = json.loads((out / "b4_summary.json").read_text(encoding="utf-8"))["censuses"]
    assert entry["stale"] is True and any("rule" in w for w in entry["staleWhy"])
    with open(out / "b4_pairs.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert all(r["stale"] == "True" and "rule" in r["stale_why"] for r in rows)
