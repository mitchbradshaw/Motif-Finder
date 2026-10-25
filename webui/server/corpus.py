"""Explore queries: recordings, coverage heatmap, spans in view, channel summaries.

Reads the **database copy** only; ``.npy`` channel files are memory-mapped
read-only from ``DATA/`` (through the worktree junction).
"""
from __future__ import annotations

import functools
import json
import logging
import os
import sqlite3
import threading
import time

import numpy as np

from Working.database import datasets as _datasets
from Working.database import queries as q
from Working.database import runs as r
from Working.database.runs import list_runs, load_recipe
from Working.database.schema import BUSY_TIMEOUT_S, VERDICTS
from Working.registration import settings as _settings
from Working.units import to_mv_factor

from . import worker
from .decimate import envelope
from .runtime import HELD_OUT_FILE

# The one electrode-name table, in the core (Working/discovery/channels.py) so
# Discovery's scope, fan-out and scoreboard call a channel what Explore calls
# it. A second copy here drifted from it within an hour of being written.
from Working.discovery import coverage_map as _CM
from Working.discovery import divergence as DIV
from Working.discovery import scoreboard as SB
from Working.discovery import spans as SPANS
from Working.discovery.channels import M2_STYLE_NAMES, channel_name as _core_channel_name

# VERDICTS is imported from Working.database.schema above — the one vocabulary,
# never a second copy (tests/test_webui_corpus.py pins it).


def connect(db_path: str) -> sqlite3.Connection:
    # fixup-dblock: wait for a background job's write as long as the core does
    # (`schema.BUSY_TIMEOUT_S`), not SQLite's default 5 s
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=BUSY_TIMEOUT_S)
    conn.row_factory = sqlite3.Row
    return conn


def channel_name(source_file: str, channel: int, n_channels: int) -> str:
    return _core_channel_name(source_file, channel, n_channels)


def dataset_name(conn, source_file: str) -> str:
    """What a dataset is CALLED, on every page and in every payload (fixup-f):
    its display name when Settings › Datasets gave it one, its source file when
    not. This is the bridge's one door to `Working.database.datasets.display_name`
    — no route formats a file name into a label itself. A name is a label, never
    a key; whatever carries it carries `source_file` beside it."""
    return _datasets.display_name(conn, source_file)


def dataset_names(conn) -> dict:
    """`source_file -> name` for every registered file, in one query."""
    return _datasets.display_names(conn)


# ── the held-out lock (a2-p1) ────────────────────────────────────────────────
#: How a refusal of the held-out recording says to unlock it — the core's own sentence.
HELD_OUT_UNLOCK_HINT = _settings.HELD_OUT_UNLOCK_HINT


def held_out_locked(conn) -> bool:
    """Settings › Datasets' held-out lock as it stands NOW: the core's one
    predicate (`Working.registration.settings.held_out_locked`), asked per
    request and never cached here, so turning the lock off or on takes effect on
    the next request with no bridge restart."""
    return _settings.held_out_locked(conn)


def is_held_out(conn, source_file) -> bool:
    """True when `source_file` is the held-out recording AND the lock is on —
    the bridge's one question before a 423 or a list exclusion. The file name is
    compared first, so any other recording costs no settings read."""
    return source_file == HELD_OUT_FILE and _settings.held_out_locked(conn)


def held_out_refusal(what: str) -> str:
    """The sentence a refusal carries while the lock is on: the file, what is
    refused, and how to unlock it."""
    return f"{HELD_OUT_FILE} is held out (spec §0 D6): {what} while the lock is on — {HELD_OUT_UNLOCK_HINT}"


@functools.lru_cache(maxsize=32)
def _mmap(npy_path: str, mtime_ns: int):
    return np.load(npy_path, mmap_mode="r")


def load_native(npy_path: str):
    """The stored samples, memory-mapped: what the CORE is handed (a detector,
    a seeded search, a chain window). Volts for a volts file — `detect5` and the
    drop-motif store multiply by 1000 themselves, so a converted array reaching
    them would print amplitudes 1000x too large. Never draw this: a page draws
    `display_channel(rec)`."""
    st = os.stat(npy_path)
    return _mmap(npy_path, st.st_mtime_ns)


class DisplayChannel:
    """A channel as a page draws it: millivolts when the recording declares its
    unit (`recordings.units`), the stored numbers with ``unit = None`` when it
    does not — so the page can say "unit undeclared" instead of "mV".

    This is the ONE place the bridge converts (fixup-b). Slicing returns a
    float64 array already in the display unit; `len()` is the channel's. The
    raw memmap stays inside: a stored-volts array and a millivolt array are
    never in circulation under the same name.
    """

    __slots__ = ("_raw", "factor", "unit", "declared")

    def __init__(self, raw, declared: str | None):
        self._raw = raw
        self.declared = declared
        f = to_mv_factor(declared)
        self.factor = 1.0 if f is None else f
        self.unit = "mV" if f is not None else None

    def __len__(self) -> int:
        return int(len(self._raw))

    def __getitem__(self, key):
        return np.asarray(self._raw[key], dtype=np.float64) * self.factor

    @property
    def shape(self):
        return (len(self),)


