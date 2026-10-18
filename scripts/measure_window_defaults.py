"""
measure_window_defaults.py
==========================
Round A_2, P3: which window length should the three drop detectors (drop_detection_v1, drop_detection_v5,
wavelet_encoded) run in? Each is run whole-span and in 12, 24, 72 and 168 h windows at 50 % overlap through the real
code path (`fanout.plan` with a window scope, `fanout.start`: every window an ordinary run, stitched), each with one
paired null draw, on synthetic recordings at 1 Hz:

* **regimes** (336 h): a loud background (five times the noise, a deep drop every hour) holding quiet stretches of
  6, 12, 24, 48 and 96 h, each with a weak drop every hour. The question is the researcher's: "a loud week sets the
  bar for a quiet hour". Reported: the share of weak drops found per quiet-stretch length, the share of deep drops
  found, and detections that match no planted drop, per hour.
* **ar1** and **random_walk** (336 h each, nothing planted): detections per hour, and what the windows' own null
  finds per hour — a window length that inflates noise detections shows here.

    python scripts/measure_window_defaults.py --out logs/window_defaults.json            # all of it, ~10-20 min
    python scripts/measure_window_defaults.py --detectors drop_detection_v1 --hours 168  # a quicker look
    python scripts/measure_window_defaults.py --short-scales     # 1 h and 10 min, fitted and as they are (RQ4b)

On a sandbox copy of the real database (never the real one: the script refuses the main checkout's
DATA/db/annotations.sqlite by any name, as scripts/backfill_seed_entry_ids.py does), the same table against the human
verdicts (interesting / seed as the truth, recall within 10 min, detections per hour):

    python scripts/measure_window_defaults.py --db webui/runtime/<stamp>/annotations.sqlite --recording-ids 3,4
    python scripts/measure_window_defaults.py --db ... --recording-ids 3 --scales 1,0.1667 --allow-short   # the sweep's scales

The chains are the canonical / overnight-sweep ones (webui/server/templates.py; HPC/Detection/generated/rq4_overnight).
Writes nothing outside a temporary folder (synthetic mode) or the sandbox database it is given.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

import numpy as np
from scipy.signal import lfilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

#: the Win32 long-path prefix (two backslashes, "?", one backslash), which names the same file
LONG_PREFIX = chr(92) * 2 + "?" + chr(92)


def main_checkout(root=ROOT):
    """The main checkout this script belongs to (`scripts/backfill_seed_entry_ids.py`'s rule): a worktree's own tree
    is not where the real database lives; `git rev-parse --git-common-dir` names the shared `.git`, whose parent is
    the main checkout. The script's own checkout when git cannot be asked."""
    try:
        out = subprocess.run(["git", "-C", root, "rev-parse", "--git-common-dir"], capture_output=True, text=True,
                             timeout=30)
        common = out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        common = ""
    if common:
        common = os.path.normpath(common if os.path.isabs(common) else os.path.join(root, common))
        if os.path.basename(common).lower() == ".git":
            return os.path.dirname(common)
    return root


#: `Working.database.schema.DB_PATH` (relative to the repository) resolved against the main checkout
REAL_DB = os.path.join(main_checkout(), "DATA", "db", "annotations.sqlite")


def _canonical(path):
    """A path as one spelling: absolute, links and junctions resolved, the long-path prefix dropped, case folded."""
    p = os.path.realpath(os.path.abspath(path))
    if p.startswith(LONG_PREFIX):
        p = p[len(LONG_PREFIX):]
    return os.path.normcase(os.path.normpath(p))


def is_the_real_database(path, real=REAL_DB):
    """True when ``path`` names the real database by any name: the spellings compared once resolved, then the files
    themselves (`os.path.samefile`, which also catches a hard link)."""
    if _canonical(path) == _canonical(real):
        return True
    try:
        return os.path.samefile(path, real)
    except OSError:
        return False

H = 3600
SCALES_H = (12, 24, 72, 168)
QUIET_H = (6, 12, 24, 48, 96)
NULL = {"method": "phase_randomize", "seed": 0}

CHAINS = {
    "drop_detection_v1": [
        {"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean_nearest", "window_s": 4916.67}},
        {"stage": "detection", "algorithm": "stage_encoding",
         "params": {"segment_seconds": 98.33, "same_fraction": 0.6, "slope_sigma": 8.0}},
        {"stage": "detection", "algorithm": "drop_detection", "params": {}}],
    "drop_detection_v5": [
        {"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean_nearest", "window_s": 4916.67}},
        {"stage": "detection", "algorithm": "stage_encoding",
         "params": {"same_fraction": 0.58, "segment_seconds": 20, "slope_sigma": 8}},
        {"stage": "detection", "algorithm": "drop_detection", "params": {"min_fall_dominance": 0.175, "min_rise_frac": 0.495}}],
    "wavelet_encoded": [
        {"stage": "preprocessing", "algorithm": "wavelet_bands", "params": {"level": 4, "levels": 0, "wavelet": "db4"}},
        {"stage": "detection", "algorithm": "stage_encoding",
         "params": {"merge_gap_segments": 0, "noise_estimator": "second_difference", "same_fraction": 0.6,
                    "segment_seconds": 60, "slope_sigma": 8, "threshold_mode": "quantile",
                    "trend_estimator": "ols_slope"}},
        {"stage": "detection", "algorithm": "drop_detection",
         "params": {"bracket_on_fall_runs": True, "bracket_on_up_runs": True, "bracket_rise_on_separation": False,
                    "lookahead_mult": 3, "min_depth_frac": 0.1, "min_fall_dominance": 0.5, "min_rise_frac": 0.5,
                    "min_separation_s": 0, "morphology": "auto", "noise_estimator": "second_difference",
                    "slope_sigma": 8, "tighten_windows": True, "trough_knee_frac": 0.05, "walk_onset_back": True,
                    "window_cap_mult": 6, "window_pad_frac": 0.25}}],
}


