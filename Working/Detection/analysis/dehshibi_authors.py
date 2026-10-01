"""
dehshibi_authors.py
===================
The spike detector of Dehshibi & Adamatzky (2021), "Electrical activity of
fungi: Spikes detection and complexity analysis", BioSystems 203, 104373 —
ported from **the authors' own MATLAB** (supplementary material, Zenodo
10.5281/zenodo.3997031, `imMain.m` and the `i*.m` it calls), not from the
printed algorithms.

Why the code and not the print (fixup-J, QUESTIONS.md Q33): the two differ,
the code is what produced the paper's figures and its 76 % true-positive
rate, and the printed Algorithm 3 read literally returns regions that end
before they start. `docs/prompts/fixup/reports/J-dehshibi-vs-the-paper.md`
tabulates every difference. `dehshibi_detection_analysis.py` holds the older
reading of the print and is kept only for its other importers.

The port is checked against the authors' code run in MATLAB R2025b on three
synthetic recordings (`tests/fixtures/dehshibi/reference.json`,
`tests/test_dehshibi_authors.py`).

Each function names the MATLAB file it ports. Indices here are 0-based and
regions are INCLUSIVE `(start, end)` pairs, as in the MATLAB; the adapters
convert to `SpanSet`'s half-open form at their seam.

Lengths are in SECONDS and are converted with `fs` (Q32). The MATLAB runs at
Fs = 1 and writes them as sample counts.
"""

from __future__ import annotations

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import brentq
from scipy.signal import find_peaks, peak_prominences, peak_widths

# ── the authors' constants (imMain.m, iApplyWavelet.m) ──────────────────────
GAMMA = 3.0                 # MATLAB cwt's default Morse wavelet: gamma 3,
BETA = 20.0                 # time-bandwidth product 60 -> beta 20
VOICES_PER_OCTAVE = 10      # cwt default
ETA = 240.0                 # scaleFactor
THR = 0.05                  # thr: extremum prominence as a fraction of Omega's range
PEAK_WIDTH_S = 60.0         # peakWidth(1): minimum distance between extrema, seconds
LOW_BAND_FRACTION = 0.25    # method 2: Omega sums the frequencies <= a quarter of the range
WINDOW_S = 3000.0           # the paper's own chunk length (Fig. 5); Q29


# ════════════════════════════════════════════════════════════════════════════
# MATLAB primitives the authors' code leans on
# ════════════════════════════════════════════════════════════════════════════

def _local_maxima(y):
    """Indices of local maxima as MATLAB `findpeaks` picks them: strictly above
    the previous sample, and the FIRST sample of a flat top. Ends excluded."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    out = []
    i = 1
    while i < n - 1:
        if y[i] > y[i - 1]:
            j = i
            while j < n - 1 and y[j + 1] == y[i]:
                j += 1
            if j < n - 1 and y[j + 1] < y[i]:
                out.append(i)
            i = j + 1
        else:
            i += 1
    return np.asarray(out, dtype=int)


def _separate(y, locs, distance):
    """`findpeaks(..., 'MinPeakDistance', d)`: tallest first, each kept peak
    deletes every other within d samples (inclusive)."""
    if len(locs) == 0 or distance <= 0:
        return locs
    order = np.argsort(-y[locs], kind="stable")
    delete = np.zeros(len(locs), dtype=bool)
    for i in order:
        if not delete[i]:
            delete |= (locs >= locs[i] - distance) & (locs <= locs[i] + distance)
            delete[i] = False
    return locs[~delete]


def findpeaks(y, min_prominence=None, min_distance=None, min_width=None):
    """MATLAB `findpeaks` with MinPeakProminence / MinPeakWidth / MinPeakDistance,
    in MATLAB's order: prominence and half-prominence width first, distance last."""
    y = np.asarray(y, dtype=float)
    locs = _local_maxima(y)
    if len(locs) and (min_prominence is not None or min_width is not None):
        prom, lb, rb = peak_prominences(y, locs)
        keep = np.ones(len(locs), dtype=bool)
        if min_prominence is not None:
            keep &= prom >= min_prominence
        if min_width is not None:
            width = peak_widths(y, locs, rel_height=0.5, prominence_data=(prom, lb, rb))[0]
            keep &= width >= min_width
        locs = locs[keep]
    if min_distance is not None:
        locs = _separate(y, locs, min_distance)
    return locs


