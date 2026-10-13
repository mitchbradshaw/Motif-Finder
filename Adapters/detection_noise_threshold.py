"""
detection_noise_threshold.py
==============================
`Signal` -> `SpanSet`: cut the chain's current signal at `k_sigma` times its
own robust noise level, after Quian Quiroga, Nadasdy & Ben-Shaul (2004),
*Neural Comput.* 16(8):1661–1687, eq. 3.1 — Thr = 4 σ_n with
σ_n = median{|x| / 0.6745}. The researcher types a multiple of the channel's
noise, never a level in volts or millivolts, so one setting carries across
channels and species whose amplitudes span 0.03–2.1 mV, and across a trace
stored in V or in mV.

The algorithm as implemented
----------------------------
1. σ_n and a centre from the finite samples (`Working.Detection.analysis.
   noise_level`): centre = median(x), σ_n = 1.4826 × median|x − centre|
   (`noise_from='whole_span'`), or the same from a rolling window of
   `noise_window_s` seconds, interpolated per sample (`'rolling'`).
2. z = (x − centre) / σ_n, the trace in noise units.
3. `direction`, with `detection.signal_threshold`'s choices and semantics,
   applied to z by that block's own `_mask_and_excursion`: `above` keeps
   z > k, `below` keeps z < −k, `either` keeps |z| > k. **The default here is
   `either`**, where `signal_threshold` defaults to `above`: a cut around the
   median in noise units has no natural side, and a researcher who has not yet
   said which side matters should see both.
4. Contiguous runs → spans (`detection.threshold.spans_from_mask`); a span
   scores its peak excursion past the cut **in σ_n units** (z_max − k,
   −k − z_min, |z|_max − k).
5. `merge_gap_s` then `min_duration_s` (`detection.threshold.tidy_spans`, both
   off at 0) — imported with `tidy_param_specs`, not copied.

Adaptations, each forced by our data
------------------------------------
* **Median absolute deviation, and a cut around the median.** The paper's
  signal is band-passed (300–6000 Hz), zero-mean by construction, and it cuts
  at ±Thr around zero. Ours is a 1 Hz trace after a rolling-mean detrend whose
  mean the events themselves pull; subtracting the median keeps σ_n blind to
  that offset, and the cut is laid at centre ± k σ_n. On a zero-median trace
  this is exactly the paper's rule.
* **`noise_from='rolling'`** (not in the paper, whose recordings are 60 s):
  our recordings run for days and a channel's noise can change; a rolling
  MAD over `noise_window_s` judges each stretch against its own noise. The
  window is at least `MIN_ROLLING_WINDOW` (300) **samples**: shorter, the MAD
  is too noisy an estimate and the cut fires on noise (white noise, k = 4:
  ~1300× the whole-span false positives at 3 samples, ~1.8× at 300). The
  minimum is in samples, so no seconds bound on the parameter can express it
  for every sampling rate; a shorter `noise_window_s` is therefore **clamped**
  up to it with a warning, not refused — refusing would make the same chain
  run on one recording and fail on a slower-sampled one. `meta` carries the
  window actually used (`noise_window_samples`). A window whose MAD is 0 (a
  flat stretch) is not judged and is not blended into its neighbours.
* **No band-pass inside the block.** At 1 Hz the paper's 300–6000 Hz band does
  not exist; the template puts baseline removal in front instead, and any
  other Signal -> Signal block can stand there.
* **The paper's own assumption is checked, not taken on trust.** When more than
  20 % of the judged samples lie past the cut, the events are not "a small
  fraction of all samples" and σ_n is inflated by them; `meta["warnings"]` says
  so. **That check has a blind spot:** events common enough can inflate σ_n so
  far that they no longer cross the cut — 40 % of samples in 5 σ or 8 σ drops
  give σ_n ≈ 2.8 σ, no span and no warning. So `meta["sigma_ratio_diff"]`
  compares σ_n with the noise read off the sample-to-sample differences,
  robust_sigma(diff(x)) / √2, which events lasting many samples barely touch:
  ≈ 1 for white noise, ≈ 2.75 at 40 % 5 σ drops. Coloured (slow, correlated)
  noise also raises it, so it is a number to read, not a warning. A rolling
  window does not cure dominance — the events dominate each window too. A trace
  whose MAD is 0 (flat, or quantised with more than half its samples
  on one value) has no noise level: its samples are not judged, they are
  counted in `n_unjudged`, and a warning says why — never a division by zero
  and never a silent blank.

`meta` carries σ_n and the cut **in the signal's stored units** (`sigma`,
`centre`, `cut_above`, `cut_below`; for `rolling`, their medians along the
trace plus `sigma_min` / `sigma_max`), the plain SD for comparison, the
fraction of samples past the cut and the rules. A `derive` row prints the same
for the span in hand. No parameter is named `threshold` on purpose: that name
makes the block page draw an absolute, draggable level, and this cut is a
consequence of the span, not a level to drag.

Implemented from the paper's published equation; no Wave_clus code (its
licence is non-commercial) was read or copied.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.detection_signal_threshold import DIRECTIONS, _mask_and_excursion
from Adapters.detection_threshold import spans_from_mask, tidy_param_specs, tidy_spans
from Adapters.registry import register
from Working.Detection.analysis.noise_level import MIN_ROLLING_WINDOW, noise_level, rolling_noise
from Working.Detection.drop_motifs.detect import robust_sigma
from Working.types import SpanSet

NOISE_FROM = ["whole_span", "rolling"]

#: the paper's assumption — spikes are a small fraction of all samples — is
#: called broken when more than this fraction of judged samples lies past the cut
EVENT_FRACTION_WARN = 0.20

RULES = [
    {"name": "sigma",
     "rule": "σ_n = median(|x − median(x)|) / 0.6745 over the finite samples (Quian Quiroga et al. 2004, eq. 3.1, "
             "on the deviation from the median); in the signal's stored units"},
    {"name": "cut",
     "rule": "above: x > median + k·σ_n; below: x < median − k·σ_n; either: |x − median| > k·σ_n"},
    {"name": "score",
     "rule": "a span's peak excursion past the cut in σ_n units: max(z) − k, −k − min(z) or max|z| − k, "
             "z = (x − median) / σ_n"},
    {"name": "sigma_ratio_diff",
     "rule": "σ_n / (robust_sigma(diff(x)) / √2): ≈ 1 for white noise; well above 1 when long events (or slow, "
             "coloured noise) fill the trace and inflate σ_n — the case the > 20 % warning cannot see"},
    {"name": "noise_window",
     "rule": f"rolling: the window is round(noise_window_s · fs) samples, at least {MIN_ROLLING_WINDOW}; "
             "a window whose MAD is 0 is not judged and not interpolated into its neighbours"},
]


def _window_samples(fs, noise_window_s):
    """(samples asked for, samples used): the rolling window clamped up to the minimum."""
    asked = int(round(float(noise_window_s) * float(fs)))
    return asked, max(MIN_ROLLING_WINDOW, asked)


def _noise(xs, fs, noise_from, noise_window_s):
    """Per-sample (centre, sigma) arrays for the chosen estimate."""
    if noise_from == "whole_span":
        c, s = noise_level(xs)
        return np.full(xs.size, c), np.full(xs.size, s)
    if noise_from == "rolling":
        return rolling_noise(xs, _window_samples(fs, noise_window_s)[1])
    raise ValueError(f"detection.noise_threshold: noise_from must be one of {NOISE_FROM}, got {noise_from!r}")


def _summary(xs, fs, k_sigma, noise_from, noise_window_s):
    """σ_n, centre and the cut in stored units — shared by run and derive."""
    centre, sigma = _noise(xs, fs, noise_from, noise_window_s)
    usable = np.isfinite(sigma) & (sigma > 0)
    if usable.any():
        c_med = float(np.median(centre[usable]))
        s_med = float(np.median(sigma[usable]))
        s_min, s_max = float(np.min(sigma[usable])), float(np.max(sigma[usable]))
    else:
        c_med = float(np.nanmedian(centre)) if np.isfinite(centre).any() else float("nan")
        s_med = s_min = s_max = (0.0 if np.isfinite(sigma).any() else float("nan"))
    d = np.diff(xs)
    d = d[np.isfinite(d)]
    s_diff = float(robust_sigma(d)) / np.sqrt(2.0) if d.size else float("nan")
    ratio = s_med / s_diff if (np.isfinite(s_med) and np.isfinite(s_diff) and s_diff > 0) else float("nan")
    return centre, sigma, usable, {
        "sigma_ratio_diff": float(ratio),
        "centre": c_med,
        "sigma": s_med,
        "sigma_min": s_min,
        "sigma_max": s_max,
        "cut_above": c_med + k_sigma * s_med,
        "cut_below": c_med - k_sigma * s_med,
    }


def _run(x, t, fs, k_sigma=4.0, direction="either", noise_from="whole_span", noise_window_s=3600.0,
         min_duration_s=0.0, merge_gap_s=0.0):
    if direction not in DIRECTIONS:
        raise ValueError(f"detection.noise_threshold: direction must be one of {DIRECTIONS}, got {direction!r}")
    xs = np.asarray(x, dtype=float).ravel()
    k = float(k_sigma)
    centre, sigma, usable, summary = _summary(xs, fs, k, noise_from, noise_window_s)

    finite = np.isfinite(xs)
    judged = finite & usable
    z = np.full(xs.size, np.nan)
    z[judged] = (xs[judged] - centre[judged]) / sigma[judged]

    cut = -k if direction == "below" else k      # signal_threshold's reading of the cut, in z
    with np.errstate(invalid="ignore"):          # an unjudged (NaN) sample compares False: never in a span
        mask, excursion = _mask_and_excursion(z, cut, direction)
    raw_starts, raw_ends = spans_from_mask(mask)
    scores = tuple(excursion(z[s:e]) for s, e in zip(raw_starts, raw_ends))
    starts, ends, scores = tidy_spans(raw_starts, raw_ends, scores, fs,
                                      min_duration_s=min_duration_s, merge_gap_s=merge_gap_s)

    n_judged = int(judged.sum())
    n_unjudged = int((finite & ~usable).sum())
    fraction = float(mask.sum()) / n_judged if n_judged else 0.0
    warnings = []
    if not finite.any():
        warnings.append("No finite sample in the span: nothing to estimate a noise level from.")
    elif n_unjudged:
        warnings.append(
            f"{n_unjudged} of {int(finite.sum())} finite samples were not judged: the noise level there is 0 "
            "(more than half the samples sit on one value — a flat or coarsely quantised trace), "
            "so no multiple of it is a meaningful cut."
            + (" With a rolling window this includes the samples within half a window of a flat stretch, whose "
               "windows reach into it." if noise_from == "rolling" else ""))
    if fraction > EVENT_FRACTION_WARN:
        warnings.append(
            f"{fraction:.0%} of the samples lie past the cut: events are not a small fraction of the trace, "
            "the assumption behind the median noise estimate, so σ_n is inflated by the events and the cut "
            "sits higher than the noise alone would put it. Shorten the span or remove the baseline first. "
            "This check is blind when events are common enough to hide under the σ_n they inflate; "
            f"sigma_ratio_diff ({summary['sigma_ratio_diff']:.2f}, about 1 for white noise) reads that case.")
    window_used = None
    if noise_from == "rolling":
        asked, window_used = _window_samples(fs, noise_window_s)
        if asked < window_used and xs.size > asked:
            warnings.append(
                f"The rolling noise window was {asked} samples ({float(noise_window_s):g} s at {float(fs):g} Hz); "
                f"it was raised to the minimum of {MIN_ROLLING_WINDOW} samples, because a noise level from fewer "
                "samples is itself so noisy that the cut fires on plain noise.")

    return AdapterResult(
        output_kind="spanset",
        value=SpanSet(starts=starts, ends=ends, scores=scores),
        meta={
            "n_spans": int(len(starts)),
            "n_samples": int(xs.size),
            "n_nan": int((~finite).sum()),
            "n_unjudged": n_unjudged,
            "k_sigma": k,
            "direction": direction,
            "noise_from": noise_from,
            "noise_window_s": float(noise_window_s),
            "noise_window_samples": window_used,
            "cut_varies": noise_from == "rolling",
            **summary,
            "plain_sd": float(np.std(xs[finite])) if finite.any() else float("nan"),
            "fraction_past_cut": fraction,
            "min_duration_s": float(min_duration_s),
            "merge_gap_s": float(merge_gap_s),
            "warnings": warnings,
            "rules": [dict(r) for r in RULES],
        },
    )


def _fmt(v):
    return "—" if not np.isfinite(v) else f"{v:.4g}"


def _derive(x, t, fs, params, **_typed):
    xs = np.asarray(x, dtype=float).ravel()
    k = float(params.get("k_sigma", 4.0))
    direction = params.get("direction", "either")
    noise_from = params.get("noise_from", "whole_span")
    _, _, usable, s = _summary(xs, fs, k, noise_from, params.get("noise_window_s", 3600.0))
    where = " (median along the span)" if noise_from == "rolling" else ""
    rows = [("Noise level σ_n" + where, f"{_fmt(s['sigma'])} in the signal's stored units", "")]
    if noise_from == "rolling":
        rows.append(("σ_n range", f"{_fmt(s['sigma_min'])} – {_fmt(s['sigma_max'])}", ""))
    cut = {"above": f"x > {_fmt(s['cut_above'])}",
           "below": f"x < {_fmt(s['cut_below'])}",
           "either": f"x < {_fmt(s['cut_below'])} or x > {_fmt(s['cut_above'])}"}.get(direction, "—")
    rows.append((f"Cut ({k:g} σ_n around the median {_fmt(s['centre'])})" + where, cut,
                 "" if usable.any() else "error"))
    if not usable.any():
        rows.append(("Noise level", "0 or undefined on this span — nothing can be cut", "error"))
    return rows


SPEC = register(AdapterSpec(
    name="detection.noise_threshold",
    display_name="Noise threshold (Signal -> SpanSet, k × robust σ)",
    stage="detection",
    category="detect",
    page_name="Noise threshold",
    params=[
        ParamSpec("k_sigma", float, 4.0,
                  "The cut, in multiples of the channel's own noise level σ_n = median|x − median| / 0.6745 "
                  "(4 in Quian Quiroga et al. 2004; lower finds weaker events and more false ones)",
                  min=0.5, max=50.0),
        ParamSpec("direction", str, "either",
                  "Which side of the cut counts: `above` keeps rises past median + k·σ_n, `below` keeps drops "
                  "under median − k·σ_n, `either` keeps both",
                  choices=list(DIRECTIONS)),
        ParamSpec("noise_from", str, "whole_span",
                  "Where σ_n comes from: the whole span (the paper), or `rolling` — a window of "
                  "`noise_window_s` around each sample, for a channel whose noise changes over days",
                  choices=list(NOISE_FROM)),
        ParamSpec("noise_window_s", float, 3600.0,
                  "Seconds in the rolling noise window (used only when noise_from is `rolling`); make it many "
                  "times longer than an event so the events stay a small fraction of each window. At least "
                  f"{MIN_ROLLING_WINDOW} samples are used whatever the sampling rate; a shorter window is "
                  "raised to that, with a warning",
                  min=3.0),
        *tidy_param_specs(),
    ],
    run=_run,
    derive=_derive,
    input_kind="signal",
    output_kind="spanset",
    plot=None,
    description=(
        "Cuts the chain's current signal at k_sigma times its own robust noise level "
        "(σ_n = median|x − median| / 0.6745, Quian Quiroga et al. 2004) and keeps the runs above it, below it "
        "or past it on either side — no level in volts or millivolts to type, so one setting works on every "
        "channel. Tune `k_sigma` first (4 is the paper's). Put baseline removal before it. A span scores by how "
        "many σ_n past the cut it reaches; σ_n and the cut in the signal's units are printed, with a warning "
        "when events are too many for the noise estimate to be trusted."
    ),
))
