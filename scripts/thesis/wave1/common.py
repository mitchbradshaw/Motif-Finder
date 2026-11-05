"""
wave1.common — the plumbing every wave-1 step shares.

* The database is opened READ-ONLY (``file:...?mode=ro`` URI, plus ``PRAGMA query_only``): nothing here can write it.
* Every channel is read memory-mapped, one recording channel at a time, and converted to millivolts with
  ``Working.units.read_as_mv`` (V x1000, mV x1, uV x0.001; an undeclared unit is read as volts and the note says so).
* Arrays are written as float32 ``.npz`` (compressed) with a JSON sidecar of the same name; a series too big for one
  zip part is split along time into ``__chunkNN`` files, each with its own sidecar and ``t0_s``.
* *Schizophyllum commune* is refused everywhere (its blind exam is unjudged). M4_aug is NOT refused: its held-out exam
  was scored on 2026-10-26, so exporting it is allowed from now on.

Headless: numpy, pandas, pyarrow and the standard library; no UI library.
"""
from __future__ import annotations

import datetime as _dt
import glob
import json
import math
import os
import shutil
import sqlite3
import sys
import time
import traceback
import warnings

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
#: the checkout this script sits in (scripts/thesis/wave1 -> three levels up)
CODE_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if CODE_ROOT not in sys.path:
    sys.path.insert(0, CODE_ROOT)

SPEC_PATH = os.path.join(HERE, "bundle_spec.json")
#: the one recording refused everywhere: its unseen-recording exam has not been judged
REFUSED_PREFIXES = ("schizophyllum",)
HELD_OUT_FILE = "M4_aug_concat_fs1.mat"     # scored 2026-10-26: exported on purpose, never refused here
#: verdicts given on a judged WINDOW rather than an event (candidate_events.WINDOW_SOURCES)
WINDOW_SOURCES = ("imported_10min", "blind_test_review")
ACCEPTED = ("interesting", "seed")
#: the sweep's negative control (candidate_events.NEGATIVE_CONTROLS): the 1-minute CNNs call ~96 % interesting
NEGATIVE_CONTROL_SUFFIX = "_1min"
CAP_SAMPLES = 4000


class StepTimeout(RuntimeError):
    """A step ran past its time box; what it wrote so far is kept and the run goes on."""


def now_iso():
    return _dt.datetime.now().isoformat(timespec="seconds")


def is_refused(source_file):
    stem = os.path.splitext(os.path.basename(str(source_file or "")))[0].strip().lower()
    return stem.startswith(REFUSED_PREFIXES)


def mentions_refused(text):
    """A name or path that points at the refused recording (a queue name, a plot file)."""
    t = str(text or "").lower().replace(" ", "").replace("_", "").replace(".", "")
    return "schizophyllum" in t or "scommune" in t


def stem_of(source_file):
    return os.path.splitext(os.path.basename(str(source_file)))[0]


def safe_name(text):
    return "".join(ch if (ch.isalnum() or ch in "-_.") else "_" for ch in str(text)).strip("_")


# ── core helpers, imported from the tool (with plain copies if the checkout's core is older) ─────────────────

def family_of(variant):
    """`Working.discovery.candidate_events.family_of` (the detector family of a template variant)."""
    try:
        from Working.discovery.candidate_events import family_of as _f
        return _f(variant)
    except Exception:  # noqa: BLE001 - the same rule, written out, if the import is unavailable
        base = str(variant).split("__", 1)[0]
        if base.startswith("cnn_"):
            return "cnn_" + base.rsplit("_", 1)[1]
        if base.startswith("mp_"):
            return "matrix_profile"
        return base


def absolute_bounds(start_idx, end_idx, span_start):
    """`Working.discovery.spans.absolute_bounds`: a legacy span-relative detection shifted to channel-absolute."""
    s, e, o = int(start_idx), int(end_idx), int(span_start or 0)
    if o and s < o:
        return s + o, e + o
    return s, e


def read_as_mv(units):
    """`Working.units.read_as_mv` -> (factor, note)."""
    try:
        from Working.units import read_as_mv as _r
        return _r(units)
    except Exception:  # noqa: BLE001
        table = {"V": 1000.0, "mV": 1.0, "uV": 0.001}
        if units in table:
            return table[units], None
        return 1000.0, "unit undeclared: read as volts (x1000 to mV)"


def channel_label(source_file, channel, n_channels):
    """`Working.discovery.channels.channel_name` (M2-style electrode names, else CH<n+1>)."""
    try:
        from Working.discovery.channels import channel_name
        return channel_name(source_file, channel, n_channels)
    except Exception:  # noqa: BLE001
        return f"CH{int(channel) + 1}"


