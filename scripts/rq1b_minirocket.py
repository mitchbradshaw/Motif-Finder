"""
rq1b_minirocket.py
==================
Round A_2, RQ1b / R4 (2026-10-20): a MiniRocket classifier of the researcher's own verdicts, interesting versus
not, trained on every span they judged and tested on recordings it never saw.

In plain words
--------------
Every span the researcher judged becomes one short picture of the signal: the span itself with a quarter of its
length of context on each side, in millivolts, squeezed to the same number of points. MiniRocket turns each picture
into a long list of "does this little pattern occur here" numbers (its fingerprint); a few plain measures ride along
(how long, how big, how noisy). A linear model then learns which fingerprints the researcher calls interesting. The
honest test is a recording the model never saw: train on four, ask about the fifth, and repeat for each.

The rules, each stated once
---------------------------
1. **Labels are the researcher's own judgements.** Direct adjudications and Library-review verdicts: interesting or
   seed (Q41) = 1, not interesting = 0. A verdict Review CARRIED to another run's detection of the same event
   (`adjudications.carried_from`) is that event again and is left out, or one judgement would count many times.
   Unsure is no answer; artifact is "kept out of training", as Review says. M4_aug (the held-out exam) and the reishi
   Fig2A pieces never enter. With `--with-windows`, the judged windows (the old 10-minute labels and the blind test,
   `WINDOW_SOURCES`) join as `kind = window`: they say something happened in a stretch, not which shape, so they can
   teach interesting-versus-not only (decision 3, 2026-10-18).
2. **One event once.** Event spans on one channel of one experiment that overlap by half the shorter are one event:
   kept once (an adjudication before a Library review) when they agree, dropped and counted when they disagree.
   Windows are never merged into events; a window judged twice (the same span) is kept once.
3. **Groups.** The recordings of one experiment are one group (`group_of`: a 10 Hz file and its `_fs2` copy), so a
   held-out recording is really unseen.
4. **The input.** The span plus `PAD` x its length of context on each side (clipped at the recording's ends), in mV
   (`Working.units.read_as_mv`), gaps of at most 5 % filled linearly (more and the span is left out), reduced to
   `LENGTH` points by bin means (or stretched linearly when shorter), z-normalised for MiniRocket. Side features:
   log10 of the span's duration (s), the window's peak-to-peak (mV), its sample-to-sample noise (mV, a robust
   median) and their ratio.
5. **The model.** MiniRocket (aeon, `Working.Catalogue.minirocket`'s set-up) fitted on the training rows only (it
   uses no label), its features beside the side features, standardised, and a ridge classifier with balanced class
   weights (the ROCKET papers' classifier). Probabilities by a logistic fit on out-of-fold scores (Platt).
6. **The test.** Leave one recording group out (the honest one), and five folds by channel. Balanced accuracy at
   the ridge's own cut, AUC, and precision / recall of "interesting", per held-out recording and pooled. Baselines on
   the same rows: the side features alone, MiniRocket alone; and, where the candidate-event tables know it, how many
   detector families agreed (context only: the classifier never sees it).

    python scripts/rq1b_minirocket.py train --real                    # the real database, read-only
    python scripts/rq1b_minirocket.py train --db <copy>.sqlite --out <dir>

Threads: 4 by default when run as a script (env RQ1B_THREADS). Writes only under `--out` (default
`<main checkout>/DATA/derived/models/rq1b_minirocket/<stamp>/`); the database is opened read-only.
"""

import os
import sys

