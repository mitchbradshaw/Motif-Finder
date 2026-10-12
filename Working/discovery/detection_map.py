"""Where each detection algorithm fires — the detection map (Discovery › Map).

Rows are algorithms, read across EVERY Discovery session; columns are datasets
and their channels (level 3), one dataset's channels in time chunks (level 2),
or one channel in time bins over the whole recording (level 1). The page
shades a cell by detections per covered hour; this module only counts.

Four rules, each pinned in tests/test_discovery_detection_map.py:

* **A row is an algorithm, not a run.** A `configs` row is per recording and
  span, so the row key is the sha1 of the *steps the runs executed* with
  recording and span stripped — the same across a fan-out's channels and
  across sessions, different the moment a cut, a k or a band differs. Two
  cuts of one seed are two rows.
* **A cell says what it is.** `state` is `covered` (hours > 0; the count may
  be 0), `not_run`, `running`, `failed` or `discarded`; the human row reads
  `not_reviewed` where nobody looked. "Did not look" and "looked and found
  nothing" are different facts and never share a shade.
* **Piecewise newest-wins.** Coverage on one channel is the union of every
  live completed run's span; each sample range is counted from the newest
  run that covers it, so a re-application neither doubles a count nor blanks
  what an older whole-recording run measured.
* **The human row's coverage is where a person looked**: the reviewed spans
  plus the span of every live verdict of any kind. Nothing in the app writes
  `reviewed_spans` any more, so a Review verdict would otherwise read as
  "not reviewed". Deleted verdicts and paired-null (surrogate) runs never
  count; a discard supersedes the shared `runs` rows, and a sibling Discovery
  run in another session that still holds them may not resurrect them.
"""
from __future__ import annotations

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


# ── rows ────────────────────────────────────────────────────────────────────

