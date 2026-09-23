"""Discovery's live routes (stage-3 prompt 04, spec §7).

Thin over `Working.discovery`: the session and its runs are rows
(`discovery_sessions` / `discovery_runs`), the fan-out is
`Working.discovery.fanout`, the scoreboard is `Working.discovery.scoreboard`,
the seeded search is `Working.discovery.seeded_search`, and the two Compare
pages are `Working.discovery.compare` + `window_chain`. Nothing numerical is
computed here.

Three things this module is careful about, because the fixture era made them
easy to get wrong:

* **A number on this page is a number from the tables.** Where there is no
  number — nothing reviewed, no null, a run the section does not reach — the
  payload carries the core's own words (`no reviewed overlap`, `not yet
  scored`) rather than a zero. §4.8's rule holds on the template cards too: a
  score never travels without its scope.
* **The scope is checked before anything runs.** The held-out file is refused
  on every route that names a recording, a channel, a run or a seed, and the
  fan-out plan drops a held-out or too-short channel before the first target
  starts rather than partway through.
* **Long work is a job.** A seeded search over a section is a `sweep` job with
  per-channel progress through `JobManager`; its result is written back to the
  session row, because a non-chain job's `result` is None after a restart.

`discovery_sessions` is on neither rule-5 list, like `settings` and
`audit_log`: it is not a verdict and not a detection, so both doors refuse it
and it is written with its own plain SQL.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import threading

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from Working.database import queries as q
from Working.database import runs as R
from Working.discovery import compare as D
from Working.discovery import fanout, seeded_search
from Working.discovery import scoreboard as SB
from Working.discovery.matching import match_span_sets, rule_from_settings
from Working.discovery.spans import absolute_bounds, clip, merged, total_length

from . import corpus
from .runtime import HELD_OUT_FILE, REPO_ROOT
from .serialize import _clean

router = APIRouter()

#: One colour per run, assigned by the order runs were added to the session.
#: Green is the human reference row's, and is never handed to an algorithm.
HUMAN_COLOUR = "#22a06b"
RUN_COLOURS = ["#0a84ff", "#12a594", "#af52de", "#e8900c", "#5b6ef5", "#d6409f", "#0f766e", "#b45309"]
SEED_DIR = os.path.join(REPO_ROOT, "DATA", "library_seed", "drop_motifs5", "motifs")
FIRES_BIN_H = 3
OVERVIEW_MAX_POINTS = 2000
TRACE_POINTS = 120
SEED_LIMIT = 24
#: A first session opens on four hours, not on a 721-hour recording — see
#: `_densest_section`.
DEFAULT_SECTION_H = 4.0
#: A null is N surrogate realisations of the section, each matched against the
#: seed. The cost is draws x section, so a generous `draws` over a long section
#: is minutes of work; past this budget the draws are cut and the payload says
#: so, rather than the page quietly waiting.
NULL_SAMPLE_BUDGET = 4_000_000
NULL_MIN_DRAWS = 5

_results: dict = {}          # cache key -> the computed seed-search result
_results_lock = threading.Lock()


def _now():
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _conn(request: Request):
    rt = request.app.state.rt
    if not getattr(request.app.state, "schema_ensured", False):
        from Working.database.schema import init_db
        init_db(rt.db_path).close()
        request.app.state.schema_ensured = True
    return corpus.connect(rt.db_path)


def _refuse_held_out(source_file: str):
    if source_file == HELD_OUT_FILE:
        raise HTTPException(423, {
            "message": (f"{HELD_OUT_FILE} is held out (spec §0 D6): locked for the final evaluation — "
                        f"Discovery will not scope, run, score or plot it"),
            "file": HELD_OUT_FILE})


# ── the scope: recordings and channels by name ──────────────────────────────

def _recordings(conn):
    return corpus.recordings(conn)


def _stem(source_file: str) -> str:
    return source_file.rsplit(".", 1)[0]


def _recording_options(conn):
    out = []
    for r in _recordings(conn):
        out.append({
            "key": _stem(r["source_file"]), "label": _stem(r["source_file"]),
            "file": r["source_file"], "stem": _stem(r["source_file"]),
            "hours": round(r["duration_h"], 3), "channels": [c["name"] for c in r["channels"]],
            "heldOut": bool(r["held_out"]), "fs": r["fs"],
            "heldOutReason": r["held_out_reason"],
        })
    return out


def _file_for_key(conn, key: str) -> dict:
    for r in _recordings(conn):
        if _stem(r["source_file"]) == key or r["source_file"] == key:
            return r
    raise HTTPException(404, {"message": f"no recording {key!r}"})


def _channel_map(conn, key: str) -> dict:
    """name -> recording row (with `name`), for one recording file."""
    rec = _file_for_key(conn, key)
    _refuse_held_out(rec["source_file"])
    out = {}
    for c in rec["channels"]:
        row = dict(q.get_recording_by_id(conn, c["id"]))
        row["name"] = c["name"]
        out[c["name"]] = row
    return out


def _ids_for(conn, key: str, names: list[str]) -> list[dict]:
    chans = _channel_map(conn, key)
    missing = [n for n in names if n not in chans]
    if missing:
        raise HTTPException(404, {"message": f"no channel(s) {missing} on {key}", "channels": sorted(chans)})
    return [chans[n] for n in names]


def _split(value: str | None) -> list[str]:
    return [p for p in (value or "").split(",") if p.strip()]


# ── the session row ─────────────────────────────────────────────────────────

def _session_row(conn):
    return conn.execute("SELECT * FROM discovery_sessions ORDER BY id DESC LIMIT 1").fetchone()


def _densest_section(conn, recording_ids, fs, n_samples, hours=DEFAULT_SECTION_H):
    """The `hours`-long section these channels have reviewed most of.

    A first session over a whole 721-hour recording is not a default, it is a
    trap: every read on the page would scan the lot, and a seeded search over
    it with 200 null draws is hours of work nobody asked for. The section that
    has been looked at most is also the only one where precision and recall
    have a denominator, so it is where the page is worth opening.
    """
    width = int(round(hours * 3600 * float(fs or 1.0)))
    if width <= 0 or width >= n_samples:
        return (0, int(n_samples))
    marks = ",".join(str(int(i)) for i in recording_ids) or "NULL"
    rows = conn.execute(
        f"SELECT start_idx, end_idx FROM reviewed_spans WHERE recording_id IN ({marks})").fetchall()
    if not rows:
        return (0, width)
    # one bucket per half-width, so a section boundary never splits the peak
    step = max(1, width // 2)
    buckets = {}
    for r in rows:
        a, b = int(r["start_idx"]), int(r["end_idx"])
        for k in range(a // step, (b - 1) // step + 1):
            lo, hi = k * step, (k + 1) * step
            buckets[k] = buckets.get(k, 0) + max(0, min(b, hi) - max(a, lo))
    best_k = max(range(min(buckets), max(buckets) + 1),
                 key=lambda k: buckets.get(k, 0) + buckets.get(k + 1, 0))
    start = min(max(0, best_k * step), max(0, n_samples - width))
    return (int(start), int(start + width))


def _default_session(conn):
    """The first session: the recording with the most reviewed coverage, its
    three most-reviewed channels, and the whole of it. A default built from the
    data rather than from a name, so it is right on any database."""
    recs = [r for r in _recordings(conn) if not r["held_out"]]
    if not recs:
        raise HTTPException(404, {"message": "no recording is registered; Discovery has nothing to scope"})
    best, best_cover = recs[0], -1
    cover_by_id = dict(conn.execute(
        "SELECT recording_id, SUM(end_idx - start_idx) FROM reviewed_spans GROUP BY recording_id").fetchall())
    for r in recs:
        cover = sum(int(cover_by_id.get(c["id"], 0) or 0) for c in r["channels"])
        if cover > best_cover:
            best, best_cover = r, cover
    channels = sorted(best["channels"], key=lambda c: -int(cover_by_id.get(c["id"], 0) or 0))[:3]
    channels.sort(key=lambda c: c["channel"])
    n_samples = best["n_samples"]
    span = _densest_section(conn, [c["id"] for c in channels], best["fs"], n_samples)
    null = seeded_search.null_from_settings(conn)
    row = {
        "name": f"{_stem(best['source_file'])} screen",
        "source_file": best["source_file"],
        "channels_json": json.dumps([c["name"] for c in channels]),
        "span_start": int(span[0]), "span_end": int(span[1]),
        "null_json": json.dumps({"method": null["method"], "n": null["draws"],
                                 "requested": null["requested"], "supported": null["supported"],
                                 "reason": null["reason"]}),
        "state_json": "{}", "created_at": _now(), "updated_at": _now(),
    }
    cur = conn.execute(
        "INSERT INTO discovery_sessions (name, source_file, channels_json, span_start, span_end, null_json, "
        "state_json, created_at, updated_at) VALUES (:name, :source_file, :channels_json, :span_start, "
        ":span_end, :null_json, :state_json, :created_at, :updated_at)", row)
    conn.commit()
    return conn.execute("SELECT * FROM discovery_sessions WHERE id = ?", (cur.lastrowid,)).fetchone()


def _session(conn):
    return _session_row(conn) or _default_session(conn)


def _session_scope(conn):
    """(session row, recording dict, [channel rows], (span_start, span_end))."""
    s = _session(conn)
    key = _stem(s["source_file"])
    names = json.loads(s["channels_json"])
    chans = _ids_for(conn, key, names)
    return s, _file_for_key(conn, key), chans, (int(s["span_start"]), int(s["span_end"]))


def _session_payload(conn):
    s = _session(conn)
    rec = _file_for_key(conn, _stem(s["source_file"]))
    fs = rec["fs"]
    null = json.loads(s["null_json"] or "{}")
    return {
        "session": {
            "id": int(s["id"]),
            "name": s["name"],
            "recording": _stem(s["source_file"]),
            "channels": json.loads(s["channels_json"]),
            "section": [int(s["span_start"]) / fs / 3600.0, int(s["span_end"]) / fs / 3600.0],
            "sectionSamples": [int(s["span_start"]), int(s["span_end"])],
            "null": null,
            "localLimitMin": fanout.ceiling_s(conn) / 60.0,
            "savedAt": (s["updated_at"] or "")[11:16],
            "matchingRule": rule_from_settings(conn),
        },
        "recordings": _recording_options(conn),
    }


class SessionBody(BaseModel):
    name: str | None = None
    recording: str | None = None
    channels: list[str] | None = None
    section: list[float] | None = None
    null: dict | None = None


@router.get("/api/discovery/session")
def get_session(request: Request):
    c = _conn(request)
    try:
        return _session_payload(c)
    finally:
        c.close()


@router.put("/api/discovery/session")
def put_session(request: Request, body: SessionBody):
    c = _conn(request)
    try:
        s = _session(c)
        key = body.recording or _stem(s["source_file"])
        rec = _file_for_key(c, key)
        _refuse_held_out(rec["source_file"])
        names = body.channels if body.channels is not None else json.loads(s["channels_json"])
        chans = _ids_for(c, key, names)
        fs = rec["fs"]
        if body.section is not None:
            a = int(round(float(body.section[0]) * 3600 * fs))
            b = int(round(float(body.section[1]) * 3600 * fs))
        else:
            a, b = int(s["span_start"]), int(s["span_end"])
        a = max(0, min(a, rec["n_samples"]))
        b = max(a + 1, min(b, rec["n_samples"]))
        null = json.loads(s["null_json"] or "{}")
        if body.null is not None:
            resolved = seeded_search.resolve_null(body.null.get("method"), body.null.get("n"))
            null = {"method": resolved["method"], "n": resolved["draws"], "requested": resolved["requested"],
                    "supported": resolved["supported"], "reason": resolved["reason"]}
        c.execute("UPDATE discovery_sessions SET name = ?, source_file = ?, channels_json = ?, span_start = ?, "
                  "span_end = ?, null_json = ?, updated_at = ? WHERE id = ?",
                  (body.name or s["name"], rec["source_file"], json.dumps([ch["name"] for ch in chans]),
                   a, b, json.dumps(null), _now(), int(s["id"])))
        c.commit()
        return _session_payload(c)
    finally:
        c.close()


# ── the runs list ───────────────────────────────────────────────────────────

def _discovery_runs(conn, session_id):
    return conn.execute("SELECT * FROM discovery_runs WHERE session_id = ? ORDER BY id",
                        (int(session_id),)).fetchall()


def _dr_by_key(conn, session_id, run_key):
    row = conn.execute("SELECT * FROM discovery_runs WHERE session_id = ? AND run_key = ?",
                       (int(session_id), run_key)).fetchone()
    if row is None:
        raise HTTPException(404, {"message": f"no Discovery run {run_key!r} in this session"})
    return row


def _run_ids(conn, dr_row):
    """The `runs` rows a Discovery run is made of.

    Recorded on the row itself, because `execute_recipe` is idempotent: a
    second Discovery run over the same recipe, recording and span is made of
    the runs the first one produced, and those keep the group they joined
    first. Falling back to the group covers rows written before this was
    recorded."""
    params = json.loads(dr_row["params_json"] or "{}")
    ids = params.get("run_ids")
    if ids:
        return [int(i) for i in ids]
    if dr_row["run_group_id"]:
        return [int(r["id"]) for r in R.list_run_group_runs(conn, int(dr_row["run_group_id"]))
                if r["surrogate_of_run_id"] is None]
    return []


def _reviewed_h(conn, chans, span):
    total = 0
    for ch in chans:
        rows = conn.execute("SELECT start_idx, end_idx FROM reviewed_spans WHERE recording_id = ?",
                            (int(ch["id"]),)).fetchall()
        total += total_length(merged(clip([(r["start_idx"], r["end_idx"]) for r in rows], span[0], span[1])))
    fs = float(chans[0]["fs"]) if chans else 1.0
    return total / fs / 3600.0


def _human_run(conn, chans, span):
    h = _reviewed_h(conn, chans, span)
    return {"key": "human", "label": "human annotations", "kind": "reference", "colour": HUMAN_COLOUR,
            "glyph": "human", "detail": f"{h:.0f} h reviewed" if h >= 1 else f"{h * 60:.0f} min reviewed",
            "status": "reference", "reviewedH": round(h, 3)}


def _run_payload(conn, row, index, span):
    params = json.loads(row["params_json"] or "{}")
    group_id = row["run_group_id"]
    ids = _run_ids(conn, row)
    status, progress, done_at, error, n_found = row["status"], None, None, None, None
    channels_done = None
    if ids:
        st = fanout.group_status(conn, run_ids=ids)
        channels_done = f"{st['done']} / {st['total']}"
        progress = st["progress"]
        n_found = sum(c["detections"] for c in st["channels"])
        if row["superseded_at"]:
            status = "superseded"
        elif st["status"] == "completed":
            status = "done"
            done_at = max((c.get("finished_at") or "") for c in st["channels"]) or None
        elif st["status"] in ("running", "queued"):
            status = "running"
        elif st["status"] == "failed":
            status = "failed"
            error = next((c["error"] for c in st["channels"] if c["error"]), None)
        elif st["status"] == "superseded":
            status = "superseded"
    elif row["superseded_at"]:
        status = "superseded"
    out = {
        "key": row["run_key"],
        "id": f"g-{group_id}" if group_id else None,
        "label": row["label"],
        "kind": row["kind"] if row["kind"] in ("template", "seed", "draft") else "template",
        "colour": row["colour"] or RUN_COLOURS[index % len(RUN_COLOURS)],
        "glyph": params.get("glyph") or "threshold",
        "detail": params.get("detail") or "",
        "status": status,
        "template": row["template_name"],
        "stageCount": params.get("stage_count"),
        "version": params.get("version"),
        "perChannelMin": params.get("per_channel_min"),
        "job": f"j-{row['job_id']}" if row["job_id"] else None,
        "runGroupId": group_id,
        "channelsDone": channels_done,
        "found": n_found,
    }
    if progress is not None and status == "running":
        out["progress"] = round(progress, 3)
    if done_at:
        out["doneAt"] = done_at[11:16]
    if error:
        out["error"] = error
    return out


@router.get("/api/discovery/runs")
def get_runs(request: Request):
    c = _conn(request)
    try:
        s, rec, chans, span = _session_scope(c)
        rows = _discovery_runs(c, s["id"])
        return [_human_run(c, chans, span)] + [_run_payload(c, r, i, span) for i, r in enumerate(rows)]
    finally:
        c.close()


# ── templates ───────────────────────────────────────────────────────────────

def _signature(steps):
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    kinds = []
    for st in steps:
        spec = get_adapter(f"{st['stage']}.{st['algorithm']}")
        if not kinds:
            kinds.append(spec.input_kind)
        kinds.append(spec.output_kind)
    label = {"signal": "Signal", "scores": "Scores", "spanset": "SpanSet", "encoding": "Encoding",
             "windowset": "WindowSet", "grouping": "Grouping", "model": "Model"}
    seen = [label.get(k, k) for k in kinds]
    dedup = [s for i, s in enumerate(seen) if i == 0 or s != seen[i - 1]]
    return " → ".join(dedup), (kinds[-1] if kinds else None)


def _template_payload(conn, row, in_session: set, rank: int):
    steps = row["steps"]
    signature, terminal = _signature(steps)
    is_seed = any(st["algorithm"] == "seed_matches" for st in steps)
    stages = [{"index": "●", "name": "Source", "signature": "— → Signal", "glyph": "source"}]
    for i, st in enumerate(steps):
        cell = _step_cell(st, i)
        stages.append({"index": f"{i + 1:02d}", "name": cell["name"], "signature": cell["signature"],
                       "locked": cell["param"], "glyph": cell["glyph"]})
    score = _last_score(conn, row["name"])
    return {
        "name": row["name"], "kind": "seed" if is_seed else "template", "signature": signature,
        "fits": terminal == "spanset",
        "fitsReason": None if terminal == "spanset" else f"terminal type is {terminal}, not SpanSet",
        "lastScore": score, "savedAt": (row.get("created_at") or "")[:10], "lastUsed": rank,
        "stages": stages, "perChannelMin": None, "complexity": _complexity(steps), "diskGB": None,
        "preview": None,
        "previewNote": "not previewed — run Preview on a sample to get a measured number",
        "bind": ("rebind" if is_seed else None),
        "inSession": (f"already in this session" if row["name"] in in_session else None),
        "hasModel": any(st["algorithm"] in ("cnn_score", "classifier") for st in steps),
        "version": row.get("version"), "builtin": bool(row.get("builtin")),
        "description": row.get("description"),
    }


def _step_cell(step, index):
    """One stage of a template, as the picker's glyph strip draws it. The
    parameter line is the template's own locked values (§7.5: "a template's
    parameters come from the template; *Open in Analyse* to change them")."""
    from Adapters.registry import discover_adapters, get_adapter
    discover_adapters()
    name = f"{step['stage']}.{step['algorithm']}"
    spec = get_adapter(name)
    label = {"signal": "Signal", "scores": "Scores", "spanset": "SpanSet", "encoding": "Encoding",
             "windowset": "WindowSet", "grouping": "Grouping", "model": "Model"}
    return {
        "index": f"{index + 1:02d}",
        "name": spec.page_name or spec.display_name,
        "algorithm": name,
        "signature": f"{label.get(spec.input_kind, spec.input_kind)} → {label.get(spec.output_kind, spec.output_kind)}",
        "param": _param_line(spec, step.get("params") or {}),
        "glyph": D.glyph_for(name),
    }


