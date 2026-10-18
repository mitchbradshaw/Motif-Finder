"""
coverage_map.py
===============
The corpus map — the home page's channels x bins heatmap — computed from the database alone, UI-free.

It lived in the bridge (`webui/server/corpus.py::_coverage`) until corpus-map-off-the-request (2026-10-19). On the
post-RQ4 database (5 M detections) a recompute takes ~100 s of Python-heavy divergence work, and inside a request it
held the bridge's interpreter: every other page stalled behind it. Here it runs in a worker PROCESS the bridge owns
(`corpus._schedule`), so the bridge keeps serving while the map is recomputed.

``compute(db_path, ...)`` opens its own read-only connection and is what the worker calls; ``compute_conn(conn, ...)``
is the same computation on a connection the caller holds (the bridge's in-place path and the thread fallback). What
each layer means is documented on `webui.server.corpus.coverage`, the bridge's read; the cells, keys and numbers are
the ones the bridge computed before the move (pinned by digest in `tests/test_coverage_map_compute.py`).

This module imports the core only — never `webui`, FastAPI or any UI library: a spawned worker child imports it, and
`tests/test_coverage_map_compute.py` checks the child's `sys.modules`.
"""
from __future__ import annotations

import pathlib
import sqlite3
import sys
import time

import numpy as np

from Working.database import queries as q
from Working.database.runs import load_recipe
from Working.database.schema import BUSY_TIMEOUT_S, VERDICTS
from Working.discovery import divergence as DIV
from Working.discovery.channels import channel_name
from Working.discovery.spans import absolute_bounds
from Working.registration import settings as _settings


def connect_read_only(db_path: str) -> sqlite3.Connection:
    """A read-only connection (`mode=ro`): the worker reads the map's inputs and can write nothing."""
    uri = pathlib.Path(db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False, timeout=BUSY_TIMEOUT_S)
    conn.row_factory = sqlite3.Row
    return conn


def child_modules(prefixes) -> list:
    """The modules loaded in THIS process whose name is, or starts with, one of `prefixes` — the boundary check a
    test sends to the worker child."""
    prefixes = tuple(prefixes)
    return sorted(m for m in list(sys.modules) if any(m == p or m.startswith(p + ".") for p in prefixes))


def ping() -> int:
    """What the bridge sends the worker to start it: the child's pid."""
    import os
    return os.getpid()


def run_methods(conn, source_file: str, run_ids=None) -> list[dict]:
    """Every run on a recording file (with or without detections), with its method (the algorithms of its recipe),
    newest first. A run's null is not a method to filter Explore by (q.not_surrogate), nor is one window of a
    windowed application: its stitched run is the result (q.not_window_part) — unless `run_ids` names it. One query,
    each recipe read once per config (a2-p3 fix round: this walked every run in the database, counting each one's
    detections and loading its recipe in turn — 2.26 s once one recording held 20,000 window runs).

    Moved from `webui/server/corpus.py` (which keeps the name) so the worker can filter runs without the bridge."""
    out = []
    recs = {row["id"]: dict(row) for row in q.list_recordings(conn, source_file)}
    if not recs:
        return out
    where = "x.source_file = ? AND " + q.not_surrogate("r")
    args = [source_file]
    if run_ids:
        ids = [int(i) for i in run_ids]
        where += " AND r.id IN (%s)" % ",".join(str(i) for i in ids)
    else:
        where += " AND " + q.not_window_part("r")
    rows = conn.execute("SELECT r.*, (SELECT COUNT(*) FROM detections d WHERE d.run_id = r.id) AS n_det FROM runs r "
                        "JOIN recordings x ON x.id = r.recording_id WHERE " + where + " ORDER BY r.id DESC",
                        args).fetchall()
    algos_of = {}
    for row in rows:
        if row["config_id"] not in algos_of:
            try:
                recipe = load_recipe(conn, row["config_id"])
                algos_of[row["config_id"]] = [s["algorithm"] for s in recipe["steps"]]
            except Exception:
                algos_of[row["config_id"]] = []
        algos = algos_of[row["config_id"]]
        out.append({"id": row["id"], "recording_id": row["recording_id"], "channel": recs[row["recording_id"]]["channel"],
                    "status": row["status"], "started_at": row["started_at"], "name": row["name"] if "name" in row.keys() else None,
                    "algorithms": algos, "method": algos[-1] if algos else "?", "n_detections": int(row["n_det"])})
    return out


