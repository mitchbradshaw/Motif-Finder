"""Chain composition helpers over the untouched core.

Uses ``Adapters.registry`` (the block registry), ``Working.chain_validation``
(``check_step_compatibility``), ``Working.recipes.make_recipe``,
``Working.execution.invalidated_step_indices`` / ``_recipe_prefix_hash`` and
``Working.hpc.job_export.estimate_recipe_seconds``.

Why ``UI/analyse/chain_state.py`` is not imported: it is headless in itself,
but ``import UI.analyse.chain_state`` executes ``UI/analyse/__init__.py``,
which imports ``RunPanel`` and with it Panel/Bokeh/HoloViews; it also only
answers "what can be appended at the tail" and drops side-inputs on
``to_recipe``. The ~40 lines below cover insert-at-position validation the
way ``UI/workspaces/analyse/builder.py`` does it.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from typing import Any

from Adapters.registry import discover_adapters, get_adapter, list_adapters
from Working.chain_validation import ROOT_SIGNAL_KIND, check_source_position, check_step_compatibility
from Working.execution import _recipe_prefix_hash, invalidated_step_indices, recording_units
from Working.hpc.job_export import estimate_recipe_seconds
from Working.recipes import make_recipe, recipe_hash, short_hash
from Working.database.queries import get_recording_by_id
from Working.database.runs import get_step_artifact

from . import views as views_mod
from Working import block_cost as _block_cost

_REAL_CALIBRATE = _block_cost.calibrate   # site-x: a stand-in (tests) is not sent to a calibration process

discover_adapters()

# `category`, `page_name` and `known_broken` live on `AdapterSpec` (stage-3
# block standard, docs/BLOCK_INTEGRATION.md): the bridge keeps no side table.
TYPE_LABEL = {"signal": "Signal", "spanset": "SpanSet", "windowset": "WindowSet", "encoding": "Encoding",
              "grouping": "Grouping", "model": "Model", "scores": "Scores"}


def _ptype(t) -> str:
    return {int: "int", float: "float", str: "str", bool: "bool"}.get(t, getattr(t, "__name__", str(t)))


def adapter_card(spec) -> dict:
    in_kind = spec.input_kind or ROOT_SIGNAL_KIND
    return {
        "name": spec.name, "stage": spec.stage, "algorithm": spec.name.split(".", 1)[1],
        "display_name": spec.display_name, "page_name": spec.page_name,
        "description": spec.description or "",
        "input_kind": in_kind, "output_kind": spec.output_kind,
        "signature": f"{TYPE_LABEL.get(in_kind, in_kind)} → {TYPE_LABEL.get(spec.output_kind, spec.output_kind)}",
        "category": spec.category,
        # the drawing standard (fixup-h): the picture is a consequence of the type signature
        **views_mod.resolve(spec),
        "has_estimate": spec.estimate is not None,
        "has_derive": spec.derive is not None,
        "max_span_samples": spec.max_span_samples,
        "has_recommend": spec.recommend is not None,
        # W3-B: an optional side input (cycle shapes' waveform) is not shown as one the block needs
        "side_inputs": [{"name": s.name, "type_kind": s.type_kind, "sources": list(s.sources),
                         "required": bool(getattr(s, "required", True))} for s in spec.side_inputs],
        "known_broken": spec.known_broken,
        # fixup-ag: a source block (Window pool) starts a chain in place of a span and can only be step 01
        "source": bool(getattr(spec, "source", False)),
        "params": [{
            "name": p.name, "type": _ptype(p.type), "default": p.default, "description": p.description or "",
            "choices": list(p.choices) if p.choices is not None else None, "min": p.min, "max": p.max,
        } for p in spec.params],
    }


def catalog() -> list[dict]:
    return [adapter_card(s) for s in list_adapters()]


def _name(step: dict) -> str:
    return f"{step['stage']}.{step['algorithm']}"


def validate(steps: list[dict]) -> dict:
    """Every junction, not just the first (the page draws the red pill *at* the
    junction). ``junctions[i]`` is the junction *into* step i."""
    producing = ROOT_SIGNAL_KIND
    junctions = []
    ok_all = True
    terminal = ROOT_SIGNAL_KIND
    for i, step in enumerate(steps):
        try:
            spec = get_adapter(_name(step))
        except KeyError:
            junctions.append({"index": i, "ok": False, "producing": producing, "expected": None,
                              "reason": f"unknown block {_name(step)!r}"})
            ok_all = False
            continue
        ok, reason = check_step_compatibility(producing, spec)
        expected = spec.input_kind or ROOT_SIGNAL_KIND
        why = "" if ok else f"{spec.page_name} needs {TYPE_LABEL.get(expected, expected)} · previous emits {TYPE_LABEL.get(producing, producing)}"
        src_ok, src_reason = check_source_position(i, spec)
        if not src_ok:
            ok, reason, why = False, src_reason, f"{spec.page_name} is a chain source · it can only be step 01"
        junctions.append({"index": i, "ok": bool(ok), "producing": producing, "expected": expected,
                          "reason": why, "core_reason": reason, "source": not src_ok or None})
        ok_all = ok_all and bool(ok)
        producing = spec.output_kind
        terminal = spec.output_kind
    # The kind `templates.kind_for_steps` will SAVE this chain as (fixup-aa): the
    # footer prints this rather than keeping a second table of which terminals
    # are template types — the two disagreed on Grouping. None when the chain
    # does not validate or has no stages.
    from .templates import kind_for_steps
    template_kind = kind_for_steps(steps) if steps and ok_all else None
    return {"ok": ok_all, "junctions": junctions, "terminal_kind": terminal if steps else None,
            "terminal_label": TYPE_LABEL.get(terminal) if steps else None, "template_kind": template_kind}


def compatible_at(steps: list[dict], position: int) -> dict:
    """Which blocks may be inserted at ``position`` (0 = before the first
    step, len(steps) = append). Mirrors builder.py's two-sided check."""
    position = max(0, min(len(steps), int(position)))
    if position == 0:
        producing = ROOT_SIGNAL_KIND
    else:
        try:
            producing = get_adapter(_name(steps[position - 1])).output_kind
        except KeyError:
            producing = ROOT_SIGNAL_KIND
    next_spec = None
    if position < len(steps):
        try:
            next_spec = get_adapter(_name(steps[position]))
        except KeyError:
            next_spec = None
    rows = []
    for spec in list_adapters():
        ok, reason = check_step_compatibility(producing, spec)
        expected = spec.input_kind or ROOT_SIGNAL_KIND
        why = ""
        if not ok:
            why = f"needs {TYPE_LABEL.get(expected, expected)} · here: {TYPE_LABEL.get(producing, producing)}"
        elif next_spec is not None:
            ok2, _ = check_step_compatibility(spec.output_kind, next_spec)
            if not ok2:
                nexp = next_spec.input_kind or ROOT_SIGNAL_KIND
                ok = False
                why = f"emits {TYPE_LABEL.get(spec.output_kind, spec.output_kind)} · next needs {TYPE_LABEL.get(nexp, nexp)}"
        if ok and position > 0 and getattr(spec, "source", False):
            ok, why = False, "a chain source · only as step 01"
        if ok and spec.known_broken:
            why = "fits · " + spec.known_broken
        rows.append({"name": spec.name, "ok": bool(ok), "reason": why})
    n_fit = sum(1 for r in rows if r["ok"])
    return {"position": position, "producing": producing, "producing_label": TYPE_LABEL.get(producing, producing),
            "next_requires": (next_spec.input_kind or ROOT_SIGNAL_KIND) if next_spec else None,
            "next_requires_label": TYPE_LABEL.get((next_spec.input_kind or ROOT_SIGNAL_KIND), (next_spec.input_kind or ROOT_SIGNAL_KIND)) if next_spec else None,
            "next_name": next_spec.page_name if next_spec else None,
            "n_fit": n_fit, "n_total": len(rows), "rows": rows,
            "stale_from": position if position < len(steps) else None}


