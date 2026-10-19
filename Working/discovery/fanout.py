"""
fanout.py
=========
Spec §7.1/§7.5 — "Each template becomes **one run across all channels in
scope**", and §7.4's *Discard run*.

The fan-out itself is `Working.run_groups`: one `run_groups` row, N `runs`
rows, the target list baked into the recipe so a SLURM array task can select
its own. This module does not repeat that. What it adds is the four things a
plan needs that the fan-out has no opinion about:

**A pre-flight.** `execute_recipe` checks the held-out lock per recipe, from
*inside* the loop — a scope containing a held-out channel runs the earlier
targets, writes their run rows, and only then raises. `plan` drops such a
target before anything starts and says which and why. Same for a channel too
short to hold the section: `materialize_target` carries one absolute span to
every target and `_load_signal` silently returns a short array rather than
raising, so a plan that did not check would produce a run over less data than
it claims.

**A route.** `webui.server.chain.estimate` never returns 'cluster' and reads
no ceiling; `Working.hpc.job_export.route_recipe` does, but its constant is
900 s while Discovery's ceiling is 20 minutes (§9.6, Settings › Compute & HPC
key `limit.Discovery`). And a block with no estimator contributes 0 s
silently — `detection.seed_matches` has none, so a 16-channel sweep would
estimate at zero and route local. `plan` reports `unknown` in that case and
names the steps it could not cost; §7.1's *Preview on a 4 h sample* is how an
uncosted chain gets a real number (`preview` below).

**Per-channel status**, which the runs list and *where each run fires* both
read, and which survives a restart because it is read from the rows.

**A discard that writes no verdicts.** §7.4: "*Discard run* marks the run
superseded and writes **no adjudications**" — a whole-run discard writing
thousands of `not_interesting` human verdicts would poison the RQ5 divergence
measurement, and the corruption would be invisible until it reached a finding.

`start` runs the loop from the same primitives `fan_out_recipe` uses
(`create_run_group`, `materialize_target`, `run_paired_recipe`, `update_run`)
rather than calling it, for one reason: a cooperative cancel **between
targets** must leave the partial group readable, and `fan_out_recipe` lets
`RecipeCancelled` out, taking the group id with it. If `fan_out_recipe` grows
an `on_target_done` hook and a between-target cancel, this loop collapses into
a call to it (request filed to the prompt that owns it).

No UI imports; the bridge is the only caller that knows a browser exists.
"""

import datetime as _dt
import json
import os

from Working.config import HELD_OUT_RECORDING_FILE
from Working.database import queries as _q
from Working.database import runs as _runs
from Working.database.schema import init_db
from Working.discovery.channels import channel_name as _channel_name
from Working.recipes import make_recipe
from Working.run_groups import materialize_target, run_paired_recipe

#: Spec §9.6 / P23: "local compute limits are per workspace (Analyse 20 min,
#: Discovery 20 min, Models 2 h)". Settings › Compute & HPC overrides it.
DEFAULT_CEILING_MIN = 20
CEILING_PAGE = "compute-hpc"
CEILING_KEY = "limit.Discovery"


def _now():
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _ceiling_from_settings(conn=None):
    minutes = DEFAULT_CEILING_MIN
    if conn is not None:
        from Working.registration.settings import get_settings
        saved = get_settings(conn, CEILING_PAGE).get(CEILING_KEY)
        if saved is not None:
            try:
                minutes = float(saved)
            except (TypeError, ValueError):
                raise ValueError(f"Settings › Compute & HPC {CEILING_KEY!r} is not a number: {saved!r}")
            if minutes <= 0:
                raise ValueError(f"Settings › Compute & HPC {CEILING_KEY!r} must be positive, got {minutes}")
    return int(round(minutes * 60))


def ceiling_s(conn=None):
    """Discovery's local compute ceiling in seconds, from Settings › Compute &
    HPC (`limit.Discovery`, minutes) or §9.6's 20 minutes."""
    return _ceiling_from_settings(conn)


