"""Where each detection algorithm fires — the detection map (Discovery › Map).

Rows are algorithms, read across EVERY Discovery session; columns are datasets
and their channels (level 3), one dataset's channels in time chunks (level 2),
or one channel in time bins over the whole recording (level 1). The page
shades a cell by detections per covered hour; this module only counts.

Five rules, each pinned in tests/test_discovery_detection_map.py:

* **A row is an algorithm, not a run.** A `configs` row is per recording and
  span, so the row key is the sha1 of the *steps the runs executed* with
  recording and span stripped — the same across a fan-out's channels and
  across sessions, different the moment a cut, a k or a band differs. Two
  cuts of one seed are two rows.
* **A cell says what it is.** `state` is `covered` (hours > 0; the count may
  be 0), `not_run`, `running`, `failed` or `discarded`; the human row reads
  `not_reviewed` where nobody looked. "Did not look" and "looked and found
  nothing" are different facts and never share a shade. The state is decided
  from the same rounded hours the page receives, so a cell is never `covered`
  with `hours == 0` unless it has a count.
* **Piecewise newest-wins.** Coverage on one channel is the union of every
  live completed run's span; each sample range is counted from the newest
  run that covers it, so a re-application neither doubles a count nor blanks
  what an older whole-recording run measured.
* **A discard is a discard — once.** Discard supersedes the shared `runs`
  rows, so a sibling Discovery run that still holds them may not resurrect
  them; but `execute_recipe` hands a superseded row back to a re-application
  made AFTER the discard, and that run is live: a row held by a Discovery run
  created after the discard counts. A discarded run with no sibling still
  shows as `discarded`, not `not_run`; a `running` row whose Discovery run has
  since failed or finished is a lost run and reads `failed`.
* **The human row's coverage is where a person looked**: the reviewed spans
  plus the span of every live verdict of any kind. Nothing in the app writes
  `reviewed_spans` any more, so a Review verdict would otherwise read as
  "not reviewed". Deleted verdicts and paired-null (surrogate) runs never
  count.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math

import numpy as np

from Working.database import datasets as _datasets
from Working.database import queries as _q
from Working.discovery.channels import channel_name
from Working.discovery.fanout import discovery_run_ids
from Working.discovery.scoreboard import annotations as _annotations
from Working.discovery.spans import absolute_bounds, clip, merged, total_length

HUMAN_KEY = "human"
#: the reference row's colour, the one the Runs page gives the human row
HUMAN_COLOUR = "#22a06b"
HUMAN_VERDICTS = ("interesting", "seed")
CHUNK_OPTIONS = (1, 2, 4, 8)
RUNNING_STATUSES = ("running", "queued", "pending", "started")
FAILED_STATUSES = ("failed", "cancelled")
#: a Discovery run in one of these states has no run still going, whatever its `runs` rows say
#: (a server restart leaves a row at `running` for ever; the Runs page already calls that lost run failed)
SETTLED_DISCOVERY_STATUSES = ("failed", "cancelled", "done", "completed", "superseded")
#: hours travel rounded to a thousandth; the state is decided from the same number
HOURS_PLACES = 3
STATE_RANK = ("covered", "running", "failed", "discarded", "not_run", "not_reviewed")


# ── rows ────────────────────────────────────────────────────────────────────

def steps_key(config_json: str) -> str:
    """The row key of one executed recipe: its steps, with recording and span
    stripped. A map key only — not the recipe hash, which keys the cache.

    Round A_2, P3: a stitched run's recipe carries its window scope, and the
    window length and overlap join the key — "treat each scale as a new
    version of the detection algorithm" (the researcher, 2026-10-17), so
    "drop_detection_v1 · 1 h windows · 50 %" and the whole-span run are two
    rows. A recipe without a window scope keys exactly as before."""
    cfg = json.loads(config_json or "{}")
    steps = cfg.get("steps", cfg)
    windows = cfg.get("windows") if isinstance(cfg, dict) else None
    if isinstance(windows, dict) and windows.get("window_s") is not None:
        ident = {"steps": steps, "windows": {"window_s": float(windows["window_s"]),
                                             "overlap_frac": float(windows.get("overlap_frac", 0.5))}}
        digest = hashlib.sha1(json.dumps(ident, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        return f"steps:{digest[:12]}"
    digest = hashlib.sha1(json.dumps(steps, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return f"steps:{digest[:12]}"


def _discovery_runs(conn):
    """Every Discovery run the researcher has not removed, newest first, with
    its session's name. Discarded (superseded) ones are kept: their rows say
    `discarded` on the map, they just name no row of their own."""
    cols = {c["name"] for c in conn.execute("PRAGMA table_info(discovery_runs)")}
    removed = " WHERE d.removed_at IS NULL" if "removed_at" in cols else ""
    return conn.execute(
        "SELECT d.*, s.name AS session_name FROM discovery_runs d "
        "JOIN discovery_sessions s ON s.id = d.session_id "
        f"{removed} ORDER BY d.id DESC").fetchall()


def _runs_by_id(conn, ids):
    if not ids:
        return {}
    marks = ",".join(str(int(i)) for i in sorted(set(ids)))
    rows = conn.execute(
        "SELECT r.id, r.config_id, r.recording_id, r.span_start, r.span_end, r.status, r.superseded_at "
        "FROM runs r WHERE r.id IN (" + marks + ") AND " + _q.not_surrogate("r")).fetchall()
    return {int(r["id"]): dict(r) for r in rows}


def _steps_keys(conn, config_ids):
    if not config_ids:
        return {}
    marks = ",".join(str(int(i)) for i in sorted(set(config_ids)))
    return {int(r["id"]): steps_key(r["config_json"])
            for r in conn.execute("SELECT id, config_json FROM configs WHERE id IN (" + marks + ")")}


def _when(stamp):
    """An ISO timestamp as a datetime, or None — the rows mix second and
    microsecond precision and the comparison must not care."""
    if not stamp:
        return None
    try:
        return _dt.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None


def _row_meta(dr, params):
    """What a row is called and what it is, from the Discovery run it came
    from — the newest live one of its key names it."""
    kind = dr["kind"] if dr["kind"] in ("template", "seed") else "template"
    label = dr["label"]
    band = params.get("band") or {}
    # round A_2, P3: a windowed application names its scale (its own row: `steps_key`)
    scope = (params.get("windows") or {}).get("scope")
    windows = None
    if scope:
        from Working.discovery.windowed import scope_label
        windows = {"scope": scope, "label": scope_label(scope)}
    if kind == "template":
        label = dr["template_name"] or dr["label"]
        if params.get("version") is not None:
            label = f"{label} v{params['version']}"
        if band.get("label"):
            label = f"{label} · {band['label']}"
        if windows:
            label = f"{label} · {windows['label']}"
    return {
        "kind": kind, "label": label, "colour": dr["colour"], "detail": params.get("detail"),
        "template": dr["template_name"], "version": params.get("version"),
        "seedId": params.get("seedId"), "cut": params.get("cut"), "k": params.get("k"),
        "exclusion": params.get("exclusion"), "scales": params.get("scales"),
        "band": band.get("label") if kind == "template" and params.get("band") else None,
        "windows": windows,
    }


def _held_copy(dr, r):
    """One Discovery run's view of one `runs` row. A row the discard
    superseded is live again for a Discovery run created after the discard
    (`execute_recipe` handed it back to that re-application); it stays
    superseded for the siblings that held it before. The holder's own status
    says whether a `running` row is really still going."""
    held = dict(r)
    sup, made = _when(r["superseded_at"]), _when(dr["created_at"])
    if sup is not None and made is not None and made > sup and not dr["superseded_at"]:
        held["superseded_at"] = None
    held["drStatus"] = dr["status"]
    held["drRunKey"] = dr["run_key"]
    held["drSession"] = int(dr["session_id"])
    held["drId"] = int(dr["id"])
    return held


def _gather(conn, exclude_files=()):
    """Every live machine row with its `runs` rows grouped by recording:
    ``rows`` (ordered, the human row first) and ``by_row[row_key][recording_id]
    -> {run_id: held row}``. A run on an excluded file (the held-out one) is as
    if it were not there: it names no row and no session. A discarded
    Discovery run names no row, but its rows reach the rows that live runs
    name, so a channel it alone touched reads `discarded`."""
    drs = _discovery_runs(conn)
    ids_of = {int(dr["id"]): discovery_run_ids(conn, dr) for dr in drs}
    runs = _runs_by_id(conn, [i for ids in ids_of.values() for i in ids])
    if exclude_files:
        hidden = {int(r["id"]) for r in _q.list_recordings(conn) if r["source_file"] in exclude_files}
        runs = {rid: r for rid, r in runs.items() if int(r["recording_id"]) not in hidden}
    keys = _steps_keys(conn, [r["config_id"] for r in runs.values()])
    rows_meta: dict[str, dict] = {}
    by_row: dict[str, dict[int, dict[int, dict]]] = {}

    def attach(dr, r):
        key = keys[int(r["config_id"])]
        slot = by_row.setdefault(key, {}).setdefault(int(r["recording_id"]), {})
        held = _held_copy(dr, r)
        prev = slot.get(int(r["id"]))
        # several Discovery runs may hold one row: the live view wins over the superseded one
        if prev is None or (prev["superseded_at"] and not held["superseded_at"]):
            slot[int(r["id"])] = held

    live = [dr for dr in drs if not dr["superseded_at"]]
    for dr in live:                                # newest first: the first Discovery run to name a key labels it
        params = json.loads(dr["params_json"] or "{}")
        for rid in ids_of[int(dr["id"])]:
            r = runs.get(rid)
            if r is None:                          # a surrogate, a hidden file, or a run row that no longer exists
                continue
            key = keys[int(r["config_id"])]
            meta = rows_meta.get(key)
            if meta is None:
                meta = rows_meta[key] = {"key": key, **_row_meta(dr, params), "sessions": [], "sessionNames": {},
                                         "latestSession": int(dr["session_id"]), "latestRunKey": dr["run_key"],
                                         "latestRunId": int(dr["id"]), "runs": 0}
            if int(dr["session_id"]) not in meta["sessions"]:
                meta["sessions"].append(int(dr["session_id"]))
                meta["sessionNames"][int(dr["session_id"])] = dr["session_name"]
            attach(dr, r)
    for dr in drs:                                 # the discarded ones, for the rows that exist
        if not dr["superseded_at"]:
            continue
        for rid in ids_of[int(dr["id"])]:
            r = runs.get(rid)
            if r is not None and keys[int(r["config_id"])] in rows_meta:
                attach(dr, r)
    for key, meta in rows_meta.items():
        meta["runs"] = sum(len(v) for v in by_row.get(key, {}).values())
        meta["sessions"] = sorted(meta["sessions"])
        meta["sessionNames"] = [meta["sessionNames"][s] for s in meta["sessions"]]
    # two rows with one label (the same template edited in place) say which steps each is
    by_label: dict[str, list] = {}
    for meta in rows_meta.values():
        by_label.setdefault(meta["label"], []).append(meta)
    for same in by_label.values():
        if len(same) > 1:
            for meta in same:
                meta["label"] = f"{meta['label']} · {meta['key'].replace('steps:', 'steps ')[:12]}"
    human = {"key": HUMAN_KEY, "kind": "human", "label": "human", "colour": HUMAN_COLOUR,
             "detail": "interesting and seed verdicts · coverage is where a person looked",
             "template": None, "version": None, "seedId": None, "cut": None, "k": None, "exclusion": None,
             "scales": None, "band": None, "windows": None, "sessions": [], "sessionNames": [], "latestSession": None,
             "latestRunKey": None, "latestRunId": None, "runs": 0}
    order = {"template": 0, "seed": 1}
    rows = [human] + sorted(rows_meta.values(), key=lambda m: (order.get(m["kind"], 2), m["label"].lower()))
    return rows, by_row


# ── coverage: piecewise newest-wins ─────────────────────────────────────────

def _subtract(pieces, taken):
    """``pieces`` minus one ``[a, b)`` interval."""
    a, b = taken
    out = []
    for lo, hi in pieces:
        if hi <= a or lo >= b:
            out.append((lo, hi))
            continue
        if lo < a:
            out.append((lo, a))
        if hi > b:
            out.append((b, hi))
    return out


def _resolve(run_rows):
    """One row on one recording: the sample ranges each live completed run
    owns — newest first takes what older runs have not yet claimed."""
    live = sorted((r for r in run_rows if r["status"] == "completed" and not r["superseded_at"]),
                  key=lambda r: -int(r["id"]))
    claimed = []                                  # (lo, hi, run_id), disjoint
    for r in live:
        pieces = [(int(r["span_start"]), int(r["span_end"]))]
        for lo, hi, _ in claimed:
            pieces = _subtract(pieces, (lo, hi))
        claimed.extend((lo, hi, int(r["id"])) for lo, hi in pieces if hi > lo)
    claimed.sort()
    return claimed


def _is_running(r):
    return r["status"] in RUNNING_STATUSES and not r["superseded_at"] \
        and r.get("drStatus") not in SETTLED_DISCOVERY_STATUSES


def _is_failed(r):
    if r["superseded_at"]:
        return False
    if r["status"] in FAILED_STATUSES:
        return True
    # a row left at `running` by a Discovery run that has since failed or finished: lost, so failed
    return r["status"] in RUNNING_STATUSES and r.get("drStatus") in SETTLED_DISCOVERY_STATUSES


def _uncovered_state(run_rows, lo, hi):
    """What a slice with no coverage is: the runs whose span reaches it say
    whether something is still running there, failed there, or was discarded
    — else nothing ever ran there."""
    here = [r for r in run_rows if int(r["span_start"]) < hi and int(r["span_end"]) > lo]
    if any(_is_running(r) for r in here):
        return "running"
    if any(_is_failed(r) for r in here):
        return "failed"
    if any(r["superseded_at"] for r in here):
        return "discarded"
    return "not_run"


def _starts(conn, claimed, run_rows):
    """Channel-absolute detection starts that count: each from the run that
    owns the sample range it falls in."""
    if not claimed:
        return np.array([], dtype=float)
    owners = sorted({rid for _, _, rid in claimed})
    marks = ",".join(str(i) for i in owners)
    span_start = {int(r["id"]): int(r["span_start"]) for r in run_rows}
    by_run: dict[int, list] = {}
    for d in conn.execute("SELECT run_id, start_idx, end_idx FROM detections WHERE run_id IN (" + marks + ")"):
        a, _ = absolute_bounds(d["start_idx"], d["end_idx"], span_start.get(int(d["run_id"]), 0))
        by_run.setdefault(int(d["run_id"]), []).append(a)
    out = []
    for lo, hi, rid in claimed:
        out.extend(a for a in by_run.get(rid, ()) if lo <= a < hi)
    return np.array(out, dtype=float)


def _hours(samples, fs):
    return round(samples / fs / 3600.0, HOURS_PLACES)


def _machine_cells(conn, run_rows, edges, fs):
    """One row on one recording, cut at ``edges`` (sample indices): a cell per
    slice with its count, covered hours (rounded, and the state decided from
    the rounded number), covered sample count, state and the Discovery run
    that owns the slice's first covered sample."""
    claimed = _resolve(run_rows)
    cover = [(lo, hi) for lo, hi, _ in claimed]
    holder = {int(r["id"]): r for r in run_rows}
    starts = _starts(conn, claimed, run_rows)
    counts = np.histogram(starts, bins=np.asarray(edges, dtype=float))[0] if len(starts) else np.zeros(len(edges) - 1, dtype=int)
    out = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        samples = total_length(clip(cover, lo, hi))
        h = _hours(samples, fs)
        count = int(counts[i])
        owner = next((holder.get(rid) for a, b, rid in claimed if a < hi and b > lo), None)
        out.append({"count": count, "hours": h, "samples": int(samples),
                    "state": "covered" if (h > 0 or count > 0) else _uncovered_state(run_rows, lo, hi),
                    "owner": ({"runKey": owner["drRunKey"], "sessionId": owner["drSession"]} if owner else None)})
    return out


