"""
test_library_schema.py
======================
The Library's storage shape, as fixed by `docs/LIBRARY_STORAGE.md` §3.2–§3.3
(stage-3 prompt 03).

Three things are asserted here and nothing else: that `init_db()` produces
every new table and column; that it stays **idempotent** and **non-destructive**
on a database that predates them (the real 4 MB `DATA/db/annotations.sqlite`
will take exactly that path, once, with 11 269 annotations on it); and that the
CHECK/UNIQUE constraints the standard writes down actually bite at the SQLite
level rather than being decoration a Python writer is trusted to honour.

Every test builds its own database in a tmp_path. Nothing here may touch
`DATA/db/annotations.sqlite`.
"""

import sqlite3

import pytest

from Working.database import schema


def _columns(conn, table):
    """The live column names of `table`, from PRAGMA — the same source `_migrate_columns` reads."""
    return [row["name"] for row in conn.execute(f"PRAGMA table_info({table})")]


def _tables(conn):
    return {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


def _indexes(conn):
    return {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
    }


def _seed_member(conn):
    """A recording → entry → member chain, so FK-carrying inserts have something real to point at.

    `get_connection` turns `PRAGMA foreign_keys` ON, so a revision or an
    assignment cannot be tested against an invented member id.
    """
    rec = conn.execute(
        "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path)"
        " VALUES ('x.mat', 0, 1.0, 100, 0, 'x.npy')"
    ).lastrowid
    entry = conn.execute(
        "INSERT INTO motif_entry (recording_id, start_idx, end_idx) VALUES (?, 0, 10)",
        (rec,),
    ).lastrowid
    member = conn.execute(
        "INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx)"
        " VALUES (?, ?, 0, 10)",
        (entry, rec),
    ).lastrowid
    conn.commit()
    return rec, entry, member


NEW_TABLES = {
    "motif_member_revision",
    "sequences",
    "sequence_members",
    "groupings",
    "grouping_assignments",
    "hand_edits",
    "window_sets",
}


# --------------------------------------------------------------------------
# The tables and columns exist
# --------------------------------------------------------------------------

def test_init_db_creates_every_new_library_table(tmp_path):
    conn = schema.init_db(str(tmp_path / "fresh.sqlite"))
    try:
        assert NEW_TABLES <= _tables(conn)
    finally:
        conn.close()


@pytest.mark.parametrize(
    "table,expected",
    [
        (
            "motif_member_revision",
            {"id", "member_id", "revision", "origin", "detection_id", "annotation_id",
             "start_idx", "end_idx", "content_hash", "created_at", "superseded_at"},
        ),
        (
            "sequences",
            {"id", "sequence_key", "origin", "recording_id", "channel", "start_idx",
             "end_idx", "n_events", "needs_extraction", "source_kind", "source_store",
             "source_ref", "annotation_id", "content_hash", "created_at"},
        ),
        (
            "sequence_members",
            {"id", "sequence_id", "position", "member_id", "start_idx", "end_idx",
             "gap_before"},
        ),
        (
            "groupings",
            {"id", "name", "unit", "basis", "method", "params_json", "cut",
             "filters_json", "n_families", "n_assigned", "n_omitted", "recipe_hash",
             "created_at", "actor"},
        ),
        (
            "grouping_assignments",
            {"id", "grouping_id", "unit", "member_ref", "content_hash", "family_id",
             "family_label", "distance", "is_medoid", "omit_reason"},
        ),
        (
            "hand_edits",
            {"id", "content_hash", "kind", "family_label", "value", "grouping_id",
             "active", "created_at", "actor"},
        ),
        (
            "window_sets",
            {"id", "name", "version", "path", "recording_id", "channel", "fs",
             "window_length", "stride", "gap", "n_windows", "split_json",
             "spacing_json", "coverage_json", "labels_source", "recipe_hash",
             "created_at"},
        ),
    ],
)
def test_new_table_carries_every_column_the_standard_names(tmp_path, table, expected):
    conn = schema.init_db(str(tmp_path / "fresh.sqlite"))
    try:
        assert set(_columns(conn, table)) == expected
    finally:
        conn.close()


def test_motif_entry_and_member_gain_the_identity_columns(tmp_path):
    conn = schema.init_db(str(tmp_path / "fresh.sqlite"))
    try:
        entry_cols = set(_columns(conn, "motif_entry"))
        assert {"content_hash", "channel", "fs", "source_kind", "source_store",
                "source_ref", "scale"} <= entry_cols
        member_cols = set(_columns(conn, "motif_member"))
        assert {"content_hash", "channel", "current_revision_id"} <= member_cols
    finally:
        conn.close()


def test_the_reader_indexes_exist(tmp_path):
    conn = schema.init_db(str(tmp_path / "fresh.sqlite"))
    try:
        assert {
            "idx_motif_entry_content_hash",
            "idx_motif_member_content_hash",
            "idx_motif_member_revision_member",
            "idx_sequences_origin",
            "idx_sequences_needs_extraction",
            "idx_sequence_members_sequence",
            "idx_grouping_assignments_grouping",
            "idx_grouping_assignments_content_hash",
            "idx_hand_edits_content_hash",
            "idx_window_sets_name",
        } <= _indexes(conn)
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Idempotence and the migration path the live database will take
# --------------------------------------------------------------------------

def test_init_db_is_idempotent(tmp_path):
    """Twice on one file: no error, and no column added a second time."""
    path = str(tmp_path / "twice.sqlite")
    first = schema.init_db(path)
    before = {t: _columns(first, t) for t in sorted(NEW_TABLES | {"motif_entry", "motif_member"})}
    first.close()

    second = schema.init_db(path)
    try:
        after = {t: _columns(second, t) for t in before}
        assert after == before
        for cols in after.values():
            assert len(cols) == len(set(cols))
    finally:
        second.close()


_OLD_MOTIF_SCHEMA = """
CREATE TABLE recordings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file   TEXT    NOT NULL,
    channel       INTEGER NOT NULL,
    fs            REAL    NOT NULL,
    n_samples     INTEGER NOT NULL,
    global_offset INTEGER NOT NULL,
    npy_path      TEXT    NOT NULL,
    notes         TEXT,
    UNIQUE (source_file, channel)
);
CREATE TABLE motif_entry (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    recording_id  INTEGER NOT NULL REFERENCES recordings(id),
    start_idx     INTEGER NOT NULL,
    end_idx       INTEGER NOT NULL,
    detection_id  INTEGER,
    label         TEXT,
    rating        INTEGER,
    notes         TEXT,
    tags          TEXT,
    sax_string    TEXT,
    created_at    TEXT,
    UNIQUE (recording_id, start_idx, end_idx)
);
CREATE TABLE motif_member (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id      INTEGER NOT NULL REFERENCES motif_entry(id),
    recording_id  INTEGER NOT NULL REFERENCES recordings(id),
    start_idx     INTEGER NOT NULL,
    end_idx       INTEGER NOT NULL
);
"""


def test_migration_over_an_old_database_keeps_its_rows(tmp_path):
    """The path the live 4 MB database takes: pre-Prompt-03 tables, with rows on them.

    ALTER TABLE ADD COLUMN must be the only thing that happens to `motif_entry`
    and `motif_member` — a rebuild here would put real curated rows at risk.
    """
    path = str(tmp_path / "old.sqlite")
    old = sqlite3.connect(path)
    old.executescript(_OLD_MOTIF_SCHEMA)
    old.execute(
        "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path)"
        " VALUES ('legacy.mat', 3, 1.0, 5000, 0, 'legacy.npy')"
    )
    old.execute(
        "INSERT INTO motif_entry (recording_id, start_idx, end_idx, label)"
        " VALUES (1, 100, 200, 'kept')"
    )
    old.execute(
        "INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx)"
        " VALUES (1, 1, 100, 200)"
    )
    old.commit()
    old.close()

    conn = schema.init_db(path)
    try:
        entry = conn.execute("SELECT * FROM motif_entry").fetchall()
        assert len(entry) == 1
        assert entry[0]["label"] == "kept"
        assert entry[0]["start_idx"] == 100
        assert entry[0]["content_hash"] is None
        member = conn.execute("SELECT * FROM motif_member").fetchall()
        assert len(member) == 1
        assert member[0]["current_revision_id"] is None
        assert NEW_TABLES <= _tables(conn)
    finally:
        conn.close()


# --------------------------------------------------------------------------
# The constraints bite
# --------------------------------------------------------------------------

def test_revision_origin_check_bites(tmp_path):
    conn = schema.init_db(str(tmp_path / "c.sqlite"))
    try:
        _rec, _entry, member = _seed_member(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO motif_member_revision"
                " (member_id, revision, origin, start_idx, end_idx, created_at)"
                " VALUES (?, 1, 'robot', 0, 10, 'now')",
                (member,),
            )
    finally:
        conn.close()


def test_sequences_origin_check_bites(tmp_path):
    conn = schema.init_db(str(tmp_path / "c.sqlite"))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO sequences (sequence_key, origin, created_at)"
                " VALUES ('s1', 'detector', 'now')"
            )
    finally:
        conn.close()


