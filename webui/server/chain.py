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
from typing import Any

from Adapters.registry import discover_adapters, get_adapter, list_adapters
from Working.chain_validation import ROOT_SIGNAL_KIND, check_step_compatibility
from Working.execution import _recipe_prefix_hash, invalidated_step_indices
from Working.hpc.job_export import estimate_recipe_seconds
from Working.recipes import make_recipe, recipe_hash, short_hash
from Working.database.runs import get_step_artifact

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
        "has_estimate": spec.estimate is not None,
        "max_span_samples": spec.max_span_samples,
        "has_recommend": spec.recommend is not None,
        "side_inputs": [{"name": s.name, "type_kind": s.type_kind, "sources": list(s.sources)} for s in spec.side_inputs],
        "known_broken": spec.known_broken,
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
        junctions.append({"index": i, "ok": bool(ok), "producing": producing, "expected": expected,
                          "reason": "" if ok else f"{spec.page_name} needs {TYPE_LABEL.get(expected, expected)} · previous emits {TYPE_LABEL.get(producing, producing)}",
                          "core_reason": reason})
        ok_all = ok_all and bool(ok)
        producing = spec.output_kind
        terminal = spec.output_kind
    return {"ok": ok_all, "junctions": junctions, "terminal_kind": terminal if steps else None,
            "terminal_label": TYPE_LABEL.get(terminal) if steps else None}


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
    total = float(estimate_recipe_seconds(recipe, n_samples, fs) or 0.0)
    per_step = []
    for i, step in enumerate(recipe["steps"]):
        sub = dict(recipe); sub["steps"] = [step]
        try:
            per_step.append(float(estimate_recipe_seconds(sub, n_samples, fs) or 0.0))
        except Exception:
            per_step.append(0.0)
    return {"total_s": total, "per_step_s": per_step}


def cache_status(recipe: dict, conn) -> list[dict]:
    """Per step: does the core's step cache already hold this prefix?
    Uses the very same key (``_recipe_prefix_hash``) and existence test
    (``step_artifacts`` row + directory) that ``execute_recipe`` uses."""
    out = []
    for i in range(len(recipe["steps"])):
        h = _recipe_prefix_hash(recipe, i)
        row = get_step_artifact(conn, h, i)
        cached = bool(row is not None and os.path.isdir(row["path"]))
        out.append({"index": i, "prefix_hash": h, "cached": cached, "path": row["path"] if row else None})
    return out


def invalidated(recipe: dict, step_index: int) -> list[int]:
    return sorted(invalidated_step_indices(recipe, step_index))


def hashes(recipe: dict) -> dict:
    return {"config_hash": short_hash(recipe), "recipe_hash": recipe_hash(recipe)}