def _complexity(steps):
    names = [f"{s['stage']}.{s['algorithm']}" for s in steps]
    heavy = [n for n in names if n in ("detection.matrix_profile", "preprocessing.window_matrix",
                                       "catalogue.window_images", "catalogue.cnn_score",
                                       # 3 KB of live memory per span sample, all of it
                                       # re-serialised by the step cache (fixup-a item 2)
                                       "preprocessing.wavelet_transform")]
    return f"{len(steps)} stages" + (f" · {len(heavy)} heavy" if heavy else "")


def _last_score(conn, template_name):
    """§4.8: a score aggregates onto a template **only with scope attached**.
    Never a bare number on a template card."""
    row = conn.execute(
        "SELECT * FROM discovery_runs WHERE template_name = ? AND run_group_id IS NOT NULL "
        "ORDER BY id DESC LIMIT 1", (template_name,)).fetchone()
    ids = _run_ids(conn, row) if row is not None else []
    if not ids:
        return "not yet scored"
    total = SB.score_runs(conn, ids)["total"]
    if total["precision"] is None:
        return total.get("recall_note") or "not yet scored"
    return (f"precision {total['precision'] * 100:.0f} % over {total['reviewed']} reviewed detections "
            f"· {total['n_channels']} ch · {total['reviewed_h']:.1f} h")


@router.get("/api/discovery/templates")
def get_templates(request: Request):
    from . import templates as T
    c = _conn(request)
    try:
        s = _session(c)
        in_session = {r["template_name"] for r in _discovery_runs(c, s["id"]) if r["template_name"]}
        rows = T.list_all(c)
        out = []
        for i, row in enumerate(rows):
            if row.get("kind") not in (None, "detection"):
                continue
            out.append(_template_payload(c, row, in_session, i))
        return out
    finally:
        c.close()


@router.get("/api/discovery/history")
def get_history(request: Request):
    """Past Discovery runs, this session and earlier ones — the History popover."""
    c = _conn(request)
    try:
        s = _session(c)
        rows = c.execute("SELECT * FROM discovery_runs ORDER BY id DESC LIMIT 40").fetchall()
        out = []
        for r in rows:
            ids = _run_ids(c, r)
            st = fanout.group_status(c, run_ids=ids) if ids else None
            n = sum(x["detections"] for x in st["channels"]) if st else 0
            out.append({
                "id": f"g-{r['run_group_id']}" if r["run_group_id"] else f"d-{r['id']}",
                "label": r["label"],
                "when": (r["updated_at"] or r["created_at"] or "")[:16].replace("T", " "),
                "status": "superseded" if r["superseded_at"] else (st["status"] if st else r["status"]),
                "runKey": r["run_key"],
                "inSession": int(r["session_id"]) == int(s["id"]),
                "detail": f"{n} detections · {st['total']} ch" if st else r["kind"],
            })
        return out
    finally:
        c.close()


# ── the scope strips ────────────────────────────────────────────────────────

@router.get("/api/discovery/overview")
def get_overview(request: Request, recording: str, channels: str = ""):
    """One value per hour for each channel's overview strip — a block mean over
    the real samples, not an envelope, because the strip is a shape at 700-hour
    scale and a min/max pair per hour would draw a band, not a trace."""
    c = _conn(request)
    try:
        rec = _file_for_key(c, recording)
        # 423, like every other route that would serve this file's samples. It
        # used to answer 200 with a {"refused": ...} body, which reads as a
        # successful request to anything that is not this page's own callout.
        _refuse_held_out(rec["source_file"])
        names = _split(channels) or [ch["name"] for ch in rec["channels"][:3]]
        rows = _ids_for(c, recording, names)
        out = {}
        unit = corpus.display_unit(rows[0]) if rows else None
        for ch in rows:
            x = corpus.display_channel(ch)
            fs = float(ch["fs"])
            per = max(1, int(round(fs * 3600)))
            n_full = len(x) // per
            if n_full == 0:
                out[ch["name"]] = [float(np.nanmean(np.asarray(x, dtype=float)))] if len(x) else []
                continue
            block = np.asarray(x[:n_full * per], dtype=float).reshape(n_full, per)
            with np.errstate(invalid="ignore"):
                vals = np.nanmean(block, axis=1)
            if n_full > OVERVIEW_MAX_POINTS:
                idx = np.linspace(0, n_full - 1, OVERVIEW_MAX_POINTS).round().astype(int)
                vals = vals[idx]
            out[ch["name"]] = [None if not np.isfinite(v) else round(float(v), 5) for v in vals]
        return {"data": out, "unit": unit}
    finally:
        c.close()


def _run_detections(conn, run_ids, recording_id, span):
    """Every detection of one channel of one Discovery run, channel-absolute
    and clipped to the section."""
    if not run_ids:
        return []
    marks = ",".join(str(int(i)) for i in run_ids)
    rows = conn.execute(
        "SELECT d.id, d.start_idx, d.end_idx, d.score, r.span_start, r.id AS run_id FROM detections d "
        "JOIN runs r ON r.id = d.run_id WHERE r.id IN (" + marks + ") AND r.recording_id = ? "
        "AND r.surrogate_of_run_id IS NULL ORDER BY d.start_idx",
        (int(recording_id),)).fetchall()
    out = []
    for r in rows:
        a, b = absolute_bounds(r["start_idx"], r["end_idx"], r["span_start"])
        if span and not (span[0] <= a < span[1]):
            continue
        out.append({"id": int(r["id"]), "start": a, "end": b, "run_id": int(r["run_id"]),
                    "score": (float(r["score"]) if r["score"] is not None else None)})
    return out