def _uncosted_steps(steps):
    """Indices of steps whose adapter declares no estimator — the ones that
    would otherwise be counted free."""
    from Adapters.registry import discover_adapters, get_adapter

    discover_adapters()
    out = []
    for i, step in enumerate(steps):
        try:
            spec = get_adapter(f"{step['stage']}.{step['algorithm']}")
        except Exception:
            out.append(i)
            continue
        if getattr(spec, "estimate", None) is None:
            out.append(i)
    return out




def plan(conn, *, steps, recording_ids, span=None, ceiling_s=None, measured_per_channel_s=None,
         null_draws=0, surrogate=None, surrogate_params=None, windows=None, stitch_rule=None):
    """The scope, checked, costed and routed — before anything runs.

    Parameters
    ----------
    steps : list[dict]
        The chain, as a template's steps.
    recording_ids : list[int]
        One per channel in scope. Order is kept.
    span : (int, int) or None
        The section, in absolute samples. None means each channel whole.
    ceiling_s : int, optional
        Local ceiling in seconds; defaults to Settings › Compute & HPC.
    measured_per_channel_s : float, optional
        Seconds one channel really took, from `preview`. Supplied, it replaces
        the estimator (and is the only honest number for an uncosted chain).
    null_draws : int
        Paired surrogate draws per channel (Settings › Nulls, Q35). Each draw
        is the whole chain again on a surrogate signal, so the estimate is
        ``per channel × channels × (1 + null_draws)`` and the ROUTE is decided
        on that total — "null draws count toward local limits" (§9.4).
    surrogate : bool, optional
        Whether the run is paired with its null (the `surrogate` flag the run's
        recipe records, and so part of every cache key); None means
        ``null_draws > 0``.
    surrogate_params : dict, optional
        The null's params (method, seed, block) — what the draws' recipes are.

    The estimate counts **only what the step cache does not hold** (round A_2,
    P2): per target, the real run and each draw are read step by step against
    the cache (`routing.target_cost`), so a chain whose heavy step came back
    from the cluster plans local. A step that must compute over a **time** cap
    (the matrix profile's, calibrated from this machine's speed) routes the plan
    to the cluster instead of being refused; ``capped`` names it.

    The dead ``reuse`` field (`seeded_search.find_reusable_profile`, read by
    nothing) is gone: the step cache keys the exact question — recording, span,
    params, backend, unit — and a profile over a longer span is not a profile
    of a shorter one (the self-join's neighbours change), so containment reuse
    would have served wrong distances.

    ``windows`` (round A_2, P3) is a window scope (``{window_s, overlap_frac,
    fit}``, `Working.discovery.windowed`): each channel's section is cut into
    windows and each window is one target, an ordinary run over its own span;
    the plan then carries ``windows`` (the count per channel, the runs left,
    the chain's minimum window and what fitting changed). ``stitch_rule`` is
    the matching rule the windows are stitched by (Settings › Analysis
    defaults when None). Without ``windows`` nothing here changes.

    Returns
    -------
    dict
        ``{targets, refused, runnable, reason, span, n_channels, recipe,
        estimate_s, estimate_real_s, null_draws, per_channel_s, uncosted,
        route, ceiling_s, costs, capped, memory_capped, surrogate}``.
    """
    ids = [int(r) for r in recording_ids]
    if not ids:
        raise ValueError("a Discovery scope needs at least one channel")
    ceiling = int(ceiling_s) if ceiling_s is not None else _ceiling_from_settings(conn)
    from Working.registration.settings import HELD_OUT_UNLOCK_HINT, held_out_locked

    by_file = {}
    targets, refused = [], []
    for rid in ids:
        rec = _q.get_recording_by_id(conn, rid)
        if rec is None:
            refused.append({"recording_id": rid, "reason": f"no recording with id {rid}"})
            continue
        source_file = rec["source_file"]
        # a2-p1: Settings › Datasets' lock, read now (never at import) — off, the held-out file plans like any other
        if source_file == HELD_OUT_RECORDING_FILE and held_out_locked(conn):
            refused.append({"recording_id": rid, "reason": (
                f"{HELD_OUT_RECORDING_FILE} is held out (spec §0 D6): locked for the final "
                f"evaluation, and refused before the fan-out starts rather than partway through it — "
                f"{HELD_OUT_UNLOCK_HINT}")})
            continue
        n_samples = int(rec["n_samples"])
        if span is not None:
            a, b = int(span[0]), int(span[1])
            if b > n_samples or a < 0:
                refused.append({"recording_id": rid, "reason": (
                    f"the section [{a}, {b}) runs past this channel: it has {n_samples} samples. "
                    f"One absolute section is carried to every channel, and a short channel would "
                    f"silently run over less data than the scope claims")})
                continue
            target_span = [a, b]
        else:
            target_span = [0, n_samples]
        if source_file not in by_file:
            by_file[source_file] = len(_q.list_recordings(conn, source_file))
        targets.append({
            "recording_id": rid,
            "channel": int(rec["channel"]),
            "channel_name": _channel_name(source_file, int(rec["channel"]), by_file[source_file]),
            "source_file": source_file,
            "fs": float(rec["fs"]),
            "n_samples": n_samples,
            "span": target_span,
            "samples": target_span[1] - target_span[0],
        })

    null_draws = max(0, int(null_draws or 0))
    surrogate = (null_draws > 0) if surrogate is None else bool(surrogate)

    if windows is not None:
        # round A_2, P3: the same channels, refused the same way, each cut into windows
        from Working.discovery import windowed
        return windowed.plan_windows(conn, steps=steps, targets=targets, refused=refused, span=span,
                                     ceiling=ceiling, measured_per_window_s=measured_per_channel_s,
                                     null_draws=null_draws, surrogate=surrogate,
                                     surrogate_params=surrogate_params, scope=windows, stitch_rule=stitch_rule)

    recipe = None
    if targets:
        recipe = make_recipe(targets[0]["recording_id"], steps, span=(list(span) if span else None),
                             fan_out={"kind": "channels", "targets": [t["recording_id"] for t in targets]})

    # what each target will really compute, against the step cache, and the caps it meets (a measured
    # cost replaces the estimate, so the draws are not read one by one for it: the real run's caps are theirs)
    costed_draws = null_draws if (surrogate and measured_per_channel_s is None) else 0
    costs = (_target_costs(conn, recipe, targets, draws=costed_draws, surrogate=surrogate,
                           surrogate_params=surrogate_params) if recipe is not None else [])
    capped, memory_capped = _capped(costs, "capped"), _capped(costs, "refused")
    uncosted = sorted({i for c in costs for i in c["uncosted"]}) if costs else _uncosted_steps(steps)

    per_channel_s = None
    if measured_per_channel_s is not None:
        per_channel_s = float(measured_per_channel_s)
        estimate_real_s = per_channel_s * len(targets)
        estimate_s = estimate_real_s * (1 + null_draws)
    elif costs and all(c["seconds"] is not None for c in costs):
        per_channel_s = max(c["real_s"] for c in costs)
        estimate_real_s = float(sum(c["real_s"] for c in costs))
        estimate_s = float(sum(c["seconds"] for c in costs))
    else:
        estimate_real_s = estimate_s = None
    from Working.discovery.routing import route as _route
    route = _route(estimate_s, ceiling, capped=capped)

    runnable = bool(targets)
    reason = None
    if not runnable:
        reason = "; ".join(r["reason"] for r in refused) or "the scope has no runnable channel"

    return {
        "targets": targets, "refused": refused, "runnable": runnable, "reason": reason,
        "span": (list(span) if span else None), "n_channels": len(targets),
        "recipe": recipe, "estimate_s": estimate_s, "estimate_real_s": estimate_real_s,
        "null_draws": null_draws, "per_channel_s": per_channel_s,
        "uncosted": uncosted, "route": route, "ceiling_s": ceiling,
        "measured": measured_per_channel_s is not None,
        "costs": costs, "capped": capped, "memory_capped": memory_capped, "surrogate": surrogate,
    }


