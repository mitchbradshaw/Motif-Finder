"""
distances.py
==============
Four named ways to say two spans are the same shape (three from T35, the
fourth from w3-d), each a named constant rather than an anonymous callable so
it can be recorded verbatim on the `motif_edge` it produces (PIPELINE_PRD.md,
"Distances"):

  DISTANCE_SCALE_INVARIANT  Resample both spans to a common length,
                            z-normalise, Euclidean. The primary distance —
                            shape independent of duration.
  DISTANCE_SYMBOLIC         SAX minimum-distance (MINDIST) at a fixed word
                            length. Scale-invariant by construction through
                            piecewise aggregation: reuses the existing SAX
                            ports (`normal_cutlines` for breakpoints,
                            `timeseries2symbol` for the PAA + z-normalise +
                            quantise pipeline it already implements) rather
                            than reimplementing PAA.
  DISTANCE_NATIVE_LENGTH    z-normalised Euclidean at native length (no
                            resampling) — the unnormalised control. Spans
                            of unequal length are compared over their
                            shorter's length, unresampled, so a duration
                            mismatch shows up as a large distance rather
                            than being reconciled away.
  DISTANCE_MPDIST           MPdist (Gharghabi et al. 2018, w3-d): do the two
                            spans share their SUB-shapes, each at its own
                            speed? Unequal lengths, extra baseline, a
                            tighter cut are all comparable. Not a verdict on
                            scale — see its section below.

Beside them (w2-b), the shape-based distance of k-Shape — `sbd`, `sbd_shift`,
`sbd_matrix`, `zero_pad_shift` — a clustering distance with its own note
below; it is not in `DISTANCE_REGISTRY`.

`DISTANCE_REGISTRY` maps each name to its function, so a caller (ticket 41)
can look a distance up by the name recorded on an edge rather than storing
a callable.

Elastic distances (e.g. dynamic time warping) are explicitly out of scope
— see PIPELINE_PRD.md's "Distances" paragraph.
"""

import numpy as np

from Working.Detection.sax.csax_python.normal_cutlines import normal_cutlines
from Working.Detection.sax.csax_python.timeseries2symbol import timeseries2symbol

DISTANCE_SCALE_INVARIANT = "scale_invariant"
DISTANCE_SYMBOLIC = "symbolic_sax"
DISTANCE_NATIVE_LENGTH = "native_length"


def z_normalize(x):
    """z-normalise `x` to zero mean, unit variance. A constant span returns
    an all-zero array rather than dividing by zero.

    The constant test is `np.ptp(x) == 0`, not `std == 0`. A span of 4.2 mV
    repeated 256 times has a standard deviation of 8.9e-16 rather than 0 —
    `mean()` and `std()` accumulate rounding error that a real flat span
    cannot avoid — so the `std == 0` guard this function used to carry missed
    every constant span except an all-zero one, and divided the rounding dust
    by itself to return a full-amplitude unit-variance waveform of noise.
    `ptp` is a subtraction of two elements and is exact where the variance is
    not, so it recognises the flat span the docstring always claimed to.

    This matters beyond this function: a flat span reaching
    `scale_invariant_distance`, `Working.cross_channel`'s waveform
    correlation, or the drop-motif clustering vectors would otherwise be
    compared as though it had structure."""
    x = np.asarray(x, dtype=float).ravel()
    if x.size == 0 or np.ptp(x) == 0:
        return np.zeros_like(x)
    mu, sigma = x.mean(), x.std()
    if sigma == 0:
        return np.zeros_like(x)
    return (x - mu) / sigma


def resample_to_length(x, n):
    """Linearly resample `x` to `n` points spanning its original extent —
    the step that makes two spans of different sample count comparable
    before a scale-invariant distance."""
    x = np.asarray(x, dtype=float).ravel()
    if len(x) == n:
        return x.copy()
    old_idx = np.linspace(0.0, 1.0, len(x))
    new_idx = np.linspace(0.0, 1.0, n)
    return np.interp(new_idx, old_idx, x)


def scale_invariant_distance(x1, x2, n_samples=None):
    """Resample both spans to a common length, z-normalise, Euclidean.

    `n_samples` defaults to the longer of the two spans' native lengths,
    so no information is thrown away by downsampling the longer span.
    """
    x1 = np.asarray(x1, dtype=float).ravel()
    x2 = np.asarray(x2, dtype=float).ravel()
    if n_samples is None:
        n_samples = max(len(x1), len(x2))
    r1 = z_normalize(resample_to_length(x1, n_samples))
    r2 = z_normalize(resample_to_length(x2, n_samples))
    return float(np.linalg.norm(r1 - r2))


def native_length_distance(x1, x2):
    """z-normalised Euclidean at native length — the unnormalised control.

    No resampling: the two spans are compared sample-for-sample from their
    start, truncated to the shorter span's length. A pair identical in
    shape but differing in duration is therefore large under this
    distance, unlike `scale_invariant_distance`.
    """
    x1 = np.asarray(x1, dtype=float).ravel()
    x2 = np.asarray(x2, dtype=float).ravel()
    n = min(len(x1), len(x2))
    r1 = z_normalize(x1[:n])
    r2 = z_normalize(x2[:n])
    return float(np.linalg.norm(r1 - r2))


