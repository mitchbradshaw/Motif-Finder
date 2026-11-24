"""
run_pool.py
===========
The drop auto-detect over every dataset and channel (the researcher, 2026-11-24: "apply the developed auto-detect
algorithm across all available datasets + channels ... Ignore rises for now, focus on finding drop events. Goal is
minimum of 100,000 new, unseen and unjudged candidates ... up to 1M surviving candidates across the datasets ... feed
them into the plotting structures of the NeurIPS agent").

In plain words
--------------
Each physical channel is searched once, by the line-up the review queue of 24 Nov came from (v4: the four detector
templates over the whole channel, drop v1 and v5 also in 6-hour windows, BEADS -> 10 sigma, the tight seed families,
the researcher's event rule as a finder, R4 on every box, the committed whole-drop rule). Two things differ:

* only the NORMAL pass runs - the one that finds drops (and keeps the sharp rises it meets, which the filters need to
  tell a drop from a spike's way back down). The pass on the inverted signal, which exists to find rises, is left
  out: the researcher said to ignore rises for now, and it is ~45 % of a channel's time;
* R4's window scan is left out. Its own candidates are R4 alone, which the queue's rules never keep ("no detector,
  seed or rule vouched for it"), and it never reinforces another candidate (`blend.R4_SCAN`); it is 10-20 % of the time.

Copies of a channel are searched once (`docs/autodetect/CHANNEL_COPIES.md`; M100 is M1 with its drift taken out and
M101_t is M100 shifted by 9,956 samples - checked 24 Nov, sample-to-sample changes r 0.99 and 1.0000). Channels
recorded at 10 Hz are searched at 2 Hz, as the 2 Hz copies of the others are made: block means of five samples.

Read-only on the database (`mode=ro`). Writes only DATA/derived/autodetect/pool_20261124/ (gitignored, beside the
app's own Auto-detect results): one folder per recording, `raw/<recording id>/`, holding candidates.parquet,
sequences.parquet and run.json. Several workers may run at once: each claims the next recording not done
(`claims/`), so a run that stops is picked up again where it was.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/run_pool.py detect [--only ID ...]
    ... run_pool.py status
"""
from __future__ import annotations

import argparse
import builtins
import datetime as dt
import hashlib
import io
import json
import os
import sys
import tempfile
import time
import warnings

os.environ.setdefault("NUMBA_NUM_THREADS", "4")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import common as K  # noqa: E402

ROOT = K.ROOT
os.chdir(ROOT)                     # the core's paths (R4's model, the channel files) are relative to the repository
POOL = os.path.join(ROOT, "DATA", "derived", "autodetect", "pool_20261124")
RAW = os.path.join(POOL, "raw")
CLAIMS = os.path.join(POOL, "claims")
#: The rate every channel is searched at: the design's "one channel at <= 2 Hz".
RUN_FS = 2.0

