"""
paired.py
=========
The paired training job of RQ1 (fixup-ab; spec §7b.1–§7b.4; `QUESTIONS.md`
Q42 and Round 10, the researcher's, 2026-10-03).

Two arms, trained IDENTICALLY on the same windows; only the label source differs
-------------------------------------------------------------------------------
* **arm A** — the human labels (`catalogue.manual_labels`' rule, carried by the
  pooled set's `label` column);
* **arm B** — a dendrogram clustering at a chosen cut (`k`), fitted ONCE on the
  pooled TRAINING windows of every training channel. Test, validation and exam
  windows take no part in forming the clusters.

Both arms train the same classifier (a random forest on the window-matrix
features, the estimator `catalogue.classifier` fits, Q42: "RF for both arms
first") with the same parameters and seed, on the same training windows.

Yardstick (A): both arms are scored against the human verdicts on windows
neither saw. Arm B's classes are translated into the human vocabulary by a
TRANSLATION TABLE that is part of the recipe — written down before any test
score exists. A recipe without one gets the majority mapping on the training
windows (no test window is consulted). Either way this is marked in arm A's own
language and so is tilted toward it; `notes` says so, once.

Three exams, never pooled
-------------------------
(i) the later time block of each training channel (`role = "test"`);
(ii) channels never trained on, the same mushroom (`role = "exam"`);
(iii) the held-out recording — a LOCKED slot. Nothing here reads it.

Per exam and arm: macro F1 with a block-bootstrap CI, balanced accuracy, the
confusion matrix, per-class P/R/F1 with n, the label-shuffle null (the arm's
training labels permuted, the forest refitted, `rf_shuffles` times) with its p,
and per channel. Per exam, paired: ΔF1 = A − B with its CI under the same
resamples, McNemar, the 2 × 2 agreement and per-class ΔF1.

The full-model null (spec §9.4: 5 shuffles, every one a full retrain) is the
same as the RF null while the arm's classifier IS the forest; it becomes its
own number when the CNN arm exists (a later cluster job, Q42).
"""

from __future__ import annotations

import time

import numpy as np

from Working.recipes import short_hash
from Working.training import metrics as tm
from Working.training import windows as tw

CLASSES = (0, 1)
CLASS_NAMES = ("not_interesting", "interesting")
VOCAB = {"interesting": 1, "not_interesting": 0}
EXAM_I, EXAM_II, EXAM_III = "i_later_block", "ii_unseen_channels", "iii_held_out"
LOCAL_LIMIT_S = 2 * 3600          # spec §7b.1: local when the estimate is <= 2 h
TEST_WARN_BELOW = 50              # spec §7b.1: warn below 50 test windows per class
IMPURE_BELOW = 0.75               # a cluster whose majority human class is < 75 % is flagged impure
SMALL_CLUSTER_MIN = 10            # a cluster under max(10, 0.5 % of the training windows) is an outlier speck
SMALL_CLUSTER_FRAC = 0.005

TILT_NOTE = ("Yardstick (A) scores both arms against the human verdicts, so it is marked in arm A's own language "
             "and is tilted toward it; arm B is judged through a translation table fixed before any test score.")


def make_recipe(window_set, k=None, translation=None, *, linkage="ward", n_estimators=300,
                class_weight="balanced", random_state=42, rf_shuffles=200, full_shuffles=5, null_seed=0,
                bootstrap_n=1000, bootstrap_seed=0, block_hours=24.0, target_precision=0.8,
                reference=False, models_dir="MODELS"):
    """The paired job's recipe. Everything that changes a number is in it, so the
    job is reproducible from its hash."""
    return {
        "kind": "paired_training", "version": 1,
        "window_set": dict(window_set),
        "arms": {
            "A": {"labels": "manual"},
            "B": {"labels": "cluster", "linkage": str(linkage), "k": (int(k) if k is not None else None),
                  "translation": ({str(c): str(v) for c, v in translation.items()} if translation else None)},
        },
        "classifier": {"name": "random_forest", "n_estimators": int(n_estimators),
                       "class_weight": str(class_weight), "random_state": int(random_state)},
        "train_on": "labelled_in_every_arm",
        "null": {"method": "label_shuffle", "rf_shuffles": int(rf_shuffles), "full_shuffles": int(full_shuffles),
                 "seed": int(null_seed)},
        "bootstrap": {"n": int(bootstrap_n), "seed": int(bootstrap_seed), "block_hours": float(block_hours)},
        "calibration": {"target_precision": float(target_precision)},
        "reference": {"enabled": bool(reference), "models_dir": str(models_dir)},
        "exams": {EXAM_I: "on", EXAM_II: "on", EXAM_III: "locked"},
    }


