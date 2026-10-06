"""
blind.py
========
fixup-ah: the BLIND check of a B.2 run (RQ1 version 2, "yardstick (B)").

In plain words
--------------
A forest was trained on piles a clustering made, with no human labels. To learn
whether what it calls interesting is what a person calls interesting, a person
labels some of the same test windows **without seeing the model's answer**, and
the two are compared. This module draws that sample, serves it to a Review queue
that hides everything that could tip the answer, records the answers as ordinary
human labels, and computes the comparison — with the manual-label CNNs scored on
the same windows as the comparison line.

The sample (decided, the researcher, 2026-10-05)
------------------------------------------------
* drawn from the run's TEST and EXAM windows only (exam (i) the later block,
  role ``test``; exam (ii) unseen channels, role ``exam``), seeded;
* up to N (default 1,000, at most 2,000), split equally between the two exams and
  then EVENLY per predicted cluster within each exam, a cluster with fewer windows
  than its share giving all it has and the rest going to the others — so a rare
  cluster is not swamped by a common one;
* every window keeps its sampling weight (its stratum's population / the windows
  drawn from it) so population figures can be reweighted;
* a fraction (default 10 %) is shown TWICE, at least a quarter of the queue apart,
  for self-agreement;
* the order is a seeded shuffle, so it does not track the model;
* FIXED and stored with the run (``blind_sample.parquet`` beside its results, an
  ``artifacts`` row) before the first label; asking for a different sample is
  refused (``SampleFixed``): the same sample for every model.

The queue and the labels
------------------------
A ``review_queues`` row of kind ``blind-test`` (unit ``test window``, blind). Its
items are the SHOWINGS in order and carry the window's place and length and
nothing else: no prediction, no cluster, no class, no score, no weight, no exam,
and a second showing never carries the first showing's answer.

A label is an ordinary human row in ``annotations`` over the window's exact span
(rule 5: the human store; ``source = 'blind_test_review'`` and a note naming the
queue tell it apart from the 2025–26 labels), linked to its showing by
``blind_test_labels``. The model's calls stay in the run's parquet file; neither
is written into the other. **The first label is a score**: it marks that exam
``scored`` in the run's results, which is what ``shape_forest.frozen_for`` reads,
so the pool's cut and mapping freeze from then on.

Against a blind human (per exam, never pooled)
----------------------------------------------
The confusion of model against human; macro F1 with the block-bootstrap CI
(``metrics.block_bootstrap``, unit = 24 h of one channel); the precision, recall
and F1 of the model's *interesting*; Cohen's kappa with its CI; per cluster (how
many of each predicted cluster the human called interesting — the check on the
researcher's mapping); per scale and per recording; the label-shuffle null (the
human's answers permuted against the model's fixed calls); population-reweighted
figures; and **self-agreement** on the repeated windows beside all of it, because
no model can be expected to agree with the human more than the human does.

The comparison line
-------------------
The manual-label models in ``MODELS/`` (GASF, GADF, recurrence, fusion CNNs and
``catch22_rf_prelabeled``) scored on the same blind-labelled windows, **one row per
scale, never pooled**, the 1- and 30-minute rows marked *outside its training
scale*. A window reaches a CNN AS IT IS — its n raw samples become an n × n image,
which the network's own transform resizes to 224 × 224; nothing is resampled. The
recurrence embedding (m = 3, τ = 4 samples) is fixed in samples and so not
scale-free (fusion carries it as its blue channel); catch22's features depend on
length. Contamination is stated on every row: they were very likely trained on
M2_aug's 2025–26 labels, so each is scored on every labelled window and on those
overlapping no earlier human label.

Headless: no UI or web library is imported here (CLAUDE.md rule 1).
"""

from __future__ import annotations

import datetime as _dt
import json
import os

import numpy as np
import pandas as pd

SOURCE_KIND = "blind-test"
UNIT = "test window"
REVIEW_SOURCE = "blind_test_review"
#: the queue's words: interesting / not are the primary pair; "can't tell" is `unsure`, an artifact is `artifact`
#: (the vocabulary is fixed at five words, Q45; `seed` is not asked here)
VERDICT_OPTIONS = ("interesting", "not_interesting", "unsure", "artifact")
SCORED = ("interesting", "not_interesting")
DEFAULT_N, MAX_N, DEFAULT_REPEAT_FRAC = 1000, 2000, 0.10
EXAMS = (("i_later_block", "test"), ("ii_unseen_channels", "exam"))
EXAM_TITLES = {"i_later_block": "exam (i) · the later block of the training channels",
               "ii_unseen_channels": "exam (ii) · channels never trained on"}
TRAINING_SCALE_MIN = 10.0
BLOCK_HOURS = 24.0
SAMPLE_FILE, SAMPLE_META = "blind_sample.parquet", "blind_sample.json"
REFERENCE_FILE, REFERENCE_META = "blind_reference.parquet", "blind_reference.json"

#: The comparison line. `fusion_cnn.pth` loads with ONE output class (AB): it is listed so its row says why it is
#: refused; `fusion_cnn_2` / `_3` are the two-class fusion checkpoints in `MODELS/` (which one is "the" fusion model
#: is not recorded anywhere — both are scored and the row says so).
REFERENCE_MODELS = (
    {"model": "GASF_cnn", "file": "GASF_cnn.pth", "kind": "cnn", "image": "GASF"},
    {"model": "GADF_cnn", "file": "GADF_cnn.pth", "kind": "cnn", "image": "GADF"},
    {"model": "recurrence_cnn", "file": "recurrence_cnn.pth", "kind": "cnn", "image": "recurrence"},
    {"model": "fusion_cnn", "file": "fusion_cnn.pth", "kind": "cnn", "image": "fusion"},
    {"model": "fusion_cnn_2", "file": "fusion_cnn_2.pth", "kind": "cnn", "image": "fusion"},
    {"model": "fusion_cnn_3", "file": "fusion_cnn_3.pth", "kind": "cnn", "image": "fusion"},
    {"model": "catch22_rf_prelabeled", "file": "catch22_rf_prelabeled.joblib", "kind": "rf", "image": None},
)
CONTAMINATION = ("very likely trained on M2_aug's 2025–26 manual labels (no provenance was recorded): a blind window "
                 "that overlaps one of those labels is not unseen for it. 'all' scores every blind-labelled window; "
                 "'no earlier label' only the windows that overlap no earlier human label (every M2_concat_fs1 window "
                 "qualifies)")
