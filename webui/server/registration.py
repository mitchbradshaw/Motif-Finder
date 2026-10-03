"""Registry, settings, audit, about and storage routes (stage-3 Prompt 02).

Thin over ``Working.registration``: every route is a few lines. Rows are
written through the rule-5 door ``writes.write_machine``; settings and the
audit log through ``Working.registration.settings`` (neither is a rule-5
table). In sandbox mode everything lands in the runtime copy — the database
copy, sidecars under ``<runtime>/sidecars/``, derived channels under
``<runtime>/derived/channels`` — and in project mode in the real places.
"""
from __future__ import annotations

import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from Working.database import datasets
from Working.discovery.channels import channel_index_note
from Working.registration import KINDS, RegistrationError, check, list_registered, register, scan, unregister
from Working.registration.settings import (
    ConfirmationRequired, append_audit, audit_csv, audit_kinds, get_settings, held_out_state, list_audit, put_settings, settings_meta,
)

from . import corpus, writes
from .runtime import HELD_OUT_FILE, REPO_ROOT

router = APIRouter()

PAGE_TITLES = {
    "datasets": "Datasets", "channels-events": "Channels & events", "vocabulary": "Vocabulary", "nulls": "Nulls",
    "analysis-defaults": "Analysis defaults", "compute-hpc": "Compute & HPC", "blocks": "Blocks", "review-queues": "Review queues",
    "models-registration": "Models & registration", "library-groupings": "Library groupings", "storage-backups": "Storage & backups",
    "export": "Export", "audit-log": "Audit log", "about": "About", "display": "Display", "keyboard": "Keyboard & behaviour",
}


class PathBody(BaseModel):
    path: str
    overrides: dict = Field(default_factory=dict)
    provenance: dict = Field(default_factory=dict)
    actor: str = "this installation"


class SettingsBody(BaseModel):
    values: dict
    confirm_name: str | None = None
    actor: str = "this installation"
    previous: dict = Field(default_factory=dict)   # the effective values the page showed before the edit (defaults live client-side)


class AuditBody(BaseModel):
    kind: str
    what: str
    where: str = "Settings"
    route: str | None = None
    detail: dict | None = None
    actor: str = "this installation"


def _rt(request: Request):
    return request.app.state.rt


def _conn(request: Request) -> sqlite3.Connection:
    rt = _rt(request)
    if not getattr(request.app.state, "schema_ensured", False):
        # rule 3: additive migrations through init_db(), idempotent — the settings, audit and
        # registered_artifacts tables and the registration columns exist before any route reads them
        from Working.database.schema import init_db
        init_db(rt.db_path).close()
        request.app.state.schema_ensured = True
    return corpus.connect(rt.db_path)


def _roots(request: Request, kind: str) -> list:
    over = getattr(request.app.state, "registry_roots", None) or {}
    roots = list(over.get(kind) or KINDS[kind].roots)
    rt = _rt(request)
    if kind == "recording" and not over and rt.mode == "sandbox":
        # what the raw kind derives in sandbox mode lands under the runtime dir: scan it too
        extra = os.path.join(rt.dir, "derived", "channels")
        if os.path.isdir(extra):
            roots.append(extra)
    return roots


def _kw(request: Request, kind: str) -> dict:
    rt = _rt(request)
    kw = {}
    if kind == "raw":
        over = getattr(request.app.state, "registry_roots", None) or {}
        kw["channels_root"] = (over.get("recording") or [None])[0] or (
            os.path.join(rt.dir, "derived", "channels") if rt.mode == "sandbox" else KINDS["recording"].roots[0])
    return kw


def _sidecar_root(request: Request) -> str | None:
    rt = _rt(request)
    return os.path.join(rt.dir, "sidecars") if rt.mode == "sandbox" else None


def _audit_surface(kind: str) -> tuple:
    """The Settings page a registration of `kind` is done on: where the audit entry links."""
    if kind in ("recording", "raw"):
        return "Datasets", "settings/datasets"
    if kind == "model":
        return "Models & registration", "settings/models-registration"
    return "Storage & backups", "settings/storage-backups"


def _kind_or_404(kind: str):
    if kind not in KINDS:
        raise HTTPException(404, f"no such registry kind {kind!r}; kinds: {sorted(KINDS)}")
    return KINDS[kind]