def _ar1(n, phi, sd, rng):
    return lfilter([1.0], [1.0, -phi], rng.standard_normal(n) * sd)


def _drop(depth, fall_s=20, tau_s=300):
    return np.concatenate([-depth * (np.arange(fall_s) / fall_s), -depth * np.exp(-np.arange(6 * tau_s) / tau_s)])


def regimes(hours=336, seed=7, deep=0.3, weak=0.02, sd=0.00005, loud_x=5.0):
    """The loud background with quiet stretches of `QUIET_H` hours, 24 h of loud between them; a drop every hour,
    deep in the loud parts and weak in the quiet ones. Returns (x, events) with events [{onset, kind, quiet_h}]."""
    rng = np.random.default_rng(seed)
    n = int(hours * H)
    x = _ar1(n, 0.97, sd, rng)
    loud = np.ones(n, dtype=bool)
    stretches, t = [], 24 * H
    for q in QUIET_H:
        if t + q * H > n:
            break
        loud[t:t + q * H] = False
        stretches.append((t, t + q * H, q))
        t += q * H + 24 * H
    x[loud] += _ar1(n, 0.97, sd * loud_x, rng)[loud]
    events = []
    for a in range(H // 2, n - 2 * H, H):
        quiet = next((q for lo, hi, q in stretches if lo + 600 <= a < hi - 2400), None)
        inside_loud = loud[a] and loud[min(n - 1, a + 2400)]
        if quiet is None and not inside_loud:
            continue                                    # straddles a regime boundary: left out of both counts
        d = _drop(weak if quiet is not None else deep)
        x[a:a + len(d)] += d
        events.append({"onset": int(a), "kind": "weak" if quiet is not None else "deep", "quiet_h": quiet})
    return x, events


def noise(kind, hours=336, seed=11, sd=0.00015):
    rng = np.random.default_rng(seed)
    n = int(hours * H)
    return _ar1(n, 0.97, sd, rng) if kind == "ar1" else np.cumsum(rng.standard_normal(n) * sd / 3.0)


def _match(spans, onsets, tol=600):
    """Each onset found when a span starts within `tol` before it or covers it; spans matching none are extra."""
    found, used = [], set()
    for a in onsets:
        hit = next((i for i, (s, e) in enumerate(spans) if s - tol <= a <= e + 60), None)
        found.append(hit is not None)
        if hit is not None:
            used.add(hit)
    return found, len(spans) - len(used)


#: how a window shorter than the chain's bound is treated (`--fit`, `--allow-short`): refused unless one is given
SHORT = {}


def _run(db, rid, steps, n, scale_h, draws=1):
    """One application through the real path; returns (spans, null spans per draw, seconds, windows)."""
    from Working.database import runs as R
    from Working.database.schema import init_db
    from Working.discovery import fanout

    conn = init_db(db)
    try:
        plan = fanout.plan(conn, steps=steps, recording_ids=[rid], span=(0, n), ceiling_s=10 ** 9, null_draws=draws,
                           surrogate=draws > 0, surrogate_params=NULL,
                           windows=(None if scale_h is None else dict({"window_s": scale_h * H, "overlap_frac": 0.5},
                                                                      **SHORT)))
    finally:
        conn.close()
    if not plan["runnable"]:
        return None, None, 0.0, 0, plan["reason"]
    t0 = time.perf_counter()
    out = fanout.start(plan, db_path=db, surrogate=draws > 0, surrogate_params=NULL, surrogate_draws=draws or None)
    el = time.perf_counter() - t0
    conn = init_db(db)
    try:
        row = out["runs"][0]
        spans = [(int(d["start_idx"]), int(d["end_idx"])) for d in R.list_detections(conn, row["run_id"])]
        nulls = [[(int(d["start_idx"]), int(d["end_idx"])) for d in R.list_detections(conn, i)]
                 for i in row["surrogate_run_ids"]]
    finally:
        conn.close()
    return spans, nulls, el, (plan.get("windows") or {}).get("per_channel", 1), None


def synthetic(args):
    import Working.config as cfg
    from Working.database import queries as q
    from Working.database.schema import init_db

    tmp = tempfile.mkdtemp(prefix="p3_window_defaults_")
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    db = os.path.join(tmp, "annotations.sqlite")
    init_db(db).close()
    recs = {}
    x, events = regimes(hours=args.hours, weak=args.weak)
    recs["regimes"] = (x, events)
    for kind in ("ar1", "random_walk"):
        recs[kind] = (noise(kind, hours=args.hours), [])
    ids = {}
    conn = init_db(db)
    try:
        for name, (sig, _) in recs.items():
            npy = os.path.join(tmp, f"{name}.npy")
            np.save(npy, sig)
            ids[name] = q.insert_recording(conn, f"{name}.mat", 0, 1.0, len(sig), 0, npy, units="V")
    finally:
        conn.close()
    rows = []
    for det in args.detectors:
        steps = CHAINS[det]
        for scale in (None,) + tuple(s for s in args.scales if s <= args.hours):
            entry = {"detector": det, "scale": "whole" if scale is None else f"{scale} h"}
            for name, (sig, ev) in recs.items():
                spans, nulls, el, nw, refused = _run(db, ids[name], steps, len(sig), scale, draws=args.draws)
                if refused:
                    entry[name] = {"refused": refused}
                    continue
                hours = len(sig) / float(H)
                e = {"detections": len(spans), "per_h": round(len(spans) / hours, 4), "seconds": round(el, 1),
                     "windows": nw, "null_per_h": round(float(np.mean([len(s) for s in nulls])) / hours, 4) if nulls else None}
                if ev:
                    found, extra = _match(spans, [x_["onset"] for x_ in ev])
                    e["deep_recall"] = round(float(np.mean([f for f, x_ in zip(found, ev) if x_["kind"] == "deep"])), 3)
                    e["weak_recall_by_quiet_h"] = {
                        str(qh): round(float(np.mean([f for f, x_ in zip(found, ev) if x_["quiet_h"] == qh])), 3)
                        for qh in QUIET_H if any(x_["quiet_h"] == qh for x_ in ev)}
                    e["weak_recall"] = round(float(np.mean([f for f, x_ in zip(found, ev) if x_["kind"] == "weak"])), 3)
                    e["extra_per_h"] = round(extra / hours, 4)
                    if nulls:
                        e["null_per_h"] = round(float(np.mean([len(s) for s in nulls])) / hours, 4)
                entry[name] = e
                print(f"[{det} · {entry['scale']} · {name}] {json.dumps(e)}", flush=True)
            rows.append(entry)
    return {"mode": "synthetic", "hours": args.hours, "scales_h": list(args.scales), "draws": args.draws,
            "weak_depth": args.weak, "deep_depth": 0.3,
            "events": {"deep": sum(1 for e in events if e["kind"] == "deep"),
                       "weak": {str(qh): sum(1 for e in events if e["quiet_h"] == qh) for qh in QUIET_H}},
            "rows": rows}


NT = [{"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean", "window_s": 600.0}},
      {"stage": "detection", "algorithm": "noise_threshold",
       "params": {"k_sigma": 4.0, "direction": "below", "min_duration_s": 30.0, "merge_gap_s": 60.0}}]


