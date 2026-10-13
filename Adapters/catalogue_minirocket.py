"""
catalogue_minirocket.py
=======================
w2-c: the *MiniRocket* block — WindowSet → WindowSet, a feature block: the same
windows (less any left out, counted), with a MiniRocket shape fingerprint
(Dempster, Schmidt & Webb 2021) added to the feature table as `mr_0000 …`
(float32). The core, and every adaptation with its reason, is
`Working/Catalogue/minirocket.py`.

It sits where Catch22 sits in RQ1's chain: Sliding windows (or Trace shape for a
pool) → MiniRocket → Manual labels / Cluster → Classifier, the Classifier's
`windows` side input bound to this step. `catalogue.classifier` is deliberately
NOT changed (a `model` parameter would change the recipe hash of every saved
classifier run): the paper pairs MiniRocket with a ridge classifier, the site's
classifier is a random forest.

Cost: O(windows × length × features), and nearly all of it is the transform and building the
table. The calibration (`Working.block_cost`) first runs an untimed warm-up — the aeon import
(14-45 s in a fresh process) and numba's kernel load, once per process — then times
`CAL_WINDOWS_PER_LENGTH` = 120 windows of 600 samples per 600 samples of the calibration signal
(stride 5: 3,881 windows of the 20,000-sample signal, a second or two of real work) at the
default 10,000 features. The stored `k` is therefore 120 × the seconds per window-sample.
`estimate` only sees the span's length, not the window set, so it assumes the densest grid the
shipped templates make — the labels' 600/200 grid, every sample in `GRID_OVERLAP` = 3 windows —
and scales by the feature count asked for. A window set that tiles the span costs a third of the
estimate; a pool's windows do not come from the span at all, so its estimate is only the span's.
"""

import numpy as np

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register
from Working.block_cost import estimate_seconds, register_cost_model

NAME = "catalogue.minirocket"
COST_MODEL = NAME
_CAL_WINDOW = 600
#: calibration windows per window length of the calibration signal (stride 600 / 120 = 5 samples)
CAL_WINDOWS_PER_LENGTH = 120
#: windows per span sample the estimate assumes: the labels' 600/200 grid
GRID_OVERLAP = 3


def _mr():
    from Working.Catalogue import minirocket as MR
    return MR


def _warm_up():
    """Untimed, before the calibration: import aeon and run one tiny transform (numba loads its kernels)."""
    _mr().fingerprint_matrix(np.random.default_rng(0).standard_normal((4, 64)), n_features=84)