def _find_candidate(request: Request, kind: str, path: str):
    kw = _kw(request, kind)
    c = _conn(request)
    try:
        for cand in scan(kind, roots=_roots(request, kind), conn=c, **kw):
            if cand.path == path or os.path.abspath(cand.path).lower() == os.path.abspath(path).lower():
                return cand
    finally:
        c.close()
    raise HTTPException(404, f"{kind}: no candidate at {path!r} under {_roots(request, kind)}")


def _registered_payload(request: Request, kind: str, c) -> list:
    out = list_registered(c, kind, sidecar_root=_sidecar_root(request))
    if kind == "recording":
        meta = datasets.list_datasets(c)
        for r in out:
            n = r["n_channels"]
            notes = dict(c.execute("SELECT id, notes FROM recordings WHERE source_file = ?", (r["source_file"],)).fetchall())
            for ch in r["channels"]:
                ch["name"] = corpus.channel_name(r["source_file"], ch["channel"], n)
                # per-CHANNEL text (recordings.notes): a different field from the dataset's notes, shown apart
                ch["notes"] = notes.get(ch["id"])
            # fixup-f: what the dataset is called and the identity Settings › Datasets authors; `name` stays
            # the directory stem (a key), `display_name` is the label
            r["display_name"] = corpus.dataset_name(c, r["source_file"])
            r["dataset"] = {f: (meta.get(r["source_file"]) or {}).get(f) for f in datasets.FIELDS}
            if r.get("excerpt_of"):
                _name_excerpt(c, r["excerpt_of"])
    return out


def _name_excerpt(c, link: dict, key: str = "channel") -> None:
    """An excerpt link names its parent's channel by the one convention and its parent by the one name."""
    sf = link.get("source_file")
    if sf is None or link.get(key) is None:
        return
    n = c.execute("SELECT COUNT(*) FROM recordings WHERE source_file = ?", (sf,)).fetchone()[0]
    link["channel_name"] = corpus.channel_name(sf, link[key], n)
    link["channel_note"] = channel_index_note(link[key])
    link["display_name"] = corpus.dataset_name(c, sf)


# ---------------------------------------------------------------- datasets --

_META = "meta."


def _stems(request: Request, c) -> dict:
    """`directory stem -> source_file` for every registered recording (the stem is what the page keys by)."""
    return {r["name"]: r["source_file"] for r in list_registered(c, "recording", sidecar_root=_sidecar_root(request))}


def _dataset_values(request: Request, c) -> dict:
    """The `datasets` table as the page's `meta.<stem>.<field>` values (only what is filled)."""
    meta = datasets.list_datasets(c)
    out = {}
    for stem, sf in _stems(request, c).items():
        for f in datasets.FIELDS:
            v = (meta.get(sf) or {}).get(f)
            if v is not None:
                out[f"{_META}{stem}.{f}"] = v
    return out


def _split_dataset_keys(request: Request, c, values: dict) -> tuple:
    """(`{source_file: {field: value}}`, the remaining settings values, `{(source_file, field): key}`)."""
    stems = _stems(request, c)
    by_file, rest, keys = {}, {}, {}
    for k, v in values.items():
        stem, _, field = k[len(_META):].rpartition(".") if k.startswith(_META) else ("", "", "")
        if field in datasets.FIELDS and stem in stems:
            by_file.setdefault(stems[stem], {})[field] = v
            keys[(stems[stem], field)] = k
        else:
            rest[k] = v
    return by_file, rest, keys


def _put_datasets(c, by_file: dict, keys: dict, actor: str) -> list:
    """Write the dataset fields (uncommitted), audit each file's change by its FILE name; the changed page keys."""
    changed = []
    lock_on = held_out_state(c)["on"]
    for sf, fields in by_file.items():
        if sf == HELD_OUT_FILE and lock_on:
            raise HTTPException(423, f"{HELD_OUT_FILE} is held out · its metadata is read-only while the lock is on (D6)")
        before = datasets.get_dataset(c, sf)
        did = datasets.put_dataset(c, sf, fields, actor=actor, commit=False)
        if did:
            after = datasets.get_dataset(c, sf)
            what = f"Dataset {sf}: " + " · ".join(f"{f.replace('_', ' ')} {before[f] or 'not set'} → {after[f] or 'not set'}" for f in did)
            append_audit(c, "settings", what[:400], "Datasets", route="settings/datasets", actor=actor,
                         detail={"source_file": sf, "changed": did, "from": {f: before[f] for f in did}, "to": {f: after[f] for f in did}}, commit=False)
        changed += [keys[(sf, f)] for f in did]
    return changed


