"""Run every builder setting on every demo channel, with its paired null, and keep what the demo draws.

    "/c/ProgramData/anaconda3/python.exe" scripts/neurips_demo/precompute_chains.py [--workers 3] [--only ID] [--slices 1,2]

Run from the demo worktree's root after build_slices.py. Every chain runs through the real core
(`Working.run_groups.run_paired_recipe`: the recipe, then NULL_DRAWS copies with `preprocessing.surrogate`
prepended), on the demo's own work database, with every core output path pointed under DATA/neurips_demo/work/.

Writes, per setting and slice, DATA/neurips_demo/store/chains/<combo id>/<slice id>.json:

    events      one row per event: span (slice samples), score, and the event-shape measures
                (onset / extremum / recovery index, amplitude mV, width s, fall time, steepest slope ...)
    rose        the steepest-slope rose (event_shape's own bins)
    intervals   interval_stats per group (CV, CV2, LV with their nulls)
    null        detections per surrogate draw
    letters     the drop detector's encoding (segment bounds + letters), for the Analyse view
    timing_s    wall time of the real run and of the null

and, once per (look-for, window, slice), store/clean/<look>_w<window>/<slice id>.npy: the cleaned trace as float32,
for the Analyse page's "after Clean" view.

A setting already written is skipped, so the script can be stopped and started again.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import demo_config as C  # noqa: E402

DEMO = ROOT / C.DEMO_DATA
STORE = DEMO / "store"
WORK = DEMO / "work"


def _redirect_core(worker: int):
    """Point every core path that writes under this worker's own corner of DATA/neurips_demo/work/ (the sandbox
    runtime's list, webui/server/runtime.py), so nothing lands in DATA/ or Results/ of any checkout."""
    import Working.config as cfg
    import Adapters.detection_matrix_profile as _mp
    import Adapters.preprocessing_window_matrix as _wm
    import Adapters.catalogue_classifier as _cc
    import Adapters.catalogue_cluster as _cl
    import Adapters.preprocessing_window_pool as _wp
    import Adapters.preprocessing_trace_shape as _tsh
    import Adapters.catalogue_shape_cluster as _csc

    base = WORK / f"w{worker}"
    base.mkdir(parents=True, exist_ok=True)
    cfg.STEP_CACHE_ROOT = str(base / "step_cache")
    _mp.RESULTS_DIR = str(base / "mp")
    _wm.RESULTS_DIR = str(base / "wm")
    _cc.MODEL_ROOT = str(base / "models")
    _cl.RESULTS_DIR = str(base / "cl")
    _wp.POOL_ROOT = str(base / "pool")
    _tsh.RESULTS_DIR = str(base / "tsh")
    _csc.RESULTS_DIR = str(base / "csc")
    db = base / "demo.sqlite"
    if not db.exists():
        shutil.copyfile(WORK / "demo.sqlite", db)
    return str(db)


def _clean_path(c, sid):
    return STORE / "clean" / f"{c['look_for']}_w{int(round(c['window_s']))}" / f"{sid}.npy"


def _out_path(c, sid):
    return STORE / "chains" / c["id"] / f"{sid}.json"


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(f) else round(f, 6)


