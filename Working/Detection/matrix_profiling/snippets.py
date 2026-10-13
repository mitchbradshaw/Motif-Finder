"""
snippets.py
===========
Time-series snippets (Imani S, Madrid F, Ding W, Crouter S, Keogh E (2018)
Matrix Profile XIII: time series snippets, ICBK 2018, DOI
10.1109/ICBK.2018.00058): the few typical pieces of a recording, and where each
one dominates.

In plain words: cut the recording into pieces of one length (an hour, say).
For every piece, slide it along the whole recording and write down how far it
is from every stretch it passes — a "distance profile". A piece that looks like
much of the recording has a profile that is low almost everywhere. Pick the
piece whose profile is lowest overall; then the piece that, together with the
first, lowers the combined minimum the most; and so on. Each chosen piece is a
**snippet**; every stretch of the recording belongs to the snippet it is
closest to (its **regime**), and a snippet's **fraction** is how much of the
recording it covers. Like the handful of thumbnail frames that best represent a
film, plus a bar under it showing which frame each scene is closest to.

The distance is **MPdist** (Gharghabi et al. 2018), not the plain Euclidean
distance: two pieces are close when enough of their *shorter sub-pieces*
(length `s`) have close matches in the other, wherever they sit. That is what
makes it robust to "spikes, warping, linear trends, dropouts, wandering
baseline" (the paper) — and **only if `s < m`**. stumpy's own default
`percentage=1.0` sets `s = m`, and MPdist then collapses to the z-normalised
Euclidean distance between whole pieces (primary-sources §13c). Here `s` is
`ceil(subseq_frac * m)`, default 0.35 — the paper's own example (sub-length 70
of 200).

The algorithm, as implemented
-----------------------------
1. **NaN (adaptation).** stumpy cannot score a sub-piece touching NaN (it gives
   it an infinite distance and pads the series with NaN itself). Every NaN is
   filled by straight-line interpolation between its finite neighbours (ends
   held flat) before anything is computed; a piece that is **more than half
   NaN** is then *not a candidate* snippet, is not counted in any area or
   fraction, and its window is labelled -1. Both counts go in the result.
2. **Global standardisation (adaptation, exact).** The series is shifted and
   scaled once by its own mean and standard deviation. Every distance below is
   z-normalised per sub-piece, so this changes no distance; it only keeps the
   running dot products well conditioned (a volt-scale recording with a large
   offset otherwise loses digits to cancellation).
3. **MPdist profiles** (paper Table II; stumpy 1.14.1 `snippets._get_all_profiles`
   and `mpdist._mpdist_vect`, BSD-3-Clause, Copyright 2019 TD Ameritrade — the
   rules are theirs, the kernel is rewritten). For each non-overlapping piece
   `S_i = T[i*m:(i+1)*m]` and each position `p` of the series: the distance
   matrix between the `j = m - s + 1` sub-pieces of `S_i` and those of
   `T[p:p+m]`; `P_ABBA` = each row's minimum followed by each column's minimum
   (2j values); MPdist = the `kth` smallest, `kth = min(ceil(mpdist_percentage
   * 2m), 2j - 1)` (stumpy's rule — 0.05 by default: the distance below which
   about one in twenty of the sub-piece matches fall). Self-matches are set to
   0, as stumpy does. **Why the kernel is rewritten:** stumpy builds the whole
   `j x (n - s + 1)` distance matrix for each piece in memory (1.6 GB per piece
   for 1-hour pieces on 24 h at 1 Hz, 4.8 GB on 72 h) and computes it with one
   FFT per sub-piece; one piece against a 10 000-sample stretch took ~30 s, so
   24 h would have taken hours. The rewrite streams the matrix column by column
   (the matrix-profile diagonal update
   `QT[r,c] = QT[r-1,c-1] - T[a+r-1]T[c-1] + T[a+r-1+s]T[c-1+s]`), holds two
   blocks of `j` columns at a time (row minima over j columns by van Herk /
   Gil-Werman), and runs the pieces in parallel under a memory budget; it
   equals stumpy's profiles to floating-point precision
   (`tests/test_snippets.py`) and ran 24 h at 1 Hz with 1-hour pieces in 24 s,
   72 h in 228 s, on this machine under load.
4. **Greedy selection** (paper Table I, stumpy `snippets`): `Q = inf`; for
   k = 1, 2, …: pick the candidate piece whose profile minimises
   `sum(min(D_i, Q))`, record that sum as `Area_k`, set `Q = min(Q, D_i)`.
   Selection is greedy, so one pass to `k_max + 1` gives every k's snippets and
   the whole areas curve. Positions whose centre falls in a mostly-NaN window
   are left out of every sum.
5. **How many (the knee).** `change_k = Area_{k-1} / Area_k - 1` for k = 2 …
   `k_max + 1` (the paper's measure: how much the k-th snippet lowered the area,
   relative). **The paper's rule** (§III.B): a small change_k means "adding the
   kth did not add much explanatory power; thus, we should use a value of k
   corresponding to a peak" — k = argmax change_k, and no k = 1 outcome (its
   change_1 is undefined). **Two adaptations, both this block's:**
   a. *Selection: the largest drop.* The knee is the k in 2 … `k_max` with the
      largest `change_k - change_{k+1}` (the last snippet that still helped a
      lot, followed by one that did not). Measured: on the three-regime set
      (seeds 0-3) the paper's peak rule gives k = 2 every time (change_2
      0.42-0.45 just above change_3 0.40-0.44 — two equally strong extra
      regimes), the largest drop gives the true 3.
   b. *Acceptance, relative to the curve's own tail, and k = 1.* The knee is
      kept only if `change_k >= c * median(change_{k+1} … change_{k_max+1})`,
      `c = max(KNEE_TAIL_RATIO, KNEE_TAIL_PER_SQRT_PIECE * sqrt(W))` for W
      pieces; otherwise k = 1 (no snippet after the first stood out from the
      ones that followed — no evidence of more than one kind of behaviour). It
      replaced an absolute floor (change_k >= 0.25), because on noise change_k
      shrinks with W (each added snippet removes about 1/W of the area): the
      floor called 12 h of detrended random walk two kinds of behaviour in
      half the runs and missed an 8 h regime in 120 h (change_2 0.14). The
      ratio of a noise curve's knee to its tail still grows with W, about as
      sqrt(W) — largest over 20-30 seeds of a detrended random walk: 1.7 at 12
      pieces, 2.3 at 24, 3.9 at 48, 4.4 at 72, 5.8 at 120 (AR(1) phi 0.999 and
      pink noise lower) — so c = 3 alone (the manager's placeholder, from the
      critic's sweep) let 6 of 30 random walks through at 48 h; the sqrt(W)
      term (0.65 * sqrt(W): 4.5 at 48, 5.5 at 72, 7.1 at 120) keeps them out,
      while the regimes measured 6.8-7.4 (three regimes, 48 pieces), 8.9-15
      (8-12 h in 72 h) and 8.1-14 (8-12 h in 120 h). Both constants are
      placeholders for the surrogate check on real recordings; the margin at
      120 pieces is thin (an 8 h regime at 8.1 against a cut of 7.1).
   An all-zero area (a constant signal) is k = 1, said so.
6. **Regimes.** Each position is owned by the selected snippet with the lowest
   profile there (ties to the earlier snippet — stumpy's rule); a snippet's
   fraction is the share of scored positions it owns (stumpy divides by all
   `n - m + 1`; here mostly-NaN windows' positions are left out of both).
7. **Window labels (adaptation).** A position `p` stands for the stretch
   `T[p:p+m]`, so it votes for the window that contains its centre
   `p + m // 2`; each window takes the snippet with most votes (ties to the
   lower label), 1 … k. A snippet's own window is always labelled by that
   snippet (its distance to itself is 0) — the exemplar is then always one of
   its label's windows; how many windows that overrode is counted.
8. **Run lengths.** A run is a maximal stretch of consecutive windows with one
   label (a -1 window ends a run and is not counted). Reported: the mean and
   median run length, the mean expected if the same labels were shuffled
   (`1 + (n - 1) * (1 - sum p_c^2)` runs for n windows with label shares
   `p_c`), and their ratio — 1 means "no more persistent than chance".

Where it breaks: a stretch whose behaviour changes faster than one piece is
averaged into whichever snippet it half-resembles; the pieces are cut at fixed
multiples of `m` from the first window, so a regime boundary inside a piece
splits that piece's vote. Detrend first: MPdist tolerates a trend *within* a
sub-piece, not a wandering level that changes what the sub-pieces look like.

Cost: the profiles are O(n²) in work (each of n/m pieces against every one of
n positions, `2j` values each) and O(n²/m) in memory. The peak
(`memory_peak`) is about twice the profiles (`n/m x n` floats, plus the
first-row dot products of the same size while the kernel runs) plus the
kernel's blocks (at most KERNEL_MEMORY_BUDGET): ~1.8 GB at 72 h with 1-hour
pieces at 1 Hz, ~3.0 GB at 7 days (critic measured 1.95 GB at 72 h). A run above MEMORY_LIMIT is refused.

No UI imports; numpy, numba and stumpy only.
"""