def _estimate_per_channel(steps, targets):
    """Seconds for the longest target, from the blocks' own estimators. Only
    reached when every step has one — an uncosted step makes the whole plan
    `unknown` rather than quietly free."""
    from Adapters.registry import discover_adapters, get_adapter
    from Working.hpc.job_export import _Span

    discover_adapters()

    n = max(t["samples"] for t in targets)
    fs = targets[0]["fs"]
    total = 0.0
    for step in steps:
        spec = get_adapter(f"{step['stage']}.{step['algorithm']}")
        v = spec.estimate(_Span(n), None, fs, **step.get("params", {}))
        if v is None:
            return None
        total += float(v)
    return total


def start(plan_dict, *, db_path=None, on_progress=None, on_target_done=None, should_cancel=None,
          surrogate=False, surrogate_params=None, force=False, run_kwargs=None,
          surrogate_draws=None, on_draw=None, run_group_id=None):
    """Run every target of a plan, linked to one run group.

    The loop is `fan_out_recipe`'s, with two differences it needs and that one
    does not have: the cancel is checked **between targets**, so a cancelled
    fan-out leaves a readable partial group instead of losing the group id
    inside a `RecipeCancelled`; and `on_target_done` fires per channel so the
    job model can publish per-channel progress rather than per step.

    ``run_group_id`` (discovery-coverage, 2026-10-19): join an EXISTING group
    instead of creating one — *run on the missing channels* extends a run, its
    new channels' runs joining the group its first channels are in. A run the
    cache hands back keeps the group it joined first, as always.

    Returns ``{run_group_id, runs, cancelled}``.
    """
    if not plan_dict.get("runnable"):
        raise ValueError(f"this scope cannot run: {plan_dict.get('reason')}")
    if plan_dict.get("windows"):
        # round A_2, P3: every window, then each channel's windows stitched into its stitched run
        from Working.discovery import windowed
        return windowed.start_windows(plan_dict, db_path=db_path, on_progress=on_progress,
                                      on_target_done=on_target_done, should_cancel=should_cancel,
                                      surrogate=surrogate, surrogate_params=surrogate_params, force=force,
                                      run_kwargs=run_kwargs, surrogate_draws=surrogate_draws, on_draw=on_draw)
    recipe = plan_dict["recipe"]
    targets = recipe["fan_out"]["targets"]
    n = len(targets)

    conn = init_db(db_path)
    try:
        group_id = int(run_group_id) if run_group_id is not None else _runs.create_run_group(conn)
        out, cancelled = [], False
        for i, target in enumerate(targets):
            if should_cancel is not None and should_cancel():
                cancelled = True
                break
            if on_progress is not None:
                on_progress(i, n, plan_dict["targets"][i]["channel_name"])
            per_target = target_recipe(recipe, i, surrogate)
            if surrogate_draws is None:
                surrogate_draws = plan_dict.get("null_draws") or None
            result = run_paired_recipe(
                per_target, db_path=db_path, force=force, run_kwargs=run_kwargs,
                surrogate=bool(surrogate), surrogate_params=surrogate_params,
                surrogate_draws=surrogate_draws, should_cancel_draws=should_cancel,
                on_draw=((lambda j, m, _i=i: on_draw(_i, n, j, m)) if on_draw is not None else None))
            # `execute_recipe` is idempotent: an identical recipe over the same
            # recording and span returns the run that already exists. Re-pointing
            # its `run_group_id` would MOVE it out of the earlier fan-out, leaving
            # that one empty — a Discovery run that had results yesterday would
            # read as "queued · 0 found" today. A run therefore keeps the first
            # group it joined, and this fan-out records the run ids it is made of.
            for rid in [result["run_id"], *result["surrogate_run_ids"]]:
                if _runs.get_run(conn, rid)["run_group_id"] is None:
                    _runs.update_run(conn, rid, run_group_id=group_id)
            row = {
                "run_id": result["run_id"],
                "run_group_id": _runs.get_run(conn, result["run_id"])["run_group_id"],
                "recording_id": target,
                "channel": plan_dict["targets"][i]["channel"],
                "channel_name": plan_dict["targets"][i]["channel_name"],
                "reused": result["reused"],
                "config_hash": result["config_hash"],
                "detections_written": result["detections_written"],
                "surrogate_run_id": result.get("surrogate_run_id"),
                "surrogate_run_ids": list(result["surrogate_run_ids"]),
                "surrogate_skipped": result.get("surrogate_skipped"),
                "surrogate_detections_written": (
                    result["surrogate_result"]["detections_written"]
                    if result.get("surrogate_run_id") is not None else None),
            }
            out.append(row)
            if on_target_done is not None:
                on_target_done(i, n, row)
        return {"run_group_id": group_id, "runs": out, "cancelled": cancelled,
                "run_ids": [r["run_id"] for r in out],
                "reused": [r["run_id"] for r in out if r["reused"]]}
    finally:
        conn.close()


