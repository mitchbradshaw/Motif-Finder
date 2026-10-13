"""
beads.py
=========
Baseline estimation and denoising with sparsity — **BEADS** (Ning, Selesnick &
Duval 2014, *Chemometr. Intell. Lab. Syst.* 139:156–167,
doi:10.1016/j.chemolab.2014.09.014). Headless: numpy and scipy only.

The model: a recording is ``y = f + x + w`` — ``f`` a slow, low-pass baseline
(drift), ``x`` a sparse layer of events (mostly zero, with mostly-zero first and
second differences), ``w`` noise. BEADS minimises

    F(x) = ½‖H(y − x)‖² + λ₀ Σ θ_ε(xₙ; r) + λ₁ Σ φ([D₁x]ₙ) + λ₂ Σ φ([D₂x]ₙ)

with ``H = B A⁻¹`` a zero-phase high-pass filter made of banded matrices (order
``d``, cut-off ``fc`` in cycles/sample), ``θ`` an asymmetric (ratio ``r``)
smoothed absolute value — events are one-sided, positive ``x`` costs 1 per unit
and negative ``x`` costs ``r`` — and ``φ(v) = √(v² + ε₁)`` a smoothed absolute
value. It is solved by majorisation–minimisation: each iteration is one banded,
symmetric positive-definite solve, so time and memory are O(N) per iteration.
The baseline is ``f = y − x − H(y − x)``.

Provenance and licence
----------------------
A port of Laurent Duval's MATLAB ``beads.m`` (the reference implementation
accompanying the paper), as also adapted by pybaselines' ``misc.beads``:

    Copyright (c) 2018, Laurent Duval. All rights reserved.
    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions are met
    (BSD 3-Clause): (1) redistributions of source code must retain the above
    copyright notice, this list of conditions and the following disclaimer;
    (2) redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution;
    (3) neither the name of the copyright holder nor the names of its
    contributors may be used to endorse or promote products derived from this
    software without specific prior written permission. THIS SOFTWARE IS
    PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS
    OR IMPLIED WARRANTIES ARE DISCLAIMED.

The update equations (filter matrices ``BAfilt``, the weights ``Γ`` and ``Λ``,
the right-hand side ``d = BᵀB A⁻¹y − λ₀ Aᵀb``, the solve
``x = A (BᵀB + AᵀMA)⁻¹ d`` and the cost) follow ``beads.m`` line for line,
with its ``L1_v2`` penalty ``φ(v) = √(v² + ε₁)`` (pybaselines' default
``cost_function=2``). The paper's own text (HAL hal-01330608) could not be
read; the equations are the implementations'.

What is ours, not the paper's — the adaptations our recordings force
---------------------------------------------------------------------
``beads()`` is the faithful algorithm. ``remove_baseline()`` wraps it for
fungal recordings, and every change is here:

1. **Parameters in our units.** ``baseline_period_s`` sets
   ``fc = 1 / (baseline_period_s · fs)`` cycles/sample: anything slower than
   that period is baseline. ``polarity`` replaces ``r``: ``"spike"`` solves
   with ``r = 6`` (positive events), ``"drop"`` negates the trace, solves with
   ``r = 6`` and negates back (our events of interest are troughs), ``"both"``
   uses ``r = 1`` (a symmetric penalty). ``sparsity`` is one unit-free
   multiplier on all three λ; **λ₁ and λ₂ are derived from it** in a fixed
   ratio (``LAMBDA_RATIOS``) and not exposed, because small changes of λ₁ are
   known to destabilise BEADS (pybeads, MIT, reports it).
2. **Unit-free, at the scale the solve sees.** The grid (adaptation 3) is
   divided by a robust scale before solving and multiplied back after, so the
   same ``sparsity`` means the same thing in volts and millivolts, and
   multiplying the input by k multiplies every output by k. The scale is the
   robust level (MAD ÷ 0.6745) of the *high-passed grid* ``H(grid)`` — exactly
   what the fidelity term ½‖H(y − x)‖² weighs — floored at the white-noise
   level σ/√q (σ: MAD of the first difference ÷ (0.6745·√2), reported as
   ``sigma``). Why not σ/√q alone, as first built: the fidelity term is
   quadratic in amplitude and the λ terms linear, so with λ in units of a
   noise level thousands of times smaller than the drift, whatever slow drift
   the filter's gentle slope lets through (6 % of a drift at twice the period)
   was cheaper to put in x than to leave — the whole drift went into the event
   layer (review 2026-10-13: 56–97 % baseline error, event fraction 0.99,
   converged=True). Measured on ``H(grid)``, that leak *is* the scale, so x
   only takes what stands out from it; and correlated noise (AR(0.95): a
   first-difference MAD reads it at 0.22× its level) is measured as it
   averages onto the grid. A first difference of the grid was tried and
   rejected: on a random walk it still left 40–55 % of the span in x. The λ
   scale (``LAMBDA_RATIOS``) is the paper's ratio 0.5 : 5 : 4 times 0.3 —
   chosen (0.1 – 3 tried) as the value that, on the acceptance trace of
   ``tests/test_beads.py``, still puts the drops' deep part into x (event
   fraction 0.047) while pure drift and noise put nothing there. Above 0.5 the
   event layer goes quiet on the drops too and the slow-drop polarity
   advantage fades. ``ε₀ = ε₁ = 1e-4`` scale units (``beads.m``: 1e-6 raw
   units): far below anything the data resolve, and it makes the banded solves
   ~10× better conditioned (measured).
   The floor of this method on pure drift is therefore the filter, not the λ:
   a drift at 2× ``baseline_period_s`` leaves ~4 % RMS (6 % peak) of its
   amplitude in the corrected trace, one at 3× ~0.9 % (1.3 % peak), one at
   1.5× ~12 %. A
   600 s rolling mean tracks a fast, large drift more closely than that; what
   it cannot do is leave a drop alone.
3. **A coarse grid for the solve.** Our cut-offs are tiny — a 2-hour period at
   1 Hz is fc = 1.4e-4 cycles/sample, against the paper's ~1e-2 — and the
   filter matrix A then has a condition number ~1/(π·fc)^(2d): above 1e15 for
   d = 2, so the solve is noise (measured: the residual blew up to 40 units
   on a drift-only trace). The baseline is slow by definition, so BEADS is run
   on block means of ``q`` samples chosen to lift the cut-off to ``FC_GRID``
   (0.02) cycles per grid sample — 144 s blocks for the default 2 h at 1 Hz —
   and its baseline is interpolated back to every sample (linearly; the
   baseline has nothing faster than the period in it, so the interpolation
   error is ~1e-4 of its amplitude). The scale is measured on this grid
   (adaptation 2). The
   corrected signal ``y − baseline`` keeps every sample's own detail. The event
   layer x is reported at the grid's resolution only. As a bonus a
   2.6 M-sample channel is solved on ~18 k grid points.
4. **Ends.** BEADS needs the trace near zero at both ends (its banded filter
   has no boundary model). The grid is padded at each end by one baseline
   period, point-reflected about the end value (so level *and* slope continue
   smoothly), then a straight line through the medians of the two padded end
   regions is removed and added back to the baseline — the role pybaselines'
   ``fit_parabola`` and pybeads' sigmoid padding play. Measured: without the
   padding a drift that is steep at a span's edge left a 1.3-unit error there.
   The weak spot: an *event* in the last quarter period is reflected with the
   end value it bends, and the baseline there follows it (measured: a span cut
   1040 s after a drop onset, 0.63 of the drop's depth; cut clear of the
   drops, 0.075). Anchoring the reflection on an end median or a robust end
   line was tried and helped one case while hurting others, so instead an
   event layer above 3 scale units within that quarter period at either end
   is named in ``meta["warnings"]``.
5. **Filter order 2, and only 2, in the block** (the plan said 1, default).
   The cut-off is a gentle slope, not a wall: a first-order filter lets ~10 %
   of a drift three times slower than ``baseline_period_s`` through as
   "signal". Measured 2026-10-13 with the grid scale of adaptation 2: on the
   acceptance trace (6 h drift, 2 h period) order 1 leaves residual drift of
   0.36 units RMS — 3.6 times the 0.1 the block must meet — and 15 % RMS of a
   drift at twice the period (order 2: 0.045 units and 4 %). (Before that
   scale it was worse: 3.8 units, the whole drift in x.) Order 1 cannot be
   made safe by λ — the leak is the filter's — so the block offers only 2;
   ``remove_baseline`` still accepts 1 for comparison.
6. **Long spans.** Every matrix is kept as its diagonals (``_Bands``) and the
   system is solved by banded Cholesky (``scipy.linalg.solveh_banded``, banded
   LU if rounding costs it its definiteness — the order MATLAB's backslash
   tries them in), so memory and time stay linear; the iterations are capped
   (``max_iter``) with a tolerance on the relative change of the cost, and
   whether it converged is reported, never hidden.
7. **Missing samples.** NaN runs at either end are trimmed from the solve
   (the result equals the result on the span without them; holding the last
   value flat through a trailing hour, as first built, bent the baseline to
   0.48 against 0.075). Interior NaNs are bridged by a straight line for the
   solve; every NaN is put back as NaN in every output, and the count, the
   longest interior gap (``longest_gap_s``) and the trimmed samples are
   reported. Across a bridged gap the baseline follows the line: near a gap
   longer than ~period/10 it is interpolated, not estimated, and
   ``meta["warnings"]`` says so.

The honest limits: no baseline method can split an event from drift with the
same time-scale. ``baseline_period_s`` must sit above the slowest event you
care about; an event as slow as the period is part of the baseline. And on a
span made mostly of events (a plateau occupying most of each interval) the
"baseline" settles partway into them — the scale and the sparse prior both
assume events are the minority — so absolute levels after BEADS are not
reliable on event-dominated spans; event shapes and relative depths are.
When the event layer covers more than 80 % of a drop/spike run the drift has
gone into x, and ``meta["warnings"]`` says so.

Why not reuse: ``Working.Preprocessing.detrend`` subtracts a rolling mean or a
line — the very filter this block replaces (it is dragged down by every big
drop and leaves an overshoot beside it); nothing in the repo solves banded
penalised systems.
"""