# ── checks ──────────────────────────────────────────────────────────────────

def _check(name, ok, detail, level=None):
    return {"name": name, "ok": bool(ok), "level": level or ("pass" if ok else "error"), "detail": detail}


def validate(recipe, pooled):
    """The *Before launch* checks (spec §7b.1): each a pass, a warn or an error."""
    checks = []
    t = pooled.table
    roles = t["role"].to_numpy()
    split = pooled.meta.get("split") or {}
    try:
        tw.check_split(split)
        gap_ok = True
    except ValueError:
        gap_ok = False
    train_rows = set(np.flatnonzero(roles == "train"))
    test_rows = set(np.flatnonzero(np.isin(roles, ["test", "exam"])))
    checks.append(_check("test block unseen", not (train_rows & test_rows) and len(test_rows) > 0,
                         f"{len(test_rows):,} test/exam windows, none in the {len(train_rows):,} training windows; "
                         "the clusters are formed on training windows only"))
    checks.append(_check("gap >= window", gap_ok,
                         f"blocked by time within each channel, gap {split.get('gap_windows', '?')} window(s); "
                         f"{sum(c.get('dropped_for_gap', 0) for c in pooled.meta.get('per_channel', []))} "
                         "window(s) dropped to keep it"))
    try:
        tw.check_stages(pooled.meta.get("stages") or [])
        lf_ok = True
    except ValueError:
        lf_ok = False
    checks.append(_check("label-derived features off", lf_ok,
                         f"features: {', '.join(pooled.meta.get('stages') or [])} (no model-derived columns)"))
    arms = recipe.get("arms") or {}
    paired_ok = (recipe.get("train_on") == "labelled_in_every_arm" and set(arms) >= {"A", "B"}
                 and arms["A"].get("labels") == "manual" and arms["B"].get("labels") == "cluster")
    checks.append(_check("arms paired", paired_ok,
                         "A manual · B cluster, one classifier, trained on the windows labelled in every arm"))
    k = arms.get("B", {}).get("k")
    n_train = len(train_rows)
    checks.append(_check("cut chosen", k is not None and 2 <= int(k) <= max(2, n_train - 1),
                         f"k = {k} on {n_train:,} training windows" if k is not None else
                         "no cut in the recipe: choose k (Propose shows silhouette per k)"))
    tr = recipe.get("arms", {}).get("B", {}).get("translation")
    if tr is not None:
        bad = [c for c, v in tr.items() if v not in VOCAB]
        missing = [str(c) for c in range(1, int(k or 0) + 1) if str(c) not in tr]
        checks.append(_check("translation table", not bad and not missing,
                             "every cluster translated into interesting / not_interesting" if not bad and not missing
                             else f"unknown class(es) {bad} · untranslated cluster(s) {missing}"))
    counts = tw.role_counts(pooled)
    low = [f"{r} {c} {counts[r][c]}" for r in ("test", "exam") for c in ("interesting", "not_interesting")
           if counts[r]["n"] and counts[r][c] < TEST_WARN_BELOW]
    one_class = [r for r in ("train",) if min(counts[r]["interesting"], counts[r]["not_interesting"]) == 0]
    if one_class:
        checks.append(_check("class counts", False, "the training windows hold one class only"))
    else:
        checks.append(_check("class counts", not low,
                             "every exam class has at least 50 windows" if not low else
                             f"fewer than {TEST_WARN_BELOW} windows: " + " · ".join(low),
                             level=None if not low else "warn"))
    ws = recipe.get("window_set") or {}
    if ws.get("key") and ws["key"] != pooled.key:
        checks.append(_check("window set", False, f"the recipe names set key {ws['key']}, the set is {pooled.key}"))
    return checks


