"""
rq1_v2_blind.py — score the cluster-label forest (B.2, run 1613) against queue 3's blind human labels,
with the app's own calculation (`Working.training.blind.score`), on a READ-ONLY database connection.

Also scores run 79's arm A (the manual-label forest of the baseline paired job) on the same blind-labelled
windows where that is like for like (10-minute windows only: arm A was trained on 600-sample windows), using the
same metrics module.

Writes JSON to docs/thesis/data/rq1_v2_blind/. Writes nothing else; the database is opened mode=ro.

    "/c/ProgramData/anaconda3/python.exe" scripts/thesis/rq1_v2_blind.py
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
OUT = os.path.join(ROOT, "docs", "thesis", "data", "rq1_v2_blind")
HELD_OUT = "M4_aug_concat_fs1.mat"


def ro():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def _clean(o):
    import numpy as np
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items() if k != "draws"}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    return o


def score_b2(conn, run_id=1613):
    from Working.training import blind
    res = blind.score(conn, run_id, n_boot=1000, n_null=1000, seed=0)
    return res


def score_arm_a(conn, run_id_b2=1613, n_boot=1000, n_null=1000, seed=0):
    """Run 79's arm A (the manual-label forest, 24 catch22 + entropy features of the raw 600-sample window) on queue
    3's labelled FIRST showings that are 10-minute windows of 600 samples (the only like-for-like scale), beside
    B.2's calls on the same windows. Subsets: all; no earlier human label (blind.contaminated); M2_concat only
    (a recording arm A never saw). Arm A's own exam channels (CH4/8/12/16) are not B.2's (pack D, CH13-16), so per
    exam the windows are NOT unseen for arm A: its rows are an upper bound, stated."""
    import joblib
    import numpy as np
    from Working.training import blind
    from Working.training import metrics as tm
    from Working.training.shape_forest import raw_features
    q = blind.queue_for_run(conn, run_id_b2)
    lab, _ = blind.labels_for_run(conn, q, run_id_b2)
    lab = lab[(~lab["repeat"]) & lab["human"].isin(blind.SCORED) & (lab["source_file"] != HELD_OUT)]
    lab = lab[(lab["length"] == 600) & (lab["fs"].astype(float) == 1.0)].reset_index(drop=True)
    art = joblib.load(os.path.join(ROOT, "DATA", "derived", "training", "paired_68f57f69_run79",
                                   "paired_68f57f69_armA.joblib"))
    pipe = art["pipeline"]
    try:
        pipe.set_params(randomforestclassifier__n_jobs=1)
    except ValueError:
        pass
    feats = raw_features(conn, lab[["recording_id", "start", "length"]])
    X = feats[art["feature_names"]]
    # the paired job fills missing values with the TRAINING medians; those are not saved with the model, so a
    # missing feature here is filled with the column median of these windows (counted)
    n_nan = int(X.isna().any(axis=1).sum())
    X = X.fillna(X.median()).to_numpy(dtype=np.float64)
    # the paired job codes the human vocabulary as Working.training.paired.VOCAB: interesting 1, not 0
    from Working.training.paired import VOCAB
    inv = {v: k for k, v in VOCAB.items()}
    pa = np.array([inv[int(v)] for v in pipe.predict(X)], dtype=object)
    flags = blind.contaminated(conn, lab)
    lab = lab.assign(armA=pa, contaminated=flags)
    out = {"n_windows": int(len(lab)), "n_rows_with_missing_feature": n_nan,
           "arm_A_exam_channels": "CH4_A2, CH8_B2, CH12_C2, CH16_D2 (run 79); trained on the other 12 M2_aug channels",
           "rows": []}
    subsets = {"all": np.ones(len(lab), bool), "no_earlier_label": ~lab["contaminated"].to_numpy(),
               "M2_concat_only": (lab["source_file"] == "M2_concat_fs1.mat").to_numpy()}
    for role_name, role in (("i_later_block", "test"), ("ii_unseen_channels", "exam"), ("both_exams", None)):
        for sname, m in subsets.items():
            mm = m & ((lab["role"] == role).to_numpy() if role else True)
            g = lab[mm]
            if len(g) == 0 or g["human"].nunique() < 2:
                out["rows"].append({"exam": role_name, "subset": sname, "n": int(len(g)), "note": "one class or empty"})
                continue
            y = g["human"].to_numpy(dtype=object)
            row = {"exam": role_name, "subset": sname, "n": int(len(g)), "human_interesting": int((y == "interesting").sum())}
            units = blind._units(g)
            bb = tm.block_bootstrap(y, {"armA": g["armA"].to_numpy(dtype=object), "B2": g["class"].to_numpy(dtype=object)},
                                    units, blind.SCORED, n=n_boot, seed=seed)
            for arm, col in (("armA", "armA"), ("B2", "class")):
                p = g[col].to_numpy(dtype=object)
                cs = tm.classification_scores(y, p, blind.SCORED)
                rng = np.random.default_rng(seed + 1)
                draws = [tm.macro_f1(rng.permutation(y), p, blind.SCORED) for _ in range(n_null)]
                pi = cs["per_class"]["interesting"]
                row[arm] = {"macro_f1": cs["macro_f1"], "macro_f1_ci": bb["arms"][arm]["macro_f1_ci"],
                            "balanced_accuracy": cs["balanced_accuracy"], "accuracy": cs["accuracy"],
                            "kappa": tm.cohen_kappa(y, p, blind.SCORED),
                            "precision": pi["precision"], "recall": pi["recall"],
                            "model_interesting": int((p == "interesting").sum()),
                            "null_mean": float(np.mean(draws)), "null_q95": float(np.quantile(draws, 0.95)),
                            "null_p": tm.null_p(cs["macro_f1"], draws)}
            row["delta_macro_f1_A_minus_B2_ci"] = bb["delta"]["ci"]
            row["mcnemar"] = tm.mcnemar(g["armA"].to_numpy() == y, g["class"].to_numpy() == y)
            out["rows"].append(row)
    return out


def extra_cis(conn, run_id=1613, n_boot=1000, seed=0):
    """Block-bootstrap CIs (24 h of one channel, as the app's own) for balanced accuracy, precision and recall of
    the model's 'interesting', which `blind.score` reports as point values only."""
    import numpy as np
    from Working.training import blind
    from Working.training import metrics as tm
    q = blind.queue_for_run(conn, run_id)
    lab, _ = blind.labels_for_run(conn, q, run_id)
    out = {}
    for ek, role in blind.EXAMS:
        f = lab[(~lab["repeat"]) & (lab["role"] == role) & lab["human"].isin(blind.SCORED)].reset_index(drop=True)
        y = f["human"].to_numpy(dtype=object)
        p = f["class"].to_numpy(dtype=object)
        units = blind._units(f)
        def stat(idx, key):
            if len(idx) == 0:
                return None
            cs = tm.classification_scores(y[idx], p[idx], blind.SCORED)
            if key == "ba":
                return cs["balanced_accuracy"]
            pi = cs["per_class"]["interesting"]
            return pi["precision"] if key == "precision" else pi["recall"]
        out[ek] = {k: blind._ci(blind._boot(units, n_boot, seed, lambda idx, k=k: stat(idx, k)))
                   for k in ("ba", "precision", "recall")}
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    conn = ro()
    res = score_b2(conn)
    with open(os.path.join(OUT, "run1613_blind_score.json"), "w", encoding="utf-8") as fh:
        json.dump(_clean(res), fh, indent=1, default=str)
    for ek, ex in (res.get("exams") or {}).items():
        print(ek, "n_scored", ex.get("n_scored"), "macroF1", ex.get("macro_f1"), ex.get("macro_f1_ci"),
              "BA", ex.get("balanced_accuracy"), "kappa", ex.get("kappa"), ex.get("kappa_ci"),
              "P/R", (ex.get("interesting") or {}).get("precision"), (ex.get("interesting") or {}).get("recall"),
              "null", (ex.get("null") or {}).get("mean"), (ex.get("null") or {}).get("q95"), (ex.get("null") or {}).get("p"),
              "confusion", ex.get("confusion"), "excluded", ex.get("excluded"))
    print("self", res.get("self_agreement"))
    cis = extra_cis(conn)
    with open(os.path.join(OUT, "run1613_extra_cis.json"), "w", encoding="utf-8") as fh:
        json.dump(_clean(cis), fh, indent=1)
    print("extra CIs", cis)
    print("verdicts", res.get("verdicts"), "progress", res.get("progress"))
    a = score_arm_a(conn)
    with open(os.path.join(OUT, "run79_armA_vs_run1613_10min.json"), "w", encoding="utf-8") as fh:
        json.dump(_clean(a), fh, indent=1, default=str)
    print("armA n", a["n_windows"], "missing", a["n_rows_with_missing_feature"])
    for r in a["rows"]:
        if "armA" not in r:
            print(r); continue
        print(r["exam"], r["subset"], r["n"], r["human_interesting"],
              "A F1 %.3f BA %.3f P %.2f R %.2f p %.3f" % (r["armA"]["macro_f1"], r["armA"]["balanced_accuracy"], r["armA"]["precision"] or 0, r["armA"]["recall"] or 0, r["armA"]["null_p"]),
              "| B2 F1 %.3f BA %.3f P %.2f R %.2f p %.3f" % (r["B2"]["macro_f1"], r["B2"]["balanced_accuracy"], r["B2"]["precision"] or 0, r["B2"]["recall"] or 0, r["B2"]["null_p"]),
              "dF1", [round(x, 3) for x in r["delta_macro_f1_A_minus_B2_ci"]], r["mcnemar"])


if __name__ == "__main__":
    main()
