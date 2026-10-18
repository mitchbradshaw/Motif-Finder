"""
sequences.py
============
Sequences built from adjacent Library members (prompt `sequences`, the
researcher's grilling of 2026-10-18).

In plain words: a Library member is one motif that carries a family label
(F-01, F-02, …). Walk along one channel in time; when one member ends and the
next starts soon after, they belong to one *sequence*, which reads as a chain
of labels — F-01 F-02 F-01 — the way a spike train reads as a run of spikes.

What was decided, and is the contract here
------------------------------------------
* **A sequence is one channel's ordered run of MEMBERS** (motifs with a family
  in the motif grouping). A detection with no family does not join, and does
  not bridge two members either. Cross-channel propagation is another question.
* **The join rule** (`RULES`):
  - ``fixed`` — two neighbours join when the gap from the end of the first to
    the start of the second is at most ``gap_s + tol_frac x the shorter
    member's length``. The default is 0 s with a 10 % tolerance, because
    members rarely touch to the sample. Overlapping members (a negative gap)
    join.
  - ``adamatzky`` and ``logisi`` — the two adaptive rules of
    `Working.interrogation.trains.find_trains`, handed the members' ONSET times
    (that module's own input), so a sequence here is exactly a train there.
  Minimum two elements (`min_len`), no maximum.
* **Same sequence = same labels in the same order** (`label_key`), whatever the
  gaps and durations. A near-match is its own family; `nearest_family` names
  the closest other one by edit distance over labels.
* **Nothing is stored by joining.** `keep_sequences` writes `sequences` rows
  the importers' way (`importers.sequences.insert_sequence`), with the member
  refs in order; identity = recording + ordered member ids, so keeping again is
  a no-op.

Gaps, two of them
-----------------
`Sequence.gaps_s` is end-to-start (the silence between elements — what the
rule tests and what the family page draws). `sequence_members.gap_before` keeps
the schema's own meaning, onset-to-onset seconds, so a reader of that column
gets the same quantity whichever importer wrote the row; `read_sequences`
recomputes end-to-start from the stored spans.

Which labels
------------
A member's label is its `family_label` in one saved motif grouping (the newest
unless `grouping_id` is given), read from `grouping_assignments` with
`family_id IS NOT NULL` — the same read `webui/server/library.py
_compositions` uses for a sequence's composition, so a kept sequence and the
atlas name its elements alike. Hand edits are not applied (neither does that
read).

Nothing here imports a UI library (CLAUDE.md rule 1). Pure Python + numpy.
"""

from __future__ import annotations

import datetime
import json
import math
from dataclasses import dataclass, field

import numpy as np

from Working.interrogation.trains import find_trains
from Working.library.importers.sequences import _sequence_hash, insert_sequence

#: The join rules the control offers, the fixed one first (the default).
RULES = ("fixed", "adamatzky", "logisi")
DEFAULT_RULE = "fixed"
DEFAULT_GAP_S = 0.0
DEFAULT_TOL_FRAC = 0.10
MIN_LEN = 2

#: `sequences.source_kind` for every row `keep_sequences` writes.
SOURCE_KIND = "library_join"
#: A join is computed by a rule from members, not drawn by a person: a machine
#: claim, as the detector CSV's sequences are. (`human` is for a sequence a
#: person drew in `annotations`.)
ORIGIN = "machine"

#: Joins labels into a family identity. A dot keeps the id URL-safe (a `>` is
#: percent-encoded in a hash route and would no longer match), and no family
#: label the grouping engine writes contains one.
KEY_SEP = "."
#: How a family is NAMED on the page: its label chain.
NAME_SEP = " → "

#: The method a label-chain sequence grouping is saved under.
LABEL_CHAIN_METHOD = "label-chain"
LABEL_CHAIN_BASIS = "label-chain"


@dataclass(frozen=True)
class Element:
    """One member, as an element of a sequence."""
    member_id: int
    start_idx: int
    end_idx: int
    label: str


