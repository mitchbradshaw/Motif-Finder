"""
m4_exam_score.py
================
The held-out M4 exam (2026-10-26), last step: mark the exam. Run ONCE, after the researcher has judged review queue
36 ("Held-out exam · M4 · blind sample") and turned the held-out lock back on.

In plain words: the researcher has now marked 290 candidate events by eye, without seeing what any detector or model
said. This script reads ONLY those marks (not copies Review carried onto other detections, not verdicts given in any
other queue), then — for the first time — asks the frozen models and detectors what they said about the same events,
and scores them against the marks exactly as the frozen manifest says. Nothing is written to the database.

    python scripts/m4_exam_score.py --real           # the exam: DB read-only; writes DATA/derived/exam/M4/results.json
                                                     # and docs/rq_roundA_2/findings/m4-exam-<date>.md
    python scripts/m4_exam_score.py --dry-run        # rehearsal: SYNTHETIC verdicts and SYNTHETIC model scores, held
                                                     # in memory; the model is never run on M4; writes to a temp folder

Checks before it marks anything: the manifest hashes to the frozen sha256 and its freeze is in the audit log
(`candidate_events.verify_exam`); the sample folder names that manifest and queue; the sample's detections are the
database's.

**Amendment 1 (2026-10-26, before any judging; `DATA/derived/exam/M4/amendment-1.json`).** The four reference CNNs
in `MODELS/` (GASF, GADF, recurrence, fusion_cnn_3) are scored on the same answered events, beside MiniRocket. The
amendment must hash to `AMENDMENT_SHA256`, name the frozen manifest's sha256, have its own audit row, and that row
must be older than every verdict of the exam queue. A CNN checkpoint whose sha256 differs from the amendment's is
refused. Each event is cut as `scripts/rq1b_cnn_vs_minirocket.py`'s `cuts600` cuts it (span + 0.25 x span each side,
mV, 600 points by the CNN block's resampler) and scored by `window_scores`' own path; P(interesting) > 0.5 is
"interesting". Metrics: AUC and balanced accuracy with the same within-stratum bootstrap as MiniRocket, and the
paired AUC difference (CNN minus MiniRocket) on the same items.

Headless; no UI library. The real database is opened read-only (`?mode=ro`).
"""

import argparse
import datetime
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from Working.config import HELD_OUT_RECORDING_FILE  # noqa: E402
from Working.discovery import candidate_events as ce  # noqa: E402

REAL_DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite")
MANIFEST = os.path.join(ROOT, "DATA", "derived", "exam", "M4", "manifest.json")
MANIFEST_SHA256 = "db32fdc7ff42aa46ddfd0198993853e138e9fb958c3d4dcf83a65e5f3317e0b6"
SAMPLE = os.path.join(ROOT, "DATA", "derived", "candidate_events", "M4_aug_concat_fs1_ae545821",
                      "sample_seed20261026_l40_f15")
QUEUE_ID = 36
AMENDMENT = os.path.join(ROOT, "DATA", "derived", "exam", "M4", "amendment-1.json")
AMENDMENT_SHA256 = "5286bac396f99c524c4e53a926ec2318e42313156aa333188d6407f962e25d14"   # audit_log 539
EXAM_AMENDED = "held-out exam: manifest amended"
OUT = os.path.join(ROOT, "DATA", "derived", "exam", "M4")
FINDINGS = os.path.join(ROOT, "docs", "rq_roundA_2", "findings")
LABEL_COLUMNS = ("label", "label_kind", "label_basis", "label_refs", "inside_interesting")
Y = {"interesting": 1, "not_interesting": 0, "artifact": 0}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ── the verdicts ────────────────────────────────────────────────────────────