import numpy as np
from scipy.linalg import LinAlgError, solve_banded, solveh_banded

#: (λ₀, λ₁, λ₂) at ``sparsity = 1``, in units of the grid scale (adaptation 2).
#: The paper's worked example uses λ₀ : λ₁ : λ₂ = 0.5 : 5 : 4 (times an
#: amplitude); the ratio is kept, the scale (×0.3) is set for a trace divided by
#: the robust level of its own high-passed grid.
LAMBDA_RATIOS = (0.15, 1.5, 1.2)
#: Above this fraction of the span the event layer is drift, not events, on a
#: one-sided (drop / spike) run — reported in ``meta["warnings"]``.
EVENT_FRACTION_WARN = 0.8
#: An interior NaN gap longer than this fraction of the baseline period is
#: bridged by a straight line the baseline then follows — reported.
GAP_WARN_PERIODS = 0.1
#: Asymmetry ratio for one-sided events (the paper's and pybaselines' 6).
ASYMMETRY = 6.0
POLARITIES = ("drop", "spike", "both")
#: Shortest trace BEADS is run on: below this the filter's edges are the trace.
MIN_SAMPLES = 64
#: The cut-off, in cycles per GRID sample, BEADS is solved at (adaptation 3).
FC_GRID = 0.02
#: ε₀ = ε₁ in noise units (adaptation 2).
EPS = 1e-4


