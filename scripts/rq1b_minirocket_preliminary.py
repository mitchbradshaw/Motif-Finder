"""
rq1b_minirocket_preliminary.py
==============================
A PRELIMINARY interesting-vs-not classifier on the researcher's event-level verdicts from one or more blind Review
queues of candidate events (queue 25: RQ1b candidate events, M2_aug_concat_fs1.mat, stratified sample, seed 0),
compared on the same items with the detector-agreement count (`n_agree` in each recording's candidate-event table).

Read-only on the database (sqlite `mode=ro`). Writes only a results JSON and one ROC figure under
docs/rq_roundA_2/findings/. Refuses the held-out recording (`Working.config.HELD_OUT_RECORDING_FILE`).

    python scripts/rq1b_minirocket_preliminary.py                          # queue 25, 600 s windows
    python scripts/rq1b_minirocket_preliminary.py --queues 25 28           # several queues, pooled
    python scripts/rq1b_minirocket_preliminary.py --length 200 --no-figure # sensitivity

Method, each step once:
1. Items: a queue's `filters_json.detection_ids`. Each detection is found in a candidate-event table
   (DATA/derived/candidate_events/*/members.parquet) for its channel-absolute span, recording and its event's
   `n_agree`; a stratum is read from a `sample*/sample.parquet` beside the table when there is one. A detection in
   no table is left out and counted (it has no agreement score to compare against).
2. Labels: the latest adjudication on each detection; interesting = 1, not_interesting = 0; unsure, artifact, seed
   and anything else are left out.
3. Windows: `--length` SECONDS centred on the detection's midpoint, sliced at the recording's own rate (from
   `recordings.fs`), shifted inside the recording at its ends, then resampled to `--fs` (default 1 Hz;
   `scipy.signal.resample_poly`, so a 2 Hz recording is low-passed before it is halved) so every window has the
   same number of samples, as MiniRocket needs. A 1 Hz recording at `--fs 1` is not touched. Windows with > 5 %
   non-finite samples are left out (minirocket.repair_gaps); each is z-normalised (minirocket does it).
4. Split: blocked by time within each dataset (source file; its channels share one time axis), `--folds`
   contiguous blocks per dataset; fold k tests block k of every dataset. Training items of the same dataset within
   `--gap` seconds of the test block are dropped. Every item gets one out-of-fold score. A forward check (the first
   80 % of each dataset's time trains, the last 20 % tests) is reported beside it.
5. With two or more datasets: leave-one-dataset-out (train on every other dataset, test on the one left out),
   per dataset and pooled.
6. MiniRocket (Working/Catalogue/minirocket.fingerprint_matrix, fitted on the training windows only) then
   standardise + RidgeClassifierCV, refitted per fold.
7. Baselines on the same items: n_agree (no training) and the detection's own length in seconds (no training).
8. Combination: logistic regression on [MiniRocket score, n_agree], the MiniRocket score for the training items
   taken from an inner blocked CV inside the training fold.
9. Intervals: paired bootstrap over items (2,000 draws) for each AUC, balanced accuracy and the AUC differences.
"""
import argparse
import glob
import json
import os
import sqlite3
import sys
import time
from fractions import Fraction

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from Working.Catalogue import minirocket  # noqa: E402
from Working.config import HELD_OUT_RECORDING_FILE  # noqa: E402

DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite")
TABLES = os.path.join(ROOT, "DATA", "derived", "candidate_events")
OUT_DIR = os.path.join(ROOT, "docs", "rq_roundA_2", "findings")
SEED = 0


def _connect():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def _queue_detections(con, queue_ids):
    ids, names = [], {}
    for q in queue_ids:
        row = con.execute("select name, filters_json from review_queues where id=?", (int(q),)).fetchone()
        if row is None:
            raise SystemExit(f"no review queue {q}")
        names[int(q)] = row[0]
        f = json.loads(row[1] or "{}")
        if "detection_ids" not in f:
            raise SystemExit(f"queue {q} lists no detection_ids (filters: {sorted(f)}); only detection queues are read")
        ids += [(int(q), int(d)) for d in f["detection_ids"]]
    return pd.DataFrame(ids, columns=["queue_id", "detection_id"]), names