def _errors(checks):
    return [c for c in checks if c["level"] == "error"]


# ── features ────────────────────────────────────────────────────────────────

class _Features:
    """The feature matrix fitted on the TRAINING windows (columns kept, medians,
    scaler) and applied unchanged to every other window."""

    def __init__(self, features, train_mask):
        from Working.Catalogue.dendrogram.dendrogram_cluster import preprocess_window_matrix
        train = features.loc[train_mask].reset_index(drop=True)
        pre = preprocess_window_matrix(train)
        self.names = list(pre.feature_names)
        self.medians = train[self.names].median()
        self.scaler = pre.scaler
        self.removed = {k: list(v) for k, v in pre.removed_summary.items()}
        self.X = features[self.names].fillna(self.medians).to_numpy(dtype=np.float64)
        self.X_scaled_train = pre.X_scaled


def _forest(cfg):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.feature_selection import VarianceThreshold
    from sklearn.pipeline import make_pipeline
    cw = cfg.get("class_weight", "balanced")
    return make_pipeline(
        VarianceThreshold(threshold=1e-6),
        RandomForestClassifier(n_estimators=int(cfg.get("n_estimators", 300)),
                               class_weight=(None if cw == "none" else cw),
                               random_state=int(cfg.get("random_state", 42)), n_jobs=-1))


# ── arm B: the clustering ───────────────────────────────────────────────────

def _linkage(X_scaled, method):
    import scipy.cluster.hierarchy as sch
    if method == "ward":
        return sch.linkage(X_scaled, method="ward", metric="euclidean")
    import scipy.spatial.distance as ssd
    return sch.linkage(ssd.pdist(X_scaled), method=method)


def _cut(Z, k):
    import scipy.cluster.hierarchy as sch
    return sch.fcluster(Z, t=int(k), criterion="maxclust").astype(np.int64)


def _contingency(clusters, human, k):
    """Rows: cluster 1..k; columns: not_interesting, interesting (training windows)."""
    rows = []
    for c in range(1, int(k) + 1):
        m = clusters == c
        rows.append([int((m & (human == 0)).sum()), int((m & (human == 1)).sum())])
    return rows


def _majority(contingency):
    return {str(i + 1): CLASS_NAMES[int(np.argmax(r))] if sum(r) else "not_interesting"
            for i, r in enumerate(contingency)}


def _purity(contingency):
    return [{"cluster": i + 1, "n": int(sum(r)),
             "purity": (float(max(r)) / sum(r)) if sum(r) else None,
             "majority": CLASS_NAMES[int(np.argmax(r))] if sum(r) else None,
             "impure": bool(sum(r) and max(r) / sum(r) < IMPURE_BELOW)} for i, r in enumerate(contingency)]


def _silhouette(X, labels, seed=0):
    from sklearn.metrics import silhouette_score
    if len(np.unique(labels)) < 2 or len(labels) < 3:
        return None
    n = len(labels)
    if n <= 8000:
        return float(silhouette_score(X, labels))
    # beyond that, a stratified sample: a random one can miss a small cluster
    # entirely (Ward splits off outlier groups of a handful of windows)
    rng = np.random.default_rng(seed)
    pick = np.concatenate([rng.choice(np.flatnonzero(labels == c), max(2, int(8000 * (labels == c).mean())), replace=True)
                           for c in np.unique(labels)])
    return float(silhouette_score(X[pick], labels[pick]))


