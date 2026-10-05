"""
pool.py
=======
RQ1 version 2 (fixup-af): UNLABELLED window sets at several scales, and the
function that combines saved window sets into a POOL with the train /
validation / test / exam fence laid over it. `AG`'s *Window pool* chain block
calls `combine`; `python -m Working.training combine` walks it from a shell.

Why a sibling of `windows.build_pooled_set`, not an extension of it
-------------------------------------------------------------------
`build_pooled_set` is the paired job's set: labelled windows only, thinned
labelled-first, split at build time and measured with features — every one of
those is wrong for this set. An unlabelled set ignores the labels, carries no
roles (the fence belongs to the pool) and stores bounds, not features (`AG`
decides what the clustering looks at). Branching the paired job's builder on
all three would put an `if` on every path the baseline run relies on, so this
module re-uses its pieces instead: `refuse_held_out`, `recording_identity`,
`blocked_split` and the `LeakageRefused` / `HeldOutRefused` guards.

An unlabelled set (`build_unlabelled_set`)
-------------------------------------------
One recording, one scale (1, 10 or 30 minutes — any whole number of minutes),
the chosen channels. Windows sit on a grid at that scale (stride = the window
by default, so no two windows of a set overlap; a stride below the window is
refused). Left out, and counted per channel:

* a window touching a span a HUMAN marked `artifact` (`annotations`, never a
  soft-deleted one, and `window_verdicts` — `catalogue.manual_labels.human_spans`);
* a window touching a span Settings › Channels & events excludes (an event whose
  effect is *exclude span*, or *exclude · mark channel bad*, which excludes its
  channel from the event's start to the end of the recording);
* a window holding a non-finite sample.

Every other label is ignored: windows are cut from the signal, labelled or not.
Where the supply is large a seeded uniform sample can be kept (`sample`).

The region plan (`plan_for`, `make_plan`)
-----------------------------------------
Roles are given to STRETCHES OF TIME on a channel before any window is placed,
the same stretches for every scale. Per recording (by identity, so the fs1 and
fs2 files of one recording share one plan): `blocked_split` cuts the recording
into `n_blocks` equal blocks — the last `test_frac` test, the `validation_frac`
before them validation, the rest train, exactly as `AB` — consecutive blocks of
one role merge into a stretch, and a GAP of `gap_s` seconds is carved from the
start of every stretch that follows another role. Exam channels (chosen, or a
whole pack with `hold_out_pack`) are one exam stretch end to end. A window has a
role only if it lies wholly inside one stretch; a window in a gap, or
straddling a boundary, is dropped and counted.

Combining (`combine`)
---------------------
A pool is an ORDERED list of saved sets, a plan and a rule. In order:

1. every window gets its role from the plan (a set on a recording the plan does
   not cover is refused with the reason; the held-out file is refused even with
   the unlock);
2. artifact spans are checked again, so a span labelled after a set was saved
   is still left out;
3. exact duplicates (same file, channel, start, length) are removed — the
   first set listed wins;
4. within one scale no two windows overlap — the first set listed wins (on one
   recording's time, so an fs2 window over an fs1 window of the same scale is
   an overlap);
5. a seeded uniform sample per scale, where asked;
6. rule ``within_scale`` (the default): across scales overlap is ALLOWED — a
   30-minute window and a 1-minute window inside it are different objects at
   different scales — but never across roles, which the plan guarantees;
   rule ``no_overlap``: no overlap across scales either, and the SMALLER scale
   wins. Larger-wins was rejected: the six sets are grids that tile the whole
   recording, so the 30-minute grid covers every minute and "larger wins" would
   quietly turn a three-scale pool into a one-scale pool. Sampling runs first,
   so every sampled small window survives and the larger ones around it go;
7. `check_pool`: no window of one role inside another role's stretch, no
   overlap across roles on one recording's time (which is the fs1 / fs2 check,
   now across every file of the pool), none within a scale.

A saved pool is itself a `window_sets` row — its members in
`window_pool_members`, its plan in `split_json`, its key in `recipe_hash` — and
its window bounds on disk (rule 4: no arrays in the database).

Headless: no UI or web library is imported here (CLAUDE.md rule 1).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

from Working.training.windows import (  # noqa: F401  (re-exported for the pool's callers)
    HeldOutRefused, LeakageRefused, blocked_split, recording_identity, refuse_held_out,
)

SCALES_MIN = (1, 10, 30)
#: the four mushroom packs of a 16-channel recording (zero-based channel indices):
#: CH1–4 A, CH5–8 B, CH9–12 C, CH13–16 D
PACKS = {"A": (0, 1, 2, 3), "B": (4, 5, 6, 7), "C": (8, 9, 10, 11), "D": (12, 13, 14, 15)}
ROLES = ("train", "validation", "test", "exam")
DEFAULT_PLAN = {"n_blocks": 10, "test_frac": 0.2, "validation_frac": 0.1, "gap_s": 1800.0}
RULES = {
    "within_scale": ("within a scale no two windows overlap; across scales overlap is allowed (a 30-minute window "
                     "and a 1-minute window inside it are different objects) but never across roles; exact "
                     "duplicates removed; the first set listed wins"),
    "no_overlap": ("no two windows overlap at all, across scales either: the SMALLER scale wins (sampled first, "
                   "then every larger window touching a kept smaller one is dropped); exact duplicates removed; "
                   "the first set listed wins within a scale"),
}
DEFAULT_RULE = "within_scale"

SETTINGS_PAGE = "channels-events"
EXCLUDE_SPAN, MARK_BAD = "exclude span", "exclude · mark channel bad"
EXCLUSIONS_RULE = ("left out: any window touching a span a human marked artifact (annotations and window verdicts, "
                   "soft-deleted labels ignored), any window touching a span Settings › Channels & events excludes "
                   "('exclude span'; 'exclude · mark channel bad' from the event's start to the end), any window "
                   "holding a non-finite sample. Every other label is ignored.")

SET_COLUMNS = ("recording_id", "channel", "start", "length")
POOL_COLUMNS = ("set_id", "recording_id", "source_file", "channel", "start", "length", "fs", "scale_min", "role")
DROP_KEYS = ("gap", "straddle", "artifact", "duplicate", "overlap_within_scale", "sampled_out",
             "overlap_across_scales")
BUILD_DROP_KEYS = ("non_finite", "artifact_human", "excluded_by_settings", "sampled_out")


class PlanRefused(ValueError):
    """A set cannot be placed under the region plan (e.g. a recording it does not cover)."""


def _now():
    return _dt.datetime.now().isoformat(timespec="seconds")


def _scale_value(length, fs):
    """Minutes, as an int when whole."""
    v = round(float(length) / float(fs) / 60.0, 6)
    return int(v) if float(v).is_integer() else v


def _key(header, arrays):
    """A content key: a header and the window columns, hashed — fast at a million windows."""
    h = hashlib.sha256(json.dumps(header, sort_keys=True, default=str).encode("utf-8"))
    for a in arrays:
        a = np.asarray(a)
        if a.dtype.kind in "OUS":
            h.update("\x00".join(map(str, a.tolist())).encode("utf-8"))
        else:
            h.update(np.ascontiguousarray(a.astype("<f8" if a.dtype.kind == "f" else "<i8")).tobytes())
        h.update(b"|")
    return h.hexdigest()[:16]


# ── exclusions ──────────────────────────────────────────────────────────────

def _channel_names(source_file, channel, n_channels):
    from Working.discovery.channels import channel_name
    return {channel_name(source_file, channel, n_channels), f"CH{int(channel) + 1}"}


def settings_exclusions(saved, stem, source_file, channel, n_channels, n_samples, fs):
    """`[(start, end)]` in samples that Settings › Channels & events excludes on one
    channel. `saved` is the page's stored values (`get_settings(conn, 'channels-events')`)."""
    events = saved.get(f"events.added.{stem}") or []
    removed = set()
    for x in saved.get(f"events.removed.{stem}") or []:
        removed.add(x if isinstance(x, str) else (x or {}).get("id"))
    names = _channel_names(source_file, channel, n_channels)
    out = []
    for e in events if isinstance(events, list) else []:
        if not isinstance(e, dict) or e.get("id") in removed:
            continue
        effect = saved.get(f"effect.{e.get('id')}", e.get("effect"))
        if effect not in (EXCLUDE_SPAN, MARK_BAD):
            continue
        chans = str(e.get("channels") or "all")
        if chans != "all" and chans not in names:
            continue
        try:
            t0 = float(e.get("t0_h")) * 3600.0
        except (TypeError, ValueError):
            continue
        if effect == MARK_BAD or e.get("open_end"):
            t1 = float(n_samples) / float(fs)
        elif e.get("t1_h") is None:
            continue          # a point event excludes no time
        else:
            t1 = float(e.get("t1_h")) * 3600.0
        out.append((int(math.floor(t0 * fs)), int(math.ceil(t1 * fs))))
    return out


