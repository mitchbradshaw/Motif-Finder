"""
detection_pan_matrix_profile.py
=================================
`detection.pan_matrix_profile` — Signal -> Encoding (an image): the pan
matrix profile (Madrid et al. 2019, matrix profile XX) over a geometric ladder
of window lengths, and per length whether anything repeats more than
amplitude-adjusted noise of the same colour does. The algorithm, its rules
and its departures from the paper are in
`Working.Detection.matrix_profiling.pan`.

The image: rows are window lengths, LONG first (row 0 = `max_window_s`), one
column per sample of the span, start-aligned (column i = the window starting
at sample i; each row's last m - 1 columns are NaN). Value = 1 - the
normalised nearest-neighbour distance, so bright = repeated.
`meta["lengths_s"]` names the rows, `meta["alignment"] = "start"`.

Why not reuse `detection.matrix_profile`: that block computes one profile at
one window and persists it for the site's matrix-profile pages; this one
needs many lengths, the same profiles on surrogate copies, and the verdict
across them, none of which that block's output carries. The profiles are
plain exact `stumpy.stump` calls (CPU), so the matrix-profile cost model
applies as is (`cost.estimate_seconds`, imported below: the bridge reads that
import to know it may calibrate the model on first need). There is no
approximate mode (fix round 1): `percentage` < 1 (scrump) drew from numpy's
global random generator, which no lock in this repository makes safe beside
another thread's draws (20 of 20 runs differed), and saved only about 20 %.

Downstream: `detection.wavelet_summation` sums a band of rows; on this image
the sum is "how strongly each moment repeats across that band of window
lengths" — `row_from = 0` is the longest length.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.Detection.matrix_profiling import pan as P
from Working.Detection.matrix_profiling.cost import estimate_seconds as mp_estimate_seconds
from Working.types import Encoding

#: *** MEMORY GUARD *** (a hard ceiling, not derived from the calibration).
#: Peak live bytes per span sample:
#:     image          32 rows max x 4 B (float32)                 128 B
#:     this module    the series, its filled copy, one null copy
#:                    (AAFT holds two argsorts while it builds it),
#:                    one profile, its argsort and a mask          ~70 B
#:     stumpy.stump   per-thread P/PL/PR (float64) + I/IL/IR (int64)
#:                    = 48 B x 16 numba threads on this machine    768 B
#:                    + the rolling means/stds of T                ~64 B
#:                                                           ~1,000 B/sample
#: Budget 1 GB -> 1,000,000 samples (277 h at 1 Hz). Measured by the critic:
#: about 0.5 KB/sample at 4 threads. A whole 721 h channel is refused here; at
#: about 6.5 h per length it belongs on the cluster in pieces anyway.
MAX_N_LENGTHS = 32
MEMORY_BUDGET_BYTES = 1_000_000_000
PEAK_BYTES_PER_SAMPLE = 1_000
MAX_SPAN_SAMPLES = MEMORY_BUDGET_BYTES // PEAK_BYTES_PER_SAMPLE

RULES = [
    {"name": "brightness",
     "rule": "1 − d / (2√m), clipped to 0…1, where d is the z-normalised Euclidean distance from the window "
             "starting at this sample to its most similar window of the same length elsewhere (stumpy's "
             "normalisation for its pan matrix profile; the paper gives none). 1 = an identical shape exists; "
             "about 0.29 = what two windows of white noise score; 0 = anti-correlated."},
    {"name": "layout",
     "rule": "Rows are window lengths, longest first (lengths_s names them); one column per sample, "
             "start-aligned: column i holds the window STARTING at sample i, so each row's last m − 1 columns are "
             "empty. A window touching a NaN gap longer than max_fill_s, or a stall (a held value, or a held "
             "value the detrend bent into a near-straight line: every second difference within 1 % of the "
             "span's typical one) lasting stall_s or more, is empty too; both are counted (n_long_gap, "
             "n_stalled, n_windows_nan per length)."},
    {"name": "distinct windows",
     "rule": "Per length, the windows sorted by distance and kept only if none already kept starts within m "
             "samples — no two overlap. N = how many; the best K = 3 are averaged (r_K), so one lucky pair "
             "of look-alikes cannot carry a length."},
    {"name": "the null",
     "rule": "Amplitude-adjusted copies of the span (AAFT, Theiler 1992; null = 'aaft', the default): the "
             "recording's own values, reordered so the spectrum is roughly kept and every shape destroyed. "
             "null = 'phase' (spectrum kept exactly, values made bell-shaped) is kept for comparison only: a "
             "lopsided recording with no structure (exp of an AR(1)) beat it 10 times in 10. Null copies are "
             "drawn only for lengths that can be judged. A quasi-periodic chain keeps its spacing in its own "
             "copies (the spectrum is kept), so a chain's period is partly in the null."},
    {"name": "gap to the null",
     "rule": "gap = N^(1/3) × ln(z_K / r_K) / ln(z_med / z_K), where z_K and z_med are the mean of the 3 best and "
             "the median distinct distances of the null copies (averaged over the draws): how far the "
             "recording's best look-alikes reach beyond noise's best, in units of how far noise's best reach "
             "beyond its typical window — as ratios, since a distance cannot go below 0 — times N^(1/3) because "
             "with fewer windows the best few vary more by chance (the exponent is measured on synthetic noise)."},
    {"name": "clears the null",
     "rule": f"A length is judged only if the span's usable samples (long gaps and stalls do not count) make at least {P.MIN_WINDOWS} windows (else 'too long to "
             "judge on this span'; 4 h judges up to 17 min, 8 h up to 34 min, 24 h up to 1 h 43 min). It clears "
             f"when the gap reaches the cut — {P.GAP_MIN:g} once the span holds {P.CUT_FULL_WINDOWS} windows, rising "
             f"to {P.gap_cut(P.MIN_WINDOWS, 1):.1f} at {P.MIN_WINDOWS} (false alarms gather at the longest judged "
             "length) — and r_K is below every draw's z_K. None cleared = 'no length stands out' (the shortest "
             "length is never a fallback). Measured at the defaults (AAFT, 3 draws), after a 2 h detrend: "
             "no-structure spans with a suggestion — 2 h random walk 0/30, AR(1) 0.99 0/30, pink noise 0/30; "
             "4 h random walk, AR(1) 0.95 and 0.99, pink, AR(1) + 6 h sine 0/50; 4 h exp(AR(1)) 0/10 (10/10 with "
             "the phase null); at one draw 1-7 %."},
    {"name": "suggested window",
     "rule": "The answer is the BAND of cleared lengths (cleared_s): a repeated event clears a band, because "
             "windows shorter than it repeat too (pieces of it), and so do longer windows that hold it when it "
             "dominates them. suggested_window_s (the field keeps its name; the summary says 'strongest gap "
             "at') is the cleared length with the largest gap — the rule that "
             "landed within one rung of the planted scale most often (20 of 38 suggesting spans, against 16 "
             "and 15 for the shortest-length rules) — and it is not the event's length: it leans toward the "
             "longest judged window when an event dominates long windows (a 90 s spike: 30-976 s), and toward "
             "an edge on chains (the 30-72 s fall of a drop); in a later check it fell near either planted "
             "motif in 2 of 10 seeds. It is not the event's length and not a window to hand another block "
             "(FLUSS, a seed search); read the band and the picture."},
]


def _run(x, t, fs, min_window_s=30.0, max_window_s=3600.0, n_lengths=12, null_draws=3, null="aaft",
         seed=0, max_fill_s=5.0, stall_s=60.0, on_progress=None, should_cancel=None):
    out = P.pan_matrix_profile(
        x, fs, min_window_s=min_window_s, max_window_s=max_window_s, n_lengths=n_lengths,
        null_draws=null_draws, null=null, seed=seed, max_fill_s=max_fill_s, stall_s=stall_s,
        on_progress=on_progress, should_cancel=should_cancel)
    img = out.pop("image")
    if img.shape[1] != len(x):  # the image contract wavelet_summation and the Encoding view rely on
        raise RuntimeError(f"pan image has {img.shape[1]} columns for a {len(x)}-sample span")
    cs = out["cleared_s"]
    if out["suggested_window_s"] is not None:
        strongest = max((d for d in out["per_length"] if d["clears"]), key=lambda d: d["gap"])
        band = f"clears from {cs[0]:g} to {cs[-1]:g} s" if len(cs) > 1 else f"clears at {cs[0]:g} s"
        head = f"{band}; strongest gap at {strongest['length_s']:g} s (not an event length)"
    elif out["verdict"].startswith("no spread"):
        head = "no spread to measure (a constant span)"
    else:
        head = "no length stands out"
    summary = (f"{len(out['lengths_s'])} lengths {out['lengths_s'][-1]:g}–{out['lengths_s'][0]:g} s · {head}"
               + (f" · {out['n_stalled']:,} stalled samples left out" if out["n_stalled"] else ""))
    meta = {
        **out,
        "alignment": "start",
        "rows": "long first",
        "n_rows": int(img.shape[0]),
        "k_best": P.K_BEST, "min_windows": P.MIN_WINDOWS, "gap_min": P.GAP_MIN,
        "summary": summary,
        "rules": RULES,
    }
    return AdapterResult(output_kind="encoding", value=Encoding(values=img, kind="image"), meta=meta)


def _estimate(x, t, fs, min_window_s=30.0, max_window_s=3600.0, n_lengths=12, null_draws=3, **params):
    """Seconds from the matrix-profile cost model (k × n² per profile; stump is flat in m) times the number of
    profiles — one per length for the span, plus `null_draws` per length that can be judged — plus stumpy's
    one-off compile when this process has not run `stump` yet (`pan.FIRST_CALL_S`). None while the model is
    uncalibrated, never a guessed number. The measurements are beside `pan.FIRST_CALL_S`."""
    one = mp_estimate_seconds(len(x), "stump")
    if one is None:
        return None
    return (one * P.profile_units(len(x), fs, min_window_s, max_window_s, n_lengths, null_draws)
            + P.first_call_seconds())


def _recommend(x, t, fs):
    """The longest length the span can judge: at least MIN_WINDOWS windows long, capped at 1 h."""
    longest = len(x) / (P.MIN_WINDOWS * float(fs))
    if longest < 30.0:
        return {}
    return {"max_window_s": float(min(3600.0, np.floor(longest)))}


def _derive(x, t, fs, params):
    n = len(x)
    try:
        kept, dropped = P.window_lengths(n, fs, params["min_window_s"], params["max_window_s"],
                                         params["n_lengths"])
    except ValueError as e:
        return [("Lengths", str(e), "error")]
    judged = sum(1 for m in kept if P.judgeable(n, m))
    rows = [
        ("Lengths (s)", ", ".join(f"{m / fs:g}" for m in kept) or "none", "" if kept else "error"),
        ("Judged against the null", f"{judged} of {len(kept)} (a length needs a span {P.MIN_WINDOWS} windows long)",
         "warn" if judged < len(kept) else ""),
    ]
    if dropped:
        rows.append(("Dropped", ", ".join(f"{m / fs:g} s" for m in dropped) + " (too short for stumpy or "
                     "longer than half the span)", "warn"))
    if len(kept) > MAX_N_LENGTHS:
        rows.append(("Rows", f"{len(kept)} > {MAX_N_LENGTHS}", "error"))
    return rows


SPEC = register(AdapterSpec(
    name="detection.pan_matrix_profile",
    display_name="Pan matrix profile (matrix profile XX)",
    stage="detection",
    category="encode",
    page_name="Pan matrix profile",
    params=[
        ParamSpec("min_window_s", float, 30.0, "Shortest window length, in seconds", min=0.001),
        ParamSpec("max_window_s", float, 3600.0,
                  "Longest window length, in seconds. Tune this first: a length is only judged when the span "
                  f"is at least {P.MIN_WINDOWS} windows long (4 h: up to 17 min; 8 h: up to 34 min)", min=0.001),
        ParamSpec("n_lengths", int, 12, "How many lengths, spaced geometrically from shortest to longest",
                  min=1, max=MAX_N_LENGTHS),
        ParamSpec("null_draws", int, 3,
                  "Amplitude-adjusted copies of the span each judged length is compared with; each costs as much "
                  "as the real span. 3 by measurement (1 draw gave 1-7 % false suggestions on noise). 0 = "
                  "picture only, no verdict", min=0, max=50),
        ParamSpec("null", str, "aaft",
                  "The noise copies: 'aaft' keeps the recording's own values (use this); 'phase' makes them "
                  "bell-shaped and is kept only for comparison", choices=list(P.NULLS)),
        ParamSpec("seed", int, 0, "Seed of the null copies", min=0),
        ParamSpec("max_fill_s", float, 5.0,
                  "NaN gaps up to this long are bridged by a straight line; longer gaps stay empty and every "
                  "window touching one is left out (placeholder: dropouts of a few samples)", min=0.0),
        ParamSpec("stall_s", float, 60.0,
                  "A held value (a stalled logger, a clipped stretch) lasting this long or longer is left out "
                  "and counted — found by its second differences staying near zero, so a held value the "
                  "detrend has bent into a near-straight line is caught too (placeholder: a quantised 1 Hz "
                  "logger never holds still this long by chance)", min=3.0),
    ],
    run=_run,
    input_kind="signal",
    output_kind="encoding",
    estimate=_estimate,
    recommend=_recommend,
    derive=_derive,
    max_span_samples=MAX_SPAN_SAMPLES,
    plot=None,
    description=(
        "At which window lengths does anything repeat? The matrix profile, for a ladder of window lengths "
        "(30 s to 1 h by default): rows are lengths, longest at the top; time runs along the bottom; the pixel in "
        "column i is bright when the window starting at sample i (not centred on it) has a close look-alike of the same length "
        "elsewhere in the span (shape only — each window is z-normalised, so loudness is ignored). Each length "
        "is compared with amplitude-adjusted copies of the span (the recording's own values reshuffled: the same "
        "colour of noise, no shapes). The answer is the band of lengths that repeat beyond those copies "
        "('clears from A to B s, strongest at C'), or 'no length stands out' — nothing repeats more than this "
        "kind of noise at any tested length, not that nothing happens. The suggested length is the strongest of "
        "the band, NOT the event's length and not a window to hand another block: it leans long when an event "
        "dominates long windows and toward the edges on chains. Tune `max_window_s` first: a length is judged only if the span is 14 windows long — "
        "4 h judges up to 17 min, 8 h up to 34 min, so a drop chain's ~30 min unit is out of reach on an 8 h "
        "span (expect 'no length' or the 30-72 s fall edge); judge chains on 24 h or more, or read the picture. "
        "Detrend first. Two occurrences must have the same length to match. A held value lasting `stall_s` "
        "or longer (a stalled logger; found after the detrend too) is left out and counted. Followed by Wavelet summation, the summed band reads "
        "'how strongly the windows starting here repeat across these lengths' (row_from 0 = the longest); it is "
        "NaN over the last m − 1 samples of the band's longest row (an hour at the 3600 s default). Costs one "
        "full matrix profile per length plus null_draws per judged length."
    ),
))
