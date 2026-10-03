"""
run_groups.py
===============
Fan-out over a channel or band scope (ticket 25). One action over N
channels or N bands creates one `run_groups` row and N `runs` rows
referencing it; locally the N runs execute sequentially with per-item
progress; on the cluster a single SLURM array job's task index selects its
own target from the target list baked into the recipe.

A channel fan-out and a band fan-out are deliberately the same mechanism
(PIPELINE_PRD.md, Execution: Fan-out and Band decomposition). The recipe
carries an optional `fan_out` scope:

    {"kind": "channels", "targets": [recording_id, ...]}
    {"kind": "bands",    "targets": [{"kind": "bandpass", "label": ..., "low_hz": ..., "high_hz": ...}, ...]}

A band is a **typed** entry (fixup-Z): `kind` names how the band is isolated
— `bandpass` today; `AC` adds a wavelet level as one more kind and one more
step builder in `_BAND_STEPS`, without reshaping the scope. Band labels are
caller-supplied; the project's named list lives in Settings › Analysis
defaults (`bands_from_settings`, Q43).

`materialize_target` turns one target index into a plain per-target recipe
(a channel target becomes the recipe's `recording_id`; a band target gets its
band step prepended). `fan_out_recipe` runs every target, linking each run row
to the shared run-group row. `band_recipes` is the band scope Discovery's
*Apply template* uses: the same materialisation, one recipe per band.

**The band step is the block Analyse inserts** — `preprocessing.bandpass` with
the adapter's own defaults filled (`order 4`) and the band's two edges set —
so a band run records byte-for-byte the recipe of the chain a researcher builds
by hand in Analyse, saves and applies (fixup-Z). Half-filled params would hash
apart from the hand-built twin and the step cache, the run history and "what
have I already tried" would see two experiments where there is one.

No UI imports — cluster-safe, headless-test-safe, same as `Working.execution`.
"""

from Working.database import runs as R
from Working.recipes import BAND_KINDS, make_recipe, normalize_band  # noqa: F401  (re-exported)

#: Where the project's band list lives (Q43): Settings › Analysis defaults.
BANDS_SETTINGS_PAGE = "analysis-defaults"
BANDS_SETTINGS_KEY = "bands"

#: Q43's seed: three log-spaced bands for a 1 Hz recording. The third band's
#: upper edge is 0.45 Hz, not the 0.5 Hz the decision names, because 0.5 Hz IS
#: Nyquist at 1 Hz and a Butterworth edge must lie strictly below it — the
#: filter refuses `Wn = 1` (fixup-Z report). Editable in Settings.
DEFAULT_BANDS = (
    {"kind": "bandpass", "label": "0.001–0.01 Hz", "low_hz": 0.001, "high_hz": 0.01},
    {"kind": "bandpass", "label": "0.01–0.1 Hz", "low_hz": 0.01, "high_hz": 0.1},
    {"kind": "bandpass", "label": "0.1–0.45 Hz", "low_hz": 0.1, "high_hz": 0.45},
)


def bands_from_settings(conn):
    """The project's band list: Settings › Analysis defaults' `bands`, else
    `DEFAULT_BANDS`. A saved band that cannot filter is refused loudly — a
    band run over an impossible band is worse than no run."""
    from Working.registration.settings import get_settings

    saved = get_settings(conn, BANDS_SETTINGS_PAGE).get(BANDS_SETTINGS_KEY)
    if saved is None:
        return [dict(b) for b in DEFAULT_BANDS]
    if not isinstance(saved, list):
        raise ValueError(f"Settings › Analysis defaults {BANDS_SETTINGS_KEY!r} must be a list of bands, "
                         f"got {saved!r}")
    return [normalize_band(b) for b in saved]


def _bandpass_step(band):
    from Adapters.registry import discover_adapters, get_adapter

    discover_adapters()
    params = get_adapter("preprocessing.bandpass").validate_params(
        {"low_hz": band["low_hz"], "high_hz": band["high_hz"]})
    return {"stage": "preprocessing", "algorithm": "bandpass", "params": params}


#: band kind -> the step that isolates it. `AC` adds "wavelet" here.
_BAND_STEPS = {"bandpass": _bandpass_step}