if __name__ == "__main__":                      # cap the numeric libraries before numpy loads them (a shared machine)
    for _k in ("NUMBA_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ.setdefault(_k, os.environ.get("RQ1B_THREADS", "4"))

import argparse
import collections
import datetime
import glob
import importlib.util
import json
import re
import sqlite3
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from Working.Catalogue.minirocket import MAX_GAP_FRAC, MIN_LENGTH, znormalise  # noqa: E402
from Working.config import HELD_OUT_RECORDING_FILE  # noqa: E402
from Working.database import queries as _queries  # noqa: E402
from Working.discovery.spans import absolute_bounds  # noqa: E402
from Working.units import read_as_mv  # noqa: E402


def _guard():
    spec = importlib.util.spec_from_file_location("_rq1b_mr_real_db_guard",
                                                  os.path.join(ROOT, "scripts", "backfill_seed_entry_ids.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GUARD = _guard()
DATA_ROOT = GUARD.main_checkout()

EXCLUDED_FILES = (HELD_OUT_RECORDING_FILE, "Fig2A_dt0p1.csv")
POSITIVE = ("interesting", "seed")
NEGATIVE = ("not_interesting",)
EVENT_ANNOTATION_SOURCES = ("library_review",)
WINDOW_SOURCES = ("imported_10min", "blind_test_review")
SOURCE_PREFERENCE = {"adjudication": 0, "library_review": 1, "window": 2}
SAME_EVENT_SHARE = 0.5
PAD = 0.25
LENGTH = 512
SIDE = ("duration_s", "p2p_mv", "noise_mv", "snr")
DEFAULT_N_FEATURES = 9_996
ALPHAS = np.logspace(-3, 3, 10)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


# ── rule 1: labels ──────────────────────────────────────────────────────────

def group_of(source_file):
    """Rule 3: the experiment a recording file belongs to — its stem without a resampling suffix (`_fs2`, `_fs1`,
    `_fs0p8`), so `L_LM_Jul_26_J_raw.mat` and `L_LM_Jul_26_J_raw_fs2.mat` are one group."""
    stem = os.path.splitext(os.path.basename(str(source_file)))[0]
    return re.sub(r"_fs\d+(p\d+)?$", "", stem)


def _label(verdict, counts):
    if verdict in POSITIVE:
        return 1
    if verdict in NEGATIVE:
        return 0
    counts[str(verdict)] += 1
    return None


def _recordings(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(recordings)")}
    units = "units" if "units" in cols else "NULL"
    return {int(r[0]): {"source_file": r[1], "channel": int(r[2]), "fs": float(r[3]), "n_samples": int(r[4]),
                        "npy_path": r[5], "units": r[6]}
            for r in conn.execute(f"SELECT id, source_file, channel, fs, n_samples, npy_path, {units} FROM recordings")}


def collect_labels(conn, *, with_windows=False):
    """Rule 1: one row per judged span, ``(source, kind, ref, recording_id, source_file, group, channel, fs, units,
    start, end, t0, t1, verdict, label)``, and the counts of what was left out and why."""
    recs = _recordings(conn)
    counts = collections.Counter()
    rows = []

    def add(rid, s, e, verdict, source, kind, ref):
        rec = recs.get(int(rid))
        if rec is None:
            counts["no_recording"] += 1
            return
        if rec["source_file"] in EXCLUDED_FILES:
            counts["held_out_or_excluded_recording"] += 1
            return
        lab = _label(verdict, counts)
        if lab is None:
            return
        if int(e) <= int(s):
            counts["empty_span"] += 1
            return
        rows.append({"source": source, "kind": kind, "ref": ref, "recording_id": int(rid),
                     "source_file": rec["source_file"], "group": group_of(rec["source_file"]),
                     "channel": rec["channel"], "fs": rec["fs"], "units": rec["units"], "start": int(s),
                     "end": int(e), "t0": int(s) / rec["fs"], "t1": int(e) / rec["fs"], "verdict": verdict,
                     "label": lab})

    for adj_id, verdict, carried, rid, s, e, s0 in conn.execute(
            f"SELECT a.id, a.verdict, a.carried_from, r.recording_id, d.start_idx, d.end_idx, r.span_start "
            f"FROM adjudications a JOIN detections d ON d.id = a.detection_id JOIN runs r ON r.id = d.run_id "
            f"WHERE {_queries.not_surrogate('r')}").fetchall():
        if carried is not None:
            counts["carried"] += 1
            continue
        a, b = absolute_bounds(s, e, s0)
        add(rid, a, b, verdict, "adjudication", "event", f"adjudication:{int(adj_id)}")
    for aid, rid, s, e, verdict, source in conn.execute(
            "SELECT id, recording_id, start_idx, end_idx, verdict, source FROM annotations "
            "WHERE deleted_at IS NULL").fetchall():
        if source in EVENT_ANNOTATION_SOURCES:
            add(rid, s, e, verdict, "library_review", "event", f"annotation:{int(aid)}")
        elif with_windows and source in WINDOW_SOURCES:
            add(rid, s, e, verdict, "window", "window", f"annotation:{int(aid)}")
    cols = ["source", "kind", "ref", "recording_id", "source_file", "group", "channel", "fs", "units", "start", "end",
            "t0", "t1", "verdict", "label"]
    return pd.DataFrame(rows, columns=cols), dict(counts)


# ── rule 2: one event once ──────────────────────────────────────────────────

def _clusters(t0, t1):
    """Union-find over spans overlapping by `SAME_EVENT_SHARE` of the shorter (spans sorted by start)."""
    n = len(t0)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    order = np.argsort(t0, kind="stable")
    for a_pos, i in enumerate(order):
        for j in order[a_pos + 1:]:
            if t0[j] >= t1[i]:
                break
            inter = min(t1[i], t1[j]) - max(t0[i], t0[j])
            if inter > 0 and inter >= SAME_EVENT_SHARE * min(t1[i] - t0[i], t1[j] - t0[j]):
                parent[find(int(i))] = find(int(j))
    out = collections.defaultdict(list)
    for i in range(n):
        out[find(i)].append(i)
    return list(out.values())


def dedupe(df):
    """Rule 2. Returns ``(rows kept, counts)``."""
    counts = collections.Counter()
    keep = []
    events = df[df["kind"] == "event"]
    for _key, g in events.groupby(["group", "channel"], sort=False):
        for members in _clusters(g["t0"].to_numpy(float), g["t1"].to_numpy(float)):
            rows = g.iloc[members]
            if rows["label"].nunique() > 1:
                counts["conflicting_events"] += len(rows)
                continue
            best = rows.assign(_p=rows["source"].map(SOURCE_PREFERENCE), _len=rows["t1"] - rows["t0"]) \
                .sort_values(["_p", "_len"]).index[0]
            keep.append(best)
            counts["duplicate_events"] += len(rows) - 1
    windows = df[df["kind"] == "window"]
    for _key, g in windows.groupby(["group", "channel", "start", "end"], sort=False):
        if g["label"].nunique() > 1:
            counts["conflicting_windows"] += len(g)
            continue
        keep.append(g.index[0])
        counts["duplicate_windows"] += len(g) - 1
    return df.loc[sorted(keep)].reset_index(drop=True), dict(counts)


# ── rule 4: the input ───────────────────────────────────────────────────────

def resample(x, n):
    """`x` reduced to `n` points by bin means, or stretched to `n` linearly when shorter."""
    x = np.asarray(x, dtype=float)
    m = len(x)
    if m == n:
        return x.copy()
    if m > n:
        edges = np.round(np.linspace(0, m, n + 1)).astype(np.int64)
        return np.add.reduceat(x, edges[:-1]) / np.diff(edges)
    return np.interp(np.linspace(0, m - 1, n), np.arange(m), x)


def _array(rec, cache):
    p = rec["npy_path"]
    path = p if os.path.isabs(p) else os.path.join(DATA_ROOT, p)
    if path not in cache:
        cache[path] = np.load(path, mmap_mode="r")
    return cache[path]


def extract(conn, rows, *, length=LENGTH, pad=PAD):
    """Rule 4. ``(M, side, keep)``: one `length`-point row per span (zeros where left out), the side features, and
    which spans could be read."""
    recs = _recordings(conn)
    cache = {}
    M = np.zeros((len(rows), int(length)), dtype=np.float64)
    keep = np.ones(len(rows), dtype=bool)
    side = []
    for i, r in enumerate(rows.itertuples(index=False)):
        rec = recs[int(r.recording_id)]
        factor, _note = read_as_mv(rec["units"])
        s, e = int(r.start), int(r.end)
        span = max(1, e - s)
        p = int(round(pad * span))
        a, b = max(0, s - p), min(rec["n_samples"], e + p)
        x = np.asarray(_array(rec, cache)[a:b], dtype=np.float64) * factor
        finite = np.isfinite(x)
        if x.size < 2 or (1.0 - finite.mean()) > MAX_GAP_FRAC:
            keep[i] = False
            side.append({k: np.nan for k in SIDE})
            continue
        if not finite.all():
            k = np.arange(x.size)
            x[~finite] = np.interp(k[~finite], k[finite], x[finite])
        M[i] = resample(x, length)
        p2p = float(np.ptp(x))
        noise = float(np.median(np.abs(np.diff(x)))) * 1.4826 / np.sqrt(2.0) if x.size > 1 else 0.0
        side.append({"duration_s": span / rec["fs"], "p2p_mv": p2p, "noise_mv": noise,
                     "snr": p2p / max(noise, 1e-9)})
    return M, pd.DataFrame(side, columns=list(SIDE)), keep


def side_matrix(side):
    return np.log10(np.maximum(side[list(SIDE)].to_numpy(dtype=float), 1e-9)).astype(np.float32)


# ── rule 5: the model ───────────────────────────────────────────────────────

def _minirocket_fit(M, n_features, seed):
    """`Working.Catalogue.minirocket.fingerprint_matrix`'s set-up, keeping the fitted transform for the model."""
    import numba
    from aeon.transformations.collection.convolution_based import MiniRocket
    if M.shape[1] < MIN_LENGTH:
        raise ValueError(f"MiniRocket needs at least {MIN_LENGTH} points")
    Z, _flat = znormalise(np.asarray(M, dtype=float))
    mr = MiniRocket(n_kernels=int(n_features), max_dilations_per_kernel=32,
                    n_jobs=int(numba.config.NUMBA_NUM_THREADS), random_state=int(seed))
    state = np.random.get_state()
    try:
        mr.fit(Z.astype(np.float32)[:, None, :])
    finally:
        np.random.set_state(state)
    return mr


def _minirocket_transform(mr, M, chunk=4_096):
    Z, _flat = znormalise(np.asarray(M, dtype=float))
    X = Z.astype(np.float32)[:, None, :]
    state = np.random.get_state()
    try:
        return np.concatenate([np.asarray(mr.transform(X[i:i + chunk]), dtype=np.float32)
                               for i in range(0, len(X), chunk)], axis=0)
    finally:
        np.random.set_state(state)


def _design(model, M, side):
    parts = []
    if model["minirocket"] is not None:
        parts.append(_minirocket_transform(model["minirocket"], M))
    if model["use_side"]:
        parts.append(side_matrix(side))
    return np.hstack(parts) if len(parts) > 1 else parts[0]


def _fit(rows, M, side, *, n_features, seed, features):
    from sklearn.linear_model import RidgeClassifierCV
    from sklearn.preprocessing import StandardScaler
    y = rows["label"].to_numpy(dtype=int)
    model = {"minirocket": _minirocket_fit(M, n_features, seed) if features in ("both", "minirocket") else None,
             "use_side": features in ("both", "side"), "features": features, "n_features": int(n_features),
             "seed": int(seed), "length": int(M.shape[1]), "pad": PAD, "side": list(SIDE), "platt": None}
    X = _design(model, M, side)
    model["scaler"] = StandardScaler().fit(X)
    model["ridge"] = RidgeClassifierCV(alphas=ALPHAS, class_weight="balanced").fit(model["scaler"].transform(X), y)
    return model


def decision(model, M, side):
    """The ridge's score per span: above 0 is "interesting"."""
    return np.asarray(model["ridge"].decision_function(model["scaler"].transform(_design(model, M, side))),
                      dtype=float)


def probability(model, M, side):
    d = decision(model, M, side)
    a, b = model["platt"] if model.get("platt") else (1.0, 0.0)
    return 1.0 / (1.0 + np.exp(-(a * d + b)))


def _platt(scores, y):
    from sklearn.linear_model import LogisticRegression
    lr = LogisticRegression(C=1e6, max_iter=1000).fit(np.asarray(scores, float)[:, None], np.asarray(y, int))
    return float(lr.coef_[0, 0]), float(lr.intercept_[0])


def fit_model(rows, M, side, *, n_features=DEFAULT_N_FEATURES, seed=0, features="both", oof=None):
    """The final model on every row given. Its probabilities come from `oof` (out-of-fold scores and their labels,
    as `evaluate` returns them), else from a three-fold grouped run here."""
    model = _fit(rows, M, side, n_features=n_features, seed=seed, features=features)
    if oof is None:
        res = evaluate(rows, M, side, split="channel", n_folds=3, n_features=n_features, seed=seed,
                       features=features)
        oof = res["oof"]
    model["platt"] = _platt(oof["decision"], oof["label"])
    return model


def save_model(model, where):
    import joblib
    os.makedirs(str(where), exist_ok=True)
    path = os.path.join(str(where), "model.joblib")
    joblib.dump(model, path)
    return path


def load_model(path):
    import joblib
    return joblib.load(path)


# ── rule 6: the test ────────────────────────────────────────────────────────

def _metrics(y, d):
    from sklearn.metrics import roc_auc_score
    y = np.asarray(y, int)
    pred = (np.asarray(d) > 0).astype(int)
    tp, fp = int(((pred == 1) & (y == 1)).sum()), int(((pred == 1) & (y == 0)).sum())
    fn, tn = int(((pred == 0) & (y == 1)).sum()), int(((pred == 0) & (y == 0)).sum())
    rec1 = tp / (tp + fn) if tp + fn else float("nan")
    rec0 = tn / (tn + fp) if tn + fp else float("nan")
    prec = tp / (tp + fp) if tp + fp else float("nan")
    both = len(set(y.tolist())) == 2
    return {"n": int(len(y)), "interesting": int(y.sum()), "balanced_accuracy": float(np.nanmean([rec1, rec0])),
            "auc": float(roc_auc_score(y, d)) if both else float("nan"), "precision": float(prec),
            "recall": float(rec1), "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def evaluate(rows, M, side, *, split="recording", n_folds=5, n_features=DEFAULT_N_FEATURES, seed=0,
             features="both", test_mask=None):
    """Rule 6: out-of-fold scores. `split = recording` holds out one group at a time (a group whose test rows are
    one class only is used for training, never as a test); `split = channel` is grouped folds over
    (group, channel). `test_mask` limits which rows are ever scored (events, when windows help train)."""
    from sklearn.model_selection import GroupKFold
    rows = rows.reset_index(drop=True)
    y = rows["label"].to_numpy(dtype=int)
    test_ok = np.ones(len(rows), dtype=bool) if test_mask is None else np.asarray(test_mask, dtype=bool)
    if split == "recording":
        folds = []
        for g in sorted(rows["group"].unique()):
            te = np.flatnonzero((rows["group"] == g).to_numpy() & test_ok)
            if len(te) and len(set(y[te].tolist())) == 2:
                folds.append((g, np.flatnonzero((rows["group"] != g).to_numpy()), te))
    else:
        keys = (rows["group"].astype(str) + ":" + rows["channel"].astype(str)).to_numpy()
        gkf = GroupKFold(n_splits=min(int(n_folds), len(set(keys))))
        folds = [(f"fold {k + 1}", tr, te[test_ok[te]]) for k, (tr, te) in enumerate(gkf.split(rows, y, keys))]
    out, oof = [], []
    for name, tr, te in folds:
        if len(set(y[tr].tolist())) < 2 or not len(te):
            continue
        t0 = time.perf_counter()
        model = _fit(rows.iloc[tr], M[tr], side.iloc[tr], n_features=n_features, seed=seed, features=features)
        d = decision(model, M[te], side.iloc[te])
        m = _metrics(y[te], d)
        m.update(held_out=name, n_train=int(len(tr)), seconds=round(time.perf_counter() - t0, 1))
        out.append(m)
        oof.append(pd.DataFrame({"row": te, "decision": d, "label": y[te], "fold": name}))
    oof = pd.concat(oof, ignore_index=True) if oof else pd.DataFrame(columns=["row", "decision", "label", "fold"])
    return {"folds": out, "pooled": _metrics(oof["label"], oof["decision"]) if len(oof) else {}, "oof": oof}


# ── the run ─────────────────────────────────────────────────────────────────

def _agreement_of(detection_ids):
    """`{detection_id: n_agree}` from every candidate-event table on disk (anchors only): context, never a feature."""
    out = {}
    want = set(int(d) for d in detection_ids)
    for p in glob.glob(os.path.join(DATA_ROOT, "DATA", "derived", "candidate_events", "*", "events.parquet")):
        t = pd.read_parquet(p, columns=["anchor_detection_id", "n_agree"])
        t = t[t["anchor_detection_id"].isin(want)]
        out.update(zip(t["anchor_detection_id"].astype(int), t["n_agree"].astype(int)))
    return out


def _windows_sample(df, per_class, seed):
    w = df[df["kind"] == "window"]
    parts = [g.sample(n=min(per_class, len(g)), random_state=seed) for _lab, g in w.groupby("label")]
    return pd.concat([df[df["kind"] == "event"]] + parts).sort_index()


def train(conn, out_dir, *, n_features=DEFAULT_N_FEATURES, length=LENGTH, with_windows=True,
          windows_per_class=1500, seed=0, log=print):
    """Every variant, the comparison, the chosen model saved with its report. Returns the manifest."""
    t_start = time.perf_counter()
    labels, left_out = collect_labels(conn, with_windows=with_windows)
    rows, dup = dedupe(labels)
    if with_windows:
        rows = _windows_sample(rows, windows_per_class, seed).reset_index(drop=True)
    log(f"labels: {len(labels)} judged spans -> {len(rows)} after one-event-once (+ window sample); left out {left_out}; {dup}")
    M, side, keep = extract(conn, rows, length=length)
    rows, M, side = rows[keep].reset_index(drop=True), M[keep], side[keep].reset_index(drop=True)
    log(f"read {len(rows)} spans ({int((~keep).sum())} left out for gaps)")
    ev = (rows["kind"] == "event").to_numpy()
    E_rows, E_M, E_side = rows[ev].reset_index(drop=True), M[ev], side[ev].reset_index(drop=True)
    variants = {}

    def run(name, r, m, s, **kw):
        t = time.perf_counter()
        res = {"recording": evaluate(r, m, s, split="recording", n_features=n_features, seed=seed, **kw),
               "channel": evaluate(r, m, s, split="channel", n_features=n_features, seed=seed, **kw)}
        variants[name] = res
        log(f"{name}: held-out recordings {_short(res['recording']['pooled'])}; held-out channels "
            f"{_short(res['channel']['pooled'])} ({time.perf_counter() - t:.0f} s)")
        return res
    run("events · MiniRocket + side", E_rows, E_M, E_side, features="both")
    run("events · side only", E_rows, E_M, E_side, features="side")
    run("events · MiniRocket only", E_rows, E_M, E_side, features="minirocket")
    if with_windows and (~ev).any():
        run("events + windows · MiniRocket + side", rows, M, side, features="both", test_mask=ev)
    # the detector-agreement context on the same held-out event rows (queue items only)
    det_ids, adj_to_det = _adjudicated_detections(conn, E_rows)
    context = _agreement_context(E_rows, det_ids, adj_to_det,
                                 variants["events · MiniRocket + side"]["recording"]["oof"])
    # choose: the best pooled AUC on held-out recordings among the full-feature variants
    full = [k for k in variants if "MiniRocket + side" in k]
    best = max(full, key=lambda k: variants[k]["recording"]["pooled"].get("auc", 0))
    use_rows, use_M, use_side = (rows, M, side) if best.startswith("events + windows") else (E_rows, E_M, E_side)
    model = fit_model(use_rows, use_M, use_side, n_features=n_features, seed=seed, features="both",
                      oof=variants[best]["recording"]["oof"])
    model.update({"variant": best, "trained_on": int(len(use_rows)), "created_at": _now(),
                  "label_rule": "interesting or seed = 1, not interesting = 0; unsure, artifact, carried copies out",
                  "input_rule": f"span + {PAD:g} x its length each side, mV, {length} points by bin means, "
                                f"z-normalised; side: {', '.join(SIDE)} (log10)"})
    os.makedirs(out_dir, exist_ok=True)
    save_model(model, out_dir)
    preds = rows.copy()
    preds["probability_final_model"] = probability(model, M, side)
    for name, res in variants.items():
        o = res["recording"]["oof"]
        if not len(o):
            continue
        rows_of = o["row"].to_numpy(dtype=int)                  # positions in `rows`, or in the event rows
        key = rows_of if name.startswith("events + windows") else np.flatnonzero(ev)[rows_of]
        preds.loc[key, f"held-out score · {name}"] = o["decision"].to_numpy()
    preds.to_parquet(os.path.join(out_dir, "predictions.parquet"), index=False)
    manifest = {"created_at": _now(), "best": best, "n_features": int(n_features), "length": int(length),
                "seed": int(seed), "threads": os.environ.get("NUMBA_NUM_THREADS"),
                "labels": {"judged_spans": int(len(labels)), "used": int(len(rows)), "events": int(ev.sum()),
                           "windows": int((~ev).sum()),
                           "left_out": left_out, "dedupe": dup, "gaps": int((~keep).sum()),
                           "by_group": _by_group(rows)},
                "variants": {k: {s: {"pooled": v[s]["pooled"], "folds": v[s]["folds"]} for s in v}
                             for k, v in variants.items()},
                "agreement_context": context, "seconds": round(time.perf_counter() - t_start, 1),
                "model": os.path.join(out_dir, "model.joblib"), "platt": model["platt"],
                "versions": _versions()}
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1, default=float)
    return manifest


def _adjudicated_detections(conn, rows):
    ids = [int(r.split(":")[1]) for r in rows["ref"] if r.startswith("adjudication:")]
    out = {}
    for i in range(0, len(ids), 400):
        chunk = ids[i:i + 400]
        out.update({int(a): int(d) for a, d in conn.execute(
            f"SELECT id, detection_id FROM adjudications WHERE id IN ({','.join('?' * len(chunk))})", chunk)})
    return list(out.values()), out


def _agreement_context(E_rows, det_ids, adj_to_det, oof):
    agree = _agreement_of(det_ids)
    from sklearn.metrics import roc_auc_score
    o = oof.copy()
    refs = E_rows["ref"].to_numpy()[o["row"].to_numpy()]
    o["n_agree"] = [agree.get(adj_to_det.get(int(r.split(":")[1]), -1)) if r.startswith("adjudication:") else None
                    for r in refs]
    o["group"] = E_rows["group"].to_numpy()[o["row"].to_numpy()]
    o = o.dropna(subset=["n_agree"])
    out = {"rows_with_agreement": int(len(o))}
    for g, h in list(o.groupby("group")) + [("all", o)]:
        if h["label"].nunique() == 2:
            out[g] = {"n": int(len(h)), "auc_agreement": float(roc_auc_score(h["label"], h["n_agree"])),
                      "auc_minirocket": float(roc_auc_score(h["label"], h["decision"]))}
    return out


def _by_group(rows):
    return {g: {"events": int((h["kind"] == "event").sum()), "windows": int((h["kind"] == "window").sum()),
                "interesting": int(h["label"].sum()), "not": int((h["label"] == 0).sum())}
            for g, h in rows.groupby("group")}


def _short(p):
    if not p:
        return "-"
    return f"balanced accuracy {p['balanced_accuracy']:.2f}, AUC {p['auc']:.2f} (n {p['n']})"


def _versions():
    out = {}
    for m in ("aeon", "sklearn", "numpy", "numba"):
        try:
            out[m] = __import__(m).__version__
        except Exception:                        # pragma: no cover - a version is a note, never a failure
            out[m] = None
    return out


def main(argv=None, real=None):
    real = real or GUARD.REAL_DB
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--db")
    t.add_argument("--real", action="store_true")
    t.add_argument("--out")
    t.add_argument("--n-features", type=int, default=DEFAULT_N_FEATURES)
    t.add_argument("--length", type=int, default=LENGTH)
    t.add_argument("--no-windows", action="store_true")
    t.add_argument("--windows-per-class", type=int, default=1500)
    t.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    if a.db and a.real:
        ap.error("give --db or --real, not both")
    db = real if a.real else a.db
    if not db:
        ap.error("name a database with --db, or pass --real")
    if not a.real and GUARD.is_the_real_database(db, real):
        ap.error(f"{db} is the real database; pass --real")
    conn = GUARD._read_only(db)
    conn.row_factory = sqlite3.Row
    out = a.out or os.path.join(DATA_ROOT, "DATA", "derived", "models", "rq1b_minirocket",
                                datetime.datetime.now().strftime("%Y%m%d-%H%M"))
    try:
        manifest = train(conn, out, n_features=a.n_features, length=a.length, with_windows=not a.no_windows,
                         windows_per_class=a.windows_per_class, seed=a.seed)
    finally:
        conn.close()
    print(json.dumps({"out": out, "best": manifest["best"], "seconds": manifest["seconds"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
