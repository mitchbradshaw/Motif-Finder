"""B4 (do events co-occur across electrodes?) on SH and SO, from the drop detector recomputed in memory (9 Nov).

In plain words: B4 asks whether a drop on one electrode is followed, within 50 s, by a drop on another more often
than chance. SH and SO have no drop-detector run in the database (their sweep tasks ran on the cluster and were
never imported), so the census page cannot run on them. This script reruns ``drop_detection_v1`` on each of their
four channels in memory, from the cluster task's own frozen specification (same input file, checked by its SHA-1;
same steps and settings), checks that every channel gives exactly the number of detections the cluster returned,
and then counts cross-channel co-occurrences with the census's own functions (``Working.cross_census``:
``co_occurrences``, ``rotation_counts`` with its joint-rotation null). Packs are not set for these recordings, so,
as on CO and LM, every pair is counted together and no shared-driver or propagation bin can be separated.

Read-only: nothing is written to the database or under DATA/. Output: docs/thesis/data/ch10_b4/b4_sh_so_20261109.json.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/b4_sh_so_20261109.py
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from Working import cross_census as cc  # noqa: E402

HPC = os.path.join(ROOT, "docs", "thesis", "hpc", "rq4_newsets_20261027")
OUT = os.path.join(ROOT, "docs", "thesis", "data", "ch10_b4", "b4_sh_so_20261109.json")
CHAIN = ["detrend", "stage_encoding", "drop_detection"]
ONSET = re.compile(r"onset=(\d+);trough=(\d+);(\w+)")


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def run_channel(target, steps):
    from Adapters.detection_drop_detection import _run as drop
    from Adapters.detection_stage_encoding import _run as encode
    from Adapters.preprocessing_detrend import _run as detrend
    npy = os.path.join(ROOT, target["npy"])
    if sha1(npy) != target["npySha1"]:
        raise ValueError(f"{target['channelName']}: the channel file differs from the one the cluster used")
    s0, s1 = (int(v) for v in target["span"])
    fs = float(target["fs"])
    x = np.asarray(np.load(npy, mmap_mode="r")[s0:s1])
    t = np.arange(s0, s1) / fs
    p = [s["params"] for s in steps]
    xd = detrend(x, t, fs, **p[0]).value.x
    enc = encode(xd, t, fs, **p[1])
    res = drop(xd, t, fs, value=enc.value, units=target.get("units") or "V", **p[2]).value
    onsets = []
    for lab in res.labels:
        m = ONSET.search(str(lab))
        if not m:
            raise ValueError(f"{target['channelName']}: a detection without an onset label: {lab!r}")
        onsets.append(int(m.group(1)) + s0)
    return np.sort(np.asarray(onsets, dtype=float)) / fs, len(res.starts)


def census(name):
    spec_path = glob.glob(os.path.join(HPC, name, "drop_detection_v1_4ch_*.chain.json"))
    if len(spec_path) != 1:
        raise ValueError(f"{name}: expected one default drop_detection_v1 spec, found {spec_path}")
    spec = json.load(open(spec_path[0], encoding="utf-8"))
    steps = spec["steps"]
    if [s["algorithm"] for s in steps] != CHAIN:
        raise ValueError(f"{name}: unexpected chain {[s['algorithm'] for s in steps]}")
    out_dir = spec_path[0].replace(".chain.json", "_out")
    onsets, rows, T = {}, [], None
    for tgt in spec["targets"]:
        result = json.load(open(os.path.join(out_dir, "return", f"task{tgt['index']}", "result.json"),
                                encoding="utf-8"))
        on, n = run_channel(tgt, steps)
        expected = int(result["run"]["detections"])
        if n != expected:
            raise ValueError(f"{name} {tgt['channelName']}: {n} detections recomputed, the cluster returned {expected}")
        onsets[int(tgt["recordingId"])] = on
        rows.append({"channel": tgt["channelName"], "recording_id": int(tgt["recordingId"]), "events": n,
                     "cluster_detections": expected})
        T = (int(tgt["span"][1]) - int(tgt["span"][0])) / float(tgt["fs"])
    events = [{"recording_id": r, "onset_s": float(s)} for r, ons in onsets.items() for s in ons]
    ceiling = 50.0
    co = cc.co_occurrences(events, ceiling)
    rids = sorted(onsets)
    pairs = [(a, b) for i, a in enumerate(rids) for b in rids[i + 1:]]
    obs, draws = cc.rotation_counts(onsets, T, pairs, ceiling, seed=20261109)
    total, null = int(obs.sum()), draws.sum(axis=1)
    p = (1 + int(np.sum(null >= total))) / (len(null) + 1)
    summary = {"recording": name, "spec": os.path.relpath(spec_path[0], ROOT).replace("\\", "/"),
               "channels": rows, "n_events": int(sum(r["events"] for r in rows)), "hours": T / 3600.0,
               "ceiling_s": ceiling, "co_occurrences": len(co), "rotation_draws": int(len(null)),
               "rotation_null_mean": float(null.mean()), "rotation_null_p95": float(np.percentile(null, 95)),
               "p": p, "packs": "not set: every pair counted together, as on CO and LM",
               "pairs": [{"a": a, "b": b, "observed": int(o), "null_mean": float(d.mean())}
                         for (a, b), o, d in zip(pairs, obs, draws.T)],
               "examples": [{"a": e["recording_id"], "b": f["recording_id"], "onset_a_h": e["onset_s"] / 3600,
                             "lag_s": f["onset_s"] - e["onset_s"]} for e, f in co[:20]]}
    print(f"{name}: {summary['n_events']} drops on {len(rows)} channels "
          f"({', '.join(str(r['events']) for r in rows)}), all equal to the cluster's counts; "
          f"{len(co)} co-occurrences within {ceiling:g} s against {summary['rotation_null_mean']:.2f} expected "
          f"(95th percentile {summary['rotation_null_p95']:g}; p {p:.3f})")
    return summary


def main():
    result = {"generated_by": "scripts/thesis/b4_sh_so_20261109.py", "read_only": True,
              "detector": "drop_detection_v1", "censuses": [census(n) for n in ("SH_fs2", "SO_fs2")]}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