# ── banded-matrix arithmetic ────────────────────────────────────────────────

class _Bands:
    """An N×N banded matrix kept as its diagonals: ``self.d[k][i] = P[i, i+k]``
    (zero where ``i + k`` falls outside the matrix). Products and mat-vecs are
    O(N · bands²), so nothing N×N is ever built."""

    def __init__(self, n, diags=None):
        self.n = int(n)
        self.d = dict(diags or {})

    @staticmethod
    def _shift(v, k):
        """``out[i] = v[i + k]`` (zero outside)."""
        n = len(v)
        out = np.zeros(n)
        if k >= 0:
            out[:n - k] = v[k:]
        else:
            out[-k:] = v[:n + k]
        return out

    @classmethod
    def toeplitz(cls, n, coefs):
        """Symmetric Toeplitz band with ``coefs`` on offsets ``-h .. h``."""
        h = (len(coefs) - 1) // 2
        diags = {}
        for j, c in enumerate(coefs):
            k = j - h
            arr = np.full(n, float(c))
            if k > 0:
                arr[n - k:] = 0.0
            elif k < 0:
                arr[:-k] = 0.0
            diags[k] = arr
        return cls(n, diags)

    @classmethod
    def diag(cls, v):
        return cls(len(v), {0: np.asarray(v, dtype=float)})

    @classmethod
    def difference_gram(cls, n, coefs, w):
        """``Dᵀ diag(w) D`` for the (N − L + 1)×N difference operator whose rows
        carry ``coefs`` (length L) — D₁ is ``[-1, 1]``, D₂ ``[1, -2, 1]``."""
        L = len(coefs)
        rows = n - L + 1
        diags = {}
        for k in range(L):
            arr = np.zeros(n)
            for s in range(L - k):
                arr[s:s + rows] += w * (coefs[s] * coefs[s + k])
            diags[k] = arr
            if k:
                diags[-k] = cls._shift(arr, -k)
        return cls(n, diags)

    def __add__(self, other):
        out = {k: v.copy() for k, v in self.d.items()}
        for k, v in other.d.items():
            out[k] = out[k] + v if k in out else v.copy()
        return _Bands(self.n, out)

    def __matmul__(self, other):
        if isinstance(other, _Bands):
            out = {}
            for l, q in other.d.items():
                for k, p in self.d.items():
                    term = p * self._shift(q, k)
                    m = k + l
                    if m in out:
                        out[m] += term
                    else:
                        out[m] = term
            return _Bands(self.n, out)
        v = np.asarray(other, dtype=float)
        out = np.zeros(self.n)
        for k, p in self.d.items():
            out += p * self._shift(v, k)
        return out

    def solve(self, rhs):
        """Solve ``P z = rhs`` for symmetric positive-definite P: banded
        Cholesky first, banded LU when rounding has cost P its definiteness —
        the order MATLAB's backslash, which ``beads.m`` uses, tries them in."""
        try:
            return solveh_banded(self.upper_form(), rhs, check_finite=False)
        except LinAlgError:
            u = max(k for k in self.d if k >= 0)
            lo = max(-k for k in self.d if k <= 0)
            ab = np.zeros((u + lo + 1, self.n))
            for k, v in self.d.items():
                # solve_banded form: ab[u + i - j, j] = P[i, j], j = i + k
                if k >= 0:
                    ab[u - k, k:] = v[:self.n - k]
                else:
                    ab[u - k, :self.n + k] = v[-k:]
            return solve_banded((lo, u), ab, rhs, check_finite=False)

    def upper_form(self):
        """The ``solveh_banded`` upper form ``ab[u + i - j, j] = P[i, j]``."""
        u = max(k for k in self.d if k >= 0)
        ab = np.zeros((u + 1, self.n))
        for k in range(u + 1):
            if k in self.d:
                ab[u - k, k:] = self.d[k][:self.n - k]
        return ab