def discovery_run_ids(conn, dr_row):
    """The `runs` rows a Discovery run is made of.

    Recorded on the row itself (`params_json.run_ids`), because `execute_recipe`
    is idempotent: a second Discovery run over the same recipe, recording and
    span is made of the runs the first one produced, and those keep the group
    they joined first. Falling back to the group covers rows written before
    this was recorded. The bridge's `_run_ids` and the detection map both read
    through here, so there is one statement of it (CODING_STANDARDS 6.4)."""
    params = json.loads(dr_row["params_json"] or "{}")
    ids = params.get("run_ids")
    if ids:
        return [int(i) for i in ids]
    if dr_row["run_group_id"]:
        return [int(r["id"]) for r in _runs.list_run_group_runs(conn, int(dr_row["run_group_id"]))
                if r["surrogate_of_run_id"] is None]
    return []


def group_status(conn, run_group_id=None, *, run_ids=None):
    """Per-channel status for one fan-out, read from the rows so it survives a
    restart. Surrogate members are folded onto their parent rather than shown
    as channels of their own.

    ``run_ids`` names the runs explicitly, which is what a caller holding a
    reused run needs: a run keeps the first group it joined, so a later fan-out
    over the same recipe is *made of* runs that belong to an earlier group.
    """
    if run_ids is not None:
        members = [r for r in (_runs.get_run(conn, int(i)) for i in run_ids) if r is not None]
    else:
        members = _runs.list_run_group_runs(conn, run_group_id)
    real = [r for r in members if r["surrogate_of_run_id"] is None]
    channels = []
    for r in real:
        rec = _q.get_recording_by_id(conn, r["recording_id"])
        n_det = conn.execute("SELECT COUNT(*) FROM detections WHERE run_id = ?", (int(r["id"]),)).fetchone()[0]
        channels.append({
            "run_id": int(r["id"]),
            "recording_id": int(r["recording_id"]),
            "channel": int(rec["channel"]) if rec else None,
            "channel_name": (_channel_name(rec["source_file"], int(rec["channel"]),
                                           len(_q.list_recordings(conn, rec["source_file"]))) if rec else None),
            "status": r["status"],
            "detections": int(n_det),
            "error": (r["error_text"].strip().splitlines()[-1] if r["error_text"] else None),
            "current_step": r["current_step"],
            "superseded_at": r["superseded_at"],
            "started_at": r["started_at"],
            "finished_at": r["finished_at"],
            "span": [int(r["span_start"]), int(r["span_end"])],
        })
    channels.sort(key=lambda c: (c["channel"] if c["channel"] is not None else -1, c["run_id"]))
    done = sum(1 for c in channels if c["status"] == "completed")
    failed = [c for c in channels if c["status"] == "failed"]
    if channels and all(c["superseded_at"] for c in channels):
        status = "superseded"
    elif failed:
        status = "failed"
    elif channels and done == len(channels):
        status = "completed"
    elif any(c["status"] == "running" for c in channels):
        status = "running"
    else:
        status = "queued"
    return {"run_group_id": (int(run_group_id) if run_group_id is not None else None),
            "run_ids": [c["run_id"] for c in channels], "channels": channels, "done": done,
            "total": len(channels), "status": status, "n_surrogates": len(members) - len(real),
            "progress": (done / len(channels)) if channels else 0.0}


