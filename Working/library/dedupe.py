"""
dedupe.py
=========
`docs/LIBRARY_STORAGE.md` §2.4 — deciding what an arriving span already is.

| case | test | what happens |
|---|---|---|
| exact duplicate | same `content_hash` | resolves onto the existing entry |
| near-duplicate | same recording **and** channel, IoU >= `IOU_THRESHOLD`, onset within `ONSET_TOLERANCE_FRACTION` x the candidate's own duration | **flagged for review, never merged** |
| different shape | neither | a new entry |

Two things this module will not do, both on purpose.

**It never merges and never deletes.** A near-duplicate is a flag carrying its
evidence, handed to a person. Two spans that overlap heavily may be one event
detected twice or two real events in quick succession, and only the researcher
can say which; silently collapsing them would lose a finding and leave no trace
that anything was lost.

**A shape recurring on another channel is not a duplicate — it is the point.**
Cross-channel recurrence is what the library exists to make visible (and what
`Working.cross_channel` then classifies as artifact, propagation or independent
recurrence). So a different recording *or* a different channel is never a
near-duplicate here, however well the spans line up.

The onset term scales with the **candidate's** own duration, per spec §4.6: a
four-hour drop may start twenty minutes out and be the same event; a
forty-second spike may not start ten seconds out. The half of the rule an
implementation loses by accident is this one, which is why it is a named
function with its own tests.

Both numbers are recorded on every flag, because a flag raised under one rule
compared against another is how an unfalsifiable count gets made (§4.6: "the
rule is recorded on the run").

The interval arithmetic and the two-halves judgement are imported from
`Working.database.similarity` and `Working.discovery.matching` rather than
written a second time — the project has one definition of "these two spans are
the same event", and a second copy here would be a second definition that
drifts.
"""

from Working.database.similarity import interval_iou
from Working.discovery.matching import (
    DEFAULT_IOU,
    DEFAULT_ONSET_FRACTION,
    match_quality,
)

# §2.4's two numbers, named as the standard names them. They are bound to
# `Working.discovery.matching`'s defaults rather than re-typed: the Library's
# near-duplicate rule and Discovery's matching rule are the same spec §4.6
# rule, and two literals that happen to agree today drift apart tomorrow.
IOU_THRESHOLD = DEFAULT_IOU
ONSET_TOLERANCE_FRACTION = DEFAULT_ONSET_FRACTION

#: The three answers `classify` gives.
EXACT = "exact"
NEAR = "near"
NEW = "new"


def span_iou(a_start, a_end, b_start, b_end):
    """Reciprocal overlap of two `[start, end)` sample spans.

    0.0 for spans that do not overlap, touch end-to-start, or are degenerate.
    """
    return interval_iou(int(a_start), int(a_end), int(b_start), int(b_end))


def onset_agrees(a_start, a_end, b_start, b_end, *,
                 fraction=ONSET_TOLERANCE_FRACTION):
    """Do two spans start close enough, measured against **a**'s duration?

    `a` is the candidate — the span being judged — and it owns the scale
    (spec §4.6). Swapping the arguments changes the tolerance, which is why
    both spans are passed whole rather than just their onsets.
    """
    duration = max(0, int(a_end) - int(a_start))
    return abs(int(a_start) - int(b_start)) <= fraction * duration


def _coords(span):
    """The four coordinates of a span, from a dict, a row or a 4-tuple.

    Callers arrive from three directions — a `sqlite3.Row` off `motif_member`,
    a dict built by an importer, and a bare tuple in a test — and none of them
    should have to reshape their span to ask a question about it.
    """
    if isinstance(span, (tuple, list)):
        recording_id, channel, start_idx, end_idx = span
    else:
        recording_id = span["recording_id"]
        channel = span["channel"]
        start_idx = span["start_idx"]
        end_idx = span["end_idx"]
    return (int(recording_id),
            None if channel is None else int(channel),
            int(start_idx), int(end_idx))


def is_near_duplicate(a, b, *, iou_threshold=IOU_THRESHOLD,
                      fraction=ONSET_TOLERANCE_FRACTION):
    """Is candidate span `a` a near-duplicate of incumbent span `b`?

    `a` and `b` carry `recording_id`, `channel`, `start_idx`, `end_idx` (as a
    dict, a database row, or a 4-tuple in that order).

    A different recording or a different channel is **never** a near-duplicate,
    checked before any arithmetic: the same shape in another place is another
    member of the same entry, which is what the library is for.
    """
    a_rec, a_ch, a_start, a_end = _coords(a)
    b_rec, b_ch, b_start, b_end = _coords(b)
    if a_rec != b_rec or a_ch != b_ch:
        return False

    quality = match_quality((a_start, a_end), (b_start, b_end),
                            iou_threshold=iou_threshold, onset_fraction=fraction)
    return bool(quality["ok"])


