"""
verdicts.py
===========
A Library member's human verdict (fixup-AE item 4, L7), through THE one
resolver — `Working/discovery/divergence.py::resolve_spans`, in its order: a
verdict given in Review on the member's detection, then the event-shaped row
it matches (§4.6), then the reviewed windows it falls in (Settings ›
Analysis defaults' containment mode).

This replaces matching a member to an annotation by exact span equality,
which matched 0.0 % on every family: no human row shares a span endpoint for
endpoint with a Library member.

A member's detection is the entry's `detection_id` or any of the member's
revisions' — whichever a Review verdict was given on.

Rule 5 in the reading direction: this reads the human tables (annotations,
adjudications) and writes nothing.
"""

from __future__ import annotations

from Working.discovery import divergence as dv

UNJUDGED = "unjudged"


def rule_text(conn) -> str:
    mode = dv.containment_from_settings(conn)
    return ("judged = a human verdict resolved by the divergence rules, in order: a verdict given in Review on the "
            "member's detection; else the event-shaped row it matches (§4.6, reciprocal IoU); else the reviewed "
            f"windows it falls in (containment mode: {mode} — "
            + ("its centre" if mode == "centre" else "wholly inside") + "; every one must agree). "
            "Not exact span equality, which matched none.")


def _detections_of(conn, members):
    """member id -> a detection id a Review verdict could have been given on."""
    ids = [int(m["member_id"]) for m in members]
    out = {}
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        marks = ",".join("?" * len(part))
        for r in conn.execute(f"SELECT mm.id, me.detection_id FROM motif_member mm JOIN motif_entry me "
                              f"ON me.id = mm.entry_id WHERE me.detection_id IS NOT NULL AND mm.id IN ({marks})", part):
            out.setdefault(int(r[0]), int(r[1]))
        # a later revision's detection is the one a reviewer most likely saw
        for r in conn.execute(f"SELECT member_id, detection_id FROM motif_member_revision WHERE detection_id IS NOT "
                              f"NULL AND member_id IN ({marks}) ORDER BY revision", part):
            out[int(r[0])] = int(r[1])
    return out


def member_verdicts(conn, members) -> dict:
    """`{member_id: {"side", "verdict", "by", "why", "judged"}}` for members
    carrying ``member_id``, ``recording_id``, ``start_idx`` and ``end_idx``."""
    members = [m for m in members if m.get("recording_id") is not None]
    dets = _detections_of(conn, members)
    by_rec = {}
    for m in members:
        by_rec.setdefault(int(m["recording_id"]), []).append(m)
    out = {}
    for rec, ms in by_rec.items():
        got = dv.resolve_spans(conn, rec, [(int(m["start_idx"]), int(m["end_idx"])) for m in ms],
                               detection_ids=[dets.get(int(m["member_id"])) for m in ms])
        for m, g in zip(ms, got):
            judged = g["side"] is not None
            out[int(m["member_id"])] = {"side": g["side"], "verdict": (g["verdict"] if judged else UNJUDGED),
                                        "by": g["by"], "why": g["why"], "judged": judged}
    return out


def accepted(verdicts) -> set:
    """The members a person accepted: resolved to *human yes* (interesting or seed)."""
    return {mid for mid, v in verdicts.items() if v["side"] == "yes"}
