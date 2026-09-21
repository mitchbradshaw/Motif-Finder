"""Training's live writes (stage-3 prompt 01, block 6): "Save window set".

A saved window set is a directory `<window_sets_root>/<name>/` holding
`windows.npz` (`starts, length, fs, source_file, channel, labels`) and
`manifest.json` (`kind: "window_set"` + the split, the spacing check and
the producing recipe hash) — the shape Prompt 02's `window_set` registration
kind scans and checks — registered as `registered_artifacts(kind='window_set')`
through `Working.registration.core.register` (rule 4: the arrays on disk,
the row holds the path). The WindowSet itself is recomputed from the run's
recipe up to the chosen step through `execute_recipe` (cheap for
`sliding_windows`; the cache/persist path for `window_matrix`).
"""
from __future__ import annotations

import json
import os
import re

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from Working.execution import execute_recipe
from Working.recipes import short_hash
from Working.registration import core as reg

from . import corpus
from .writes import write_machine

router = APIRouter()
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class SaveBody(BaseModel):
    job_id: int
    step: int
    name: str
    notes: str | None = None


def _conn(request: Request):
    return corpus.connect(request.app.state.rt.db_path)


def write_window_set(root: str, name: str, ws, recording: dict, recipe: dict, step: int, notes: str | None = None) -> str:
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    labels = ws.features["split"].to_numpy() if ws.features is not None and "split" in ws.features.columns else np.full(len(ws.starts), -1)
    np.savez_compressed(os.path.join(d, "windows.npz"), starts=np.asarray(ws.starts, dtype=np.int64), length=np.int64(ws.length),
                        fs=np.float64(ws.fs), source_file=np.str_(recording["source_file"]), channel=np.int64(recording["channel"]),
                        labels=np.asarray(labels, dtype=np.int64))
    gaps = np.diff(np.asarray(ws.starts)) if len(ws.starts) > 1 else np.array([])
    counts = {name_: int((labels == i).sum()) for i, name_ in enumerate(("train", "validation", "test"))}
    man = {"kind": "window_set", "name": name, "recording": recording["source_file"], "channel": int(recording["channel"]),
           "recording_id": int(recording["id"]), "fs": float(ws.fs), "length": int(ws.length), "n_windows": int(len(ws.starts)),
           "labels_source": "split" if (labels >= 0).any() else "none", "split_counts": counts,
           "spacing": {"min_gap": int(gaps.min()) if gaps.size else None, "train_safe": bool(gaps.size == 0 or gaps.min() >= ws.length)},
           "span": [int(ws.starts.min()) if len(ws.starts) else 0, int(ws.starts.max() + ws.length) if len(ws.starts) else 0],
           "recipe_hash": short_hash(recipe), "recipe": recipe, "step": int(step), "notes": notes, "producer": "webui/training save window set"}
    with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=2, default=str)
    return d


@router.post("/api/windowsets")
def save_window_set(request: Request, body: SaveBody):
    rt, manager = request.app.state.rt, request.app.state.manager
    if not _NAME.match(body.name):
        raise HTTPException(422, "name must be 1–64 characters of letters, digits, _ . - (no spaces)")
    snap = manager.snapshot(body.job_id)
    if snap is None or snap.get("kind", "chain_run") != "chain_run" or not snap.get("recipe"):
        raise HTTPException(404, f"no chain run job {body.job_id}")
    recipe = snap["recipe"]
    if not (0 <= body.step < len(recipe["steps"])):
        raise HTTPException(422, f"step {body.step} is not in this {len(recipe['steps'])}-step recipe")
    sub = dict(recipe); sub["steps"] = recipe["steps"][:body.step + 1]
    root = rt.window_sets_root
    if os.path.isdir(os.path.join(root, body.name)):
        raise HTTPException(409, f"a window set named {body.name!r} already exists under {root}")
    out = execute_recipe(sub, db_path=rt.db_path, force=True)
    result = out["result"]
    if result is None or result.output_kind != "windowset":
        raise HTTPException(422, f"step {body.step} emits {getattr(result, 'output_kind', None)!r}, not a WindowSet")
    c = _conn(request)
    try:
        rec = corpus.recording_row(c, recipe["recording_id"])
        d = write_window_set(root, body.name, result.value, rec, recipe, body.step, body.notes)
        # the registry's own scanner collects the facts its checks read (manifest, keys)
        cands = [k for k in reg.scan("window_set", roots=[root], conn=c) if os.path.normcase(os.path.abspath(k.path)) == os.path.normcase(os.path.abspath(d))]
        if not cands:
            raise HTTPException(500, f"the registry scanner did not find the window set it was just written to: {d}")
        cand = cands[0]
        report = reg.check(cand, c)
        if not report.ok:
            raise HTTPException(422, {"message": "the saved window set failed its own registration checks",
                                      "checks": [{"name": ch.name, "ok": ch.ok, "detail": ch.detail} for ch in report.checks]})
        rid = reg.register(c, cand, report, provenance={"producer": "webui/training", "notes": body.notes or ""}, writer=write_machine)
    finally:
        c.close()
    return {"id": rid, "name": body.name, "path": d, "n_windows": int(result.value.n_windows), "length": int(result.value.length),
            "run_id": out["run_id"], "note": rt.banner()}


@router.get("/api/windowsets")
def list_window_sets(request: Request):
    c = _conn(request)
    try:
        rows = c.execute("SELECT id, name, path, recording_id, channel, fs, params_json, created_at, active, manifest_path FROM registered_artifacts "
                         "WHERE kind = 'window_set' ORDER BY id DESC").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            mp = os.path.join(d["path"], "manifest.json")
            if os.path.isfile(mp):
                try:
                    with open(mp, encoding="utf-8") as f:
                        d["manifest"] = json.load(f)
                except Exception as e:
                    d["manifest_error"] = str(e)
            out.append(d)
    finally:
        c.close()
    return {"window_sets": out, "root": request.app.state.rt.window_sets_root}