def exam_verdicts(conn, sample, queue_id):
    """`(verdicts, report)`. `verdicts`: {detection_id: verdict} for the sample's anchors whose adjudication is the
    researcher's own (``carried_from IS NULL``) AND was written through queue `queue_id` (a not-undone 'verdict' row
    of ``review_audit`` names it among its targets). Everything else is counted in `report` and left out."""
    anchors = {int(d) for d in sample["detection_id"]}
    via_queue = set()
    for (payload,) in conn.execute("SELECT payload_json FROM review_audit WHERE queue_id = ? AND action = 'verdict' "
                                   "AND undone_at IS NULL", (int(queue_id),)):
        try:
            targets = json.loads(payload or "{}").get("targets") or []
        except ValueError:
            continue
        for t in targets:
            for k in ("row_id", "target_id"):
                if t.get(k) is not None:
                    via_queue.add(int(t[k]))
    out, carried, elsewhere = {}, [], []
    ids = sorted(anchors)
    for i in range(0, len(ids), 400):
        chunk = ids[i:i + 400]
        marks = ",".join("?" * len(chunk))
        for d, verdict, carried_from in conn.execute(
                f"SELECT detection_id, verdict, carried_from FROM adjudications WHERE detection_id IN ({marks})",
                chunk):
            d = int(d)
            if carried_from is not None:
                carried.append(d)
            elif d not in via_queue:
                elsewhere.append(d)
            else:
                out[d] = verdict
    report = {"n_items": len(anchors), "n_own_exam_verdicts": len(out), "excluded_carried": sorted(carried),
              "excluded_not_via_exam_queue": sorted(elsewhere),
              "unanswered": len(anchors) - len(out) - len(carried) - len(elsewhere)}
    return out, report


# ── the model metrics ───────────────────────────────────────────────────────

def _auc(y, s, w=None):
    from sklearn.metrics import roc_auc_score
    y = np.asarray(y, int)
    if len(set(y.tolist())) < 2:
        return float("nan")
    return float(roc_auc_score(y, np.asarray(s, float), sample_weight=w))


def _ba(y, s, w=None):
    y = np.asarray(y, int)
    pred = (np.asarray(s, float) > 0).astype(int)
    w = np.ones(len(y)) if w is None else np.asarray(w, float)
    r1 = (w * ((pred == 1) & (y == 1))).sum() / (w * (y == 1)).sum() if (y == 1).any() else np.nan
    r0 = (w * ((pred == 0) & (y == 0))).sum() / (w * (y == 0)).sum() if (y == 0).any() else np.nan
    return float(np.nanmean([r1, r0])) if not (np.isnan(r1) and np.isnan(r0)) else float("nan")


def _ci(vals):
    v = np.asarray([x for x in vals if not np.isnan(x)], float)
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if len(v) else [None, None]


def score_metrics(frame, *, n_boot, seed=0):
    """AUC and balanced accuracy (decision > 0) of `frame['score']` against `frame['y']`, unweighted (primary) and
    weighted by `frame['weight']` (secondary), each with a 95 % bootstrap interval resampling within `stratum`."""
    y, s, w, h = (frame["y"].to_numpy(int), frame["score"].to_numpy(float), frame["weight"].to_numpy(float),
                  frame["stratum"].to_numpy(object))
    point = {"auc": _auc(y, s), "balanced_accuracy": _ba(y, s), "auc_weighted": _auc(y, s, w),
             "balanced_accuracy_weighted": _ba(y, s, w)}
    rng = np.random.default_rng(int(seed))
    by_h = [np.flatnonzero(h == k) for k in pd.unique(h)]
    boots = {k: [] for k in point}
    for _ in range(int(n_boot)):
        idx = np.concatenate([g[rng.integers(0, len(g), len(g))] for g in by_h]) if by_h else np.array([], int)
        yb, sb, wb = y[idx], s[idx], w[idx]
        boots["auc"].append(_auc(yb, sb))
        boots["balanced_accuracy"].append(_ba(yb, sb))
        boots["auc_weighted"].append(_auc(yb, sb, wb))
        boots["balanced_accuracy_weighted"].append(_ba(yb, sb, wb))
    out = {k: {"value": (None if np.isnan(v) else v), "ci": _ci(boots[k])} for k, v in point.items()}
    pred = s > 0
    out.update(n=int(len(y)), interesting=int(y.sum()), tp=int((pred & (y == 1)).sum()),
               fp=int((pred & (y == 0)).sum()), fn=int((~pred & (y == 1)).sum()), tn=int((~pred & (y == 0)).sum()))
    return out


