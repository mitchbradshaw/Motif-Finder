"""fixup-aj: Jobs, as far as RQ1 needs it (ticket `docs/prompts/fixup/AJ-jobs-usable-for-rq1.md`).

The local jobs are the bridge's own job table, read through the existing ``GET /api/jobs`` (``jobs.py``). This
module adds the cluster half — the site writes scripts and reads results back; it never logs in to or submits to
the cluster:

* ``GET /api/hpc/exported`` — every job directory the site wrote for the cluster (fixup-AI's B.2 CNN and the
  full-pool Ward, plus the local smoke's directory), read from the directory itself
  (``Working.hpc.job_export.list_exported_jobs``: its ``job.json`` is the record of what was written), with its
  state: *written · results copied back · importing · results imported (the run, a link) · import refused (why)*.
* ``POST /api/hpc/inbox/import`` — the Manifest inbox: a returned job directory is imported by a local job of kind
  ``import`` that calls ``Working.training.hpc_import.import_results`` — the function behind
  ``python -m Working.training import-results``: one implementation, two callers. A refusal is that job's error
  and is kept in the job table, so the exported row can say why.
* ``GET /api/hpc/inbox`` — the import attempts, newest first.
"""
from __future__ import annotations

import json
import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from . import corpus
from .runtime import HELD_OUT_FILE

router = APIRouter()

#: the `meta.what` of an inbox import job (Library's own `import` jobs carry another)
INBOX_WHAT = "cluster results"
#: an import that was refused, as opposed to one that crashed
REFUSALS = ("ImportRefused", "CutFrozen")


def _conn(request: Request):
    return corpus.connect(request.app.state.rt.db_path)


def _roots(rt):
    from .training_routes import _hpc_dir
    hpc = _hpc_dir(rt)
    return [hpc, os.path.join(hpc, "smoke")]          # the local smoke writes its job under smoke/


def _key(path):
    return os.path.normcase(os.path.abspath(str(path))) if path else None


def _attempt(snap: dict) -> dict:
    meta = snap.get("meta") or {}
    err = snap.get("error") or {}
    prog = snap.get("progress") or {}
    status = snap.get("status")
    if status == "completed":
        outcome = "imported"
    elif status == "failed":
        outcome = "refused" if err.get("type") in REFUSALS else "failed"
    else:
        outcome = "importing" if status in ("running", "queued") else status
    msg = err.get("message") or prog.get("message") or ""
    t = err.get("type")
    reason = msg[len(t) + 2:] if t and msg.startswith(f"{t}: ") else msg
    return {"job_id": snap.get("job_id"), "job_dir": meta.get("job_dir"), "recipe_hash": meta.get("recipe_hash"),
            "outcome": outcome, "status": status, "message": reason, "error_type": t,
            "traceback": err.get("traceback") if outcome == "failed" else None,
            "started_at": snap.get("started_at"), "finished_at": snap.get("finished_at")}


def _attempts(request: Request, limit: int = 100) -> list[dict]:
    manager = request.app.state.manager
    c = _conn(request)
    try:
        ids = [int(r[0]) for r in c.execute(
            "SELECT id FROM jobs WHERE kind = 'import' AND json_extract(meta_json, '$.what') = ? ORDER BY id DESC "
            "LIMIT ?", (INBOX_WHAT, int(limit)))]
    finally:
        c.close()
    live = [j.id for j in list(manager.jobs.values())
            if getattr(j, "kind", None) == "import" and (getattr(j, "meta", None) or {}).get("what") == INBOX_WHAT]
    out = []
    for jid in sorted(set(ids) | set(live), reverse=True):
        snap = manager.snapshot(jid)
        if snap is not None:
            out.append(_attempt(snap))
    return out