def dips_and_drops(hours=48, seed=21, sd=0.0001):
    """AR(1) noise with, every 30 minutes in turn, a 60-s dip and a drop that recovers over ~30 min, both 6 sigma deep."""
    rng = np.random.default_rng(seed)
    n = int(hours * H)
    x = _ar1(n, 0.97, sd, rng)
    level = sd / np.sqrt(1 - 0.97 ** 2)
    fast, slow = [], []
    for k, a in enumerate(range(900, n - 3600, 1800)):
        if k % 2 == 0:
            x[a:a + 60] -= 6 * level
            fast.append(a)
        else:
            d = np.concatenate([-6 * level * np.arange(20) / 20, -6 * level * np.exp(-np.arange(1800) / 300.0)])
            x[a:a + len(d)] += d
            slow.append(a)
    return x, {"60-s dips": fast, "30-min drops": slow}


def drops_loud_beside_quiet(hours=48, seed=3):
    """tests/test_windowed_detection.py's: hours 0-28 five times the noise and a deep drop (0.2) an hour; hours 28-48
    a weak drop (0.02) an hour."""
    rng = np.random.default_rng(seed)
    n = int(hours * H)
    x = _ar1(n, 0.97, 0.00005, rng)
    x[:28 * H] += _ar1(28 * H, 0.97, 0.00025, rng)
    deep = list(range(1 * H, 27 * H, H))
    for a in deep:
        d = np.concatenate([-0.2 * np.arange(20) / 20, -0.2 * np.exp(-np.arange(1800) / 300.0)])
        x[a:a + len(d)] += d
    weak = list(range(29 * H, 47 * H, H))
    for a in weak:
        d = np.concatenate([-0.02 * np.arange(20) / 20, -0.02 * np.exp(-np.arange(1800) / 300.0)])
        x[a:a + len(d)] += d
    return x, {"weak drops": weak, "deep drops": deep}


