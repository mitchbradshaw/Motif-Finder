"""
fluss.py
========
FLUSS — Fast Low-cost Unipotent Semantic Segmentation (Gharghabi S, Ding Y,
Yeh C-CM, Kamgar K, Ulanova L, Keogh E (2017) Matrix Profile VIII, ICDM 2017,
pp. 117-126, DOI 10.1109/ICDM.2017.21): where does a recording change
behaviour?

In plain words: the matrix-profile index says, for every window of the
recording, where its most similar window is. Draw an arc from each window to
that look-alike. Inside one regime of behaviour the arcs stay inside it, so at
a change of behaviour few arcs cross. Count the arcs over every point (the arc
curve, AC), divide by how many would cross there if neighbours were random
(the idealised arc curve, IAC — the middle of a series always collects more
arcs than its ends), cap at 1: that is the corrected arc curve, CAC. Dips of
the CAC are the changes. This module returns **1 - CAC** as a regime-change
score (0 = no evidence of a change, high = a change), so the generic
`detection.threshold` can cut it.

The algorithm, as implemented
-----------------------------
1. Input: the matrix-profile INDEX `I` (integers, `mp[:, 1]`), never the
   distances. stumpy's own `fluss` docstring examples pass `mp[:, 0]` / `mp.P_`
   (distances) — wrong; a float array is refused here with that explanation.
2. AC, CAC and the regime extraction are stumpy 1.14.1's `stumpy.fluss`
   (BSD-3-Clause, Copyright 2019 TD Ameritrade) — called, not copied.
   **Missing neighbours (adaptation).** A window touching a NaN has no
   neighbour (stumpy marks it -1) and draws no arc, but the IAC assumes every
   window draws one, so beside a long NaN gap the arc count falls short of the
   IAC and the valid stretch looks like the end of a regime (a 4000-sample
   gap in one regime scored 0.93). So FLUSS runs on the *compressed* index:
   the valid windows only, renumbered 0..k_valid-1 (a neighbour is always a
   valid window), with the IAC for k_valid windows; the CAC is mapped back to
   the valid windows' positions and the windows with no neighbour are not
   scored (NaN). Across a gap the compressed index sees the two sides as
   adjacent, which is what they are to the matrix profile. Counted in
   `n_no_neighbour`.
3. The IAC (parameter `iac`):
   - `"parabola"` (default) — the paper's 2i(n-i)/n, height n/2 (fig. 4, "a
     special case of beta(2,2)"), passed to stumpy as `custom_iac`.
   - `"beta"` — stumpy's default: a beta distribution fitted (1000 fits of
     1000 samples, seed 0) to the arc curve of a uniformly random index, then
     scaled by least squares. On a random index it is the parabola to within
     about 1 % in the middle and 1-2 % near the ends. Its cost grows with the
     span (it draws random indices of the span's length): about 1.4 s at 4 h
     and 4.9 s at 24 h at 1 Hz, on top of the matrix profile.
4. Edges — **stumpy's convention is kept**: CAC is set to 1 over the first and
   last `excl_factor * L` (valid) subsequences (stumpy `floss.py:178-179`), where the
   paper sets only the first and last `L` (Table I line 17). With L = the
   window m and excl_factor 5, that is five windows at each end. The reason to
   keep it: the IAC is near zero at the ends, so AC/IAC there is a ratio of two
   small, noisy counts, and the wider blank is what stops a spurious "change"
   at either end of every span. **Adaptation:** the blanked stretches are
   reported as NaN in the score, not 0 — they are "not scored", not "no
   change" — and counted in `n_blanked_each_end`.
5. Score = 1 - CAC. CAC has `n - m + 1` values (one per window start); the
   last `m - 1` samples start no full window and are NaN, as
   `detection.matrix_profile` pads its profile. `detection.threshold` treats
   NaN as "below the cut", so neither NaN stretch can become a span.
6. Readout: the paper's regime extraction (Table II, `stumpy.fluss`'s `_rea`):
   the `n_regimes - 1` lowest CAC minima, each excluding `excl_factor * L`
   either side, with the CAC at each. stumpy always returns that many; once
   the exclusion zones cover the whole span it pads with the argmin of an
   all-ones curve (location 0, CAC 1.0). **Adaptation:** locations whose CAC
   is 1.0 are dropped (they are not evidence of anything) and
   `n_regimes_found` = kept locations + 1 is reported. A kept location can
   still have a CAC near 1 on a recording with no change — read the CAC
   beside it (paper §7: a high CAC minimum means only "no evidence of a
   change").

Where it breaks: a drift ramp, z-normalised, looks the same everywhere, so its
nearest neighbours are anywhere, arcs cross everywhere and the CAC stays near
1 — FLUSS fails safe (finds no change) rather than inventing one. Detrend
first. FLUSS "is not able to segment single gesture patterns" (paper): a
change must last several windows to show.

No UI imports; numpy and stumpy only. The matrix profile itself is not
computed here (the adapter reuses the site's existing computation).
"""

import numpy as np
import stumpy

IAC_KINDS = ("parabola", "beta")


def parabola_iac(k):
    """The paper's idealised arc curve for a `k`-long index: 2i(k-i)/k,
    zero at i = 0 and k/2 at the middle (Gharghabi et al. 2017, fig. 4)."""
    i = np.arange(k, dtype=np.float64)
    return 2.0 * i * (k - i) / k


