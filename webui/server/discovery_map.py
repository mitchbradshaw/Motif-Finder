"""Discovery › Map — the detection map's three reads (2026-10-12).

Thin over `Working.discovery.detection_map`, which counts; this module names
datasets (`corpus.dataset_name`), orders them as the rest of the app does,
refuses the held-out file and says which session is open, so the client knows
which cells the Runs browser can show. Nothing numerical is computed here.

* `GET /api/discovery/map` — level 3: every dataset with a live Discovery
  run, all its channels, one cell per row and channel; `withoutRuns` and
  `heldOutOmitted` say what is not drawn and why.
* `GET /api/discovery/map/dataset?recording=&chunks=` — level 2: one
  dataset's channels, each in 1, 2, 4 or 8 equal time slices.
* `GET /api/discovery/map/channel?recording=&channel=&binH=` — level 1: one
  channel over the whole recording in `binH`-hour bins, with the covered
  fraction of every bin.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request

from Working.discovery import detection_map as DM

from . import corpus
from .discovery import _conn, _file_for_key, _refuse_held_out, _session, _stem
from .runtime import HELD_OUT_FILE

router = APIRouter()


def _session_bit(conn):
    """The open session and its scope: the client opens the Runs browser from a
    level-1 bin only inside it, because the browser reads nothing outside it."""
    s = _session(conn)
    rec = _file_for_key(conn, _stem(s["source_file"]))
    fs = float(rec["fs"])
    return {"id": int(s["id"]), "name": s["name"], "recording": _stem(s["source_file"]),
            "channels": json.loads(s["channels_json"] or "[]"),
            "section": [int(s["span_start"] or 0) / fs / 3600.0, int(s["span_end"] or 0) / fs / 3600.0]}


def _keyed(conn, payload):
    """Datasets in the app's order (M2_aug first, as the scope card lists them)
    and keyed the way every other Discovery route keys a recording."""
    order = {r["source_file"]: i for i, r in enumerate(corpus.recordings(conn))}
    for group in ("datasets", "withoutRuns"):
        for d in payload.get(group, []):
            d["key"] = _stem(d["file"])
        payload[group] = sorted(payload.get(group, []), key=lambda d: (order.get(d["file"], 999), d["file"]))
    return payload


@router.get("/api/discovery/map")
def get_map(request: Request):
    c = _conn(request)
    try:
        m = _keyed(c, DM.dataset_map(c, exclude_files=[HELD_OUT_FILE]))
        m["session"] = _session_bit(c)
        return m
    finally:
        c.close()


@router.get("/api/discovery/map/dataset")
def get_map_dataset(request: Request, recording: str, chunks: int = 1):
    c = _conn(request)
    try:
        rec = _file_for_key(c, recording)
        _refuse_held_out(rec["source_file"])
        if chunks not in DM.CHUNK_OPTIONS:
            raise HTTPException(422, {"message": f"chunks must be one of {list(DM.CHUNK_OPTIONS)}, not {chunks}"})
        m = DM.channel_map(c, rec["source_file"], chunks=chunks, exclude_files=[HELD_OUT_FILE])
        m["key"] = _stem(rec["source_file"])
        m["session"] = _session_bit(c)
        return m
    finally:
        c.close()


@router.get("/api/discovery/map/channel")
def get_map_channel(request: Request, recording: str, channel: str, binH: float = 3.0):
    c = _conn(request)
    try:
        rec = _file_for_key(c, recording)
        _refuse_held_out(rec["source_file"])
        if not binH > 0:
            raise HTTPException(422, {"message": f"binH must be a positive number of hours, not {binH}"})
        try:
            m = DM.timeline_map(c, rec["source_file"], channel, bin_h=binH, exclude_files=[HELD_OUT_FILE])
        except KeyError as e:
            raise HTTPException(404, {"message": str(e.args[0]) if e.args else "no such channel",
                                      "channels": [ch["name"] for ch in rec["channels"]]})
        m["key"] = _stem(rec["source_file"])
        m["session"] = _session_bit(c)
        return m
    finally:
        c.close()
