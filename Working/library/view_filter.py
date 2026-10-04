"""
view_filter.py
==============
What the Library SHOWS (fixup-AE; `QUESTIONS.md` Q21, Q22, Q-X2.5). A view
filter, never a gate: nothing here writes, and every member it hides is
counted — per import store, per dataset — so a page can say how much is under
the floor rather than quietly having less in it.

The noise floor (Q21, Q-X2.5)
-----------------------------
**The floor** is the dataset's own: Settings › Datasets › *noise floor*, the
key ``meta.<stem>.noise_floor`` (``stem`` the recording's directory name, as
Settings › Datasets names it). Where it is empty, **0.1 mV** — the instrument
floor `detect5.py:927` names.

**What is compared with it** is the detector's own ``drop_depth_mv`` from
``motif_features`` (``source = 'detector'``) — not peak-to-peak over the stored
span, which Q-X2.5 measured to be the wrong measure. Where a member has no
detector depth, ``interrogation.event_shape``'s depth (``event_amplitude_mv``)
is used and the member says so. Where it has neither it is **unmeasured**:
shown, counted and badged, never silently passed as above the floor and never
hidden.

The two other filters (Q22)
---------------------------
``fall_duration_s`` (the detector's, globally comparable) is a range; ``is_pure``
(one fall in the window, or several) is a toggle. A member neither filter can
judge — no fall duration, no purity recorded — is shown and counted, by the same
rule as the floor. ``scale_band`` is **not** a filter: it is a within-span octave
index (band 1 is 174 s in one span and 4 s in another), carried as provenance
with its own duration range.

Headless: plain SQL over an open connection, no UI import (rule 1).
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

from Working.library import features as F

#: Q-X2.5: the instrument floor, used where a dataset's own floor is empty.
DEFAULT_FLOOR_MV = 0.1
#: Settings › Datasets: `meta.<stem>.noise_floor` (webui/server/registration.py).
FLOOR_PAGE = "datasets"
FLOOR_KEY = "meta.{stem}.noise_floor"

ABOVE, SUB_FLOOR, UNMEASURED = "above", "sub_floor", "unmeasured"
DEPTH_DETECTOR = "detector"
DEPTH_SHAPE = F.SHAPE_SOURCE
DEPTH_FEATURE = "drop_depth_mv"
SHAPE_DEPTH_FEATURE = "event_amplitude_mv"

FLOOR_RULE = ("noise floor: a member is hidden when the detector's own drop_depth_mv (else interrogation.event_shape's "
              "event_amplitude_mv) is under its dataset's noise floor (Settings › Datasets; 0.1 mV where empty). "
              "A member with neither depth is unmeasured: shown and counted. Nothing is deleted.")


def _num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


@dataclass(frozen=True)
class ViewFilter:
    """The Library's view: the floor ON by default, nothing else."""
    floor: bool = True
    fall_min_s: float | None = None
    fall_max_s: float | None = None
    pure_only: bool = False

    @classmethod
    def from_query(cls, floor=None, fall_min=None, fall_max=None, pure=None):
        """From query strings: ``floor=0`` turns the floor off; an empty bound is no bound."""
        def flag(v, default):
            if v in (None, ""):
                return default
            return str(v).strip().lower() not in ("0", "false", "no", "off")
        return cls(floor=flag(floor, True), fall_min_s=_num(fall_min) if fall_min not in (None, "") else None,
                   fall_max_s=_num(fall_max) if fall_max not in (None, "") else None, pure_only=flag(pure, False))

    @property
    def has_fall(self):
        return self.fall_min_s is not None or self.fall_max_s is not None

    def describe(self) -> str:
        parts = [("noise floor on: sub-floor members hidden" if self.floor else "noise floor off: sub-floor members shown")]
        if self.has_fall:
            lo = "0" if self.fall_min_s is None else f"{self.fall_min_s:g}"
            hi = "∞" if self.fall_max_s is None else f"{self.fall_max_s:g}"
            parts.append(f"fall duration {lo}–{hi} s")
        if self.pure_only:
            parts.append("pure windows only (one fall per window)")
        return " · ".join(parts)

    def as_dict(self) -> dict:
        return {"floor": self.floor, "fallMinS": self.fall_min_s, "fallMaxS": self.fall_max_s, "pureOnly": self.pure_only}


# ── the floors ──────────────────────────────────────────────────────────────

def dataset_stem(npy_path, source_file):
    """The name Settings › Datasets keys a dataset by: the channel directory's name."""
    d = os.path.basename(os.path.dirname(str(npy_path or "").replace("\\", "/")))
    return d or str(source_file).rsplit(".", 1)[0]


def dataset_floors(conn) -> dict:
    """`{source_file: {"floor_mv", "set", "stem", "from"}}` for every recorded dataset."""
    from Working.registration.settings import get_settings
    saved = get_settings(conn, FLOOR_PAGE)
    out = {}
    for sf, npy in conn.execute("SELECT source_file, MIN(npy_path) FROM recordings GROUP BY source_file"):
        stem = dataset_stem(npy, sf)
        v = _num(saved.get(FLOOR_KEY.format(stem=stem)))
        ok = v is not None and v > 0
        out[str(sf)] = {"floor_mv": v if ok else DEFAULT_FLOOR_MV, "set": ok, "stem": stem,
                        "from": ("Settings › Datasets" if ok else f"default {DEFAULT_FLOOR_MV:g} mV (empty in Settings › Datasets)")}
    return out


# ── per member ──────────────────────────────────────────────────────────────

