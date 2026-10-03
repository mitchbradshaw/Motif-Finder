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


# ── Models › Launch / Results / Compare (fixup-ab) ─────────────────────────
#
# The paired training job of RQ1 lives in the core (`Working/training/`); these
# routes only hand it a connection, a sandbox root and a job, and hand its
# results back. A window set ACROSS channels is saved from Launch as a
# `training` job (measuring ~10k windows takes a minute or two); the cut
# proposal and the Before-launch checks answer directly; training is a
# `training` job with per-stage progress. The held-out recording is never a
# source: it appears only as a locked slot, unlocked on Settings › Datasets.

from Working.training import paired as _tp  # noqa: E402
from Working.training import store as _ts  # noqa: E402
from Working.training import windows as _tw  # noqa: E402

from . import templates as _templates  # noqa: E402
from .runtime import HELD_OUT_FILE, REPO_ROOT  # noqa: E402

_LABEL_LENGTH, _LABEL_GRID = 600, 200     # the 10-minute labels' own grid (AA, Q-W1)
_HPC_NOTE = ("An HPC job's results re-enter the app only when Jobs › Manifest inbox is wired (its own prompt). "
             "For Q42's default — a random forest per arm — nothing needs the cluster: train locally.")


def _training_root(rt) -> str:
    return os.path.join(rt.dir, "training") if rt.mode == "sandbox" else os.path.join(REPO_ROOT, "DATA", "derived", "training")


def _hpc_dir(rt) -> str:
    return os.path.join(rt.dir, "hpc", "training") if rt.mode == "sandbox" else os.path.join(REPO_ROOT, "HPC", "Training", "generated")


def _template_geometry(t: dict, fs: float = 1.0) -> dict:
    """Window length, step and feature stages a training template's window matrix
    implies, and whether its windows can hold the 10-minute labels at all."""
    from Working.database import window_matrix_store as wm_store
    wm = next((s for s in t["steps"] if s.get("algorithm") == "window_matrix"), None)
    clf = next((s for s in t["steps"] if s.get("algorithm") == "classifier"), None)
    out = {"name": t["name"], "id": t.get("id"), "kind": t.get("kind"), "description": t.get("description", ""),
           "steps": [f"{s['stage']}.{s['algorithm']}" for s in t["steps"]],
           "n_estimators": int(((clf or {}).get("params") or {}).get("n_estimators", 300))}
    if wm is None:
        return {**out, "on_label_grid": False, "length": None, "grid": None, "stages": [],
                "reason": "no window-matrix step: the paired job measures windows with one"}
    p = wm.get("params") or {}
    m = int(round(float(p.get("window_min", 10.0)) * 60 * fs))
    step = int(wm_store.step_samples(m, float(p.get("step_frac", 1.0))))
    stages = [s for s, on in (("catch22", p.get("catch22", True)), ("fast_entropy", p.get("fast_entropy", True)),
                              ("slow_entropy", p.get("slow_entropy", True))) if on]
    on_grid = m == _LABEL_LENGTH and step == _LABEL_GRID
    reason = None if on_grid else (
        f"{m}-sample windows on a {step}-sample step are off the labels' {_LABEL_LENGTH}/{_LABEL_GRID} grid: no window "
        f"wholly contains a 10-minute label, so arm A would have no labels. Use manual_labels_model's geometry.")
    if p.get("cnn") or p.get("rf"):
        on_grid, reason = False, "its window matrix computes label-derived columns (cnn / rf); they stay off"
    return {**out, "on_label_grid": on_grid, "length": m, "grid": step, "stages": stages, "reason": reason}


def _multi_sets(c) -> list[dict]:
    out = []
    runs = _ts.list_runs(c)
    for r in c.execute("SELECT * FROM window_sets WHERE recording_id IS NULL AND EXISTS "
                       "(SELECT 1 FROM window_set_members m WHERE m.window_set_id = window_sets.id) ORDER BY id DESC"):
        d = {k: r[k] for k in r.keys()}
        for k in ("split_json", "spacing_json", "coverage_json"):
            d[k[:-5]] = json.loads(d.pop(k) or "null")
        d["members"] = _ts.members(c, r["id"])
        for m in d["members"]:
            m["counts"] = json.loads(m.pop("counts_json") or "{}")
        d["runs"] = [x for x in runs if (x["window_set"] or {}).get("key") == r["recipe_hash"]]
        out.append(d)
    return out