_EMBEDDING = {
    "recurrence": ("the recurrence image's embedding (m = 3, τ = 4 samples) is fixed in SAMPLES, so it is not "
                   "scale-free: the same shape at 1, 10 and 30 minutes gives a different recurrence image"),
    "fusion": ("fusion's blue channel is the recurrence image, whose embedding (m = 3, τ = 4 samples) is fixed in "
               "samples: not scale-free"),
    "GASF": "a Gramian field of the window's own samples: no fixed-sample parameter, but each pixel covers n / 224 samples",
    "GADF": "a Gramian field of the window's own samples: no fixed-sample parameter, but each pixel covers n / 224 samples",
    None: "catch22's features are length-dependent (autocorrelation lags, histogram counts): not scale-free",
}


class SampleFixed(ValueError):
    """A run's blind sample is fixed once drawn: a different N, repeat fraction or seed is refused."""


def _now():
    return _dt.datetime.now().isoformat(timespec="seconds")


def _atomic_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, allow_nan=False)
    os.replace(tmp, path)


# ── the sample ──────────────────────────────────────────────────────────────

def _even_split(total, caps):
    """`total` shared as evenly as the caps allow: a cap below its share gives all it has, the rest is shared again."""
    out = [0] * len(caps)
    left = min(int(total), int(sum(caps)))
    open_ = [i for i, c in enumerate(caps) if c > 0]
    while left > 0 and open_:
        share = left // len(open_)
        if share == 0:
            for i in open_[:left]:
                out[i] += 1
            break
        nxt = []
        for i in open_:
            give = min(share, caps[i] - out[i])
            out[i] += give
            left -= give
            if out[i] < caps[i]:
                nxt.append(i)
        open_ = nxt
    return out