def _locate(det_ids):
    """Every candidate-event table's rows for `det_ids`: span, recording, event, n_agree, stratum, source file."""
    want = set(det_ids)
    parts = []
    for where in sorted(glob.glob(os.path.join(TABLES, "*", "meta.json"))):
        where = os.path.dirname(where)
        with open(os.path.join(where, "meta.json"), encoding="utf-8") as fh:
            source = json.load(fh).get("source_file")
        if source == HELD_OUT_RECORDING_FILE:
            continue
        m = pd.read_parquet(os.path.join(where, "members.parquet"),
                            columns=["event_id", "detection_id", "recording_id", "start", "end"])
        m = m[m.detection_id.isin(want)]
        if not len(m):
            continue
        ev = pd.read_parquet(os.path.join(where, "events.parquet"), columns=["event_id", "n_agree"])
        m = m.merge(ev, on="event_id", how="left")
        strata = [pd.read_parquet(p, columns=["detection_id", "stratum"])
                  for p in glob.glob(os.path.join(where, "sample*", "sample.parquet"))]
        if strata:
            m = m.merge(pd.concat(strata).drop_duplicates("detection_id"), on="detection_id", how="left")
        m["table"] = os.path.basename(where)
        m["source_file"] = source
        parts.append(m)
    if not parts:
        return pd.DataFrame(columns=["detection_id"])
    out = pd.concat(parts, ignore_index=True)
    if "stratum" not in out:
        out["stratum"] = None
    return out.drop_duplicates("detection_id")


def load_items(queue_ids):
    con = _connect()
    q, names = _queue_detections(con, queue_ids)
    adj = pd.read_sql("select detection_id, verdict, created_at, id from adjudications", con)
    adj = adj[adj.detection_id.isin(q.detection_id)].sort_values(["created_at", "id"]).groupby("detection_id").tail(1)
    rec = pd.read_sql("select id as recording_id, source_file as rec_source, channel, fs, n_samples, npy_path "
                      "from recordings", con)
    con.close()
    s = q.drop_duplicates("detection_id").merge(adj[["detection_id", "verdict"]], on="detection_id", how="left")
    counts = {"queues": {str(k): v for k, v in names.items()},
              "verdicts": s.verdict.fillna("unjudged").value_counts().to_dict()}
    s = s.merge(_locate(s.detection_id), on="detection_id", how="left")
    counts["not_in_any_table"] = int(s.recording_id.isna().sum())
    s = s[s.recording_id.notna()].merge(rec, on="recording_id", how="left")
    if (s.rec_source == HELD_OUT_RECORDING_FILE).any():
        raise SystemExit(f"refused: an item sits on the held-out recording {HELD_OUT_RECORDING_FILE}")
    s = s[s.verdict.isin(["interesting", "not_interesting"])].copy()
    s["y"] = (s.verdict == "interesting").astype(int)
    s["length_s"] = (s.end - s.start) / s.fs
    s["mid"] = (s.start + s.end) // 2
    s["t_s"] = s.mid / s.fs                      # seconds on the dataset's own time axis
    s["stratum"] = s.stratum.fillna("unknown")
    counts["used_by_dataset"] = s.groupby("rec_source").y.agg(["size", "sum"]).rename(
        columns={"size": "n", "sum": "interesting"}).to_dict("index")
    # one canonical order: MiniRocket's biases come from randomly chosen training rows, so row order moves the
    # third decimal; this keeps a re-run independent of the order the queues list their items in
    s = s.sort_values(["rec_source", "recording_id", "start", "detection_id"])
    return s.reset_index(drop=True), counts