@router.get("/api/models/setup")
def models_setup(request: Request):
    rt = request.app.state.rt
    c = _conn(request)
    try:
        temps = [_template_geometry(t) for t in _templates.list_all(c) if t.get("kind") == "training"]
        names = corpus.dataset_names(c)
        recs = {}
        for r in c.execute("SELECT id, source_file, channel, fs, n_samples FROM recordings ORDER BY source_file, channel"):
            if r["source_file"] == HELD_OUT_FILE:
                continue
            counts = {v: n for v, n in c.execute(
                "SELECT verdict, COUNT(*) FROM annotations WHERE recording_id = ? AND deleted_at IS NULL GROUP BY verdict",
                (r["id"],))}
            g = recs.setdefault(r["source_file"], {"source_file": r["source_file"],
                                                   "name": names.get(r["source_file"], r["source_file"]),
                                                   "channels": []})
            g["channels"].append({"recording_id": int(r["id"]), "channel": int(r["channel"]),
                                  "hours": round(r["n_samples"] / float(r["fs"]) / 3600.0, 2), "fs": float(r["fs"]),
                                  "verdicts": int(sum(counts.values())),
                                  "interesting": int(counts.get("interesting", 0) + counts.get("seed", 0)),
                                  "not_interesting": int(counts.get("not_interesting", 0)),
                                  "artifact": int(counts.get("artifact", 0))})
        for g in recs.values():
            n = len(g["channels"])
            for ch in g["channels"]:
                ch["name"] = corpus.channel_name(g["source_file"], ch["channel"], n)
        return {
            "templates": temps,
            "recordings": [g for g in recs.values() if any(ch["verdicts"] for ch in g["channels"])],
            "recordings_without_verdicts": [g["source_file"] for g in recs.values()
                                            if not any(ch["verdicts"] for ch in g["channels"])],
            "held_out": {"file": HELD_OUT_FILE, "name": names.get(HELD_OUT_FILE, HELD_OUT_FILE), "locked": True,
                         "where": "Settings › Datasets",
                         "reason": "exam (iii): a different mushroom, scored once after the freeze when the researcher "
                                   "unlocks it; nothing on this page reads it"},
            "window_sets": _multi_sets(c),
            "runs": _ts.list_runs(c),
            "defaults": {"split": dict(_tw.DEFAULT_SPLIT), "stages": list(_tw.DEFAULT_STAGES),
                         "length": _LABEL_LENGTH, "grid": _LABEL_GRID, "rf_shuffles": 200, "full_shuffles": 5,
                         "bootstrap_n": 1000, "block_hours": 24.0, "n_estimators": 300, "linkage": "ward",
                         "test_warn_below": _tp.TEST_WARN_BELOW},
            "local_limit_s": _tp.LOCAL_LIMIT_S,
            "hpc_note": _HPC_NOTE,
            "note": rt.banner(),
        }
    finally:
        c.close()


class PooledSetBody(BaseModel):
    name: str
    source_file: str
    channels: list[int]
    exam_channels: list[int] = []
    length: int = _LABEL_LENGTH
    grid: int = _LABEL_GRID
    stages: list[str] = list(_tw.DEFAULT_STAGES)
    split: dict = {}
    template: str | None = None
    notes: str | None = None


def _refuse_held_out(source_file: str):
    if source_file == HELD_OUT_FILE:
        raise HTTPException(423, f"{HELD_OUT_FILE} is held out (exam iii); it is never a training source and is "
                                 "unlocked only on Settings › Datasets, after the freeze")


