"""
spike_analysis.py
=================
Adamatzky's neighbourhood-average spike detector (Adamatzky et al. 2023,
*Multiscalar electrical spiking in Schizophyllum commune*, Sci Rep 13:12808),
as `detection.spike_v1` runs it.

The rule, in plain words: compare each sample with the average of the samples
around it; a sample that stands out from that local average by more than a
threshold is a candidate; candidates closer together than a refractory gap are
one spike, placed at its most extreme sample.

Departures from the paper's printed rule (fixup-ak, 2026-10-15), each forced by
our data:

1. **A signed deviation, with a polarity.** The paper tests
   ``|x_i| - |a_i| > delta``. On a recording whose baseline sits away from zero
   (M2 sits near -0.4 V, other channels at +/-2 V) that sees only one direction:
   below zero a dip makes ``|x|`` larger and passes while a rise never can, and
   above zero the reverse - which direction is visible depends on the sign of
   the DC offset, not on the biology. Here the deviation is ``x_i - a_i`` and
   ``polarity`` picks ``both`` (``|x_i - a_i| > delta``), ``up``
   (``x_i - a_i > delta``) or ``down`` (``x_i - a_i < -delta``). On a baseline
   at zero, ``up`` is the paper's test for positive samples.
2. **The true local mean.** The paper's ``a_i = (4w)^-1 * sum_{i-2w<=j<=i+2w} x_j``
   divides 4w+1 samples by 4w, which biases ``a_i`` by baseline/(4w) - 25 mV on
   a 2 V baseline at w = 20, larger than the spikes - and divides the shorter
   windows at the ends by 4w too. The unsigned test hid that (both sides moved
   together); a signed one cannot, so ``a_i`` is the mean of the samples the
   window actually holds.
3. **Gaps are skipped.** A NaN sample is never a spike and never enters a
   neighbour's mean (the project's NaN policy: skip the gaps).
4. **One spike per cluster, at the event, not keep-first** (fix round, the
   critic's measurement). An event lowers (or raises) the local mean of every
   sample within 2w of it, so its neighbours stand out the OTHER way: a halo of
   false candidates up to 2w either side. The paper's refractory filter keeps
   the FIRST candidate - the halo's leading edge - so a 10 mV x 10 s dip came out
   as three "rises" at [967, 997, 1027], a 30 mV x 3 s dip was never kept, and a
   60 s-wide spike was counted three times, 11 s before its peak. Here the
   candidates (``|x - a| > delta``) are chained into clusters wherever
   consecutive ones are closer than d samples; each cluster is ONE spike, at the
   sample that stands furthest from the baseline around the cluster (the mean
   of the finite x within 2w outside it on either side - outside the cluster x
   is baseline even where the halo's mean is not), and its sign is that
   sample's side of the baseline. ``polarity`` then keeps clusters, never
   candidates, so a dip's halo can no longer be reported as a rise. Two real
   spikes closer than d are one spike (as the refractory gap always made them).
5. **Vectorised.** The mean and the cluster baselines are cumulative sums and the
   per-cluster extreme a ``reduceat``: a 2.6 M-sample channel in ~0.2 s.

``delta`` here is in the samples' own unit; the adapter converts the
researcher's millivolts by the recording's declared unit.
"""
import numpy as np

POLARITIES = ("both", "up", "down")


