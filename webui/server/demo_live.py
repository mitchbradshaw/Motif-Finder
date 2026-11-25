"""The demo's one live computation: a seed search from a stretch a visitor marked (Q7 = B).

The search and its matches are the core's (`Working.discovery.seeded_search.candidates`, the block's own
match_exemplar, z-normalised distances), the cut is the core's `recommended_cut`. Only the null differs from the
pre-searched shelf: instead of drawing fresh surrogates it reads the three phase-randomised copies of each slice that
scripts/neurips_demo/precompute_extras.py stored, so a search over all 12 slices stays under a second.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

K = 25          # matches per slice, as the shelf (precompute_extras.SEED_K)
SHOWN = 60      # matches sent with a snippet


def _resample(ex, fs_from, fs_to):
    if abs(fs_from - fs_to) < 1e-9:
        return np.asarray(ex, dtype=float)
    n = max(8, int(round(len(ex) * fs_to / fs_from)))
    return np.interp(np.linspace(0, len(ex) - 1, n), np.arange(len(ex)), ex)


def _snippet(x, a, b, fs, n_max=120):
    a, b = max(0, int(a)), min(len(x), int(b))
    seg = x[a:b]
    step = max(1, int(math.ceil(max(1, len(seg)) / n_max)))
    return {"dt": step / fs, "v": [round(float(v), 4) for v in seg[::step]]}


MAX_SEED_S = 300.0      # a live seed is at most 5 minutes (a 15-minute one took ~7 s over 12 slices + null)

_POOL = None


def _pool():
    global _POOL
    if _POOL is None:
        from concurrent.futures import ThreadPoolExecutor
        _POOL = ThreadPoolExecutor(max_workers=6, thread_name_prefix="seed")
    return _POOL


def warm():
    """Compile the matrix-profile kernels once (stumpy/numba: ~6 s on the first call), before a visitor asks."""
    from Working.discovery import seeded_search as SS
    x = np.random.default_rng(0).standard_normal(20000)
    SS.candidates(x, x[1000:1046], k=K + 1)


def live_search(store, sid: int, a: int, b: int) -> dict:
    from Working.discovery import seeded_search as SS

    src = store.slices[sid]
    ex = store.x(sid)[a:b]
    surr = store.surrogates()

    def one(s):
        x = store.x(s["id"])
        e = _resample(ex, src["fs"], s["fs"])
        if len(e) >= len(x) // 4:
            return [], [], 0
        ms = []
        for c in SS.candidates(x, e, k=K + 1):
            i = int(c["index"])
            if s["id"] == sid and i < b and i + len(e) > a:
                continue          # the seed's own place is not a match
            ms.append({"slice": s["id"], "dataset": s["dataset"], "index": i, "length": len(e),
                       "distance": round(float(c["distance"]), 4)})
        nd = []
        for y in surr[s["id"]]:
            nd += [float(c["distance"]) for c in SS.candidates(y, e, k=K)]
        return ms, nd, len(surr[s["id"]])

    matches, null_d, draws = [], [], 0
    for ms, nd, dr in _pool().map(one, list(store.slices.values())):
        matches += ms
        null_d += nd
        draws += dr
    matches.sort(key=lambda m: m["distance"])
    cut = SS.recommended_cut([m["distance"] for m in matches], {"distances": null_d, "draws": draws})
    kept = [m for m in matches if cut is not None and m["distance"] <= cut]
    for m in matches[:SHOWN]:
        x = store.x(m["slice"])
        pad = m["length"] // 2
        m["snip"] = _snippet(x, m["index"] - pad, m["index"] + m["length"] + pad, store.slices[m["slice"]]["fs"])
        m["pad"] = pad
    datasets = [d["key"] for d in store.manifest["datasets"]]
    return {"id": "live", "name": "Your marked stretch", "dataset": src["dataset"], "slice": sid, "a": a, "b": b,
            "fs": src["fs"], "exemplar": _snippet(store.x(sid), a, b, src["fs"]), "matches": matches[:SHOWN],
            "n_matches": len(matches), "null": sorted(round(d, 4) for d in null_d), "null_draws": draws, "cut": cut,
            "n_kept": len(kept), "kept_by_dataset": {k: sum(1 for m in kept if m["dataset"] == k) for k in datasets}}