def _entries(conn, entry_ids):
    out = {}
    ids = sorted({int(e) for e in entry_ids if e is not None})
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        for r in conn.execute(f"SELECT id, content_hash, source_store FROM motif_entry WHERE id IN "
                              f"({','.join('?' * len(part))})", part):
            out[int(r[0])] = (r[1], r[2])
    return out


def member_measures(conn, members) -> dict:
    """`{member_id: {...}}` — what the view needs of each member.

    ``members`` are mappings with ``member_id``, ``entry_id`` and ``recording_id``.
    Features are read by the ENTRY's content hash: that is the hash the backfill
    measured (``motif_entry.content_hash``, the store snippet's)."""
    members = list(members)
    floors = dataset_floors(conn)
    recs = {int(r[0]): (str(r[1])) for r in conn.execute("SELECT id, source_file FROM recordings")}
    entries = _entries(conn, [m.get("entry_id") for m in members])
    hashes = sorted({h for h, _ in entries.values() if h})
    feats = F.read_features(conn, hashes) if hashes else {}
    det = F.DETECTOR_PREFIX
    out = {}
    for m in members:
        mid = int(m["member_id"])
        digest, store = entries.get(int(m["entry_id"])) if m.get("entry_id") is not None and \
            int(m["entry_id"]) in entries else (None, None)
        f = feats.get(digest, {}) if digest else {}
        dataset = recs.get(int(m.get("recording_id") or 0))
        fl = floors.get(dataset, {"floor_mv": DEFAULT_FLOOR_MV, "set": False, "from": "default"})
        depth, source = _num(f.get(det + DEPTH_FEATURE)), DEPTH_DETECTOR
        if depth is None:
            depth, source = _num(f.get(SHAPE_DEPTH_FEATURE)), DEPTH_SHAPE
        if depth is None:
            source, status = None, UNMEASURED
        else:
            status = SUB_FLOOR if abs(depth) < fl["floor_mv"] else ABOVE
        pure = _num(f.get(det + "is_pure"))
        band = _num(f.get(det + "scale_band"))
        out[mid] = {
            "depth_mv": depth, "depth_source": source, "floor_mv": fl["floor_mv"], "floor_set": fl["set"],
            "status": status, "dataset": dataset, "store": store or "not imported from a store",
            "fall_duration_s": _num(f.get(det + "fall_duration_s")),
            "is_pure": None if pure is None else bool(pure >= 0.5),
            "scale_band": None if band is None else int(band),
            "scale_band_label": (F.scale_band_label(f.get(det + F.SCALE_BAND_RANGE[0]), f.get(det + F.SCALE_BAND_RANGE[1]))
                                 if band is not None else None),
        }
    return out


# ── the view ────────────────────────────────────────────────────────────────

def _bump(d, key, field):
    slot = d.setdefault(key, {"n": 0, SUB_FLOOR: 0, UNMEASURED: 0})
    slot["n"] += 1
    if field:
        slot[field] += 1


def filter_members(conn, members, view: ViewFilter | None = None, *, families=None, measures=None) -> dict:
    """Which members the view shows, and everything it hid, counted.

    Returns ``{"kept": set(member_id), "measures": {...}, "report": {...}}``. The
    report counts the floor per import store and per dataset whether or not the
    floor is on (so *show sub-floor (n)* can say n), the members each filter hid
    and the ones it could not judge, and — given ``families`` (`{label: [member
    ids]}`) — the families every one of whose members is under the floor."""
    view = view or ViewFilter()
    members = list(members)
    measures = measures if measures is not None else member_measures(conn, members)
    by_store, by_dataset = {}, {}
    kept = set()
    fall = {"hidden": 0, "unmeasured": 0}
    pure = {"hidden": 0, "unmeasured": 0}
    n_sub = n_unmeasured = 0
    for m in members:
        mid = int(m["member_id"])
        x = measures[mid]
        field = SUB_FLOOR if x["status"] == SUB_FLOOR else (UNMEASURED if x["status"] == UNMEASURED else None)
        _bump(by_store, x["store"], field)
        _bump(by_dataset, x["dataset"] or "unknown", field)
        n_sub += x["status"] == SUB_FLOOR
        n_unmeasured += x["status"] == UNMEASURED
        show = not (view.floor and x["status"] == SUB_FLOOR)
        if view.has_fall:
            d = x["fall_duration_s"]
            if d is None:
                fall["unmeasured"] += 1
            elif (view.fall_min_s is not None and d < view.fall_min_s) or (view.fall_max_s is not None and d > view.fall_max_s):
                fall["hidden"] += show
                show = False
        if view.pure_only:
            if x["is_pure"] is None:
                pure["unmeasured"] += 1
            elif not x["is_pure"]:
                pure["hidden"] += show
                show = False
        if show:
            kept.add(mid)
    all_sub = []
    for label, ids in sorted((families or {}).items()):
        ids = [int(i) for i in ids if int(i) in measures]
        if ids and view.floor and all(measures[i]["status"] == SUB_FLOOR for i in ids):
            all_sub.append(label)
    floors = dataset_floors(conn)
    report = {
        "view": view.as_dict(), "rule": f"{view.describe()} — {FLOOR_RULE}",
        "floor": {"on": view.floor, "sub_floor": n_sub, "by_store": by_store, "by_dataset": by_dataset,
                  "floors": {k: {"floorMv": v["floor_mv"], "from": v["from"]} for k, v in floors.items()
                             if k in by_dataset}},
        "unmeasured": n_unmeasured, "fall": fall, "pure": pure,
        "n": len(members), "shown": len(kept),
        "families_all_sub_floor": all_sub,
    }
    return {"kept": kept, "measures": measures, "report": report}
