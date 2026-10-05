"""
ag_shape_pool_report.py
=======================
fixup-ag evidence (dev tooling, not imported by the app): one real clustering of
a pool on trace shape, and the POSITION-IN-WINDOW measurement the ticket asks
for before the piles are trusted.

    python scripts/ag_shape_pool_report.py --db <sandbox copy>/annotations.sqlite --out <dir> [--figs <dir>]

Reads the database READ-ONLY apart from nothing: the pool is combined in memory
(`Working.training.pool.combine`), never saved. Writes only under --out / --figs.

Stage 1 — the clustering, exactly as the chain's blocks do it: the saved
unlabelled sets of M2_aug_concat_fs1 and M2_concat_fs1, pack D held out, 20,000
windows per scale (seed 0), `shape.trace_shapes` (noise floor on),
`shape.cluster_shapes` (20,000 training windows, seed 0), `shape.propose`.
Timings and the process's peak memory are printed.

Stage 2 — do the piles gather by shape or by where the event sits?
  * every window's `peak_frac` (where its largest excursion from the median sits,
    0 = start, 1 = end);
  * eta^2 of peak_frac by cluster: the share of its variance the clusters explain
    (0 = the clusters ignore position, 1 = they are position bins);
  * normalised mutual information between cluster and position decile, against
    cluster x scale and cluster x recording;
  * position alone as a predictor: a 1-D nearest-neighbour on peak_frac, the
    share of held-back sampled windows it puts in their own cluster, against
    chance (the largest cluster's share);
  * shifted copies: for every pair of cluster mean shapes, the correlation at lag 0
    against the best correlation over lags up to half a window — a pair that is
    one shape at two positions correlates far better shifted;
  * the counterfactual: the same windows re-cut CENTRED on their largest
    excursion, clustered on the same sample, compared with the grid clustering
    (adjusted Rand index) and with eta^2 again.
"""

import argparse
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SOURCES = ("M2_aug_concat_fs1.mat", "M2_concat_fs1.mat")


def _say(*a):
    print(*a, flush=True)


def stage1(db, out, per_scale=20000, sample=20000, seed=0):
    from Working.database.schema import init_db
    from Working.training import pool as tpool
    from Working.training import shape as sh
    conn = init_db(db)
    sets = [s for s in tpool.list_sets(conn) if s["kind"] == "unlabelled" and set(s["source_files"]) <= set(SOURCES)]
    ids = [s["id"] for s in sets]
    _say("sets:", [(s["id"], s["name"], s["n_windows"]) for s in sets])
    t = time.time()
    plan = tpool.plan_for(conn, list(SOURCES), hold_out_pack="D")
    pool = tpool.combine(conn, ids, plan, sample={1: per_scale, 10: per_scale, 30: per_scale}, seed=seed)
    t_pool = time.time() - t
    _say(f"pool: {len(pool.table):,} windows in {t_pool:.1f} s · by role {pool.meta['counts']['by_role']}")
    t = time.time()
    shapes = sh.trace_shapes(conn, sh.pool_frame(sh.pool_windowset(pool)))
    t_shape = time.time() - t
    uf = shapes.meta["under_floor"]
    _say(f"shapes: {len(shapes.frame):,} kept of {shapes.meta['n_in']:,} in {t_shape:.1f} s · under floor {uf['n']:,} · "
         f"unmeasured {shapes.meta['unmeasured']['n']:,} · floors {shapes.meta['floors']}")
    shapes.save(os.path.join(out, "shapes"))
    t = time.time()
    tree = sh.cluster_shapes(shapes, sample=sample, seed=seed)
    t_tree = time.time() - t
    _say(f"tree: {len(tree.leaf_rows):,} clustered of {len(tree.train_rows):,} training windows · Ward {tree.meta['ward_seconds']} s "
         f"· stage {t_tree:.1f} s · peak RSS {tree.meta['peak_rss_mb']} MB")
    tree.save(os.path.join(out, "tree"))
    t = time.time()
    prop = sh.propose(tree, shapes)
    t_prop = time.time() - t
    _say(f"propose (k 2–20) {t_prop:.1f} s · suggested k {prop['suggested_k']} · specks under {prop['small_below']}")
    for r in prop["by_k"]:
        _say(f"  k {r['k']:>2}: silhouette {r['silhouette'] if r['silhouette'] is None else round(r['silhouette'], 3)} · "
             f"effective {r['effective_k']} · sizes {sorted(r['sizes'].values(), reverse=True)}")
    under_by = {}
    for r in uf["by"]:
        k = (r["recording"], r["scale_min"])
        under_by[k] = under_by.get(k, 0) + r["n"]
    in_by = {}
    for (sf, sc), n in sh.pool_frame(sh.pool_windowset(pool)).groupby(["source_file", "scale_min"]).size().items():
        in_by[(sf, sc)] = int(n)
    facts = {"n_pool": int(len(pool.table)), "pool_by_role": pool.meta["counts"]["by_role"], "t_pool_s": round(t_pool, 1),
             "n_kept": int(len(shapes.frame)), "under_floor": uf["n"], "under_floor_by": [
                 {"recording": k[0], "scale_min": k[1], "n": v, "of": in_by.get((k[0], float(k[1])), None)} for k, v in sorted(under_by.items())],
             "unmeasured": shapes.meta["unmeasured"]["n"], "floors": shapes.meta["floors"], "t_shape_s": round(t_shape, 1),
             "n_train": int(len(tree.train_rows)), "n_clustered": int(len(tree.leaf_rows)), "ward_s": tree.meta["ward_seconds"],
             "t_tree_s": round(t_tree, 1), "peak_rss_mb": sh.peak_rss_mb(), "t_propose_s": round(t_prop, 1),
             "suggested_k": prop["suggested_k"], "small_below": prop["small_below"],
             "by_k": [{"k": r["k"], "silhouette": r["silhouette"], "effective_k": r["effective_k"],
                       "sizes": sorted(r["sizes"].values(), reverse=True)} for r in prop["by_k"]]}
    with open(os.path.join(out, "stage1.json"), "w", encoding="utf-8") as f:
        json.dump(facts, f, indent=2, default=str)
    conn.close()
    return shapes, tree, prop, facts


