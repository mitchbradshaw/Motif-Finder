"""Library routes (stage-3 Prompt 03) — `/api/library/...`.

Thin over ``Working.library``: identity, dedupe, revisions, hand edits, the
grouping engine and the four importers all live in the core and are called
here, never reimplemented. What this module adds is presentation — the
payload shapes `webui/client/src/fixtures/library.ts` declares, built from
real rows instead of synthesised ones.

Three things this file is deliberate about.

**Real waveforms.** Every trace the Library draws today is synthesised in the
browser by ``motifShape(kind, amp, seed)``. Here ``exemplarTrace`` and
``medoidTrace`` are decimated mV read off the channel memmap through
``decimate.envelope`` — rule 4, the bulk array never enters the database and
never reaches the client whole.

**Two recording identifiers, reconciled.** The fixtures use a key
(``M2_aug_fs1``) for cell and coverage keys and a *label* (``M2_aug fs1``) on
``Member.recording`` and ``OmittedEntry.recording``. Both are emitted: the
declared field keeps the label the type promises, and a sibling
``recordingKey`` carries the key, so a page that wants to cross-reference a
cell no longer has to guess the transform.

**Absent is not unlooked-at.** Spec §8.4: a cell with no reviewed coverage
and no members must not look like one a person examined and found nothing in.
``Cell.noCoverage`` is what tells them apart, and it is computed from
``reviewed_spans``, not from the member count.

Every write goes through ``writes.write_human`` / ``writes.write_machine``
(rule 5, §3.5 of the standard). Errors are never swallowed: a bad read raises
and the app's handler turns it into a 500 with the traceback.
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import math
import os
import re
import sqlite3
import time

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from Working.library import hand_edits as hand_edits_mod
from Working.library.grouping import bases as bases_mod
from Working.library.grouping import engine as engine_mod
from Working.library.importers import annotations as ann_importer
from Working.library.importers import catalogue as cat_importer
from Working.library.importers import event_store as store_importer
from Working.library.importers import sequences as seq_importer

from . import corpus, decimate, writes
from .runtime import HELD_OUT_FILE, REPO_ROOT

router = APIRouter(prefix="/api/library")

#: The recording token inside the held-out file name: 'M4_aug_concat_fs1.mat'
#: -> 'M4_aug'. A bundle on disk is named after the recording, not the .mat, so
#: `M4_aug_holdout` has to be recognised by this stem rather than by the whole
#: file name — otherwise the refusal only fires for a path nobody types.
HELD_OUT_STEM = HELD_OUT_FILE.split("_concat")[0]


def _is_held_out_path(path) -> bool:
    text = str(path or "").replace("\\", "/")
    base = os.path.basename(text)
    return HELD_OUT_FILE in text or base.startswith(HELD_OUT_STEM)

# ── conventions ─────────────────────────────────────────────────────────────

#: `fixtures/canon.ts` FAMILY_COLOURS, F-01…F-11, verbatim. A live family id
#: outside that range would get `undefined` client-side, so the bridge emits a
#: colour on every family row and cycles this palette by index.
FAMILY_PALETTE = [
    "#5856D6", "#E85AAD", "#30B0C7", "#A2845E", "#8E9C3A", "#64D2FF",
    "#7A8FA6", "#6D4C41", "#F4A6C8", "#1E6F7A", "#C97B63",
]

#: `groupings.unit` (the CHECK constraint) -> the client's `Unit`.
UNIT_TO_CLIENT = {"single_motifs": "motifs", "sequences": "sequences", "spike_trains": "spike-trains"}
UNIT_TO_DB = {v: k for k, v in UNIT_TO_CLIENT.items()}

#: `bases.BASES` kind -> the client's `BasisOption.group`.
BASIS_GROUP = {"distance": "distance", "feature-bins": "feature bins · no distance", "labels": "labels"}

#: The client's `ShapeKind`. A family's shape is read off its tags when one of
#: them names a shape, and falls back to 'drop' — the detector that produced
#: the seed corpus is a drop detector, so that is the honest default rather
#: than a guess dressed as a finding.
SHAPE_KINDS = ("drop", "burst", "sharkfin", "spiketrain", "ripple", "plateau", "drift", "fall", "peak", "notch")

#: `AMP_DOMAIN` from the fixtures: the amplitude histogram's fixed extent.
AMP_DOMAIN = (0.1, 0.4)
AMP_BINS = 12

#: Trace lengths the pages expect: `motifShape` default n=120, sequences 160.
#: `decimate.envelope` emits about 2*px points, so px is half the target.
MOTIF_TRACE_PX = 60
SEQUENCE_TRACE_PX = 80

#: How many entries the grouping editor's distributions are computed over. The
#: real catalogue holds thousands and every one costs a memmap slice; the cap
#: is reported on the payload (`distributionsSampledFrom`) so a number drawn
#: from a sample is never mistaken for a census.
EDITOR_SAMPLE_CAP = 600

#: `recordings.fs_source` values that mean the sampling rate was WORKED OUT
#: rather than read. 'unrecorded' is deliberately not one of them: no claim was
#: made, which is a different thing from a claim that was inferred, and
#: conflating them stamps the warning on everything until it means nothing.
FS_INFERRED = ("inferred", "assumed", "provisional", "estimated")

#: Channels listed on a RecGroup before the rest become `hiddenChannels`.
CHANNELS_SHOWN = 8

TEMPLATE_GLYPHS = [
    ("bandpass", "bandpass"), ("lowpass", "lowpass"), ("highpass", "bandpass"),
    ("matrix_profile", "matrix_profile"), ("discord", "matrix_profile"), ("motif", "matrix_profile"),
    ("threshold", "threshold"), ("baseline", "baseline"), ("detrend", "baseline"),
    ("sax", "sax"), ("drop", "drop_detection"), ("seed", "seeded_search"),
    ("window_matrix", "window_matrix"), ("windowset", "sliding_windows"), ("window", "sliding_windows"),
    ("image", "image_encode"), ("encode", "image_encode"), ("encoding", "image_encode"),
    ("cluster", "cluster"), ("surrogate", "surrogate"), ("null", "surrogate"),
    ("spike", "spike"), ("wavelet", "spike"),
    ("cnn", "model"), ("classifier", "model"), ("model", "model_stage"),
    ("source", "source"), ("load", "source"),
]


# ── small helpers ───────────────────────────────────────────────────────────

def _rt(request: Request):
    return request.app.state.rt


def _conn(request: Request) -> sqlite3.Connection:
    rt = _rt(request)
    if not getattr(request.app.state, "schema_ensured", False):
        from Working.database.schema import init_db
        init_db(rt.db_path).close()
        request.app.state.schema_ensured = True
    return corpus.connect(rt.db_path)


def rec_key(source_file: str) -> str:
    """`M2_aug_concat_fs1.mat` -> `M2_aug_fs1`, the fixtures' RecGroup.key."""
    stem = os.path.splitext(os.path.basename(str(source_file or "")))[0]
    return stem.replace("_concat", "")


def rec_label(source_file: str) -> str:
    """`M2_aug_concat_fs1.mat` -> `M2_aug fs1`, the form Member.recording carries."""
    return re.sub(r"_(fs\d+)$", r" \1", rec_key(source_file))


def gid_str(row_id) -> str:
    """`7` -> `'g-07'`. The client's `nextGroupingId` parses `g-NN` with
    `Number(id.slice(2))`, so the id must be `g-` plus a plain integer; it is
    zero-padded to two places because every fixture id is."""
    return f"g-{int(row_id):02d}"


def gid_int(value) -> int | None:
    """`'g-07'`, `'7'` or `7` -> `7`; anything else -> None (a 404, not a 500)."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    m = re.fullmatch(r"(?:g-)?(\d+)", text)
    return int(m.group(1)) if m else None


def family_colour(index: int) -> str:
    return FAMILY_PALETTE[int(index) % len(FAMILY_PALETTE)]


def _iso_to_human(value) -> str:
    """`'2026-09-14T11:02:00'` -> `'14 Sep 2026'`, the fixtures' `computed`."""
    if not value:
        return ""
    try:
        return _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d %b %Y")
    except ValueError:
        return str(value)


def _f(value, default=0.0) -> float:
    """A finite float, or the default. JSON has no NaN and the pages have no
    branch for one, so a NaN that escaped here would render as a blank cell
    rather than as the missing measurement it is."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


def _params_text(params: dict) -> str:
    """A grouping's params as the one-line chip text the bar renders."""
    if not params:
        return "defaults"
    parts = []
    for k, v in sorted(params.items()):
        if isinstance(v, float):
            v = f"{v:g}"
        parts.append(f"{k} {v}")
    return " · ".join(parts)


def _refuse_held_out(source_file: str) -> None:
    if str(source_file or "").endswith(HELD_OUT_FILE) or os.path.basename(str(source_file or "")) == HELD_OUT_FILE:
        raise HTTPException(status_code=423, detail=(
            f"{HELD_OUT_FILE} is held out: the bridge refuses every request for it, "
            "in both runtime modes. No Library route reads it and no import writes it."))


# ── the recording index ─────────────────────────────────────────────────────

def _recordings_index(conn) -> dict:
    """`recording_id -> {...}` plus the per-file grouping the pages call a
    RecGroup. One pass; every read below shares it."""
    groups = corpus.recordings(conn)
    by_id, by_key = {}, {}
    for g in groups:
        key = rec_key(g["source_file"])
        by_key[key] = g
        for ch in g["channels"]:
            by_id[int(ch["id"])] = {
                "recording_id": int(ch["id"]), "source_file": g["source_file"],
                "key": key, "label": rec_label(g["source_file"]),
                "channel": int(ch["channel"]), "name": ch["name"],
                "fs": float(g["fs"]), "n_samples": int(g["n_samples"]),
                "held_out": bool(g["held_out"]), "npy_exists": bool(ch["npy_exists"]),
            }
    # npy_path is not on corpus.recordings(); fetch it once for the traces
    for r in conn.execute("SELECT id, npy_path FROM recordings"):
        if int(r["id"]) in by_id:
            by_id[int(r["id"])]["npy_path"] = r["npy_path"]
    return {"by_id": by_id, "by_key": by_key, "groups": groups}


def _rec_groups(conn, index) -> list[dict]:
    """`RecGroup[]` — the recurrence matrix's rows."""
    reviewed = _reviewed_fraction(conn, index)
    out = []
    for g in index["groups"]:
        key = rec_key(g["source_file"])
        names = [c["name"] for c in g["channels"]]
        shown = [] if g["held_out"] else names[:CHANNELS_SHOWN]
        pcts = [reviewed.get(f"{key}:{n}", 0.0) for n in names] or [0.0]
        row = {
            "key": key, "label": rec_label(g["source_file"]),
            "hours": round(_f(g["duration_h"]), 2),
            "reviewedPct": round(100.0 * (sum(pcts) / len(pcts)), 1),
            "channels": shown,
            "hiddenChannels": 0 if g["held_out"] else max(0, len(names) - len(shown)),
        }
        src = str(g.get("fs_source") or "unrecorded")
        if src in FS_INFERRED:
            # L_LM_Jul26_J's 10 Hz is inferred, not read — say so on the row
            row["fsNote"] = f"{_f(g['fs']):g} Hz {src}"
        if g["held_out"]:
            row["heldOut"] = True
        parent = g.get("excerpt_of")
        if parent and parent.get("source_file"):
            row["resampleOf"] = rec_key(parent["source_file"])
        out.append(row)
    return out


