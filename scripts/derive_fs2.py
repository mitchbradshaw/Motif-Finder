"""
derive_fs2.py
=============
Derive 2 Hz versions of three 10 Hz recordings for the RQ4 batch 3 sweep (the researcher, 2026-10-19). At 10 Hz each
would bring back about 26 GB of cluster results, more than the account's 30 GB; at 2 Hz the three are similar in size
(3.5–4.6 M samples a channel):

    DATA/raw/LM.mat                 (17,280,001 x 4, V)   -> DATA/derived/channels/LM_fs2/
    DATA/raw/CO.mat                 (17,280,001 x 4, V)   -> DATA/derived/channels/CO_fs2/
    DATA/raw/L_LM_Jul_26_J_raw.mat  (22,892,769 x 5, mV)  -> DATA/derived/channels/L_LM_Jul_26_J_raw_fs2/
                                    (read from the already extracted .../L_LM_Jul_26_J_raw_fs10/CH*.npy)

What the files are (read, not assumed, 2026-10-19)
--------------------------------------------------
Each .mat (MATLAB 5.0) holds one double matrix (samples x channels) and an MCOS object: a MATLAB `duration` time
vector, one double per sample in milliseconds, which scipy cannot decode as an object. Its raw doubles are read here
from the function-workspace blob (`_timestamps`). In all three, every step is exactly 100 ms, so the rate is 10 Hz
read from the file:
- LM and CO start at t = 1,800,000 ms (30 min into their recording) and run 480 h with no gap;
- L_LM starts at 0 and runs 636 h. This also confirms its 10 Hz, which was inferred until now.

Units:
- LM and CO are volts as stored (values about -0.7..0.3), the scale of MJu26a, the raw parent of L_LM.
- L_LM is millivolts as stored (x1000 of MJu26a; verified 2026-09-23).

Method: non-overlapping block means of 5 consecutive samples (10 Hz -> 2 Hz), the repo's decimation convention
(`Working/registration/excerpt.py::block_mean`). Sample i of the 2 Hz series is the mean of source samples 5i..5i+4,
centred at source time t0 + (5i + 2) x 100 ms. The trailing partial block is dropped and counted in the manifest.
Nothing else is altered: no filtering beyond the block mean, no detrending, no rescaling.

Registration is a separate step: Settings › Datasets, or `POST /api/registry/recording/register` with the folder.

    python scripts/derive_fs2.py --dry-run
    python scripts/derive_fs2.py [--only LM_fs2 ...] [--force]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import struct
import sys
import zlib

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHANNELS = os.path.join(REPO, "DATA", "derived", "channels")
FACTOR = 5
FS_IN = 10.0

SETS = {
    "LM_fs2": {"raw": "LM.mat", "var": "LM", "units": "V", "source_file": "LM_fs2.mat"},
    "CO_fs2": {"raw": "CO.mat", "var": "CO", "units": "V", "source_file": "CO_fs2.mat"},
    "L_LM_Jul_26_J_raw_fs2": {"raw": "L_LM_Jul_26_J_raw.mat", "var": "M23", "units": "mV",
                              "source_file": "L_LM_Jul_26_J_raw_fs2.mat", "from_npy": "L_LM_Jul_26_J_raw_fs10",
                              "parent_source_file": "L_LM_Jul_26_J_raw.mat"},
}


def _timestamps(path, n):
    """The `duration` vector of a v5 .mat: n float64 milliseconds read from the last element (the MCOS function
    workspace). It is the first run of n values there that starts at or above 0 and strictly increases."""
    with open(path, "rb") as f:
        f.seek(128)
        last = None
        while True:
            tag = f.read(8)
            if len(tag) < 8:
                break
            t, size = struct.unpack("<II", tag)
            last = (size, f.tell())
            f.seek(f.tell() + size)
        f.seek(last[1])
        raw = zlib.decompress(f.read(last[0]))
    for off in range(0, len(raw) - 8 * n + 1, 8):
        head = np.frombuffer(raw, dtype="<f8", count=3, offset=off)
        if not (np.all(np.isfinite(head)) and head[0] >= 0 and head[0] < 1e12 and head[2] > head[1] > head[0]
                and abs((head[1] - head[0]) - 100.0) < 1e-6):
            continue
        v = np.frombuffer(raw, dtype="<f8", count=n, offset=off)
        if np.all(np.diff(v) > 0):
            return v
    raise SystemExit(f"{path}: no {n:,}-sample time vector found in its MCOS blob")


def _load(cfg):
    raw = os.path.join(REPO, "DATA", "raw", cfg["raw"])
    if cfg.get("from_npy"):
        d = os.path.join(CHANNELS, cfg["from_npy"])
        chans = sorted((int(f[2:-4]), f) for f in os.listdir(d) if f.startswith("CH") and f.endswith(".npy"))
        X = np.stack([np.load(os.path.join(d, f), mmap_mode="r") for _i, f in chans], axis=1)
    else:
        import scipy.io as sio
        X = sio.loadmat(raw, variable_names=[cfg["var"]])[cfg["var"]]
    return raw, np.asarray(X, dtype=np.float64)


def derive(stem, dry=False, force=False):
    cfg = SETS[stem]
    final = os.path.join(CHANNELS, stem)
    if os.path.isfile(os.path.join(final, "manifest.json")) and not force:
        print(f"[{stem}] exists, skipped (--force to redo)")
        return
    raw, X = _load(cfg)
    n, c = X.shape
    t = _timestamps(raw, n)
    steps = np.diff(t)
    if not np.allclose(steps, 100.0, atol=1e-6):
        bad = np.where(np.abs(steps - 100.0) > 1e-6)[0]
        raise SystemExit(f"[{stem}] {len(bad)} time steps are not 100 ms (first at sample {bad[0]}): not uniform 10 Hz")
    m = n // FACTOR * FACTOR
    Y = X[:m].reshape(-1, FACTOR, c).mean(axis=1)
    print(f"[{stem}] {cfg['raw']}: {n:,} x {c} at 10 Hz (t0 {t[0]:.0f} ms, every step 100 ms) -> {len(Y):,} x {c} at "
          f"2 Hz ({len(Y) / 2 / 3600:.1f} h), {n - m} trailing sample(s) dropped")
    if dry:
        return
    os.makedirs(CHANNELS, exist_ok=True)
    staging = os.path.join(CHANNELS, f".staging_{stem}_{os.getpid()}")
    if os.path.isdir(staging):
        shutil.rmtree(staging)
    os.makedirs(staging)
    for j in range(c):
        np.save(os.path.join(staging, f"CH{j}.npy"), np.ascontiguousarray(Y[:, j]))
    manifest = {
        "source_file": cfg["source_file"],
        "raw_file": f"DATA/raw/{cfg['raw']}",
        "n_channels": int(c),
        "fs": 2.0,
        "fs_note": ("2 Hz: block means of 5 consecutive samples of the source, whose own per-sample time vector (the "
                    "MATLAB duration object in the .mat, decoded by scripts/derive_fs2.py) steps exactly 100 ms "
                    f"throughout (10 Hz). Sample i is centred at source time t0 + (5i + 2) x 100 ms, t0 = {t[0]:.0f} ms."),
        "n_samples_per_channel": int(len(Y)),
        "dtype": "float64",
        "units": (f"{cfg['units']} as stored in the source (" +
                  ("millivolts: x1000 of MJu26a, verified 2026-09-23" if cfg["units"] == "mV" else
                   "volts: values about -0.7..0.3, the scale of MJu26a, the raw parent of L_LM") + "); nothing is rescaled"),
        "imported_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "derived_by": "scripts/derive_fs2.py on 2026-10-19",
        "time_base": f"uniform 2 Hz: source t0 {t[0]:.0f} ms + (5i + 2) x 100 ms",
        "preprocessing": {
            "decimation": FACTOR, "method": "non-overlapping block mean (Working/registration/excerpt.py::block_mean)",
            "source_fs": FS_IN, "source_samples": int(n), "trailing_samples_dropped": int(n - m),
            "source_t0_ms": float(t[0]), "source_t_end_ms": float(t[-1]), "source_step_ms": 100.0,
            "parent_source_file": cfg.get("parent_source_file"),
            "values_altered_otherwise": "none: no filtering beyond the block mean, no detrending, no rescaling",
        },
    }
    with open(os.path.join(staging, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    if os.path.isdir(final):
        shutil.rmtree(final)
    os.replace(staging, final)
    print(f"[{stem}] wrote {final}: CH0..CH{c - 1}.npy + manifest.json")


def main():
    ap = argparse.ArgumentParser(description="derive the 2 Hz recordings for RQ4 batch 3")
    ap.add_argument("--only", nargs="*", default=None, choices=list(SETS))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    for stem in a.only or list(SETS):
        derive(stem, dry=a.dry_run, force=a.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
