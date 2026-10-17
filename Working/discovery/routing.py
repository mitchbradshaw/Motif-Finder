"""
routing.py
==========
Where each step of a planned run will compute — one place, read by Discovery's
plan (`fanout.plan`), the cluster export (`chain_job`) and Analyse's pre-check
(round A_2, P2).

A step is one of four things before it runs:

* **cached** — the step cache already holds its output under the recipe-prefix
  key (`Working.execution._recipe_prefix_hash`, the recording's unit included).
  It costs nothing, and it is served whatever its span (the cap guards a
  computation, and a cached step computes nothing: `execute_recipe` checks the
  cap only in its compute branch).
* **cluster** — it must compute and its span is over a **time** cap: a cap
  calibrated from THIS machine's speed (`cost.max_span_samples_for_background`,
  the local background budget). That is a limit on running here, not on the
  question, so the run is offered to the cluster, where there is none.
* **refused** — it must compute and its span is over a **memory** cap (a
  Gramian image, the wavelet scalogram, the PAN profile's per-thread buffers):
  that limit is physical and holds anywhere.
* **local** — it must compute, within any cap.

`TIME_CAPPED_BLOCKS` names the time caps. A table, not a rule read off the
adapter, because the two kinds are indistinguishable from the spec: the PAN
profile imports the same cost module as the matrix profile, but its cap is a
memory guard (`Adapters/detection_pan_matrix_profile.py`). A block whose cap is
derived from `max_span_samples_for_background` joins the table.

Why a core twin of `webui/server/chain.py::cache_status`: the core cannot import
the bridge. The key and the existence test are the same (`step_artifacts` row
plus its directory), so the two cannot disagree on what is cached.

No UI imports.
"""

import os

from Working.database import queries as _q
from Working.database.runs import get_step_artifact

#: blocks whose `max_span_samples` is this machine's TIME budget (the matrix-profile
#: calibration), not a memory limit: over it, a run is routed to the cluster
TIME_CAPPED_BLOCKS = frozenset({"detection.matrix_profile", "detection.fluss"})

ROUTES = ("cached", "local", "cluster", "refused")


def _name(step):
    return f"{step['stage']}.{step['algorithm']}"


def _spec(name):
    from Adapters.registry import discover_adapters, get_adapter

    try:
        return get_adapter(name)
    except KeyError:
        discover_adapters()
        try:
            return get_adapter(name)
        except KeyError:
            return None


def cap_kind(name):
    """'time' for a block whose cap is this machine's budget (whether or not the
    machine is calibrated yet: uncalibrated, the cap is None and nothing is over
    it), 'memory' for a block with a fixed span cap, None for a block without one."""
    if name in TIME_CAPPED_BLOCKS:
        return "time"
    spec = _spec(name)
    if spec is None or spec.max_span_samples is None:
        return None
    return "memory"


def step_route(status):
    """The route of one step from its status (`step_status`): cached, cluster,
    refused or local."""
    if status.get("cached"):
        return "cached"
    if status.get("over_cap"):
        return "cluster" if status.get("cap_kind") == "time" else "refused"
    return "local"


def _estimate(spec, step, samples, fs):
    """The block's own estimate for `samples` at `fs`; None when it has none or it
    cannot say (uncalibrated). Never 0 for "unknown"."""
    if spec is None or getattr(spec, "estimate", None) is None:
        return None
    from Working.hpc.job_export import _Span
    try:
        v = spec.estimate(_Span(int(samples)), None, float(fs), **(step.get("params") or {}))
    except Exception:
        return None
    return None if v is None else float(v)


def step_status(conn, recipe, *, samples, fs=1.0, units=None, skip=0, estimates=None):
    """Per step of a plain per-target recipe: its prefix key, whether the step
    cache holds it, its cap and whether the span is over it, its estimate.

    ``samples`` is the span the chain runs over (every block preserves it).
    ``units`` is the recording's (`recording_units`); read from the database when
    not given. ``skip`` leaves out the first steps (a null draw's prepended
    surrogate step) from the list, keeping their indices. ``estimates`` is a dict
    the caller shares across calls (a run and its draws): a step's estimate is
    asked of its block once per (block, params, span) rather than per draw."""
    import json as _json
    from Working.execution import _recipe_prefix_hash, recording_units

    if units is None:
        units = recording_units(_q.get_recording_by_id(conn, recipe["recording_id"]))
    estimates = {} if estimates is None else estimates
    out = []
    for i, step in enumerate(recipe["steps"]):
        if i < skip:
            continue
        name = _name(step)
        spec = _spec(name)
        h = _recipe_prefix_hash(recipe, i, units)
        row = get_step_artifact(conn, h, i)
        cached = bool(row is not None and os.path.isdir(row["path"]))
        cap = getattr(spec, "max_span_samples", None) if spec is not None else None
        st = {"index": i, "name": name, "prefix_hash": h, "cached": cached, "cap": cap,
              "cap_kind": (None if cap is None else ("time" if name in TIME_CAPPED_BLOCKS else "memory")),
              "over_cap": bool(cap is not None and int(samples) > int(cap)),
              "has_estimate": bool(spec is not None and getattr(spec, "estimate", None) is not None),
              "estimate_s": None}
        if not cached:
            key = (name, _json.dumps(step.get("params") or {}, sort_keys=True, default=str), int(samples), float(fs))
            if key not in estimates:
                estimates[key] = _estimate(spec, step, samples, fs)
            st["estimate_s"] = estimates[key]
        st["route"] = step_route(st)
        out.append(st)
    return out