def find_duplicates(conn, content_hash):
    """The id of the entry already holding `content_hash`, or None.

    Same hash means the same `motif_entry` and never a second one (§2.1), so
    this is the first question an importer asks. `LIMIT 1` with the lowest id
    is deliberate: if a pre-hash entry ever duplicated a shape, the oldest row
    is the one that keeps its members.
    """
    if not content_hash:
        return None
    row = conn.execute(
        "SELECT id FROM motif_entry WHERE content_hash = ? ORDER BY id LIMIT 1",
        (content_hash,),
    ).fetchone()
    return row["id"] if row is not None else None


def find_near_duplicates(conn, *, recording_id, channel, start_idx, end_idx,
                         exclude_entry_id=None, exclude_member_id=None,
                         iou_threshold=IOU_THRESHOLD,
                         fraction=ONSET_TOLERANCE_FRACTION):
    """Existing members of the same recording and channel that this span
    nearly duplicates.

    Returns a list of flag dicts, each carrying the other row's ids, the
    measured IoU and onset delta, **and the two thresholds it was judged
    under** — so a flag stored today is still readable after the defaults are
    changed (§4.6 makes changing them a versioned act).

    `exclude_member_id` keeps a member re-examined against the catalogue from
    flagging itself; `exclude_entry_id` excludes a whole entry, which is what
    a re-import of one entry's members wants.

    Nothing is written. The caller decides what a flag means.
    """
    sql = ["SELECT id, entry_id, recording_id, channel, start_idx, end_idx, "
           "content_hash FROM motif_member WHERE recording_id = ?"]
    params = [int(recording_id)]
    if channel is None:
        sql.append("AND channel IS NULL")
    else:
        sql.append("AND (channel = ? OR channel IS NULL)")
        params.append(int(channel))
    if exclude_entry_id is not None:
        sql.append("AND entry_id != ?")
        params.append(int(exclude_entry_id))
    if exclude_member_id is not None:
        sql.append("AND id != ?")
        params.append(int(exclude_member_id))

    candidate = {"recording_id": recording_id, "channel": channel,
                 "start_idx": start_idx, "end_idx": end_idx}

    flags = []
    for row in conn.execute(" ".join(sql), params).fetchall():
        # A member row written before `channel` was added carries NULL there.
        # Treat it as this candidate's channel rather than skipping it: its
        # recording row already fixes one channel, so a NULL is missing
        # denormalisation, not a different channel.
        other = {"recording_id": row["recording_id"],
                 "channel": channel if row["channel"] is None else row["channel"],
                 "start_idx": row["start_idx"], "end_idx": row["end_idx"]}
        if not is_near_duplicate(candidate, other,
                                 iou_threshold=iou_threshold, fraction=fraction):
            continue
        flags.append({
            "member_id": row["id"],
            "entry_id": row["entry_id"],
            "content_hash": row["content_hash"],
            "start_idx": row["start_idx"],
            "end_idx": row["end_idx"],
            "iou": span_iou(start_idx, end_idx, row["start_idx"], row["end_idx"]),
            "onset_delta": abs(int(start_idx) - int(row["start_idx"])),
            "onset_tolerance": fraction * max(0, int(end_idx) - int(start_idx)),
            "iou_threshold": iou_threshold,
            "onset_tolerance_fraction": fraction,
        })
    flags.sort(key=lambda f: (-f["iou"], f["member_id"]))
    return flags


def classify(conn, *, content_hash, recording_id, channel, start_idx, end_idx,
             exclude_entry_id=None, exclude_member_id=None,
             iou_threshold=IOU_THRESHOLD, fraction=ONSET_TOLERANCE_FRACTION):
    """The one call an importer makes before writing a span (§2.4).

    Returns

        {"verdict": 'exact' | 'near' | 'new',
         "entry_id": int or None,      # set on 'exact' — the entry to resolve onto
         "flags": [ ... ],             # the near-duplicate evidence, possibly empty
         "content_hash": str,
         "rule": {"iou_threshold": ..., "onset_tolerance_fraction": ...}}

    `exact` wins over `near`: an identical shape is the same entry however its
    span overlaps its neighbours. The flags are still gathered and returned in
    that case, because "this arrived twice AND overlaps something else" is
    exactly the state a reviewer wants to see, not a fact to be dropped because
    the first question already answered.

    Reads only. A verdict is not a write.
    """
    entry_id = find_duplicates(conn, content_hash)
    flags = find_near_duplicates(
        conn, recording_id=recording_id, channel=channel,
        start_idx=start_idx, end_idx=end_idx,
        exclude_entry_id=exclude_entry_id, exclude_member_id=exclude_member_id,
        iou_threshold=iou_threshold, fraction=fraction,
    )
    if entry_id is not None:
        verdict = EXACT
    elif flags:
        verdict = NEAR
    else:
        verdict = NEW
    return {
        "verdict": verdict,
        "entry_id": entry_id,
        "flags": flags,
        "content_hash": content_hash,
        "rule": {"iou_threshold": iou_threshold,
                 "onset_tolerance_fraction": fraction},
    }