def m2_style_names():
    try:
        from Working.discovery.channels import M2_STYLE_NAMES
        return tuple(M2_STYLE_NAMES)
    except Exception:  # noqa: BLE001
        return None


# ── the database, read-only ──────────────────────────────────────────────────────────────────────────────

def open_ro(db_path):
    """The database read-only. ``mode=ro`` first (what every thesis script uses); ``immutable=1`` only when that
    cannot open (a WAL database whose -shm cannot be created), with a warning, since it ignores an uncheckpointed
    WAL. Returns ``(conn, note)``."""
    p = os.path.abspath(db_path).replace("\\", "/")
    if not os.path.isfile(db_path):
        raise FileNotFoundError(f"no database at {db_path}")
    note = None
    try:
        conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=60)
        conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
    except sqlite3.Error as e:
        conn = sqlite3.connect(f"file:{p}?mode=ro&immutable=1", uri=True, timeout=60)
        conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
        note = f"mode=ro failed ({e}); opened with immutable=1 (an uncheckpointed WAL would be ignored)"
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn, note


def columns_of(conn, table):
    try:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    except sqlite3.Error:
        return []


def has_table(conn, table):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def chunks(seq, n=400):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


# ── the run context ──────────────────────────────────────────────────────────────────────────────────────

class Ctx:
    """Everything a step needs: paths, the read-only connection, the recordings, the spec, the log, the time box."""

    def __init__(self, *, root, db_path, out, spec, max_part_mb=24.0, step_timeout_s=5400.0, echo=True):
        self.root = os.path.abspath(root)
        self.db_path = os.path.abspath(db_path)
        self.out = os.path.abspath(out)
        self.data_dir = os.path.join(self.out, "data")
        self.spec = spec
        self.max_part_mb = float(max_part_mb)
        self.step_timeout_s = float(step_timeout_s)
        self.echo = echo
        os.makedirs(self.data_dir, exist_ok=True)
        self.log_path = os.path.join(self.out, "wave1.log")
        self._log = open(self.log_path, "a", encoding="utf-8")
        self.step = "-"
        self.deadline = None
        self.t_start = time.time()
        self.notes = []            # run-level warnings for REPORT.md
        self.cache = {}
        self.conn, db_note = open_ro(self.db_path)
        if db_note:
            self.warn(db_note)
        self.recordings = load_recordings(self.conn)
        self.by_file = {}
        for r in self.recordings.values():
            self.by_file.setdefault(r["source_file"], {})[int(r["channel"])] = r
        self.kept = resolve_kept(self)

    # logging ------------------------------------------------------------------------------------------------
    def log(self, msg):
        line = f"[{_dt.datetime.now().strftime('%H:%M:%S')} +{time.time() - self.t_start:7.1f}s] [{self.step}] {msg}"
        try:
            self._log.write(line + "\n")
            self._log.flush()
        except Exception:  # noqa: BLE001
            pass
        if self.echo:
            try:
                print(line, flush=True)
            except UnicodeEncodeError:
                print(line.encode("ascii", "replace").decode("ascii"), flush=True)

    def warn(self, msg):
        self.notes.append(f"[{self.step}] {msg}")
        self.log("WARNING " + msg)

    def log_exception(self, where):
        tb = traceback.format_exc()
        self.log(f"ERROR in {where}:\n{tb}")
        return tb

    def close(self):
        try:
            self.conn.close()
        finally:
            self._log.close()

    # the time box -------------------------------------------------------------------------------------------
    def start_step(self, name):
        self.step = name
        self.deadline = time.time() + self.step_timeout_s

    def tick(self):
        if self.deadline is not None and time.time() > self.deadline:
            raise StepTimeout(f"step {self.step} ran past its {self.step_timeout_s / 60:.0f}-minute time box")

    # paths --------------------------------------------------------------------------------------------------
    def step_dir(self, step=None, *, clear=False):
        d = os.path.join(self.data_dir, step or self.step)
        if clear and os.path.isdir(d):
            assert os.path.commonpath([os.path.abspath(d), self.data_dir]) == self.data_dir
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)
        return d

    def path(self, *parts):
        """A repo path: under --root first, then the checkout the script sits in (they are one folder on the PC)."""
        p = os.path.join(self.root, *parts)
        if os.path.exists(p):
            return p
        q = os.path.join(CODE_ROOT, *parts)
        return q if os.path.exists(q) else p

    def rel(self, p):
        try:
            return os.path.relpath(p, self.out).replace("\\", "/")
        except ValueError:
            return p

    # recordings ---------------------------------------------------------------------------------------------
    def rec(self, recording_id):
        r = self.recordings.get(int(recording_id))
        if r is None:
            raise KeyError(f"no recording id {recording_id}")
        if is_refused(r["source_file"]):
            raise PermissionError(f"recording {recording_id} ({r['source_file']}) is refused (S. commune)")
        return r

    def channels_of(self, source_file):
        return [self.by_file[source_file][c] for c in sorted(self.by_file.get(source_file, {}))]

    def short_of(self, source_file):
        for short, sf in self.kept.items():
            if sf == source_file:
                return short
        return safe_name(stem_of(source_file))