def _sax_symbols(x, word_length, cutlines):
    """One span's 0-based SAX symbol string at a fixed word length, via
    the existing SAX ports: `timeseries2symbol` z-normalises and
    PAA-reduces the whole span to `word_length` symbols in one call
    (N=len(x): a single window spanning the whole span; NR_opt=1: no
    numerosity reduction, so the one window is always recorded)."""
    x = np.asarray(x, dtype=float).ravel()
    symbols, _ = timeseries2symbol(x, len(x), word_length, cutlines,
                                    normalize=True, NR_opt=1)
    return symbols[0] - 1  # 1-based -> 0-based


def _mindist_cell_table(cutlines, alphabet_size):
    """Symbol-to-symbol MINDIST lookup: 0 for adjacent-or-equal symbols
    (|r-c|<=1), otherwise the gap between the breakpoints separating
    them — the classic SAX distance table (Lin, Keogh, Lonardi & Chiu,
    2003), built from the same `cutlines` used to quantise both spans."""
    table = np.zeros((alphabet_size, alphabet_size))
    for r in range(alphabet_size):
        for c in range(alphabet_size):
            if abs(r - c) <= 1:
                continue
            lo, hi = (r, c) if r < c else (c, r)
            table[r, c] = cutlines[hi - 1] - cutlines[lo]
    return table


def symbolic_distance(x1, x2, word_length, alphabet_size=10):
    """SAX minimum-distance (MINDIST) between two spans' symbol strings at
    a fixed word length. Scale-invariant by construction: piecewise
    aggregation folds each span's own duration into the same word length
    before comparison, so no separate resampling step is needed.
    """
    cutlines = normal_cutlines(alphabet_size)
    s1 = _sax_symbols(x1, word_length, cutlines)
    s2 = _sax_symbols(x2, word_length, cutlines)
    table = _mindist_cell_table(cutlines, alphabet_size)
    cell_dists = table[s1, s2]
    return float(np.sqrt(np.sum(cell_dists ** 2)))


