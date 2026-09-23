"""
features.py
============
`motif_features`: per-event features stored ON THE MOTIF, keyed by content
hash (fixup-d; QUESTIONS.md Q-I1, Q-I4, Q14). Recomputable from the snippet,
never authoritative, never a comparison.

This is a deliberate, versioned change to Library spec §4.4 and
`LIBRARY_STORAGE.md` §3.4, which rejected measured features on Library ROWS
("a row's meaning would then depend on whichever interrogation happened to run
last"). The rows are untouched: features live in their own table, keyed by the
hash of the very waveform they were measured on, so a measurement cannot
outlive its waveform. `Working/library/grouping/bases.py` keeps computing its
four grouping features on demand; nothing here replaces it.

Which waveform
--------------
**The store's `detrended_mv` snippet** — the array the event-store importer
hashed (`importers/event_store.py`, "The waveform that is hashed"). So the
feature row keyed by hash H is a measurement of H's own samples, and the
shape measures come from `Working.interrogation.event_shape` with `to_mv = 1`
(the snippet is already mV). A chain run is NOT a source: its detrend differs,
so its waveform would not hash to the Library's H, and writing its numbers
under H would describe a different waveform than H names.

The detector's own numbers
--------------------------
The Library import took span indices and dropped every amplitude the detector
computed; filtering the Library by amplitude was impossible, and peak-to-peak
over the stored span is the wrong measure (the snippet is ~4x the onset-to-
trough extent). So where a detector produced the event, its own numbers are
carried beside ours under `source = 'detector'`: `drop_depth_mv` (what
Q-X2.5's floor filter must filter on), `fall_duration_s`, `peak_to_peak_mv`,
`rise_height_mv`, and the slopes in mV/s — `max_slope_raw` is V/s with fs
already applied (`detect5.py:596`, verified 338/338 by fixup-b), so mV/s =
raw x 1000 with no second fs factor.

A caveat recorded rather than hidden: the content hash is z-normalised, so it
is blind to amplitude; two motifs of the same shape at different depths would
share a hash and therefore one feature row. On the live Library today every one
of the 3,603 members has a distinct hash, so the case does not occur.

No plotting library - CLAUDE.md rule 1. No bulk array enters the database.
"""

import datetime
import math
import os

import numpy as np

from Working.interrogation import event_shape as ES
from Working.library.identity import content_hash

SHAPE_SOURCE = "interrogation.event_shape"
DETECTOR_SOURCE = "detector"
DETECTOR_PREFIX = "detector_"

RULE_VERSION = (f"event_shape/1 anchors=detector knee_frac={ES.KNEE_FRAC:g} recovery_frac={ES.RECOVERY_FRAC:g} "
                f"recovery_max_mult={ES.RECOVERY_MAX_MULT:g} walk_onset_back=1 polarity=drop")