@router.post("/api/models/windowsets")
def models_save_window_set(request: Request, body: PooledSetBody):
    rt, manager = request.app.state.rt, request.app.state.manager
    _refuse_held_out(body.source_file)
    if not _NAME.match(body.name):
        raise HTTPException(422, "name must be 1–64 characters of letters, digits, _ . - (no spaces)")
    try:
        _tw.check_split({**_tw.DEFAULT_SPLIT, **body.split})
        _tw.check_stages(tuple(body.stages))
    except ValueError as e:
        raise HTTPException(422, str(e))
    if not body.channels:
        raise HTTPException(422, "tick at least one training channel")
    root = rt.window_sets_root

    def work(job):
        c = _conn(request)
        try:
            ps = _tw.build_pooled_set(c, body.source_file, body.channels, exam_channels=body.exam_channels,
                                      length=body.length, grid=body.grid, split=body.split, stages=tuple(body.stages),
                                      progress=lambda d, t, m: job.progress(d, t, m),
                                      cancel=job.cancel_event.is_set)
            ws_id = _ts.save_window_set(c, ps, root, body.name, notes=body.notes)
            row = _ts.window_set_row(c, {"id": ws_id})
            return {"window_set_id": int(ws_id), "name": body.name, "version": int(row["version"]), "key": ps.key,
                    "n_windows": int(len(ps.table)), "by_role": _tw.role_counts(ps), "path": row["path"],
                    "per_channel": [{k: v for k, v in ch.items() if k != "blocks"} for ch in ps.meta["per_channel"]]}
        finally:
            c.close()

    job = manager.start_job("training", work, meta={"stage": "window set", "name": body.name,
                                                    "source_file": body.source_file, "channels": body.channels,
                                                    "exam_channels": body.exam_channels, "template": body.template})
    return job.snapshot()


def _load(c, window_set_id: int):
    try:
        return _ts.load_window_set(c, {"id": int(window_set_id)})
    except _tw.HeldOutRefused as e:
        raise HTTPException(423, str(e))
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(404, str(e))


class ProposeBody(BaseModel):
    window_set_id: int
    linkage: str = "ward"
    k_min: int = 2
    k_max: int = 8


_PROPOSALS: dict = {}


@router.post("/api/models/propose")
def models_propose(request: Request, body: ProposeBody):
    c = _conn(request)
    try:
        row, ps = _load(c, body.window_set_id)
    finally:
        c.close()
    key = (ps.key, body.linkage, body.k_min, body.k_max)
    if key not in _PROPOSALS:
        _PROPOSALS[key] = _tp.propose(ps, linkage=body.linkage, k_range=(body.k_min, body.k_max))
    return {**_PROPOSALS[key], "window_set_id": int(row["id"]), "key": ps.key}


class RecipeBody(BaseModel):
    window_set_id: int
    k: int | None = None
    translation: dict | None = None
    linkage: str = "ward"
    n_estimators: int = 300
    class_weight: str = "balanced"
    random_state: int = 42
    rf_shuffles: int = 200
    full_shuffles: int = 5
    bootstrap_n: int = 1000
    block_hours: float = 24.0
    target_precision: float = 0.8
    reference: bool = False


def _recipe(row, ps, body: RecipeBody) -> dict:
    return _tp.make_recipe({"id": int(row["id"]), "name": row["name"], "version": int(row["version"]), "key": ps.key},
                           k=body.k, translation=body.translation, linkage=body.linkage,
                           n_estimators=body.n_estimators, class_weight=body.class_weight,
                           random_state=body.random_state, rf_shuffles=body.rf_shuffles,
                           full_shuffles=body.full_shuffles, bootstrap_n=body.bootstrap_n,
                           block_hours=body.block_hours, target_precision=body.target_precision,
                           reference=body.reference)


@router.post("/api/models/checks")
def models_checks(request: Request, body: RecipeBody):
    c = _conn(request)
    try:
        row, ps = _load(c, body.window_set_id)
        recipe = _recipe(row, ps, body)
        checks = _tp.validate(recipe, ps)
        frozen = None
        if body.k is not None:
            try:
                _ts.check_cut_frozen(c, recipe, ps.key)
            except _ts.CutFrozen as e:
                frozen = str(e)
        checks.append({"name": "cut not changed after a test score", "ok": frozen is None,
                       "level": "error" if frozen else "pass",
                       "detail": frozen or "no run on this set has scored a different cut"})
    finally:
        c.close()
    est = _tp.estimate(recipe, ps)
    if body.reference:
        # measured 2026-10-03: four CNNs + the catch22 forest on CPU, ~1.5 s per exam window
        est["parts"]["reference"] = 1.5 * int(ps.role_mask("test", "exam").sum())
        est["seconds"] = float(sum(est["parts"].values()))
        est["where"] = "local" if est["seconds"] <= _tp.LOCAL_LIMIT_S else "slurm"
    return {"checks": checks, "estimate": est, "recipe": recipe, "recipe_hash": short_hash(recipe),
            "by_role": _tw.role_counts(ps), "ok": not any(ch["level"] == "error" for ch in checks)}


