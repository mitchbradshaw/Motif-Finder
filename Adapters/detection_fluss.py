"""
detection_fluss.py
====================
`detection.fluss` — Signal -> Scores: the FLUSS regime-change score (1 - CAC,
Gharghabi et al. 2017, matrix profile VIII) of the span, one value per sample.
The algorithm, its deviations from the paper and why are in
`Working.Detection.matrix_profiling.fluss`.

The matrix profile is computed by the site's existing
`Pipelines.matrix_profile.run_matrix_profile.matrix_profile` (backend "auto":
the GPU when there is one, else `stumpy.stump`) — the same call
`detection.matrix_profile` makes, so the two blocks see one profile for one
window. Reuse rather than chaining after `detection.matrix_profile`: that
block's output is the distance profile (a Scores), and FLUSS needs the index,
which a downstream block cannot see (a block does not read the previous
block's `meta`). Nothing is persisted: the index is recomputed, which is the
O(n²) cost declared below.

Why not reuse `detection.rupture`: PELT finds changes in mean / variance;
FLUSS finds changes in the repertoire of shapes, which a mean/variance model
cannot see.

Adaptations: the window is in seconds (`window_s`), converted at the span's
fs. The paper sets the window to about one period of the behaviour. The block
default stays 60 s — the 1-minute scale that served spikes on rec 385, the
only real-data evidence for a scale; the synthetic regimes the template is
calibrated on have 5- and 15-minute periods, so the `fluss_regimes` template
sets 300 s, and at 60 s their jittered versions were missed. A threshold cut
on this score holds for the window it was calibrated at only: a longer window
gives fewer, more distinctive windows and higher peaks on changes and nulls
alike (on the synthetic set the change peaked at 0.35-0.40 at 60 s, 0.65-0.82
at 300 s, the nulls at <= 0.23 and <= 0.44).

NaN: a window touching NaN has no neighbour; it is not scored, and the IAC is
corrected for it (see the core). But `preprocessing.detrend`'s rolling mean
spreads one NaN sample over about a detrend window, so a recording's NaN gaps
grow before they get here — check them.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.config import MP_MIN_WINDOW_SAMPLES
from Working.Detection.matrix_profiling.cost import max_span_samples_for_background
from Working.Detection.matrix_profiling.fluss import IAC_KINDS, regime_change_score
from Working.types import Scores

RULES = [
    {"name": "regime-change score",
     "rule": "1 − CAC. For every window, the matrix profile names its most similar window; an arc joins "
             "the two. AC(i) counts the arcs passing over sample i; CAC(i) = min(AC(i) / IAC(i), 1), where "
             "IAC is the count expected if neighbours were random (the paper's parabola 2i(n−i)/n, or "
             "stumpy's fitted beta). 0 = arcs cross freely (no evidence of a change); near 1 = almost no "
             "arc crosses (a change of behaviour)."},
    {"name": "blanked edges",
     "rule": "The first and last excl_factor × window samples are not scored (NaN): the expected arc count "
             "is near zero there, so the ratio is noise. stumpy's convention (5 windows); the paper blanks "
             "one window."},
    {"name": "regime locations",
     "rule": "The paper's extraction (Table II): the n_regimes_readout − 1 lowest CAC minima, each "
             "excluding excl_factor × window either side. A location with CAC 1.0 (stumpy's padding once the "
             "exclusion zones cover the span) is dropped; n_regimes_found counts the rest + 1. A kept "
             "location is not yet a change — read the CAC beside it (near 1 = no evidence)."},
    {"name": "missing neighbours",
     "rule": "A window touching NaN has no neighbour: it is not scored (NaN), and the arcs are counted over "
             "the valid windows only, with the expected curve for that many, so a long gap is not read as "
             "the end of a regime."},
]


def _window_samples(window_s, fs):
    return int(round(float(window_s) * float(fs)))


def _run(x, t, fs, window_s=60.0, n_regimes_readout=3, iac="parabola", excl_factor=5):
    from Pipelines.matrix_profile.run_matrix_profile import matrix_profile

    x = np.asarray(x, dtype=np.float64)
    m = _window_samples(window_s, fs)
    if m < MP_MIN_WINDOW_SAMPLES:
        raise ValueError(
            f"window_s={window_s:g} at fs={fs:g} gives a {m}-sample window; "
            f"stumpy requires at least {MP_MIN_WINDOW_SAMPLES} samples."
        )
    needed = 2 * int(excl_factor) * m + m - 1      # the core's own limit: one scored window
    if len(x) <= needed:
        raise ValueError(
            f"span too short for FLUSS: {len(x)} samples, but a {m}-sample window with "
            f"excl_factor {excl_factor} needs more than {needed} ({excl_factor} windows are blanked "
            "at each end). Shorten window_s or analyse a longer span."
        )

    mp = matrix_profile(x, t, m, backend="auto")
    out = regime_change_score(mp["mpi"], m=m, iac=iac, excl_factor=excl_factor,
                              n_regimes=n_regimes_readout)
    score = out["score"]
    if len(score) != len(x):  # the contract a Scores consumer relies on
        raise RuntimeError(f"FLUSS score has {len(score)} values for a {len(x)}-sample span")

    return AdapterResult(
        output_kind="scores",
        value=Scores(values=score, fs=float(fs)),
        meta={
            "m": m, "window_s": float(window_s), "iac": iac, "excl_factor": int(excl_factor),
            "cac_min": out["cac_min"], "cac_min_idx": out["cac_min_idx"],
            "score_max": 1.0 - out["cac_min"],
            "regime_locs": out["regime_locs"], "regime_cac": out["regime_cac"],
            "n_regimes_readout": int(n_regimes_readout),
            "n_regimes_found": out["n_regimes_found"],
            "n_blanked_each_end": out["n_blanked_each_end"],
            "n_scored": int(np.count_nonzero(np.isfinite(score))),
            "n_no_neighbour": out["n_no_neighbour"],
            "backend": mp["backend"], "elapsed_s": mp["elapsed_s"],
            "rules": RULES,
        },
    )


def _estimate(x, t, fs, window_s=60.0, n_regimes_readout=3, iac="parabola", excl_factor=5):
    """Seconds for this span from the matrix-profile cost model (the O(n²)
    profile dominates; the arc count is O(n)), or None while uncalibrated —
    never a guessed number. `iac="beta"` adds its fitting, not modelled: it
    grows with the span, about 1.4 s at 4 h and 4.9 s at 24 h at 1 Hz."""
    from Working.Detection.matrix_profiling.cost import estimate_seconds
    return estimate_seconds(len(x), "stump")


SPEC = register(AdapterSpec(
    name="detection.fluss",
    display_name="FLUSS regime change (matrix profile VIII)",
    stage="detection",
    category="detect",
    page_name="FLUSS regime change",
    params=[
        ParamSpec("window_s", float, 60.0,
                  "Window in seconds — about one event period of the behaviour (the paper's L). Tune this "
                  "first; a threshold cut on the score holds only for the window it was calibrated at",
                  min=0.001),
        ParamSpec("n_regimes_readout", int, 3,
                  "Readout only: report this many regimes (this minus one changes) in the block's numbers; "
                  "does not change the score", min=2, max=50),
        ParamSpec("iac", str, "parabola",
                  "Idealised arc curve: 'parabola' is the paper's 2i(n−i)/n; 'beta' is stumpy's fitted curve "
                  "(nearly identical; its fit costs ~1.4 s at 4 h, ~4.9 s at 24 h)", choices=list(IAC_KINDS)),
        ParamSpec("excl_factor", int, 5,
                  "Windows left unscored at each end, and kept apart between reported changes", min=1, max=50),
    ],
    run=_run,
    input_kind="signal",
    output_kind="scores",
    estimate=_estimate,
    max_span_samples=max_span_samples_for_background(),
    plot=None,
    description=(
        "EXPERIMENTAL: on real recordings it found nothing beyond its surrogate null (docs/prompts/blocks/reports/W1-evaluation.md). "
        "Where does the recording change behaviour? For every window the matrix profile finds its most "
        "similar window elsewhere; inside one regime those look-alikes stay inside it, so at a change few "
        "of the links cross. The score is high where few cross (1 − CAC; 0 = no change). Detrend first: a "
        "drifting baseline makes every window look alike and the score goes flat (no change found). Set "
        "`window_s` to about one event period (the paper's rule) and tune it first. Follow with Threshold "
        "to get one span per change; the cut depends on the window — a longer window raises the peaks — so "
        "recalibrate the cut whenever you change `window_s` (the fluss_regimes template's 0.46 is for "
        "300 s). Windows touching NaN are not scored, but detrending spreads a NaN gap by about one detrend "
        "window, so check the recording's NaN gaps before trusting a span beside one. Costs a full matrix "
        "profile (O(n²))."
    ),
))