def test_grouping_unit_check_bites(tmp_path):
    conn = schema.init_db(str(tmp_path / "c.sqlite"))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO groupings (name, unit, basis, method, params_json, created_at)"
                " VALUES ('g', 'everything', 'shape-distance', 'ward', '{}', 'now')"
            )
    finally:
        conn.close()


def test_hand_edit_kind_check_bites(tmp_path):
    conn = schema.init_db(str(tmp_path / "c.sqlite"))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO hand_edits (content_hash, kind, created_at)"
                " VALUES ('abc', 'rename', 'now')"
            )
    finally:
        conn.close()


def test_revision_unique_per_member(tmp_path):
    conn = schema.init_db(str(tmp_path / "c.sqlite"))
    try:
        _rec, _entry, member = _seed_member(conn)
        sql = (
            "INSERT INTO motif_member_revision"
            " (member_id, revision, origin, start_idx, end_idx, created_at)"
            " VALUES (?, 1, 'machine', 0, 10, 'now')"
        )
        conn.execute(sql, (member,))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql, (member,))
    finally:
        conn.close()


def test_sequence_key_unique_per_origin(tmp_path):
    """The same key from a detector and from a person are two different claims (§3.5)."""
    conn = schema.init_db(str(tmp_path / "c.sqlite"))
    try:
        conn.execute(
            "INSERT INTO sequences (sequence_key, origin, created_at)"
            " VALUES ('oyster_id10', 'machine', 'now')"
        )
        conn.execute(
            "INSERT INTO sequences (sequence_key, origin, created_at)"
            " VALUES ('oyster_id10', 'human', 'now')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO sequences (sequence_key, origin, created_at)"
                " VALUES ('oyster_id10', 'machine', 'now')"
            )
    finally:
        conn.close()