def _time_once(x, fs):
    """The calibration run: `CAL_WINDOWS_PER_LENGTH` windows of 600 samples per 600 samples of the calibration
    signal (stride 5), the default 10,000 features, fitted on the first 80 %."""
    import pandas as pd
    from Working.types import WindowSet
    MR = _mr()
    n = len(x)
    stride = max(1, _CAL_WINDOW // CAL_WINDOWS_PER_LENGTH)
    starts = np.arange(0, n - _CAL_WINDOW + 1, stride, dtype=np.int64)
    split = (np.arange(len(starts)) >= int(0.8 * len(starts))).astype(np.int64) * 2
    ws = WindowSet(starts=starts, length=_CAL_WINDOW, fs=fs, features=pd.DataFrame({"split": split}))
    MR.fingerprint(ws, x, np.arange(n) / fs, fs, n_features=MR.DEFAULT_N_FEATURES)


register_cost_model(COST_MODEL, 1.0, _time_once, warm_up=_warm_up)


def _estimate(x, t, fs, n_features=10_000, **params):
    """Seconds for this span at `n_features` on the labels' 600/200 grid (`GRID_OVERLAP` windows per sample);
    None until `Working.block_cost.calibrate()` has timed it."""
    n = len(x) if x is not None else 0
    base = estimate_seconds(COST_MODEL, n * GRID_OVERLAP / CAL_WINDOWS_PER_LENGTH)
    if base is None:
        return None
    MR = _mr()
    return float(base * MR.real_feature_count(n_features) / MR.real_feature_count(MR.DEFAULT_N_FEATURES))


def _run(x, t, fs, n_features=10_000, max_dilations=32, seed=0, normalise=True, max_cells=50_000_000,
         keep_upstream_features=True, value=None):
    if value is None:
        raise ValueError("MiniRocket needs a WindowSet from a prior step (input_kind='windowset'): put Sliding "
                         "windows, Window matrix or Trace shape before it")
    out = _mr().fingerprint(value, x, t, fs, n_features=n_features, max_dilations=max_dilations, seed=seed,
                            normalise=normalise, max_cells=max_cells,
                            keep_upstream_features=bool(keep_upstream_features))
    return AdapterResult(output_kind="windowset", value=out.windows, meta=out.meta)


def _derive(x, t, fs, params, value=None):
    MR = _mr()
    real = MR.real_feature_count(params["n_features"])
    if value is None:
        return [("Windows", "run a windows block first", "warn"), ("Features", f"{real:,} per window", "")]
    n = int(value.n_windows)
    cells = n * real
    over = cells > int(params["max_cells"])
    feats = value.features
    src = "Trace shape file" if feats is not None and MR.SHAPE_FILE_COLUMN in feats.columns else "the signal"
    mask, _ = MR.train_mask(feats)
    fit = f"{int(mask.sum()):,} training windows" if mask is not None else "every window (no split: optimistic)"
    return [("Windows", f"{n:,} × {int(value.length):,} samples, from {src}",
             "error" if int(value.length) < MR.MIN_LENGTH else ""),
            ("Features", f"{real:,} per window", ""),
            ("Table", f"{cells:,} cells · {cells * 4 / 1e6:,.0f} MB", "error" if over else
             ("warn" if cells * 4 > 500e6 else "")),
            ("Fitted on", fit, "" if mask is not None else "warn")]


SPEC = register(AdapterSpec(
    name=NAME,
    display_name="MiniRocket shape fingerprint (WindowSet -> WindowSet + features)",
    stage="catalogue",
    category="encode",
    page_name="MiniRocket",
    params=[
        ParamSpec("n_features", int, 10_000,
                  "How many fingerprint numbers per window (the paper's 10,000; aeon rounds down to a multiple of "
                  "84, and the real count is shown). Tune this first: fewer is faster and smaller — the table is "
                  "windows × features × 4 bytes, so a whole channel on the 10-minute labels' grid (~13,000 "
                  "windows) needs about 1,000 to stay under max_cells. But fewer features lose real accuracy on "
                  "weak shapes: a 'no' at 1,000 is not a 'no' — the decisive run is 10,000 on a shorter span.",
                  min=84, max=50_000),
        ParamSpec("max_dilations", int, 32,
                  "Most spacings per pattern detector (the paper's 32): how far apart the 9 taps of a detector may "
                  "be spread, up to the whole window.", min=1, max=128),
        ParamSpec("seed", int, 0,
                  "Which random training windows the detectors' cut-offs are read from; the same seed gives the "
                  "same fingerprint.", min=0),
        ParamSpec("normalise", bool, True,
                  "z-normalise each window first (minus its mean, over its spread), so the fingerprint is about "
                  "shape, not level or size — as the paper's data are. Off: the window as it is."),
        ParamSpec("max_cells", int, 50_000_000,
                  "Refuse a table of more than this many numbers (windows × features; 50 M = 200 MB): a memory "
                  "guard. Lower n_features before raising it.", min=1),
        ParamSpec("keep_upstream_features", bool, True,
                  "Keep the measures the windows already carried (Catch22, entropies) beside the fingerprint. Off: "
                  "only the fingerprint and bookkeeping (split, pool and shape-file columns) go on, so a classifier "
                  "learns from the shape fingerprint alone — what an arm compared against Catch22 needs."),
    ],
    run=_run,
    estimate=_estimate,
    derive=_derive,
    input_kind="windowset",
    output_kind="windowset",
    description=(
        "Gives every window a shape fingerprint: about ten thousand tiny fixed pattern detectors, and for each the "
        "fraction of the window where it fires (MiniRocket, Dempster, Schmidt & Webb 2021). A classifier can learn "
        "from it in seconds — it answers 'can this label be learned from the raw shape at all?', but the numbers "
        "mean nothing one by one. Fitted on the training windows only (the split column), never on labels; each "
        "window z-normalised first. Without a split (Window matrix on the labels' 600/200 grid) it fits on every "
        "window and says so: acceptable there, because the fit only reads cut-offs from window shapes and never "
        "sees a label. Tune n_features first: it sets the table's size and the time."
    ),
))
