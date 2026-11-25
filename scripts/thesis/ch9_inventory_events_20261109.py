"""Chapter 9 (9 Nov): every accepted span of the 2,959-span inventory measured with the tool's own event-shape block,
and the measured events grouped by shape. Read-only (database `mode=ro`, channel files memory-mapped); writes only
docs/thesis/data/ch9_inventory_20261109/ and two figures in docs/thesis/figures/new/.

In plain words: each accepted stretch of signal is measured the way Figure 5.2 shows (the onset of the fall, the
trough, the point where it has recovered half way), so every event gets a depth, a fall time and a half-recovery time.
Spans that are not single events are left out: region-length spans (over an hour), spans where no fall can be found,
and spans that hold more than one fall of at least half the main fall's depth. The single events are then cut to
their own shape (onset to half recovery, with a quarter of that length before), resampled to 100 points and
z-normalised, and grouped by Ward clustering into families, the method of the Library's groupings.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/ch9_inventory_events_20261109.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))

from Working.interrogation.event_shape import measure_events  # noqa: E402

SPANS = os.path.join(ROOT, "docs", "thesis", "data", "accepted_catalogue_20261109", "accepted_spans.csv")
OUT = os.path.join(ROOT, "docs", "thesis", "data", "ch9_inventory_20261109")
ORDER = ["M2_aug", "M2_concat", "M4", "LM", "CO", "MJu26a", "SH", "SO"]
MAX_SPAN_S = 3600.0
K_FAMILIES = 12
N_POINTS = 100
SEED = 20261109


def to_mv(units):
    return {"mV": 1.0, "uV": 0.001}.get(units or "V", 1000.0)


def n_falls(z, depth):
    """Falls of at least half the main depth inside the oriented span (a fall here is a trough with that prominence)."""
    from scipy.signal import find_peaks
    if len(z) < 5 or not np.isfinite(depth) or depth <= 0:
        return 0
    k = max(1, len(z) // 200)
    zs = np.convolve(z, np.ones(k) / k, mode="same") if k > 1 else z
    peaks, _ = find_peaks(-zs, prominence=0.5 * depth)
    return int(len(peaks))


def measure_all(spans, conn):
    recs = {int(r[0]): {"npy": r[1], "fs": float(r[2]), "units": r[3]} for r in
            conn.execute("SELECT id, npy_path, fs, units FROM recordings")}
    rows = []
    for rid, g in spans.groupby("recording_id"):
        rec = recs[int(rid)]
        x = np.load(os.path.join(ROOT, rec["npy"]), mmap_mode="r")
        g = g.sort_values("start_idx")
        keep = g[g["span_s"] <= MAX_SPAN_S]
        for _, r in g[g["span_s"] > MAX_SPAN_S].iterrows():
            rows.append({"event_id": r["event_id"], "dataset": r["dataset"], "status": "region"})
        if keep.empty:
            continue
        lo = int(max(0, keep["start_idx"].min()))
        hi = int(min(len(x), keep["end_idx"].max() + int(3600 * rec["fs"])))
        local = np.asarray(x[lo:hi], dtype=float)
        feats, detail = measure_events(local, (keep["start_idx"] - lo).tolist(), (keep["end_idx"] - lo).tolist(),
                                       rec["fs"], polarity="auto", to_mv=to_mv(rec["units"]))
        events = {e["index"]: e for e in detail["events"] if e is not None}
        for i, (_, r) in enumerate(keep.iterrows()):
            f = feats.iloc[i]
            row = {"event_id": r["event_id"], "dataset": r["dataset"], "recording_id": int(rid), "fs": rec["fs"],
                   "start_idx": int(r["start_idx"]), "end_idx": int(r["end_idx"]),
                   "acceptance_level": r["acceptance_level"]}
            if not np.isfinite(f["onset_idx"]):
                row["status"] = "no_fall"
                rows.append(row)
                continue
            e = events[i]
            nf = n_falls(e["snippet_mv"], e["depth"])
            row.update(status="multiple" if nf >= 2 else "single", n_falls=nf, polarity=int(f["polarity"]),
                       depth_mv=float(f["event_amplitude_mv"]), fall_s=float(f["event_width_s"]),
                       half_recovery_s=float(f["recovery_time_s"]), duration_s=float(f["duration_s"]),
                       onset_idx=int(f["onset_idx"]) + lo, extremum_idx=int(f["extremum_idx"]) + lo,
                       recovery_idx=(int(f["recovery_idx"]) + lo) if np.isfinite(f["recovery_idx"]) else None)
            rows.append(row)
    return pd.DataFrame(rows)


def shape_vectors(m, conn):
    recs = {int(r[0]): {"npy": r[1], "fs": float(r[2]), "units": r[3]} for r in
            conn.execute("SELECT id, npy_path, fs, units FROM recordings")}
    vecs, keep = [], []
    for idx, r in m.iterrows():
        rec = recs[int(r["recording_id"])]
        x = np.load(os.path.join(ROOT, rec["npy"]), mmap_mode="r")
        on, ex = int(r["onset_idx"]), int(r["extremum_idx"])
        end = int(r["recovery_idx"]) if pd.notna(r["recovery_idx"]) else ex + 2 * max(1, ex - on)
        length = max(end - on, 4)
        a, b = max(0, on - length // 4), min(len(x), end + 1)
        seg = np.asarray(x[a:b], dtype=float) * (1.0 if r["polarity"] < 0 else -1.0)
        if len(seg) < 5 or not np.all(np.isfinite(seg)) or np.std(seg) == 0:
            continue
        v = np.interp(np.linspace(0, len(seg) - 1, N_POINTS), np.arange(len(seg)), seg)
        vecs.append((v - v.mean()) / v.std())
        keep.append(idx)
    return np.array(vecs), keep


def main():
    from scipy.cluster.hierarchy import cophenet, fcluster, linkage
    from scipy.spatial.distance import pdist
    from sklearn.metrics import adjusted_rand_score
    os.makedirs(OUT, exist_ok=True)
    spans = pd.read_csv(SPANS)
    spans = spans[spans["thesis_scope"].astype(bool)]
    db = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    m = measure_all(spans, conn)
    m.to_csv(os.path.join(OUT, "measures.csv"), index=False)
    status = m["status"].value_counts().to_dict()
    single = m[m["status"] == "single"].copy()
    pct = lambda s, q: float(np.nanpercentile(s, q)) if s.notna().any() else float("nan")  # noqa: E731
    summ = []
    for d in ORDER + ["All"]:
        s = single if d == "All" else single[single["dataset"] == d]
        if s.empty:
            continue
        summ.append({"dataset": d, "n": len(s), "falls_pct": 100.0 * float((s["polarity"] < 0).mean()),
                     **{f"{c}_{q}": pct(s[c], q) for c in ("depth_mv", "fall_s", "half_recovery_s", "duration_s")
                        for q in (5, 50, 95)},
                     "not_recovered": int(s["half_recovery_s"].isna().sum())})
    summary = pd.DataFrame(summ)
    summary.to_csv(os.path.join(OUT, "summary_by_recording.csv"), index=False)

    X, idx = shape_vectors(single, conn)
    conn.close()
    Z = linkage(X, method="ward")
    coph = float(cophenet(Z, pdist(X))[0])
    labels = fcluster(Z, K_FAMILIES, criterion="maxclust")
    rng = np.random.default_rng(SEED)
    ari = {}
    for jit in (0.01, 0.02):
        Zj = linkage(X + rng.normal(0, jit, X.shape), method="ward")
        ari[str(jit)] = float(adjusted_rand_score(labels, fcluster(Zj, K_FAMILIES, criterion="maxclust")))
    fam = single.loc[idx].copy()
    fam["family"] = labels
    fam.to_csv(os.path.join(OUT, "families.csv"), index=False)
    np.save(os.path.join(OUT, "shape_vectors.npy"), X)
    np.save(os.path.join(OUT, "linkage.npy"), Z)
    per_family = []
    for f, g in fam.groupby("family"):
        per_family.append({"family": int(f), "n": len(g), "recordings": int(g["dataset"].nunique()),
                           "datasets": dict(g["dataset"].value_counts()),
                           "depth_median_mv": float(g["depth_mv"].median()),
                           "half_recovery_median_s": float(np.nanmedian(g["half_recovery_s"]))})
    out = {"spans": int(len(spans)), "status": {k: int(v) for k, v in status.items()}, "grouped": int(len(X)),
           "families": K_FAMILIES, "cophenetic": coph, "ari_jitter": ari, "per_family": per_family}
    with open(os.path.join(OUT, "grouping.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=int)
    pd.set_option("display.width", 220)
    print(json.dumps({k: v for k, v in out.items() if k != "per_family"}, indent=1))
    print(summary.round(2).to_string(index=False))
    for p in per_family:
        print(p)


if __name__ == "__main__":
    main()