def _reviewed_fraction(conn, index) -> dict:
    """`'<recKey>:<channel>' -> 0…1` of the channel a person has looked at.

    Overlapping spans are **merged** before they are summed. A window reviewed
    twice is one window seen, not two: summing the raw rows over-counted every
    re-reviewed channel (recording 1: 531,275 samples summed against 476,753
    merged, a 11% over-statement), and the `min(1.0, …)` clamp hid the error
    entirely once a channel crossed 100%. Reviewed-% is the denominator a
    researcher uses to decide whether a family's absence from a channel means
    anything, so it has to be the union.
    """
    out = {}
    try:
        rows = conn.execute(
            "SELECT recording_id, start_idx, end_idx FROM reviewed_spans "
            "ORDER BY recording_id, start_idx").fetchall()
    except sqlite3.OperationalError:
        return out
    merged = {}                      # recording_id -> [samples seen, cursor]
    for r in rows:
        rid = int(r["recording_id"])
        start, end = int(r["start_idx"] or 0), int(r["end_idx"] or 0)
        if end <= start:
            continue
        state = merged.setdefault(rid, [0, None])
        if state[1] is None or start >= state[1]:
            state[0] += end - start
            state[1] = end
        elif end > state[1]:
            state[0] += end - state[1]
            state[1] = end
    for rid, (seen, _cursor) in merged.items():
        meta = index["by_id"].get(rid)
        if meta is None or meta["n_samples"] <= 0:
            continue
        out[f"{meta['key']}:{meta['name']}"] = min(1.0, seen / meta["n_samples"])
    return out


# ── traces (rule 4: decimated off the memmap, never whole) ──────────────────

def _trace(index, recording_id, start_idx, end_idx, px=MOTIF_TRACE_PX) -> list:
    """Real decimated mV for one span. `[]` when the channel is not on disk —
    an empty trace draws as an empty plot, which is honest; a synthesised one
    would draw as a finding that is not there."""
    meta = index["by_id"].get(int(recording_id or 0))
    if meta is None or meta.get("held_out"):
        return []
    path = meta.get("npy_path")
    if not path or not os.path.isfile(path):
        return []
    x = corpus.load_channel(path)
    env = decimate.envelope(x, meta["fs"], int(start_idx or 0), int(end_idx or 0), int(px))
    return [0.0 if v is None else round(_f(v), 5) for v in env["v"]]


def _amplitude_mv(trace) -> float:
    return round(float(np.ptp(np.asarray(trace, dtype=float))), 4) if trace else 0.0


#: Peak-to-peak per span, memoised. A member's amplitude is a property of its
#: span and never changes, but reading it cost one `decimate.envelope` call
#: each — 3000 members made the Atlas a 4.7 s read. `np.ptp` over the memmap
#: slice is the same number for a fraction of the work, and the cache means the
#: second request pays nothing at all. Bounded so a long-lived server cannot
#: grow it without limit.
_AMP_CACHE: dict = {}
_AMP_CACHE_MAX = 50000


def _span_amplitude(index, recording_id, start_idx, end_idx) -> float:
    """Peak-to-peak mV of one span, straight off the memmap.

    Rule 4 holds: a bounded slice is read to produce one number, and the array
    itself never leaves this function.
    """
    key = (int(recording_id or 0), int(start_idx or 0), int(end_idx or 0))
    hit = _AMP_CACHE.get(key)
    if hit is not None:
        return hit
    meta = index["by_id"].get(key[0])
    if meta is None or meta.get("held_out"):
        return 0.0
    path = meta.get("npy_path")
    if not path or not os.path.isfile(path):
        return 0.0
    x = corpus.load_channel(path)
    seg = np.asarray(x[key[1]:key[2]], dtype=float)
    if seg.size == 0:
        value = 0.0
    else:
        finite = seg[np.isfinite(seg)]
        value = round(float(np.ptp(finite)), 4) if finite.size else 0.0
    if len(_AMP_CACHE) < _AMP_CACHE_MAX:
        _AMP_CACHE[key] = value
    return value


def _snr_db(trace) -> float:
    """A rough SNR for the family card: peak-to-peak against the median
    absolute successive difference, which estimates the sample-to-sample noise
    without assuming the span is mostly baseline."""
    a = np.asarray(trace, dtype=float)
    if a.size < 3:
        return 0.0
    noise = float(np.median(np.abs(np.diff(a))))
    ptp = float(np.ptp(a))
    if noise <= 0 or ptp <= 0:
        return 0.0
    return round(20.0 * math.log10(ptp / noise), 1)


def _amp_domain(values) -> tuple:
    """The extent the amplitude axis is drawn at, measured from the values.

    `AMP_DOMAIN` — the fixture's (0.1, 0.4) mV — is a fixture's number, and on
    this catalogue the real depths run about 0.006 to 0.015 mV: an order of
    magnitude below its floor. Binning against it put **every** member of
    **every** family in bin 0 and drew an axis labelled 0.1 / 0.25 / 0.4 over
    data that is nowhere near it. A histogram that is one full bar and eleven
    empty ones, under an axis stating a range the data does not occupy, is a
    picture that says something false.

    So the domain is the values' own range, padded a little so the end bars are
    not flush against the axis, and it is echoed to the client as `ampDomain`
    so the axis is drawn from the same numbers the bars were counted with.
    `AMP_DOMAIN` stays as the fallback for an empty or degenerate family.
    """
    a = np.asarray([v for v in values if math.isfinite(v)], dtype=float)
    if a.size == 0:
        return AMP_DOMAIN
    lo, hi = float(a.min()), float(a.max())
    if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
        # every member at one amplitude: a domain of zero width has no bins
        centre = lo if math.isfinite(lo) else AMP_DOMAIN[0]
        pad = abs(centre) * 0.1 or 0.01
        return (centre - pad, centre + pad)
    pad = (hi - lo) * 0.05
    return (lo - pad, hi + pad)


def _amp_bins(values, domain=None) -> list:
    """Exactly 12 counts over `domain`, the extent the axis is drawn at.
    Values outside it land in the end bins rather than vanishing."""
    a = np.asarray([v for v in values if math.isfinite(v)], dtype=float)
    if a.size == 0:
        return [0] * AMP_BINS
    lo, hi = domain or _amp_domain(values)
    if hi <= lo:
        return [int(a.size)] + [0] * (AMP_BINS - 1)
    idx = np.clip(((a - lo) / (hi - lo) * AMP_BINS).astype(int), 0, AMP_BINS - 1)
    return np.bincount(idx, minlength=AMP_BINS)[:AMP_BINS].astype(int).tolist()


# ── grouping rows ───────────────────────────────────────────────────────────

def _grouping_rows(conn) -> list:
    return list(conn.execute("SELECT * FROM groupings ORDER BY id"))


def _grouping_row(conn, grouping_id):
    gid = gid_int(grouping_id)
    if gid is None:
        return None
    return conn.execute("SELECT * FROM groupings WHERE id = ?", (gid,)).fetchone()


def _default_grouping(conn, unit_db="single_motifs"):
    return conn.execute(
        "SELECT * FROM groupings WHERE unit = ? ORDER BY id DESC LIMIT 1", (unit_db,)).fetchone()


def _resolve_grouping(conn, grouping, unit_db="single_motifs"):
    """The grouping a read is about: the one asked for, else the newest of that
    unit. Returns None when the caller named one that does not exist — the
    route turns that into an empty payload, never a 500."""
    if grouping in (None, "", "undefined", "null"):
        return _default_grouping(conn, unit_db)
    return _grouping_row(conn, grouping)


def _hand_edits_kept(conn, grouping_id) -> int:
    try:
        return len(hand_edits_mod.active_edits(conn, grouping_id))
    except sqlite3.OperationalError:
        return 0


def _unresolved_assignments(conn, grouping_id, unit_db="single_motifs") -> int:
    """Assignments of this grouping that name a row which is not there.

    `_member_rows` LEFT JOINs and the family builder then drops every row whose
    join found nothing, which silently narrowed the result set: the grouping
    card counted 3,239 assigned while the atlas summed 3,235 members, with no
    third number reconciling them. Counting them here lets a surface say
    "3,239 assigned · 4 unresolved" instead of quietly disagreeing with itself.
    """
    table = "sequences" if unit_db == "sequences" else "motif_member"
    try:
        return int(conn.execute(
            f"SELECT COUNT(*) FROM grouping_assignments ga WHERE ga.grouping_id = ? "
            f"AND ga.unit = ? AND ga.family_label IS NOT NULL AND NOT EXISTS "
            f"(SELECT 1 FROM {table} t WHERE t.id = ga.member_ref)",
            (int(grouping_id), unit_db)).fetchone()[0])
    except sqlite3.OperationalError:
        return 0


def _grouping_payload(conn, row) -> dict:
    params = json.loads(row["params_json"] or "{}")
    basis = row["basis"]
    meta = bases_mod.BASES.get(basis, (None, basis, ""))
    basis_label = meta[1]
    text = _params_text(params)
    n_assigned = int(row["n_assigned"] or 0)
    n_omitted = int(row["n_omitted"] or 0)
    return {
        "id": gid_str(row["id"]),
        "unit": UNIT_TO_CLIENT.get(row["unit"], "motifs"),
        "basis": basis, "basisLabel": basis_label, "params": text,
        "chip": [basis_label, text],
        "computed": _iso_to_human(row["created_at"]),
        "motifs": n_assigned + n_omitted,
        "families": int(row["n_families"] or 0),
        "omitted": n_omitted,
        "unresolved": _unresolved_assignments(conn, row["id"], str(row["unit"])),
        "handEditsKept": _hand_edits_kept(conn, row["id"]),
        "name": row["name"], "method": row["method"], "cut": row["cut"],
        "recipeHash": row["recipe_hash"], "actor": row["actor"],
    }


# ── assignments -> families ─────────────────────────────────────────────────

def _member_rows(conn, grouping_id) -> list:
    """Every assigned motif member of one grouping, with its entry and its
    recording, in one query. `member_ref` is a `motif_member.id` when the unit
    is single motifs (what the engine's `_ref` writes)."""
    return list(conn.execute(
        """
        SELECT ga.id            AS assignment_id,
               ga.member_ref    AS member_ref,
               ga.family_label  AS family_label,
               ga.family_id     AS family_id,
               ga.distance      AS distance,
               ga.is_medoid     AS is_medoid,
               ga.omit_reason   AS omit_reason,
               ga.content_hash  AS content_hash,
               mm.id            AS member_id,
               mm.entry_id      AS entry_id,
               mm.recording_id  AS recording_id,
               mm.start_idx     AS start_idx,
               mm.end_idx       AS end_idx,
               me.label         AS entry_label,
               me.tags          AS entry_tags,
               me.scale         AS scale
          FROM grouping_assignments ga
          LEFT JOIN motif_member mm ON mm.id = ga.member_ref
          LEFT JOIN motif_entry  me ON me.id = mm.entry_id
         WHERE ga.grouping_id = ? AND ga.unit = 'single_motifs'
         ORDER BY ga.family_label, ga.distance
        """, (int(grouping_id),)))


def _verdicts(conn, index) -> dict:
    """`(recording_id, start_idx, end_idx) -> verdict`, the human side only.

    Rule 5 in the reading direction: a member's verdict is joined from
    `annotations` (a person's) and `adjudications` (a person's, on a machine
    row). Nothing here reads `detections.
    """
    out = {}
    try:
        for r in conn.execute("SELECT recording_id, start_idx, end_idx, verdict, created_at FROM annotations"):
            out[(int(r["recording_id"]), int(r["start_idx"]), int(r["end_idx"]))] = (r["verdict"], r["created_at"])
    except sqlite3.OperationalError:
        pass
    return out


