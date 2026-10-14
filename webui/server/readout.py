"""A block's `derive` readout, computed on what the block is handed in a run (2026-10-14).

`AdapterSpec.derive(x, t, fs, params, **typed)` is a block's pre-run readout — "Slope-noise σ (MAD)",
"Fast cut", "Missing samples". The block page shows it beside the Parameters panel and asks again as a
parameter changes, and it has to read the block's INPUT: the noise-threshold block after baseline removal
reads the detrended trace, the drop detector reads the encoder's letters. Read off the stored span instead
(the route's behaviour until this change), the first printed a σ_n 8-20x too large — a cut near -500 mV
where it cuts near -6 mV — and every block that reads an upstream typed value said "run X first" even
straight after a run (measured on M2_aug and Schizophyllum spans, 2026-10-14).

So the stages before the block are walked the way `Working.execution._execute_recipe_with_conn` walks them:
the signal carried through every Signal stage, the previous typed value handed on as `value`, side inputs
resolved by the core's own resolver, a store-reading stage handed `conn` and `recording`. Three differences
keep a readout a readout:

* a stage the step cache holds — under the key a run writes, `_recipe_prefix_hash` of the recipe
  `chain.build_recipe` makes, exactly as POST /api/runs builds it — is read from the cache;
* a stage the cache does not hold is re-run in memory only when the bridge's own estimate
  (`chain.estimate`) puts every such stage together under `BUDGET_S`; otherwise nothing runs and
  `skipped` names the stage. One run of the chain puts it in the cache (a sandbox caches every step, the
  project bridge every step slower than `STEP_CACHE_WRITE_THRESHOLD_S`, and a faster one is cheap to
  re-run);
* nothing is written: no run row, no step-cache entry, no `persist`.

A stage before the block that refuses its parameters or the span raises `ReadoutRefused` naming the stage —
the run would refuse there too. The block's own `derive` is called as it is: its rows are its own say.
"""
from __future__ import annotations

import inspect
import time

from Adapters.registry import get_adapter
from Working.chain_validation import validate_recipe_steps
from Working.database.runs import get_step_artifact
from Working.execution import _first_store_reading_step, _load_cached_result, _load_signal, _recipe_prefix_hash
from Working.side_inputs import SideInputResolutionError, resolve_side_inputs, typed_step_value
from Working.types import Signal

from . import chain as chain_mod

#: The most the readout spends re-running the stages before a block that the step cache does not hold, by the
#: bridge's own estimate. It is asked again on every parameter edit, so it has to stay quick: the canonical
#: drop detector's prefix is 2-44 ms on a 10-72 h span and under 0.5 s on a whole 30-day channel.
BUDGET_S = 2.0


class ReadoutRefused(ValueError):
    """A stage up to the block refused its parameters, the chain or the span — a run would refuse there too."""


def _label(i: int, spec) -> str:
    return f"{i + 1:02d} {spec.page_name}"


def _accepts(fn, name: str) -> bool:
    ps = inspect.signature(fn).parameters
    return name in ps or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in ps.values())


def _duration(s: float) -> str:
    return f"{s:.1f} s" if s < 90 else f"{s / 60:.0f} min" if s < 5400 else f"{s / 3600:.1f} h"


def _side_inputs(conn, i, spec, step, root_signal, step_results) -> dict:
    if not spec.side_inputs:
        return {}
    try:
        return resolve_side_inputs(conn, spec, step.get("side_inputs") or {},
                                   root_signal=root_signal, step_results=step_results)
    except SideInputResolutionError as e:
        raise ReadoutRefused(f"{_label(i, spec)}: {e}") from e