def run_one(c, s, db_path):
    from Working.recipes import make_recipe
    from Working.run_groups import run_paired_recipe

    steps = C.recipe_steps(c)
    recipe = make_recipe(s["id"], steps, span=None)
    captured = {}

    def on_step(i, result):
        captured[i] = result

    from Working.execution import execute_recipe

    names = [st["algorithm"] for st in steps]
    t0 = time.perf_counter()
    out = execute_recipe(recipe, db_path=db_path, on_step_result=on_step)
    wall = time.perf_counter() - t0
    # The null needs only "how many events does the detector find on a noise copy": the paired null of the chain
    # up to the detector (event shape and intervals never drop a span, so the count is the same, and measuring
    # several hundred noise events ten times over was 95 % of a sensitive setting's time).
    i_det = max(i for i, n in enumerate(names) if n in ("drop_detection", "noise_threshold", "cwt_ridges"))
    prefix = make_recipe(s["id"], steps[: i_det + 1], span=None)
    t1 = time.perf_counter()
    nul = run_paired_recipe(prefix, db_path=db_path, surrogate=True,
                            surrogate_params={"method": C.NULL_METHOD, "seed": 0}, surrogate_draws=C.NULL_DRAWS)
    wall_null = time.perf_counter() - t1
    i_detrend = names.index("detrend")
    i_shape = names.index("event_shape")
    i_iv = names.index("intervals")
    final = captured.get(i_iv) or out.get("result")
    shape = captured.get(i_shape)
    if final is None or shape is None:
        raise RuntimeError(f"{c['id']} slice {s['id']}: a step result was not captured (reused run?)")

    # the cleaned trace, once per (look, window, slice)
    cp = _clean_path(c, s["id"])
    if not cp.exists():
        cp.parent.mkdir(parents=True, exist_ok=True)
        x = np.asarray(captured[i_detrend].value.x, dtype=np.float32)
        np.save(cp, x)

    ss = final.value
    feats = ss.features
    events = []
    for k in range(len(ss.starts)):
        a, b = int(ss.starts[k]), int(ss.ends[k])
        row = {"s": a, "e": b, "score": _num(ss.scores[k]) if ss.scores is not None else None}
        if feats is not None and k < len(feats):
            f = feats.iloc[k]
            for col in feats.columns:
                v = f[col]
                if col.endswith("_idx"):
                    # already in the analysed signal's frame (the whole slice), like `starts`
                    row[col] = None if v is None or (isinstance(v, float) and not np.isfinite(v)) else int(v)
                elif isinstance(v, (str, bool)) or v is None:
                    row[col] = v
                else:
                    row[col] = _num(v)
        events.append(row)

    letters = None
    if "stage_encoding" in names:
        enc = captured[names.index("stage_encoding")].value
        letters = _letters(enc, int(round(float(c["knobs"]["segment_s"]) * float(s["fs"]))))

    null = [int(len(r["result"].value.starts)) if r.get("result") is not None else int(r.get("detections_written") or 0)
            for r in nul.get("surrogate_results", [])]
    rec = {
        "combo": c["id"], "slice": s["id"], "n": len(events), "events": events,
        "rose": _jsonable(shape.meta.get("rose")),
        "intervals": _jsonable(final.meta.get("interval_stats")),
        "null": null, "letters": letters,
        "timing_s": {"wall": round(wall + wall_null, 2), "real": round(wall, 2), "null": round(wall_null, 2),
                     "steps": {str(k): round(v, 3) for k, v in (out.get("step_timings") or {}).items()}},
    }
    p = _out_path(c, s["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, separators=(",", ":")))
    os.replace(tmp, p)
    return rec


def _letters(enc, seg_samples):
    """The symbolic encoding: one letter per segment of `seg` samples, contiguous from sample 0."""
    vals = getattr(enc, "values", None)
    if vals is None or getattr(enc, "kind", "symbolic") != "symbolic":
        return None
    return {"seg": int(seg_samples), "letters": [str(v) for v in np.asarray(vals).ravel()]}


def _jsonable(o):
    if o is None:
        return None
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return _jsonable(o.tolist())
    if isinstance(o, (np.floating, float)):
        return _num(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    return o


def worker(args):
    wid, jobs = args
    db = _redirect_core(wid)
    slices = {s["id"]: s for s in json.loads((STORE / "slices.json").read_text())["slices"]}
    by_id = {c["id"]: c for c in C.combos()}
    log = (WORK / f"w{wid}.log").open("a", encoding="utf-8")
    done = 0
    for cid, sid in jobs:
        c, s = by_id[cid], slices[sid]
        if _out_path(c, sid).exists():
            continue
        try:
            rec = run_one(c, s, db)
            done += 1
            log.write(f"{time.strftime('%H:%M:%S')} ok {cid} {sid} n={rec['n']} null={rec['null']} wall={rec['timing_s']['wall']}\n")
        except Exception:
            log.write(f"{time.strftime('%H:%M:%S')} FAIL {cid} {sid}\n{traceback.format_exc()}\n")
        log.flush()
    log.close()
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--only", default=None, help="one combo id")
    ap.add_argument("--slices", default=None, help="comma-separated slice ids")
    ap.add_argument("--group", default=None, help="only one Clean group, e.g. rises_w300")
    ap.add_argument("--reverse", action="store_true", help="work the list from its end (a helper meeting a worker)")
    ap.add_argument("--worker-base", type=int, default=0, help="first worker folder number (helpers use their own)")
    a = ap.parse_args()
    os.chdir(ROOT)
    slices = json.loads((STORE / "slices.json").read_text())["slices"]
    sids = [s["id"] for s in slices] if not a.slices else [int(v) for v in a.slices.split(",")]
    cs = [c for c in C.combos() if (a.only is None or c["id"] == a.only)
          and (a.group is None or f"{c['look_for']}_w{int(round(c['window_s']))}" == a.group)]
    # partition by the Clean prefix (look-for, window) so no two workers share a step-cache prefix
    groups = {}
    for c in cs:
        groups.setdefault((c["look_for"], c["window_s"]), []).append(c)
    buckets = [[] for _ in range(max(1, a.workers))]
    for i, (_, g) in enumerate(sorted(groups.items())):
        for c in g:
            for sid in sids:
                buckets[i % len(buckets)].append((c["id"], sid))
    if a.reverse:
        buckets = [list(reversed(b)) for b in buckets]
    print(f"{len(cs)} settings x {len(sids)} slices = {sum(len(b) for b in buckets)} chains on {len(buckets)} workers")
    if len(buckets) == 1:
        print("done", worker((a.worker_base, buckets[0])))
        return
    with mp.get_context("spawn").Pool(len(buckets)) as pool:
        print("done", sum(pool.map(worker, [(a.worker_base + i, b) for i, b in enumerate(buckets)])))


if __name__ == "__main__":
    main()