@router.get("/api/datasets")
def get_datasets(request: Request):
    """Every registered dataset with the name it is called by — the client naming seam's one read (fixup-f)."""
    c = _conn(request)
    try:
        out = []
        for r in corpus.recordings(c):
            out.append({"source_file": r["source_file"], "stem": r["stem"], "name": r["display_name"], "named": r["named"], **r["dataset"],
                        "n_channels": r["n_channels"], "fs": r["fs"], "duration_h": r["duration_h"], "units": r["units"],
                        "fs_source": r["fs_source"], "held_out": r["held_out"], "has_parent": r["excerpt_of"] is not None})
        return {"datasets": out, "species_values": datasets.species_values(c), "fields": list(datasets.FIELDS)}
    finally:
        c.close()


# ---------------------------------------------------------------- registry --

@router.get("/api/registry")
def get_registry():
    return {"kinds": [k.describe() for k in KINDS.values()]}


@router.get("/api/registry/{kind}")
def get_kind(request: Request, kind: str):
    _kind_or_404(kind)
    c = _conn(request)
    try:
        t0 = time.perf_counter()
        cands = [x.to_dict() for x in scan(kind, roots=_roots(request, kind), conn=c, **_kw(request, kind))]
        return {"kind": kind, "spec": KINDS[kind].describe(), "roots": _roots(request, kind), "registered": _registered_payload(request, kind, c),
                "candidates": cands, "scan_ms": (time.perf_counter() - t0) * 1e3}
    finally:
        c.close()


@router.post("/api/registry/{kind}/check")
def post_check(request: Request, kind: str, body: PathBody):
    _kind_or_404(kind)
    cand = _find_candidate(request, kind, body.path)
    c = _conn(request)
    try:
        return _name_report(c, cand, check(cand, c, overrides=body.overrides, **_kw(request, kind)).to_dict())
    finally:
        c.close()


def _name_report(c, cand, report: dict) -> dict:
    """A check report's excerpt links name their channels by the one convention (fixup-f): the registered
    side through its own file, the candidate's side through the file and channel count it would register as."""
    facts = report.get("facts") or {}
    cand_file = facts.get("source_file") or cand.name
    cand_n = facts.get("n_channels") or 0
    for link in [*(report.get("excerpts") or []), *([report["excerpt_of"]] if report.get("excerpt_of") else [])]:
        _name_excerpt(c, link)
        if link.get("candidate_channel") is not None:
            link["candidate_channel_name"] = corpus.channel_name(cand_file, link["candidate_channel"], cand_n)
    return report


@router.post("/api/registry/{kind}/register")
def post_register(request: Request, kind: str, body: PathBody):
    spec = _kind_or_404(kind)
    cand = _find_candidate(request, kind, body.path)
    c = _conn(request)
    try:
        kw = _kw(request, kind)
        rep = check(cand, c, overrides=body.overrides, **kw)
        if not rep.ok:
            raise HTTPException(422, {"message": f"{kind} {cand.name!r} fails {len(rep.failures())} check(s)", **rep.to_dict()})
        try:
            rid = register(c, cand, report=rep, provenance=body.provenance, actor=body.actor, writer=writes.write_machine,
                           sidecar_root=_sidecar_root(request), **kw)
        except RegistrationError as e:
            raise HTTPException(422, {"message": str(e), **(e.report.to_dict() if e.report else {})})
        what = f"Registered {spec.label.lower()} {cand.name}"
        if rep.warnings:
            what += f" · {len(rep.warnings)} warning{'s' if len(rep.warnings) != 1 else ''}"
        where, route = _audit_surface(kind)
        append_audit(c, "registration", what, where, route=route, actor=body.actor, detail={"kind": kind, "path": cand.path, "id": rid, "sha1": rep.sha1, "warnings": rep.warnings})
        table = spec.table
        return {"id": rid, "kind": kind, "name": cand.name, "path": cand.path, "table": table, "warnings": rep.warnings, "sha1": rep.sha1,
                "recording_id": rep.facts.get("recording_id") if kind != "recording" else rid, "ids": rep.facts.get("registered_ids"),
                "facts": rep.facts, "excerpts": rep.excerpts, "excerpt_of": rep.excerpt_of,
                "note": "written to the throwaway database copy" if _rt(request).mode == "sandbox" else "written to the project database"}
    finally:
        c.close()