def propose(pooled, linkage="ward", k_range=(2, 8)):
    """Silhouette, sizes and the cluster×human contingency per k, on the pooled
    TRAINING windows only — what the researcher looks at to choose the cut."""
    train = pooled.role_mask("train")
    feats = _Features(pooled.features, train)
    Z = _linkage(feats.X_scaled_train, linkage)
    human = pooled.table["label"].to_numpy()[train]
    small_below = max(SMALL_CLUSTER_MIN, int(np.ceil(SMALL_CLUSTER_FRAC * len(human))))
    by_k = []
    for k in range(int(k_range[0]), int(k_range[1]) + 1):
        if k >= len(human):
            break
        lab = _cut(Z, k)
        cont = _contingency(lab, human, k)
        sizes = {str(c): int((lab == c).sum()) for c in range(1, k + 1)}
        small = [int(c) for c, n in sizes.items() if n < small_below]
        by_k.append({"k": k, "silhouette": _silhouette(feats.X_scaled_train, lab), "sizes": sizes,
                     "small_clusters": small, "effective_k": k - len(small),
                     "contingency": cont, "translation": _majority(cont), "purity": _purity(cont)})
    # Ward splits off outlier specks first; a cut whose "clusters" are one big
    # group and a few specks scores a near-perfect silhouette and means nothing.
    # The draft cut is the best silhouette among cuts with >= 2 real clusters.
    scored = [r for r in by_k if r["silhouette"] is not None and r["effective_k"] >= 2]
    suggested = max(scored, key=lambda r: (round(r["silhouette"], 3), r["effective_k"]))["k"] if scored else None
    heights = Z[:, 2]
    return {"linkage": linkage, "n_windows_clustered": int(train.sum()), "features": feats.names,
            "by_k": by_k, "suggested_k": suggested, "small_below": small_below,
            "suggestion_rule": (f"best silhouette among cuts with at least two clusters of {small_below}+ windows; "
                                "smaller clusters are outlier specks and do not count"),
            "merge_heights_top": [float(h) for h in heights[-12:][::-1]],
            "note": "clusters formed on the training windows of every training channel, pooled; "
                    "silhouette is a guide, the cut is the researcher's"}


# ── the job ─────────────────────────────────────────────────────────────────

def _translate(pred_clusters, translation):
    return np.array([VOCAB[translation[str(int(c))]] for c in pred_clusters], dtype=np.int64)


def _p_interesting_b(proba, classes_, translation):
    cols = [i for i, c in enumerate(classes_) if translation[str(int(c))] == "interesting"]
    return proba[:, cols].sum(axis=1) if cols else np.zeros(len(proba))


def per_channel(y, preds, channel, mask):
    """Both arms' macro F1 on each channel's windows of one exam. A channel whose
    windows there hold ONE class has no macro F1 — half of a perfect score on the
    one class present reads as a coin toss (measured: 7 of 12 M2_aug test blocks
    hold no interesting window) — so it reports accuracy and says so."""
    rows = []
    for ch in sorted(np.unique(channel[mask]).tolist()):
        cm = mask & (channel == ch)
        n_int = int((cm & (y == 1)).sum())
        one = n_int == 0 or n_int == int(cm.sum())
        row = {"channel": int(ch), "n": int(cm.sum()), "interesting": n_int, "one_class": bool(one)}
        for arm, pr in preds.items():
            row[arm] = None if one else tm.macro_f1(y[cm], pr[cm], CLASSES)
            row[f"accuracy_{arm}"] = float((pr[cm] == y[cm]).mean()) if cm.any() else None
        rows.append(row)
    return rows


