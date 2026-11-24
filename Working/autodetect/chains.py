"""
chains.py
=========
A detection template's steps, run on samples held in memory.

In plain words: a template is a recipe of blocks (detrend, then encode, then detect). The tool normally runs one
through `Working.execution.execute_recipe`, which writes a `runs` row, every detection and a step cache. Auto-detect
needs the detections only, quickly and without touching the database, so this runs the same blocks with the same
calling convention and keeps the spans in memory.

What it keeps of the executor (`Working.execution._execute_recipe_with_conn`), so a template behaves here as it does
there:

* each step's adapter is looked up by ``stage.algorithm`` and its params validated by the adapter itself;
* every block is handed the current signal and the span's absolute time axis; a typed step that declares ``value``
  receives the previous typed step's output; a block that declares ``units`` is told the recording's unit (the
  researcher's choice, 2026-10-15: samples are handed over as stored);
* a ``signal`` step must preserve the sample count;
* the spans written are those of a step that outputs a SpanSet from a non-SpanSet input (a SpanSet -> SpanSet
  block measures spans; it does not detect them).

What it leaves out, on purpose: side inputs and blocks that need the database (refused, by name), the step cache,
and ``persist`` hooks (nothing is written anywhere).
"""

from __future__ import annotations

import inspect
import time

import numpy as np

from Adapters.registry import discover_adapters, get_adapter


class ChainError(RuntimeError):
    """A template this module cannot run in memory, or a block that broke the executor's contract."""


def run_chain(steps, x, fs, *, start_idx=0, units=None):
    """Run ``steps`` (a template's ``steps_json``, parsed) over ``x``.

    Parameters
    ----------
    steps : list of dict
        ``{"stage", "algorithm", "params", "side_inputs"}`` as a template stores them.
    x : array
        The samples, in the recording's stored unit.
    fs : float
        Sampling rate, Hz.
    start_idx : int
        The channel index of ``x[0]``; only the time axis handed to the blocks depends on it.
    units : str or None
        The recording's declared unit, for blocks that declare ``units``.

    Returns
    -------
    dict
        ``{"starts", "ends", "scores"}`` (int arrays relative to ``x``, a float array with NaN where a block gave no
        score) and ``"timings"`` (seconds per step).
    """
    discover_adapters()
    x = np.asarray(x, dtype=float)
    t = (int(start_idx) + np.arange(len(x))) / float(fs)
    current_value = None
    starts, ends, scores, timings = [], [], [], []
    last = None
    for i, step in enumerate(steps):
        name = f"{step['stage']}.{step['algorithm']}"
        if step.get("side_inputs"):
            raise ChainError(f"step {i} ({name}) binds side inputs; auto-detect runs templates without them")
        spec = get_adapter(name)
        params = spec.validate_params(step.get("params"))
        if spec.max_span_samples is not None and len(x) > spec.max_span_samples:
            raise ChainError(f"step {i} ({name}): {len(x)} samples exceed its max_span_samples "
                             f"({spec.max_span_samples})")
        accepted = inspect.signature(spec.run).parameters
        if "conn" in accepted:
            raise ChainError(f"step {i} ({name}) reads the database; auto-detect runs without one")
        extra = {}
        if spec.input_kind is not None and "value" in accepted:
            extra["value"] = current_value
        if "units" in accepted:
            extra["units"] = units
        t0 = time.perf_counter()
        result = spec.run(x, t, fs, **params, **extra)
        timings.append(time.perf_counter() - t0)
        if result.output_kind == "signal":
            nx = np.asarray(result.value.x, dtype=float)
            if len(nx) != len(t):
                raise ChainError(f"step {i} ({name}) returned {len(nx)} samples from a {len(t)}-sample span")
            x = nx
        elif result.output_kind == "spanset" and spec.input_kind != "spanset":
            ss = result.value
            sc = ss.scores or (None,) * len(ss.starts)
            starts.extend(int(s) for s in ss.starts)
            ends.extend(int(e) for e in ss.ends)
            scores.extend(np.nan if v is None else float(v) for v in sc)
        if result.value is not None:
            current_value = result.value
        last = result
    if last is None:
        raise ChainError("the template has no steps")
    return {"starts": np.asarray(starts, dtype=np.int64), "ends": np.asarray(ends, dtype=np.int64),
            "scores": np.asarray(scores, dtype=float), "timings": timings}


def run_chain_windowed(steps, x, fs, *, window_s, overlap=None, fit=False, start_idx=0, units=None):
    """``run_chain`` over sliding windows, stitched: the tool's own window scope (`Working.discovery.windowed`,
    2026-10-17: "drop detection should run over sliding windows with overlap"), in memory.

    Each window is judged on its own scale, so a quiet stretch is not held to a loud week's bar. The windows, their
    cores, the bound (a window at least 4 x the chain's longest averaging stretch, else refused — or, with ``fit``,
    every averaging stretch scaled down to a quarter of the window) and the stitch (one event once, kept from the
    window whose core holds its onset) are that module's, unchanged. A stretch shorter than one window runs whole.

    Returns `run_chain`'s dict plus ``windows`` (how many) and ``changes`` (what fitting changed)."""
    from Working.discovery import windowed as W

    overlap = W.DEFAULT_OVERLAP if overlap is None else float(overlap)
    if fit:
        steps, changes = W.fit_steps(steps, fs, window_s)
    else:
        refusal = W.bound_refusal(steps, fs, window_s)
        if refusal:
            raise ChainError(refusal)
        changes = []
    a, n = int(start_idx), len(x)
    spans = W.window_spans(a, a + n, W.window_samples(window_s, fs), overlap)
    if not spans:
        out = run_chain(steps, x, fs, start_idx=start_idx, units=units)
        out.update(windows=0, changes=changes)
        return out
    cores = W.window_cores(spans, a, a + n)
    wins, total = [], 0.0
    for k, ((s0, s1), core) in enumerate(zip(spans, cores)):
        out = run_chain(steps, np.asarray(x)[s0 - a:s1 - a], fs, start_idx=s0, units=units)
        total += sum(out["timings"])
        wins.append({"index": k, "span": (s0, s1), "core": core,
                     "spans": [(int(s) + s0, int(e) + s0, None if not np.isfinite(sc) else float(sc))
                               for s, e, sc in zip(out["starts"], out["ends"], out["scores"])]})
    st = W.stitch(wins)
    kept = st["spans"]
    return {"starts": np.asarray([sp["start"] - a for sp in kept], dtype=np.int64),
            "ends": np.asarray([sp["end"] - a for sp in kept], dtype=np.int64),
            "scores": np.asarray([np.nan if sp.get("score") is None else float(sp["score"]) for sp in kept],
                                 dtype=float),
            "timings": [total], "windows": len(spans), "changes": changes}