#: The physical channels, once each, in the order they are searched (the datasets with reviewed events first, then
#: the ones never reviewed, the largest last). `dataset` and `species` are the names the NeurIPS plots use
#: (`scripts/thesis/figstyle.py`); a dataset it does not know is "unknown".
TARGETS = [
    {"file": "M4_aug_concat_fs1.mat", "dataset": "M4", "species": "oyster"},
    {"file": "M2_aug_concat_fs1.mat", "dataset": "M2_aug", "species": "oyster"},
    {"file": "MJu26a_fs2.mat", "dataset": "MJu26a", "species": "lion's mane"},
    {"file": "CO_fs2.mat", "dataset": "CO", "species": "chocolate oyster"},
    {"file": "LM_fs2.mat", "dataset": "LM", "species": "lion's mane"},
    {"file": "SH_fs2.mat", "dataset": "SH", "species": "Asian shiitake"},
    {"file": "SO_fs2.mat", "dataset": "SO", "species": "snow oyster"},
    {"file": "M2_concat_fs1.mat", "dataset": "M2_concat", "species": "oyster"},
    {"file": "Schizophyllum commune.txt", "dataset": "S_commune", "species": "split gill"},
    {"file": "Cordyceps militari.txt", "dataset": "Cordyceps", "species": "Cordyceps"},
    {"file": "Enoki fungi Flammulina velutipes.txt", "dataset": "Enoki", "species": "enoki"},
    {"file": "record-mfs2-2026-09-01-15-22-51.csv", "dataset": "Dwij_B", "species": "unknown"},
    {"file": "record-mfs2-2026-09-02-08-49-40.csv", "dataset": "Dwij_C", "species": "unknown"},
    {"file": "record-mfs2-2026-09-08-09-49-38.csv", "dataset": "Dwij_D", "species": "unknown"},
    {"file": "F2B.mat", "dataset": "F2B", "species": "unknown"},
    {"file": "L_R_Aug_26_PD_raw.mat", "dataset": "L_R_Aug_26_PD", "species": "unknown"},
    {"file": "M1.mat", "dataset": "M1", "species": "unknown"},
]
#: Left out, and why (recorded in every run.json so the choice travels with the results).
SKIPPED = {
    "MJu26a.mat": "the uneven 7.246 Hz original of MJu26a_fs2 (same data)",
    "MJu26a_fs10.mat": "MJu26a at 10 Hz; MJu26a_fs2 is its 2 Hz block means (same data)",
    "L_LM_Jul_26_J_raw.mat": "MJu26a CH10, 13-16 x1000 plus an offset (same data)",
    "L_LM_Jul_26_J_raw_fs2.mat": "its 2 Hz block means (same data)",
    "Mushroom_260720_0509_4hrs_CH14_fs1.mat": "a 4-hour excerpt of MJu26a CH14 (same data)",
    "SH.mat": "SH at 10 Hz; SH_fs2 is its 2 Hz copy, where the verdicts are",
    "SO.mat": "SO at 10 Hz; SO_fs2 is its 2 Hz copy, where the verdicts are",
    "M2_aug_concat_fs2.mat": "a 2 Hz copy of M2_aug_concat_fs1 whose joins do not line up; the 1 Hz file is the one "
                             "reviewed and the reference",
    "M100.mat": "M1 with its slow drift taken out (sample-to-sample changes r 0.986-0.990, 24 Nov)",
    "M101_t.mat": "M100 shifted by 9,956 samples (r 1.0000, 24 Nov)",
    "Fig2A_dt0p1.csv": "a 20-minute figure trace",
    "record-mfs2-2026-09-01-14-31-11.csv": "16 minutes long",
}


# ── the write guard: nothing under DATA/ but this run's own folder ───────────

_DATA = os.path.normcase(os.path.join(ROOT, "DATA")) + os.sep
_MINE = os.path.normcase(POOL) + os.sep
_real_open = builtins.open


def _guarded_open(file, mode="r", *args, **kwargs):
    if isinstance(file, (str, bytes, os.PathLike)) and any(c in str(mode) for c in "wax+"):
        path = os.path.normcase(os.path.abspath(os.fsdecode(file)))
        if path.startswith(_DATA) and not path.startswith(_MINE):
            raise PermissionError(f"run_pool: refusing to write under DATA/ outside {POOL}: {path}")
    return _real_open(file, mode, *args, **kwargs)


def install_write_guard():
    builtins.open = _guarded_open
    io.open = _guarded_open


# ── the targets ──────────────────────────────────────────────────────────────

def targets(conn):
    """Every recording to search, in order: ``[(rec, target), ...]``."""
    out = []
    for t in TARGETS:
        recs = [dict(r) for r in conn.execute("SELECT * FROM recordings WHERE source_file = ? ORDER BY channel",
                                              (t["file"],))]
        if not recs:
            raise RuntimeError(f"{t['file']} is not in this database")
        out += [(r, t) for r in recs]
    return out


def _fingerprint(path):
    with open(os.path.join(ROOT, path), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:12]


RULE_FILES = ("Working/autodetect/anchor.py", "Working/autodetect/pipeline.py", "Working/autodetect/gates.py",
              "Working/autodetect/finder.py", "Working/autodetect/candidates.py", "Working/autodetect/blend.py",
              "Working/autodetect/seeds.py", "Working/autodetect/r4.py", "Working/autodetect/sequences.py")


def load_signal(rec):
    """``(x, fs, decimation)``: the channel in its stored unit at <= `RUN_FS`, block means of ``decimation`` samples
    when it was recorded faster (sample ``i`` stands for stored samples ``[i*d, (i+1)*d)``)."""
    raw = np.load(os.path.join(ROOT, rec["npy_path"]), mmap_mode="r")
    fs0 = float(rec["fs"])
    if fs0 <= RUN_FS * 1.01:
        return np.asarray(raw, dtype=np.float64), fs0, 1
    d = int(round(fs0 / RUN_FS))
    if abs(fs0 / d - RUN_FS) > 1e-6:
        raise RuntimeError(f"recording {rec['id']}: {fs0} Hz is not a whole multiple of {RUN_FS} Hz")
    n2 = len(raw) // d
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)     # an all-gap block is a gap
        x = np.nanmean(np.asarray(raw[:n2 * d], dtype=np.float64).reshape(n2, d), axis=1)
    return x, fs0 / d, d


