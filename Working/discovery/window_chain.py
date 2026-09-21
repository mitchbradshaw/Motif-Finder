"""
window_chain.py
=================
Spec §7.8 — "the same window pushed through both runs". Pushes one
in-memory window (a few tens of seconds) through a recipe's steps and
returns what each step produced, so the Compare-every-stage page can draw a
card per stage for run A beside run B.

This is a preview of a *window*, not a run: nothing here writes a `runs`
row, a detection, a step-cache artifact or a `persist` artifact.
`Working.execution.execute_recipe` is what writes runs, and calling it for a
40-second preview would leave a run row and a set of detections behind for a
window nobody asked to analyse.

What it must NOT do is invent a second calling convention. A step that saw a
different argument here than in a real run would make the comparison page a
lie, so the (x, t, fs, **params) call, the side-input resolution and the
signal-threading below mirror `Working.execution._execute_recipe_with_conn`
line for line; each mirrored passage says which behaviour it is copying.

Nothing here imports a UI library (see CLAUDE.md rule 1).
"""

import inspect
import time

import numpy as np

from Adapters.registry import discover_adapters, get_adapter
from Working.side_inputs import resolve_side_inputs, typed_step_value
from Working.types import Signal


def run_window(conn, recipe, x, fs, *, span_start=0, stop_on_error=True):
    """Run every step of `recipe` over the window `x`, recording each step.

    Parameters
    ----------
    conn : sqlite3.Connection or None
        Only ever used for a `library_exemplar` side-input binding's
        recording lookup (`Working.side_inputs`). None is accepted for a
        chain with no such binding — this function reads nothing else from
        the database, and a caller previewing a window off an already-loaded
        array should not have to open a connection to do it.
    recipe : dict
        As built by `Working.recipes.make_recipe`. Its `recording_id` and
        `span` are NOT read: the window is the caller's, not the recipe's.
    x : array-like
        The window's samples.
    fs : float
        Sample rate, in Hz.
    span_start : int
        Index of the window's first sample within its channel. Only used to
        build the absolute time axis `t`, exactly as
        `execution._load_signal` does for a real run, so a step that reads
        `t` (rather than only `x`) sees the same numbers it would there.
    stop_on_error : bool
        When True (the default) the steps after a failed one are not run;
        they are still reported, carrying `error='skipped: step N failed'`.
        When False each later step is attempted on whatever the chain last
        produced.

    Returns
    -------
    list of dict, one per step, in order:
        {'index', 'stage', 'algorithm', 'ok', 'kind', 'value', 'meta', 'error'}
        `algorithm` is the registry name ('detection.threshold'), `kind` the
        step's declared `output_kind`, `value` the typed `Working.types`
        object the step produced (None when it failed), `meta` the adapter's
        own meta plus `elapsed_s`, and `error` a message or None.

    A step that raises is recorded, never propagated: the page draws a stage
    card saying what failed, which is the loud-failure contract. Only the
    caller's own mistakes (an unusable `recipe`) escape as exceptions.
    """
    discover_adapters()  # idempotent; mirrors execute_recipe's first line

    x = np.asarray(x, dtype=float).ravel()
    # execution._load_signal builds `t` as the span's ABSOLUTE time axis
    # (np.arange(start, end) / fs). A window preview keeps that convention so
    # a block that uses `t` for anything but its length behaves identically.
    t = np.arange(span_start, span_start + len(x)) / fs
    root_signal = Signal(x=x, fs=fs)

    entries = []
    current_value = None   # last typed result, for a step whose `run`
                           # declares `value` (execution.py's same name)
    step_results = {}      # {index: typed value}, for `earlier_step`
    failed_index = None

    for i, step in enumerate(recipe["steps"]):
        adapter_name = f"{step['stage']}.{step['algorithm']}"
        entry = {
            "index": i,
            "stage": step["stage"],
            "algorithm": adapter_name,
            "ok": False,
            "kind": None,
            "value": None,
            "meta": {},
            "error": None,
        }

        if failed_index is not None and stop_on_error:
            entry["error"] = f"skipped: step {failed_index} failed"
            entries.append(entry)
            continue

        try:
            spec = get_adapter(adapter_name)
            entry["kind"] = spec.output_kind
            params = spec.validate_params(step.get("params"))

            # execution.py refuses a span longer than a declared
            # max_span_samples before calling `run`, because the block would
            # try to allocate an O(n^2) matrix. Same guard, same reason —
            # recorded rather than raised, as everything else here is.
            if spec.max_span_samples is not None and len(x) > spec.max_span_samples:
                raise ValueError(
                    f"window is {len(x)} samples, which exceeds this block's "
                    f"max_span_samples={spec.max_span_samples}."
                )

            accepted = inspect.signature(spec.run).parameters
            extra = {}
            if spec.side_inputs:
                extra.update(resolve_side_inputs(
                    conn, spec, step.get("side_inputs") or {},
                    root_signal=root_signal, step_results=step_results,
                ))
            # The `value` thread: a typed (non-root-signal) step whose `run`
            # declares `value` receives the previous typed output directly,
            # which is what lets matrix_profile -> threshold pass a `Scores`
            # without going back via (x, t). Copied from execution.py.
            if spec.input_kind is not None and "value" in accepted:
                extra["value"] = current_value

            # execution.py also forwards a `run_kwargs` dict filtered by
            # inspect.signature here. A window preview has no long-running
            # adapter loop to report progress from and no cancellation to
            # offer, so there is nothing to forward; `accepted` is still
            # needed for `value` above.
            t0 = time.time()
            result = spec.run(x, t, fs, **params, **extra)
            elapsed_s = time.time() - t0

            # Every step's typed value is kept. execution.py keeps only the
            # steps some later `earlier_step` binding names, because a whole
            # channel's intermediates would defeat its memory-mapping care;
            # a window of a few tens of seconds costs nothing to keep, and
            # keeping all of them is what lets the page show every stage.
            step_results[i] = typed_step_value(result)

            if result.output_kind == "signal":
                # The chain's time axis is the window's, and a Signal carries
                # no absolute offset, so a signal block that changed the
                # sample count would silently misalign every later stage
                # against the window. execution.py refuses it; so does this.
                if len(result.value.x) != len(t):
                    raise ValueError(
                        f"returned {len(result.value.x)} sample(s) from a "
                        f"{len(t)}-sample window; a 'signal' block must "
                        "preserve the sample count."
                    )
                x = result.value.x

            # A 'spanset' result is span-relative here and stays that way:
            # execution.py adds span_start only because it is writing
            # channel-absolute `detections` rows, and this writes none. The
            # caller holds the window's offset (it passed span_start in).

            if result.value is not None:
                current_value = result.value

            # `spec.persist` is deliberately not called: it writes a file and
            # an `artifacts` row for a run, and this has no run.

            entry["ok"] = True
            entry["value"] = result.value
            entry["meta"] = dict(result.meta or {})
            entry["meta"]["elapsed_s"] = elapsed_s

        except Exception as e:  # noqa: BLE001 — recorded, not propagated
            entry["error"] = str(e) or type(e).__name__
            failed_index = i

        entries.append(entry)

    return entries