def _units_of(rec) -> str | None:
    """A recordings row's declared unit — from a dict or a `sqlite3.Row`."""
    if isinstance(rec, dict):
        return rec.get("units")
    return rec["units"] if "units" in rec.keys() else None


def display_channel(rec) -> DisplayChannel:
    """`rec` is a recordings row; its `units` decides the factor."""
    return DisplayChannel(load_native(rec["npy_path"]), _units_of(rec))


def display_unit(rec) -> str | None:
    """'mV' when the recording declares a unit the pages can convert, else None."""
    return "mV" if to_mv_factor(_units_of(rec)) is not None else None


def recordings(conn) -> list[dict]:
    # a soft-unregistered recording (recordings.active = 0, Settings › Datasets) is not offered anywhere
    rows = [dict(x) for x in q.list_recordings(conn) if dict(x).get("active", 1)]
    by_file: dict[str, list[dict]] = {}
    for row in rows:
        by_file.setdefault(row["source_file"], []).append(row)
    names, meta = dataset_names(conn), _datasets.list_datasets(conn)
    locked = held_out_locked(conn)          # a2-p1: once per read, from the settings row as it stands now
    out = []
    for sf, chans in by_file.items():
        chans.sort(key=lambda c: c["channel"])
        fs = float(chans[0]["fs"]); n = int(chans[0]["n_samples"])
        c0 = chans[0]
        parent = None
        if c0.get("parent_recording_id"):
            p = conn.execute("SELECT id, source_file, channel FROM recordings WHERE id = ?", (c0["parent_recording_id"],)).fetchone()
            if p is not None:
                parent = {"recording_id": p[0], "source_file": p[1], "channel": p[2], "offset": c0.get("parent_offset"), "decimation": c0.get("decimation")}
        out.append({
            "source_file": sf, "fs": fs, "n_samples": n, "duration_h": n / fs / 3600.0,
            # fixup-f: what the dataset is called (its display name, else the file), whether that is a
            # given name, the directory stem Settings keys by, and the identity Settings › Datasets authors
            "display_name": names.get(sf) or sf, "named": bool((meta.get(sf) or {}).get("display_name")),
            "stem": os.path.basename(os.path.dirname(c0["npy_path"])) or sf.rsplit(".", 1)[0],
            "dataset": {f: (meta.get(sf) or {}).get(f) for f in _datasets.FIELDS},
            # fixup-b: the unit the samples are stored in, and the one the pages draw them in
            "units": c0.get("units"), "units_note": c0.get("units_note"), "display_unit": display_unit(c0),
            # registration facts (stage-3 Prompt 02): where fs came from, the warnings the row carries, the excerpt link
            "fs_source": c0.get("fs_source") or "unrecorded",
            "warnings": json.loads(c0["warnings_json"]) if c0.get("warnings_json") else [],
            "excerpt_of": parent,
            "n_channels": len(chans), "held_out": sf == HELD_OUT_FILE and locked,
            "held_out_reason": (held_out_refusal("the bridge refuses every request for it and the pages never draw it")
                                if sf == HELD_OUT_FILE and locked else None),
            "channels": [{"id": c["id"], "channel": c["channel"],
                          "name": channel_name(sf, c["channel"], len(chans)),
                          "npy_exists": os.path.isfile(c["npy_path"])} for c in chans],
        })
    order = {"M2_aug_concat_fs1.mat": 0, "M2_aug_concat_fs2.mat": 1, "M2_concat_fs1.mat": 2}
    out.sort(key=lambda d: (order.get(d["source_file"], 9), d["source_file"]))
    return out


def recording_row(conn, recording_id: int) -> dict | None:
    row = q.get_recording_by_id(conn, recording_id)
    if row is None:
        return None
    d = dict(row)
    n_ch = conn.execute("SELECT COUNT(*) FROM recordings WHERE source_file = ?", (d["source_file"],)).fetchone()[0]
    d["name"] = channel_name(d["source_file"], d["channel"], n_ch)
    d["held_out"] = is_held_out(conn, d["source_file"])      # a2-p1: the lock as it stands now
    d["duration_s"] = d["n_samples"] / d["fs"]
    d["display_unit"] = display_unit(d)
    return d


#: Channel-absolute bounds for a detections row — the one rule, `Working.discovery.spans.absolute_bounds`
#: (span-plot: this was a second copy, though the core's docstring said it delegated). Rows written before
#: 2026-09-21 by a spanned run are span-relative; a start below the run's span_start marks one.
_absolute = SPANS.absolute_bounds


#: corpus-map-off-the-request: both moved to the core with the map (`Working.discovery.coverage_map`) so the worker
#: process can filter runs without importing the bridge; the names stay here for their readers (explore_routes, tests)
run_methods = _CM.run_methods
_runs_matching = _CM.runs_matching


#: (source_file, bins, verdicts, run_ids, method) -> (channels fingerprint, payload)
_COVERAGE_CACHE: dict = {}
_COVERAGE_CACHE_MAX = 64
#: ux-1018: one flight per cache key, so concurrent misses compute a map once (see `coverage`)
_COVERAGE_FLIGHT = worker.OneFlight()


