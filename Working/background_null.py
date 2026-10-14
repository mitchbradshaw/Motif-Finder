"""
background_null.py
===================
Windows of a recording's own background: stretches cut at random from where
nothing was detected, for a noise test whose noise is the recording itself
(w3-b). Generic on purpose — it knows nothing of cycles, families or events.
`Working.interrogation.cycle_shapes` uses it for its verdict null, and the
Library's quiet-stretch test for families (W3-G) is meant to reuse it.

Why a background null at all (wave 2's lesson, `Working/library/coherence.py::
SMOOTH_CAVEAT`): a surrogate built from the shapes themselves keeps whatever it
does not destroy — the trend-kept phase surrogate keeps a smooth curve that
fills the window, so a broad hump or a drop-floor-climb cycle reads "no more
coherent than its own noise". Windows of the recording where no event lies
have the recording's colour, drift and artefacts, and none of the shapes.

The contract
------------
`sample_background(trace, avoid, lengths, count, seed, *, fs=None)` ->
`BackgroundSample(starts, lengths, windows, report)`:

* `trace` — 1-D array, one recording (or span) in its own index frame;
* `avoid` — sample ranges `(start, end)`, half-open, in the trace's frame, that
  no window may touch (the events; clipped to the trace). Samples holding NaN
  are avoided too, so a background window carries no gap;
* `lengths` — the window lengths wanted, in samples: each window's length is
  drawn uniformly, with replacement, from this list (so passing the real
  windows' lengths gives the null their length distribution; a single value
  gives every window that length);
* `count` — how many windows; `seed` — the seed of the generator (seeded,
  never numpy's global state: the bridge runs jobs on threads);
* returns the window starts and lengths (int64 arrays, in the trace's frame),
  the windows themselves (copies, one 1-D array each), and `report`:
  `n_wanted`, `n_cut`, `n_fallback`, `fell_back`, `n_too_long`,
  `background_samples` (free samples: neither avoided nor NaN),
  `background_s` (when `fs` is given), `trace_samples`, `rule`, and
  `longest_free_samples` / `longest_free_s` (the longest free stretch: fragmented
  background versus too little; added in w3-b's fix round, the earlier keys unchanged).

**The fallback.** A window whose length fits in no free stretch is cut instead
at a uniformly random place in the whole trace (it may overlap events and
gaps), and counted in `n_fallback`; `fell_back` is True when any window was.
A window longer than the trace is not cut at all (`n_too_long`). Windows may
overlap one another: they are draws, not a partition.

No plotting library — CLAUDE.md rule 1.
"""

from dataclasses import dataclass, field

import numpy as np

RULE = ("background windows: each length drawn with replacement from the wanted lengths; each start uniform over "
        "every place the whole window fits in a free stretch (no avoided sample, no NaN); a window that fits in no "
        "free stretch is cut at a uniform place in the whole trace instead (counted as a fallback); windows may "
        "overlap one another; seeded")


@dataclass
class BackgroundSample:
    starts: np.ndarray
    lengths: np.ndarray
    windows: list = field(default_factory=list)
    report: dict = field(default_factory=dict)


def free_runs(n, avoid, nan_mask=None):
    """`(run_starts, run_ends)` of the samples in `0..n-1` that no avoided range
    covers and that are not NaN, as half-open runs."""
    free = np.ones(int(n), dtype=bool)
    for a, b in avoid:
        a, b = max(0, int(a)), min(int(n), int(b))
        if b > a:
            free[a:b] = False
    if nan_mask is not None:
        free &= ~np.asarray(nan_mask, dtype=bool)
    edges = np.diff(np.concatenate([[0], free.astype(np.int8), [0]]))
    return np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)


def sample_background(trace, avoid, lengths, count, seed, *, fs=None):
    """Background windows of `trace` (module docstring: the contract)."""
    trace = np.asarray(trace, dtype=float).ravel()
    n = trace.size
    lengths = np.asarray(lengths, dtype=np.int64).ravel()
    count = int(count)
    if lengths.size == 0 and count > 0:
        raise ValueError("sample_background needs at least one wanted window length.")
    if np.any(lengths <= 0):
        raise ValueError("sample_background: every wanted window length must be a positive number of samples.")
    rng = np.random.default_rng(seed)
    rs, re = free_runs(n, avoid, np.isnan(trace))
    run_len = re - rs
    want = rng.choice(lengths, size=count, replace=True) if count > 0 else np.zeros(0, dtype=np.int64)
    starts, got, windows = [], [], []
    n_fallback = n_too_long = 0
    for L in want:
        L = int(L)
        if L > n:
            n_too_long += 1
            continue
        cs = np.cumsum(np.maximum(0, run_len - L + 1))
        total = int(cs[-1]) if cs.size else 0
        if total > 0:
            u = int(rng.integers(total))
            k = int(np.searchsorted(cs, u, side="right"))
            s = int(rs[k] + u - (int(cs[k - 1]) if k else 0))
        else:
            n_fallback += 1
            s = int(rng.integers(n - L + 1))
        starts.append(s)
        got.append(L)
        windows.append(trace[s:s + L].copy())
    free_samples = int(run_len.sum())
    report = {"n_wanted": count, "n_cut": len(starts), "n_fallback": n_fallback, "fell_back": bool(n_fallback),
              "n_too_long": n_too_long, "background_samples": free_samples,
              "background_s": (free_samples / float(fs)) if fs else None, "trace_samples": int(n), "rule": RULE}
    # w3-b fix 1 (compatible extension): the longest free stretch, so a caller can tell "too little
    # background" from "plenty, but in pieces shorter than the windows"
    longest = int(run_len.max()) if run_len.size else 0
    report["longest_free_samples"] = longest
    report["longest_free_s"] = (longest / float(fs)) if fs else None
    return BackgroundSample(starts=np.asarray(starts, dtype=np.int64), lengths=np.asarray(got, dtype=np.int64),
                            windows=windows, report=report)
