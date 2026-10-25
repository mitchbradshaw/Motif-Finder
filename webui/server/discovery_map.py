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
  worker process — see `overview` and `_Cache`.
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


# ── one stale-while-revalidate cache for every view (tq-mapcache, 2026-10-25) ──
#
# The overview (map-overview-cache, 2026-10-20) and levels 2 and 1 (site-map, 2026-10-20) kept a hand-written copy
# each of one algorithm, and the copies had drifted; `_Cache` is that algorithm once. A read fingerprints what the
# overview reads (`detection_map.overview_fingerprint`, which every level reads too; `_fingerprint` skips it while
# SQLite's change counter stands) and answers the view held for that state; else the last one held marked
# ``stale`` with ``stale_since`` (when the newer state was first seen) and ONE recompute scheduled off the request
# (single flight per view), throttled to one per `RUNNING_GAP_S` while a Discovery run is going; a recorded failure
# raises `MapFailed` until the fingerprint moves. While a view's recompute is in flight a read does not fingerprint
# (~0.5 s on the real database, and the page polls every 5 s): it answers the view held, marked stale.
#
# What differs between the two caches is a parameter, not a copy:
#
# * the overview's first miss answers ``pending`` (the page shows "counting…"); a level's computes on the request,
#   so a page never waits on a "pending" it does not know — and a level dropped from the cache while its recompute
#   is in flight waits for that recompute (one flight per view) instead of computing a second time beside it;
# * the overview recomputes in the bridge's one worker process (`worker.run_in_worker`, the pool the corpus maps
#   use: 17–21 s per read on the real database) and is kept on disk under `<runtime root>/cache/map/`
#   (`corpus.disk_write`); a level recomputes on a thread (one level-2 read takes ~1-3 s, and queueing it behind a
#   corpus-map warm of minutes would make the first open slower than computing it here), memory only, a restart
#   recounts on first read;
# * the overview is deep-copied out (a read keys and sorts its datasets in place); a level shallowly (a read only adds
#   top-level keys, and a deep copy of a 1 h level-1 payload cost ~0.2 s);
# * the overview says ``running: true`` while a Discovery run is going; the levels never did;
# * the levels are bounded by their summed JSON size and dropped least recently read first (`LEVEL_CACHE_BYTES`).

class MapFailed(RuntimeError):
    """The last recompute of a view failed. A read raises it with the sentence (the app's loud handler makes it a 500
    the page shows as a red card) — never a blank map, never the old one passed off as current."""