def band_step(band):
    """The step a band prepends to a chain — the block Analyse inserts, with
    the adapter's own defaults filled and the band's edges set."""
    band = normalize_band(band)
    return _BAND_STEPS[band["kind"]](band)


def band_recipes(recording_id, steps, span=None, bands=()):
    """One plain recipe per band: `steps` with each band's step prepended,
    built by `materialize_target` over a band fan-out so there is one
    materialisation, not two."""
    fan = make_recipe(recording_id, steps, span=span, fan_out={"kind": "bands", "targets": list(bands)})
    return [materialize_target(fan, i) for i in range(len(fan["fan_out"]["targets"]))]


def _surrogate_enabled(recipe, surrogate):
    """Resolve the surrogate switch from the explicit argument or the
    recipe's recorded `surrogate` control. `None` means "use the recipe",
    which in turn defaults to off for headless callers that never set it."""
    if surrogate is not None:
        return bool(surrogate)
    return bool(recipe.get("surrogate", False))


def surrogate_recipe(recipe, params=None):
    """Build the paired null recipe: the identical chain with a
    `preprocessing.surrogate` step prepended.

    The `fan_out` scope and the `surrogate` control key are stripped — this
    is a plain per-target recipe, and the surrogate run records its
    provenance in `runs.surrogate_of_run_id`, not in its recipe.
    """
    step = {
        "stage": "preprocessing",
        "algorithm": "surrogate",
        "params": dict(params or {"method": "phase_randomize", "seed": 0}),
    }
    surrogate = dict(recipe)
    surrogate["steps"] = [step] + recipe["steps"]
    surrogate.pop("fan_out", None)
    surrogate.pop("surrogate", None)
    return surrogate


#: `preprocessing.surrogate`'s default, restated so a draw's recipe always names
#: its method and its seed.
DEFAULT_SURROGATE_PARAMS = {"method": "phase_randomize", "seed": 0}


def _longest_detection_s(conn, run_id):
    """The longest span a run detected, in seconds — "the longest motif under
    test" for a paired block shuffle (Q-Null-1). None when it found nothing."""
    row = conn.execute(
        "SELECT MAX(d.end_idx - d.start_idx) AS n, rec.fs AS fs FROM detections d "
        "JOIN runs r ON r.id = d.run_id JOIN recordings rec ON rec.id = r.recording_id "
        "WHERE d.run_id = ?", (int(run_id),)).fetchone()
    if row is None or row["n"] is None:
        return None
    return float(row["n"]) / (float(row["fs"]) or 1.0)


def surrogate_draw_params(conn, original_run_id, params=None):
    """The params every draw of one paired null shares, with the seed as the
    BASE seed (draw i runs at `seed + i`).

    Block shuffle keeps any motif shorter than a block intact, so its block
    must be longer than the motif under test; unless the caller fixes
    `block_s`, it is twice the longest span the real run detected (never under
    two samples). A run that found nothing has no motif under test and so no
    block length: the null is skipped with a reason rather than run at a length
    nobody chose. Returns ``(params, skipped_reason)``.
    """
    out = dict(params or DEFAULT_SURROGATE_PARAMS)
    out.setdefault("method", DEFAULT_SURROGATE_PARAMS["method"])
    out["seed"] = int(out.get("seed") or 0)
    if out["method"] == "block_shuffle" and not out.get("block_s"):
        longest = _longest_detection_s(conn, original_run_id)
        if longest is None:
            return None, ("block shuffle needs a block twice the longest motif under test, and this run "
                          "detected nothing: there is no motif to size the block by, and no null was drawn")
        fs = conn.execute(
            "SELECT rec.fs FROM runs r JOIN recordings rec ON rec.id = r.recording_id WHERE r.id = ?",
            (int(original_run_id),)).fetchone()[0]
        out["block_s"] = max(2.0 * longest, 2.0 / (float(fs) or 1.0))
    return out, None


