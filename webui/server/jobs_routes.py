"""Jobs, the bridge side (fixup-aj, then fixup-jobs: the whole page real).

The local jobs are the bridge's own job table, read through the existing ``GET /api/jobs`` (``jobs.py``). This
module adds the cluster half — the site writes scripts and reads results back; it never logs in to or submits to
the cluster:

* ``GET /api/hpc/exported`` — every job directory the site wrote for the cluster (fixup-AI's B.2 CNN and the
  full-pool Ward, plus the local smoke's directory), read from the directory itself
  (``Working.hpc.job_export.list_exported_jobs``: its ``job.json`` is the record of what was written), with its
  state: *written · results copied back · importing · results imported (the run, a link) · import refused (why)*.
* ``GET /api/hpc/cluster`` (fixup-jobs) — **one list of every job the site wrote for the cluster, whatever wrote
  it**: the job directories above, Discovery's seed searches sent to the cluster (their run rows carry
  ``params.hpc``; the state is read from the result file ``seed_job`` checkpoints into, and from the row once it is
  imported), and the flat recipe + script pairs Discovery's chain export and Models' paired-training export write
  (listed as *written*; their results do not come back through the site, and the row says so). Each row names its
  workspace, its state and how its results come back; ``counts`` summarise the states for the page's chips.
* ``POST /api/hpc/inbox/import`` — the Manifest inbox: a returned job directory is imported by a local job of kind
  ``import`` that calls ``Working.training.hpc_import.import_results`` — the function behind
  ``python -m Working.training import-results``: one implementation, two callers. A refusal is that job's error
  and is kept in the job table, so the exported row can say why.
* ``POST /api/hpc/seed/import`` (fixup-jobs) — a seed job's result file imported by path, through the Seed page's
  own import function (``discovery.import_seed_result_dict``): one implementation, two callers.
* ``GET /api/hpc/inbox`` — the import attempts, newest first.
"""
from __future__ import annotations

import datetime as _dt
import json
import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from . import corpus
from .runtime import HELD_OUT_FILE, REPO_ROOT

router = APIRouter()

#: the `meta.what` of an inbox import job (Library's own `import` jobs carry another)
INBOX_WHAT = "cluster results"
#: an import that was refused, as opposed to one that crashed
REFUSALS = ("ImportRefused", "CutFrozen")

#: fixup-jobs: which workspace reads each job directory's results back
JOB_DIR_WORKSPACE = {"shape_cluster_cnn": "Models", "shape_tree_full": "Analyse"}
#: a Discovery seed search sent to the cluster (`Working.discovery.seed_job`)
SEED_KIND = "seed_search"
SEED_LABEL = "Seed search · candidates and null draws on the cluster"
#: the flat recipe + script pairs, by the recipe they were written with: (label, workspace, why no import)
SCRIPT_KINDS = {
    "paired_training": ("Paired training · forests, clustering and null", "Models",
                        "not imported through the site: on the cluster `python -m Working.training run` writes the "
                        "run under DATA/derived/training; bring that tree and the database rows back by hand"),
    "detection_chain": ("Discovery chain over channels", "Discovery",
                        "not imported through the site: the chain writes its runs into the cluster's copy of the "
                        "database; there is no return path for them here yet"),
    "recipe": ("Recipe", "Analyse", "not imported through the site: no return path is defined for this recipe"),
}
#: every state a cluster row can be in, in the order the page's chips count them
STATES = ("written", "partial", "returned", "importing", "imported", "refused", "failed", "unreadable")


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


# ── fixup-jobs: one list of every job the site wrote for the cluster ─────────

def _abs(path):
    """A path as stored (repo-relative in project mode, absolute in a sandbox or a test) made absolute."""
    if not path:
        return None
    p = str(path)
    return os.path.abspath(p if os.path.isabs(p) else os.path.join(REPO_ROOT, p))


def _iso_mtime(path):
    try:
        return _dt.datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="seconds")
    except OSError:
        return None


def _bytes(path):
    try:
        return int(os.path.getsize(_abs(path)))
    except (OSError, TypeError):
        return 0


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _seed_out_dir(request: Request):
    from .discovery import _hpc_out_dir          # where `/api/discovery/seed/slurm` and `/api/discovery/slurm` write
    return _hpc_out_dir(request)


def _blank_row(**kw) -> dict:
    """The shared shape every cluster row has, whatever wrote it, so the page draws them in one table."""
    row = {"source": None, "name": None, "kind": None, "kind_label": None, "workspace": None, "label": None,
           "run_key": None, "session": None, "job_dir": None, "job_repo": None, "recipe_hash": None, "recipe_ok": None,
           "written_at": None, "smoke": False, "model": None, "pool_key": None, "n": None, "scripts": [],
           "sbatch_command": None, "copy": [], "total_bytes": 0, "returned": None, "imported": None, "error": None,
           "state": "written", "reason": None, "last_attempt": None, "open": None,
           "import_how": None, "import_path": None, "import_note": None, "result_path": None, "progress": None,
           "estimate_s": None, "draws": None, "run_status": None}
    row.update(kw)
    return row