#: run_id -> (min detection id, max detection id, count) — see `group_status_light`
_COUNT_CACHE: dict = {}
_COUNT_CACHE_MAX = 200_000


def _detection_count(conn, run_id):
    """A run's detection count, remembered against its detection id range: detections are machine rows,
    append-only (`scoreboard.inputs_fingerprint` states why), so while a run's first and last id stand its count
    does. Two index seeks per run, where counting a 60k-detection run walks 60k index entries."""
    lo, hi = conn.execute("SELECT (SELECT MIN(id) FROM detections WHERE run_id = ?), "
                          "(SELECT MAX(id) FROM detections WHERE run_id = ?)", (int(run_id), int(run_id))).fetchone()
    db = _db_key(conn)
    key = (db, int(run_id))
    hit = _COUNT_CACHE.get(key) if db is not None else None
    if hit is not None and hit[0] == lo and hit[1] == hi:
        return hit[2]
    n = 0 if lo is None else int(conn.execute("SELECT COUNT(*) FROM detections WHERE run_id = ?",
                                              (int(run_id),)).fetchone()[0])
    if db is not None:
        if len(_COUNT_CACHE) >= _COUNT_CACHE_MAX:
            _COUNT_CACHE.clear()
        _COUNT_CACHE[key] = (lo, hi, n)
    return n