def run_paired(recipe, pooled, progress=None, cancel=None, model_dir=None):
    """Train both arms, score the exams, return the results dict (module docstring).
    `model_dir`, when given, is where the two fitted forests are written."""
    def _p(done, total, msg):
        if progress is not None:
            progress(done, total, msg)

    def _cancelled():
        if cancel is not None and cancel():
            raise InterruptedError("the paired training job was cancelled")

    t0 = time.time()
    timings = {}
    ws = recipe.get("window_set") or {}
    if ws.get("key") and ws["key"] != pooled.key:
        raise ValueError(f"the recipe names window set key {ws['key']} but the set given is {pooled.key}: "
                         "a recipe is only reproducible against the set it names")
    checks = validate(recipe, pooled)
    if _errors(checks):
        raise ValueError("the paired job refuses to start: " +
                         "; ".join(f"{c['name']}: {c['detail']}" for c in _errors(checks)))

    t = pooled.table
    roles = t["role"].to_numpy()
    y = t["label"].to_numpy().astype(np.int64)
    channel = t["channel"].to_numpy()
    start = t["start"].to_numpy()
    fs = float(pooled.meta.get("fs") or 1.0)
    train = roles == "train"
    train_ids = np.flatnonzero(train)

    _p(0, 6, "fitting the feature space on the training windows")
    feats = _Features(pooled.features, train)
    X = feats.X

    # arm B's labels: one clustering over the pooled training windows
    _p(1, 6, f"clustering {int(train.sum()):,} training windows")
    tc = time.time()
    armB = recipe["arms"]["B"]
    k = int(armB["k"])
    Z = _linkage(feats.X_scaled_train, armB.get("linkage", "ward"))
    clusters = _cut(Z, k)
    cont = _contingency(clusters, y[train], k)
    translation = armB.get("translation")
    translation_source = "recipe"
    if not translation:
        translation = _majority(cont)
        translation_source = "majority on training windows (no test window consulted)"
    timings["cluster_s"] = time.time() - tc
    _cancelled()

    cfg = recipe["classifier"]
    labels = {"A": y[train], "B": clusters}
    models = {}
    tf = time.time()
    _p(2, 6, "training arm A (manual) and arm B (cluster)")
    for arm in ("A", "B"):
        m = _forest(cfg)
        m.fit(X[train], labels[arm])
        models[arm] = m
    timings["fit_s"] = time.time() - tf

    exams = {EXAM_I: roles == "test", EXAM_II: roles == "exam"}
    preds, p_int = {}, {}
    for arm in ("A", "B"):
        m = models[arm]
        raw = m.predict(X)
        proba = m.predict_proba(X)
        classes_ = m.named_steps["randomforestclassifier"].classes_
        if arm == "A":
            preds[arm] = raw.astype(np.int64)
            p_int[arm] = proba[:, list(classes_).index(1)] if 1 in classes_ else np.zeros(len(X))
        else:
            preds[arm] = _translate(raw, translation)
            p_int[arm] = _p_interesting_b(proba, classes_, translation)

    # the label-shuffle null: each arm's training labels permuted, the forest refitted
    nshuf = int(recipe["null"]["rf_shuffles"])
    rng = np.random.default_rng(int(recipe["null"].get("seed", 0)))
    null_draws = {arm: {e: [] for e in exams} for arm in ("A", "B")}
    tn = time.time()
    for s in range(nshuf):
        _cancelled()
        _p(3, 6, f"label-shuffle null {s + 1}/{nshuf}")
        perm = rng.permutation(len(train_ids))
        for arm in ("A", "B"):
            m = _forest(cfg)
            m.fit(X[train], labels[arm][perm])
            raw = m.predict(X)
            pr = raw.astype(np.int64) if arm == "A" else _translate(raw, translation)
            for e, mask in exams.items():
                if mask.any():
                    null_draws[arm][e].append(tm.macro_f1(y[mask], pr[mask], CLASSES))
    timings["null_s"] = time.time() - tn

    _p(4, 6, "scoring the exams")
    bs = recipe["bootstrap"]
    out_exams = {}
    for e, mask in exams.items():
        if not mask.any():
            out_exams[e] = {"status": "empty", "n_windows": 0,
                            "reason": ("no exam channel was chosen" if e == EXAM_II else "no test windows")}
            continue
        units = tm.units_for(channel[mask], start[mask], fs, bs["block_hours"])
        boot = tm.block_bootstrap(y[mask], {"A": preds["A"][mask], "B": preds["B"][mask]}, units, CLASSES,
                                  n=bs["n"], seed=bs["seed"])
        arms_out = {}
        for arm in ("A", "B"):
            sc = tm.classification_scores(y[mask], preds[arm][mask], CLASSES, CLASS_NAMES)
            draws = null_draws[arm][e]
            sc["macro_f1_ci"] = boot["arms"][arm]["macro_f1_ci"]
            for i, nm in enumerate(CLASS_NAMES):
                sc["per_class"][nm]["f1_ci"] = boot["arms"][arm]["per_class_f1_ci"][i]
            sc["null"] = {"method": "label shuffle, forest refitted", "draws": draws,
                          "p": tm.null_p(sc["macro_f1"], draws) if draws else None,
                          "mean": float(np.mean(draws)) if draws else None,
                          "q95": float(np.quantile(draws, 0.95)) if draws else None,
                          "full_model": ("the arm's full model is this random forest (Q42), so these shuffles are "
                                         "its null; the 5 full-model shuffles apply when the CNN arm exists")}
            arms_out[arm] = sc
        ca = preds["A"][mask] == y[mask]
        cb = preds["B"][mask] == y[mask]
        per_class_delta = {nm: {"delta": arms_out["A"]["per_class"][nm]["f1"] - arms_out["B"]["per_class"][nm]["f1"],
                                "ci": boot["delta"]["per_class_ci"][i]} for i, nm in enumerate(CLASS_NAMES)}
        per_channel_rows = per_channel(y, preds, channel, mask)
        out_exams[e] = {
            "status": "scored", "n_windows": int(mask.sum()),
            "class_counts": {nm: int((y[mask] == c).sum()) for c, nm in zip(CLASSES, CLASS_NAMES)},
            "n_units": boot["n_units"], "unit": f"{bs['block_hours']:g} h of one channel",
            "arms": arms_out,
            "paired": {"delta_f1": arms_out["A"]["macro_f1"] - arms_out["B"]["macro_f1"],
                       "delta_f1_ci": boot["delta"]["ci"], "delta_draws_sample": boot["delta"]["draws"][:400],
                       "mcnemar": tm.mcnemar(ca, cb), "agreement": tm.agreement(ca, cb),
                       "per_class_delta": per_class_delta},
            "per_channel": per_channel_rows,
            "window_ids": np.flatnonzero(mask).tolist(),
            "predictions": {"A": preds["A"][mask].tolist(), "B": preds["B"][mask].tolist()},
        }
    out_exams[EXAM_III] = {
        "status": "locked", "n_windows": 0,
        "reason": ("the held-out recording (M4_aug_concat_fs1.mat, a different mushroom) is scored once, after the "
                   "freeze, when the researcher unlocks it in Settings › Datasets; this job never reads it")}

    _p(5, 6, "calibration on the validation block")
    val = roles == "validation"
    target = recipe.get("calibration", {}).get("target_precision", 0.8)
    calibration = {arm: tm.calibration(y[val], p_int[arm][val], target) for arm in ("A", "B")}

    if model_dir is not None:
        import os

        import joblib
        os.makedirs(model_dir, exist_ok=True)
        paths = {}
        for arm in ("A", "B"):
            paths[arm] = os.path.join(model_dir, f"paired_{short_hash(recipe)}_arm{arm}.joblib")
            joblib.dump({"pipeline": models[arm], "feature_names": feats.names, "arm": arm,
                         "translation": translation if arm == "B" else None}, paths[arm])
    else:
        paths = {}

    importances = {}
    for arm in ("A", "B"):
        pipe = models[arm]
        kept = pipe.named_steps["variancethreshold"].get_support()
        names = [n for n, k_ in zip(feats.names, kept) if k_]
        imp = pipe.named_steps["randomforestclassifier"].feature_importances_
        importances[arm] = sorted(({"feature": n, "importance": float(v)} for n, v in zip(names, imp)),
                                  key=lambda r: -r["importance"])[:12]

    training = {arm: {"label_source": "manual" if arm == "A" else "cluster",
                      "n_train": int(train.sum()), "window_ids": train_ids.tolist(),
                      "classifier": dict(cfg), "n_classes": int(len(np.unique(labels[arm]))),
                      "class_counts": {str(int(c)): int((labels[arm] == c).sum()) for c in np.unique(labels[arm])},
                      "feature_importance": importances[arm], "model_path": paths.get(arm)}
                for arm in ("A", "B")}
    timings["total_s"] = time.time() - t0
    _p(6, 6, "done")
    return {
        "kind": "paired_training_results", "recipe": recipe, "recipe_hash": short_hash(recipe),
        "window_set": {"name": ws.get("name"), "id": ws.get("id"), "key": pooled.key,
                       "n_windows": int(len(t)), "by_role": tw.role_counts(pooled),
                       "source_file": pooled.meta.get("source_file"), "channels": pooled.meta.get("channels"),
                       "exam_channels": pooled.meta.get("exam_channels"), "length": pooled.meta.get("length"),
                       "grid": pooled.meta.get("grid"), "stages": pooled.meta.get("stages"),
                       "split": pooled.meta.get("split"), "per_channel": pooled.meta.get("per_channel"),
                       "non_overlap_rule": pooled.meta.get("non_overlap_rule")},
        "checks": checks,
        "features": {"kept": feats.names, "removed": feats.removed},
        "cluster": {"k": k, "linkage": armB.get("linkage", "ward"), "n_windows": int(train.sum()),
                    "sizes": {str(c): int((clusters == c).sum()) for c in range(1, k + 1)},
                    "contingency": cont, "contingency_columns": list(CLASS_NAMES),
                    "purity": _purity(cont), "impure_below": IMPURE_BELOW,
                    "silhouette": _silhouette(feats.X_scaled_train, clusters),
                    "translation": translation, "translation_source": translation_source},
        "training": training,
        "exams": out_exams,
        "calibration": calibration,
        "yardstick_b": {"status": "not yet labelled",
                        "note": "blind hand-labelling of test windows in the cluster vocabulary is the Review "
                                "behaviour prompt's (Q42); its result lands here"},
        "reference": [],
        "notes": [TILT_NOTE,
                  "Exams are reported separately and never pooled.",
                  "Both arms: one random forest, same parameters and seed, same training windows; only the labels "
                  "differ."],
        "timings": timings,
    }