def _human_spans(conn, recording_id, span, verdicts=("interesting", "seed")):
    rows = conn.execute(
        "SELECT id, start_idx, end_idx, verdict FROM annotations WHERE recording_id = ? ORDER BY start_idx",
        (int(recording_id),)).fetchall()
    out = []
    for r in rows:
        if verdicts and r["verdict"] not in verdicts:
            continue
        a, b = int(r["start_idx"]), int(r["end_idx"])
        if span and not (span[0] <= a < span[1]):
            continue
        out.append({"id": int(r["id"]), "start": a, "end": b, "score": None, "verdict": r["verdict"]})
    return out


def _spans_for(conn, session_id, run_key, ch, span):
    if run_key == "human":
        return _human_spans(conn, ch["id"], span)
    row = _dr_by_key(conn, session_id, run_key)
    return _run_detections(conn, _run_ids(conn, row), int(ch["id"]), span)


@router.get("/api/discovery/fires")
def get_fires(request: Request, channels: str = "", t0: float = 0.0, t1: float = 0.0, runs: str = ""):
    """§7.2 — detection density per 3 h bin, by channel then by run, with the
    reviewed hours as the human row's underlay."""
    c = _conn(request)
    try:
        s, rec, _, _ = _session_scope(c)
        fs = rec["fs"]
        names = _split(channels) or json.loads(s["channels_json"])
        chans = _ids_for(c, _stem(s["source_file"]), names)
        keys = _split(runs) or ["human"]
        bin_h = FIRES_BIN_H
        first_bin = int(np.floor(t0 / bin_h))
        n_bins = max(1, int(np.ceil(t1 / bin_h)) - first_bin)
        span = (int(round(t0 * 3600 * fs)), int(round(t1 * 3600 * fs)))
        edges = np.array([(first_bin + i) * bin_h * 3600 * fs for i in range(n_bins + 1)])

        out_channels = []
        for ch in chans:
            rev = c.execute(
                "SELECT start_idx, end_idx FROM reviewed_spans WHERE recording_id = ?", (int(ch["id"]),)).fetchall()
            cov = merged(clip([(r["start_idx"], r["end_idx"]) for r in rev], span[0], span[1]))
            reviewed_bins = []
            for i in range(n_bins):
                lo, hi = edges[i], edges[i + 1]
                reviewed_bins.append(round(total_length(clip(cov, lo, hi)) / fs / 3600.0, 3))
            rows = []
            for key in keys:
                spans = _spans_for(c, s["id"], key, ch, span)
                starts = np.array([sp["start"] for sp in spans], dtype=float)
                counts = np.histogram(starts, bins=edges)[0].tolist() if len(starts) else [0] * n_bins
                row = {"run": key, "counts": [int(v) for v in counts]}
                if key != "human":
                    dr = _dr_by_key(c, s["id"], key)
                    ids = _run_ids(c, dr)
                    if ids:
                        st = fanout.group_status(c, run_ids=ids)
                        if st["status"] in ("running", "queued"):
                            row["unfinishedFrom"] = int(n_bins * st["progress"])
                rows.append(row)
            out_channels.append({
                "channel": ch["name"],
                "reviewedH": round(total_length(cov) / fs / 3600.0, 3),
                "reviewed": reviewed_bins, "rows": rows,
            })
        return {"binH": bin_h, "firstBin": first_bin, "nBins": n_bins, "channels": out_channels}
    finally:
        c.close()


# ── the scoreboard ──────────────────────────────────────────────────────────

def _recall_cell(row):
    """§7.3's three-branch recall: a value with the hours it was computed over,
    or the words for having none. The client branches on key presence.

    A channel row states its own reviewed hours; a total row states the hours
    it POOLED, which is a different number — a channel with no reviewed overlap
    contributes its counts but not its hours (§7.3: "the run total states the
    hours it pooled")."""
    over = row.get("recall_over_h", row.get("pooled_h"))
    if row["recall"] is not None:
        return {"value": round(row["recall"], 3), "overH": round(float(over or 0.0), 3)}
    return {"none": True, "note": row.get("recall_note")}


def _score_row(row):
    return {
        "found": row["found"], "judged": row["already_judged"], "reviewed": row["reviewed"],
        "interesting": row["interesting"],
        # §7.3's "null expects" is a count, and 0 is a real one: a surrogate run
        # that found nothing is the best × null there is, not a missing figure.
        # `nullRun` separates it from "no null was run at all".
        "nullExpects": (row["null_expects"] if row["null_expects"] is not None else 0),
        "nullRun": row["null_expects"] is not None,
        "nullDraws": row.get("null_draws"),
        "xNullNote": (row.get("x_null_scope") or
                      (None if row["x_null"] is not None else
                       ("no paired null run on this scope" if row["null_expects"] is None
                        else "the null found nothing here"))),
        "recall": _recall_cell(row),
        "precision": (round(row["precision"], 4) if row["precision"] is not None else None),
        "xNull": (round(row["x_null"], 2) if row["x_null"] is not None else None),
        "note": row.get("note"), "precisionNote": row.get("precision_note"),
        "reviewedH": round(float(row.get("reviewed_h") or 0.0), 3), "status": row.get("status"),
    }


@router.get("/api/discovery/scoreboard")
def get_scoreboard(request: Request, runs: str = "", channels: str = "", t0: float = 0.0, t1: float = 0.0):
    c = _conn(request)
    try:
        s, rec, _, _ = _session_scope(c)
        fs = rec["fs"]
        names = _split(channels) or json.loads(s["channels_json"])
        chans = _ids_for(c, _stem(s["source_file"]), names)
        span = (int(round(t0 * 3600 * fs)), int(round(t1 * 3600 * fs)))
        rule = rule_from_settings(c)
        out = []
        for key in _split(runs):
            if key == "human":
                continue
            dr = _dr_by_key(c, s["id"], key)
            ids = _run_ids(c, dr)
            if not ids:
                continue
            scored = SB.score_runs(c, ids, rule=rule, span=span)
            wanted = {ch["id"] for ch in chans}
            rows = [r for r in scored["channels"] if r["recording_id"] in wanted]
            total = SB.run_total(c, [r["run_id"] for r in rows], rule=rule, rows=rows)
            out.append({
                "run": key,
                "total": _score_row(total) | {"recall": _recall_cell(total),
                                             "precisionNote": total.get("precision_note")},
                "channels": [_score_row(r) | {"channel": next(ch["name"] for ch in chans
                                                              if ch["id"] == r["recording_id"])} for r in rows],
                "pooledH": round(total["pooled_h"], 3),
                "rule": total["rule"],
                "reviewedCriterion": SB.REVIEWED_CRITERION,
            })
        return out
    finally:
        c.close()


# ── browsing detections ─────────────────────────────────────────────────────

def _depth_mv(ch, a, b):
    x = corpus.display_channel(ch)
    if x.unit is None:
        return None             # no unit behind it: not printed as mV
    seg = np.asarray(x[max(0, a):min(len(x), b)], dtype=float)
    if not seg.size or not np.isfinite(seg).any():
        return None
    return round(float(np.nanmax(seg) - np.nanmin(seg)), 4)


@router.get("/api/discovery/detections")
def get_detections(request: Request, run: str, channel: str, t0: float = 0.0, t1: float = 0.0):
    c = _conn(request)
    try:
        s, rec, _, _ = _session_scope(c)
        fs = rec["fs"]
        ch = _ids_for(c, _stem(s["source_file"]), [channel])[0]
        span = (int(round(t0 * 3600 * fs)), int(round(t1 * 3600 * fs)))
        spans = _spans_for(c, s["id"], run, ch, span)
        rule = rule_from_settings(c)
        others = {}
        for other in _discovery_runs(c, s["id"]):
            if other["run_key"] == run or not other["run_group_id"]:
                continue
            others[other["run_key"]] = _run_detections(c, _run_ids(c, other), int(ch["id"]), span)
        humans = _human_spans(c, ch["id"], span, verdicts=None)
        mine = [(sp["start"], sp["end"]) for sp in spans]
        also = {i: [] for i in range(len(mine))}
        for key, rows in others.items():
            pairing = match_span_sets(mine, [(r["start"], r["end"]) for r in rows], rule=rule)
            for p in pairing["pairs"]:
                also[p["candidate"]].append(key)
        verdicts = match_span_sets(mine, [(h["start"], h["end"]) for h in humans], rule=rule)
        verdict_of = {p["candidate"]: humans[p["reference"]]["verdict"] for p in verdicts["pairs"]}
        out = []
        for i, sp in enumerate(spans):
            out.append({
                "id": f"d-{sp['id']}", "detectionId": sp["id"], "index": i + 1, "of": len(spans),
                "run": run, "channel": ch["name"],
                "atH": round(sp["start"] / fs / 3600.0, 4),
                "durationS": round((sp["end"] - sp["start"]) / fs, 2),
                "depthMv": _depth_mv(ch, sp["start"], sp["end"]),
                "score": (round(sp["score"], 4) if sp["score"] is not None else None),
                "priorVerdict": verdict_of.get(i),
                "alsoFoundBy": also[i],
            })
        return out
    finally:
        c.close()


@router.get("/api/discovery/detections/{detection_id}/window")
def get_detection_window(request: Request, detection_id: int, pad_s: float = 120.0, px: int = 900):
    c = _conn(request)
    try:
        row = c.execute("SELECT d.start_idx, d.end_idx, r.span_start, r.recording_id FROM detections d "
                        "JOIN runs r ON r.id = d.run_id WHERE d.id = ?", (int(detection_id),)).fetchone()
        if row is None:
            raise HTTPException(404, {"message": f"no detection {detection_id}"})
        rec = corpus.recording_row(c, int(row["recording_id"]))
        _refuse_held_out(rec["source_file"])
        a, b = absolute_bounds(row["start_idx"], row["end_idx"], row["span_start"])
        fs = float(rec["fs"])
        pad = int(round(pad_s * fs))
        lo, hi = max(0, a - pad), min(int(rec["n_samples"]), b + pad)
        x = corpus.display_channel(rec)
        seg = np.asarray(x[lo:hi], dtype=float)
        if len(seg) > px:
            idx = np.linspace(0, len(seg) - 1, px).round().astype(int)
            seg = seg[idx]
            step = (hi - lo) / len(seg) / fs
        else:
            step = 1.0 / fs
        return {"t0H": lo / fs / 3600.0, "stepS": step,
                "values": [None if not np.isfinite(v) else round(float(v), 5) for v in seg],
                "spanS": [(a - lo) / fs, (b - lo) / fs], "unit": x.unit}
    finally:
        c.close()


@router.get("/api/discovery/signal")
def get_signal(request: Request, channel: str, t0: float = 0.0, t1: float = 0.0, px: int = 1200):
    c = _conn(request)
    try:
        s, rec, _, _ = _session_scope(c)
        ch = _ids_for(c, _stem(s["source_file"]), [channel])[0]
        fs = float(ch["fs"])
        x = corpus.display_channel(ch)
        lo = max(0, int(round(t0 * 3600 * fs)))
        hi = min(len(x), max(lo + 1, int(round(t1 * 3600 * fs))))
        seg = np.asarray(x[lo:hi], dtype=float)
        n = min(px, len(seg)) or 1
        idx = np.linspace(0, len(seg) - 1, n).round().astype(int) if len(seg) else np.array([], dtype=int)
        vals = seg[idx] if len(seg) else seg
        step = ((hi - lo) / max(1, n)) / fs
        return {"t0H": lo / fs / 3600.0, "stepS": step,
                "values": [None if not np.isfinite(v) else round(float(v), 5) for v in vals], "unit": x.unit}
    finally:
        c.close()


def _param_line(spec, params):
    """A template's locked parameters as one readable line (§7.5). Built from
    the step's own values against the adapter's ParamSpecs, so a block that
    grows a parameter says so here without this module being edited."""
    bits = []
    for p in getattr(spec, "params", []) or []:
        if p.name not in (params or {}):
            continue
        v = params[p.name]
        if isinstance(v, float):
            v = f"{v:g}"
        bits.append(f"{p.name.replace('_', ' ')} {v}")
    return " · ".join(bits[:3]) or "defaults"