def _as_index(mpi):
    a = np.asarray(mpi)
    if a.dtype.kind == "O":                         # stumpy.stump's mixed-type output column
        try:
            f = a.astype(np.float64)
        except (TypeError, ValueError) as e:
            raise TypeError("FLUSS needs the matrix-profile index (integers, mp[:, 1])") from e
        if not np.all(np.isfinite(f)) or not np.all(f == np.round(f)):
            raise TypeError("FLUSS needs the matrix-profile index (integers, mp[:, 1]), "
                            "not the distances (mp[:, 0])")
        a = f
    elif a.dtype.kind not in "iu":
        raise TypeError(
            f"FLUSS needs the matrix-profile index (integers, mp[:, 1]); got a {a.dtype} array — "
            "the distances (mp[:, 0]) are a common mistake (stumpy's own fluss docstring makes it)."
        )
    if a.ndim != 1:
        raise ValueError(f"the matrix-profile index must be 1-D; got shape {a.shape}")
    return a.astype(np.int64, copy=True)


def regime_change_score(mpi, m, iac="parabola", excl_factor=5, n_regimes=3):
    """Regime-change score (1 - CAC) from a matrix-profile index.

    Parameters
    ----------
    mpi : array of int, length k = n - m + 1
        The matrix-profile index of the analysed signal (`mp[:, 1]`).
        Not modified.
    m : int
        The window (subsequence length) the profile was computed with; used
        as FLUSS's L for the edge blanking and the readout's exclusion zone.
    iac : "parabola" | "beta"
        The idealised arc curve (see the module docstring).
    excl_factor : int >= 1
        Edges blanked and readout exclusion, in windows (stumpy's 5).
    n_regimes : int >= 2
        For the readout only: report the `n_regimes - 1` strongest changes.

    Returns
    -------
    dict with
        score : float array of length k + m - 1 (= n), NaN where not scored
        cac : the raw CAC (length k, edges set to 1 as stumpy does, NaN at
            windows with no neighbour)
        cac_min, cac_min_idx : the lowest CAC inside the scored region, and
            where (span-relative sample index)
        regime_locs, regime_cac : the readout (lists; CAC-1.0 padding dropped)
        n_regimes_found : len(regime_locs) + 1
        n_blanked_each_end, n_no_neighbour, iac, excl_factor, m
    """
    if iac not in IAC_KINDS:
        raise ValueError(f"iac must be one of {IAC_KINDS}, got {iac!r}")
    m = int(m)
    excl_factor = int(excl_factor)
    n_regimes = int(n_regimes)
    if m < 1:
        raise ValueError(f"window m must be at least 1 sample, got {m}")
    if excl_factor < 1:
        raise ValueError(f"excl_factor must be at least 1, got {excl_factor}")
    if n_regimes < 2:
        raise ValueError(f"n_regimes must be at least 2 (one change), got {n_regimes}")

    index = _as_index(mpi)
    k = len(index)
    blank = excl_factor * m
    if k <= 2 * blank:
        raise ValueError(
            f"span too short for FLUSS: {k} window starts, but {blank} are blanked at each end "
            f"(excl_factor {excl_factor} x window {m}); the span needs more than "
            f"{2 * blank + m - 1} samples. Shorten the window or lengthen the span."
        )
    valid = index >= 0
    pos = np.flatnonzero(valid)                      # compressed position -> window start
    kv = len(pos)
    n_no_neighbour = k - kv
    if kv <= 2 * blank:
        raise ValueError(
            f"too few scorable windows for FLUSS: {n_no_neighbour} of {k} windows touch NaN and "
            f"have no neighbour, leaving {kv}, but {blank} are blanked at each end. Fill or cut "
            "the NaN gaps, or shorten the window."
        )
    rank = np.full(k, -1, dtype=np.int64)
    rank[pos] = np.arange(kv)
    cindex = rank[index[valid]]
    dangling = cindex < 0                            # a neighbour with no neighbour of its own:
    cindex[dangling] = np.flatnonzero(dangling)      # never in a real profile; drawn as no arc

    custom = parabola_iac(kv) if iac == "parabola" else None
    ccac, clocs = stumpy.fluss(cindex, L=m, n_regimes=n_regimes, excl_factor=excl_factor,
                               custom_iac=custom)
    ccac = np.asarray(ccac, dtype=np.float64)

    cac = np.full(k, np.nan)                         # NaN = no neighbour, never scored
    cac[pos] = ccac
    score = np.full(k + m - 1, np.nan)
    inner_pos = pos[blank:kv - blank]
    score[inner_pos] = 1.0 - ccac[blank:kv - blank]
    inner = ccac[blank:kv - blank]
    j = int(np.argmin(inner))

    kept = [int(v) for v in np.asarray(clocs).ravel() if ccac[int(v)] < 1.0]
    return {
        "score": score,
        "cac": cac,
        "cac_min": float(inner[j]),
        "cac_min_idx": int(inner_pos[j]),
        "regime_locs": [int(pos[v]) for v in kept],
        "regime_cac": [float(ccac[v]) for v in kept],
        "n_regimes_found": len(kept) + 1,
        "n_blanked_each_end": blank,
        "n_no_neighbour": int(n_no_neighbour),
        "iac": iac,
        "excl_factor": excl_factor,
        "m": m,
    }