def _human_cells(conn, recording_id, edges, fs):
    """The human reference on one recording: live interesting/seed verdicts
    per slice, over the hours a person looked at (reviewed spans plus every
    live verdict's own span)."""
    live = _annotations(conn, recording_id)
    reviewed = merged([(r["start_idx"], r["end_idx"]) for r in conn.execute(
        "SELECT start_idx, end_idx FROM reviewed_spans WHERE recording_id = ?", (int(recording_id),))])
    looked = merged(list(reviewed) + [(a["start"], a["end"]) for a in live])
    marks = [a for a in live if a["verdict"] in HUMAN_VERDICTS]
    starts = np.array([a["start"] for a in marks], dtype=float)
    counts = np.histogram(starts, bins=np.asarray(edges, dtype=float))[0] if len(starts) else np.zeros(len(edges) - 1, dtype=int)
    out = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        samples = total_length(clip(looked, lo, hi))
        h = _hours(samples, fs)
        count = int(counts[i])
        inside = [a for a in marks if lo <= a["start"] < hi]
        out.append({"count": count, "hours": h, "samples": int(samples),
                    "state": "covered" if (h > 0 or count > 0) else "not_reviewed",
                    "interesting": sum(1 for a in inside if a["verdict"] == "interesting"),
                    "seed": sum(1 for a in inside if a["verdict"] == "seed"),
                    "reviewedH": _hours(total_length(clip(reviewed, lo, hi)), fs), "owner": None})
    return out