# --------------------------------------------------------------------------
# MPdist — shared sub-shapes at native speed (w3-d)
# --------------------------------------------------------------------------
#
# Gharghabi S, Imani S, Bagnall A, Darvishzadeh A, Keogh E (2018) Matrix
# Profile XII: MPdist. ICDM 2018, DOI 10.1109/ICDM.2018.00119.
#
# In plain words: slide a short window (the sub-length s) along both members;
# for every piece of one, find its closest piece anywhere in the other (each
# piece z-normalised, so only its shape counts); pool those closest distances
# from both directions and read one low order statistic of the pool. Two
# members are close when enough of their pieces have a close partner in the
# other — wherever it sits, so extra baseline, a tighter cut or a different
# total length do not count against them. It answers "do these share their
# sub-shapes?", which neither the scale-invariant distance (stretch both to one
# length) nor the native-length control (compare from the start) does. It does
# NOT answer "is one a time-stretched copy of the other": a piece of a 0.8x
# copy is itself squeezed, and a smooth shape's squeezed piece still matches
# some piece of the original (measured below).
#
# The algorithm, as implemented
# -----------------------------
# 1. Each member is checked and standardised once by its own mean and standard
#    deviation over its finite samples (exact: every distance below is
#    z-normalised per piece; this only keeps stumpy's running dot products well
#    conditioned on a volt-scale member with an offset). Refused, in words
#    (`MPdistRefused`): a member more than half NaN; a flat member; a shorter
#    member under 2 x MPDIST_MIN_SUB_LENGTH samples.
# 2. s = `snippets.sub_length(shorter member's length, sub_frac)` =
#    min(ceil(sub_frac x n), n) — the same rule, the same function, as
#    `catalogue.snippets`, so "the sub-length" means one thing in both blocks.
# 3. P_AB = each piece of A's distance to its nearest piece of B, P_BA the
#    reverse — what `stumpy.mpdist` computes with two AB-joins
#    (`core._compute_P_ABBA`). Two engines give the same numbers (pinned):
#    **dense** — every piece z-normalised as a row, one matrix of
#    piece-to-piece correlations r, d = sqrt(2 s (1 - r)), row and column
#    maxima — for members up to `MPDIST_DENSE_MAX_WORK`; **stumpy** —
#    `stumpy.stump(T_A, s, T_B, ignore_trivial=False)` both ways, above it.
# 4. **Adaptation: pieces with no shape are left out of the pool.** A piece that
#    touches a NaN (stumpy already scores it infinite) or is flat (constant) has
#    no shape, so its own entry is dropped. Why: stumpy scores two flat pieces 0
#    apart, so two different shapes on long noise-free flat baselines read as
#    IDENTICAL under plain `stumpy.mpdist` (pinned in the tests); and an
#    infinite entry makes stumpy quietly read a lower order statistic. Nor is a
#    flat piece anyone's PARTNER: stumpy gives a shaped piece against a flat one
#    the distance sqrt(s) (0.71 on the footing below — "half correlated", which
#    it is not), so a piece whose nearest partner came back flat is re-measured
#    against the other member's shaped pieces alone (`stumpy.mass`). Real
#    recordings rarely hold an exactly constant piece; noise-free synthetic
#    baselines, a clipped ADC or a held value do.
# 5. k = min(ceil(percentage x n_eff), pool size - 1), where n_eff is the two
#    lengths less the pieces left out; the value is the k-th smallest of the
#    pool (0-based) — stumpy's rule, which it reduces to exactly when nothing
#    is left out. `percentage` = 0.05 (the paper's 5 %, stumpy's default) reads
#    the distance below which about one in twenty of the pooled closest-piece
#    distances fall: two members are close when about 5 % of their pieces have
#    a close partner. NOT stumpy.snippets' `percentage` (that one sets s).
# 6. **The footing**: value = raw / sqrt(2 s). For z-normalised pieces
#    raw = sqrt(2 s (1 - r)), so the value is sqrt(1 - r) of the piece pair it
#    reads: 0 for an identical sub-shape, 1 for an uncorrelated one, sqrt(2)
#    the hard maximum (a mirror). It is on no length's footing: it is not
#    comparable with the other three distances' numbers, nor with a seed run's
#    cut, only with itself and with its null (`mpdist_null`).
#
# Why not `stumpy.mpdist` itself, or the snippets kernel: `stumpy.mpdist` has
# no way to leave a piece out (step 4) and its pool selection is private; its
# pairwise form does NOT hold the j x n matrix per piece W2-D measured (that is
# `_mpdist_vect`, the snippets path) — an AB-join is O(n_A n_B) time and O(n)
# memory — but `stumpy.stump` is numba-compiled without a cache: its first call
# in a fresh process took 40-56 s here (measured twice, machine under load),
# and every later call has a ~6 ms parallel-launch floor (12 ms a pair). The
# dense engine is plain numpy: no compile, ~3-4 ms a pair at 60-300 samples. So
# the first *Add N matches* in a bridge process pays no compile unless a pair
# is past the dense budget (members longer than ~15 min at 1 Hz). `snippets.mpdist_profiles` computes a piece
# against every position of a whole series (a profile), not one number
# between two members; deriving the pair from it would mean pretending one
# member is "the series".
#
# The default sub-length, `sub_frac` = 0.5 of the shorter member, not
# snippets' 0.35 (the paper's 70 of 200 example): measured on synthetic pairs
# (300 samples, white noise sd 0.05 on a unit drop), 0.5 gave same-shape 0.16,
# 30 %-extra-baseline 0.16, drop vs square 0.39-0.40 (2.5x), and separated a
# 0.8x-squeezed ringing shape (0.39 vs 0.11); 0.35 left the square at
# 0.26-0.28 (1.9x) and the squeezed ringing shape at 0.26. At 0.5 the shorter
# member always holds two whole sub-pieces, so 0.5 is also the ceiling.
# `MPDIST_MIN_SUB_LENGTH` = 8 is a placeholder floor (stumpy needs 3; a
# z-normalised piece of fewer points is a handful of numbers): at s = 10
# (20-sample members) the separation still held — same 0.15, square 0.35,
# AR(1) phi 0.99 null median 0.49.
#
# Where coloured noise sits on the footing (measured, 300 samples, sub_frac
# 0.5): AR(1) phi 0.99 pairs median 0.48-0.57 (5th percentile 0.29-0.36), a
# detrended random walk 0.48-0.53 (0.31-0.37), white noise 0.85-0.92; a shared
# shape at white-noise sd 0.05: 0.13-0.17; at sd 0.10: 0.28-0.31. A
# z-normalised, amplitude-blind distance gives smooth noise plenty of shared
# sub-shapes, so every value must be read beside its own null
# (`mpdist_null`). A quiet member against an active one is invisible to it.

DISTANCE_MPDIST = "mpdist"

#: The sub-length as a fraction of the SHORTER member (measured, see above).
MPDIST_SUB_FRAC = 0.5
#: Which order statistic of the pooled closest-piece distances is read — the
#: paper's 5 % and stumpy's default.
MPDIST_PERCENTAGE = 0.05
#: The shortest sub-length compared (a placeholder floor, see above); the
#: shorter member must hold two such pieces.
MPDIST_MIN_SUB_LENGTH = 8
#: The dense engine's budget, in multiply-adds (pieces of A x pieces of B x
#: sub-length): its matrix product is O(j_A j_B s) where stumpy's join is
#: O(j_A j_B), so dense wins only on short members. Measured (one pair, machine
#: under load): 300 samples dense 4.4 ms vs stumpy 16 ms; 1,200 samples dense
#: 52 ms vs stumpy 38 ms. 1e8 is two members of about 930 samples (15.5 min at
#: 1 Hz); its arrays then stay under ~90 MB whatever the longer member's length.
MPDIST_DENSE_MAX_WORK = 100_000_000
#: A member more than this share NaN is refused (`catalogue.snippets`' rule).
MPDIST_MAX_NAN_FRACTION = 0.5
#: The null: the Library's shared trend-kept surrogates, NULL_DRAWS (5) draws
#: as `Working.library.coherence` does, and its placeholder 0.9 margin.
MPDIST_NULL_DRAWS = 5
MPDIST_NULL_MARGIN = 0.9

