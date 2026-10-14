"""
block_cost.py
==============
Per-machine cost calibration for blocks whose runtime is a simple function
of the span length — the generic counterpart of the bespoke calibrations
`Working.Detection.matrix_profiling.cost` (O(n²) matrix profile) and
`Working.Preprocessing.window_matrix.cost` (per-window measures) keep for
themselves.

A block declares its cost model once, by name, in `MODELS`: seconds are
`k * n ** exponent` for a span of `n` samples, with `k` measured on THIS
machine by timing the block on a synthetic signal of `CALIBRATION_N`
samples and stored in `DATA/db/block_calibration.json` keyed by
(block, cpu_count, python). `estimate_seconds` returns `None` while
uncalibrated — the same "never guess" contract the two bespoke modules
follow, so a wrong number can never route a long job into the interactive
path.

Calibrate from a shell (a few seconds per block):

    python -c "from Working.block_cost import calibrate; print(calibrate())"

No UI imports; plain numpy and json.
"""

import json
import multiprocessing
import os
import platform
import tempfile
import threading
import time

import numpy as np

CALIBRATION_PATH = os.path.join("DATA", "db", "block_calibration.json")
CALIBRATION_N = 20_000

# block name -> (exponent, callable(x, fs) that runs the block's core once)
# The callables are resolved lazily so importing this module stays cheap.
MODELS = {}

# block name -> callable() run once, untimed, before `run_once` is timed: a
# block whose first call in a process pays a one-off cost (numba loading its
# compiled kernels) would otherwise calibrate several times too slow.
WARM_UPS = {}


def register_cost_model(name, exponent, run_once, warm_up=None):
    """Declare how `name` scales (`seconds = k * n ** exponent`) and how to
    time it. `run_once(x, fs)` must execute the block's algorithm on the
    synthetic signal `x` at sample rate `fs` with default-ish parameters;
    `warm_up()`, if given, runs first and is not timed."""
    MODELS[name] = (float(exponent), run_once)
    if warm_up is not None:
        WARM_UPS[name] = warm_up


def _key(name):
    return json.dumps({
        "block": name,
        "cpu_count": multiprocessing.cpu_count(),
        "python": platform.python_version(),
    }, sort_keys=True)


#: Guards the calibration file's read-merge-write within one process (two threads timing two models at once).
_FILE_LOCK = threading.Lock()


def _load(path=None):
    path = path or CALIBRATION_PATH
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data, path=None):
    path = path or CALIBRATION_PATH
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + ".", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def calibrate(names=None, force=False, n=CALIBRATION_N, fs=1.0, path=None):
    """Time every registered cost model (or the `names` given) once on a
    synthetic signal and store `k`. Returns {name: k}.

    `path` (default `CALIBRATION_PATH`, read at call time) is fixed for the
    whole call: a caller that times a model in a background thread (the web
    bridge, W3-F) passes the path it resolved when it started, so a redirect
    restored while the timing runs cannot send the result to another file."""
    path = path or CALIBRATION_PATH
    names = list(MODELS) if names is None else list(names)
    data = _load(path)
    out = {}
    for name in names:
        exponent, run_once = MODELS[name]
        key = _key(name)
        if not force and key in data:
            out[name] = data[key]["k"]
            continue
        x = np.cumsum(np.random.default_rng(0).standard_normal(int(n))) * 1e-3
        if name in WARM_UPS:
            WARM_UPS[name]()
        t0 = time.perf_counter()
        run_once(x, fs)
        elapsed = time.perf_counter() - t0
        k = elapsed / (float(n) ** exponent)
        data[key] = {"k": k, "exponent": exponent, "n": int(n), "elapsed_s": elapsed,
                     "calibrated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        out[name] = k
    # re-read before writing: another process — or another thread timing another model (the web bridge times
    # models side by side) — may have stored a model while this one was timing. The lock covers only this
    # read-merge-write, never the timing.
    with _FILE_LOCK:
        merged = _load(path)
        merged.update({_key(name): data[_key(name)] for name in names if _key(name) in data})
        _save(merged, path)
    return out


def calibration_status(name):
    """`{'calibrated': bool, 'k': float | None, 'exponent': float | None}`."""
    data = _load().get(_key(name))
    exponent = MODELS.get(name, (None, None))[0]
    if data is None:
        return {"calibrated": False, "k": None, "exponent": exponent}
    return {"calibrated": True, "k": float(data["k"]), "exponent": float(data.get("exponent", exponent))}


def estimate_seconds(name, n_samples):
    """Seconds for `name` over `n_samples`, or None while uncalibrated."""
    status = calibration_status(name)
    if not status["calibrated"]:
        return None
    return float(status["k"] * float(n_samples) ** status["exponent"])
