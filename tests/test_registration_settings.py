"""
test_registration_settings.py
=============================
Project settings and the audit log (stage-3 Prompt 02, spec §9, P23): a
`settings` table (page, key, value_json, updated_at, actor) and an append-only
`audit_log` table, both additive migrations applied by `init_db()`, plus the
held-out lock as a setting whose *unlock* needs the recording's name typed
and is enforced server-side (D6).

`Working/registration/settings.py` is the plain-SQL layer; the bridge routes
sit over it. Nothing here touches `DATA/`.
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
from Working.registration.settings import (  # noqa: E402
    ConfirmationRequired, HELD_OUT_PAGE, HELD_OUT_ON_KEY, HELD_OUT_RECORDING_KEY, append_audit, audit_csv,
    get_settings, held_out_state, list_audit, put_settings,
)


@pytest.fixture
def conn(tmp_path):
    c = init_db(str(tmp_path / "annotations.sqlite"))
    yield c
    c.close()


# ---------------------------------------------------------------- schema --

def test_init_db_is_idempotent_with_the_registration_tables(tmp_path):
    db = str(tmp_path / "a.sqlite")
    c1 = init_db(db); c1.close()
    c2 = init_db(db)
    tables = {r[0] for r in c2.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"settings", "audit_log", "registered_artifacts"} <= tables
    rec_cols = {r["name"] for r in c2.execute("PRAGMA table_info(recordings)")}
    assert {"parent_recording_id", "parent_offset", "decimation", "fs_source", "registered_at", "registered_by", "warnings_json", "active"} <= rec_cols
    art_cols = {r["name"] for r in c2.execute("PRAGMA table_info(registered_artifacts)")}
    assert {"kind", "path", "manifest_path", "recording_id", "channel", "span_start", "span_end", "fs", "params_json", "producer",
            "sha1", "checks_json", "warnings_json", "created_at", "actor", "active"} <= art_cols
    # existing rows are untouched by the additive columns: active defaults to 1
    c2.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) VALUES ('a.mat', 0, 1, 10, 0, 'a.npy')")
    assert c2.execute("SELECT active FROM recordings").fetchone()[0] == 1
    c2.close()


def test_a_legacy_database_gains_the_columns_on_the_next_init_db(tmp_path):
    db = str(tmp_path / "legacy.sqlite")
    raw = sqlite3.connect(db)
    raw.executescript("""CREATE TABLE recordings (id INTEGER PRIMARY KEY AUTOINCREMENT, source_file TEXT NOT NULL, channel INTEGER NOT NULL,
                         fs REAL NOT NULL, n_samples INTEGER NOT NULL, global_offset INTEGER NOT NULL, npy_path TEXT NOT NULL, notes TEXT,
                         UNIQUE (source_file, channel));
                         INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) VALUES ('old.mat', 0, 1, 5, 0, 'old.npy');""")
    raw.commit(); raw.close()
    c = init_db(db)
    row = c.execute("SELECT active, parent_recording_id, fs_source FROM recordings").fetchone()
    assert row["active"] == 1 and row["parent_recording_id"] is None and row["fs_source"] is None
    c.close()


# -------------------------------------------------------------- settings --

def test_settings_round_trip_and_json_typing(conn):
    assert get_settings(conn, "nulls") == {}
    changed = put_settings(conn, "nulls", {"alpha": 0.05, "null.detection.draws": 300, "show_x_null": False, "tokens": ["<a>", "<b>"], "note": None},
                           actor="this installation")
    assert set(changed) == {"alpha", "null.detection.draws", "show_x_null", "tokens", "note"}
    got = get_settings(conn, "nulls")
    assert got == {"alpha": 0.05, "null.detection.draws": 300, "show_x_null": False, "tokens": ["<a>", "<b>"], "note": None}
    assert isinstance(got["show_x_null"], bool) and isinstance(got["tokens"], list)
    # a second put of the same values changes nothing; a changed one reports only the changed keys
    assert put_settings(conn, "nulls", {"alpha": 0.05}) == []
    assert put_settings(conn, "nulls", {"alpha": 0.01, "show_x_null": False}) == ["alpha"]
    row = conn.execute("SELECT page, key, value_json, updated_at, actor FROM settings WHERE key = 'alpha'").fetchone()
    assert row["page"] == "nulls" and row["value_json"] == "0.01" and row["updated_at"] and row["actor"]
    assert get_settings(conn, "storage-backups") == {}    # pages do not leak into each other


def test_put_settings_rejects_a_bad_page_or_key(conn):
    with pytest.raises(ValueError):
        put_settings(conn, "not a page!", {"a": 1})
    with pytest.raises(ValueError):
        put_settings(conn, "nulls", {"": 1})
    with pytest.raises(ValueError):
        put_settings(conn, "nulls", "alpha=1")   # not a mapping


# ------------------------------------------------------------- held out --

def test_held_out_defaults_to_on_for_the_held_out_file(conn):
    st = held_out_state(conn)
    assert st["on"] is True and st["recording"] == "M4_aug_concat_fs1" and st["name"] == "M4_aug_concat_fs1"
    assert HELD_OUT_PAGE == "datasets" and HELD_OUT_ON_KEY == "heldout.on" and HELD_OUT_RECORDING_KEY == "heldout.recording"


def test_unlocking_needs_the_name_typed_and_is_audited(conn):
    with pytest.raises(ConfirmationRequired) as ei:
        put_settings(conn, "datasets", {"heldout.on": False})
    assert ei.value.name == "M4_aug_concat_fs1"
    assert held_out_state(conn)["on"] is True                     # nothing was written
    with pytest.raises(ConfirmationRequired):
        put_settings(conn, "datasets", {"heldout.on": False}, confirm_name="m4_aug")   # exact, not fuzzy
    changed = put_settings(conn, "datasets", {"heldout.on": False}, confirm_name="M4_aug_concat_fs1", actor="this installation")
    assert changed == ["heldout.on"]
    assert held_out_state(conn)["on"] is False
    entries = list_audit(conn, kind="lock")
    assert len(entries) == 1 and "turned off" in entries[0]["what"] and "M4_aug_concat_fs1" in entries[0]["what"]
    assert entries[0]["where"] == "Datasets" and entries[0]["route"] == "settings/datasets"
    # turning it back on needs no confirmation, and is audited too
    assert put_settings(conn, "datasets", {"heldout.on": True}) == ["heldout.on"]
    assert held_out_state(conn)["on"] is True
    assert len(list_audit(conn, kind="lock")) == 2


def test_the_typed_name_is_the_display_name_when_one_is_set(conn):
    put_settings(conn, "datasets", {"meta.M4_aug_concat_fs1.display_name": "M4 August"})
    assert held_out_state(conn)["name"] == "M4 August"
    with pytest.raises(ConfirmationRequired):
        put_settings(conn, "datasets", {"heldout.on": False}, confirm_name="M4_aug_concat_fs1")
    assert put_settings(conn, "datasets", {"heldout.on": False}, confirm_name="M4 August") == ["heldout.on"]


# ---------------------------------------------------------------- audit --

def test_audit_is_append_only_newest_first_and_filterable(conn):
    a = append_audit(conn, "settings", "Analyse local limit 10 → 20 min", "Compute & HPC", route="settings/compute-hpc")
    b = append_audit(conn, "lock", "Held-out lock turned off · M4 selectable", "Datasets", route="settings/datasets", detail={"name": "M4"})
    c = append_audit(conn, "sign-off", "Registered fusion_cnn.pth", "Models & registration")
    assert a < b < c
    entries = list_audit(conn)
    assert [e["id"] for e in entries] == [c, b, a]
    assert entries[1]["detail"] == {"name": "M4"} and entries[0]["route"] is None
    assert {e["kind"] for e in entries} == {"settings", "lock", "sign-off"}
    assert [e["id"] for e in list_audit(conn, kind="lock")] == [b]
    assert all(e["by"] == "this installation" and e["when"] for e in entries)
    assert len(list_audit(conn, limit=2)) == 2
    text = audit_csv(conn)
    lines = text.strip().splitlines()
    assert lines[0].startswith("when,kind,what,where,route,by") and len(lines) == 4
    # no API edits or deletes an entry; the table also has no updated_at to edit through
    import Working.registration.settings as S
    assert not any(n.startswith(("update_audit", "delete_audit", "edit_audit")) for n in dir(S))


def test_append_audit_validates_kind_and_what(conn):
    with pytest.raises(ValueError):
        append_audit(conn, "", "x", "y")
    with pytest.raises(ValueError):
        append_audit(conn, "settings", "", "y")


# ---------------------------------------------------- rule-5 write seam --

def test_registered_artifacts_is_a_machine_table_at_the_bridge_seam(conn):
    from server import writes
    assert writes.is_machine_table("registered_artifacts") and not writes.is_human_table("registered_artifacts")
    with pytest.raises(PermissionError):
        writes.write_human(conn, "registered_artifacts", {"kind": "model", "path": "x", "created_at": "t"})
    rid = writes.write_machine(conn, "registered_artifacts", {"kind": "model", "path": "x.pth", "created_at": "2026-09-21T00:00:00", "active": 1})
    assert rid == 1
    # settings and audit are neither human verdicts nor machine detections: both doors refuse them
    for t in ("settings", "audit_log"):
        with pytest.raises(PermissionError):
            writes.write_human(conn, t, {"a": 1})
        with pytest.raises(PermissionError):
            writes.write_machine(conn, t, {"a": 1})
