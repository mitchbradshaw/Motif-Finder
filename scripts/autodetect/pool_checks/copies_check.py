"""Are M1 / M100 / M101_t copies of one another? And amplitude scales of every target file (read-only).

A side check of the 24 Nov drop pool (scripts/autodetect/run_pool.py, build_pool.py): which files are copies of one another (M1 / M100 / M101_t) and each file's amplitude scale - why M100 and M101_t are left out (output: checks/copies_check.out.txt).
Read-only on the database. Kept from the session that built the pool; queue 57's detections are ids 13389236-13394543.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/pool_checks/copies_check.py
"""
import os
import sqlite3

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # the repo
c = sqlite3.connect(f"file:{os.path.join(ROOT, 'DATA', 'db', 'annotations.sqlite').replace(os.sep, '/')}?mode=ro", uri=True)
rows = {(f, ch): (rid, npy, fs, n, u) for rid, f, ch, npy, fs, n, u in
        c.execute("SELECT id, source_file, channel, npy_path, fs, n_samples, units FROM recordings")}


def load(f, ch, a=0, b=None):
    rid, npy, fs, n, u = rows[(f, ch)]
    x = np.load(os.path.join(ROOT, npy), mmap_mode="r")
    return np.asarray(x[a:b if b else len(x)], dtype=float), fs, u


chs = sorted(ch for (f, ch) in rows if f == "M1.mat")
print("M1 channels:", chs)
for ch in chs[:4]:
    seg = {}
    for f in ("M1.mat", "M100.mat", "M101_t.mat"):
        x, fs, u = load(f, ch, 1_000_000, 1_400_000)
        seg[f] = x
    a, b, d = seg["M1.mat"], seg["M100.mat"], seg["M101_t.mat"]
    ok = np.isfinite(a) & np.isfinite(b) & np.isfinite(d)
    r1 = np.corrcoef(a[ok], b[ok])[0, 1] if ok.sum() > 10 else np.nan
    r2 = np.corrcoef(a[ok], d[ok])[0, 1] if ok.sum() > 10 else np.nan
    print(f"CH{ch}: r(M1,M100)={r1:.5f} r(M1,M101_t)={r2:.5f}  ratio sd M100/M1={np.nanstd(b) / np.nanstd(a):.4g} "
          f"M101/M1={np.nanstd(d) / np.nanstd(a):.4g}  M1 p1-p99={np.nanpercentile(a, 1):.4g}..{np.nanpercentile(a, 99):.4g}")

# lagged check M1 vs M101_t (different length: maybe a time shift)
a, _, _ = load("M1.mat", chs[0], 2_000_000, 2_100_000)
d, _, _ = load("M101_t.mat", chs[0], 2_000_000 - 20_000, 2_100_000 + 20_000)
best = max(((np.corrcoef(a, d[k:k + len(a)])[0, 1], k - 20_000) for k in range(0, 40_000, 50)), key=lambda t: t[0])
print("M1 vs M101_t best lag (samples):", best)

print("\namplitude scale per target file (channel 1, middle 200k samples, stored units):")
for f in sorted({f for (f, ch) in rows}):
    ch = min(ch for (ff, ch) in rows if ff == f)
    rid, npy, fs, n, u = rows[(f, ch)]
    mid = n // 2
    x, fs, u = load(f, ch, max(0, mid - 100_000), min(n, mid + 100_000))
    dx = np.diff(x[np.isfinite(x)])
    step = 1.4826 * np.median(np.abs(dx - np.median(dx))) if len(dx) else np.nan
    nan_share = float(np.mean(~np.isfinite(np.load(os.path.join(ROOT, npy), mmap_mode="r")[::97])))
    print(f"{f:50s} units={u!s:5s} fs={fs:g} p1..p99={np.nanpercentile(x, 1):.4g}..{np.nanpercentile(x, 99):.4g} "
          f"step-noise={step:.3g} NaN~{nan_share:.1%}")
