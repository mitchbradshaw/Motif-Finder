"""Discovery › Map — the detection map's three reads (2026-10-12).

Thin over `Working.discovery.detection_map`, which counts; this module names
datasets (`corpus.dataset_name`), orders them as the rest of the app does,
refuses the held-out file while Settings › Datasets' lock is on (a2-p1: read per
request) and says which session is open, so the client knows which cells the
Runs browser can show. Nothing numerical is computed here.

* `GET /api/discovery/map` — level 3: every dataset with a live Discovery
  run, all its channels, one cell per row and channel; `withoutRuns` and
  `heldOutOmitted` say what is not drawn and why. **A read never computes**
  (map-overview-cache, 2026-10-20: 17–21 s per read on the real database): it
  answers the last overview at once and the recompute runs in the bridge's one
  worker process — see `overview`.
* `GET /api/discovery/map/dataset?recording=&chunks=` — level 2: one
  dataset's channels, each in 1, 2, 4 or 8 equal time slices.
* `GET /api/discovery/map/channel?recording=&channel=&binH=` — level 1: one
  channel over the whole recording in `binH`-hour bins, with the covered
  fraction of every bin.
"""
from __future__ import annotations

import copy
import json
from collections import OrderedDict
import logging
import threading
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from Working.discovery import detection_map as DM

from . import corpus, worker
from .discovery import _conn, _file_for_key, _refuse_held_out, _session, _stem
from .runtime import HELD_OUT_FILE

router = APIRouter()


def _held_out_files(conn) -> list:
    """The files the map leaves out: the held-out one while the lock is on, none
    once it is off (a2-p1). Read per request, never at import."""
    return [HELD_OUT_FILE] if corpus.held_out_locked(conn) else []


def _session_bit(conn):
    """The open session and its scope: the client opens the Runs browser from a
    level-1 bin only inside it, because the browser reads nothing outside it."""
    s = _session(conn)
    # map-overview-cache: one row's rate, not `_file_for_key`'s whole recordings listing (~0.2 s of every map read)
    hit = conn.execute("SELECT fs FROM recordings WHERE source_file = ? ORDER BY channel LIMIT 1",
                       (s["source_file"],)).fetchone()
    fs = float(hit[0]) if hit is not None else float(_file_for_key(conn, _stem(s["source_file"]))["fs"])
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
    t0 = time.perf_counter()        # the read's own time: not the connection, nor the first request's schema check
    try:
        m = overview(c, request.app.state.rt.db_path)
        m["session"] = _session_bit(c)
        m["read_ms"] = (time.perf_counter() - t0) * 1e3
        return m
    finally:
        c.close()


# ── the overview off the request (map-overview-cache, 2026-10-20) ───────────
#
# The corpus map's pattern (`corpus.coverage`, corpus-map-off-the-request): the read fingerprints what the overview
# reads (`detection_map.overview_fingerprint`) and answers the overview held for that state — memory, else the copy
# under `<runtime root>/cache/map/` — or the last one marked stale, or `pending` when there has never been one, and
# schedules ONE recompute in the worker process the corpus maps use (`worker.run_in_worker`: there is one pool).

class MapFailed(RuntimeError):
    """The last recompute of the overview failed. A read raises it with the sentence (the app's loud handler makes it
    a 500 the page shows as a red card) — never a blank map, never the old one passed off as current."""


#: while a Discovery run is going its runs write as they go, so every poll sees a new state; after one recompute
#: lands the next is scheduled no sooner than this (the overview is marked stale + running meanwhile)
RUNNING_GAP_S = 30.0

_STATE = {"cache": {}, "errors": {}, "first_seen": {}, "done_at": {}, "in_flight": {}, "scheduled": 0, "computed": 0,
          "failed": 0, "mode": None, "stored": None}
_LOCK = threading.Lock()
_IDLE = threading.Event()
_IDLE.set()


def _exclude(conn) -> tuple:
    return tuple(_held_out_files(conn))