@router.delete("/api/registry/{kind}/{row_id}")
def delete_registered(request: Request, kind: str, row_id: int):
    spec = _kind_or_404(kind)
    c = _conn(request)
    try:
        name = None
        try:
            if spec.table == "recordings":
                r = c.execute("SELECT npy_path, source_file FROM recordings WHERE id = ?", (row_id,)).fetchone()
                name = (os.path.basename(os.path.dirname(r["npy_path"])) or r["source_file"]) if r else None
            elif spec.table == "registered_artifacts":
                r = c.execute("SELECT name FROM registered_artifacts WHERE id = ?", (row_id,)).fetchone()
                name = r["name"] if r else None
            elif spec.table == "encodings":
                r = c.execute("SELECT path FROM encodings WHERE id = ?", (row_id,)).fetchone()
                name = os.path.basename(r["path"]) if r else None
        except Exception:
            name = None
        try:
            out = unregister(c, kind, row_id)
        except KeyError as e:
            raise HTTPException(404, str(e))
        where, route = _audit_surface(kind)
        append_audit(c, "registration", f"Unregistered {spec.label.lower()} {name or f'{spec.table} id {row_id}'} (kept on disk, row {row_id} kept inactive)", where,
                     route=route, detail={"kind": kind, "id": row_id, "name": name})
        return out
    finally:
        c.close()


class UnitsBody(BaseModel):
    units: str
    note: str | None = None
    actor: str = "this installation"


@router.put("/api/registry/recording/{row_id}/units")
def put_recording_units(request: Request, row_id: int, body: UnitsBody):
    """Declare the unit a registered recording's samples are stored in (fixup-b).
    Every channel of the recording takes it together; the change is audited.
    A unit it cannot read is a 422 — never a guess."""
    from Working.registration.kinds import declare_units
    c = _conn(request)
    try:
        r = c.execute("SELECT source_file, units FROM recordings WHERE id = ?", (row_id,)).fetchone()
        if r is None:
            raise HTTPException(404, f"no recordings row {row_id}")
        if r["source_file"] == HELD_OUT_FILE:
            raise HTTPException(423, f"{HELD_OUT_FILE} is held out; its unit is not declared through the interface")
        try:
            out = declare_units(c, r["source_file"], body.units, note=body.note, actor=body.actor)
        except ValueError as e:
            raise HTTPException(422, str(e))
        append_audit(c, "settings", f"Declared the unit of {r['source_file']}: {r['units'] or 'undeclared'} → {out['units']} "
                     f"({out['channels']} channel{'s' if out['channels'] != 1 else ''})", "Settings › Datasets",
                     route="settings/datasets", actor=body.actor,
                     detail={"source_file": r["source_file"], "from": r["units"], "to": out["units"], "note": out["units_note"]},
                     commit=False)
        c.commit()
        return out
    finally:
        c.close()


# ---------------------------------------------------------------- settings --