def validated_params(step: dict) -> dict:
    spec = get_adapter(_name(step))
    return spec.validate_params(step.get("params") or {})


def build_recipe(recording_id: int, span: tuple[int, int] | None, steps: list[dict]) -> dict:
    """Params are normalised through the adapter's own ``validate_params`` (defaults filled,
    coerced) BEFORE hashing, so a chain with an explicit default and the same chain without it
    share one recipe hash and therefore one step-cache prefix (critique r1)."""
    norm = []
    for s in steps:
        try:
            params = get_adapter(f"{s['stage']}.{s['algorithm']}").validate_params(s.get("params") or {})
        except KeyError:
            params = s.get("params") or {}
        norm.append({"stage": s["stage"], "algorithm": s["algorithm"], "params": params,
                     "side_inputs": s.get("side_inputs") or {}})
    return make_recipe(recording_id, norm, span=span)


def estimate(recipe: dict, n_samples: int, fs: float) -> dict:
    """Per-step seconds. A step whose estimator answers None (uncalibrated on this
    machine) or raises is reported as ``null`` and listed in ``unknown`` — never as
    0.0 (docs/BLOCK_INTEGRATION.md §3: the honest answer routes to "unknown", not to a
    spinner). ``total_s`` sums the known steps; a block with no estimator is free."""
    from Working.hpc.job_export import _Span
    per_step, unknown, errors, calibrating = [], [], {}, []
    for i, step in enumerate(recipe["steps"]):
        spec = get_adapter(f"{step['stage']}.{step['algorithm']}")
        if spec.estimate is None:
            per_step.append(0.0)
            continue
        try:
            v = spec.estimate(_Span(n_samples), None, fs, **step["params"])
        except Exception as e:      # an estimator that raises is not "free"
            v = None
            errors[i] = f"{type(e).__name__}: {e}"
        if v is None:
            per_step.append(None); unknown.append(i)
            # why it is unknown, in words the page prints (W2-ledger decision 24): a cost model still being
            # timed on this machine, or one whose timing failed
            for name in _block_cost_models(step):
                st = block_calibration_state(name)
                if st["state"] == "calibrating" and i not in calibrating:
                    calibrating.append(i)
                elif st["state"] == "failed" and i not in errors:
                    errors[i] = f"calibrating {name} failed: {st['error']}"
        else:
            per_step.append(float(v))
    fan = recipe.get("fan_out")
    width = len(fan["targets"]) if fan else 1
    total = sum(v for v in per_step if v is not None) * width
    return {"total_s": total, "per_step_s": per_step, "unknown": unknown, "errors": errors,
            "calibrating": calibrating, "route": "unknown" if unknown else "local"}


