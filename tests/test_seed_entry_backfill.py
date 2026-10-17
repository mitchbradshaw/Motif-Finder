"""
test_seed_entry_backfill.py
===========================
a2-p4 change 4.5: the researcher's two judged dip searches (Discovery runs
9-11 `dip_search`, 13 `dip_search_allch`) were started from the Seed page's
old "Family medoid" tab — sixteen catalogue spans of the drop-motif store, ids
`medoid:<recording>:<start>:<end>` — so their rows carry no `entryId`, and
*Add N matches to E-xxxx* refuses them. Since a2-p4 a catalogue span whose
span IS a Library entry's span resolves to that entry when a run is made; the
backfill gives the old rows the same link.

What it pins, on a fresh `init_db()` database:

* **It links exactly the catalogue-span seed runs whose span is an entry's**
  (same recording, same start, same end), and only while they have no entry.
* **It changes nothing else:** only the `entryId` inside `params_json`; every
  other key of those params, every other column, every other row stays as it
  was. A library run, an Explore run and a template run are never touched.
* **A dry run writes nothing** and says what it would do.
* **It is audited:** one `audit_log` row per backfill that changed something,
  naming each run and its entry before and after.
* **It is idempotent:** a second run links nothing and writes no audit row.
* **The script refuses the real database** unless `--real` is given — by any name: another case, the other
  slash, a `..`, the Win32 long-path prefix, a hard link, a junction — and refuses `--db` with `--real`. The tests never
  name the real file: the script is handed a stand-in "real" database in a temp directory.
* **A dry run opens the database read-only** and runs no migration; `--apply` runs `init_db` and sums up its
  migration chatter in one line instead of printing it (fix round, 2026-10-17).
"""

import importlib.util
import json
import logging
import os
import sqlite3
import stat
import subprocess
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db  # noqa: E402

SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "backfill_seed_entry_ids.py")
OLD = "2026-10-06T10:00:00+00:00"
#: the Win32 long-path prefix: two backslashes, "?", one backslash
LONG_PREFIX = chr(92) * 2 + "?" + chr(92)


def _backfill():
    from Working.discovery import seed_entry_backfill as B
    return B


def _db(tmp_path):
    path = str(tmp_path / "annotations.sqlite")
    conn = init_db(path)
    for ch in range(2):
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                     "VALUES ('syn.mat', ?, 1.0, 6000, 0, ?)", (ch, f"CH{ch}.npy"))
    ids = {}
    for name, rid, a, b in (("dip", 1, 600, 705), ("dip_allch", 2, 1800, 2616), ("other", 1, 3000, 3060)):
        ids[name] = conn.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx, label, source_kind) "
                                 "VALUES (?, ?, ?, ?, 'event_store')", (rid, a, b, name)).lastrowid
    sess = conn.execute("INSERT INTO discovery_sessions (name, source_file, channels_json, state_json, created_at, "
                        "updated_at) VALUES ('s', 'syn.mat', '[]', '{}', ?, ?)", (OLD, OLD)).lastrowid

    def run(key, kind, params, status="done"):
        return conn.execute("INSERT INTO discovery_runs (session_id, run_key, kind, label, params_json, status, "
                            "created_at, updated_at, run_group_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
                            (sess, key, kind, key.replace("_", " "), json.dumps(params), status, OLD, OLD)).lastrowid

    common = {"stage_count": 1, "glyph": "seed", "cut": 3.2, "k": 200, "run_ids": [11, 12, 13],
              "identity": {"seedId": "x", "channels": ["CH1"], "span": [0, 6000], "k": 200, "cut": 3.2},
              "null": {"paired": True, "draws": 200, "drawn": 200}, "detail": "105 samples · MASS"}
    rows = {
        # the two judged dip searches: catalogue spans at an entry's span, no entry yet
        "dip_search": run("dip_search", "seed", dict(common, seedId="medoid:1:600:705", entryId=None)),
        "dip_search_allch": run("dip_search_allch", "seed", dict(common, seedId="medoid:2:1800:2616",
                                                                  entryId=None)),
        # a catalogue span that is no entry's span (same start, other end; other recording)
        "orphan": run("orphan", "seed", dict(common, seedId="medoid:1:600:700", entryId=None)),
        "elsewhere": run("elsewhere", "seed", dict(common, seedId="medoid:2:600:705", entryId=None)),
        # already linked, by hand or by a run made after a2-p4
        "linked": run("linked", "seed", dict(common, seedId="medoid:1:3000:3060", entryId=ids["other"])),
        # not catalogue spans: never touched, even at an entry's span
        "library": run("library", "seed", dict(common, seedId="library:1:600:705", entryId=None)),
        "explore": run("explore", "seed", dict(common, seedId="explore:1:600:705", entryId=None)),
        "template": run("template", "template", {"stage_count": 3, "glyph": "threshold", "seedId": "medoid:1:600:705"}),
        "garbled": run("garbled", "seed", dict(common, seedId="medoid:nonsense", entryId=None)),
    }
    # dip_search's runs were taken off the session (History keeps them, their verdicts stand): still linked
    conn.execute("UPDATE discovery_runs SET removed_at = ? WHERE id = ?", (OLD, rows["dip_search"]))
    conn.commit()
    return conn, ids, rows