def _db_key(conn):
    """The database file (path and file identity) a cache entry belongs to; None for an in-memory one."""
    row = next((r for r in conn.execute("PRAGMA database_list").fetchall() if r[1] == "main"), None)
    path = row[2] if row is not None else ""
    if not path:
        return None
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (os.path.normcase(os.path.abspath(path)), getattr(st, "st_ino", 0), st.st_ctime_ns)


def group_status_light(conn, run_group_id=None, *, run_ids=None):
    """`group_status`, answered in a fixed handful of queries (AR, the speed pass): the member runs in one read,
    their recordings in one, each file's channel count in one, and each run's detection count from its id range
    (`_detection_count`). Discovery's run list called `group_status` per Discovery run — a run read, a recording
    read, a recording LISTING and a COUNT(*) per member — 10-13 s for 53 runs on the real database. The answer is
    `group_status`'s, key for key (tests/test_webui_ar_speed.py compares them); `group_status` stays for the
    callers that read one fan-out."""
    if run_ids is not None:
        ids = [int(i) for i in run_ids]
        marks = ",".join(str(i) for i in ids) or "NULL"
        by_id = {int(r["id"]): r for r in conn.execute(f"SELECT * FROM runs WHERE id IN ({marks})").fetchall()}
        members = [by_id[i] for i in ids if i in by_id]
    else:
        members = _runs.list_run_group_runs(conn, run_group_id)
    real = [r for r in members if r["surrogate_of_run_id"] is None]
    rec_marks = ",".join(str(int(r["recording_id"])) for r in real) or "NULL"
    recs = {int(r["id"]): r for r in conn.execute(f"SELECT * FROM recordings WHERE id IN ({rec_marks})").fetchall()}
    files = {r["source_file"] for r in recs.values()}
    n_by_file = {}
    if files:
        n_by_file = {row[0]: int(row[1]) for row in conn.execute(
            "SELECT source_file, COUNT(*) FROM recordings WHERE source_file IN ({}) GROUP BY source_file".format(
                ",".join("?" * len(files))), sorted(files)).fetchall()}
    channels = []
    for r in real:
        rec = recs.get(int(r["recording_id"]))
        channels.append({
            "run_id": int(r["id"]),
            "recording_id": int(r["recording_id"]),
            "channel": int(rec["channel"]) if rec else None,
            "channel_name": (_channel_name(rec["source_file"], int(rec["channel"]), n_by_file.get(rec["source_file"], 0))
                             if rec else None),
            "status": r["status"],
            "detections": _detection_count(conn, int(r["id"])),
            "error": (r["error_text"].strip().splitlines()[-1] if r["error_text"] else None),
            "current_step": r["current_step"],
            "superseded_at": r["superseded_at"],
            "started_at": r["started_at"],
            "finished_at": r["finished_at"],
            "span": [int(r["span_start"]), int(r["span_end"])],
        })
    return _status_of(channels, run_group_id, len(members) - len(real))