def windows(s, length_s, fs_out):
    n_out = int(round(length_s * fs_out))
    M = np.empty((len(s), n_out))
    cache = {}
    for i, r in enumerate(s.itertuples()):
        if r.npy_path not in cache:
            cache[r.npy_path] = np.load(os.path.join(ROOT, r.npy_path), mmap_mode="r")
        x = cache[r.npy_path]
        n = int(round(length_s * r.fs))
        a = min(max(int(r.mid) - n // 2, 0), len(x) - n)
        w = np.asarray(x[a:a + n], dtype=float)
        ratio = Fraction(fs_out / r.fs).limit_denominator(1000)
        if ratio != 1:
            from scipy.signal import resample_poly
            w = resample_poly(w, ratio.numerator, ratio.denominator)
        if len(w) != n_out:                    # an inexact rate: trim or edge-pad to the common length
            w = np.pad(w[:n_out], (0, max(0, n_out - len(w))), mode="edge")
        M[i] = w
    M, keep, _ = minirocket.repair_gaps(M)
    return M, keep


def folds_blocked(t, src, n_folds, gap):
    """(train_idx, test_idx) per fold: fold k tests time block k of every dataset; training items of the same
    dataset within `gap` seconds of that block are dropped."""
    lo, hi = np.empty(len(t)), np.empty(len(t))
    fold = np.empty(len(t), int)
    for g in np.unique(src):
        sel = src == g
        edges = np.linspace(t[sel].min(), t[sel].max() + 1, n_folds + 1)
        k = np.clip(np.searchsorted(edges, t[sel], side="right") - 1, 0, n_folds - 1)
        fold[sel], lo[sel], hi[sel] = k, edges[k], edges[k + 1]
    out = []
    for k in range(n_folds):
        test = np.flatnonzero(fold == k)
        if not len(test):
            continue
        near = np.zeros(len(t), bool)
        for g in np.unique(src[test]):
            sel = src == g
            blo, bhi = lo[test][src[test] == g][0], hi[test][src[test] == g][0]
            near |= sel & (t >= blo - gap) & (t < bhi + gap)
        out.append((np.flatnonzero(~near & (fold != k)), test))
    return out


def ridge_scores(Xtr, ytr, Xte):
    from sklearn.linear_model import RidgeClassifierCV
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    clf = make_pipeline(StandardScaler(), RidgeClassifierCV(alphas=np.logspace(-1, 5, 13)))
    clf.fit(Xtr, ytr)
    return clf.decision_function(Xte)


def _fingerprints(Mfit, Mapply):
    """MiniRocket fitted on `Mfit` only, applied to both (each window z-normalised, as minirocket does)."""
    both = np.vstack([Mfit, Mapply])
    mask = np.r_[np.ones(len(Mfit), bool), np.zeros(len(Mapply), bool)]
    F = minirocket.fingerprint_matrix(both, fit_mask=mask, seed=SEED)
    return F[mask], F[~mask]


def fit_predict(M, y, agree, t, src, train, test, gap, inner_folds=4):
    """MiniRocket score and MiniRocket+agreement probability for `test`, fitted on `train` only."""
    F, Fte = _fingerprints(M[train], M[test])
    mr_test = ridge_scores(F, y[train], Fte)
    inner = np.full(len(train), np.nan)
    for itr, ite in folds_blocked(t[train], src[train], inner_folds, gap):
        if len(np.unique(y[train][itr])) < 2 or len(ite) == 0:
            continue
        inner[ite] = ridge_scores(F[itr], y[train][itr], F[ite])
    ok = np.isfinite(inner)
    from sklearn.linear_model import LogisticRegression
    st = LogisticRegression().fit(np.c_[inner[ok], agree[train][ok]], y[train][ok])
    combo_test = st.predict_proba(np.c_[mr_test, agree[test]])[:, 1]
    return mr_test, combo_test


def auc(y, s):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s))


def _auc_or_none(y, s):
    return auc(y, s) if len(np.unique(y)) > 1 else None


def balanced_accuracy(y, pred):
    from sklearn.metrics import balanced_accuracy_score
    return float(balanced_accuracy_score(y, pred))


