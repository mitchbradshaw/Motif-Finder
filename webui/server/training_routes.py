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

fixup-aa: the save also writes the `window_sets` row (§6.9) — the table Library ›
Window sets reads, which had 0 rows because nothing wrote it. The row carries the
split and its rule, the spacing check, the human-verdict coverage per split and per
class AT SAVE TIME (by `catalogue.manual_labels`' own rule, so the set and the block
count the same way), and the producing recipe's hash. A training set keeps no two
overlapping windows by default (`non_overlapping`, Q-W1 revised): the saved set is
the non-overlapping subset, labelled windows kept first, the rule recorded and the
dropped counted. The
directory also holds `windowset.npz` + `features.parquet` (`WindowSet.to_path`), so a
later reader (`AB`'s Models input) loads it with `WindowSet.from_path`.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from Adapters.catalogue_manual_labels import RULES as LABEL_RULES, human_spans, label_windows
from Working.execution import execute_recipe
from Working.recipes import short_hash
from Working.registration import core as reg
from Working.types import WindowSet

from . import corpus
from .writes import write_machine

router = APIRouter()
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class SaveBody(BaseModel):
    job_id: int
    step: int
    name: str
    notes: str | None = None
    # a training set keeps no two overlapping windows (Q-W1); off keeps every window
    non_overlapping: bool = True


_SPLIT_NAMES = ("train", "validation", "test")
_CLASSES = ("interesting", "not_interesting")
_FATES = ("interesting", "not_interesting", "unlabelled", "conflicting", "artifact")


def window_set_facts(ws, spans, split_rule: str | None, non_overlapping: bool):
    """The saved subset and everything the `window_sets` row says about it.

    Returns `(kept WindowSet, split_json, spacing_json, coverage_json, extra)`.
    Coverage is counted by `catalogue.manual_labels`' rule over the windows SAVED;
    `dropped_for_overlap` counts the windows the non-overlap rule left out of it."""
    lab = label_windows(ws.starts, ws.length, spans, non_overlapping=non_overlapping)
    keep = lab.fate != "dropped_for_overlap"
    feats = ws.features.loc[keep].reset_index(drop=True) if ws.features is not None else None
    kept = WindowSet(starts=np.asarray(ws.starts)[keep], length=int(ws.length), fs=float(ws.fs), features=feats)
    fate = lab.fate[keep]

    split = None
    if feats is not None and "split" in feats.columns:
        split = feats["split"].to_numpy()
        split_json = {"rule": split_rule or "unrecorded",
                      **{n: int((split == i).sum()) for i, n in enumerate(_SPLIT_NAMES)}}
    else:
        split_json = {"rule": "none",
                      "note": "this block assigns no split; a blocked split is applied where the set is trained on"}

    starts = np.sort(np.asarray(kept.starts))
    min_gap = int(np.diff(starts).min()) if len(starts) > 1 else None
    spacing_json = {"no two windows overlap": bool(min_gap is None or min_gap >= kept.length)}

    def tally(mask):
        return {f: int(((fate == f) & mask).sum()) for f in _FATES}

    everything = np.ones(len(fate), dtype=bool)
    by_split = {"all": tally(everything)}
    if split is not None:
        for i, n in enumerate(_SPLIT_NAMES):
            by_split[n] = tally(split == i)
    class_counts = {c: by_split["all"][c] for c in _CLASSES}
    coverage_json = {
        "labelled_windows": int(sum(class_counts.values())),
        "class_counts_at_save": class_counts,
        "class_counts": class_counts,
        "by_split": by_split,
        "unlabelled": by_split["all"]["unlabelled"],
        "conflicting": by_split["all"]["conflicting"],
        "artifact": by_split["all"]["artifact"],
        "seed": int(lab.counts.get("seed") or 0),
        "dropped_for_overlap": int(lab.counts["dropped_for_overlap"]),
        "dropped": int(lab.counts["dropped_for_overlap"]),
        "non_overlap_rule": lab.counts["non_overlap_rule"],
        "non_overlapping": bool(non_overlapping),
        "n_windows_offered": int(len(ws.starts)),
        "n_spans": len(spans),
        "rules": LABEL_RULES,
    }
    extra = {"min_gap": min_gap, "verdict_labels": lab.labels[keep]}
    return kept, split_json, spacing_json, coverage_json, extra


def _conn(request: Request):
    return corpus.connect(request.app.state.rt.db_path)


def write_window_set(root: str, name: str, ws, recording: dict, recipe: dict, step: int, notes: str | None = None,
                     verdict_labels=None, facts: dict | None = None) -> str:
    d = os.path.join(root, name)
    os.makedirs(d, exist_ok=True)
    labels = ws.features["split"].to_numpy() if ws.features is not None and "split" in ws.features.columns else np.full(len(ws.starts), -1)
    extra = {} if verdict_labels is None else {"verdict_labels": np.asarray(verdict_labels, dtype=np.int64)}
    np.savez_compressed(os.path.join(d, "windows.npz"), starts=np.asarray(ws.starts, dtype=np.int64), length=np.int64(ws.length),
                        fs=np.float64(ws.fs), source_file=np.str_(recording["source_file"]), channel=np.int64(recording["channel"]),
                        labels=np.asarray(labels, dtype=np.int64), **extra)
    ws.to_path(d)   # windowset.npz + features.parquet: `WindowSet.from_path(d)` reads the set back
    gaps = np.diff(np.asarray(ws.starts)) if len(ws.starts) > 1 else np.array([])
    counts = {name_: int((labels == i).sum()) for i, name_ in enumerate(("train", "validation", "test"))}
    man = {"kind": "window_set", "name": name, "recording": recording["source_file"], "channel": int(recording["channel"]),
           "recording_id": int(recording["id"]), "fs": float(ws.fs), "length": int(ws.length), "n_windows": int(len(ws.starts)),
           "labels_source": "split" if (labels >= 0).any() else "none", "split_counts": counts,
           "spacing": {"min_gap": int(gaps.min()) if gaps.size else None, "train_safe": bool(gaps.size == 0 or gaps.min() >= ws.length)},
           "span": [int(ws.starts.min()) if len(ws.starts) else 0, int(ws.starts.max() + ws.length) if len(ws.starts) else 0],
           "recipe_hash": short_hash(recipe), "recipe": recipe, "step": int(step), "notes": notes, "producer": "webui/training save window set",
           **(facts or {})}
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
        split_rule = (sub["steps"][-1].get("params") or {}).get("split_rule")
        if split_rule is None and result.value.features is not None and "split" in result.value.features.columns:
            split_rule = (result.meta or {}).get("split_rule")
        ws, split_json, spacing_json, coverage_json, extra = window_set_facts(
            result.value, human_spans(c, rec["id"]), split_rule, body.non_overlapping)
        if ws.n_windows == 0:
            raise HTTPException(422, "the step produced no windows to save")
        facts = {"split_json": split_json, "spacing_json": spacing_json, "coverage": coverage_json,
                 "min_gap": extra["min_gap"]}
        d = write_window_set(root, body.name, ws, rec, sub, body.step, body.notes,
                             verdict_labels=extra["verdict_labels"], facts=facts)
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
        starts = np.sort(np.asarray(ws.starts))
        stride = int(np.median(np.diff(starts))) if len(starts) > 1 else None
        made_by = f"Analyse › step {body.step + 1:02d} {sub['steps'][-1]['algorithm']} · job {body.job_id}"
        ws_id = write_machine(c, "window_sets", {
            "name": body.name, "version": 1, "path": d, "recording_id": int(rec["id"]), "channel": int(rec["channel"]),
            "fs": float(ws.fs), "window_length": int(ws.length), "stride": stride, "gap": extra["min_gap"],
            "n_windows": int(ws.n_windows), "split_json": json.dumps(split_json), "spacing_json": json.dumps(spacing_json),
            "coverage_json": json.dumps(coverage_json, default=str),
            "labels_source": f"human verdicts (annotations + window verdicts) · {made_by}",
            "recipe_hash": short_hash(sub), "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
        })
        c.commit()
    finally:
        c.close()
    return {"id": rid, "window_set_id": ws_id, "name": body.name, "path": d, "n_windows": int(ws.n_windows),
            "n_windows_offered": int(result.value.n_windows), "length": int(ws.length), "coverage": coverage_json,
            "split": split_json, "spacing": spacing_json, "run_id": out["run_id"], "note": rt.banner()}


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