def draw_params(conn, recipe, surrogate_params=None):
    """The params every null draw of this recipe shares (seed = the base seed), as
    `run_groups.draw_paired_null` will resolve them — or ``(None, reason)`` when
    they cannot be known before the real run: a block shuffle sizes its block from
    the real run's detections, so its draws are known only once that run exists."""
    from Working import run_groups as RG
    from Working.database.runs import find_completed_run, get_config_by_hash
    from Working.recipes import short_hash

    params = dict(surrogate_params or RG.DEFAULT_SURROGATE_PARAMS)
    params.setdefault("method", RG.DEFAULT_SURROGATE_PARAMS["method"])
    params["seed"] = int(params.get("seed") or 0)
    if params["method"] != "block_shuffle" or params.get("block_s"):
        return params, None
    cfg_row = get_config_by_hash(conn, short_hash(recipe))
    span = recipe.get("span")
    if cfg_row is not None:
        rec = _q.get_recording_by_id(conn, recipe["recording_id"])
        a, b = (int(span[0]), int(span[1])) if span else (0, int(rec["n_samples"]) if rec else 0)
        run = find_completed_run(conn, cfg_row["id"], recipe["recording_id"], a, b)
        if run is not None:
            base, skipped = RG.surrogate_draw_params(conn, run["id"], params)
            return base, skipped
    return None, "a block shuffle sizes its block from the real run's detections, which do not exist yet"


def draw_recipes(conn, recipe, *, draws, surrogate_params=None):
    """The recipes of the first ``draws`` null draws (`run_groups.surrogate_recipe`
    at seed base + j), or ``(None, reason)`` when their params are not known yet."""
    from Working import run_groups as RG

    base, why = draw_params(conn, recipe, surrogate_params)
    if base is None:
        return None, why
    return [RG.surrogate_recipe(recipe, dict(base, seed=base["seed"] + j)) for j in range(int(draws))], None


def _run_cost(statuses):
    """Seconds still to compute for one run, the steps that cannot be costed, and
    the steps over a cap: a cached step is free; an uncached one costs its
    estimate."""
    seconds, uncosted, capped, refused = 0.0, [], [], []
    for st in statuses:
        if st["cached"]:
            continue
        if st["over_cap"]:
            (capped if st["cap_kind"] == "time" else refused).append(st)
        if st["estimate_s"] is None:
            # the surrogate step a draw prepends is an FFT (or a block permutation):
            # O(n log n), free beside the chain it feeds, and declares no estimator
            if st["name"] != "preprocessing.surrogate":
                uncosted.append(st["index"])
            continue
        seconds += st["estimate_s"]
    return seconds, uncosted, capped, refused


def target_cost(conn, recipe, *, samples, fs=1.0, draws=0, surrogate_params=None):
    """What one target of a plan will really compute: the real run and each of its
    ``draws`` null draws, step by step, against the step cache.

    Returns ``{seconds, real_s, draws_s, uncosted, capped, refused, cached,
    draws_cached, draws_known, steps}``. ``seconds`` is None when an uncached step
    cannot be costed; ``uncosted`` names those steps (the chain's own indices, a
    draw's surrogate step excluded); ``capped`` / ``refused`` the uncached steps
    over a time / memory cap (each with ``where``: ``real`` or ``draw j``);
    ``cached`` the real run's cached step indices; ``draws_cached`` how many draws
    are cached step for step. When the draws cannot be known before the real run
    (a block shuffle without a fixed block), each is costed as the real chain."""
    from Working.execution import recording_units

    units = recording_units(_q.get_recording_by_id(conn, recipe["recording_id"]))
    estimates = {}
    real = step_status(conn, recipe, samples=samples, fs=fs, units=units, estimates=estimates)
    real_s, uncosted, capped, refused = _run_cost(real)
    for st in capped + refused:
        st["where"] = "real"
    out = {"steps": real, "cached": [st["index"] for st in real if st["cached"]], "real_s": real_s,
           "draws_s": 0.0, "draws_cached": 0, "draws_known": True}
    unc = set(uncosted)
    draws = max(0, int(draws or 0))
    if draws:
        recipes, why = draw_recipes(conn, recipe, draws=draws, surrogate_params=surrogate_params)
        if recipes is None:
            # unknown until the real run exists: each draw computes what the real run computes from scratch
            cold = [dict(st, cached=False) for st in real]
            for st in cold:
                if st["estimate_s"] is None and st["has_estimate"]:
                    st["estimate_s"] = _estimate(_spec(st["name"]), recipe["steps"][st["index"]], samples, fs)
            s, u, c, r = _run_cost(cold)
            out["draws_s"] = s * draws
            unc.update(u)
            for st in c + r:
                st["where"] = "draws"
            capped += c
            refused += r
            out["draws_known"] = False
            out["draws_why"] = why
        else:
            for j, dr in enumerate(recipes):
                sts = step_status(conn, dr, samples=samples, fs=fs, units=units, estimates=estimates)
                s, u, c, r = _run_cost(sts)
                out["draws_s"] += s
                unc.update(i - 1 for i in u)          # the chain's own index, not the draw's
                for st in c + r:
                    st["where"] = f"draw {j}"
                capped += c
                refused += r
                if all(st["cached"] for st in sts):
                    out["draws_cached"] += 1
    out["uncosted"] = sorted(unc)
    out["capped"] = capped
    out["refused"] = refused
    out["seconds"] = None if unc else out["real_s"] + out["draws_s"]
    return out


def route(seconds, ceiling_s, *, capped=(), refused=()):
    """The plan's route from its cost: ``cluster`` when a step must compute over a
    time cap or the total is over the ceiling, ``unknown`` when an uncached step
    cannot be costed, else ``local``. A memory-capped step does not change the
    route (it fails wherever it runs; the plan names it)."""
    if capped:
        return "cluster"
    if seconds is None:
        return "unknown"
    return "cluster" if seconds > ceiling_s else "local"