def short_scales(args):
    """The sweep's short scales against the bound (the 10-minute decision, RQ4b): whole span, 6 h, 1 h and 10 min,
    each fitted and as it is, no null. The stitch is the real one; 'as it is' bypasses the bound only by asking."""
    import Working.config as cfg
    from Working.database import queries as q
    from Working.database.schema import init_db

    tmp = tempfile.mkdtemp(prefix="p3_short_scales_")
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    db = os.path.join(tmp, "annotations.sqlite")
    init_db(db).close()
    recs = {"dips_and_drops": dips_and_drops(), "drops_loud_beside_quiet": drops_loud_beside_quiet(),
            "ar1": (noise("ar1", hours=48, seed=9), {})}
    ids = {}
    conn = init_db(db)
    try:
        for name, (sig, _) in recs.items():
            npy = os.path.join(tmp, f"{name}.npy")
            np.save(npy, sig)
            ids[name] = q.insert_recording(conn, f"{name}.mat", 0, 1.0, len(sig), 0, npy, units="V")
    finally:
        conn.close()
    chains = {"noise_threshold": NT, **CHAINS}
    plan_of = {"noise_threshold": ("dips_and_drops", "ar1")}
    rows = []
    for det in ["noise_threshold"] + list(args.detectors):
        for name in plan_of.get(det, ("drops_loud_beside_quiet", "ar1")):
            sig, events = recs[name]
            for label, scale_h, short in (("whole span", None, {}), ("6 h", 6, {}), ("1 h, fitted", 1, {"fit": True}),
                                          ("1 h, as it is", 1, {"allow_short": True}),
                                          ("10 min, fitted", 1 / 6.0, {"fit": True}),
                                          ("10 min, as it is", 1 / 6.0, {"allow_short": True})):
                SHORT.clear()
                SHORT.update(short)
                spans, _, el, nw, refused = _run(db, ids[name], chains[det], len(sig), scale_h, draws=0)
                row = {"detector": det, "recording": name, "scale": label}
                if refused:
                    row["refused"] = refused
                else:
                    row.update(per_h=round(len(spans) / (len(sig) / float(H)), 3), windows=nw, seconds=round(el, 1))
                    for kind, onsets in events.items():
                        row[kind] = round(float(np.mean(_match(spans, onsets, tol=600)[0])), 3)
                rows.append(row)
                print(json.dumps(row), flush=True)
    SHORT.clear()
    return {"mode": "short-scales", "rows": rows}