class CoverageFailed(RuntimeError):
    """The last recompute of a corpus map failed. A read raises it with the sentence (the route's loud handler makes
    it a 500 the page shows as a red card) — never a blank, and never the old map passed off as current."""


def coverage(conn, source_file: str, bins: int = 57, verdicts: tuple | None = None,
             run_ids: list | None = None, method: str | None = None, db_path: str | None = None) -> dict:
    """channels × bins counts of annotation spans, detection spans, their SUM
    and 'disagree', plus per-channel summaries. `run_ids` / `method` restrict
    the detection layers to those runs.

    'disagree' is the divergence's two disagreement cells
    (`Working.discovery.divergence`, fixup-X): *machine yes · human no* (a
    detection a human rejected, or one inside reviewed windows that say no)
    plus *machine no · human yes* (a label a human said yes to where a run
    covered the place and found nothing). It used to be every annotation with
    no overlapping detection plus the reverse, whatever the verdict and
    whether or not any run had looked — 11,261 "disagreements" against 11,265
    annotations on M2_aug. A place no run covered, or no human reviewed, is
    *not comparable* and is counted beside the cells, never in them. With no
    run picked the divergence pools every run on the recording and
    `divergence.scope` says so. It reads every verdict: the verdict filter
    shapes the annotation layers, not what counts as a human yes or no.

    The `both` key is a sum, `annotations + detections`, NOT the bins where
    both are present — the map colours by total activity and that is what the
    number is for. It was named and documented as an intersection until
    fixup-a item 16; the name is kept (it is the payload contract the client
    reads) and every label that shows it now says what it is.

    Answered from memory while nothing on the recording's channels has changed
    (`scoreboard.channels_fingerprint`), else from the copy kept on disk.

    **With `db_path` (the route, the start-up warm): a read never computes** (corpus-map-off-the-request,
    2026-10-19: a recompute after any run took ~100 s on the post-RQ4 database, inside the request, and every other
    page stalled behind it). When the map for this question is not current the read answers at once with the LAST
    map it knows (memory, else disk), marked ``stale: true`` and ``stale_since`` (when the newer state was first
    seen), or — when no map was ever computed for the question — the map's shape with empty layers and
    ``pending: true``; and it schedules the recompute on the bridge's one worker process (`_schedule`). A fresh map
    carries neither marker and is the same map as before, cell for cell. When the last recompute of the current
    state failed, the read raises `CoverageFailed` with the reason.

    Without `db_path` (a library call on a connection: scripts, the core's tests, an in-memory database no worker
    could open) the map is computed in place on a miss, one flight per key, as before.

    `compute_ms` is this read's own time; `_coverage` is the computation."""
    import copy

    t0 = time.perf_counter()
    rec_ids = [int(x["id"]) for x in q.list_recordings(conn, source_file)]
    if not rec_ids:
        raise KeyError(source_file)
    # AR: the held-out answer is part of the map (`held_out`), so the lock's state is part of the key
    key = (source_file, int(bins), tuple(verdicts) if verdicts else None,
           tuple(int(i) for i in run_ids) if run_ids is not None else None, method,
           bool(is_held_out(conn, source_file)))
    # AR: only the settings the map reads (COVERAGE_SETTINGS). Memory compares the in-process digest (cheap); a miss
    # there computes the digest stable across restarts, which keys the copy kept on disk
    if db_path:
        behind = _while_queued(conn, key)
        if behind is not None:
            behind["compute_ms"] = (time.perf_counter() - t0) * 1e3
            return behind
    # corpus-map-off-the-request: one memo for both digests of this read, so the stable one (a miss in memory)
    # reuses the rows the in-process one already read instead of reading every channel's runs a second time
    memo = {}
    fp = SB.channels_fingerprint(conn, rec_ids, memo, settings_keys=COVERAGE_SETTINGS)
    hit = _COVERAGE_CACHE.get(key)
    if hit is not None and hit[0] == fp:
        out = copy.deepcopy(hit[1])
    elif db_path:
        out = _read_behind(conn, key, fp, rec_ids, db_path, memo)
    else:
        # ux-1018: one flight per key. The startup warm and a page's request for the same map used to compute it
        # side by side (two ~10 s divergences over M2_aug's 16 channels, competing for the GIL and SQLite); the
        # second reader now waits on the first and takes the entry it wrote.
        with _COVERAGE_FLIGHT(key):
            hit = _COVERAGE_CACHE.get(key)
            if hit is not None and hit[0] == fp:
                out = copy.deepcopy(hit[1])
            else:
                disk_fp = SB.channels_fingerprint(conn, rec_ids, memo, settings_keys=COVERAGE_SETTINGS, stable=True)
                out = _disk_read(key, disk_fp)
                if out is None:
                    out = _coverage(conn, source_file, bins=bins, verdicts=verdicts, run_ids=run_ids, method=method)
                    _disk_write(key, disk_fp, out)
                _remember(key, fp, out)
    out["compute_ms"] = (time.perf_counter() - t0) * 1e3
    return out