MPDIST_FOOTING = ("MPdist divided by sqrt(2 x sub-length): sqrt(1 - r) of the sub-piece pair it reads — 0 an "
                  "identical sub-shape, 1 an uncorrelated one, sqrt(2) a mirror. Not on any length's footing: "
                  "compare it only with other MPdist values and with its null, never with a seed run's cut.")

MPDIST_RULE = (
    "MPdist (Gharghabi et al. 2018): slide a piece half the shorter member long along both members, find each "
    "piece's closest piece in the other (z-normalised: shape only), pool both directions and read the value "
    "below which 5 % of the pool falls; flat pieces and pieces touching a gap are left out. " + MPDIST_FOOTING
    + " Null: the same distance between trend-kept phase-randomised surrogates of the two members (each "
    f"member's colour and cubic trend kept), {MPDIST_NULL_DRAWS} seeded draws; beyond_noise = value < "
    f"{MPDIST_NULL_MARGIN} x null_p05 (a placeholder margin). Measured on pure coloured-noise pairs (AR(1) "
    "phi 0.99, random walk), 10-20 % of single pairs are called beyond noise, so read it across a family's "
    "pairs, not pair by pair. Not a scale verdict: a squeezed copy of a smooth shape shares its sub-shapes "
    "with the original. Amplitude-blind: a quiet member and an active one are not told apart.")

#: The read-out's tooltip, worded so it cannot be read as a scale verdict.
MPDIST_TOOLTIP = (
    "Shared sub-shapes (MPdist): how closely short pieces of one member find matching pieces anywhere in the "
    "other, each at its own speed. Small means they share sub-shapes — extra baseline or a tighter cut does "
    "not count against them. It is NOT a scale verdict: a time-squeezed copy of a smooth shape still shares "
    "its sub-shapes with the original, so a small value does not say the motif survives rescaling — read the "
    "scale-invariant distance against the native-length control for that. 0 = identical sub-shapes, 1 = no "
    "more alike than unrelated pieces; read it beside its noise null.")


class MPdistRefused(ValueError):
    """MPdist cannot compare these two members; the message says why in
    words. Raised rather than returning 0 (which would read "identical") or
    NaN (which would read "missing")."""


def _mpdist_member(x, which):
    """`(standardised member, nan mask)`, or MPdistRefused in words."""
    x = np.asarray(x, dtype=float).ravel()
    n = len(x)
    if n == 0:
        raise MPdistRefused(f"member {which} is empty: there is nothing to compare")
    bad = ~np.isfinite(x)
    if bad.mean() > MPDIST_MAX_NAN_FRACTION:
        raise MPdistRefused(
            f"member {which} is {100.0 * bad.mean():.0f} % NaN (gaps in the recording): MPdist compares only "
            f"members at most {100.0 * MPDIST_MAX_NAN_FRACTION:.0f} % gap")
    fin = x[~bad]
    if np.ptp(fin) == 0:
        raise MPdistRefused(f"member {which} is flat (every finite sample is {fin[0]:.6g}): "
                            "it has no sub-shape to share")
    z = np.full(n, np.nan)
    z[~bad] = (fin - fin.mean()) / fin.std()
    return z, bad


def _piece_masks(z, bad, s):
    """`(touches a gap, flat)` per length-s piece of a standardised member."""
    from numpy.lib.stride_tricks import sliding_window_view

    gap = sliding_window_view(bad, s).any(axis=1)
    flat = np.ptp(sliding_window_view(np.where(bad, 0.0, z), s), axis=1) == 0
    return gap, flat & ~gap


def _z_pieces(z, s, shaped):
    """Every length-s piece of `z`, z-normalised, as rows; a piece that is not
    `shaped` (flat, or touching a gap) is a row of zeros (never read, never a
    partner — the caller masks it)."""
    from numpy.lib.stride_tricks import sliding_window_view

    W = sliding_window_view(np.where(np.isfinite(z), z, 0.0), s)
    mu = W.mean(axis=1)
    sd = W.std(axis=1)
    sd = np.where(shaped & (sd > 0), sd, 1.0)
    P = (W - mu[:, None]) / sd[:, None]
    P[~shaped] = 0.0
    return P


def _joins_dense(za, zb, s, keep_a, keep_b):
    """`(P_AB, P_BA)` from one matrix of piece-to-piece correlations: for
    z-normalised pieces d = sqrt(2 s (1 - r)), so each piece's nearest partner
    is its most correlated one among the other member's shaped pieces. Exact
    (agrees with `stumpy.stump` to rounding, pinned in the tests), no numba
    compile, and a few milliseconds for members of minutes."""
    A = _z_pieces(za, s, keep_a)
    B = _z_pieces(zb, s, keep_b)
    R = (A @ B.T) / float(s)
    R[:, ~keep_b] = -np.inf
    r_ab = R.max(axis=1)
    R[~keep_a, :] = -np.inf
    r_ba = R.max(axis=0)
    d = lambda r: np.sqrt(np.clip(2.0 * s * (1.0 - np.clip(r, -1.0, 1.0)), 0.0, None))  # noqa: E731
    return d(r_ab), d(r_ba)