import math
import time

import numba
import numpy as np
from numba import njit, prange
from stumpy import core as _stumpy_core

#: the knee's acceptance (step 5b): change_k must reach c times the median of the
#: changes after it, c = max(KNEE_TAIL_RATIO, KNEE_TAIL_PER_SQRT_PIECE * sqrt(W)).
#: Placeholders, measured on synthetic sets only (see step 5b).
KNEE_TAIL_RATIO = 3.0
KNEE_TAIL_PER_SQRT_PIECE = 0.65

#: a window more than this NaN is not a candidate and is labelled -1 (step 1)
MAX_NAN_FRACTION = 0.5

#: memory the parallel kernel may hold at once (bytes), across threads
KERNEL_MEMORY_BUDGET = 1_500_000_000

#: a run whose memory peak (`memory_peak`) would pass this is refused (bytes)
MEMORY_LIMIT = 4_000_000_000


# ── the kernel ─────────────────────────────────────────────────────────────────

@njit(cache=True)
def _quickselect(a, kth):
    """The kth smallest of `a` (0-based), partially reordering `a` in place."""
    lo, hi = 0, a.shape[0] - 1
    while hi > lo:
        mid = (lo + hi) // 2
        # median of three as the pivot
        x, y, z = a[lo], a[mid], a[hi]
        if x < y:
            pivot = y if y < z else (z if x < z else x)
        else:
            pivot = x if x < z else (z if y < z else y)
        i, j = lo, hi
        while i <= j:
            while a[i] < pivot:
                i += 1
            while a[j] > pivot:
                j -= 1
            if i <= j:
                tmp = a[i]
                a[i] = a[j]
                a[j] = tmp
                i += 1
                j -= 1
        if kth <= j:
            hi = j
        elif kth >= i:
            lo = i
        else:
            return a[kth]
    return a[kth]