def load_recordings(conn):
    cols = columns_of(conn, "recordings")
    rows = {}
    for r in conn.execute("SELECT * FROM recordings ORDER BY id"):
        d = {c: r[c] for c in cols}
        d.setdefault("units", None)
        d.setdefault("active", 1)
        rows[int(d["id"])] = d
    return rows


def resolve_kept(ctx):
    """`spec['recordings']` (short -> {stem, recording_id?}) resolved to source files present in the database.
    Exact stem first, then a unique prefix match; a recording that is absent is logged and skipped."""
    files = sorted(ctx.by_file)
    out = {}
    for short, want in (ctx.spec.get("recordings") or {}).items():
        stem = want["stem"] if isinstance(want, dict) else str(want)
        rid = want.get("recording_id") if isinstance(want, dict) else None
        hit = None
        if rid is not None and int(rid) in ctx.recordings and \
                stem_of(ctx.recordings[int(rid)]["source_file"]).startswith(stem):
            hit = ctx.recordings[int(rid)]["source_file"]
        if hit is None:
            exact = [f for f in files if stem_of(f) == stem]
            pref = [f for f in files if stem_of(f).startswith(stem)]
            hit = exact[0] if exact else (pref[0] if len(pref) == 1 else None)
            if hit is None and len(pref) > 1:
                ctx_note = f"recording {short}: stem {stem!r} matches {len(pref)} files {pref}; none chosen"
                ctx.notes.append(ctx_note)
        if hit is None:
            ctx.notes.append(f"[setup] recording {short} (stem {stem!r}) is not in this database: skipped")
            continue
        if is_refused(hit):
            continue
        out[short] = hit
    return out


# ── channels, in mV ──────────────────────────────────────────────────────────────────────────────────────

def npy_path(ctx, rec):
    """The channel file: `recordings.npy_path` as stored (absolute, or relative to the repo root), else the
    conventional DATA/derived/channels/<stem>/CH<n>.npy."""
    p = str(rec["npy_path"] or "")
    cands = []
    if p:
        cands.append(p if os.path.isabs(p) else os.path.join(ctx.root, p))
        if not os.path.isabs(p):
            cands.append(os.path.join(CODE_ROOT, p))
    cands.append(os.path.join(ctx.root, "DATA", "derived", "channels", stem_of(rec["source_file"]),
                              f"CH{int(rec['channel'])}.npy"))
    for c in cands:
        if os.path.isfile(c):
            return c
    raise FileNotFoundError(f"channel file of recording {rec['id']} ({rec['source_file']} CH{rec['channel']}) not "
                            f"found; tried {cands}")


def channel_array(ctx, rec):
    x = np.load(npy_path(ctx, rec), mmap_mode="r")
    if x.ndim != 1:
        x = x.reshape(-1)
    return x


def mv_factor(rec):
    return read_as_mv(rec.get("units"))


def block_mean(seg, k):
    """Non-overlapping means of `k` samples (NaN-aware); a trailing partial block is the mean of what is there."""
    seg = np.asarray(seg, dtype=np.float64)
    k = int(k)
    if k <= 1 or seg.size == 0:
        return seg
    m = (seg.size // k) * k
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        head = np.nanmean(seg[:m].reshape(-1, k), axis=1) if m else np.zeros(0)
        if seg.size > m:
            head = np.concatenate([head, [np.nanmean(seg[m:])]])
    return head


def read_segment(ctx, rec, start, end, decim=1):
    """Samples [start, end) of one channel in mV, float32, block-mean decimated by `decim`. Returns
    ``(x, start, end)`` with the bounds clipped to the channel."""
    x = channel_array(ctx, rec)
    n = len(x)
    s, e = max(0, int(start)), min(n, int(end))
    if e <= s:
        return np.zeros(0, np.float32), s, s
    seg = np.asarray(x[s:e], dtype=np.float64)
    if decim > 1:
        seg = block_mean(seg, decim)
    factor, _ = mv_factor(rec)
    return (seg * factor).astype(np.float32), s, e


def rec_meta(rec, *, n_channels=None):
    factor, note = mv_factor(rec)
    return {"source_file": rec["source_file"], "recording_id": int(rec["id"]), "channel": int(rec["channel"]),
            "channel_name": channel_label(rec["source_file"], rec["channel"], n_channels or 1),
            "fs": float(rec["fs"]), "n_samples": int(rec["n_samples"]), "units_original": rec.get("units"),
            "mv_factor": factor, "units_note": note, "converted_to": "mV",
            "active": None if rec.get("active") is None else int(rec.get("active"))}


# ── writers ──────────────────────────────────────────────────────────────────────────────────────────────

def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, default=_json_default)
    os.replace(tmp, path)
    return path