def measure_real(args):
    """The table on a sandbox copy's recordings against its human verdicts (`main` has refused the real database)."""
    from Working.database import queries as q
    from Working.database.schema import init_db

    rows = []
    for rid in [int(r) for r in args.recording_ids.split(",") if r.strip()]:
        conn = init_db(args.db)
        try:
            rec = q.get_recording_by_id(conn, rid)
            truth = [int(r[0]) for r in conn.execute(
                "SELECT start_idx FROM annotations WHERE recording_id = ? AND deleted_at IS NULL AND verdict IN "
                "('interesting', 'seed')", (rid,))]
        finally:
            conn.close()
        n, fs = int(rec["n_samples"]), float(rec["fs"])
        for det in args.detectors:
            for scale in (None,) + tuple(args.scales):
                spans, nulls, el, nw, refused = _run(args.db, rid, CHAINS[det], n, scale, draws=args.draws)
                entry = {"recording": rid, "file": rec["source_file"], "channel": int(rec["channel"]), "detector": det,
                         "scale": "whole" if scale is None else f"{scale} h"}
                if refused:
                    entry["refused"] = refused
                else:
                    found, extra = _match(spans, truth, tol=int(600 * fs))
                    hours = n / fs / H
                    entry.update(detections=len(spans), per_h=round(len(spans) / hours, 4), seconds=round(el, 1),
                                 windows=nw, human=len(truth), human_recall=(round(float(np.mean(found)), 3) if truth else None),
                                 null_per_h=(round(float(np.mean([len(s) for s in nulls])) / hours, 4) if nulls else None))
                rows.append(entry)
                print(json.dumps(entry), flush=True)
    return {"mode": "real", "db": args.db, "rows": rows}


def main(argv=None, real=None):
    """``real``: the real database's path (the main checkout's by default); a test hands in a stand-in."""
    real = real or REAL_DB
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--detectors", default=",".join(CHAINS), help="comma-separated, of " + ", ".join(CHAINS))
    ap.add_argument("--scales", default=",".join(str(s) for s in SCALES_H), help="window lengths in hours")
    ap.add_argument("--hours", type=float, default=336.0, help="synthetic recordings' length")
    ap.add_argument("--draws", type=int, default=1, help="null draws per window")
    ap.add_argument("--weak", type=float, default=0.02,
                    help="the quiet stretches' drop depth (the deep ones are 0.3): 0.02 is under the drop detector's "
                         "10 %% depth gate against a deep drop in the same span, 0.04 above it")
    ap.add_argument("--db", help="a SANDBOX copy of the database: measure on its recordings against human verdicts")
    ap.add_argument("--recording-ids", default="", help="with --db: the channels to measure")
    ap.add_argument("--fit", action="store_true", help="fit the chain to windows shorter than its bound")
    ap.add_argument("--allow-short", action="store_true",
                    help="run the chain as it is in windows shorter than its bound (warned)")
    ap.add_argument("--short-scales", action="store_true",
                    help="the sweep's 1-hour and 10-minute scales, fitted and as they are, on 48-h synthetic recordings")
    ap.add_argument("--out", help="write the result as JSON here")
    args = ap.parse_args(argv)
    if args.db and is_the_real_database(args.db, real):
        ap.error(f"{args.db} is the real database ({real}); measure on a sandbox copy "
                 f"(webui/runtime/<stamp>/annotations.sqlite)")
    if args.fit:
        SHORT["fit"] = True
    elif args.allow_short:
        SHORT["allow_short"] = True
    args.detectors = [d.strip() for d in args.detectors.split(",") if d.strip()]
    args.scales = tuple(float(s) for s in args.scales.split(",") if s.strip())
    out = measure_real(args) if args.db else short_scales(args) if args.short_scales else synthetic(args)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