ANALYSE_LIMIT_KEY = "limit.Analyse"     # Settings › Compute & HPC, minutes


def analyse_ceiling_s(conn=None) -> int:
    """The Analyse local limit in seconds: Settings › Compute & HPC ``limit.Analyse`` (minutes) when saved, else
    ``Working.config.CLUSTER_ROUTING_CEILING_S`` — the core's one routing ceiling (PRD "Cluster routing")."""
    from Working.config import CLUSTER_ROUTING_CEILING_S
    from Working.discovery.fanout import CEILING_PAGE
    if conn is not None:
        from Working.registration.settings import get_settings
        saved = get_settings(conn, CEILING_PAGE).get(ANALYSE_LIMIT_KEY)
        if saved is not None:
            minutes = float(saved)
            if minutes <= 0:
                raise ValueError(f"Settings › Compute & HPC {ANALYSE_LIMIT_KEY!r} must be positive, got {minutes}")
            return int(round(minutes * 60))
    return int(CLUSTER_ROUTING_CEILING_S)


def _calibrate_matrix_profile() -> dict:
    """Time this machine's matrix profile once (a few seconds, `cost.calibrate`): the FLUSS and matrix-profile
    blocks estimate from it, and without it they answer None — which used to let a days-long FLUSS run start."""
    import time
    from Working.Detection.matrix_profiling import cost
    t0 = time.time()
    entry = cost.calibrate("stump")
    return {"calibrated": True, "seconds": round(time.time() - t0, 1), "k": entry["k"],
            "path": os.path.abspath(cost.CALIBRATION_PATH)}


def _uses_mp_cost(step: dict) -> bool:
    """Does this step's adapter estimate with the matrix-profile cost model (FLUSS, matrix profile)? Read off
    the adapter module importing from `Working.Detection.matrix_profiling.cost` — so calibrating that model can
    answer it. Another uncalibrated estimator (its own cost model) is left as ``unknown``, not calibrated here."""
    import sys
    from Working.Detection.matrix_profiling import cost
    spec = get_adapter(f"{step['stage']}.{step['algorithm']}")
    mod = sys.modules.get(getattr(spec.estimate, "__module__", ""), None)
    return mod is not None and any(getattr(v, "__module__", None) == cost.__name__ for v in vars(mod).values())