def write_csv(path, df):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)
    if len(df.columns) == 0:                       # a header a reader can parse, never a blank file
        df = pd.DataFrame({"no_rows": []})
    df.to_csv(path, index=False, float_format="%.10g")
    return path


def split_samples(ctx, n_rows=1):
    """The most float32 samples (per row) one npz may hold so that it always fits in a zip part (compressed is
    never bigger than raw plus a small overhead)."""
    budget = ctx.max_part_mb * 0.8 * 1e6
    return max(1000, int(budget / 4 / max(1, n_rows)))


def save_series(ctx, base, x, meta):
    """A time series (1-D, or 2-D channels x time) as float32 ``<base>.npz`` (key ``x``) + ``<base>.json``. Split
    along time into ``<base>__chunkNN`` when too big for one zip part. Returns the list of npz paths."""
    x = np.asarray(x, dtype=np.float32)
    n = x.shape[-1]
    rows = 1 if x.ndim == 1 else x.shape[0]
    lim = split_samples(ctx, rows)
    dt = float(meta.get("dt_s") or (1.0 / float(meta["fs"])))
    pieces = [(0, n)] if n <= lim else [(a, min(n, a + lim)) for a in range(0, n, lim)]
    paths = []
    for k, (a, b) in enumerate(pieces):
        stem = base if len(pieces) == 1 else f"{base}__chunk{k + 1:02d}"
        m = dict(meta)
        m["t0_s"] = float(meta.get("t0_s", 0.0)) + a * dt
        if "start_idx" in meta and meta.get("start_idx") is not None:
            m["start_idx"] = int(meta["start_idx"]) + a * int(meta.get("decimation", 1) or 1)
        m.update({"n": int(b - a), "shape": list(x[..., a:b].shape), "dtype": "float32", "npz_key": "x",
                  "chunk": None if len(pieces) == 1 else {"index": k + 1, "of": len(pieces)},
                  "read_with": "np.load(path)['x']; time of sample i = t0_s + i * dt_s"})
        m.setdefault("dt_s", dt)
        np.savez_compressed(stem + ".npz", x=x[..., a:b])
        write_json(stem + ".json", m)
        paths.append(stem + ".npz")
    return paths


def save_stack(ctx, base, segs, index_rows, meta):
    """Many short windows of different lengths in one ragged stack: ``<base>.npz`` holds ``values`` (float32, all
    windows concatenated) and ``offsets`` (int64, n+1; window i is values[offsets[i]:offsets[i+1]]), plus
    ``<base>_index.csv`` (one row per window: where it came from, t0_s, dt_s, decimation) and ``<base>.json``.
    Split into ``<base>__chunkNN`` stacks when too big for one zip part. Returns the list of npz paths."""
    lim = split_samples(ctx, 1)
    groups, cur, size = [], [], 0
    for i, s in enumerate(segs):
        if cur and size + len(s) > lim:
            groups.append(cur)
            cur, size = [], 0
        cur.append(i)
        size += len(s)
    if cur or not groups:
        groups.append(cur)
    paths = []
    for k, idx in enumerate(groups):
        stem = base if len(groups) == 1 else f"{base}__chunk{k + 1:02d}"
        vals = [np.asarray(segs[i], dtype=np.float32) for i in idx]
        offsets = np.zeros(len(vals) + 1, dtype=np.int64)
        if vals:
            offsets[1:] = np.cumsum([len(v) for v in vals])
        values = np.concatenate(vals) if vals else np.zeros(0, np.float32)
        np.savez_compressed(stem + ".npz", values=values, offsets=offsets)
        rows = []
        for j, i in enumerate(idx):
            r = dict(index_rows[i])
            r.update({"stack_file": os.path.basename(stem) + ".npz", "row": j, "offset": int(offsets[j]),
                      "n": int(offsets[j + 1] - offsets[j])})
            rows.append(r)
        write_csv(stem + "_index.csv", pd.DataFrame(rows))
        m = dict(meta)
        m.update({"n_windows": len(idx), "dtype": "float32", "converted_to": "mV",
                  "chunk": None if len(groups) == 1 else {"index": k + 1, "of": len(groups)},
                  "read_with": "z = np.load(path); w_i = z['values'][z['offsets'][i]:z['offsets'][i+1]]; "
                               "its row i in <stack>_index.csv gives recording, channel, t0_s, dt_s",
                  "index_csv": os.path.basename(stem) + "_index.csv"})
        write_json(stem + ".json", m)
        paths.append(stem + ".npz")
    return paths