def human_artifact_spans(conn, recording_id):
    from Adapters.catalogue_manual_labels import human_spans
    return [(int(a), int(b)) for a, b, v, _src in human_spans(conn, int(recording_id)) if v == "artifact"]


def _touches(starts, length, spans):
    """Per window: does [start, start + length) touch any span [a, b)?"""
    starts = np.asarray(starts, dtype=np.int64)
    hit = np.zeros(len(starts), dtype=bool)
    if not len(starts):
        return hit
    lengths = np.broadcast_to(np.asarray(length, dtype=np.int64), starts.shape)
    for a, b in spans:
        hit |= (starts < int(b)) & (starts + lengths > int(a))
    return hit


class _Exclusions:
    """The spans left out on each recording row, read once per call."""

    def __init__(self, conn):
        from Working.library.view_filter import dataset_stem
        from Working.registration.settings import get_settings
        self.conn = conn
        self.saved = get_settings(conn, SETTINGS_PAGE)
        self._stem = dataset_stem
        self._n_channels = {}

    def n_channels(self, source_file):
        if source_file not in self._n_channels:
            self._n_channels[source_file] = int(self.conn.execute(
                "SELECT COUNT(*) FROM recordings WHERE source_file = ?", (str(source_file),)).fetchone()[0])
        return self._n_channels[source_file]

    def spans(self, rec):
        human = human_artifact_spans(self.conn, rec["id"])
        settings = settings_exclusions(self.saved, self._stem(rec["npy_path"], rec["source_file"]),
                                       rec["source_file"], rec["channel"], self.n_channels(rec["source_file"]),
                                       rec["n_samples"], rec["fs"])
        return human, settings


# ── an unlabelled set ───────────────────────────────────────────────────────

@dataclass
class UnlabelledSet:
    """`table`: one row per window (`SET_COLUMNS`), no role, no label. `meta`: how it
    was cut and what was left out, per channel and in all."""
    table: pd.DataFrame
    meta: dict

    _HOW = ("source_file", "scale_min", "length", "grid", "offset", "channels", "exclude_artifacts", "sample", "seed")

    @property
    def key(self):
        t = self.table
        return _key({"kind": "unlabelled_window_set", "how": {k: self.meta.get(k) for k in self._HOW}},
                    [t[c].to_numpy() for c in SET_COLUMNS])

    def save(self, d):
        os.makedirs(d, exist_ok=True)
        np.savez_compressed(os.path.join(d, "unlabelled_windows.npz"),
                            **{c: self.table[c].to_numpy().astype(np.int64) for c in SET_COLUMNS})
        with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"kind": "unlabelled_window_set", "key": self.key, **self.meta}, f, indent=2, default=str)
        return d

    @classmethod
    def load(cls, d):
        with np.load(os.path.join(d, "unlabelled_windows.npz"), allow_pickle=False) as z:
            table = pd.DataFrame({c: z[c].astype(np.int64) for c in SET_COLUMNS})
        with open(os.path.join(d, "manifest.json"), encoding="utf-8") as f:
            meta = json.load(f)
        saved = meta.pop("key", None)
        meta.pop("kind", None)
        out = cls(table=table, meta=meta)
        if saved is not None and saved != out.key:
            raise ValueError(f"the window set at {d} does not match its own key ({saved} on disk, {out.key} "
                             "recomputed): its files were changed after it was saved")
        return out


def _recording_rows(conn, source_file, channels=None):
    rows = [dict(r) for r in conn.execute("SELECT * FROM recordings WHERE source_file = ? ORDER BY channel",
                                          (str(source_file),))]
    if not rows:
        raise ValueError(f"no recording {source_file} in this database")
    if channels is None:
        return rows
    want = [int(c) for c in channels]
    have = {int(r["channel"]): r for r in rows}
    missing = [c for c in want if c not in have]
    if missing:
        raise ValueError(f"{source_file} has no channel(s) {missing} (it has {sorted(have)})")
    return [have[c] for c in sorted(set(want))]


def supply(n_samples, fs, scale_min, grid=None, offset=0):
    """How many windows a grid at this scale cuts from one channel."""
    length = int(round(float(scale_min) * 60.0 * float(fs)))
    grid = length if grid is None else int(grid)
    n = int(n_samples) - int(offset) - length
    return 0 if n < 0 else n // grid + 1


