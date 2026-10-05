"""
ag_alignment_report.py
======================
fixup-ag continuation evidence (dev tooling, not imported by the app): the four
ways of lining a window up — grid / centred on its largest swing × no detrend /
linear detrend — on ONE pool and seed, and the researcher's worry measured
directly: after centring, how much of each pile is near-floor noise, per scale,
and how that changes as the floor is raised.

    python scripts/ag_alignment_report.py --db <sandbox copy>/annotations.sqlite --out <dir> --figs <dir>

The database is a sandbox copy; this script writes Settings › Datasets floors
into IT (to try floors) and nothing else; files only under --out / --figs.

Per combination: `shape.trace_shapes` (the block's own function), the Library's
Ward on 20,000 training windows (seed 0), `shape.propose` (k 2–20), and at k = 8
(and the proposal): sizes, scale mix, shifted copies among pile averages, and per
pile the share of NOISE-LIKE windows — raw range under 1 mV, and raw range under
8× the dataset's median sample-to-sample noise (sigma from the median absolute
first difference). A contact sheet per combination: per pile its medoid and 11
seeded members.
"""

import argparse
import json
import os
import shutil
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SOURCES = ("M2_aug_concat_fs1.mat", "M2_concat_fs1.mat")
STEMS = {"M2_aug_concat_fs1.mat": "M2_aug_concat_fs1", "M2_concat_fs1.mat": "M2_concat_fs1"}
COMBOS = (("grid", "off"), ("grid", "linear"), ("centre", "off"), ("centre", "linear"))
NOISE_MULT = 8.0


def _say(*a):
    print(*a, flush=True)


def _pool(conn):
    from Working.training import pool as tpool
    ids = [s["id"] for s in tpool.list_sets(conn) if s["kind"] == "unlabelled" and set(s["source_files"]) <= set(SOURCES)]
    plan = tpool.plan_for(conn, list(SOURCES), hold_out_pack="D")
    return tpool.combine(conn, ids, plan, sample={1: 20000, 10: 20000, 30: 20000}, seed=0)


def _best_shift(a, b, max_lag):
    a = (a - a.mean()) / (a.std() or 1)
    b = (b - b.mean()) / (b.std() or 1)
    n = len(a)
    best = -2.0
    for lag in range(-max_lag, max_lag + 1):
        x, y = (a[lag:], b[:n - lag]) if lag >= 0 else (a[:n + lag], b[-lag:])
        best = max(best, float(np.corrcoef(x, y)[0, 1]))
    return best


def _noise_like(f):
    rr = f["raw_range_mv"].to_numpy(dtype=float)
    sig = f.groupby("source_file")["noise_mv"].transform("median").to_numpy(dtype=float)
    return rr < 1.0, rr < NOISE_MULT * sig