def block_readout(conn, rec: dict, span, steps: list[dict], index: int, *, budget_s: float = BUDGET_S) -> dict:
    """Block `index` of `steps`: its derive rows on recording `rec` over `span` ((start, end) samples; None
    is the whole channel), computed on what a run hands it.

    Returns ``{block, index, has_derive, rows, input, skipped, elapsed_s}``: ``rows`` as
    ``{label, value, severity}``; ``input`` one ``{index, name, from}`` per stage before the block, ``from``
    being ``"cache"`` or ``"run"``; ``skipped`` (with no rows) why nothing was computed. Raises `IndexError`
    for an index outside the chain, `KeyError` for an unknown block, `ReadoutRefused` as described above."""
    t_start = time.perf_counter()
    if not 0 <= index < len(steps):
        raise IndexError(f"there is no stage {index + 1:02d} in this {len(steps)}-stage chain")
    upto = [dict(s) for s in steps[:index + 1]]
    specs = [get_adapter(f"{s['stage']}.{s['algorithm']}") for s in upto]
    spec = specs[index]
    out = {"block": spec.name, "index": index, "has_derive": spec.derive is not None,
           "rows": [], "input": [], "skipped": None}

    def done(**kw):
        return {**out, **kw, "elapsed_s": round(time.perf_counter() - t_start, 4)}

    if spec.derive is None:
        return done()
    params = []
    for i, (s, sp) in enumerate(zip(upto, specs)):
        try:
            params.append(sp.validate_params(s.get("params") or {}))
        except ValueError as e:
            raise ReadoutRefused(f"{_label(i, sp)}: {e}") from e
    ok, reason = validate_recipe_steps(upto)
    if not ok:
        raise ReadoutRefused(f"the chain up to {_label(index, spec)} does not connect: {reason}")
    try:
        recipe = chain_mod.build_recipe(int(rec["id"]), tuple(span) if span else None, upto)
    except ValueError as e:
        raise ReadoutRefused(str(e)) from e
    fs = float(rec["fs"])
    n = (int(span[1]) - int(span[0])) if span else int(rec["n_samples"])

    # the plan: which stages before the block the cache holds (never a store-reading stage or one after it,
    # as in a run) — read now, so an entry that will not load counts as not held before the budget is
    # checked; the rest are re-run, and only when together they fit the budget
    store_from = _first_store_reading_step(recipe["steps"])
    cached: dict = {}
    for i in range(index):
        if store_from is not None and i >= store_from:
            break
        row = get_step_artifact(conn, _recipe_prefix_hash(recipe, i), i)
        result = _load_cached_result(specs[i], row["path"]) if row is not None else None
        if result is not None:
            cached[i] = result
    rerun = [i for i in range(index) if i not in cached]
    if rerun:
        per = chain_mod.estimate(recipe, n, fs)["per_step_s"]
        unknown = [i for i in rerun if per[i] is None]
        if unknown:
            i = unknown[0]
            return done(skipped=f"{_label(i, specs[i])} is not in the step cache and its time on this span is unknown "
                                "— run the chain once and the readout reads it from the cache")
        if sum(per[i] for i in rerun) > budget_s:
            i = max(rerun, key=lambda k: per[k])
            return done(skipped=f"{_label(i, specs[i])} is not in the step cache and takes ≈ {_duration(per[i])} on this "
                                "span — run the chain once and the readout reads it from the cache")

    x, t = _load_signal(rec, tuple(span) if span else None)
    root_signal = Signal(x=x, fs=fs)
    current_value = None            # the previous typed value, handed on as `value` (execute_recipe's rule)
    step_results: dict = {}
    for i in range(index):
        sp, step = specs[i], upto[i]
        result = cached.get(i)
        if result is not None:
            out["input"].append({"index": i, "name": sp.name, "from": "cache"})
        else:
            if sp.max_span_samples is not None and len(x) > sp.max_span_samples:
                raise ReadoutRefused(f"{_label(i, sp)} is over its local ceiling ({sp.max_span_samples:,} samples) "
                                     f"on this {len(x):,}-sample span")
            accepted = inspect.signature(sp.run).parameters
            extra = _side_inputs(conn, i, sp, step, root_signal, step_results)
            if sp.input_kind is not None and "value" in accepted:
                extra["value"] = current_value
            if "conn" in accepted:
                extra["conn"] = conn
                extra["recording"] = dict(rec)
            try:
                result = sp.run(x, t, fs, **params[i], **extra)
            except ValueError as e:
                raise ReadoutRefused(f"{_label(i, sp)} refused this span: {e}") from e
            out["input"].append({"index": i, "name": sp.name, "from": "run"})
        step_results[i] = typed_step_value(result)
        if result.output_kind == "signal":
            x = result.value.x
            if len(x) != len(t):        # execute_recipe refuses this too: the chain's time axis is the span's
                raise ReadoutRefused(f"{_label(i, sp)} returned {len(x)} samples from a {len(t)}-sample span; "
                                     "a Signal block must keep the sample count")
        if result.value is not None:
            current_value = result.value

    typed = {k: v for k, v in _side_inputs(conn, index, spec, upto[index], root_signal, step_results).items()
             if _accepts(spec.derive, k)}
    if spec.input_kind is not None and _accepts(spec.derive, "value"):
        typed["value"] = current_value
    rows = spec.derive(x, t, fs, params[index], **typed)
    return done(rows=[{"label": r[0], "value": str(r[1]), "severity": r[2] if len(r) > 2 else ""} for r in rows])