def build_unlabelled_set(conn, source_file, channels=None, scale_min=10, *, grid=None, offset=0,
                         exclude_artifacts=True, sample=None, seed=0, progress=None, cancel=None):
    """Cut one recording's channels into windows of `scale_min` minutes (module docstring)."""
    from Working.discovery.channels import channel_name

    refuse_held_out(source_file)
    scale_min = float(scale_min)
    if not scale_min > 0:
        raise ValueError(f"a window of {scale_min:g} minutes is not a window")
    rows = _recording_rows(conn, source_file, channels)
    fs = float(rows[0]["fs"])
    length = int(round(scale_min * 60.0 * fs))
    if length < 2:
        raise ValueError(f"{scale_min:g} min at {fs:g} Hz is under two samples")
    grid = length if grid is None else int(grid)
    if grid < length:
        raise ValueError(f"a grid of {grid} samples under a {length}-sample window would make the set's own windows "
                         "overlap; an unlabelled set is non-overlapping (stride ≥ window)")
    offset = int(offset)
    if not 0 <= offset < grid:
        raise ValueError(f"the grid offset must be in [0, {grid})")
    if sample is not None and int(sample) < 1:
        raise ValueError("a sample keeps at least one window")
    ex = _Exclusions(conn) if exclude_artifacts else None
    n_file_channels = int(conn.execute("SELECT COUNT(*) FROM recordings WHERE source_file = ?",
                                       (str(source_file),)).fetchone()[0])
    parts, per_channel = [], []
    for i, rec in enumerate(rows):
        if cancel is not None and cancel():
            raise InterruptedError("cancelled while building the window set")
        if progress is not None:
            progress(i, len(rows), f"cutting channel {channel_name(source_file, rec['channel'], n_file_channels)}")
        n = int(rec["n_samples"])
        starts = np.arange(offset, n - length + 1, grid, dtype=np.int64) if n >= offset + length else np.zeros(0, np.int64)
        keep = np.ones(len(starts), dtype=bool)
        c = {k: 0 for k in ("non_finite", "artifact_human", "excluded_by_settings")}
        x = np.load(rec["npy_path"], mmap_mode="r")
        finite = np.isfinite(x)
        if not finite.all():
            bad = np.concatenate([[0], np.cumsum(~finite, dtype=np.int64)])
            nf = (bad[starts + length] - bad[starts]) > 0
            c["non_finite"] = int((nf & keep).sum())
            keep &= ~nf
        if ex is not None:
            human, settings = ex.spans(rec)
            h = _touches(starts, length, human)
            c["artifact_human"] = int((h & keep).sum())
            keep &= ~h
            s = _touches(starts, length, settings)
            c["excluded_by_settings"] = int((s & keep).sum())
            keep &= ~s
        kept = starts[keep]
        parts.append(pd.DataFrame({"recording_id": np.full(len(kept), int(rec["id"]), np.int64),
                                   "channel": np.full(len(kept), int(rec["channel"]), np.int64),
                                   "start": kept, "length": np.full(len(kept), length, np.int64)}))
        per_channel.append({"channel": int(rec["channel"]), "recording_id": int(rec["id"]),
                            "name": channel_name(source_file, rec["channel"], n_file_channels), "n_samples": n,
                            "hours": round(n / fs / 3600.0, 2), "grid_windows": int(len(starts)), **c,
                            "sampled_out": 0, "n_windows": int(len(kept))})
    table = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame({c: [] for c in SET_COLUMNS})
    if sample is not None and int(sample) < len(table):
        rng = np.random.default_rng(int(seed))
        pick = np.sort(rng.choice(len(table), size=int(sample), replace=False))
        out_mask = np.ones(len(table), dtype=bool)
        out_mask[pick] = False
        dropped = table.loc[out_mask, "recording_id"].value_counts().to_dict()
        for pc in per_channel:
            pc["sampled_out"] = int(dropped.get(pc["recording_id"], 0))
            pc["n_windows"] -= pc["sampled_out"]
        table = table.iloc[pick].reset_index(drop=True)
    counts = {k: int(sum(pc[k] for pc in per_channel)) for k in ("grid_windows", *BUILD_DROP_KEYS, "n_windows")}
    meta = {
        "source_file": str(source_file), "identity": recording_identity(source_file),
        "scale_min": _scale_value(length, fs), "length": length, "grid": grid, "offset": offset, "fs": fs,
        "channels": [int(r["channel"]) for r in rows], "exclude_artifacts": bool(exclude_artifacts),
        "sample": None if sample is None else int(sample), "seed": int(seed),
        "labels": "ignored — windows are cut from the signal, labelled or not (RQ1 version 2)",
        "exclusions": EXCLUSIONS_RULE if exclude_artifacts else "artifact exclusion off",
        "counts": counts, "per_channel": per_channel,
    }
    if progress is not None:
        progress(len(rows), len(rows), f"{len(table):,} windows")
    return UnlabelledSet(table=table, meta=meta)


# ── the region plan ─────────────────────────────────────────────────────────

def make_plan(recordings, *, n_blocks=None, test_frac=None, validation_frac=None, gap_s=None, hold_out_pack=None,
              exam_channels=None):
    """The region plan over `recordings` = `{identity: {"duration_s", "n_channels", "source_files"}}`.

    `exam_channels`: a list applied to every recording, or `{identity: [...]}`;
    `hold_out_pack`: 'A'–'D', the whole pack's channels as exam on every recording."""
    p = dict(DEFAULT_PLAN)
    for k, v in (("n_blocks", n_blocks), ("test_frac", test_frac), ("validation_frac", validation_frac),
                 ("gap_s", gap_s)):
        if v is not None:
            p[k] = v
    p["n_blocks"], p["gap_s"] = int(p["n_blocks"]), float(p["gap_s"])
    p["test_frac"], p["validation_frac"] = float(p["test_frac"]), float(p["validation_frac"])
    if p["gap_s"] <= 0:
        raise ValueError("the gap between roles must be longer than zero (it is at least one window of the pool's "
                         "largest scale when a pool is combined)")
    pack = None
    if hold_out_pack not in (None, ""):
        pack = str(hold_out_pack).upper()
        if pack not in PACKS:
            raise ValueError(f"no pack {hold_out_pack!r}: the packs are {', '.join(PACKS)} "
                             "(CH1–4 A, CH5–8 B, CH9–12 C, CH13–16 D)")
    out = {"rule": "region_first", "split": "blocked_by_time", **p, "hold_out_pack": pack, "recordings": {},
           "note": ("roles are stretches of time on a channel, laid before any window is placed, the same for every "
                    "scale; a window has a role only if it lies wholly inside one stretch")}
    for ident, r in recordings.items():
        dur = float(r["duration_s"])
        n_ch = int(r["n_channels"])
        exam = set()
        if isinstance(exam_channels, dict):
            exam |= {int(c) for c in exam_channels.get(ident, [])}
        elif exam_channels:
            exam |= {int(c) for c in exam_channels}
        if pack:
            if max(PACKS[pack]) >= n_ch:
                raise ValueError(f"pack {pack} is CH{PACKS[pack][0] + 1}–{PACKS[pack][-1] + 1}; {ident} has only "
                                 f"{n_ch} channels")
            exam |= set(PACKS[pack])
        bad = sorted(c for c in exam if not 0 <= c < n_ch)
        if bad:
            raise ValueError(f"exam channel(s) {bad} are not channels of {ident} ({n_ch} channels)")
        if len(exam) >= n_ch:
            raise ValueError(f"every channel of {ident} is an exam channel: nothing would be trained on")
        sp = blocked_split(np.zeros(0, dtype=np.int64), 1, int(math.ceil(dur)), p["n_blocks"], p["test_frac"],
                           p["validation_frac"], 1)
        merged = []
        for b in sp.blocks:
            if merged and merged[-1]["role"] == b["role"]:
                merged[-1]["end_s"] = float(b["end"])
            else:
                merged.append({"role": b["role"], "start_s": float(b["start"]), "end_s": float(b["end"])})
        stretches = []
        for i, s in enumerate(merged):
            a = s["start_s"] + (p["gap_s"] if i > 0 else 0.0)
            if a < s["end_s"]:
                stretches.append({"role": s["role"], "start_s": a, "end_s": s["end_s"]})
        out["recordings"][ident] = {"source_files": sorted(r.get("source_files") or []), "duration_s": dur,
                                    "n_channels": n_ch, "exam_channels": sorted(exam), "stretches": stretches}
    return out