_STAGES = {0: "features", 1: "cluster", 2: "train", 3: "null", 4: "score", 5: "calibrate", 6: "done"}


@router.post("/api/models/train")
def models_train(request: Request, body: RecipeBody):
    rt, manager = request.app.state.rt, request.app.state.manager
    c = _conn(request)
    try:
        row, ps = _load(c, body.window_set_id)
        recipe = _recipe(row, ps, body)
        if body.k is None:
            raise HTTPException(422, "choose arm B's cut (k) first")
        try:
            _ts.check_cut_frozen(c, recipe, ps.key)
        except _ts.CutFrozen as e:
            raise HTTPException(409, str(e))
        errors = [ch for ch in _tp.validate(recipe, ps) if ch["level"] == "error"]
        if errors:
            raise HTTPException(422, {"message": "the Before-launch checks refuse this job", "checks": errors})
    finally:
        c.close()
    root = _training_root(rt)

    def work(job):
        cc = _conn(request)
        try:
            def progress(done, total, message):
                job.meta["stage"] = _STAGES.get(int(done), "reference") if total == 6 else "reference"
                job.progress(done, total, message)
            out = _ts.run_and_record(cc, recipe, root, progress=progress, cancel=job.cancel_event.is_set)
            ex = out["results"]["exams"].get(_tp.EXAM_I) or {}
            head = ({arm: ex["arms"][arm]["macro_f1"] for arm in ("A", "B")} if ex.get("status") == "scored" else None)
            return {"run_id": int(out["run_id"]), "recipe_hash": out["config_hash"], "macro_f1": head,
                    "results_path": out["results_path"]}
        finally:
            cc.close()

    job = manager.start_job("training", work, meta={"stage": "queued", "window_set": recipe["window_set"],
                                                    "k": recipe["arms"]["B"]["k"], "recipe_hash": short_hash(recipe),
                                                    "where": "local"})
    return job.snapshot()


@router.post("/api/models/slurm")
def models_slurm(request: Request, body: RecipeBody):
    from Working.hpc.job_export import export_training_job
    rt = request.app.state.rt
    c = _conn(request)
    try:
        row, ps = _load(c, body.window_set_id)
        recipe = _recipe(row, ps, body)
    finally:
        c.close()
    est = _tp.estimate(recipe, ps)
    base = f"paired_{row['name']}_k{body.k}_{short_hash(recipe)}"
    res = export_training_job(recipe, out_dir=_hpc_dir(rt), base_name=base, est_seconds=est["seconds"])
    return {**res, "estimate": est, "note": _HPC_NOTE}


@router.get("/api/models/runs")
def models_runs(request: Request):
    manager = request.app.state.manager
    c = _conn(request)
    try:
        runs = _ts.list_runs(c)
    finally:
        c.close()
    live = [j.snapshot() for j in list(manager.jobs.values()) if getattr(j, "kind", None) == "training"]
    return {"runs": runs, "jobs": sorted(live, key=lambda s: -s["job_id"])}


def _run_or_404(c, run_id: int) -> dict:
    got = _ts.get_run(c, run_id)
    if got is None:
        raise HTTPException(404, f"no paired training run {run_id}")
    return got


@router.get("/api/models/runs/{run_id}")
def models_run(request: Request, run_id: int):
    c = _conn(request)
    try:
        return _run_or_404(c, run_id)
    finally:
        c.close()


_DIFFERS = (
    ("template", lambda r: (r["window_set"].get("length"), r["window_set"].get("grid"),
                            tuple(r["window_set"].get("stages") or ()))),
    ("window set", lambda r: r["window_set"].get("key")),
    ("split", lambda r: json.dumps(r["window_set"].get("split"), sort_keys=True)),
    ("classifier", lambda r: json.dumps(r["recipe"]["classifier"], sort_keys=True)),
    ("options", lambda r: json.dumps({k: r["recipe"][k] for k in ("null", "bootstrap", "train_on")}, sort_keys=True)),
)


