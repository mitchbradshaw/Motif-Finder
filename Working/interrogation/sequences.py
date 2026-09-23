"""
sequences.py
=============
The per-event measures of a stored sequence, and the rose that compares the
steepest slopes ACROSS THE EVENTS OF ONE SEQUENCE (fixup-d, seam 4).

`gradients.rose_data`'s default split is `span_key` — an analysed span, not a
sequence. A sequence is its own unit (`sequences` + `sequence_members`,
`schema.py`), and no `motif_entry` carries `scale = 'train'`, so the rose keys
off `sequences`: the sequence key is handed to `rose_data` as the group, whose
per-group output takes it unchanged.

Each member's features come from `motif_features` when stored (by the member's
content hash, the way Q14 decided) and are otherwise measured from the Library
snippet on the spot — flagged `stored: false`, and NOT written: a view writes
nothing, and the backfill is the one write path. The rose is taken on the
snippet with the same onset and extremum the feature table reports, so the
drawn angle and the quoted slope are one measurement.

No plotting library - CLAUDE.md rule 1.
"""

import os

import numpy as np

from Working.Detection.drop_motifs.gradients import DEFAULT_SLOPE_REF_MV_S, SLOPE_SCALES, rose_data
from Working.interrogation.event_shape import MEASURES, rose_payload
from Working.library import features as F


def list_sequences(conn):
    """Every sequence with at least one member row, largest first."""
    rows = conn.execute(
        "SELECT s.id, s.sequence_key, s.origin, s.recording_id, s.channel, s.n_events, s.source_kind, "
        "r.source_file, r.fs, COUNT(m.id) AS n_members FROM sequences s "
        "JOIN sequence_members m ON m.sequence_id = s.id LEFT JOIN recordings r ON r.id = s.recording_id "
        "GROUP BY s.id ORDER BY n_members DESC, s.id").fetchall()
    keys = ("id", "sequence_key", "origin", "recording_id", "channel", "n_events", "source_kind", "source_file",
            "fs", "n_members")
    return [dict(zip(keys, tuple(r))) for r in rows]


class _Stores:
    """One read per store, however many members share it."""

    def __init__(self, repo_root):
        self.repo_root = repo_root
        self._cache = {}

    def event(self, store_ref, ref):
        from Working.library.importers.event_store import read_event_store
        if store_ref not in self._cache:
            path = store_ref if os.path.isabs(store_ref) else os.path.join(self.repo_root, *store_ref.split("/"))
            try:
                st = read_event_store(path)
                self._cache[store_ref] = (st, {str(e["event_id"]): e for e in st["events"]})
            except (FileNotFoundError, OSError):
                self._cache[store_ref] = None
        cached = self._cache[store_ref]
        if cached is None:
            return None, None
        st, by_id = cached
        snip = st["snippets"].get(str(ref))
        return by_id.get(str(ref)), (None if snip is None else np.asarray(snip["detrended_mv"], dtype=float))


def store_cache(repo_root):
    """A store reader to keep across calls (the stores are read-only files; the bridge
    holds one so a second look at a sequence does not re-read a 3,000-event npz)."""
    return _Stores(repo_root)


def sequence_shape(conn, sequence_id, *, scale="raw", reference=DEFAULT_SLOPE_REF_MV_S, repo_root=None, stores=None):
    """`{"sequence", "events", "rose"}` for one sequence, members in position order."""
    if scale not in SLOPE_SCALES:
        raise ValueError(f"rose scale must be one of {SLOPE_SCALES}, got {scale!r}")
    seq = conn.execute("SELECT s.*, r.source_file AS source_file FROM sequences s LEFT JOIN recordings r "
                       "ON r.id = s.recording_id WHERE s.id = ?", (int(sequence_id),)).fetchone()
    if seq is None:
        raise LookupError(f"sequence {sequence_id} does not exist")
    seq = dict(seq)
    members = conn.execute(
        "SELECT sm.position, sm.start_idx, sm.end_idx, sm.gap_before, sm.member_id, mm.content_hash, "
        "e.source_kind, e.source_store, e.source_ref FROM sequence_members sm "
        "LEFT JOIN motif_member mm ON mm.id = sm.member_id "
        "LEFT JOIN motif_entry e ON e.content_hash = mm.content_hash "
        "WHERE sm.sequence_id = ? GROUP BY sm.id ORDER BY sm.position", (int(sequence_id),)).fetchall()
    stores = stores or _Stores(repo_root or os.getcwd())
    stored = F.read_features(conn, [m["content_hash"] for m in members if m["content_hash"]])
    key = str(seq["sequence_key"])

    events, rose_events, snippets = [], [], {}
    for m in members:
        ev = {"position": int(m["position"]), "member_id": m["member_id"], "content_hash": m["content_hash"],
              "start_idx": int(m["start_idx"]), "end_idx": int(m["end_idx"]),
              "gap_before_s": None if m["gap_before"] is None else float(m["gap_before"]),
              "stored": False, "features": None, "detector": None, "why": None}
        event, snip = (None, None)
        if m["source_kind"] == "event_store" and m["source_store"] and m["source_ref"]:
            event, snip = stores.event(m["source_store"], m["source_ref"])
        have = stored.get(m["content_hash"]) if m["content_hash"] else None
        if have and any(k in have for k in MEASURES):
            ev["stored"] = True
            ev["features"] = {k: _clean(v) for k, v in have.items() if not k.startswith(F.DETECTOR_PREFIX)}
            ev["detector"] = {k[len(F.DETECTOR_PREFIX):]: _clean(v) for k, v in have.items()
                              if k.startswith(F.DETECTOR_PREFIX)}
        elif snip is not None:
            fs = float(event["fs"])
            ev["features"] = F.measure_snippet(snip, fs, F.detector_anchor(event))
            ev["detector"] = F.detector_measures(event)
        else:
            ev["why"] = "no Library snippet for this member (not from an event store) and no stored features"
        feats = ev["features"] or {}
        if snip is not None and feats.get("onset_idx") is not None and feats.get("extremum_idx") is not None:
            eid = str(len(rose_events))
            orient = 1.0 if (feats.get("polarity") or -1) < 0 else -1.0
            rose_events.append({"event_id": eid, "snippet_start_idx": 0, "onset_idx": int(feats["onset_idx"]),
                                "trough_idx": int(feats["extremum_idx"]), "fs": float(event["fs"]), "span_key": key,
                                "span_label": key, "recording_id": int(seq["recording_id"] or 0),
                                "source_file": seq.get("source_file") or "", "onset_h": 0.0,
                                "drop_depth_mv": float(feats.get("event_amplitude_mv") or 0.0),
                                "fall_duration_s": float(feats.get("event_width_s") or 0.0),
                                "position": ev["position"]})
            snippets[eid] = {"detrended_mv": orient * snip}
        events.append(ev)

    rd = rose_data(rose_events, snippets, scale=scale, fixed=reference, field="max_slope_mv_s", split_by="span_key")
    rose = rose_payload(rd, [e["position"] for e in rose_events])
    seq_out = {k: seq.get(k) for k in ("id", "sequence_key", "origin", "recording_id", "channel", "n_events",
                                        "source_kind", "source_store", "source_file")}
    seq_out["n_members"] = len(events)
    seq_out["n_stored"] = sum(1 for e in events if e["stored"])
    return {"sequence": seq_out, "events": events, "rose": rose}


def _clean(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return v
    return v if np.isfinite(v) else None