def plan_for(conn, source_files, **kw):
    """`make_plan` over the recordings these files hold (the fs1 / fs2 files of one
    recording become ONE entry, so they share their stretches)."""
    recs = {}
    for sf in source_files:
        refuse_held_out(sf)
        row = conn.execute("SELECT MAX(n_samples * 1.0 / fs), COUNT(*) FROM recordings WHERE source_file = ?",
                           (str(sf),)).fetchone()
        if not row or not row[1]:
            raise ValueError(f"no recording {sf} in this database")
        ident = recording_identity(sf)
        r = recs.setdefault(ident, {"duration_s": 0.0, "n_channels": 0, "source_files": []})
        r["duration_s"] = max(r["duration_s"], float(row[0]))
        r["n_channels"] = max(r["n_channels"], int(row[1]))
        if str(sf) not in r["source_files"]:
            r["source_files"].append(str(sf))
    return make_plan(recs, **kw)


def stretches_for(plan, source_file, channel):
    ident = recording_identity(source_file)
    rec = (plan.get("recordings") or {}).get(ident)
    if rec is None:
        raise PlanRefused(f"{source_file} is not covered by the region plan (it covers "
                          f"{', '.join(plan.get('recordings') or {}) or 'nothing'}); lay a plan over that recording "
                          "too, or leave the set out")
    if int(channel) in rec["exam_channels"]:
        return [{"role": "exam", "start_s": 0.0, "end_s": float(rec["duration_s"])}]
    return rec["stretches"]


def assign_roles(plan, source_file, channel, starts, lengths, fs):
    """One role per window: the stretch it lies wholly inside, else `gap` (inside no
    stretch) or `straddle` (across a stretch's edge)."""
    st = stretches_for(plan, source_file, channel)
    a = np.asarray(starts, dtype=np.float64) / float(fs)
    b = a + np.asarray(lengths, dtype=np.float64) / float(fs)
    s0 = np.array([s["start_s"] for s in st], dtype=np.float64)
    s1 = np.array([s["end_s"] for s in st], dtype=np.float64)
    role = np.array([s["role"] for s in st] + ["gap"], dtype=object)
    out = np.full(len(a), "gap", dtype=object)
    if not len(st) or not len(a):
        return out.astype(str)
    i = np.searchsorted(s0, a, side="right") - 1
    ok = i >= 0
    ii = np.where(ok, i, 0)
    inside = ok & (b <= s1[ii] + 1e-9)
    out[inside] = role[ii[inside]]
    touch_here = ok & (a < s1[ii])
    nxt = np.minimum(np.where(ok, i + 1, 0), len(st) - 1)
    touch_next = (np.where(ok, i + 1, 0) < len(st)) & (b > s0[nxt] + 1e-9)
    out[~inside & (touch_here | touch_next)] = "straddle"
    return out.astype(str)


# ── reading any saved set as plain windows ──────────────────────────────────

def _coverage(row):
    try:
        return json.loads(row["coverage_json"] or "{}") or {}
    except (TypeError, ValueError):
        return {}


def set_kind(conn, row):
    k = _coverage(row).get("set_kind")
    if k:
        return k
    if conn.execute("SELECT 1 FROM window_set_members WHERE window_set_id = ? LIMIT 1", (int(row["id"]),)).fetchone():
        return "labelled_across_channels"
    return "labelled_one_channel"


def window_set_row(conn, ref):
    if isinstance(ref, (int, np.integer)):
        ref = {"id": int(ref)}
    elif isinstance(ref, str):
        ref = {"id": int(ref)} if ref.isdigit() else {"name": ref}
    ref = dict(ref or {})
    if ref.get("id") is not None:
        row = conn.execute("SELECT * FROM window_sets WHERE id = ?", (int(ref["id"]),)).fetchone()
    else:
        row = conn.execute("SELECT * FROM window_sets WHERE name = ? ORDER BY version DESC LIMIT 1",
                           (str(ref.get("name")),)).fetchone()
    if row is None:
        raise ValueError(f"no saved window set {ref}")
    return row


def load_set(conn, ref):
    """`(row, UnlabelledSet)` of a saved unlabelled set, its key checked against the row."""
    row = window_set_row(conn, ref)
    if set_kind(conn, row) != "unlabelled":
        raise ValueError(f"window set {row['name']} v{row['version']} is not an unlabelled set")
    u = UnlabelledSet.load(row["path"])
    refuse_held_out(u.meta.get("source_file"))
    if row["recipe_hash"] and row["recipe_hash"] != u.key:
        raise ValueError(f"the files of {row['name']} v{row['version']} no longer match its key "
                         f"({row['recipe_hash']} in the row, {u.key} on disk)")
    return row, u


def _rec_index(conn):
    return {int(r["id"]): dict(r) for r in conn.execute(
        "SELECT id, source_file, channel, fs, n_samples, npy_path FROM recordings")}


