"""
test_webui_runtime.py
=====================
`webui/server/runtime.py` has two modes (stage-3 wiring plan D4, fog C9):

* **sandbox** (the default, what `webui/smoke.py` runs against): the database
  is *copied* into `webui/runtime/<stamp>/` and every writable path the core
  reads at call time — the step cache, both adapter `RESULTS_DIR`s and the
  classifier `MODEL_ROOT` — is redirected under that directory;
* **project**: the REAL database is opened in place, in WAL mode, after a
  timestamped backup is written beside it (`backups/<stamp>.sqlite`, last ten
  kept), and nothing is redirected.

These tests never touch `DATA/`: every run is against a fresh `init_db()`
database in a temp directory, with the runtime root pointed at another temp
directory. No FastAPI import — this is the runtime object alone.
"""

import os
import sqlite3
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from Working.database.schema import init_db  # noqa: E402
from server.runtime import Runtime  # noqa: E402


def _fresh_db(tmp_path):
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    conn.execute(
        "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
        "VALUES ('probe.mat', 0, 1.0, 10, 0, 'probe.npy')")
    conn.commit()
    conn.close()
    return db


def _core_paths():
    import Working.config as cfg
    import Adapters.detection_matrix_profile as _mp
    import Adapters.preprocessing_window_matrix as _wm
    import Adapters.catalogue_classifier as _cc
    return {
        "STEP_CACHE_ROOT": cfg.STEP_CACHE_ROOT,
        "STEP_CACHE_WRITE_THRESHOLD_S": cfg.STEP_CACHE_WRITE_THRESHOLD_S,
        "matrix_profile.RESULTS_DIR": _mp.RESULTS_DIR,
        "window_matrix.RESULTS_DIR": _wm.RESULTS_DIR,
        "classifier.MODEL_ROOT": _cc.MODEL_ROOT,
    }


def _journal_mode(db):
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute("PRAGMA journal_mode").fetchone()[0].lower()
    finally:
        conn.close()


def test_project_mode_backs_up_opens_wal_and_redirects_nothing(tmp_path):
    db = _fresh_db(tmp_path)
    before = _core_paths()
    assert _journal_mode(db) != "wal", "a fresh init_db() database is not already WAL"

    rt = Runtime(mode="project", stamp="20260921-000001",
                 db_source=str(db), runtime_root=str(tmp_path / "runtime"))
    try:
        rt.setup()

        # the real file is what the bridge opens — no copy
        assert os.path.samefile(rt.db_path, str(db))

        # a backup was written beside it, named by the stamp, and it is a real database
        backup = tmp_path / "db" / "backups" / "20260921-000001.sqlite"
        assert backup.is_file(), "project mode must back the database up before opening it"
        conn = sqlite3.connect(str(backup))
        try:
            assert conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0] == 1
        finally:
            conn.close()

        # the live database is now in WAL mode
        assert _journal_mode(db) == "wal"

        # nothing was redirected
        assert _core_paths() == before, "project mode must leave every core path where it is"

        info = rt.describe()
        assert info["mode"] == "project"
        assert os.path.samefile(info["db_path"], str(db))
        assert info["db_copy"] is None
        assert os.path.samefile(info["db_backup"], str(backup))
        assert info["journal_mode"] == "wal"
        assert info["redirected"] is False
    finally:
        rt.restore()


def test_project_mode_keeps_only_the_last_ten_backups(tmp_path):
    db = _fresh_db(tmp_path)
    backups = tmp_path / "db" / "backups"
    backups.mkdir()
    for i in range(12):
        (backups / f"20260901-{i:06d}.sqlite").write_bytes(b"old")

    rt = Runtime(mode="project", stamp="20260921-000002",
                 db_source=str(db), runtime_root=str(tmp_path / "runtime"))
    try:
        rt.setup()
        kept = sorted(p.name for p in backups.iterdir())
        assert len(kept) == 10
        assert kept[-1] == "20260921-000002.sqlite", "the backup just written is the newest kept"
        assert kept[0] == "20260901-000003.sqlite", "the three oldest were pruned"
    finally:
        rt.restore()


def test_sandbox_mode_still_copies_and_redirects_everything(tmp_path):
    db = _fresh_db(tmp_path)
    before = _core_paths()
    root = tmp_path / "runtime"

    rt = Runtime(mode="sandbox", stamp="20260921-000003",
                 db_source=str(db), runtime_root=str(root))
    try:
        rt.setup()
        assert not os.path.samefile(rt.db_path, str(db)), "sandbox must open a copy"
        assert os.path.abspath(rt.db_path).startswith(os.path.abspath(str(root)))
        after = _core_paths()
        for key in ("STEP_CACHE_ROOT", "matrix_profile.RESULTS_DIR",
                    "window_matrix.RESULTS_DIR", "classifier.MODEL_ROOT"):
            assert os.path.abspath(after[key]).startswith(os.path.abspath(rt.dir)), key
        assert not (tmp_path / "db" / "backups").exists(), "sandbox writes no backup"
        info = rt.describe()
        assert info["mode"] == "sandbox"
        assert info["redirected"] is True
        assert os.path.samefile(info["db_copy"], rt.db_path)
    finally:
        rt.restore()
    assert _core_paths() == before, "restore() puts the core paths back"


def test_the_default_mode_is_sandbox():
    assert Runtime().mode == "sandbox"


def test_an_unknown_mode_is_refused():
    with pytest.raises(ValueError):
        Runtime(mode="production")
