"""
core.py
=======
The generic half of registration: the ``Candidate`` / ``Check`` / ``Report``
types, ``scan`` / ``check`` / ``register`` / ``unregister`` / ``list_registered``
over the ``KindSpec`` registry in ``kinds.py``, the content hash, and the
sidecar manifest every registered artifact gets
(``<file>.manifest.json`` or ``<dir>/registration.manifest.json``).

Rows are inserted through a ``writer(conn, table, row) -> id`` callable. The
default is a plain ``INSERT``; the bridge passes ``webui.server.writes.
write_machine`` so a kind whose table is on the human side of rule 5 is
refused before any row lands.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass, field

ACTOR = "this installation"
SIDECAR_SUFFIX = ".manifest.json"
DIR_SIDECAR = "registration.manifest.json"
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class RegistrationError(RuntimeError):
    """A registration that cannot proceed: failing checks, or a candidate that no longer exists."""

    def __init__(self, message: str, report: "Report | None" = None):
        super().__init__(message)
        self.report = report


@dataclass
class Candidate:
    kind: str
    path: str                          # forward-slashed, as scanned (repo-relative when the root is)
    name: str
    facts: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    registered: bool = False
    registered_ids: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Report:
    candidate: Candidate
    checks: list = field(default_factory=list)
    facts: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    sha1: str | None = None
    excerpts: list = field(default_factory=list)     # registered rows that are excerpts of this candidate
    excerpt_of: dict | None = None                   # this candidate is an excerpt of a registered row

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def add(self, name: str, ok: bool, detail: str = "") -> bool:
        self.checks.append(Check(name, bool(ok), detail))
        return bool(ok)

    def warn(self, text: str) -> None:
        if text not in self.warnings:
            self.warnings.append(text)

    def failures(self) -> list:
        return [c for c in self.checks if not c.ok]

    def to_dict(self) -> dict:
        return {"candidate": self.candidate.to_dict(), "ok": self.ok, "checks": [dataclasses.asdict(c) for c in self.checks],
                "facts": self.facts, "warnings": list(self.warnings), "sha1": self.sha1, "excerpts": self.excerpts, "excerpt_of": self.excerpt_of}


# ------------------------------------------------------------------ helpers --

def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def portable(path: str) -> str:
    return path.replace(os.sep, "/") if path else path


def code_version() -> str:
    try:
        from Working.manifest import get_code_version
        return get_code_version()
    except Exception:  # pragma: no cover
        return "unknown"


def sha1_of(path: str, head_tail_mb: int = 4) -> str:
    """Content fingerprint. A file: sha1 of the whole file. A directory: sha1
    over every regular file (sorted) of name, size and the sha1 of its first
    and last ``head_tail_mb`` MB — bulk channel trees are gigabytes."""
    h = hashlib.sha1()
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            dirs.sort()
            for fn in sorted(files):
                if fn == DIR_SIDECAR or fn.endswith(SIDECAR_SUFFIX):
                    continue
                p = os.path.join(root, fn)
                rel = portable(os.path.relpath(p, path))
                h.update(rel.encode("utf-8")); h.update(str(os.path.getsize(p)).encode("ascii"))
                h.update(_head_tail_sha1(p, head_tail_mb).encode("ascii"))
        return h.hexdigest()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _head_tail_sha1(path: str, mb: int) -> str:
    n = mb << 20
    size = os.path.getsize(path)
    h = hashlib.sha1()
    with open(path, "rb") as f:
        h.update(f.read(n))
        if size > 2 * n:
            f.seek(size - n)
            h.update(f.read(n))
        elif size > n:
            h.update(f.read())
    return h.hexdigest()


def sidecar_path(candidate_or_path) -> str:
    path = candidate_or_path.path if isinstance(candidate_or_path, Candidate) else str(candidate_or_path)
    if os.path.isdir(path):
        return portable(os.path.join(path, DIR_SIDECAR))
    return portable(path + SIDECAR_SUFFIX)


def redirected_sidecar_path(path: str, sidecar_root: str | None) -> str:
    """Sandbox mode: the sidecar is written under ``sidecar_root`` mirroring the
    artifact's path, never beside the real artifact."""
    sc = sidecar_path(path)
    if not sidecar_root:
        return sc
    drive, rest = os.path.splitdrive(os.path.abspath(sc))
    rel = rest.lstrip("\\/")
    return portable(os.path.join(sidecar_root, drive.replace(":", ""), rel))


def read_sidecar(path: str, sidecar_root: str | None = None) -> dict | None:
    for p in (redirected_sidecar_path(path, sidecar_root), sidecar_path(path)):
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:  # a corrupt sidecar is reported, not hidden
                return {"error": f"{type(e).__name__}: {e}", "path": p}
    return None


