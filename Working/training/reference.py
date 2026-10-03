"""
reference.py
============
The existing `MODELS/` as a REFERENCE LINE on Results (fixup-ab, Q42): the
GADF, GASF, recurrence and fusion CNNs and `catch22_rf_prelabeled`, scored on
the same exams as the two arms where their inputs allow — and labelled
*trained differently*, never an arm.

Why they are not an arm, said on every row: their training data and split were
never recorded (each manifest says "no provenance sidecar yet"). They were very
likely trained on the same 10-minute manual labels the arms are scored
against, so a test window here may have been one of their training windows —
their number is an upper bound, not an exam.

They are applied exactly as the window matrix applies them (the `cnn` and `rf`
stages of `Working.Preprocessing.window_matrix.build`), at the exam windows'
own starts, and a probability of `interesting` >= 0.5 is read as interesting.
A model that cannot be scored on an exam says why on its row.
"""

from __future__ import annotations

import os

import numpy as np

from Working.training import metrics as tm
from Working.training import paired as tp

TRAINED_DIFFERENTLY = ("trained differently: training data and split unrecorded (no provenance sidecar); very "
                       "likely the same 10-minute manual labels, so these exam windows may be among its training "
                       "windows — an upper bound, not an exam")

_MODELS = (
    ("catch22_rf_prelabeled", "rf", "rf_p_interesting", "catch22_rf_prelabeled.joblib"),
    ("fusion_cnn", "cnn", "cnn_p_fusion_interesting", "fusion_cnn.pth"),
    ("GASF_cnn", "cnn", "cnn_p_GASF_interesting", "GASF_cnn.pth"),
    ("GADF_cnn", "cnn", "cnn_p_GADF_interesting", "GADF_cnn.pth"),
    ("recurrence_cnn", "cnn", "cnn_p_recurrence_interesting", "recurrence_cnn.pth"),
)


def score_reference(conn, pooled, results, cfg, progress=None, cancel=None):
    from Working.Preprocessing.window_matrix.build import features_at

    models_dir = str(cfg.get("models_dir") or "MODELS")
    t = pooled.table
    length = int(pooled.meta["length"])
    y = t["label"].to_numpy()
    roles = t["role"].to_numpy()
    masks = {tp.EXAM_I: roles == "test", tp.EXAM_II: roles == "exam"}
    want = masks[tp.EXAM_I] | masks[tp.EXAM_II]

    columns = {}
    errors = {}
    need_cnn = any(os.path.isfile(os.path.join(models_dir, f)) for _, st, _, f in _MODELS if st == "cnn")
    rf_path = os.path.join(models_dir, "catch22_rf_prelabeled.joblib")
    stages = tuple(s for s, ok in (("rf", os.path.isfile(rf_path)), ("cnn", need_cnn)) if ok)
    values = np.full((len(t), 5), np.nan)
    col_names = []
    if stages:
        recs = {int(c["channel"]): c for c in pooled.meta["per_channel"]}
        out_cols = None
        for ch in sorted(np.unique(t.loc[want, "channel"]).tolist()):
            if cancel is not None and cancel():
                raise InterruptedError("cancelled while scoring the reference line")
            rows = np.flatnonzero(want & (t["channel"].to_numpy() == ch))
            rid = int(recs[ch]["recording_id"])
            npy = conn.execute("SELECT npy_path FROM recordings WHERE id = ?", (rid,)).fetchone()[0]
            x = np.load(npy, mmap_mode="r")
            if progress is not None:
                progress(0, 1, f"reference line: channel {ch}, {len(rows):,} windows")
            try:
                v, comp, out_cols = features_at(x, t["start"].to_numpy()[rows], length, stages,
                                                cnn_model_dir=models_dir, rf_model_path=rf_path)
            except Exception as e:   # one model stack failing is a row's reason, not the run's failure
                for name, *_ in _MODELS:
                    errors[name] = f"{type(e).__name__}: {e}"
                break
            if not col_names:
                col_names = list(out_cols)
                values = np.full((len(t), len(col_names)), np.nan)
            values[rows] = np.where(comp, v, np.nan)
        for i, c in enumerate(col_names):
            columns[c] = values[:, i]

    rows_out = []
    for name, stage, col, fname in _MODELS:
        row = {"name": name, "file": os.path.join(models_dir, fname), "trained_differently": TRAINED_DIFFERENTLY,
               "exams": {}}
        if not os.path.isfile(row["file"]):
            row["status"] = "not scored"
            row["reason"] = f"{row['file']} is not on this machine"
            rows_out.append(row)
            continue
        if name in errors:
            row["status"] = "not scored"
            row["reason"] = errors[name]
            rows_out.append(row)
            continue
        p = columns.get(col)
        row["status"] = "scored"
        for e, mask in masks.items():
            if not mask.any():
                row["exams"][e] = {"status": "empty"}
                continue
            pe = None if p is None else p[mask]
            if pe is None or np.isnan(pe).all():
                row["exams"][e] = {"status": "not scored",
                                   "reason": "the model produced no probability for these windows (see the server log)"}
                continue
            ok = ~np.isnan(pe)
            pred = (pe[ok] >= 0.5).astype(int)
            sc = tm.classification_scores(y[mask][ok], pred, tp.CLASSES, tp.CLASS_NAMES)
            row["exams"][e] = {"status": "scored", "macro_f1": sc["macro_f1"],
                               "balanced_accuracy": sc["balanced_accuracy"], "n": int(ok.sum()),
                               "n_failed": int((~ok).sum()), "per_class": sc["per_class"]}
        row["exams"][tp.EXAM_III] = {"status": "locked"}
        rows_out.append(row)
    return rows_out
