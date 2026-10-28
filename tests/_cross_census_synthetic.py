"""
_cross_census_synthetic.py
==========================
Synthetic multichannel recordings for the cross-channel census (xc-S1). Not a test module (leading underscore).

A recording is `n` channels of white noise (sd 0.02 mV, stored in mV) with planted events. Each planted event is a
sharp drop (3 mV over 3 s, recovering over a minute) plus a smoothed random wiggle unique to that event, so two
different events correlate weakly while a copy of one event correlates near 1. A planted event becomes one
`drop_detection_v1` detection whose stored start is PADDED (`PAD_S` before the onset), as the real block stores it,
and whose label (the `onset=` the block writes) is not stored anywhere — the census must recover the onset.

`build(conn, root, source_file, n, plant, hours=...)` registers the channels, writes the samples, and inserts one
completed Discovery template run per channel (zero detections where nothing is planted). `plant` is
`{channel_index: [(onset_s, event_key), ...]}`: the same `event_key` on two channels plants the SAME waveform, so a
copy at one instant or a delayed arrival on a neighbour is one event seen twice.
"""

import json

import numpy as np

from Working.database import queries as q

FS = 1.0
NOISE_SD = 0.02
DEPTH = 3.0
EVENT_S = 300
PAD_S = 20
T = "2026-10-28T00:00:00"
DETECTOR = "drop_detection_v1"

_KEY = [0]


def waveform(key, fs=FS):
    """The planted event `key`: a drop at sample 0 plus a wiggle seeded by `key`."""
    n = int(EVENT_S * fs)
    t = np.arange(n) / fs
    fall = np.clip(t / 3.0, 0, 1)
    drop = -DEPTH * fall * np.exp(-np.clip(t - 3.0, 0, None) / 60.0)
    rng = np.random.default_rng(10_000 + int(key))
    w = np.convolve(rng.standard_normal(n + 40), np.ones(30) / 30, mode="same")[20:20 + n]
    w = 0.8 * w / (w.std() or 1.0)
    w[: int(3 * fs)] = 0.0
    return drop + w * (1 - np.exp(-t / 10.0))


def _session(conn, source_file):
    cur = conn.execute("INSERT INTO discovery_sessions (name, source_file, channels_json, created_at, updated_at) "
                       "VALUES ('census', ?, '[]', ?, ?)", (source_file, T, T))
    return cur.lastrowid


def add_run(conn, sid, rid, n_samples, detections, variant=DETECTOR, finished_at=T):
    """One completed template run of `variant` over the whole channel, with `detections` [(start, end)]."""
    _KEY[0] += 1
    gid = conn.execute("INSERT INTO run_groups (created_at) VALUES (?)", (T,)).lastrowid
    cid = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES (?, ?, ?)",
                       (f"xc-cfg-{_KEY[0]}", json.dumps({"template": variant}), T)).lastrowid
    run = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, "
                       "run_group_id, finished_at) VALUES (?, ?, 0, ?, ?, 'completed', ?, ?)",
                       (cid, rid, n_samples, T, gid, finished_at)).lastrowid
    for s, e in detections:
        conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, 1.0)",
                     (run, int(s), int(e)))
    conn.execute("INSERT INTO discovery_runs (session_id, run_key, kind, label, template_name, run_group_id, "
                 "status, created_at, updated_at) VALUES (?, ?, 'template', ?, ?, ?, 'done', ?, ?)",
                 (sid, f"xc-k{_KEY[0]}", variant, variant, gid, T, T))
    return run


def build(conn, root, source_file, n, plant, *, hours=60.0, fs=FS, seed=0, units="mV", channels_with_run=None,
          variant=DETECTOR):
    """Register `n` channels of `source_file`, write their samples and one run each. Returns
    `{recording_ids, npy, onsets: {rid: [onset_sample, ...]}, n_samples}`."""
    stem = source_file.rsplit(".", 1)[0]
    d = root / "channels" / stem
    d.mkdir(parents=True, exist_ok=True)
    ns = int(hours * 3600 * fs)
    rng = np.random.default_rng(seed)
    sid = _session(conn, source_file)
    rids, onsets = [], {}
    for ch in range(n):
        x = NOISE_SD * rng.standard_normal(ns)
        dets = []
        for onset_s, key in plant.get(ch, ()):
            i0 = int(round(onset_s * fs))
            w = waveform(key, fs)
            x[i0:i0 + len(w)] += w[: max(0, ns - i0)]
            dets.append((max(0, i0 - int(PAD_S * fs)), min(ns, i0 + len(w))))
        npy = d / f"CH{ch}.npy"
        np.save(npy, x)
        rid = q.insert_recording(conn, source_file, ch, fs, ns, 0, str(npy), commit=False, units=units)
        rids.append(rid)
        onsets[rid] = [int(round(o * fs)) for o, _ in plant.get(ch, ())]
        if channels_with_run is None or ch in channels_with_run:
            add_run(conn, sid, rid, ns, dets, variant=variant)
    conn.commit()
    return {"recording_ids": rids, "onsets": onsets, "n_samples": ns, "session_id": sid}


def every(n, gap_s, first_s=1800.0, jitter_s=900.0, seed=1):
    """`n` onsets about `gap_s` apart, each jittered by up to ±`jitter_s` (seeded): a strictly periodic train would
    line up with itself under rotation every period, which no real recording does."""
    rng = np.random.default_rng(seed)
    return [first_s + jitter_s + k * gap_s + float(rng.uniform(-jitter_s, jitter_s)) for k in range(n)]