def build_sidecar(candidate: Candidate, report: Report, provenance: dict | None, actor: str, row: dict) -> dict:
    prov = dict(provenance or {})
    f = report.facts
    return {
        "manifest_version": 1,
        "kind": candidate.kind,
        "name": candidate.name,
        "path": candidate.path,
        "source": {"recording": f.get("source_file"), "recording_id": f.get("recording_id"), "channel": f.get("channel"),
                   "span": f.get("span"), "raw_file": prov.get("raw_file") or f.get("raw_file")},
        "fs": f.get("fs"),
        "fs_source": f.get("fs_source"),
        "parameters": f.get("parameters", {}),
        "producer": prov.get("producer") or f.get("producer") or "unknown",
        "recipe_hash": prov.get("recipe_hash") or f.get("recipe_hash") or f.get("config_hash"),
        "created_at": now_iso(),
        "registered_by": actor,
        "code_version": code_version(),
        "checks_passed": [c.name for c in report.checks if c.ok],
        "warnings": list(report.warnings),
        "sha1": report.sha1,
        "row": row,
        "notes": prov.get("notes"),
    }


def plain_insert(conn: sqlite3.Connection, table: str, row: dict) -> int:
    if not _IDENT.match(table):
        raise ValueError(f"bad table name {table!r}")
    cols = list(row.keys())
    bad = [c for c in cols if not _IDENT.match(c)]
    if bad:
        raise ValueError(f"{table}: invalid column name(s) {bad!r}")
    cur = conn.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})", tuple(row[c] for c in cols))
    return int(cur.lastrowid)


# ------------------------------------------------------------------ the API --

def _spec(kind: str):
    from .kinds import KINDS
    if kind not in KINDS:
        raise KeyError(f"unknown kind {kind!r}; known: {sorted(KINDS)}")
    return KINDS[kind]


def scan(kind: str, roots=None, conn: sqlite3.Connection | None = None, **kw) -> list:
    """Every candidate of ``kind`` under ``roots`` (default: the kind's
    conventional directories), marked registered when ``conn`` knows it."""
    spec = _spec(kind)
    roots = list(roots) if roots else list(spec.roots)
    cands = spec.scan(roots, conn, **kw)
    if conn is not None:
        for c in cands:
            ids = spec.registered_ids(conn, c, **kw)
            c.registered = bool(ids)
            c.registered_ids = list(ids)
            if ids:
                c.warnings = []   # what a registered artifact lacks was settled at registration; the row carries its warnings
    return cands


def check(candidate: Candidate, conn: sqlite3.Connection | None, overrides: dict | None = None, **kw) -> Report:
    """Run the checks. Never raises for a bad file: the failure is a check."""
    spec = _spec(candidate.kind)
    rep = Report(candidate=candidate, facts=dict(candidate.facts), warnings=list(candidate.warnings))
    ov = dict(overrides or {})
    exists = os.path.exists(candidate.path)
    rep.add("exists", exists, candidate.path if exists else f"{candidate.path} does not exist")
    if not exists:
        return rep
    try:
        spec.check(candidate, conn, rep, ov, **kw)
    except Exception as e:  # a kind's checker must never take the route down
        rep.add("readable", False, f"{type(e).__name__}: {e}")
    if conn is not None:
        ids = spec.registered_ids(conn, candidate, **kw)
        rep.add("not_registered", not ids, f"already registered as {spec.table} id(s) {ids}" if ids else "not registered yet")
    if rep.sha1 is None:
        try:
            rep.sha1 = sha1_of(candidate.path)
            rep.add("hash", True, rep.sha1)
        except Exception as e:
            rep.add("hash", False, f"{type(e).__name__}: {e}")
    return rep


def register(conn: sqlite3.Connection, candidate: Candidate, report: Report | None = None, provenance: dict | None = None,
             actor: str = ACTOR, overrides: dict | None = None, writer=None, sidecar_root: str | None = None, **kw) -> int:
    """Insert the row(s) through ``writer`` and write the sidecar; commits.
    Refuses (``RegistrationError``) unless every check passes."""
    spec = _spec(candidate.kind)
    if report is None:
        report = check(candidate, conn, overrides, **kw)
    if not report.ok:
        bad = "; ".join(f"{c.name}: {c.detail}" for c in report.failures())
        raise RegistrationError(f"{candidate.kind} {candidate.name!r} cannot be registered — {bad}", report)
    writer = writer or plain_insert
    row_id, row = spec.register(conn, candidate, report, provenance, actor, writer, **kw)
    sc = redirected_sidecar_path(candidate.path, sidecar_root)
    os.makedirs(os.path.dirname(sc) or ".", exist_ok=True)
    with open(sc, "w", encoding="utf-8") as f:
        json.dump(build_sidecar(candidate, report, provenance, actor, row), f, indent=2, default=str)
    if spec.table == "registered_artifacts":
        conn.execute("UPDATE registered_artifacts SET manifest_path = ? WHERE id = ?", (sc, row_id))
    conn.commit()
    return row_id


def unregister(conn: sqlite3.Connection, kind: str, row_id: int, actor: str = ACTOR) -> dict:
    """Soft: ``active = 0``. The row, its id and everything referencing it stay."""
    spec = _spec(kind)
    out = spec.unregister(conn, row_id, actor)
    conn.commit()
    return out


def list_registered(conn: sqlite3.Connection, kind: str, sidecar_root: str | None = None, **kw) -> list:
    return _spec(kind).list_registered(conn, sidecar_root=sidecar_root, **kw)