def bootstrap(y, scores, n=2000, seed=SEED):
    rng = np.random.default_rng(seed)
    names = list(scores)
    out = {k: [] for k in names}
    diffs = {f"{a}-{b}": [] for a in names for b in names if a < b}
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if len(np.unique(y[i])) < 2:
            continue
        v = {k: auc(y[i], scores[k][i]) for k in names}
        for k in names:
            out[k].append(v[k])
        for a in names:
            for b in names:
                if a < b:
                    diffs[f"{a}-{b}"].append(v[a] - v[b])
    ci = lambda arr: [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]  # noqa: E731
    return {k: ci(v) for k, v in out.items()}, {k: {"ci": ci(v), "p_le_0": float(np.mean(np.asarray(v) <= 0))}
                                                 for k, v in diffs.items()}


def bootstrap_metric(y, pred, fn, n=2000, seed=SEED):
    rng = np.random.default_rng(seed + 1)
    vals = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if len(np.unique(y[i])) < 2:
            continue
        vals.append(fn(y[i], pred[i]))
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def evaluate(y, scores, preds):
    cis, diffs = bootstrap(y, scores)
    res = {"n": int(len(y)), "n_interesting": int(y.sum()), "auc": {}, "balanced_accuracy": {}, "auc_differences": diffs}
    for k in scores:
        res["auc"][k] = {"value": auc(y, scores[k]), "ci95": cis[k]}
    for k, p in preds.items():
        res["balanced_accuracy"][k] = {"value": balanced_accuracy(y, p),
                                       "ci95": bootstrap_metric(y, p, balanced_accuracy)}
    return res


def agree_threshold(agree_tr, y_tr):
    """The n_agree cut (predict interesting when n_agree >= c) with the best training balanced accuracy."""
    best = (-1, None)
    for c in np.unique(agree_tr):
        b = balanced_accuracy(y_tr, (agree_tr >= c).astype(int))
        if b > best[0]:
            best = (b, c)
    return best[1]


def _scored_split(M, y, agree, lengths, t, src, tr, te, gap):
    mr, combo = fit_predict(M, y, agree, t, src, tr, te, gap)
    ag_pred = (agree[te] >= agree_threshold(agree[tr], y[tr])).astype(int)
    return mr, combo, ag_pred