def set_windows(conn, ref, index=None):
    """`(row, DataFrame[recording_id, source_file, channel, start, length, fs])` for ANY saved
    window set — unlabelled, a pool, a paired-job set across channels, a one-channel set.
    A set that carries its own split keeps it for its own job; here it is plain windows."""
    from Working.training import windows as tw
    row = window_set_row(conn, ref)
    kind = set_kind(conn, row)
    index = index if index is not None else _rec_index(conn)
    if kind == "unlabelled":
        _row, u = load_set(conn, {"id": int(row["id"])})
        t = u.table[["recording_id", "start", "length"]].copy()
    elif kind == "pool":
        _row, p = load_pool(conn, {"id": int(row["id"])})
        t = p.table[["recording_id", "start", "length"]].copy()
    elif kind == "labelled_across_channels":
        ps = tw.PooledSet.load(row["path"])
        tw.refuse_held_out(ps.meta.get("source_file"))
        t = ps.table[["recording_id", "start"]].copy()
        t["length"] = int(ps.meta["length"])
    else:
        from Adapters.catalogue_manual_labels import _saved_window_bounds
        if row["recording_id"] is None:
            raise ValueError(f"window set {row['name']} v{row['version']} names no recording and no channels")
        starts, length = _saved_window_bounds(row["path"], row["window_length"])
        t = pd.DataFrame({"recording_id": int(row["recording_id"]), "start": starts.astype(np.int64),
                          "length": int(length)})
    missing = sorted(set(t["recording_id"].astype(int)) - set(index))
    if missing:
        raise ValueError(f"window set {row['name']} v{row['version']} names recording row(s) {missing} that this "
                         "database does not hold")
    t["source_file"] = [index[int(r)]["source_file"] for r in t["recording_id"]]
    t["channel"] = [int(index[int(r)]["channel"]) for r in t["recording_id"]]
    t["fs"] = [float(index[int(r)]["fs"]) for r in t["recording_id"]]
    for sf in t["source_file"].unique():
        refuse_held_out(sf)
    t = t.astype({"recording_id": np.int64, "start": np.int64, "length": np.int64, "channel": np.int64})
    return row, t[["recording_id", "source_file", "channel", "start", "length", "fs"]].reset_index(drop=True)


def list_sets(conn):
    """Every saved window set, as the *Window pool* block lists them: id, name, version,
    kind, scale (None for a pool of several), windows, the files it draws from."""
    index = _rec_index(conn)
    out = []
    for row in conn.execute("SELECT * FROM window_sets ORDER BY id"):
        cov = _coverage(row)
        kind = set_kind(conn, row)
        rids = [int(r[0]) for r in conn.execute(
            "SELECT recording_id FROM window_set_channels WHERE window_set_id = ? UNION "
            "SELECT recording_id FROM window_set_members WHERE window_set_id = ?", (row["id"], row["id"]))]
        if row["recording_id"] is not None:
            rids.append(int(row["recording_id"]))
        files = sorted({index[r]["source_file"] for r in rids if r in index})
        fs = row["fs"] or (index[rids[0]]["fs"] if rids and rids[0] in index else None)
        scale = cov.get("scale_min")
        if scale is None and kind != "pool" and row["window_length"] and fs:
            scale = _scale_value(row["window_length"], fs)
        out.append({"id": int(row["id"]), "name": row["name"], "version": int(row["version"] or 1), "kind": kind,
                    "scale_min": scale, "scales_min": cov.get("scales_min"), "n_windows": int(row["n_windows"] or 0),
                    "source_files": files, "key": row["recipe_hash"], "path": row["path"],
                    "created_at": row["created_at"]})
    return out


# ── the pool ────────────────────────────────────────────────────────────────

@dataclass
class Pool:
    """`table`: one row per window (`POOL_COLUMNS`), its role from the plan.
    `meta`: the plan, the rule, the sample, the members and the counts."""
    table: pd.DataFrame
    meta: dict

    _HOW = ("plan", "rule", "sample", "seed", "recheck_artifacts")

    @property
    def key(self):
        t = self.table
        return _key({"kind": "window_pool", "how": {k: self.meta.get(k) for k in self._HOW},
                     "members": [m.get("key") for m in self.meta.get("members") or []]},
                    [t[c].to_numpy() for c in ("source_file", "channel", "start", "length", "role")])

    def save(self, d):
        os.makedirs(d, exist_ok=True)
        t = self.table
        np.savez_compressed(
            os.path.join(d, "pool_windows.npz"),
            **{c: (t[c].to_numpy().astype(str) if c in ("source_file", "role") else
                   t[c].to_numpy().astype(np.float64) if c in ("fs", "scale_min") else
                   t[c].to_numpy().astype(np.int64)) for c in POOL_COLUMNS})
        with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"kind": "window_pool", "key": self.key, **self.meta}, f, indent=2, default=str)
        return d

    @classmethod
    def load(cls, d):
        with np.load(os.path.join(d, "pool_windows.npz"), allow_pickle=False) as z:
            table = pd.DataFrame({c: (z[c].astype(str) if c in ("source_file", "role") else
                                      z[c].astype(np.float64) if c in ("fs", "scale_min") else
                                      z[c].astype(np.int64)) for c in POOL_COLUMNS})
        with open(os.path.join(d, "manifest.json"), encoding="utf-8") as f:
            meta = json.load(f)
        saved = meta.pop("key", None)
        meta.pop("kind", None)
        out = cls(table=table, meta=meta)
        if saved is not None and saved != out.key:
            raise ValueError(f"the pool at {d} does not match its own key ({saved} on disk, {out.key} recomputed): "
                             "its files were changed after it was saved")
        return out


def _union(a, b):
    """Sorted disjoint union of half-open intervals."""
    if not len(a):
        return a, b
    o = np.argsort(a, kind="stable")
    a, b = a[o], b[o]
    cm = np.maximum.accumulate(b)
    new = np.r_[True, a[1:] >= cm[:-1]]
    first = np.flatnonzero(new)
    return a[new], np.maximum.reduceat(b, first)


def _hits(a, b, ua, ub):
    """Per interval [a, b): does it overlap the sorted disjoint union (ua, ub)?"""
    if not len(ua) or not len(a):
        return np.zeros(len(a), dtype=bool)
    i = np.searchsorted(ua, b, side="left") - 1
    ok = i >= 0
    return ok & (ub[np.where(ok, i, 0)] > a)


def _sample_key(sample):
    return {f"{float(k):g}": int(v) for k, v in (sample or {}).items() if v is not None}