def _tags_for_entries(conn, entry_ids) -> tuple:
    """`(tags_by_entry, elements_by_entry)`. §3.4: tags live on the entry, and
    an occurrence that resolved onto an existing entry contributed its tags to
    it, so a disagreement between two sources is visible here rather than lost.

    The tags are read from `motif_entry_tags JOIN tag_vocabulary` — the tables
    the importers actually write. The legacy `motif_entry.tags` JSON column is
    read only for entries the normalised tables say nothing about, so rows
    written before those tables existed are not silently untagged. Reading the
    legacy column *first* is what made all 149 families report shape "drop":
    it is empty on every row of this installation, while 772 entries carry
    `element = sharkfin` and 2,827 carry `element = trough` next door.
    """
    tags, elements = {}, {}
    if not entry_ids:
        return tags, elements
    marks = ",".join("?" * len(entry_ids))
    try:
        for r in conn.execute(
            f"SELECT met.entry_id AS entry_id, tv.category AS category, tv.value AS value "
            f"FROM motif_entry_tags met JOIN tag_vocabulary tv ON tv.id = met.tag_id "
            f"WHERE met.entry_id IN ({marks}) ORDER BY met.entry_id, tv.category, tv.value",
                tuple(entry_ids)):
            eid, value = int(r["entry_id"]), str(r["value"])
            tags.setdefault(eid, []).append(value)
            if str(r["category"]) == "element":
                elements.setdefault(eid, []).append(value)
    except sqlite3.OperationalError:
        pass

    legacy = [e for e in entry_ids if e not in tags]
    if legacy:
        marks = ",".join("?" * len(legacy))
        for r in conn.execute(f"SELECT id, tags FROM motif_entry WHERE id IN ({marks})", tuple(legacy)):
            raw = r["tags"]
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
                values = parsed if isinstance(parsed, list) else [str(parsed)]
            except (ValueError, TypeError):
                values = [t.strip() for t in str(raw).split(",") if t.strip()]
            tags[int(r["id"])] = [str(t) for t in values]
    return tags, elements


def _shape_of(elements, tags=()) -> tuple:
    """`(shape, label, mix)` for one family.

    The shape is the `element` tag its members carry most often — the real
    vocabulary value (`trough`, `sharkfin`, …), not a guess. A family whose
    members disagree keeps the majority and reports the split, because §3.4
    calls a morphology disagreement a finding rather than noise. A family
    whose members carry no element tag at all gets `None` and the label "not
    recorded": defaulting it to "drop" stated a morphology nobody measured.
    """
    counts = {}
    for e in elements or ():
        value = str(e).strip().lower()
        if value:
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        # entries that predate the normalised tag tables: the legacy JSON
        # column named the shape in free text, so a name match is all there is
        for t in tags or ():
            low = str(t).lower().replace(" ", "").replace("-", "").replace("_", "")
            for kind in SHAPE_KINDS:
                if kind == low:
                    return kind, kind, {kind: 1}
        return None, "not recorded", {}
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    shape = ordered[0][0]
    if len(ordered) == 1:
        return shape, shape, counts
    return shape, "mixed · " + " · ".join(f"{k} {v}" for k, v in ordered), counts


def _edges_label(conn, member_ids) -> tuple:
    """`(edges text, artifactChannels, propChannels, indChannels)` from
    `motif_edge.classification_bin`, which `matching.classify_cross_channel_edges`
    writes. No edges yet is reported as such, not as zero of each."""
    if not member_ids:
        return "no edges", 0, 0, 0
    marks = ",".join("?" * len(member_ids))
    rows = conn.execute(
        f"SELECT classification_bin, COUNT(*) AS n FROM motif_edge "
        f"WHERE member_a_id IN ({marks}) OR member_b_id IN ({marks}) GROUP BY classification_bin",
        tuple(member_ids) * 2).fetchall()
    counts = {str(r["classification_bin"] or "unclassified"): int(r["n"]) for r in rows}
    if not counts:
        return "no edges", 0, 0, 0
    art = counts.get("artifact", 0)
    prop = counts.get("propagation", 0) + counts.get("propagating", 0)
    ind = counts.get("independent", 0)
    text = " · ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    return text, art, prop, ind


def _families_for(conn, index, grouping_row) -> list:
    """`MotifFamily[]` for one grouping, built from real rows."""
    if grouping_row is None:
        return []
    rows = _member_rows(conn, grouping_row["id"])
    # `family_label` on an omitted row names its NEAREST family, not the one it
    # joined — `family_id` is what says it joined at all. Filtering on the
    # label alone counted every omitted motif as a member of the family it
    # failed to reach.
    assigned = [r for r in rows if r["family_id"] is not None and r["member_id"] is not None]
    if not assigned:
        return []

    tags_by_entry, elements_by_entry = _tags_for_entries(
        conn, sorted({int(r["entry_id"]) for r in assigned if r["entry_id"]}))
    verdicts = _verdicts(conn, index)
    edits = hand_edits_mod.active_edits(conn, grouping_row["id"])
    hand_by_family = {}
    for e in edits:
        label = hand_edits_mod._field(e, "family_label")
        if label:
            hand_by_family[label] = hand_by_family.get(label, 0) + 1

    by_family = {}
    for r in assigned:
        by_family.setdefault(r["family_label"], []).append(r)

    # hoisted: this was one query per family, run 30 times for 30 families
    reviewed = _reviewed_fraction(conn, index)
    out = []
    for i, (label, members) in enumerate(sorted(by_family.items())):
        out.append(_one_family(conn, index, label, members, i, tags_by_entry, verdicts,
                               hand_by_family.get(label, 0), grouping_row, reviewed,
                               elements_by_entry))
    return out


def _one_family(conn, index, label, members, i, tags_by_entry, verdicts, hand, grouping_row,
                reviewed=None, elements_by_entry=None) -> dict:
    reviewed = _reviewed_fraction(conn, index) if reviewed is None else reviewed
    elements_by_entry = elements_by_entry or {}
    durations, amps, cells, tags, elements = [], [], {}, [], []
    judged = 0
    artifact = 0
    recordings = set()

    medoid_row = next((m for m in members if m["is_medoid"]), members[0])
    exemplar_row = min(members, key=lambda m: _f(m["distance"], 1e9))

    for m in members:
        meta = index["by_id"].get(int(m["recording_id"] or 0))
        if meta is None:
            continue
        recordings.add(meta["key"])
        fs = meta["fs"] or 1.0
        durations.append((int(m["end_idx"] or 0) - int(m["start_idx"] or 0)) / fs)
        tags.extend(tags_by_entry.get(int(m["entry_id"] or 0), []))
        elements.extend(elements_by_entry.get(int(m["entry_id"] or 0), []))
        verdict = verdicts.get((meta["recording_id"], int(m["start_idx"] or 0), int(m["end_idx"] or 0)))
        if verdict:
            judged += 1
            if str(verdict[0]).lower() == "artifact":
                artifact += 1
        ck = f"{meta['key']}:{meta['name']}"
        cell = cells.setdefault(ck, {"perHour": None, "count": 0})
        cell["count"] += 1

    # A cell for EVERY channel of every recording the matrix can draw, whether
    # or not anyone has reviewed it and whether or not this family has members
    # there. The client cannot tell "never looked" from "looked and found
    # nothing" by the absence of a cell — it drew a missing cell as
    # reviewed-and-empty, which manufactured a negative result for the seven
    # recordings nobody has opened. So absence carries no meaning here: the
    # three facts (`count`, `perHour`, `noCoverage`) are stated on every cell.
    # `perHour` stays None when the recording has no duration to divide by,
    # which is not the same as a rate of zero.
    for g in index["groups"]:
        if g.get("held_out"):
            continue                 # D6: a held-out recording offers no cells
        key = rec_key(g["source_file"])
        hours = _f(g.get("duration_h"), 0.0)
        for ch in g["channels"]:
            ck = f"{key}:{ch['name']}"
            cell = cells.setdefault(ck, {"perHour": None, "count": 0})
            if hours > 0:
                cell["perHour"] = round(cell["count"] / hours, 3)
            if reviewed.get(ck, 0.0) <= 0:
                # §8.4: never looked at is not the same as looked at and empty.
                # It is also not the same as "no members": a channel can hold
                # members from a run nobody has reviewed, so the flag is about
                # the coverage and the count is about the members.
                cell["noCoverage"] = True

    # only the two traces the card actually draws are decimated; every other
    # member contributes a single number, not a polyline
    ex_trace = _trace(index, exemplar_row["recording_id"], exemplar_row["start_idx"], exemplar_row["end_idx"])
    me_trace = _trace(index, medoid_row["recording_id"], medoid_row["start_idx"], medoid_row["end_idx"])
    amps = [_span_amplitude(index, m["recording_id"], m["start_idx"], m["end_idx"]) for m in members]
    amps = [a for a in amps if a > 0]
    amp_domain = _amp_domain(amps)

    dur = float(np.mean(durations)) if durations else 0.0
    dur_sd = float(np.std(durations)) if len(durations) > 1 else 0.0
    depth = float(np.mean(amps)) if amps else _amplitude_mv(ex_trace)
    depth_sd = float(np.std(amps)) if len(amps) > 1 else 0.0
    dists = [_f(m["distance"]) for m in members if m["distance"] is not None]
    member_ids = [int(m["member_id"]) for m in members if m["member_id"] is not None]
    edges, art_ch, prop_ch, ind_ch = _edges_label(conn, member_ids)
    shape, shape_label, shape_mix = _shape_of(elements, tags)

    return {
        "id": label, "name": label, "colour": family_colour(i), "shape": shape,
        "shapeLabel": shape_label, "shapeMix": shape_mix,
        "members": len(members), "inScope": len(members), "recordings": len(recordings),
        "hand": hand, "artifact": artifact,
        "durationS": round(dur, 2), "durationSd": round(dur_sd, 2),
        "depthMv": round(depth, 3), "depthLabel": f"{depth:.2f} mV ± {depth_sd:.2f}",
        "judgedPct": round(100.0 * judged / len(members), 1) if members else 0.0,
        "judged": judged,
        "exemplar": f"m-{exemplar_row['member_id']}", "medoid": f"m-{medoid_row['member_id']}",
        "exemplarMedoidD": round(_f(exemplar_row["distance"]), 4),
        "meanMemberD": round(float(np.mean(dists)), 4) if dists else 0.0,
        "snrDb": _snr_db(ex_trace),
        "artifactChannels": art_ch, "propChannels": prop_ch, "indChannels": ind_ch, "edges": edges,
        "cells": cells, "exemplarTrace": ex_trace, "medoidTrace": me_trace,
        # the bars and the axis come from one measurement of this family's own
        # amplitudes, so the picture and its scale cannot disagree
        "ampBins": _amp_bins(amps, amp_domain), "ampDomain": [round(v, 5) for v in amp_domain],
        "grouping": gid_str(grouping_row["id"]),
    }


# ── sequence families ───────────────────────────────────────────────────────

def _sequence_families_for(conn, index, grouping_row) -> list:
    if grouping_row is None:
        return []
    rows = list(conn.execute(
        """
        SELECT ga.family_label AS family_label, ga.distance AS distance, ga.is_medoid AS is_medoid,
               s.id AS sequence_id, s.recording_id AS recording_id, s.n_events AS n_events,
               s.start_idx AS start_idx, s.end_idx AS end_idx, s.origin AS origin
          FROM grouping_assignments ga
          JOIN sequences s ON s.id = ga.member_ref
         WHERE ga.grouping_id = ? AND ga.unit = 'sequences' AND ga.family_id IS NOT NULL
         ORDER BY ga.family_label, ga.distance
        """, (int(grouping_row["id"]),)))
    if not rows:
        return []

    by_family = {}
    for r in rows:
        by_family.setdefault(r["family_label"], []).append(r)

    # the motif grouping the compositions are read under: a sequence's events
    # are named by the family they fell into, and two saved motif groupings
    # name them differently. Joining without one produced one composition row
    # per grouping per event, which is how a 12-event exemplar came back with
    # 24 events in it.
    motif_g = _default_grouping(conn, "single_motifs")
    comps = _compositions(conn, [int(r["sequence_id"]) for r in rows], motif_g)
    verdicts = _verdicts(conn, index)
    out = []
    for i, (label, seqs) in enumerate(sorted(by_family.items())):
        out.append(_one_sequence_family(conn, index, label, seqs, i, comps, verdicts))
    return out