def _join_without_flat_partners(stumpy, ta, tb, s, flat_a, flat_b, keep_a):
    """Each piece of `ta`'s distance to its nearest piece of `tb` (an AB-join,
    `stumpy.stump(ta, s, tb, ignore_trivial=False)`), with the flat pieces of
    `tb` never a partner: stumpy gives a shaped piece against a flat one the
    distance sqrt(s), so a piece whose nearest partner came back flat is
    re-measured against `tb`'s non-flat pieces alone (`stumpy.mass`). Only
    pieces of `ta` that are read (`keep_a`) are re-measured."""
    out = stumpy.stump(ta, s, tb, ignore_trivial=False, T_A_subseq_isconstant=flat_a,
                       T_B_subseq_isconstant=flat_b)
    p = np.asarray(out[:, 0], dtype=float)
    if flat_b.any():
        nn = np.asarray(out[:, 1], dtype=np.int64)
        redo = np.flatnonzero(keep_a & (nn >= 0) & flat_b[np.clip(nn, 0, len(flat_b) - 1)])
        for i in redo:
            prof = np.asarray(stumpy.mass(ta[i:i + s], tb, T_subseq_isconstant=flat_b), dtype=float)
            prof[flat_b] = np.inf
            p[i] = float(np.min(prof))
    return p


def mpdist_detail(x1, x2, sub_frac=MPDIST_SUB_FRAC, percentage=MPDIST_PERCENTAGE, engine="auto"):
    """MPdist between two members with everything a page might print:
    `value` (on the unit footing), `raw` (stumpy's own scale), `sub_length`,
    `k`, `pool` (entries the order statistic was read from), `excluded_flat`,
    `excluded_gap`, `sub_frac`, `percentage`, `footing`, `engine`. Raises
    `MPdistRefused` (in words) for a pair it cannot compare and ValueError for
    a parameter out of range. See the section comment for the algorithm.

    `engine`: "auto" (dense up to `MPDIST_DENSE_MAX_WORK`, stumpy above),
    "dense" or "stumpy" — the same numbers, two costs (tests pin agreement)."""
    import math

    from Working.Detection.matrix_profiling.snippets import sub_length

    if engine not in ("auto", "dense", "stumpy"):
        raise ValueError(f"engine={engine!r} must be 'auto', 'dense' or 'stumpy'")

    sub_frac = float(sub_frac)
    percentage = float(percentage)
    if not 0.0 < sub_frac <= 0.5:
        raise ValueError(f"sub_frac={sub_frac} must be in (0, 0.5]: the shorter member must hold two sub-pieces")
    if not 0.0 < percentage <= 1.0:
        raise ValueError(f"percentage={percentage} must be in (0, 1]")
    za, bad_a = _mpdist_member(x1, "a")
    zb, bad_b = _mpdist_member(x2, "b")
    n_a, n_b = len(za), len(zb)
    shorter = min(n_a, n_b)
    s = sub_length(shorter, sub_frac)
    need = 2 * MPDIST_MIN_SUB_LENGTH
    if shorter < need or s < MPDIST_MIN_SUB_LENGTH:
        raise MPdistRefused(
            f"too short: the shorter member is {shorter} samples; MPdist needs at least {need} (two sub-pieces "
            f"of {MPDIST_MIN_SUB_LENGTH}) and a sub-length of {MPDIST_MIN_SUB_LENGTH} (here {s} = "
            f"{sub_frac} x {shorter})")
    gap_a, flat_a = _piece_masks(za, bad_a, s)
    gap_b, flat_b = _piece_masks(zb, bad_b, s)
    keep_a, keep_b = ~(gap_a | flat_a), ~(gap_b | flat_b)
    for which, keep in (("a", keep_a), ("b", keep_b)):
        if not keep.any():
            raise MPdistRefused(f"member {which} has no sub-piece of {s} samples with a shape: every one is flat "
                                "or touches a gap")
    j_a, j_b = len(keep_a), len(keep_b)
    dense = j_a * j_b * s <= MPDIST_DENSE_MAX_WORK if engine == "auto" else engine == "dense"
    if dense:
        p_ab, p_ba = _joins_dense(za, zb, s, keep_a, keep_b)
    else:
        import stumpy

        p_ab = _join_without_flat_partners(stumpy, za, zb, s, flat_a, flat_b, keep_a)
        p_ba = _join_without_flat_partners(stumpy, zb, za, s, flat_b, flat_a, keep_b)
    pool = np.concatenate([p_ab[keep_a], p_ba[keep_b]])
    pool = pool[np.isfinite(pool)]
    left_out = int((~keep_a).sum() + (~keep_b).sum())
    n_eff = n_a + n_b - left_out
    k = int(min(math.ceil(percentage * n_eff), len(pool) - 1))
    raw = float(np.partition(pool, k)[k])
    return {"value": raw / math.sqrt(2.0 * s), "raw": raw, "sub_length": int(s), "k": k, "pool": int(len(pool)),
            "excluded_flat": int(flat_a.sum() + flat_b.sum()), "excluded_gap": int(gap_a.sum() + gap_b.sum()),
            "sub_frac": sub_frac, "percentage": percentage, "footing": MPDIST_FOOTING,
            "engine": "dense" if dense else "stumpy"}