def item_window(start, end, n, cap=CAP_SAMPLES):
    """The context window of one item: its span +- one span length, clipped to the channel; the integer
    decimation that brings it to at most `cap` points."""
    s, e = int(start), int(end)
    L = max(1, e - s)
    ws, we = max(0, s - L), min(int(n), e + L)
    W = max(0, we - ws)
    decim = int(math.ceil(W / float(cap))) if W > cap else 1
    return ws, we, decim


def window_rows(ctx, items, *, cap=CAP_SAMPLES, context=None):
    """Read the context window of every item (dicts with recording_id, start, end, and anything else to keep).
    `context`: a fixed number of samples each side instead of one span length (and no cap). Returns
    ``(segs, index_rows, n_skipped)``; channels are read one recording at a time."""
    segs, rows, skipped = [], [], 0
    order = sorted(range(len(items)), key=lambda i: (int(items[i]["recording_id"]), int(items[i]["start"])))
    out = {}
    for i in order:
        it = items[i]
        ctx.tick()
        try:
            rec = ctx.rec(it["recording_id"])
            n = int(rec["n_samples"])
            if context is None:
                ws, we, decim = item_window(it["start"], it["end"], n, cap)
            else:
                ws, we, decim = max(0, int(it["start"]) - context), min(n, int(it["end"]) + context), 1
            x, ws, we = read_segment(ctx, rec, ws, we, decim)
        except (KeyError, PermissionError, FileNotFoundError, OSError, ValueError) as e:
            skipped += 1
            ctx.log(f"window skipped for item {it}: {e}")
            continue
        fs = float(rec["fs"])
        factor, note = mv_factor(rec)
        row = dict(it)
        row.update({"source_file": rec["source_file"], "channel": int(rec["channel"]), "fs": fs,
                    "win_start_idx": ws, "win_end_idx": we, "t0_s": ws / fs, "dt_s": decim / fs,
                    "decimation": decim, "item_t0_s": int(it["start"]) / fs, "item_t1_s": int(it["end"]) / fs,
                    "units_original": rec.get("units"), "mv_factor": factor})
        out[i] = (x, row)
    for i in range(len(items)):
        if i in out:
            segs.append(out[i][0])
            rows.append(out[i][1])
    return segs, rows, skipped


# ── shared readers ───────────────────────────────────────────────────────────────────────────────────────

def own_adjudication_clause(conn, alias="a"):
    return f"{alias}.carried_from IS NULL" if "carried_from" in columns_of(conn, "adjudications") else "1 = 1"


def accepted_events(ctx, recording_ids):
    """Human-accepted EVENTS per recording id: live annotations (verdict interesting/seed, not on a judged window)
    and own adjudications (interesting/seed) on real runs' detections, channel-absolute, deduplicated.
    Returns {recording_id: sorted int64 array of starts} and the full rows."""
    conn = ctx.conn
    ids = sorted({int(r) for r in recording_ids})
    rows = []
    win = ",".join("?" * len(WINDOW_SOURCES))
    own = own_adjudication_clause(conn)
    surr = "r.surrogate_of_run_id IS NULL" if "surrogate_of_run_id" in columns_of(conn, "runs") else "1 = 1"
    deleted = "AND deleted_at IS NULL" if "deleted_at" in columns_of(conn, "annotations") else ""
    for ch in chunks(ids):
        marks = ",".join("?" * len(ch))
        for r in conn.execute(f"SELECT recording_id, start_idx, end_idx FROM annotations WHERE recording_id IN "
                              f"({marks}) AND verdict IN ('interesting','seed') AND source NOT IN ({win}) {deleted}",
                              ch + list(WINDOW_SOURCES)):
            rows.append((int(r[0]), int(r[1]), int(r[2])))
        for r in conn.execute(f"SELECT r.recording_id, d.start_idx, d.end_idx, r.span_start FROM adjudications a "
                              f"JOIN detections d ON d.id = a.detection_id JOIN runs r ON r.id = d.run_id "
                              f"WHERE r.recording_id IN ({marks}) AND a.verdict IN ('interesting','seed') AND {own} "
                              f"AND {surr}", ch):
            s, e = absolute_bounds(r[1], r[2], r[3])
            rows.append((int(r[0]), s, e))
    rows = sorted(set(rows))
    by = {}
    for rid, s, _e in rows:
        by.setdefault(rid, []).append(s)
    return {k: np.asarray(sorted(v), dtype=np.int64) for k, v in by.items()}, rows