def _compositions(conn, sequence_ids, motif_grouping) -> dict:
    """`sequence_id -> {"labels": [family label per event, in order],
    "members": [motif_member.id, …], "gaps": [...], "resolved": bool}`.

    `labels` is what "the same order of the same shapes" is measured over, so
    it is only meaningful when every event of the sequence resolved to a
    family in one grouping. `resolved` says whether it did; nothing downstream
    may compare two unresolved compositions and call them equal.
    """
    out = {}
    if not sequence_ids:
        return out
    gid = int(motif_grouping["id"]) if motif_grouping is not None else None
    marks = ",".join("?" * len(sequence_ids))
    args = list(sequence_ids)
    join = ("LEFT JOIN grouping_assignments ga ON ga.member_ref = sm.member_id "
            "AND ga.unit = 'single_motifs' AND ga.family_id IS NOT NULL AND ga.grouping_id = ? ")
    if gid is None:
        join = ""
    else:
        args = [gid] + args
    for r in conn.execute(
        f"SELECT sm.sequence_id AS sid, sm.member_id AS member_id, sm.gap_before AS gap, "
        f"{'ga.family_label' if gid is not None else 'NULL'} AS fam "
        f"FROM sequence_members sm {join}"
        f"WHERE sm.sequence_id IN ({marks}) ORDER BY sm.sequence_id, sm.position", tuple(args)):
        slot = out.setdefault(int(r["sid"]), {"labels": [], "members": [], "gaps": [], "resolved": True})
        if r["fam"]:
            slot["labels"].append(str(r["fam"]))
        else:
            slot["resolved"] = False
        if r["member_id"] is not None:
            slot["members"].append(int(r["member_id"]))
        if r["gap"] is not None:
            slot["gaps"].append(_f(r["gap"]))
    return out


def _one_sequence_family(conn, index, label, seqs, i, comps=None, verdicts=None) -> dict:
    comps = comps or {}
    verdicts = verdicts or {}
    medoid = next((s for s in seqs if s["is_medoid"]), seqs[0])
    exemplar = min(seqs, key=lambda s: _f(s["distance"], 1e9))
    recordings, durations = set(), []
    motifs = 0
    for s in seqs:
        meta = index["by_id"].get(int(s["recording_id"] or 0))
        if meta:
            recordings.add(meta["key"])
            fs = meta["fs"] or 1.0
            if s["start_idx"] is not None and s["end_idx"] is not None:
                durations.append((int(s["end_idx"]) - int(s["start_idx"])) / fs)
        motifs += int(s["n_events"] or 0)

    ex_comp = comps.get(int(exemplar["sequence_id"]), {"labels": [], "gaps": [], "resolved": False})
    composition = list(ex_comp["labels"])
    gaps = list(ex_comp["gaps"])

    dur = float(np.mean(durations)) if durations else 0.0
    gap = float(np.mean(gaps)) if gaps else 0.0
    dists = [_f(s["distance"]) for s in seqs if s["distance"] is not None]
    hand = 0

    # "judged" is a human verdict over this family's motifs, counted the way
    # `_one_family` counts one — not the sequence's `origin`. A human-*drawn*
    # sequence has not been judged by anyone, and an adjudicated machine one
    # has; reporting origin as judgement reversed both, and put a count of
    # sequences over a count of motifs.
    judged_motifs, total_motifs = 0, 0
    for s in seqs:
        for member_id in comps.get(int(s["sequence_id"]), {}).get("members", []):
            row = conn.execute(
                "SELECT recording_id, start_idx, end_idx FROM motif_member WHERE id = ?",
                (member_id,)).fetchone()
            if row is None:
                continue
            total_motifs += 1
            if verdicts.get((int(row["recording_id"]), int(row["start_idx"]), int(row["end_idx"]))):
                judged_motifs += 1

    # how many member sequences preserve the exemplar's order of families —
    # the measurement the label "order kept" names. It needs every event of
    # both sequences to have resolved to a family, so a family whose
    # compositions are unresolved reports nothing at all rather than a number
    # that counts something else.
    order_kept = None
    comparable = [s for s in seqs
                  if comps.get(int(s["sequence_id"]), {}).get("resolved")
                  and comps[int(s["sequence_id"])]["labels"]]
    if ex_comp.get("resolved") and composition:
        order_kept = sum(1 for s in comparable
                         if comps[int(s["sequence_id"])]["labels"] == composition)

    payload = {
        "id": label, "name": label, "colour": family_colour(i), "sequences": len(seqs),
        "composition": composition,
        "compositionLabel": " · ".join(composition) or "unresolved",
        "recordings": len(recordings), "hand": hand,
        "durationLabel": f"{dur:.0f} s" if dur else "—",
        "gapLabel": f"{gap:.0f} s" if gap else "—",
        "judgedPct": round(100.0 * judged_motifs / total_motifs, 1) if total_motifs else 0.0,
        "exemplar": f"sq-{exemplar['sequence_id']}", "motifs": motifs,
        "exemplarMedoidD": round(_f(exemplar["distance"]), 4),
        "meanMemberD": round(float(np.mean(dists)), 4) if dists else 0.0,
        "judgedMotifs": judged_motifs, "judgedOf": total_motifs, "gapS": f"{gap:.1f}",
        "exemplarTrace": _trace(index, exemplar["recording_id"], exemplar["start_idx"],
                                exemplar["end_idx"], px=SEQUENCE_TRACE_PX),
        "medoidTrace": _trace(index, medoid["recording_id"], medoid["start_idx"],
                              medoid["end_idx"], px=SEQUENCE_TRACE_PX),
    }
    if order_kept is not None:
        payload["orderKept"] = order_kept
        payload["orderKeptOf"] = len(comparable)
    else:
        # the field is absent, not zero: nothing here measured order
        payload["orderKeptNote"] = ("not computed — the events of these sequences did not all "
                                    "resolve to a family in the current motif grouping")
    payload["exemplarEvents"] = len(composition)
    return payload


# ══════════════════════════════════════════════════════ READS ═══════════════

@router.get("/counts")
def get_counts(request: Request):
    """`LibraryCounts` — the SectionBar on every Library page."""
    conn = _conn(request)
    try:
        def one(sql, args=()):
            return int(conn.execute(sql, args).fetchone()[0])
        return {
            # §3.2: an entry with no scale is an event-scale entry written before
            # the column existed, not an unknown third thing
            "motifs": one("SELECT COUNT(*) FROM motif_entry WHERE scale = 'event' OR scale IS NULL"),
            "spikeTrains": one("SELECT COUNT(*) FROM motif_entry WHERE scale = 'train'"),
            "sequences": one("SELECT COUNT(*) FROM sequences"),
            "templates": one("SELECT COUNT(*) FROM templates"),
            "windowSets": one("SELECT COUNT(*) FROM window_sets"),
        }
    finally:
        conn.close()


@router.get("/groupings")
def get_groupings(request: Request):
    """`Grouping[]`. Ids are `g-NN` so the client's `nextGroupingId` parses."""
    conn = _conn(request)
    try:
        return [_grouping_payload(conn, r) for r in _grouping_rows(conn)]
    finally:
        conn.close()


@router.get("/recurrence")
def get_recurrence(request: Request, grouping: str | None = Query(default=None)):
    """`{recordings, families, coverage, sharedGround}` — the recurrence matrix."""
    conn = _conn(request)
    try:
        index = _recordings_index(conn)
        row = _resolve_grouping(conn, grouping)
        families = _families_for(conn, index, row)
        coverage = _reviewed_fraction(conn, index)
        shared = []
        for fam in families:
            live = sorted(k for k, c in fam["cells"].items() if c.get("count"))
            for a_i in range(len(live)):
                for b_i in range(a_i + 1, len(live)):
                    shared.append({"pair": [live[a_i], live[b_i]], "family": fam["id"]})
        return {
            "recordings": _rec_groups(conn, index),
            "families": families,
            "coverage": {k: round(v, 4) for k, v in coverage.items()},
            "sharedGround": shared[:200],
            "grouping": gid_str(row["id"]) if row else None,
            # stated, not dropped: see `_unresolved_assignments`
            "unresolved": _unresolved_assignments(conn, row["id"], str(row["unit"])) if row else 0,
        }
    finally:
        conn.close()


@router.get("/families")
def get_families(request: Request, grouping: str | None = Query(default=None)):
    """`MotifFamily[]` — the Atlas. Every row carries `colour`."""
    conn = _conn(request)
    try:
        index = _recordings_index(conn)
        return _families_for(conn, index, _resolve_grouping(conn, grouping))
    finally:
        conn.close()


@router.get("/sequence-families")
def get_sequence_families(request: Request, grouping: str | None = Query(default=None)):
    """`SequenceFamily[]` — the sequence rail."""
    conn = _conn(request)
    try:
        index = _recordings_index(conn)
        return _sequence_families_for(conn, index, _resolve_grouping(conn, grouping, "sequences"))
    finally:
        conn.close()


@router.get("/family/{family_id}")
def get_family(request: Request, family_id: str, grouping: str | None = Query(default=None),
               unit: str | None = Query(default=None)):
    """The `FamilyRead` union. An unknown family is `{kind:'missing', id}` —
    a 200 with a shape the page renders, not a 500 and not a blank.

    **The unit decides which grouping answers.** Nineteen labels (`F-01`,
    `F-02`, …) name both a motif family and a sequence family, and matching
    motifs first meant `?unit=sequences` opened a different family's members
    under the id that was asked for. The resolution order is: an explicit
    `unit`; else the unit of the `grouping` the caller named; else motifs,
    with `otherUnit` on the answer when the same label also names a family in
    the other unit — so a caller can never be handed a substitute silently.
    """
    conn = _conn(request)
    try:
        index = _recordings_index(conn)
        want = (unit or "").strip().lower()
        if want in ("sequences", "sequence", "seq"):
            want = "sequences"
        elif want in ("motifs", "motif", "single_motifs"):
            want = "single_motifs"
        elif want:
            raise HTTPException(status_code=400, detail=f"unknown unit {unit!r}: motifs or sequences")
        elif grouping not in (None, "", "undefined", "null"):
            row = _grouping_row(conn, grouping)
            if row is None:
                return {"kind": "missing", "id": family_id}
            want = str(row["unit"])

        def _motif():
            # an explicit unit outranks a grouping id for the other unit: the
            # caller asked for a motif family, so the newest motif grouping
            # answers rather than a grouping that holds no motif families
            g = _resolve_grouping(conn, grouping, "single_motifs")
            if g is not None and str(g["unit"]) != "single_motifs":
                g = _default_grouping(conn, "single_motifs")
            fams = _families_for(conn, index, g)
            fam = next((f for f in fams if f["id"] == family_id), None)
            return (({"kind": "motif", "detail": _family_detail(conn, index, fam, g),
                      "grouping": gid_str(g["id"])}) if fam is not None else None)

        def _sequence():
            g = _resolve_grouping(conn, grouping, "sequences")
            if g is not None and str(g["unit"]) != "sequences":
                g = _default_grouping(conn, "sequences")
            for sf in _sequence_families_for(conn, index, g):
                if sf["id"] == family_id:
                    return {"kind": "sequence", "family": sf, "grouping": gid_str(g["id"])}
            return None

        if want == "sequences":
            return _sequence() or {"kind": "missing", "id": family_id, "unit": "sequences"}
        if want == "single_motifs":
            return _motif() or {"kind": "missing", "id": family_id, "unit": "motifs"}

        found = _motif()
        if found is not None:
            if _sequence() is not None:
                found["otherUnit"] = "sequences"
            return found
        return _sequence() or {"kind": "missing", "id": family_id}
    finally:
        conn.close()