# ── the generic block cost models (`Working.block_cost`), calibrated on first need (W3-F item 2) ──────────────
# Measured 2026-10-15 on this machine (fresh process after the registry import; `calibrate([name], force=True)`,
# warm-ups included): rupture 447 s (Pelt on the calibration's random walk), snippets 19.8 s (numba compile),
# MiniRocket 7.5 s (61.5 s when aeon is not yet imported), cycle shapes 4.6 s, deconvolve 2.9 s, MSE 2.1 s, the
# rest under 1.5 s; warm, every one but rupture under 3 s. Holding POST /api/chain/validate for 20 s — let alone
# 7 min — is not acceptable, so a model is calibrated in a background thread the first time a chain needs it, and
# `route_local` waits up to CALIBRATION_WAIT_S for it: most land inside the request, the slow ones read
# "calibrating" (the page re-validates until they land). Lazily, not at bridge start: before `Runtime.setup()`
# the calibration file still points at the checkout's DATA/db, and most models are never needed in a session.

#: How long one request waits for a background calibration before answering "calibrating".
CALIBRATION_WAIT_S = 10.0
#: A failed calibration (a block that cannot run here: no model checkpoint) is retried after this long.
CALIBRATION_RETRY_S = 60.0

_BC_LOCK = threading.Lock()          # guards the state table
# W3-F fix 1: no lock across models. One model is timed by one thread at a time (the state table says
# "calibrating"), different models time side by side, and `block_cost.calibrate` holds its own lock only around the
# file's read-merge-write — so rupture's 7-minute timing never holds MSE or snippets. Side by side (or beside a run
# in the same process) a timing is inflated by CPU contention; that errs toward refusing a run, never toward
# starting one too long for the machine.
_BC_STATE: dict[str, dict] = {}
_BC_THREADS: dict[str, threading.Thread] = {}


def reset_block_calibration() -> None:
    """Forget every background calibration's state (tests; a bridge restart does the same). A calibration still
    running keeps its own file (resolved when it started) and its result is dropped, so it cannot write into what
    comes after the reset."""
    with _BC_LOCK:
        _BC_STATE.clear()
        _BC_THREADS.clear()


def block_calibration_state(name: str) -> dict:
    """`{state: 'calibrated' | 'calibrating' | 'failed' | 'uncalibrated', seconds, error}` for one model."""
    from Working import block_cost
    with _BC_LOCK:
        st = dict(_BC_STATE.get(name) or {})
    if st.get("state") in ("calibrating", "failed"):
        return {"state": st["state"], "seconds": st.get("seconds"), "error": st.get("error")}
    if name in block_cost.MODELS and block_cost.calibration_status(name)["calibrated"]:
        return {"state": "calibrated", "seconds": st.get("seconds"), "error": None}
    return {"state": "uncalibrated", "seconds": None, "error": None}


def _block_cost_models(step: dict) -> list[str]:
    """The `Working.block_cost` models this step's adapter registered — read off the adapter's module (the
    model's timing callable is defined there, or the module names the model in a constant), so a block that
    registers a model is found without a table here."""
    from Working import block_cost
    try:
        spec = get_adapter(f"{step['stage']}.{step['algorithm']}")
    except KeyError:
        return []
    modname = getattr(spec.estimate, "__module__", None) or getattr(spec.run, "__module__", None)
    mod = sys.modules.get(modname or "")
    if mod is None:
        return []
    named = {v for v in vars(mod).values() if isinstance(v, str)}
    return [name for name, (_, run_once) in block_cost.MODELS.items()
            if getattr(run_once, "__module__", None) == modname or name in named]


#: site-x (2026-10-20, "pulled a span into Analyse, loading forever, the whole website lagging"): where a model is
#: timed. "process" (the default): a process of its own, so the timing's Python never holds the bridge's GIL — on a
#: thread, timing detection.rupture (~447 s) slowed every other route two to five times for as long as it ran.
#: "thread": on the calling thread (a sandbox that forbids processes). A stand-in `block_cost.calibrate` (a test's
#: fake) cannot cross a process boundary, so it always runs on the thread.
CALIBRATION_WORKER = "process"
_BC_POOLS: set = set()               # the calibration processes in flight, stopped at interpreter exit
_BC_ATEXIT = {"registered": False}