def best_window(onsets_by_key, length, n_by_key):
    """The window of `length` samples holding the most onsets, over every key (channel). Returns
    ``(key, start, count)`` with the window centred on the events it holds and clipped to the channel, or
    ``(None, None, 0)`` when there are no onsets."""
    best = (None, None, 0, None)
    for key in sorted(onsets_by_key):
        on = np.sort(np.asarray(onsets_by_key[key], dtype=np.int64))
        if not on.size:
            continue
        j = np.searchsorted(on, on + int(length), side="left")
        cnt = j - np.arange(on.size)
        i = int(np.argmax(cnt))
        if int(cnt[i]) > best[2]:
            best = (key, i, int(cnt[i]), on)
    key, i, count, on = best
    if key is None:
        return None, None, 0
    n = int(n_by_key[key])
    j = int(np.searchsorted(on, on[i] + int(length), side="left"))
    first, last = int(on[i]), int(on[j - 1])
    slack = int(length) - (last - first)
    start = first - slack // 2
    start = max(0, min(start, n - int(length)))
    count = int(((on >= start) & (on < start + int(length))).sum())
    return key, int(start), count


def candidate_tables(ctx):
    """Every candidate-event table on disk (DATA/derived/candidate_events/<key>/meta.json + events.parquet)."""
    if "candidate_tables" in ctx.cache:
        return ctx.cache["candidate_tables"]
    out = []
    for meta_path in sorted(glob.glob(os.path.join(ctx.root, "DATA", "derived", "candidate_events", "*",
                                                   "meta.json"))):
        d = os.path.dirname(meta_path)
        if not os.path.isfile(os.path.join(d, "events.parquet")):
            continue
        try:
            with open(meta_path, encoding="utf-8") as fh:
                m = json.load(fh)
        except (OSError, ValueError):
            continue
        out.append({"dir": d, "key": m.get("key") or os.path.basename(d), "source_file": m.get("source_file"),
                    "created_at": str(m.get("created_at") or ""), "n_events": m.get("n_events"),
                    "n_detections": m.get("n_detections"), "version": m.get("version"),
                    "exam": bool(m.get("exam")), "recordings": m.get("recordings") or {}})
    ctx.cache["candidate_tables"] = out
    return out


def newest_table(ctx, source_file):
    """The candidate-event table of `source_file` every step reads: of its tables, the newest one that holds a
    drawn sample (``sample_*/sample.parquet``: the frame the precision ladder and the blind queues were estimated
    on, so counts and precisions describe one table), else the newest. The choice and the alternatives are in
    meta/candidate_tables.csv; ``table['why']`` says which rule picked it."""
    tabs = [t for t in candidate_tables(ctx) if t["source_file"] == source_file and not is_refused(source_file)]
    if not tabs:
        return None
    for t in tabs:
        t["has_sample"] = bool(glob.glob(os.path.join(t["dir"], "sample_*", "sample.parquet")))
    newest = lambda ts: sorted(ts, key=lambda t: (t["created_at"],  # noqa: E731
                                                  os.path.getmtime(os.path.join(t["dir"], "meta.json"))))[-1]
    with_sample = [t for t in tabs if t["has_sample"]]
    pick = newest(with_sample) if with_sample else newest(tabs)
    pick["why"] = (f"newest of {len(with_sample)} table(s) holding a drawn sample (of {len(tabs)})" if with_sample
                   else f"newest of {len(tabs)} table(s) (none holds a sample)")
    return pick