def runs_matching(conn, source_file: str, run_ids, method) -> list | None:
    """Run ids to keep for the detection layers, or None for 'every run'.
    `run_ids` is an explicit list; `method` a substring of any algorithm in the
    run's recipe (stage-3 prompt 01: Explore's run/method filters)."""
    if not run_ids and not method:
        return None
    keep = []
    for r in run_methods(conn, source_file, run_ids=run_ids or None):
        if run_ids and r["id"] not in run_ids:
            continue
        if method and not any(method.lower() in a.lower() for a in r["algorithms"]):
            continue
        keep.append(r["id"])
    return keep


def is_held_out(conn, source_file: str) -> bool:
    """The held-out lock's answer for `source_file`, as `corpus.is_held_out` gives it."""
    return source_file == _settings.HELD_OUT_FILE and _settings.held_out_locked(conn)


def compute(db_path: str, source_file: str, bins: int = 57, verdicts: tuple | None = None,
            run_ids: list | None = None, method: str | None = None, held_out: bool | None = None) -> dict:
    """The corpus map of `source_file`, read from the database at `db_path` through a read-only connection of its
    own: the worker process's entry. `held_out` is the parent's answer to the lock (its key carries it; a script's
    `Working.config.HELD_OUT_UNLOCK` override lives in the parent's memory), None to ask the database."""
    conn = connect_read_only(db_path)
    try:
        return compute_conn(conn, source_file, bins=bins, verdicts=verdicts, run_ids=run_ids, method=method,
                            held_out=held_out)
    finally:
        conn.close()


def compute_conn(conn, source_file: str, bins: int = 57, verdicts: tuple | None = None,
                 run_ids: list | None = None, method: str | None = None, held_out: bool | None = None,
                 between_channels=None) -> dict:
    """The corpus map, computed on `conn`. `between_channels`, when given, is called before every channel after the
    first (the bridge's thread fallback yields to the pages there)."""
    t0 = time.perf_counter()
    recs = [dict(x) for x in q.list_recordings(conn, source_file)]
    if not recs:
        raise KeyError(source_file)
    keep_runs = runs_matching(conn, source_file, run_ids, method)
    n = int(recs[0]["n_samples"]); fs = float(recs[0]["fs"])
    edges = np.linspace(0, n, bins + 1)
    rows = []
    verdict_counts = {v: 0 for v in VERDICTS}
    div_runs = set()
    div_totals = {c: 0 for c in DIV.CELLS}
    div_nc = 0
    for i, rec in enumerate(recs):
        if i and between_channels is not None:
            between_channels()
        rid = rec["id"]
        ann = conn.execute("SELECT start_idx, end_idx, verdict FROM annotations WHERE recording_id = ? AND deleted_at IS NULL",
                           (rid,)).fetchall()
        det = conn.execute("SELECT d.start_idx, d.end_idx, d.run_id, r.span_start FROM detections d JOIN runs r ON r.id = d.run_id WHERE r.recording_id = ? AND " + q.not_surrogate("r")
                           + ("" if keep_runs is not None else " AND " + q.not_window_part("r")),   # a2-p3: a window run is its stitched run's part
                           (rid,)).fetchall()
        if keep_runs is not None:
            det = [d for d in det if d["run_id"] in keep_runs]
        det = [dict(zip(("start_idx", "end_idx", "run_id"), (*absolute_bounds(d["start_idx"], d["end_idx"], d["span_start"]), d["run_id"]))) for d in det]
        for a in ann:
            if a["verdict"] in verdict_counts:
                verdict_counts[a["verdict"]] += 1
        if verdicts:
            ann = [a for a in ann if a["verdict"] in verdicts]
        a_s = np.array([a["start_idx"] for a in ann], dtype=np.int64); a_e = np.array([a["end_idx"] for a in ann], dtype=np.int64)
        d_s = np.array([d["start_idx"] for d in det], dtype=np.int64); d_e = np.array([d["end_idx"] for d in det], dtype=np.int64)
        a_mid = (a_s + a_e) / 2 if len(a_s) else a_s
        d_mid = (d_s + d_e) / 2 if len(d_s) else d_s
        ah = np.histogram(a_mid, bins=edges)[0] if len(a_s) else np.zeros(bins, int)
        dh = np.histogram(d_mid, bins=edges)[0] if len(d_s) else np.zeros(bins, int)
        div = DIV.channel_divergence(conn, rid, keep_runs)
        div_runs.update(div["run_ids"])
        for k in DIV.CELLS:
            div_totals[k] += div["cells"][k]
        div_nc += div["not_comparable"]["n"]
        dis_mid = np.array([(it["start"] + it["end"]) / 2.0 for it in div["items"] if it["cell"] in DIV.DISAGREE])
        xh = np.histogram(dis_mid, bins=edges)[0] if len(dis_mid) else np.zeros(bins, int)
        reviewed = q.reviewed_fraction(conn, rid)
        try:
            reviewed_pct = float(reviewed) * (100.0 if float(reviewed) <= 1.0 else 1.0)
        except Exception:
            reviewed_pct = None
        rows.append({
            "id": rid, "channel": rec["channel"], "name": channel_name(source_file, rec["channel"], len(recs)),
            # `both` is annotations + detections per bin - a SUM, not an
            # intersection. See `corpus.coverage`'s docstring (fixup-a item 16).
            "annotations": ah.tolist(), "detections": dh.tolist(), "both": (ah + dh).tolist(), "disagree": xh.tolist(),
            "counts": {"annotations": int(len(a_s)), "detections": int(len(d_s)),
                       "disagree": int(sum(div["cells"][k] for k in DIV.DISAGREE)),
                       "divergence": {**div["cells"], "not_comparable": div["not_comparable"]["n"],
                                      "not_comparable_why": {**div["not_comparable"]["detections"],
                                                             **div["not_comparable"]["labels"]},
                                      "runs": len(div["run_ids"])},
                       "reviewed_pct": reviewed_pct},
        })
    n_runs = conn.execute("SELECT COUNT(DISTINCT r.id) FROM runs r JOIN detections d ON d.run_id = r.id JOIN recordings x ON x.id = r.recording_id WHERE x.source_file = ? AND " + q.not_surrogate("r") + " AND " + q.not_window_part("r"), (source_file,)).fetchone()[0]
    return {"source_file": source_file, "fs": fs, "n_samples": n, "duration_h": n / fs / 3600.0,
            "bins": bins, "bin_h": n / fs / 3600.0 / bins, "bin_edges_h": (edges / fs / 3600.0).tolist(),
            "rows": rows, "verdict_counts": verdict_counts, "n_detection_runs": int(n_runs),
            "run_filter": keep_runs, "method_filter": method or None,
            "divergence": divergence_header(conn, len(div_runs), keep_runs is None, div_totals, div_nc),
            "held_out": is_held_out(conn, source_file) if held_out is None else bool(held_out),
            "compute_ms": (time.perf_counter() - t0) * 1e3}