#: while a Discovery run is going its runs write as they go, so every poll sees a new state; after one recompute
#: lands the next is scheduled no sooner than this (the view is marked stale meanwhile)
RUNNING_GAP_S = 30.0


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class _Cache:
    """One stale-while-revalidate cache of map views, as the comment above says. `copy` copies a held view out;
    `disk` is corpus's disk-cache kind (None: memory only); `bound()` gives ``(max JSON bytes, max views)`` (None:
    unbounded); `mark_running` adds ``running: true`` while a Discovery run is going. The recompute runs on a thread
    named ``discovery-map-<name>``."""

    def __init__(self, name, *, copy, disk=None, bound=None, mark_running=False):
        self.name, self.copy, self.disk, self.bound, self.mark_running = name, copy, disk, bound, mark_running
        self.lock = threading.Lock()
        self.idle = threading.Event()
        self.idle.set()
        self.flight = worker.OneFlight()
        self.in_flight: dict = {}           # key -> the fingerprint its recompute was scheduled for
        self.clear()

    def clear(self):
        """Forget everything held in memory (the disk copies stay); a recompute in flight still lands."""
        self.held: OrderedDict = OrderedDict()   # key -> (fingerprint, view), least recently read first
        self.sizes: dict = {}
        self.bytes = 0
        self.errors: dict = {}              # key -> (fingerprint whose recompute failed, the sentence)
        self.first_seen: dict = {}          # key -> (fingerprint, when that state was first seen)
        self.done_at: dict = {}             # key -> when its last recompute ended (monotonic)
        self.scheduled = self.computed = self.failed = 0
        self.mode = self.stored = None

    def read(self, key, fingerprint, running: bool, compute, what: str, pending=None) -> dict:
        """The view for `key`, as the comment above says. `fingerprint()` digests the current state; `compute()`
        returns ``(fingerprint read, view)`` and raises what the core raises; `pending()` is the first-miss answer
        (None: compute on the request); `what` names the view in the log and in a failure's sentence."""
        with self.lock:
            busy = key in self.in_flight
        if busy:
            hit = self._held(key)
            if hit is not None or pending is not None:
                return self._behind(key, hit, running, None, pending)
        fp = fingerprint()
        hit = self._held(key)
        if hit is not None and hit[0] == fp:
            out = self.copy(hit[1])
            if running and self.mark_running:
                out.update(stale=True, stale_since=self._since(key, fp), running=True)
            return out
        with self.lock:
            failed = self.errors.get(key)
            done_at = self.done_at.get(key)
        if failed is not None and failed[0] == fp:
            raise MapFailed(failed[1])
        if hit is None and pending is None:
            with self.flight(key):          # a recompute of this view in flight lands first
                hit = self._held(key)
                if hit is not None and hit[0] == fp:
                    return self.copy(hit[1])
                got_fp, out = compute()
                self._keep(key, got_fp, out)
            return self.copy(out)
        since = self._since(key, fp)
        if not (running and done_at is not None and time.monotonic() - done_at < RUNNING_GAP_S):
            self._schedule(key, fp, compute, what)
        return self._behind(key, hit, running, since, pending)

    def _held(self, key):
        """`(fingerprint, view)` held for `key`: memory, else the copy on disk (then kept in memory); or None."""
        with self.lock:
            hit = self.held.get(key)
            if hit is not None:
                self.held.move_to_end(key)
        if hit is None and self.disk:
            got = corpus.disk_read_any(key, self.disk)
            if got is not None:
                with self.lock:
                    hit = self.held.setdefault(key, tuple(got))
        return hit

    def _behind(self, key, hit, running, since, pending) -> dict:
        """The view held, marked stale; else the first-miss answer."""
        if hit is None:
            return pending()
        with self.lock:
            seen = self.first_seen.get(key)
        out = self.copy(hit[1])
        out.update(stale=True, stale_since=since or (seen[1] if seen is not None else _now()))
        if running and self.mark_running:
            out["running"] = True
        return out

    def _since(self, key, fp) -> str:
        """When the state `fp` names was first seen for `key` (UTC, ISO 8601)."""
        with self.lock:
            seen = self.first_seen.get(key)
            if seen is None or seen[0] != fp:
                seen = self.first_seen[key] = (fp, _now())
            return seen[1]

    def _keep(self, key, fp, out):
        if fp is None:                      # the database changed while it was read: not kept, the next read recounts
            return
        size = len(json.dumps(out, separators=(",", ":"))) if self.bound else 0
        if self.disk:
            corpus.disk_write(key, fp, out, self.disk)
        with self.lock:
            self.computed += 1
            self.stored = fp
            self.errors.pop(key, None)
            self._drop_locked(key)
            limit, most = self.bound() if self.bound else (None, None)
            if limit is not None and size > limit:     # larger than the whole budget: served, not kept
                return
            self.held[key] = (fp, out)
            self.sizes[key] = size
            self.bytes += size
            while limit is not None and self.held and (self.bytes > limit or len(self.held) > most):
                self._drop_locked(next(iter(self.held)))

    def _drop_locked(self, key):
        if self.held.pop(key, None) is not None:
            self.bytes -= self.sizes.pop(key, 0)

    def _schedule(self, key, fp, compute, what):
        with self.lock:
            if key in self.in_flight:
                return
            self.in_flight[key] = fp
            self.scheduled += 1
            self.idle.clear()
        threading.Thread(target=self._recompute, args=(key, fp, compute, what), daemon=True,
                         name=f"discovery-map-{self.name}").start()

    def _recompute(self, key, asked_fp, compute, what):
        """One recompute off the request. The view is kept under the fingerprint the compute READ; whatever it
        raises is recorded as the failure a read then raises."""
        log = logging.getLogger("webui.discovery_map")
        t0 = time.perf_counter()
        try:
            with self.flight(key):
                got_fp, out = compute()
                self._keep(key, got_fp, out)
            if got_fp is None:
                log.info("%s: the database changed while it was computed; not kept, the next read schedules it", what)
            else:
                log.info("%s recomputed (%.1f s)", what, time.perf_counter() - t0)
        except worker.Stopped:
            log.info("%s abandoned: the worker was stopped", what)
        except BaseException as exc:            # noqa: B902 - recorded, never swallowed into a blank
            sentence = f"{what} could not be computed: {type(exc).__name__}: {exc}"
            log.error("%s", sentence, exc_info=(type(exc), exc, exc.__traceback__))
            with self.lock:
                self.errors[key] = (asked_fp, sentence)
                self.failed += 1
        finally:
            with self.lock:
                self.in_flight.pop(key, None)
                self.done_at[key] = time.monotonic()
                if not self.in_flight:
                    self.idle.set()

    def reset(self, timeout: float):
        """Tests: wait out a recompute in flight, then forget everything held in memory (the disk copies stay)."""
        self.idle.wait(timeout)
        close_probe()
        with self.lock:
            self.clear()


#: views kept, least recently read dropped first, bounded by their summed JSON size (critic, site-map fix round: on
#: the real database a 1 h level-1 timeline of M2_aug is ~2.9 MB of JSON, ~10 MB in memory, and level 2 x8 ~5 MB in
#: memory — a count cap of 48 could reach hundreds of MB on a box with ~1 GB free). Memory is ~3-4x the JSON size, so
#: 16 MB of JSON is roughly 50-60 MB held. A view larger than the whole budget is served and not kept.
LEVEL_CACHE_BYTES = 16_000_000
LEVEL_CACHE_MAX = 48