def _remember(key, fp, out):
    import copy
    if key not in _COVERAGE_CACHE and len(_COVERAGE_CACHE) >= _COVERAGE_CACHE_MAX:
        _COVERAGE_CACHE.pop(next(iter(_COVERAGE_CACHE)))
    _COVERAGE_CACHE[key] = (fp, copy.deepcopy(out))


def _read_behind(conn, key, fp, rec_ids, db_path, memo=None) -> dict:
    """The read that never computes (see `coverage`): fresh from disk, else the last map marked stale, else the
    empty shape marked pending — and the recompute scheduled."""
    import copy

    disk_fp = SB.channels_fingerprint(conn, rec_ids, memo, settings_keys=COVERAGE_SETTINGS, stable=True)
    held = _disk_read_any(key)
    if held is not None and held[0] == disk_fp:
        _remember(key, fp, held[1])
        return copy.deepcopy(held[1])
    failed = _COVERAGE_ERRORS.get(key)
    if failed is not None and failed[0] == disk_fp:
        raise CoverageFailed(failed[1])
    source_file, bins, verdicts, run_ids, method, held_out = key
    _schedule(key, {"key": key, "fp": fp, "disk_fp": disk_fp, "db_path": db_path, "source_file": source_file,
                    "bins": bins, "verdicts": verdicts, "run_ids": list(run_ids) if run_ids is not None else None,
                    "method": method, "held_out": held_out})
    since = _stale_since(key, disk_fp)
    hit = _COVERAGE_CACHE.get(key)
    last = hit[1] if hit is not None else (held[1] if held is not None else None)
    if last is not None:
        out = copy.deepcopy(last)
        out["stale"] = True
        out["stale_since"] = since
        return out
    out = _CM.empty(conn, source_file, bins=bins, held_out=held_out)
    out["pending"] = True
    return out


def _while_queued(conn, key):
    """While a recompute of `key` is queued or running, the answer a poll gets without fingerprinting again: the
    last map marked stale, or the empty shape marked pending. Each fingerprint holds the interpreter ~0.3 s on a
    5 M-detection database and the page polls every 3 s for as long as the recompute takes; the read after the
    worker finishes fingerprints as usual, so a change made meanwhile is still noticed (and recomputed).
    None when nothing for `key` is queued."""
    import copy

    with _WORK_LOCK:
        cur = _WORK["in_flight"]
        queued = _WORK["pending"].get(key) or (cur if cur is not None and cur["key"] == key else None)
        seen = _FIRST_SEEN.get(key)
    if queued is None:
        return None
    hit = _COVERAGE_CACHE.get(key)
    held = None if hit is not None else _disk_read_any(key)
    last = hit[1] if hit is not None else (held[1] if held is not None else None)
    if last is None:
        out = _CM.empty(conn, key[0], bins=key[1], held_out=key[5])
        out["pending"] = True
        return out
    out = copy.deepcopy(last)
    out["stale"] = True
    out["stale_since"] = seen[1] if seen is not None else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return out


def _stale_since(key, disk_fp) -> str:
    """When the state `disk_fp` names was first seen for `key` (UTC, ISO 8601)."""
    with _WORK_LOCK:
        seen = _FIRST_SEEN.get(key)
        if seen is None or seen[0] != disk_fp:
            seen = _FIRST_SEEN[key] = (disk_fp, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        return seen[1]


#: AR (the speed pass): the settings `_coverage` reads, and only these, go into its fingerprint — the matching
#: rule's two halves (`matching.rule_from_settings`) and the containment mode
#: (`divergence.containment_from_settings`). A setting added to the divergence must be added here, or a map is
#: served stale after it changes (tests/test_webui_ar_speed.py changes one of these and expects a recompute, and
#: changes another setting and expects none).
COVERAGE_SETTINGS = (("analysis-defaults", "iou"), ("analysis-defaults", "onset"),
                     ("analysis-defaults", "containment"))

#: AR: where computed maps are kept between restarts — `<runtime root>/cache/coverage/`, set by `Runtime.setup`;
#: None (memory only) for a caller that never set it. A file per key, holding its fingerprint: read back on a
#: miss in memory before recomputing; a path on disk, never a blob in the database (CLAUDE.md rule 4).
DISK_CACHE_DIR: str | None = None


def _disk_path(key, kind: str = "coverage") -> str | None:
    """`<runtime root>/cache/<kind>/<sha1 of the key>.json`: `coverage` for the corpus maps, `map` for Discovery ›
    Map's overview (map-overview-cache shares these helpers rather than keeping a second copy)."""
    if not DISK_CACHE_DIR:
        return None
    import hashlib
    return os.path.join(DISK_CACHE_DIR, kind, hashlib.sha1(repr(key).encode("utf-8")).hexdigest() + ".json")


def _disk_read(key, fp):
    path = _disk_path(key)
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            held = json.load(fh)
    except (OSError, ValueError):
        logging.getLogger("webui.corpus").warning("unreadable corpus-map cache file %s; recomputing", path)
        return None
    if held.get("fp") != fp or held.get("key") != repr(key):
        return None
    return held.get("payload")


def _disk_write(key, fp, out, kind: str = "coverage"):
    path = _disk_path(key, kind)
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"fp": fp, "key": repr(key), "payload": out}, fh)
        os.replace(tmp, path)
    except (OSError, TypeError, ValueError):
        # the map is still served from memory; only the restart cache misses it
        logging.getLogger("webui.corpus").exception("could not keep the corpus map for %s on disk", key[0])


