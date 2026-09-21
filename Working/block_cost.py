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
import time

import numpy as np

CALIBRATION_PATH = os.path.join("DATA", "db", "block_calibration.json")
CALIBRATION_N = 20_000

# block name -> (exponent, callable(x, fs) that runs the block's core once)
# The callables are resolved lazily so importing this module stays cheap.
MODELS = {}


def register_cost_model(name, exponent, run_once):
    """Declare how `name` scales (`seconds = k * n ** exponent`) and how to
    time it. `run_once(x, fs)` must execute the block's algorithm on the
    synthetic signal `x` at sample rate `fs` with default-ish parameters."""
    MODELS[name] = (float(exponent), run_once)


def _key(name):
    return json.dumps({
        "block": name,
        "cpu_count": multiprocessing.cpu_count(),
        "python": platform.python_version(),
    }, sort_keys=True)


def _load():
    if not os.path.isfile(CALIBRATION_PATH):
        return {}
    with open(CALIBRATION_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data):
    directory = os.path.dirname(CALIBRATION_PATH) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=os.path.basename(CALIBRATION_PATH) + ".", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp, CALIBRATION_PATH)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def calibrate(names=None, force=False, n=CALIBRATION_N, fs=1.0):
    """Time every registered cost model (or the `names` given) once on a
    synthetic signal and store `k`. Returns {name: k}."""
    names = list(MODELS) if names is None else list(names)
    data = _load()
    out = {}
    for name in names:
        exponent, run_once = MODELS[name]
        key = _key(name)
        if not force and key in data:
            out[name] = data[key]["k"]
            continue
        x = np.cumsum(np.random.default_rng(0).standard_normal(int(n))) * 1e-3
        t0 = time.perf_counter()
        run_once(x, fs)
        elapsed = time.perf_counter() - t0
        k = elapsed / (float(n) ** exponent)
        data[key] = {"k": k, "exponent": exponent, "n": int(n), "elapsed_s": elapsed,
                     "calibrated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        out[name] = k
    _save(data)
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
