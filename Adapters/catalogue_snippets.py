"""
catalogue_snippets.py
======================
`catalogue.snippets` — WindowSet -> Grouping: the few typical pieces of a
recording and where each one dominates (Imani et al. 2018, matrix profile
XIII). The algorithm, its deviations from the paper and why are in
`Working.Detection.matrix_profiling.snippets`.

The input windows ARE the pieces: run it after `preprocessing.sliding_windows`
with `gap_s = 0` (contiguous, non-overlapping), so the piece length m is the
window length. Windows with gaps or overlaps are accepted: the pieces are then
cut at multiples of m from the span's start, every window is labelled by the
majority of the stretches centred in it, and `meta["contiguous"]` is False.
The WindowSet's `starts` are channel-absolute (its convention); the span's
offset `t[0] * fs` is subtracted before slicing `x`, as
`catalogue.window_images` does.

Output: one label per window, 1..k (the snippet the window most resembles), or
-1 where the window is more than half NaN (or, never in practice, got no
vote). The exemplar of each label is the snippet itself — a real window of the
recording, never an average — named in `meta["exemplar_windows"]`.

Why not reuse `catalogue.cluster` or `catalogue.shape_cluster`: they cluster a
feature table (or shapes) window against window; snippets compares every piece
against every *position* of the recording with a distance (MPdist) that
tolerates phase shifts and a trend inside a piece, chooses the typical pieces
greedily by how much of the recording they explain, and decides how many by
the paper's knee — none of which a feature clustering does.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.block_cost import estimate_seconds, register_cost_model
from Working.Detection.matrix_profiling.snippets import (
    KNEE_TAIL_PER_SQRT_PIECE,
    KNEE_TAIL_RATIO,
    MAX_NAN_FRACTION,
    find_snippets,
)
from Working.types import Grouping, WindowSet

NAME = "catalogue.snippets"

#: 7 days at 1 Hz. Above it the profiles alone (n/m x n floats) pass ~0.8 GB at
#: 1-hour pieces, and the run would take ~20 min here (O(n²): 24 h took 24 s, 72 h 228 s);
#: the core also refuses any run whose memory peak would exceed MEMORY_LIMIT (4 GB;
#: ~3 GB at 7 days with 1-hour pieces).
MAX_SPAN_SAMPLES = 7 * 24 * 3600

EXEMPLAR_RULE = ("the snippet itself: the piece whose MPdist profile, together with the snippets chosen "
                 "before it, explains the most of the recording (paper Table I) — a real window of the "
                 "recording, never an average")

RULES = [
    {"name": "MPdist",
     "rule": "Distance between two pieces of length m: cut both into every sub-piece of length s = "
             "ceil(subseq_frac × m); for each sub-piece of one, its z-normalised distance to the closest "
             "sub-piece of the other, both ways (2(m − s + 1) values); MPdist is the k-th smallest, k = "
             "ceil(mpdist_percentage × 2m). Robust to a phase shift, a spike or a trend inside a piece. "
             "subseq_frac = 1 makes it the plain z-normalised Euclidean distance."},
    {"name": "snippets",
     "rule": "Each non-overlapping piece's MPdist profile against every position of the recording. "
             "Greedy (paper Table I): the k-th snippet is the piece that most lowers the area under the "
             "minimum of the chosen profiles; Area_k is that area."},
    {"name": "k (knee)",
     "rule": "change_k = Area_(k−1) / Area_k − 1. The knee is the k (2..k_max) with the largest drop "
             "change_k − change_(k+1), kept only if change_k ≥ c × the median of change_(k+1) … "
             f"change_(k_max+1), c = max({KNEE_TAIL_RATIO:g}, {KNEE_TAIL_PER_SQRT_PIECE:g} × √pieces); "
             "otherwise k = 1 (no evidence of a second kind of behaviour). Both are this block's "
             "adaptations: the paper takes the peak of change_k and has no k = 1. Measured on synthetic noise "
             "from 12 to 120 pieces; trust it from 24 pieces on. k > 0 sets it by hand."},
    {"name": "fraction",
     "rule": "The share of the recording's positions whose nearest snippet (lowest profile) is this one; "
             "positions centred in a mostly-NaN window are left out."},
    {"name": "window label",
     "rule": "A position p stands for the stretch starting at p; it votes for the window holding its centre "
             "p + m/2. A window takes the snippet with most votes; a snippet's own window always takes its "
             f"own label. A window more than {MAX_NAN_FRACTION:.0%} NaN is −1."},
    {"name": "regime run length",
     "rule": "A run is a stretch of consecutive windows with one label (−1 ends a run). Mean and median "
             "run length; 'vs shuffled' divides the mean by the mean expected if the same labels were "
             "shuffled (n / (1 + (n − 1)(1 − Σ p²))) — 1 means no more persistent than chance. "
             "runs_by_k (the run lengths at every fixed k) labels the windows without the exemplar "
             "override, so at the chosen k it can differ from the headline run length when windows were "
             "relabelled; compare recordings with runs_by_k."},
    {"name": "NaN",
     "rule": "NaN is filled by a straight line between its finite neighbours before the distances are "
             f"computed (counted); a piece more than {MAX_NAN_FRACTION:.0%} NaN is never a snippet."},
]


def _span_offset(t, fs):
    return int(round(float(t[0]) * float(fs))) if t is not None and len(t) else 0


def _run(x, t, fs, k=0, k_max=6, subseq_frac=0.35, mpdist_percentage=0.05, value=None):
    if value is None:
        raise ValueError(f"{NAME} requires a WindowSet input from a prior step (input_kind='windowset'): "
                         "put Sliding windows (gap 0) before it.")
    if not isinstance(value, WindowSet):
        raise ValueError(f"{NAME} needs a WindowSet (the pieces); got {type(value).__name__}.")
    x = np.asarray(x, dtype=np.float64)
    offset = _span_offset(t, fs)
    rel = np.asarray(value.starts, dtype=np.int64) - offset
    out = find_snippets(x, rel, int(value.length), k=k, k_max=k_max, subseq_frac=subseq_frac,
                        mpdist_percentage=mpdist_percentage)
    labels = out.pop("labels")
    fs = float(fs)
    t0 = float(t[0]) if t is not None and len(t) else 0.0
    starts_s = [t0 + v / fs for v in out["snippet_starts"]]
    runs = out["runs"]
    fr = ", ".join(f"{f:.0%}" for f in out["fractions"])
    nan_part = (f" · {out['n_windows_nan']} of {out['n_windows']} windows mostly NaN (−1)"
                if out["n_windows_nan"] else "")
    run_part = (f" · regime runs mean {runs['mean']:.1f} windows ({runs['ratio']:.1f}× shuffled)"
                if out["k"] > 1 and runs["mean"] is not None else "")
    nr = out["n_exemplar_relabelled"]
    relabel_part = (f" · {nr} exemplar window{'s' if nr != 1 else ''} relabelled to its own snippet"
                    if nr else "")
    summary = (f"k = {out['k']} snippet{'s' if out['k'] != 1 else ''} ({out['k_chosen_by']}) · covering "
               f"{fr}{run_part}{nan_part}{relabel_part}")
    meta = dict(out)
    meta.update({
        "snippet_starts_s": starts_s,
        "m_s": out["m"] / fs,
        "s_s": out["s"] / fs,
        "run_length_mean": runs["mean"],
        "run_length_median": runs["median"],
        "run_length_vs_shuffled": runs["ratio"],
        "exemplar_rule": EXEMPLAR_RULE,
        "rules": RULES,
        "summary": summary,
    })
    return AdapterResult(output_kind="grouping", value=Grouping(labels=np.asarray(labels, dtype=np.int64)),
                         meta=meta)


def _warm_up():
    """Load (or, the first time on a machine, compile) the numba kernel on a
    tiny series — ~6 s once per process, which would otherwise be timed."""
    find_snippets(np.random.default_rng(0).standard_normal(480), np.arange(24) * 20, 20, k_max=3)


def _run_once(x, fs):
    """Cost-model probe: 24 pieces over the calibration series (the work is
    O(n²) whatever the piece length; measured: k from 20 000 samples predicted
    24 s for 24 h at 1 Hz with 1-hour pieces, against 24 s run)."""
    m = max(8, len(x) // 24)
    find_snippets(x, np.arange(len(x) // m) * m, m)


register_cost_model(NAME, exponent=2.0, run_once=_run_once, warm_up=_warm_up)


def _estimate(x, t, fs, **params):
    """Seconds for this span — the work is O(n²) and nearly independent of the
    piece length (n/m pieces × n positions × 2(m − s) sub-piece matches) — or
    None while uncalibrated (`Working.block_cost.calibrate`), never a guess."""
    return estimate_seconds(NAME, len(x))


SPEC = register(AdapterSpec(
    name=NAME,
    display_name="Snippets: the typical pieces of a recording (matrix profile XIII)",
    stage="catalogue",
    category="cluster",
    page_name="Snippets",
    params=[
        ParamSpec("k", int, 0,
                  "How many snippets. 0 = automatic: the paper's knee of the areas curve (k = 1 when no second "
                  "kind of behaviour lowers the area enough). Set it by hand to compare recordings at one k",
                  min=0, max=12),
        ParamSpec("k_max", int, 6,
                  "The largest k the knee may choose; the span must hold at least 2 × k_max pieces",
                  min=2, max=12),
        ParamSpec("subseq_frac", float, 0.35,
                  "MPdist's sub-piece length as a fraction of the piece (the paper's example: 70 of 200). "
                  "Tune this first: smaller tolerates more phase shift and drift inside a piece; 1.0 turns "
                  "MPdist into plain whole-piece distance (stumpy's default — and it lost the regimes on "
                  "drifting synthetic recordings)",
                  min=0.05, max=1.0),
        ParamSpec("mpdist_percentage", float, 0.05,
                  "Which of the sub-piece matches MPdist reports, as a share of 2m: 0.05 (stumpy's default) "
                  "= about the best twentieth — two pieces count as alike when that many of their parts "
                  "match closely; higher demands that more of them match",
                  min=0.0, max=1.0),
    ],
    run=_run,
    input_kind="windowset",
    output_kind="grouping",
    estimate=_estimate,
    max_span_samples=MAX_SPAN_SAMPLES,
    description=(
        "EXPERIMENTAL: on two M2_aug 24 h spans and one known drop chain its regimes were no more persistent "
        "than on phase-randomised surrogates; on a second chain (72 h) its k = 3 regimes were three times as "
        "persistent and beat every surrogate, but its knee chose k = 1 — so set k by hand and read the run "
        "lengths (docs/prompts/blocks/reports/W2-evaluation.md). "
        "What kinds of behaviour does this recording hold, and where? Picks the two to six most typical "
        "pieces (snippets) and colours every window by the snippet it most resembles — like the few "
        "thumbnail frames that best represent a film, with a bar showing which frame each scene is closest "
        "to. Put Sliding windows (gap 0) before it: the windows are the pieces (an hour is a good start) — "
        "and Baseline removal before that. Tune `subseq_frac` first. k = 0 lets the paper's knee choose how "
        "many; k = 1 means no evidence of more than one kind. Shapes are compared after z-normalisation, so "
        "a quiet stretch of pure noise has no shape of its own and is absorbed by whichever snippet it "
        "happens to resemble — read the run lengths: a label that flickers window to window is not a regime. "
        "Trust the automatic k from 24 pieces (24 h of 1-hour pieces) on. Windows more than half NaN are −1. Costs O(n²): about 25 s for 24 h at 1 Hz here; refused above "
        "7 days."
    ),
))