def del2(x):
    """MATLAB `del2` of a vector: a quarter of the second difference, the two
    end samples extrapolated linearly from the interior."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    L = np.zeros(n)
    if n < 3:
        return L
    L[1:-1] = (x[2:] - 2.0 * x[1:-1] + x[:-2]) / 4.0
    if n > 3:
        L[0] = 2.0 * L[1] - L[2]
        L[-1] = 2.0 * L[-2] - L[-3]
    else:
        L[0] = L[-1] = L[1]
    return L


def envelope_peak(x, n_p):
    """MATLAB `envelope(x, n_p, 'peak')`: a not-a-knot spline through the local
    maxima at least `n_p` samples apart (upper), and through the minima (lower)."""
    x = np.asarray(x, dtype=float)
    nx = len(x)
    grid = np.arange(nx, dtype=float)

    def one(sign):
        pk = findpeaks(sign * x, min_distance=n_p) if nx > n_p + 1 else np.array([], dtype=int)
        locs = np.concatenate([[0], pk, [nx - 1]]).astype(int) if len(pk) < 2 else pk
        locs = np.unique(locs)
        if len(locs) < 2:
            return x.copy()
        if len(locs) == 2:
            return x[locs[0]] + (x[locs[1]] - x[locs[0]]) * (grid - locs[0]) / (locs[1] - locs[0])
        if len(locs) == 3:
            return np.polyval(np.polyfit(locs.astype(float), x[locs], 2), grid)
        return CubicSpline(locs.astype(float), x[locs], bc_type="not-a-knot", extrapolate=True)(grid)

    return one(1.0), one(-1.0)


# ════════════════════════════════════════════════════════════════════════════
# cwt(chunk, Fs) — MATLAB's default continuous wavelet transform
# ════════════════════════════════════════════════════════════════════════════

def morse_peak_frequency(beta=BETA, gamma=GAMMA):
    return float((beta / gamma) ** (1.0 / gamma))


def morse_scales(n, beta=BETA, gamma=GAMMA, voices=VOICES_PER_OCTAVE):
    """The scale grid MATLAB's `cwt` builds for an n-sample signal: from the
    scale whose filter has fallen to half its peak at Nyquist, in `voices`
    steps per octave, up to the scale whose wavelet is two time-standard-
    deviations wide over the signal."""
    w0 = morse_peak_frequency(beta, gamma)
    half = lambda w: beta * np.log(w / w0) - w ** gamma + w0 ** gamma - np.log(0.5)
    cut = brentq(half, w0, 12.0 * np.pi)
    s0 = cut / np.pi
    sigma_t = np.sqrt(beta * gamma / 2.0)
    max_scale = max(n / (2.0 * sigma_t), s0 * 2.0 ** (1.0 / voices))
    n_oct = max(np.log2(max_scale / s0), 1.0 / voices)
    return s0 * 2.0 ** (np.arange(0, int(np.floor(n_oct * voices)) + 1) / voices)


def scale_frequencies(scales, fs=1.0, beta=BETA, gamma=GAMMA):
    return morse_peak_frequency(beta, gamma) / (2.0 * np.pi * np.asarray(scales)) * fs


def _modulus_rows(x, scales, beta=BETA, gamma=GAMMA):
    """Yield |W(s, tau)| one scale at a time: the analytic Morse transform,
    L1-normalised (filter peak 2), the signal extended by reflection as `cwt`
    does. One padded complex row is alive at a time, never the whole matrix."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    npad = n // 2 if n <= 100_000 else int(np.ceil(np.log2(n)))
    xp = np.concatenate([x[:npad][::-1], x, x[n - npad:][::-1]]) if npad else x
    m = len(xp)
    so1 = np.arange(1, m // 2 + 1) * (2.0 * np.pi / m)      # positive frequencies only: analytic
    log_so1 = np.log(so1)
    F = np.fft.fft(xp)[1:m // 2 + 1]
    w0 = morse_peak_frequency(beta, gamma)
    log_norm = -beta * np.log(w0) + w0 ** gamma
    spec = np.zeros(m, dtype=complex)
    for s in scales:
        spec[1:m // 2 + 1] = F * (2.0 * np.exp(log_norm + beta * (np.log(s) + log_so1) - (s * so1) ** gamma))
        yield np.abs(np.fft.ifft(spec))[npad:npad + n]


def morse_cwt_modulus(x, scales, beta=BETA, gamma=GAMMA):
    """The modulus matrix, rows following `scales` (MATLAB order: highest
    frequency first)."""
    return np.vstack(list(_modulus_rows(x, scales, beta=beta, gamma=gamma)))


def _scale_row(a, eta):
    """iApplyWavelet.m's normalisation of one frequency: subtract the minimum
    over time, divide by the maximum, times eta, truncate, add 1. A frequency
    with no range is all ones."""
    a = a - a.min()
    mx = a.max()
    if mx < np.finfo(float).eps:
        return np.ones_like(a)
    return 1.0 + np.fix(eta * (a / mx))


def scaled_scalogram(x, scales, eta=ETA, beta=BETA, gamma=GAMMA, out=None):
    """iApplyWavelet.m, the lines before `switch method`. Rows follow `scales`.
    With `out` (a (rows, n) array) the rows are written in place."""
    if out is None:
        out = np.empty((len(scales), len(x)), dtype=float)
    for i, a in enumerate(_modulus_rows(x, scales, beta=beta, gamma=gamma)):
        out[i] = _scale_row(a, eta)
    return out


def low_band_rows(freqs, fraction=LOW_BAND_FRACTION):
    """iApplyWavelet.m method 2: the rows whose frequency is at most `fraction`
    of the frequency RANGE. Returns a boolean mask over rows."""
    freqs = np.asarray(freqs, dtype=float)
    idx = np.flatnonzero(freqs <= fraction * (freqs.max() - freqs.min()))
    mask = np.zeros(len(freqs), dtype=bool)
    if len(idx):
        mask[idx.min():idx.max() + 1] = True
    return mask


# ════════════════════════════════════════════════════════════════════════════
# The four stages
# ════════════════════════════════════════════════════════════════════════════

def wavelet_regions(omega, thr=THR, peak_width=60):
    """iApplyWavelet.m after Omega is formed: candidate regions between
    consecutive extrema of Omega. Returns `(regions, peaks, valleys)`."""
    omega = np.asarray(omega, dtype=float)
    n = len(omega)
    inv = omega.max() - omega
    prom = thr * (omega.max() - omega.min())
    kw = dict(min_prominence=prom, min_distance=peak_width, min_width=peak_width / 2.0)
    peaks = findpeaks(omega, **kw)
    valleys = findpeaks(inv, **kw)
    marks = np.sort(np.concatenate([peaks, valleys])).astype(int)
    if len(marks) == 0:
        return [], peaks, valleys
    odd = len(marks) % 2 == 1
    if odd:
        marks = np.append(marks, n - 1)
    pairs = marks.reshape(-1, 2).astype(int)
    if odd:
        slack = int(np.floor(np.mean(pairs[:-1, 1] - pairs[:-1, 0]))) if len(pairs) > 1 else None
        if slack is not None:
            pairs[-1, 1] = min(pairs[-1, 0] + slack, pairs[-1, 1])
    widths = pairs[:, 1] - pairs[:, 0]
    slack = int(np.floor(np.std(widths, ddof=1))) if len(widths) > 1 else 0
    back = int(peak_width // 2) if slack > peak_width else slack // 2
    pairs[:, 0] = np.maximum(0, pairs[:, 0] - back)
    return [(int(a), int(b)) for a, b in pairs], peaks, valleys


def cluster_regions(x, regions, peak_width=60):
    """iClusterWaveletROI.m: a region of at least `peak_width` samples is a
    spike candidate when the signal inside it goes below both its ends or
    above both its ends; otherwise a pseudo-spike. Shorter regions are dropped."""
    x = np.asarray(x, dtype=float)
    spikes, pseudo = [], []
    for a, b in regions:
        if (b - a) < peak_width:
            continue
        w = x[a:b + 1]
        mins = find_peaks(-w)[0]
        maxs = find_peaks(w)[0]
        lo = w[mins].min() if len(mins) else w[0]
        hi = w[maxs].max() if len(maxs) else w[0]
        if (lo < w[0] and lo < w[-1]) or (hi > w[0] and hi > w[-1]):
            spikes.append((a, b))
        else:
            pseudo.append((a, b))
    return spikes, pseudo


def envelope_regions(x, peak_width=60):
    """iApplyEnvelope.m: the mean of the peak envelopes of del2(x); its minima
    and maxima (the first maximum dropped), sorted together and paired.
    Returns `(regions, delta, env_mid)`."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    hi, lo = envelope_peak(del2(x), peak_width)
    mid = (hi + lo) / 2.0
    mins = find_peaks(-mid)[0]
    if len(mins) == 0:
        mins = np.array([0])
    maxs = find_peaks(mid)[0]
    if len(maxs) == 0:
        maxs = mins + 1
    maxs = maxs[1:]
    marks = np.sort(np.concatenate([mins, maxs])).astype(int)
    odd = len(marks) % 2 == 1
    if odd:
        marks = np.append(marks, n - 1)
    pairs = marks.reshape(-1, 2).astype(int)
    if odd and len(pairs) > 1:
        slack = int(np.floor(np.mean(pairs[:-1, 1] - pairs[:-1, 0])))
        pairs[-1, 1] = min(pairs[-1, 0] + slack, pairs[-1, 1])
    pairs = np.clip(pairs, 0, n - 1)
    delta = np.abs(mid[pairs[:, 1]] - mid[pairs[:, 0]])
    return [(int(a), int(b)) for a, b in pairs], delta, mid


def _nearest(values, q):
    """MATLAB `dsearchn` on a column: index of the nearest value, first on ties."""
    return int(np.argmin(np.abs(np.asarray(values, dtype=float) - q)))


def locate_spikes(spike_regions, env_regions, env_delta):
    """iLocateSpike.m up to `Spike.boundary`: drop weak envelope regions, widen
    each wavelet spike region to the hull of the envelope regions it
    intersects, merge what then overlaps. With no intersection anywhere the
    wavelet regions are returned as they are. Returns `(spikes, kept_env)`."""
    if not spike_regions:
        return [], []
    env = np.asarray(env_regions, dtype=int).reshape(-1, 2)
    delta = np.asarray(env_delta, dtype=float)
    if len(delta):
        sd = np.std(delta, ddof=1) if len(delta) > 1 else 0.0
        cut = delta.mean() - sd if sd < delta.mean() else delta.mean()
        keep = ~(delta < cut)
        env = env[keep]
    wav = np.asarray(spike_regions, dtype=int).reshape(-1, 2)
    hits = {}
    if len(env):
        for i, (a, b) in enumerate(wav):
            j0, j1 = _nearest(env[:, 0], a), _nearest(env[:, 0], b)
            for j in range(j0, j1 + 1):
                if min(b, env[j, 1]) >= max(a, env[j, 0]):
                    hits.setdefault(i, []).append(j)
    if not hits:
        return [(int(a), int(b)) for a, b in wav], [(int(a), int(b)) for a, b in env]
    roi = []
    for i in sorted(hits):
        js = hits[i]
        roi.append([min(wav[i, 0], env[js, 0].min()), max(wav[i, 1], env[js, 1].max())])
    i = 0
    while i < len(roi) - 1:
        if roi[i][1] < roi[i + 1][0]:
            i += 1
        else:
            roi[i][1] = roi[i + 1][1]
            del roi[i + 1]
    return [(int(a), int(b)) for a, b in roi], [(int(a), int(b)) for a, b in env]


# ════════════════════════════════════════════════════════════════════════════
# Chunking
# ════════════════════════════════════════════════════════════════════════════

def fixed_windows(n, window):
    """Consecutive `window`-sample chunks covering every sample; a tail shorter
    than half a window joins the chunk before it. Inclusive pairs."""
    window = max(1, int(window))
    starts = list(range(0, n, window))
    if len(starts) > 1 and n - starts[-1] < window / 2.0:
        starts.pop()
    return [(s, (starts[i + 1] - 1) if i + 1 < len(starts) else n - 1) for i, s in enumerate(starts)]


def state_levels(x, n_bins=100):
    """MATLAB `statelevels` (histogram method, mode): the most populated bin of
    the lower and of the upper half of the amplitude histogram."""
    x = np.asarray(x, dtype=float)
    lo, hi = float(x.min()), float(x.max())
    if hi == lo:
        return lo, hi
    counts, edges = np.histogram(x, bins=n_bins, range=(lo, hi))
    centres = 0.5 * (edges[:-1] + edges[1:])
    nz = np.flatnonzero(counts)
    i0, i1 = int(nz[0]), int(nz[-1])
    half = i0 + (i1 - i0) // 2
    low = centres[i0 + int(np.argmax(counts[i0:half + 1]))]
    high = centres[half + 1 + int(np.argmax(counts[half + 1:i1 + 1]))] if half + 1 <= i1 else centres[i1]
    return float(low), float(high)


def split_signal(x, tolerance=0.02):
    """iSplitSignal.m: cut the recording at the start of every pulse separation
    `pulsesep` reports — the rising mid-reference crossing of each positive
    pulse that is followed by another — and keep EVERY piece. A transition
    counts only when the signal goes from inside one state's tolerance band to
    inside the other's (IEEE Std 181), so noise about the midpoint cuts nothing."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    low, high = state_levels(x)
    amp = high - low
    if amp <= 0:
        return [(0, n - 1)]
    lo_b, hi_b, mid = low + tolerance * amp, high - tolerance * amp, (low + high) / 2.0
    state = np.zeros(n, dtype=int)
    state[x <= lo_b] = -1
    state[x >= hi_b] = 1
    idx = np.flatnonzero(state)
    rises, falls = [], []
    for a, b in zip(idx[:-1], idx[1:]):
        if state[a] == -1 and state[b] == 1:
            seg = np.flatnonzero((x[a:b] < mid) & (x[a + 1:b + 1] >= mid))
            j = a + (int(seg[0]) if len(seg) else 0)
            rises.append(j + (mid - x[j]) / (x[j + 1] - x[j]) if x[j + 1] != x[j] else float(j))
        elif state[a] == 1 and state[b] == -1:
            falls.append(float(b))
    # a separation runs from a pulse's fall to the next pulse's rise; pulsesep
    # reports it at the rise that OPENS the pulse before it
    cuts = []
    for k, r in enumerate(rises):
        later_falls = [f for f in falls if f > r]
        if later_falls and any(r2 > later_falls[0] for r2 in rises[k + 1:]):
            cuts.append(int(np.floor(r)) - 1)      # MATLAB uses floor(crossing time) as a 1-based index
    cuts = sorted({c for c in cuts if 0 < c < n})
    edges = [0] + cuts + [n]
    return [(edges[i], edges[i + 1] - 1) for i in range(len(edges) - 1)]


# ════════════════════════════════════════════════════════════════════════════
# The pipeline
# ════════════════════════════════════════════════════════════════════════════

def samples(seconds, fs):
    return max(1, int(round(float(seconds) * float(fs))))


def chunks_for(x, fs, window_s=WINDOW_S, slice_by_state=False):
    return split_signal(x) if slice_by_state else fixed_windows(len(x), samples(window_s, fs))


def detect_from_omega(x, omega, fs=1.0, thr=THR, peak_width_s=PEAK_WIDTH_S,
                      window_s=WINDOW_S, slice_by_state=False):
    """Everything after Omega, chunk by chunk (imMain.m's inner loop without
    the transform). `omega` is any per-sample score aligned to `x`; a chunk
    whose score is not finite throughout is skipped and counted.

    Returns `(spikes, info)`; `info` holds every intermediate region set in
    span indices, inclusive: `chunks`, `B` (wavelet regions), `C` (spike
    candidates), `D` (pseudo-spikes), `R` (envelope regions), `R_kept`,
    `peaks`, `valleys`, `chunks_skipped`."""
    x = np.asarray(x, dtype=float).ravel()
    omega = np.asarray(omega, dtype=float).ravel()
    pw = samples(peak_width_s, fs)
    chunks = chunks_for(x, fs, window_s, slice_by_state)
    info = {"chunks": chunks, "B": [], "C": [], "D": [], "R": [], "R_kept": [],
            "peaks": [], "valleys": [], "chunks_skipped": 0}
    spikes = []
    for c0, c1 in chunks:
        w = omega[c0:c1 + 1]
        xc = x[c0:c1 + 1]
        if len(xc) < 4 or not np.isfinite(w).all():
            info["chunks_skipped"] += 1
            continue
        B, pk, vl = wavelet_regions(w, thr=thr, peak_width=pw)
        C, D = cluster_regions(xc, B, peak_width=pw)
        R, delta, _mid = envelope_regions(xc, peak_width=pw)
        S, R_kept = locate_spikes(C, R, delta)
        shift = lambda regs: [(a + c0, b + c0) for a, b in regs]
        info["B"] += shift(B); info["C"] += shift(C); info["D"] += shift(D)
        info["R"] += shift(R); info["R_kept"] += shift(R_kept)
        info["peaks"] += [int(p) + c0 for p in pk]; info["valleys"] += [int(v) + c0 for v in vl]
        spikes += shift(S)
    return spikes, info


def transform(x, fs=1.0, window_s=WINDOW_S, slice_by_state=False, eta=ETA, beta=BETA, gamma=GAMMA):
    """The scaled scalogram of the whole span, chunk by chunk, on ONE frequency
    grid (the grid `cwt` builds for a chunk of the nominal window length), rows
    ordered LOW to HIGH frequency. Returns `(image float32 (rows, n), freqs_hz, chunks)`."""
    x = np.asarray(x, dtype=float).ravel()
    n = len(x)
    chunks = chunks_for(x, fs, window_s, slice_by_state)
    scales = morse_scales(min(samples(window_s, fs), n) if not slice_by_state else samples(window_s, fs),
                          beta=beta, gamma=gamma)
    freqs = scale_frequencies(scales, fs=fs, beta=beta, gamma=gamma)
    img = np.full((len(scales), n), np.nan, dtype=np.float32)
    for c0, c1 in chunks:
        if c1 - c0 + 1 < 4:
            continue
        # written through the reversed view: row 0 of `img` is the lowest frequency
        scaled_scalogram(x[c0:c1 + 1], scales, eta=eta, beta=beta, gamma=gamma, out=img[::-1, c0:c1 + 1])
    return img, freqs[::-1], chunks


def detect_spikes(x, fs=1.0, thr=THR, peak_width_s=PEAK_WIDTH_S, window_s=WINDOW_S,
                  slice_by_state=False, low_band_fraction=LOW_BAND_FRACTION,
                  eta=ETA, beta=BETA, gamma=GAMMA):
    """The whole detector: transform, Omega over the authors' low band, regions.
    Returns `(spikes, pseudo_spikes, info)`; `info` adds `omega`, `freqs`."""
    img, freqs, _ = transform(x, fs=fs, window_s=window_s, slice_by_state=slice_by_state,
                              eta=eta, beta=beta, gamma=gamma)
    omega = img[low_band_rows(freqs, low_band_fraction)].astype(float).sum(axis=0)
    spikes, info = detect_from_omega(x, omega, fs=fs, thr=thr, peak_width_s=peak_width_s,
                                     window_s=window_s, slice_by_state=slice_by_state)
    info["omega"], info["freqs"] = omega, freqs
    return spikes, info["D"], info