def run(queue_ids, length, fs_out, n_folds, gap, figure, tag):
    t0 = time.time()
    s, counts = load_items(queue_ids)
    no_agree = s.n_agree.isna()
    counts["no_agreement_score"] = int(no_agree.sum())
    s = s[~no_agree].reset_index(drop=True)
    M, keep = windows(s, length, fs_out)
    dropped = int((~keep).sum())
    s, M = s[keep].reset_index(drop=True), M[keep]
    y, agree, t = s.y.to_numpy(), s.n_agree.to_numpy().astype(float), s.t_s.to_numpy()
    src = s.rec_source.to_numpy()
    lengths = s.length_s.to_numpy().astype(float)

    # 1) blocked CV with a gap: one out-of-fold score per item
    mr, combo = np.full(len(y), np.nan), np.full(len(y), np.nan)
    mr_pred, ag_pred = np.zeros(len(y), int), np.zeros(len(y), int)
    fold_info = []
    for k, (tr, te) in enumerate(folds_blocked(t, src, n_folds, gap)):
        mr[te], combo[te], ag_pred[te] = _scored_split(M, y, agree, lengths, t, src, tr, te, gap)
        mr_pred[te] = (mr[te] > 0).astype(int)
        fold_info.append({"fold": k, "n_train": int(len(tr)), "n_test": int(len(te)),
                          "test_interesting": float(y[te].mean()),
                          "auc_minirocket": _auc_or_none(y[te], mr[te]),
                          "auc_agreement": _auc_or_none(y[te], agree[te])})
    scores = {"minirocket": mr, "agreement": agree, "minirocket+agreement": combo, "event_length": lengths}
    preds = {"minirocket": mr_pred, "agreement": ag_pred, "minirocket+agreement": (combo > 0.5).astype(int)}
    cv = evaluate(y, scores, preds)
    cv["folds"] = fold_info
    cv["by_dataset"] = {g: {"n": int((src == g).sum()),
                            **{f"auc_{k}": _auc_or_none(y[src == g], v[src == g]) for k, v in scores.items()}}
                        for g in np.unique(src)}

    # 2) forward check: the first 80 % of each dataset's time trains, the last 20 % tests
    cut = np.array([np.quantile(t[src == g], 0.8) for g in src])
    tr, te = np.flatnonzero(t < cut - gap), np.flatnonzero(t >= cut)
    f_mr, f_combo, f_ag_pred = _scored_split(M, y, agree, lengths, t, src, tr, te, gap)
    fwd = evaluate(y[te], {"minirocket": f_mr, "agreement": agree[te], "minirocket+agreement": f_combo,
                           "event_length": lengths[te]},
                   {"minirocket": (f_mr > 0).astype(int), "agreement": f_ag_pred,
                    "minirocket+agreement": (f_combo > 0.5).astype(int)})
    fwd["n_train"] = int(len(tr))

    # 3) leave one dataset out, when there are several
    loro = None
    datasets = np.unique(src)
    if len(datasets) > 1:
        lmr, lcombo = np.full(len(y), np.nan), np.full(len(y), np.nan)
        lmr_pred, lag_pred = np.zeros(len(y), int), np.zeros(len(y), int)
        per = {}
        for g in datasets:
            te, tr = np.flatnonzero(src == g), np.flatnonzero(src != g)
            if len(np.unique(y[tr])) < 2:
                continue
            lmr[te], lcombo[te], lag_pred[te] = _scored_split(M, y, agree, lengths, t, src, tr, te, gap)
            lmr_pred[te] = (lmr[te] > 0).astype(int)
            per[g] = {"n": int(len(te)), "interesting": int(y[te].sum()),
                      "auc_minirocket": _auc_or_none(y[te], lmr[te]),
                      "auc_agreement": _auc_or_none(y[te], agree[te]),
                      "auc_minirocket+agreement": _auc_or_none(y[te], lcombo[te]),
                      "auc_event_length": _auc_or_none(y[te], lengths[te]),
                      "balanced_accuracy_minirocket": balanced_accuracy(y[te], lmr_pred[te]),
                      "balanced_accuracy_agreement": balanced_accuracy(y[te], lag_pred[te])}
        ok = np.isfinite(lmr)
        loro = {"per_dataset": per,
                "pooled": evaluate(y[ok], {"minirocket": lmr[ok], "agreement": agree[ok],
                                           "minirocket+agreement": lcombo[ok], "event_length": lengths[ok]},
                                   {"minirocket": lmr_pred[ok], "agreement": lag_pred[ok],
                                    "minirocket+agreement": (lcombo[ok] > 0.5).astype(int)}),
                "note": "pooled scores mix models and n_agree scales of different datasets; read per_dataset first"}

    # 4) by stratum kind (agreement levels vs selective detectors), where the queue carries one
    strata = s.groupby(["rec_source", "stratum"]).y.agg(["size", "mean"]).round(3).reset_index().to_dict("records")
    kinds = {}
    for name, sel in (("agreement_strata", s.stratum.str.startswith("agree:").to_numpy()),
                      ("family_strata", s.stratum.str.startswith("family:").to_numpy())):
        if sel.sum() and len(np.unique(y[sel])) > 1:
            kinds[name] = {"n": int(sel.sum()), "auc_minirocket": auc(y[sel], mr[sel]),
                           "auc_agreement": auc(y[sel], agree[sel]), "auc_combo": auc(y[sel], combo[sel])}

    res = {"queue_ids": list(queue_ids), "window_s": length, "fs": fs_out, "folds": n_folds, "gap_s": gap,
           "counts": counts, "windows_dropped_for_gaps": dropped,
           "datasets": sorted(map(str, datasets)), "tables": sorted(s.table.unique().tolist()),
           "event_length_s": {q: float(np.percentile(lengths, q)) for q in (10, 25, 50, 75, 90)},
           "blocked_cv": cv, "forward_80_20": fwd, "leave_one_dataset_out": loro,
           "strata": strata, "by_stratum_kind": kinds, "seconds": round(time.time() - t0, 1)}
    if figure:
        plot(y, scores, cv, length, len(datasets), queue_ids,
             os.path.join(OUT_DIR, f"rq1b-minirocket-preliminary-{tag}-roc.png"))
    return res