def _filter_matrices(d, fc, n):
    """``beads.m``'s ``BAfilt``: banded A, B such that ``H = B A⁻¹`` is a
    zero-phase high-pass filter of order ``d`` with cut-off ``fc``."""
    b1 = np.array([1.0, -1.0])
    for _ in range(d - 1):
        b1 = np.convolve(b1, [-1.0, 2.0, -1.0])
    b = np.convolve(b1, [-1.0, 1.0])
    omc = 2.0 * np.pi * fc
    t = ((1.0 - np.cos(omc)) / (1.0 + np.cos(omc))) ** d
    a = np.array([1.0])
    for _ in range(d):
        a = np.convolve(a, [1.0, 2.0, 1.0])
    a = b + t * a
    return _Bands.toeplitz(n, a), _Bands.toeplitz(n, b)


def _theta(x, r, eps0):
    """The asymmetric smoothed absolute value θ_ε(x; r), summed."""
    pos = x > eps0
    neg = x < -eps0
    mid = ~(pos | neg)
    xm = x[mid]
    return (x[pos].sum() - r * x[neg].sum()
            + np.sum((1 + r) / (4 * eps0) * xm ** 2 + (1 - r) / 2 * xm + eps0 * (1 + r) / 4))


# ── the algorithm ───────────────────────────────────────────────────────────