def _page_extras(request: Request, page: str, c) -> dict:
    rt = _rt(request)
    if page == "datasets":
        regs = _registered_payload(request, "recording", c)
        cands = [x.to_dict() for x in scan("recording", roots=_roots(request, "recording"), conn=c)]
        raws = [x.to_dict() for x in scan("raw", roots=_roots(request, "raw"), conn=c, **_kw(request, "raw"))]
        state = held_out_state(c)
        defaults = {"heldout.on": True, "heldout.recording": HELD_OUT_FILE[:-4]}
        for r in regs:
            # an unnamed dataset has an EMPTY display name (it is called by its source file), not its stem
            for f in (*datasets.FIELDS, "substrate", "electrode_config", "start", "time_zone", "noise_floor", "temperature", "humidity"):
                defaults[f"meta.{r['name']}.{f}"] = "Europe/London" if f == "time_zone" else ""
        return {"recordings": regs, "species_values": datasets.species_values(c), "candidates": [x for x in cands if not x["registered"]], "raw_candidates": [x for x in raws if not x["registered"]],
                "held_out": state, "defaults": defaults}
    if page == "vocabulary":
        from Working.database.schema import VERDICTS
        ann = dict(c.execute("SELECT verdict, COUNT(*) FROM annotations WHERE deleted_at IS NULL GROUP BY verdict").fetchall())
        adj = dict(c.execute("SELECT verdict, COUNT(*) FROM adjudications GROUP BY verdict").fetchall())
        tags = [dict(r) for r in c.execute("SELECT * FROM tag_vocabulary ORDER BY 1").fetchall()] if _table_exists(c, "tag_vocabulary") else []
        return {"verdicts": [{"name": v, "n_annotations": int(ann.get(v, 0)), "n_adjudications": int(adj.get(v, 0))} for v in VERDICTS], "tags": tags}
    if page == "compute-hpc":
        return {"machine": _machine()}
    if page == "nulls":
        # Q36: the page offers what `preprocessing.surrogate` implements, read off the block, so it
        # cannot name a method `resolve_null` refuses. The defaults are the core's too (Q35, Q37).
        from Working.discovery import seeded_search as ss
        return {"null_methods": ss.offered_methods(),
                "null_defaults": {"draws": dict(ss.DEFAULT_DRAWS_BY_KIND), "method": ss.DEFAULT_NULL_METHOD,
                                  "alpha": ss.CUT_ALPHA, "correction": ss.CUT_CORRECTION},
                "block_rule": "twice the longest motif under test: the seed for a seed search, the run's "
                              "longest detection for a detection chain. A block under 2 samples is refused."}
    if page == "analysis-defaults":
        return {"cache_gb": _tree_bytes(rt.step_cache_root) / 1e9 if rt.step_cache_root and os.path.isdir(rt.step_cache_root) else 0.0, "cache_root": rt.step_cache_root}
    if page == "blocks":
        from . import chain as chain_mod
        cat = chain_mod.catalog()
        return {"adapters": cat, "n_adapters": len(cat)}
    return {}


@router.get("/api/settings")
def get_all_pages(request: Request):
    """Every page's saved values in one read (the rail's differs-from-default dots need them all)."""
    c = _conn(request)
    try:
        return {"pages": {p: get_settings(c, p) for p in PAGE_TITLES}, "mode": _rt(request).mode}
    finally:
        c.close()


@router.get("/api/settings/{page}")
def get_page(request: Request, page: str):
    if page not in PAGE_TITLES:
        raise HTTPException(404, f"no settings page {page!r}; pages: {sorted(PAGE_TITLES)}")
    c = _conn(request)
    try:
        out = {"page": page, "title": PAGE_TITLES[page], "values": _page_values(request, page, c), **settings_meta(c, page), "mode": _rt(request).mode}
        out.update(_page_extras(request, page, c))
        return out
    finally:
        c.close()


@router.put("/api/settings/{page}")
def put_page(request: Request, page: str, body: SettingsBody):
    if page not in PAGE_TITLES:
        raise HTTPException(404, f"no settings page {page!r}")
    c = _conn(request)
    try:
        before = _page_values(request, page, c)
        # fixup-f: a dataset's identity lives in `datasets`, keyed by source file; the page still saves it as
        # `meta.<stem>.<field>` through this one audited path. Everything in a save lands or nothing does.
        by_file, rest, keys = _split_dataset_keys(request, c, body.values) if page == "datasets" else ({}, body.values, {})
        try:
            changed = _put_datasets(c, by_file, keys, body.actor)
            changed += put_settings(c, page, rest, actor=body.actor, confirm_name=body.confirm_name)
        except ConfirmationRequired as e:
            c.rollback()
            raise HTTPException(409, {"message": str(e), "name": e.name, "confirm": "type the recording name exactly"})
        except (ValueError, KeyError) as e:
            c.rollback()
            raise HTTPException(422, str(e.args[0]) if e.args else str(e))
        except HTTPException:
            c.rollback()
            raise
        told = [k for k in changed if k != "heldout.on" and k not in keys.values()]
        if told:
            brief = lambda v: (f"{len(v)} rows" if isinstance(v, list) else str(v))[:60]  # noqa: E731
            was = lambda k: before.get(k, body.previous.get(k, "default"))  # noqa: E731
            what = f"{PAGE_TITLES[page]}: " + " · ".join(f"{k} {brief(was(k))} → {brief(body.values[k])}" for k in told)
            append_audit(c, "settings", what, PAGE_TITLES[page], route=f"settings/{page}", actor=body.actor, detail={"changed": told})
        return {"page": page, "changed": changed, "values": _page_values(request, page, c), **settings_meta(c, page),
                **({"held_out": held_out_state(c)} if page == "datasets" else {})}
    finally:
        c.close()