def run_paired_recipe(recipe, db_path=None, force=False, on_progress=None,
                      should_cancel=None, run_kwargs=None, on_step_result=None,
                      surrogate=None, surrogate_params=None, surrogate_draws=None,
                      on_draw=None, should_cancel_draws=None):
    """Run a single recipe, optionally paired with its surrogate null.

    The original recipe always records the resolved `surrogate` switch in its
    stored config (so an explicitly-off control is visible rather than simply
    absent). When the switch is on, `surrogate_draws` further runs (default 1)
    execute the identical chain with `preprocessing.surrogate` prepended, draw
    `i` at seed `seed + i`, each linked to the original by
    `runs.surrogate_of_run_id`.

    **N draws, not one** (fixup-T, Q35): a column called "null expects" over a
    single realisation is not an expectation. Each draw is its own recipe (the
    seed is a parameter), so `execute_recipe`'s reuse-by-hash is what makes
    "reuse null draws while the recipe is unchanged" true — raising N adds the
    missing draws and re-runs none.

    Parameters
    ----------
    on_draw : callable(i, n), optional
        Fired before draw `i` of `n`, so a caller can show null progress.
    should_cancel_draws : callable() -> bool, optional
        Checked BETWEEN draws only. A caller that must never interrupt the
        real run mid-chain (`fanout.start` cancels between targets) can still
        stop a long null early; the draws already made stay linked and the
        result says how many there are.

    Returns
    -------
    dict : the `execute_recipe` result for the original run, plus
    `surrogate_run_ids` (one per draw, [] when off), `surrogate_results`,
    `surrogate_draws` (the count actually drawn — fewer than asked on a
    cancel), `surrogate_skipped` (a sentence when no null could be drawn), and
    the first draw under the single-draw keys `surrogate_run_id` /
    `surrogate_result` that earlier callers read.
    """
    from Working.database.schema import init_db
    from Working.execution import RecipeCancelled, execute_recipe

    enabled = _surrogate_enabled(recipe, surrogate)
    original_recipe = dict(recipe)
    original_recipe["surrogate"] = bool(enabled)

    original = execute_recipe(
        original_recipe, db_path=db_path, force=force,
        should_cancel=should_cancel, run_kwargs=run_kwargs,
        on_step_result=on_step_result, on_progress=on_progress,
    )
    out = dict(original)
    out["surrogate_run_id"] = None
    out["surrogate_run_ids"] = []
    out["surrogate_results"] = []
    out["surrogate_draws"] = 0
    out["surrogate_skipped"] = None
    if not enabled:
        return out

    n_draws = 1 if surrogate_draws is None else int(surrogate_draws)
    if n_draws < 1:
        raise ValueError(f"a paired null needs at least one draw, got {surrogate_draws!r}")

    conn = init_db(db_path)
    try:
        base, skipped = surrogate_draw_params(conn, original["run_id"], surrogate_params)
        if skipped:
            out["surrogate_skipped"] = skipped
            return out
        for i in range(n_draws):
            if should_cancel is not None and should_cancel():
                break
            if should_cancel_draws is not None and should_cancel_draws():
                break
            if on_draw is not None:
                on_draw(i, n_draws)
            params = dict(base, seed=base["seed"] + i)
            try:
                draw = execute_recipe(
                    surrogate_recipe(original_recipe, params),
                    db_path=db_path, force=force,
                    should_cancel=should_cancel, run_kwargs=run_kwargs,
                )
            except RecipeCancelled:
                break
            R.update_run(conn, draw["run_id"], surrogate_of_run_id=original["run_id"])
            out["surrogate_run_ids"].append(draw["run_id"])
            out["surrogate_results"].append(draw)
        out["surrogate_draws"] = len(out["surrogate_run_ids"])
        if out["surrogate_run_ids"]:
            out["surrogate_run_id"] = out["surrogate_run_ids"][0]
            out["surrogate_result"] = out["surrogate_results"][0]
        return out
    finally:
        conn.close()


def target_for_index(recipe, target_index):
    """The raw fan-out target for a given index — what a cluster task index
    selects from the baked-in list."""
    return recipe["fan_out"]["targets"][target_index]