@dataclass(frozen=True)
class Sequence:
    """An ordered run of members on one channel."""
    recording_id: int
    fs: float
    elements: tuple = ()
    #: end-to-start seconds between consecutive elements; len(elements) - 1
    gaps_s: tuple = ()
    sequence_id: int | None = field(default=None, compare=False)

    def __len__(self):
        return len(self.elements)

    @property
    def labels(self) -> tuple:
        return tuple(e.label for e in self.elements)

    @property
    def member_ids(self) -> tuple:
        return tuple(e.member_id for e in self.elements)

    @property
    def start_idx(self) -> int:
        return int(self.elements[0].start_idx)

    @property
    def end_idx(self) -> int:
        return int(max(e.end_idx for e in self.elements))

    @property
    def identity(self) -> str:
        """`sequences.sequence_key`: recording + ordered member refs."""
        return f"join:r{int(self.recording_id)}:" + "-".join(str(int(m)) for m in self.member_ids)

    def to_dict(self) -> dict:
        fs = self.fs or 1.0
        return {
            "recording_id": int(self.recording_id), "key": label_key(self),
            "labels": list(self.labels), "member_ids": [int(m) for m in self.member_ids],
            "start_s": self.start_idx / fs, "end_s": self.end_idx / fs,
            "gaps_s": [float(g) for g in self.gaps_s],
        }


# ── identity ────────────────────────────────────────────────────────────────

def _clean(label) -> str:
    return str(label).replace(KEY_SEP, "_")


def label_key(seq_or_labels) -> str:
    """The family identity: the labels in order. Order-sensitive on purpose —
    F-01 then F-02 is not F-02 then F-01."""
    labels = seq_or_labels.labels if isinstance(seq_or_labels, Sequence) else seq_or_labels
    return KEY_SEP.join(_clean(x) for x in labels)


def key_labels(key: str) -> list:
    return [x for x in str(key).split(KEY_SEP) if x]


def family_name(key: str) -> str:
    return NAME_SEP.join(key_labels(key))


def edit_distance(a, b) -> int:
    """Levenshtein distance between two label lists (insert, delete, substitute
    one element each cost 1)."""
    a, b = list(a), list(b)
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, start=1):
        cur = [i]
        for j, y in enumerate(b, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def nearest_family(key: str, keys) -> tuple | None:
    """`(other_key, distance)` — the closest OTHER family by edit distance over
    labels, ties broken by key; None when there is no other family."""
    mine = key_labels(key)
    best = None
    for other in sorted(set(keys)):
        if other == key:
            continue
        d = edit_distance(mine, key_labels(other))
        if best is None or d < best[1]:
            best = (other, d)
    return best


# ── reading members ─────────────────────────────────────────────────────────

def motif_grouping_id(conn, grouping_id=None) -> int | None:
    """The motif grouping whose labels name the members: the one given, else
    the newest of unit `single_motifs` (what the Library pages default to)."""
    if grouping_id is not None:
        return int(grouping_id)
    row = conn.execute(
        "SELECT id FROM groupings WHERE unit = 'single_motifs' ORDER BY id DESC LIMIT 1").fetchone()
    return int(row[0]) if row is not None else None


def _fs(conn, recording_id) -> float:
    row = conn.execute("SELECT fs FROM recordings WHERE id = ?", (int(recording_id),)).fetchone()
    if row is None:
        raise ValueError(f"no recording {recording_id}")
    fs = float(row[0] or 0.0)
    if not math.isfinite(fs) or fs <= 0:
        raise ValueError(f"recording {recording_id} has no usable sampling rate ({row[0]!r})")
    return fs


def labelled_members(conn, recording_id, grouping_id=None) -> list:
    """The recording's members that carry a family label, ordered by start
    (then end, then id). Two members on exactly the same span are one element:
    the lower id is kept, so a span is never joined to itself."""
    gid = motif_grouping_id(conn, grouping_id)
    if gid is None:
        return []
    rows = conn.execute(
        """SELECT mm.id AS member_id, mm.start_idx AS start_idx, mm.end_idx AS end_idx,
                  ga.family_label AS label
             FROM motif_member mm
             JOIN grouping_assignments ga
               ON ga.member_ref = mm.id AND ga.unit = 'single_motifs' AND ga.grouping_id = ?
            WHERE mm.recording_id = ? AND ga.family_id IS NOT NULL AND ga.family_label IS NOT NULL
            ORDER BY mm.start_idx, mm.end_idx, mm.id""",
        (gid, int(recording_id))).fetchall()
    out, seen = [], set()
    for r in rows:
        span = (int(r["start_idx"]), int(r["end_idx"]))
        if span in seen or span[1] <= span[0]:
            continue
        seen.add(span)
        out.append(Element(int(r["member_id"]), span[0], span[1], str(r["label"])))
    return out


def member_counts(conn, grouping_id=None) -> dict:
    """`recording_id -> labelled members on it`, for the recording picker."""
    gid = motif_grouping_id(conn, grouping_id)
    if gid is None:
        return {}
    return {int(r[0]): int(r[1]) for r in conn.execute(
        """SELECT mm.recording_id, COUNT(DISTINCT mm.start_idx || ':' || mm.end_idx)
             FROM motif_member mm
             JOIN grouping_assignments ga
               ON ga.member_ref = mm.id AND ga.unit = 'single_motifs' AND ga.grouping_id = ?
            WHERE ga.family_id IS NOT NULL AND ga.family_label IS NOT NULL
            GROUP BY mm.recording_id""", (gid,))}


# ── joining ─────────────────────────────────────────────────────────────────

def _gaps(elements, fs) -> tuple:
    return tuple(float((b.start_idx - a.end_idx) / fs) for a, b in zip(elements, elements[1:]))


def _check(rule, gap_s, tol_frac, min_len):
    if rule not in RULES:
        raise ValueError(f"unknown join rule {rule!r}; choose one of {list(RULES)}")
    for name, v in (("gap_s", gap_s), ("tol_frac", tol_frac)):
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"{name} must be a number, got {v!r}") from None
        if not math.isfinite(f) or f < 0:
            raise ValueError(f"{name} must be a finite number >= 0, got {v!r}")
    if int(min_len) < 2:
        raise ValueError(f"a sequence has at least two elements; min_len {min_len!r} is below 2")