#: AR: when the bridge last finished serving a request and how many are in flight — kept by `app.py`'s
#: middleware, read by the start-up warm so it computes between page reads, not under them
REQUEST_CLOCK = {"last": 0.0, "inflight": 0}


def wait_for_quiet(quiet_s: float = 2.0, max_wait_s: float = 30.0) -> float:
    """Wait until no request is in flight and none has finished for `quiet_s`, or `max_wait_s` passes (a page
    that polls must not hold the warm off for ever). Returns the seconds waited."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < max_wait_s:
        if REQUEST_CLOCK["inflight"] <= 0 and time.monotonic() - REQUEST_CLOCK["last"] >= quiet_s:
            break
        time.sleep(0.1)
    return time.monotonic() - t0


#: what the Corpus page — the home page — asks first (`CorpusPage.tsx`'s default bins and verdicts)
HOME_COVERAGE = {"bins": 57, "verdicts": ("seed", "interesting")}

#: how long the start-up warm waits for the worker to finish the maps it scheduled before it logs and returns (the
#: template-score warm follows it); a map still computing then simply lands later
WARM_WAIT_S = 1800.0


def _db_file(conn) -> str:
    """The file behind `conn`'s main database, or '' for an in-memory one (no worker can open that)."""
    try:
        for row in conn.execute("PRAGMA database_list").fetchall():
            if row[1] == "main":
                return row[2] or ""
    except Exception:
        return ""
    return ""


def warm_coverage(conn, first: str | None = None, db_path: str | None = None) -> list:
    """Make the home page's first coverage request current for every recording file
    (`first` before the rest), so a bridge's first page load answers fresh.
    Returns the files warmed.

    corpus-map-off-the-request: the warm goes through the same queue as the pages' reads, so the bridge's own
    interpreter never computes a map; it schedules each file whose map is not current, then waits (at most
    `WARM_WAIT_S`) for the worker, which logs a line per map. On an in-memory database no worker can open, the maps
    are computed in place as before, yielding to the pages between files."""
    files = [sf for sf in dict.fromkeys(row["source_file"] for row in q.list_recordings(conn))
             if sf != HELD_OUT_FILE]
    if first in files:
        files.remove(first)
        files.insert(0, first)
    log = logging.getLogger("webui.corpus")
    db_path = db_path or _db_file(conn)
    if db_path:
        t0 = time.perf_counter()
        behind = 0
        for sf in files:
            got = coverage(conn, sf, db_path=db_path, **HOME_COVERAGE)
            behind += bool(got.get("stale") or got.get("pending"))
        log.info("corpus map warm: %d files, %d current, %d scheduled on the worker", len(files),
                 len(files) - behind, behind)
        if behind and not wait_coverage_idle(WARM_WAIT_S):
            log.info("corpus map warm: the worker is still computing after %.0f s; the maps land as it finishes",
                     time.perf_counter() - t0)
        return files
    for i, sf in enumerate(files, 1):
        if i > 1:
            # AR: the first file (the home page's) at once; each after it between page reads
            waited = wait_for_quiet()
            if waited >= 1.0:
                log.info("corpus map warm waited %.1f s for the pages to go quiet", waited)
        t0 = time.perf_counter()
        coverage(conn, sf, **HOME_COVERAGE)
        # ux-1018: a line per file, so a 462 s warm (2026-10-18) can be watched and the slow file named
        log.info("corpus map %d/%d warmed: %s (%.1f s)", i, len(files), sf, time.perf_counter() - t0)
    return files


def _coverage(conn, source_file: str, bins: int = 57, verdicts: tuple | None = None,
              run_ids: list | None = None, method: str | None = None, **kw) -> dict:
    """The corpus map, computed on `conn`: the core's `coverage_map.compute_conn` (corpus-map-off-the-request moved
    the body there so a worker process can run it). See `coverage` for what each layer is."""
    return _CM.compute_conn(conn, source_file, bins=bins, verdicts=verdicts, run_ids=run_ids, method=method, **kw)


def _disk_read_any(key, kind: str = "coverage"):
    """The map kept on disk for `key` whatever state it was computed from: `(stable fingerprint, payload)`, or None.
    The last known map a stale read serves."""
    path = _disk_path(key, kind)
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            held = json.load(fh)
    except (OSError, ValueError):
        logging.getLogger("webui.corpus").warning("unreadable corpus-map cache file %s; recomputing", path)
        return None
    if held.get("key") != repr(key) or "payload" not in held:
        return None
    return held.get("fp"), held["payload"]


# ── the recompute, off the request (corpus-map-off-the-request) ─────────────
#
# Every map the reads and the warm schedule is computed one at a time, from a de-duplicated queue, in the bridge's
# shared worker process (`worker.run_in_worker`; the child imports `Working` only, `coverage_map.compute`); the result
# lands in memory and on disk. If no process can be started the queue is drained on a daemon thread instead, which
# yields to the pages between channels (`wait_for_quiet`) — and the log says so.