# ── the seeds (§7.6: Library exemplar · Explore selection · Family medoid) ──

def _seed_store():
    """The drop-motif seed store, read through the core's own reader. The
    Library's `motif_entry` table is the first source; until Prompt 03 fills
    it, these 410 extracted events are what a "library exemplar" means here,
    and every payload says which source it came from."""
    from Working.Detection.drop_motifs import store as S
    if not os.path.isdir(SEED_DIR):
        return []
    try:
        return S.load_events(SEED_DIR)
    except Exception:
        return []


def _trace(conn, rec_row, a, b, n=TRACE_POINTS):
    x = corpus.display_channel(dict(rec_row))
    seg = np.asarray(x[max(0, a):min(len(x), b)], dtype=float)
    if not seg.size:
        return []
    idx = np.linspace(0, len(seg) - 1, min(n, len(seg))).round().astype(int)
    return [None if not np.isfinite(v) else round(float(v), 5) for v in seg[idx]]


def _seed_id(source, recording_id, a, b):
    return f"{source}:{recording_id}:{a}:{b}"


def _seed_by_id(conn, seed_id: str):
    try:
        source, rid, a, b = seed_id.split(":")
        rec = q.get_recording_by_id(conn, int(rid))
    except Exception:
        raise HTTPException(400, {"message": f"unreadable seed id {seed_id!r}; expected source:recording:start:end"})
    if rec is None:
        raise HTTPException(404, {"message": f"no recording {rid} for seed {seed_id!r}"})
    _refuse_held_out(rec["source_file"])
    seed = seeded_search.seed_from_content(conn, rec["source_file"], int(rec["channel"]), int(a), int(b),
                                           role=source)
    seed["id"] = seed_id
    seed["source"] = source
    return seed


def _seed_info(conn, seed, *, title=None, family=None, family_line=None):
    rec = q.get_recording_by_id(conn, seed["recording_id"])
    return {
        "id": seed["id"],
        "role": {"library": "Library exemplar", "explore": "Explore selection",
                 "medoid": "Family medoid"}.get(seed["source"], seed["source"]),
        "source": seed["source"],
        "title": title or f"{_stem(rec['source_file'])} · {seed['start_h']:.1f} h",
        "family": family, "familyLine": family_line,
        "recording": _stem(rec["source_file"]),
        "channel": corpus.channel_name(rec["source_file"], int(rec["channel"]),
                                       len(q.list_recordings(conn, rec["source_file"]))),
        "startH": round(seed["start_h"], 4), "samples": seed["samples"],
        "lengthS": round(seed["length_s"], 2), "hash": seed["hash"],
        "trace": _trace(conn, rec, seed["start_idx"], seed["end_idx"]),
        "unit": corpus.display_unit(dict(rec)),
    }