def _stop_block_calibrations() -> None:
    """Stop every calibration process now (interpreter exit): a bridge must not wait out a 7-minute timing to
    close. The model stays uncalibrated; the next chain that needs it starts it again."""
    from . import corpus
    for pool in list(_BC_POOLS):
        _BC_POOLS.discard(pool)
        corpus._terminate(pool)


def _calibrate_in_process(name: str, path: str) -> int:
    """`block_cost.calibrate([name], path=path)` in a spawned process of its own (one per model, so a slow model
    never queues behind another, nor behind the corpus maps' worker); the child's pid. The child watches the
    bridge and ends with it (`coverage_map.watch_parent`)."""
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor
    from Working import block_cost
    from Working.discovery import coverage_map
    from . import calibrate_child, corpus
    module = getattr((block_cost.MODELS.get(name) or (None, None))[1], "__module__", None)
    pool = ProcessPoolExecutor(max_workers=1, mp_context=mp.get_context("spawn"), initializer=coverage_map.watch_parent)
    _BC_POOLS.add(pool)
    if not _BC_ATEXIT["registered"]:
        register = getattr(threading, "_register_atexit", None)    # before concurrent.futures joins its workers
        if register is not None:
            register(_stop_block_calibrations)
        _BC_ATEXIT["registered"] = True
    try:
        with corpus._POOL_LOCK, corpus._MainHidden():   # the child must not re-run the bridge's main script
            fut = pool.submit(calibrate_child.calibrate_in_child, name, path, module)
        return fut.result()
    finally:
        _BC_POOLS.discard(pool)
        pool.shutdown(wait=False)


def _calibrate_block_cost(name: str, path: str, generation: dict) -> None:
    """Time one model and store it in `path` — the calibration file resolved when the request started it (a
    sandbox's runtime copy), never whatever the module points at by the time a minutes-long timing ends (a
    restored runtime would otherwise send it to the checkout's DATA/db). site-x: timed in a process of its own
    (`_calibrate_in_process`); the state records which process (`pid`)."""
    from Working import block_cost
    t0 = time.time()
    try:
        if CALIBRATION_WORKER == "process" and block_cost.calibrate is _REAL_CALIBRATE:
            pid = _calibrate_in_process(name, path)
        else:
            block_cost.calibrate([name], path=path)
            pid = os.getpid()
        st = {"state": "calibrated", "seconds": round(time.time() - t0, 1), "error": None, "pid": pid}
    except Exception as e:          # a block that cannot run here: say why, never "free"
        st = {"state": "failed", "seconds": round(time.time() - t0, 1), "error": f"{type(e).__name__}: {e}",
              "failed_at": time.time()}
    with _BC_LOCK:
        if _BC_STATE.get(name) is generation:     # not reset (or restarted) while it ran
            _BC_STATE[name] = st


def _ensure_block_calibration(name: str) -> threading.Thread | None:
    """Start `name`'s calibration in the background unless it is calibrated or already running; the thread."""
    if block_calibration_state(name)["state"] == "calibrated":
        return None
    with _BC_LOCK:
        st = _BC_STATE.get(name) or {}
        if st.get("state") == "calibrating":
            return _BC_THREADS.get(name)
        if st.get("state") == "failed" and time.time() - st.get("failed_at", 0) < CALIBRATION_RETRY_S:
            return None
        from Working import block_cost
        generation = {"state": "calibrating", "seconds": None, "error": None}
        _BC_STATE[name] = generation
        t = threading.Thread(target=_calibrate_block_cost,
                             args=(name, os.path.abspath(block_cost.CALIBRATION_PATH), generation),
                             name=f"calibrate-{name}", daemon=True)
        _BC_THREADS[name] = t
    t.start()
    return t


