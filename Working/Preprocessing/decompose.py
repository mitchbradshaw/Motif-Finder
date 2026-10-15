"""
decompose.py
=============
Split a span into three layers that ADD UP to it (fixup-AO): the slow wander
(**baseline**), the fast fuzz (**noise**) and what is left between them
(**signal**, where the events live). Headless: numpy/scipy only.

In plain words: a recording is three things added together. Take the slow
wander out with a running median, take the fast fuzz out of what remains with a
highpass filter, and the rest is the part a detector should read. Because the
signal layer is *defined* as the input minus the other two, the three always add
back to the input -- nothing is lost and nothing is invented.

* **baseline** -- a centred running median over `baseline_window_s`
  (`Working.Detection.analysis.data_analysis.make_smooth`, the core's own
  rolling median, edges by `mode="nearest"`). A median, not a mean, so a drop or
  a spike does not pull the baseline towards itself. On request
  (`baseline_method="rolling_mean"`) it is the detrend block's centred rolling
  mean instead (`Working.Preprocessing.detrend.make_detrend_filter`, read back
  as input minus the detrended trace), so a chain that used the Detrend block
  can see exactly what that block removed.
* **noise** -- the highpass block's zero-phase Butterworth
  (`Working.Detection.analysis.freq_analysis.make_highpass_filter`) above
  `noise_cut_hz`, applied to the input *with its baseline already taken off*
  (the baseline holds the span's level and its slow wander; filtering what is
  left keeps filtfilt's edge transient small). `noise_cut_hz = 0` (auto) is a
  quarter of Nyquist, fs / 8.
* **signal** -- input - baseline - noise.

Why not a new filter: the prompt's rule, and 00-common's -- the running median
and both filters already exist and are what the Detrend and Highpass blocks run.
Why not `preprocessing.wavelet_bands`: that splits by octave (frequency
layers); this splits by *role* (wander / events / fuzz) with a median that is
not a linear filter. The frequency case is that block's, and this one's
description says so.

Gaps: a NaN would poison the median's neighbours and the IIR filter's whole
output, so a span holding one is refused with its count (the wavelet block's
rule).
"""

import numpy as np

#: the baseline estimators offered; the first is the default
BASELINE_METHODS = ("rolling_median", "rolling_mean")


def auto_noise_cut_hz(fs):
    """A quarter of Nyquist: the noise layer is the top quarter of the band."""
    return float(fs) / 8.0


def baseline_half_width(fs, baseline_window_s):
    """The running median's half-width `j` in samples (window = 2j + 1), the
    nearest odd window to `baseline_window_s`; at least 1."""
    return max(1, int(round(float(baseline_window_s) * float(fs) / 2.0)))


def decompose(x, fs, baseline_window_s=600.0, noise_cut_hz=0.0, baseline_method="rolling_median", order=4):
    """``{"baseline", "noise", "signal", "noise_cut_hz", "noise_cut_auto",
    "baseline_window_samples"}`` for the span `x` at `fs` Hz. The three arrays
    are as long as `x` and ``baseline + noise + signal == x`` to rounding."""
    from Working.Detection.analysis.data_analysis import make_smooth
    from Working.Detection.analysis.freq_analysis import make_highpass_filter
    from Working.Preprocessing.detrend import make_detrend_filter

    x = np.asarray(x, dtype=float)
    fs = float(fs)
    bad = int((~np.isfinite(x)).sum())
    if bad:
        raise ValueError(
            f"decompose: the span holds {bad} NaN or infinite sample(s); a running median and a filter spread one "
            "missing sample into its neighbours. Choose a span without gaps, or fill them upstream.")
    if baseline_method not in BASELINE_METHODS:
        raise ValueError(f"decompose: baseline_method {baseline_method!r} is not one of {list(BASELINE_METHODS)}")
    nyquist = fs / 2.0
    auto = not noise_cut_hz or float(noise_cut_hz) <= 0
    cut = auto_noise_cut_hz(fs) if auto else float(noise_cut_hz)
    if cut >= nyquist:
        raise ValueError(
            f"decompose: a noise cut of {cut:g} Hz is at or above the Nyquist frequency ({nyquist:g} Hz at "
            f"{fs:g} Hz sampling): nothing would be left to call noise. Choose a cut below {nyquist:g} Hz, "
            "or 0 for a quarter of Nyquist.")
    j = baseline_half_width(fs, baseline_window_s)
    if baseline_method == "rolling_median":
        baseline = make_smooth(j)(x)
        window_samples = 2 * j + 1
    else:
        baseline = x - make_detrend_filter(fs, mode="rolling_mean", window_s=float(baseline_window_s))(x)
        # the detrend block's window: `half = window_samples // 2` either side of the centre
        window_samples = 2 * max(1, max(1, int(round(float(baseline_window_s) * fs))) // 2) + 1
    rest = x - baseline
    noise = make_highpass_filter(fs, cut, order=int(order))(rest)
    signal = rest - noise
    return {"baseline": baseline, "noise": noise, "signal": signal, "noise_cut_hz": cut,
            "noise_cut_auto": bool(auto), "baseline_window_samples": int(window_samples)}