def beads(y, *, fc, d=1, r=ASYMMETRY, lam0, lam1, lam2, max_iter=30, tol=1e-3,
          eps0=1e-6, eps1=1e-6):
    """BEADS on ``y`` exactly as ``beads.m`` runs it.

    Parameters
    ----------
    y : array, the trace (should start and end near zero — see the module notes).
    fc : float, high-pass cut-off in cycles/sample, 0 < fc < 0.5.
    d : int, filter order (1 or 2).
    r : float, asymmetry ratio (≥ 1; 1 is symmetric).
    lam0, lam1, lam2 : float, weights on x, D₁x, D₂x.
    max_iter : int, cap on MM iterations.
    tol : float, stop when the cost changes by less than this fraction.

    Returns
    -------
    x : the sparse event layer.
    f : the baseline, ``y − x − H(y − x)``.
    info : ``{"iterations", "converged", "cost"}`` — the cost after every
        iteration, and whether the relative change fell below ``tol``.
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    if d not in (1, 2):
        raise ValueError(f"BEADS filter order d must be 1 or 2, got {d!r}.")
    if not 0.0 < fc < 0.5:
        raise ValueError(f"BEADS cut-off fc must lie in (0, 0.5) cycles/sample, got {fc!r}.")
    if n < MIN_SAMPLES:
        raise ValueError(f"BEADS needs at least {MIN_SAMPLES} samples, got {n}.")

    A, B = _filter_matrices(d, fc, n)
    BTB = B @ B                      # B is symmetric

    def H(v):
        return B @ A.solve(v)

    b_vec = np.full(n, (1.0 - r) / 2.0)
    rhs = BTB @ A.solve(y) - lam0 * (A @ b_vec)

    def wfun(v):
        return 1.0 / np.sqrt(v ** 2 + eps1)

    def phi(v):
        return np.sqrt(v ** 2 + eps1)

    x = y.copy()
    costs = []
    converged = False
    for _ in range(int(max_iter)):
        d1x = np.diff(x)
        d2x = np.diff(x, 2)
        gram = (_Bands.difference_gram(n, (-1.0, 1.0), lam1 * wfun(d1x))
                + _Bands.difference_gram(n, (1.0, -2.0, 1.0), lam2 * wfun(d2x)))
        ax = np.abs(x)
        gamma = np.where(ax > eps0, (1.0 + r) / 4.0 / np.maximum(ax, eps0), (1.0 + r) / 4.0 / eps0)
        M = gram + _Bands.diag(2.0 * lam0 * gamma)
        system = BTB + A @ M @ A
        x = A @ system.solve(rhs)

        h = H(y - x)
        cost = (0.5 * float(h @ h) + lam0 * _theta(x, r, eps0)
                + lam1 * float(phi(np.diff(x)).sum()) + lam2 * float(phi(np.diff(x, 2)).sum()))
        if costs and abs(cost - costs[-1]) <= tol * abs(costs[-1]):
            costs.append(cost)
            converged = True
            break
        costs.append(cost)

    f = y - x - H(y - x)
    return x, f, {"iterations": len(costs), "converged": converged, "cost": costs}


# ── the wrapper the block calls ─────────────────────────────────────────────

def robust_sigma(y):
    """Noise level from the MAD of the first difference / (0.6745·√2) — blind to
    drift and to sparse events. Falls back to the plain std of the difference
    (÷ √2), then to 0.0 for a straight line, which has no noise to scale by
    (``remove_baseline`` returns it whole as baseline). Returns
    ``(sigma, source)``."""
    y = np.asarray(y, dtype=float)
    dy = np.diff(y)
    # rounding noise of a straight line is not noise: anything below 1e-12 of
    # the trace's own size counts as zero
    floor = 1e-12 * float(np.max(np.abs(y))) if len(y) else 0.0
    mad = np.median(np.abs(dy - np.median(dy)))
    sigma = mad / (0.6745 * np.sqrt(2.0))
    if sigma > floor and np.isfinite(sigma):
        return float(sigma), "mad_of_difference"
    sd = float(np.std(dy)) / np.sqrt(2.0)
    if sd > floor:
        return sd, "std_of_difference"
    return 0.0, "flat_trace"


def _end_line(y, period_samples):
    """A line through the medians of the two end regions (each the shorter of
    5 % of the span and a quarter of the baseline period, at least 1 sample)."""
    n = len(y)
    m = int(max(1, min(n // 20, period_samples // 4)))
    left, right = float(np.median(y[:m])), float(np.median(y[n - m:]))
    xl, xr = (m - 1) / 2.0, n - 1 - (m - 1) / 2.0
    idx = np.arange(n, dtype=float)
    return left + (right - left) * (idx - xl) / (xr - xl), m


def _block_means(v, q):
    """Means of consecutive blocks of ``q`` samples (the last may be shorter)
    and the fractional sample index of each block's centre."""
    n = len(v)
    nb = -(-n // q)
    starts = np.arange(nb) * q
    sums = np.add.reduceat(v, starts)
    counts = np.diff(np.append(starts, n))
    return sums / counts, starts + (counts - 1) / 2.0


def _to_samples(n, centres, values):
    """Linear interpolation from the grid back to every sample, continued
    linearly (not held flat) over the half block before the first centre and
    after the last — a held value would put a step of slope × q/2 there."""
    full = np.arange(n, dtype=float)
    out = np.interp(full, centres, values)
    head = full < centres[0]
    tail = full > centres[-1]
    if head.any():
        slope = (values[1] - values[0]) / (centres[1] - centres[0])
        out[head] = values[0] + slope * (full[head] - centres[0])
    if tail.any():
        slope = (values[-1] - values[-2]) / (centres[-1] - centres[-2])
        out[tail] = values[-1] + slope * (full[tail] - centres[-1])
    return out


def grid_scale(z, d, fc, inner):
    """The scale the fidelity term actually sees: the robust level (MAD ÷ 0.6745)
    of the high-passed grid ``H z`` — the noise *as averaged onto the grid*
    (correlated noise does not average down by √q) plus whatever slow drift the
    filter's gentle slope lets through — measured on ``inner`` (the grid without
    its end padding)."""
    A, B = _filter_matrices(d, fc, len(z))
    h = (B @ A.solve(z))[inner]
    return float(np.median(np.abs(h - np.median(h))) / 0.6745)


def _longest_run(mask):
    """Length of the longest run of True in ``mask``."""
    if not mask.any():
        return 0
    edges = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return int(np.max(np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1)))