def combine(conn, sets, plan, *, rule=DEFAULT_RULE, sample=None, seed=0, recheck_artifacts=True, progress=None):
    """Combine saved window sets (an ordered list of ids / names / refs) under a region plan."""
    if rule not in RULES:
        raise ValueError(f"no rule {rule!r}: the rules are {', '.join(RULES)}")
    if not sets:
        raise ValueError("a pool needs at least one saved window set")
    sample = _sample_key(sample)
    index = _rec_index(conn)
    members, frames = [], []
    for pos, ref in enumerate(sets):
        if progress is not None:
            progress(pos, len(sets) + 3, f"reading set {pos + 1} of {len(sets)}")
        row, w = set_windows(conn, ref, index=index)
        for sf in w["source_file"].unique():
            if recording_identity(sf) not in (plan.get("recordings") or {}):
                raise PlanRefused(
                    f"window set {row['name']} v{row['version']} holds windows of {sf}, which the region plan does not "
                    f"cover (it covers {', '.join(plan.get('recordings') or {}) or 'nothing'}). Lay the plan over "
                    "that recording too, or leave the set out.")
        w["set_id"] = int(row["id"])
        w["position"] = pos
        cov = _coverage(row)
        members.append({"id": int(row["id"]), "name": row["name"], "version": int(row["version"] or 1),
                        "key": row["recipe_hash"], "kind": set_kind(conn, row), "n_offered": int(len(w)),
                        "at_build": {k: int((cov.get("counts") or {}).get(k, 0)) for k in BUILD_DROP_KEYS},
                        "dropped": {k: 0 for k in DROP_KEYS}, "n_kept": 0})
        frames.append(w)
    t = pd.concat(frames, ignore_index=True)
    t["scale_min"] = np.round(t["length"].to_numpy() / t["fs"].to_numpy() / 60.0, 6)
    t["identity"] = [recording_identity(s) for s in t["source_file"]]
    t["a_s"] = t["start"].to_numpy() / t["fs"].to_numpy()
    t["b_s"] = (t["start"].to_numpy() + t["length"].to_numpy()) / t["fs"].to_numpy()

    longest = float((t["length"] / t["fs"]).max()) if len(t) else 0.0
    if longest > float(plan["gap_s"]) + 1e-9:
        raise PlanRefused(f"the plan's gap ({plan['gap_s']:g} s) is shorter than the longest window in the pool "
                          f"({longest:g} s): a window of one role could sit within one window's length of another "
                          f"role's. Raise the gap to at least {longest:g} s.")

    dropped = {k: 0 for k in DROP_KEYS}

    def drop(mask, why):
        mask = np.asarray(mask, dtype=bool)
        if mask.any():
            for pos, n in pd.Series(t.loc[mask, "position"]).value_counts().items():
                members[int(pos)]["dropped"][why] += int(n)
            dropped[why] += int(mask.sum())
        return t.loc[~mask].reset_index(drop=True)

    # 1. roles from the plan
    role = np.empty(len(t), dtype=object)
    for (sf, ch), g in t.groupby(["source_file", "channel"], sort=False):
        role[g.index.to_numpy()] = assign_roles(plan, sf, ch, g["start"].to_numpy(), g["length"].to_numpy(),
                                                float(g["fs"].iloc[0]))
    t["role"] = role.astype(str)
    t = drop(t["role"].to_numpy() == "gap", "gap")
    t = drop(t["role"].to_numpy() == "straddle", "straddle")

    # 2. artifact spans now (a span labelled after a set was saved is still left out)
    if recheck_artifacts and len(t):
        if progress is not None:
            progress(len(sets), len(sets) + 3, "checking artifact spans")
        ex = _Exclusions(conn)
        hit = np.zeros(len(t), dtype=bool)
        for rid, g in t.groupby("recording_id", sort=False):
            human, settings = ex.spans(index[int(rid)])
            hit[g.index.to_numpy()] = _touches(g["start"].to_numpy(), g["length"].to_numpy(), human + settings)
        t = drop(hit, "artifact")

    # 3. exact duplicates — the first set listed wins
    t = t.sort_values(["position", "recording_id", "start"], kind="stable").reset_index(drop=True)
    t = drop(t.duplicated(subset=["recording_id", "start", "length"], keep="first").to_numpy(), "duplicate")

    # 4. within one scale no two windows overlap — the first set listed wins (on the recording's own time)
    over = np.zeros(len(t), dtype=bool)
    for _k, g in t.groupby(["identity", "channel", "scale_min"], sort=False):
        ka, kb = np.zeros(0), np.zeros(0)
        for _pos, gp in g.groupby("position", sort=True):
            gp = gp.sort_values("a_s", kind="stable")
            a, b = gp["a_s"].to_numpy(), gp["b_s"].to_numpy()
            ov = _hits(a, b, ka, kb)
            keep_idx = np.flatnonzero(~ov)
            if len(keep_idx) > 1 and (np.diff(a[keep_idx]) < (b - a)[keep_idx][:-1] - 1e-9).any():
                last, kept = -np.inf, []
                for j in keep_idx:
                    if a[j] >= last - 1e-9:
                        kept.append(j)
                        last = b[j]
                self_ov = np.ones(len(a), dtype=bool)
                self_ov[kept] = False
                ov = ov | self_ov
            over[gp.index.to_numpy()[ov]] = True
            ka, kb = _union(np.r_[ka, a[~ov]], np.r_[kb, b[~ov]])
    t = drop(over, "overlap_within_scale")

    # 5. a seeded uniform sample per scale
    if sample:
        rng = np.random.default_rng(int(seed))
        out = np.zeros(len(t), dtype=bool)
        for sc in sorted(t["scale_min"].unique()):
            want = sample.get(f"{float(sc):g}")
            idx = np.flatnonzero(t["scale_min"].to_numpy() == sc)
            if want is not None and want < len(idx):
                keep = rng.choice(len(idx), size=int(want), replace=False)
                m = np.ones(len(idx), dtype=bool)
                m[keep] = False
                out[idx[m]] = True
        t = drop(out, "sampled_out")

    # 6. the strict rule: no overlap across scales — the smaller scale wins
    if rule == "no_overlap":
        across = np.zeros(len(t), dtype=bool)
        for _k, g in t.groupby(["identity", "channel"], sort=False):
            ka, kb = np.zeros(0), np.zeros(0)
            for _sc, gs in g.groupby("scale_min", sort=True):
                a, b = gs["a_s"].to_numpy(), gs["b_s"].to_numpy()
                ov = _hits(a, b, ka, kb)
                across[gs.index.to_numpy()[ov]] = True
                ka, kb = _union(np.r_[ka, a[~ov]], np.r_[kb, b[~ov]])
        t = drop(across, "overlap_across_scales")

    t = t.sort_values(["source_file", "channel", "scale_min", "start"], kind="stable").reset_index(drop=True)
    for pos, n in t["position"].value_counts().items():
        members[int(pos)]["n_kept"] = int(n)
    t["scale_min"] = t["scale_min"].astype(np.float64)
    table = t[list(POOL_COLUMNS)].copy()
    meta = {"plan": plan, "rule": rule, "rule_text": RULES[rule], "sample": sample, "seed": int(seed),
            "recheck_artifacts": bool(recheck_artifacts), "members": members,
            "source_files": sorted(table["source_file"].unique().tolist())}
    pool = Pool(table=table, meta=meta)
    meta["counts"] = pool_counts(pool, dropped)
    meta["checks"] = check_pool(pool)
    if progress is not None:
        progress(len(sets) + 3, len(sets) + 3, f"{len(table):,} windows in the pool")
    return pool


def pool_counts(pool, dropped=None):
    t = pool.table
    by = []
    for (sf, sc, r), n in t.groupby(["source_file", "scale_min", "role"]).size().items():
        by.append({"recording": sf, "scale_min": _scale_value(sc * 60.0, 1.0), "role": r, "n": int(n)})
    at_build = {k: sum(int(m["at_build"].get(k, 0)) for m in pool.meta.get("members") or []) for k in BUILD_DROP_KEYS}
    return {"n_windows": int(len(t)), "by": by,
            "by_role": {r: int((t["role"] == r).sum()) for r in ROLES},
            "by_scale": {f"{float(s):g}": int(n) for s, n in t["scale_min"].value_counts().sort_index().items()},
            "dropped": dict(dropped if dropped is not None else (pool.meta.get("counts") or {}).get("dropped") or {}),
            "at_build": at_build}