def runs_fixed(elements, fs, gap_s=DEFAULT_GAP_S, tol_frac=DEFAULT_TOL_FRAC) -> list:
    """Index runs `[(first, last), …]` under the fixed rule."""
    runs, first = [], 0
    for i in range(1, len(elements)):
        a, b = elements[i - 1], elements[i]
        shorter = min(a.end_idx - a.start_idx, b.end_idx - b.start_idx) / fs
        limit = float(gap_s) + float(tol_frac) * shorter
        if (b.start_idx - a.end_idx) / fs > limit + 1e-9:
            runs.append((first, i - 1))
            first = i
    if elements:
        runs.append((first, len(elements) - 1))
    return runs


def runs_adaptive(elements, fs, rule, min_len=MIN_LEN) -> list:
    """Index runs under `find_trains(rule)` over the members' onsets. Trains
    are contiguous runs of the time-sorted events there, and `elements` is
    already sorted by onset, so a train is a run here."""
    if not elements:
        return []
    onsets = np.asarray([e.start_idx for e in elements], dtype=float) / fs
    tid = find_trains(onsets, rule, min_events=int(min_len))["train_id"]
    runs, start = [], None
    for i, t in enumerate(tid):
        if start is not None and (t < 0 or t != tid[start]):
            runs.append((start, i - 1))
            start = None
        if t >= 0 and start is None:
            start = i
    if start is not None:
        runs.append((start, len(elements) - 1))
    return runs


def join_members(conn, recording_id, rule=DEFAULT_RULE, gap_s=DEFAULT_GAP_S, tol_frac=DEFAULT_TOL_FRAC,
                 min_len=MIN_LEN, *, grouping_id=None) -> list:
    """The sequences one recording's members make under `rule`, in time order.
    Deterministic; writes nothing."""
    _check(rule, gap_s, tol_frac, min_len)
    fs = _fs(conn, recording_id)
    elements = labelled_members(conn, recording_id, grouping_id)
    runs = (runs_fixed(elements, fs, gap_s, tol_frac) if rule == "fixed"
            else runs_adaptive(elements, fs, rule, min_len))
    out = []
    for a, b in runs:
        els = tuple(elements[a:b + 1])
        if len(els) >= int(min_len):
            out.append(Sequence(int(recording_id), fs, els, _gaps(els, fs)))
    return out


# ── keeping ─────────────────────────────────────────────────────────────────