def _page_values(request: Request, page: str, c) -> dict:
    """A page's saved values. Datasets reads its identity fields from the `datasets` table."""
    values = get_settings(c, page)
    if page == "datasets":
        values.update(_dataset_values(request, c))
    return values


# ------------------------------------------------------------------- audit --

@router.get("/api/audit")
def get_audit(request: Request, kind: str | None = None, limit: int = 500):
    c = _conn(request)
    try:
        return {"entries": list_audit(c, kind=kind, limit=limit), "kinds": audit_kinds(c), "mode": _rt(request).mode}
    finally:
        c.close()


@router.post("/api/audit")
def post_audit(request: Request, body: AuditBody):
    c = _conn(request)
    try:
        try:
            aid = append_audit(c, body.kind, body.what, body.where, route=body.route, actor=body.actor, detail=body.detail)
        except ValueError as e:
            raise HTTPException(422, str(e))
        return {"id": aid}
    finally:
        c.close()


@router.get("/api/audit.csv")
def get_audit_csv(request: Request, kind: str | None = None):
    c = _conn(request)
    try:
        return PlainTextResponse(audit_csv(c, kind=kind), media_type="text/csv",
                                 headers={"Content-Disposition": 'attachment; filename="audit-log.csv"'})
    finally:
        c.close()


# ------------------------------------------------------------------- about --

def _git(*args) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, stderr=subprocess.DEVNULL, timeout=5).decode("utf-8", "replace").strip()
    except Exception:
        return None


def _packages() -> dict:
    out = {}
    for name in ("numpy", "scipy", "pandas", "stumpy", "aeon", "torch", "sklearn", "fastapi", "uvicorn", "openpyxl", "h5py", "joblib"):
        try:
            mod = __import__(name)
            out[name] = getattr(mod, "__version__", "?")
        except Exception:
            out[name] = None
    return out


import functools


@functools.lru_cache(maxsize=1)
def _machine() -> dict:
    """Cached: the first call imports torch (seconds); the machine does not change while the bridge runs."""
    total = None
    try:
        import psutil
        total = psutil.virtual_memory().total
    except Exception:
        if sys.platform == "win32":
            try:
                import ctypes
                class MS(ctypes.Structure):
                    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                                ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
                ms = MS(); ms.dwLength = ctypes.sizeof(MS)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
                total = int(ms.ullTotalPhys)
            except Exception:
                total = None
    gpu = None
    try:
        import torch
        if torch.cuda.is_available():
            gpu = f"{torch.cuda.get_device_name(0)} · {torch.cuda.get_device_properties(0).total_memory / 2**30:.0f} GB"
    except Exception:
        gpu = None
    return {"cores": os.cpu_count(), "ram_gb": round(total / 2**30) if total else None, "gpu": gpu, "platform": platform.platform(), "machine": platform.machine(),
            "detected": " · ".join(x for x in (f"{os.cpu_count()} cores", gpu or "no CUDA GPU", f"{round(total / 2**30)} GB RAM" if total else None) if x)}


# warm the cached machine facts off the request path: the first _machine() imports torch (seconds in
# the venv), and the Compute page's first read must not pay for it
import threading as _threading
_threading.Thread(target=_machine, daemon=True, name="machine-facts-warm").start()


def _table_exists(c, name) -> bool:
    return c.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


