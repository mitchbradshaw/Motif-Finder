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

from Working.config import HELD_OUT_RECORDING_FILE, HELD_OUT_UNLOCK
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
         reuse_lookup=None):
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
    reuse_lookup : callable(conn, recording_id, span) -> dict | None, optional
        Per-target artifact reuse (a matrix profile already on disk). Recorded
        on the target, never assumed.

    Returns
    -------
    dict
        ``{targets, refused, runnable, reason, span, n_channels, recipe,
        estimate_s, per_channel_s, uncosted, route, ceiling_s}``.
    """
    ids = [int(r) for r in recording_ids]
    if not ids:
        raise ValueError("a Discovery scope needs at least one channel")
    ceiling = int(ceiling_s) if ceiling_s is not None else _ceiling_from_settings(conn)

    by_file = {}
    targets, refused = [], []
    for rid in ids:
        rec = _q.get_recording_by_id(conn, rid)
        if rec is None:
            refused.append({"recording_id": rid, "reason": f"no recording with id {rid}"})
            continue
        source_file = rec["source_file"]
        if source_file == HELD_OUT_RECORDING_FILE and not HELD_OUT_UNLOCK:
            refused.append({"recording_id": rid, "reason": (
                f"{HELD_OUT_RECORDING_FILE} is held out (spec §0 D6): locked for the final "
                f"evaluation, and refused before the fan-out starts rather than partway through it")})
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
            "reuse": (reuse_lookup(conn, rid, tuple(target_span)) if reuse_lookup else None),
        })

    uncosted = _uncosted_steps(steps)
    per_channel_s = None
    if measured_per_channel_s is not None:
        per_channel_s = float(measured_per_channel_s)
    elif not uncosted and targets:
        per_channel_s = _estimate_per_channel(steps, targets)

    estimate_s = per_channel_s * len(targets) if per_channel_s is not None else None
    if estimate_s is None:
        route = "unknown"
    elif estimate_s > ceiling:
        route = "cluster"
    else:
        route = "local"

    recipe = None
    if targets:
        recipe = make_recipe(targets[0]["recording_id"], steps, span=(list(span) if span else None),
                             fan_out={"kind": "channels", "targets": [t["recording_id"] for t in targets]})

    runnable = bool(targets)
    reason = None
    if not runnable:
        reason = "; ".join(r["reason"] for r in refused) or "the scope has no runnable channel"

    return {
        "targets": targets, "refused": refused, "runnable": runnable, "reason": reason,
        "span": (list(span) if span else None), "n_channels": len(targets),
        "recipe": recipe, "estimate_s": estimate_s, "per_channel_s": per_channel_s,
        "uncosted": uncosted, "route": route, "ceiling_s": ceiling,
        "measured": measured_per_channel_s is not None,
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
          surrogate=False, surrogate_params=None, force=False, run_kwargs=None):
    """Run every target of a plan, linked to one run group.

    The loop is `fan_out_recipe`'s, with two differences it needs and that one
    does not have: the cancel is checked **between targets**, so a cancelled
    fan-out leaves a readable partial group instead of losing the group id
    inside a `RecipeCancelled`; and `on_target_done` fires per channel so the
    job model can publish per-channel progress rather than per step.

    Returns ``{run_group_id, runs, cancelled}``.
    """
    if not plan_dict.get("runnable"):
        raise ValueError(f"this scope cannot run: {plan_dict.get('reason')}")
    recipe = plan_dict["recipe"]
    targets = recipe["fan_out"]["targets"]
    n = len(targets)

    conn = init_db(db_path)
    try:
        group_id = _runs.create_run_group(conn)
        out, cancelled = [], False
        for i, target in enumerate(targets):
            if should_cancel is not None and should_cancel():
                cancelled = True
                break
            if on_progress is not None:
                on_progress(i, n, plan_dict["targets"][i]["channel_name"])
            per_target = materialize_target(recipe, i)
            per_target["surrogate"] = bool(surrogate)
            result = run_paired_recipe(
                per_target, db_path=db_path, force=force, run_kwargs=run_kwargs,
                surrogate=bool(surrogate), surrogate_params=surrogate_params)
            # `execute_recipe` is idempotent: an identical recipe over the same
            # recording and span returns the run that already exists. Re-pointing
            # its `run_group_id` would MOVE it out of the earlier fan-out, leaving
            # that one empty — a Discovery run that had results yesterday would
            # read as "queued · 0 found" today. A run therefore keeps the first
            # group it joined, and this fan-out records the run ids it is made of.
            for rid in (result["run_id"], result.get("surrogate_run_id")):
                if rid is None:
                    continue
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