def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def keep_sequences(conn, seqs, provenance) -> list:
    """Write `seqs` as `sequences` rows with their member refs in order, and
    commit. Returns `[{id, sequence_key, key, created}]` in the order given;
    a sequence already kept (same recording, same ordered members) is
    `created: False` and untouched.

    `provenance` (rule, numbers, motif grouping, …) is stored as JSON in
    `source_store` with the date; the label key goes in `source_ref`."""
    created_at = _now()
    note = json.dumps({**(provenance or {}), "date": created_at}, sort_keys=True)
    out = []
    for s in seqs:
        if len(s) < 2:
            raise ValueError("a sequence has at least two elements")
        ident = s.identity
        row = conn.execute("SELECT id FROM sequences WHERE sequence_key = ? AND origin = ?",
                           (ident, ORIGIN)).fetchone()
        if row is not None:
            out.append({"id": int(row[0]), "sequence_key": ident, "key": label_key(s), "created": False})
            continue
        channel = conn.execute("SELECT channel FROM recordings WHERE id = ?", (int(s.recording_id),)).fetchone()
        fs = s.fs or 1.0
        onset_gaps = [None] + [float((b.start_idx - a.start_idx) / fs)
                               for a, b in zip(s.elements, s.elements[1:])]
        sid = insert_sequence(
            conn,
            dict(sequence_key=ident, origin=ORIGIN, recording_id=int(s.recording_id),
                 channel=int(channel[0]) if channel is not None else None,
                 start_idx=s.start_idx, end_idx=s.end_idx, n_events=len(s), needs_extraction=0,
                 source_kind=SOURCE_KIND, source_store=note, source_ref=label_key(s),
                 content_hash=_sequence_hash(onset_gaps), created_at=created_at),
            [dict(member_id=e.member_id, start_idx=e.start_idx, end_idx=e.end_idx, gap_before=g)
             for e, g in zip(s.elements, onset_gaps)],
        )
        out.append({"id": int(sid), "sequence_key": ident, "key": label_key(s), "created": True})
    conn.commit()
    return out


def read_sequences(conn, sequence_ids, *, grouping_id=None) -> list:
    """Stored sequences as `Sequence`s, in the order asked, their elements
    labelled under the motif grouping (`labelled_members`' rule) — `'?'` for an
    element whose member has no family there (or no member row). A sequence id
    that is not there, or has no members, is skipped."""
    ids = [int(i) for i in sequence_ids]
    if not ids:
        return []
    gid = motif_grouping_id(conn, grouping_id)
    marks = ",".join("?" * len(ids))
    heads = {int(r["id"]): r for r in conn.execute(
        f"SELECT s.id, s.recording_id, r.fs FROM sequences s LEFT JOIN recordings r ON r.id = s.recording_id "
        f"WHERE s.id IN ({marks})", ids)}
    labels = {}
    if gid is not None:
        labels = {int(r[0]): str(r[1]) for r in conn.execute(
            f"SELECT sm.member_id, ga.family_label FROM sequence_members sm JOIN grouping_assignments ga "
            f"ON ga.member_ref = sm.member_id AND ga.unit = 'single_motifs' AND ga.grouping_id = ? "
            f"AND ga.family_id IS NOT NULL WHERE sm.sequence_id IN ({marks})", [gid] + ids)}
    members = {}
    for r in conn.execute(
            f"SELECT sequence_id, member_id, start_idx, end_idx FROM sequence_members "
            f"WHERE sequence_id IN ({marks}) ORDER BY sequence_id, position", ids):
        members.setdefault(int(r["sequence_id"]), []).append(r)
    out = []
    for sid in ids:
        head, ms = heads.get(sid), members.get(sid)
        if head is None or not ms or head["recording_id"] is None:
            continue
        fs = float(head["fs"] or 1.0)
        els = tuple(Element(int(m["member_id"] or 0), int(m["start_idx"]), int(m["end_idx"]),
                            labels.get(int(m["member_id"] or 0), "?")) for m in ms)
        out.append(Sequence(int(head["recording_id"]), fs, els, _gaps(els, fs), sequence_id=sid))
    return out


def label_chain_assignments(conn) -> list:
    """One assignment per kept (`library_join`) sequence for a label-chain
    sequence grouping: `family_label` = its label key, `family_id` numbered
    1.. over the sorted keys, the lowest sequence id of each family its
    medoid. The caller writes them (a grouping is a human-door table)."""
    rows = conn.execute(
        "SELECT id, source_ref, content_hash FROM sequences WHERE source_kind = ? ORDER BY id",
        (SOURCE_KIND,)).fetchall()
    keys = sorted({str(r["source_ref"]) for r in rows if r["source_ref"]})
    number = {k: i + 1 for i, k in enumerate(keys)}
    seen, out = set(), []
    for r in rows:
        k = str(r["source_ref"] or "")
        if not k:
            continue
        out.append({"sequence_id": int(r["id"]), "family_label": k, "family_id": number[k],
                    "is_medoid": 0 if k in seen else 1, "content_hash": r["content_hash"]})
        seen.add(k)
    return out
