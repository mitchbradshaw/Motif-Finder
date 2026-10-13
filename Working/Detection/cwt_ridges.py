"""
cwt_ridges.py
==============
Multi-scale peaks and troughs by continuous-wavelet-transform ridge lines —
Du, Kibbe & Lin (2006), "Improved peak detection in mass spectrum by
incorporating continuous wavelet transform-based pattern matching",
*Bioinformatics* 22(17):2059-2065, doi:10.1093/bioinformatics/btl355.

In plain words: slide a "Mexican hat" template along the trace at many sizes.
A real event lights the template up over a whole run of neighbouring sizes;
noise only at the smallest. The bright points are joined across sizes into
ridge lines and the long, strong ones are kept. The size at which a ridge is
brightest is that event's own width, so one pass finds events of every
duration, each with its scale. The hat has zero mean and zero first moment,
so a constant offset and a straight drift cancel without a detrend window.

The paper's steps, as implemented
---------------------------------
1. **CWT with the Mexican hat (Ricker)** over a geometric range of scales,
   normalised by `1/a` (the paper: `1/sqrt(a)`; see A0). Each
   wavelet is truncated to `[-5a, 5a]` (the paper's support [-5, 5]) and its
   discrete mean removed so a constant cancels exactly. Convolution is by FFT.
2. **Local maxima per scale** in a window of `+/- a` samples (proportional to
   the scale), positive coefficients only.
3. **Ridge lines**, linked from the largest scale down: every ridge takes the
   nearest maximum at the next smaller scale within `0.5 a` samples (a
   maximum claimed by two ridges goes to the nearer); a ridge that finds none
   counts a gap and ends after `max_gap_scales` consecutive gaps; a maximum
   no ridge claims starts a new ridge.
4. **A peak needs** (a) a ridge of at least `min_ridge_scales` points, (b)
   the scale of the ridge maximum strictly inside the ridge's scale range
   (a maximum at the smallest scale is noise; at the largest, an event wider
   than the range — both are counted, not reported), (c) SNR >= `min_snr`,
   where signal = **the maximum coefficient on the ridge** and noise = **the
   95th percentile of |coefficients| at the smallest scale** in a local window
   of `noise_window_s` around the peak, floored (see `NOISE_FLOOR_FRAC`).
5. **Location** from the ridge at its small-scale end; **width from the scale
   of the ridge maximum**.

`scipy.signal.find_peaks_cwt` is NOT used: it is not the paper's algorithm
(its noise is the 10th percentile of the *signed* smallest-scale
coefficients and its SNR numerator the smallest-scale coefficient, not the
ridge maximum; it has no scale-range test and no width) —
`docs/research/analysis-blocks-primary-sources.md` §7. scipy's public
`cwt` / `ricker` are gone in 1.17, so the Ricker is written here.
`scipy.signal.find_peaks` is used only to find the maxima of one ridge's
coefficient profile over scale (A6).

Adaptations our data force (each a deviation from the paper, with its reason)
------------------------------------------------------------------------------
A0. **Normalisation 1/a, not the paper's 1/sqrt(a).** Under 1/sqrt(a) an
    event's coefficient grows with its width (as sqrt(width)) and its profile
    over scale is flat-topped (within 1 % from 2 to 3 standard deviations)
    and decays only as a^-1/2 past its best scale, so on a day of events with
    curved drift the profile of a 43-min trough was overtaken at the largest
    scales by its neighbours' lobes: measured over 20 synthetic days, 2
    missed and a worst duration error of 1.45x. Under 1/a an event's peak
    coefficient is 0.84 x its amplitude whatever its width (SNR reads as
    height over noise), its profile decays as 1/a past the peak, and white
    noise shrinks with scale (a^-1/2): 0 missed, worst 1.18x, and fewer
    large-scale false ridges. The ridge, SNR and width steps are the paper's.
A1. **Scales in seconds** (`min_scale_s`=10, `max_scale_s`=7200, `n_scales`=40,
    geometric). Mass spectra are indexed by m/z points; our recordings are
    1 Hz to 10 Hz traces whose events last 20 s to hours. A scale is
    converted to samples at the recording's fs. Scales whose main lobe would
    not fit in the span (`a > n/4` samples) are dropped and counted.
A2. **Polarity** (`spike` / `drop` / `both`). The paper looks for positive
    peaks only; a fungal trace has troughs as well, which are maxima of the
    negated coefficients. Both polarities are always traced so that one can
    veto the other's side lobes (A7); `polarity` only filters what is
    reported.
A3. **Long spans**: processed in **overlapping chunks** (`chunk_samples`,
    default 2^21). Inside a chunk the transform is streamed scale by scale and
    only each scale's maxima, the smallest scale's row and a coarse
    scalogram are kept, so memory is O(chunk), never O(n x n_scales). Each
    chunk is extended on both sides by `overlap = 5a_max` (exact
    coefficients) `+ 4a_max` (the farthest a ridge can wander sideways from
    the largest scale to the smallest) `+ noise_window/2`, and reports only
    the events located in its own core, so chunked and unchunked processing
    agree (tested).
A4. **Span edges**: the span is extended by odd (point) reflection, which
    continues a straight drift instead of folding it into a kink (an even
    reflection turns a slope into a V, which the hat reads as an event at
    the edge). An event whose wavelet support at its best scale (`+/- 5a`)
    crosses a span edge is kept and flagged (`edge_flag`).
A5. **Asymmetric events** (a sharkfin) put the ridge's centre toward the slow
    side; the block reports the scale and an approximate extent and leaves
    onset timing to `interrogation.event_shape` downstream.
A6. **Nested events.** A fast event on top of a slow one shares one ridge;
    the paper reports one peak per ridge. Here every interior maximum of the
    ridge's coefficient profile over scale is a separate event, each with its
    own best scale, location and SNR, if it passes `min_snr` and stands at
    least `PROMINENCE_SNR` x the local noise above the saddle between it and
    its neighbour (the plan: "nested events give two ridges at two scales ...
    needs a rule"). Where the profile is cut off by the scale range (or the
    ridge's own end) on one side, that side says nothing and only the other
    side's depth counts. Tested: a 24 s spike on a twice-as-tall 8 min bump,
    centred or off-centre, and on a three-times-as-tall 43 min one, is two
    events at two scales.
A7. **Side lobes.** The hat's negative side lobes make every strong spike
    produce two weaker trough ridges beside it (at 2e^-1.5 = 0.45 of its
    coefficient) and vice versa; the paper never sees them because it looks
    for one polarity. A candidate is dropped as a side lobe when, at its own
    best scale, the opposite polarity reaches at least `1/SIDELOBE_RATIO`
    times its coefficient within `SIDELOBE_REACH` scales of it. This is read
    off the opposite polarity's coefficient maxima, so a parent that was not
    itself reported still vetoes its lobes. A genuine opposite event that
    close to, and that much weaker than, its neighbour is dropped too.
A8. **Duplicates.** A ridge broken by more than `max_gap_scales` gaps is two
    ridges and can report one event twice; of two same-polarity events
    closer than half a scale with best scales within a factor of 1.5, the
    stronger is kept.
A9. **Location robust to noise.** The paper takes the ridge's position at
    its smallest scale; on a slow event the small-scale end of the ridge is
    pure noise and wanders. Here the location is the ridge's position at
    the smallest scale of the event's own band whose coefficient is still at
    least half the event's peak coefficient — the paper's rule wherever the
    event dominates its smallest scales.
A10. **Best scale refined** by a parabola through the profile's top three
    points in log-scale (the grid is ~18 % per step at the defaults).
A14. **Step pairs.** An abrupt edge (a fall over less than a minute, the
    front of a sharkfin) is a spike-shaped corner above it and a drop-shaped
    corner below it, of equal strength, at one scale: the hat reports both.
    Neither is dropped; an event whose own best scale holds an opposite-
    polarity coefficient between 0.6 and 1/0.6 of its own within 2.5 scales
    (comparable on both sides: not a side lobe either way) is flagged
    `step_pair`.
A11. **NaN samples** are filled by linear interpolation for the transform
    only, and an event whose support overlaps a filled sample is flagged
    (`nan_in_support`); the count is in the result.
A12. **A per-scale coefficient baseline.** The hat has zero mean and zero
    first moment but not zero second moment, so a curved drift (quadratic,
    or any slow bend) adds an offset of about `-4.3 c a^2` (for `c t^2`)
    that grows with scale and can carry a slow trough's profile on rising to
    the largest scale (no interior maximum: missed). Each scale's
    coefficients have their running median over `+/- 10 a` subtracted (taken
    on a grid of `a/4` samples aligned to the span and interpolated back). A
    curved drift is nearly constant along a row and goes; an event, narrower
    than the window, stays. At small scales a slow event is itself "drift"
    and is subtracted there, which helps a fast event on top of it stand out.
A13. **Composites.** At scales comparable to the spacing of events, the hat
    spans several of them and a ridge can describe their arrangement (a
    spike between two troughs is a hump at a scale several times larger).
    Such a ridge is reported like any other; most reach a span edge and are
    flagged. Keep `max_scale_s` below the typical spacing to avoid them.

Duration rule (calibrated in `tests/test_cwt_ridges.py`): for a Gaussian bump
of standard deviation s, the 1/a-normalised Ricker response at its centre is
`A s a^2 / (a^2 + s^2)^1.5` (times a constant), maximal at `a* = sqrt(2) s`;
its FWHM is `2 sqrt(2 ln 2) s`. So **duration_s = FWHM = 2 sqrt(ln 2) a* =
1.665 x best_scale_s**. The reported span is
`peak +/- duration_s` (twice the FWHM: the bump with its shoulders, about
+/- 2.1 standard deviations, so Event shape downstream can find an onset).

No UI imports; numpy and scipy only.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy import fft as sfft
from scipy.ndimage import maximum_filter1d, median_filter
from scipy.signal import find_peaks

POLARITIES = ("both", "spike", "drop")
SUPPORT_MULT = 5.0           # wavelet truncated to [-5a, 5a] (the paper's support)
LOCAL_MAX_MULT = 1.0         # local-maximum window: +/- 1.0 a
LINK_MULT = 0.5              # ridge linking tolerance: 0.5 a of the larger scale
RIDGE_REACH_MULT = 4.0       # lateral wander of a ridge from top to bottom, in a_max
NOISE_PERCENTILE = 95.0
NOISE_FLOOR_FRAC = 0.05      # local noise floored at 5 % of the span's own smallest-scale p95 ...
ROUNDOFF_FLOOR = 1e-9        # ... and above FFT round-off on a flat trace (relative to max |x|)
SIDELOBE_RATIO = 0.6         # a side lobe is <= 0.45 of its parent; 0.6 leaves a margin
SIDELOBE_REACH = 2.5         # a side lobe sits within ~1.9 a* of its parent
DUP_DISTANCE = 0.5           # duplicates: closer than 0.5 scale ...
DUP_SCALE_RATIO = 1.5        # ... with best scales within 1.5x
BASELINE_MULT = 10.0         # A12: each scale's coefficient baseline is its running median over +/- 10 a
BASELINE_STEP = 0.25         # ... taken on a grid of a/4 samples, aligned to the span, then interpolated
PROMINENCE_SNR = 1.0         # A6: a profile maximum must stand >= 1 x the local noise above its saddle
HALF_PEAK = 0.5              # A9: location at the smallest scale still >= half the peak
FWHM_PER_SCALE = 2.0 * np.sqrt(np.log(2.0))       # 1.6651: FWHM of a Gaussian / its best 1/a scale
DEFAULT_CHUNK = 2 ** 21
SCALOGRAM_COLUMNS = 4096
MAX_RIDGES_IN_META = 500

DEFAULTS = dict(min_scale_s=10.0, max_scale_s=7200.0, n_scales=40, polarity="both", min_snr=3.0,
                min_ridge_scales=6, max_gap_scales=3, noise_window_s=3600.0)


def ricker(a, support_mult=SUPPORT_MULT):
    """The Mexican hat at scale `a` samples, normalised by 1/a (A0), truncated to
    `[-support_mult a, support_mult a]`, discrete mean removed."""
    h = max(1, int(np.ceil(support_mult * a)))
    k = np.arange(-h, h + 1, dtype=float) / a
    w = (2.0 / (np.sqrt(3.0) * np.pi ** 0.25)) * (1.0 - k * k) * np.exp(-0.5 * k * k) / a
    return w - w.mean()


def scales_seconds(min_scale_s, max_scale_s, n_scales):
    return np.geomspace(float(min_scale_s), float(max_scale_s), int(n_scales))


def rules():
    return [
        {"name": "scale", "rule": "the Mexican-hat (Ricker) scale a, in seconds; CWT normalised by 1/a (the paper "
                                  "uses 1/sqrt(a)), wavelet truncated to +/- 5a (Du, Kibbe & Lin 2006)"},
        {"name": "best_scale_s", "rule": "the scale at which the ridge's coefficient is largest, refined by a "
                                         "parabola in log-scale through the top three ridge points"},
        {"name": "duration_s", "rule": "FWHM of a Gaussian bump whose Ricker response peaks at best_scale_s: "
                                       "duration_s = 2*sqrt(ln 2) * best_scale_s = 1.665 * best_scale_s"},
        {"name": "span", "rule": "peak_idx +/- duration_s (twice the FWHM), clipped to the span"},
        {"name": "snr", "rule": "the largest coefficient on the ridge (within the event's scale band) / the 95th "
                                "percentile of |coefficients| at the smallest scale in a noise_window_s window "
                                "centred within noise_window_s/32 of the peak, floored at 5 % of that percentile "
                                "over the whole span"},
        {"name": "coefficient baseline", "rule": "each scale's coefficients minus their running median over "
                                                 "+/- 10 scales, so a curved drift (which the hat does not cancel) "
                                                 "goes and an event stays"},
        {"name": "peak_idx", "rule": "the ridge's position at the smallest scale of the event's band whose "
                                     "coefficient is still >= half the event's peak (span-relative)"},
        {"name": "ridge_scales", "rule": "number of scales the ridge has a maximum on (gaps excluded)"},
        {"name": "polarity", "rule": "+1 spike (a maximum of the coefficients), -1 drop (a maximum of the negated "
                                     "coefficients) — Event shape's encoding; ridge_polarity says it in words "
                                     "and survives Event shape, which re-measures `polarity`"},
        {"name": "edge_flag", "rule": "the wavelet's support at best_scale_s (+/- 5a) crosses a span edge, where "
                                      "the trace was extended by odd reflection"},
        {"name": "side lobe", "rule": "a candidate is dropped when, at its own best scale, the opposite polarity "
                                      "reaches >= 1/0.6 times its coefficient within 2.5 scales of it (the hat's "
                                      "negative lobes are 0.45 of its peak)"},
        {"name": "nested", "rule": "every maximum of a ridge's coefficient profile over scale that passes min_snr "
                                   "and stands >= 1 x the local noise above its saddle is its own event (a fast "
                                   "event on a slow one)"},
        {"name": "step_pair", "rule": "at the event's best scale, an opposite-polarity coefficient within 2.5 "
                                      "scales is between 0.6 and 1/0.6 of its own: it may be one corner of an "
                                      "abrupt edge (a sharkfin's fall), not an event of its own"},
        {"name": "duplicate", "rule": "of two same-polarity events closer than half a scale with best scales "
                                      "within 1.5x, the stronger is kept"},
    ]


@dataclass
class CwtRidgeResult:
    events: list                        # one dict per accepted event, sorted by peak_idx
    scales_s: np.ndarray                # the scales actually used
    scales_dropped: int                 # scales too large for the span
    counts: dict = field(default_factory=dict)
    ridges: list = field(default_factory=list)      # the strongest MAX_RIDGES_IN_META events' ridge points
    scalogram: dict = field(default_factory=dict)
    n_nan: int = 0
    n_chunks: int = 0


def _fill_nan(x):
    bad = ~np.isfinite(x)
    if not bad.any():
        return x, bad
    if bad.all():
        raise ValueError("detection.cwt_ridges: every sample of the span is NaN")
    idx = np.arange(len(x))
    y = x.copy()
    y[bad] = np.interp(idx[bad], idx[~bad], x[~bad])
    return y, bad


def _local_maxima(row, half):
    """Columns where `row` is the maximum of its +/- `half` window and positive;
    a plateau reports its first column only."""
    mf = maximum_filter1d(row, size=2 * half + 1, mode="nearest")
    m = (row == mf) & (row > 0)
    if m.any():
        prev = np.empty_like(m)
        prev[0] = False
        prev[1:] = m[:-1] & (row[1:] == row[:-1])
        m &= ~prev
    return np.flatnonzero(m)


def _trace_ridges(maxima, scales_samp, max_gap):
    """Link maxima (per scale: (cols, vals), ascending scale) into ridges from the
    largest scale down. Returns arrays (rid, j, col, val) of every ridge point."""
    S = len(maxima)
    out_r, out_j, out_c, out_v = [], [], [], []
    cols, vals = maxima[S - 1]
    n_r = len(cols)
    act_id = np.arange(n_r)
    act_col = cols.copy()
    act_gap = np.zeros(n_r, dtype=int)
    out_r.append(act_id.copy()); out_j.append(np.full(n_r, S - 1)); out_c.append(cols); out_v.append(vals)
    for j in range(S - 2, -1, -1):
        cols, vals = maxima[j]
        tol = max(1.0, LINK_MULT * scales_samp[j + 1])
        claimed = np.zeros(len(cols), dtype=bool)
        linked = np.zeros(len(act_id), dtype=bool)
        if len(cols) and len(act_id):
            pos = np.searchsorted(cols, act_col)
            left = np.clip(pos - 1, 0, len(cols) - 1)
            right = np.clip(pos, 0, len(cols) - 1)
            dl = np.abs(cols[left] - act_col)
            dr = np.abs(cols[right] - act_col)
            near = np.where(dr < dl, right, left)
            dist = np.minimum(dl, dr)
            ok = np.flatnonzero(dist <= tol)
            if ok.size:
                # a maximum claimed by several ridges goes to the nearest (then the lower ridge id)
                order = ok[np.lexsort((act_id[ok], dist[ok], near[ok]))]
                first = np.ones(order.size, dtype=bool)
                first[1:] = near[order][1:] != near[order][:-1]
                win = order[first]
                linked[win] = True
                claimed[near[win]] = True
                out_r.append(act_id[win]); out_j.append(np.full(win.size, j))
                out_c.append(cols[near[win]]); out_v.append(vals[near[win]])
                act_col[win] = cols[near[win]]
        act_gap[linked] = 0
        act_gap[~linked] += 1
        keep = act_gap <= max_gap
        act_id, act_col, act_gap = act_id[keep], act_col[keep], act_gap[keep]
        new = np.flatnonzero(~claimed)
        if new.size:
            ids = np.arange(n_r, n_r + new.size)
            n_r += new.size
            out_r.append(ids); out_j.append(np.full(new.size, j)); out_c.append(cols[new]); out_v.append(vals[new])
            act_id = np.concatenate([act_id, ids])
            act_col = np.concatenate([act_col, cols[new]])
            act_gap = np.concatenate([act_gap, np.zeros(new.size, dtype=int)])
    cat = lambda xs, dt: np.concatenate(xs).astype(dt) if xs else np.zeros(0, dtype=dt)  # noqa: E731
    return cat(out_r, np.int64), cat(out_j, np.int64), cat(out_c, np.int64), cat(out_v, float)


def _refine_scale(js, v, p, log_scales):
    """A10: the best scale by a parabola in log-scale through the top three points."""
    if 0 < p < len(v) - 1 and js[p - 1] == js[p] - 1 and js[p + 1] == js[p] + 1:
        y0, y1, y2 = v[p - 1], v[p], v[p + 1]
        den = y0 - 2.0 * y1 + y2
        if den < 0:
            off = 0.5 * (y0 - y2) / den
            off = float(np.clip(off, -0.5, 0.5))
            step = log_scales[js[p] + 1] - log_scales[js[p]] if js[p] + 1 < len(log_scales) else \
                log_scales[js[p]] - log_scales[js[p] - 1]
            return float(np.exp(log_scales[js[p]] + off * step))
    return float(np.exp(log_scales[js[p]]))


def _profile_prominence(v, p):
    """Prominence of the profile maximum `p`, one-sided where the ridge is cut off.

    Each side is searched until a higher point or the ridge's end. A side that
    reaches the end without a higher point is truncated by the scale range (or
    the ridge's own start/end), so its minimum says nothing about the event; the
    other side's depth is used. Both sides open (a global maximum): the deeper.
    Neither: the shallower, as `scipy.signal.peak_prominences` does."""
    sides = []
    for step in (-1, 1):
        i, lo, open_end = p + step, v[p], True
        while 0 <= i < len(v):
            if v[i] > v[p]:
                open_end = False
                break
            lo = min(lo, v[i])
            i += step
        sides.append((v[p] - lo, open_end))
    (dl, ol), (dr, orr) = sides
    if ol and orr:
        return max(dl, dr)
    if ol:
        return dr
    if orr:
        return dl
    return min(dl, dr)


def _candidates(rid, rj, rc, rv, scales_samp, min_ridge, min_snr, noise_at, in_core, counts):
    """Events from one polarity's ridges. `noise_at(col)` is the local noise at an
    ext-frame column; `in_core(col)` says whether a column is this chunk's to count.
    Each candidate is a dict with its ext-frame location and its ridge's points."""
    if rid.size == 0:
        return []
    order = np.lexsort((rj, rid))
    rid, rj, rc, rv = rid[order], rj[order], rc[order], rv[order]
    bounds = np.flatnonzero(np.diff(rid)) + 1
    starts = np.concatenate([[0], bounds])
    ends = np.concatenate([bounds, [rid.size]])
    lengths = ends - starts
    mine = np.array([in_core(c) for c in rc[starts]], dtype=bool)   # a ridge belongs where its small end is
    counts["ridges"] += int(mine.sum())
    long_enough = lengths >= min_ridge
    counts["ridges_too_short"] += int((~long_enough & mine).sum())
    log_scales = np.log(scales_samp)
    S = len(scales_samp)
    out = []
    for s, e, own in zip(starts[long_enough], ends[long_enough], mine[long_enough]):
        js, cs, v = rj[s:e], rc[s:e], rv[s:e]
        peaks, _ = find_peaks(v)
        if peaks.size == 0:
            if own:
                top = int(np.argmax(v))
                if js[top] == 0 or top == 0:
                    counts["max_at_smallest_scale"] += 1
                elif js[top] == S - 1 or top == len(v) - 1:
                    counts["max_at_largest_scale"] += 1
                else:
                    counts["no_interior_maximum"] += 1
            continue
        prev = None
        for p in peaks:
            prom = _profile_prominence(v, p)
            lo = 0 if prev is None else int(prev + np.argmin(v[prev:p + 1]))
            band = np.arange(lo, p + 1)
            strong = band[v[band] >= HALF_PEAK * v[p]]
            q = int(strong[0]) if strong.size else int(p)
            loc = int(cs[q])
            noise = noise_at(loc)
            if v[p] < min_snr * noise or prom < PROMINENCE_SNR * noise:
                if in_core(loc):
                    counts["below_snr" if v[p] < min_snr * noise else "shallow_maximum"] += 1
                continue
            prev = int(p)
            out.append({
                "loc": loc, "peak_coef": float(v[p]), "noise": float(noise), "snr": float(v[p] / noise),
                "best_j": int(js[p]), "best_scale": _refine_scale(js, v, p, log_scales),
                "ridge_scales": int(len(v)), "ridge_j": js.copy(), "ridge_c": cs.copy(),
            })
    return out


def _opposite_ratio(c, opposite, scales_samp):
    """A7 / A14: the strongest opposite-polarity coefficient within SIDELOBE_REACH
    scales of the candidate, at the candidate's own best scale, over the
    candidate's coefficient. Read off the opposite polarity's maxima, so a parent
    that was not itself accepted (a fast spike merged into a slow one's ridge)
    still vetoes its lobes."""
    cols, vals = opposite[c["best_j"]]
    near = np.abs(cols - c["loc"]) <= SIDELOBE_REACH * scales_samp[c["best_j"]]
    return float(vals[near].max() / c["peak_coef"]) if near.any() else 0.0


def _suppress(cands, counts, c0, c1):
    """A8 duplicates, strongest first (counted when the dropped candidate lies in
    this chunk's core [c0, c1))."""
    order = sorted(range(len(cands)), key=lambda i: -cands[i]["peak_coef"])
    kept = []
    for i in order:
        c = cands[i]
        dup = any(d["sign"] == c["sign"]
                  and 1.0 / DUP_SCALE_RATIO <= c["best_scale"] / d["best_scale"] <= DUP_SCALE_RATIO
                  and abs(c["loc"] - d["loc"]) <= DUP_DISTANCE * max(c["best_scale"], d["best_scale"])
                  for d in kept)
        if dup:
            counts["duplicates"] += int(c0 <= c["loc"] < c1)
        else:
            kept.append(c)
    return kept


def _block_extreme(vals, blocks):
    """Signed value of the largest |v| per run of equal block ids (ids non-decreasing)."""
    starts = np.concatenate([[0], np.flatnonzero(np.diff(blocks)) + 1])
    hi = np.maximum.reduceat(vals, starts)
    lo = np.minimum.reduceat(vals, starts)
    return blocks[starts], np.where(np.abs(hi) >= np.abs(lo), hi, lo)


def detect(x, fs, *, min_scale_s=10.0, max_scale_s=7200.0, n_scales=40, polarity="both", min_snr=3.0,
           min_ridge_scales=6, max_gap_scales=3, noise_window_s=3600.0,
           chunk_samples=DEFAULT_CHUNK, keep_ridges=True):
    """Find multi-scale peaks and troughs in `x` (one span, sampled at `fs`).

    Returns a `CwtRidgeResult`; every index in it is span-relative."""
    if polarity not in POLARITIES:
        raise ValueError(f"detection.cwt_ridges: polarity must be one of {POLARITIES}, got {polarity!r}")
    fs = float(fs)
    if not max_scale_s > min_scale_s:
        raise ValueError(f"detection.cwt_ridges: max_scale_s ({max_scale_s:g}) must exceed min_scale_s ({min_scale_s:g})")
    if min_scale_s * fs < 1.0:
        raise ValueError(f"detection.cwt_ridges: min_scale_s={min_scale_s:g} s is below one sample at {fs:g} Hz")
    x = np.asarray(x, dtype=float).ravel()
    n = len(x)
    all_scales = scales_seconds(min_scale_s, max_scale_s, n_scales)
    fit = all_scales * fs <= n / 4.0
    scales_s = all_scales[fit]
    dropped = int((~fit).sum())
    counts = {k: 0 for k in ("ridges", "ridges_too_short", "max_at_smallest_scale", "max_at_largest_scale",
                             "no_interior_maximum", "below_snr", "shallow_maximum", "side_lobes",
                             "duplicates")}
    if len(scales_s) < 3:
        return CwtRidgeResult(events=[], scales_s=scales_s, scales_dropped=dropped, counts=counts,
                              scalogram={}, n_nan=int((~np.isfinite(x)).sum()))
    xf, bad = _fill_nan(x)
    S = len(scales_s)
    a = scales_s * fs                                   # scales in samples
    halves = [max(1, int(np.ceil(SUPPORT_MULT * aj))) for aj in a]
    P = halves[-1]
    xp = np.pad(xf, P, mode="reflect", reflect_type="odd") if n > 1 else np.pad(xf, P, mode="edge")
    W = max(1, int(round(noise_window_s * fs)))
    noise_step = max(1, W // 16)
    Q = P + int(np.ceil((RIDGE_REACH_MULT + BASELINE_MULT) * a[-1])) + W // 2 + 2
    chunk = max(int(chunk_samples), 1)

    # global smallest-scale |coefficient| percentile, for the noise floor: needs row 0 everywhere,
    # which is cheap (the smallest wavelet) — computed once over the whole padded span
    w0 = ricker(a[0])
    row0_all = np.abs(_conv_same(xp, w0)[P:P + n])
    floor = max(NOISE_FLOOR_FRAC * float(np.percentile(row0_all, NOISE_PERCENTILE)),
                ROUNDOFF_FLOOR * float(np.max(np.abs(xf))) * np.sqrt(a[-1]), 1e-300)

    n_cols = min(SCALOGRAM_COLUMNS, n)
    per_col = int(np.ceil(n / n_cols))
    n_cols = int(np.ceil(n / per_col))
    scal = np.zeros((S, n_cols), dtype=np.float32)
    scal_abs = np.full((S, n_cols), -1.0)

    events = []
    ridges_meta = []
    n_chunks = 0
    for c0 in range(0, n, chunk):
        c1 = min(n, c0 + chunk)
        n_chunks += 1
        e0, e1 = max(-P, c0 - Q), min(n + P, c1 + Q)           # ext region, span coordinates
        seg = xp[e0 + P:e1 + P]
        L = len(seg)
        nfft = sfft.next_fast_len(L + 2 * P + 1, real=True)
        X = sfft.rfft(seg, nfft)
        max_pos, max_neg = [], []
        core = slice(c0 - e0, c1 - e0)
        for j in range(S):
            w = ricker(a[j])
            h = halves[j]
            row = sfft.irfft(X * sfft.rfft(w, nfft), nfft)[h:h + L]
            row = row - _row_baseline(row, e0, a[j])
            half = max(1, int(round(LOCAL_MAX_MULT * a[j])))
            cp = _local_maxima(row, half)
            cn = _local_maxima(-row, half)
            max_pos.append((cp, row[cp]))
            max_neg.append((cn, -row[cn]))
            # coarse scalogram over this chunk's core
            g = np.arange(c0, c1)
            ids, ext = _block_extreme(row[core], g // per_col)
            better = np.abs(ext) > scal_abs[j, ids]
            scal[j, ids[better]] = ext[better]
            scal_abs[j, ids[better]] = np.abs(ext[better])
            if j == 0:
                row0 = np.abs(row)
        cands = []

        noise_cache = {}

        def noise_at(col, row0=row0, e0=e0, cache=noise_cache):
            # the window is centred on the grid point (every W/16 samples, aligned to the span) nearest
            # the peak, so one percentile serves every candidate near it and a chunk agrees with the span
            g = int(round((col + e0) / noise_step)) * noise_step
            if g not in cache:
                lo = max(0, g - W // 2, e0) - e0
                hi = min(n, g + W // 2 + 1, e0 + len(row0)) - e0
                cache[g] = max(float(np.percentile(row0[lo:max(hi, lo + 1)], NOISE_PERCENTILE)), floor)
            return cache[g]

        def in_core(col, e0=e0, c0=c0, c1=c1):
            return c0 <= col + e0 < c1

        for sign, maxima in ((1, max_pos), (-1, max_neg)):
            rid, rj, rc, rv = _trace_ridges(maxima, a, int(max_gap_scales))
            for cd in _candidates(rid, rj, rc, rv, a, int(min_ridge_scales), float(min_snr), noise_at, in_core,
                                  counts):
                cd["sign"] = sign
                ratio = _opposite_ratio(cd, max_neg if sign > 0 else max_pos, a)
                if ratio * SIDELOBE_RATIO >= 1.0:          # the opposite side is >= 1/0.6 as strong
                    counts["side_lobes"] += int(in_core(cd["loc"]))
                    continue
                cd["step_pair"] = ratio >= SIDELOBE_RATIO     # comparable on both sides: an edge's corner
                cd["loc"] += e0                                  # ext frame -> span-relative
                cd["ridge_c"] = cd["ridge_c"] + e0
                if 0 <= cd["loc"] < n:
                    cands.append(cd)
        for cd in _suppress(cands, counts, c0, c1):
            if c0 <= cd["loc"] < c1:
                events.append(cd)

    out = []
    strongest = set(sorted(range(len(events)), key=lambda i: -events[i]["snr"])[:MAX_RIDGES_IN_META])
    for i_ev, cd in sorted(enumerate(events), key=lambda ie: (ie[1]["loc"], -ie[1]["sign"])):
        best_s = cd["best_scale"] / fs
        dur_s = FWHM_PER_SCALE * best_s
        d = max(1, int(round(dur_s * fs)))
        loc = cd["loc"]
        sup = int(np.ceil(SUPPORT_MULT * cd["best_scale"]))
        lo, hi = max(0, loc - sup), min(n, loc + sup + 1)
        ev = {
            "peak_idx": int(loc), "start": int(max(0, loc - d)), "end": int(min(n, loc + d + 1)),
            "best_scale_s": best_s, "duration_s": dur_s, "ridge_scales": cd["ridge_scales"],
            "snr": float(cd["snr"]), "peak_coef": float(cd["peak_coef"]), "noise": float(cd["noise"]),
            "polarity": int(cd["sign"]), "ridge_polarity": "spike" if cd["sign"] > 0 else "drop",
            "edge_flag": bool(loc - sup < 0 or loc + sup >= n),
            "nan_in_support": bool(bad[lo:hi].any()), "step_pair": bool(cd["step_pair"]),
        }
        if polarity == "both" or ev["ridge_polarity"] == polarity:
            out.append(ev)
            if keep_ridges and i_ev in strongest:
                ridges_meta.append({"peak_idx": int(loc), "polarity": ev["ridge_polarity"],
                                    "cols": cd["ridge_c"].tolist(), "scales_s": (scales_s[cd["ridge_j"]]).tolist()})
    return CwtRidgeResult(events=out, scales_s=scales_s, scales_dropped=dropped, counts=counts,
                          ridges=ridges_meta,
                          scalogram={"values": scal, "samples_per_column": per_col, "n_columns": n_cols},
                          n_nan=int(bad.sum()), n_chunks=n_chunks)


def _row_baseline(row, e0, a):
    """A12: the running median of one scale's coefficients over +/- BASELINE_MULT a,
    on a grid of BASELINE_STEP a samples aligned to span index 0 (so a chunk and
    the whole span sample the same columns), linearly interpolated back."""
    step = max(1, int(BASELINE_STEP * a))
    L = len(row)
    g0 = -(-e0 // step) * step                     # first grid column >= e0, in span coordinates
    cols = np.arange(g0, e0 + L, step)
    if cols.size < 2:
        return np.full(L, float(np.median(row)))
    size = 2 * int(np.ceil(BASELINE_MULT * a / step)) + 1
    med = median_filter(row[cols - e0], size=size, mode="nearest")
    return np.interp(np.arange(e0, e0 + L), cols, med)


def _conv_same(x, w):
    h = (len(w) - 1) // 2
    nfft = sfft.next_fast_len(len(x) + len(w) - 1, real=True)
    return sfft.irfft(sfft.rfft(x, nfft) * sfft.rfft(w, nfft), nfft)[h:h + len(x)]