def _status_of(channels, run_group_id, n_surrogates):
    channels.sort(key=lambda c: (c["channel"] if c["channel"] is not None else -1, c["run_id"]))
    done = sum(1 for c in channels if c["status"] == "completed")
    failed = [c for c in channels if c["status"] == "failed"]
    if channels and all(c["superseded_at"] for c in channels):
        status = "superseded"
    elif failed:
        status = "failed"
    elif channels and done == len(channels):
        status = "completed"
    elif any(c["status"] == "running" for c in channels):
        status = "running"
    else:
        status = "queued"
    return {"run_group_id": (int(run_group_id) if run_group_id is not None else None),
            "run_ids": [c["run_id"] for c in channels], "channels": channels, "done": done,
            "total": len(channels), "status": status, "n_surrogates": n_surrogates,
            "progress": (done / len(channels)) if channels else 0.0}


def supersede(conn, run_group_id=None, *, run_ids=None, reason=None, at=None):
    """§7.4's *Discard run*: mark every run of the group superseded.

    Writes to `runs` only. No `adjudications` row and no `annotations` row is
    created, here or anywhere this path reaches — that is the whole point of
    the column (a bulk discard must never become thousands of human verdicts).
    Returns how many runs were marked.
    """
    at = at or _now()
    rows = ([r for r in (_runs.get_run(conn, int(i)) for i in run_ids) if r is not None]
            if run_ids is not None else _runs.list_run_group_runs(conn, run_group_id))
    n = 0
    for r in rows:
        if r["superseded_at"]:
            continue
        conn.execute("UPDATE runs SET superseded_at = ? WHERE id = ?", (at, int(r["id"])))
        n += 1
    if reason and n:
        marks = ",".join(str(int(r["id"])) for r in rows)
        conn.execute("UPDATE runs SET error_text = COALESCE(error_text, '') || ? "
                     "WHERE id IN (" + marks + ") AND superseded_at = ?",
                     ("\n[superseded] " + str(reason), at))
    conn.commit()
    return n


def restore(conn, run_group_id=None, *, run_ids=None):
    """Undo a discard. The rows never went anywhere, so this is one UPDATE."""
    if run_ids is not None:
        marks = ",".join(str(int(i)) for i in run_ids) or "NULL"
        cur = conn.execute(f"UPDATE runs SET superseded_at = NULL WHERE id IN ({marks}) "
                           f"AND superseded_at IS NOT NULL")
    else:
        cur = conn.execute("UPDATE runs SET superseded_at = NULL WHERE run_group_id = ? "
                           "AND superseded_at IS NOT NULL", (int(run_group_id),))
    conn.commit()
    return cur.rowcount