def _dump(conn):
    return [tuple(r) for r in conn.execute("SELECT * FROM discovery_runs ORDER BY id")]


def _params(conn, run_id):
    return json.loads(conn.execute("SELECT params_json FROM discovery_runs WHERE id = ?", (run_id,)).fetchone()[0])


def _audits(conn):
    return conn.execute("SELECT kind, what, where_, detail_json FROM audit_log ORDER BY id").fetchall()


def test_a_dry_run_reports_and_writes_nothing(tmp_path):
    B = _backfill()
    conn, ids, rows = _db(tmp_path)
    try:
        before, audits = _dump(conn), len(_audits(conn))
        report = B.backfill(conn)
        assert report["applied"] is False
        assert {r["runKey"]: r["entryId"] for r in report["linked"]} == {
            "dip_search": ids["dip"], "dip_search_allch": ids["dip_allch"]}
        assert {r["runKey"] for r in report["unmatched"]} == {"orphan", "elsewhere"}
        assert {r["runKey"] for r in report["already"]} == {"linked"}
        assert {r["runKey"] for r in report["unreadable"]} == {"garbled"}
        assert report["auditId"] is None
        assert _dump(conn) == before and len(_audits(conn)) == audits, "a dry run wrote"
    finally:
        conn.close()


def test_apply_links_the_catalogue_span_runs_and_changes_nothing_else(tmp_path):
    B = _backfill()
    conn, ids, rows = _db(tmp_path)
    try:
        before = {r[0]: r for r in _dump(conn)}
        params_before = {k: _params(conn, i) for k, i in rows.items()}
        report = B.backfill(conn, apply=True)
        assert report["applied"] is True
        after = {r[0]: r for r in _dump(conn)}
        cols = [d[0] for d in conn.execute("SELECT * FROM discovery_runs LIMIT 0").description]
        pj = cols.index("params_json")
        for key, rid in rows.items():
            if key in ("dip_search", "dip_search_allch"):
                p = _params(conn, rid)
                want = ids["dip"] if key == "dip_search" else ids["dip_allch"]
                assert p["entryId"] == want, f"{key} was not linked"
                # nothing else in the params moved, and nothing else in the row
                assert {k: v for k, v in p.items() if k != "entryId"} == \
                    {k: v for k, v in params_before[key].items() if k != "entryId"}
                assert [v for i, v in enumerate(after[rid]) if i != pj] == \
                    [v for i, v in enumerate(before[rid]) if i != pj], f"{key}: a column other than params_json moved"
            else:
                assert after[rid] == before[rid], f"{key} was touched"
        # audited once, naming each run and its entry before and after
        audits = _audits(conn)
        assert len(audits) == 1
        kind, what, where, detail = audits[0]
        assert kind == "library" and "dip_search" in what and where
        detail = json.loads(detail)
        assert {(r["runKey"], r["before"], r["entryId"]) for r in detail["runs"]} == {
            ("dip_search", None, ids["dip"]), ("dip_search_allch", None, ids["dip_allch"])}
        assert report["auditId"] is not None
    finally:
        conn.close()


def test_a_second_backfill_changes_nothing(tmp_path):
    B = _backfill()
    conn, ids, rows = _db(tmp_path)
    try:
        B.backfill(conn, apply=True)
        snapshot, audits = _dump(conn), len(_audits(conn))
        again = B.backfill(conn, apply=True)
        assert again["linked"] == []
        assert {r["runKey"] for r in again["already"]} == {"dip_search", "dip_search_allch", "linked"}
        assert again["auditId"] is None
        assert _dump(conn) == snapshot and len(_audits(conn)) == audits
    finally:
        conn.close()


