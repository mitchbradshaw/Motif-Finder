"""
settings.py
===========
Project settings and the audit log (spec §9 / P23), plain SQL over the two
tables ``init_db()`` creates: ``settings`` (page, key, value_json, updated_at,
actor) and ``audit_log`` (append-only — this module has no update or delete).

The held-out lock (D6) is a setting on the ``datasets`` page: ``heldout.on``
and ``heldout.recording``. Turning it OFF needs the recording's display name
typed exactly (``confirm_name``) and is written to the audit log with kind
``lock``; that rule lives here so every caller (the bridge, a script) gets
it. The routes' refusal of the held-out FILE (423) is separate and does not
read this setting.

Neither table is a rule-5 table: a setting is not a verdict and not a
detection, so ``webui.server.writes`` refuses both doors and the SQL here is
the only path.
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import re
import sqlite3

ACTOR = "this installation"
HELD_OUT_FILE = "M4_aug_concat_fs1.mat"
HELD_OUT_STEM = HELD_OUT_FILE[:-4]
HELD_OUT_PAGE = "datasets"
HELD_OUT_ON_KEY = "heldout.on"
HELD_OUT_RECORDING_KEY = "heldout.recording"

_PAGE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
_KEY_MAX = 200


class ConfirmationRequired(PermissionError):
    """Unlocking the held-out recording needs its name typed exactly."""

    def __init__(self, name: str):
        super().__init__(f"turning the held-out lock off needs the recording name typed exactly: {name!r}")
        self.name = name


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _check_page(page: str) -> None:
    if not isinstance(page, str) or not _PAGE.match(page):
        raise ValueError(f"bad settings page {page!r}: expected a slug like 'nulls' or 'storage-backups'")


def _check_key(key) -> None:
    if not isinstance(key, str) or not key.strip() or len(key) > _KEY_MAX or any(ord(ch) < 32 for ch in key):
        raise ValueError(f"bad settings key {key!r}")


# ---------------------------------------------------------------- settings --

def get_settings(conn: sqlite3.Connection, page: str) -> dict:
    _check_page(page)
    rows = conn.execute("SELECT key, value_json FROM settings WHERE page = ? ORDER BY key", (page,)).fetchall()
    return {r[0]: json.loads(r[1]) for r in rows}


def settings_meta(conn: sqlite3.Connection, page: str) -> dict:
    _check_page(page)
    row = conn.execute("SELECT MAX(updated_at), COUNT(*) FROM settings WHERE page = ?", (page,)).fetchone()
    actor = conn.execute("SELECT actor FROM settings WHERE page = ? ORDER BY updated_at DESC LIMIT 1", (page,)).fetchone()
    return {"updated_at": row[0], "n_keys": row[1], "actor": actor[0] if actor else None}


def held_out_state(conn: sqlite3.Connection) -> dict:
    v = get_settings(conn, HELD_OUT_PAGE)
    on = v.get(HELD_OUT_ON_KEY, True)
    rec = v.get(HELD_OUT_RECORDING_KEY) or HELD_OUT_STEM
    name = v.get(f"meta.{rec}.display_name") or rec
    return {"on": bool(on), "recording": str(rec), "name": str(name), "file": HELD_OUT_FILE}


def put_settings(conn: sqlite3.Connection, page: str, values, actor: str = ACTOR, confirm_name: str | None = None) -> list:
    """Upsert the given keys; returns the keys whose stored value changed
    (insertion order). Raises ``ConfirmationRequired`` for a held-out unlock
    without the exact typed name."""
    _check_page(page)
    if not isinstance(values, dict):
        raise ValueError("values must be a mapping of key -> JSON value")
    for k in values:
        _check_key(k)
    current = get_settings(conn, page)
    lock_change = None
    if page == HELD_OUT_PAGE and HELD_OUT_ON_KEY in values:
        state = held_out_state(conn)
        want = bool(values[HELD_OUT_ON_KEY])
        if state["on"] and not want:
            if confirm_name is None or confirm_name != state["name"]:
                raise ConfirmationRequired(state["name"])
            lock_change = ("off", state)
        elif not state["on"] and want:
            lock_change = ("on", state)
    changed = []
    now = _now()
    for k, v in values.items():
        vj = json.dumps(v, sort_keys=True)
        if k in current and json.dumps(current[k], sort_keys=True) == vj:
            continue
        conn.execute("INSERT INTO settings (page, key, value_json, updated_at, actor) VALUES (?, ?, ?, ?, ?) "
                     "ON CONFLICT(page, key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at, actor = excluded.actor",
                     (page, k, vj, now, actor))
        changed.append(k)
    if lock_change and HELD_OUT_ON_KEY in changed:
        which, state = lock_change
        what = (f"Held-out lock turned off · {state['name']} selectable in every workspace" if which == "off"
                else f"Held-out lock turned on · {state['name']} held out")
        append_audit(conn, "lock", what, "Datasets", route="settings/datasets", actor=actor,
                     detail={"recording": state["recording"], "name": state["name"], "on": which == "on"}, commit=False)
    conn.commit()
    return changed


# ------------------------------------------------------------------- audit --

def append_audit(conn: sqlite3.Connection, kind: str, what: str, where: str, route: str | None = None,
                 actor: str = ACTOR, detail: dict | None = None, commit: bool = True) -> int:
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError("audit kind must be a non-empty string")
    if not isinstance(what, str) or not what.strip():
        raise ValueError("audit 'what' must be a non-empty string")
    where = where if isinstance(where, str) and where.strip() else "Settings"
    cur = conn.execute("INSERT INTO audit_log (at, kind, what, where_, route, actor, detail_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (_now(), kind.strip(), what.strip(), where.strip(), route, actor or ACTOR, json.dumps(detail) if detail is not None else None))
    if commit:
        conn.commit()
    return int(cur.lastrowid)


def list_audit(conn: sqlite3.Connection, kind: str | None = None, limit: int = 500) -> list:
    """Newest first. ``kind`` filters; ``limit`` caps."""
    limit = max(1, min(int(limit), 10000))
    if kind and kind != "all":
        rows = conn.execute("SELECT * FROM audit_log WHERE kind = ? ORDER BY id DESC LIMIT ?", (kind, limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        r = dict(zip([d[0] for d in conn.execute("SELECT * FROM audit_log LIMIT 0").description], tuple(r))) if not hasattr(r, "keys") else dict(r)
        out.append({"id": r["id"], "when": r["at"], "kind": r["kind"], "what": r["what"], "where": r["where_"], "route": r["route"],
                    "by": r["actor"], "detail": json.loads(r["detail_json"]) if r["detail_json"] else None})
    return out


def audit_kinds(conn: sqlite3.Connection) -> list:
    return [r[0] for r in conn.execute("SELECT kind, COUNT(*) FROM audit_log GROUP BY kind ORDER BY kind")]


def audit_csv(conn: sqlite3.Connection, kind: str | None = None) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["when", "kind", "what", "where", "route", "by", "detail"])
    for e in reversed(list_audit(conn, kind=kind, limit=10000)):
        w.writerow([e["when"], e["kind"], e["what"], e["where"], e["route"] or "", e["by"], json.dumps(e["detail"]) if e["detail"] is not None else ""])
    return buf.getvalue()
