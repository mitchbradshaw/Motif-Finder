"""
family_queue.py
===============
The *Library family* Review queue (fixup-FQ): Library › Family *Send N to
Review as a queue*, wired.

A family of unjudged members is a proposal, not a finding. This queue puts
the family's unjudged members to a person, one at a time, in Review — the
same surface every other verdict is given on — and the Family page counts
the answers.

**Where the verdict lives — `annotations`, over the member's span.** Most
Library members have no detection (imported from a store or a catalogue), and
one found by a run may carry no adjudication at all; a verdict has to land
somewhere the Family page's own resolver reads. That resolver is THE one
(`Working.library.verdicts` → `Working.discovery.divergence.resolve_spans`):
a verdict given in Review on the member's detection, else the event-shaped
human row the member matches by reciprocal IoU, else the reviewed windows it
falls in. A row over exactly the member's span matches at IoU 1 and onset gap
0, so a verdict written here is what the page then counts as judged — the
button's number and the page's are one number, with nothing to keep in step.
Rule 5: nothing here writes `motif_member`, `motif_edge`, `motif_entry` or
`adjudications`.

**The vocabulary stays at five words** (the researcher, 2026-10-05). The
reviewer answers *interesting*, *not_interesting*, *artifact* or *unsure*.
*seed* is not this queue's question: the member is already in the Library.
*unsure* is answered in the queue (the row exists; the member is not asked
again) but the resolver gives it no side, so the Family page still counts the
member unjudged — which is what unsure means.

**One queue per family.** The filters hold the members asked about; a second
send returns the open queue, widened to any member it did not yet hold (a
member added by hand after the first send), rather than opening a second
queue over the same family with a second progress count.

The span-level helpers are `artifact_queue`'s, parameterised on the source:
the two queues differ only in what they ask and the note they leave.

No UI library: `webui/server` calls into this, never the other way round.
"""

import json

from Working.database import queries as _queries
from Working.review.artifact_queue import _members, _review_rows

#: `review_queues.source_kind` for this queue, and its unit.
SOURCE_KIND = "library-family"
UNIT = "member"
#: `annotations.source` on every verdict this queue writes.
REVIEW_SOURCE = "library_review"
#: The five-word vocabulary, minus `seed`: the member is already in the Library.
VERDICT_OPTIONS = ("interesting", "not_interesting", "artifact", "unsure")


def queue_name(family):
    return f"Library · {family} unjudged"


def member_verdicts(conn, member_ids):
    """`{member_id: verdict}` for every member a human has answered through a
    queue of this kind (the verdict belongs to the span, not the queue)."""
    from Working.review.artifact_queue import member_verdicts as _mv
    return _mv(conn, member_ids, REVIEW_SOURCE)


def review_annotation_id(conn, member_id):
    """The annotation a verdict on this member lands on, or None (a new one)."""
    from Working.review.artifact_queue import review_annotation_id as _rid
    return _rid(conn, member_id, REVIEW_SOURCE)


def verdict_note(family, member_id):
    """The note every verdict row carries: where the question came from."""
    where = f"{family} · m-{member_id}" if family else f"m-{member_id}"
    return f"judged in Review from the Library family ({where})"


# ── the queue ───────────────────────────────────────────────────────────────

def open_family_queue(conn, family, grouping=None):
    """The id of the open queue of this kind over `family` (and `grouping`,
    when the queue names one and the caller does), or None."""
    for row in conn.execute(
            "SELECT id, filters_json FROM review_queues WHERE closed_at IS NULL AND source_kind = ? "
            "AND source_ref = ? ORDER BY id DESC", (SOURCE_KIND, str(family))):
        f = json.loads(row["filters_json"] or "{}")
        if grouping is not None and f.get("grouping") not in (None, str(grouping)):
            continue
        return int(row["id"])
    return None