def _family_detail(conn, index, fam, grouping_row) -> dict:
    rows = [r for r in _member_rows(conn, grouping_row["id"])
            if r["family_label"] == fam["id"] and r["family_id"] is not None]
    tags_by_entry, _elements = _tags_for_entries(
        conn, sorted({int(r["entry_id"]) for r in rows if r["entry_id"]}))
    verdicts = _verdicts(conn, index)
    edits = hand_edits_mod.active_edits(conn, grouping_row["id"])
    edits_by_hash = {}
    for e in edits:
        edits_by_hash.setdefault(hand_edits_mod._field(e, "content_hash"), []).append(e)

    members, removed = [], []
    medoid_id = next((r["member_id"] for r in rows if r["is_medoid"]), None)
    exemplar_id = min(rows, key=lambda r: _f(r["distance"], 1e9))["member_id"] if rows else None

    for r in rows:
        meta = index["by_id"].get(int(r["recording_id"] or 0))
        if meta is None:
            continue
        fs = meta["fs"] or 1.0
        start, end = int(r["start_idx"] or 0), int(r["end_idx"] or 0)
        verdict_row = verdicts.get((meta["recording_id"], start, end))
        hand_rows = edits_by_hash.get(r["content_hash"], [])
        role = "medoid" if r["member_id"] == medoid_id else ("exemplar" if r["member_id"] == exemplar_id else None)
        member = {
            "id": f"m-{r['member_id']}", "d": round(_f(r["distance"]), 4),
            "recording": meta["label"], "recordingKey": meta["key"], "channel": meta["name"],
            "onsetH": round(start / fs / 3600.0, 3),
            "durationS": round((end - start) / fs, 2),
            "amplitudeMv": _span_amplitude(index, r["recording_id"], start, end),
            "verdict": (verdict_row[0] if verdict_row else "unjudged"),
            "foundBy": str(r["scale"] or "event"),
            "revisions": _revisions_for(conn, r["member_id"]),
            "tags": tags_by_entry.get(int(r["entry_id"] or 0), []),
            "seed": int(r["member_id"] or 0),
            "contentHash": r["content_hash"],
        }
        if role:
            member["role"] = role
        if verdict_row and verdict_row[1]:
            member["verdictAt"] = _iso_to_human(verdict_row[1])
        if hand_rows:
            member["addedByHand"] = any(hand_edits_mod._field(e, "kind") == "add_member" for e in hand_rows)
            e = hand_rows[0]
            member["handRecord"] = (f"{hand_edits_mod._field(e, 'kind')} · {fam['id']} · "
                                    f"{hand_edits_mod._field(e, 'actor') or 'this installation'} · "
                                    f"{_iso_to_human(hand_edits_mod._field(e, 'created_at'))}")
        members.append(member)

    # a removal is a hand edit against this family, not a row that vanished
    for e in edits:
        if hand_edits_mod._field(e, "kind") != "remove_member":
            continue
        if hand_edits_mod._field(e, "family_label") != fam["id"]:
            continue
        digest = hand_edits_mod._field(e, "content_hash")
        src = conn.execute(
            "SELECT mm.id, mm.recording_id, mm.start_idx, mm.end_idx FROM motif_member mm "
            "WHERE mm.content_hash = ? LIMIT 1", (digest,)).fetchone()
        meta = index["by_id"].get(int(src["recording_id"])) if src else None
        removed.append({
            "id": f"m-{src['id']}" if src else f"h-{hand_edits_mod._field(e, 'id')}",
            "d": 0.0,
            "channel": meta["name"] if meta else "—",
            "recording": meta["label"] if meta else "—",
            "recordingKey": meta["key"] if meta else None,
            "removedAt": _iso_to_human(hand_edits_mod._field(e, "created_at")),
            "note": hand_edits_mod._field(e, "value") or "removed by hand",
            "seed": int(src["id"]) if src else 0,
            "onsetH": round(int(src["start_idx"]) / (meta["fs"] or 1.0) / 3600.0, 3) if (src and meta) else None,
            "contentHash": digest,
        })

    return {
        "family": fam, "cut": _f(grouping_row["cut"]),
        "members": members, "removed": removed,
        "channels": len({m["channel"] for m in members}),
        "depthLabel": fam["depthLabel"],
        "handAdded": sum(1 for m in members if m.get("addedByHand")),
    }


def _revisions_for(conn, member_id) -> list:
    """`Revision[]` from `motif_member_revision` — real, not invented."""
    if member_id is None:
        return []
    out = []
    for r in conn.execute(
        "SELECT revision, origin, detection_id, annotation_id, start_idx, end_idx, created_at "
        "FROM motif_member_revision WHERE member_id = ? ORDER BY revision", (int(member_id),)):
        origin = "machine" if r["origin"] == "machine" else "human edit"
        run = f"detection {r['detection_id']}" if r["detection_id"] else (
            f"annotation {r['annotation_id']}" if r["annotation_id"] else "—")
        out.append({
            "rev": int(r["revision"]), "spanId": f"{r['start_idx']}:{r['end_idx']}",
            "origin": origin, "run": run,
            # §4.2: rev 1 is what the matcher compares against; the current one is
            # what the researcher sees. Saying which is which is the whole point.
            "role": "matching" if int(r["revision"]) == 1 else "current",
        })
    if out:
        out[-1]["role"] = "current" if len(out) > 1 else "matching · current"
    return out


@router.get("/omitted")
def get_omitted(request: Request, grouping: str | None = Query(default=None)):
    """`{groupingId, singles, sequences}` — what did not fit, with its reason.

    **One grouping per unit.** Single motifs are omitted by a motif grouping
    and sequences by a sequence grouping, and no saved grouping holds both, so
    resolving one id for the whole payload left the `sequences` half empty on
    every default call — the nine `past_cut` sequence omissions were
    unreachable unless the caller happened to know to ask for `?grouping=g-03`.

    `motifsInNoSequence` is a different quantity from either list and is named
    as one: the catalogue members that belong to no sequence at all, which is
    not something a grouping omitted.
    """
    conn = _conn(request)
    try:
        index = _recordings_index(conn)
        asked = grouping not in (None, "", "undefined", "null")
        motif_g = _resolve_grouping(conn, grouping, "single_motifs")
        seq_g = _resolve_grouping(conn, grouping, "sequences")
        if asked:
            # a named grouping answers for its own unit only; the other unit
            # falls back to its newest, never to the named one
            named = motif_g if motif_g is not None else None
            if named is None:
                # `_resolve_grouping` returned None: the id names nothing
                return {"groupingId": None, "singles": [], "sequences": [],
                        "reason": f"no grouping {grouping}"}
            if str(named["unit"]) == "sequences":
                motif_g, seq_g = _default_grouping(conn, "single_motifs"), named
            else:
                motif_g, seq_g = named, _default_grouping(conn, "sequences")

        singles, seqs = [], []
        for row, unit_db, bucket in ((motif_g, "single_motifs", singles), (seq_g, "sequences", seqs)):
            if row is None:
                continue
            for r in conn.execute(
                "SELECT * FROM grouping_assignments WHERE grouping_id = ? AND unit = ? "
                "AND family_id IS NULL", (int(row["id"]), unit_db)):
                bucket.append(_omitted_entry(conn, index, r))

        return {
            "groupingId": gid_str(motif_g["id"]) if motif_g is not None else None,
            "sequenceGroupingId": gid_str(seq_g["id"]) if seq_g is not None else None,
            "singles": singles, "sequences": seqs,
            # a catalogue fact, not a grouping one: the page said "0 motifs in
            # no sequence" off `len(singles)`, which counts something else
            "motifsInNoSequence": int(conn.execute(
                "SELECT COUNT(*) FROM motif_member mm WHERE NOT EXISTS "
                "(SELECT 1 FROM sequence_members sm WHERE sm.member_id = mm.id)").fetchone()[0]),
        }
    finally:
        conn.close()


def _omitted_entry(conn, index, r) -> dict:
    is_seq = r["unit"] == "sequences"
    table = "sequences" if is_seq else "motif_member"
    entry_col = "NULL AS entry_id" if is_seq else "entry_id"
    src = conn.execute(
        f"SELECT recording_id, start_idx, end_idx, {entry_col} FROM {table} WHERE id = ?",
        (int(r["member_ref"]),)).fetchone()
    shape, shape_label = None, "not recorded"
    if src is not None and src["entry_id"] is not None:
        _tags, elements = _tags_for_entries(conn, [int(src["entry_id"])])
        shape, shape_label, _mix = _shape_of(elements.get(int(src["entry_id"]), []),
                                             _tags.get(int(src["entry_id"]), []))
    meta = index["by_id"].get(int(src["recording_id"])) if (src and src["recording_id"]) else None
    fs = (meta["fs"] if meta else 1.0) or 1.0
    amp = _span_amplitude(index, src["recording_id"], src["start_idx"], src["end_idx"]) if src else 0.0
    return {
        "id": (f"sq-{r['member_ref']}" if is_seq else f"m-{r['member_ref']}"),
        "kind": "sequence" if is_seq else "motif",
        "nearest": r["family_label"] or "—",
        "d": round(_f(r["distance"]), 4),
        "recording": meta["label"] if meta else "—",
        "recordingKey": meta["key"] if meta else None,
        "channel": meta["name"] if meta else "—",
        "onsetH": round(int(src["start_idx"] or 0) / fs / 3600.0, 3) if src else 0.0,
        # the shape is the entry's own `element` tag, not the detector that
        # produced the seed corpus dressed up as a measurement
        "shape": shape, "shapeLabel": shape_label,
        "amp": amp, "seed": int(r["member_ref"]),
        # the reason is the point of the list: "past the cut" and "in no
        # sequence" are different findings and must not both render as absent
        "omitReason": r["omit_reason"],
    }