def _script():
    """The script as a module, so a test can hand it a stand-in "real" database (`main(argv, real=...)`) and never
    name the real one."""
    spec = importlib.util.spec_from_file_location("backfill_seed_entry_ids_script", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_real(tmp_path):
    """A stand-in for the real database, in a temp directory: what the refusal must recognise by any name."""
    real_dir = tmp_path / "main" / "DATA" / "db"
    real_dir.mkdir(parents=True)
    real = real_dir / "annotations.sqlite"
    init_db(str(real)).close()
    return real


def _path(conn):
    return conn.execute("PRAGMA database_list").fetchone()[2]


def test_the_script_dry_runs_by_default_and_applies_on_request(tmp_path, capsys):
    S = _script()
    conn, ids, rows = _db(tmp_path)
    db = _path(conn)
    conn.close()
    real = str(_fake_real(tmp_path))
    assert S.main(["--db", db], real=real) == 0
    out = capsys.readouterr().out
    assert "dip_search" in out and "dry run" in out.lower()
    c = sqlite3.connect(db)
    try:
        assert json.loads(c.execute("SELECT params_json FROM discovery_runs WHERE id = ?",
                                    (rows["dip_search"],)).fetchone()[0])["entryId"] is None
    finally:
        c.close()
    assert S.main(["--db", db, "--apply"], real=real) == 0
    c = sqlite3.connect(db)
    try:
        assert json.loads(c.execute("SELECT params_json FROM discovery_runs WHERE id = ?",
                                    (rows["dip_search"],)).fetchone()[0])["entryId"] == ids["dip"]
    finally:
        c.close()


def test_the_script_refuses_the_real_database_by_any_name(tmp_path, capsys):
    """F4: the refusal compared two strings, so another case, the other slash, a `..`, the Win32 long-path prefix, a
    hard link or a junction walked past it. Every alias here names the stand-in real database."""
    S = _script()
    real = _fake_real(tmp_path)
    (real.parent / "sub").mkdir()
    hard = tmp_path / "hard_link.sqlite"
    os.link(real, hard)
    aliases = [str(real), str(real).replace("\\", "/"), os.path.join(str(real.parent), "sub", "..", real.name),
               str(hard)]
    if os.name == "nt":
        aliases += [str(real).upper(), LONG_PREFIX + os.path.abspath(str(real))]
    junction = None
    if os.name == "nt":
        # a junction to the stand-in's directory, inside the temp directory; removed below (the link, not its target)
        junction = tmp_path / "junction"
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(real.parent)], capture_output=True)
        if made.returncode == 0:
            aliases.append(str(junction / real.name))
        else:
            junction = None
    before = real.read_bytes()
    try:
        for alias in aliases:
            for extra in ([], ["--apply"]):
                with pytest.raises(SystemExit) as e:
                    S.main(["--db", alias] + extra, real=str(real))
                assert e.value.code == 2, f"{alias!r} {extra} was not refused"
                assert "--real" in capsys.readouterr().err
    finally:
        if junction is not None:
            os.rmdir(junction)
    assert real.read_bytes() == before, "the stand-in real database was touched"
    if os.name == "nt":
        assert any(a.startswith(LONG_PREFIX) for a in aliases) and any("junction" in a for a in aliases)


def test_db_and_real_together_are_refused(tmp_path, capsys):
    """F4: `--db X --real` used to drop `--db` silently and write the real database."""
    S = _script()
    conn, ids, rows = _db(tmp_path)
    db = _path(conn)
    conn.close()
    with pytest.raises(SystemExit) as e:
        S.main(["--db", db, "--real", "--apply"], real=str(_fake_real(tmp_path)))
    assert e.value.code == 2
    assert "not both" in capsys.readouterr().err


def test_a_dry_run_opens_the_database_read_only_and_runs_no_migration(tmp_path, monkeypatch, capsys):
    """F4: the dry run called `init_db` on its target, which runs every migration — on a read-only snapshot of the
    real database that printed ~300 lines of a legacy-detections migration over the report."""
    S = _script()
    conn, ids, rows = _db(tmp_path)
    db = _path(conn)
    conn.close()

    def no_migrations(*a, **k):
        raise AssertionError("a dry run ran init_db (every migration) on its target")

    monkeypatch.setattr(S, "init_db", no_migrations)
    os.chmod(db, stat.S_IREAD)
    try:
        assert S.main(["--db", db], real=str(_fake_real(tmp_path))) == 0
    finally:
        os.chmod(db, stat.S_IREAD | stat.S_IWRITE)
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "dip_search" in out


def test_apply_sums_up_the_migration_chatter_in_one_line(tmp_path, monkeypatch, capsys):
    """F4: `--apply` keeps `init_db`, but its migration warnings are counted and summed up, not printed one by one."""
    S = _script()
    conn, ids, rows = _db(tmp_path)
    db = _path(conn)
    conn.close()
    real_init = S.init_db

    def chatty(path):
        log = logging.getLogger("Working.database.schema")
        for i in range(300):
            log.warning("legacy detections: refusing run %d (ambiguous): span [0, 10) n=1 n_legacy=1", i)
        return real_init(path)

    monkeypatch.setattr(S, "init_db", chatty)
    assert S.main(["--db", db, "--apply"], real=str(_fake_real(tmp_path))) == 0
    cap = capsys.readouterr()
    text = cap.out + cap.err
    assert text.count("legacy detections: refusing run") <= 1, "the chatter was printed line by line"
    assert "300 migration message" in text, "the chatter is summed up in one line"
