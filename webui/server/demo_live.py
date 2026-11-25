"""The demo's one live computation: a seed search from a stretch a visitor marked (Q7 = B).

The distance is the core's (`Adapters.detection_seed_matches.match_exemplar` = `stumpy.match`): the z-normalised
Euclidean distance of the seed to every window, and matches taken closest first with an exclusion zone of
ceil(m / 2) samples around each one. The core recomputes the distance profile from scratch every call (about 25-150
ms a channel); here every channel's and every noise copy's FFT and running sums are computed ONCE at start, so a
search is one FFT per series and the 12 channels plus their 36 noise copies take well under a second.
`tests/test_webui_neurips_demo.py` checks these matches against the core's on real slices.

The cut is the core's (`Working.discovery.seeded_search.recommended_cut`); the null is three phase-randomised copies
of each channel that scripts/neurips_demo/precompute_extras.py stored.
"""
from __future__ import annotations

import math
import sys
import threading
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

K = 25                  # matches per slice, as the shelf (precompute_extras.SEED_K)
SHOWN = 60              # matches sent with a snippet
MAX_SEED_S = 300.0      # a live seed is at most 5 minutes
EXCLUSION = 0.5         # the block's default: an exclusion zone of ceil(0.5 * m)


def _next_fast_len(n: int) -> int:
    try:
        from scipy.fft import next_fast_len
        return int(next_fast_len(n))
    except ImportError:          # pragma: no cover
        return 1 << int(math.ceil(math.log2(n)))


class Series:
    """One signal ready for many queries: its FFT (padded for the longest seed) and its running sums."""

    def __init__(self, x, m_max: int):
        x = np.asarray(x, dtype=np.float64)
        x = x - x.mean()                      # z-normalised distances ignore the offset; this keeps the FFT precise
        self.n = len(x)
        self.L = _next_fast_len(self.n + m_max)
        self.F = np.fft.rfft(x, self.L)
        self.c1 = np.concatenate([[0.0], np.cumsum(x)])
        self.c2 = np.concatenate([[0.0], np.cumsum(x * x)])

    def profile(self, q: np.ndarray) -> np.ndarray:
        """The z-normalised distance of q to every window of this series (inf where the window is flat)."""
        m = len(q)
        sd = q.std()
        qz = (q - q.mean()) / sd
        conv = np.fft.irfft(self.F * np.fft.rfft(qz[::-1], self.L), self.L)
        qt = conv[m - 1: self.n]
        s1 = self.c1[m:] - self.c1[:-m]
        s2 = self.c2[m:] - self.c2[:-m]
        mu = s1 / m
        var = s2 / m - mu * mu
        with np.errstate(invalid="ignore", divide="ignore"):
            r = qt / (m * np.sqrt(var))
            d = np.sqrt(np.maximum(0.0, 2.0 * m * (1.0 - r)))
        d[~(var > 1e-18)] = np.inf
        return d


def top_k(d: np.ndarray, k: int, m: int) -> list[tuple[float, int]]:
    """stumpy.match's greedy pass: the closest window, then nothing within ceil(m * EXCLUSION) of it, k times."""
    d = d.copy()
    excl = int(math.ceil(m * EXCLUSION))
    out = []
    for _ in range(k):
        i = int(np.argmin(d))
        v = float(d[i])
        if not math.isfinite(v):
            break
        out.append((v, i))
        d[max(0, i - excl): i + excl + 1] = np.inf
    return out


class Index:
    """Every slice and every stored noise copy, ready to search."""

    def __init__(self, store):
        self.store = store
        m_max = max(int(MAX_SEED_S * s["fs"]) for s in store.slices.values()) + 2
        surr = store.surrogates()
        self.real = {sid: Series(store.x(sid), m_max) for sid in store.slices}
        self.null = {sid: [Series(y, m_max) for y in surr[sid]] for sid in store.slices}


_INDEX = None
_LOCK = threading.Lock()


def index(store) -> Index:
    global _INDEX
    with _LOCK:
        if _INDEX is None or _INDEX.store is not store:
            _INDEX = Index(store)
        return _INDEX


def warm(store=None):
    """Build the index before a visitor asks (a few seconds at start)."""
    if store is not None:
        index(store)


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


def live_search(store, sid: int, a: int, b: int) -> dict:
    from Working.discovery import seeded_search as SS

    src = store.slices[sid]
    ex = store.x(sid)[a:b]
    if ex.std() <= 1e-12:
        raise ValueError("this stretch is flat: mark one with a shape")
    ix = index(store)
    matches, null_d, draws = [], [], 0
    for s in store.slices.values():
        e = _resample(ex, src["fs"], s["fs"])
        m = len(e)
        if m >= s["n"] // 4:
            continue
        for d, i in top_k(ix.real[s["id"]].profile(e), K + 1, m):
            if s["id"] == sid and i < b and i + m > a:
                continue          # the seed's own place is not a match
            matches.append({"slice": s["id"], "dataset": s["dataset"], "index": i, "length": m,
                            "distance": round(d, 4)})
        for ser in ix.null[s["id"]]:
            null_d += [d for d, _ in top_k(ser.profile(e), K, m)]
            draws += 1
    matches.sort(key=lambda m: (m["distance"], m["index"]))
    cut = SS.recommended_cut([m["distance"] for m in matches], {"distances": null_d, "draws": draws})
    kept = [m for m in matches if cut is not None and m["distance"] <= cut]
    for mt in matches[:SHOWN]:
        x = store.x(mt["slice"])
        pad = mt["length"] // 2
        mt["snip"] = _snippet(x, mt["index"] - pad, mt["index"] + mt["length"] + pad, store.slices[mt["slice"]]["fs"])
        mt["pad"] = pad
    datasets = [d["key"] for d in store.manifest["datasets"]]
    return {"id": "live", "name": "Your marked stretch", "dataset": src["dataset"], "slice": sid, "a": a, "b": b,
            "fs": src["fs"], "exemplar": _snippet(store.x(sid), a, b, src["fs"]), "matches": matches[:SHOWN],
            "n_matches": len(matches), "null": sorted(round(d, 4) for d in null_d), "null_draws": draws, "cut": cut,
            "n_kept": len(kept), "kept_by_dataset": {k: sum(1 for m in kept if m["dataset"] == k) for k in datasets}}