def create_family_queue(conn, *, family, member_ids, grouping=None):
    """*Send N to Review as a queue*: the family's queue, made through
    `create_queue` — or the open one that already IS this family's, widened
    to any of `member_ids` it did not yet hold. Returns the queue id."""
    from Working.review import queues as Q

    ids = sorted({int(m) for m in member_ids})
    found = open_family_queue(conn, family, grouping)
    if found is not None:
        q = Q.get_queue(conn, found)
        have = sorted(int(m) for m in (q["filters"].get("member_ids") or []))
        union = sorted(set(have) | set(ids))
        if union != have:
            filters = dict(q["filters"])
            filters["member_ids"] = union
            conn.execute("UPDATE review_queues SET filters_json = ? WHERE id = ?", (json.dumps(filters), found))
            conn.commit()
        return found
    filters = {"member_ids": ids, "family": family}
    if grouping is not None:
        filters["grouping"] = grouping
    return Q.create_queue(conn, name=queue_name(family), source_kind=SOURCE_KIND, source_ref=family,
                          verdict_options=list(VERDICT_OPTIONS), filters=filters,
                          note=("the family's members that had never been judged when it was sent; a verdict "
                                "lands in annotations over the member's span, which is what the Family page "
                                "counts as judged"))


def resolve_items(conn, q):
    """The queue's items NOW: the members it was sent, each with the verdict
    a human has given — through this queue, or anywhere a human row over the
    span was written (the Family page's resolver), so a verdict given
    elsewhere is not asked for again."""
    from Working.library.verdicts import member_verdicts as _resolved

    ids = sorted({int(m) for m in (q["filters"].get("member_ids") or [])})
    if not ids:
        return []
    members = _members(conn, ids)
    own = _review_rows(conn, members, REVIEW_SOURCE)
    resolved = _resolved(conn, [{"member_id": mid, "recording_id": m["recording_id"],
                                 "start_idx": m["start_idx"], "end_idx": m["end_idx"]}
                                for mid, m in members.items()])
    family = q["filters"].get("family") or q.get("source_ref")
    items = []
    for mid in ids:
        m = members.get(mid)
        if m is None:
            continue                        # a member row that is gone takes no verdict
        key = (int(m["recording_id"]), int(m["start_idx"]), int(m["end_idx"]))
        res = resolved.get(mid) or {}
        if res.get("judged"):
            verdict, by = res["verdict"], res.get("by")
        elif key in own:
            verdict, by = own[key][1], "this queue"      # unsure: answered here, no side
        else:
            verdict, by = None, None
        items.append({
            "target_id": mid, "unit": q["unit"], "member_id": mid,
            "recording_id": key[0], "channel": int(m["channel"]),
            # drawn at the current revision (edit-span); `key` — the member's own span — stays the verdict's
            "start_idx": int(m["shown_start_idx"]), "end_idx": int(m["shown_end_idx"]),
            "judged": verdict is not None, "verdict": verdict, "judged_by": by,
            "family": family, "tags": [],
        })
    return items


def write_member_verdict(conn, queue, member_id, verdict, note=None, tags=None):
    """One human verdict on one member, into `annotations` over its span.
    Re-describes this source's existing row for the span in place, or inserts
    one. Returns `(prior, annotation_id)`; `prior` is `{"inserted": True}` for
    a new row, so undo withdraws it."""
    from Working.database import vocabulary as _vocabulary

    if verdict not in VERDICT_OPTIONS:
        raise ValueError(f"a Library family queue takes {', '.join(VERDICT_OPTIONS)}; got {verdict!r}")
    m = _members(conn, [member_id]).get(int(member_id))
    if m is None:
        raise ValueError(f"no family member with id {member_id}")
    filters = json.loads(queue["filters_json"]) if queue["filters_json"] else {}
    family = filters.get("family") or queue["source_ref"]
    text = verdict_note(family, int(member_id))
    if note:
        text = f"{text} — {note}"
    existing = review_annotation_id(conn, member_id)
    if existing is not None:
        row = _queries.get_annotation(conn, existing)
        prior = {"verdict": row["verdict"], "note": row["note"],
                 "tags": _vocabulary.get_annotation_tags(conn, existing)}
        conn.execute("UPDATE annotations SET verdict = ?, note = ? WHERE id = ?", (verdict, text, existing))
        aid = existing
    else:
        aid = _queries.insert_annotation(conn, int(m["recording_id"]), int(m["start_idx"]), int(m["end_idx"]),
                                         verdict, source=REVIEW_SOURCE, note=text, commit=False)
        prior = {"inserted": True}
    if tags:
        for category, values in tags.items():
            _vocabulary.set_annotation_tags(conn, aid, category, values, commit=False)
    return prior, int(aid)