def preview(plan_dict, *, db_path=None, sample_samples=14400, target_index=0):
    """§7.1's *Preview on a 4 h sample*: run the chain on a sample of one
    channel, time it, and extrapolate hit count and cost over the scope.

    This is the only honest estimate for a chain whose blocks declare no
    estimator, and it is measured, not modelled — the returned `measured_s` is
    a real elapsed time on this machine.
    """
    import time

    from Working.execution import execute_recipe

    if not plan_dict.get("runnable"):
        raise ValueError(f"this scope cannot run: {plan_dict.get('reason')}")
    target = plan_dict["targets"][target_index]
    a, b = target["span"]
    sample_samples = int(min(sample_samples, b - a))
    steps = plan_dict["recipe"]["steps"]
    sample_recipe = make_recipe(target["recording_id"], steps, span=(a, a + sample_samples))

    t0 = time.perf_counter()
    result = execute_recipe(sample_recipe, db_path=db_path, force=True)
    measured = time.perf_counter() - t0

    scale = (b - a) / float(sample_samples) if sample_samples else 1.0
    spans = int(result.get("detections_written") or 0)
    per_channel = measured * scale
    if plan_dict.get("windows"):
        # round A_2, P3: the sample is (part of) one window, timed with its run's bookkeeping; the application is
        # every window of every channel, each with its draws, and each window's own share of the timeline is
        # (1 - overlap) of it
        w = plan_dict["windows"]
        runs = len(plan_dict["targets"]) * (1 + (int(plan_dict.get("null_draws") or 0)
                                                 if plan_dict.get("surrogate") else 0))
        share = 1.0 - float(w["scope"]["overlap_frac"])
        return {
            "channel": target["channel_name"], "recording_id": target["recording_id"],
            "sample_samples": sample_samples, "sample_span": [a, a + sample_samples],
            "sample_hours": sample_samples / target["fs"] / 3600.0, "measured_s": measured,
            "per_window_s": per_channel, "per_channel_s": per_channel * w["per_channel"],
            "estimate_s": per_channel * runs, "windows": w["targets"], "runs": runs,
            "spans_in_sample": spans, "extrapolated_spans": int(round(spans * scale * w["targets"] * share)),
            "run_id": result.get("run_id"), "scale": scale,
        }
    return {
        "channel": target["channel_name"],
        "recording_id": target["recording_id"],
        "sample_samples": sample_samples,
        "sample_span": [a, a + sample_samples],
        "sample_hours": sample_samples / target["fs"] / 3600.0,
        "measured_s": measured,
        "per_channel_s": per_channel,
        "estimate_s": per_channel * plan_dict["n_channels"],
        "spans_in_sample": spans,
        "extrapolated_spans": int(round(spans * scale * plan_dict["n_channels"])),
        "run_id": result.get("run_id"),
        "scale": scale,
    }


# ── round A_2, P2: one target's recipe, and what it will really compute ─────

def target_recipe(recipe, index, surrogate):
    """The plain per-target recipe a fan-out RUNS for target ``index``:
    `materialize_target` plus the `surrogate` flag the run records (and so every
    cache key carries). One statement of it, read by `start`, by the plan's cache
    lookups and by the cluster export (`chain_job.build_spec`), so the three
    cannot drift on what a target's recipe is."""
    per = materialize_target(recipe, index)
    per["surrogate"] = bool(surrogate)
    return per


def _target_costs(conn, recipe, targets, *, draws, surrogate, surrogate_params):
    """Per target: what its real run and its draws will compute against the step
    cache (`routing.target_cost`), with the target's identity."""
    from Working.discovery import routing

    out = []
    for i, t in enumerate(targets):
        c = routing.target_cost(conn, target_recipe(recipe, i, surrogate), samples=t["samples"], fs=t["fs"],
                                draws=draws, surrogate_params=surrogate_params)
        out.append({"recording_id": t["recording_id"], "channel_name": t["channel_name"], "samples": t["samples"],
                    "seconds": c["seconds"], "real_s": c["real_s"], "draws_s": c["draws_s"],
                    "uncosted": c["uncosted"], "cached": c["cached"], "draws_cached": c["draws_cached"],
                    "draws_known": c["draws_known"], "capped": c["capped"], "refused": c["refused"]})
    return out


def _capped(costs, key):
    """Each (target, chain step) over a cap that must compute, once: the real
    run's index, a draw's shifted back past its surrogate step."""
    out, seen = [], set()
    for c in costs:
        for st in c[key]:
            where = st.get("where") or "real"
            step = st["index"] if where in ("real", "draws") else st["index"] - 1
            if (c["recording_id"], step) in seen:
                continue
            seen.add((c["recording_id"], step))
            out.append({"recording_id": c["recording_id"], "channel_name": c["channel_name"], "step": step,
                        "name": st["name"], "cap": st["cap"], "samples": c["samples"], "where": where})
    return out