def test_sequence_member_position_unique(tmp_path):
    conn = schema.init_db(str(tmp_path / "c.sqlite"))
    try:
        seq = conn.execute(
            "INSERT INTO sequences (sequence_key, origin, created_at)"
            " VALUES ('s', 'machine', 'now')"
        ).lastrowid
        sql = (
            "INSERT INTO sequence_members (sequence_id, position, start_idx, end_idx)"
            " VALUES (?, 0, 0, 10)"
        )
        conn.execute(sql, (seq,))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql, (seq,))
    finally:
        conn.close()


def test_sequence_member_may_have_no_extracted_member(tmp_path):
    """needs_extraction = 1 means the events are claimed, not invented (§4)."""
    conn = schema.init_db(str(tmp_path / "c.sqlite"))
    try:
        seq = conn.execute(
            "INSERT INTO sequences (sequence_key, origin, needs_extraction, created_at)"
            " VALUES ('s', 'human', 1, 'now')"
        ).lastrowid
        conn.execute(
            "INSERT INTO sequence_members (sequence_id, position, member_id, start_idx, end_idx)"
            " VALUES (?, 0, NULL, 0, 10)",
            (seq,),
        )
        conn.commit()
        row = conn.execute("SELECT member_id FROM sequence_members").fetchone()
        assert row["member_id"] is None
    finally:
        conn.close()


def test_grouping_assignment_unique_per_member(tmp_path):
    conn = schema.init_db(str(tmp_path / "c.sqlite"))
    try:
        _rec, _entry, member = _seed_member(conn)
        grouping = conn.execute(
            "INSERT INTO groupings (name, unit, basis, method, params_json, created_at)"
            " VALUES ('g', 'single_motifs', 'shape-distance', 'ward', '{}', 'now')"
        ).lastrowid
        sql = (
            "INSERT INTO grouping_assignments (grouping_id, unit, member_ref)"
            " VALUES (?, 'single_motifs', ?)"
        )
        conn.execute(sql, (grouping, member))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql, (grouping, member))
    finally:
        conn.close()


def test_window_set_unique_name_version(tmp_path):
    conn = schema.init_db(str(tmp_path / "c.sqlite"))
    try:
        conn.execute(
            "INSERT INTO window_sets (name, version, path, created_at)"
            " VALUES ('ws', 1, 'DATA/derived/window_sets/ws/windows.npz', 'now')"
        )
        conn.execute(
            "INSERT INTO window_sets (name, version, path, created_at)"
            " VALUES ('ws', 2, 'DATA/derived/window_sets/ws/windows.npz', 'now')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO window_sets (name, version, path, created_at)"
                " VALUES ('ws', 1, 'DATA/derived/window_sets/ws/windows.npz', 'now')"
            )
    finally:
        conn.close()