# ── one worker ───────────────────────────────────────────────────────────────

class Context:
    def __init__(self, conn):
        from Working.autodetect import r4, service as S
        from Working.discovery.matching import rule_from_settings
        self.specs, self.missing = S.detector_specs(conn)
        self.fams, self.bank = S.load_seed_bank()
        self.model = r4.load_model(r4.MODEL)
        self.rule = rule_from_settings(conn)


def _claim(rid):
    os.makedirs(CLAIMS, exist_ok=True)
    path = os.path.join(CLAIMS, f"{rid}.claim")
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            with open(path, encoding="utf-8") as fh:
                pid = int(json.load(fh)["pid"])
        except Exception:  # noqa: BLE001 - a claim being written; leave it
            return False
        import psutil
        if psutil.pid_exists(pid):
            return False
        os.remove(path)                       # its worker died: take it over
        return _claim(rid)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"pid": os.getpid(), "at": dt.datetime.now().isoformat(timespec="seconds")}, fh)
    return True


def done(rid):
    return os.path.isfile(os.path.join(RAW, str(rid), "run.json"))


def _save_frame(df, path):
    try:
        df.to_parquet(path, index=False)
    except Exception:  # noqa: BLE001 - a mixed-type column: keep it as text rather than lose it
        df.astype({c: str for c in df.columns if df[c].dtype == object}).to_parquet(path, index=False)


