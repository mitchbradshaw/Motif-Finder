"""
metrics.py
==========
The numbers a paired training job reports (spec §7b.3 / §7b.4), each computed
here once so the Results and Compare pages print the same thing:

* macro F1, balanced accuracy, the confusion matrix and per-class
  precision / recall / F1 with the number of test windows behind each;
* a BLOCK bootstrap: the resampling unit is a contiguous stretch of one
  channel (`block_hours`), never a single window — neighbouring windows of a
  slow signal are not independent, and resampling them one by one would make
  every interval look narrower than the data allow;
* the paired difference A − B under the same resamples, McNemar's exact test
  on the windows exactly one arm got right, and the 2 × 2 agreement;
* calibration on the validation block: a reliability curve, the expected
  calibration error and the threshold that reaches a target precision.

Plain numpy (scipy only for the exact binomial), no sklearn in the scoring
path: the bootstrap calls macro F1 thousands of times.
"""

from __future__ import annotations

import numpy as np


def _codes(y, classes):
    y = np.asarray(y)
    out = np.full(len(y), -1, dtype=np.int64)
    for i, c in enumerate(classes):
        out[y == c] = i
    return out


def _confusion_codes(ti, pi, k):
    ok = (ti >= 0) & (pi >= 0)
    return np.bincount(ti[ok] * k + pi[ok], minlength=k * k).reshape(k, k)


def confusion(y_true, y_pred, classes):
    k = len(classes)
    return _confusion_codes(_codes(y_true, classes), _codes(y_pred, classes), k)


def _per_class_from_confusion(m):
    tp = np.diag(m).astype(float)
    fp = m.sum(axis=0) - tp
    fn = m.sum(axis=1) - tp
    with np.errstate(divide="ignore", invalid="ignore"):
        precision = np.where(tp + fp > 0, tp / (tp + fp), 0.0)
        recall = np.where(tp + fn > 0, tp / (tp + fn), 0.0)
        f1 = np.where(2 * tp + fp + fn > 0, 2 * tp / (2 * tp + fp + fn), 0.0)
    return precision, recall, f1, m.sum(axis=1)


def macro_f1(y_true, y_pred, classes):
    """Macro F1 over `classes` (a class with no true and no predicted window scores 0, as sklearn's
    `zero_division=0`)."""
    _, _, f1, _ = _per_class_from_confusion(confusion(y_true, y_pred, classes))
    return float(f1.mean()) if len(f1) else 0.0


def classification_scores(y_true, y_pred, classes, names=None):
    names = list(names or [str(c) for c in classes])
    m = confusion(y_true, y_pred, classes)
    precision, recall, f1, n = _per_class_from_confusion(m)
    present = n > 0
    return {
        "n": int(m.sum()),
        "macro_f1": float(f1.mean()) if len(f1) else 0.0,
        "balanced_accuracy": float(recall[present].mean()) if present.any() else 0.0,
        "accuracy": float(np.trace(m) / m.sum()) if m.sum() else 0.0,
        "confusion": m.tolist(),
        "confusion_labels": names,
        "per_class": {nm: {"precision": float(precision[i]), "recall": float(recall[i]), "f1": float(f1[i]),
                           "n": int(n[i]), "n_predicted": int(m[:, i].sum())}
                      for i, nm in enumerate(names)},
    }


def units_for(channel, start, fs, block_hours):
    """The bootstrap unit of each window: (channel, which `block_hours` stretch)."""
    span = max(1, int(round(float(block_hours) * 3600.0 * float(fs))))
    return np.array([f"{int(c)}:{int(s) // span}" for c, s in zip(channel, start)], dtype=object)


def _ci(values, level=0.95):
    v = np.asarray(values, dtype=float)
    if not len(v):
        return [None, None]
    a = (1.0 - level) / 2.0
    return [float(np.quantile(v, a)), float(np.quantile(v, 1.0 - a))]