def check_pool(pool):
    """The leakage checks of a pool, as counts; raises `LeakageRefused` when a
    window sits inside another role's stretch or two roles overlap in time."""
    t = pool.table
    plan = pool.meta["plan"]
    misplaced = 0
    for (sf, ch), g in t.groupby(["source_file", "channel"], sort=False):
        want = assign_roles(plan, sf, ch, g["start"].to_numpy(), g["length"].to_numpy(), float(g["fs"].iloc[0]))
        misplaced += int((want != g["role"].to_numpy().astype(str)).sum())
    a_all = t["start"].to_numpy() / t["fs"].to_numpy()
    b_all = (t["start"].to_numpy() + t["length"].to_numpy()) / t["fs"].to_numpy()
    ident = np.array([recording_identity(s) for s in t["source_file"]], dtype=object)
    cross_role = cross_scale = within_scale = 0
    frame = pd.DataFrame({"ident": ident, "channel": t["channel"].to_numpy(), "role": t["role"].to_numpy(),
                          "scale": t["scale_min"].to_numpy(), "a": a_all, "b": b_all})
    for _k, g in frame.groupby(["ident", "channel"], sort=False):
        unions = {r: _union(gr["a"].to_numpy(), gr["b"].to_numpy()) for r, gr in g.groupby("role")}
        for r, gr in g.groupby("role"):
            for r2, (ua, ub) in unions.items():
                if r2 != r:
                    cross_role += int(_hits(gr["a"].to_numpy(), gr["b"].to_numpy(), ua, ub).sum())
            for sc, gs in gr.groupby("scale"):
                a, b = gs["a"].to_numpy(), gs["b"].to_numpy()
                o = np.argsort(a, kind="stable")
                within_scale += int((a[o][1:] < b[o][:-1] - 1e-9).sum())
                other = gr[gr["scale"] != sc]
                ua, ub = _union(other["a"].to_numpy(), other["b"].to_numpy())
                cross_scale += int(_hits(a, b, ua, ub).sum())
    checks = {"windows inside another role's stretch": misplaced, "overlaps across roles": cross_role,
              "overlaps within a scale": within_scale, "overlaps across scales (allowed)": cross_scale}
    if misplaced or cross_role:
        raise LeakageRefused(
            f"the pool leaks across roles: {misplaced} window(s) sit outside their own role's stretch and "
            f"{cross_role} overlap a window of another role on one recording's time (the fs1 / fs2 files of one "
            "recording included). A pool's roles come from its plan and nothing else.")
    if pool.meta.get("rule") == "no_overlap":
        checks["overlaps across scales (allowed)"] = cross_scale
    return checks


# ── saving ──────────────────────────────────────────────────────────────────

def _next_version(conn, name):
    top = conn.execute("SELECT MAX(version) FROM window_sets WHERE name = ?", (str(name),)).fetchone()[0]
    return int(top or 0) + 1


def save_unlabelled_set(conn, u, root, name, notes=None):
    """One `window_sets` row (no recording, no roles) + a `window_set_channels` row per channel."""
    version = _next_version(conn, name)
    d = os.path.join(str(root), f"{name}_v{version}")
    u.save(d)
    m = u.meta
    coverage = {"set_kind": "unlabelled", "scale_min": m["scale_min"], "length": m["length"], "grid": m["grid"],
                "offset": m["offset"], "channels": m["channels"], "exclude_artifacts": m["exclude_artifacts"],
                "exclusions": m["exclusions"], "sample": m["sample"], "seed": m["seed"], "labels": m["labels"],
                "counts": m["counts"], "labelled_windows": 0, "notes": notes,
                "supply_note": (f"{m['counts']['grid_windows']:,} windows on the grid; "
                                f"{m['counts']['n_windows']:,} kept")}
    cur = conn.execute(
        "INSERT INTO window_sets (name, version, path, recording_id, channel, fs, window_length, stride, gap, "
        "n_windows, split_json, spacing_json, coverage_json, labels_source, recipe_hash, created_at) "
        "VALUES (?, ?, ?, NULL, NULL, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)",
        (str(name), version, d, float(m["fs"]), int(m["length"]), int(m["grid"]), int(len(u.table)),
         json.dumps({"rule": "none", "note": "no roles: the train / test fence is laid over the pool that combines "
                                             "this set (a region-first plan, fixup-af)"}),
         json.dumps({"no two windows overlap": True}), json.dumps(coverage, default=str),
         f"unlabelled · cut from the signal, manual labels ignored · {m['source_file']} · {m['scale_min']} min · "
         f"{len(m['channels'])} channel(s)", u.key, _now()))
    ws_id = int(cur.lastrowid)
    for pc in m["per_channel"]:
        conn.execute("INSERT INTO window_set_channels (window_set_id, recording_id, channel, n_windows, counts_json) "
                     "VALUES (?, ?, ?, ?, ?)", (ws_id, int(pc["recording_id"]), int(pc["channel"]),
                                                int(pc["n_windows"]), json.dumps(pc, default=str)))
    conn.commit()
    return ws_id


def save_pool(conn, pool, root, name, notes=None):
    """The pool as a `window_sets` row, its members in order, its channels."""
    version = _next_version(conn, name)
    d = os.path.join(str(root), f"{name}_v{version}")
    pool.save(d)
    t, m = pool.table, pool.meta
    counts = m.get("counts") or pool_counts(pool)
    fss = sorted(set(t["fs"].tolist()))
    lengths = sorted(set(t["length"].tolist()))
    fs = fss[0] if len(fss) == 1 else None
    plan = m["plan"]
    split = {"rule": "region_first", **{r: counts["by_role"][r] for r in ROLES}, "plan": plan,
             "note": "roles are stretches of time laid before any window was placed; a window has a role only if it "
                     "lies wholly inside one stretch"}
    spacing = {"no two windows of one scale overlap": True, "no window of one role inside another role's stretch": True,
               "no overlap across roles (fs1 / fs2 included)": True,
               f"gap ≥ the longest window ({plan['gap_s']:g} s)": True}
    if m["rule"] == "no_overlap":
        spacing["no overlap across scales (smaller scale wins)"] = True
    scales = sorted({_scale_value(s * 60.0, 1.0) for s in t["scale_min"].unique()})
    coverage = {"set_kind": "pool", "rule": m["rule"], "rule_text": m["rule_text"], "scales_min": scales,
                "sample": m["sample"], "seed": m["seed"], "counts": counts, "dropped": counts["dropped"],
                "checks": m.get("checks"), "members": [mm["name"] for mm in m["members"]],
                "hold_out_pack": plan.get("hold_out_pack"), "labelled_windows": 0, "notes": notes,
                "labels": "ignored — a pool is windows and roles; labels are read where the pool is used"}
    pack = plan.get("hold_out_pack")
    cur = conn.execute(
        "INSERT INTO window_sets (name, version, path, recording_id, channel, fs, window_length, stride, gap, "
        "n_windows, split_json, spacing_json, coverage_json, labels_source, recipe_hash, created_at) "
        "VALUES (?, ?, ?, NULL, NULL, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)",
        (str(name), version, d, fs, int(lengths[0]) if len(lengths) == 1 else None,
         int(round(plan["gap_s"] * fs)) if fs else None, int(len(t)), json.dumps(split, default=str),
         json.dumps(spacing), json.dumps(coverage, default=str),
         f"pool of {len(m['members'])} window set(s) · region-first plan"
         f"{f' · pack {pack} held out' if pack else ''} · {m['rule']}", pool.key, _now()))
    ws_id = int(cur.lastrowid)
    for pos, mm in enumerate(m["members"]):
        conn.execute("INSERT INTO window_pool_members (pool_id, member_set_id, position, n_offered, n_kept, counts_json) "
                     "VALUES (?, ?, ?, ?, ?, ?)", (ws_id, int(mm["id"]), pos, int(mm["n_offered"]), int(mm["n_kept"]),
                                                   json.dumps(mm, default=str)))
    for rid, g in t.groupby("recording_id"):
        per = {"by_role": {r: int((g["role"] == r).sum()) for r in ROLES},
               "by_scale": {f"{float(s):g}": int(n) for s, n in g["scale_min"].value_counts().sort_index().items()}}
        conn.execute("INSERT INTO window_set_channels (window_set_id, recording_id, channel, n_windows, counts_json) "
                     "VALUES (?, ?, ?, ?, ?)", (ws_id, int(rid), int(g["channel"].iloc[0]), int(len(g)),
                                                json.dumps(per)))
    conn.commit()
    return ws_id