def neighbourhood_mean(x, width):
    """The mean of ``x[i-2w .. i+2w]`` (clipped to the signal) for every i,
    over the finite samples the window holds; NaN where it holds none.

    A cumulative sum of the samples less their own mean (so a 2 V baseline over
    millions of samples does not cost the sum its precision)."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n == 0:
        return np.empty(0)
    h = 2 * int(width)
    ok = np.isfinite(x)
    centre = float(np.mean(x[ok])) if ok.any() else 0.0
    c = np.concatenate(([0.0], np.cumsum(np.where(ok, x - centre, 0.0))))
    k = np.concatenate(([0], np.cumsum(ok)))
    i = np.arange(n)
    lo = np.maximum(0, i - h)
    hi = np.minimum(n, i + h + 1)
    cnt = k[hi] - k[lo]
    with np.errstate(invalid="ignore", divide="ignore"):
        m = (c[hi] - c[lo]) / cnt + centre
    m[cnt == 0] = np.nan
    return m


def spike_deviation(x, width):
    """``x_i - a_i``: how far each sample stands from its local mean (NaN at a gap)."""
    x = np.asarray(x, dtype=float)
    return x - neighbourhood_mean(x, width)


def _range_sums(x, lo, hi):
    """Sum and count of the finite x over each half-open [lo, hi) (cumulative sums, centred for precision)."""
    ok = np.isfinite(x)
    centre = float(np.mean(x[ok])) if ok.any() else 0.0
    c = np.concatenate(([0.0], np.cumsum(np.where(ok, x - centre, 0.0))))
    k = np.concatenate(([0], np.cumsum(ok)))
    cnt = k[hi] - k[lo]
    return c[hi] - c[lo] + centre * cnt, cnt


def cluster_spikes(x, candidates, d, width):
    """Chain candidates closer than ``d`` samples into clusters; each cluster is one spike at the sample furthest
    from the baseline around it (module docstring, departure 4).

    Returns ``(indices, signs, excess)``: the spike's sample, +1 / -1 for its side of the baseline, and
    ``x[index] - baseline`` in the samples' unit."""
    x = np.asarray(x, dtype=float)
    c = np.asarray(candidates, dtype=np.int64)
    if c.size == 0:
        return np.array([], dtype=int), np.array([], dtype=int), np.array([])
    n = len(x)
    h = 2 * int(width)
    brk = np.flatnonzero(np.diff(c) >= int(d))
    cs = c[np.concatenate(([0], brk + 1))]
    ce = c[np.concatenate((brk, [c.size - 1]))]
    sl, nl = _range_sums(x, np.maximum(0, cs - h), cs)
    sr, nr = _range_sums(x, np.minimum(n, ce + 1), np.minimum(n, ce + 1 + h))
    tot = nl + nr
    with np.errstate(invalid="ignore", divide="ignore"):
        base = (sl + sr) / tot
    lengths = ce - cs + 1
    offsets = np.concatenate(([0], np.cumsum(lengths)[:-1]))
    rep = np.repeat(np.arange(cs.size), lengths)
    pos = cs[rep] + (np.arange(int(lengths.sum())) - offsets[rep])
    xv = x[pos]
    none = tot == 0          # a cluster with no finite sample around it: its own median is the baseline
    if none.any():
        for k in np.flatnonzero(none):
            seg = xv[offsets[k]:offsets[k] + lengths[k]]
            base[k] = np.nanmedian(seg) if np.isfinite(seg).any() else 0.0
    dev = np.abs(xv - base[rep])
    dev[~np.isfinite(dev)] = -1.0
    best = np.maximum.reduceat(dev, offsets)
    hit = dev == best[rep]
    _, first = np.unique(rep[hit], return_index=True)
    idx = pos[np.flatnonzero(hit)[first]]
    excess = x[idx] - base
    return idx.astype(int), np.where(excess < 0, -1, 1).astype(int), excess


def spike_candidates(dev, delta):
    """The indices whose deviation stands more than ``delta`` from the local mean, either way (NaN never does)."""
    dev = np.asarray(dev, dtype=float)
    with np.errstate(invalid="ignore"):
        return np.flatnonzero(np.abs(dev) > delta)


def detect_spikes(x, width=20, delta=0.01, d=30, polarity="both"):
    """The whole rule: ``(indices, signs, excess)`` of the kept spikes (module docstring)."""
    if polarity not in POLARITIES:
        raise ValueError(f"polarity must be one of {POLARITIES}, got {polarity!r}")
    x = np.asarray(x, dtype=float)
    idx, sign, excess = cluster_spikes(x, spike_candidates(spike_deviation(x, width), delta), d, width)
    keep = np.ones(idx.size, dtype=bool) if polarity == "both" else sign > 0 if polarity == "up" else sign < 0
    return idx[keep], sign[keep], excess[keep]


def spike_detection_v1(x, width=20, delta=0.01, d=30, polarity="both"):
    """
    Spike detection (Adamatzky 2023), signed and clustered - see the module docstring.

    a_i   = mean of the finite x_j with i-2w <= j <= i+2w
    candidate if |x_i - a_i| > delta
    candidates closer than d samples are one spike, at the sample furthest from the baseline around them;
    polarity ('both' | 'up' | 'down') keeps spikes by that sample's side of the baseline.

    Paper defaults for S. commune fast spikes: w = 20, delta = 0.01 (mV), d = 30.
    ``delta`` is in the SAME unit as x. Returns the sorted sample indices of the kept spikes.
    """
    return detect_spikes(x, width, delta, d, polarity)[0]


def compute_spike_statistics(x, spikelocs):
    """
    Function to compute some statistics about the spikes inside a sequence x

    """

    # -- Average duration of spike (median, std)

    # -- Average amplitude of spike (median, std)

    # -- Average distance between spikes (median, std)