def divergence_header(conn, n_runs: int, pooled: bool, cells: dict, not_comparable: int) -> dict:
    """The map's `divergence` block: what was pooled, the totals, and the rules in words."""
    return {"pooled": pooled, "n_runs": n_runs,
            "scope": DIV.scope_text(n_runs, pooled),
            "cells": cells, "not_comparable": not_comparable,
            "labels": DIV.CELL_LABEL, "disagree": list(DIV.DISAGREE),
            "containment": DIV.containment_from_settings(conn),
            "rules": {"containment": DIV.containment_rule_text(DIV.containment_from_settings(conn)),
                      "extent": DIV.extent_rule_text(DIV.rule_from_settings(conn))},
            "verdicts": "every verdict counts here; the verdict filter shapes the annotation layers only"}


def empty(conn, source_file: str, bins: int = 57, held_out: bool | None = None) -> dict:
    """The map's shape with every layer empty: what a read answers (with `pending: true`) while the first map of a
    question is being computed, so the page can lay out its channels and say "computing…". Cheap: the recordings
    list and the settings, no detection or annotation is read. Every number in it is a zero, never a guess."""
    recs = [dict(x) for x in q.list_recordings(conn, source_file)]
    if not recs:
        raise KeyError(source_file)
    n = int(recs[0]["n_samples"]); fs = float(recs[0]["fs"])
    edges = np.linspace(0, n, bins + 1)
    zeros = [0] * bins
    rows = [{"id": rec["id"], "channel": rec["channel"], "name": channel_name(source_file, rec["channel"], len(recs)),
             "annotations": list(zeros), "detections": list(zeros), "both": list(zeros), "disagree": list(zeros),
             "counts": {"annotations": 0, "detections": 0, "disagree": 0,
                        "divergence": {**{c: 0 for c in DIV.CELLS}, "not_comparable": 0, "not_comparable_why": {},
                                       "runs": 0},
                        "reviewed_pct": None}} for rec in recs]
    return {"source_file": source_file, "fs": fs, "n_samples": n, "duration_h": n / fs / 3600.0,
            "bins": bins, "bin_h": n / fs / 3600.0 / bins, "bin_edges_h": (edges / fs / 3600.0).tolist(),
            "rows": rows, "verdict_counts": {v: 0 for v in VERDICTS}, "n_detection_runs": 0,
            "run_filter": None, "method_filter": None,
            "divergence": divergence_header(conn, 0, True, {c: 0 for c in DIV.CELLS}, 0),
            "held_out": is_held_out(conn, source_file) if held_out is None else bool(held_out),
            "compute_ms": 0.0}