def mpdist_distance(x1, x2, sub_frac=MPDIST_SUB_FRAC, percentage=MPDIST_PERCENTAGE):
    """MPdist between two members on the unit footing (`MPDIST_FOOTING`):
    0 for identical sub-shapes, 1 for uncorrelated ones. Symmetric. Raises
    `MPdistRefused` in words for a member mostly NaN, flat, or too short."""
    return mpdist_detail(x1, x2, sub_frac=sub_frac, percentage=percentage)["value"]


def mpdist_null(x1, x2, draws=MPDIST_NULL_DRAWS, seed=0, sub_frac=MPDIST_SUB_FRAC,
                percentage=MPDIST_PERCENTAGE):
    """The value beside its noise: MPdist between trend-kept phase-randomised
    surrogates of the two members (`Working.library.grouping.methods.kshape.
    trend_kept_surrogates`, the Library's shared surrogate — each member's
    colour and cubic trend kept, its shape destroyed), `draws` seeded draws.

    Returns `{value, null_median, null_p05, draws, beyond_noise, margin,
    rule}`; `beyond_noise` = value < MPDIST_NULL_MARGIN x null_p05. A
    member's gaps are filled by straight lines for the surrogate only and put
    back as NaN, so the surrogate leaves out the same pieces. Blind spot (the
    surrogate's, `coherence.SMOOTH_CAVEAT`): a smooth member that is one slow
    curve keeps that curve in its own surrogate."""
    from Working.Detection.matrix_profiling.snippets import fill_nan
    from Working.library.grouping.methods.kshape import null_rng, trend_kept_surrogates

    value = mpdist_distance(x1, x2, sub_frac=sub_frac, percentage=percentage)
    filled = [fill_nan(np.asarray(x, dtype=float).ravel()) for x in (x1, x2)]
    rng = null_rng(seed, 41)
    null = []
    for _ in range(int(draws)):
        sur = []
        for x, bad in filled:
            y = trend_kept_surrogates(x[None, :], rng)[0]
            y[bad] = np.nan
            sur.append(y)
        null.append(mpdist_distance(sur[0], sur[1], sub_frac=sub_frac, percentage=percentage))
    p05 = float(np.percentile(null, 5))
    return {"value": float(value), "null_median": float(np.median(null)), "null_p05": p05,
            "draws": int(draws), "beyond_noise": bool(value < MPDIST_NULL_MARGIN * p05),
            "margin": MPDIST_NULL_MARGIN, "rule": MPDIST_RULE}


DISTANCE_REGISTRY = {
    DISTANCE_SCALE_INVARIANT: scale_invariant_distance,
    DISTANCE_SYMBOLIC: symbolic_distance,
    DISTANCE_NATIVE_LENGTH: native_length_distance,
    DISTANCE_MPDIST: mpdist_distance,
}


# --------------------------------------------------------------------------
# The shape-based distance (SBD) of k-Shape (w2-b)
# --------------------------------------------------------------------------
#
# Paparrizos & Gravano 2015 (SIGMOD), eq. 9:
#
#     SBD(x, y) = 1 - max_w  CC_w(x, y) / sqrt(R0(x, x) * R0(y, y))
#
# over every shift w, the shifts ZERO-PADDED (eq. 5) rather than cyclic, the
# cross-correlation computed through FFTs padded to the next power of two
# >= 2m - 1 (Alg. 1). SBD lies in [0, 2]: 0 for a copy at its best shift, 2 for
# an input whose every shift anti-correlates. The Library's methods report it
# divided by 2 so it sits on the grouping editor's [0, 1] cut scale beside
# Ward's normalised distance (`Working.library.grouping.methods.ward`).
#
# It is NOT in `DISTANCE_REGISTRY`: that registry names the three distances an
# imported `motif_edge` may record (`Pipelines/import_drop_motifs`), and SBD is
# a clustering distance, not an edge distance anyone records yet.
#
# Why not reuse `Working.cross_channel.cross_correlate`: it is one pair at a
# time through `scipy.signal.correlate`, it resamples the two inputs to a
# common length first (SBD compares unequal lengths as they are), and it
# reports a correlation per lag rather than the best shift's sign convention a
# caller needs to align a member. On two z-normalised spans of one length its
# peak IS SBD's peak, and `tests/test_sbd.py` pins that agreement. aeon's
# `sbd_pairwise_distance` is not reused either: it calls scipy once per pair
# from numba's object mode, which at 3,603 x 3,603 pairs is minutes, not
# seconds, and it returns no shifts.
#
# Shift convention, used by every function below: `shift = k` means
# `zero_pad_shift(b, k)` (b moved RIGHT by k, zeros in behind) is the best match
# to `a`, i.e. a[t] ~ b[t - k]. That is the lag k maximising
# R_k(a, b) = sum_l a[l + k] * b[l].
#
# A flat input (zero norm after z-normalisation) has no shape: against a span
# with shape it scores 1.0 (no correlation at any shift), and two flat inputs
# score 0.0 (identical). Defined rather than NaN, so one flat member cannot
# poison a whole distance matrix.

DISTANCE_SBD = "sbd"