def _seed_rows(request: Request) -> list[dict]:
    """Discovery's seed searches sent to the cluster (`/api/discovery/seed/slurm`): one row per run row that
    carries `params.hpc`. The state is read from the result file (`seed_job` checkpoints into it after every
    channel: a file that is there but not `complete` is *partial*) and from the row once the Seed page's import
    stamped `importedAt`. A result file written from another spec is not this job's result and says so."""
    from Working.hpc.job_export import repo_relative
    c = _conn(request)
    try:
        rs = c.execute(
            "SELECT r.*, s.name AS session_name, s.source_file FROM discovery_runs r "
            "JOIN discovery_sessions s ON s.id = r.session_id "
            "WHERE r.kind = 'seed' AND json_extract(r.params_json, '$.hpc') IS NOT NULL ORDER BY r.id DESC").fetchall()
    finally:
        c.close()
    out = []
    for r in rs:
        p = json.loads(r["params_json"] or "{}")
        hpc = p.get("hpc") or {}
        script, spec, result = _abs(hpc.get("scriptPath")), _abs(hpc.get("specPath")), _abs(hpc.get("resultPath"))
        name = os.path.basename(script)[:-3] if script and script.endswith(".sh") else str(r["run_key"])
        want = hpc.get("specHash")
        channels = None
        try:
            channels = len(_read_json(spec).get("channels") or []) if spec and os.path.isfile(spec) else None
        except Exception:
            channels = None
        row = _blank_row(
            source="seed", name=name, kind=SEED_KIND, kind_label=SEED_LABEL, workspace="Discovery",
            label=r["label"], run_key=r["run_key"], session=r["session_name"], recipe_hash=want,
            written_at=hpc.get("createdAt") or (_iso_mtime(script) if script else None) or r["created_at"],
            scripts=([{"name": os.path.basename(script), "path": script, "repo": repo_relative(script)}]
                     if script else []),
            sbatch_command=hpc.get("sbatch") or (f"sbatch {repo_relative(script)}" if script else None),
            import_how="seed", import_path=result, result_path=result, run_status=r["status"],
            estimate_s=hpc.get("estimateS"), draws=hpc.get("draws"))
        copy = []
        if spec:
            copy.append({"what": "spec", "path": repo_relative(spec), "bytes": _bytes(spec),
                         "note": "the exemplar's samples, the channels, the span and the null"})
        if script:
            copy.append({"what": "script", "path": repo_relative(script), "bytes": _bytes(script)})
        listed = {_key(spec), _key(script)}
        for inp in (hpc.get("dependencies") or {}).get("inputs") or []:
            if _key(_abs(inp)) in listed:
                continue
            copy.append({"what": "input", "path": repo_relative(inp), "bytes": _bytes(inp),
                         "note": "named in the script's dependency block"})
        row["copy"], row["total_bytes"] = copy, int(sum(x["bytes"] for x in copy))
        if result and os.path.isfile(result):
            try:
                got = _read_json(result)
                got_hash = got.get("specHash")
                if want and got_hash != want:
                    row["reason"] = (f"{os.path.basename(result)} was computed from spec {got_hash}, not this "
                                     f"job's spec {want}: it is not this job's result")
                else:
                    done = len(got.get("perChannel") or [])
                    complete = bool(got.get("complete"))
                    row["returned"] = {"status": "complete" if complete else "partial", "recipe_hash": got_hash,
                                       "finished_at": got.get("finishedAt")}
                    row["state"] = "returned" if complete else "partial"
                    if not complete:
                        row["progress"] = {"channels_done": done, "channels": channels}
            except Exception as e:                       # loud: the row says what is wrong with the file
                row["returned"] = {"status": f"unreadable: {type(e).__name__}: {e}", "recipe_hash": None,
                                   "finished_at": None}
                row["state"] = "unreadable"
                row["error"] = f"{type(e).__name__}: {e}"
        if hpc.get("importedAt"):
            row["state"] = "imported"
            row["imported"] = {"run_id": None, "name": r["label"], "at": hpc["importedAt"]}
            row["open"] = {"label": "Open in Discovery",
                           "route": f"discovery/runs?run={r['run_key']}"}
        out.append(row)
    return out


def _script_kind(recipe: dict) -> str:
    if isinstance(recipe, dict) and recipe.get("arms"):
        return "paired_training"
    if isinstance(recipe, dict) and (recipe.get("steps") or recipe.get("fan_out")):
        return "detection_chain"
    return "recipe"