@router.get("/grouping-editor")
def get_grouping_editor(request: Request, unit: str = Query(default="motifs")):
    """`{units, bases, distributions, clusterings}` — the grouping editor.

    Every basis is listed for every unit; one that does not apply carries the
    core's own `reason` (spec §8.2: disabled *with* its reason), so the page
    never has to invent an explanation.
    """
    conn = _conn(request)
    t0 = time.perf_counter()
    try:
        index = _recordings_index(conn)
        counts = {
            "motifs": conn.execute("SELECT COUNT(*) FROM motif_entry WHERE scale = 'event' OR scale IS NULL").fetchone()[0],
            "sequences": conn.execute("SELECT COUNT(*) FROM sequences").fetchone()[0],
            "spike-trains": conn.execute("SELECT COUNT(*) FROM motif_entry WHERE scale = 'train'").fetchone()[0],
        }
        units = [
            {"unit": "motifs", "caption": "single motifs", "count": int(counts["motifs"])},
            {"unit": "sequences", "caption": "sequences", "count": int(counts["sequences"])},
            {"unit": "spike-trains", "caption": "spike trains", "count": int(counts["spike-trains"])},
        ]
        unit_db = UNIT_TO_DB.get(unit, "single_motifs")
        applicable = bases_mod.applicable_bases(unit_db)
        bases = []
        for name, info in applicable.items():
            option = {
                "kind": name, "group": BASIS_GROUP.get(info["kind"], info["kind"]),
                "title": info["label"], "caption": info["help"],
                "units": [u for u in ("motifs", "sequences", "spike-trains")
                          if bases_mod.applicable_bases(UNIT_TO_DB[u])[name]["applies"]],
            }
            if not info["applies"]:
                option["reason"] = info["reason"]
            bases.append(option)

        distributions, sampled = _distributions_cached(conn, index)
        clusterings = [
            {"value": r["name"] or f"a-{r['id']}", "label": r["name"] or f"artifact {r['id']}",
             "scope": r["kind"]}
            for r in conn.execute(
                "SELECT id, name, kind FROM registered_artifacts WHERE active = 1 AND kind = 'clustering' ORDER BY id DESC LIMIT 20")
        ]
        return {
            "units": units, "bases": bases, "distributions": distributions,
            "clusterings": clusterings,
            "distributionsSampledFrom": sampled,
            "elapsedMs": round((time.perf_counter() - t0) * 1000, 1),
        }
    finally:
        conn.close()


#: The editor's five histograms, against a fingerprint of the catalogue they
#: were computed from. They cost a Ward fit over the sampled waveforms — about
#: 1.2 s for 600 of them — and nothing about them changes until a member is
#: added or removed, so recomputing them per request was paying that on every
#: keystroke in the editor.
_DIST_CACHE: dict = {}


def _catalogue_fingerprint(conn) -> tuple:
    """Cheap and sufficient: the row count and the highest id. An import only
    ever appends, so a change to either means the catalogue moved."""
    row = conn.execute("SELECT COUNT(*), COALESCE(MAX(id), 0) FROM motif_member").fetchone()
    return (int(row[0]), int(row[1]))


def _distributions_cached(conn, index) -> tuple:
    finger = _catalogue_fingerprint(conn)
    hit = _DIST_CACHE.get("distributions")
    if hit is not None and hit[0] == finger:
        return hit[1], hit[2]
    dists, sampled = _distributions(conn, index)
    _DIST_CACHE["distributions"] = (finger, dists, sampled)
    return dists, sampled


def _distributions(conn, index) -> tuple:
    """The five distributions the editor draws, computed from the live
    catalogue through `Working.library.grouping.bases`.

    Capped at `EDITOR_SAMPLE_CAP` entries: each one costs a memmap slice, and
    the real catalogue holds thousands. The cap travels on the payload so a
    sampled histogram is never read as a census.
    """
    keys = ("frequency-content", "amplitude", "timescale", "shape-distance", "sequence-similarity")
    out = {k: [] for k in keys}
    rows = list(conn.execute(
        "SELECT mm.recording_id, mm.start_idx, mm.end_idx FROM motif_member mm "
        "ORDER BY mm.id LIMIT ?", (EDITOR_SAMPLE_CAP,)))
    if not rows:
        return out, 0

    values = {"frequency-content": [], "amplitude": [], "timescale": []}
    waveforms = []
    for r in rows:
        meta = index["by_id"].get(int(r["recording_id"] or 0))
        if meta is None or meta.get("held_out"):
            continue
        trace = _trace(index, r["recording_id"], r["start_idx"], r["end_idx"], px=64)
        if not trace:
            continue
        waveforms.append(trace)
        fs = meta["fs"] or 1.0
        for name in values:
            try:
                values[name].append(float(bases_mod.compute_feature(name, trace, fs)))
            except Exception:
                # a feature that cannot be computed for one span is not a reason
                # to fail the whole editor; it is one fewer sample in that bin
                continue

    for name, vals in values.items():
        finite = [v for v in vals if math.isfinite(v)]
        if not finite:
            continue
        dist = bases_mod.distribution(finite, bin_method=bases_mod.BIN_QUANTILES,
                                      count=min(bases_mod.MAX_BINS, max(bases_mod.MIN_BINS, 16)))
        out[name] = [{"lo": _f(lo), "hi": _f(hi), "n": int(n)}
                     for lo, hi, n in zip(dist.edges[:-1], dist.edges[1:], dist.counts)]

    # the two distance bases draw merge heights, which only a fit produces
    heights = _merge_heights(waveforms)
    out["shape-distance"] = heights
    out["sequence-similarity"] = heights
    return out, len(waveforms)


def _merge_heights(waveforms) -> list:
    """Ward merge heights over the sampled waveforms, binned the way the
    editor's cut slider reads them."""
    if len(waveforms) < 3:
        return []
    # `member_ref` and `values` are the engine's item keys (`engine._ref` and
    # `engine._waveform`). They were `ref` and `waveform` here, which raised a
    # KeyError on every call — and the bare `except` below turned that into an
    # empty list, so the cut slider's histogram silently had no data at all.
    # Neither the exception nor the emptiness was ever visible. Loud failure is
    # the rule (CLAUDE.md), so the KeyError now propagates: a wrong item shape
    # is a bug in this file, not a condition to absorb.
    items = [{"member_ref": i, "values": w} for i, w in enumerate(waveforms)]
    result = engine_mod.run_grouping(items, unit="single_motifs", basis="shape-distance",
                                     method="ward", params={})
    heights = [h for h in (result.merge_heights or []) if math.isfinite(_f(h))]
    if not heights:
        return []
    dist = bases_mod.distribution(heights, bin_method=bases_mod.BIN_QUANTILES,
                                  count=bases_mod.MAX_BINS)
    return [{"lo": _f(lo), "hi": _f(hi), "n": int(n)}
            for lo, hi, n in zip(dist.edges[:-1], dist.edges[1:], dist.counts)]


@router.get("/windowsets")
def get_window_sets(request: Request):
    """`WindowSetRow[]` from the real `window_sets` table."""
    conn = _conn(request)
    try:
        index = _recordings_index(conn)
        return [_window_set_row(conn, index, r) for r in
                conn.execute("SELECT * FROM window_sets ORDER BY name, version")]
    finally:
        conn.close()


def _window_set_row(conn, index, r) -> dict:
    meta = index["by_id"].get(int(r["recording_id"] or 0))
    split = json.loads(r["split_json"] or "null")
    spacing = json.loads(r["spacing_json"] or "{}")
    coverage = json.loads(r["coverage_json"] or "{}")
    fs = _f(r["fs"], meta["fs"] if meta else 1.0) or 1.0
    window_s = _f(r["window_length"]) / fs if r["window_length"] else None
    gap_s = _f(r["gap"]) / fs if r["gap"] else None

    counts = split if isinstance(split, dict) else None
    if counts and {"train", "validation", "test"} <= set(counts):
        split_counts = {k: int(counts[k]) for k in ("train", "validation", "test")}
        split_label = "blocked"
    elif counts and counts.get("test"):
        split_counts, split_label = None, "test only"
    else:
        split_counts, split_label = None, "no split"

    fs_source = "file"
    if meta:
        group = index["by_key"].get(meta["key"])
        fs_source = str((group or {}).get("fs_source") or "unrecorded")
    if fs_source in FS_INFERRED:
        check, reason = "fs inferred", (
            f"{meta['key'] if meta else 'this recording'}'s {fs:g} Hz is {fs_source}, not read from the file; "
            "every window boundary below is only as good as that number")
    elif gap_s is not None and window_s is not None and gap_s < window_s:
        check, reason = "gap < window", f"the gap between splits ({gap_s:g} s) is shorter than one window ({window_s:g} s)"
    elif split_label == "blocked":
        check, reason = "train-safe", "blocked split: no window straddles two splits"
    elif split_label == "test only":
        check, reason = "test sample", "test windows only; nothing here may train a model"
    else:
        check, reason = "not train-safe", "no split recorded, so nothing prevents a train/test leak"

    labelled = int(coverage.get("labelled_windows") or 0)
    n_windows = int(r["n_windows"] or 0)
    return {
        "id": r["name"], "version": int(r["version"] or 1),
        "saved": str(r["created_at"] or ""), "savedBy": "this installation",
        "source": str(r["labels_source"] or "—"),
        "recording": meta["label"] if meta else "—",
        "recordingKeys": [meta["key"]] if meta else [],
        "channels": [meta["name"]] if meta else [],
        "spacing": f"{_f(r['stride']) / fs:g} s" if r["stride"] else "—",
        "windowS": round(window_s, 3) if window_s else None,
        "gapS": round(gap_s, 3) if gap_s else None,
        "windows": n_windows,
        "split": split_counts, "splitLabel": split_label,
        "labelledPct": round(100.0 * labelled / n_windows, 1) if n_windows else 0.0,
        "labelledWindows": labelled,
        "usedBy": [], "usedLabel": None,
        "check": check, "checkReason": reason,
        "madeBy": str(r["labels_source"] or "—"), "recipeHash": r["recipe_hash"] or "",
        "lastUsed": "", "splitPlan": (split if isinstance(split, dict) and not split_counts else {}),
        "planHours": round(n_windows * (window_s or 0) / 3600.0, 2),
        "dropped": int(coverage.get("dropped") or 0),
        "spacingChecks": [{"label": k, "ok": bool(v)} for k, v in sorted(spacing.items())],
        "classCounts": {"now": coverage.get("class_counts") or {},
                        "atSave": coverage.get("class_counts_at_save") or {},
                        "atSaveLabelled": labelled},
        "path": r["path"],
    }


@router.get("/templates")
def get_templates(request: Request):
    """The Library's presentation `Template[]`, built from the REAL `templates`
    table (§4.5: there is no second template store).

    This is a *mapping*, not an alias: `api.ts` exports an id-keyed `Template`
    (`{id,name,builtin,steps,...}`) and the Library's is keyed by `name` and
    carries stages with glyphs, versions and scores. Both come from the same
    rows.
    """
    conn = _conn(request)
    try:
        from . import templates as templates_mod
        out = []
        for row in templates_mod.list_all(conn):
            steps = row["steps"] or []
            stages = [{"glyph": _glyph_for(s), "name": str(s.get("algorithm") or s.get("stage") or "step"),
                       "params": _params_text(s.get("params") or {})} for s in steps]
            # `runs` carries no template name; a run points at a `configs` row
            # and the recipe name lives inside its JSON. Matching on that is
            # honest about being a substring match rather than a foreign key.
            run_count = int(conn.execute(
                "SELECT COUNT(*) FROM runs r JOIN configs c ON c.id = r.config_id "
                "WHERE c.config_json LIKE ?", (f'%"{row["name"]}"%',)).fetchone()[0])
            out.append({
                "name": row["name"], "version": int(row.get("version") or 1),
                "kind": row.get("kind") or "detection",
                "signature": " → ".join(s["name"] for s in stages) or "—",
                "badges": ([{"label": "built-in", "tone": "purple"}] if row.get("builtin") else []) +
                          [{"label": row.get("kind") or "detection", "tone": "blue"}],
                "stages": stages,
                "recipe": row.get("description") or "",
                "nullModel": "—",
                "containsModel": any(s["glyph"] in ("model", "model_stage") for s in stages),
                "latest": None, "runs": f"{run_count} runs", "runCount": run_count,
                "lastRun": "", "versions": [], "scores": [],
                "id": row["id"],
            })
        return out
    finally:
        conn.close()


def _glyph_for(step) -> str:
    """A step's glyph. Matched on the algorithm name against the glyph
    vocabulary `BlockGlyph` consumes; `source` is the honest fallback because
    an unmapped block is still a block in the chain."""
    text = f"{step.get('stage','')}.{step.get('algorithm','')}".lower()
    for needle, glyph in TEMPLATE_GLYPHS:
        if needle in text:
            return glyph
    return "source"


