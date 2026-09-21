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
from fastapi import APIRouter, HTTPException

from Working.Detection.drop_motifs import gradients as G
from Working.Detection.drop_motifs import store as S

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
    t = np.asarray(t, dtype=float); v = np.asarray(v, dtype=float)
    if len(t) <= n:
        return t.tolist(), v.tolist()
    idx = np.linspace(0, len(t) - 1, n).round().astype(int)
    return t[idx].tolist(), v[idx].tolist()


@router.get("/api/interrogation/families")
def list_families():
    d = _load()
    return {"source": SOURCE, "store": SEED_DIR, "manifest": _clean(d["manifest"]), "families": _families(d["events"])}


def _members_of(key):
    d = _load()
    members = [e for e in d["events"] if (e.get("span_key") or f"r{e['recording_id']}") == key]
    if not members:
        raise HTTPException(404, f"no seed family {key!r}")
    return members, d["snippets"]


@router.get("/api/interrogation/families/{key}/members")
def family_members(key: str, snippets: bool = True):
    members, snips = _members_of(key)
    out = []
    for e in members:
        row = {k: _clean(e[k]) for k in ("event_id", "recording_id", "source_file", "channel", "fs", "morphology", "trigger",
                                          "onset_idx", "onset_h", "trough_idx", "trough_h", "snippet_start_idx", "snippet_end_idx",
                                          "drop_depth_mv", "rise_height_mv", "fall_duration_s", "peak_to_peak_mv", "fall_dominance",
                                          "purity", "is_pure", "cluster_id") if k in e}
        row["source"] = SOURCE
        if snippets and e["event_id"] in snips:
            s = snips[e["event_id"]]
            t, v = _decimate(s["t_s"], s["detrended_mv"])
            row["snippet"] = {"t_s": t, "detrended_mv": v, "n": int(len(s["t_s"]))}
        out.append(row)
    return {"family": key, "source": SOURCE, "members": out}


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
        {"name": "steepest", "rule": "minimum of d/dt over [onset, trough] in mV/s"},
        {"name": "chord", "rule": "(x[trough] − x[onset]) / duration"},
    ]
    members_out = []
    for e, g in zip(members, grads):
        s = snips[e["event_id"]]
        start = int(e["snippet_start_idx"])
        members_out.append({**{k: _clean(v) for k, v in g.items()},
                            "onset_offset": int(e["onset_idx"]) - start, "trough_offset": int(e["trough_idx"]) - start,
                            "angle_deg": float(np.rad2deg(rose["angles"][len(members_out)])) if len(rose["angles"]) else None})
    return {"family": key, "source": SOURCE, "features": features, "rules": rules, "members": members_out,
            "rose": {"bin_centres_deg": np.rad2deg(rose["bin_centres"]).tolist(), "counts": [int(c) for c in rose["counts"]],
                     "scale": scale, "caption": rose.get("caption", ""),
                     "groups": {k: {kk: _clean(vv) for kk, vv in v.items() if kk not in ("angles", "counts", "slopes_mv_s")} for k, v in rose["groups"].items()}}}


@router.get("/api/interrogation/families/{key}/aggregate")
def family_aggregate(key: str):
    """02 Aggregate: distributions of depth, inter-event interval and steepest slope, and the occurrence timeline."""
    members, snips = _members_of(key)
    grads = G.event_gradients(members, snips)
    onsets = np.array([float(e["onset_h"]) for e in members]) * 3600.0
    order = np.argsort(onsets)
    intervals = np.diff(onsets[order])
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
