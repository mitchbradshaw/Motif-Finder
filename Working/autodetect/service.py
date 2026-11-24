"""
service.py
==========
Auto-detect for one recording, as the app runs it (2026-11-23: "integrate the auto-detect into the site"): everything
`pipeline.auto_detect_both` needs, read from the database and the model files; the result written to disk and read
back for the page; and the researcher's *send to Review*.

    run(conn, rec, ...)        one channel (or a stretch of it), with progress, a time estimate and cancel
    save / load / results      the result on disk: candidates.csv, sequences.csv, run.json - never in the database
    payload(...)               what the page draws: candidates column by column, sequences, the run's notes
    send_to_review(...)        candidates as machine detections in a listed detection queue (the path the Library's
                               candidate-event queues use), sequences through `sequence_queue.send_to_sequence_review`

The line-up is the reference runs' (docs/autodetect/20261123_v4): the four detector templates over the whole
stretch, drop v1 and v5 also in 6-hour windows, BEADS -> 10 sigma, the tight seed families, the researcher's event
rule as a finder, R4 (`r4.py`) scoring every candidate and scanning windows, all run on the signal and again on the
inverted signal. Bulk arrays never enter the database (CLAUDE.md rule 4); a send writes machine rows only - the
detections and the candidate sequences - never a verdict (rule 5).

No plotting library, no web framework - CLAUDE.md rule 1.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import time

import numpy as np
import pandas as pd

from Working.autodetect import gates, r4
from Working.autodetect.pipeline import auto_detect_both
from Working.autodetect.seeds import MIN_FAMILY_LINE, SeedFamily
from Working.units import read_as_mv

#: Where results are kept, relative to the repository root like every core path (the web bridge's sandbox points
#: it into its runtime directory, as it does the adapters' results).
RESULTS_DIR = os.path.join("DATA", "derived", "autodetect")
#: The seed bank (64 shape families of the 9 Nov accepted catalogue's single events; built by
#: `scripts/autodetect/build_seed_bank.py`), shipped beside this module.
SEED_BANK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_bank")
#: The four detector templates (the researcher, 2026-11-19, Q8 (b)), by name.
DETECTORS = ("drop_detection_v1", "drop_detection_v5", "wavelet_encoded", "BEADs_invert_detect_v1")
#: Drop v1 and v5 also run over 6-hour sliding windows (2026-11-23, Q3 (a)).
WINDOWED = {"drop_detection_v1": 6 * 3600.0, "drop_detection_v5": 6 * 3600.0}
#: BEADS -> threshold with the cut from the local noise (2026-11-23, Q3 (a)).
BEADS_SIGMA = [
    {"stage": "preprocessing", "algorithm": "beads",
     "params": {"baseline_period_s": 60.0, "filter_order": 2, "polarity": "drop", "sparsity": 1}},
    {"stage": "detection", "algorithm": "noise_threshold",
     "params": {"direction": "either", "k_sigma": 10.0, "noise_from": "rolling", "noise_window_s": 3600.0,
                "merge_gap_s": 0.0, "min_duration_s": 2.0}},
]
#: The version of the line-up a result says it came from.
VERSION = "v4"
#: Seconds per sample the four reference channels took (2026-11-23: 4.5-12 minutes for 1.8-1.9 M samples, both runs)
#: - the estimate before any stage has finished.
SECONDS_PER_SAMPLE = 2.6e-4
#: ...plus what any run costs whatever its length (the seed search's and the boxes' set-up, the first compile): a
#: 4-hour stretch at 2 Hz took 21 s where the per-sample figure alone says 7 s.
FIXED_S = 15.0


class Cancelled(Exception):
    """The run was cancelled between two stages."""


# ── what the run needs ──────────────────────────────────────────────────────

def detector_specs(conn):
    """``(specs, missing)``: the line-up as `pipeline.detector_specs` reads it, and the templates this database does
    not hold (a run goes on without them and says so)."""
    steps, missing = {}, []
    for name in DETECTORS:
        row = conn.execute("SELECT steps_json FROM templates WHERE name = ? ORDER BY id LIMIT 1", (name,)).fetchone()
        if row is None:
            missing.append(name)
            continue
        steps[name] = json.loads(row[0])
    specs = [{"variant": name, "steps": st, "window_s": None, "fit": False} for name, st in steps.items()]
    specs += [{"variant": f"{name}__w{w / 3600:g}h", "steps": steps[name], "window_s": w, "fit": False}
              for name, w in WINDOWED.items() if name in steps]
    specs.append({"variant": "beads_sigma", "steps": BEADS_SIGMA, "window_s": None, "fit": False})
    return specs, missing


def noise_floor_mv(conn, source_file):
    """``(floor, where)``: Settings › Datasets' ``meta.<stem>.noise_floor`` (a derived copy, ``_fs2``, reads its
    parent's), else the Library's instrument floor."""
    from Working.library.view_filter import DEFAULT_FLOOR_MV, FLOOR_KEY, FLOOR_PAGE
    stem = os.path.splitext(os.path.basename(str(source_file)))[0]
    for s in (stem, re.sub(r"_fs\d+(p\d+)?$", "", stem)):
        row = conn.execute("SELECT value_json FROM settings WHERE page = ? AND key = ?",
                           (FLOOR_PAGE, FLOOR_KEY.format(stem=s))).fetchone()
        if row is not None:
            try:
                v = float(json.loads(row[0]))
                if v > 0:
                    return v, f"Settings › Datasets meta.{s}.noise_floor"
            except (TypeError, ValueError):
                pass
    return float(DEFAULT_FLOOR_MV), "the Library's instrument floor (none set for this dataset)"


def load_seed_bank(where=SEED_BANK_DIR):
    """The seed families and the bank's own description."""
    with open(os.path.join(where, "seed_bank.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    arr = np.load(os.path.join(where, "seed_bank.npz"))
    fams = [SeedFamily(label=f["label"], exemplar_mv=np.asarray(arr[f["label"]], dtype=float),
                       exemplar_fs=float(f["exemplar_fs"]), durations_s=tuple(f["durations_s"]),
                       min_corr=float(f["min_corr"]), n_members=int(f["n_members"]), provenance=f["medoid"])
            for f in meta["families"]]
    return fams, meta


def setup(conn, *, model_path=r4.MODEL, seed_bank=SEED_BANK_DIR):
    """What a run here would use, and what is missing: ``ready`` False when R4's model or the seed bank is absent."""
    _specs, missing = detector_specs(conn)
    problems = []
    if not os.path.isfile(model_path):
        problems.append(f"R4's model is not at {model_path}")
    if not os.path.isfile(os.path.join(seed_bank, "seed_bank.npz")):
        problems.append(f"the seed bank is not at {seed_bank}")
    return {"ready": not problems, "problems": problems, "missing_detectors": missing, "version": VERSION,
            "model": model_path, "seed_bank": seed_bank, "seconds_per_sample": SECONDS_PER_SAMPLE, "fixed_s": FIXED_S,
            "rules": {"rise_sharpness": gates.MIN_RISE_SHARPNESS, "min_steady_samples": gates.MIN_STEADY_SAMPLES,
                      "min_significance": gates.MIN_SIGNIFICANCE}}


def estimate_s(n_samples):
    """A first guess at a run's length, from the reference channels and one short stretch."""
    return float(FIXED_S + SECONDS_PER_SAMPLE * max(0, int(n_samples)))


# ── progress ────────────────────────────────────────────────────────────────

#: Each stage's share of one pass, from the reference runs' timings (the boxes and the detectors dominate).
_STAGE_WEIGHT = (("detector", 0.016), ("seed search", 0.08), ("the event rule", 0.01), ("merge", 0.005),
                 ("boxes", 0.25), ("R4 window scan", 0.06), ("gates", 0.01), ("R4 on", 0.01), ("sequences", 0.002))


def _weight(stage):
    for key, w in _STAGE_WEIGHT:
        if stage.startswith(key):
            return w
    return 0.005


class Progress:
    """Turns the pipeline's stage messages into a fraction done and a time left. A stage is done when the next one
    starts; until a tenth is done the estimate is the size-based one."""

    def __init__(self, n_detectors, n_samples, report):
        per_pass = n_detectors * _weight("detector") + sum(w for k, w in _STAGE_WEIGHT if k != "detector")
        self.total = 2.0 * per_pass
        self.done = 0.0
        self.current = None
        self.t0 = time.perf_counter()
        self.first_guess = estimate_s(n_samples)
        self.report = report

    def __call__(self, message):
        run, _, stage = str(message).partition(": ")
        if self.current is not None:
            self.done += _weight(self.current)
        self.current = stage or run
        frac = min(0.99, self.done / self.total)
        elapsed = time.perf_counter() - self.t0
        left = (elapsed / frac - elapsed) if frac >= 0.1 else max(0.0, self.first_guess - elapsed)
        what = {"normal": "the signal", "inverted": "the inverted signal"}.get(run, run)
        self.report(frac, f"{what}: {self.current}", left)


# ── the run ─────────────────────────────────────────────────────────────────

def run(conn, rec, x_native, *, start_idx=0, end_idx=None, model=None, model_path=r4.MODEL, families=None,
        on_progress=None, cancelled=None):
    """Auto-detect on recording ``rec`` (a recordings row as a dict), samples ``start_idx:end_idx`` of ``x_native``
    (the stored samples, memory-mapped). ``on_progress(fraction, message, seconds_left)``; ``cancelled()`` is asked
    between stages and stops the run with `Cancelled`. Returns ``(result, meta)``."""
    fs = float(rec["fs"])
    n_total = len(x_native)
    a = max(0, int(start_idx))
    b = n_total if end_idx is None else min(n_total, int(end_idx))
    if b - a < 10:
        raise ValueError(f"the stretch {a}-{b} is too short to search")
    factor, _note = read_as_mv(rec.get("units"))
    specs, missing = detector_specs(conn)
    floor, floor_src = noise_floor_mv(conn, rec["source_file"])
    from Working.discovery.matching import rule_from_settings
    rule = rule_from_settings(conn)
    model = r4.load_model(model_path) if model is None else model
    if families is None:
        families, _bank = load_seed_bank()
    x_mv_full = np.asarray(x_native, dtype=np.float64) * factor
    x = np.asarray(x_native[a:b], dtype=np.float64)

    def report(frac, message, left):
        if on_progress is not None:
            on_progress(frac, message, left)

    tracker = Progress(len(specs), b - a, report)

    def say(message):
        if cancelled is not None and cancelled():
            raise Cancelled("cancelled")
        tracker(message)

    t0 = time.perf_counter()
    res = auto_detect_both(
        x, fs, units=rec.get("units"), detectors=specs, seed_families=families,
        score_spans=r4.Scorer(model, x_mv_full, fs, offset=a),
        score_spans_inverted=r4.Scorer(model, x_mv_full, fs, offset=a, invert=True),
        floor_mv=floor, start_idx=a, rule=rule, seed_min_family_line=MIN_FAMILY_LINE, on_progress=say)
    wall = time.perf_counter() - t0
    meta = {"version": VERSION, "recording": {k: rec.get(k) for k in ("id", "source_file", "channel", "fs", "units",
                                                                      "n_samples")},
            "stretch": {"start_idx": a, "end_idx": b, "n_samples": b - a},
            "floor_mv": floor, "floor_source": floor_src, "missing_detectors": missing,
            "wall_s": wall, "timings": res.timings, "scan_windows": res.scan_windows, "info": res.info,
            "whole_drop": _whole_drop_fingerprint(), "created_at": _dt.datetime.now().isoformat(timespec="seconds")}
    return res, meta


def _whole_drop_fingerprint():
    """The whole-drop rule this run used: the sha256 of the module as loaded (the rule's owner pins versions)."""
    import hashlib
    from Working.interrogation import whole_drop
    try:
        with open(whole_drop.__file__, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()[:12]
    except OSError:
        digest = None
    return {"sha256_12": digest, "pinned_blob": getattr(whole_drop, "__pinned_blob__", None)}


# ── on disk ─────────────────────────────────────────────────────────────────

def result_dir(job_id, root=None):
    return os.path.join(RESULTS_DIR if root is None else root, f"job_{int(job_id)}")


def save(out_dir, result, meta):
    """candidates.csv, sequences.csv and run.json (the summary, the run's notes, the timings) in ``out_dir``. Never
    over an earlier result: its run.json holds what was sent to Review, and losing that would let a send repeat."""
    if os.path.exists(os.path.join(out_dir, "run.json")):
        raise FileExistsError(f"an auto-detect result is already saved in {out_dir}; not overwriting it")
    os.makedirs(out_dir, exist_ok=True)
    result.candidates.to_csv(os.path.join(out_dir, "candidates.csv"), index=False)
    result.sequences.to_csv(os.path.join(out_dir, "sequences.csv"), index=False)
    c = result.candidates
    hi = c[c["confidence"] >= 0.5] if len(c) else c
    summary = {"candidates": int(len(c)), "at_05": int(len(hi)),
               "drops_05": int((hi["polarity"] == "drop").sum()) if len(hi) else 0,
               "rises_05": int((hi["polarity"] == "spike").sum()) if len(hi) else 0,
               "sequences": int(len(result.sequences)), "wall_s": float(meta["wall_s"])}
    meta = {**meta, "summary": summary}
    with open(os.path.join(out_dir, "run.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    return summary


def load(out_dir):
    """``(candidates, sequences, meta)`` of a saved result."""
    with open(os.path.join(out_dir, "run.json"), encoding="utf-8") as fh:
        meta = json.load(fh)
    c = pd.read_csv(os.path.join(out_dir, "candidates.csv"))
    path = os.path.join(out_dir, "sequences.csv")
    s = pd.read_csv(path) if os.path.isfile(path) and os.path.getsize(path) > 0 else pd.DataFrame()
    return c, s, meta


def results(root=None, *, recording_id=None):
    """Every saved result's summary, newest first: ``{job_id, recording_id, created_at, stretch, summary}``."""
    root = RESULTS_DIR if root is None else root
    out = []
    if not os.path.isdir(root):
        return out
    for name in os.listdir(root):
        m = re.fullmatch(r"job_(\d+)", name)
        path = os.path.join(root, name, "run.json")
        if not m or not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                meta = json.load(fh)
        except (OSError, ValueError):
            continue
        rid = int((meta.get("recording") or {}).get("id") or -1)
        if recording_id is not None and rid != int(recording_id):
            continue
        out.append({"job_id": int(m.group(1)), "recording_id": rid, "created_at": meta.get("created_at"),
                    "stretch": meta.get("stretch"), "summary": meta.get("summary"), "version": meta.get("version"),
                    "sent": meta.get("sent") or []})
    out.sort(key=lambda r: -r["job_id"])
    return out


# ── what the page draws ─────────────────────────────────────────────────────

#: The sources a candidate can name, in the order the page's source mask uses (bit k = SOURCES[k]).
SOURCES = ("drop_detection_v1", "drop_detection_v5", "wavelet_encoded", "BEADs_invert_detect_v1", "seed",
           "beads_sigma", "event_rule")
SOURCE_LABEL = {"drop_detection_v1": "drop v1", "drop_detection_v5": "drop v5", "wavelet_encoded": "wavelet",
                "BEADs_invert_detect_v1": "BEADS", "seed": "seed", "beads_sigma": "BEADS σ",
                "event_rule": "event rule", "r4_scan": "R4 scan"}


def _f(v, nd=4):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return round(v, nd) if np.isfinite(v) else None


def _mask(v):
    m = 0
    for s in (str(v).split("|") if isinstance(v, str) and v else []):
        if s in SOURCES:
            m |= 1 << SOURCES.index(s)
    return m


def _families(v):
    if not isinstance(v, str):
        return ""
    f = sorted({p.split("__", 1)[1] for p in v.split("|") if p.startswith("seed__")})
    return ", ".join(f[:6]) + (f" +{len(f) - 6}" if len(f) > 6 else "")


def _col(c, name, fn, default=None):
    return [fn(v) for v in c[name]] if name in c else [default] * len(c)


def payload(cands, seqs, meta):
    """The result as the page reads it: candidates column by column (sample indices relative to the stretch's start),
    sequences, the sources' names, and the run's notes."""
    c = cands.reset_index(drop=True)
    a = int(meta["stretch"]["start_idx"])
    cols = {
        "id": c["candidate_id"].astype(int).tolist() if len(c) else [],
        "s": (c["start"].astype(np.int64)).tolist() if len(c) else [],
        "e": (c["end"].astype(np.int64)).tolist() if len(c) else [],
        "c": _col(c, "confidence", lambda v: _f(v, 4) or 0.0, 0.0),
        "p": _col(c, "p_r4", _f),
        "k": _col(c, "kind", lambda v: 1 if v == "r4_scan" else 0, 0),
        "src": _col(c, "sources", _mask, 0),
        "seq": _col(c, "sequence_id", lambda v: int(v) if v == v else -1, -1),
        "pol": _col(c, "polarity", lambda v: 1 if v == "spike" else 0, 0),
        "dep": _col(c, "depth_mv", lambda v: _f(v, 3)),
        "ex": _col(c, "extremum", lambda v: int(v) if v == v else None),
        "inv": _col(c, "run", lambda v: 1 if v == "inverted" else 0, 0),
        "both": _col(c, "runs", lambda v: 1 if v == "both" else 0, 0),
        "shp": _col(c, "sharpness", lambda v: _f(v, 1)),
        "rec": _col(c, "recovered", lambda v: bool(v) if v == v else False, False),
        "fam": _col(c, "member_variants", _families, ""),
        "lifts": _col(c, "lifts", lambda v: v if isinstance(v, str) else "[]", "[]"),
        "sp": _col(c, "scan_p", _f),
    }
    s = seqs.reset_index(drop=True) if seqs is not None else pd.DataFrame()
    sq = {"id": s["sequence_id"].astype(int).tolist() if len(s) else [],
          "s": (s["start"].astype(np.int64)).tolist() if len(s) else [],
          "e": (s["end"].astype(np.int64)).tolist() if len(s) else [],
          "n": s["n_members"].astype(int).tolist() if len(s) else [],
          "mc": [_f(v, 3) for v in s["mean_confidence"]] if len(s) else [],
          "pol": [1 if p == "spike" else 0 for p in s["polarity"]] if len(s) and "polarity" in s else [0] * len(s)}
    rec = meta["recording"]
    return {"version": meta.get("version"), "recording": rec, "start_idx": a,
            "n": int(meta["stretch"]["n_samples"]), "fs": float(rec["fs"]), "candidates": cols, "sequences": sq,
            "sources": list(SOURCES), "source_labels": SOURCE_LABEL, "summary": meta.get("summary"),
            "notes": notes(meta), "wall_s": meta.get("wall_s"), "created_at": meta.get("created_at"),
            "floor_mv": meta.get("floor_mv"), "missing_detectors": meta.get("missing_detectors") or [],
            "rules": {"rise_sharpness": (meta.get("info") or {}).get("rise_sharpness"),
                      "drop_rule": (meta.get("info") or {}).get("drop_rule")},
            "sent": meta.get("sent") or []}


def notes(meta):
    """The run in sentences: what proposed how much, what the gates removed, how the runs were joined."""
    info = meta.get("info") or {}
    out = [f"Noise floor {meta.get('floor_mv')} mV ({meta.get('floor_source')})."]
    dc = info.get("detector_counts") or {}
    if dc:
        out.append("Proposals on the signal: " + ", ".join(f"{SOURCE_LABEL.get(k.split('__')[0], k)}"
                                                           f"{' (6 h windows)' if '__w' in k else ''} {v}"
                                                           for k, v in dc.items()) + ".")
    if meta.get("missing_detectors"):
        out.append("Not in this database, so not run: " + ", ".join(meta["missing_detectors"]) + ".")
    gt = info.get("gates") or {}
    if gt:
        out.append(f"Removed on the signal: {gt.get('flat', 0)} flat drift, {gt.get('below_floor', 0)} under the "
                   f"floor, {gt.get('not_sharp', 0)} rises not sharp, {gt.get('not_distinct', 0)} drops not told "
                   f"from noise.")
    cb = info.get("combined") or {}
    if cb:
        out.append(f"The run on the inverted signal added {cb.get('inverted', 0)} rises; {cb.get('rises_found_by_both', 0)} "
                   f"rises were found by both runs and kept once; {cb.get('folded_across_runs', 0)} candidates were "
                   f"another's return or part of it and were folded in.")
    si = info.get("sequence_info") or {}
    if si:
        out.append(f"Sequences: {si.get('n_sequences', 0)} ({si.get('rule')}).")
    if info.get("errors"):
        out.append("Stages that failed (the rest ran): " + "; ".join(
            f"{k}: {str(v).strip().splitlines()[-1]}" for k, v in info["errors"].items()))
    return out


# ── send to Review ──────────────────────────────────────────────────────────

#: The machine config a sent result's runs share (one per line-up version).
CONFIG_KIND = "autodetect"


def selection(cands, *, min_confidence=0.5, polarities=("drop", "spike"), candidate_ids=None):
    """The candidates a send would take: at least ``min_confidence``, of the given polarities, or exactly
    ``candidate_ids`` when given."""
    c = cands
    if candidate_ids is not None:
        return c[c["candidate_id"].isin([int(i) for i in candidate_ids])]
    keep = (c["confidence"] >= float(min_confidence)) & c["polarity"].isin(list(polarities))
    return c[keep]


def lanes(starts, ends):
    """Each box's lane: the first lane whose last box ends at or before this one starts - a greedy interval
    colouring over boxes in start order. Review serves the overlapping detections of one run as ONE item (one key
    press, one verdict: `review.overlap.overlap_sets`, half-open intervals), so a send puts each lane in a run of its
    own and two candidates that overlap - a drop's box running into the next rise - stay two items. The same rule as
    ``lanes()`` in scripts/library_analysis/candidate_events_20261123.py (a script, so not importable here)."""
    order = sorted(range(len(starts)), key=lambda i: (int(starts[i]), int(ends[i])))
    last_end, out = [], [0] * len(starts)
    for i in order:
        s, e = int(starts[i]), int(ends[i])
        k = next((j for j, end in enumerate(last_end) if end <= s), len(last_end))
        if k == len(last_end):
            last_end.append(e)
        else:
            last_end[k] = e
        out[i] = k
    return out


def write_detections(conn, recording_id, boxes, *, config_id, name):
    """Machine rows for `boxes` on one recording: one completed run per lane (`lanes`, so two boxes that overlap
    never share a run and Review asks about each one) spanning the whole recording, and one detection per box with
    absolute indices, in the order given. A box is ``{"start_idx", "end_idx", "score", "meta"}``. Writes no verdict
    and commits nothing: the caller commits. Returns ``(detection ids in the order given, run ids by lane)``."""
    if not boxes:
        return [], []
    now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
    n = int(conn.execute("SELECT n_samples FROM recordings WHERE id = ?", (int(recording_id),)).fetchone()[0])
    lane = lanes([b["start_idx"] for b in boxes], [b["end_idx"] for b in boxes])
    n_lanes = max(lane) + 1
    run_ids = []
    for k in range(n_lanes):
        cur = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, "
                           "name, finished_at) VALUES (?, ?, 0, ?, ?, 'completed', ?, ?)",
                           (int(config_id), int(recording_id), n, now,
                            name + (f" · lane {k + 1} of {n_lanes}" if n_lanes > 1 else ""), now))
        run_ids.append(int(cur.lastrowid))
    ids = []
    for b, k in zip(boxes, lane):
        cur = conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score, meta_json) VALUES (?, ?, ?, ?, ?)",
                           (run_ids[k], int(b["start_idx"]), int(b["end_idx"]), b.get("score"),
                            json.dumps(b.get("meta") or {}, default=lambda o: o.item() if hasattr(o, "item") else str(o))))
        ids.append(int(cur.lastrowid))
    return ids, run_ids


def channel_label(conn, rec):
    """The channel's name by the one convention (`discovery.channels.channel_name`: one-based, CH14 for stored
    channel 13), for the names of the queues a send makes."""
    from Working.discovery.channels import channel_name
    n = conn.execute("SELECT COUNT(*) FROM recordings WHERE source_file = ?", (rec["source_file"],)).fetchone()[0]
    return channel_name(rec["source_file"], int(rec["channel"]), n)


def send_to_review(conn, out_dir, *, job_id, min_confidence=0.5, polarities=("drop", "spike"), candidate_ids=None,
                   sequences=True, name=None):
    """Put a saved result in Review. Candidates: one machine run on the recording (``config_json`` kind
    ``autodetect``), one detection per candidate (absolute samples, its confidence as the score, its details as
    ``meta_json``), in a detection queue listed in time order - Review's own matching rule then holds back an item
    already judged as the same event (``held_back`` counts them). Sequences (when ``sequences``): every sequence two
    or more of the picked candidates make, through `sequence_queue.send_to_sequence_review` (machine candidates, their
    events listed). A second send of the same result adds no candidate and no sequence it already sent. Records the
    send in run.json. Returns what was written."""
    from Working.database import runs as _runs
    from Working.review import queues as Q
    from Working.review import sequence_queue as SQ

    cands, seqs, meta = load(out_dir)
    rec = meta["recording"]
    rid, a = int(rec["id"]), int(meta["stretch"]["start_idx"])
    pick = selection(cands, min_confidence=min_confidence, polarities=polarities, candidate_ids=candidate_ids)
    pick = pick.sort_values("start")
    where = f"{rec['source_file']} {channel_label(conn, rec)}"
    label = name or f"Auto-detect · {where} · job {int(job_id)}"
    already = {int(d) for s in (meta.get("sent") or []) for d in (s.get("candidate_ids") or [])}
    seq_already = {int(d) for s in (meta.get("sent") or []) for d in (s.get("sequence_ids") or [])}
    fresh = pick[~pick["candidate_id"].isin(list(already))]
    out = {"queue_id": None, "detections": 0, "held_back": None, "sequence_queue_id": None, "sequences": 0,
           "already_sent": int(len(pick) - len(fresh)), "sequences_already_sent": 0}
    sent_seq = []
    if len(fresh):
        cfg_id, _h = _runs.get_or_create_config(conn, {"kind": CONFIG_KIND, "version": meta.get("version"),
                                                       "whole_drop": meta.get("whole_drop"),
                                                       "rules": (meta.get("info") or {}).get("drop_rule")})
        boxes = [{"start_idx": int(r.start) + a, "end_idx": int(r.end) + a, "score": _f(r.confidence, 4),
                  "meta": {"source": "autodetect", "job_id": int(job_id), "candidate_id": int(r.candidate_id),
                           "polarity": r.polarity, "depth_mv": _f(r.depth_mv, 3), "confidence": _f(r.confidence, 4),
                           "p_r4": _f(getattr(r, "p_r4", None), 4),
                           "sources": r.sources if isinstance(r.sources, str) else "",
                           "run": getattr(r, "run", None), "sharpness": _f(getattr(r, "sharpness", None), 1),
                           "sequence_id": int(r.sequence_id) if r.sequence_id == r.sequence_id else -1}}
                 for r in fresh.itertuples(index=False)]
        ids, run_ids = write_detections(conn, rid, boxes, config_id=cfg_id, name=f"Auto-detect · job {int(job_id)}")
        conn.commit()
        qid = Q.create_queue(conn, name=label, source_kind="discovery-run",
                             filters={"detection_ids": ids, "order": "listed"},
                             note=(f"Auto-detect candidates (job {int(job_id)}): drops and sharp rises at confidence "
                                   f"{float(min_confidence):g} or more, in time order. A verdict here is yours; the "
                                   f"candidate stays the machine's."))
        out.update(queue_id=int(qid), detections=len(ids), run_id=run_ids[0], run_ids=run_ids)
    if sequences and seqs is not None and len(seqs) and len(pick):
        spans = []
        for s in seqs.itertuples(index=False):
            members = pick[pick["sequence_id"] == s.sequence_id]
            if len(members) < 2:
                continue
            if int(s.sequence_id) in seq_already:
                out["sequences_already_sent"] += 1
                continue
            sent_seq.append(int(s.sequence_id))
            spans.append({"recording_id": rid, "start_idx": int(s.start) + a, "end_idx": int(s.end) + a,
                          "events": [{"start_idx": int(m.start) + a, "end_idx": int(m.end) + a}
                                     for m in members.itertuples(index=False)],
                          "note": f"auto-detect job {int(job_id)}: {int(s.n_members)} "
                                  f"{'rises' if getattr(s, 'polarity', 'drop') == 'spike' else 'drops'}",
                          "evidence": {"mean_confidence": _f(s.mean_confidence, 3), "rule": str(s.rule)}})
        if spans:
            got = SQ.send_to_sequence_review(conn, spans=spans, provenance=f"autodetect_job_{int(job_id)}",
                                             name=f"Auto-detect sequences · {where}")
            out.update(sequence_queue_id=int(got["queue_id"]), sequences=int(got["created"]))
    sent = list(meta.get("sent") or [])
    sent.append({"at": _dt.datetime.now().isoformat(timespec="seconds"), "min_confidence": float(min_confidence),
                 "polarities": list(polarities), "queue_id": out["queue_id"], "sequence_queue_id": out["sequence_queue_id"],
                 "candidate_ids": [int(i) for i in fresh["candidate_id"]], "detections": out["detections"],
                 "sequence_ids": sent_seq, "sequences": out["sequences"]})
    meta["sent"] = sent
    with open(os.path.join(out_dir, "run.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    # what Review will put in front of the researcher now: its resolver holds back a candidate that is the same
    # event as a span a person already judged (`queues._prior_verdicts`, which reads annotations). Counted as the
    # items with those held back included minus the items without, so nothing else is mistaken for one. Counted
    # after the send is recorded, so a failure here cannot make it send twice; a failure is reported beside the
    # count, never as a zero.
    if out["queue_id"] is not None:
        try:
            every = Q.queue_items(conn, out["queue_id"], include_prior_judged=True)
            out["held_back"] = int(len(every) - len(Q.queue_items(conn, out["queue_id"])))
            out["items"] = int(len(every))
        except Exception as exc:  # noqa: BLE001 - reported to the page, not swallowed
            out["held_back_error"] = f"{type(exc).__name__}: {exc}"
    return out