def _compute_here(db_path, exclude):
    """The thread fallback (no worker process): the same core call the worker makes."""
    return DM.compute(db_path, exclude)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def overview(conn, db_path: str) -> dict:
    """The overview (`detection_map.dataset_map`), keyed and ordered, answered at once:

    * the overview held for the database's current state (memory, else disk): fresh, no marker;
    * else the last overview held, ``stale: true`` with ``stale_since`` (when the newer state was first seen), and a
      recompute scheduled; ``pending: true`` with empty layers when there has never been one (the page shows its
      "counting…" line, never zeros drawn as counts);
    * while a Discovery run is going, ``stale: true`` and ``running: true`` whatever the state, and a recompute at
      most every `RUNNING_GAP_S`;
    * `MapFailed` when the last recompute of the current state failed.

    While a recompute is in flight a read does not fingerprint (each costs ~0.5 s on the real database and the page
    polls every 5 s): it answers the last overview marked stale. The read after the recompute lands fingerprints as
    usual, so a change made meanwhile is noticed and recomputed."""
    exclude = _exclude(conn)
    key = ("overview", exclude)
    running = DM.any_running(conn)
    with _LOCK:
        busy = key in _STATE["in_flight"]
    if busy:
        return _behind(conn, key, exclude, running, None)
    fp = _fingerprint(conn, db_path, exclude)
    hit = _held(key)
    if hit is not None and hit[0] == fp:
        out = _keyed(conn, copy.deepcopy(hit[1]))
        if running:
            out.update(stale=True, stale_since=_stale_since(key, fp), running=True)
        return out
    with _LOCK:
        failed = _STATE["errors"].get(key)
        done_at = _STATE["done_at"].get(key)
    if failed is not None and failed[0] == fp:
        raise MapFailed(failed[1])
    since = _stale_since(key, fp)
    if not (running and done_at is not None and time.monotonic() - done_at < RUNNING_GAP_S):
        _schedule(key, fp, db_path, exclude)
    return _behind(conn, key, exclude, running, since)


#: the last fingerprint and the database's change counter when it was taken, read on a connection of this module's
#: own: SQLite's `PRAGMA data_version` moves when any OTHER connection commits, so while it stands the database is
#: unchanged and the fingerprint (~0.5 s on the real database) need not be taken again
_PROBE = {"conn": None, "path": None, "version": None, "fp": None, "exclude": None}
_PROBE_LOCK = threading.Lock()


def _fingerprint(conn, db_path, exclude) -> str:
    """`detection_map.overview_fingerprint`, skipped while nothing has been committed to the database since the last
    one. The counter is read before the fingerprint, so a write landing between the two only costs a fingerprint."""
    with _PROBE_LOCK:
        if _PROBE["conn"] is None or _PROBE["path"] != db_path:
            _close_probe_locked()
            _PROBE.update(conn=corpus.connect(db_path), path=db_path)
        version = _PROBE["conn"].execute("PRAGMA data_version").fetchone()[0]
        if version == _PROBE["version"] and exclude == _PROBE["exclude"] and _PROBE["fp"] is not None:
            return _PROBE["fp"]
    fp = DM.overview_fingerprint(conn, exclude)
    with _PROBE_LOCK:
        if _PROBE["path"] == db_path:
            _PROBE.update(version=version, fp=fp, exclude=exclude)
    return fp


def _close_probe_locked():
    if _PROBE["conn"] is not None:
        try:
            _PROBE["conn"].close()
        except Exception:
            pass
    _PROBE.update(conn=None, path=None, version=None, fp=None, exclude=None)


def close_probe():
    """Close the change-counter connection (the runtime's `restore()`, through `worker.shutdown`, so
    the sandbox copy can be removed; tests)."""
    with _PROBE_LOCK:
        _close_probe_locked()


worker.on_stop(close_probe)


def _held(key):
    """`(fingerprint, overview)` held for `key`: memory, else the copy on disk (then kept in memory); or None."""
    with _LOCK:
        hit = _STATE["cache"].get(key)
    if hit is None:
        held = corpus._disk_read_any(key, "map")
        if held is not None:
            with _LOCK:
                hit = _STATE["cache"].setdefault(key, tuple(held))
    return hit


def _behind(conn, key, exclude, running, since) -> dict:
    """The last overview held for `key`, marked stale; else the empty shape marked pending."""
    hit = _held(key)
    if hit is None:
        return {"rows": [], "datasets": [], "withoutRuns": [], "heldOutOmitted": list(exclude), "pending": True}
    with _LOCK:
        seen = _STATE["first_seen"].get(key)
    out = _keyed(conn, copy.deepcopy(hit[1]))
    out["stale"] = True
    out["stale_since"] = since or (seen[1] if seen is not None else _now())
    if running:
        out["running"] = True
    return out


