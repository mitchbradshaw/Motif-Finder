"""
datasets.py
===========
A dataset's identity, plain SQL over the `datasets` table (fixup-f).

`recordings` is one row per channel. What a researcher calls a dataset is the
set of rows sharing a `source_file`, and its species, organism id, experiment
date, condition, display name and notes are properties of that set — so they
live here, one row per source file, and not on fourteen channel rows.

The rule every label in the project goes through is `display_name`:

    a dataset is printed by its display name when it has one, and by its
    source file when it does not.

There is no second fallback anywhere. A display name is a LABEL: nothing
keys, joins, filters, caches or routes on it, the files on disk keep their
names, and whatever prints the name carries the source file beside it,
because the file is what the disk and every log line say.

`recordings.notes` is per-channel text and is a different field from a
dataset's `notes`; nothing here reads or writes it.
"""
from __future__ import annotations

import datetime as _dt

#: The editable fields, in the order Settings › Datasets shows them.
FIELDS = ("display_name", "species", "organism_id", "experiment_date", "condition", "notes")

NAME_MAX = 60
ACTOR = "this installation"


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _clean(value):
    """A stored field: stripped text, or None when there is nothing in it."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def source_files(conn) -> list:
    """Every source file `recordings` knows, active or not, in name order."""
    return [r[0] for r in conn.execute("SELECT DISTINCT source_file FROM recordings ORDER BY source_file")]


def get_dataset(conn, source_file: str) -> dict:
    """The dataset's fields; every one None when the file has no row yet."""
    row = conn.execute(f"SELECT {', '.join(FIELDS)}, updated_at, actor FROM datasets WHERE source_file = ?",
                       (source_file,)).fetchone()
    out = {"source_file": source_file, **{f: None for f in FIELDS}, "updated_at": None, "actor": None}
    if row is not None:
        out.update(dict(zip((*FIELDS, "updated_at", "actor"), tuple(row))))
    return out


def list_datasets(conn) -> dict:
    """`source_file -> fields` for every file that has a row."""
    rows = conn.execute(f"SELECT source_file, {', '.join(FIELDS)}, updated_at, actor FROM datasets").fetchall()
    return {r[0]: dict(zip(("source_file", *FIELDS, "updated_at", "actor"), tuple(r))) for r in rows}


def display_name(conn, source_file: str) -> str:
    """THE rule: the display name when there is one, the source file when not."""
    row = conn.execute("SELECT display_name FROM datasets WHERE source_file = ?", (source_file,)).fetchone()
    return (row[0] if row is not None and row[0] else None) or str(source_file)


def display_names(conn) -> dict:
    """`source_file -> name` for every source file in `recordings`, named or not."""
    named = {r[0]: r[1] for r in conn.execute("SELECT source_file, display_name FROM datasets WHERE display_name IS NOT NULL")}
    return {sf: named.get(sf) or sf for sf in source_files(conn)}


def species_values(conn) -> list:
    """The species already in use — offered beside a free text field, never a locked vocabulary."""
    return [r[0] for r in conn.execute("SELECT DISTINCT species FROM datasets WHERE species IS NOT NULL ORDER BY species")]


def validate(conn, source_file: str, values: dict) -> dict:
    """The cleaned fields of `values`, or ValueError / KeyError. Writes nothing."""
    if not isinstance(values, dict):
        raise ValueError("values must be a mapping of field -> text")
    unknown = [k for k in values if k not in FIELDS]
    if unknown:
        raise ValueError(f"unknown dataset field {unknown[0]!r}; the fields are {', '.join(FIELDS)}")
    if conn.execute("SELECT 1 FROM recordings WHERE source_file = ? LIMIT 1", (source_file,)).fetchone() is None:
        raise KeyError(f"no recordings rows for {source_file!r}")
    clean = {k: _clean(v) for k, v in values.items()}
    date = clean.get("experiment_date")
    if date is not None:
        try:
            ok = _dt.date.fromisoformat(date).isoformat() == date
        except ValueError:
            ok = False
        if not ok:
            raise ValueError(f"experiment_date {date!r} is not a date; use YYYY-MM-DD")
    name = clean.get("display_name")
    if name is not None:
        if len(name) > NAME_MAX:
            raise ValueError(f"display_name is {len(name)} characters; at most {NAME_MAX}")
        low = name.lower()
        for other, other_name in display_names(conn).items():
            if other != source_file and low in (other_name.lower(), other.lower()):
                raise ValueError(f"display_name {name!r} is already what {other} is called")
    return clean


def put_dataset(conn, source_file: str, values: dict, actor: str = ACTOR, commit: bool = True) -> list:
    """Write the given fields; returns the ones whose stored value changed.

    A blank value clears the field. Refuses (ValueError) an unknown field, an
    `experiment_date` that is not YYYY-MM-DD, and a display name another
    dataset already answers to — by name or by file, which is the confusion
    the table exists to end. KeyError for a file `recordings` does not know.
    A refused write leaves nothing behind.
    """
    clean = validate(conn, source_file, values)
    current = get_dataset(conn, source_file)
    changed = [k for k, v in clean.items() if current[k] != v]
    if not changed:
        return []
    merged = {f: clean.get(f, current[f]) for f in FIELDS}
    conn.execute(
        f"INSERT INTO datasets (source_file, {', '.join(FIELDS)}, updated_at, actor) VALUES (?, {', '.join('?' for _ in FIELDS)}, ?, ?) "
        f"ON CONFLICT(source_file) DO UPDATE SET {', '.join(f'{f} = excluded.{f}' for f in FIELDS)}, "
        "updated_at = excluded.updated_at, actor = excluded.actor",
        (source_file, *(merged[f] for f in FIELDS), _now(), actor))
    if commit:
        conn.commit()
    return changed