def route_local(recipe: dict, n_samples: int, fs: float, *, ceiling_s: float, draws: int = 0) -> dict:
    """Can this run finish locally? ``estimate`` per step; when a step's estimator is uncalibrated, its cost
    model is calibrated — the matrix-profile model synchronously (a few seconds), a `Working.block_cost` model in
    the background, waited for up to ``CALIBRATION_WAIT_S`` — and the estimate taken again. The run's cost is
    the real chain plus ``draws`` paired null draws (each runs the whole chain again). ``route`` is ``cluster``
    over the ceiling, ``local`` under it, ``unknown`` when a step still cannot be estimated: ``calibrating``
    lists the steps whose model is still being timed, ``errors`` the estimator's (or calibration's) own words."""
    est = estimate(recipe, n_samples, fs)
    calibration: dict | None = None
    if any(_uses_mp_cost(recipe["steps"][i]) for i in est["unknown"]):
        calibration = _calibrate_matrix_profile()
        est = estimate(recipe, n_samples, fs)
    models = sorted({name for i in est["unknown"] for name in _block_cost_models(recipe["steps"][i])})
    if models:
        # site-x: only the request that STARTS a timing waits for it (a quick model lands inside it); a re-validate
        # that finds one already running answers "calibrating" at once — the page asks again every 3 s, and each of
        # those waiting 10 s again held the chain page "loading" for the whole of a minutes-long timing
        with _BC_LOCK:
            running = {m for m in models if (_BC_STATE.get(m) or {}).get("state") == "calibrating"}
        threads = [t for t in (_ensure_block_calibration(m) for m in models if m not in running) if t is not None]
        deadline = time.time() + float(CALIBRATION_WAIT_S)
        for t in threads:
            t.join(max(0.0, deadline - time.time()))
        calibration = dict(calibration or {})
        calibration["block_cost"] = {m: block_calibration_state(m) for m in models}
        est = estimate(recipe, n_samples, fs)
    real = est["total_s"]
    total = real * (1 + max(0, int(draws)))
    route = "cluster" if total > ceiling_s else ("unknown" if est["unknown"] else "local")
    slowest = None
    known = [(v, i) for i, v in enumerate(est["per_step_s"]) if v is not None]
    if known:
        v, i = max(known)
        step = recipe["steps"][i]
        slowest = {"index": i, "name": f"{step['stage']}.{step['algorithm']}", "seconds": v}
    return {"route": route, "estimate_s": total, "estimate_real_s": real, "draws": int(draws),
            "ceiling_s": float(ceiling_s), "per_step_s": est["per_step_s"], "unknown": est["unknown"],
            "calibrating": est["calibrating"], "errors": est["errors"],
            "slowest": slowest, "calibration": calibration}


def max_local_samples(recipe: dict, fs: float, *, ceiling_s: float, draws: int = 0, upper: int) -> int:
    """The longest span (samples, ≤ ``upper``) whose estimate, times 1 + ``draws``, stays under the ceiling —
    found by bisection on the per-step estimators, so it holds for any cost shape. 0 if even the shortest
    span is over; calibrate first (``route_local``) or an uncalibrated step counts as free here."""
    def fits(n):
        return estimate(recipe, n, fs)["total_s"] * (1 + max(0, int(draws))) <= ceiling_s
    lo, hi = 0, int(upper)
    if fits(hi):
        return hi
    while hi - lo > max(1, int(fs)):
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if fits(mid) else (lo, mid)
    return lo


def fmt_seconds(s: float) -> str:
    if s < 90:
        return f"{s:.0f} s"
    if s < 5400:
        return f"{s / 60:.0f} min"
    if s < 172800:
        return f"{s / 3600:.1f} h"
    return f"{s / 86400:.1f} days"


def cache_status(recipe: dict, conn) -> list[dict]:
    """Per step: does the core's step cache already hold this prefix?
    Uses the very same key (``_recipe_prefix_hash``, with the recording's unit)
    and existence test (``step_artifacts`` row + directory) that
    ``execute_recipe`` uses."""
    units = recording_units(get_recording_by_id(conn, recipe["recording_id"]))
    out = []
    for i in range(len(recipe["steps"])):
        h = _recipe_prefix_hash(recipe, i, units)
        row = get_step_artifact(conn, h, i)
        cached = bool(row is not None and os.path.isdir(row["path"]))
        out.append({"index": i, "prefix_hash": h, "cached": cached, "path": row["path"] if row else None})
    return out


def invalidated(recipe: dict, step_index: int) -> list[int]:
    return sorted(invalidated_step_indices(recipe, step_index))


def hashes(recipe: dict) -> dict:
    return {"config_hash": short_hash(recipe), "recipe_hash": recipe_hash(recipe)}
