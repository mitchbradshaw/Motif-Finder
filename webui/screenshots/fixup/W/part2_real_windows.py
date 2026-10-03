"""Fixup W Part 2 -- Explore's cross-channel computation (same absolute window on
every channel, webui/server/explore_routes.py get_cross_channel) on ~300
`interesting` windows of M2_aug_concat_fs1.mat, all 16 channels, reference =
the window's own channel. DB opened read-only; channels mmap'd read-only."""
import sys, os, sqlite3, csv
sys.path.insert(0, r"C:\Users\mmebr\Documents\CNN")
import numpy as np
from Working.cross_channel import classify_waveforms

ROOT = r"C:\Users\mmebr\Documents\CNN"
OUT = os.path.join(ROOT, r"webui\screenshots\fixup\W")
MAX_LEN = 20_000          # np.correlate(full) is O(n^2); longer windows excluded and counted
N_WIN = 300
CROSS_MAX_SAMPLES = 200_000

c = sqlite3.connect("file:" + os.path.join(ROOT, r"DATA\db\annotations.sqlite").replace("\\", "/") + "?mode=ro", uri=True)
c.row_factory = sqlite3.Row
recs = {r["id"]: dict(r) for r in c.execute(
    "select id, channel, fs, units, npy_path, n_samples from recordings where source_file='M2_aug_concat_fs1.mat'")}
ch = {rid: np.load(os.path.join(ROOT, r["npy_path"]), mmap_mode="r") for rid, r in recs.items()}
ids = sorted(recs)
anns = [dict(r) for r in c.execute(
    "select id, recording_id, start_idx, end_idx from annotations where verdict='interesting' and deleted_at is null "
    "and recording_id in (%s) order by id" % ",".join(map(str, ids)))]
c.close()
long_ = [a for a in anns if a["end_idx"] - a["start_idx"] > MAX_LEN]
ok = [a for a in anns if 4 <= a["end_idx"] - a["start_idx"] <= MAX_LEN]
rng = np.random.default_rng(40)
pick = [ok[i] for i in sorted(rng.choice(len(ok), size=min(N_WIN, len(ok)), replace=False))]
print(f"interesting windows on M2_aug: {len(anns)}; >{MAX_LEN} samples excluded: {len(long_)}; sampled {len(pick)}")
print("window lengths sampled:", np.unique([a['end_idx'] - a['start_idx'] for a in pick], return_counts=True))

rows = []; undefined = 0
for a in pick:
    s0, s1 = a["start_idx"], a["end_idx"]
    ref = np.asarray(ch[a["recording_id"]][s0:s1], float)
    stride = max(1, int(np.ceil(len(ref) / CROSS_MAX_SAMPLES)))
    ref = ref[::stride]
    for rid in ids:
        if rid == a["recording_id"]:
            continue
        y = np.asarray(ch[rid][s0:s1], float)[::stride]
        n = min(len(y), len(ref))
        if not (n >= 4 and np.isfinite(ref[:n]).all() and np.isfinite(y[:n]).all() and ref[:n].std() > 0 and y[:n].std() > 0):
            undefined += 1; continue
        lag, r, cls = classify_waveforms(ref[:n], y[:n])
        rows.append((a["id"], recs[a["recording_id"]]["channel"], recs[rid]["channel"], n, stride, lag, r, cls))

with open(os.path.join(OUT, "part2_pairs.csv"), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["annotation_id", "ref_ch", "other_ch", "n", "stride", "lag", "r", "bin"]); w.writerows(rows)

lag = np.array([r[5] for r in rows]); rr = np.array([r[6] for r in rows]); b = np.array([r[7] for r in rows])
print(f"\ntotal pairs {len(rows)}  (undefined/skipped {undefined})")
print("bins all pairs:", {k: int((b == k).sum()) for k in ("artifact", "propagation", "independent_recurrence")})
z = np.abs(lag) <= 1
print(f"\n|lag|<=1: {z.sum()}   (lag==0: {(lag==0).sum()})")
bands = [(0, .5, "<0.5"), (.5, .7, "0.5-0.7"), (.7, .9, "0.7-0.9"), (.9, .99, "0.9-0.99"), (.99, 9, ">=0.99")]
print(f"{'|r| band':10} {'r>0':>6} {'r<0':>6} {'total':>6} | {'artifact':>8} {'propag':>7} {'indep':>6}")
for lo, hi, name in bands:
    m = z & (np.abs(rr) >= lo) & (np.abs(rr) < hi)
    print(f"{name:10} {(m & (rr > 0)).sum():6d} {(m & (rr < 0)).sum():6d} {m.sum():6d} | "
          f"{(m & (b=='artifact')).sum():8d} {(m & (b=='propagation')).sum():7d} {(m & (b=='independent_recurrence')).sum():6d}")
m = z & (np.abs(rr) >= .5) & (np.abs(rr) < .99)
print(f"|lag|<=1 & 0.5<=|r|<0.99: {m.sum()} -> propagation {(m & (b=='propagation')).sum()}")
print(f"r <= -0.99 at lag 0: {((lag==0) & (rr <= -.99)).sum()}  (at |lag|<=1: {(z & (rr <= -.99)).sum()})")
print(f"r >= +0.99 at |lag|<=1: {(z & (rr >= .99)).sum()}")
nz = np.abs(lag[lag != 0])
print(f"\nnon-zero lag pairs: {nz.size}")
edges = [1, 2, 6, 11, 51, 101, 301, 10**9]
for lo, hi in zip(edges[:-1], edges[1:]):
    print(f"  |lag| {lo}-{hi-1 if hi<10**9 else 'max'}: {((nz>=lo)&(nz<hi)).sum()}")
if nz.size: print("  median |lag|", np.median(nz), "max", nz.max())
print("|r| at non-zero lag: median %.3f" % np.median(np.abs(rr[lag != 0])) if nz.size else "")
print("|r| at |lag|>1 by bin:", {k: int(((np.abs(lag) > 1) & (b == k)).sum()) for k in ("propagation", "independent_recurrence")})

import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, axs = plt.subplots(1, 2, figsize=(13, 5))
col = {"artifact": "#d62728", "propagation": "#1f77b4", "independent_recurrence": "#7f7f7f"}
for ax, xl in zip(axs, (None, (-12, 12))):
    for k in col:
        m = b == k
        ax.scatter(lag[m], rr[m], s=5, alpha=.4, c=col[k], label=f"{k} ({m.sum()})")
    for y in (.99, -.99): ax.axhline(y, lw=.6, ls="--", c="k")
    ax.axvspan(-1.5, 1.5, color="orange", alpha=.12)
    ax.set_xlabel("lag (samples, fs = 1 Hz; y relative to reference)"); ax.set_ylabel("r at peak |r|")
    if xl: ax.set_xlim(*xl); ax.set_title("zoom |lag| <= 12")
    else: ax.set_symlog = None; ax.set_xscale("symlog", linthresh=10); ax.set_title(f"all {len(rows)} pairs, {len(pick)} interesting windows, M2_aug (symlog x)")
axs[0].legend(loc="lower left", fontsize=8)
fig.tight_layout(); p = os.path.join(OUT, "part2_lag_vs_r.png"); fig.savefig(p, dpi=130); print("\nwrote", p)
