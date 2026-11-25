"""Do the cross-recording drop matches happen one electrode at a time? (Chapter 7's setup-artefact check, 9 Nov.)

In plain words: a fault in the recording equipment, or a knock to the bench, makes every electrode jump at the same
moment; activity in the culture need not. Chapter 7 checked this for the 372 drop matches in M2_aug (only 6 had a
match on another channel within 50 s, about the 4.6 expected by chance). This repeats the same count on the seven
other recordings searched with the unchanged drop query: the fixed-cut matches of the completed 64-channel transfer
search (cut 2.2080859509008204, the frozen M2_aug threshold), each recording against chance, where chance keeps each
channel's number of matches and places them uniformly in time (1,000 draws).

Read-only on the returned seed results under DATA/derived/hpc/rq2_drop_transfer_20261107/ (the same files
`audit_recovery_return_20261108.seed_audit` verifies). Writes docs/thesis/data/transfer_cooccurrence_20261109.json.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/transfer_cooccurrence_20261109.py
"""
from __future__ import annotations

import json
import os

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SEED = os.path.join(ROOT, "DATA", "derived", "hpc", "rq2_drop_transfer_20261107")
OUT = os.path.join(ROOT, "docs", "thesis", "data", "transfer_cooccurrence_20261109.json")
W = 50.0
DRAWS = 1000


def matches(d, cut):
    spec_path = os.path.join(ROOT, d["spec_path"])
    spec = json.load(open(spec_path, encoding="utf-8"))
    stem = os.path.basename(spec_path).replace(".spec.json", "")
    parts = os.path.join(os.path.dirname(spec_path), stem + "_parts")
    out = {}
    for ch in spec["channels"]:
        r = json.load(open(os.path.join(parts, f"{stem}__{ch['name']}.result.json"), encoding="utf-8"))
        if not r.get("complete") or r["perChannel"][0]["null"]["draws"] != 200:
            raise ValueError(f"{d['recording']} {ch['name']}: incomplete seed result")
        res = r["perChannel"][0]
        out[ch["name"]] = np.sort(np.array([c["index"] for c in res["candidates"] if c["distance"] <= cut],
                                           dtype=float) / float(res["fs"]))
    return out


def co_count(times):
    """Matches with at least one match on ANOTHER channel within W seconds."""
    allt = np.concatenate([t for t in times.values()]) if times else np.zeros(0)
    lab = np.concatenate([np.full(len(t), i) for i, t in enumerate(times.values())]) if times else np.zeros(0)
    order = np.argsort(allt, kind="stable")
    allt, lab = allt[order], lab[order]
    hit = np.zeros(len(allt), dtype=bool)
    lo = 0
    for i in range(len(allt)):
        while allt[i] - allt[lo] > W:
            lo += 1
        j = lo
        while j < len(allt) and allt[j] - allt[i] <= W:
            if j != i and lab[j] != lab[i]:
                hit[i] = True
                break
            j += 1
    return int(hit.sum()), allt, lab, hit


def main():
    man = json.load(open(os.path.join(SEED, "manifest.json"), encoding="utf-8"))
    cut = float(man["frozen_m2_aug_cut"])
    rng = np.random.default_rng(20261109)
    rows = []
    for d in man["datasets"]:
        times = matches(d, cut)
        n = sum(len(t) for t in times.values())
        obs, allt, lab, hit = co_count(times)
        T = float(d["recording_hours"]) * 3600.0
        null = np.array([co_count({k: np.sort(rng.uniform(0, T, len(t))) for k, t in times.items()})[0]
                         for _ in range(DRAWS)])
        names = list(times)
        pairs = sorted({tuple(sorted((names[int(lab[i])], names[int(lab[j])])))
                        for i in np.flatnonzero(hit) for j in range(len(allt))
                        if j != i and lab[j] != lab[i] and abs(allt[j] - allt[i]) <= W})
        row = {"recording": d["recording"], "channels": len(times),
               "channels_with_matches": sum(len(t) > 0 for t in times.values()), "matches": n,
               "with_other_channel_within_50s": obs, "chance_mean": float(null.mean()),
               "chance_p95": float(np.percentile(null, 95)), "p": (1 + int(np.sum(null >= obs))) / (DRAWS + 1),
               "co_occurring_channel_pairs": [list(p) for p in pairs]}
        rows.append(row)
        print(f"{d['recording']:10s} {n:4d} matches on {row['channels_with_matches']:2d}/{len(times):2d} channels; "
              f"{obs:3d} with another channel's match within {W:g} s, chance {row['chance_mean']:.1f} "
              f"(95th pct {row['chance_p95']:g}; p {row['p']:.3f}); pairs {pairs}")
    tot = {"matches": sum(r["matches"] for r in rows),
           "with_other_channel_within_50s": sum(r["with_other_channel_within_50s"] for r in rows),
           "chance_mean": sum(r["chance_mean"] for r in rows)}
    print("all seven:", tot)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"cut": cut, "window_s": W, "draws": DRAWS, "recordings": rows, "total": tot}, f, indent=2)


if __name__ == "__main__":
    main()