# The matrix is built in row blocks so that a block's working arrays stay near
# this many bytes (the FFT engine's block is rows x columns x FFT length).
SBD_BLOCK_BYTES = 64 * 1024 * 1024

# Two engines compute the same zero-padded cross-correlation maximum for the
# matrix. `"fft"` is Alg. 1's: batched FFTs padded to the next power of two
# >= 2m - 1, O(n^2 m log m) element work in numpy. `"lags"` is the same sum
# R_k = X[:, k:] @ Y[:, :m-k].T taken one lag at a time as a matrix product,
# O(n^2 m^2) flops but in BLAS. Measured on this machine (n = 800, m = 256,
# under load from other jobs): fft 10.5 s, lags 3.7 s, agreeing to 4e-13. So
# `"auto"` uses lags up to this length and the FFT above it, where m^2 loses —
# except against a handful of rows (k-Shape's n rows x k centres), where the
# skinny products waste BLAS and the FFT wins (3,603 x 6: fft 0.20 s, lags 0.31 s).
SBD_LAGS_MAX_LENGTH = 512
SBD_FFT_FEW_ROWS = 64


def _next_pow2(n):
    """The smallest power of two >= n (n >= 1)."""
    return 1 << max(0, int(n) - 1).bit_length()


def zero_pad_shift(x, k):
    """`x` moved by `k` samples — right for k > 0, left for k < 0 — with zeros
    filling what was vacated. Never wraps: a fungal event does not come round
    again at the other end of its window."""
    x = np.asarray(x, dtype=float).ravel()
    out = np.zeros_like(x)
    m = x.size
    k = int(k)
    if abs(k) >= m:
        return out
    if k >= 0:
        out[k:] = x[:m - k]
    else:
        out[:m + k] = x[-k:]
    return out


def _sbd_input(x, z_normalise):
    x = np.asarray(x, dtype=float).ravel()
    if x.size == 0:
        raise ValueError("SBD needs two non-empty inputs.")
    return z_normalize(x) if z_normalise else x


def sbd_shift(a, b, *, z_normalise=True):
    """`(distance, shift)`: the shape-based distance of `a` and `b` in [0, 2]
    and the shift that best aligns `b` to `a` (module note above). The two
    inputs may differ in length. `z_normalise=True` (the paper's precondition,
    and the default) makes the distance blind to offset and scale."""
    a = _sbd_input(a, z_normalise)
    b = _sbd_input(b, z_normalise)
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return (0.0 if na == nb else 1.0), 0
    nfft = _next_pow2(a.size + b.size - 1)
    cc = np.fft.irfft(np.fft.rfft(a, nfft) * np.conj(np.fft.rfft(b, nfft)), nfft)
    # lags -(len(b) - 1) .. -1 live at the end of the circular result, 0 .. len(a) - 1 at its start
    values = np.concatenate([cc[nfft - (b.size - 1):] if b.size > 1 else cc[:0], cc[:a.size]])
    lags = np.arange(-(b.size - 1), a.size)
    best = int(np.argmax(values))
    distance = 1.0 - values[best] / (na * nb)
    return float(min(2.0, max(0.0, distance))), int(lags[best])


def sbd(a, b, *, z_normalise=True):
    """The shape-based distance of `a` and `b`, in [0, 2] (`sbd_shift`)."""
    return sbd_shift(a, b, z_normalise=z_normalise)[0]


def _sbd_rows(X, z_normalise):
    X = np.asarray(X, dtype=np.float64)
    if X.ndim != 2 or X.shape[1] == 0:
        raise ValueError("sbd_matrix needs a 2-D array, one equal-length row per series.")
    if z_normalise:
        X = np.vstack([z_normalize(row) for row in X]) if X.shape[0] else X.copy()
    return X