def _script_rows(request: Request, skip: set) -> list[dict]:
    """The flat recipe + script pairs (`<base>.json` beside `<base>.sh`) the Discovery chain export and the
    Models paired-training export leave at the top of their folders. A seed job's script (its sibling is
    `<base>.spec.json`) is listed from its run row instead, never twice."""
    from Working.hpc.job_export import repo_relative
    from Working.recipes import short_hash
    from .training_routes import _hpc_dir
    rt = request.app.state.rt
    out = []
    for root in (_seed_out_dir(request), _hpc_dir(rt)):
        if not root or not os.path.isdir(root):
            continue
        for fn in sorted(os.listdir(root)):
            if not fn.endswith(".sh") or not os.path.isfile(os.path.join(root, fn)):
                continue
            stem = fn[:-3]
            if stem in skip or os.path.isfile(os.path.join(root, stem + ".spec.json")):
                continue
            script = os.path.join(root, fn)
            recipe_path = os.path.join(root, stem + ".json")
            if not os.path.isfile(recipe_path):
                continue
            row = _blank_row(source="script", name=stem, workspace="Analyse",
                             written_at=_iso_mtime(script),
                             scripts=[{"name": fn, "path": script, "repo": repo_relative(script)}],
                             sbatch_command=f"sbatch {repo_relative(script)}")
            try:
                recipe = _read_json(recipe_path)
                kind = _script_kind(recipe)
                row["recipe_hash"] = short_hash(recipe) if isinstance(recipe, dict) else None
            except Exception as e:
                kind = "recipe"
                row["error"], row["state"] = f"{type(e).__name__}: {e}", "unreadable"
            label, ws, note = SCRIPT_KINDS[kind]
            row.update(kind=kind, kind_label=label, workspace=ws, import_note=note)
            row["copy"] = [{"what": "recipe", "path": repo_relative(recipe_path), "bytes": _bytes(recipe_path)},
                           {"what": "script", "path": repo_relative(script), "bytes": _bytes(script)}]
            row["total_bytes"] = int(sum(x["bytes"] for x in row["copy"]))
            out.append(row)
    return out


@router.get("/api/hpc/cluster")
def cluster(request: Request):
    """Every job the site wrote for the cluster, whatever wrote it, newest first, with counts by state."""
    rt = request.app.state.rt
    dirs = exported(request)["jobs"]
    rows = []
    for r in dirs:
        rows.append(_blank_row(**r, source="job_dir", workspace=JOB_DIR_WORKSPACE.get(r.get("kind"), "Models"),
                               import_how="inbox", import_path=r["job_dir"]))
    seeds = _seed_rows(request)
    rows += seeds
    rows += _script_rows(request, skip={s["name"] for s in seeds})
    rows.sort(key=lambda r: (r.get("written_at") or ""), reverse=True)
    counts = {s: 0 for s in STATES}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    counts["to_import"] = sum(1 for r in rows if r["state"] == "returned" and r["import_how"])
    counts["waiting"] = counts["written"] + counts["partial"]
    counts["total"] = len(rows)
    return {"jobs": rows, "roots": [_seed_out_dir(request), *_roots(rt)], "mode": rt.mode, "counts": counts,
            "note": ("the site writes the scripts and reads the results back; it never logs in to or submits to the "
                     "cluster — you copy, sbatch and bring the results back")}


@router.get("/api/hpc/inbox")
def inbox(request: Request):
    return {"attempts": _attempts(request), "roots": _roots(request.app.state.rt)}


class InboxBody(BaseModel):
    path: str


@router.post("/api/hpc/inbox/import")
def inbox_import(request: Request, body: InboxBody):
    """Import a returned job directory: a local job calling the CLI's `import_results`."""
    import Adapters.catalogue_shape_cluster as csc
    from Working.hpc.job_export import REPO_ROOT as _REPO
    from .training_routes import _training_root
    p = (body.path or "").strip().strip('"').strip("'")
    if not p:
        raise HTTPException(422, "name the returned job directory (the folder holding recipe.json, job.json and out/)")
    if HELD_OUT_FILE in p:
        raise HTTPException(423, f"{HELD_OUT_FILE} is held out; the web UI refuses it")
    job_dir = os.path.abspath(p if os.path.isabs(p) else os.path.join(_REPO, p))
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


@router.post("/api/hpc/seed/import")
def seed_import(request: Request, body: InboxBody):
    """A seed job's result file, imported by path from Jobs through the Seed page's own import (one
    implementation, two callers). The file is read here; everything it means is decided there."""
    from . import discovery                              # looked up at call time: the Seed page's function
    p = (body.path or "").strip().strip('"').strip("'")
    if not p:
        raise HTTPException(422, "name the result file the seed job wrote (…result.json)")
    if HELD_OUT_FILE in p:
        raise HTTPException(423, f"{HELD_OUT_FILE} is held out; the web UI refuses it")
    path = _abs(p)
    if not os.path.isfile(path):
        raise HTTPException(404, f"no result file at {path}: bring the seed job's …result.json back first")
    try:
        result = _read_json(path)
    except Exception as e:
        raise HTTPException(422, f"{path} is not a seed job result: {type(e).__name__}: {e}")
    if not isinstance(result, dict):
        raise HTTPException(422, f"{path} is not a seed job result (not a JSON object)")
    return discovery.import_seed_result_dict(request, result)
