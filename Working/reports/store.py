"""The `reports` table: one row per saved snapshot — its PATH, never its bytes
(CLAUDE.md rule 4). The table is created by `init_db()` (`schema._migrate_reports_table`).

Not a rule-5 table: a report is neither a detection nor a verdict.
"""
from __future__ import annotations

import datetime as _dt


def _now():
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def record(conn, *, kind, path, run_key=None, run_id=None, session_id=None, title=None, note=None,
           created_at=None) -> int:
    cur = conn.execute(
        "INSERT INTO reports (kind, run_key, run_id, session_id, title, created_at, path, note) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (kind, run_key, run_id, session_id, title, created_at or _now(), str(path), note))
    conn.commit()
    return int(cur.lastrowid)


def _row(r) -> dict:
    return {k: r[k] for k in r.keys()}


def list_reports(conn) -> list[dict]:
    """Every snapshot, newest first."""
    return [_row(r) for r in conn.execute("SELECT * FROM reports ORDER BY id DESC").fetchall()]


def get_report(conn, report_id) -> dict | None:
    r = conn.execute("SELECT * FROM reports WHERE id = ?", (int(report_id),)).fetchone()
    return _row(r) if r is not None else None
