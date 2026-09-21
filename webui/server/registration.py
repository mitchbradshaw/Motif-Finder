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
        for r in out:
            n = r["n_channels"]
            for ch in r["channels"]:
                ch["name"] = corpus.channel_name(r["source_file"], ch["channel"], n)
    return out


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
        return check(cand, c, overrides=body.overrides, **_kw(request, kind)).to_dict()
    finally:
        c.close()


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
            for f in ("display_name", "species", "substrate", "electrode_config", "start", "time_zone", "noise_floor", "temperature", "humidity", "notes"):
                defaults[f"meta.{r['name']}.{f}"] = r["name"] if f == "display_name" else "Europe/London" if f == "time_zone" else ""
        return {"recordings": regs, "candidates": [x for x in cands if not x["registered"]], "raw_candidates": [x for x in raws if not x["registered"]],
                "held_out": state, "defaults": defaults}
    if page == "vocabulary":
        from Working.database.schema import VERDICTS
        ann = dict(c.execute("SELECT verdict, COUNT(*) FROM annotations WHERE deleted_at IS NULL GROUP BY verdict").fetchall())
        adj = dict(c.execute("SELECT verdict, COUNT(*) FROM adjudications GROUP BY verdict").fetchall())
        tags = [dict(r) for r in c.execute("SELECT * FROM tag_vocabulary ORDER BY 1").fetchall()] if _table_exists(c, "tag_vocabulary") else []
        return {"verdicts": [{"name": v, "n_annotations": int(ann.get(v, 0)), "n_adjudications": int(adj.get(v, 0))} for v in VERDICTS], "tags": tags}
    if page == "compute-hpc":
        return {"machine": _machine()}
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
        out = {"page": page, "title": PAGE_TITLES[page], "values": get_settings(c, page), **settings_meta(c, page), "mode": _rt(request).mode}
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
        before = get_settings(c, page)
        try:
            changed = put_settings(c, page, body.values, actor=body.actor, confirm_name=body.confirm_name)
        except ConfirmationRequired as e:
            raise HTTPException(409, {"message": str(e), "name": e.name, "confirm": "type the recording name exactly"})
        except ValueError as e:
            raise HTTPException(422, str(e))
        if changed and not (page == "datasets" and changed == ["heldout.on"]):
            brief = lambda v: (f"{len(v)} rows" if isinstance(v, list) else str(v))[:60]  # noqa: E731
            was = lambda k: before.get(k, body.previous.get(k, "default"))  # noqa: E731
            what = f"{PAGE_TITLES[page]}: " + " · ".join(f"{k} {brief(was(k))} → {brief(body.values[k])}" for k in changed if k != "heldout.on")
            if what.rstrip(": "):
                append_audit(c, "settings", what, PAGE_TITLES[page], route=f"settings/{page}", actor=body.actor, detail={"changed": changed})
        return {"page": page, "changed": changed, "values": get_settings(c, page), **settings_meta(c, page),
                **({"held_out": held_out_state(c)} if page == "datasets" else {})}
    finally:
        c.close()


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