def _eta2(y, g):
    y = np.asarray(y, float)
    m = y.mean()
    ss_tot = ((y - m) ** 2).sum()
    ss_b = sum(((y[g == c].mean() - m) ** 2) * (g == c).sum() for c in np.unique(g))
    return float(ss_b / ss_tot) if ss_tot > 0 else 0.0


def _nmi(a, b):
    from sklearn.metrics import normalized_mutual_info_score
    return float(normalized_mutual_info_score(a, b))


def _best_shift_corr(a, b, max_lag):
    a = (a - a.mean()) / (a.std() or 1)
    b = (b - b.mean()) / (b.std() or 1)
    n = len(a)
    best, lag_at = -2.0, 0
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            x, y = a[lag:], b[:n - lag]
        else:
            x, y = a[:n + lag], b[-lag:]
        c = float(np.corrcoef(x, y)[0, 1])
        if c > best:
            best, lag_at = c, lag
    return best, lag_at


def aligned_vectors(conn, frame, n):
    """The same windows, re-cut so the largest excursion sits at the centre (same length), then the Library's
    resample + z-normalise. A re-cut that runs off the channel is clamped to it."""
    from Working.library.grouping.methods import ward
    recs = {int(r[0]): (r[1], int(r[2])) for r in conn.execute("SELECT id, npy_path, n_samples FROM recordings")}
    out = np.zeros((len(frame), n), dtype=np.float32)
    for rid, g in frame.groupby("recording_id"):
        npy, ns = recs[int(rid)]
        x = np.load(npy, mmap_mode="r")
        segs = []
        for a, L, pk in zip(g["start"].to_numpy(), g["length"].to_numpy(), g["peak_frac"].to_numpy()):
            c = int(a) + int(round(pk * (L - 1)))
            s0 = min(max(0, c - L // 2), ns - L)
            segs.append(np.asarray(x[s0:s0 + L], float))
        out[g.index.to_numpy()] = ward.shape_vectors(segs, n)
    return out


def stage2(db, out, figs, shapes, tree, k):
    from sklearn.metrics import adjusted_rand_score
    from sklearn.neighbors import KNeighborsClassifier
    from Working.database.schema import init_db
    from Working.training import shape as sh
    lab = sh.labels_at(tree, shapes, k)
    f = shapes.frame
    tr = tree.train_rows
    g = lab.labels[tr]
    pk = f["peak_frac"].to_numpy()[tr]
    dec = np.minimum((pk * 10).astype(int), 9)
    res = {"k": int(lab.k), "eta2_peak_by_cluster": _eta2(pk, g),
           "nmi_cluster_position_decile": _nmi(g, dec),
           "nmi_cluster_scale": _nmi(g, f["scale_min"].to_numpy()[tr]),
           "nmi_cluster_recording": _nmi(g, f["source_file"].to_numpy()[tr])}
    # position alone as a predictor of the cluster, on the sampled windows (half fit, half held back)
    rng = np.random.default_rng(0)
    leaf = tree.leaf_rows.copy()
    rng.shuffle(leaf)
    a, b = leaf[: len(leaf) // 2], leaf[len(leaf) // 2:]
    knn = KNeighborsClassifier(n_neighbors=25).fit(f["peak_frac"].to_numpy()[a, None], lab.labels[a])
    res["position_only_accuracy"] = float((knn.predict(f["peak_frac"].to_numpy()[b, None]) == lab.labels[b]).mean())
    res["chance_largest_cluster"] = float(np.bincount(lab.labels[b]).max() / len(b))
    # shifted copies among cluster means
    means = np.vstack([np.asarray(shapes.vectors[tr][g == c], float).mean(axis=0) for c in range(1, lab.k + 1)])
    n = means.shape[1]
    pairs = []
    for i in range(lab.k):
        for j in range(i + 1, lab.k):
            c0 = float(np.corrcoef(means[i], means[j])[0, 1])
            cb, lag = _best_shift_corr(means[i], means[j], n // 2)
            pairs.append({"a": i + 1, "b": j + 1, "corr_lag0": round(c0, 3), "corr_best": round(cb, 3),
                          "lag_frac": round(lag / n, 3)})
    res["pairs"] = pairs
    res["pairs_shifted_copies"] = [p for p in pairs if p["corr_best"] >= 0.8 and p["corr_best"] - p["corr_lag0"] >= 0.3]
    # per-cluster peak position summary
    res["clusters"] = [{"cluster": c, "n": int((g == c).sum()), "peak_frac_median": float(np.median(pk[g == c])),
                        "peak_frac_iqr": [float(np.quantile(pk[g == c], 0.25)), float(np.quantile(pk[g == c], 0.75))],
                        "scales": {str(s): int(((g == c) & (f["scale_min"].to_numpy()[tr] == s)).sum()) for s in (1.0, 10.0, 30.0)}}
                       for c in range(1, lab.k + 1)]
    # the counterfactual: centre each window on its largest excursion
    conn = init_db(db)
    t = time.time()
    av = aligned_vectors(conn, f, shapes.vectors.shape[1])
    conn.close()
    aligned = sh.ShapeSet(frame=f, vectors=av, meta=dict(shapes.meta, aligned=True))
    atree = sh.cluster_shapes(aligned, sample=len(tree.leaf_rows), seed=int(tree.meta.get("seed") or 0))
    alab = sh.labels_at(atree, aligned, k)
    ga = alab.labels[tr]
    res["aligned"] = {"seconds": round(time.time() - t, 1), "ari_vs_grid": float(adjusted_rand_score(g, ga)),
                      "eta2_peak_by_cluster": _eta2(pk, ga), "nmi_cluster_position_decile": _nmi(ga, dec),
                      "nmi_cluster_scale": _nmi(ga, f["scale_min"].to_numpy()[tr]),
                      "silhouette": sh.propose(atree, aligned, k_range=(k, k))["by_k"][0]["silhouette"],
                      "sizes": sorted(np.bincount(ga)[1:].tolist(), reverse=True)}
    with open(os.path.join(out, f"stage2_k{k}.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    if figs:
        _figures(figs, shapes, tree, lab, pk, g, means, aligned, alab, res)
    return res


def _figures(figs, shapes, tree, lab, pk, g, means, aligned, alab, res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(figs, exist_ok=True)
    k = lab.k
    tr = tree.train_rows
    x = np.linspace(0, 1, shapes.vectors.shape[1])
    # 1. per cluster: mean shape ± sd and where the largest excursion sits
    fig, axes = plt.subplots(2, k, figsize=(2.2 * k, 4.6), squeeze=False)
    for c in range(1, k + 1):
        v = np.asarray(shapes.vectors[tr][g == c], float)
        ax = axes[0, c - 1]
        ax.fill_between(x, v.mean(0) - v.std(0), v.mean(0) + v.std(0), color="#cfe0fb")
        ax.plot(x, v.mean(0), color="#0a64d8", lw=1.2)
        ax.set_title(f"cluster {c} · n {len(v):,}", fontsize=8)
        ax.set_xticks([0, 0.5, 1]); ax.tick_params(labelsize=6)
        ax = axes[1, c - 1]
        ax.hist(pk[g == c], bins=20, range=(0, 1), color="#888")
        ax.set_xlabel("largest excursion at (0 start, 1 end)", fontsize=6); ax.tick_params(labelsize=6)
    fig.suptitle(f"Grid windows, Ward on trace shape, k = {k}: mean shape ± sd (top) and where the event sits (bottom)", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(figs, f"position_grid_clusters_k{k}.png"), dpi=130)
    plt.close(fig)
    # 2. the same after centring on the largest excursion
    ga = alab.labels[tr]
    fig, axes = plt.subplots(2, k, figsize=(2.2 * k, 4.6), squeeze=False)
    for c in range(1, k + 1):
        v = np.asarray(aligned.vectors[tr][ga == c], float)
        ax = axes[0, c - 1]
        if len(v):
            ax.fill_between(x, v.mean(0) - v.std(0), v.mean(0) + v.std(0), color="#e6d8fb")
            ax.plot(x, v.mean(0), color="#6b3fd4", lw=1.2)
        ax.set_title(f"cluster {c} · n {len(v):,}", fontsize=8)
        ax.set_xticks([0, 0.5, 1]); ax.tick_params(labelsize=6)
        ax = axes[1, c - 1]
        sc = shapes.frame["scale_min"].to_numpy()[tr]
        ax.bar(["1", "10", "30"], [int(((ga == c) & (sc == s)).sum()) for s in (1.0, 10.0, 30.0)], color="#888")
        ax.set_xlabel("scale (min)", fontsize=6); ax.tick_params(labelsize=6)
    fig.suptitle(f"Centred on the largest excursion, same sample, k = {k}: mean shape ± sd (top), scale mix (bottom) · ARI vs grid {res['aligned']['ari_vs_grid']:.2f}", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(figs, f"position_centred_clusters_k{k}.png"), dpi=130)
    plt.close(fig)
    # 3. twelve random members of the three largest grid clusters
    rng = np.random.default_rng(0)
    big = np.argsort(-np.bincount(g)[1:])[:3] + 1
    fig, axes = plt.subplots(3, 12, figsize=(16, 4.2), squeeze=False)
    for r, c in enumerate(big):
        idx = tr[g == c]
        pick = rng.choice(idx, size=min(12, len(idx)), replace=False)
        for j, row in enumerate(pick):
            ax = axes[r, j]
            ax.plot(x, shapes.vectors[row], lw=0.8, color="#333")
            fr = shapes.frame.iloc[row]
            ax.set_title(f"c{c} · {fr['scale_min']:g}m · {fr['raw_range_mv']:.2g} mV", fontsize=6)
            ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle("Twelve random members of the three largest grid clusters (normalised; scale and raw range above each)", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(figs, f"position_members_k{k}.png"), dpi=120)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--figs")
    ap.add_argument("--k", type=int, help="the cut for stage 2 (default: the proposal)")
    ap.add_argument("--reuse", action="store_true", help="read stage 1 from --out instead of recomputing it")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    from Working.training import shape as sh
    if a.reuse:
        shapes = sh.ShapeSet.load(os.path.join(a.out, "shapes", "shapes.npz"))
        tree = sh.ShapeTree.load(os.path.join(a.out, "tree"))
        with open(os.path.join(a.out, "stage1.json"), encoding="utf-8") as f:
            facts = json.load(f)
        k = a.k or facts["suggested_k"]
    else:
        shapes, tree, prop, facts = stage1(a.db, a.out)
        k = a.k or prop["suggested_k"]
    res = stage2(a.db, a.out, a.figs, shapes, tree, k)
    _say(json.dumps({k2: v for k2, v in res.items() if k2 not in ("pairs",)}, indent=1))


if __name__ == "__main__":
    main()