def detect_one(conn, ctx, rec, target, *, log):
    import psutil
    from Working.autodetect import gates, r4
    from Working.autodetect import service as S
    from Working.autodetect.pipeline import auto_detect
    from Working.autodetect.seeds import MIN_FAMILY_LINE
    from Working.units import read_as_mv

    rid = int(rec["id"])
    t0 = time.perf_counter()
    # the working set, sampled every 0.25 s: the peak of each stage goes into run.json (memory is this machine's limit)
    import threading
    proc = psutil.Process()
    stage = {"name": "load", "peaks": {}, "stop": False}

    def watch():
        while not stage["stop"]:
            rss = proc.memory_info().rss / 1e9
            stage["peaks"][stage["name"]] = max(stage["peaks"].get(stage["name"], 0.0), rss)
            time.sleep(0.25)

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()

    def progress(m):
        stage["name"] = m.split(" (")[0].split(" in ")[0]
        log(f"  [{time.perf_counter() - t0:7.1f} s] rec {rid}: {m}")

    x, fs, dec = load_signal(rec)
    factor, unit_note = read_as_mv(rec["units"])
    x_mv = x * factor
    floor, floor_src = S.noise_floor_mv(conn, rec["source_file"])
    parts = stretches(len(x), fs)
    log(f"rec {rid} {rec['source_file']} CH{rec['channel']}: {len(x):,} samples at {fs:g} Hz"
        f"{f' (block means of {dec})' if dec > 1 else ''}, {len(x) / fs / 3600:.0f} h, floor {floor} mV, "
        f"{len(parts)} stretch{'es' if len(parts) > 1 else ''}")
    frames, seq_frames, per_stretch, n_props = [], [], [], 0
    for k, (a, b, keep_from, keep_to) in enumerate(parts):
        res = auto_detect(x[a:b], fs, units=rec["units"], detectors=ctx.specs, seed_families=ctx.fams,
                          # R4 reads context past the stretch's ends, as the app's runs of a stretch do
                          score_spans=r4.Scorer(ctx.model, x_mv, fs, offset=a), floor_mv=floor, start_idx=a,
                          rule=ctx.rule, seed_min_family_line=MIN_FAMILY_LINE,
                          min_sharpness={"spike": gates.MIN_RISE_SHARPNESS}, drop_rule="drop", use_finder=True,
                          scan_durations_s=(), on_progress=progress)
        c = res.candidates.copy()
        if len(c):
            # one frame for the whole channel: every index column in channel samples (start == start_idx)
            for col in ("start", "end", "orig_start", "orig_end", "onset", "extremum", "event_end"):
                if col in c:
                    c[col] = pd.to_numeric(c[col], errors="coerce") + a
            mid = (c["start_idx"].to_numpy(np.int64) + c["end_idx"].to_numpy(np.int64)) // 2
            c = c[(mid >= keep_from) & (mid < keep_to)]       # a candidate belongs to the stretch it is central in
            c["stretch"] = k
        frames.append(c)
        if len(res.sequences):
            seq_frames.append(res.sequences.assign(stretch=k))
        n_props += int(len(res.proposals))
        per_stretch.append({"stretch": k, "start_idx": a, "end_idx": b, "keep_from": keep_from, "keep_to": keep_to,
                            "timings": res.timings, "info": res.info})
    wall = time.perf_counter() - t0
    stage["stop"] = True
    cands = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if len(cands):
        cands = cands.sort_values(["start_idx", "end_idx"]).reset_index(drop=True)
        cands["candidate_id"] = np.arange(len(cands), dtype=np.int64)
    cands.insert(0, "recording_id", rid)
    cands["decimation"] = dec
    cands["fs_run"] = fs
    out = os.path.join(RAW, str(rid))
    os.makedirs(out, exist_ok=True)
    _save_frame(cands, os.path.join(out, "candidates.parquet"))
    _save_frame(pd.concat(seq_frames, ignore_index=True) if seq_frames else pd.DataFrame(),
                os.path.join(out, "sequences.parquet"))
    res.timings = {f"stretch{p['stretch']}:{k}": v for p in per_stretch for k, v in p["timings"].items()}
    res.info = {"stretches": per_stretch}
    pol = cands["polarity"].astype(str) if len(cands) else pd.Series(dtype=str)
    conf = cands["confidence"].astype(float) if len(cands) else pd.Series(dtype=float)
    meta = {"recording": {k: rec[k] for k in ("id", "source_file", "channel", "fs", "n_samples", "units",
                                              "npy_path")},
            "target": target, "run_fs": fs, "decimation": dec, "n_samples_run": int(len(x)),
            "hours": len(x) / fs / 3600.0, "floor_mv": floor, "floor_source": floor_src, "unit_note": unit_note,
            "line_up": {"version": "v4, normal pass only, no R4 window scan", "detectors": [s["variant"] for s in
                                                                                             ctx.specs],
                        "missing_detectors": ctx.missing, "seed_families": len(ctx.fams),
                        "seed_min_family_line": MIN_FAMILY_LINE, "rise_sharpness": gates.MIN_RISE_SHARPNESS},
            "whole_drop": WHOLE_DROP_PIN, "rule_files": {p: _fingerprint(p) for p in RULE_FILES},
            "skipped_files": SKIPPED, "wall_s": wall, "timings": res.timings, "info": res.info,
            "counts": {"candidates": int(len(cands)), "drops": int((pol == "drop").sum()),
                       "rises": int((pol == "spike").sum()), "drops_conf_0.6": int(((pol == "drop") & (conf >= 0.6)).sum()),
                       "proposals": n_props},
            "stretches": [{k: p[k] for k in ("stretch", "start_idx", "end_idx", "keep_from", "keep_to")}
                          for p in per_stretch],
            "peak_rss_gb": max(stage["peaks"].values()) if stage["peaks"] else None,
            "peak_rss_gb_by_stage": {k: round(v, 3) for k, v in stage["peaks"].items()},
            "process_peak_wset_gb": getattr(proc.memory_info(), "peak_wset", 0) / 1e9,
            "finished_at": dt.datetime.now().isoformat(timespec="seconds"), "pid": os.getpid()}
    tmp = os.path.join(out, "run.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    os.replace(tmp, os.path.join(out, "run.json"))
    log(f"rec {rid} done in {wall:.0f} s ({wall / max(len(x), 1) * 1e6:.0f} us/sample): "
        f"{meta['counts']['drops']:,} drops ({meta['counts']['drops_conf_0.6']:,} at >= 0.6), "
        f"{meta['counts']['rises']:,} sharp rises; peak {meta['peak_rss_gb']:.2f} GB "
        f"({max(stage['peaks'], key=stage['peaks'].get) if stage['peaks'] else '?'})"
        + "".join(f"; ERRORS in stretch {p['stretch']}: {list(p['info']['errors'])}" for p in per_stretch
                  if p["info"].get("errors")))
    return meta


#: The longest stretch searched in one go: the reference runs' (264 h at 2 Hz, 528 h at 1 Hz; 1.85 GB at the peak on
#: this machine). A longer channel is searched in stretches that share `OVERLAP_S`; a candidate is kept from the
#: stretch it is central in, so none is counted twice.
MAX_STRETCH = int(os.environ.get("POOL_MAX_STRETCH", 1_900_800))   # a second worker runs smaller, for memory
OVERLAP_S = 7200.0


def stretches(n, fs):
    """``[(a, b, keep_from, keep_to), ...]``: stretches of at most `MAX_STRETCH` samples covering ``[0, n)``, each
    sharing `OVERLAP_S` with the next, and the part of each whose candidates it keeps."""
    if n <= MAX_STRETCH:
        return [(0, n, 0, n)]
    ov = int(round(OVERLAP_S * fs))
    k = int(np.ceil((n - ov) / (MAX_STRETCH - ov)))
    size = int(np.ceil((n + (k - 1) * ov) / k))
    out, a = [], 0
    for i in range(k):
        b = n if i == k - 1 else min(n, a + size)
        out.append((a, b, 0 if i == 0 else a + ov // 2, n if i == k - 1 else b - ov // 2))
        a = b - ov
    return out


def cmd_detect(args):
    install_write_guard()
    K.redirect_adapter_outputs(tempfile.mkdtemp(prefix="autodetect_pool_"))
    conn = K.connect()
    todo = targets(conn)
    if args.only:
        want = {int(i) for i in args.only}
        todo = [(r, t) for r, t in todo if int(r["id"]) in want]
    if args.reverse:                      # a second worker starts from the other end of the list
        todo = todo[::-1]
    os.makedirs(RAW, exist_ok=True)
    logf = open(os.path.join(POOL, f"worker_{os.getpid()}.log"), "a", encoding="utf-8")

    def log(msg):
        line = f"{dt.datetime.now():%H:%M:%S} {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    ctx = Context(conn)
    log(f"worker {os.getpid()}: {len(todo)} recordings in the list; detectors {[s['variant'] for s in ctx.specs]}; "
        f"{len(ctx.fams)} seed families; whole drop {WHOLE_DROP_PIN}")
    n_done = 0
    for rec, target in todo:
        rid = int(rec["id"])
        if done(rid) or not _claim(rid):
            continue
        try:
            detect_one(conn, ctx, rec, target, log=log)
            n_done += 1
        except Exception as exc:  # noqa: BLE001 - logged loud with its traceback; the claim stays for a look
            import traceback
            log(f"rec {rid} FAILED: {type(exc).__name__}: {exc}\n{traceback.format_exc()}")
            with open(os.path.join(CLAIMS, f"{rid}.failed"), "w", encoding="utf-8") as fh:
                fh.write(traceback.format_exc())
        if args.max and n_done >= args.max:
            break
    log(f"worker {os.getpid()}: finished, {n_done} recordings searched")


def cmd_status(args):
    conn = K.connect()
    todo = targets(conn)
    rows = []
    for rec, t in todo:
        rid = int(rec["id"])
        p = os.path.join(RAW, str(rid), "run.json")
        st = "done" if os.path.isfile(p) else ("failed" if os.path.isfile(os.path.join(CLAIMS, f"{rid}.failed"))
                                              else ("running" if os.path.isfile(os.path.join(CLAIMS, f"{rid}.claim"))
                                                    else "waiting"))
        m = json.load(open(p, encoding="utf-8")) if st == "done" else {}
        n_run = int(rec["n_samples"]) // max(1, int(round(float(rec["fs"]) / RUN_FS)) if float(rec["fs"]) > RUN_FS * 1.01 else 1)
        rows.append({"id": rid, "file": rec["source_file"], "ch": rec["channel"], "state": st, "n_run": n_run,
                     "wall_s": m.get("wall_s"), "drops": m.get("counts", {}).get("drops"),
                     "drops_06": m.get("counts", {}).get("drops_conf_0.6"), "peak_gb": m.get("peak_rss_gb")})
    df = pd.DataFrame(rows)
    d = df[df["state"] == "done"]
    rate = (d["wall_s"].sum() / d["n_run"].sum()) if len(d) else 1.5e-4
    left = df.loc[df["state"] != "done", "n_run"].sum() * rate
    print(df.groupby(["file", "state"]).size().unstack(fill_value=0).to_string())
    print(f"\n{len(d)}/{len(df)} done; drops {int(d['drops'].sum()):,} ({int(d['drops_06'].sum()):,} at >= 0.6); "
          f"{rate * 1e6:.0f} us/sample; ~{left / 3600:.1f} h of one worker left; peak {d['peak_gb'].max() if len(d) else 0:.2f} GB")


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detect")
    d.add_argument("--only", nargs="*", help="recording ids (default: every target)")
    d.add_argument("--max", type=int, default=0, help="stop after this many recordings (0: no limit)")
    d.add_argument("--reverse", action="store_true", help="take the list from its end (a second worker)")
    sub.add_parser("status")
    args = ap.parse_args(argv)
    {"detect": cmd_detect, "status": cmd_status}[args.cmd](args)


# the whole-drop rule as committed (the researcher, 2026-11-23: "use latest committed whole drop rule"), pinned before
# anything imports Working.autodetect
WHOLE_DROP_PIN = K.pin_whole_drop(os.environ.get("AUTODETECT_WHOLE_DROP_REV", "HEAD"))

if __name__ == "__main__":
    main()