def read_events(table, columns, filters=None):
    """Columns of a table's events.parquet (pyarrow; only what is asked, so ~1M rows stay small)."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    path = os.path.join(table["dir"], "events.parquet")
    schema = pq.read_schema(path)
    cols = [c for c in columns if c in schema.names]
    # strings (family lists, labels) dictionary-encoded: ~1M rows of them stay a few MB, not hundreds
    strs = [c for c in cols if pa.types.is_string(schema.field(c).type) or pa.types.is_large_string(
        schema.field(c).type)]
    t = pq.read_table(path, columns=cols, filters=filters, read_dictionary=strs or None)
    return t.to_pandas()


def samples_with_queue(ctx):
    """{queue_id: [sample dir, ...]}: the candidate-event samples whose meta names the Review queue made from them."""
    if "samples_by_queue" in ctx.cache:
        return ctx.cache["samples_by_queue"]
    out = {}
    for meta_path in sorted(glob.glob(os.path.join(ctx.root, "DATA", "derived", "candidate_events", "*",
                                                   "sample_*", "meta.json"))):
        try:
            with open(meta_path, encoding="utf-8") as fh:
                m = json.load(fh)
        except (OSError, ValueError):
            continue
        q = m.get("queue_id")
        if q is not None and os.path.isfile(os.path.join(os.path.dirname(meta_path), "sample.parquet")):
            out.setdefault(int(q), []).append(os.path.dirname(meta_path))
    ctx.cache["samples_by_queue"] = out
    return out


def queue_filters(ctx):
    """{queue_id: (row dict, filters dict)} for every Review queue."""
    if "queue_filters" in ctx.cache:
        return ctx.cache["queue_filters"]
    out = {}
    if has_table(ctx.conn, "review_queues"):
        cols = columns_of(ctx.conn, "review_queues")
        for r in ctx.conn.execute("SELECT * FROM review_queues ORDER BY id"):
            d = {c: r[c] for c in cols}
            try:
                f = json.loads(d.get("filters_json") or "{}") or {}
            except ValueError:
                f = {}
            out[int(d["id"])] = (d, f if isinstance(f, dict) else {})
    ctx.cache["queue_filters"] = out
    return out


def detection_queue_map(ctx):
    """{detection_id: "q25;q28"}: which queues list a detection (queues whose filters name detection ids)."""
    if "det_queue" in ctx.cache:
        return ctx.cache["det_queue"]
    m = {}
    for qid, (_row, f) in queue_filters(ctx).items():
        for d in f.get("detection_ids") or []:
            try:
                m.setdefault(int(d), []).append(qid)
            except (TypeError, ValueError):
                continue
    out = {k: ";".join(str(q) for q in sorted(set(v))) for k, v in m.items()}
    ctx.cache["det_queue"] = out
    return out


def live_groups(ctx):
    """{run_group_id: {"kind": "template"|"seed", "names": set, "discovery_run_ids": [...]}} for the live
    Discovery runs (not removed from their session, not superseded). Also fills ctx.cache["seed_param_runs"]:
    {run_id: name} for the runs a live SEED run names only in its ``params_json.run_ids`` (an HPC seed search has
    no run group; webui/server/library.py ``_seed_runs_by_run_id`` reads them the same way)."""
    if "live_groups" in ctx.cache:
        return ctx.cache["live_groups"]
    out, by_param = {}, {}
    if has_table(ctx.conn, "discovery_runs"):
        cols = columns_of(ctx.conn, "discovery_runs")
        live = " AND ".join(c + " IS NULL" for c in ("removed_at", "superseded_at") if c in cols) or "1 = 1"
        for r in ctx.conn.execute(f"SELECT id, kind, label, template_name, run_group_id, params_json "
                                  f"FROM discovery_runs WHERE kind IN ('template', 'seed') AND {live}"):
            name = r["template_name"] if r["kind"] == "template" else f"seed:{r['label']}"
            if r["kind"] == "seed":
                try:
                    for rid in (json.loads(r["params_json"] or "{}").get("run_ids") or []):
                        by_param.setdefault(int(rid), name)
                except (ValueError, TypeError, AttributeError):
                    pass
            if r["run_group_id"] is None:
                continue
            g = out.setdefault(int(r["run_group_id"]), {"kind": r["kind"], "names": set(), "discovery_run_ids": []})
            if name:
                g["names"].add(str(name))
            g["discovery_run_ids"].append(int(r["id"]))
            if r["kind"] == "template":
                g["kind"] = "template"
    ctx.cache["live_groups"] = out
    ctx.cache["seed_param_runs"] = by_param
    return out


def runs_on(ctx, recording_ids, *, kinds=("template",), include_surrogates=False):
    """Completed, not superseded, not-a-window-part runs of live Discovery run groups on these recordings:
    DataFrame(run_id, recording_id, run_group_id, span_start, span_end, surrogate_of, kind, variant)."""
    conn = ctx.conn
    groups = live_groups(ctx)
    rcols = columns_of(conn, "runs")
    sur_col = "r.surrogate_of_run_id" if "surrogate_of_run_id" in rcols else "NULL"
    sup = "AND r.superseded_at IS NULL" if "superseded_at" in rcols else ""
    win = ("AND NOT EXISTS (SELECT 1 FROM stitched_windows sw WHERE sw.window_run_id = r.id)"
           if has_table(conn, "stitched_windows") else "")
    by_param = ctx.cache.get("seed_param_runs", {}) if "seed" in kinds else {}
    rows, seen = [], set()
    for ch in chunks(sorted({int(r) for r in recording_ids})):
        marks = ",".join("?" * len(ch))
        for r in conn.execute(f"SELECT r.id, r.recording_id, r.run_group_id, r.span_start, r.span_end, {sur_col} "
                              f"FROM runs r WHERE r.recording_id IN ({marks}) AND r.status = 'completed' "
                              f"{sup} {win}", ch):
            if r[5] is not None and not include_surrogates:
                continue
            g = groups.get(int(r[2])) if r[2] is not None else None
            if g is not None and g["kind"] in kinds:
                kind, variant = g["kind"], "|".join(sorted(g["names"]))
            elif int(r[0]) in by_param:
                kind, variant = "seed", by_param[int(r[0])]
            else:
                continue
            if int(r[0]) in seen:
                continue
            seen.add(int(r[0]))
            rows.append((int(r[0]), int(r[1]), None if r[2] is None else int(r[2]), int(r[3] or 0), int(r[4] or 0),
                         None if r[5] is None else int(r[5]), kind, variant))
    return pd.DataFrame(rows, columns=["run_id", "recording_id", "run_group_id", "span_start", "span_end",
                                       "surrogate_of", "kind", "variant"])


def rule1_choice(runs):
    """candidate_events rule 1: of the REAL runs, one per (variant, recording): the longest span, then the newest
    (highest id). Returns the set of chosen run ids."""
    real = runs[runs["surrogate_of"].isna()].copy()
    if not len(real):
        return set()
    real["len"] = real["span_end"] - real["span_start"]
    real = real.sort_values(["variant", "recording_id", "len", "run_id"])
    return set(real.drop_duplicates(["variant", "recording_id"], keep="last")["run_id"].astype(int))


def detections_of_run(ctx, run_id, span_start, ws=None, we=None, maxlen=None):
    """A run's detections, channel-absolute, optionally only those overlapping [ws, we). DataFrame(detection_id,
    start, end, score)."""
    conn = ctx.conn
    if ws is not None and not span_start and maxlen is not None:
        cur = conn.execute("SELECT id, start_idx, end_idx, score FROM detections WHERE run_id = ? AND start_idx >= ? "
                           "AND start_idx < ? AND end_idx > ?", (int(run_id), int(ws) - int(maxlen) - 1, int(we),
                                                                 int(ws)))
    else:
        cur = conn.execute("SELECT id, start_idx, end_idx, score FROM detections WHERE run_id = ?", (int(run_id),))
    out = []
    for d, s, e, sc in cur:
        a, b = absolute_bounds(s, e, span_start)
        if ws is not None and not (a < we and b > ws):
            continue
        out.append((int(d), a, b, np.nan if sc is None else float(sc)))
    df = pd.DataFrame(out, columns=["detection_id", "start", "end", "score"])
    return df.astype({"detection_id": "int64", "start": "int64", "end": "int64", "score": "float64"})


def touched(win_s, win_e, det_s, det_e):
    """scripts/thesis/miss_rate.py's rule: does any detection [s, e) overlap each window [ws, we)?"""
    win_s, win_e = np.asarray(win_s, dtype=np.int64), np.asarray(win_e, dtype=np.int64)
    if len(det_s) == 0:
        return np.zeros(len(win_s), dtype=bool)
    o = np.argsort(det_s, kind="stable")
    ds, de = np.asarray(det_s, dtype=np.int64)[o], np.maximum.accumulate(np.asarray(det_e, dtype=np.int64)[o])
    idx = np.searchsorted(ds, win_e, side="left")
    out = np.zeros(len(win_s), dtype=bool)
    ok = idx > 0
    out[ok] = de[idx[ok] - 1] > win_s[ok]
    return out


def file_bytes(path):
    total = 0
    for dp, _dn, fns in os.walk(path):
        for f in fns:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total