def grid_factor(n, fc, fc_grid=FC_GRID):
    """How many samples BEADS averages into one grid point: enough to lift the
    cut-off to ``fc_grid`` cycles/sample, never so many that fewer than
    ``MIN_SAMPLES`` grid points are left."""
    if fc_grid is None:
        return 1
    return int(max(1, min(np.floor(fc_grid / fc), n // MIN_SAMPLES)))


def remove_baseline(y, fs, *, baseline_period_s=7200.0, polarity="drop", sparsity=1.0,
                    filter_order=2, max_iter=30, tol=1e-3, fc_grid=FC_GRID, eps=EPS):
    """Unit-free BEADS for a recording sampled at ``fs`` Hz.

    Returns a dict: ``corrected`` (``y − baseline``), ``baseline``, ``events``
    (the sparse layer x, in the trace's units and sign, at the grid's
    resolution), and ``meta`` — fc, r, the λ used, iterations, converged, the
    robust σ and how it was found, the grid, the baseline's range, the end
    padding, the NaN count, and the fraction of grid points where ``|x|``
    exceeds 3 × the grid's noise level.
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    if polarity not in POLARITIES:
        raise ValueError(f"BEADS polarity must be one of {POLARITIES}, got {polarity!r}.")
    if filter_order not in (1, 2):
        raise ValueError(f"BEADS filter_order must be 1 or 2, got {filter_order!r}.")
    if not (sparsity > 0):
        raise ValueError(f"BEADS sparsity must be positive, got {sparsity!r}.")
    if n < MIN_SAMPLES:
        raise ValueError(
            f"BEADS baseline removal needs at least {MIN_SAMPLES} samples; this span has {n}. "
            "Choose a longer span.")
    period_samples = float(baseline_period_s) * float(fs)
    if not period_samples > 2.0:
        raise ValueError(
            f"baseline_period_s = {baseline_period_s:g} s is {period_samples:g} samples at fs = {fs:g} Hz; "
            "it must span more than 2 samples (the cut-off must sit below the Nyquist frequency).")
    fc = 1.0 / period_samples

    finite = np.isfinite(y)
    n_finite = int(finite.sum())
    n_nan = n - n_finite
    if n_finite < MIN_SAMPLES:
        raise ValueError(
            f"BEADS baseline removal needs at least {MIN_SAMPLES} finite samples; "
            f"this span has {n_finite} of {n}.")
    # NaN at either end is trimmed from the solve (holding the last value flat
    # through it would be solved as data); interior gaps are bridged linearly
    fin_idx = np.flatnonzero(finite)
    lo, hi = int(fin_idx[0]), int(fin_idx[-1]) + 1
    m = hi - lo
    work = y[lo:hi].copy()
    inside_nan = ~finite[lo:hi]
    if inside_nan.any():
        idx = np.arange(m)
        work[inside_nan] = np.interp(idx[inside_nan], idx[~inside_nan], work[~inside_nan])
    longest_gap = _longest_run(inside_nan)

    sigma, sigma_source = robust_sigma(y[finite])
    sign = -1.0 if polarity == "drop" else 1.0
    r = 1.0 if polarity == "both" else ASYMMETRY
    lam0, lam1, lam2 = (float(sparsity) * c for c in LAMBDA_RATIOS)

    q = grid_factor(m, fc, fc_grid)
    grid, centres = _block_means(work, q)
    ng = len(grid)
    period_grid = period_samples / q
    pad = int(min(ng - 1, round(period_grid)))
    if pad:
        grid = np.concatenate([2 * grid[0] - grid[pad:0:-1], grid, 2 * grid[-1] - grid[-2:-pad - 2:-1]])
    line, end_samples = _end_line(grid, period_grid)
    inner = slice(pad, pad + ng)
    sigma_white = sigma / np.sqrt(q)
    if sigma > 0:
        sigma_grid = max(grid_scale(grid - line, int(filter_order), fc * q, inner), sigma_white)
        z = sign * (grid - line) / sigma_grid
        xs, fs_, info = beads(z, fc=fc * q, d=int(filter_order), r=r, lam0=lam0, lam1=lam1, lam2=lam2,
                              max_iter=max_iter, tol=tol, eps0=eps, eps1=eps)
        f_grid = (sign * fs_ * sigma_grid + line)[inner]
        x_grid = (sign * xs * sigma_grid)[inner]
        xs = xs[inner]
    else:
        # a straight line has no noise to measure events against: all baseline
        sigma_grid = 0.0
        f_grid, x_grid, xs = grid[inner].copy(), np.zeros(ng), np.zeros(ng)
        info = {"iterations": 0, "converged": True, "cost": []}
    baseline = np.full(n, np.nan)
    events = np.full(n, np.nan)
    if q == 1:
        baseline[lo:hi], events[lo:hi] = f_grid, x_grid
    else:
        baseline[lo:hi], events[lo:hi] = _to_samples(m, centres, f_grid), _to_samples(m, centres, x_grid)
    events[~finite] = np.nan
    baseline[~finite] = np.nan
    corrected = y - baseline

    event_fraction = float(np.mean(np.abs(xs) > 3.0))
    warnings = []
    if polarity != "both" and event_fraction > EVENT_FRACTION_WARN:
        warnings.append(
            f"The event layer covers {event_fraction:.0%} of the span: that is drift, not events, and the "
            "baseline is not trustworthy. Raise `sparsity` or `baseline_period_s`.")
    edge = int(max(1, min(ng // 4, round(period_grid / 4))))
    edge_events = [side for side, part in (("start", xs[:edge]), ("end", xs[-edge:]))
                   if np.any(np.abs(part) > 3.0)]
    if edge_events:
        warnings.append(
            f"An event sits within {edge * q / float(fs):g} s of the span's {' and '.join(edge_events)}: the "
            "end padding reflects it, and the baseline over the last half period there can be off by a "
            "large fraction of the event's depth. Widen the span past the event if you can.")
    if longest_gap > GAP_WARN_PERIODS * period_samples:
        warnings.append(
            f"A gap of {longest_gap / float(fs):g} s (longer than a tenth of the {baseline_period_s:g} s "
            "period) was bridged by a straight line: the baseline near it is interpolated, not estimated.")

    meta = {
        "fc_cycles_per_sample": fc,
        "baseline_period_s": float(baseline_period_s),
        "polarity": polarity,
        "r": r,
        "lam0": lam0, "lam1": lam1, "lam2": lam2,
        "sparsity": float(sparsity),
        "filter_order": int(filter_order),
        "grid_factor": int(q),
        "grid_step_s": q / float(fs),
        "fc_grid_cycles_per_sample": fc * q,
        "iterations": int(info["iterations"]),
        "max_iter": int(max_iter),
        "converged": bool(info["converged"]),
        "final_cost": float(info["cost"][-1]) if info["cost"] else None,
        "sigma": sigma,
        "sigma_grid": float(sigma_grid),
        "sigma_grid_white": float(sigma_white),
        "sigma_source": sigma_source,
        "baseline_min": float(np.nanmin(baseline)),
        "baseline_max": float(np.nanmax(baseline)),
        "grid_points": int(ng),
        "end_pad_grid_points": int(pad),
        "end_region_grid_points": int(end_samples),
        "n_nan": int(n_nan),
        "longest_gap_s": longest_gap / float(fs),
        "trimmed_end_samples": int(n - m),
        "event_fraction_3sigma": event_fraction,
        "span_shorter_than_period": bool(n < period_samples),
        "warnings": warnings,
    }
    return {"corrected": corrected, "baseline": baseline, "events": events, "meta": meta}