@router.get("/sequences")
def get_sequences(request: Request, needs_extraction: int = Query(default=0)):
    """The sequences awaiting event extraction — Review's "extract events" queue.

    §4.4: a sequence whose events could not be resolved is written with
    `needs_extraction = 1` and no members. The claim is recorded; the events
    are not invented, and this route is how a person is asked to supply them.
    """
    conn = _conn(request)
    try:
        index = _recordings_index(conn)
        sql = "SELECT * FROM sequences"
        args = ()
        if int(needs_extraction):
            sql += " WHERE needs_extraction = 1"
        out = []
        for r in conn.execute(sql + " ORDER BY id"):
            meta = index["by_id"].get(int(r["recording_id"] or 0))
            fs = (meta["fs"] if meta else 1.0) or 1.0
            out.append({
                "id": f"sq-{r['id']}", "sequenceKey": r["sequence_key"], "origin": r["origin"],
                "recording": meta["label"] if meta else "—",
                "recordingKey": meta["key"] if meta else None,
                "channel": meta["name"] if meta else "—",
                "onsetH": round(int(r["start_idx"] or 0) / fs / 3600.0, 3),
                "nEvents": int(r["n_events"] or 0),
                "needsExtraction": bool(r["needs_extraction"]),
                "sourceKind": r["source_kind"], "sourceStore": r["source_store"],
                "createdAt": r["created_at"],
            })
        return out
    finally:
        conn.close()


# ═══════════════════════════════════════════════ WRITES AND JOBS ════════════

class GroupingRunBody(BaseModel):
    unit: str = "motifs"
    basis: str = "shape-distance"
    method: str = "ward"
    params: dict = Field(default_factory=dict)
    name: str | None = None
    limit: int | None = None


class GroupingSaveBody(BaseModel):
    unit: str = "motifs"
    basis: str = "shape-distance"
    method: str = "ward"
    params: dict = Field(default_factory=dict)
    cut: float | None = None
    name: str | None = None
    actor: str = "this installation"
    assignments: list = Field(default_factory=list)


def _grouping_items(conn, index, unit_db, limit=None):
    """The items the engine groups, with their waveforms read off disk."""
    if unit_db == "sequences":
        rows = conn.execute("SELECT id, recording_id, start_idx, end_idx, content_hash FROM sequences ORDER BY id").fetchall()
    else:
        scale = "train" if unit_db == "spike_trains" else "event"
        rows = conn.execute(
            "SELECT mm.id, mm.recording_id, mm.start_idx, mm.end_idx, mm.content_hash, mm.entry_id "
            "FROM motif_member mm JOIN motif_entry me ON me.id = mm.entry_id "
            "WHERE me.scale = ? OR (me.scale IS NULL AND ? = 'event') ORDER BY mm.id", (scale, scale)).fetchall()
    if limit:
        rows = rows[:int(limit)]
    items = []
    for r in rows:
        meta = index["by_id"].get(int(r["recording_id"] or 0))
        if meta is None or meta.get("held_out"):
            continue
        trace = _trace(index, r["recording_id"], r["start_idx"], r["end_idx"], px=64)
        if not trace:
            continue
        # `member_ref` / `values` are what `engine._ref` and `engine._waveform`
        # look for; `ref` / `waveform` raised a KeyError and failed every
        # regroup job (the job reported it, which is how it was found).
        item = {"member_ref": int(r["id"]), "content_hash": r["content_hash"], "values": trace,
                "fs": meta["fs"], "recording_id": meta["recording_id"], "channel": meta["name"]}
        if unit_db == "sequences":
            item["sequence_id"] = int(r["id"])
        items.append(item)
    return items


@router.post("/groupings/run")
def run_grouping_job(request: Request, body: GroupingRunBody):
    """Run a grouping as a `regroup` job. Returns the job id; the client
    streams `GET /api/jobs/{id}/events` as it already does for a chain run.

    The result carries spec §8.2's preview numbers — groups, members, omitted,
    recompute cost and what happens to the hand edits — because those are the
    numbers the page shows *before* asking whether to save.
    """
    rt = _rt(request)
    manager = request.app.state.manager
    unit_db = UNIT_TO_DB.get(body.unit, body.unit)
    if unit_db not in ("single_motifs", "sequences", "spike_trains"):
        raise HTTPException(status_code=400, detail=f"unknown grouping unit {body.unit!r}")

    def _work(job):
        conn = corpus.connect(rt.db_path)
        try:
            index = _recordings_index(conn)
            job.progress(0, 4, "reading the catalogue")
            items = _grouping_items(conn, index, unit_db, body.limit)
            job.progress(1, 4, f"{len(items)} items")
            if job.cancel_event.is_set():
                return None
            # As plain dicts: `active_edits` returns `sqlite3.Row`, and the
            # engine's item contract is dicts — `_hand_edit_outcome` reads
            # `edit.get("family_label")`, which a Row does not have. Converting
            # here rather than widening the engine keeps the engine free of the
            # database's row type, which is what lets it be tested without one.
            edits = [dict(e) for e in hand_edits_mod.active_edits(conn, None)]
            job.progress(2, 4, "grouping")
            preview = engine_mod.preview(items, unit=unit_db, basis=body.basis,
                                         method=body.method, params=body.params, hand_edits=edits)
            job.progress(3, 4, "measuring")
            result = preview.result
            assignments = [
                {"ref": a.ref, "contentHash": a.content_hash, "familyId": a.family_id,
                 "familyLabel": a.family_label, "distance": a.distance,
                 "isMedoid": bool(a.is_medoid), "omitReason": a.omit_reason}
                for a in result.assignments]
            job.progress(4, 4, "done")
            return {
                "unit": body.unit, "basis": body.basis, "method": body.method,
                "params": body.params, "recipeHash": result.recipe_hash,
                "preview": {
                    "groups": preview.n_groups, "members": preview.n_members,
                    "omitted": preview.n_omitted,
                    "omittedByReason": dict(preview.omitted_by_reason or {}),
                    "recompute": preview.recompute,
                    "handEdits": preview.hand_edits,
                },
                "mergeHeights": [ _f(h) for h in (result.merge_heights or []) ],
                "assignments": assignments,
            }
        finally:
            conn.close()

    job = manager.start_job("regroup", _work, meta={"what": "grouping", "unit": body.unit, "basis": body.basis})
    return {"job_id": job.id, "kind": "regroup", "status": job.status}


@router.post("/groupings")
def save_grouping(request: Request, body: GroupingSaveBody):
    """Save a computed grouping: the `groupings` row and its assignments.

    Rule 5: `groupings` and `grouping_assignments` are human tables (§3.5) — a
    grouping is a person's decision about how to carve the library up, not a
    detector's output — so both go through `write_human`.
    """
    conn = _conn(request)
    try:
        unit_db = UNIT_TO_DB.get(body.unit, body.unit)
        assigned = [a for a in body.assignments if a.get("familyLabel")]
        omitted = [a for a in body.assignments if not a.get("familyLabel")]
        families = {a["familyLabel"] for a in assigned}
        now = _dt.datetime.now().isoformat(timespec="seconds")
        gid = writes.write_human(conn, "groupings", {
            "name": body.name or f"{body.unit} · {body.basis}",
            "unit": unit_db, "basis": body.basis, "method": body.method,
            "params_json": json.dumps(body.params or {}, sort_keys=True),
            "cut": body.cut, "n_families": len(families),
            "n_assigned": len(assigned), "n_omitted": len(omitted),
            "recipe_hash": engine_mod.recipe_hash({
                "unit": unit_db, "basis": body.basis, "method": body.method, "params": body.params or {}}),
            "created_at": now, "actor": body.actor,
        })
        for a in body.assignments:
            writes.write_human(conn, "grouping_assignments", {
                "grouping_id": gid, "unit": unit_db,
                "member_ref": int(a.get("ref") or 0),
                "content_hash": a.get("contentHash"),
                "family_id": a.get("familyId"),
                "family_label": a.get("familyLabel"),
                "distance": a.get("distance"),
                "is_medoid": 1 if a.get("isMedoid") else 0,
                "omit_reason": a.get("omitReason"),
            })
        conn.commit()
        row = conn.execute("SELECT * FROM groupings WHERE id = ?", (gid,)).fetchone()
        return _grouping_payload(conn, row)
    finally:
        conn.close()


# ── import ──────────────────────────────────────────────────────────────────

class ImportBody(BaseModel):
    path: str
    kind: str | None = None          # 'drop_motif_store' | 'catalogue_spreadsheet' | 'annotations'
    exclude_corpora: list | None = None


def _bundle_kind(conn, path: str) -> str:
    row = conn.execute(
        "SELECT kind FROM registered_artifacts WHERE path = ? AND active = 1 LIMIT 1", (path,)).fetchone()
    if row:
        return row["kind"]
    return "catalogue_spreadsheet" if str(path).lower().endswith((".xlsx", ".xls")) else "drop_motif_store"


