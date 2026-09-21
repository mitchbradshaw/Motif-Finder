"""The rule-5 seam: every write the bridge makes goes through one of two doors.

CLAUDE.md rule 5 — *detections are machine-only; annotations are human-only.
They are separate tables on purpose. No code path may write a human verdict
into a machine row or the reverse.*

``write_human(conn, table, row)`` accepts only the tables a person's verdict,
tag, template or motif-library edit lands in; ``write_machine(conn, table,
row)`` accepts only the tables a run, its detections and its artifacts land
in. Each refuses the other's tables — and any table on neither list — with a
``PermissionError`` that names the rule, so a route wired to the wrong door
fails loudly on its first request instead of quietly crossing the line.

Both are plain-SQL inserts (``INSERT INTO <table> (<cols>) VALUES (?, ...)``),
return the new row id, and do not commit — the caller owns the transaction,
exactly as ``Working.database.*`` does. Identifiers are validated before any
SQL is built. No route uses these yet; stage-3 prompts 01 and 02 do.
"""
from __future__ import annotations

import re
import sqlite3

HUMAN_TABLES = frozenset({
    "annotations", "annotation_tags",
    "adjudications", "adjudication_tags",
    "templates", "tag_vocabulary",
    "reviewed_spans",   # a person looked at this span (Review/Explore coverage) - human-side
    # stage-3 Prompt 03 (docs/LIBRARY_STORAGE.md 3.5): a grouping is a question
    # a researcher asked of the catalogue, and its assignments are that
    # question's answer. A hand edit is a person overruling the computation.
    "groupings", "grouping_assignments", "hand_edits",
})
HUMAN_PREFIXES = ("motif_",)   # motif_entry, motif_member, motif_edge, motif_entry_tags, motif_tags,
                               # motif_member_revision

MACHINE_TABLES = frozenset({
    "detections", "runs", "configs", "artifacts", "encodings", "step_artifacts", "recordings",
    "run_groups",       # a fan-out of runs is made by the machine, like the runs in it
    "registered_artifacts",   # stage-3 Prompt 02: a registered model / matrix profile / window matrix / ... is machine data
    "window_sets",      # stage-3 Prompt 03: a window set is produced by a chain, like the artifacts above it
    # stage-3 Prompt 04: a Discovery session's scope and its run rows. Machine
    # data, like `run_groups`: a scope is not a verdict. They are written with
    # their own plain SQL today (the rows are upserted, and this door only
    # inserts), but they belong on a list so a later caller reaching for the
    # seam gets a write rather than a confusing refusal.
    "discovery_sessions", "discovery_runs",
})
# `settings` and `audit_log` are on NEITHER list on purpose: a project setting is
# not a verdict and not a detection, so both doors refuse them and
# Working.registration.settings writes them with its own plain SQL.
#
# `sequences` and `sequence_members` are on neither list for a different reason:
# they are the one pair whose side is decided PER ROW, by the row's own `origin`
# column. A sequence read out of `Plots/drop_motifs11/sequences.csv` is a
# detector's claim (`origin = 'machine'`); one read out of `annotations` is a
# person's (`origin = 'human'`). Putting the table on either list would declare
# a side for both kinds and make the wrong half a quiet crossing — exactly what
# rule 5 exists to prevent — and putting it on both would mean the door checks
# nothing. So the importers in `Working/library/importers/` write these two
# tables with their own plain SQL, as `Working.registration.settings` does, and
# the `origin` column carries the distinction where a reader can see it.
#
# If a route ever needs to write a sequence, do NOT add these tables here. Add a
# `write_sequence(conn, table, row)` that reads `origin`, refuses a row without a
# valid one, and dispatches to the right door — so the rule stays executable
# rather than becoming a convention someone has to remember.

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RULE = "rule 5 (CLAUDE.md): detections are machine-only, annotations are human-only"


def is_human_table(table: str) -> bool:
    return table in HUMAN_TABLES or table.startswith(HUMAN_PREFIXES)


def is_machine_table(table: str) -> bool:
    return table in MACHINE_TABLES


def write_human(conn: sqlite3.Connection, table: str, row: dict) -> int:
    """Insert a human-authored row. Refuses every machine table."""
    if not isinstance(table, str) or not _IDENT.match(table) or not is_human_table(table):
        side = "a machine-only table" if isinstance(table, str) and is_machine_table(table) else "not a human table"
        raise PermissionError(
            f"write_human refuses {table!r}: {side}. {RULE}. "
            f"Human tables: {sorted(HUMAN_TABLES)} and motif_*.")
    return _insert(conn, table, row)


def write_machine(conn: sqlite3.Connection, table: str, row: dict) -> int:
    """Insert a machine-produced row. Refuses every human table."""
    if not isinstance(table, str) or not _IDENT.match(table) or not is_machine_table(table):
        side = "a human-only table" if isinstance(table, str) and is_human_table(table) else "not a machine table"
        raise PermissionError(
            f"write_machine refuses {table!r}: {side}. {RULE}. "
            f"Machine tables: {sorted(MACHINE_TABLES)}.")
    return _insert(conn, table, row)


def _insert(conn: sqlite3.Connection, table: str, row: dict) -> int:
    if not isinstance(row, dict) or not row:
        raise ValueError(f"{table}: row must be a non-empty dict of column -> value")
    cols = list(row.keys())
    bad = [c for c in cols if not isinstance(c, str) or not _IDENT.match(c)]
    if bad:
        raise ValueError(f"{table}: invalid column name(s) {bad!r}")
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
    cur = conn.execute(sql, tuple(row[c] for c in cols))
    return int(cur.lastrowid)