def _public(cell):
    """The cell as it travels: the sample count and the owner are the
    timeline's business."""
    return {k: v for k, v in cell.items() if k not in ("samples", "owner")}


# ── datasets ────────────────────────────────────────────────────────────────

def _files(conn):
    """``source_file -> [recording row, ...]`` in channel order, registered
    recordings only (a soft-unregistered one is `active = 0`)."""
    out: dict[str, list] = {}
    for row in (dict(r) for r in _q.list_recordings(conn)):
        if not row.get("active", 1):
            continue
        out.setdefault(row["source_file"], []).append(row)
    for chans in out.values():
        chans.sort(key=lambda c: int(c["channel"]))
    return dict(sorted(out.items()))


def _dataset(source_file, chans, names):
    fs = float(chans[0]["fs"])
    return {"file": source_file, "name": names.get(source_file) or source_file,
            "hours": _hours(max(int(c["n_samples"]) for c in chans), fs), "fs": fs,
            "channels": [{"name": channel_name(source_file, c["channel"], len(chans)), "recordingId": int(c["id"]),
                          "hours": _hours(int(c["n_samples"]), float(c["fs"]))} for c in chans]}


def dataset_map(conn, *, exclude_files=()):
    """Level 3: every dataset that has a Discovery run, each with all its
    channels; one cell per row and channel. ``withoutRuns`` names the
    registered datasets no Discovery run touched and ``heldOutOmitted`` the
    excluded files that exist, so a one-dataset map explains itself."""
    rows, by_row = _gather(conn, exclude_files)
    files = _files(conn)
    names = _datasets.display_names(conn)
    touched = {rid for per in by_row.values() for rid in per}
    datasets, without, omitted = [], [], []
    for sf, chans in files.items():
        if sf in exclude_files:
            omitted.append(sf)
            continue
        ds = _dataset(sf, chans, names)
        if not any(int(c["id"]) in touched for c in chans):
            without.append({"file": sf, "name": ds["name"], "hours": ds["hours"]})
            continue
        fs = ds["fs"]
        cells: dict[str, dict] = {}
        for row in rows:
            per = {}
            for c in chans:
                edges = [0, int(c["n_samples"])]
                name = channel_name(sf, c["channel"], len(chans))
                if row["key"] == HUMAN_KEY:
                    per[name] = _public(_human_cells(conn, int(c["id"]), edges, fs)[0])
                else:
                    run_rows = list(by_row.get(row["key"], {}).get(int(c["id"]), {}).values())
                    per[name] = _public(_machine_cells(conn, run_rows, edges, fs)[0])
            cells[row["key"]] = per
        ds["cells"] = cells
        datasets.append(ds)
    return {"rows": rows, "datasets": datasets, "withoutRuns": without, "heldOutOmitted": omitted}


