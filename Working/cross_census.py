"""
cross_census.py
===============
The cross-channel CENSUS (cross-channel explorer S1; decisions D3, D7, D9, D16, D18, D20, X1, X5 in
`docs/prompts/changes/cross-channel-explorer-decisions.md`). It answers round-B question B4: is there evidence of a
propagation lag between channels that is not artefact?

In plain words
--------------
Every event one detector found on every channel of a recording is paired with every event on another channel whose
onset is within the propagation ceiling (Settings, 50 s). Each pair is measured on the SAME stretch of both channels,
from 60 s before to 180 s after the earlier onset, with the lag searched only within ±50 s, and is tested against
luck (the same statistic at random other times) and against the noise floor. Then it goes in one bin:

- **artifact** — a copy: |lag| ≤ 1 s and |r| ≥ 0.98, beating chance, both swings over the floor. Any packs.
- **shared_driver** — across packs and not a copy: both packs reacting to one stimulus. Never propagation.
- **propagation** — within a pack, 1 s < |lag| ≤ 50 s, |r| ≥ 0.5, beating chance, over the floor.
- **independent_recurrence** — within a pack, everything else.
- **pack_unknown** — exactly one of the two channels has no pack (a partly set layout): their relation is not known,
  so the pair is counted apart, never as propagation and never as a shared driver.

Copies at one instant are joined into an **instant** (union-find over artifact pairs). Its breadth is its number of
channels; it is **common mode** when it is broader than half the recording's channels with every copy's amplitude
ratio within ×2, or when it spans two or more packs (D7). A mark inside `artifact`, never a bin.

Every count sits beside its null (D18): rotation of whole event trains for co-occurrence excess, breadth and shared
driver; random-time windows for each waveform; and for the **timetable** (X1, confirmed 2026-10-27) the pair's
non-copy lags against lags measured between the same channels at random other times. p = (1 + #null ≥ observed) /
(K + 1); per-recording Benjamini–Hochberg at q 0.05 through `seeded_search.corrected_levels`, the one implementation.

The census numbers that are not Settings keys are named constants (`CensusConstants`, X5), recorded on every census
and in its hash. The bin lines stay the existing Settings keys (`cross_channel.rule_from_settings`).

Reuses, never copies: `candidate_events.load_sweep_detections` (Rule 1, the one run selector),
`channel_layout.channel_layout` / `same_pack` (the one pack rule), `cross_channel` (the lag, r, chance test and bin
lines), `library.matching`'s floor check and human-artifact reader, `view_filter.dataset_floors`.

Storage (D20): `cross_census` and `cross_cooccurrence` (machine rows only, CLAUDE.md rule 5); the null draws are an
.npz under `Working.config.STEP_CACHE_ROOT` (rule 4), which the sandbox bridge redirects. Writes are short
transactions after everything is computed (fixup-dblock: holding the write lock across null computations made
concurrent writes fail with `database is locked`).

No UI library (CLAUDE.md rule 1).
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass

import numpy as np

from Working import cross_channel as xc
from Working.cross_channel import ARTIFACT, INDEPENDENT_RECURRENCE, PROPAGATION, SHARED_DRIVER

#: bumped whenever the census's arithmetic changes, so a stored census goes stale (it is in the hash)
CENSUS_VERSION = 1
#: the default detector (D16): 92–100 % precise in the blind estimate
DEFAULT_DETECTOR = "drop_detection_v1"
#: a pair with exactly one unassigned channel (S0's `same_pack` returns None): counted apart
PACK_UNKNOWN = "pack_unknown"
CENSUS_BINS = (ARTIFACT, PROPAGATION, INDEPENDENT_RECURRENCE, SHARED_DRIVER, PACK_UNKNOWN)
#: detectors that are never a census detector: wavelet_encoded fires ~2,700 times on its surrogate against 5–147
#: on the signal (Facts, 2026-10-27)
NEVER_CENSUS = ("wavelet_encoded*",)

_ONSET_LABEL = re.compile(r"(?:^|;)\s*onset=(-?\d+)")


@dataclass(frozen=True)
class CensusConstants:
    """X5: the census's numbers that are not Settings keys. Recorded on every census and in its hash."""

    onset_window_s: tuple = (-60.0, 180.0)   # the measured stretch, about the earlier onset
    timetable_delta_s: float = 2.0           # the timetable's ±δ
    rotation_k: int = 1000                   # co-occurrence excess, shared driver
    breadth_k: int = 1000
    timetable_k: int = 1000
    waveform_k: int = 100                    # the random-time waveform null (chance_null)
    timetable_pool_min: int = 2000           # lags at random other times, per pair
    timetable_min_n: int = 2                 # a timetable needs at least two non-copy lags
    min_rotation_s: float = 3600.0           # a rotation is at least 1 h from zero
    breadth_fraction: float = 0.5            # common mode: broader than this share of channels …
    amplitude_band: float = 2.0              # … with every copy's amplitude ratio within ×2
    q: float = 0.05                          # Benjamini–Hochberg, per recording
    onset_smooth_s: float = 5.0              # the steepest fall is read on a 5 s moving average

    def as_dict(self):
        d = dataclasses.asdict(self)
        d["onset_window_s"] = [float(v) for v in self.onset_window_s]
        d["census_version"] = CENSUS_VERSION
        return d


DEFAULT_CONSTANTS = CensusConstants()


class CensusRefused(ValueError):
    """The census will not run, and says why in words (a detector without a real run on every channel)."""


def _now():
    return _dt.datetime.now().isoformat(timespec="seconds")


def _refuse_held_out(source_file):
    from Working.config import HELD_OUT_RECORDING_FILE
    if str(source_file) == HELD_OUT_RECORDING_FILE:
        raise PermissionError(f"{source_file} is the held-out recording: no census is made from it")


# ── which runs: Rule 1, filtered to one template ────────────────────────────

def _never(detector):
    import fnmatch
    return any(fnmatch.fnmatchcase(str(detector), p) for p in NEVER_CENSUS)


def _status_from(layout, sweep, detector):
    channels = [int(r) for r in layout["channels"]]
    with_run = {int(r["recording_id"]) for r in sweep["runs"] if r["variant"] == detector}
    k = sum(1 for r in channels if r in with_run)
    missing = [layout["channels"][r]["name"] for r in channels if r not in with_run]
    out = {"detector": detector, "n_channels": len(channels), "n_with_run": k, "missing": missing,
           "full": bool(channels) and k == len(channels) and not _never(detector), "reason": None}
    if _never(detector):
        out["reason"] = (f"{detector} fires far more on its surrogate than on the signal: it is never a census "
                         f"detector")
    elif not out["full"]:
        out["reason"] = f"{detector} has a real run on {k} of {len(channels)} channels"
    return out


def _sweep(conn, source_file):
    from Working.discovery.candidate_events import load_sweep_detections
    return load_sweep_detections(conn, source_file)