def _abs_bundle(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(REPO_ROOT, path)


def _import_bundle_payload(conn, path, report, kind, blocked=None, held_out=False) -> dict:
    """`ImportBundle` — what the dry run draws.

    The counts are read from the report's own `outcomes` counter rather than
    reconstructed from `n_created` + `n_duplicate`. `n_duplicate` counts the
    `member_added` outcome only, so a bundle that is already held end to end
    reported "0 of 410 rows already describe a shape this library holds" on
    the same card whose outcome line read `already_present × 410`, and the
    headline tile said "0 motifs" for a 410-row bundle. Reading the counter
    directly also means this stays right whichever way `n_duplicate` is
    defined in the importer.
    """
    index = None
    counts = {"motifs": 0, "spikeTrains": 0, "recordings": 0, "channels": 0}
    checks, creates, sample = [], [], []
    if report is not None:
        d = report.as_dict() if hasattr(report, "as_dict") else dict(report)
        outcomes = {str(k): int(v) for k, v in (d.get("outcomes") or {}).items()}
        n_rows = int(d.get("n_rows", 0))
        skipped = outcomes.get(store_importer.SKIPPED, 0)
        # every row that describes a motif: the bundle minus the rows no
        # importer will touch
        decided = sum(outcomes.values())
        counts["motifs"] = max(0, (decided if decided else n_rows) - skipped)
        # a row already held is one that resolved onto a shape this library
        # has — whether it added an occurrence, found the occurrence already
        # described, or only filled in a missing revision
        already = (outcomes.get(store_importer.MEMBER_ADDED, 0)
                   + outcomes.get(store_importer.ALREADY_PRESENT, 0)
                   + outcomes.get(store_importer.REVISION_ADDED, 0))
        index = _recordings_index(conn)
        samples = d.get("samples", [])
        rec_ids = {int(s["recording_id"]) for s in samples if s.get("recording_id") is not None}
        counts["channels"] = len(rec_ids)
        counts["recordings"] = len({index["by_id"][r]["key"] if r in index["by_id"] else f"#{r}"
                                    for r in rec_ids})
        if outcomes:
            checks.append({"status": "ok", "title": "safe to run twice",
                           "detail": (f"{already} of {n_rows} rows already describe a shape "
                                      "this library holds; a second import adds members, never a "
                                      "second entry.")})
        else:
            # the catalogue and annotation importers report per-key totals, not
            # a per-row outcome. Saying "0 of 0 rows already held" of a bundle
            # this read never counted rows for would be a number, not a fact.
            totals = {str(k): int(v) for k, v in (d.get("counts") or {}).items()}
            checks.append({"status": "ok", "title": "safe to run twice",
                           "detail": ("this importer reports totals rather than a per-row outcome, "
                                      "so how many rows are already held is not recorded here"
                                      + (" · " + " · ".join(f"{k} {v}" for k, v in sorted(totals.items()))
                                         if totals else ""))})
        if d.get("warnings"):
            checks.append({"status": "warn", "title": "warnings from the store",
                           "detail": f"{len(d['warnings'])} warnings", "items": [str(w) for w in d["warnings"][:10]]})
        if d.get("flags"):
            checks.append({"status": "warn", "title": "near-duplicates flagged",
                           "detail": (f"{len(d['flags'])} spans overlap an existing one by more than the IoU "
                                      "threshold. Nothing is merged; each is flagged with the rule it was judged under."),
                           "items": [str(f) for f in d["flags"][:10]]})
        creates = [f"{k} × {v}" for k, v in sorted(outcomes.items())]
        # the preview reads the keys the importer actually emits — `source_ref`,
        # `recording_id`, `start_idx`/`end_idx`, `outcome`. It used to ask for
        # `event_id`, `recording`, `onset_h`, `duration_s` and `amplitude_mv`,
        # none of which exist on a sample, so every row defaulted to 0 and "—"
        # and twelve identical blank motifs were drawn as the preview. A field
        # this read does not carry is `None`, never a zero.
        for s in samples[:12]:
            rid = s.get("recording_id")
            meta = index["by_id"].get(int(rid)) if rid is not None else None
            start, end = s.get("start_idx"), s.get("end_idx")
            fs = (meta["fs"] if meta else 0.0) or 0.0
            row = {
                "id": str(s.get("source_ref")) if s.get("source_ref") is not None else None,
                "recording": meta["label"] if meta else None,
                "recordingKey": meta["key"] if meta else None,
                "channel": meta["name"] if meta else None,
                "onsetH": round(int(start) / fs / 3600.0, 3) if (meta and fs and start is not None) else None,
                "durationS": (round((int(end) - int(start)) / fs, 2)
                              if (meta and fs and start is not None and end is not None) else None),
                # the store carries no morphology per row and this read reads
                # no samples off the memmap, so neither is invented here
                "shape": None, "amp": None, "seed": None,
                "outcome": s.get("outcome"), "detail": s.get("detail"),
            }
            sample.append(row)
    bundle = {
        "path": path, "provenanceFound": bool(report is not None and getattr(report, "source", None)),
        "counts": counts, "checks": checks, "creates": creates, "sample": sample,
        "kind": kind,
    }
    if blocked:
        bundle["blockedReason"] = blocked
        checks.append({"status": "fail", "title": "cannot import", "detail": blocked})
    if held_out:
        bundle["heldOut"] = True
    return bundle


def _dry_run(conn, path: str, kind: str, exclude=None):
    """Drive the right importer with `dry_run=True`. Returns
    `(report, blocked_reason)`; the importer's own named refusals become the
    blocked reason rather than an exception the page cannot draw."""
    target = _abs_bundle(path)
    try:
        if kind == "catalogue_spreadsheet":
            return cat_importer.import_catalogue(conn, target, dry_run=True), None
        if kind == "annotations":
            return ann_importer.import_annotations(conn, dry_run=True), None
        kwargs = {"dry_run": True}
        if exclude is not None:
            kwargs["exclude_corpora"] = tuple(exclude)
        return store_importer.import_event_store(conn, target, **kwargs), None
    except store_importer.StoreRefused as e:
        return None, str(e)
    except FileNotFoundError as e:
        return None, str(e)


@router.post("/import/dry-run")
def import_dry_run(request: Request, body: ImportBody):
    """An `ImportBundle` that writes NOTHING.

    The importers guard every write site under `dry_run=True` and compare the
    row counts of every table they can touch before and after, so a dry run
    that wrote something raises rather than returning a report that lies.
    """
    conn = _conn(request)
    try:
        if _is_held_out_path(body.path):
            return _import_bundle_payload(
                conn, body.path, None, body.kind or "drop_motif_store", held_out=True,
                blocked=(f"{HELD_OUT_FILE} is held out (spec §0 D6). The bridge refuses it on every route, "
                         "in both runtime modes, and no import may write a row that describes it."))
        kind = body.kind or _bundle_kind(conn, body.path)
        report, blocked = _dry_run(conn, body.path, kind, body.exclude_corpora)
        return _import_bundle_payload(conn, body.path, report, kind, blocked=blocked)
    finally:
        conn.close()


@router.post("/import")
def start_import(request: Request, body: ImportBody):
    """The real import, as an `import` job with progress."""
    rt = _rt(request)
    manager = request.app.state.manager
    if _is_held_out_path(body.path):
        raise HTTPException(status_code=423, detail=f"{HELD_OUT_FILE} is held out; no import may write it.")

    def _work(job):
        conn = corpus.connect(rt.db_path)
        try:
            kind = body.kind or _bundle_kind(conn, body.path)
            target = _abs_bundle(body.path)

            def progress(done, total=None, message=""):
                job.progress(done, total, message)

            job.progress(0, None, f"importing {os.path.basename(body.path)}")
            if kind == "catalogue_spreadsheet":
                report = cat_importer.import_catalogue(conn, target, progress=progress)
            elif kind == "annotations":
                report = ann_importer.import_annotations(conn, progress=progress)
            else:
                kwargs = {"progress": progress}
                if body.exclude_corpora is not None:
                    kwargs["exclude_corpora"] = tuple(body.exclude_corpora)
                report = store_importer.import_event_store(conn, target, **kwargs)
            conn.commit()
            return {"path": body.path, "kind": kind,
                    "report": report.as_dict() if hasattr(report, "as_dict") else dict(report)}
        finally:
            conn.close()

    job = manager.start_job("import", _work, meta={"what": "import", "path": body.path})
    return {"job_id": job.id, "kind": "import", "status": job.status}


@router.get("/import/bundles")
def import_bundles(request: Request):
    """Importable bundles read from the REGISTRY (`registered_artifacts`), not
    by rescanning the disk — Prompt 02's rule. A bundle the registry does not
    know about is not offered, which is what makes the list reproducible."""
    conn = _conn(request)
    try:
        out = []
        for r in conn.execute(
            "SELECT id, kind, path, name, created_at FROM registered_artifacts "
            "WHERE active = 1 AND kind IN ('drop_motif_store', 'catalogue_spreadsheet') ORDER BY id DESC"):
            held = _is_held_out_path(r["path"])
            out.append({"path": r["path"], "name": r["name"] or os.path.basename(str(r["path"])),
                        "kind": r["kind"], "registeredAt": r["created_at"], "heldOut": bool(held)})
        return out
    finally:
        conn.close()


# ── hand edits ──────────────────────────────────────────────────────────────

class HandEditBody(BaseModel):
    contentHash: str
    kind: str
    familyLabel: str | None = None
    value: str | None = None
    grouping: str | None = None
    actor: str = "this installation"


@router.post("/hand-edits")
def post_hand_edit(request: Request, body: HandEditBody):
    """Record one hand edit, through `write_human` (rule 5: `hand_edits` is a
    human table — it is by definition a person's decision).

    The core keys an edit by content hash rather than by member id, which is
    what makes it survive a regroup, a re-import and a re-clustering.
    """
    conn = _conn(request)
    try:
        if body.kind not in hand_edits_mod.KINDS:
            raise HTTPException(status_code=400,
                                detail=f"hand edit kind must be one of {sorted(hand_edits_mod.KINDS)}, got {body.kind!r}")
        if not body.contentHash:
            raise HTTPException(status_code=400, detail=(
                "a hand edit needs a contentHash: it is keyed by the shape, not by a member id, "
                "so that it survives a regroup and a re-import"))
        edit_id = writes.write_human(conn, "hand_edits", {
            "content_hash": body.contentHash, "kind": body.kind,
            "family_label": body.familyLabel, "value": body.value,
            "grouping_id": gid_int(body.grouping),
            "active": 1,
            "created_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "actor": body.actor,
        })
        conn.commit()
        row = conn.execute("SELECT * FROM hand_edits WHERE id = ?", (edit_id,)).fetchone()
        return {"id": edit_id, **{k: row[k] for k in row.keys()}}
    finally:
        conn.close()


@router.delete("/hand-edits/{edit_id}")
def delete_hand_edit(request: Request, edit_id: int):
    """Undo one hand edit. `Working.library.hand_edits.undo` flips `active` to
    0 rather than deleting the row: what a person decided and then changed
    their mind about is itself a record (rule: nothing here hard-deletes)."""
    conn = _conn(request)
    try:
        row = conn.execute("SELECT * FROM hand_edits WHERE id = ?", (int(edit_id),)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"no hand edit {edit_id}")
        hand_edits_mod.undo(conn, int(edit_id))
        return {"id": int(edit_id), "active": 0, "undone": True}
    finally:
        conn.close()


# ── export ──────────────────────────────────────────────────────────────────

def _attachment(payload, filename: str, fmt: str) -> StreamingResponse:
    """A real download: the right content type and a Content-Disposition
    attachment, so the browser saves a file instead of rendering JSON."""
    if fmt == "csv":
        buf = io.StringIO()
        rows = payload if isinstance(payload, list) else [payload]
        flat = [_flatten(r) for r in rows]
        columns = []
        for r in flat:
            for k in r:
                if k not in columns:
                    columns.append(k)
        writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for r in flat:
            writer.writerow(r)
        body, media = buf.getvalue(), "text/csv"
    else:
        body, media = json.dumps(payload, indent=2), "application/json"
    return StreamingResponse(
        io.BytesIO(body.encode("utf-8")), media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}.{fmt}"'})


def _flatten(row) -> dict:
    """One CSV row. A nested value becomes compact JSON in its cell rather
    than `[object Object]` — a spreadsheet cell that still carries the fact."""
    out = {}
    for k, v in (row or {}).items():
        if isinstance(v, (dict, list)):
            if k in ("exemplarTrace", "medoidTrace", "cells", "ampBins"):
                out[k] = json.dumps(v, separators=(",", ":"))[:2000]
            else:
                out[k] = json.dumps(v, separators=(",", ":"))
        else:
            out[k] = v
    return out


@router.get("/export/family/{family_id}")
def export_family(request: Request, family_id: str,
                  grouping: str | None = Query(default=None),
                  format: str = Query(default="json")):
    """One family as a downloadable file."""
    fmt = "csv" if str(format).lower() == "csv" else "json"
    conn = _conn(request)
    try:
        index = _recordings_index(conn)
        row = _resolve_grouping(conn, grouping)
        families = _families_for(conn, index, row)
        fam = next((f for f in families if f["id"] == family_id), None)
        if fam is None:
            raise HTTPException(status_code=404, detail=f"no family {family_id!r} in grouping {grouping!r}")
        detail = _family_detail(conn, index, fam, row)
        payload = detail["members"] if fmt == "csv" else detail
        return _attachment(payload, f"family-{family_id}", fmt)
    finally:
        conn.close()


@router.get("/export/atlas")
def export_atlas(request: Request, grouping: str | None = Query(default=None),
                 format: str = Query(default="json")):
    """The whole atlas as a downloadable file."""
    fmt = "csv" if str(format).lower() == "csv" else "json"
    conn = _conn(request)
    try:
        index = _recordings_index(conn)
        row = _resolve_grouping(conn, grouping)
        families = _families_for(conn, index, row)
        payload = families if fmt == "csv" else {
            "grouping": _grouping_payload(conn, row) if row else None, "families": families}
        return _attachment(payload, "atlas", fmt)
    finally:
        conn.close()