def _file_rows(conn, source_file):
    chans = _files(conn).get(source_file)
    if not chans:
        raise KeyError(f"no registered recording {source_file!r}")
    return chans


def channel_map(conn, source_file, *, chunks=1, exclude_files=()):
    """Level 2: one dataset's channels, each cut into ``chunks`` equal slices
    of its timeline (1, 2, 4 or 8)."""
    chunks = int(chunks)
    if chunks not in CHUNK_OPTIONS:
        raise ValueError(f"chunks must be one of {CHUNK_OPTIONS}, not {chunks}")
    chans = _file_rows(conn, source_file)
    rows, by_row = _gather(conn, exclude_files)
    ds = _dataset(source_file, chans, _datasets.display_names(conn))
    fs = ds["fs"]
    cells: dict[str, dict] = {}
    for row in rows:
        per = {}
        for c in chans:
            n = int(c["n_samples"])
            edges = [int(round(n * i / chunks)) for i in range(chunks + 1)]
            name = channel_name(source_file, c["channel"], len(chans))
            if row["key"] == HUMAN_KEY:
                per[name] = [_public(x) for x in _human_cells(conn, int(c["id"]), edges, fs)]
            else:
                run_rows = list(by_row.get(row["key"], {}).get(int(c["id"]), {}).values())
                per[name] = [_public(x) for x in _machine_cells(conn, run_rows, edges, fs)]
        cells[row["key"]] = per
    return {**ds, "rows": rows, "chunks": chunks, "cells": cells}