def load_pool(conn, ref):
    """`(row, Pool)`: the same windows and the same key as when it was saved."""
    row = window_set_row(conn, ref)
    if set_kind(conn, row) != "pool":
        raise ValueError(f"window set {row['name']} v{row['version']} is not a pool")
    pool = Pool.load(row["path"])
    for sf in pool.meta.get("source_files") or []:
        refuse_held_out(sf)
    if row["recipe_hash"] and row["recipe_hash"] != pool.key:
        raise ValueError(f"the files of pool {row['name']} v{row['version']} no longer match its key "
                         f"({row['recipe_hash']} in the row, {pool.key} on disk)")
    return row, pool


# ── the printout ────────────────────────────────────────────────────────────

_DROP_WORDS = {"gap": "in a gap", "straddle": "straddling a role boundary", "artifact": "artifact (checked again)",
               "duplicate": "exact duplicates", "overlap_within_scale": "overlap within a scale",
               "overlap_across_scales": "overlap across scales", "sampled_out": "sampled out"}
_BUILD_WORDS = {"artifact_human": "artifact (human label)", "excluded_by_settings": "excluded by Settings",
                "non_finite": "non-finite samples", "sampled_out": "sampled out"}


def _fmt_scale(s):
    return f"{s:g} min"


def set_summary(u, name=None, version=None):
    m, c = u.meta, u.meta["counts"]
    head = f"{name} v{version} · " if name else ""
    return (f"{head}{m['source_file']} · {_fmt_scale(m['scale_min'])} ({m['length']} samples, grid {m['grid']}) · "
            f"{len(m['channels'])} channels · {c['n_windows']:,} windows of {c['grid_windows']:,} on the grid · "
            f"left out: artifact (human label) {c['artifact_human']:,} · excluded by Settings "
            f"{c['excluded_by_settings']:,} · non-finite {c['non_finite']:,} · sampled out {c['sampled_out']:,} · "
            f"key {u.key}")


def pool_summary(pool, name=None, version=None, key=None):
    m = pool.meta
    plan = m["plan"]
    c = m.get("counts") or pool_counts(pool)
    lines = [f"pool {name + ' v' + str(version) + ' · ' if name else ''}key {key or pool.key} · {c['n_windows']:,} windows",
             f"rule {m['rule']}: {m['rule_text']}"]
    pack = plan.get("hold_out_pack")
    lines.append(f"plan: region-first, blocked by time · {plan['n_blocks']} blocks · test {plan['test_frac']:g} · "
                 f"validation {plan['validation_frac']:g} · gap {plan['gap_s'] / 60.0:g} min · "
                 + (f"pack {pack} (CH{PACKS[pack][0] + 1}–{PACKS[pack][-1] + 1}) held out as exam" if pack else "no pack held out"))
    for ident, r in plan["recordings"].items():
        st = " · ".join(f"{s['role']} {s['start_s'] / 3600:.1f}–{s['end_s'] / 3600:.1f} h" for s in r["stretches"])
        lines.append(f"  {ident}: {r['duration_s'] / 3600:.1f} h · exam channels "
                     f"{[x + 1 for x in r['exam_channels']] or 'none'} (one-based) · {st}")
    if m.get("sample"):
        lines.append(f"sample per scale (seed {m['seed']}): " + ", ".join(f"{k} min → {v:,}" for k, v in m["sample"].items()))
    lines.append("members, in order (the first listed wins a duplicate or an overlap):")
    for i, mm in enumerate(m["members"], 1):
        lines.append(f"  {i}. {mm['name']} v{mm['version']} ({mm['kind']}, key {mm['key']}) · offered "
                     f"{mm['n_offered']:,} · kept {mm['n_kept']:,}")
    lines.append("windows per recording × scale × role:")
    lines.append(f"  {'recording':<28}{'scale':>8}" + "".join(f"{r:>12}" for r in ROLES) + f"{'total':>10}")
    cells = {(b["recording"], b["scale_min"], b["role"]): b["n"] for b in c["by"]}
    for sf in sorted({b["recording"] for b in c["by"]}):
        for sc in sorted({b["scale_min"] for b in c["by"] if b["recording"] == sf}):
            row = [cells.get((sf, sc, r), 0) for r in ROLES]
            lines.append(f"  {sf:<28}{_fmt_scale(sc):>8}" + "".join(f"{v:>12,}" for v in row) + f"{sum(row):>10,}")
    tot = [c["by_role"][r] for r in ROLES]
    lines.append(f"  {'all':<28}{'':>8}" + "".join(f"{v:>12,}" for v in tot) + f"{sum(tot):>10,}")
    d = c.get("dropped") or {}
    lines.append("dropped when combined: " + " · ".join(f"{_DROP_WORDS[k]} {int(d.get(k, 0)):,}" for k in DROP_KEYS))
    ab = c.get("at_build") or {}
    lines.append("left out when the sets were built: " + " · ".join(
        f"{_BUILD_WORDS[k]} {int(ab.get(k, 0)):,}" for k in ("artifact_human", "excluded_by_settings", "non_finite",
                                                            "sampled_out")))
    ch = m.get("checks") or check_pool(pool)
    lines.append("checks: " + " · ".join(f"{k}: {v:,}" for k, v in ch.items()))
    return "\n".join(lines)