def _at_k(shapes, tree, k):
    from sklearn.metrics import normalized_mutual_info_score as nmi
    from Working.training import shape as sh
    lab = sh.labels_at(tree, shapes, k)
    tr = tree.train_rows
    g = lab.labels[tr]
    f = shapes.frame.iloc[tr].reset_index(drop=True)
    under1, undern = _noise_like(f)
    sc = f["scale_min"].to_numpy()
    piles = []
    for c in range(1, lab.k + 1):
        m = g == c
        piles.append({"cluster": c, "n": int(m.sum()),
                      "scales": {f"{int(s)}": int((m & (sc == s)).sum()) for s in (1.0, 10.0, 30.0)},
                      "under_1mv": round(float(under1[m].mean()), 3) if m.any() else None,
                      "under_noise": round(float(undern[m].mean()), 3) if m.any() else None,
                      "under_noise_by_scale": {f"{int(s)}": (round(float(undern[m & (sc == s)].mean()), 3) if (m & (sc == s)).any() else None)
                                               for s in (1.0, 10.0, 30.0)}})
    means = np.vstack([np.asarray(shapes.vectors[tr][g == c], float).mean(axis=0) for c in range(1, lab.k + 1)])
    n = means.shape[1]
    shifted = 0
    shifted_q = 0
    pairs = 0
    for i in range(lab.k):
        for j in range(i + 1, lab.k):
            pairs += 1
            c0 = float(np.corrcoef(means[i], means[j])[0, 1])
            cb = _best_shift(means[i], means[j], n // 2)
            shifted += int(cb >= 0.8 and cb - c0 >= 0.3)
            # the stricter count: a slide of at most a quarter window, so three quarters of each curve still overlap
            # (at half a window, half of any two smooth curves correlate well, and the loose count says little)
            cq = _best_shift(means[i], means[j], n // 4)
            shifted_q += int(cq >= 0.8 and cq - c0 >= 0.3)
    # where do the noise-like windows go: the share of them that sit in piles that are mostly noise-like
    noisy_piles = [p["cluster"] for p in piles if (p["under_noise"] or 0) >= 0.5]
    in_noisy = float(np.isin(g[undern], noisy_piles).mean()) if undern.any() else None
    return {"k": int(lab.k), "sizes": [p["n"] for p in piles], "piles": piles,
            "nmi_scale": round(float(nmi(g, sc)), 4), "nmi_recording": round(float(nmi(g, f["source_file"])), 4),
            "shifted_copies": shifted, "shifted_copies_quarter": shifted_q, "pairs": pairs, "means": means.round(4).tolist(),
            "noise_like_share": {"under_1mv": round(float(under1.mean()), 3), "under_noise": round(float(undern.mean()), 3),
                                 "under_noise_by_scale": {f"{int(s)}": round(float(undern[sc == s].mean()), 3) for s in (1.0, 10.0, 30.0)},
                                 "under_1mv_by_scale": {f"{int(s)}": round(float(under1[sc == s].mean()), 3) for s in (1.0, 10.0, 30.0)}},
            "noisy_piles": noisy_piles, "share_of_noise_in_noisy_piles": None if in_noisy is None else round(in_noisy, 3)}, lab


def _sheet(path, shapes, tree, lab, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from Working.training import shape as sh
    k = lab.k
    fig, axes = plt.subplots(k, 12, figsize=(17, 1.25 * k + 0.6), squeeze=False)
    x = np.linspace(0, 1, shapes.vectors.shape[1])
    for c in range(1, k + 1):
        d = sh.cluster_detail(tree, shapes, lab, c, n_members=11, seed=0)
        for j, w in enumerate([d["medoid"], *d["members"]]):
            ax = axes[c - 1, j]
            ax.plot(x, w["shape"], lw=0.8, color="#b35900" if j == 0 else "#333")
            ax.set_xticks([]); ax.set_yticks([])
            rr = w["raw_range_mv"]
            ax.set_title(f"{'MEDOID ' if j == 0 else ''}{w['scale_min']}m · {rr:.2g} mV" if rr is not None else "", fontsize=5.5)
        axes[c - 1, 0].set_ylabel(f"pile {c}\nn {d['n']:,}", fontsize=7)
    fig.suptitle(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def run_combo(conn, frame, align, detrend, label, out, figs, ks=(8,)):
    from Working.training import shape as sh
    t = time.time()
    shapes = sh.trace_shapes(conn, frame, align=align, detrend=detrend)
    t_shape = time.time() - t
    t = time.time()
    tree = sh.cluster_shapes(shapes, sample=20000, seed=0)
    t_tree = time.time() - t
    prop = sh.propose(tree, shapes)
    res = {"align": align, "detrend": detrend, "label": label, "t_shape_s": round(t_shape, 1), "t_tree_s": round(t_tree, 1),
           "n_kept": int(len(shapes.frame)), "n_train": int(len(tree.train_rows)),
           "under_floor": shapes.meta["under_floor"]["n"], "floors": shapes.meta["floors"], "recut": shapes.meta["recut"],
           "silhouette_by_k": {r["k"]: r["silhouette"] for r in prop["by_k"]}, "suggested_k": prop["suggested_k"],
           "at_k": {}}
    for k in sorted(set([*ks, prop["suggested_k"] or 2])):
        r, lab = _at_k(shapes, tree, k)
        res["at_k"][k] = r
        if figs and k in ks:
            _sheet(os.path.join(figs, f"align_sheet_{label}_k{k}.png"), shapes, tree, lab,
                   f"{label}: align {align} · detrend {detrend} · k = {k} · medoid (brown) and 11 members per pile "
                   f"(normalised shape; scale and raw range above each)")
    _say(json.dumps({"label": label, "suggested_k": res["suggested_k"], "sil_k2_8_12": [res["silhouette_by_k"].get(x) for x in (2, 8, 12)],
                     "recut": {k: v for k, v in res["recut"].items() if k not in ("by_scale", "rule")},
                     "k8": {k2: res["at_k"][8][k2] for k2 in ("sizes", "nmi_scale", "shifted_copies", "shifted_copies_quarter", "noise_like_share",
                                                             "noisy_piles", "share_of_noise_in_noisy_piles")}}, default=str))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--figs")
    ap.add_argument("--floors", default="0.3,1.0", help="raised floors (mV) to try on the recommended combination")
    ap.add_argument("--best", default="centre,linear")
    ap.add_argument("--combos", default="grid-off,grid-linear,centre-off,centre-linear")
    ap.add_argument("--json", default="alignment.json")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    from Working.database.schema import init_db
    from Working.registration.settings import put_settings
    from Working.training import shape as sh
    work = os.path.join(a.out, "work.sqlite")
    shutil.copyfile(a.db, work)
    conn = init_db(work)
    pool = _pool(conn)
    frame = sh.pool_frame(sh.pool_windowset(pool))
    _say(f"pool {len(frame):,} · key {pool.key}")
    results = {"pool_key": pool.key, "combos": [], "floors": []}
    for align, det in [tuple(c.split("-")) for c in a.combos.split(",") if c]:
        results["combos"].append(run_combo(conn, frame, align, det, f"{align}-{det}", a.out, a.figs))
        with open(os.path.join(a.out, a.json), "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=1, default=str)
    best = tuple(a.best.split(","))
    for fl in [float(v) for v in a.floors.split(",") if v]:
        put_settings(conn, "datasets", {f"meta.{stem}.noise_floor": fl for stem in STEMS.values()})
        r = run_combo(conn, frame, best[0], best[1], f"{best[0]}-{best[1]}-floor{fl:g}", a.out, a.figs)
        r["floor_mv"] = fl
        results["floors"].append(r)
        with open(os.path.join(a.out, a.json), "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=1, default=str)
    conn.close()


if __name__ == "__main__":
    main()