def _stale_since(key, fp) -> str:
    """When the state `fp` names was first seen for `key` (UTC, ISO 8601)."""
    with _LOCK:
        seen = _STATE["first_seen"].get(key)
        if seen is None or seen[0] != fp:
            seen = _STATE["first_seen"][key] = (fp, _now())
        return seen[1]


def _schedule(key, fp, db_path, exclude) -> bool:
    """Start the recompute of `key` unless one is already in flight (single flight: one at a time per key)."""
    with _LOCK:
        if key in _STATE["in_flight"]:
            return False
        _STATE["in_flight"][key] = fp
        _STATE["scheduled"] += 1
        _IDLE.clear()
    threading.Thread(target=_recompute, args=(key, fp, db_path, exclude), daemon=True,
                     name="discovery-map-overview").start()
    return True


def _recompute(key, asked_fp, db_path, exclude):
    """One recompute, in the worker process (else on this thread). The overview is kept, in memory and on disk,
    under the fingerprint the WORKER read; whatever it raises is recorded as the failure a read then raises."""
    log = logging.getLogger("webui.discovery_map")
    t0 = time.perf_counter()
    try:
        mode, (fp, out) = worker.run_in_worker(DM.compute, db_path, exclude, what="the Discovery map overview",
                                               fallback=lambda: _compute_here(db_path, exclude))
        if fp is None:
            log.info("map overview: the database changed while it was computed; not kept, the next read schedules it")
        else:
            corpus._disk_write(key, fp, out, "map")
            with _LOCK:
                _STATE["cache"][key] = (fp, out)
                _STATE["errors"].pop(key, None)
                _STATE["computed"] += 1
                _STATE["mode"] = mode
                _STATE["stored"] = fp
            log.info("map overview recomputed (%.1f s, in a %s)", time.perf_counter() - t0, mode)
    except worker.Stopped:
        log.info("map overview abandoned: the worker was stopped")
    except BaseException as exc:            # noqa: B902 - recorded, never swallowed into a blank
        sentence = f"the Discovery map overview could not be computed: {type(exc).__name__}: {exc}"
        log.error("%s", sentence, exc_info=(type(exc), exc, exc.__traceback__))
        with _LOCK:
            _STATE["errors"][key] = (asked_fp, sentence)
            _STATE["failed"] += 1
    finally:
        with _LOCK:
            _STATE["in_flight"].pop(key, None)
            _STATE["done_at"][key] = time.monotonic()
            if not _STATE["in_flight"]:
                _IDLE.set()


def map_status() -> dict:
    """What the overview's recompute is doing: in flight, scheduled / computed / failed so far, where the last one
    ran ("process" / "thread") and the fingerprint the last stored overview was read under."""
    with _LOCK:
        return {"in_flight": list(_STATE["in_flight"]), "scheduled": _STATE["scheduled"],
                "computed": _STATE["computed"], "failed": _STATE["failed"], "mode": _STATE["mode"],
                "stored": _STATE["stored"]}


def wait_map_idle(timeout: float | None = None) -> bool:
    """Block until no recompute is in flight (tests). True when idle."""
    return _IDLE.wait(timeout)


def reset_map_cache(timeout: float = 120.0):
    """Tests: wait out a recompute in flight, then forget everything held in memory (the disk copies stay)."""
    wait_map_idle(timeout)
    close_probe()
    with _LOCK:
        for k in ("cache", "errors", "first_seen", "done_at"):
            _STATE[k].clear()
        _STATE.update(scheduled=0, computed=0, failed=0, mode=None, stored=None)


@router.get("/api/discovery/map/dataset")
def get_map_dataset(request: Request, recording: str, chunks: int = 1):
    c = _conn(request)
    try:
        rec = _file_for_key(c, recording)
        _refuse_held_out(c, rec["source_file"])
        if chunks not in DM.CHUNK_OPTIONS:
            raise HTTPException(422, {"message": f"chunks must be one of {list(DM.CHUNK_OPTIONS)}, not {chunks}"})
        t0 = time.perf_counter()
        m = _level(c, request.app.state.rt.db_path, "dataset", rec["source_file"], {"chunks": chunks})
        m["key"] = _stem(rec["source_file"])
        m["session"] = _session_bit(c)
        m["read_ms"] = (time.perf_counter() - t0) * 1e3
        # plain JSON: FastAPI's jsonable_encoder walked a 1 h level-1 payload (2.6 MB) in ~0.3 s
        return JSONResponse(m)
    finally:
        c.close()


