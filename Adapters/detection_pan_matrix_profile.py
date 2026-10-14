"""
detection_pan_matrix_profile.py
=================================
`detection.pan_matrix_profile` — Signal -> Encoding (an image): the pan
matrix profile (Madrid et al. 2019, matrix profile XX) over a geometric ladder
of window lengths, and per length whether anything repeats more than
phase-randomised noise of the same colour does. The algorithm, its rules and
its departures from the paper are in
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
plain `stumpy.stump` calls (CPU), so the matrix-profile cost model applies
as is (`cost.estimate_seconds`, imported below: the bridge reads that import
to know it may calibrate the model on first need).

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
#:     this module    the series, its filled copy, one null copy,
#:                    one profile, its argsort and a mask          ~41 B
#:     stumpy.stump   per-thread P/PL/PR (float64) + I/IL/IR (int64)
#:                    = 48 B x 16 numba threads on this machine    768 B
#:                    + the rolling means/stds of T                ~64 B
#:                                                           ~1,000 B/sample
#: Budget 1 GB -> 1,000,000 samples (277 h at 1 Hz). A whole 721 h channel is
#: refused here; at about 6.5 h per length it belongs on the cluster in pieces
#: anyway. On a node with more numba threads stumpy's share grows (3 KB/sample
#: at 64 threads): still inside a node's memory at this ceiling.
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
             "start-aligned: column i is the window starting at sample i, so each row's last m − 1 columns are "
             "empty. A window touching a NaN gap longer than max_fill_s is empty too (counted per length)."},
    {"name": "distinct windows",
     "rule": "Per length, the windows sorted by distance and kept only if none already kept starts within m "
             "samples — no two overlap. N = how many; the best K = 3 are averaged (r_K), so one lucky pair "
             "of look-alikes cannot carry a length."},
    {"name": "gap to the null",
     "rule": "gap = N^(1/3) × ln(z_K / r_K) / ln(z_med / z_K), where z_K and z_med are the mean of the 3 best and "
             "the median distinct distances of the phase-randomised copies (spectrum kept, phases drawn; "
             "averaged over the draws): how far the recording's best look-alikes reach beyond noise's best, in "
             "units of how far noise's best reach beyond its typical window — as ratios, since a distance "
             "cannot go below 0 — times N^(1/3) because with fewer windows the best few vary more by chance (the exponent is measured on synthetic noise)."},
    {"name": "clears the null",
     "rule": f"A length is judged only if the span is at least {P.MIN_WINDOWS} windows long (else 'too long to "
             f"judge on this span'; 4 h judges up to 17 min); it clears when gap ≥ {P.GAP_MIN:g} and r_K is "
             "below every draw's z_K. suggested_window_s = the cleared length with the largest gap; none "
             "cleared = 'no length stands out' (the shortest length is never a fallback). Measured with one "
             "draw: about 4 no-structure spans in 100 still get a suggestion — more draws steady it."},
]


def _run(x, t, fs, min_window_s=30.0, max_window_s=3600.0, n_lengths=12, percentage=1.0, null_draws=1,
         seed=0, max_fill_s=5.0, on_progress=None, should_cancel=None):
    out = P.pan_matrix_profile(
        x, fs, min_window_s=min_window_s, max_window_s=max_window_s, n_lengths=n_lengths,
        percentage=percentage, null_draws=null_draws, seed=seed, max_fill_s=max_fill_s,
        on_progress=on_progress, should_cancel=should_cancel)
    img = out.pop("image")
    if img.shape[1] != len(x):  # the image contract wavelet_summation and the Encoding view rely on
        raise RuntimeError(f"pan image has {img.shape[1]} columns for a {len(x)}-sample span")
    approx = float(percentage) < 1.0
    summary = (f"{len(out['lengths_s'])} lengths {out['lengths_s'][-1]:g}–{out['lengths_s'][0]:g} s · "
               + (f"suggested {out['suggested_window_s']:g} s" if out["suggested_window_s"] is not None
                  else "no length stands out")
               + (f" · APPROXIMATE ({percentage:g} of the distances)" if approx else ""))
    meta = {
        **out,
        "alignment": "start",
        "rows": "long first",
        "n_rows": int(img.shape[0]),
        "approximate": approx,
        "approximate_note": (f"scrump with {percentage:g} of the distance-matrix diagonals: every distance is an "
                             "upper bound on the exact one, so the picture is darker than the truth and a "
                             "repetition can be missed, never invented") if approx else "",
        "k_best": P.K_BEST, "min_windows": P.MIN_WINDOWS, "gap_min": P.GAP_MIN,
        "summary": summary,
        "rules": RULES,
    }
    return AdapterResult(output_kind="encoding", value=Encoding(values=img, kind="image"), meta=meta)


def _estimate(x, t, fs, min_window_s=30.0, max_window_s=3600.0, n_lengths=12, percentage=1.0, null_draws=1,
              **params):
    """Seconds from the matrix-profile cost model (k × n² per profile; stump is flat in m) times the number of
    profiles — one per length for the span and for each null draw — times the scrump factor when approximate,
    plus stumpy's one-off compile when this process has not run `stump` yet (`pan.FIRST_CALL_S`). None while the
    model is uncalibrated, never a guessed number. Measured (loaded machine, ratio actual / estimate): 4 h cold
    1.06, warm 1.05-1.59; 24 h warm 0.75, cold 1.37 before the compile term was added (about 1.15 with it)."""
    one = mp_estimate_seconds(len(x), "stump")
    if one is None:
        return None
    return (one * P.profile_units(len(x), fs, min_window_s, max_window_s, n_lengths, percentage, null_draws)
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
                  f"is at least {P.MIN_WINDOWS} windows long (a 4 h span judges up to 17 min)", min=0.001),
        ParamSpec("n_lengths", int, 12, "How many lengths, spaced geometrically from shortest to longest",
                  min=1, max=MAX_N_LENGTHS),
        ParamSpec("percentage", float, 1.0,
                  "1 = exact. Below 1: approximate (scrump), that fraction of the distances computed — darker, "
                  "may miss a repetition but never invents one. Faster only on long windows (its sampling pass "
                  "costs more than an exact run below about 1 min): about 0.8× the exact cost on the default "
                  "ladder at 0.1", min=0.01, max=1.0),
        ParamSpec("null_draws", int, 1,
                  "Phase-randomised copies of the span (same spectrum) each length is compared with; each "
                  "costs as much as the real span. 0 = picture only, no verdict", min=0, max=50),
        ParamSpec("seed", int, 0, "Seed of the null copies (and of scrump's order when approximate)", min=0),
        ParamSpec("max_fill_s", float, 5.0,
                  "NaN gaps up to this long are bridged by a straight line; longer gaps stay empty and every "
                  "window touching one is left out (placeholder: dropouts of a few samples)", min=0.0),
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
        "(30 s to 1 h by default): rows are lengths, longest at the top; time runs along the bottom; a pixel is "
        "bright where the window starting there has a close look-alike of the same length elsewhere in the "
        "span (shape only — each window is z-normalised, so loudness is ignored). Each length is then "
        "compared with phase-randomised copies of the span (the same spectrum, so the same colour of noise): "
        "the block suggests the length whose best look-alikes beat noise by the widest margin, or says 'no "
        "length stands out' — which means nothing in the span repeats more than coloured noise does at any "
        "tested length, not that nothing happens. Tune `max_window_s` first: a length is judged only if the "
        "span is 14 windows long (4 h: up to 17 min). Detrend first. Two occurrences must have the same length to match. "
        "Followed by Wavelet summation, the summed band reads 'how strongly this moment repeats across these "
        "lengths' (row_from 0 = the longest). Costs one full matrix profile per length, times 1 + null_draws."
    ),
))