def materialize_target(recipe, target_index):
    """Build the plain per-target recipe for one fan-out target.

    The returned recipe has no `fan_out` scope of its own: a channel target
    becomes the recipe's `recording_id`, a band target gets its band step
    (`band_step`) prepended. Rebuilt through `Working.recipes.make_recipe` so
    the chain is re-validated exactly as an ordinary hand-built recipe would be.
    """
    fan = recipe["fan_out"]
    target = fan["targets"][target_index]
    if fan["kind"] == "channels":
        return make_recipe(target, recipe["steps"], span=recipe["span"])
    return make_recipe(
        recipe["recording_id"], [band_step(target)] + recipe["steps"], span=recipe["span"],
    )


def fan_out_recipe(recipe, db_path=None, force=False, on_progress=None,
                   should_cancel=None, run_kwargs=None, on_step_result=None,
                   surrogate=None, surrogate_params=None, surrogate_draws=None):
    """Execute every target of a fan-out recipe sequentially.

    One `run_groups` row is created, each target is materialised into a plain
    per-target recipe and executed through `Working.execution.execute_recipe`,
    and the resulting run row is linked to the group via `run_group_id`. With
    `surrogate` on, each target is run as a paired surrogate run and both the
    original and surrogate run rows are linked to the shared group.

    Parameters
    ----------
    recipe : dict
        A recipe carrying a `fan_out` scope, as built by
        `Working.recipes.make_recipe(..., fan_out=...)`.
    db_path : str, optional
        Passed through to `execute_recipe`.
    force : bool
        Recompute each target even if a completed run already exists.
    on_progress : callable(index, total, label), optional
        Fired once per target before it executes, so a caller can show
        per-item progress across the fan-out. This is the fan-out's own
        progress channel, distinct from `execute_recipe`'s per-step
        `on_progress`.
    surrogate : bool, optional
        If None, the recipe's recorded `surrogate` control is used. When
        True, each per-target run is paired with a surrogate null run linked
        by `runs.surrogate_of_run_id`.
    surrogate_params : dict, optional
        Params for the prepended `preprocessing.surrogate` step.
    surrogate_draws : int, optional
        Null draws per target (default 1); see `run_paired_recipe`.
    should_cancel, run_kwargs, on_step_result
        Forwarded unchanged to `execute_recipe` for each target.

    Returns
    -------
    dict : {
        "run_group_id": int,
        "runs": [{"run_id": int, "target": target, "reused": bool,
                  "config_hash": str, "detections_written": int,
                  "surrogate_run_id": int | None,
                  "surrogate_detections_written": int | None}, ...],
    }
    """
    if "fan_out" not in recipe:
        raise ValueError("Recipe has no fan_out scope; nothing to fan out.")

    from Working.database.schema import init_db

    enabled = _surrogate_enabled(recipe, surrogate)

    conn = init_db(db_path)
    try:
        group_id = R.create_run_group(conn)
        fan = recipe["fan_out"]
        targets = fan["targets"]
        n_targets = len(targets)
        runs_out = []
        for i, target in enumerate(targets):
            if on_progress is not None:
                label = target if fan["kind"] == "channels" else target["label"]
                on_progress(i, n_targets, label)
            per_target = materialize_target(recipe, i)
            per_target["surrogate"] = enabled
            result = run_paired_recipe(
                per_target, db_path=db_path, force=force,
                should_cancel=should_cancel, run_kwargs=run_kwargs,
                on_step_result=on_step_result,
                surrogate=enabled, surrogate_params=surrogate_params,
                surrogate_draws=surrogate_draws,
            )
            R.update_run(conn, result["run_id"], run_group_id=group_id)
            surrogate_detections = None
            for sid in result["surrogate_run_ids"]:
                R.update_run(conn, sid, run_group_id=group_id)
            if result.get("surrogate_run_id") is not None:
                surrogate_detections = result["surrogate_result"]["detections_written"]
            runs_out.append({
                "run_id": result["run_id"],
                "target": target,
                "reused": result["reused"],
                "config_hash": result["config_hash"],
                "detections_written": result["detections_written"],
                "surrogate_run_id": result.get("surrogate_run_id"),
                "surrogate_run_ids": list(result["surrogate_run_ids"]),
                "surrogate_detections_written": surrogate_detections,
            })
        return {"run_group_id": group_id, "runs": runs_out}
    finally:
        conn.close()