def steps_key(config_json: str) -> str:
    """The row key of one executed recipe: its steps, with recording and span
    stripped. A map key only — not the recipe hash, which keys the cache."""
    cfg = json.loads(config_json or "{}")
    steps = cfg.get("steps", cfg)
    digest = hashlib.sha1(json.dumps(steps, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return f"steps:{digest[:12]}"


def _live_discovery_runs(conn):
    """Every Discovery run the researcher has not removed or discarded, newest
    first, with its session's name."""
    cols = {c["name"] for c in conn.execute("PRAGMA table_info(discovery_runs)")}
    removed = " AND d.removed_at IS NULL" if "removed_at" in cols else ""
    return conn.execute(
        "SELECT d.*, s.name AS session_name FROM discovery_runs d "
        "JOIN discovery_sessions s ON s.id = d.session_id "
        f"WHERE d.superseded_at IS NULL{removed} ORDER BY d.id DESC").fetchall()


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


def _row_meta(dr, params):
    """What a row is called and what it is, from the Discovery run it came
    from — the newest one of its key names it."""
    kind = dr["kind"] if dr["kind"] in ("template", "seed") else "template"
    label = dr["label"]
    if kind == "template":
        label = dr["template_name"] or dr["label"]
        if params.get("version") is not None:
            label = f"{label} v{params['version']}"
        band = params.get("band") or {}
        if band.get("label"):
            label = f"{label} · {band['label']}"
    return {
        "kind": kind, "label": label, "colour": dr["colour"], "detail": params.get("detail"),
        "template": dr["template_name"], "version": params.get("version"),
        "seedId": params.get("seedId"), "cut": params.get("cut"), "k": params.get("k"),
        "exclusion": params.get("exclusion"), "scales": params.get("scales"),
        "band": band.get("label") if kind == "template" and params.get("band") else None,
    }


def _gather(conn, exclude_files=()):
    """Every live machine row with its `runs` rows grouped by recording:
    ``rows`` (ordered, the human row first) and ``by_row[row_key][recording_id]
    -> [runs row, ...]`` (de-duplicated by `runs.id`). A run on an excluded
    file (the held-out one) is as if it were not there: it names no row and
    no session."""
    drs = _live_discovery_runs(conn)
    ids_of = {int(dr["id"]): discovery_run_ids(conn, dr) for dr in drs}
    runs = _runs_by_id(conn, [i for ids in ids_of.values() for i in ids])
    if exclude_files:
        hidden = {int(r["id"]) for r in _q.list_recordings(conn) if r["source_file"] in exclude_files}
        runs = {rid: r for rid, r in runs.items() if int(r["recording_id"]) not in hidden}
    keys = _steps_keys(conn, [r["config_id"] for r in runs.values()])
    rows_meta: dict[str, dict] = {}
    by_row: dict[str, dict[int, dict[int, dict]]] = {}
    for dr in drs:                                 # newest first: the first Discovery run to name a key labels it
        params = json.loads(dr["params_json"] or "{}")
        for rid in ids_of[int(dr["id"])]:
            r = runs.get(rid)
            if r is None:                          # a surrogate, or a run row that no longer exists
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
            by_row.setdefault(key, {}).setdefault(int(r["recording_id"]), {})[rid] = r
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
             "scales": None, "band": None, "sessions": [], "sessionNames": [], "latestSession": None,
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


def _uncovered_state(run_rows, lo, hi):
    """What a slice with no coverage is: the runs whose span reaches it say
    whether something is still running there, failed there, or was discarded
    — else nothing ever ran there."""
    here = [r for r in run_rows if int(r["span_start"]) < hi and int(r["span_end"]) > lo]
    if any(r["status"] in RUNNING_STATUSES and not r["superseded_at"] for r in here):
        return "running"
    if any(r["status"] in FAILED_STATUSES and not r["superseded_at"] for r in here):
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


def _machine_cells(conn, run_rows, edges, fs):
    """One row on one recording, cut at ``edges`` (sample indices): a cell per
    slice with its count, covered hours and state."""
    claimed = _resolve(run_rows)
    cover = [(lo, hi) for lo, hi, _ in claimed]
    starts = _starts(conn, claimed, run_rows)
    counts = np.histogram(starts, bins=np.asarray(edges, dtype=float))[0] if len(starts) else np.zeros(len(edges) - 1, dtype=int)
    out = []
    for i in range(len(edges) - 1):
        h = total_length(clip(cover, edges[i], edges[i + 1])) / fs / 3600.0
        out.append({"count": int(counts[i]), "hours": round(h, 3),
                    "state": "covered" if h > 0 else _uncovered_state(run_rows, edges[i], edges[i + 1])})
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
        h = total_length(clip(looked, lo, hi)) / fs / 3600.0
        inside = [a for a in marks if lo <= a["start"] < hi]
        out.append({"count": int(counts[i]), "hours": round(h, 3), "state": "covered" if h > 0 else "not_reviewed",
                    "interesting": sum(1 for a in inside if a["verdict"] == "interesting"),
                    "seed": sum(1 for a in inside if a["verdict"] == "seed"),
                    "reviewedH": round(total_length(clip(reviewed, lo, hi)) / fs / 3600.0, 3)})
    return out


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
            "hours": round(max(int(c["n_samples"]) for c in chans) / fs / 3600.0, 3), "fs": fs,
            "channels": [{"name": channel_name(source_file, c["channel"], len(chans)), "recordingId": int(c["id"]),
                          "hours": round(int(c["n_samples"]) / float(c["fs"]) / 3600.0, 3)} for c in chans]}


def dataset_map(conn, *, exclude_files=()):
    """Level 3: every dataset that has a live Discovery run, each with all its
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
                if row["key"] == HUMAN_KEY:
                    per[channel_name(sf, c["channel"], len(chans))] = _human_cells(conn, int(c["id"]), edges, fs)[0]
                else:
                    run_rows = list(by_row.get(row["key"], {}).get(int(c["id"]), {}).values())
                    per[channel_name(sf, c["channel"], len(chans))] = _machine_cells(conn, run_rows, edges, fs)[0]
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
                per[name] = _human_cells(conn, int(c["id"]), edges, fs)
            else:
                run_rows = list(by_row.get(row["key"], {}).get(int(c["id"]), {}).values())
                per[name] = _machine_cells(conn, run_rows, edges, fs)
        cells[row["key"]] = per
    return {**ds, "rows": rows, "chunks": chunks, "cells": cells}


def timeline_map(conn, source_file, channel, *, bin_h=3.0, exclude_files=()):
    """Level 1: one channel over the WHOLE recording in ``bin_h``-hour bins —
    counts per bin and the covered fraction of each bin, so a bin the run never
    reached is not-run rather than empty."""
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
        states = {p["state"] for p in per}
        rank = ("covered", "running", "failed", "discarded", "not_run", "not_reviewed")
        cells[row["key"]] = {
            "counts": [p["count"] for p in per],
            "covered": [round(min(1.0, p["hours"] * 3600.0 * fs / widths[i]), 4) for i, p in enumerate(per)],
            "state": next(st for st in rank if st in states),
        }
    return {**ds, "rows": rows, "channel": channel, "recordingId": int(c["id"]), "hours": round(hours, 3),
            "binH": bin_h, "nBins": n_bins, "cells": cells}