def _open_route(c, row) -> dict | None:
    """Where an imported job's result is read: Models › Results for a CNN run, the Analyse chain whose tree it
    replaces for the full-pool Ward."""
    imp = row.get("imported")
    if not imp:
        return None
    if row["kind"] == "shape_cluster_cnn":
        return {"label": "Open in Models › Results", "route": f"models/results/b2/{imp['run_id']}"}
    if row["kind"] == "shape_tree_full":
        key = row.get("pool_key")
        pool = c.execute("SELECT id FROM window_sets WHERE recipe_hash = ? ORDER BY id DESC LIMIT 1",
                         (str(key),)).fetchone() if key else None
        tpl = c.execute("SELECT json_extract(c.config_json, '$.template.id') FROM runs r JOIN configs c ON "
                        "c.id = r.config_id WHERE json_extract(c.config_json, '$.pool.key') = ? AND "
                        "json_extract(c.config_json, '$.template.id') IS NOT NULL ORDER BY r.id DESC LIMIT 1",
                        (str(key),)).fetchone() if key else None
        q = "&".join(x for x in (f"template={tpl[0]}" if tpl and tpl[0] is not None else "",
                                 f"poolId={pool[0]}" if pool else "") if x)
        return {"label": "Open the chain in Analyse", "route": "analyse/chain" + (f"?{q}" if q else ""),
                "note": ("the tree over every training window replaces the sampled one: set the Shape clustering "
                         "block's sample to 0 (every training window) and re-run; choose the cut and the mapping "
                         "again")}
    return None


@router.get("/api/hpc/exported")
def exported(request: Request):
    from Working.hpc.job_export import list_exported_jobs
    rt = request.app.state.rt
    latest: dict = {}
    for a in _attempts(request):                       # newest first: the first per directory is the latest
        latest.setdefault(_key(a["job_dir"]), a)
    c = _conn(request)
    try:
        rows = list_exported_jobs(_roots(rt), conn=c)
        for r in rows:
            a = latest.get(_key(r["job_dir"]))
            r["last_attempt"] = a
            r["reason"] = None
            if r["error"]:
                r["state"] = "unreadable"
            elif r["imported"]:
                r["state"] = "imported"
            elif a and a["outcome"] == "importing":
                r["state"] = "importing"
            elif a and a["outcome"] in ("refused", "failed"):
                r["state"] = a["outcome"]
                r["reason"] = a["message"]
            elif r["returned"]:
                r["state"] = "returned"
            else:
                r["state"] = "written"
            r["open"] = _open_route(c, r)
    finally:
        c.close()
    return {"jobs": rows, "roots": _roots(rt), "mode": rt.mode,
            "note": ("the site writes the scripts and reads the results back; it never logs in to or submits to the "
                     "cluster — you copy, sbatch and copy out/ back")}


@router.get("/api/hpc/inbox")
def inbox(request: Request):
    return {"attempts": _attempts(request), "roots": _roots(request.app.state.rt)}


class InboxBody(BaseModel):
    path: str


@router.post("/api/hpc/inbox/import")
def inbox_import(request: Request, body: InboxBody):
    """Import a returned job directory: a local job calling the CLI's `import_results`."""
    import Adapters.catalogue_shape_cluster as csc
    from Working.hpc.job_export import REPO_ROOT
    from .training_routes import _training_root
    p = (body.path or "").strip().strip('"').strip("'")
    if not p:
        raise HTTPException(422, "name the returned job directory (the folder holding recipe.json, job.json and out/)")
    if HELD_OUT_FILE in p:
        raise HTTPException(423, f"{HELD_OUT_FILE} is held out; the web UI refuses it")
    job_dir = os.path.abspath(p if os.path.isabs(p) else os.path.join(REPO_ROOT, p))
    rt, manager = request.app.state.rt, request.app.state.manager
    root, tree_root = _training_root(rt), csc.RESULTS_DIR
    h = None
    try:
        with open(os.path.join(job_dir, "job.json"), encoding="utf-8") as fh:
            h = json.load(fh).get("recipe_hash")
    except Exception:
        pass                                            # the import says what is missing, as a refusal

    def work(job):
        from Working.training import hpc_import          # looked up at call time: the CLI's function, not a copy
        job.progress(0, 1, f"checking {job_dir} against its recipe hash")
        c = _conn(request)
        try:
            got = hpc_import.import_results(c, job_dir, root=root, tree_root=tree_root)
        finally:
            c.close()
        job.progress(1, 1, got.get("message") or "imported")
        return got

    job = manager.start_job("import", work, meta={"what": INBOX_WHAT, "stage": "Manifest inbox · import results",
                                                  "job_dir": job_dir, "recipe_hash": h, "where": "local"})
    return job.snapshot()