@njit(cache=True)
def _one_piece(T, a, s, j, kth, mu, inv_sig, iscon, qt_row0, qt_col0, out, blocks, G, colmin, col, buf):
    """MPdist of the piece T[a:a+m] (m = s + j - 1) against every position p
    of T (len(out) of them).

    The distance matrix between the piece's j sub-pieces (rows r) and T's
    sub-pieces (columns c) is streamed one column at a time and held in blocks
    of j columns aligned at multiples of j. For a position p the j columns
    p..p+j-1 span at most two blocks, so each row's minimum over them is
    min(suffix-min of the earlier block from p, prefix-min of the later block
    up to p+j-1) (van Herk / Gil-Werman). Arrays are [column, row] so every
    inner loop runs over contiguous rows; the prefix minimum is taken while
    filling, and the two block buffers alternate instead of being copied.
    """
    L = T.shape[0] - s + 1                  # columns
    P = out.shape[0]                        # positions (L - j + 1)
    sqrt_s = math.sqrt(s)
    for r in range(j):
        col[r] = qt_col0[r]                 # QT[:, 0]
    n_blocks = (L + j - 1) // j
    for b in range(n_blocks):
        cur = blocks[b % 2]
        Hprev = blocks[(b + 1) % 2]
        c0 = b * j
        lb = min(j, L - c0)
        for q in range(lb):
            c = c0 + q
            if c > 0:                       # step every diagonal one column on
                tc = T[c - 1]
                tcs = T[c - 1 + s]
                for r in range(j - 1, 0, -1):
                    col[r] = col[r - 1] - T[a + r - 1] * tc + T[a + r - 1 + s] * tcs
                col[0] = qt_row0[c]
            row = cur[q]
            if iscon[c]:
                for r in range(j):
                    row[r] = 0.0 if iscon[a + r] else sqrt_s
            else:
                mc = mu[c] * s
                isc = inv_sig[c] / s
                for r in range(j):
                    R = a + r
                    if iscon[R]:
                        row[r] = sqrt_s
                    else:
                        rho = (col[r] - mu[R] * mc) * inv_sig[R] * isc
                        if rho > 1.0:
                            rho = 1.0
                        row[r] = math.sqrt(abs(2.0 * s * (1.0 - rho)))
            r_self = c - a
            if 0 <= r_self < j:             # a sub-piece against itself: 0 (stumpy's precision fix)
                row[r_self] = 0.0
            v = row[0]
            if q == 0:
                for r in range(j):
                    x0 = row[r]
                    G[0, r] = x0
                    if x0 < v:
                        v = x0
            else:
                gp = G[q - 1]
                gq = G[q]
                for r in range(j):
                    x0 = row[r]
                    y0 = gp[r]
                    gq[r] = x0 if x0 < y0 else y0
                    if x0 < v:
                        v = x0
            colmin[c] = v
        # the positions that start in the previous block are now complete
        if b > 0:
            for qq in range(j):
                p = c0 - j + qq
                if p >= P:
                    break
                hq = Hprev[qq]
                if qq == 0:
                    for r in range(j):
                        buf[r] = hq[r]
                else:
                    gq = G[qq - 1]
                    for r in range(j):
                        x0 = hq[r]
                        y0 = gq[r]
                        buf[r] = x0 if x0 < y0 else y0
                for r in range(j):
                    buf[j + r] = colmin[p + r]
                out[p] = _quickselect(buf, kth)
        # suffix minimum within the block, in place: it becomes the next block's Hprev
        for q in range(lb - 2, -1, -1):
            nxt = cur[q + 1]
            row = cur[q]
            for r in range(j):
                if nxt[r] < row[r]:
                    row[r] = nxt[r]
        # a position whose j columns are exactly this (last, full) block
        if b == n_blocks - 1 and c0 <= P - 1:
            for r in range(j):
                buf[r] = cur[0, r]
            for r in range(j):
                buf[j + r] = colmin[c0 + r]
            out[c0] = _quickselect(buf, kth)


