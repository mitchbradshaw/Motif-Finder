"""
spike_analysis.py
=================
Adamatzky's neighbourhood-average spike detector (Adamatzky et al. 2023,
*Multiscalar electrical spiking in Schizophyllum commune*, Sci Rep 13:12808),
as `detection.spike_v1` runs it.

The rule, in plain words: compare each sample with the average of the samples
around it; a sample that stands out from that local average by more than a
threshold is a spike; of spikes closer together than a refractory gap, keep
the first.

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
4. **Vectorised.** The mean is a cumulative sum (O(n), a 2.6 M-sample channel in
   well under a second) and the refractory filter jumps by ``searchsorted`` from
   each kept spike, so its cost is the number of spikes kept, not of candidates.

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


def refractory_filter(candidates, d):
    """Keep the first candidate, then the first at least ``d`` samples after the
    last kept one, and so on (the paper's refractory-period filter)."""
    c = np.asarray(candidates, dtype=np.int64)
    if c.size == 0:
        return np.array([], dtype=int)
    kept = [int(c[0])]
    j = 0
    while True:
        j = int(np.searchsorted(c, kept[-1] + int(d), side="left"))
        if j >= c.size:
            break
        kept.append(int(c[j]))
    return np.array(kept, dtype=int)


def spike_detection_v1(x, width=20, delta=0.01, d=30, polarity="both"):
    """
    Spike detection (Adamatzky 2023), signed - see the module docstring.

    a_i  = mean of the finite x_j with i-2w <= j <= i+2w
    dev_i = x_i - a_i
    candidate if  |dev_i| > delta  (both) · dev_i > delta  (up) · dev_i < -delta  (down)
    then any candidate within d samples of the last kept spike is dropped.

    Paper defaults for S. commune fast spikes: w = 20, delta = 0.01 (mV), d = 30.

    Parameters
    ----------
    x        : array-like  the signal, in its stored unit
    width    : int         neighbourhood half-width w (the window is 4w+1 samples)
    delta    : float       threshold, in the SAME unit as x
    d        : int         minimum distance between kept spikes, samples
    polarity : str         'both' | 'up' | 'down'

    Returns
    -------
    spike_indices : np.ndarray  sorted sample indices of the kept spikes
    """
    if polarity not in POLARITIES:
        raise ValueError(f"polarity must be one of {POLARITIES}, got {polarity!r}")
    return refractory_filter(spike_candidates(spike_deviation(x, width), delta, polarity), d)


def spike_candidates(dev, delta, polarity="both"):
    """The indices whose deviation passes the threshold in the chosen direction (NaN never passes)."""
    if polarity not in POLARITIES:
        raise ValueError(f"polarity must be one of {POLARITIES}, got {polarity!r}")
    dev = np.asarray(dev, dtype=float)
    with np.errstate(invalid="ignore"):
        hit = np.abs(dev) > delta if polarity == "both" else dev > delta if polarity == "up" else dev < -delta
    return np.flatnonzero(hit)


def compute_spike_statistics(x, spikelocs):
    """
    Function to compute some statistics about the spikes inside a sequence x

    """

    # -- Average duration of spike (median, std)

    # -- Average amplitude of spike (median, std)

    # -- Average distance between spikes (median, std)