def minirocket_scorer(conn, manifest):
    """The frozen MiniRocket R4's decision on each row's span (`rq1b_minirocket.extract`/`decision`), checked
    against the manifest's sha256 first. Returns a function rows -> (scores, readable mask)."""
    import importlib.util
    m = manifest["models"]["minirocket_R4"]
    path = os.path.join(ROOT, m["dir"], "model.joblib")
    if _sha_file(path) != m["files"]["model.joblib"]["sha256"]:
        raise SystemExit(f"{path} is not the frozen model (sha256 differs from the manifest)")
    spec = importlib.util.spec_from_file_location("_m4_exam_minirocket", os.path.join(ROOT, "scripts",
                                                                                      "rq1b_minirocket.py"))
    mr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mr)
    model = mr.load_model(path)

    def score(rows):
        M, side, keep = mr.extract(conn, rows, length=int(model["length"]), pad=float(model.get("pad", mr.PAD)))
        d = np.full(len(rows), np.nan)
        if keep.any():
            d[keep] = mr.decision(model, M[keep], side[keep].reset_index(drop=True))
        return d, keep
    return score


# ── amendment 1: the reference CNNs ─────────────────────────────────────────

def _abs(path):
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def _parse_time(t):
    return datetime.datetime.fromisoformat(str(t).replace("Z", "+00:00"))


def verify_amendment(conn, path, sha, manifest_sha, queue_id):
    """`(amendment, audit_id, audited_at)`, or SystemExit: the file must hash to `sha`, amend the frozen manifest
    `manifest_sha`, have an audit row (kind 'exam', `EXAM_AMENDED`, detail sha256), and that row must be no younger
    than every verdict given through the exam queue (it was added before judging)."""
    if not os.path.isfile(path):
        raise SystemExit(f"amendment {path} does not exist")
    if not sha or _sha_file(path) != sha:
        raise SystemExit(f"{path} does not hash to the amendment's sha256 {sha}")
    with open(path, encoding="utf-8") as fh:
        am = json.load(fh)
    if (am.get("amends") or {}).get("sha256") != manifest_sha:
        raise SystemExit(f"{path} amends manifest {(am.get('amends') or {}).get('sha256')}, not the frozen manifest "
                         f"{manifest_sha}")
    rows = []
    for aid, at, detail in conn.execute("SELECT id, at, detail_json FROM audit_log WHERE kind = ? AND what LIKE ?",
                                        (ce.EXAM_AUDIT_KIND, EXAM_AMENDED + "%")):
        try:
            if json.loads(detail or "{}").get("sha256") == sha:
                rows.append((int(aid), at))
        except (ValueError, AttributeError):
            continue
    if not rows:
        raise SystemExit(f"the audit log holds no '{EXAM_AMENDED}' entry for sha256 {sha}")
    aid, at = min(rows)
    (first,) = conn.execute("SELECT MIN(created_at) FROM review_audit WHERE queue_id = ? AND action = 'verdict'",
                            (int(queue_id),)).fetchone()
    if first is not None and _parse_time(first) < _parse_time(at):
        raise SystemExit(f"amendment {sha} was audited at {at}, after the first exam verdict ({first}): it was not "
                         "added before judging, so it cannot count")
    return am, aid, at


def verify_cnn_files(am):
    """SystemExit if any reference CNN checkpoint's sha256 differs from the amendment's. Returns the list of
    extraction-code files whose sha256 drifted (reported, not refused)."""
    for name, c in am["models"]["reference_cnns"].items():
        path = _abs(c["path"])
        if not os.path.isfile(path) or _sha_file(path) != c["sha256"]:
            raise SystemExit(f"{name}: {path} is not the frozen checkpoint (sha256 differs from the amendment); "
                             "refusing to score")
    return [rel for rel, h in (am.get("code") or {}).items()
            if not os.path.isfile(_abs(rel)) or _sha_file(_abs(rel)) != h]