def _finish_sbd(best, at, nx, ny):
    """Peak correlations -> distances in [0, 2], with the flat-input rule."""
    denom = nx[:, None] * ny[None, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        d = 1.0 - best / denom
    flat = denom == 0.0
    if flat.any():
        d[flat] = 1.0
        d[(nx[:, None] == 0.0) & (ny[None, :] == 0.0)] = 0.0
        if at is not None:
            at[flat] = 0
    np.clip(d, 0.0, 2.0, out=d)
    return d, at


def _peaks_by_lags(Xb, Y, return_shifts):
    """max_k R_k(x_i, y_j) (and its k) by one matrix product per lag. Lags are
    visited 0, +1, -1, +2, -2, ...; a negative lag replaces on a tie and a
    positive one only when strictly greater, which is exactly "the first
    maximum in ascending lag order" — the tie rule `sbd_shift` uses."""
    m = Xb.shape[1]
    best = Xb @ Y.T
    at = np.zeros(best.shape, dtype=np.int64) if return_shifts else None
    for k in range(1, m):
        pos = Xb[:, k:] @ Y[:, :m - k].T          # R_{+k}
        if return_shifts:
            better = pos > best
            at[better] = k
        np.maximum(best, pos, out=best)
        neg = Xb[:, :m - k] @ Y[:, k:].T          # R_{-k}
        if return_shifts:
            better = neg >= best
            at[better] = -k
        np.maximum(best, neg, out=best)
    return best, at


def _peaks_by_fft(FXb, FY, m, nfft, return_shifts):
    """max_k R_k(x_i, y_j) (and its k) from batched FFTs (Alg. 1)."""
    from scipy import fft as _fft
    cc = _fft.irfft(FXb[:, None, :] * np.conj(FY[None, :, :]), nfft, axis=2, workers=-1)
    # lag order -(m-1) .. m-1, the order `sbd_shift` searches, so ties break alike
    values = np.concatenate([cc[..., nfft - (m - 1):], cc[..., :m]], axis=2) if m > 1 else cc[..., :1]
    del cc
    if not return_shifts:
        return values.max(axis=2), None
    at = values.argmax(axis=2)
    best = np.take_along_axis(values, at[..., None], axis=2)[..., 0]
    return best, at - (m - 1)


def sbd_matrix(X, Y=None, *, z_normalise=True, return_shifts=False, method="auto",
               dtype=np.float64, block_bytes=SBD_BLOCK_BYTES):
    """The SBD between every row of `X` and every row of `Y` (of `X` itself
    when `Y` is None), as an `(n_x, n_y)` array in [0, 2]; with
    `return_shifts=True`, also the `(n_x, n_y)` integer shifts aligning each
    `Y` row to each `X` row (the convention of `sbd_shift`).

    Rows must share one length — resample first (`resample_to_length`), as
    the Library's methods do. Every shift is zero-padded, never cyclic.
    `method` picks the engine (`"auto"`, `"lags"`, `"fft"`; see
    `SBD_LAGS_MAX_LENGTH`) — both give the same numbers. For `X` against
    itself only the upper triangle is computed and mirrored (the shift
    mirrored with its sign flipped). Work is done in row blocks of about
    `block_bytes`, so memory beyond the answer stays bounded.

    `dtype=np.float32` computes the correlations in single precision — about
    twice as fast, and good to ~1e-6 on SBD's [0, 2] scale, which is what a
    clustering of thousands of members needs; the default stays double so
    the pair and the matrix agree to 1e-10. The answer is always float64.
    """
    X = _sbd_rows(X, z_normalise)
    symmetric = Y is None
    Y = X if symmetric else _sbd_rows(Y, z_normalise)
    if X.shape[1] != Y.shape[1]:
        raise ValueError(f"sbd_matrix needs rows of one length; got {X.shape[1]} and {Y.shape[1]}.")
    if method not in ("auto", "lags", "fft"):
        raise ValueError(f"sbd_matrix method must be auto, lags or fft; got {method!r}.")
    n, p, m = X.shape[0], Y.shape[0], X.shape[1]
    D = np.zeros((n, p))
    S = np.zeros((n, p), dtype=np.int64) if return_shifts else None
    if n == 0 or p == 0:
        return (D, S) if return_shifts else D
    if method == "auto":
        method = ("lags" if m <= SBD_LAGS_MAX_LENGTH and min(n, p) > SBD_FFT_FEW_ROWS
                  else "fft")

    nx = np.linalg.norm(X, axis=1)
    ny = nx if symmetric else np.linalg.norm(Y, axis=1)
    dtype = np.dtype(dtype)
    if dtype not in (np.dtype(np.float64), np.dtype(np.float32)):
        raise ValueError(f"sbd_matrix dtype must be float64 or float32; got {dtype}.")
    if dtype != np.float64:
        X = X.astype(dtype)
        Y = X if symmetric else Y.astype(dtype)
    if method == "fft":
        from scipy import fft as _fft
        nfft = _next_pow2(2 * m - 1)
        FX = _fft.rfft(X, nfft, axis=1)
        FY = FX if symmetric else _fft.rfft(Y, nfft, axis=1)
        per_row = p * nfft * 40          # complex product + real result + the lag-ordered copy
    else:
        per_row = p * 8 * 4              # best, two lag products, the shift
    rows_per_block = max(1, int(block_bytes) // max(1, per_row))

    for i0 in range(0, n, rows_per_block):
        i1 = min(n, i0 + rows_per_block)
        j0 = i0 if symmetric else 0
        if method == "fft":
            best, at = _peaks_by_fft(FX[i0:i1], FY[j0:], m, nfft, return_shifts)
        else:
            best, at = _peaks_by_lags(X[i0:i1], Y[j0:], return_shifts)
        d, at = _finish_sbd(best.astype(np.float64, copy=False), at, nx[i0:i1], ny[j0:])
        D[i0:i1, j0:] = d
        if return_shifts:
            S[i0:i1, j0:] = at
        if symmetric:
            D[j0:, i0:i1] = d.T
            # the block's own square holds both (i, j) and (j, i); keep the upper
            # triangle's value for both, so the matrix is exactly symmetric
            w = i1 - i0
            sq = d[:, :w]
            D[i0:i1, i0:i1] = np.triu(sq) + np.triu(sq, 1).T
            if return_shifts:
                S[j0:, i0:i1] = -at.T
                sq = at[:, :w]
                S[i0:i1, i0:i1] = np.triu(sq) - np.triu(sq, 1).T
    if symmetric:
        np.fill_diagonal(D, 0.0)
        if return_shifts:
            np.fill_diagonal(S, 0)
    return (D, S) if return_shifts else D
