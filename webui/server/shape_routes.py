"""fixup-ag: the bridge side of the RQ1 version-2 chain — *Window pool* → *Trace
shape* → *Shape clustering* (ticket `docs/prompts/fixup/AG-…`).

* ``GET /api/windowsets/library`` — what the *Window pool* block's page lists: the
  library of EVERY saved window set (unlabelled sets, pools, the baseline's
  labelled set), each with its kind, recording(s), scale and counts, from
  ``Working.training.pool.list_sets`` — nothing assumes six. The held-out
  recording is never listed.

The core does the work (``Working.training.pool``, ``Working.training.shape``);
these routes hand it a connection and hand its answers back.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Request

from . import corpus
from .runtime import HELD_OUT_FILE

router = APIRouter()


def _conn(request: Request):
    return corpus.connect(request.app.state.rt.db_path)


def _per_recording(c, row) -> dict:
    out: dict[str, int] = {}
    for sf, n in c.execute("SELECT r.source_file, SUM(w.n_windows) FROM window_set_channels w JOIN recordings r "
                           "ON r.id = w.recording_id WHERE w.window_set_id = ? GROUP BY r.source_file", (row["id"],)):
        out[str(sf)] = int(n or 0)
    if not out:
        for sf, n in c.execute("SELECT r.source_file, COUNT(*) FROM window_set_members m JOIN recordings r "
                               "ON r.id = m.recording_id WHERE m.window_set_id = ? GROUP BY r.source_file", (row["id"],)):
            out[str(sf)] = int(n or 0)
    return out


@router.get("/api/windowsets/library")
def windowset_library(request: Request):
    """Every saved window set, as the Window pool block lists them."""
    from Adapters.registry import discover_adapters, get_adapter
    from Working.training import pool as tpool
    discover_adapters()
    spec = get_adapter("preprocessing.window_pool")
    c = _conn(request)
    try:
        out = []
        for s in tpool.list_sets(c):
            if HELD_OUT_FILE in (s.get("source_files") or []):
                continue
            row = c.execute("SELECT * FROM window_sets WHERE id = ?", (s["id"],)).fetchone()
            try:
                cov = json.loads(row["coverage_json"] or "{}") or {}
            except (TypeError, ValueError):
                cov = {}
            n_ch = c.execute("SELECT COUNT(*) FROM window_set_channels WHERE window_set_id = ?", (s["id"],)).fetchone()[0] \
                or c.execute("SELECT COUNT(*) FROM window_set_members WHERE window_set_id = ?", (s["id"],)).fetchone()[0] \
                or (1 if row["recording_id"] is not None else 0)
            out.append({**{k: s[k] for k in ("id", "name", "version", "kind", "scale_min", "scales_min", "n_windows",
                                             "source_files", "key", "created_at")},
                        "n_channels": int(n_ch), "per_recording": _per_recording(c, row),
                        "counts": cov.get("counts"), "hold_out_pack": cov.get("hold_out_pack"),
                        "labels_source": row["labels_source"], "rule": cov.get("rule"),
                        "dropped": cov.get("dropped")})
    finally:
        c.close()
    defaults = {p.name: p.default for p in spec.params}
    return {"sets": out, "defaults": defaults, "rules": tpool.RULES, "packs": {k: [c + 1 for c in v] for k, v in tpool.PACKS.items()},
            "note": ("tick the sets to combine; the first listed wins a duplicate or an overlap. Library › Window sets "
                     "› New window set makes more.")}