def _seed_candidates(conn):
    """The three sources §7.6 names, from what actually exists on this machine."""
    out = []
    entries = conn.execute("SELECT * FROM motif_entry ORDER BY id LIMIT ?", (SEED_LIMIT,)).fetchall()
    for e in entries:
        rec = q.get_recording_by_id(conn, int(e["recording_id"]))
        if rec is None or rec["source_file"] == HELD_OUT_FILE:
            continue
        out.append(("library", int(e["recording_id"]), int(e["start_idx"]), int(e["end_idx"]),
                    f"entry {e['id']}", f"E-{e['id']:04d}", None))
    events = _seed_store()
    if not entries and events:
        pure = [e for e in events if int(e.get("is_pure", 1) or 0)]
        pure.sort(key=lambda e: -float(e["drop_depth_mv"]))
        for e in pure[:SEED_LIMIT]:
            out.append(("library", int(e["recording_id"]), int(e["snippet_start_idx"]), int(e["snippet_end_idx"]),
                        f"{e['event_id']} · {float(e['drop_depth_mv']):.1f} mV",
                        e.get("span_key"), e.get("span_label")))
    by_family = {}
    for e in events:
        by_family.setdefault(e.get("span_key") or f"r{e['recording_id']}", []).append(e)
    for key, members in sorted(by_family.items()):
        depths = sorted(float(m["drop_depth_mv"]) for m in members)
        median = depths[len(depths) // 2]
        medoid = min(members, key=lambda m: abs(float(m["drop_depth_mv"]) - median))
        out.append(("medoid", int(medoid["recording_id"]), int(medoid["snippet_start_idx"]),
                    int(medoid["snippet_end_idx"]), f"{key} medoid · {len(members)} members",
                    key, f"{len(members)} members · {medoid.get('morphology')}"))
    seeds = conn.execute(
        "SELECT id, recording_id, start_idx, end_idx FROM annotations WHERE verdict = 'seed' "
        "ORDER BY id DESC LIMIT ?", (SEED_LIMIT,)).fetchall()
    for a in seeds:
        out.append(("explore", int(a["recording_id"]), int(a["start_idx"]), int(a["end_idx"]),
                    f"span {a['id']}", None, "taken for Review in Explore"))
    return out


def _seeds_inline(conn):
    out = []
    for source, rid, a, b, title, family, family_line in _seed_candidates(conn):
        rec = q.get_recording_by_id(conn, rid)
        if rec is None or rec["source_file"] == HELD_OUT_FILE:
            continue
        try:
            seed = seeded_search.seed_from_content(conn, rec["source_file"], int(rec["channel"]), a, b, role=source)
        except (ValueError, PermissionError):
            continue
        seed["id"] = _seed_id(source, rid, a, b)
        seed["source"] = source
        out.append(_seed_info(conn, seed, title=title, family=family, family_line=family_line))
    return out


@router.get("/api/discovery/seeds")
def get_seeds(request: Request):
    c = _conn(request)
    try:
        seeds = _seeds_inline(c)
        counts = {}
        for s in seeds:
            counts[s["source"]] = counts.get(s["source"], 0) + 1
        note = None
        if not c.execute("SELECT COUNT(*) FROM motif_entry").fetchone()[0]:
            note = ("the motif library is empty, so a Library exemplar here is a span of the drop-motif seed "
                    "store (DATA/library_seed/drop_motifs5/motifs, 410 extracted events)")
        return {"seeds": seeds, "counts": counts, "note": note}
    finally:
        c.close()


def _draft(conn, session, seed_id=None):
    state = json.loads(session["state_json"] or "{}")
    draft = dict(state.get("seed_draft") or {})
    if seed_id:
        draft["seedId"] = seed_id
    if not draft.get("seedId"):
        first = next(iter(_seed_candidates(conn)), None)
        if first is None:
            return None
        draft["seedId"] = _seed_id(first[0], first[1], first[2], first[3])
    seed = _seed_by_id(conn, draft["seedId"])
    recommended = seeded_search.recommended_params(seed)
    params = dict(draft.get("params") or recommended)
    # §7.6: the window is at the exemplar's native length and is LOCKED, so a
    # stale draft cannot carry a window from a different seed.
    params["windowSamples"] = recommended["windowSamples"]
    params["windowS"] = recommended["windowS"]
    # the exclusion zone is not settable through this block, so the draft cannot
    # carry a different one: what the card shows is what stumpy.match applied
    params["exclusionS"] = recommended["exclusionS"]
    params["exclusionSamples"] = recommended["exclusionSamples"]
    params["specExclusionS"] = recommended["specExclusionS"]
    params["exclusionSettable"] = recommended["exclusionSettable"]
    params["algorithm"] = recommended["algorithm"]
    return {
        "key": draft.get("key") or f"seed_{seed['hash'][:6]}",
        "label": draft.get("label") or f"seed {seed['hash'][:6]}",
        "seedId": draft["seedId"], "source": seed["source"],
        "bind": draft.get("bind") or "carry",
        "params": params, "applied": draft.get("applied"),
        "estimateS": draft.get("estimateS"),
        "recommended": recommended, "seed": _seed_info(conn, seed),
    }


@router.get("/api/discovery/seed/setup")
def get_seed_setup(request: Request, seed: str | None = None):
    c = _conn(request)
    try:
        s = _session(c)
        draft = _draft(c, s, seed)
        if draft is None:
            raise HTTPException(404, {"message": (
                "no seed is available: the motif library is empty and the drop-motif seed store is not on "
                "disk, so there is nothing to search for")})
        return {"draft": draft, "recommended": draft["recommended"], "seeds": _seeds_inline(c)}
    finally:
        c.close()


class SeedDraftBody(BaseModel):
    seedId: str | None = None
    label: str | None = None
    bind: str | None = None
    params: dict | None = None


@router.put("/api/discovery/seed/draft")
def put_seed_draft(request: Request, body: SeedDraftBody):
    c = _conn(request)
    try:
        s = _session(c)
        state = json.loads(s["state_json"] or "{}")
        draft = dict(state.get("seed_draft") or {})
        for key in ("seedId", "label", "bind"):
            v = getattr(body, key)
            if v is not None:
                draft[key] = v
        if body.params is not None:
            draft["params"] = body.params
        state["seed_draft"] = draft
        c.execute("UPDATE discovery_sessions SET state_json = ?, updated_at = ? WHERE id = ?",
                  (json.dumps(state), _now(), int(s["id"])))
        c.commit()
        return {"draft": _draft(c, _session(c))}
    finally:
        c.close()


# ── the seeded search itself ────────────────────────────────────────────────

class SeedBody(BaseModel):
    seedId: str
    channels: list[str] = Field(default_factory=list)
    t0: float = 0.0
    t1: float = 0.0
    k: int = 200
    maxDistance: float = 0.0
    label: str | None = None
    cut: float | None = None


def _seed_key(seed_id, channels, t0, t1, k, max_distance, null, source_file="", rule=None) -> str:
    """Everything the result depends on.

    The recording matters: four registered files share the channel names
    CH1..CH5, so a search on one and a later search on another produced
    byte-identical keys and the second was served the first's matches. The
    matching rule matters too — the `judged` flags on every candidate were
    computed under it."""
    r = rule or {}
    return "|".join([source_file, seed_id, ",".join(channels), f"{t0:.6f}", f"{t1:.6f}", str(k),
                     f"{max_distance:g}", str(null.get("method")), str(null.get("n")),
                     f"{r.get('iou')}:{r.get('onset')}"])


def _seed_search(conn, seed, chans, span, *, k, max_distance, null, job=None):
    """Candidates and the null, per channel.

    The candidates are the block's own `match_exemplar`; the null is N
    surrogate draws of the same channel put through the same function, so the
    two distributions are comparable by construction rather than by assertion.
    """
    exemplar = np.asarray(seeded_search.exemplar_signal(conn, seed).x, dtype=float)
    per_channel, pooled_null, candidates, capped = [], [], [], []
    n = len(chans)
    rule = rule_from_settings(conn)
    for i, ch in enumerate(chans):
        if job is not None:
            job.progress(i, n, f"{ch['name']} · matching")
        # the core matches stored samples against a stored-unit exemplar
        x = np.asarray(corpus.load_native(ch["npy_path"])[span[0]:span[1]], dtype=float)
        fs = float(ch["fs"])
        found = seeded_search.candidates(x, exemplar, k=k,
                                         max_distance=(max_distance if max_distance > 0 else None))
        first = len(candidates)
        for c_ in found:
            candidates.append({
                "id": f"{ch['name']}:{span[0] + c_['index']}",
                "d": round(c_["distance"], 4), "channel": ch["name"],
                "atH": round((span[0] + c_["index"]) / fs / 3600.0, 5),
                "index": span[0] + c_["index"], "judged": False, "verdict": None, "trace": [],
            })
        # §4.7: a rediscovery is a new row pointing at the prior verdict, never
        # a second question to the researcher — so say which matches are judged
        humans = _human_spans(conn, ch["id"], span, verdicts=None)
        mine = [(c_["index"], c_["index"] + seed["samples"]) for c_ in candidates[first:]]
        pairing = match_span_sets(mine, [(h["start"], h["end"]) for h in humans], rule=rule)
        for p in pairing["pairs"]:
            candidates[first + p["candidate"]]["judged"] = True
            candidates[first + p["candidate"]]["verdict"] = humans[p["reference"]]["verdict"]

        draws = 0
        if null.get("supported", True) and null.get("method") and int(null.get("n") or 0) > 0:
            want = int(null["n"])
            afford = max(NULL_MIN_DRAWS, NULL_SAMPLE_BUDGET // max(1, len(x)))
            asked = min(want, afford)
            if asked < want:
                capped.append(f"{ch['name']}: {want} draws asked, {asked} drawn "
                              f"({len(x):,} samples x {want} is over the budget)")
            if job is not None:
                job.progress(i, n, f"{ch['name']} · null, {asked} draws")
            nulls = seeded_search.null_distances(
                x, exemplar, draws=asked, seed=0, method=null["method"], k=k,
                max_distance=(max_distance if max_distance > 0 else None), fs=fs,
                on_progress=((lambda d, t, ch=ch, i=i: job.progress(i, n, f"{ch['name']} · null {d}/{t}"))
                             if job is not None else None),
                should_cancel=(job.cancel_event.is_set if job is not None else None))
            pooled_null.extend(nulls["distances"])
            draws = nulls["draws"]
        per_channel.append({"channel": ch["name"], "n": len(found), "nullDraws": draws})

    candidates.sort(key=lambda c_: (c_["d"], c_["index"]))
    # `draws` is the count PER CHANNEL, because `kept` is one realisation over
    # every channel: dividing a pooled hit count by the pooled draw-channels
    # would understate the null by the channel count, and dividing by nothing
    # overstates it by the draw count. `drawChannels` keeps the pooled figure
    # for anyone who needs the size of the sample.
    per_channel_draws = max((p["nullDraws"] for p in per_channel), default=0)
    null_obj = {
        "distances": [round(float(d), 4) for d in pooled_null],
        "draws": per_channel_draws,
        "drawChannels": sum(p["nullDraws"] for p in per_channel),
        "channels": len(per_channel),
        "method": null.get("method"), "supported": bool(null.get("supported", True)),
        "reason": null.get("reason"), "requested": null.get("requested"),
        "asked": int(null.get("n") or 0),
        "capped": (" · ".join(capped) or None),
    }
    ds = [c_["d"] for c_ in candidates]
    cut = seeded_search.recommended_cut(ds, null_obj)
    return {
        "candidates": candidates, "nullDistances": null_obj["distances"], "null": null_obj,
        # the rule the marker was computed under, so the figure can be checked
        # against it (fixup-a item 12)
        "recommendedCut": cut, "cutRule": seeded_search.cut_rule(),
        "perChannel": per_channel, "m": seed["samples"],
        "seedId": seed["id"], "span": [span[0], span[1]],
        "counts": (seeded_search.cut_counts(ds, null_obj, cut) if cut is not None else None),
        "exclusionNote": seeded_search.recommended_params(seed)["exclusion_note"],
        "computedAt": _now(),
    }


def _store_result(conn, session_id, key, result):
    with _results_lock:
        _results[key] = result
    row = conn.execute("SELECT state_json FROM discovery_sessions WHERE id = ?", (int(session_id),)).fetchone()
    state = json.loads((row["state_json"] if row else "{}") or "{}")
    # a non-chain job's `result` is None after a restart (jobs.py::_from_row), so
    # what the page needs to redraw its histogram and its cut lives in the row
    state["seed_result"] = {
        "key": key, "computedAt": result["computedAt"], "candidates": result["candidates"][:5000],
        "null": result["null"], "recommendedCut": result["recommendedCut"],
        "cutRule": result["cutRule"], "m": result["m"],
        "seedId": result["seedId"], "span": result["span"], "perChannel": result["perChannel"],
        "exclusionNote": result["exclusionNote"],
    }
    conn.execute("UPDATE discovery_sessions SET state_json = ?, updated_at = ? WHERE id = ?",
                 (json.dumps(state), _now(), int(session_id)))
    conn.commit()


def _cached_result(conn, session_id, key):
    with _results_lock:
        if key in _results:
            return _results[key]
    row = conn.execute("SELECT state_json FROM discovery_sessions WHERE id = ?", (int(session_id),)).fetchone()
    state = json.loads((row["state_json"] if row else "{}") or "{}")
    stored = state.get("seed_result")
    if stored and stored.get("key") == key:
        return dict(stored, nullDistances=stored["null"]["distances"], counts=None, restored=True)
    return None


@router.post("/api/discovery/seed/results")
def start_seed_results(request: Request, body: SeedBody):
    c = _conn(request)
    try:
        s, rec, _, _ = _session_scope(c)
        fs = rec["fs"]
        names = body.channels or json.loads(s["channels_json"])
        _ids_for(c, _stem(s["source_file"]), names)          # refuses held out / unknown names
        _seed_by_id(c, body.seedId)
        null = json.loads(s["null_json"] or "{}")
        key = _seed_key(body.seedId, names, body.t0, body.t1, body.k, body.maxDistance, null,
                        source_file=s["source_file"], rule=rule_from_settings(c))
        cached = _cached_result(c, s["id"], key)
        if cached is not None:
            return {"ready": True, "key": key, **cached}
        span = (int(round(body.t0 * 3600 * fs)), int(round(body.t1 * 3600 * fs)))
        if span[1] <= span[0]:
            span = (int(s["span_start"]), int(s["span_end"]))
        db_path = request.app.state.rt.db_path
        session_id, source_file = int(s["id"]), s["source_file"]

        def run(job):
            conn2 = corpus.connect(db_path)
            try:
                seed2 = _seed_by_id(conn2, body.seedId)
                chans2 = _ids_for(conn2, _stem(source_file), names)
                result = _seed_search(conn2, seed2, chans2, span, k=body.k,
                                      max_distance=body.maxDistance, null=null, job=job)
                _store_result(conn2, session_id, key, result)
                return {"key": key, "n_candidates": len(result["candidates"]),
                        "null_draws": result["null"]["draws"]}
            finally:
                conn2.close()

        job = request.app.state.manager.start_job("sweep", run, meta={
            "what": "seeded search", "seed": body.seedId, "channels": names,
            "span": list(span), "k": body.k, "null": null, "key": key})
        return {"ready": False, "job_id": job.id, "key": key}
    finally:
        c.close()


@router.get("/api/discovery/seed/results")
def get_seed_results(request: Request, seedId: str, channels: str = "", t0: float = 0.0, t1: float = 0.0,
                     k: int = 200, maxDistance: float = 0.0):
    c = _conn(request)
    try:
        s = _session(c)
        null = json.loads(s["null_json"] or "{}")
        names = _split(channels) or json.loads(s["channels_json"])
        key = _seed_key(seedId, names, t0, t1, k, maxDistance, null,
                        source_file=s["source_file"], rule=rule_from_settings(c))
        cached = _cached_result(c, s["id"], key)
        if cached is not None:
            return {"ready": True, "key": key, **cached}
        live = [j for j in request.app.state.manager.list_jobs(limit=25)
                if j.get("kind") == "sweep" and (j.get("meta") or {}).get("key") == key]
        if live:
            j = live[0]
            if j["status"] == "failed":
                err = j.get("error") or {}
                raise HTTPException(500, {"message": f"the seeded search failed: {err.get('message')}",
                                          "traceback": err.get("traceback")})
            return {"ready": False, "job_id": j["job_id"], "progress": j.get("progress"), "key": key}
        return {"ready": False, "job_id": None, "key": key,
                "note": "no result for this query yet — POST the same query to start the search"}
    finally:
        c.close()


@router.get("/api/discovery/seed/profile")
def get_seed_profile(request: Request, seedId: str, channel: str, t0: float = 0.0, t1: float = 0.0,
                     px: int = 1200):
    """§7.6's distance profile: one channel and one zoomed view at a time — the
    clean signal, and the distance at every position in it (`stumpy.mass`)."""
    c = _conn(request)
    try:
        s, rec, _, _ = _session_scope(c)
        fs = rec["fs"]
        ch = _ids_for(c, _stem(s["source_file"]), [channel])[0]
        seed = _seed_by_id(c, seedId)
        exemplar = np.asarray(seeded_search.exemplar_signal(c, seed).x, dtype=float)
        if t1 <= t0:
            raise HTTPException(422, {"message": (
                f"the view [{t0}, {t1}] h is not a window: t1 must be greater than t0. A clamped "
                f"range that inverts is a bug in the caller, not a window to serve.")})
        x = np.asarray(corpus.load_native(ch["npy_path"]), dtype=float)
        lo = max(0, int(round(t0 * 3600 * fs)))
        hi = min(len(x), max(lo + len(exemplar) + 1, int(round(t1 * 3600 * fs))))
        view = seeded_search.distance_profile(x, exemplar, view=(lo, hi))
        disp = corpus.display_channel(ch)          # the drawn signal; the distance is the core's

        def thin(vals, n):
            vals = np.asarray(vals, dtype=float)
            if len(vals) <= n:
                return [round(float(v), 5) for v in vals]
            idx = np.linspace(0, len(vals) - 1, n).round().astype(int)
            return [round(float(vals[i]), 5) for i in idx]

        n_sig = min(px, max(1, hi - lo))
        return {"t0H": lo / fs / 3600.0, "stepS": (hi - lo) / n_sig / fs,
                "signal": thin(np.asarray(view["signal"], dtype=float) * disp.factor, px),
                "distance": thin(view["distance"], px), "unit": disp.unit,
                "m": view["m"], "seedId": seedId, "channel": ch["name"],
                "nSignal": len(view["signal"]), "nDistance": len(view["distance"])}
    finally:
        c.close()


# ── planning, previewing and routing a run (§7.5) ───────────────────────────

class PlanBody(BaseModel):
    template: str | None = None
    seedId: str | None = None
    channels: list[str] = Field(default_factory=list)
    t0: float = 0.0
    t1: float = 0.0
    k: int = 200
    maxDistance: float = 0.0
    measuredPerChannelS: float | None = None
    sampleHours: float = 4.0
    label: str | None = None


def _steps_for(conn, body: PlanBody):
    """The chain a plan is about: a template's steps, or the one seeded-search
    step. Exactly one of the two, because a run is one or the other (P17)."""
    if body.template and body.seedId:
        raise HTTPException(422, {"message": "a run is a template or a seed search, not both (spec §7.1, P17)"})
    if body.template:
        from . import templates as T
        row = next((t for t in T.list_all(conn) if t["name"] == body.template), None)
        if row is None:
            raise HTTPException(404, {"message": f"no template {body.template!r}"})
        return row["steps"], row, None
    if body.seedId:
        seed = _seed_by_id(conn, body.seedId)
        return (seeded_search.seed_steps(seed, k=body.k,
                                         max_distance=(body.maxDistance if body.maxDistance > 0 else None)),
                None, seed)
    raise HTTPException(422, {"message": "name a template or a seedId"})


def _scope(conn, body: PlanBody):
    s, rec, _, span = _session_scope(conn)
    fs = rec["fs"]
    names = body.channels or json.loads(s["channels_json"])
    chans = _ids_for(conn, _stem(s["source_file"]), names)
    if body.t1 > body.t0:
        span = (int(round(body.t0 * 3600 * fs)), int(round(body.t1 * 3600 * fs)))
    return s, rec, chans, span


def _plan(conn, body: PlanBody):
    steps, template, seed = _steps_for(conn, body)
    s, rec, chans, span = _scope(conn, body)
    m = seed["samples"] if seed else None

    def reuse(c2, recording_id, target_span):
        """A matrix profile already on disk for this exact question. Only the
        matrix-profile blocks can consume one; `detection.seed_matches` runs
        `stumpy.match` directly and has nothing to reuse (seeded_search
        .WHY_NO_PROFILE), so a seeded search never claims a reuse it did not
        make."""
        mp_steps = [st for st in steps if st["algorithm"] == "matrix_profile"]
        if not mp_steps:
            return None
        rec_row = q.get_recording_by_id(c2, recording_id)
        window_min = float((mp_steps[0].get("params") or {}).get("window_min") or 0)
        if window_min <= 0:
            return None
        mm = int(round(window_min * 60 * float(rec_row["fs"])))
        return seeded_search.find_reusable_profile(c2, recording_id, mm, span=target_span)

    plan = fanout.plan(conn, steps=steps, recording_ids=[ch["id"] for ch in chans], span=span,
                       measured_per_channel_s=body.measuredPerChannelS, reuse_lookup=reuse)
    plan["template"] = template["name"] if template else None
    plan["seedId"] = seed["id"] if seed else None
    plan["m"] = m
    plan["usesMatrixProfile"] = any(st["algorithm"] == "matrix_profile" for st in steps)
    plan["reuseNote"] = (None if plan["usesMatrixProfile"]
                         else seeded_search.WHY_NO_PROFILE if seed else None)
    plan["sectionH"] = [span[0] / rec["fs"] / 3600.0, span[1] / rec["fs"] / 3600.0]
    plan["channels"] = [ch["name"] for ch in chans]
    return plan, steps, template, seed, span, chans, s


@router.post("/api/discovery/plan")
def post_plan(request: Request, body: PlanBody):
    c = _conn(request)
    try:
        plan, *_ = _plan(c, body)
        return _clean(plan)
    finally:
        c.close()


@router.post("/api/discovery/preview")
def post_preview(request: Request, body: PlanBody):
    """§7.1's *Preview on a sample*: run the chain on a sample of one channel,
    time it, and extrapolate. The only honest cost for a chain whose blocks
    declare no estimator — and `detection.seed_matches` declares none."""
    c = _conn(request)
    try:
        plan, steps, template, seed, span, chans, s = _plan(c, body)
        if not plan["runnable"]:
            raise HTTPException(422, {"message": plan["reason"], "refused": plan["refused"]})
        fs = float(chans[0]["fs"])
        sample = int(round(body.sampleHours * 3600 * fs))
        out = fanout.preview(plan, db_path=request.app.state.rt.db_path, sample_samples=sample)
        out["route"] = ("cluster" if out["estimate_s"] > plan["ceiling_s"] else "local")
        out["ceiling_s"] = plan["ceiling_s"]
        out["template"] = plan["template"]
        out["note"] = request.app.state.rt.banner()
        return _clean(out)
    finally:
        c.close()


# ── adding runs (§7.5) and running them ─────────────────────────────────────

def _next_key(conn, session_id, base):
    key, n = base, 1
    while conn.execute("SELECT 1 FROM discovery_runs WHERE session_id = ? AND run_key = ?",
                       (int(session_id), key)).fetchone():
        n += 1
        key = f"{base}_{n}"
    return key


def _insert_run(conn, session_id, *, run_key, kind, label, template_name=None, template_id=None,
                params=None, colour=None):
    n = conn.execute("SELECT COUNT(*) FROM discovery_runs WHERE session_id = ?", (int(session_id),)).fetchone()[0]
    conn.execute(
        "INSERT INTO discovery_runs (session_id, run_key, kind, label, colour, template_id, template_name, "
        "params_json, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)",
        (int(session_id), run_key, kind, label, colour or RUN_COLOURS[n % len(RUN_COLOURS)],
         template_id, template_name, json.dumps(params or {}), _now(), _now()))
    conn.commit()
    return conn.execute("SELECT * FROM discovery_runs WHERE session_id = ? AND run_key = ?",
                        (int(session_id), run_key)).fetchone()


def _surrogate_for(conn):
    """The paired null run's settings, from Settings › Nulls' `detection` kind.

    §7.3's *null expects* is "how many detections the null gives on the same
    scope", which is a **run** — `run_paired_recipe` prepends
    `preprocessing.surrogate` and links it by `runs.surrogate_of_run_id`. The
    PRD has surrogates on by default; a method the block does not implement
    turns the pairing off and says why, rather than quietly running a different
    null under the name the page prints.
    """
    resolved = seeded_search.null_from_settings(conn, kind="detection")
    if not resolved["supported"]:
        return False, None, resolved["reason"]
    return True, {"method": resolved["method"], "seed": 0}, None


def _start_sweep(request, *, session_id, run_key, plan, label, surrogate=True,
                 surrogate_params=None):
    """One fan-out, one `sweep` job, per-channel progress. The job writes the
    run group id back onto the `discovery_runs` row as soon as it has one, so a
    page that reloads mid-sweep still finds the runs."""
    db_path = request.app.state.rt.db_path

    def run(job):
        conn2 = corpus.connect(db_path)
        try:
            state = {"group": None}

            def on_progress(i, n, label_):
                job.progress(i, n, f"{label_} ({i + 1} of {n})")

            def on_target_done(i, n, row):
                if state["group"] is None:
                    return
                job.progress(i + 1, n, f"{row['channel_name']} · {row['detections_written']} spans")

            out = fanout.start(plan, db_path=db_path, on_progress=on_progress,
                               on_target_done=on_target_done, should_cancel=job.cancel_event.is_set,
                               surrogate=surrogate, surrogate_params=surrogate_params)
            cur = conn2.execute("SELECT params_json FROM discovery_runs WHERE session_id = ? AND run_key = ?",
                                (int(session_id), run_key)).fetchone()
            params = json.loads((cur["params_json"] if cur else "{}") or "{}")
            params["run_ids"] = out["run_ids"]
            params["reused_run_ids"] = out["reused"]
            # the group the runs are actually in: a reused run keeps the first
            # group it joined, so this is not always out["run_group_id"]
            groups = sorted({r["run_group_id"] for r in out["runs"] if r["run_group_id"]})
            conn2.execute("UPDATE discovery_runs SET run_group_id = ?, params_json = ?, status = ?, "
                          "updated_at = ? WHERE session_id = ? AND run_key = ?",
                          (groups[0] if groups else out["run_group_id"], json.dumps(params),
                           "cancelled" if out["cancelled"] else "done", _now(),
                           int(session_id), run_key))
            conn2.commit()
            return {"run_group_id": out["run_group_id"], "runs": len(out["runs"]),
                    "cancelled": out["cancelled"],
                    "detections": sum(r["detections_written"] or 0 for r in out["runs"])}
        except Exception:
            conn2.execute("UPDATE discovery_runs SET status = 'failed', updated_at = ? "
                          "WHERE session_id = ? AND run_key = ?", (_now(), int(session_id), run_key))
            conn2.commit()
            raise
        finally:
            conn2.close()

    job = request.app.state.manager.start_job("sweep", run, meta={
        "what": label, "run_key": run_key, "channels": plan["channels"],
        "span": plan["span"], "route": plan["route"],
        "null": ("paired surrogate run per channel" if surrogate else "off")})
    return job


class ApplyBody(BaseModel):
    templates: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    t0: float = 0.0
    t1: float = 0.0
    run: bool = True


@router.post("/api/discovery/templates/apply")
def apply_templates(request: Request, body: ApplyBody):
    """§7.5: "Each template becomes **one run across all channels in scope**".
    Over the ceiling the run is added but not started — the page's primary
    action becomes *Create SLURM script*."""
    c = _conn(request)
    try:
        out = []
        for name in body.templates:
            pb = PlanBody(template=name, channels=body.channels, t0=body.t0, t1=body.t1)
            plan, steps, template, _seed, span, chans, s = _plan(c, pb)
            if not plan["runnable"]:
                raise HTTPException(422, {"message": plan["reason"], "refused": plan["refused"],
                                          "template": name})
            key = _next_key(c, s["id"], name)
            on, sp, why = _surrogate_for(c)
            params = {"stage_count": len(steps), "version": template.get("version"),
                      "null": {"paired": on, "params": sp, "reason": why},
                      "detail": f"v{template.get('version') or 1} · {len(steps)} stages",
                      "glyph": D.glyph_for(f"{steps[-1]['stage']}.{steps[-1]['algorithm']}"),
                      "route": plan["route"], "estimate_s": plan["estimate_s"]}
            _insert_run(c, s["id"], run_key=key, kind="template", label=name,
                        template_name=name, template_id=template.get("id"), params=params)
            job_id = None
            if body.run and plan["route"] != "cluster":
                job = _start_sweep(request, session_id=int(s["id"]), run_key=key, plan=plan, label=name,
                                   surrogate=on, surrogate_params=sp)
                job_id = job.id
                c.execute("UPDATE discovery_runs SET job_id = ?, status = 'running', updated_at = ? "
                          "WHERE session_id = ? AND run_key = ?", (job_id, _now(), int(s["id"]), key))
                c.commit()
            out.append({"run_key": key, "job_id": job_id, "route": plan["route"],
                        "ceiling_s": plan["ceiling_s"], "estimate_s": plan["estimate_s"],
                        "started": job_id is not None,
                        "note": (None if job_id else
                                 ("over the local ceiling — create a SLURM script" if plan["route"] == "cluster"
                                  else "added, not started"))})
        return out
    finally:
        c.close()


@router.post("/api/discovery/seed/run")
def run_seed_search(request: Request, body: SeedBody):
    """§7.6's apply bar: "A run seed search becomes a normal run row"."""
    c = _conn(request)
    try:
        pb = PlanBody(seedId=body.seedId, channels=body.channels, t0=body.t0, t1=body.t1,
                      k=body.k, maxDistance=(body.cut if body.cut is not None else body.maxDistance))
        plan, steps, _t, seed, span, chans, s = _plan(c, pb)
        if not plan["runnable"]:
            raise HTTPException(422, {"message": plan["reason"], "refused": plan["refused"]})
        base = body.label or f"seed_{seed['hash'][:6]}"
        key = _next_key(c, s["id"], base)
        on, sp, why = _surrogate_for(c)
        params = {"stage_count": 1, "glyph": "seed", "seedId": seed["id"], "cut": body.cut,
                  "null": {"paired": on, "params": sp, "reason": why},
                  "k": body.k, "detail": f"{seed['samples']} samples · MASS",
                  "route": plan["route"], "exclusion_note": seeded_search.recommended_params(seed)["exclusion_note"]}
        _insert_run(c, s["id"], run_key=key, kind="seed", label=base, params=params)
        job_id = None
        if plan["route"] != "cluster":
            job = _start_sweep(request, session_id=int(s["id"]), run_key=key, plan=plan, label=base,
                               surrogate=on, surrogate_params=sp)
            job_id = job.id
            c.execute("UPDATE discovery_runs SET job_id = ?, status = 'running', updated_at = ? "
                      "WHERE session_id = ? AND run_key = ?", (job_id, _now(), int(s["id"]), key))
            c.commit()
        return {"run_key": key, "job_id": job_id, "route": plan["route"], "started": job_id is not None}
    finally:
        c.close()


@router.post("/api/discovery/slurm")
def post_slurm(request: Request, body: PlanBody):
    """§7.5: above the ceiling the primary action is *Create SLURM script*.
    The script is `Working.hpc.job_export`'s, fan-out aware — one array job
    whose task index selects its own channel."""
    from Working.hpc.job_export import export_job

    c = _conn(request)
    try:
        plan, steps, template, seed, span, chans, s = _plan(c, body)
        if not plan["runnable"]:
            raise HTTPException(422, {"message": plan["reason"], "refused": plan["refused"]})
        name = body.label or plan["template"] or (f"seed_{seed['hash'][:6]}" if seed else "discovery")
        out_dir = os.path.join(request.app.state.rt.dir, "hpc") if request.app.state.rt.mode == "sandbox" \
            else os.path.join(REPO_ROOT, "HPC", "Detection", "generated")
        os.makedirs(out_dir, exist_ok=True)
        base = f"{name}_{plan['n_channels']}ch_{int(span[0])}-{int(span[1])}"
        res = export_job(plan["recipe"], out_dir=out_dir, base_name=base, job_name=base,
                         est_seconds=plan["estimate_s"])
        script = ""
        if os.path.isfile(res["script_path"]):
            with open(res["script_path"], encoding="utf-8") as f:
                script = f.read()
        return {**res, "script": script, "route": plan["route"], "estimate_s": plan["estimate_s"],
                "ceiling_s": plan["ceiling_s"], "channels": plan["channels"],
                "note": request.app.state.rt.banner()}
    finally:
        c.close()


# ── run acts (§7.4) ─────────────────────────────────────────────────────────

@router.post("/api/discovery/history/{hid}/open")
def open_history_run(request: Request, hid: str):
    """Adopt a past Discovery run into this session.

    The History popover used to fabricate the row client-side: an invented
    template name, a guessed kind and a colour, under the *real* run key. The
    key then went out in `runs=` on /fires and /scoreboard, which know only the
    rows this table holds, and answered 404. Adoption is a row in
    `discovery_runs` pointing at the same `run_group_id` — the runs themselves
    are not copied, re-executed or re-owned, so two sessions referencing one
    fan-out see the same detections and the same scores.
    """
    c = _conn(request)
    try:
        s = _session(c)
        if hid.startswith("g-"):
            src = c.execute("SELECT * FROM discovery_runs WHERE run_group_id = ? ORDER BY id DESC LIMIT 1",
                            (int(hid[2:]),)).fetchone()
        elif hid.startswith("d-"):
            src = c.execute("SELECT * FROM discovery_runs WHERE id = ?", (int(hid[2:]),)).fetchone()
        else:
            raise HTTPException(422, {"message": f"'{hid}' is not a history id: expected 'g-<group>' or 'd-<row>'."})
        if src is None:
            raise HTTPException(404, {"message": f"no Discovery run behind history id '{hid}'."})
        if int(src["session_id"]) == int(s["id"]):
            return {"run_key": src["run_key"], "adopted": False, "note": "already in this session"}
        existing = c.execute("SELECT run_key FROM discovery_runs WHERE session_id = ? AND run_key = ?",
                             (int(s["id"]), src["run_key"])).fetchone()
        if existing is not None:
            return {"run_key": src["run_key"], "adopted": False, "note": "already in this session"}
        now = _now()
        c.execute(
            "INSERT INTO discovery_runs (session_id, run_key, kind, label, colour, template_id, template_name, "
            "run_group_id, job_id, params_json, status, created_at, updated_at, superseded_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (int(s["id"]), src["run_key"], src["kind"], src["label"], src["colour"], src["template_id"],
             src["template_name"], src["run_group_id"], src["job_id"], src["params_json"], src["status"],
             now, now, src["superseded_at"]))
        c.commit()
        return {"run_key": src["run_key"], "adopted": True,
                "note": "the same runs, read by this session — nothing was re-executed"}
    finally:
        c.close()


@router.post("/api/discovery/runs/{run_key}/discard")
def discard_run(request: Request, run_key: str):
    """§7.4: *Discard run* marks the run superseded and writes **no**
    adjudications. The detections stay; nothing human is written anywhere on
    this path, which is why a bulk discard cannot poison the RQ5 divergence
    measurement."""
    c = _conn(request)
    try:
        s = _session(c)
        row = _dr_by_key(c, s["id"], run_key)
        ids = _run_ids(c, row)
        n = fanout.supersede(c, run_ids=ids, reason="discarded in Discovery") if ids else 0
        c.execute("UPDATE discovery_runs SET superseded_at = ?, status = 'superseded', updated_at = ? "
                  "WHERE id = ?", (_now(), _now(), int(row["id"])))
        c.commit()
        return {"run_key": run_key, "status": "superseded", "superseded": n,
                "adjudications_written": 0, "annotations_written": 0,
                "note": "the detections are kept; the run stays reproducible from its own recipe"}
    finally:
        c.close()


@router.post("/api/discovery/runs/{run_key}/restore")
def restore_run(request: Request, run_key: str):
    c = _conn(request)
    try:
        s = _session(c)
        row = _dr_by_key(c, s["id"], run_key)
        ids = _run_ids(c, row)
        n = fanout.restore(c, run_ids=ids) if ids else 0
        c.execute("UPDATE discovery_runs SET superseded_at = NULL, status = 'done', updated_at = ? WHERE id = ?",
                  (_now(), int(row["id"])))
        c.commit()
        return {"run_key": run_key, "status": "done", "restored": n}
    finally:
        c.close()


class ReviewBody(BaseModel):
    limit: int = 500
    name: str | None = None


@router.post("/api/discovery/runs/{run_key}/review")
def send_to_review(request: Request, run_key: str, body: ReviewBody):
    """§7.4's *Send N unjudged to Review* (P20): a named queue over this run's
    unadjudicated detections. The queue is a **filter over the existing rows**
    — `Working.review.queue_state.ReviewQueue` on `run_group_id` — not a copy
    of them, so nothing is duplicated and no verdict is written here."""
    from Working.review.queue_state import ReviewQueue

    c = _conn(request)
    try:
        s = _session(c)
        row = _dr_by_key(c, s["id"], run_key)
        if not row["run_group_id"]:
            raise HTTPException(422, {"message": f"{run_key} has not run yet, so it has nothing to send"})
        # The queue must cover the runs this Discovery run is MADE of. A
        # fan-out that reused runs spans more than one `run_groups` row, and
        # filtering on the lowest group would hand Review a silently short
        # queue; `ReviewQueue` takes one group, so the union is counted here
        # and the run ids travel on the descriptor for Review to filter by.
        ids = _run_ids(c, row)
        groups = sorted({int(r["run_group_id"]) for r in
                         (R.get_run(c, i) for i in ids) if r and r["run_group_id"]})
        seen, n = set(), 0
        for gid in groups or [int(row["run_group_id"])]:
            for cand in ReviewQueue(c, run_group_id=gid, adjudication_status="unadjudicated").candidates:
                if int(cand["id"]) in seen or int(cand["run_id"]) not in set(ids):
                    continue
                seen.add(int(cand["id"]))
                n += 1
        name = body.name or f"Discovery · {row['label']} unjudged"
        state = json.loads(s["state_json"] or "{}")
        queues = state.setdefault("review_queues", [])
        queues = [x for x in queues if x.get("run_key") != run_key]
        queues.append({"name": name, "run_key": run_key, "run_group_id": int(row["run_group_id"]),
                       "run_ids": ids, "run_groups": groups,
                       "n": n, "created_at": _now(), "source": "discovery run", "blind": False,
                       "writes": "adjudications"})
        state["review_queues"] = queues
        c.execute("UPDATE discovery_sessions SET state_json = ?, updated_at = ? WHERE id = ?",
                  (json.dumps(state), _now(), int(s["id"])))
        c.commit()
        return {"run_key": run_key, "queued": min(n, body.limit), "unjudged": n, "queue": name,
                "run_group_id": int(row["run_group_id"]), "writes": "adjudications",
                "note": ("the queue is a filter over this run's unadjudicated detections, not a copy; "
                         "Review's own page reads it through ReviewQueue(run_group_id=…)")}
    finally:
        c.close()


@router.get("/api/discovery/queues")
def get_queues(request: Request):
    c = _conn(request)
    try:
        s = _session(c)
        return json.loads(s["state_json"] or "{}").get("review_queues", [])
    finally:
        c.close()


# ── comparing two runs (§7.7) and every stage (§7.8) ───────────────────────

def _recipe_of(conn, run_key, session_id):
    """The recipe behind a Discovery run: its first run's config. Every member
    of a fan-out shares one recipe but for its `recording_id`, so any of them
    is the chain."""
    row = _dr_by_key(conn, session_id, run_key)
    ids = _run_ids(conn, row)
    if not ids:
        return None, row
    run = R.get_run(conn, ids[0])
    if run is None:
        return None, row
    return R.load_recipe(conn, int(run["config_id"])), row


def _side(conn, session_id, run_key, chans, span, scope_label):
    """One column of §7.7's "what differs": the chain laid out by role, with
    the run's precision, reviewed count and × null beside it."""
    fs = float(chans[0]["fs"]) if chans else 1.0
    if run_key == "human":
        h = _reviewed_h(conn, chans, span)
        cells = {r: None for r in D.ROLES}
        cells["Source"] = {"index": "●", "name": "Source", "param": scope_label,
                           "signature": "— → Signal", "glyph": "source", "algorithm": None}
        cells["Detect"] = {"index": "01", "name": "human verdicts", "param": f"{h:.0f} h reviewed",
                           "signature": "Review → SpanSet", "glyph": "human", "algorithm": None}
        return {"run": "human", "label": "human annotations", "subtitle": "reference", "isSeed": False,
                "cells": cells, "precision": None, "reviewed": 0, "xNull": None, "threshold": None,
                "found": sum(len(_human_spans(conn, ch["id"], span)) for ch in chans)}, None
    recipe, row = _recipe_of(conn, run_key, session_id)
    params = json.loads(row["params_json"] or "{}")
    cells = (D.role_cells(recipe, source_label=scope_label) if recipe
             else {r: None for r in D.ROLES})
    is_seed = row["kind"] == "seed"
    precision = reviewed = x_null = None
    found = 0
    ids = _run_ids(conn, row)
    if ids:
        total = SB.score_runs(conn, ids, span=span)["total"]
        precision, reviewed, x_null = total["precision"], total["reviewed"], total["x_null"]
        found = total["found"]
    threshold = params.get("cut")
    if threshold is None and recipe:
        for st in recipe["steps"]:
            for name in ("threshold", "max_distance"):
                v = (st.get("params") or {}).get(name)
                if v:
                    threshold = float(v)
    return {"run": run_key, "label": row["label"], "subtitle": f"{row['kind']} · {row['status']}",
            "isSeed": is_seed, "cells": cells,
            "precision": (round(precision, 4) if precision is not None else None),
            "reviewed": reviewed or 0,
            "xNull": (round(x_null, 2) if x_null is not None else None),
            "threshold": threshold, "found": found}, recipe


def _same_cell(x, y):
    if x is None and y is None:
        return True
    if not x or not y:
        return False
    return x.get("name") == y.get("name") and x.get("param") == y.get("param")


@router.get("/api/discovery/compare")
def get_compare(request: Request, a: str, b: str, channels: str = "", t0: float = 0.0, t1: float = 0.0,
                limit: int = 400):
    """§7.7 — what differs, where A and B fire, set overlap, and the
    disagreements to step through."""
    c = _conn(request)
    try:
        s, rec, _, session_span = _session_scope(c)
        fs = rec["fs"]
        names = _split(channels) or json.loads(s["channels_json"])
        chans = _ids_for(c, _stem(s["source_file"]), names)
        span = (int(round(t0 * 3600 * fs)), int(round(t1 * 3600 * fs))) if t1 > t0 else session_span
        scope_label = " · ".join(ch["name"] for ch in chans)
        side_a, recipe_a = _side(c, s["id"], a, chans, span, scope_label)
        side_b, recipe_b = _side(c, s["id"], b, chans, span, scope_label)
        differing = [r for r in D.ROLES if not _same_cell(side_a["cells"].get(r), side_b["cells"].get(r))]

        per_channel, disagreements, both = [], [], []
        for ch in chans:
            sa = _spans_for(c, s["id"], a, ch, span)
            sb = _spans_for(c, s["id"], b, ch, span)
            per_channel.append({"channel": ch["name"],
                                "a": [(x["start"], x["end"]) for x in sa],
                                "b": [(x["start"], x["end"]) for x in sb]})
            out = D.compare_spans([(x["start"], x["end"]) for x in sa],
                                  [(x["start"], x["end"]) for x in sb])
            paired_a = {p["a"] for p in out["pairs"]}
            for p in out["pairs"]:
                both.append({"channel": ch["name"], "atH": round(sa[p["a"]]["start"] / fs / 3600.0, 5),
                             "iou": round(p["iou"], 3)})
            for i in out["only_a"]:
                disagreements.append(_disagreement("only A", ch["name"], sa[i], fs, side_b))
            for j in out["only_b"]:
                disagreements.append(_disagreement("only B", ch["name"], sb[j], fs, side_a))
        rows = D.overlap_rows(per_channel)
        total = rows[-1] if rows else {"channel": "all channels", "onlyA": 0, "both": 0, "onlyB": 0}

        # §7.7 asks for the closest call first. The other side's nearest score at
        # a place is a per-window computation (it is what /compare/window draws),
        # so the list is ordered by the firing run's own confidence — the
        # highest-scoring thing the other side missed — and says so rather than
        # implying a margin it has not computed.
        disagreements.sort(key=lambda d: -(d["score"] if d["score"] is not None else 0.0))
        capped = len(disagreements) > limit
        return {
            "a": side_a, "b": side_b, "differing": differing,
            "overlap": rows[:-1], "total": total,
            "disagreements": disagreements[:limit], "disagreementsTotal": len(disagreements),
            "disagreementsCapped": capped,
            "sortedBy": ("this run's own score, highest first — the other side's nearest score is "
                         "computed for the window you step to"),
            "both": both,
            "attributable": len(differing) <= 1,
            "attributionNote": (None if len(differing) <= 1 else
                                f"{len(differing)} roles differ, so a difference in output cannot be "
                                f"attributed to any single stage"),
            "stageDiff": (D.stage_diff(recipe_a, recipe_b) if recipe_a and recipe_b else []),
            "rule": rule_from_settings(c),
            "channels": [ch["name"] for ch in chans],
        }
    finally:
        c.close()


def _disagreement(kind, channel, span_row, fs, other_side):
    return {
        "kind": kind, "channel": channel,
        "atH": round(span_row["start"] / fs / 3600.0, 5),
        "index": span_row["start"], "end": span_row["end"],
        "detection": f"d-{span_row['id']}",
        "score": (round(span_row["score"], 4) if span_row.get("score") is not None else None),
        "otherNearest": None,
        "otherThreshold": other_side.get("threshold"),
        "otherIsSeed": bool(other_side.get("isSeed")),
    }


def _window_scores(conn, session_id, run_key, ch, lo, hi, fs):
    """The other side's own score curve over one window: for a seed run its
    distance profile, for a chain the last Scores its steps produce. Empty with
    a reason when the chain has no scoring stage at all (a Signal → SpanSet
    detector decides without one)."""
    x_full = corpus.load_native(ch["npy_path"])
    x = np.asarray(x_full[lo:hi], dtype=float)
    if run_key == "human":
        return [], "human verdicts carry no score"
    row = _dr_by_key(conn, session_id, run_key)
    params = json.loads(row["params_json"] or "{}")
    if row["kind"] == "seed" and params.get("seedId"):
        seed = _seed_by_id(conn, params["seedId"])
        exemplar = np.asarray(seeded_search.exemplar_signal(conn, seed).x, dtype=float)
        if len(exemplar) >= len(x):
            return [], f"the window is shorter than the seed ({len(exemplar)} samples)"
        prof = seeded_search.distance_profile(x, exemplar)
        return [round(float(v), 5) for v in prof], None
    recipe, _ = _recipe_of(conn, run_key, session_id)
    if recipe is None:
        return [], "this run has not run yet"
    from Working.discovery import window_chain
    steps = window_chain.run_window(conn, recipe, x, fs, span_start=lo)
    scores = [st for st in steps if st["ok"] and st["kind"] == "scores"]
    if not scores:
        failed = next((st for st in steps if not st["ok"] and not str(st.get("error", "")).startswith("skipped")), None)
        if failed:
            return [], f"step {failed['index']} ({failed['algorithm']}) could not run on this window: {failed['error']}"
        return [], "this chain has no scoring stage — it decides straight from the signal"
    vals = np.asarray(scores[-1]["value"].values, dtype=float)
    return [None if not np.isfinite(v) else round(float(v), 5) for v in vals], None


def _lowest(values):
    """The index of the smallest finite value, or None when there is none.

    The wire spells a non-finite score `None`, which `np.nanargmin` cannot
    order against a float — it raises, and the stepper's whole window comes
    back a 500."""
    if not values:
        return None
    arr = np.array([np.nan if v is None else float(v) for v in values], dtype=float)
    if not np.isfinite(arr).any():
        return None
    return int(np.nanargmin(arr))


@router.get("/api/discovery/compare/window")
def get_compare_window(request: Request, a: str, b: str, channel: str, atH: float, kind: str = "only A",
                       windowS: float = 240.0, detection: str | None = None):
    """§7.7's stepper: one clean signal for the window, the firing side's span
    track, and the other side's own score at that place — so the non-firing
    side shows how close it came."""
    c = _conn(request)
    try:
        s, rec, _, _ = _session_scope(c)
        fs = rec["fs"]
        ch = _ids_for(c, _stem(s["source_file"]), [channel])[0]
        centre = int(round(atH * 3600 * fs))
        half = int(round(windowS * fs / 2))
        x_full = corpus.display_channel(ch)
        lo = max(0, centre - half)
        hi = min(len(x_full), centre + half)
        seg = np.asarray(x_full[lo:hi], dtype=float)
        firing, other = (a, b) if kind == "only A" else (b, a)
        spans = _spans_for(c, s["id"], firing, ch, (lo, hi))
        near = min(spans, key=lambda sp: abs(sp["start"] - centre), default=None)
        track = [ (near["start"] - lo) / fs, (near["end"] - lo) / fs ] if near else None
        other_scores, note = _window_scores(c, s["id"], other, ch, lo, hi, fs)
        return {
            "t0H": lo / fs / 3600.0, "windowS": (hi - lo) / fs, "stepS": 1.0 / fs, "unit": x_full.unit,
            "values": [None if not np.isfinite(v) else round(float(v), 5) for v in seg],
            "aSpan": track if kind == "only A" else None,
            "bSpan": track if kind == "only B" else None,
            "aScore": [], "bScore": other_scores, "scoreNote": note,
            # the score list carries None where the value is not finite, and
            # numpy cannot order None against a float — so the minimum is taken
            # over an array that spells those NaN
            "minAt": _lowest(other_scores),
            "otherThreshold": (_side(c, s["id"], other, [ch], (lo, hi), ch["name"])[0]["threshold"]),
            "channel": ch["name"], "detection": detection,
        }
    finally:
        c.close()


_THUMB_BY_KIND = {"signal": "trace", "scores": "distance", "encoding": "symbols", "spanset": "trace"}


def _stage_cells(conn, side, recipe, steps_out, other_cells, x, fs, lo, threshold, is_seed,
                 side_label="A", factor=1.0):
    """Five cells in ROLES order, each the block's own output drawn as its
    chain-row thumbnail (§6.8) so any chain renders."""
    by_role = {}
    if recipe:
        for i, st in enumerate(recipe["steps"]):
            role = None
            try:
                from Adapters.registry import discover_adapters, get_adapter
                discover_adapters()
                role = D.role_of(get_adapter(f"{st['stage']}.{st['algorithm']}"))
            except Exception:
                role = None
            if role:
                by_role[role] = i
    cells = []
    for role in D.ROLES:
        mine = side["cells"].get(role)
        theirs = other_cells.get(role)
        # the badge names the side it is ON. Hard-coding "A only" attributed
        # B's own stages to A, on B's own column.
        badge = ("absent" if not mine else "identical" if _same_cell(mine, theirs)
                 else (f"{side_label} only" if not theirs else "differs"))
        if not mine:
            cells.append({"role": role, "cell": None, "badge": "absent", "thumb": {"kind": "absent"},
                          "caption": (f"the other run runs {theirs['name'].lower()} here" if theirs
                                      else "neither run has a stage here"),
                          "decided": "— no stage",
                          "absentNote": (f"{side['run']} has no {role} stage" if theirs else None)})
            continue
        if role == "Source":
            cells.append({"role": role, "cell": mine, "badge": badge,
                          "thumb": {"kind": "trace", "values": x},
                          "caption": f"the same {len(x)} samples in both runs", "decided": "the same window"})
            continue
        idx = by_role.get(role)
        out = next((s for s in steps_out if s["index"] == idx), None) if idx is not None else None
        if out is None or not out["ok"]:
            reason = (out or {}).get("error") or "this stage did not run on this window"
            cells.append({"role": role, "cell": mine, "badge": badge,
                          "thumb": {"kind": "absent"}, "caption": reason, "decided": "could not run here",
                          "error": reason})
            continue
        cells.append(_thumb_cell(role, mine, badge, out, x, fs, threshold, is_seed, factor=factor))
    return cells


def _thumb_cell(role, cell, badge, out, x, fs, threshold, is_seed, factor=1.0):
    kind = out["kind"]
    value = out["value"]
    if kind == "signal":
        # a Signal stage preserves units: drawn by the same factor as its ghost `x`
        vals = [round(float(v), 5) for v in np.asarray(value.x, dtype=float) * factor]
        return {"role": role, "cell": cell, "badge": badge,
                "thumb": {"kind": "trace", "values": vals, "ghost": x, "stroke": "var(--trace-blue)"},
                "caption": f"{cell['param']}", "decided": cell["param"]}
    if kind == "scores":
        vals = np.asarray(value.values, dtype=float)
        finite = vals[np.isfinite(vals)]
        lowest = int(np.nanargmin(vals)) if finite.size else 0
        return {"role": role, "cell": cell, "badge": badge,
                "thumb": {"kind": "distance",
                          "values": [None if not np.isfinite(v) else round(float(v), 5) for v in vals],
                          "threshold": threshold, "minIndex": lowest,
                          "minValue": (round(float(vals[lowest]), 4) if finite.size else None),
                          "isSeed": bool(is_seed)},
                "caption": (f"lowest {vals[lowest]:.3f}" if finite.size else "no finite values")
                           + (f" · threshold {threshold}" if threshold else ""),
                "decided": (f"lowest {vals[lowest]:.3f}" if finite.size else "nothing scored")}
    if kind == "encoding" and getattr(value, "kind", None) == "symbolic":
        syms = np.asarray(value.values).ravel()
        uniq = sorted({str(s) for s in syms.tolist()})
        order = {s: i for i, s in enumerate(uniq)}
        seq = [order[str(s)] for s in syms.tolist()][:400]
        return {"role": role, "cell": cell, "badge": badge,
                "thumb": {"kind": "symbols", "values": seq, "lowRun": None},
                "caption": f"{len(syms)} symbols · alphabet {len(uniq)}",
                "decided": f"{len(syms)} symbols"}
    if kind == "spanset":
        n = len(value.starts)
        span = ([float(value.starts[0]) / fs, float(value.ends[0]) / fs] if n else None)
        return {"role": role, "cell": cell, "badge": badge,
                "thumb": {"kind": "trace", "values": x, "span": span, "emptyTrack": n == 0},
                "caption": f"{n} span{'s' if n != 1 else ''} in this window",
                "decided": f"{n} span{'s' if n != 1 else ''}"}
    if kind == "encoding":
        shape = getattr(getattr(value, "values", None), "shape", None)
        return {"role": role, "cell": cell, "badge": badge, "thumb": {"kind": "absent"},
                "caption": f"an image encoding {list(shape) if shape else ''} — drawn on its block page, "
                           f"not as a stage thumbnail",
                "decided": f"image encoding {list(shape) if shape else ''}"}
    return {"role": role, "cell": cell, "badge": badge, "thumb": {"kind": "absent"},
            "caption": f"a {kind} has no stage thumbnail in this view", "decided": kind}


@router.get("/api/discovery/compare/stages")
def get_compare_stages(request: Request, a: str, b: str, channel: str, atH: float, kind: str = "only A",
                       index: int = 1, of: int = 1, windowS: float = 240.0, detection: str | None = None):
    """§7.8 — the same window pushed through both runs, rows aligned by role.
    Each chain is run over the window through `Working.discovery.window_chain`,
    which uses execution.py's calling convention and writes no run row: this is
    a preview of a window, not a run."""
    from Working.discovery import window_chain

    c = _conn(request)
    try:
        s, rec, _, _ = _session_scope(c)
        fs = rec["fs"]
        ch = _ids_for(c, _stem(s["source_file"]), [channel])[0]
        centre = int(round(atH * 3600 * fs))
        half = int(round(windowS * fs / 2))
        x_full = corpus.load_native(ch["npy_path"])
        lo, hi = max(0, centre - half), min(len(x_full), centre + half)
        seg = np.asarray(x_full[lo:hi], dtype=float)           # what both chains are handed
        disp = corpus.display_channel(ch)
        x = [None if not np.isfinite(v) else round(float(v), 5) for v in seg * disp.factor]

        side_a, recipe_a = _side(c, s["id"], a, [ch], (lo, hi), ch["name"])
        side_b, recipe_b = _side(c, s["id"], b, [ch], (lo, hi), ch["name"])
        out_a = window_chain.run_window(c, recipe_a, seg, fs, span_start=lo) if recipe_a else []
        out_b = window_chain.run_window(c, recipe_b, seg, fs, span_start=lo) if recipe_b else []
        cells_a = _stage_cells(c, side_a, recipe_a, out_a, side_b["cells"], x, fs, lo,
                               side_a["threshold"], side_a["isSeed"], side_label="A", factor=disp.factor)
        cells_b = _stage_cells(c, side_b, recipe_b, out_b, side_a["cells"], x, fs, lo,
                               side_b["threshold"], side_b["isSeed"], side_label="B", factor=disp.factor)
        first = next((r for r, ca, cb in zip(D.ROLES, cells_a, cells_b)
                      if ca["badge"] != "identical" or cb["badge"] != "identical"), None)
        return {
            "d": {"kind": kind, "channel": ch["name"], "atH": atH, "detection": detection},
            "index": index, "of": of, "firstDiffering": first,
            "a": cells_a, "b": cells_b,
            "aSubtitle": side_a["subtitle"], "bSubtitle": side_b["subtitle"],
            "windowS": (hi - lo) / fs, "unit": disp.unit,
            "note": ("the window is pushed through both chains here and nothing is written: no run row, "
                     "no detections, no step cache"),
        }
    finally:
        c.close()