# ── the estimate ────────────────────────────────────────────────────────────

def _time_one_fit(n_train, n_features, n_estimators):
    """Seconds one forest fit takes here, measured on a small fit and scaled."""
    from sklearn.ensemble import RandomForestClassifier
    rng = np.random.default_rng(0)
    n = int(min(max(n_train, 50), 3000))
    Xs = rng.standard_normal((n, max(1, int(n_features))))
    ys = (Xs[:, 0] > 0).astype(int)
    trees = 20
    t = time.time()
    RandomForestClassifier(n_estimators=trees, n_jobs=-1, random_state=0).fit(Xs, ys)
    dt = time.time() - t
    return dt * (n_estimators / trees) * (max(n_train, 1) / n) * np.log2(max(n_train, 2)) / np.log2(max(n, 2))


def estimate(recipe, pooled=None, *, n_train=None, n_features=None, n_windows_to_measure=0, stages=()):
    """Seconds this job should take here, the parts, and where it should run
    (local when <= 2 h, spec §7b.1). The set's features are already measured
    when `pooled` is given; otherwise `n_windows_to_measure` are priced too."""
    if pooled is not None:
        n_train = int(pooled.role_mask("train").sum())
        n_features = int(pooled.features.shape[1])
    n_train = int(n_train or 0)
    n_features = int(n_features or 26)
    cfg = recipe["classifier"]
    fit = _time_one_fit(n_train, n_features, int(cfg.get("n_estimators", 300)))
    n_fits = 2 * (1 + int(recipe["null"]["rf_shuffles"]))
    parts = {"fits": n_fits * fit, "cluster": 1e-8 * n_train ** 2 + 0.5,
             "bootstrap": 2e-4 * int(recipe["bootstrap"]["n"]) * 2}
    if n_windows_to_measure:
        from Working.Preprocessing.window_matrix.cost import estimate_seconds
        try:
            parts["features"] = float(estimate_seconds(int(n_windows_to_measure), 600, tuple(stages)) or 0.0)
        except Exception:
            parts["features"] = 0.03 * int(n_windows_to_measure)
    seconds = float(sum(parts.values()))
    return {"seconds": seconds, "parts": parts, "n_fits": n_fits, "seconds_per_fit": fit,
            "where": "local" if seconds <= LOCAL_LIMIT_S else "slurm", "local_limit_s": LOCAL_LIMIT_S}