def _layout(conn, source_file, registered=None):
    from Working.channel_layout import channel_layout
    return channel_layout(conn, source_file, registered=registered)


def detector_status(conn, source_file, detector=DEFAULT_DETECTOR, *, layout=None, sweep=None):
    """`{detector, n_channels, n_with_run, missing, full, reason}`: a detector is FULL on a recording only when every
    active channel has one real run of it (D16). `reason` says why not, in words."""
    _refuse_held_out(source_file)
    layout = layout or _layout(conn, source_file)
    sweep = sweep if sweep is not None else _sweep(conn, source_file)
    return _status_from(layout, sweep, detector)


def detectors_offered(conn, source_file, *, layout=None, sweep=None):
    """Every template with a real run on the recording, the default first (listed even with no run), each `full`
    or with its reason."""
    _refuse_held_out(source_file)
    layout = layout or _layout(conn, source_file)
    sweep = sweep if sweep is not None else _sweep(conn, source_file)
    names = sorted({r["variant"] for r in sweep["runs"]} - {DEFAULT_DETECTOR})
    return [_status_from(layout, sweep, d) for d in [DEFAULT_DETECTOR] + names]


# ── events and their onsets ────────────────────────────────────────────────

def recover_onset(x, start, end, fs, label=None, smooth_s=DEFAULT_CONSTANTS.onset_smooth_s):
    """`(onset_sample, onset_from)`. A detection's stored start is the PADDED window start, never the onset. The
    block's label (`onset=<i>;…`) wins when it is stored (`onset_from` = "label"); otherwise the steepest fall
    inside the detection's first half, on a `smooth_s` moving average ("steepest_fall")."""
    if label:
        m = _ONSET_LABEL.search(str(label))
        if m:
            return int(m.group(1)), "label"
    start, end = int(start), int(end)
    m = max(1, int(round(float(smooth_s) * float(fs))))
    stop = min(len(x), start + max(2, (end - start) // 2) + m)
    seg = np.asarray(x[start:stop], dtype=float)
    if seg.size < m + 2:
        seg = np.asarray(x[start:min(len(x), end)], dtype=float)
    if seg.size < m + 2:
        raise ValueError(f"a detection of {end - start} samples is too short to find its steepest fall "
                         f"(a {m}-sample moving average needs at least {m + 2})")
    good = np.isfinite(seg)
    if not good.all():
        if not good.any():
            raise ValueError("the detection's first half holds no finite sample: its onset cannot be found")
        seg = np.where(good, seg, np.interp(np.arange(seg.size), np.flatnonzero(good), seg[good]))
    ma = np.convolve(seg, np.ones(m) / m, mode="valid")
    j = int(np.argmin(np.diff(ma)))
    return start + j + m // 2 + 1, "steepest_fall"


def _labels(conn, det_ids):
    out = {}
    ids = sorted(int(d) for d in det_ids)
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        for d, meta in conn.execute(f"SELECT id, meta_json FROM detections WHERE id IN ({','.join('?' * len(part))}) "
                                    f"AND meta_json IS NOT NULL", part):
            try:
                lab = json.loads(meta).get("label")
            except (ValueError, AttributeError):
                lab = None
            if lab:
                out[int(d)] = lab
    return out


def _recordings(conn, source_file):
    return {int(r[0]): {"id": int(r[0]), "channel": int(r[1]), "fs": float(r[2] or 1.0), "n_samples": int(r[3]),
                        "npy_path": r[4], "units": r[5]}
            for r in conn.execute("SELECT id, channel, fs, n_samples, npy_path, units FROM recordings "
                                  "WHERE source_file = ?", (str(source_file),))}


def _run_stamps(conn, run_ids):
    ids = sorted(int(r) for r in run_ids)
    out = {}
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        for rid, fin in conn.execute(f"SELECT id, finished_at FROM runs WHERE id IN ({','.join('?' * len(part))})",
                                     part):
            out[int(rid)] = fin
    return [[r, out.get(r)] for r in ids]


def census_events(conn, source_file, detector=DEFAULT_DETECTOR, *, layout=None, registered=None, arrays=None):
    """The detector's events on every channel: `{source_file, detector, layout, runs, recordings, events}`.

    Selected through `load_sweep_detections` (Rule 1) and filtered to the detector's exact template name. Refuses
    (`CensusRefused`, in words) unless the detector is full on the recording; refuses the held-out file
    (PermissionError). Each event: `detection_id, run_id, recording_id, channel, name, fs, start, end, onset,
    onset_s, onset_from` (onset in channel-absolute samples)."""
    _refuse_held_out(source_file)
    layout = layout or _layout(conn, source_file, registered)
    sweep = _sweep(conn, source_file)
    status = _status_from(layout, sweep, detector)
    if not status["full"]:
        raise CensusRefused(status["reason"])
    recs = _recordings(conn, source_file)
    active = {int(r) for r in layout["channels"]}
    runs = [r for r in sweep["runs"] if r["variant"] == detector and int(r["recording_id"]) in active]
    det = sweep["detections"]
    det = det[(det["variant"] == detector) & det["recording_id"].isin(sorted(active))]
    labels = _labels(conn, det["detection_id"].tolist())
    arrays = {} if arrays is None else arrays
    events = []
    for row in det.itertuples(index=False):
        rid = int(row.recording_id)
        rec = recs[rid]
        if rid not in arrays:
            arrays[rid] = np.load(rec["npy_path"], mmap_mode="r")
        onset, how = recover_onset(arrays[rid], int(row.start), int(row.end), rec["fs"],
                                   labels.get(int(row.detection_id)))
        events.append({"detection_id": int(row.detection_id), "run_id": int(row.run_id), "recording_id": rid,
                       "channel": rec["channel"], "name": layout["channels"][rid]["name"], "fs": rec["fs"],
                       "start": int(row.start), "end": int(row.end), "onset": int(onset),
                       "onset_s": float(onset) / rec["fs"], "onset_from": how})
    events.sort(key=lambda e: (e["onset_s"], e["recording_id"], e["detection_id"]))
    return {"source_file": source_file, "detector": detector, "layout": layout,
            "runs": _run_stamps(conn, [r["run_id"] for r in runs]), "recordings": recs, "events": events,
            "status": status}


def co_occurrences(events, ceiling_s):
    """Pure: every pair of events on DIFFERENT channels whose onsets are within `ceiling_s` (inclusive), as
    `(a, b)` with `a` on the lower recording id (so a lag reads as b relative to a)."""
    evs = sorted(events, key=lambda e: float(e["onset_s"]))
    out = []
    j0 = 0
    for i, e in enumerate(evs):
        while float(evs[j0]["onset_s"]) < float(e["onset_s"]) - ceiling_s:
            j0 += 1
        for f in evs[j0:i]:
            if f["recording_id"] == e["recording_id"]:
                continue
            if abs(float(e["onset_s"]) - float(f["onset_s"])) <= ceiling_s:
                out.append((f, e) if f["recording_id"] < e["recording_id"] else (e, f))
    out.sort(key=lambda p: (p[0]["recording_id"], p[1]["recording_id"], p[0]["onset_s"], p[1]["onset_s"]))
    return out


# ── one pair, measured ──────────────────────────────────────────────────────

def onset_window(onset_a, onset_b, fs, n, consts=DEFAULT_CONSTANTS):
    """The measured stretch `[w0, w1)` in samples: from 60 s before to 180 s after the earlier onset, clipped."""
    t = min(int(onset_a), int(onset_b))
    w0 = max(0, t + int(round(consts.onset_window_s[0] * fs)))
    w1 = min(int(n), t + int(round(consts.onset_window_s[1] * fs)))
    return w0, w1


def measure_pair(x, y, onset_a, onset_b, fs, rule=xc.DEFAULT_RULE, consts=DEFAULT_CONSTANTS, *, seed=0,
                 forbidden=(), units=(None, None), floor=None):
    """One co-occurrence, measured (Measure, S4, reuses it): `x` and `y` are the WHOLE channels (an mmap is fine).

    The onset window is cut on both channels' same samples; the lag is the restricted-lag peak (|lag| ≤ the
    propagation ceiling); the waveform null is `chance_null` with the same restriction on the partner channel `y`
    (`consts.waveform_k` windows, ≥ 60 s away, never over `forbidden`, y's human-marked artifact spans); both swings
    are checked against `floor` (a `dataset_floors` entry) in mV by `units`.

    Returns `{window, lag_s, r, chance, floor, amplitude_ratio, measurable, reason}`; lag and r are None, with a
    reason, when either window is flat or non-finite."""
    from Working.library.matching import _amplitude_ratio, _floor_check, _measurable

    fs = float(fs)
    n = min(len(x), len(y))
    w0, w1 = onset_window(onset_a, onset_b, fs, n, consts)
    xa = np.asarray(x[w0:w1], dtype=float)
    yb = np.asarray(y[w0:w1], dtype=float)
    out = {"window": [int(w0), int(w1)], "lag_s": None, "r": None, "chance": None, "floor": None,
           "amplitude_ratio": None, "measurable": False, "reason": None}
    ok, m = _measurable(xa, yb)
    if not ok:
        out["reason"] = "flat or non-finite samples in the window: lag and r undefined"
        return out
    xa, yb = xa[:m], yb[:m]
    max_lag = int(round(rule.propagation_max_lag_s * fs))
    lag, r = xc.cross_correlation_peak(xa, yb, max_lag=max_lag)
    null = xc.chance_null(xa, y, w0, w0 + m, fs, rule=dataclasses.replace(rule, null_k=consts.waveform_k),
                          seed=int(seed), forbidden=forbidden, max_lag=max_lag)
    fl = _floor_check(xa, yb, units[0], units[1], floor or {"floor_mv": 0.1, "from": "default 0.1 mV"})
    out.update({"lag_s": lag / fs, "r": float(r), "chance": xc.chance_summary(r, null), "floor": fl,
                "amplitude_ratio": _amplitude_ratio(fl), "measurable": True})
    return out


def is_copy(pair, rule):
    """A copy (D16): |lag| ≤ the artifact line, |r| ≥ the artifact r floor, beating chance, both swings over the
    floor."""
    if pair.get("lag_s") is None or pair.get("r") is None:
        return False
    beats = bool((pair.get("chance") or {}).get("beats"))
    above = bool((pair.get("floor") or {}).get("ok"))
    return xc.bin_for(pair["lag_s"], pair["r"], rule, beats_chance=beats, above_floor=above) == ARTIFACT


def census_bin(pair, layout, rule):
    """`(bin, cross_pack)` for one measured co-occurrence (D9, D16). `pair` carries `rec_a_id, rec_b_id, lag_s, r,
    chance{beats}, floor{ok}`. `cross_pack` is True/False, or None when the packs' relation is unknown (S0's
    `same_pack` None: exactly one channel unassigned). A copy is an artifact on any packs; otherwise a pack-unknown
    pair is `pack_unknown`, a cross-pack pair `shared_driver`, and a within-pack pair propagation or independent."""
    from Working.channel_layout import same_pack

    sp = same_pack(layout, pair["rec_a_id"], pair["rec_b_id"])
    cross = None if sp is None else (not sp)
    if is_copy(pair, rule):
        return ARTIFACT, cross
    if sp is None:
        return PACK_UNKNOWN, None
    if sp is False:
        return SHARED_DRIVER, True
    if pair.get("lag_s") is None:
        return INDEPENDENT_RECURRENCE, False
    beats = bool((pair.get("chance") or {}).get("beats"))
    above = bool((pair.get("floor") or {}).get("ok"))
    b = xc.bin_for(pair["lag_s"], pair["r"], rule, beats_chance=beats, above_floor=above)
    return (PROPAGATION if b == PROPAGATION else INDEPENDENT_RECURRENCE), False


def _pack_of(layout, rid):
    from Working.channel_layout import _row
    return _row(layout, rid)


def instants(pairs, layout, n_channels, consts=DEFAULT_CONSTANTS):
    """Union-find over the copy pairs (`bin` == artifact): each connected set of events is an INSTANT, with its
    breadth (distinct channels), packs and the common-mode mark (D7). Sets `instant_id` and `common_mode` on every
    pair whose two events fall in one instant. Returns the instants, in onset order."""
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for p in pairs:
        if p["bin"] == ARTIFACT:
            ra, rb = find(p["det_a_id"]), find(p["det_b_id"])
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    groups = {}
    for p in pairs:
        if p["bin"] == ARTIFACT:
            g = groups.setdefault(find(p["det_a_id"]), {"events": set(), "channels": set(), "ratios": [],
                                                        "onset_s": float("inf")})
            g["events"].update((p["det_a_id"], p["det_b_id"]))
            g["channels"].update((p["rec_a_id"], p["rec_b_id"]))
            g["ratios"].append(p.get("amplitude_ratio"))
            g["onset_s"] = min(g["onset_s"], p["onset_a_s"], p["onset_b_s"])
    out, ident = [], {}
    band = float(consts.amplitude_band)
    for k, (root, g) in enumerate(sorted(groups.items(), key=lambda kv: kv[1]["onset_s"]), start=1):
        rows = [_pack_of(layout, r) for r in sorted(g["channels"])]
        packs = sorted({row["pack"] for row in rows})
        known = {row["pack"] for row in rows if row["pack_from"] != "unassigned"}
        breadth = len(g["channels"])
        in_band = all(r is not None and r > 0 and 1.0 / band <= float(r) <= band for r in g["ratios"])
        broad = breadth > consts.breadth_fraction * int(n_channels) and in_band
        spans = len(known) >= 2
        why = []
        if broad:
            why.append(f"broader than {consts.breadth_fraction:g} of {n_channels} channels with every amplitude "
                       f"ratio within ×{band:g}")
        if spans:
            why.append(f"spans {len(known)} packs")
        out.append({"instant_id": k, "breadth": breadth, "channels": sorted(g["channels"]),
                    "events": sorted(g["events"]), "packs": packs, "onset_s": g["onset_s"],
                    "common_mode": bool(broad or spans), "why": "; ".join(why) or None})
        ident[root] = (k, bool(broad or spans))
    for p in pairs:
        ra, rb = find(p["det_a_id"]), find(p["det_b_id"])
        if ra == rb and ra in ident:
            p["instant_id"], p["common_mode"] = ident[ra]
        else:
            p["instant_id"], p["common_mode"] = None, False
    return out


# ── the nulls (D18, X1) ────────────────────────────────────────────────────

def p_value(observed, null):
    """p = (1 + #null ≥ observed) / (K + 1)."""
    null = np.asarray(null)
    return float((1 + int(np.sum(null >= observed))) / (null.size + 1))


def bh(p_values, q=DEFAULT_CONSTANTS.q):
    """Benjamini–Hochberg through the one implementation (`seeded_search.corrected_levels`): the level each test is
    held to, or None where it fails."""
    if not p_values:
        return []
    from Working.discovery.seeded_search import corrected_levels
    return corrected_levels(list(p_values), alpha=q, correction="bh")


def rotation_offsets(n_channels, T_s, K, min_offset_s, seed):
    """`(K, n)` circular offsets in seconds, one per channel per draw, with every PAIR of channels at least
    `min_offset_s` apart on the circle — so each pair's relative rotation is at least that far from zero, and
    every pair's, pack pair's and the overall count are read off the same joint draws. Drawn exactly: n points on
    a circle of T − n·g, spread by g, rotated at random and dealt to the channels at random."""
    n, T, g = int(n_channels), float(T_s), float(min_offset_s)
    if n < 1:
        return np.zeros((int(K), 0))
    if T - n * g <= 0:
        raise ValueError(f"the recording is too short for the rotation null: {n} channels at least "
                         f"{g / 3600:g} h apart need more than {n * g / 3600:g} h, and it holds {T / 3600:g} h")
    rng = np.random.default_rng(seed)
    u = np.sort(rng.uniform(0.0, T - n * g, size=(int(K), n)), axis=1) + np.arange(n) * g
    u = (u + rng.uniform(0.0, T, size=(int(K), 1))) % T
    perm = np.argsort(rng.random((int(K), n)), axis=1)
    return np.take_along_axis(u, perm, axis=1)


def count_co(ta, tb, w):
    """The number of onset pairs (i, j) with |ta_i − tb_j| ≤ w; `tb` sorted."""
    ta, tb = np.asarray(ta, dtype=float), np.asarray(tb, dtype=float)
    if not ta.size or not tb.size:
        return 0
    return int(np.sum(np.searchsorted(tb, ta + w, side="right") - np.searchsorted(tb, ta - w, side="left")))


def rotation_counts(onsets_s, T_s, pairs, ceiling_s, consts=DEFAULT_CONSTANTS, seed=0):
    """`(observed, draws)`: each channel pair's co-occurrence count, and its `(K, n_pairs)` counts under joint
    rotation (`rotation_offsets`). `onsets_s` is `{recording_id: onsets in seconds}`."""
    rids = sorted(onsets_s)
    col = {r: i for i, r in enumerate(rids)}
    ons = {r: np.sort(np.asarray(onsets_s[r], dtype=float)) for r in rids}
    obs = np.array([count_co(ons[a], ons[b], ceiling_s) for a, b in pairs], dtype=np.int64)
    K = int(consts.rotation_k)
    draws = np.zeros((K, len(pairs)), dtype=np.int32)
    if not pairs:
        return obs, draws
    off = rotation_offsets(len(rids), T_s, K, consts.min_rotation_s, seed)
    T = float(T_s)
    for k in range(K):
        sh = {r: np.sort((ons[r] + off[k, col[r]]) % T) for r in rids}
        for j, (a, b) in enumerate(pairs):
            draws[k, j] = count_co(sh[a], sh[b], ceiling_s)
    return obs, draws


def _scan_candidates(lags, delta, lo, hi):
    eps = 1e-6
    c = np.concatenate([lags, lags + delta, lags - delta, [lo + eps, -(lo + eps), hi, -hi]])
    return c[(np.abs(c) > lo) & (np.abs(c) <= hi)]


def _scan_max(lags_2d, delta, lo, hi):
    """The timetable statistic per row of `lags_2d` (K, n): the largest count within ±δ of one allowed L."""
    out = np.zeros(lags_2d.shape[0], dtype=np.int32)
    for k in range(lags_2d.shape[0]):
        lags = lags_2d[k]
        c = _scan_candidates(lags, delta, lo, hi)
        if c.size:
            out[k] = int((np.abs(lags[None, :] - c[:, None]) <= delta + 1e-9).sum(axis=1).max())
    return out


def timetable_scan(lags_s, delta_s, lo_s, hi_s):
    """X1's statistic: the largest number of lags within ±δ of one lag L with lo < |L| ≤ hi, and the median lag and
    MAD of those lags. `L_s` is their median (the timetable's lag); `window_centre_s` the L that held them."""
    lags = np.asarray([v for v in lags_s if v is not None], dtype=float)
    out = {"count": 0, "L_s": None, "window_centre_s": None, "median_lag_s": None, "mad_s": None, "lags_in": []}
    if not lags.size:
        return out
    c = _scan_candidates(lags, delta_s, lo_s, hi_s)
    if not c.size:
        return out
    hits = np.abs(lags[None, :] - c[:, None]) <= delta_s + 1e-9
    counts = hits.sum(axis=1)
    best = None
    for i in np.flatnonzero(counts == counts.max()):
        inside = lags[hits[i]]
        med = float(np.median(inside))
        mad = float(np.median(np.abs(inside - med)))
        key = (mad, abs(float(c[i]) - med), abs(float(c[i])))
        if best is None or key < best[0]:
            best = (key, i, inside, med, mad)
    _, i, inside, med, mad = best
    out.update({"count": int(counts[i]), "L_s": med, "window_centre_s": float(c[i]), "median_lag_s": med,
                "mad_s": mad, "lags_in": [float(v) for v in inside]})
    return out


def timetable_pool(x, y, windows, fs, max_lag, *, size=DEFAULT_CONSTANTS.timetable_pool_min, seed=0, forbidden=()):
    """X1's pool: `size` lags (seconds) measured between the pair's onset windows on `x` and the partner channel
    `y` at random other times (each ≥ 60 s from that window, never over a human-marked artifact of `y`), each the
    restricted-lag peak. Fewer only when the recording has no room."""
    rng = np.random.default_rng(seed)
    fs = float(fs)
    n = len(y)
    gap = int(np.ceil(xc.CROSS_CHANNEL_NULL_MIN_GAP_S * fs))
    wins = []
    for w0, w1 in windows:
        xw = np.asarray(x[int(w0):int(w1)], dtype=float)
        if xw.size < 4 or not np.isfinite(xw).all() or xw.std() == 0:
            continue
        allowed = xc._allowed_starts(n, xw.size, int(w0), int(w1), gap, forbidden)
        total = sum(b - a for a, b in allowed)
        if total > 0:
            wins.append((xw, allowed, np.cumsum([0] + [b - a for a, b in allowed]), total))
    pool = []
    if not wins:
        return np.zeros(0)
    tries = 0
    while len(pool) < size and tries < 3 * size:
        tries += 1
        xw, allowed, bounds, total = wins[int(rng.integers(len(wins)))]
        p = int(rng.integers(total))
        i = int(np.searchsorted(bounds, p, side="right")) - 1
        s0 = int(allowed[i][0] + (p - bounds[i]))
        yw = np.asarray(y[s0:s0 + xw.size], dtype=float)
        if yw.size != xw.size or not np.isfinite(yw).all() or yw.std() == 0:
            continue
        pool.append(xc.cross_correlation_peak(xw, yw, max_lag=max_lag)[0] / fs)
    return np.asarray(pool, dtype=float)


def timetable_null(n, pool, consts=DEFAULT_CONSTANTS, lo_s=1.0, hi_s=50.0, seed=0):
    """X1's null: `consts.timetable_k` draws, each `n` lags resampled from `pool` and scanned as the observed."""
    rng = np.random.default_rng(seed)
    pool = np.asarray(pool, dtype=float)
    draws = rng.choice(pool, size=(int(consts.timetable_k), int(n)), replace=True)
    return _scan_max(draws, consts.timetable_delta_s, lo_s, hi_s)


def breadth_null(onsets_s, T_s, ceiling_s, consts=DEFAULT_CONSTANTS, seed=0):
    """D18's breadth null (conservative): at a uniformly random instant, 1 + the number of OTHER channels (all but
    a random anchor) with any onset within ±ceiling of it. `(K,)` integers."""
    rng = np.random.default_rng(seed)
    rids = sorted(onsets_s)
    K = int(consts.breadth_k)
    t = rng.uniform(0.0, float(T_s), size=K)
    anchor = rng.integers(len(rids), size=K) if rids else np.zeros(K, dtype=int)
    has = np.zeros((K, len(rids)), dtype=bool)
    for j, r in enumerate(rids):
        arr = np.sort(np.asarray(onsets_s[r], dtype=float))
        has[:, j] = np.searchsorted(arr, t + ceiling_s, side="right") > np.searchsorted(arr, t - ceiling_s, side="left")
    if not rids:
        return np.ones(K, dtype=np.int32)
    return (1 + has.sum(axis=1) - has[np.arange(K), anchor]).astype(np.int32)


# ── the hash and stale ─────────────────────────────────────────────────────

def _packs(layout):
    return {str(r): row["pack"] for r, row in sorted(layout["channels"].items(), key=lambda kv: int(kv[0]))}


def census_inputs(conn, source_file, detector=DEFAULT_DETECTOR, *, rule=None, consts=DEFAULT_CONSTANTS, layout=None,
                  runs=None):
    """What a census's hash is made of, read from today's database: the source file, the detector, its real run ids
    and their `finished_at`, the rule, the layout's packs and the channels-events page's last save, the constants
    and the census version."""
    _refuse_held_out(source_file)
    layout = layout or _layout(conn, source_file)
    if runs is None:
        sweep = _sweep(conn, source_file)
        runs = _run_stamps(conn, [r["run_id"] for r in sweep["runs"] if r["variant"] == detector
                                  and int(r["recording_id"]) in {int(k) for k in layout["channels"]}])
    rule = rule or xc.rule_from_settings(conn)
    return {"source_file": str(source_file), "detector": str(detector), "runs": [list(r) for r in runs],
            "rule": rule.as_dict(), "packs": _packs(layout), "settings_updated_at": layout.get("settings_updated_at"),
            "consts": consts.as_dict(), "census_version": CENSUS_VERSION}


def census_hash(inputs):
    """sha256 of the canonical JSON of `census_inputs`."""
    blob = json.dumps(inputs, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def is_stale(conn, census_row):
    """`{stale, why}`: recomputes the inputs from today's database and names each one that changed."""
    row = _parsed(census_row)
    sf, det = row["source_file"], row["detector"]
    why = []
    layout = _layout(conn, sf)
    status = detector_status(conn, sf, det, layout=layout)
    if not status["full"]:
        why.append(f"the detector is no longer full: {status['reason']}")
    now = census_inputs(conn, sf, det, layout=layout)
    then_runs = [list(r) for r in row["run_ids"]]
    if now["runs"] != then_runs:
        added = sorted({r[0] for r in now["runs"]} - {r[0] for r in then_runs})
        gone = sorted({r[0] for r in then_runs} - {r[0] for r in now["runs"]})
        bits = [f"new run{'s' if len(added) != 1 else ''} {', '.join(map(str, added))}" if added else "",
                f"run{'s' if len(gone) != 1 else ''} {', '.join(map(str, gone))} gone" if gone else ""]
        why.append("the detector's runs changed: " + ("; ".join(b for b in bits if b) or "a run was re-finished"))
    if now["rule"] != row["rule"]:
        changed = sorted(k for k in now["rule"] if now["rule"].get(k) != row["rule"].get(k))
        why.append(f"the rule changed in Settings › Analysis defaults ({', '.join(changed)})")
    then_layout = row["layout"]
    if now["packs"] != _packs(then_layout):
        why.append("a channel's pack changed in Settings › Channels & events")
    elif now["settings_updated_at"] != then_layout.get("settings_updated_at"):
        why.append("Settings › Channels & events was saved since (packs are unchanged)")
    if now["consts"] != row["consts"]:
        why.append("the census's constants changed (a new census version)")
    return {"stale": bool(why), "why": why}


# ── the run ────────────────────────────────────────────────────────────────

def _seed(h, *parts):
    v = int(h[:15], 16)
    for p in parts:
        v = (v * 1_000_003 + int(p)) % (2 ** 62)
    return v


def _channel_pairs(rids):
    rids = sorted(rids)
    return [(a, b) for i, a in enumerate(rids) for b in rids[i + 1:]]


def _null_dir():
    from Working import config
    return os.path.join(config.STEP_CACHE_ROOT, "cross_census")


def run_census(conn, source_file, detector=DEFAULT_DETECTOR, *, progress=None, cancel=None, actor="census",
               rule=None, consts=DEFAULT_CONSTANTS, registered=None):
    """Compute the census, then write it in short transactions. Returns `{census_id, hash, summary}`, or None when
    `cancel()` turned true (nothing is written). `progress(done, total, message)` is called with real counts: one
    unit per co-occurrence measured, one per within-pack channel pair's timetable, and one each for the rotation
    draws, the breadth draws and the write."""
    from Working.channel_layout import same_pack
    from Working.library.matching import _human_artifact_spans
    from Working.library.view_filter import dataset_floors

    t_start = time.time()
    _refuse_held_out(source_file)
    rule = rule or xc.rule_from_settings(conn)
    layout = _layout(conn, source_file, registered)
    arrays = {}
    ev = census_events(conn, source_file, detector, layout=layout, arrays=arrays)
    events, recs = ev["events"], ev["recordings"]
    inputs = census_inputs(conn, source_file, detector, rule=rule, consts=consts, layout=layout, runs=ev["runs"])
    h = census_hash(inputs)
    rids = sorted(int(r) for r in layout["channels"])
    for r in rids:
        if r not in arrays:
            arrays[r] = np.load(recs[r]["npy_path"], mmap_mode="r")
    fs_set = {recs[r]["fs"] for r in rids}
    if len(fs_set) != 1:
        raise CensusRefused(f"{source_file}'s channels are at different rates ({sorted(fs_set)} Hz): no common window")
    fs = fs_set.pop()
    T_s = max(recs[r]["n_samples"] for r in rids) / fs
    ceiling = float(rule.propagation_max_lag_s)
    floors = dataset_floors(conn)
    floor = floors.get(str(source_file)) or {"floor_mv": 0.1, "from": "default 0.1 mV"}
    forbidden = _human_artifact_spans(conn, rids)
    ch_pairs = _channel_pairs(rids)
    within = [(a, b) for a, b in ch_pairs if same_pack(layout, a, b) is True]
    across = [(a, b) for a, b in ch_pairs if same_pack(layout, a, b) is False]
    cos = co_occurrences(events, ceiling)
    total = len(cos) + len(within) + 3
    done = 0

    def tick(msg, k=1):
        nonlocal done
        done += k
        if progress is not None:
            progress(min(done, total), total, msg)

    def cancelled():
        return cancel is not None and bool(cancel())

    if progress is not None:
        progress(0, total, f"{len(events)} events · {len(cos)} co-occurrences to measure")

    # 1. measure every co-occurrence
    pairs = []
    for i, (a, b) in enumerate(cos):
        if cancelled():
            return None
        m = measure_pair(arrays[a["recording_id"]], arrays[b["recording_id"]], a["onset"], b["onset"], fs, rule,
                         consts, seed=_seed(h, a["detection_id"], b["detection_id"]),
                         forbidden=forbidden.get(b["recording_id"], ()),
                         units=(recs[a["recording_id"]]["units"], recs[b["recording_id"]]["units"]), floor=floor)
        p = {"det_a_id": a["detection_id"], "det_b_id": b["detection_id"], "rec_a_id": a["recording_id"],
             "rec_b_id": b["recording_id"], "onset_a_s": a["onset_s"], "onset_b_s": b["onset_s"], **m}
        p["bin"], p["cross_pack"] = census_bin(p, layout, rule)
        pairs.append(p)
        if (i + 1) % 20 == 0 or i + 1 == len(cos):
            tick(f"measured {i + 1} of {len(cos)} co-occurrences", k=(i + 1) - done)
    inst = instants(pairs, layout, len(rids), consts)

    # 2. rotation: co-occurrence excess (within-pack pairs and overall) and shared driver (pack pairs and overall)
    if cancelled():
        return None
    onsets = {r: np.array([e["onset_s"] for e in events if e["recording_id"] == r]) for r in rids}
    obs, draws = rotation_counts(onsets, T_s, ch_pairs, ceiling, consts, seed=_seed(h, 1))
    col = {pr: j for j, pr in enumerate(ch_pairs)}
    tick(f"rotation null: {consts.rotation_k} draws over {len(ch_pairs)} channel pairs")

    by_pair = {}
    for p in pairs:
        by_pair.setdefault((p["rec_a_id"], p["rec_b_id"]), []).append(p)

    # 3. the timetable, per within-pack pair
    lo, hi = float(rule.artifact_max_lag_s), ceiling
    max_lag = int(round(ceiling * fs))
    tt_arrays = {}
    pair_rows = []
    for a, b in within:
        if cancelled():
            return None
        ps = by_pair.get((a, b), [])
        noncopy = [p for p in ps if p["bin"] != ARTIFACT and p["lag_s"] is not None]
        scan = timetable_scan([p["lag_s"] for p in noncopy], consts.timetable_delta_s, lo, hi)
        tt = {"n_noncopy": len(noncopy), "count": scan["count"], "L_s": scan["L_s"],
              "median_lag_s": scan["median_lag_s"], "mad_s": scan["mad_s"], "p": None, "q": None,
              "testable": False, "reason": None, "pool": 0, "null_mean": None, "null_p95": None}
        if len(noncopy) < consts.timetable_min_n:
            tt["reason"] = (f"{len(noncopy)} non-copy co-occurrence{'s' if len(noncopy) != 1 else ''}: a timetable "
                            f"needs at least {consts.timetable_min_n}")
        else:
            pool = timetable_pool(arrays[a], arrays[b], [p["window"] for p in noncopy], fs, max_lag,
                                  size=consts.timetable_pool_min, seed=_seed(h, 2, a, b),
                                  forbidden=forbidden.get(b, ()))
            tt["pool"] = int(pool.size)
            if pool.size < consts.timetable_pool_min:
                tt["reason"] = (f"only {pool.size} random-time lags could be measured (the pool needs "
                                f"{consts.timetable_pool_min})")
            if pool.size:
                null = timetable_null(len(noncopy), pool, consts, lo, hi, seed=_seed(h, 3, a, b))
                tt.update({"testable": True, "p": p_value(scan["count"], null), "null_mean": float(null.mean()),
                           "null_p95": float(np.percentile(null, 95))})
                tt_arrays[f"tt_{a}_{b}_pool"] = pool
                tt_arrays[f"tt_{a}_{b}_null"] = null
        d = draws[:, col[(a, b)]]
        pair_rows.append({"a": a, "b": b, "a_name": layout["channels"][a]["name"],
                          "b_name": layout["channels"][b]["name"], "pack": layout["channels"][a]["pack"],
                          "n": int(obs[col[(a, b)]]), "null_mean": float(d.mean()),
                          "null_p95": float(np.percentile(d, 95)), "p": p_value(int(obs[col[(a, b)]]), d), "q": None,
                          "bins": {k: sum(1 for p in ps if p["bin"] == k) for k in CENSUS_BINS},
                          "timetable": tt})
        tick(f"timetable {layout['channels'][a]['name']} → {layout['channels'][b]['name']}")
    for row, lvl in zip(pair_rows, bh([r["p"] for r in pair_rows], consts.q)):
        row["q"] = lvl
    testable = [r for r in pair_rows if r["timetable"]["testable"]]
    for row, lvl in zip(testable, bh([r["timetable"]["p"] for r in testable], consts.q)):
        row["timetable"]["q"] = lvl

    def _overall(cols, observed):
        if not cols:
            return {"n": int(observed), "null_mean": None, "null_p95": None, "p": None, "pairs": 0}
        s = draws[:, cols].sum(axis=1)
        return {"n": int(observed), "null_mean": float(s.mean()), "null_p95": float(np.percentile(s, 95)),
                "p": p_value(int(observed), s), "pairs": len(cols)}

    overall_within = _overall([col[pr] for pr in within], sum(int(obs[col[pr]]) for pr in within))

    # shared driver, per pack pair
    sd_rows = []
    pack_pairs = {}
    for a, b in across:
        key = tuple(sorted((layout["channels"][a]["pack"], layout["channels"][b]["pack"])))
        pack_pairs.setdefault(key, []).append((a, b))
    for key in sorted(pack_pairs):
        prs = pack_pairs[key]
        n_sd = sum(1 for pr in prs for p in by_pair.get(pr, []) if p["bin"] == SHARED_DRIVER)
        row = _overall([col[pr] for pr in prs], n_sd)
        row.update({"packs": list(key), "copies": sum(1 for pr in prs for p in by_pair.get(pr, [])
                                                      if p["bin"] == ARTIFACT)})
        sd_rows.append(row)
    for row, lvl in zip(sd_rows, bh([r["p"] for r in sd_rows], consts.q)):
        row["q"] = lvl
    overall_sd = _overall([col[pr] for pr in across], sum(1 for p in pairs if p["bin"] == SHARED_DRIVER))

    # 4. breadth
    if cancelled():
        return None
    bnull = breadth_null(onsets, T_s, ceiling, consts, seed=_seed(h, 4))
    breadth_rows = []
    for i in inst:
        breadth_rows.append({**{k: i[k] for k in ("instant_id", "breadth", "channels", "packs", "onset_s",
                                                  "common_mode", "why")},
                             "names": [layout["channels"][r]["name"] for r in i["channels"]],
                             "n_events": len(i["events"]), "p": p_value(i["breadth"], bnull), "q": None})
    for row, lvl in zip(breadth_rows, bh([r["p"] for r in breadth_rows], consts.q)):
        row["q"] = lvl
    tick(f"breadth null: {consts.breadth_k} random instants")

    if cancelled():
        return None
    summary = {
        "source_file": str(source_file), "detector": detector, "hash": h, "fs": fs, "hours": T_s / 3600.0,
        "n_channels": len(rids), "n_events": len(events), "n_cooccurrences": len(pairs),
        "events_per_channel": {str(r): sum(1 for e in events if e["recording_id"] == r) for r in rids},
        "onset_from": {k: sum(1 for e in events if e["onset_from"] == k) for k in ("label", "steepest_fall")},
        "bins": {k: sum(1 for p in pairs if p["bin"] == k) for k in CENSUS_BINS},
        "common_mode_pairs": sum(1 for p in pairs if p.get("common_mode")),
        "unmeasured": sum(1 for p in pairs if not p["measurable"]),
        "layout_known": bool(layout["layout_known"]), "layout_note": layout.get("note"),
        "pack_unknown": sum(1 for p in pairs if p["bin"] == PACK_UNKNOWN),
        "packs": layout["packs"],
        "pairs": pair_rows,
        "overall": {"within_pack": overall_within, "shared_driver": overall_sd},
        "shared_driver": sd_rows,
        "breadth": breadth_rows,
        "breadth_null": {"k": int(bnull.size), "mean": float(bnull.mean()), "p95": float(np.percentile(bnull, 95))},
        "bh": {"method": "Benjamini–Hochberg", "q": consts.q,
               "families": {"excess": len(pair_rows), "timetable": len(testable), "breadth": len(breadth_rows),
                            "shared_driver": len(sd_rows)}},
        "rules": rules_in_words(rule, consts),
    }

    # 5. the draws on disk, then the rows in short transactions
    os.makedirs(_null_dir(), exist_ok=True)
    null_path = os.path.abspath(os.path.join(_null_dir(), f"{h}.npz"))
    np.savez_compressed(null_path, rotation=draws, rotation_pairs=np.asarray(ch_pairs, dtype=np.int64).reshape(-1, 2),
                        rotation_observed=obs, breadth=bnull, **tt_arrays)
    old = [int(r[0]) for r in conn.execute("SELECT id FROM cross_census WHERE hash = ?", (h,)).fetchall()]
    with conn:
        for o in old:
            conn.execute("DELETE FROM cross_cooccurrence WHERE census_id = ?", (o,))
            conn.execute("DELETE FROM cross_census WHERE id = ?", (o,))
        cid = conn.execute(
            "INSERT INTO cross_census (source_file, detector, hash, run_ids_json, layout_json, rule_json, consts_json, "
            "status, summary_json, null_path, created_at, actor) VALUES (?, ?, ?, ?, ?, ?, ?, 'writing', NULL, ?, ?, ?)",
            (str(source_file), detector, h, json.dumps(ev["runs"]), json.dumps(layout, default=str),
             json.dumps(rule.as_dict()), json.dumps(consts.as_dict()), null_path, _now(), actor)).lastrowid
    for i in range(0, len(pairs), 500):
        with conn:
            conn.executemany(
                "INSERT INTO cross_cooccurrence (census_id, det_a_id, det_b_id, rec_a_id, rec_b_id, onset_a_s, "
                "onset_b_s, lag_s, r, bin, cross_pack, instant_id, common_mode, chance_json, floor_json, "
                "amplitude_ratio) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(cid, p["det_a_id"], p["det_b_id"], p["rec_a_id"], p["rec_b_id"], p["onset_a_s"], p["onset_b_s"],
                  p["lag_s"], p["r"], p["bin"], None if p["cross_pack"] is None else int(bool(p["cross_pack"])),
                  p.get("instant_id"), int(bool(p.get("common_mode"))),
                  json.dumps(p["chance"]) if p["chance"] else None,
                  json.dumps(dict(p["floor"], window=p["window"], reason=p["reason"] or p["floor"].get("reason")))
                  if p["floor"] else json.dumps({"window": p["window"], "reason": p["reason"]}),
                  p["amplitude_ratio"]) for p in pairs[i:i + 500]])
    summary["timing_s"] = round(time.time() - t_start, 3)
    with conn:
        conn.execute("UPDATE cross_census SET status = 'done', summary_json = ?, finished_at = ? WHERE id = ?",
                     (json.dumps(summary, default=float), _now(), cid))
    tick("written")
    return {"census_id": int(cid), "hash": h, "summary": summary}


# ── reads ──────────────────────────────────────────────────────────────────

def _parsed(row):
    r = dict(row)
    for src, dst in (("summary_json", "summary"), ("run_ids_json", "run_ids"), ("layout_json", "layout"),
                     ("rule_json", "rule"), ("consts_json", "consts")):
        if src in r:
            r[dst] = json.loads(r[src]) if r[src] else None
    return r


def latest_census(conn, source_file, detector=None):
    """The newest finished census of `source_file` (of `detector`, when given), parsed; None when there is none."""
    sql = "SELECT * FROM cross_census WHERE source_file = ? AND status = 'done'"
    args = [str(source_file)]
    if detector:
        sql += " AND detector = ?"
        args.append(str(detector))
    cur = conn.execute(sql + " ORDER BY id DESC LIMIT 1", args)
    row = cur.fetchone()
    if row is None:
        return None
    return _parsed(dict(zip([d[0] for d in cur.description], tuple(row))))


def cooccurrence_rows(conn, census_id, bin=None, a=None, b=None, instant=None, limit=200, offset=0):
    """`{total, rows}` of one census's co-occurrences, filtered by bin, by channel (`a`, and `b` for one pair, in
    either orientation) and by instant. Raises LookupError for an unknown census."""
    if conn.execute("SELECT 1 FROM cross_census WHERE id = ?", (int(census_id),)).fetchone() is None:
        raise LookupError(f"no census {census_id}")
    where, args = ["census_id = ?"], [int(census_id)]
    if bin:
        where.append("bin = ?"); args.append(str(bin))
    if a is not None and b is not None:
        where.append("((rec_a_id = ? AND rec_b_id = ?) OR (rec_a_id = ? AND rec_b_id = ?))")
        args += [int(a), int(b), int(b), int(a)]
    elif a is not None:
        where.append("(rec_a_id = ? OR rec_b_id = ?)"); args += [int(a), int(a)]
    if instant is not None:
        where.append("instant_id = ?"); args.append(int(instant))
    w = " AND ".join(where)
    total = int(conn.execute(f"SELECT COUNT(*) FROM cross_cooccurrence WHERE {w}", args).fetchone()[0])
    cur = conn.execute(f"SELECT * FROM cross_cooccurrence WHERE {w} ORDER BY onset_a_s, id LIMIT ? OFFSET ?",
                       args + [max(0, int(limit)), max(0, int(offset))])
    cols = [d[0] for d in cur.description]
    rows = []
    for raw in cur.fetchall():
        r = dict(zip(cols, raw))
        r["chance"] = json.loads(r.pop("chance_json")) if r.get("chance_json") else None
        r["floor"] = json.loads(r.pop("floor_json")) if r.get("floor_json") else None
        r["cross_pack"] = None if r["cross_pack"] is None else bool(r["cross_pack"])
        r["common_mode"] = bool(r["common_mode"])
        rows.append(r)
    return {"total": total, "rows": rows}


def rules_in_words(rule=xc.DEFAULT_RULE, consts=DEFAULT_CONSTANTS):
    """Every rule the census applies, in words, from the values in use — what the card prints beside each number."""
    f = xc._fmt
    a, r, p, ar = f(rule.artifact_max_lag_s), f(rule.min_abs_r), f(rule.propagation_max_lag_s), f(rule.artifact_min_abs_r)
    w0, w1 = (f(abs(v)) for v in consts.onset_window_s)
    chance = (f"beats chance (|r| above the {f(rule.null_percentile)}th percentile of the partner channel at "
              f"{consts.waveform_k} random other times, each at least {f(xc.CROSS_CHANNEL_NULL_MIN_GAP_S)} s away and "
              f"never over a human-marked artifact, with the same restricted lag search)")
    floor = "both swings clear the dataset's noise floor (Settings › Datasets, 0.1 mV where empty)"
    kr, kb, kt = consts.rotation_k, consts.breadth_k, consts.timetable_k
    return {
        "co_occurrence": f"two events on different channels co-occur when their onsets are within {p} s "
                         f"(the propagation ceiling, Settings › Analysis defaults)",
        "window": f"lag and r are measured on the same samples of both channels, from {w0} s before to {w1} s after "
                  f"the earlier onset",
        "lag_search": f"the lag is searched only within ±{p} s (unrestricted, unrelated drifting channels peak far "
                      f"beyond any propagation)",
        "onset": "the onset is the detector's stored onset label where one is kept, otherwise the steepest fall in "
                 f"the detection's first half on a {f(consts.onset_smooth_s)} s moving average — never the padded "
                 "window start",
        "bins": {
            ARTIFACT: f"suspected artifact (a copy): |lag| ≤ {a} s and |r| ≥ {ar}, {chance}, and {floor}. Any packs. "
                      f"The machine only flags it; a human confirms it in Review",
            PROPAGATION: f"within one pack, {a} s < |lag| ≤ {p} s and |r| ≥ {r}, {chance}, and {floor} — the event "
                         f"arriving on the other electrode a little later",
            INDEPENDENT_RECURRENCE: "within one pack, everything else: not shown to be one event on two electrodes",
            SHARED_DRIVER: "across packs and not a copy: both packs reacting to one stimulus. Never propagation; "
                           "listed for the environment work",
            PACK_UNKNOWN: "exactly one of the two channels has no pack set: whether they share a pack is unknown, so "
                          "the pair is counted apart, never as propagation or a shared driver",
        },
        "common_mode": f"an instant (events joined by copies) is common mode when it covers more than "
                       f"{f(consts.breadth_fraction * 100)} % of the channels with every copy's amplitude ratio "
                       f"within ×{f(consts.amplitude_band)}, or spans two or more packs. A mark inside artifact, "
                       f"never a bin",
        "nulls": {
            "excess": f"rotation: every channel's onset train circularly shifted, each pair at least "
                      f"{f(consts.min_rotation_s / 3600)} h apart, {kr} draws; p = (1 + draws ≥ observed) / (K + 1)",
            "waveform": f"random time: the partner channel at {consts.waveform_k} random other times, "
                        f"{f(rule.null_percentile)}th percentile",
            "timetable": f"the largest number of a pair's non-copy lags within ±{f(consts.timetable_delta_s)} s of "
                         f"one lag L ({a} s < |L| ≤ {p} s), against {kt} draws of as many lags resampled from at "
                         f"least {consts.timetable_pool_min} lags measured between the pair's onset windows and the "
                         f"partner channel at random other times",
            "breadth": f"at {kb} random instants, 1 + the number of other channels with any onset within ±{p} s "
                       f"(conservative)",
            "shared_driver": f"rotation, {kr} draws: cross-pack co-occurrences of any kind under rotation against "
                             f"the observed non-copy ones",
        },
        "correction": f"Benjamini–Hochberg at q = {f(consts.q)}, per recording, separately for co-occurrence excess, "
                      f"timetables, breadth and shared driver; the q shown is the level a test was held to (blank "
                      f"when it fails)",
    }