@njit(parallel=True, cache=True)
def _all_pieces(T, piece_starts, s, j, kth, mu, inv_sig, iscon, qt_rows, qt_cols, D):
    W = piece_starts.shape[0]
    L = T.shape[0] - s + 1
    for i in prange(W):
        blocks = np.empty((2, j, j))
        G = np.empty((j, j))
        colmin = np.empty(L)
        col = np.empty(j)
        buf = np.empty(2 * j)
        _one_piece(T, piece_starts[i], s, j, kth, mu, inv_sig, iscon, qt_rows[i], qt_cols[i], D[i],
                   blocks, G, colmin, col, buf)


def _kth(m, j, mpdist_percentage):
    """stumpy's rule (`mpdist._mpdist_vect`): kth = min(ceil(pct * 2m), 2j - 1)."""
    pct = float(np.clip(mpdist_percentage, 0.0, 1.0))
    return int(min(math.ceil(pct * (2 * m)), 2 * j - 1))


def sub_length(m, subseq_frac):
    """MPdist's sub-length `s` = min(ceil(subseq_frac * m), m) — stumpy's
    `percentage` rule (`snippets._get_all_profiles`)."""
    return int(min(math.ceil(float(subseq_frac) * int(m)), int(m)))


def mpdist_profiles(T, m, s, mpdist_percentage=0.05, piece_starts=None):
    """MPdist profile of each non-overlapping piece `T[i*m:(i+1)*m]` (or of
    the pieces starting at `piece_starts`) against every position of `T`.

    Returns a `(n_pieces, len(T) - m + 1)` float array — stumpy's
    `snippets._get_all_profiles(T, m, s=s, mpdist_percentage=...)` (see the
    module docstring, step 3). `T` must be finite.
    """
    T = np.asarray(T, dtype=np.float64)
    n = T.shape[0]
    m, s = int(m), int(s)
    if not np.all(np.isfinite(T)):
        raise ValueError("mpdist_profiles needs a finite series; fill NaN first")
    if s < 3 or s > m:
        raise ValueError(f"sub-length s={s} must be between 3 and the piece length m={m}")
    if m > n // 2:
        raise ValueError(f"piece length m={m} is longer than half the series ({n} samples)")
    if piece_starts is None:
        piece_starts = np.arange(n // m, dtype=np.int64) * m
    piece_starts = np.asarray(piece_starts, dtype=np.int64)
    sd = float(np.std(T))
    T = (T - float(np.mean(T))) / (sd if sd > 0 else 1.0)
    mu, sig = _stumpy_core.compute_mean_std(T, s)
    iscon = np.asarray(_stumpy_core.process_isconstant(T, s, None), dtype=np.bool_)
    with np.errstate(divide="ignore"):
        inv_sig = np.where(sig > 0, 1.0 / np.where(sig > 0, sig, 1.0), 0.0)
    j = m - s + 1
    kth = _kth(m, j, mpdist_percentage)
    W = len(piece_starts)
    P = n - m + 1
    qt_rows = np.empty((W, n - s + 1))
    qt_cols = np.empty((W, j))
    for i, a in enumerate(piece_starts):
        qt_rows[i] = _stumpy_core.sliding_dot_product(T[a:a + s], T)
        qt_cols[i] = _stumpy_core.sliding_dot_product(T[0:s], T[a:a + m])
    D = np.empty((W, P))
    per_thread = 8 * (3 * j * j + (n - s + 1) + 3 * j)
    threads = max(1, min(numba.get_num_threads(), KERNEL_MEMORY_BUDGET // max(per_thread, 1), W))
    before = numba.get_num_threads()
    numba.set_num_threads(int(threads))
    try:
        _all_pieces(T, piece_starts, s, j, kth, mu, inv_sig, iscon, qt_rows, qt_cols, D)
    finally:
        numba.set_num_threads(before)
    return D


# ── selection, knee, regimes ───────────────────────────────────────────────────

def greedy_snippets(D, n_select, candidates=None, scored=None):
    """Paper Table I: pick `n_select` rows of `D` greedily.

    `candidates` (bool per row) limits which rows may be picked; `scored`
    (bool per column) limits which positions count in the areas. Returns
    `(chosen rows, areas)` where `areas[k-1]` is the area with k snippets.
    Works row by row on `D` itself (no copy, no rows x positions temporary):
    an unscored position starts with Q = 0, so it adds nothing to any area.
    """
    D = np.asarray(D, dtype=np.float64)
    W, P = D.shape
    cand = np.ones(W, dtype=bool) if candidates is None else np.asarray(candidates, dtype=bool)
    Q = np.full(P, np.inf)
    if scored is not None:
        Q[~np.asarray(scored, dtype=bool)] = 0.0
    tmp = np.empty(P)
    chosen, areas = [], []
    for _ in range(int(n_select)):
        a = np.full(W, np.inf)
        for i in range(W):
            if cand[i] and i not in chosen:
                np.minimum(D[i], Q, out=tmp)
                a[i] = tmp.sum()
        idx = int(np.argmin(a))
        if not np.isfinite(a[idx]):
            break
        chosen.append(idx)
        areas.append(float(a[idx]))
        np.minimum(Q, D[idx], out=Q)
    return chosen, areas


def change_curve(areas):
    """`change_k = Area_{k-1} / Area_k - 1` for k = 2 .. len(areas) (paper).
    Returned as `{k: change_k}`; an area of 0 gives inf (nan if both are 0)."""
    out = {}
    for k in range(2, len(areas) + 1):
        prev, cur = areas[k - 2], areas[k - 1]
        if cur > 0:
            out[k] = float(prev / cur - 1.0)
        else:
            out[k] = float("nan") if prev <= 0 else float("inf")
    return out


def knee_threshold(n_pieces=None):
    """The acceptance factor c of step 5b for `n_pieces` pieces."""
    if not n_pieces:
        return KNEE_TAIL_RATIO
    return float(max(KNEE_TAIL_RATIO, KNEE_TAIL_PER_SQRT_PIECE * math.sqrt(n_pieces)))


def knee_detail(changes, k_max, n_pieces=None, areas=None):
    """The knee rule (module docstring step 5). Returns a dict: `k`,
    `reason`, `candidate` (the largest-drop k), `ratio` (change_candidate /
    median of the changes after it) and `threshold` (c)."""
    c = knee_threshold(n_pieces)
    out = {"k": 1, "candidate": None, "ratio": None, "threshold": c}
    if areas is not None and len(areas) and areas[0] <= 0:
        out["reason"] = "constant signal: every distance is 0, so no snippet can explain more than another"
        return out
    best_k, best_drop = None, -np.inf
    for k in range(2, int(k_max) + 1):
        if k not in changes or (k + 1) not in changes:
            continue
        drop = changes[k] - changes[k + 1]
        if np.isfinite(drop) and drop > best_drop:
            best_k, best_drop = k, drop
    if best_k is None:
        out["reason"] = "too few snippets to read a knee"
        return out
    tail = [changes[j] for j in range(best_k + 1, int(k_max) + 2) if j in changes]
    med = float(np.median(tail))
    ratio = float(changes[best_k] / med) if med > 0 else float("inf")
    out.update(candidate=best_k, ratio=ratio)
    if ratio < c:
        out["reason"] = (f"no knee: the largest drop in change_k is at k={best_k}, but change_{best_k} = "
                         f"{changes[best_k]:.3f} is only {ratio:.1f}x the median {med:.3f} of the changes "
                         f"after it (needs {c:.1f}x) — no snippet after the first stood out")
        return out
    out["k"] = best_k
    out["reason"] = (f"knee at k={best_k}: change_{best_k} = {changes[best_k]:.3f}, "
                     f"change_{best_k + 1} = {changes[best_k + 1]:.3f} (largest drop); {ratio:.1f}x the "
                     f"median {med:.3f} of the changes after it (needs {c:.1f}x)")
    return out


def knee(changes, k_max, n_pieces=None):
    """`(k, reason)` of `knee_detail`."""
    d = knee_detail(changes, k_max, n_pieces)
    return d["k"], d["reason"]


def memory_peak(n, m, s, n_pieces=None):
    """Bytes a run holds at its peak: while the kernel runs, the profiles
    (`n/m x (n - m + 1)` floats), the first-row dot products (the same size)
    and the kernel's blocks (three `j x j` per thread, threads capped by
    KERNEL_MEMORY_BUDGET); the greedy afterwards holds the profiles alone."""
    n, m, s = int(n), int(m), int(s)
    W = int(n // m) if n_pieces is None else int(n_pieces)
    j = m - s + 1
    profiles = 8 * W * (n - m + 1)
    qt = 8 * W * (n - s + 1 + j)
    per_thread = 8 * (3 * j * j + (n - s + 1) + 3 * j)
    threads = max(1, min(numba.get_num_threads(), KERNEL_MEMORY_BUDGET // max(per_thread, 1), max(W, 1)))
    return int(profiles + qt + threads * per_thread)


def regime_owner(D_sel, scored=None):
    """For each position, the index (0-based, into `D_sel`'s rows) of the
    snippet with the lowest profile, ties to the earlier one; -1 where not
    scored."""
    owner = np.argmin(np.asarray(D_sel), axis=0).astype(np.int64)
    if scored is not None:
        owner[~np.asarray(scored, dtype=bool)] = -1
    return owner


def label_windows(owner, rel_starts, length, m, k):
    """Window labels 1..k from position owners (step 7); 0 = no vote."""
    P = len(owner)
    half = m // 2
    labels = np.zeros(len(rel_starts), dtype=np.int64)
    votes = np.zeros((len(rel_starts), k), dtype=np.int64)
    for wi, st in enumerate(np.asarray(rel_starts)):
        lo, hi = int(st), int(st) + int(length)
        # positions p whose centre p + m // 2 lies in [lo, hi)
        sel = owner[max(0, lo - half):max(0, min(P, hi - half))]
        sel = sel[sel >= 0]
        if len(sel):
            votes[wi] = np.bincount(sel, minlength=k)[:k]
    has = votes.sum(axis=1) > 0
    labels[has] = np.argmax(votes[has], axis=1) + 1
    return labels, votes


def run_lengths(labels):
    """Lengths of runs of one label over consecutive windows; -1 and 0 end a
    run and are not counted."""
    runs, cur, n = [], None, 0
    for lab in np.asarray(labels):
        lab = int(lab)
        if lab <= 0:
            if n:
                runs.append(n)
            cur, n = None, 0
            continue
        if lab == cur:
            n += 1
        else:
            if n:
                runs.append(n)
            cur, n = lab, 1
    if n:
        runs.append(n)
    return runs


def run_summary(labels):
    """Mean / median run length, and the mean expected for shuffled labels."""
    labels = np.asarray(labels)
    runs = run_lengths(labels)
    kept = labels[labels > 0]
    if not runs:
        return {"n_runs": 0, "mean": None, "median": None, "shuffled_mean": None, "ratio": None}
    n = len(kept)
    _, counts = np.unique(kept, return_counts=True)
    p = counts / n
    expected_runs = 1.0 + (n - 1) * (1.0 - float(np.sum(p ** 2)))
    shuffled_mean = n / expected_runs
    mean = float(np.mean(runs))
    return {"n_runs": len(runs), "mean": mean, "median": float(np.median(runs)),
            "shuffled_mean": float(shuffled_mean), "ratio": float(mean / shuffled_mean)}


# ── the whole method ───────────────────────────────────────────────────────────

def fill_nan(x):
    """Straight-line interpolation over NaN, ends held flat. Returns
    `(filled, nan_mask)`; raises if nothing is finite."""
    x = np.asarray(x, dtype=np.float64)
    bad = ~np.isfinite(x)
    if bad.all():
        raise ValueError("the span holds no finite sample (all NaN): nothing to summarise")
    if not bad.any():
        return x.copy(), bad
    idx = np.arange(len(x))
    out = x.copy()
    out[bad] = np.interp(idx[bad], idx[~bad], x[~bad])
    return out, bad


def find_snippets(x, rel_starts, length, k=0, k_max=6, subseq_frac=0.35, mpdist_percentage=0.05):
    """Snippets of `x` with pieces of `length` samples, labelling the windows
    starting at `rel_starts` (span-relative).

    Returns a dict (see the adapter for what each key means on the page).
    Raises ValueError, in words, when the input cannot be summarised.
    """
    t0 = time.perf_counter()
    x = np.asarray(x, dtype=np.float64)
    rel_starts = np.asarray(rel_starts, dtype=np.int64)
    m = int(length)
    k, k_max = int(k), int(k_max)
    if len(rel_starts) == 0:
        raise ValueError("the window set is empty: no pieces to summarise")
    if rel_starts.min() < 0 or rel_starts.max() + m > len(x):
        raise ValueError(
            f"the windows do not lie inside the span ({len(x)} samples): starts run "
            f"{int(rel_starts.min())}..{int(rel_starts.max())} with length {m}")
    order = np.sort(rel_starts)
    contiguous = bool(len(order) == 1 or np.all(np.diff(order) == m))
    lo = int(order[0])
    hi = int(order[-1]) + m if contiguous else len(x)
    if not contiguous:
        lo = 0
    seg = x[lo:hi]
    n = len(seg)
    if m > n // 2:
        raise ValueError(
            f"the piece is too long for the span: {m} samples per piece, but stumpy's limit is half "
            f"the series ({n // 2} of {n}). Shorten the windows or analyse a longer span.")
    s = sub_length(m, subseq_frac)
    if s < 3:
        raise ValueError(f"subseq_frac={subseq_frac:g} of a {m}-sample piece gives a sub-length of {s}; "
                         "MPdist needs at least 3 samples")
    filled, nan_mask = fill_nan(seg)
    n_pieces = n // m
    piece_starts = np.arange(n_pieces, dtype=np.int64) * m
    piece_nan = np.array([nan_mask[a:a + m].mean() for a in piece_starts])
    cand = piece_nan <= MAX_NAN_FRACTION
    if int(cand.sum()) < 2 * k_max:
        raise ValueError(
            f"too few pieces to choose from: {int(cand.sum())} usable piece(s) of {m} samples "
            f"({n_pieces - int(cand.sum())} more than half NaN), but k_max={k_max} needs at least "
            f"{2 * k_max}. Lower k_max, shorten the windows or analyse a longer span.")
    if k > k_max:
        raise ValueError(f"k={k} is above k_max={k_max}")
    need = memory_peak(n, m, s, n_pieces)
    if need > MEMORY_LIMIT:
        raise ValueError(
            f"the span is too long for {m}-sample pieces: the run's memory peak would be "
            f"{need / 1e9:.1f} GB (the profiles, {n_pieces} pieces x {n - m + 1} positions, twice over "
            f"while the kernel runs, plus its blocks; the limit is {MEMORY_LIMIT / 1e9:.0f} GB). "
            "Use longer pieces or a shorter span.")

    D = mpdist_profiles(filled, m, s, mpdist_percentage, piece_starts=piece_starts)
    P = D.shape[1]
    # a position is scored unless its centre lies in a mostly-NaN piece
    centre_piece = np.minimum((np.arange(P) + m // 2) // m, n_pieces - 1)
    scored = cand[centre_piece]
    chosen, areas = greedy_snippets(D, k_max + 1, candidates=cand, scored=scored)
    changes = change_curve(areas)
    if k == 0:
        kd = knee_detail(changes, k_max, n_pieces=int(cand.sum()), areas=areas)
        k_used, reason = kd["k"], kd["reason"]
        chosen_by = "knee"
    else:
        kd = knee_detail(changes, k_max, n_pieces=int(cand.sum()), areas=areas)
        k_used, reason, chosen_by = k, f"k={k} set by hand", "parameter"
    sel = chosen[:k_used]
    owner = regime_owner(D[sel], scored)
    n_scored = int(scored.sum())
    fractions = [float(np.sum(owner == c) / n_scored) for c in range(k_used)]

    # windows: position owners -> window labels (seg-relative starts)
    w_starts = rel_starts - lo
    labels, votes = label_windows(owner, w_starts, m, m, k_used)
    w_nan = np.array([nan_mask[a:a + m].mean() for a in w_starts])
    nan_windows = w_nan > MAX_NAN_FRACTION
    labels[nan_windows] = -1
    labels[labels == 0] = -1
    exemplar_windows, relabelled = {}, 0
    for c, row in enumerate(sel):
        a = int(piece_starts[row])
        if contiguous:
            wi = int(np.flatnonzero(w_starts == a)[0])
        else:
            # the window containing the snippet's centre with that label, else the label's nearest window
            mine = np.flatnonzero(labels == c + 1)
            centre = a + m // 2
            inside = [int(w) for w in mine if w_starts[w] <= centre < w_starts[w] + m]
            if inside:
                wi = inside[0]
            elif len(mine):
                wi = int(mine[np.argmin(np.abs(w_starts[mine] - a))])
            else:
                wi = int(np.argmin(np.abs(w_starts - a)))
        if labels[wi] != c + 1:
            labels[wi] = c + 1
            relabelled += 1
        exemplar_windows[str(c + 1)] = wi

    runs = run_summary(labels)
    # run length at every k, for a comparison at fixed k
    runs_by_k = {}
    for kk in range(1, min(k_max, len(chosen)) + 1):
        o = regime_owner(D[chosen[:kk]], scored)
        lab, _ = label_windows(o, w_starts, m, m, kk)
        lab[nan_windows] = -1
        lab[lab == 0] = -1
        rs = run_summary(lab)
        runs_by_k[str(kk)] = {"mean": rs["mean"], "median": rs["median"], "ratio": rs["ratio"]}

    return {
        "labels": labels,
        "k": int(k_used), "k_chosen_by": chosen_by, "k_reason": reason,
        "k_max": k_max, "knee_candidate": kd["candidate"], "knee_ratio": kd["ratio"],
        "knee_threshold": kd["threshold"],
        "areas": [float(a) for a in areas], "change_k": {str(kk): v for kk, v in changes.items()},
        "snippet_pieces": [int(r) for r in sel],
        "snippet_starts": [int(piece_starts[r]) + lo for r in sel],   # span-relative samples
        "fractions": fractions,
        "exemplar_windows": exemplar_windows, "n_exemplar_relabelled": int(relabelled),
        "contiguous": contiguous,
        "m": m, "s": int(s), "subseq_frac": float(subseq_frac), "mpdist_percentage": float(mpdist_percentage),
        "kth": _kth(m, m - s + 1, mpdist_percentage),
        "n_pieces": int(n_pieces), "n_pieces_excluded_nan": int((~cand).sum()),
        "n_windows": int(len(labels)), "n_windows_nan": int(nan_windows.sum()),
        "n_windows_unlabelled": int(np.sum(labels == -1)),
        "n_nan_filled": int(nan_mask.sum()),
        "n_positions": int(P), "n_positions_scored": n_scored,
        "runs": runs, "runs_by_k": runs_by_k,
        "elapsed_s": float(time.perf_counter() - t0),
    }