# detector column -> (feature name, factor to the stated unit)
_DETECTOR_COLUMNS = {
    "drop_depth_mv": ("drop_depth_mv", 1.0),
    "fall_duration_s": ("fall_duration_s", 1.0),
    "peak_to_peak_mv": ("peak_to_peak_mv", 1.0),
    "rise_height_mv": ("rise_height_mv", 1.0),
    "max_slope_raw": ("max_slope_mv_s", 1000.0),     # V/s, fs applied once -> mV/s
    "onset_slope_raw": ("onset_slope_mv_s", 1000.0),
}


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _finite(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def detector_anchor(event):
    """The detector's own onset and trough, relative to its snippet, or None."""
    try:
        s0 = int(event["snippet_start_idx"])
        return int(event["onset_idx"]) - s0, int(event["trough_idx"]) - s0
    except (KeyError, TypeError, ValueError):
        return None


def measure_snippet(values_mv, fs, anchor=None):
    """Event shape's measures of one Library snippet (already mV), as a dict of
    `MEASURES` plus the snippet-relative onset / extremum the rose needs.

    `anchor` is the detector's `(onset, trough)` in the snippet when a detector
    produced the event: a stored snippet carries minutes of context either side
    (410 seed events: pre-context up to 443 s), and on 10 of the 360 the block's
    own anatomy search locks onto a steeper NEIGHBOUR. Where the detector said
    which fall it meant, that is the event; FWHM, recovery and the rest are then
    measured from the detector's anchors, and the depth IS the detector's depth."""
    v = np.asarray(values_mv, dtype=float).ravel()
    feats, _ = ES.measure_events(v, [0], [len(v)], fs, to_mv=1.0, anchors=None if anchor is None else [anchor])
    row = feats.iloc[0]
    out = {k: _finite(row[k]) for k in ES.MEASURES}
    out["polarity"] = int(row["polarity"])
    out["onset_idx"] = _finite(row["onset_idx"])
    out["extremum_idx"] = _finite(row["extremum_idx"])
    return out


def detector_measures(event):
    """The detector's own per-event numbers off an events/motifs row."""
    out = {}
    for col, (name, factor) in _DETECTOR_COLUMNS.items():
        v = _finite(event.get(col))
        if v is not None:
            out[name] = v * factor
    return out


def features_from_event_store(store_path, event_ids=None, *, store=None):
    """One row per event of a drop-motif store: its content hash (over the
    `detrended_mv` snippet, the importer's hashed waveform), fs, Event shape's
    measures and the detector's own. `store` is a `read_event_store` result, if
    the caller already has one."""
    if store is None:
        from Working.library.importers.event_store import read_event_store
        store = read_event_store(store_path)
    wanted = None if event_ids is None else set(event_ids)
    rows = []
    for e in store["events"]:
        eid = str(e["event_id"])
        if wanted is not None and eid not in wanted:
            continue
        snip = store["snippets"].get(eid)
        if snip is None or "detrended_mv" not in snip:
            continue
        values = np.asarray(snip["detrended_mv"], dtype=float)
        fs = float(e["fs"])
        rows.append({"event_id": eid, "content_hash": content_hash(values), "fs": fs,
                     "measures": measure_snippet(values, fs, detector_anchor(e)), "detector": detector_measures(e)})
    return rows


def write_features(conn, rows, *, rule_version=RULE_VERSION, commit=True):
    """Upsert every measure of every row; returns how many values were written.
    A re-measurement REPLACES its predecessor (one value per hash, fs, source,
    feature) — the table is a cache of a computation, not a history."""
    now = _now()
    n = 0
    for r in rows:
        items = [(SHAPE_SOURCE, k, v) for k, v in (r.get("measures") or {}).items()]
        items += [(DETECTOR_SOURCE, k, v) for k, v in (r.get("detector") or {}).items()]
        for source, feature, value in items:
            conn.execute(
                "INSERT INTO motif_features (content_hash, fs, source, feature, value, rule_version, computed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (content_hash, fs, source, feature) DO UPDATE SET "
                "value = excluded.value, rule_version = excluded.rule_version, computed_at = excluded.computed_at",
                (str(r["content_hash"]), float(r["fs"]), source, str(feature), _finite(value),
                 rule_version if source == SHAPE_SOURCE else "detector", now))
            n += 1
    if commit:
        conn.commit()
    return n


def read_features(conn, content_hashes, *, fs=None):
    """`{hash: {feature: value}}` — Event shape's measures under their own names,
    the detector's prefixed `detector_`. NULL reads back as NaN. A hash measured
    at more than one fs returns the first unless `fs` picks one."""
    hashes = [str(h) for h in content_hashes]
    out = {}
    for i in range(0, len(hashes), 500):
        chunk = hashes[i:i + 500]
        sql = ("SELECT content_hash, fs, source, feature, value FROM motif_features WHERE content_hash IN (%s)"
               % ",".join("?" * len(chunk)))
        params = list(chunk)
        if fs is not None:
            sql += " AND fs = ?"
            params.append(float(fs))
        for r in conn.execute(sql + " ORDER BY fs", params):
            h, feature = r[0], r[3]
            key = feature if r[2] == SHAPE_SOURCE else DETECTOR_PREFIX + feature
            out.setdefault(h, {}).setdefault(key, float("nan") if r[4] is None else float(r[4]))
    return out


def _has_shape(conn, digest, fs):
    return conn.execute("SELECT 1 FROM motif_features WHERE content_hash = ? AND fs = ? AND source = ? LIMIT 1",
                        (digest, float(fs), SHAPE_SOURCE)).fetchone() is not None


def backfill_library(conn, *, repo_root=None, only_missing=True, progress=None):
    """Measure every Library entry whose snippet a store holds and write its row.

    Reads `motif_entry.source_store` + `source_ref` (the `.npz` key, §3.2) —
    one store read per store, not per entry. Everything that cannot be measured
    is counted with its reason, never dropped silently. Returns the report.
    """
    from Working.library.importers.event_store import SOURCE_KIND, read_event_store
    repo_root = repo_root or os.getcwd()
    report = {"measured": 0, "already_present": 0, "values_written": 0, "skipped": {}, "stores": {}}

    def skip(reason):
        report["skipped"][reason] = report["skipped"].get(reason, 0) + 1

    entries = conn.execute(
        "SELECT id, content_hash, source_kind, source_store, source_ref FROM motif_entry "
        "WHERE content_hash IS NOT NULL ORDER BY source_store, id").fetchall()
    stores = {}
    for i, (eid, digest, kind, store_ref, ref) in enumerate(entries):
        if progress is not None:
            progress(i, len(entries))
        if kind != SOURCE_KIND or not store_ref or not ref:
            skip("no_store_snippet")
            continue
        if store_ref not in stores:
            path = store_ref if os.path.isabs(store_ref) else os.path.join(repo_root, *store_ref.split("/"))
            try:
                st = read_event_store(path)
                stores[store_ref] = (st, {str(e["event_id"]): e for e in st["events"]})
            except (FileNotFoundError, OSError) as exc:
                stores[store_ref] = None
                report["stores"][store_ref] = f"unreadable: {exc}"
        if stores[store_ref] is None:
            skip("store_unreadable")
            continue
        st, by_id = stores[store_ref]
        event = by_id.get(str(ref))
        if event is None or str(ref) not in st["snippets"]:
            skip("event_not_in_store")
            continue
        fs = float(event["fs"])
        if only_missing and _has_shape(conn, digest, fs):
            report["already_present"] += 1
            continue
        values = np.asarray(st["snippets"][str(ref)]["detrended_mv"], dtype=float)
        if content_hash(values) != digest:
            skip("snippet_hash_mismatch")          # never file a measurement under a hash it does not describe
            continue
        row = {"content_hash": digest, "fs": fs, "measures": measure_snippet(values, fs, detector_anchor(event)),
               "detector": detector_measures(event)}
        report["values_written"] += write_features(conn, [row], commit=False)
        report["measured"] += 1
        report["stores"].setdefault(store_ref, "read")
    conn.commit()
    return report