def draw_sample(preds, *, n=DEFAULT_N, repeat_frac=DEFAULT_REPEAT_FRAC, seed=0):
    """The blind sample of a run's predictions: one row per SHOWING, in the order shown.

    Columns: `showing` (0..), `window` (the window's id in the sample), `repeat` (a second showing),
    `first_showing` (a repeat's first showing, −1 otherwise), `exam`, the prediction table's own columns, and
    `weight` = `stratum_size` / `stratum_drawn` for the window's (exam, predicted cluster) stratum."""
    n = int(n)
    if n > MAX_N:
        raise ValueError(f"a blind sample is at most {MAX_N:,} windows (asked for {n:,})")
    if n < 1:
        raise ValueError("a blind sample needs at least one window")
    repeat_frac = float(repeat_frac)
    if not 0.0 <= repeat_frac <= 0.5:
        raise ValueError(f"the repeated fraction is between 0 and 0.5 (got {repeat_frac:g})")
    p = preds[preds["role"].isin([r for _, r in EXAMS])].reset_index(drop=True)
    if p.empty:
        raise ValueError("the run predicted no test or exam windows: there is nothing to label blind")
    rng = np.random.default_rng(int(seed))
    present = [(ek, role) for ek, role in EXAMS if (p["role"] == role).any()]
    per_exam = _even_split(n, [int((p["role"] == role).sum()) for _, role in present])
    picked, weight, size, drawn, exam = [], [], [], [], []
    for (ek, role), quota in zip(present, per_exam):
        pe = p[p["role"] == role]
        clusters = sorted(int(c) for c in pe["cluster"].unique())
        sizes = [int((pe["cluster"] == c).sum()) for c in clusters]
        for c, sz, k in zip(clusters, sizes, _even_split(quota, sizes)):
            if k <= 0:
                continue
            idx = pe.index[pe["cluster"] == c].to_numpy()
            take = np.sort(rng.choice(idx, size=k, replace=False)) if k < sz else idx
            picked.extend(int(i) for i in take)
            weight.extend([sz / k] * len(take))
            size.extend([sz] * len(take))
            drawn.extend([k] * len(take))
            exam.extend([ek] * len(take))
    firsts = p.loc[picked].reset_index(drop=True)
    firsts["exam"] = exam
    firsts["weight"] = np.asarray(weight, dtype=float)
    firsts["stratum_size"] = np.asarray(size, dtype=np.int64)
    firsts["stratum_drawn"] = np.asarray(drawn, dtype=np.int64)
    m = len(firsts)
    order = rng.permutation(m)                       # position in the queue of each first showing
    firsts = firsts.iloc[np.argsort(order)].reset_index(drop=True)    # rows now in shown order
    firsts["window"] = np.arange(m, dtype=np.int64)
    # repeats: windows whose first showing leaves room for a second at least a quarter of the queue later
    gap = max(1, m // 4)
    eligible = np.arange(0, max(0, m - gap))
    n_rep = min(int(round(repeat_frac * m)), len(eligible))
    rep_pos = np.sort(rng.choice(eligible, size=n_rep, replace=False)) if n_rep else np.zeros(0, dtype=int)
    keys = np.concatenate([np.arange(m, dtype=float),
                           np.array([rng.uniform(pos + gap - 0.5, m - 0.5) if pos + gap < m else m + rng.random()
                                     for pos in rep_pos], dtype=float)])
    rows = pd.concat([firsts.assign(repeat=False), firsts.iloc[rep_pos].assign(repeat=True)], ignore_index=True)
    rows = rows.iloc[np.argsort(keys, kind="stable")].reset_index(drop=True)
    rows["showing"] = np.arange(len(rows), dtype=np.int64)
    first_at = {int(w): int(s) for w, s, r in zip(rows["window"], rows["showing"], rows["repeat"]) if not r}
    rows["first_showing"] = [first_at[int(w)] if r else -1 for w, r in zip(rows["window"], rows["repeat"])]
    lead = ["showing", "window", "repeat", "first_showing", "exam"]
    return rows[lead + [c for c in rows.columns if c not in lead]]


def sample_summary(sample, mapping=None):
    """What the sample is made of: per exam × predicted cluster (population, drawn, weight), per scale, the repeats."""
    firsts = sample[~sample["repeat"]]
    reps = sample[sample["repeat"]]
    gaps = [int(r["showing"]) - int(r["first_showing"]) for _, r in reps.iterrows()]
    clusters = (mapping or {}).get("clusters") or {}
    strata = []
    for (ek, c), g in firsts.groupby(["exam", "cluster"], sort=True):
        strata.append({"exam": ek, "cluster": int(c), "class": str(g["class"].iloc[0]),
                       "name": (clusters.get(str(int(c))) or {}).get("name") or "",
                       "population": int(g["stratum_size"].iloc[0]), "drawn": int(len(g)),
                       "weight": float(g["weight"].iloc[0])})
    by_scale = [{"exam": ek, "scale_min": float(s), "drawn": int(len(g))}
                for (ek, s), g in firsts.groupby(["exam", "scale_min"], sort=True)]
    return {"n": int(len(firsts)), "n_showings": int(len(sample)), "n_repeats": int(len(reps)),
            "min_gap": int(min(gaps)) if gaps else None, "strata": strata, "by_scale": by_scale,
            "by_exam": {ek: int((firsts["exam"] == ek).sum()) for ek, _ in EXAMS},
            "rule": ("test and exam windows only; N split equally between the two exams, then evenly per predicted "
                     "cluster (a cluster smaller than its share gives all it has); weight = the stratum's windows / "
                     "the windows drawn from it; a fraction shown twice, at least a quarter of the queue apart; the "
                     "order a seeded shuffle")}


# ── the run, its sample, its queue ─────────────────────────────────────────

def _run_results(conn, run_id):
    from Working.training import shape_forest as sf
    row = conn.execute("SELECT r.id, c.config_json FROM runs r JOIN configs c ON c.id = r.config_id WHERE r.id = ?",
                       (int(run_id),)).fetchone()
    if row is None or json.loads(row["config_json"]).get("kind") not in sf.B2_KINDS:      # forest or CNN (fixup-ai)
        raise LookupError(f"no B.2 run {run_id}")
    path, res = sf._results_of(conn, int(run_id))
    if res is None:
        raise LookupError(f"B.2 run {run_id} has no results yet (still running, or failed)")
    return path, res


def queue_for_run(conn, run_id):
    """The open blind queue of this run, as a dict with its filters, or None."""
    row = conn.execute("SELECT * FROM review_queues WHERE source_kind = ? AND source_ref = ? AND closed_at IS NULL "
                       "ORDER BY id LIMIT 1", (SOURCE_KIND, str(int(run_id)))).fetchone()
    if row is None:
        return None
    q = {k: row[k] for k in row.keys()}
    q["filters"] = json.loads(q["filters_json"] or "{}")
    return q


def make_queue(conn, run_id, *, n=DEFAULT_N, repeat_frac=DEFAULT_REPEAT_FRAC, seed=0):
    """*Label test windows blind*: draw (or re-use) the run's fixed sample and the queue over it.

    Returns `{"queue_id", "created", "sample_path", "summary"}`. A second call with the same settings returns the
    same queue; different settings raise `SampleFixed`."""
    from Working.database import runs as R
    from Working.review import queues as Q
    n, repeat_frac, seed = int(n), float(repeat_frac), int(seed)
    if n > MAX_N or n < 1:
        raise ValueError(f"a blind sample is 1 to {MAX_N:,} windows (asked for {n:,})")
    path, res = _run_results(conn, run_id)
    run_dir = os.path.dirname(path)
    sample_path = os.path.join(run_dir, SAMPLE_FILE)
    meta_path = os.path.join(run_dir, SAMPLE_META)
    want = {"n": n, "repeat_frac": repeat_frac, "seed": seed}
    if os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as fh:
            meta = json.load(fh)
        have = {k: meta["params"][k] for k in want}
        if have != want:
            raise SampleFixed(f"run {run_id}'s blind sample is fixed: N = {have['n']:,}, {have['repeat_frac']:.0%} shown "
                              f"twice, seed {have['seed']} (drawn {meta['drawn_at']}) — the same sample for every "
                              f"model; asked for N = {n:,}, {repeat_frac:.0%}, seed {seed}")
        sample = pd.read_parquet(sample_path)
    else:
        preds = pd.read_parquet(res["predictions_path"])
        sample = draw_sample(preds, n=n, repeat_frac=repeat_frac, seed=seed)
        sample.to_parquet(sample_path, index=False)
        meta = {"params": want, "drawn_at": _now(), "run_id": int(run_id), "pool": res.get("pool"),
                "summary": sample_summary(sample, res.get("mapping"))}
        _atomic_json(meta_path, meta)
        R.insert_artifact(conn, int(run_id), "other", sample_path)
        R.insert_artifact(conn, int(run_id), "other", meta_path)
        conn.commit()
    q = queue_for_run(conn, run_id)
    if q is not None:
        return {"queue_id": int(q["id"]), "created": False, "sample_path": sample_path, "summary": meta["summary"]}
    qid = Q.create_queue(
        conn, name=f"Blind test · B.2 run {int(run_id)}", source_kind=SOURCE_KIND, source_ref=str(int(run_id)),
        verdict_options=list(VERDICT_OPTIONS),
        filters={"run_id": int(run_id), "sample_path": sample_path, **want},
        note=("a seeded sample of the run's test and exam windows, labelled interesting / not WITHOUT the model's "
              "answer; each label is an annotations row over the window's span"))
    return {"queue_id": int(qid), "created": True, "sample_path": sample_path, "summary": meta["summary"]}


_SAMPLE_CACHE: dict = {}


def load_sample(path):
    """The fixed sample (read once per file version)."""
    st = os.stat(path)
    key = (os.path.abspath(path), st.st_mtime_ns, st.st_size)
    hit = _SAMPLE_CACHE.get(key[0])
    if hit is None or hit[0] != key:
        hit = (key, pd.read_parquet(path))
        _SAMPLE_CACHE[key[0]] = hit
    return hit[1]


def _filters(queue):
    try:
        f = queue["filters"]
        if isinstance(f, dict):
            return f
    except (KeyError, IndexError):
        pass
    return json.loads(queue["filters_json"] or "{}")


def _sample_of(queue):
    return load_sample(_filters(queue)["sample_path"])


def _answers(conn, queue_id):
    """`{showing: (annotation_id, verdict)}` — each showing's own live answer."""
    return {int(r[0]): (int(r[1]), r[2]) for r in conn.execute(
        "SELECT b.showing, a.id, a.verdict FROM blind_test_labels b JOIN annotations a ON a.id = b.annotation_id "
        "WHERE b.queue_id = ? AND a.deleted_at IS NULL", (int(queue_id),))}


def resolve_items(conn, q):
    """The queue's items: its showings in order, each with WHERE the window is and how long — and nothing else."""
    s = _sample_of(q)
    ans = _answers(conn, q["id"])
    out = []
    for sh, rid, ch, st, ln, fs in zip(s["showing"].to_numpy(), s["recording_id"].to_numpy(), s["channel"].to_numpy(),
                                       s["start"].to_numpy(), s["length"].to_numpy(), s["fs"].to_numpy()):
        sh = int(sh)
        a = ans.get(sh)
        out.append({"target_id": sh, "unit": UNIT, "showing": sh, "recording_id": int(rid), "channel": int(ch),
                    "start_idx": int(st), "end_idx": int(st) + int(ln), "length": int(ln), "fs": float(fs),
                    "duration_s": float(ln) / float(fs), "judged": a is not None, "verdict": a[1] if a else None,
                    "tags": []})
    return out


def showing_target(conn, queue, target_id):
    """`(showing, annotation id or None)` for a verdict through `verdicts.write_verdict`."""
    try:
        sh = int(target_id)
    except (TypeError, ValueError):
        raise ValueError(f"a blind queue's target is a showing number, got {target_id!r}")
    s = _sample_of(queue)
    if not 0 <= sh < len(s):
        raise ValueError(f"blind queue {queue['id']} has {len(s)} showings; there is no showing {sh}")
    a = _answers(conn, queue["id"]).get(sh)
    return sh, (a[0] if a else None)


def label_note(queue_id, run_id, row, n_showings):
    text = (f"blind test label · queue {int(queue_id)} · B.2 run {int(run_id)} · showing {int(row['showing']) + 1} "
            f"of {int(n_showings)} · the model's answer was hidden")
    if bool(row["repeat"]):
        text += " · second showing of a window, for self-agreement"
    return text


def write_showing_verdict(conn, queue, showing, verdict, note=None, tags=None):
    """One human answer on one showing, into `annotations` over the window's span. Returns `(prior, annotation_id)`;
    `prior` is `{"inserted": True}` for a new row, so undo withdraws it. The first answer on an exam marks it
    scored (the freeze)."""
    from Working.database import queries as _queries
    from Working.database import vocabulary as _vocabulary
    if verdict not in VERDICT_OPTIONS:
        raise ValueError(f"a blind test queue takes {', '.join(VERDICT_OPTIONS)}; got {verdict!r}")
    s = _sample_of(queue)
    sh = int(showing)
    row = s.iloc[sh]
    run_id = int(_filters(queue)["run_id"])
    text = label_note(queue["id"], run_id, row, len(s))
    if note:
        text = f"{text} — {note}"
    existing = _answers(conn, queue["id"]).get(sh)
    if existing is not None:
        aid = existing[0]
        old = _queries.get_annotation(conn, aid)
        prior = {"verdict": old["verdict"], "note": old["note"], "tags": _vocabulary.get_annotation_tags(conn, aid)}
        conn.execute("UPDATE annotations SET verdict = ?, note = ? WHERE id = ?", (verdict, text, aid))
    else:
        aid = _queries.insert_annotation(conn, int(row["recording_id"]), int(row["start"]),
                                         int(row["start"]) + int(row["length"]), verdict, source=REVIEW_SOURCE,
                                         note=text, commit=False)
        conn.execute("INSERT INTO blind_test_labels (queue_id, showing, annotation_id, created_at) VALUES (?, ?, ?, ?) "
                     "ON CONFLICT (queue_id, showing) DO UPDATE SET annotation_id = excluded.annotation_id, "
                     "created_at = excluded.created_at", (int(queue["id"]), sh, int(aid), _now()))
        prior = {"inserted": True}
    if tags:
        for category, values in tags.items():
            _vocabulary.set_annotation_tags(conn, aid, category, values, commit=False)
    mark_scored(conn, run_id, str(row["exam"]), int(queue["id"]))
    return prior, int(aid)


def mark_scored(conn, run_id, exam, queue_id):
    """The first blind label on an exam is a score: the run's results say so, and `shape_forest.frozen_for` reads
    exactly that — from now on the pool's cut and mapping are frozen. Never un-marked (an undone label was still
    seen)."""
    path, res = _run_results(conn, run_id)
    ex = (res.get("exams") or {}).get(exam)
    if ex is None or ex.get("status") == "scored":
        return False
    ex["status"] = "scored"
    ex["scored_by"] = {"kind": "blind human labels", "queue_id": int(queue_id), "first_label_at": _now(),
                       "note": ("the first blind label is a score: the pool's cut and interesting / not mapping are "
                                "frozen from here; the figures are on Models › Results › against a blind human")}
    res["yardstick_B"] = {"status": "labelling", "queue_id": int(queue_id),
                          "reason": "blind interesting / not labels are being given in Review"}
    _atomic_json(path, res)
    return True


def labels(conn, queue_id):
    """The sample with each showing's human answer (`human`, None when unanswered) and its `annotation_id`."""
    from Working.review import queues as Q
    q = Q.get_queue(conn, int(queue_id))
    if q is None:
        raise LookupError(f"no review queue {queue_id}")
    s = _sample_of(q).copy()
    ans = _answers(conn, int(queue_id))
    s["human"] = [ans[int(x)][1] if int(x) in ans else None for x in s["showing"]]
    s["annotation_id"] = [ans[int(x)][0] if int(x) in ans else None for x in s["showing"]]
    return s


# ── the scores ──────────────────────────────────────────────────────────────

def _units(df):
    span = (BLOCK_HOURS * 3600.0 * df["fs"].astype(float)).round().clip(lower=1).astype(np.int64)
    return np.array([f"{int(r)}:{int(s) // int(sp)}" for r, s, sp in zip(df["recording_id"], df["start"], span)],
                    dtype=object)


def _boot(units, n_boot, seed, fn):
    """`fn(index array)` over `n_boot` resamples of whole units (the block bootstrap of `metrics`)."""
    uniq = np.unique(units)
    members = [np.flatnonzero(units == u) for u in uniq]
    rng = np.random.default_rng(int(seed))
    out = []
    for _ in range(int(n_boot)):
        pick = rng.integers(0, len(uniq), len(uniq))
        idx = np.concatenate([members[i] for i in pick]) if len(pick) else np.zeros(0, dtype=int)
        v = fn(idx)
        if v is not None:
            out.append(v)
    return out


def _ci(values):
    from Working.training.metrics import _ci as mci
    return mci(values) if values else [None, None]


def _small(y, p):
    """Scores on a slice (a scale, a recording): macro F1 and kappa only when both classes are there."""
    from Working.training import metrics as tm
    y = np.asarray(y, dtype=object)
    p = np.asarray(p, dtype=object)
    n = int(len(y))
    out = {"n": n, "human_interesting": int((y == "interesting").sum()),
           "model_interesting": int((p == "interesting").sum()),
           "agreement": float((y == p).mean()) if n else None}
    if n == 0:
        return {**out, "one_class": False, "macro_f1": None, "kappa": None, "precision": None, "recall": None}
    sc = tm.classification_scores(y, p, SCORED)
    one = len(set(y.tolist())) < 2
    pi = sc["per_class"]["interesting"]
    return {**out, "one_class": bool(one), "macro_f1": None if one else sc["macro_f1"],
            "kappa": None if one else tm.cohen_kappa(y, p, SCORED),
            "precision": pi["precision"] if pi["n_predicted"] else None, "recall": pi["recall"] if pi["n"] else None}


def self_agreement(lab, role=None):
    """The human against themself on the windows shown twice."""
    from Working.training import metrics as tm
    reps = lab[lab["repeat"]]
    if role is not None:
        reps = reps[reps["role"] == role]
    by_showing = dict(zip(lab["showing"].astype(int), lab["human"]))
    pairs = [(by_showing.get(int(f)), h) for f, h in zip(reps["first_showing"], reps["human"])]
    answered = [(a, b) for a, b in pairs if a is not None and b is not None]
    scored = [(a, b) for a, b in answered if a in SCORED and b in SCORED]
    agree = sum(1 for a, b in scored if a == b)
    return {"n_pairs": len(pairs), "n_answered_pairs": len(answered), "n_scored_pairs": len(scored),
            "agree": int(agree), "share": (agree / len(scored)) if scored else None,
            "any_word_share": (sum(1 for a, b in answered if a == b) / len(answered)) if answered else None,
            "kappa": tm.cohen_kappa([a for a, _ in scored], [b for _, b in scored], SCORED) if scored else None,
            "note": ("the same window shown twice, at least a quarter of the queue apart: how often the human gave "
                     "the same interesting / not answer. No model can be expected to agree with the human more "
                     "than the human agrees with themself")}


def _exam_scores(f, lab, role, mapping, n_boot, n_null, seed):
    from Working.training import metrics as tm
    clusters = (mapping or {}).get("clusters") or {}
    k = int((mapping or {}).get("k") or (max(int(c) for c in clusters) if clusters else 0))
    hv = f["human"]
    excluded = {"unsure": int((hv == "unsure").sum()), "artifact": int((hv == "artifact").sum()),
                "not_yet_labelled": int(hv.isna().sum())}
    sc = f[hv.isin(SCORED)]
    n_lab = int(hv.notna().sum())
    status = "not yet labelled" if n_lab == 0 else ("labelled" if n_lab == len(f) else "labelling")
    sa = self_agreement(lab, role)
    out = {"status": status, "n_sample": int(len(f)), "n_labelled": n_lab, "n_scored": int(len(sc)),
           "excluded": excluded, "self_agreement": sa,
           "unit": f"{BLOCK_HOURS:g} h of one channel", "confusion_labels": list(SCORED),
           "confusion_note": "rows: the blind human · columns: the model (its cluster through the frozen mapping)"}
    per_cluster = []
    for c in range(1, k + 1):
        g = f[f["cluster"] == c]
        gs = g[g["human"].isin(SCORED)]
        cls = (clusters.get(str(c)) or {}).get("class")
        hi = int((gs["human"] == "interesting").sum())
        per_cluster.append({"cluster": c, "name": (clusters.get(str(c)) or {}).get("name") or "", "class": cls,
                            "n_sample": int(len(g)), "n": int(len(gs)), "human_interesting": hi,
                            "share_interesting": (hi / len(gs)) if len(gs) else None,
                            "agrees_with_mapping": (float((gs["human"] == cls).mean()) if len(gs) else None),
                            "population": int(g["stratum_size"].iloc[0]) if len(g) else 0})
    out["per_cluster"] = per_cluster
    empty_null = {"n": int(n_null), "mean": None, "q95": None, "p": None, "draws": [],
                  "rule": "the human's answers permuted against the model's fixed calls"}
    if sc.empty:
        out.update({"macro_f1": None, "macro_f1_ci": [None, None], "kappa": None, "kappa_ci": [None, None],
                    "accuracy": None, "confusion": [[0, 0], [0, 0]],
                    "interesting": {"precision": None, "recall": None, "f1": None, "f1_ci": [None, None]},
                    "null": empty_null, "per_scale": [], "per_recording": [], "n_units": 0,
                    "reweighted": {"note": "no window of this exam is labelled interesting / not yet"}})
        return out
    y = sc["human"].to_numpy(dtype=object)
    p = sc["class"].to_numpy(dtype=object)
    cs = tm.classification_scores(y, p, SCORED)
    units = _units(sc)
    bb = tm.block_bootstrap(y, {"model": p}, units, SCORED, n=n_boot, seed=seed)
    kap = tm.cohen_kappa(y, p, SCORED)
    kd = _boot(units, n_boot, seed, lambda idx: tm.cohen_kappa(y[idx], p[idx], SCORED) if len(idx) else None)
    pi = cs["per_class"]["interesting"]
    rng = np.random.default_rng(int(seed) + 1)
    draws = [tm.macro_f1(rng.permutation(y), p, SCORED) for _ in range(int(n_null))]
    w = sc["weight"].to_numpy(dtype=float)
    tp = float(w[(y == "interesting") & (p == "interesting")].sum())
    fp = float(w[(y != "interesting") & (p == "interesting")].sum())
    fn = float(w[(y == "interesting") & (p != "interesting")].sum())
    rw_p = tp / (tp + fp) if tp + fp else None
    rw_r = tp / (tp + fn) if tp + fn else None
    out.update({
        "macro_f1": cs["macro_f1"], "macro_f1_ci": bb["arms"]["model"]["macro_f1_ci"],
        "accuracy": cs["accuracy"], "balanced_accuracy": cs["balanced_accuracy"],
        "kappa": kap, "kappa_ci": _ci(kd), "confusion": cs["confusion"],
        "interesting": {"precision": pi["precision"], "recall": pi["recall"], "f1": pi["f1"],
                        "f1_ci": bb["arms"]["model"]["per_class_f1_ci"][0], "n_human": pi["n"],
                        "n_model": pi["n_predicted"]},
        "not_interesting": cs["per_class"]["not_interesting"],
        "null": {**empty_null, "mean": float(np.mean(draws)), "q95": float(np.quantile(draws, 0.95)),
                 "p": tm.null_p(cs["macro_f1"], draws), "draws": [float(x) for x in draws[:200]]},
        "n_units": int(len(np.unique(units))),
        "reweighted": {"precision": rw_p, "recall": rw_r,
                       "f1": (2 * rw_p * rw_r / (rw_p + rw_r)) if rw_p and rw_r else None,
                       "accuracy": float(w[y == p].sum() / w.sum()) if w.sum() else None,
                       "note": ("each labelled window weighted by its stratum's windows / the windows drawn from it "
                                "(exam × predicted cluster): an estimate for every test window of this exam, not "
                                "only the sample, which over-represents rare clusters on purpose")},
        "per_scale": [{"scale_min": float(s), "outside_training_scale": bool(float(s) != TRAINING_SCALE_MIN),
                       **_small(g["human"], g["class"])} for s, g in sc.groupby("scale_min", sort=True)],
        "per_recording": [{"recording": str(r), **_small(g["human"], g["class"])}
                          for r, g in sc.groupby("source_file", sort=True)],
    })
    return out


def contaminated(conn, lab):
    """For each row: does the window overlap an EARLIER human label (any human store but this queue's own)?"""
    from Adapters.catalogue_manual_labels import human_spans
    out = np.zeros(len(lab), dtype=bool)
    for rid, idx in lab.groupby("recording_id").groups.items():
        # this queue's own rows (and any other blind queue's) are not an EARLIER label
        spans = [(s, e) for s, e, _v, src in human_spans(conn, int(rid)) if src != REVIEW_SOURCE]
        if not spans:
            continue
        a = np.array(spans, dtype=np.int64)
        for i in idx:
            st = int(lab.at[i, "start"])
            en = st + int(lab.at[i, "length"])
            out[lab.index.get_loc(i)] = bool(((a[:, 0] < en) & (a[:, 1] > st)).any())
    return out


def score(conn, run_id, *, n_boot=1000, n_null=1000, seed=0):
    """Models › Results — the run against a blind human, per exam, never pooled."""
    path, res = _run_results(conn, run_id)
    from Working.review import queues as Q
    base = {"run_id": int(run_id), "k": int(res["arm"]["k"]), "mapping": res.get("mapping"), "pool": res.get("pool"),
            "arm": res.get("arm"), "template": res.get("template"), "exam_titles": EXAM_TITLES,
            "predicted": {ek: {kk: (res["exams"].get(ek) or {}).get(kk) for kk in ("n", "by_class", "by_cluster", "status")}
                          for ek, _ in EXAMS}}
    q = queue_for_run(conn, run_id)
    if q is None:
        return {**base, "queue_id": None, "status": "no blind queue yet", "exams": {}, "sample": None,
                "reference": {"status": "not computed", "rows": []}}
    lab = labels(conn, int(q["id"]))
    counts = Q.queue_counts(conn, int(q["id"]))
    run_dir = os.path.dirname(path)
    meta_path = os.path.join(run_dir, SAMPLE_META)
    sample_meta = None
    if os.path.isfile(meta_path):
        with open(meta_path, encoding="utf-8") as fh:
            sample_meta = json.load(fh)
    firsts = lab[~lab["repeat"]]
    exams = {ek: {"title": EXAM_TITLES[ek], **_exam_scores(firsts[firsts["role"] == role], lab, role, res.get("mapping"),
                                                          n_boot, n_null, seed)}
             for ek, role in EXAMS}
    verdicts = {v: int((lab["human"] == v).sum()) for v in VERDICT_OPTIONS}
    return {**base, "queue_id": int(q["id"]), "status": "labelling" if counts["remaining"] else "labelled",
            "progress": {**counts, "pace_s": Q.queue_pace_s(conn, int(q["id"]))},
            "verdicts": verdicts, "sample": sample_meta, "exams": exams, "self_agreement": self_agreement(lab),
            "reference": reference_section(conn, run_dir, lab)}


def disagreements(conn, run_id, exam, kind):
    """The windows where the model and the blind human disagree, one way: `model_yes_human_no` or
    `model_no_human_yes` (first showings only)."""
    role = dict(EXAMS).get(exam)
    if role is None:
        raise ValueError(f"exam is one of {', '.join(e for e, _ in EXAMS)}; got {exam!r}")
    want = {"model_yes_human_no": ("interesting", "not_interesting"),
            "model_no_human_yes": ("not_interesting", "interesting")}.get(kind)
    if want is None:
        raise ValueError("kind is model_yes_human_no or model_no_human_yes")
    q = queue_for_run(conn, run_id)
    if q is None:
        return []
    lab = labels(conn, int(q["id"]))
    f = lab[(~lab["repeat"]) & (lab["role"] == role) & (lab["class"] == want[0]) & (lab["human"] == want[1])]
    return [{"showing": int(r["showing"]), "window": int(r["window"]), "recording_id": int(r["recording_id"]),
             "source_file": str(r["source_file"]), "channel": int(r["channel"]), "start": int(r["start"]),
             "length": int(r["length"]), "fs": float(r["fs"]), "scale_min": float(r["scale_min"]),
             "cluster": int(r["cluster"]), "model_class": str(r["class"]),
             "p_interesting": float(r["p_interesting"]), "human": str(r["human"])} for _, r in f.iterrows()]


# ── the comparison line ─────────────────────────────────────────────────────

def reference_image(window, image_type):
    """The window AS IT IS → the image the manual-label CNN was trained on (n × n for n samples; the recurrence
    image (n − 8) × (n − 8)), before the network's transform resizes it to 224 × 224."""
    from Working.Catalogue.cnn.apply_cnn import _window_to_pil
    return _window_to_pil(np.asarray(window, dtype=np.float64), image_type)


def reference_tensor(window, image_type):
    from Working.Catalogue.cnn.cnn_rangapur import get_transforms
    t = get_transforms(224, is_train=False, is_rgb=(image_type == "fusion"))
    return t(reference_image(window, image_type)).unsqueeze(0)


def how_fed(m):
    if m["kind"] == "rf":
        return ("the raw window as it is (its n samples) to the catch22 pipeline, P(interesting) = class 1; nothing "
                "resampled")
    return (f"the raw window as it is: its n samples → an n × n {m['image']} image, resized to 224 × 224 by the "
            "network's own transform; nothing resampled. P(interesting) = class 0, as the window matrix reads it")


def _checkpoint_classes(path):
    import torch
    ck = torch.load(path, map_location="cpu", weights_only=True)
    w = ck.get("backbone.classifier.1.weight") if hasattr(ck, "get") else None
    return int(w.shape[0]) if w is not None else None


def reference_probabilities(conn, rows, models_dir, progress=None, cancel=None):
    """P(interesting) of every reference model for every window in `rows` (one per window), and each model's status."""
    probs = {}
    meta = {}
    recs = {int(r[0]): r[1] for r in conn.execute("SELECT id, npy_path FROM recordings")}
    rows = rows.reset_index(drop=True)
    windows = []
    for rid, g in rows.groupby("recording_id", sort=True):
        x = np.load(recs[int(rid)], mmap_mode="r")
        for i, st, ln in zip(g.index, g["start"], g["length"]):
            windows.append((int(i), np.asarray(x[int(st):int(st) + int(ln)], dtype=np.float64)))
    windows.sort()
    for mi, m in enumerate(REFERENCE_MODELS):
        f = os.path.join(models_dir, m["file"])
        info = {"file": f, "image": m["image"], "kind": m["kind"], "how_fed": how_fed(m)}
        meta[m["model"]] = info
        if not os.path.isfile(f):
            info.update(status="not scored", reason=f"{f} is not on this machine")
            continue
        if progress is not None:
            progress(mi, len(REFERENCE_MODELS), f"{m['model']}: {len(windows):,} windows")
        try:
            if m["kind"] == "cnn":
                ncls = _checkpoint_classes(f)
                info["n_classes"] = ncls
                if ncls != 2:
                    info.update(status="not scored", reason=(
                        f"{m['file']} has {ncls} output class{'es' if ncls != 1 else ''}, not interesting / not: "
                        + ("its softmax is 1.0 for every window (AB measured it calling everything interesting)"
                           if ncls == 1 else "a different question's model")))
                    continue
                probs[m["model"]] = _cnn_probs(f, m["image"], windows, cancel)
            else:
                probs[m["model"]] = _rf_probs(f, windows, cancel)
            info["status"] = "scored"
        except InterruptedError:
            raise
        except Exception as e:      # one model failing is its row's reason, never the job's failure
            info.update(status="not scored", reason=f"{type(e).__name__}: {e}")
    return pd.DataFrame(probs, index=range(len(windows))), meta


def _cnn_probs(path, image_type, windows, cancel):
    import torch
    import torch.nn.functional as F
    from Working.Catalogue.cnn.apply_cnn import load_model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_model(path, device)
    out = np.full(len(windows), np.nan)
    for b in range(0, len(windows), 32):
        if cancel is not None and cancel():
            raise InterruptedError("cancelled while scoring the reference line")
        batch = windows[b:b + 32]
        tens, ok = [], []
        for i, w in batch:
            try:
                tens.append(reference_tensor(w, image_type))
                ok.append(i)
            except Exception:
                pass
        if tens:
            with torch.no_grad():
                pr = F.softmax(model(torch.cat(tens, dim=0).to(device)), dim=1).cpu().numpy()
            for i, row in zip(ok, pr):
                out[i] = float(row[0])
    return out


def _rf_probs(path, windows, cancel):
    import sys
    import joblib
    from Working.Catalogue.aeon_classification.classification import ThresholdedPipeline
    sys.modules["__main__"].ThresholdedPipeline = ThresholdedPipeline
    model = joblib.load(path)
    out = np.full(len(windows), np.nan)
    for i, w in windows:
        if cancel is not None and cancel():
            raise InterruptedError("cancelled while scoring the reference line")
        try:
            out[i] = float(model.predict_proba(w.reshape(1, 1, -1).astype(np.float32))[0, 1])
        except Exception:
            try:
                out[i] = float(model.predict_proba(w.reshape(1, -1).astype(np.float32))[0, 1])
            except Exception:
                pass
    return out


def run_reference(conn, run_id, models_dir, progress=None, cancel=None):
    """Score the comparison line on the run's blind sample (every window, labelled or not), and keep it on disk."""
    path, _res = _run_results(conn, run_id)
    q = queue_for_run(conn, run_id)
    if q is None:
        raise LookupError(f"B.2 run {run_id} has no blind queue yet: make one first")
    s = _sample_of(q)
    firsts = s[~s["repeat"]].reset_index(drop=True)
    probs, meta = reference_probabilities(conn, firsts, models_dir, progress=progress, cancel=cancel)
    probs.insert(0, "window", firsts["window"].to_numpy())
    run_dir = os.path.dirname(path)
    probs.to_parquet(os.path.join(run_dir, REFERENCE_FILE), index=False)
    _atomic_json(os.path.join(run_dir, REFERENCE_META), {"computed_at": _now(), "models_dir": models_dir,
                                                          "n_windows": int(len(firsts)), "models": meta})
    return {"n_windows": int(len(firsts)), "models": meta}


def _ref_stats(y, pr):
    if not len(y):
        return {"n": 0, "macro_f1": None, "kappa": None, "precision": None, "recall": None, "one_class": False,
                "human_interesting": 0, "model_interesting": 0, "agreement": None}
    pred = np.where(pr >= 0.5, "interesting", "not_interesting").astype(object)
    return _small(y, pred)


def score_reference(lab, probs, meta, *, contaminated):
    """One row per reference model per SCALE (never pooled): its scores on each exam's blind-labelled first showings,
    on all of them and on those overlapping no earlier human label. `probs` is aligned row-for-row with `lab`."""
    lab = lab.reset_index(drop=True)
    probs = probs.reset_index(drop=True)
    clean = ~np.asarray(contaminated, dtype=bool)
    keep = (~lab["repeat"].to_numpy(dtype=bool)) & lab["human"].isin(SCORED).to_numpy()
    scales = sorted({float(s) for s in lab.loc[keep, "scale_min"]}) or sorted({float(s) for s in lab["scale_min"]})
    rows = []
    for model in probs.columns:
        m = meta.get(model) or {}
        image = m.get("image")
        kind = m.get("kind") or ("rf" if image is None else "cnn")
        p_all = probs[model].to_numpy(dtype=float)
        finite = p_all[np.isfinite(p_all)]
        constant = len(finite) > 0 and float(finite.max() - finite.min()) < 1e-9
        status = m.get("status") or "scored"
        reason = m.get("reason")
        if status == "scored" and constant:
            status = "not scored"
            reason = (f"its output is constant (p = {float(finite.max()):.3g} for every window): the checkpoint does "
                      "not separate the classes as loaded")
        if status == "scored" and not len(finite):
            status, reason = "not scored", "the model produced no probability for these windows (see the server log)"
        for s in scales:
            row = {"model": model, "file": m.get("file"), "image": image, "kind": kind, "scale_min": s,
                   "outside_training_scale": bool(s != TRAINING_SCALE_MIN),
                   "how_fed": m.get("how_fed") or how_fed({"kind": kind, "image": image}),
                   "embedding": _EMBEDDING.get(image, _EMBEDDING[None]), "contamination": CONTAMINATION,
                   "status": status, "reason": reason, "exams": {}}
            if status == "scored":
                for ek, role in EXAMS:
                    sel = keep & (lab["role"].to_numpy() == role) & (lab["scale_min"].to_numpy(dtype=float) == s) \
                        & np.isfinite(p_all)
                    y = lab["human"].to_numpy(dtype=object)
                    row["exams"][ek] = {"all": _ref_stats(y[sel], p_all[sel]),
                                        "no_earlier_label": _ref_stats(y[sel & clean], p_all[sel & clean]),
                                        "n_overlapping_earlier_label": int((sel & ~clean).sum())}
            rows.append(row)
    return rows


def reference_section(conn, run_dir, lab):
    """The comparison line for Results: computed (from the run's `blind_reference.*`) or what would be computed."""
    pf, mf = os.path.join(run_dir, REFERENCE_FILE), os.path.join(run_dir, REFERENCE_META)
    if not (os.path.isfile(pf) and os.path.isfile(mf)):
        return {"status": "not computed", "rows": [],
                "models": [{"model": m["model"], "file": m["file"], "image": m["image"], "how_fed": how_fed(m)}
                           for m in REFERENCE_MODELS],
                "note": "Score the comparison line runs every reference model on the sample's windows (a job)"}
    probs = pd.read_parquet(pf)
    with open(mf, encoding="utf-8") as fh:
        meta = json.load(fh)
    by_window = probs.set_index("window")
    cols = [c for c in probs.columns if c != "window"]
    aligned = pd.DataFrame({c: by_window[c].reindex(lab["window"].to_numpy()).to_numpy() for c in cols})
    for name, m in meta["models"].items():
        if name not in aligned.columns:
            aligned[name] = np.nan
    flags = contaminated(conn, lab)
    rows = score_reference(lab, aligned, meta["models"], contaminated=flags)
    keep = (~lab["repeat"]) & lab["human"].isin(SCORED)
    return {"status": "computed", "computed_at": meta.get("computed_at"), "n_windows": meta.get("n_windows"),
            "rows": rows, "n_labelled": int(keep.sum()),
            "n_overlapping_earlier_label": int((np.asarray(flags) & keep.to_numpy()).sum()),
            "contamination": CONTAMINATION, "training_scale_min": TRAINING_SCALE_MIN}
