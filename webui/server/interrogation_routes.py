"""Interrogation's live reads (stage-3 prompt 01, block 7).

Until Prompt 03 imports the events into the Library's motif tables, the
families are the 16 spans of the seed store `DATA/library_seed/drop_motifs5/
motifs/` (410 drop events, `PROVENANCE.md`: not regenerable), read directly
through `Working.Detection.drop_motifs.store` and **clearly marked
`source: "seed"`** in every payload. The slope features are
`Working.Detection.drop_motifs.gradients` — onset slope, steepest slope,
mean (chord) slope, peakedness, depth, fall duration — and the rose is
`rose_data`, so every number a page shows is the store's own measurement.
"""
from __future__ import annotations

import os
import threading

import numpy as np
from fastapi import APIRouter, HTTPException, Request

from Working.Detection.drop_motifs import gradients as G
from Working.Detection.drop_motifs import store as S
from Working.interrogation import sequences as SEQ
from Working.interrogation.event_shape import rose_payload
from Working.interrogation.intervals import inter_event_intervals

from Working.Detection.drop_motifs import extent as X

from . import corpus
from .decimate import _fast_minmax
from .runtime import REPO_ROOT
from .serialize import _clean

router = APIRouter()
SEED_DIR = os.path.join(REPO_ROOT, "DATA", "library_seed", "drop_motifs5", "motifs")
SOURCE = "seed"
_cache: dict = {}
_lock = threading.Lock()
SNIPPET_POINTS = 400


def _load():
    with _lock:
        if "events" in _cache:
            return _cache
        if not os.path.isdir(SEED_DIR):
            raise HTTPException(404, f"seed store not found at {SEED_DIR}")
        events = S.load_events(SEED_DIR)
        snippets = S.load_snippets(SEED_DIR)
        _cache.update(events=events, snippets=snippets, manifest=S.load_manifest(SEED_DIR))
        return _cache


def _families(events):
    fams = {}
    for e in events:
        key = e.get("span_key") or f"r{e['recording_id']}"
        f = fams.setdefault(key, {"id": key, "label": e.get("span_label") or key, "source": SOURCE, "recording_id": int(e["recording_id"]),
                                  "source_file": e["source_file"], "channel": int(e["channel"]), "fs": float(e["fs"]),
                                  "morphology": e.get("morphology"), "n_members": 0, "onset_h": [], "depth_mv": []})
        f["n_members"] += 1
        f["onset_h"].append(float(e["onset_h"])); f["depth_mv"].append(float(e["drop_depth_mv"]))
    out = []
    for f in fams.values():
        f["span_h"] = [min(f["onset_h"]), max(f["onset_h"])]
        f["median_depth_mv"] = float(np.median(f["depth_mv"]))
        del f["onset_h"], f["depth_mv"]
        out.append(f)
    return out