def block_bootstrap(y_true, preds, units, classes, n=1000, seed=0):
    """Resample whole units with replacement `n` times. Returns, for each named
    prediction, the macro-F1 CI and per-class F1 CIs; for exactly two (A, B), the
    paired difference's draws and CI and the per-class ΔF1 CIs."""
    names = list(preds)
    kc = len(classes)
    ti = _codes(y_true, classes)
    pcodes = {k: _codes(preds[k], classes) for k in names}
    units = np.asarray(units)
    uniq = np.unique(units)
    members = [np.flatnonzero(units == u) for u in uniq]
    rng = np.random.default_rng(int(seed))
    draws = {k: [] for k in names}
    cls_draws = {k: [] for k in names}
    for _ in range(int(n)):
        pick = rng.integers(0, len(uniq), len(uniq))
        idx = np.concatenate([members[i] for i in pick]) if len(pick) else np.zeros(0, dtype=int)
        for k in names:
            m = _confusion_codes(ti[idx], pcodes[k][idx], kc)
            _, _, f1, _ = _per_class_from_confusion(m)
            draws[k].append(float(f1.mean()))
            cls_draws[k].append(f1)
    out = {"n_units": int(len(uniq)), "n_draws": int(n), "seed": int(seed),
           "arms": {k: {"macro_f1_ci": _ci(draws[k]),
                        "per_class_f1_ci": [_ci([d[i] for d in cls_draws[k]]) for i in range(len(classes))]}
                    for k in names}}
    if len(names) == 2:
        a, b = names
        diff = np.asarray(draws[a]) - np.asarray(draws[b])
        out["delta"] = {"draws": diff.tolist(), "ci": _ci(diff),
                        "per_class_ci": [_ci([da[i] - db[i] for da, db in zip(cls_draws[a], cls_draws[b])])
                                         for i in range(len(classes))]}
    return out


def mcnemar(a_correct, b_correct):
    """Exact McNemar: `b` = windows only A got right, `c` = only B; p is the
    two-sided binomial test of c successes in b + c at one half."""
    a = np.asarray(a_correct, dtype=bool)
    b_ = np.asarray(b_correct, dtype=bool)
    b = int((a & ~b_).sum())
    c = int((~a & b_).sum())
    if b + c == 0:
        return {"b": 0, "c": 0, "p": 1.0, "method": "exact binomial (no discordant windows)"}
    from scipy.stats import binomtest
    return {"b": b, "c": c, "p": float(binomtest(c, b + c, 0.5).pvalue), "method": "exact binomial"}


def agreement(a_correct, b_correct):
    a = np.asarray(a_correct, dtype=bool)
    b = np.asarray(b_correct, dtype=bool)
    return {"both_right": int((a & b).sum()), "only_a": int((a & ~b).sum()),
            "only_b": int((~a & b).sum()), "both_wrong": int((~a & ~b).sum())}


def null_p(observed, draws):
    """One-sided permutation p: (1 + #draws >= observed) / (1 + n)."""
    d = np.asarray(draws, dtype=float)
    return float((1 + int((d >= float(observed) - 1e-12).sum())) / (1 + len(d)))


def calibration(y_true, p_positive, target_precision=0.8, n_bins=10):
    """Reliability of P(interesting) on the validation block, its ECE, and the
    lowest threshold whose precision reaches `target_precision`."""
    y = np.asarray(y_true, dtype=int)
    p = np.asarray(p_positive, dtype=float)
    if not len(y):
        return {"n": 0, "reason": "no validation windows: the split set aside no validation block"}
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    which = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, n_bins - 1)
    bins, ece = [], 0.0
    for i in range(n_bins):
        m = which == i
        if not m.any():
            continue
        conf, freq = float(p[m].mean()), float(y[m].mean())
        bins.append({"lo": float(edges[i]), "hi": float(edges[i + 1]), "n": int(m.sum()),
                     "mean_p": conf, "fraction_positive": freq})
        ece += m.sum() / len(y) * abs(conf - freq)
    suggested = None
    for t in np.unique(np.round(p, 4)):
        pred = p >= t
        if pred.sum() == 0:
            continue
        prec = float(y[pred].mean())
        if prec >= float(target_precision):
            suggested = {"threshold": float(t), "precision": prec,
                         "recall": float(pred[y == 1].mean()) if (y == 1).any() else 0.0}
            break
    return {"n": int(len(y)), "n_positive": int(y.sum()), "bins": bins, "ece": float(ece),
            "target_precision": float(target_precision), "suggested": suggested,
            "suggested_reason": None if suggested else
            f"no threshold reaches precision {target_precision:g} on the validation block"}