@router.get("/api/discovery/map/channel")
def get_map_channel(request: Request, recording: str, channel: str, binH: float = 3.0):
    c = _conn(request)
    try:
        rec = _file_for_key(c, recording)
        _refuse_held_out(c, rec["source_file"])
        if not binH > 0:
            raise HTTPException(422, {"message": f"binH must be a positive number of hours, not {binH}"})
        t0 = time.perf_counter()
        try:
            m = _level(c, request.app.state.rt.db_path, "channel", rec["source_file"], {"channel": channel, "bin_h": float(binH)})
        except KeyError as e:
            raise HTTPException(404, {"message": str(e.args[0]) if e.args else "no such channel",
                                      "channels": [ch["name"] for ch in rec["channels"]]})
        m["key"] = _stem(rec["source_file"])
        m["session"] = _session_bit(c)
        m["read_ms"] = (time.perf_counter() - t0) * 1e3
        # plain JSON: FastAPI's jsonable_encoder walked a 1 h level-1 payload (2.6 MB) in ~0.3 s
        return JSONResponse(m)
    finally:
        c.close()


# ── levels 2 and 1, kept per view (site-map, 2026-10-20) ────────────────────
#
# Both were computed on every read: on a copy of the real database level 2 took 6.1-6.8 s per read and level 1
# 1.3-3.5 s, the bridge holding the GIL meanwhile. Each view — (level, recording, chunks) or (level, recording,
# channel, bin) — is now kept under the overview's fingerprint (both levels read the rows the overview reads), which
# `_fingerprint` skips while SQLite's change counter stands. A read of a view held for the current state answers from
# memory; a view held for an older state is answered at once marked ``stale`` and recomputed once, off the request, on
# a thread (its own read-only connection, `detection_map.compute_level`); a view never seen is computed on the request,
# as before, so a page never has to wait on a "pending" it does not know. Memory only: a restart recounts on first read.
# Not the worker process the overview and corpus maps use: one level-2 read takes ~1-3 s, and queueing it behind a
# corpus-map warm of minutes would make the first open slower than computing it here.

#: views kept, least recently read dropped first, bounded by their summed JSON size (critic, site-map fix round: on
#: the real database a 1 h level-1 timeline of M2_aug is ~2.9 MB of JSON, ~10 MB in memory, and level 2 x8 ~5 MB in
#: memory — a count cap of 48 could reach hundreds of MB on a box with ~1 GB free). Memory is ~3-4x the JSON size, so
#: 16 MB of JSON is roughly 50-60 MB held. A view larger than the whole budget is served and not kept.
LEVEL_CACHE_BYTES = 16_000_000
LEVEL_CACHE_MAX = 48

_LV = {"cache": OrderedDict(), "sizes": {}, "bytes": 0, "errors": {}, "first_seen": {}, "done_at": {},
       "in_flight": set(), "scheduled": 0, "computed": 0}
_LV_LOCK = threading.Lock()
_LV_IDLE = threading.Event()
_LV_IDLE.set()