def _decimate(t, v, n=SNIPPET_POINTS):
    """`(t, v, decimated)`: every stored sample while they fit, else a min/max
    envelope - each bucket's true minimum and true maximum, at the times they
    occur (fixup-h). This used to pick every k-th sample, and a stride deletes a
    narrow event, which is the one thing a snippet exists to show."""
    t = np.asarray(t, dtype=float); v = np.asarray(v, dtype=float)
    if len(t) <= n or not np.isfinite(v).all():
        return t.tolist(), v.tolist(), False
    idx, vals = _fast_minmax(v, max(1, n // 2))
    return t[idx].tolist(), vals.astype(float).tolist(), True


def _named(request: Request, rows: list) -> list:
    """Each row's dataset and channel by the names the rest of the site uses
    (fixup-f). The seed store's own `source_file` is the channel FILE it read
    (`CH0.npy`) and its `channel` the stored index, so the pages printed
    "CH0 · CH0"; both stay on the row as provenance, and `dataset`,
    `dataset_file` and `channel_name` are resolved from `recording_id`."""
    c = _seq_conn(request)
    try:
        recs = {}
        for row in rows:
            rid = row.get("recording_id")
            if rid not in recs:
                rec = corpus.recording_row(c, int(rid)) if rid is not None else None
                recs[rid] = (corpus.dataset_name(c, rec["source_file"]), rec["source_file"], rec["name"]) if rec else None
            if recs[rid]:
                row["dataset"], row["dataset_file"], row["channel_name"] = recs[rid]
    finally:
        c.close()
    return rows


@router.get("/api/interrogation/families")
def list_families(request: Request):
    d = _load()
    return {"source": SOURCE, "store": SEED_DIR, "manifest": _clean(d["manifest"]), "families": _named(request, _families(d["events"]))}


def _members_of(key):
    d = _load()
    members = [e for e in d["events"] if (e.get("span_key") or f"r{e['recording_id']}") == key]
    if not members:
        raise HTTPException(404, f"no seed family {key!r}")
    return members, d["snippets"]


@router.get("/api/interrogation/families/{key}/members")
def family_members(request: Request, key: str, snippets: bool = True):
    members, snips = _members_of(key)
    # fixup-h: what the drawing needs to say about each event's extent, read off the row and never
    # changed - which edges sit at the fall-multiple cap (Q18), the frame a sequence is drawn in (Q19),
    # and whether the stored array is the length its indices claim (DETECTION_AND_FIGURES.md 6.7).
    frames = X.sequence_frames(members)
    out = []
    for e, frame in zip(members, frames):
        row = {k: _clean(e[k]) for k in ("event_id", "recording_id", "source_file", "channel", "fs", "morphology", "trigger",
                                          "onset_idx", "onset_h", "trough_idx", "trough_h", "snippet_start_idx", "snippet_end_idx",
                                          "drop_depth_mv", "rise_height_mv", "fall_duration_s", "peak_to_peak_mv", "fall_dominance",
                                          "purity", "is_pure", "cluster_id") if k in e}
        row["source"] = SOURCE
        row["left_capped"], row["right_capped"] = X.capped_edges(e)
        row["sequence_frame"] = frame
        if snippets and e["event_id"] in snips:
            s = snips[e["event_id"]]
            t, v, decimated = _decimate(s["t_s"], s["detrended_mv"])
            row["snippet"] = {"t_s": t, "detrended_mv": v, "n": int(len(s["t_s"])), "decimated": decimated,
                              "mismatch": X.snippet_mismatch(e, len(s["detrended_mv"]))}
        out.append(row)
    return {"family": key, "source": SOURCE, "members": _named(request, out), "capped": X.capped_counts(members)}


@router.get("/api/interrogation/families/{key}/slope")
def family_slope(key: str, scale: str = "raw"):
    """01 Resolve spans: the anatomy of every member (onset, steepest, trough, chord, depth) and the rose."""
    members, snips = _members_of(key)
    grads = G.event_gradients(members, snips)
    rose = G.rose_data(members, snips, scale=scale, split_by="span_key")
    features = [
        {"name": "onset_slope_mv_s", "unit": "mV/s", "kind": "slope", "label": "Onset slope"},
        {"name": "max_slope_mv_s", "unit": "mV/s", "kind": "slope", "label": "Steepest slope"},
        {"name": "mean_slope_mv_s", "unit": "mV/s", "kind": "slope", "label": "Chord slope"},
        {"name": "peakedness", "unit": "", "kind": "ratio", "label": "Peakedness"},
        {"name": "drop_depth_mv", "unit": "mV", "kind": "amplitude", "label": "Drop depth"},
        {"name": "fall_duration_s", "unit": "s", "kind": "duration", "label": "Fall duration"},
    ]
    rules = [
        {"name": "onset", "rule": "first sample steeper than −slope_sigma·σ after the rise, walked back to the shoulder (detect5)"},
        {"name": "trough", "rule": "steepest fall onward to the knee (trough_knee_frac of the steepest slope)"},
        {"name": "steepest", "rule": "minimum of np.gradient × fs (a central difference, so one sample either side) over [onset, trough], "
                                     "mV/s, and the sample that minimum is at (gradients.fall_gradients)"},
        {"name": "chord", "rule": "(x[trough] − x[onset]) / duration"},
    ]
    members_out = []
    for e, g in zip(members, grads):
        # fixup-k: the anatomy figure's marks. The offsets are clipped into the snippet exactly as
        # `fall_gradients` clips them, so a mark is always at the sample the slope was measured from; the
        # three heights are the full-resolution snippet's own samples (the page holds a 400-point decimation).
        v = np.asarray(snips[e["event_id"]]["detrended_mv"], dtype=float).ravel()
        start = int(e["snippet_start_idx"])
        onset, trough = (int(np.clip(int(e[k]) - start, 0, max(len(v) - 1, 0))) for k in ("onset_idx", "trough_idx"))
        steepest = g.pop("max_slope_idx")
        at = lambda i: None if i is None or not len(v) else float(v[i])
        members_out.append({**{k: _clean(v_) for k, v_ in g.items()},
                            "onset_offset": onset, "trough_offset": trough, "steepest_offset": steepest,
                            "onset_mv": at(onset), "trough_mv": at(trough), "steepest_mv": at(steepest),
                            "n_samples": int(len(v)),
                            "angle_deg": float(np.rad2deg(rose["angles"][len(members_out)])) if len(rose["angles"]) else None})
    return {"family": key, "source": SOURCE, "features": features, "rules": rules, "members": members_out,
            # the whole of `rose_data` in the one shape the kit's Rose draws (fixup-h): bins, every event's
            # angle, the circular statistics. `event_index` is the member's position in `members` above.
            "rose": _clean(rose_payload(rose))}


@router.get("/api/interrogation/families/{key}/aggregate")
def family_aggregate(key: str):
    """02 Aggregate: distributions of depth, inter-event interval and steepest slope, and the occurrence timeline."""
    members, snips = _members_of(key)
    grads = G.event_gradients(members, snips)
    onsets = np.array([float(e["onset_h"]) for e in members]) * 3600.0
    order = np.argsort(onsets)
    intervals = inter_event_intervals(onsets)          # the one implementation (fixup-d)
    depth = np.array([float(e["drop_depth_mv"]) for e in members])
    slope = np.array([g["max_slope_mv_s"] for g in grads])
    dur = np.array([float(e["fall_duration_s"]) for e in members])

    def dist(v, bins=12):
        v = np.asarray(v, dtype=float); v = v[np.isfinite(v)]
        if v.size == 0:
            return {"n": 0, "counts": [], "edges": [], "median": None, "iqr": None}
        counts, edges = np.histogram(v, bins=bins)
        q1, q3 = np.percentile(v, [25, 75])
        return {"n": int(v.size), "counts": counts.tolist(), "edges": edges.tolist(), "median": float(np.median(v)), "iqr": [float(q1), float(q3)],
                "min": float(v.min()), "max": float(v.max())}

    # depth vs duration: a log-log slope with a bootstrap CI (the scaling relationship the spec asks for)
    beta = None
    if len(depth) >= 4 and (depth > 0).all() and (dur > 0).all():
        lx, ly = np.log(dur), np.log(depth)
        b = np.polyfit(lx, ly, 1)[0]
        rng = np.random.default_rng(0)
        bs = [np.polyfit(lx[i], ly[i], 1)[0] for i in (rng.integers(0, len(lx), len(lx)) for _ in range(200))]
        beta = {"x": "fall_duration_s", "y": "drop_depth_mv", "beta": float(b), "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], "n": int(len(lx))}
    return {"family": key, "source": SOURCE, "n": len(members),
            "distributions": {"drop_depth_mv": dist(depth), "inter_event_interval_s": dist(intervals), "max_slope_mv_s": dist(slope), "fall_duration_s": dist(dur)},
            "timeline": [{"event_id": members[i]["event_id"], "onset_h": float(members[i]["onset_h"]), "depth_mv": float(depth[i]),
                          "max_slope_mv_s": float(slope[i]), "position": float(k / max(1, len(order) - 1))} for k, i in enumerate(order)],
            "scaling": beta}


# ---------------------------------------------------------------- event shape (fixup-e) --
# 01 Event shape: `interrogation.event_shape`'s measures of every member of a seed family,
# so the Aggregate page draws measurements and never a constant times a duration. Each
# member's features come from `motif_features` when the Library carries them (fixup-d's
# backfill, keyed by the content hash of the store's own `detrended_mv` snippet) and are
# otherwise measured on that snippet on the spot from the detector's own onset and trough
# (`Working.library.features.measure_snippet`) — flagged `stored: false`, and NOT written:
# a view writes nothing. Recovery that is not reached inside the rule's bound is None and
# counted, never 0; a drop's rise time is None, never 0 (Q19).

def _shape_rules():
    from Working.interrogation.event_shape import rules
    return rules(to_mv=1.0, anchors_used=("the detector's own onset_idx / trough_idx from events.csv: the event was already "
                                          "located, so the anatomy search is not run (fixup-d: 410 / 410 seed depths agree)"))


@router.get("/api/interrogation/families/{key}/shape")
def family_shape(request: Request, key: str):
    """01 Event shape: every member's per-event measures from the core, with the rule behind each."""
    from Working.interrogation import event_shape as ES
    from Working.library import features as F
    from Working.library.identity import content_hash

    members, snips = _members_of(key)
    hashes = {e["event_id"]: content_hash(np.asarray(snips[e["event_id"]]["detrended_mv"], dtype=float))
              for e in members if e["event_id"] in snips}
    c = _seq_conn(request)
    try:
        stored = F.read_features(c, list(hashes.values())) if hashes else {}
    finally:
        c.close()

    wanted = tuple(ES.MEASURES) + ("polarity", "onset_idx", "extremum_idx")
    counts = {"n": len(members), "n_stored": 0, "n_measured_here": 0, "n_no_snippet": 0,
              "n_not_recovered": 0, "n_no_fwhm": 0, "n_no_rise": 0}
    out = []
    for e in members:
        eid = e["event_id"]
        row = {"event_id": eid, "content_hash": hashes.get(eid), "stored": False, "features": None,
               "detector": F.detector_measures(e), "completed_from_snippet": [], "why": None}
        snip = snips.get(eid)
        have = stored.get(hashes[eid]) if eid in hashes else None
        feats = None
        if have and any(k in have for k in ES.MEASURES):
            row["stored"] = True
            counts["n_stored"] += 1
            feats = {k: have.get(k, float("nan")) for k in wanted}
            row["detector"] = {**row["detector"], **{k[len(F.DETECTOR_PREFIX):]: v for k, v in have.items()
                                                    if k.startswith(F.DETECTOR_PREFIX)}}
            missing = [k for k in ES.MEASURES if k not in have]
            if missing and snip is not None:
                # a row written under an older rule set (before rise_time_s existed): fill the gap from
                # the same snippet the row was measured on, and say which measures were filled
                fresh = F.measure_snippet(snip["detrended_mv"], float(e["fs"]), F.detector_anchor(e))
                for k in missing:
                    feats[k] = fresh.get(k, float("nan"))
                row["completed_from_snippet"] = missing
        elif snip is not None:
            feats = F.measure_snippet(snip["detrended_mv"], float(e["fs"]), F.detector_anchor(e))
            counts["n_measured_here"] += 1
        else:
            row["why"] = "no snippet in the store for this event, and no stored features"
            counts["n_no_snippet"] += 1
            out.append(row)
            continue
        row["features"] = {k: _clean(None if v is None else float(v)) for k, v in feats.items()}
        pol = row["features"].get("polarity")
        row["features"]["polarity"] = None if pol is None else int(pol)
        counts["n_not_recovered"] += int(row["features"]["recovery_time_s"] is None)
        counts["n_no_fwhm"] += int(row["features"]["fwhm_s"] is None)
        counts["n_no_rise"] += int(row["features"]["rise_time_s"] is None)
        out.append(row)
    return _clean({
        "family": key, "source": SOURCE, "block": "interrogation.event_shape", "members": out, "rules": _shape_rules(),
        "counts": counts,
        "recovery": {"frac": ES.RECOVERY_FRAC, "max_mult": ES.RECOVERY_MAX_MULT},
        "rise_time_frac": ES.RISE_TIME_FRAC,
        "measured_on": ("the store's own detrended_mv snippet, the waveform the Library's content hash covers; "
                        "the store wrote samples x 1000 as mV, which is mV only where the recording is in volts (Q-X2.8)"),
    })


# ---------------------------------------------------------------- sequences (fixup-d) --
# The steepest-slope rose compared across the events of ONE sequence. The events'
# features are `motif_features` rows where the backfill stored them, measured on the
# spot from the Library snippet (and flagged `stored: false`) where it did not; the
# view writes nothing. Snippets are the event stores' `detrended_mv`, which the store
# wrote as samples x 1000 whatever the file's unit — so a sequence on a recording
# whose unit is not a declared V says so beside every mV (fixup-b).

_SEQ_STORES = SEQ.store_cache(REPO_ROOT)


def _seq_conn(request: Request):
    return corpus.connect(request.app.state.rt.db_path)


def _unit_note(conn, recording_id):
    if recording_id is None:
        return "no recording on this sequence: the unit of its snippets is not known"
    cols = {r[1] for r in conn.execute("PRAGMA table_info(recordings)")}
    units = conn.execute("SELECT units FROM recordings WHERE id = ?", (int(recording_id),)).fetchone()[0]         if "units" in cols else None
    if units == "V":
        return None
    if units is None:
        return ("unit undeclared for this recording: the store wrote samples x 1000 as 'mV', which is mV only if "
                "the samples are volts — declare it in Settings › Datasets")
    return f"recording stored in {units}: the store's 'mV' assumed volts and is off by the same factor (QUESTIONS.md Q-X2.8)"


@router.get("/api/interrogation/sequences")
def list_sequences(request: Request):
    c = _seq_conn(request)
    try:
        return {"sequences": SEQ.list_sequences(c)}
    finally:
        c.close()


@router.get("/api/interrogation/sequences/{sequence_id}/shape")
def sequence_shape(request: Request, sequence_id: int, scale: str = "raw", reference: float = G.DEFAULT_SLOPE_REF_MV_S):
    if scale not in G.SLOPE_SCALES:
        raise HTTPException(422, f"scale must be one of {G.SLOPE_SCALES}, got {scale!r}")
    c = _seq_conn(request)
    try:
        try:
            with _lock:
                out = SEQ.sequence_shape(c, sequence_id, scale=scale, reference=reference, repo_root=REPO_ROOT,
                                         stores=_SEQ_STORES)
        except LookupError as e:
            raise HTTPException(404, str(e))
        from Working.interrogation.event_shape import rules
        out["rules"] = rules(to_mv=1.0)
        out["unit_note"] = _unit_note(c, out["sequence"]["recording_id"])
        return _clean(out)
    finally:
        c.close()
