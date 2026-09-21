"""
test_webui_writes.py
====================
Rule 5 (CLAUDE.md): detections are machine-only, annotations are human-only,
and no code path may write a human verdict into a machine row or the reverse.

`webui/server/writes.py` is the one seam every future write route of the
bridge goes through. `write_human` accepts only the human tables, and
`write_machine` only the machine tables; each refuses the other's with a
`PermissionError` that names rule 5, so a route wired to the wrong function
fails loudly on its first request rather than silently crossing the line.

No route uses these yet (stage-3 prompts 01 and 02 will); this file proves the
refusal and the happy path against a fresh in-memory `init_db()`.
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from Working.database.schema import init_db  # noqa: E402
from server import writes  # noqa: E402

HUMAN = ("annotations", "annotation_tags", "adjudications", "adjudication_tags",
         "motif_entry", "motif_member", "motif_edge", "motif_entry_tags", "motif_tags",
         "templates", "tag_vocabulary")
MACHINE = ("detections", "runs", "configs", "artifacts", "encodings", "step_artifacts", "recordings")


@pytest.fixture
def conn():
    c = init_db(":memory:")
    try:
        yield c
    finally:
        c.close()


def _recording(conn):
    return writes.write_machine(conn, "recordings", {
        "source_file": "probe.mat", "channel": 0, "fs": 1.0, "n_samples": 100,
        "global_offset": 0, "npy_path": "probe.npy"})


# ── the seam refuses the other side's tables, naming rule 5 ───────────────

@pytest.mark.parametrize("table", MACHINE)
def test_write_human_refuses_every_machine_table(conn, table):
    with pytest.raises(PermissionError) as excinfo:
        writes.write_human(conn, table, {"id": 1})
    assert "rule 5" in str(excinfo.value)
    assert table in str(excinfo.value)


@pytest.mark.parametrize("table", HUMAN)
def test_write_machine_refuses_every_human_table(conn, table):
    with pytest.raises(PermissionError) as excinfo:
        writes.write_machine(conn, table, {"id": 1})
    assert "rule 5" in str(excinfo.value)
    assert table in str(excinfo.value)


def test_a_table_on_neither_list_is_refused_by_both(conn):
    for fn in (writes.write_human, writes.write_machine):
        with pytest.raises(PermissionError) as excinfo:
            fn(conn, "annotations_rebuild", {"id": 1})
        assert "rule 5" in str(excinfo.value)


def test_a_refused_write_leaves_the_database_untouched(conn):
    rec = _recording(conn)
    with pytest.raises(PermissionError):
        writes.write_human(conn, "detections", {"run_id": 1, "recording_id": rec,
                                                "start_idx": 0, "end_idx": 5})
    assert conn.execute("SELECT COUNT(*) FROM detections").fetchone()[0] == 0


def test_table_and_column_names_are_validated_before_any_sql(conn):
    with pytest.raises(PermissionError):
        writes.write_machine(conn, "recordings; DROP TABLE recordings", {"id": 1})
    with pytest.raises(ValueError):
        writes.write_machine(conn, "recordings", {"source_file); DROP TABLE recordings; --": "x"})
    assert conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0] == 0


# ── the happy path: each side writes its own tables ───────────────────────

def test_write_machine_inserts_a_machine_row_and_returns_its_id(conn):
    rec = _recording(conn)
    assert isinstance(rec, int) and rec > 0
    row = conn.execute("SELECT source_file, channel FROM recordings WHERE id = ?", (rec,)).fetchone()
    assert tuple(row) == ("probe.mat", 0)


def test_write_human_inserts_a_human_row_and_returns_its_id(conn):
    rec = _recording(conn)
    ann = writes.write_human(conn, "annotations", {
        "recording_id": rec, "start_idx": 10, "end_idx": 20, "label": "spike"})
    assert isinstance(ann, int) and ann > 0
    assert conn.execute("SELECT label FROM annotations WHERE id = ?", (ann,)).fetchone()[0] == "spike"
    assert conn.execute("SELECT COUNT(*) FROM detections").fetchone()[0] == 0


def test_the_motif_prefix_is_human(conn):
    rec = _recording(conn)
    entry = writes.write_human(conn, "motif_entry", {
        "recording_id": rec, "start_idx": 0, "end_idx": 10})
    assert entry > 0