_OVERVIEW = _Cache("overview", copy=copy.deepcopy, disk="map", mark_running=True)
_LEVELS = _Cache("level", copy=dict, bound=lambda: (LEVEL_CACHE_BYTES, LEVEL_CACHE_MAX))


def _exclude(conn) -> tuple:
    return tuple(_held_out_files(conn))


def _compute_here(db_path, exclude):
    """The thread fallback (no worker process): the same core call the worker makes."""
    return DM.compute(db_path, exclude)


def overview(conn, db_path: str) -> dict:
    """The overview (`detection_map.dataset_map`), keyed and ordered, answered at once:

    * the overview held for the database's current state (memory, else disk): fresh, no marker;
    * else the last overview held, ``stale: true`` with ``stale_since``, and a recompute scheduled in the worker;
      ``pending: true`` with empty layers when there has never been one (the page shows its "counting…" line, never
      zeros drawn as counts);
    * while a Discovery run is going, ``stale: true`` and ``running: true`` whatever the state, and a recompute at
      most every `RUNNING_GAP_S`;
    * `MapFailed` when the last recompute of the current state failed."""
    exclude = _exclude(conn)

    def compute():
        mode, (fp, out) = worker.run_in_worker(DM.compute, db_path, exclude, what="the Discovery map overview",
                                               fallback=lambda: _compute_here(db_path, exclude))
        if fp is not None:
            _OVERVIEW.mode = mode
        return fp, out
    out = _OVERVIEW.read(("overview", exclude), lambda: _fingerprint(conn, db_path, exclude), DM.any_running(conn),
                         compute, "the Discovery map overview",
                         pending=lambda: {"rows": [], "datasets": [], "withoutRuns": [],
                                          "heldOutOmitted": list(exclude), "pending": True})
    return out if out.get("pending") else _keyed(conn, out)


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


def map_status() -> dict:
    """What the overview's recompute is doing: in flight, scheduled / computed / failed so far, where the last one
    ran ("process" / "thread") and the fingerprint the last stored overview was read under."""
    with _OVERVIEW.lock:
        return {"in_flight": list(_OVERVIEW.in_flight), "scheduled": _OVERVIEW.scheduled,
                "computed": _OVERVIEW.computed, "failed": _OVERVIEW.failed, "mode": _OVERVIEW.mode,
                "stored": _OVERVIEW.stored}


def wait_map_idle(timeout: float | None = None) -> bool:
    """Block until no recompute of the overview is in flight (tests). True when idle."""
    return _OVERVIEW.idle.wait(timeout)


def reset_map_cache(timeout: float = 120.0):
    """Tests: wait out a recompute in flight, then forget every overview held in memory (the disk copies stay)."""
    _OVERVIEW.reset(timeout)


def level_status() -> dict:
    with _LEVELS.lock:
        return {"held": len(_LEVELS.held), "bytes": _LEVELS.bytes, "in_flight": len(_LEVELS.in_flight),
                "scheduled": _LEVELS.scheduled, "computed": _LEVELS.computed}


def wait_levels_idle(timeout: float | None = None) -> bool:
    """Block until no level recompute is in flight (tests). True when idle."""
    return _LEVELS.idle.wait(timeout)


def reset_level_cache(timeout: float = 120.0):
    """Tests: wait out a recompute in flight, then forget every view held."""
    _LEVELS.reset(timeout)


@router.get("/api/discovery/map/dataset")
def get_map_dataset(request: Request, recording: str, chunks: int = 1):
    c = _conn(request)
    try:
        rec = _file_for_key(c, recording)
        _refuse_held_out(c, rec["source_file"])
        if chunks not in DM.CHUNK_OPTIONS:
            raise HTTPException(422, {"message": f"chunks must be one of {list(DM.CHUNK_OPTIONS)}, not {chunks}"})
        t0 = time.perf_counter()
        m = _level(c, request.app.state.rt.db_path, "dataset", DM.channel_map, rec["source_file"], chunks=chunks)
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
            m = _level(c, request.app.state.rt.db_path, "channel", DM.timeline_map, rec["source_file"],
                       channel=channel, bin_h=float(binH))
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


def _level(conn, db_path, level: str, view, source_file, **args) -> dict:
    """The level-2 (`detection_map.channel_map`) or level-1 (`timeline_map`) payload for one view — (level,
    recording, chunks) or (level, recording, channel, bin) — through `_LEVELS` (see the cache's comment): computed on
    the request on a first read, raising what the core raises there (KeyError for a channel the recording lacks);
    `MapFailed` when the last off-request recompute of this view failed on the current state. Both levels were
    computed on every read before site-map: 6.1-6.8 s (level 2) and 1.3-3.5 s (level 1) on a copy of the real
    database, the bridge holding the GIL meanwhile."""
    exclude = _exclude(conn)
    return _LEVELS.read((level, source_file, tuple(sorted(args.items())), exclude),
                        lambda: _fingerprint(conn, db_path, exclude), DM.any_running(conn),
                        lambda: DM.compute(db_path, exclude, view, source_file, **args),
                        f"the Discovery map's {level} level")