def reference_cnn_scorers(am):
    """{name: rows -> (P(interesting), readable)} for the amendment's checkpoints, cutting each span once
    (`rq1b_cnn_vs_minirocket.cuts600`) and scoring with `window_scores`' own path (softmax column 0)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_m4_exam_cnn", os.path.join(ROOT, "scripts",
                                                                               "rq1b_cnn_vs_minirocket.py"))
    cv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cv)
    cache = {}

    def cuts(rows):
        key = tuple(map(tuple, rows[["recording_id", "start", "end"]].to_numpy().tolist()))
        if key not in cache:
            cache.clear()
            cache[key] = cv.cuts600(rows, length=int(am.get("input_length", cv.LENGTH)), log=lambda *_: None)
        return cache[key]

    def make(c):
        def score(rows):
            import torch
            from Working.Catalogue.cnn.cnn_rangapur import get_transforms
            from Working.Catalogue.cnn.window_scores import load_scorer, predict, window_image
            X, ok = cuts(rows)
            model, _ = load_scorer(_abs(c["path"]), c["image_type"], 0, torch.device("cpu"))
            transform = get_transforms(224, is_train=False, is_rgb=(c["image_type"] == "fusion"))
            p = np.full(len(rows), np.nan)
            todo = np.flatnonzero(ok)
            for b in range(0, len(todo), 32):
                chunk = todo[b:b + 32]
                p[chunk] = predict(model, [transform(window_image(X[i], c["image_type"], 224, X.shape[1]))
                                           for i in chunk], 0)
            del model
            return p, np.asarray(ok, bool)
        return score
    return {name: make(c) for name, c in am["models"]["reference_cnns"].items()}


def paired_auc_difference(frame, a, b, *, n_boot, seed=0):
    """AUC(frame[a]) - AUC(frame[b]) on the same items, with the within-stratum bootstrap interval."""
    y, h = frame["y"].to_numpy(int), frame["stratum"].to_numpy(object)
    sa, sb = frame[a].to_numpy(float), frame[b].to_numpy(float)
    rng = np.random.default_rng(int(seed))
    by_h = [np.flatnonzero(h == k) for k in pd.unique(h)]
    diffs = []
    for _ in range(int(n_boot)):
        idx = np.concatenate([g[rng.integers(0, len(g), len(g))] for g in by_h]) if by_h else np.array([], int)
        diffs.append(_auc(y[idx], sa[idx]) - _auc(y[idx], sb[idx]))
    v = _auc(y, sa) - _auc(y, sb)
    d = np.asarray([x for x in diffs if not np.isnan(x)], float)
    return {"value": None if np.isnan(v) else float(v), "ci": _ci(diffs), "n": int(len(y)),
            "share_ge_0": float(np.mean(d >= 0)) if len(d) else None}


def score_cnns(answered, keep, am, scorers, *, n_boot, synthetic):
    """Each CNN on the answered items MiniRocket could read (and the CNN could cut), beside MiniRocket."""
    cut = float((am.get("metrics") or {}).get("cut", 0.5))
    out = {}
    base = answered[np.asarray(keep, bool)].reset_index(drop=True)
    for name, scorer in scorers.items():
        p, ok = scorer(base[["recording_id", "start", "end"]].reset_index(drop=True))
        f = base.assign(p=np.asarray(p, float), mr=base["score"].to_numpy(float))[np.asarray(ok, bool)]
        f = f.reset_index(drop=True)
        c = am["models"]["reference_cnns"].get(name, {})
        out[name] = {"checkpoint": c.get("path"), "sha256": c.get("sha256"), "cut": cut,
                     "unscored": int(len(base) - len(f)), "scores_synthetic": bool(synthetic),
                     "metrics": score_metrics(f.assign(score=f["p"] - cut), n_boot=n_boot) if len(f) else None,
                     "auc_minus_minirocket": paired_auc_difference(f, "p", "mr", n_boot=n_boot) if len(f) else None}
    return out


# ── the exam ────────────────────────────────────────────────────────────────

def mark(conn, *, manifest_path, manifest_sha, sample_dir, queue_id, scorer=None, verdicts=None, n_boot=None,
         amendment=None, cnn_scorers=None):
    """Everything the manifest says to compute. `scorer`: rows -> (scores, readable) (default the frozen MiniRocket);
    `verdicts`: {detection_id: verdict} to use INSTEAD of the database's (the dry run's synthetic ones).
    `amendment`: `(path, sha256)` of an amendment to verify and apply (amendment 1: the reference CNNs);
    `cnn_scorers`: {name: rows -> (P, readable)} INSTEAD of the real checkpoints (tests, the dry run)."""
    man = ce.verify_exam(conn, ce.ExamManifest(manifest_path, manifest_sha), HELD_OUT_RECORDING_FILE)
    am = None
    if amendment is not None:
        am, am_audit, am_at = verify_amendment(conn, amendment[0], amendment[1], manifest_sha, queue_id)
        code_drift = verify_cnn_files(am)
    sample, labels, smeta = ce.load_sample(sample_dir)
    if (smeta.get("exam") or {}).get("sha256") != manifest_sha:
        raise SystemExit(f"{sample_dir} was not drawn under manifest {manifest_sha}")
    if int(smeta.get("queue_id", -1)) != int(queue_id):
        raise SystemExit(f"{sample_dir} is queue {smeta.get('queue_id')}, not {queue_id}")
    events, members, tmeta = ce.load_table(os.path.dirname(os.path.abspath(sample_dir)))
    if tmeta["key"] != smeta["table_key"]:
        raise SystemExit(f"{sample_dir} was drawn from table {smeta['table_key']}, not {tmeta['key']}")
    events = events.drop(columns=[c for c in LABEL_COLUMNS if c in events]).merge(labels, on="event_id", how="left")
    ce.check_sample_against(conn, sample)
    db_verdicts, vreport = exam_verdicts(conn, sample, queue_id)
    synthetic = verdicts is not None
    use = verdicts if synthetic else db_verdicts
    nb = int(n_boot or man["metrics"]["estimate_n_boot"])
    est = ce.estimate(events, members, sample, use, n_boot=nb, seed=int(man["metrics"]["estimate_seed"]))
    groups = est["groups"]
    s = sample.copy()
    s["verdict"] = [use.get(int(d)) for d in s["detection_id"]]
    s["y"] = s["verdict"].map(Y)
    answered = s[s["y"].notna()].reset_index(drop=True)
    answered["y"] = answered["y"].astype(int)
    n_ans = answered.groupby("stratum").size()
    answered["weight"] = answered["frame_size"].astype(float) / answered["stratum"].map(n_ans).astype(float)
    n_agree = events.set_index("event_id")["n_agree"]
    answered["n_agree"] = answered["event_id"].map(n_agree).astype(float)
    if scorer is None:
        scorer = minirocket_scorer(conn, man)
    scores, keep = scorer(answered[["recording_id", "start", "end"]].reset_index(drop=True))
    answered["score"] = scores
    readable = answered[np.asarray(keep, bool)].reset_index(drop=True)
    mr = score_metrics(readable, n_boot=nb) if len(readable) else None
    comp = readable.assign(score=readable["n_agree"])
    comparator = {"auc": _auc(comp["y"], comp["score"]) if len(comp) else None,
                  "auc_weighted": _auc(comp["y"], comp["score"], comp["weight"]) if len(comp) else None}
    pick = lambda pref: {k: v for k, v in groups.items() if k.startswith(pref)}  # noqa: E731
    extra = {}
    if am is not None:
        scorers = cnn_scorers if cnn_scorers is not None else reference_cnn_scorers(am)
        extra = {"amendment": {"path": os.path.abspath(amendment[0]), "sha256": amendment[1], "audit_id": am_audit,
                               "audited_at": am_at, "code_drift": code_drift},
                 "cnns": score_cnns(answered, keep, am, scorers, n_boot=nb, synthetic=synthetic)}
    return extra | {
        "exam": "M4 held-out exam", "dry_run": synthetic, "synthetic": synthetic, "created_at": _now(),
        "manifest": {"path": os.path.abspath(manifest_path), "sha256": manifest_sha},
        "scorer": {"path": os.path.abspath(__file__), "sha256": _sha_file(os.path.abspath(__file__)),
                   "git_head": _git_head()},
        "queue_id": int(queue_id), "sample": os.path.abspath(sample_dir), "table_key": tmeta["key"],
        "verdicts": vreport | ({"note": "SYNTHETIC verdicts used instead of the database's"} if synthetic else {}),
        "answered": est["answered"], "unsure": est["unsure"], "pending": est["pending"],
        "estimated_share_real": groups.get("all"),
        "agreement_ladder": pick("agree:"),
        "per_family_precision": pick("family:"),
        "per_setting_precision": pick("variant:"),
        "minirocket": {"model": "minirocket_R4", "unreadable_spans": int((~np.asarray(keep, bool)).sum()),
                       "metrics": mr, "comparator_n_agree": comparator,
                       "scores_synthetic": synthetic},
        "n_boot": nb,
    }


def _git_head():
    try:
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:  # noqa: BLE001 - provenance only
        return None


def _pct(g):
    if not g or g.get("precision") is None:
        return "—"
    lo, hi = g["ci"]
    return f"{100 * g['precision']:.0f} % [{100 * lo:.0f}–{100 * hi:.0f}]" if lo is not None else \
        f"{100 * g['precision']:.0f} %"


def findings_markdown(res):
    m = (res["minirocket"] or {}).get("metrics") or {}
    def v(k):
        x = m.get(k) or {}
        if x.get("value") is None:
            return "—"
        lo, hi = x["ci"]
        return f"{x['value']:.2f} [{lo:.2f}–{hi:.2f}]" if lo is not None else f"{x['value']:.2f}"
    lines = [f"# M4 held-out exam — results{' (DRY RUN, SYNTHETIC)' if res['synthetic'] else ''}", "",
             f"Scored {res['created_at']} by `scripts/m4_exam_score.py` (sha256 `{res['scorer']['sha256']}`) under the "
             f"frozen manifest `{res['manifest']['sha256']}`; review queue {res['queue_id']}.", "",
             "## In plain words", "",
             "The researcher judged a fixed random sample of M4's candidate events without seeing any detector or "
             "model output. The numbers below say how often each kind of candidate was real, and how well the frozen "
             "MiniRocket model agreed with the researcher on events it had never seen.", "",
             "## The answers", "",
             f"- items {res['verdicts']['n_items']}; answered {res['answered']}; unsure {res['unsure']}; "
             f"unanswered {res['pending']}",
             f"- excluded: {len(res['verdicts']['excluded_carried'])} carried copies, "
             f"{len(res['verdicts']['excluded_not_via_exam_queue'])} verdicts not given in the exam queue", "",
             "## Estimated share of real candidates", "",
             f"All events: **{_pct(res['estimated_share_real'])}**", "",
             "## Agreement ladder", "", "| level | precision [95 %] | sampled |", "|---|---|---|"]
    lines += [f"| {k} | {_pct(g)} | {g['n_sampled']} |" for k, g in res["agreement_ladder"].items()]
    lines += ["", "## Per detector family", "", "| family | precision [95 %] | sampled |", "|---|---|---|"]
    lines += [f"| {k[7:]} | {_pct(g)} | {g['n_sampled']} |" for k, g in res["per_family_precision"].items()]
    lines += ["", "## MiniRocket R4", "",
              f"- AUC {v('auc')}; balanced accuracy {v('balanced_accuracy')} (unweighted, primary)",
              f"- weighted: AUC {v('auc_weighted')}; balanced accuracy {v('balanced_accuracy_weighted')}",
              f"- comparator (agreement count as a score): AUC "
              f"{(res['minirocket']['comparator_n_agree'] or {}).get('auc')}",
              f"- unreadable spans {res['minirocket']['unreadable_spans']}", "",
              "Per-setting precision and the full intervals are in `DATA/derived/exam/M4/results.json`.", ""]
    if res.get("cnns"):
        def cv(x):
            if not x or x.get("value") is None:
                return "—"
            lo, hi = x["ci"]
            return f"{x['value']:.2f} [{lo:.2f}–{hi:.2f}]" if lo is not None else f"{x['value']:.2f}"
        am = res["amendment"]
        lines += ["## Reference CNNs (amendment 1)", "",
                  f"Amendment `{am['sha256']}` (audit row {am['audit_id']}, {am['audited_at']}, before any judging). "
                  "The same answered events as MiniRocket; P(interesting) > 0.5 is 'interesting'. The CNNs' "
                  "training data is not recorded (most likely M2_aug labels only).", "",
                  "| CNN | AUC [95 %] | balanced accuracy [95 %] | AUC minus MiniRocket [95 %] | scored |",
                  "|---|---|---|---|---|"]
        for name, r in res["cnns"].items():
            m = r.get("metrics") or {}
            lines.append(f"| {name} | {cv(m.get('auc'))} | {cv(m.get('balanced_accuracy'))} | "
                         f"{cv(r.get('auc_minus_minirocket'))} | {m.get('n', 0)} |")
        if am.get("code_drift"):
            lines += ["", f"**Warning:** extraction code changed since the amendment: {', '.join(am['code_drift'])}."]
        lines.append("")
    return "\n".join(lines)


def _clean(x):
    """NaN -> None, numpy scalars -> Python, so results.json is plain JSON."""
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if np.isnan(x) else float(x)
    if isinstance(x, np.integer):
        return int(x)
    return x


def _write(res, out_dir, findings_dir):
    res = _clean(res)
    os.makedirs(out_dir, exist_ok=True)
    rp = os.path.join(out_dir, "results.json")
    with open(rp, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    os.makedirs(findings_dir, exist_ok=True)
    fp = os.path.join(findings_dir, f"m4-exam-{datetime.date.today().isoformat()}.md")
    with open(fp, "w", encoding="utf-8") as fh:
        fh.write(findings_markdown(res))
    return rp, fp


def synthetic_verdicts(sample, seed=0):
    rng = np.random.default_rng(seed)
    words = np.array(["interesting", "not_interesting", "artifact", "unsure"])
    return {int(d): str(words[rng.choice(4, p=[0.45, 0.45, 0.05, 0.05])]) for d in sample["detection_id"]}


def synthetic_scorer(verdicts, seed=0):
    """A stand-in for the model on the dry run: pure noise. The real model never runs on M4 before judging."""
    rng = np.random.default_rng(seed)

    def score(rows):
        return rng.normal(0, 1, len(rows)), np.ones(len(rows), bool)
    return score


def _synthetic_p(seed=0):
    """A stand-in CNN on the dry run: uniform noise in [0, 1]. No CNN runs on M4 before judging."""
    rng = np.random.default_rng(seed)

    def score(rows):
        return rng.uniform(0, 1, len(rows)), np.ones(len(rows), bool)
    return score


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--real", action="store_true", help="mark the exam from the real database (read-only)")
    mode.add_argument("--dry-run", action="store_true", help="synthetic verdicts and scores; writes to a temp dir")
    ap.add_argument("--db", default=REAL_DB)
    ap.add_argument("--manifest", default=MANIFEST)
    ap.add_argument("--sha256", default=MANIFEST_SHA256)
    ap.add_argument("--sample", default=SAMPLE)
    ap.add_argument("--queue", type=int, default=QUEUE_ID)
    ap.add_argument("--out", help="results folder (default DATA/derived/exam/M4; a temp folder on --dry-run)")
    ap.add_argument("--n-boot", type=int)
    ap.add_argument("--amendment", help="an amendment file (default: amendment 1, the reference CNNs, whenever the "
                                        "frozen M4 manifest is marked); '' to mark without it")
    ap.add_argument("--amendment-sha256")
    a = ap.parse_args(argv)
    if a.amendment is None and a.sha256 == MANIFEST_SHA256:      # the real exam: amendment 1 applies by default
        a.amendment, a.amendment_sha256 = AMENDMENT, a.amendment_sha256 or AMENDMENT_SHA256
    amendment = (a.amendment, a.amendment_sha256) if a.amendment and a.amendment_sha256 else None
    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    try:
        if a.dry_run:
            sample, _l, _m = ce.load_sample(a.sample)
            fake = synthetic_verdicts(sample)
            fake_cnns = None
            if amendment is not None:
                with open(amendment[0], encoding="utf-8") as fh:
                    names = list(json.load(fh)["models"]["reference_cnns"])
                fake_cnns = {n: _synthetic_p(seed=i + 1) for i, n in enumerate(names)}
            res = mark(conn, manifest_path=a.manifest, manifest_sha=a.sha256, sample_dir=a.sample, queue_id=a.queue,
                       scorer=synthetic_scorer(fake), verdicts=fake, n_boot=a.n_boot or 200, amendment=amendment,
                       cnn_scorers=fake_cnns)
            out = a.out or tempfile.mkdtemp(prefix="m4_exam_dry_")
            paths = _write(res, out, out)
        else:
            if amendment is None and a.amendment:
                raise SystemExit("--real marks the exam WITH amendment 1 (the CNNs), and its sha256 is not set; pass "
                                 "--amendment '' to mark without it only on purpose, and say so in the findings")
            res = mark(conn, manifest_path=a.manifest, manifest_sha=a.sha256, sample_dir=a.sample, queue_id=a.queue,
                       n_boot=a.n_boot, amendment=amendment)
            paths = _write(res, a.out or OUT, FINDINGS)
    finally:
        conn.close()
    print(json.dumps({"results": paths[0], "findings": paths[1], "dry_run": bool(a.dry_run),
                      "answered": res["answered"], "verdicts": {k: (len(v) if isinstance(v, list) else v)
                                                                for k, v in res["verdicts"].items()}}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