@router.get("/api/about")
def get_about(request: Request):
    rt = _rt(request)
    from . import chain as chain_mod
    c = _conn(request)
    try:
        tables = c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0]
        n_settings = c.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
        n_audit = c.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        n_rec = c.execute("SELECT COUNT(DISTINCT source_file) FROM recordings WHERE active = 1").fetchone()[0]
        n_rec_rows = c.execute("SELECT COUNT(*) FROM recordings WHERE active = 1").fetchone()[0]
        n_art = c.execute("SELECT COUNT(*) FROM registered_artifacts WHERE active = 1").fetchone()[0]
    finally:
        c.close()
    cat = chain_mod.catalog()
    broken = [a["name"] for a in cat if a.get("known_broken")]
    head, branch, dirty = _git("rev-parse", "--short", "HEAD"), _git("rev-parse", "--abbrev-ref", "HEAD"), _git("status", "--porcelain")
    code = {"version": head or "unknown", "branch": branch, "dirty": bool(dirty), "summary": f"{head or 'unknown'} · {branch or '?'} · {'uncommitted changes' if dirty else 'clean working tree'}"}
    pk = _packages()
    about = {
        "project": "Underground Brains · fungal bio-electric recordings", "code": code,
        "schema": {"tables": tables, "settings_rows": n_settings, "audit_rows": n_audit, "recordings": n_rec, "recording_rows": n_rec_rows, "registered_artifacts": n_art, "path": rt.db_path},
        "blocks": {"registered": len(cat), "broken": broken, "summary": f"{len(cat)} registered · {len(broken)} known broken"},
        "python": platform.python_version(), "executable": sys.executable, "packages": pk, "mode": rt.mode, "banner": rt.banner(), "db_path": rt.db_path,
        "db_backup": rt.db_backup, "runtime_dir": rt.dir, "repo_root": REPO_ROOT, "held_out_file": HELD_OUT_FILE,
        "settings_store": f"{rt.db_path} · table settings ({n_settings} rows) · personal preferences in this browser (localStorage)",
        "environment": f"python {platform.python_version()} · " + " · ".join(f"{k} {v}" for k, v in pk.items() if v),
        "future": [
            {"name": "user accounts", "detail": "named researchers on verdicts, hand edits, HPC status and sign-offs; per-user blind state; a second sign-off for registration"},
            {"name": "multi-seed search", "detail": "seed searches that take several exemplars (Discovery §7.6)"},
            {"name": "cross-channel analysis", "detail": "multivariate chains; Explore's cross-channel mode stays a placeholder"},
        ],
    }
    about["diagnostics"] = "\n".join([
        about["project"], f"code      {code['summary']}", f"mode      {rt.mode}", f"database  {rt.db_path} ({tables} tables, {n_rec} recordings / {n_rec_rows} channel rows, {n_art} registered artifacts)",
        f"blocks    {about['blocks']['summary']}", f"python    {platform.python_version()} ({sys.executable})",
        f"packages  " + ", ".join(f"{k}={v}" for k, v in pk.items() if v), f"platform  {platform.platform()}", f"held out  {HELD_OUT_FILE}",
    ])
    return about


# ----------------------------------------------------------------- storage --

def _tree_bytes(path: str) -> int:
    total = 0
    if not path or not os.path.exists(path):
        return 0
    if os.path.isfile(path):
        return os.path.getsize(path)
    for root, _d, files in os.walk(path):
        for fn in files:
            try:
                total += os.path.getsize(os.path.join(root, fn))
            except OSError:
                pass
    return total


def _tree_files(path: str) -> int:
    if not path or not os.path.exists(path):
        return 0
    if os.path.isfile(path):
        return 1
    return sum(len(files) for _r, _d, files in os.walk(path))