#: key -> (stable fingerprint of the state whose recompute failed, the sentence)
_COVERAGE_ERRORS: dict = {}
#: key -> (stable fingerprint, when that state was first seen) — a stale answer's `stale_since`
_FIRST_SEEN: dict = {}
_WORK = {"pending": {}, "in_flight": None, "computed": 0, "failed": 0, "thread": None, "mode": None}
_WORK_LOCK = threading.Lock()
_WORK_IDLE = threading.Event()
_WORK_IDLE.set()


def _drop_queue():
    """The worker was stopped (`worker.shutdown`): queued recomputes are dropped; the next read schedules them again."""
    with _WORK_LOCK:
        _WORK["pending"].clear()


worker.on_stop(_drop_queue)


def _schedule(key, job) -> bool:
    """Queue `job` (the recompute of `key` for the state `job['disk_fp']`) unless that exact recompute is queued or
    running. A newer state of a queued key replaces the queued job in its place. Returns whether it queued."""
    with _WORK_LOCK:
        cur = _WORK["in_flight"]
        if cur is not None and cur["key"] == key and cur["disk_fp"] == job["disk_fp"]:
            return False
        queued = _WORK["pending"].get(key)
        if queued is not None and queued["disk_fp"] == job["disk_fp"]:
            return False
        _WORK["pending"][key] = job
        _WORK_IDLE.clear()
        if _WORK["thread"] is None:
            _WORK["thread"] = threading.Thread(target=_drain, daemon=True, name="corpus-map-worker")
            _WORK["thread"].start()
        return True


def _run(job):
    """One recompute: `(stable fingerprint of the state it read, map)`. In the worker process, else (no pool, or it
    broke) on this thread with a yield between channels."""
    args = dict(bins=job["bins"], verdicts=job["verdicts"], run_ids=job["run_ids"], method=job["method"],
                held_out=job["held_out"])

    def here():
        conn = _CM.connect_read_only(job["db_path"])
        try:
            return _CM.fingerprinted(conn, job["source_file"], COVERAGE_SETTINGS, _coverage,
                                     between_channels=lambda: wait_for_quiet(), **args)
        finally:
            conn.close()
    mode, out = worker.run_in_worker(_CM.compute_fingerprinted, job["db_path"], job["source_file"],
                                     COVERAGE_SETTINGS, fallback=here,
                                     what=f"the corpus map for {job['source_file']}", **args)
    _WORK["mode"] = mode
    return out


def _drain():
    """Drain the queue, one recompute at a time. Whatever a job raises — an exception, a Ctrl-C delivered through
    `.result()`, any `BaseException` — is recorded as that map's failure (a read then raises it, loud), and the job
    is always cleared, so one bad job can never leave every map "recomputing…" for good (critic, corpus-map S2)."""
    log = logging.getLogger("webui.corpus")
    while True:
        with _WORK_LOCK:
            if not _WORK["pending"]:
                _WORK["in_flight"] = None
                _WORK["thread"] = None
                _WORK_IDLE.set()
                return
            key = next(iter(_WORK["pending"]))
            job = _WORK["in_flight"] = _WORK["pending"].pop(key)
        t0 = time.perf_counter()
        try:
            got_fp, out = _run(job)
            if got_fp is None:
                log.info("corpus map for %s: the database changed while it was computed; not kept, the next read "
                         "schedules it again", key[0])
            else:
                # kept under the state it READ; in memory (keyed by the scheduling read's in-process digest) only
                # when that is the state the read saw, so a map is never served as fresh for another state
                _disk_write(key, got_fp, out)
                with _WORK_LOCK:
                    if got_fp == job["disk_fp"]:
                        _remember(key, job["fp"], out)
                    _COVERAGE_ERRORS.pop(key, None)
                    _WORK["computed"] += 1
                log.info("corpus map recomputed: %s, %d bins (%.1f s, in a %s)", key[0], key[1],
                         time.perf_counter() - t0, _WORK["mode"])
        except worker.Stopped:
            log.info("corpus map for %s abandoned: the worker was stopped", key[0])
        except BaseException as exc:        # noqa: B902 - recorded, never swallowed into a blank
            sentence = f"the corpus map for {key[0]} could not be computed: {type(exc).__name__}: {exc}"
            log.error("%s", sentence, exc_info=(type(exc), exc, exc.__traceback__))
            with _WORK_LOCK:
                _COVERAGE_ERRORS[key] = (job["disk_fp"], sentence)
                _WORK["failed"] += 1
        finally:
            with _WORK_LOCK:
                _WORK["in_flight"] = None


def coverage_status() -> dict:
    """What the worker is doing: queued keys, the key in flight, maps computed and failed so far, and where the last
    one ran ("process" / "thread")."""
    with _WORK_LOCK:
        cur = _WORK["in_flight"]
        return {"pending": list(_WORK["pending"]), "in_flight": cur["key"] if cur is not None else None,
                "computed": _WORK["computed"], "failed": _WORK["failed"], "mode": _WORK["mode"],
                "pool_pid": worker.status()["pid"], "pool_failed": worker.status()["failed"]}


