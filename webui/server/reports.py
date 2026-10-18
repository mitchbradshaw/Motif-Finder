"""Reports — the figures and tables behind a result (docs/prompts/changes/reports.md).

Thin over `Working.reports`, which draws (matplotlib) and writes. This module
gathers what the report shows, and it gathers it from the Discovery page's
own reads so a report cannot disagree with the page it stands behind:

* the scoreboard is `discovery.get_scoreboard` for this run, its channels and
  section — the route itself, called with this request;
* the fires strip is `discovery.get_fires` for ``human,<run>``;
* each example's trace is `discovery.get_detection_window`;
* the map is `detection_map.channel_map`, read in the core.

Routes:

* ``GET  /api/reports/detection-run/{run_key}`` — the live report as JSON:
  ``{title, fragment, html, markdown, examples, …}``. ``fragment`` is the HTML
  the page puts in a container, the figures inline as data URIs (nothing is
  written to disk for a live render);
* ``GET  /api/reports/detection-run/{run_key}/html`` — the same as a whole
  page, to open in a tab and print;
* ``POST /api/reports/detection-run/{run_key}/snapshot`` — writes report.html,
  report.md and the PNGs under the results folder and records the PATH;
* ``GET  /api/reports`` — every snapshot; ``GET /api/reports/{id}/files/{name}``
  serves one of its files; ``POST /api/reports/{id}/open-folder`` opens its
  folder on this machine.

The held-out lock applies: the session scope is resolved by Discovery's own
`_session_scope`, which refuses the held-out recording with the same 423.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import threading

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from Working.discovery.matching import match_span_sets, rule_from_settings
from Working.reports import detection_run as DR
from Working.reports import provenance as PV
from Working.reports import render as RD
from Working.reports import store as ST

from . import corpus
from . import discovery as D
from .runtime import HELD_OUT_FILE, REPO_ROOT

router = APIRouter()

#: the example trace: the span with this much signal either side, at this many points
EXAMPLE_PAD_MIN_S = 60.0
EXAMPLE_PX = 400
#: one render at a time: matplotlib's font cache and the Agg canvases are not
#: worth racing, and a report is a deliberate act, not a poll
_render_lock = threading.Lock()


def _results_root(rt) -> str:
    """Where snapshots live: the sandbox's own results folder, or the repository's
    `Results/` in a project start (where the adapters' results already go)."""
    return os.path.join(rt.results_dir or os.path.join(REPO_ROOT, "Results"), "reports")


def _hours(fs, samples):
    return samples / float(fs) / 3600.0


def _verdict_of(conn, det, humans, rule):
    """A verdict given on the detection in Review, else the human verdict the
    matching rule pairs it with (the browser's `priorVerdict`), else None."""
    row = conn.execute("SELECT verdict FROM adjudications WHERE detection_id = ?", (int(det["id"]),)).fetchone()
    if row is not None:
        return row["verdict"]
    if not humans:
        return None
    pairing = match_span_sets([(det["start"], det["end"])], [(h["start"], h["end"]) for h in humans], rule=rule)
    for p in pairing["pairs"]:
        return humans[p["reference"]]["verdict"]
    return None


def _seed_null(conn, s, params, names, dets_by_channel):
    """The Seed page's histogram data for a seed run: the null's distances per
    channel from the session's stored seed result (when it is this run's seed)
    and the run's own match distances (its detections' scores)."""
    state = json.loads(s["state_json"] or "{}")
    stored = state.get("seed_result") or {}
    by = stored.get("nullByChannel") or {}
    if stored.get("seedId") != params.get("seedId") or not by:
        return None, ("The null's distances are not stored for this run (the session's last seed result is for "
                      "another seed or was never computed), so its histogram cannot be drawn; the counts above are "
                      "the scoreboard's.")
    out = {}
    for name in names:
        part = by.get(name)
        if part is None:
            continue
        out[name] = {"null": part.get("distances") or [],
                     "found": [d["score"] for d in dets_by_channel.get(name, []) if d.get("score") is not None]}
    return out, None


def _gather(request: Request, run_key: str, channels: str = "", t0: float | None = None, t1: float | None = None):
    """Everything the detection-run report shows, read through Discovery's own routes."""
    c = D._conn(request)
    try:
        s, rec, chans, span = D._session_scope(c)          # 423 for the held-out recording, as every page
        dr = D._dr_by_key(c, s["id"], run_key)             # 404 naming the key
        fs = float(rec["fs"])
        names = D._split(channels) or json.loads(s["channels_json"])
        chans = D._ids_for(c, D._stem(s["source_file"]), names)
        a = int(round(t0 * 3600 * fs)) if t0 is not None else int(s["span_start"])
        b = int(round(t1 * 3600 * fs)) if t1 is not None else int(s["span_end"])
        span = (a, b)
        h0, h1 = _hours(fs, a), _hours(fs, b)
        rows = D._discovery_runs(c, s["id"])
        index = next((i for i, r in enumerate(rows) if r["run_key"] == run_key), 0)
        payload = D._run_payload(c, dr, index, span, jobs=dict(request.app.state.manager.jobs))
        params = json.loads(dr["params_json"] or "{}")
        ids = D._run_ids(c, dr)
        steps = []
        if ids:
            cfg = c.execute("SELECT c.config_json FROM runs r JOIN configs c ON c.id = r.config_id WHERE r.id = ?",
                            (int(ids[0]),)).fetchone()
            if cfg is not None:
                parsed = json.loads(cfg["config_json"] or "{}")
                steps = parsed.get("steps", []) if isinstance(parsed, dict) else parsed
        rule = rule_from_settings(c)
        dets, dets_by_channel, humans_by_channel = [], {}, {}
        for ch in chans:
            mine = [dict(d, channel=ch["name"], recording_id=int(ch["id"]))
                    for d in D._run_detections(c, ids, int(ch["id"]), span)]
            dets += mine
            dets_by_channel[ch["name"]] = mine
            humans_by_channel[ch["name"]] = D._human_spans(c, ch["id"], span, verdicts=None)
        session_name, state_row = s["name"], s
    finally:
        c.close()

    hours_args = {"channels": ",".join(names), "t0": h0, "t1": h1}
    scoreboard = next(iter(D.get_scoreboard(request, runs=run_key, **hours_args)), None)
    fires = D.get_fires(request, runs=f"human,{run_key}", **hours_args)

    picked = DR.pick_examples(dets, run_key, lower_is_better=(dr["kind"] == "seed"))
    c = D._conn(request)
    try:
        examples = []
        for d in picked:
            dur_s = (d["end"] - d["start"]) / fs
            trace = D.get_detection_window(request, int(d["id"]), pad_s=max(EXAMPLE_PAD_MIN_S, 2 * dur_s),
                                           px=EXAMPLE_PX)
            examples.append(dict(d, detectionId=int(d["id"]), atH=_hours(fs, d["start"]), durationS=round(dur_s, 2),
                                 verdict=_verdict_of(c, d, humans_by_channel.get(d["channel"]) or [], rule),
                                 trace=trace))
        null_rec = params.get("null") or {}
        source = (null_rec.get("source") or ("paired" if null_rec.get("paired") else "off"))
        null = {"kind": "seed" if dr["kind"] == "seed" else "template", "source": source,
                "draws": null_rec.get("draws"), "cut": params.get("cut"),
                "method": null_rec.get("method") or (null_rec.get("params") or {}).get("method"),
                "rows": [{"channel": r["channel"], "found": r["found"], "nullExpects": r["nullExpects"],
                          "nullRun": r["nullRun"], "nullDraws": r["nullDraws"], "nullDrawsMax": r["nullDrawsMax"],
                          "xNull": r["xNull"], "xNullNote": r["xNullNote"]}
                         for r in (scoreboard or {}).get("channels", [])]}
        if dr["kind"] == "seed" and source != "off":
            by, missing = _seed_null(c, state_row, params, names, dets_by_channel)
            if by:
                null["byChannel"] = by
            if missing:
                null["missing"] = missing
        exclude = [] if not corpus.held_out_locked(c) else [HELD_OUT_FILE]
        rt = request.app.state.rt
        database = rt.db_source if os.path.normcase(rt.db_source) == os.path.normcase(rt.db_path) else \
            f"{rt.db_source} (read from the sandbox copy {rt.db_path})"
        run = {"key": run_key, "label": payload["label"], "kind": payload["kind"], "sourceFile": s["source_file"],
               "recording": corpus.dataset_name(c, s["source_file"]), "channels": names, "sectionH": [h0, h1],
               "session": session_name, "template": dr["template_name"], "version": params.get("version"),
               "status": payload["status"], "found": payload.get("found"), "runIds": ids, "steps": steps,
               "nullRecord": null_rec, "seedId": params.get("seedId"), "cut": params.get("cut")}
        with _render_lock:
            report = DR.detection_run_report(c, run, scoreboard=scoreboard, fires=fires, examples=examples,
                                             null=null, provenance=PV.provenance(REPO_ROOT, database),
                                             exclude_files=exclude)
        return report, {"sessionId": int(s["id"]), "examples": examples}
    finally:
        c.close()


def _wire(report, extra, run_key):
    return {
        "kind": report["kind"], "runKey": run_key, "title": report["title"], "subtitle": report["subtitle"],
        "fragment": RD.report_fragment(report, inline=True), "html": RD.report_html(report, inline=True),
        "markdown": report["markdown"], "figures": [name for name, _ in report["figures"]],
        "examples": [{"detectionId": e["detectionId"], "channel": e["channel"], "pick": e["pick"],
                      "atH": round(e["atH"], 4), "score": e.get("score"), "verdict": e.get("verdict")}
                     for e in extra["examples"]],
    }


@router.get("/api/reports/detection-run/{run_key}")
def get_detection_run_report(request: Request, run_key: str, channels: str = "", t0: float | None = None,
                             t1: float | None = None):
    report, extra = _gather(request, run_key, channels, t0, t1)
    return _wire(report, extra, run_key)


@router.get("/api/reports/detection-run/{run_key}/html", response_class=HTMLResponse)
def get_detection_run_report_html(request: Request, run_key: str, channels: str = "", t0: float | None = None,
                                  t1: float | None = None):
    report, _ = _gather(request, run_key, channels, t0, t1)
    return HTMLResponse(RD.report_html(report, inline=True))


@router.post("/api/reports/detection-run/{run_key}/snapshot")
def post_detection_run_snapshot(request: Request, run_key: str, body: dict = Body(default={})):
    body = body or {}
    report, extra = _gather(request, run_key, body.get("channels") or "", body.get("t0"), body.get("t1"))
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    root = os.path.join(_results_root(request.app.state.rt), DR.KIND, run_key)
    out_dir = os.path.join(root, stamp)
    n = 1
    while os.path.exists(out_dir):           # two saves in one second are two snapshots, never one overwritten
        n += 1
        out_dir = os.path.join(root, f"{stamp}-{n}")
    paths = RD.write_report(report, out_dir)
    c = D._conn(request)
    try:
        rid = ST.record(c, kind=DR.KIND, run_key=run_key, session_id=extra["sessionId"], title=report["title"],
                        path=out_dir, note=(body.get("note") or None))
        return {"id": rid, "path": out_dir, "files": sorted(os.listdir(out_dir)), "markdown": paths["markdown"],
                "html": paths["html"]}
    finally:
        c.close()


def _snapshot_wire(row):
    path = row["path"]
    return {"id": row["id"], "kind": row["kind"], "runKey": row["run_key"], "runId": row["run_id"],
            "sessionId": row["session_id"], "title": row["title"], "createdAt": row["created_at"], "path": path,
            "note": row["note"], "exists": os.path.isfile(os.path.join(path, "report.html"))}


@router.get("/api/reports")
def get_reports(request: Request):
    c = D._conn(request)
    try:
        return [_snapshot_wire(r) for r in ST.list_reports(c)]
    finally:
        c.close()


def _snapshot_or_404(request, report_id):
    c = D._conn(request)
    try:
        row = ST.get_report(c, report_id)
    finally:
        c.close()
    if row is None:
        raise HTTPException(404, {"message": f"no saved report {report_id}"})
    return row


@router.get("/api/reports/{report_id}/files/{name}")
def get_report_file(request: Request, report_id: int, name: str):
    """One file of a snapshot, by its bare name (report.html, report.md, fig-NN-*.png) — never a path."""
    row = _snapshot_or_404(request, report_id)
    if name != os.path.basename(name) or name in ("", ".", "..") or "/" in name or "\\" in name:
        raise HTTPException(400, {"message": f"{name!r} is not a file name"})
    path = os.path.join(row["path"], name)
    if not os.path.isfile(path):
        raise HTTPException(404, {"message": f"the snapshot has no file {name!r} (folder {row['path']})"})
    media = {".html": "text/html", ".md": "text/markdown", ".png": "image/png"}.get(os.path.splitext(name)[1])
    return FileResponse(path, media_type=media)


@router.post("/api/reports/{report_id}/open-folder")
def post_open_folder(request: Request, report_id: int):
    """Open the snapshot's folder in the file manager of the machine the bridge runs on (the researcher's own)."""
    row = _snapshot_or_404(request, report_id)
    path = row["path"]
    if not os.path.isdir(path):
        raise HTTPException(404, {"message": f"the folder {path} no longer exists"})
    if not hasattr(os, "startfile"):
        raise HTTPException(501, {"message": f"opening a folder is only wired on Windows; the folder is {path}",
                                  "path": path})
    os.startfile(path)  # noqa: S606 — a recorded snapshot folder, not a path from the request
    return {"opened": path, "platform": sys.platform}
