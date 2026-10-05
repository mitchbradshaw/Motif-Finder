"""
preprocessing_trace_shape.py
============================
fixup-ag: the *Trace shape* block — WindowSet → WindowSet (ticket
`docs/prompts/fixup/AG-…` "What to build" 2).

Every window of a pool is resampled to the Library's own length and
z-normalised with the Library's own helpers (`Working.training.shape.
trace_shapes` → `Working.library.grouping.methods.ward.shape_vectors`), so a
1-minute and a 30-minute window are compared by shape, not by duration.
Normalising throws amplitude away, so a window under its dataset's noise floor
(Settings › Datasets, 0.1 mV where empty) is LEFT OUT by default — counted per
recording, scale and role — and every window keeps its raw range beside it.
The switch turns the floor off.

The vectors are a bulk array: written to disk under `RESULTS_DIR` (rule 4),
content-keyed, and named on every window of the output (`shape_file`), so the
clustering step reads them by path. The output WindowSet is the kept windows,
with their pool metadata plus `shape_raw_range_mv`, `shape_peak_frac` (where in
the window the largest excursion sits, 0–1) and `shape_row`.
"""

import os

from Adapters.base import AdapterResult, AdapterSpec, ParamSpec
from Adapters.registry import register

#: where the vectors are written; the bridge's sandbox redirects it (runtime.py)
RESULTS_DIR = os.path.join("DATA", "derived", "trace_shapes")


def _default(name):
    from Working.training import shape as tshape
    return getattr(tshape, name)


def _resample_default():
    from Working.library.grouping.methods.ward import RESAMPLE_LENGTH
    return RESAMPLE_LENGTH


def _run(x, t, fs, resample_length=None, noise_floor=True, align=None, detrend=None, value=None, conn=None,
         recording=None):
    from Working.training import shape as tshape
    if conn is None:
        raise ValueError("the Trace shape block reads each window's trace and its dataset's noise floor from the "
                         "store and needs its connection")
    if value is None:
        raise ValueError("Trace shape needs the windows of a Window pool before it")
    frame = tshape.pool_frame(value)
    n = int(resample_length or _resample_default())
    shapes = tshape.trace_shapes(conn, frame, resample_length=n, noise_floor=bool(noise_floor),
                                 align=align or tshape.DEFAULT_ALIGN, detrend=detrend or tshape.DEFAULT_DETREND)
    d = os.path.join(RESULTS_DIR, shapes.key)
    path = os.path.join(d, "shapes.npz")
    if not os.path.isfile(path):
        path = shapes.save(d)
    meta = {k: shapes.meta[k] for k in ("resample_length", "noise_floor", "floors", "n_in", "n_kept", "under_floor",
                                        "unmeasured", "method", "seconds", "align", "detrend", "align_rule",
                                        "detrend_rule", "swing_rule", "recut")}
    meta.update({"shape_file": os.path.abspath(path), "shape_key": shapes.key})
    return AdapterResult(output_kind="windowset", value=tshape.frame_windowset(shapes.frame, os.path.abspath(path)),
                         meta=meta)


def _estimate(x, t, fs, **params):
    """Reading 60,000 windows of 1, 10 and 30 minutes from their channels: about 20 s on this machine."""
    return 20.0


SPEC = register(AdapterSpec(
    name="preprocessing.trace_shape",
    display_name="Trace shape (WindowSet -> WindowSet, resampled + z-normalised)",
    stage="preprocessing",
    category="preprocess",
    page_name="Trace shape",
    params=[
        ParamSpec("resample_length", int, _resample_default(),
                  "Points every window is resampled to before z-normalising — the Library's own length, so a "
                  "distance here means what it means in the Library.", min=8),
        ParamSpec("align", str, _default("DEFAULT_ALIGN"),
                  "grid: the window as the pool cut it. centre: re-cut, the same length, centred on its largest swing "
                  "(trend removed, a running median so a glitch cannot be it), kept inside its own role's stretch and "
                  "clear of artifact spans; a window that cannot be centred is shifted as far as allowed (counted); "
                  "two windows that centre onto one event keep one (counted).", choices=["grid", "centre"]),
        ParamSpec("detrend", str, _default("DEFAULT_DETREND"),
                  "off: the trace as it is. linear: the window's straight line removed before the resample and "
                  "normalise, so a slow drift is not the shape.", choices=["off", "linear"]),
        ParamSpec("noise_floor", bool, True,
                  "Leave out windows whose raw range is under their dataset's noise floor (Settings › Datasets; "
                  "0.1 mV where empty). Normalising throws amplitude away: a wiggle and a drop would look alike."),
    ],
    run=_run,
    input_kind="windowset",
    output_kind="windowset",
    estimate=_estimate,
    description=("Resamples every window of a pool to one length and z-normalises it (the Library's shape "
                 "method), keeps its raw range, and leaves out windows under the noise floor, counted."),
))
