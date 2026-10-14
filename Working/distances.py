"""
distances.py
==============
Three named ways to say two spans are the same shape (T35), each a named
constant rather than an anonymous callable so it can be recorded verbatim
on the `motif_edge` it produces (PIPELINE_PRD.md, "Distances"):

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


DISTANCE_REGISTRY = {
    DISTANCE_SCALE_INVARIANT: scale_invariant_distance,
    DISTANCE_SYMBOLIC: symbolic_distance,
    DISTANCE_NATIVE_LENGTH: native_length_distance,
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