def timeline_map(conn, source_file, channel, *, bin_h=3.0, exclude_files=()):
    """Level 1: one channel over the WHOLE recording in ``bin_h``-hour bins —
    counts per bin, the covered fraction of each bin (from sample counts, so a
    bin with a count is never drawn uncovered), each bin's state, and the
    Discovery run that owns each covered bin (what a click can open)."""
    bin_h = float(bin_h)
    if not bin_h > 0:
        raise ValueError(f"binH must be positive, not {bin_h}")
    chans = _file_rows(conn, source_file)
    by_name = {channel_name(source_file, c["channel"], len(chans)): c for c in chans}
    if channel not in by_name:
        raise KeyError(f"no channel {channel!r} on {source_file!r}; it has {sorted(by_name)}")
    c = by_name[channel]
    fs, n = float(c["fs"]), int(c["n_samples"])
    hours = n / fs / 3600.0
    n_bins = max(1, int(math.ceil(hours / bin_h - 1e-9)))
    edges = [min(n, int(round(i * bin_h * 3600.0 * fs))) for i in range(n_bins + 1)]
    edges[-1] = n
    widths = [max(1, edges[i + 1] - edges[i]) for i in range(n_bins)]
    rows, by_row = _gather(conn, exclude_files)
    ds = _dataset(source_file, chans, _datasets.display_names(conn))
    cells: dict[str, dict] = {}
    for row in rows:
        if row["key"] == HUMAN_KEY:
            per = _human_cells(conn, int(c["id"]), edges, fs)
        else:
            per = _machine_cells(conn, list(by_row.get(row["key"], {}).get(int(c["id"]), {}).values()), edges, fs)
        states = [p["state"] for p in per]
        cells[row["key"]] = {
            "counts": [p["count"] for p in per],
            "covered": [round(min(1.0, p["samples"] / widths[i]), 4) for i, p in enumerate(per)],
            "states": states,
            "owners": [p["owner"] for p in per],
            "state": next(st for st in STATE_RANK if st in states),
        }
    return {**ds, "rows": rows, "channel": channel, "recordingId": int(c["id"]), "hours": _hours(n, fs),
            "binH": bin_h, "nBins": n_bins, "cells": cells}