def _level(conn, db_path, level, source_file, args) -> dict:
    """The level-2 or level-1 payload for one view, as the module comment says. Raises what the core raises
    (KeyError for a channel the recording lacks) on the request; `MapFailed` when the last off-request recompute of
    this view failed on the current state."""
    exclude = _exclude(conn)
    key = (level, source_file, tuple(sorted(args.items())), exclude)
    with _LV_LOCK:
        busy = key in _LV["in_flight"]
        held = _LV["cache"].get(key)
        seen = _LV["first_seen"].get(key)
    if busy and held is not None:
        # a recompute of this view is in flight: answer the held view marked stale without fingerprinting (~0.5 s
        # on the real database, and the page polls every 5 s during a run), as `overview` does
        out = dict(held[1])
        out.update(stale=True, stale_since=seen[1] if seen is not None else _now())
        return out
    fp = _fingerprint(conn, db_path, exclude)
    with _LV_LOCK:
        hit = _LV["cache"].get(key)
        if hit is not None:
            _LV["cache"].move_to_end(key)
        failed = _LV["errors"].get(key)
    # shallow copies: a read only adds top-level keys (key, session, read_ms, stale); the cells are never written
    # (a deep copy of a 1 h level-1 payload cost ~0.2 s)
    if hit is not None and hit[0] == fp:
        return dict(hit[1])
    if failed is not None and failed[0] == fp:
        raise MapFailed(failed[1])
    if hit is not None:
        with _LV_LOCK:
            seen = _LV["first_seen"].get(key)
            if seen is None or seen[0] != fp:
                seen = _LV["first_seen"][key] = (fp, _now())
            done_at = _LV["done_at"].get(key)
        if not (done_at is not None and time.monotonic() - done_at < RUNNING_GAP_S and DM.any_running(conn)):
            _schedule_level(key, fp, db_path, level, source_file, args, exclude)
        out = dict(hit[1])
        out.update(stale=True, stale_since=seen[1])
        return out
    got_fp, out = DM.compute_level(db_path, level, source_file, args, exclude)
    _keep_level(key, got_fp, out)
    return dict(out)


def _keep_level(key, fp, out):
    if fp is None:                      # the database changed while it was read: not kept, the next read recounts
        return
    size = len(json.dumps(out, separators=(",", ":")))
    with _LV_LOCK:
        _LV["computed"] += 1
        _LV["errors"].pop(key, None)
        _drop_level_locked(key)
        if size > LEVEL_CACHE_BYTES:
            return
        _LV["cache"][key] = (fp, out)
        _LV["sizes"][key] = size
        _LV["bytes"] += size
        while _LV["cache"] and (_LV["bytes"] > LEVEL_CACHE_BYTES or len(_LV["cache"]) > LEVEL_CACHE_MAX):
            _drop_level_locked(next(iter(_LV["cache"])))


def _drop_level_locked(key):
    if _LV["cache"].pop(key, None) is not None:
        _LV["bytes"] -= _LV["sizes"].pop(key, 0)


def _schedule_level(key, fp, db_path, level, source_file, args, exclude) -> bool:
    """One recompute of `key` off the request, unless one is in flight (single flight per view)."""
    with _LV_LOCK:
        if key in _LV["in_flight"]:
            return False
        _LV["in_flight"].add(key)
        _LV["scheduled"] += 1
        _LV_IDLE.clear()
    threading.Thread(target=_recompute_level, args=(key, fp, db_path, level, source_file, args, exclude), daemon=True,
                     name=f"discovery-map-level-{level}").start()
    return True


def _recompute_level(key, asked_fp, db_path, level, source_file, args, exclude):
    log = logging.getLogger("webui.discovery_map")
    t0 = time.perf_counter()
    try:
        got_fp, out = DM.compute_level(db_path, level, source_file, args, exclude)
        _keep_level(key, got_fp, out)
        log.info("map %s level recomputed for %s %s (%.1f s)", level, source_file, dict(args), time.perf_counter() - t0)
    except BaseException as exc:            # noqa: B902 - recorded, never swallowed into a blank
        sentence = f"the Discovery map's {level} level could not be computed: {type(exc).__name__}: {exc}"
        log.error("%s", sentence, exc_info=(type(exc), exc, exc.__traceback__))
        with _LV_LOCK:
            _LV["errors"][key] = (asked_fp, sentence)
    finally:
        with _LV_LOCK:
            _LV["in_flight"].discard(key)
            _LV["done_at"][key] = time.monotonic()
            if not _LV["in_flight"]:
                _LV_IDLE.set()


def level_status() -> dict:
    with _LV_LOCK:
        return {"held": len(_LV["cache"]), "bytes": _LV["bytes"], "in_flight": len(_LV["in_flight"]),
                "scheduled": _LV["scheduled"], "computed": _LV["computed"]}


def wait_levels_idle(timeout: float | None = None) -> bool:
    """Block until no level recompute is in flight (tests). True when idle."""
    return _LV_IDLE.wait(timeout)


def reset_level_cache(timeout: float = 120.0):
    """Tests: wait out a recompute in flight, then forget every view held."""
    wait_levels_idle(timeout)
    close_probe()
    with _LV_LOCK:
        for k in ("cache", "sizes", "errors", "first_seen", "done_at"):
            _LV[k].clear()
        _LV.update(bytes=0, scheduled=0, computed=0)