def wait_coverage_idle(timeout: float | None = None) -> bool:
    """Block until nothing is queued or computing (tests, the warm). True when idle."""
    return _WORK_IDLE.wait(timeout)


def clear_coverage_cache():
    """Forget every map held in memory, every failure and every stale-since time (the disk copies stay)."""
    with _WORK_LOCK:
        _COVERAGE_CACHE.clear()
        _COVERAGE_ERRORS.clear()
        _FIRST_SEEN.clear()


def reset_coverage_worker(timeout: float = 120.0):
    """Tests: drop what is queued, wait for the map in flight, and forget everything in memory. The worker process
    is kept (a fresh one costs seconds to start)."""
    with _WORK_LOCK:
        _WORK["pending"].clear()
    wait_coverage_idle(timeout)
    clear_coverage_cache()


def _finite(v):
    """JSON has no inf/NaN; detection scores in the real DB include inf."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if np.isfinite(f) else None


def spans(conn, recording_id: int, t0_s: float, t1_s: float, fs: float, cap: int = 5000, spread: bool = False) -> dict:
    """Annotations and detections overlapping [t0_s, t1_s), in channel seconds, each list capped at `cap`.

    A capped detection list is the window's FIRST `cap` rows by start (a prefix: what a reader walking rows in
    order wants). `spread=True` (the span view's own read) instead thins a capped list evenly across the window,
    every k-th row in time order, so a plot of it shows where the detections are rather than piling every band
    into the window's opening hours (span-plot critic round, 2026-10-18)."""
    s0 = int(np.floor(t0_s * fs)); s1 = int(np.ceil(t1_s * fs))
    ann = conn.execute(
        "SELECT id, start_idx, end_idx, verdict, tag, note, source FROM annotations WHERE recording_id = ? AND deleted_at IS NULL "
        "AND end_idx > ? AND start_idx < ? ORDER BY start_idx LIMIT ?", (recording_id, s0, s1, cap + 1)).fetchall()
    # legacy relative rows must be shifted before the window test. The SQL states `_absolute`'s
    # shift as a CASE so only the window's rows come back (it fetched every detection on the
    # channel, 300k+ rows, on every zoom step: 5-9 s a call in the smoke walk, perf 2026-10-18);
    # the Python test below is unchanged and still decides.
    shifted = "(IFNULL(r.span_start, 0) != 0 AND d.start_idx < r.span_start)"
    det_all = conn.execute(
        "SELECT d.id, d.start_idx, d.end_idx, d.score, d.run_id, r.span_start, r.span_end, r.started_at FROM detections d JOIN runs r ON r.id = d.run_id "
        "WHERE r.recording_id = ? AND " + q.not_surrogate("r") + " AND " + q.not_window_part("r") + " "
        f"AND (CASE WHEN {shifted} THEN d.end_idx + r.span_start ELSE d.end_idx END) > ? "
        f"AND (CASE WHEN {shifted} THEN d.start_idx + r.span_start ELSE d.start_idx END) < ? "
        "ORDER BY d.start_idx", (recording_id, s0, s1)).fetchall()
    det = []
    suspect = {}
    seen = set()   # each run tested once per read, not once per row (a wide view holds 300k rows)
    for d in det_all:
        a, b = _absolute(d["start_idx"], d["end_idx"], d["span_start"])
        if b > s0 and a < s1:
            det.append({"id": d["id"], "start_idx": a, "end_idx": b, "score": d["score"], "run_id": d["run_id"]})
            rid = d["run_id"]
            if rid not in seen:
                seen.add(rid)
                if rid not in SPANS._AMBIGUOUS_REPORTED \
                        and SPANS.legacy_ambiguous(d["span_start"], d["span_end"], d["started_at"]):
                    suspect[rid] = (d["span_start"], d["span_end"], d["started_at"])
    _warn_ambiguous(conn, suspect)
    det.sort(key=lambda d: d["start_idx"])
    # span-plot, the pile at t = 0: a capped read is the window's FIRST `cap` detections by start, so a reader
    # that takes a whole-channel read for the channel sees them all near its start. Say where they stop.
    complete_to = det[cap - 1]["start_idx"] / fs if len(det) > cap else t1_s
    total = len(det)
    thinned = bool(spread and total > cap)
    if thinned:
        det = [det[i] for i in np.unique(np.linspace(0, total - 1, cap).round().astype(int))]
        complete_to = None   # thinned across the whole window, not truncated: no second where it stops
    return {
        "recording_id": recording_id, "t0_s": t0_s, "t1_s": t1_s,
        "annotations": [{"id": a["id"], "start_s": a["start_idx"] / fs, "end_s": a["end_idx"] / fs, "verdict": a["verdict"],
                         "tag": a["tag"], "note": a["note"], "source": a["source"]} for a in ann[:cap]],
        "detections": [{"id": d["id"], "start_s": d["start_idx"] / fs, "end_s": d["end_idx"] / fs,
                        "score": _finite(d["score"]), "run_id": d["run_id"]} for d in det[:cap]],
        "annotations_capped": len(ann) > cap, "detections_capped": total > cap,
        "detections_complete_to_s": complete_to, "detections_total": total, "detections_spread": thinned,
    }


def _warn_ambiguous(conn, suspect: dict) -> None:
    """Name each ambiguous legacy run in a read once per process (`Working.discovery.spans.warn_if_ambiguous`),
    with its detector read from its recipe — fetched only for runs not yet reported."""
    for rid, (o, e, started) in suspect.items():
        row = conn.execute("SELECT c.config_json FROM runs r LEFT JOIN configs c ON c.id = r.config_id WHERE r.id = ?",
                           (rid,)).fetchone()
        SPANS.warn_if_ambiguous(rid, o, e, started, algorithm=SPANS.detector_of(row[0] if row else None))


def ribbons(conn, recording_id: int, fs: float, n: int, buckets: int = 300) -> dict:
    """Overview ribbons for Explore › Signal: per-bucket dominant annotation
    verdict (coverage) and detection count (density)."""
    edges = np.linspace(0, n, buckets + 1)
    ann = conn.execute("SELECT start_idx, end_idx, verdict FROM annotations WHERE recording_id = ? AND deleted_at IS NULL", (recording_id,)).fetchall()
    det = conn.execute("SELECT d.start_idx, d.end_idx, r.span_start FROM detections d JOIN runs r ON r.id = d.run_id WHERE r.recording_id = ? AND " + q.not_surrogate("r") + " AND " + q.not_window_part("r"), (recording_id,)).fetchall()
    det_starts = [_absolute(d["start_idx"], d["end_idx"], d["span_start"])[0] for d in det]   # legacy relative rows shifted, like spans()
    cov = [None] * buckets
    counts = {v: np.zeros(buckets, int) for v in VERDICTS}
    for a in ann:
        b0 = int(np.searchsorted(edges, a["start_idx"], side="right") - 1)
        b1 = int(np.searchsorted(edges, max(a["start_idx"], a["end_idx"] - 1), side="right") - 1)
        v = a["verdict"] if a["verdict"] in counts else "unsure"
        counts[v][max(0, b0):min(buckets, b1 + 1)] += 1
    prio = ["artifact", "seed", "interesting", "unsure", "not_interesting"]
    for b in range(buckets):
        best = None
        for v in prio:
            if counts[v][b] > 0:
                best = v; break
        cov[b] = best
    dh = np.histogram(det_starts, bins=edges)[0] if det else np.zeros(buckets, int)
    return {"buckets": buckets, "bucket_s": n / fs / buckets, "coverage": cov, "detection_density": dh.tolist()}


def channel_summary(conn, recording_id: int) -> dict:
    a = conn.execute("SELECT COUNT(*) FROM annotations WHERE recording_id = ? AND deleted_at IS NULL", (recording_id,)).fetchone()[0]
    real = q.not_surrogate("r") + " AND " + q.not_window_part("r")     # a paired null's spans are not detections (fixup-T); a window run is its stitched run's part (a2-p3)
    d = conn.execute("SELECT COUNT(*) FROM detections d JOIN runs r ON r.id = d.run_id WHERE r.recording_id = ? AND " + real, (recording_id,)).fetchone()[0]
    runs = conn.execute("SELECT COUNT(DISTINCT r.id) FROM runs r JOIN detections d ON d.run_id = r.id WHERE r.recording_id = ? AND " + real, (recording_id,)).fetchone()[0]
    return {"annotations": int(a), "detections": int(d), "detection_runs": int(runs)}


def window(conn, rec: dict, t0_s: float, t1_s: float, px: int) -> dict:
    x = display_channel(rec)
    fs = float(rec["fs"])
    i0 = int(max(0, np.floor(t0_s * fs))); i1 = int(min(len(x), np.ceil(t1_s * fs)))
    tt = time.perf_counter()
    env = envelope(x, fs, i0, i1, px)
    ms = (time.perf_counter() - tt) * 1e3
    return {"recording_id": rec["id"], "fs": fs, "n_samples": int(len(x)), "t0_s": i0 / fs, "t1_s": i1 / fs,
            "envelope": env, "decimate_ms": ms, "unit": x.unit,
            # the same two fields a chain Signal payload carries (serialize.py::_signal), for the block whose
            # input is the source window itself: stored-unit parameter -> drawn trace, and a drag back
            "unit_factor": x.factor if x.unit is not None else None, "stored_unit": x.declared}


@functools.lru_cache(maxsize=64)
def _yrange(npy_path: str, mtime_ns: int):
    x = _mmap(npy_path, mtime_ns)
    return float(np.nanmin(x)), float(np.nanmax(x))


def y_range(rec: dict) -> list:
    """The channel's full extent in its display unit (mV when declared). The
    scan is cached on the stored samples; the factor is applied after, so a
    unit declared later is never served from a stale extent."""
    st = os.stat(rec["npy_path"])
    lo, hi = _yrange(rec["npy_path"], st.st_mtime_ns)
    f = to_mv_factor(_units_of(rec)) or 1.0
    return [lo * f, hi * f]
