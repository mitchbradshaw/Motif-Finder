"""
newsets_fs2.py — the 2 Hz copies of MJu26a_fs10, SH and SO, the L_LM <-> MJu26a check, and their rangpur sweep
bundle (the researcher, 2026-10-26: "for 10 Hz datasets a resampled 2 Hz version is preferred").

Subcommands, one Python process at a time (the PC is short of memory):

    PY="/c/ProgramData/anaconda3/python.exe"
    "$PY" scripts/thesis/newsets_fs2.py derive [--only MJu26a_fs2 SH_fs2 SO_fs2] [--dry-run] [--force]
    "$PY" scripts/thesis/newsets_fs2.py llm-map            # read-only: L_LM_Jul_26_J_raw vs MJu26a_fs10
    "$PY" scripts/thesis/newsets_fs2.py bundle --db-source DATA/db/backups/<stamp>.sqlite [--date 20261027]

derive
------
The method of `scripts/derive_fs2.py` (CO_fs2, LM_fs2, L_LM_Jul_26_J_raw_fs2): non-overlapping block means of 5
consecutive 10 Hz samples (`Working/registration/excerpt.py::block_mean`), the trailing partial block dropped and
counted, nothing else altered (no anti-alias filter beyond the block mean, no detrending, no rescaling), float64,
one `CH<i>.npy` per channel plus a `manifest.json` in derive_fs2's format. The source is the already-registered
10 Hz channel files (as derive_fs2 did for L_LM), read memory-mapped one channel at a time in chunks, each 2 Hz
channel written before the next is read: a whole 16-channel 10 Hz recording is never in memory.

- SH, SO: `DATA/derived/channels/{SH,SO}_fs10/` are SH.mat / SO.mat as stored. Their 10 Hz was inferred from the
  sample count; here the files' own MATLAB `duration` vector (the MCOS function-workspace blob, as derive_fs2
  decodes it for LM/CO) is read STREAMING and every step checked, so the rate is read, not inferred, when every
  step is 100 ms.
- MJu26a: `MJu26a_fs10/` is MJu26a.mat linearly interpolated onto a uniform 10 Hz grid
  (`scripts/derive_mju26a_fs10.py`); its 2 Hz copy is the block mean of that grid.

NaN handling: as derive_fs2 (a block containing a NaN gives NaN); the count of non-finite samples is checked and
written in the manifest (none in these three).

bundle
------
`scripts/thesis/scommune_bundle.py`'s build: batch 3's `rq4_overnight.py build-batch` (the V variant set, as LM_fs2
and CO_fs2 got) over the three new recordings, on a SANDBOX copy of the real database in the session scratchpad
(`webui.server.runtime.Runtime(mode="sandbox")`: step cache, RESULTS_DIRs, MODEL_ROOT and the cost calibrations
redirected there), deleted afterwards. Output: `docs/thesis/hpc/rq4_newsets_<date>/`.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import json
import os
import shutil
import struct
import sys
import zlib

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
CHANNELS = os.path.join(ROOT, "DATA", "derived", "channels")
FACTOR = 5
FS_IN = 10.0
TODAY = "2026-10-27"
SCRATCH = os.environ.get(
    "NEWSETS_SANDBOX",
    r"C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN\ee7dfe78-0c27-48d6-91e6-dd2ef2948732"
    r"\scratchpad\newsets_sandbox")

SETS = {
    "MJu26a_fs2": {"from_npy": "MJu26a_fs10", "source_file": "MJu26a_fs2.mat", "parent_source_file": "MJu26a_fs10.mat",
                   "raw": "MJu26a.mat", "duration_vector": False},
    "SH_fs2": {"from_npy": "SH_fs10", "source_file": "SH_fs2.mat", "parent_source_file": "SH.mat", "raw": "SH.mat",
               "duration_vector": True},
    "SO_fs2": {"from_npy": "SO_fs10", "source_file": "SO_fs2.mat", "parent_source_file": "SO.mat", "raw": "SO.mat",
               "duration_vector": True},
}
BUNDLE_SOURCES = ["MJu26a_fs2.mat", "SH_fs2.mat", "SO_fs2.mat"]
PREFIX = "rq4n"


# ------------------------------------------------------------------------------------------------ derive --

def block_mean_file(src, dst, *, factor=FACTOR, chunk=5_000_000):
    """Block means of ``factor`` consecutive samples of the 1-D ``src`` .npy into the float64 ``dst`` .npy, read
    memory-mapped ``chunk`` samples at a time. Identical to `excerpt.block_mean` on the whole channel (each block's
    mean is computed alone either way)."""
    x = np.load(src, mmap_mode="r")
    n = int(x.shape[0])
    m = n // factor * factor
    chunk = max(factor, chunk // factor * factor)
    out = np.lib.format.open_memmap(dst, mode="w+", dtype=np.float64, shape=(m // factor,))
    bad = 0
    lo, hi = np.inf, -np.inf
    try:
        for a in range(0, m, chunk):
            b = min(a + chunk, m)
            blk = np.asarray(x[a:b], dtype=np.float64)
            bad += int(blk.size - np.count_nonzero(np.isfinite(blk)))
            y = blk.reshape(-1, factor).mean(axis=1)
            out[a // factor:b // factor] = y
            if y.size:
                lo, hi = min(lo, float(np.nanmin(y))), max(hi, float(np.nanmax(y)))
        out.flush()
    finally:
        del out
        del x
    return {"source_samples": n, "samples": m // factor, "trailing_samples_dropped": n - m, "non_finite": bad,
            "min": lo, "max": hi}


def _last_element(f):
    f.seek(128)
    last = None
    while True:
        tag = f.read(8)
        if len(tag) < 8:
            break
        _t, size = struct.unpack("<II", tag)
        last = (size, f.tell())
        f.seek(f.tell() + size)
    return last


def duration_steps(path, n, *, step_ms=100.0, in_chunk=4 << 20, out_chunk=16 << 20):
    """Read the MATLAB `duration` vector of a v5 .mat (n float64 milliseconds in the MCOS function-workspace blob,
    the file's last element) STREAMING, and check every step. The vector's start is found as
    `scripts/derive_fs2.py::_timestamps` finds it (the first 8-byte-aligned run that starts at 0..1e12 ms, steps
    ``step_ms`` and keeps increasing); the vector itself is never held in memory."""
    st = {"found": False, "checked": 0, "bad_steps": 0, "first_bad": None, "t0_ms": None, "t_end_ms": None,
          "min_step_ms": None, "max_step_ms": None}
    prev = None

    def _validate(v):
        nonlocal prev
        need = n - st["checked"]
        v = v[:need]
        if not len(v):
            return
        if prev is None:
            steps, base = np.diff(v), st["checked"]
        else:
            steps, base = np.diff(np.concatenate([[prev], v])), st["checked"] - 1
        if len(steps):
            bad = np.abs(steps - step_ms) > 1e-6
            nb = int(np.count_nonzero(bad))
            if nb and st["first_bad"] is None:
                st["first_bad"] = int(base + int(np.argmax(bad)))
            st["bad_steps"] += nb
            smin, smax = float(steps.min()), float(steps.max())
            st["min_step_ms"] = smin if st["min_step_ms"] is None else min(st["min_step_ms"], smin)
            st["max_step_ms"] = smax if st["max_step_ms"] is None else max(st["max_step_ms"], smax)
        st["checked"] += len(v)
        prev = float(v[-1])

    carry = b""

    def _feed(piece):
        nonlocal carry
        buf = carry + piece
        usable = len(buf) // 8 * 8
        arr = np.frombuffer(buf, dtype="<f8", count=usable // 8)
        if not st["found"]:
            if len(arr) < 3:
                carry = buf
                return
            a0, a1, a2 = arr[:-2], arr[1:-1], arr[2:]
            with np.errstate(invalid="ignore", over="ignore"):
                ok = (np.isfinite(a0) & np.isfinite(a1) & np.isfinite(a2) & (a0 >= 0) & (a0 < 1e12)
                      & (np.abs((a1 - a0) - step_ms) < 1e-6) & (a2 > a1))
            if not ok.any():
                carry = buf[usable - 16:]
                return
            k = int(np.argmax(ok))
            st["found"], st["t0_ms"] = True, float(arr[k])
            _validate(arr[k:])
        else:
            _validate(arr)
        carry = buf[usable:]

    with open(path, "rb") as f:
        size, start = _last_element(f)
        f.seek(start)
        d = zlib.decompressobj()
        left = size
        while left > 0 and st["checked"] < n:
            data = f.read(min(in_chunk, left))
            if not data:
                break
            left -= len(data)
            out = d.decompress(data, out_chunk)
            _feed(out)
            while d.unconsumed_tail and st["checked"] < n:
                _feed(d.decompress(d.unconsumed_tail, out_chunk))
        if st["checked"] < n:
            _feed(d.flush())
    st["t_end_ms"] = prev
    return st


def _src_manifest(stem):
    with open(os.path.join(CHANNELS, SETS[stem]["from_npy"], "manifest.json"), encoding="utf-8") as fh:
        return json.load(fh)


def derive(stem, *, dry=False, force=False):
    cfg = SETS[stem]
    final = os.path.join(CHANNELS, stem)
    if os.path.isfile(os.path.join(final, "manifest.json")) and not force:
        print(f"[{stem}] exists, skipped (--force to redo)")
        return
    src_dir = os.path.join(CHANNELS, cfg["from_npy"])
    sm = _src_manifest(stem)
    n_src = int(sm["n_samples_per_channel"])
    if float(sm["fs"]) != FS_IN:
        raise SystemExit(f"[{stem}] {cfg['from_npy']} is {sm['fs']} Hz, not 10 Hz")
    chans = sorted(int(f[2:-4]) for f in os.listdir(src_dir) if f.startswith("CH") and f.endswith(".npy"))
    if chans != list(range(int(sm["n_channels"]))):
        raise SystemExit(f"[{stem}] {cfg['from_npy']}: channel files {chans} do not match n_channels {sm['n_channels']}")
    raw = os.path.join(ROOT, "DATA", "raw", cfg["raw"])
    dv = None
    if cfg["duration_vector"]:
        dv = duration_steps(raw, n_src)
        print(f"[{stem}] {cfg['raw']} duration vector: {dv}")
        if not dv["found"] or dv["checked"] != n_src:
            raise SystemExit(f"[{stem}] no {n_src:,}-sample duration vector found in {cfg['raw']}")
    m = n_src // FACTOR
    print(f"[{stem}] {cfg['from_npy']}: {len(chans)} ch x {n_src:,} at 10 Hz -> {m:,} at 2 Hz ({m / 2 / 3600:.1f} h), "
          f"{n_src - m * FACTOR} trailing sample(s) dropped")
    if dry:
        return
    staging = os.path.join(CHANNELS, f".staging_{stem}_{os.getpid()}")
    if os.path.isdir(staging):
        shutil.rmtree(staging)
    os.makedirs(staging)
    per = []
    for j in chans:
        info = block_mean_file(os.path.join(src_dir, f"CH{j}.npy"), os.path.join(staging, f"CH{j}.npy"))
        if info["source_samples"] != n_src:
            raise SystemExit(f"[{stem}] CH{j}: {info['source_samples']:,} samples, manifest says {n_src:,}")
        per.append(info)
        print(f"[{stem}] CH{j}: {info['samples']:,} samples, range {info['min']:.4g}..{info['max']:.4g}, "
              f"non-finite in source {info['non_finite']}", flush=True)
    nonfinite = sum(p["non_finite"] for p in per)
    if dv is not None:
        t0_ms = dv["t0_ms"]
        uniform = dv["bad_steps"] == 0
        fs_note = (f"2 Hz: block means of 5 consecutive samples of the source ({cfg['from_npy']}, {cfg['raw']} as "
                   f"stored), whose own per-sample time vector (the MATLAB duration object in {cfg['raw']}, read "
                   f"streaming by scripts/thesis/newsets_fs2.py) steps exactly 100 ms throughout (10 Hz, every one "
                   f"of {n_src - 1:,} steps checked). Sample i is centred at source time t0 + (5i + 2) x 100 ms, "
                   f"t0 = {t0_ms:.0f} ms.") if uniform else (
                   f"2 Hz from block means of 5; the source's 10 Hz is inferred: {dv['bad_steps']} of its duration "
                   f"vector's steps are not 100 ms (first after sample {dv['first_bad']})")
        time_base = f"uniform 2 Hz: source t0 {t0_ms:.0f} ms + (5i + 2) x 100 ms"
        src_time = {"source_t0_ms": t0_ms, "source_t_end_ms": dv["t_end_ms"], "source_step_ms": 100.0,
                    "steps_checked": n_src - 1, "steps_not_100ms": dv["bad_steps"]}
    else:
        t0_s = float(sm["time_base"].split("t[0] = ")[1].split()[0])
        fs_note = (f"2 Hz: block means of 5 consecutive samples of the source {cfg['from_npy']}, itself MJu26a.mat's "
                   f"uneven rows linearly interpolated onto a uniform 0.1 s grid by scripts/derive_mju26a_fs10.py "
                   f"(10 Hz by construction). Sample i is centred at source grid time t[0] + (5i + 2) x 0.1 s, "
                   f"t[0] = {t0_s} s in MJu26a.mat's t.")
        time_base = f"uniform 2 Hz: t[0] {t0_s} s + (5i + 2) x 0.1 s, in MJu26a.mat's t"
        src_time = {"source_t0_s": t0_s, "source_step_s": 0.1, "source_grid": sm.get("resampling")}
    units = (f"V as stored in the source ({cfg['from_npy']}: {sm.get('units')}); nothing is rescaled")
    manifest = {
        "source_file": cfg["source_file"],
        "raw_file": f"DATA/raw/{cfg['raw']}",
        "derived_from": {"stem": cfg["from_npy"], "source_file": cfg["parent_source_file"],
                         "path": f"DATA/derived/channels/{cfg['from_npy']}"},
        "n_channels": len(chans),
        "fs": 2.0,
        "fs_note": fs_note,
        "n_samples_per_channel": int(per[0]["samples"]),
        "dtype": "float64",
        "units": units,
        "imported_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "derived_by": f"scripts/thesis/newsets_fs2.py on {TODAY} (the method of scripts/derive_fs2.py)",
        "time_base": time_base,
        "preprocessing": {
            "decimation": FACTOR, "method": "non-overlapping block mean (Working/registration/excerpt.py::block_mean)",
            "anti_aliasing": "the 5-sample block mean only (a boxcar); no other filter",
            "nan_policy": "as scripts/derive_fs2.py: a block holding a non-finite sample is non-finite; "
                          f"{nonfinite} non-finite source samples",
            "source_fs": FS_IN, "source_samples": n_src, "trailing_samples_dropped": int(n_src - m * FACTOR),
            **src_time,
            "parent_source_file": cfg["parent_source_file"],
            "read": "memory-mapped, one channel at a time, in 5,000,000-sample chunks",
            "values_altered_otherwise": "none: no filtering beyond the block mean, no detrending, no rescaling",
        },
        "channels": [{"channel": j, "min": p["min"], "max": p["max"], "non_finite_source": p["non_finite"]}
                     for j, p in zip(chans, per)],
    }
    with open(os.path.join(staging, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    if os.path.isdir(final):
        shutil.rmtree(final)
    os.replace(staging, final)
    print(f"[{stem}] wrote {final}: CH0..CH{len(chans) - 1}.npy + manifest.json")


# ---------------------------------------------------------------------------------------------- llm-map --

def _hp(x, w):
    c = np.cumsum(np.concatenate([[0.0], x]))
    mm = (c[w:] - c[:-w]) / w
    pad = (len(x) - len(mm)) // 2
    mm = np.concatenate([np.full(pad, mm[0]), mm, np.full(len(x) - len(mm) - pad, mm[-1])])
    return x - mm


def llm_map(*, window=108_000, max_lag=600, hp=600):
    """Read-only. For each L_LM_Jul_26_J_raw_fs10 channel and every MJu26a_fs10 channel, on windows of ``window``
    samples (3 h at 10 Hz) at 25/50/75 % of the recording: the lag (within +-``max_lag``) of the best normalised
    correlation of the high-passed signals, its r, and the least-squares scale L_LM ~ a x MJu26a + b at that lag."""
    from scipy.signal import correlate
    a_dir, b_dir = os.path.join(CHANNELS, "L_LM_Jul_26_J_raw_fs10"), os.path.join(CHANNELS, "MJu26a_fs10")
    la = [np.load(os.path.join(a_dir, f"CH{i}.npy"), mmap_mode="r") for i in range(5)]
    mb = [np.load(os.path.join(b_dir, f"CH{j}.npy"), mmap_mode="r") for j in range(16)]
    n = min(len(la[0]), len(mb[0]))
    print(f"L_LM {len(la[0]):,} samples x 5, MJu26a_fs10 {len(mb[0]):,} x 16")
    out = []
    for i in range(5):
        rows = []
        for frac in (0.25, 0.5, 0.75):
            s = int(n * frac)
            x = np.asarray(la[i][s:s + window], dtype=np.float64)
            xh = _hp(x, hp)
            xh = (xh - xh.mean()) / xh.std()
            best = []
            for j in range(16):
                y = np.asarray(mb[j][s - max_lag:s + window + max_lag], dtype=np.float64)
                yh = _hp(y, hp)
                # normalised r at every lag: correlate x (fixed) with each window of y
                num = correlate(yh, xh, mode="valid", method="fft")
                c1 = np.cumsum(np.concatenate([[0.0], yh]))
                c2 = np.cumsum(np.concatenate([[0.0], yh * yh]))
                s1 = c1[window:] - c1[:-window]
                s2 = c2[window:] - c2[:-window]
                sd = np.sqrt(np.maximum(s2 / window - (s1 / window) ** 2, 1e-30))
                r = num / (window * sd)
                k = int(np.argmax(r))
                best.append((float(r[k]), j, k - max_lag))
            best.sort(reverse=True)
            r1, j1, lag = best[0]
            y = np.asarray(mb[j1][s + lag:s + lag + window], dtype=np.float64)
            a_, b_ = np.polyfit(y, x, 1)
            resid = x - (a_ * y + b_)
            rows.append({"frac": frac, "start": s, "best": j1, "r": r1, "lag": lag, "scale": float(a_),
                         "intercept": float(b_), "resid_rms_over_std": float(resid.std() / x.std()),
                         "second": {"channel": best[1][1], "r": best[1][0]}})
        out.append({"llm_channel": i, "windows": rows})
        print(f"L_LM CH{i}: " + "; ".join(
            f"{w['frac']:.0%} -> MJu26a CH{w['best']} r {w['r']:.4f} lag {w['lag']} scale {w['scale']:.2f} "
            f"(+{w['intercept']:.3g}) resid {w['resid_rms_over_std']:.3g}, next CH{w['second']['channel']} "
            f"r {w['second']['r']:.3f}" for w in rows), flush=True)
    print(json.dumps(out, indent=1))
    return out


# ----------------------------------------------------------------------------------------------- bundle --

def bundle(*, date="20261027", keep_sandbox=False, db_source=None):
    """``db_source``: the database to copy into the sandbox. The live bridge keeps recent writes in the WAL, which a
    file copy of annotations.sqlite misses (2026-10-27: the three new registrations were not in the copy), so pass a
    backup taken through the bridge (`POST /api/backups`, the sqlite backup API) after the registrations."""
    out_rel = os.path.join("docs", "thesis", "hpc", f"rq4_newsets_{date}")
    from webui.server.runtime import Runtime
    rt = Runtime(mode="sandbox", runtime_root=SCRATCH, db_source=db_source).setup()
    print("sandbox database:", rt.db_path)
    try:
        spec = importlib.util.spec_from_file_location("rq4o", os.path.join(ROOT, "scripts", "rq4_overnight.py"))
        R = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(R)
        batch = R.build_batch(rt.db_path, BUNDLE_SOURCES, out_rel=out_rel, prefix=PREFIX,
                              units={s: "V" for s in BUNDLE_SOURCES})
    finally:
        rt.restore()
        if not keep_sandbox:
            shutil.rmtree(rt.dir, ignore_errors=True)
    for d in batch["datasets"]:
        print(f"{d['source']}: {d['jobs']} chain jobs, {d['tasks']} tasks, unit {d['unit']}, matrix profile on "
              f"{d['mpChannels'] or 'no channels'}" + (f" ({d['mpLeftOut']})" if d["mpLeftOut"] else ""))
        for x in d.get("leftOut") or []:
            print(f"    left out: {x['label']}: {x['reason']}")
        for r in d["refused"]:
            print(f"    refused: {r['label']}: {str(r['reason'])[:200]}")
    for p in batch["packs"]:
        print(f"    {p['name']}: {p['tasks']} tasks, {p['parallel']} at a time, about "
              f"{p['estimateCoreS'] / 3600:.2f} core-hours (balancing estimate)")
    print(f"    inputs the cluster needs: {len(set(batch['inputs']))} files")
    return batch


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("derive")
    d.add_argument("--only", nargs="*", default=None, choices=list(SETS))
    d.add_argument("--dry-run", action="store_true")
    d.add_argument("--force", action="store_true")
    sub.add_parser("llm-map")
    b = sub.add_parser("bundle")
    b.add_argument("--date", default="20261027")
    b.add_argument("--keep-sandbox", action="store_true")
    b.add_argument("--db-source", default=None, help="a backup taken through POST /api/backups after registering")
    a = ap.parse_args(argv)
    if a.cmd == "derive":
        for stem in a.only or list(SETS):
            derive(stem, dry=a.dry_run, force=a.force)
    elif a.cmd == "llm-map":
        llm_map()
    else:
        bundle(date=a.date, keep_sandbox=a.keep_sandbox, db_source=a.db_source)
    return 0


if __name__ == "__main__":
    sys.exit(main())