def plot(y, scores, cv, length, n_datasets, queue_ids, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import roc_curve
    style = [("minirocket", "MiniRocket (shape only)", "#2a78d6", "-", 2.4),
             ("agreement", "Detector agreement (count)", "#eb6834", "-", 2.4),
             ("minirocket+agreement", "MiniRocket + agreement", "#1baf7a", "-", 1.6),
             ("event_length", "Event length alone", "#8a8984", (0, (4, 3)), 1.4)]
    fig, ax = plt.subplots(figsize=(7.2, 6.2), dpi=200)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ax.plot([0, 1], [0, 1], color="#c9c8c2", lw=1, ls=":", zorder=0)
    for key, label, col, ls, lw in style:
        fpr, tpr, _ = roc_curve(y, scores[key])
        a = cv["auc"][key]
        ax.plot(fpr, tpr, color=col, ls=ls, lw=lw,
                label=f"{label}   AUC {a['value']:.2f} [{a['ci95'][0]:.2f}–{a['ci95'][1]:.2f}]")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.01)
    ax.set_xlabel("False-positive rate (dull events called interesting)", color="#52514e")
    ax.set_ylabel("True-positive rate (interesting events found)", color="#52514e")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#c9c8c2")
    ax.tick_params(colors="#52514e")
    ax.grid(color="#ecebe7", lw=0.8)
    ax.set_title("Is an event interesting? Shape classifier vs detector agreement",
                 loc="left", fontsize=12, color="#0b0b0b", fontweight="bold", pad=22)
    where = "M2_aug" if n_datasets == 1 and list(queue_ids) == [25] else f"{n_datasets} dataset(s)"
    qs = ", ".join(str(q) for q in queue_ids)
    ax.text(0, 1.02, f"{where} · {cv['n']} blind event verdicts (queue {qs}) · {length} s windows · "
            "out-of-fold, 5 time blocks with a 1 h gap",
            transform=ax.transAxes, fontsize=8, color="#52514e", va="bottom")
    ax.legend(loc="lower right", frameon=False, fontsize=8.5, labelcolor="#0b0b0b")
    fig.tight_layout()
    fig.savefig(path, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queues", type=int, nargs="+", default=[25], help="Review queue ids (detection queues)")
    ap.add_argument("--length", type=float, default=600, help="window length in SECONDS")
    ap.add_argument("--fs", type=float, default=1.0, help="every window is resampled to this rate (Hz)")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--gap", type=float, default=3600, help="seconds")
    ap.add_argument("--no-figure", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    length = int(a.length) if float(a.length).is_integer() else a.length
    tag = "q" + "+".join(str(q) for q in a.queues)
    res = run(a.queues, length, a.fs, a.folds, a.gap, not a.no_figure, tag)
    out = a.out or os.path.join(OUT_DIR, f"rq1b-minirocket-preliminary-{tag}-{length}s.json")
    with open(out, "w") as f:
        json.dump(res, f, indent=1, default=float)
    print(json.dumps({k: res[k] for k in ("queue_ids", "window_s", "fs", "counts", "windows_dropped_for_gaps",
                                          "seconds")}, default=str))
    for part in ("blocked_cv", "forward_80_20"):
        r = res[part]
        print(part, "n", r["n"], {k: round(v["value"], 3) for k, v in r["auc"].items()},
              {k: round(v["value"], 3) for k, v in r["balanced_accuracy"].items()})
    if res["leave_one_dataset_out"]:
        for g, v in res["leave_one_dataset_out"]["per_dataset"].items():
            print("leave out", g, {k: (round(x, 3) if isinstance(x, float) else x) for k, x in v.items()})
    print("by stratum kind", res["by_stratum_kind"])


if __name__ == "__main__":
    main()