@router.get("/api/models/runs/{run_id}/compare")
def models_compare(request: Request, run_id: int):
    """Arm A against arm B of one paired run (spec §7b.4): what differs between
    them (only the label source, by construction), and per exam the paired numbers."""
    c = _conn(request)
    try:
        got = _run_or_404(c, run_id)
    finally:
        c.close()
    res = got["results"]
    if not res:
        raise HTTPException(409, f"run {run_id} is {got['status']}: no results to compare")
    differs = [{"name": n, "a": str(f(res)), "b": str(f(res)), "same": True} for n, f in _DIFFERS]
    differs.append({"name": "label source", "a": "manual (human verdicts)",
                    "b": f"cluster ({res['cluster']['linkage']}, k = {res['cluster']['k']}, translated)", "same": False})
    exams = {}
    for e, ex in res["exams"].items():
        if ex.get("status") != "scored":
            exams[e] = {"status": ex.get("status"), "reason": ex.get("reason")}
            continue
        arms = {}
        for arm in ("A", "B"):
            a = ex["arms"][arm]
            d = a["null"]["draws"] or [0.0]
            arms[arm] = {"macro_f1": a["macro_f1"], "macro_f1_ci": a["macro_f1_ci"],
                         "balanced_accuracy": a["balanced_accuracy"],
                         "null_band": [float(np.quantile(d, 0.05)), float(np.quantile(d, 0.95))],
                         "null_p": a["null"]["p"], "per_class": a["per_class"]}
        exams[e] = {"status": "scored", "n_windows": ex["n_windows"], "class_counts": ex["class_counts"],
                    "n_units": ex["n_units"], "unit": ex["unit"], "arms": arms,
                    **{k: ex["paired"][k] for k in ("delta_f1", "delta_f1_ci", "delta_draws_sample", "mcnemar",
                                                    "agreement", "per_class_delta")},
                    "per_channel": ex["per_channel"]}
    return {"run_id": run_id, "recipe_hash": res["recipe_hash"],
            "attributable": sum(not d["same"] for d in differs) == 1,
            "differs": differs, "exams": exams, "cluster": res["cluster"], "notes": res["notes"],
            "reference": res.get("reference") or [], "yardstick_b": res["yardstick_b"]}


@router.get("/api/models/runs/{run_id}/disagreements")
def models_disagreement(request: Request, run_id: int, filter: str = "only_a", i: int = 1, exam: str = _tp.EXAM_I):
    """The i-th window (1-based) where only A, only B, or neither arm was right:
    the window's signal, the human verdict and both arms' predictions."""
    if filter not in ("only_a", "only_b", "both_wrong"):
        raise HTTPException(422, "filter is only_a | only_b | both_wrong")
    c = _conn(request)
    try:
        got = _run_or_404(c, run_id)
        res = got["results"]
        ex = (res or {}).get("exams", {}).get(exam) or {}
        if ex.get("status") != "scored":
            raise HTTPException(404, f"exam {exam} has no scored windows in run {run_id}")
        row, ps = _load(c, res["window_set"]["id"])
        ids = np.asarray(ex["window_ids"])
        y = ps.table["label"].to_numpy()[ids]
        pa, pb = np.asarray(ex["predictions"]["A"]), np.asarray(ex["predictions"]["B"])
        ok_a, ok_b = pa == y, pb == y
        masks = {"only_a": ok_a & ~ok_b, "only_b": ~ok_a & ok_b, "both_wrong": ~ok_a & ~ok_b}
        hits = np.flatnonzero(masks[filter])
        counts = {k: int(v.sum()) for k, v in masks.items()}
        if not (1 <= i <= len(hits)):
            raise HTTPException(404, f"{filter}: {len(hits)} window(s); there is no #{i}")
        j = int(hits[i - 1])
        w = ps.table.iloc[int(ids[j])]
        rec = corpus.recording_row(c, int(w["recording_id"]))
        length = int(ps.meta["length"])
        ch = corpus.display_channel(rec)
        x = ch[int(w["start"]):int(w["start"]) + length]
        step = max(1, len(x) // 300)
        names = ("not_interesting", "interesting")
        return {"run_id": run_id, "exam": exam, "filter": filter, "i": i, "n": int(len(hits)), "counts": counts,
                "window": {"recording_id": int(w["recording_id"]), "channel": int(w["channel"]),
                           "channel_name": rec["name"], "start": int(w["start"]), "end": int(w["start"]) + length,
                           "fs": float(rec["fs"])},
                "human": names[int(y[j])], "a": names[int(pa[j])], "b": names[int(pb[j])],
                "trace": [float(v) for v in x[::step]], "unit": ch.unit}
    finally:
        c.close()