@router.get("/api/storage")
def get_storage(request: Request):
    rt = _rt(request)
    sandbox = rt.mode == "sandbox"
    db_dir = os.path.dirname(rt.db_source)
    backups_dir = os.path.join(db_dir, "backups") if not sandbox else os.path.join(rt.dir, "backups")
    # the roots are the conventional directories the registry scans; sandbox mode ADDS its redirected
    # write locations as their own rows rather than hiding the real ones behind them
    mp_dir, wm_dir = KINDS["matrix_profile"].roots[0], KINDS["window_matrix"].roots[0]
    roots = [
        ("database", "database", rt.db_path, ["open folder", "back up"], f"{'sandbox copy' if sandbox else 'the project database (WAL)'}"),
        ("recordings", "raw recordings", KINDS["raw"].roots[0], ["scan"], "read only · derived into channels"),
        ("channels", "channel arrays", KINDS["recording"].roots[0], ["scan"], "one .npy per channel · registered rows point here"),
        ("step_cache", "step cache", rt.step_cache_root or "", ["clear"], "retention in Analysis defaults"),
        ("window_matrices", "window matrices", wm_dir, ["scan"], KINDS["window_matrix"].naming.split(" · ")[0]),
        ("legacy_matrices", "legacy matrices (csv)", KINDS["window_matrix"].roots[1], ["scan"], "no manifest fields"),
        ("matrix_profiles", "matrix profiles", mp_dir, ["scan"], KINDS["matrix_profile"].naming),
        ("models", "models", KINDS["model"].roots[0], ["scan"], "PyTorch checkpoints"),
        ("classifiers", "classifier joblibs", KINDS["model"].roots[1], ["scan"], "sklearn"),
        ("window_sets", "window sets", KINDS["window_set"].roots[0], ["scan"], "none saved yet" if not os.path.isdir(KINDS["window_set"].roots[0]) else ""),
        ("encodings", "encodings", KINDS["encoding"].roots[0], ["scan"], ""),
        ("library_seed", "library seed", "DATA/library_seed", ["scan"], "tracked on purpose · not regenerable"),
        ("catalogue", "catalogue spreadsheets", KINDS["catalogue_spreadsheet"].roots[0], ["scan"], ""),
        ("hpc_results", "HPC results", KINDS["hpc_result"].roots[0], ["scan"], "drop a job's bundle here"),
        ("exports", "exports", rt.exports_dir, ["open folder"], ""),
        ("backups", "database backups", backups_dir, ["open folder"], f"written on every --project start · last {10} kept"),
    ] + ([
        ("sandbox_results", "sandbox results (redirected)", rt.results_dir or "", [], "where this sandbox's runs write matrix profiles and window matrices"),
        ("sandbox_models", "sandbox models (redirected)", rt.models_dir or "", [], "where this sandbox's classifier writes"),
        ("sandbox_channels", "sandbox derived channels", os.path.join(rt.dir, "derived", "channels"), ["scan"], "where an import derives in sandbox mode (scanned with the real channels)"),
    ] if sandbox else [])
    out = []
    for rid, label, path, actions, note in roots:
        exists = bool(path) and os.path.exists(path)
        out.append({"id": rid, "root": label, "path": path.replace("\\", "/") if path else "", "exists": exists, "bytes": _tree_bytes(path) if exists else 0,
                    "n_files": _tree_files(path) if exists else 0, "actions": actions, "note": note, "locked": rid in ("database",)})
    backups = []
    if os.path.isdir(backups_dir):
        for fn in sorted(os.listdir(backups_dir), reverse=True):
            if fn.endswith(".sqlite"):
                p = os.path.join(backups_dir, fn)
                backups.append({"name": fn, "path": p, "bytes": os.path.getsize(p), "mtime": os.path.getmtime(p), "current": p == rt.db_backup})
    try:
        du = shutil.disk_usage(REPO_ROOT)
        free_gb, total_gb = du.free / 2**30, du.total / 2**30
    except Exception:
        free_gb = total_gb = None
    return {"roots": out, "backups": backups, "free_gb": free_gb, "total_gb": total_gb, "mode": rt.mode, "backups_dir": backups_dir, "db_backup": rt.db_backup}


@router.post("/api/backups")
def post_backup(request: Request):
    """A consistent copy of the open database via the sqlite backup API — to
    DATA/db/backups/ in project mode, the runtime dir in sandbox mode."""
    import datetime as _dt
    rt = _rt(request)
    backups_dir = os.path.join(os.path.dirname(rt.db_source), "backups") if rt.mode == "project" else os.path.join(rt.dir, "backups")
    os.makedirs(backups_dir, exist_ok=True)
    dest = os.path.join(backups_dir, _dt.datetime.now().strftime("%Y%m%d-%H%M%S") + ".sqlite")
    src = sqlite3.connect(rt.db_path)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    c = _conn(request)
    try:
        append_audit(c, "backup", f"Backed up the database to {dest}", "Storage & backups", route="settings/storage-backups", detail={"path": dest, "bytes": os.path.getsize(dest)})
    finally:
        c.close()
    return {"path": dest, "bytes": os.path.getsize(dest), "mode": rt.mode}
