"""
queues.py
=========
Review queues: the descriptor store and the live source resolver
(stage-3 wiring prompt 05, PIPELINE_PRD §10.1).

**A queue holds no items of its own.** A row in `review_queues` records what a
queue *is* — its name, which kind of source it points at, which row that
source is, the unit a verdict lands on, which table that verdict writes, and
whether the machine's opinion is hidden (P20 blind) — and nothing about which
items are in it. `queue_items` resolves the source on every call. That is the
whole design: a verdict written anywhere else (Discovery's scoreboard, another
queue, a direct `adjudications` insert) immediately changes what this queue
shows, with nothing to keep in step (04-to-05 §1).

Rule 5 (CLAUDE.md) is carried in `writes_to`, decided ONCE at creation from
the source kind and stored where a person can read it, rather than re-inferred
at each verdict where a wrong inference would silently cross a machine
detection with a human verdict. Detection queues write `adjudications`; span
and sequence queues write `annotations`; window queues write `window_verdicts`
because a window is neither a detection nor a span a person drew.

Three exclusions are structural rather than cosmetic:

* **Superseded runs.** `queue_candidates` has no such filter and its existing
  callers do not want one, so the exclusion lives here, in the resolver: a run
  with `runs.superseded_at` set was *discarded*, and Discovery deliberately
  writes no verdicts when it discards (04-to-05 §2). Its detections stay in
  the table; without this filter they keep arriving in Review after the
  researcher threw them away.
* **The blind score.** A blind queue's items do not carry the machine score at
  all — the key is absent from the payload, not merely unrendered — because a
  number that reaches the browser is one inspector away from the eye it was
  meant to be kept from.
* **The rediscovery.** A detection that is the same event as a span the
  researcher has already judged carries that verdict as `prior_verdict`, and
  is not asked about again unless `include_prior_judged` says to (04-to-05 §3,
  spec §4.7). The rule is `Working.discovery.matching` — reciprocal IoU **and**
  onset agreement scaled to the candidate's own duration, thresholds from
  Settings › Analysis defaults via `rule_from_settings` — and NOT
  `Working.compare`'s `SIMILARITY_IOU_THRESHOLD`, which is overlap-only at
  0.8 and would call a span starting half a duration late the same event. One
  rule holds across Discovery and Review or the two workspaces disagree about
  what "already judged" means.

  **Detection queues only.** An `explore-spans` item *is* a human span, so
  running the rule over it would pair every item with itself and empty the
  queue; a window has no extent to match on.

No UI library, no fastapi: `webui/server/review.py` calls into this, never the
other way round.
"""

import json
import math
from bisect import bisect_left, bisect_right
from datetime import datetime, timezone

from Working.database import queries as _queries
from Working.discovery.matching import match_quality, rule_from_settings
from Working.discovery.spans import absolute_bounds
from Working.review.queue_state import ReviewQueue

#: SQLite's default host-parameter ceiling is 999; stay well under it when
#: expanding an id set into an `IN (...)` list.
_ID_CHUNK = 400

# The six source kinds and what §10.1 says each one implies when the caller
# does not say otherwise: the unit a verdict lands on, the table it writes,
# and whether the machine's score is withheld.
SOURCE_KINDS = (
    "discovery-run",
    "seed-search",
    "explore-spans",
    "training-windows",
    "model-verification",
    "extract-events",
)

_DEFAULTS = {
    "discovery-run":      ("detection", "adjudications", 0),
    "seed-search":        ("detection", "adjudications", 0),
    "explore-spans":      ("human span", "annotations", 0),
    "training-windows":   ("window", "window_verdicts", 1),
    "model-verification": ("window", "window_verdicts", 1),
    "extract-events":     ("sequence", "annotations", 0),
}

_DETECTION_KINDS = ("discovery-run", "seed-search")
_WINDOW_KINDS = ("training-windows", "model-verification")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_dict(row):
    return {k: row[k] for k in row.keys()}


# ── the descriptor store ────────────────────────────────────────────────────

def create_queue(conn, *, name, source_kind, source_ref=None, unit=None,
                 writes_to=None, blind=None, cap=None, verdict_options=None,
                 filters=None, note=None):
    """Record a queue descriptor and return its id.

    `unit`, `writes_to` and `blind` are inferred from `source_kind` per §10.1
    unless given explicitly. `source_ref` is the row the kind keys on — a
    run-group id for a discovery run, a window-set id for a window queue, a
    session id for a seeded search — as TEXT, because the six kinds key on
    different things. `filters` is a dict passed through to the resolver.
    """
    if source_kind not in _DEFAULTS:
        raise ValueError(
            "source_kind must be one of {}, got {!r}".format(
                ", ".join(SOURCE_KINDS), source_kind))
    d_unit, d_writes, d_blind = _DEFAULTS[source_kind]
    # A queue that names a unit or a write target contradicting its own source
    # kind is the rule-5 crossing written down (CLAUDE.md rule 5): "my items
    # are detections and I write `annotations`" is a standing instruction to
    # fabricate human verdicts. These arguments are settable from an HTTP body,
    # so the refusal belongs here, at the moment the queue is made, not at each
    # verdict written through it.
    if unit is not None and unit != d_unit:
        raise ValueError(
            "source_kind {!r} has unit {!r}, not {!r}; a queue whose unit "
            "contradicts its source is not a queue anyone can answer".format(
                source_kind, d_unit, unit))
    if writes_to is not None and writes_to != d_writes:
        # ValueError, not PermissionError: nothing has been written and no
        # door has been forced -- this is a malformed queue being refused at
        # the moment it is described. The PermissionError lives at the write
        # seam in `verdicts._queue_is_itself_the_crossing`, for a queue that
        # reached the table some other way.
        raise ValueError(
            "rule 5 (CLAUDE.md): writes_to={!r} contradicts source_kind "
            "{!r}, which writes {!r}. A queue may not declare a write target "
            "its source kind does not have.".format(
                writes_to, source_kind, d_writes))
    cur = conn.execute(
        """INSERT INTO review_queues
               (name, source_kind, source_ref, unit, writes_to, blind, cap,
                verdict_options, filters_json, created_at, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, source_kind,
         None if source_ref is None else str(source_ref),
         unit or d_unit,
         writes_to or d_writes,
         d_blind if blind is None else int(bool(blind)),
         cap,
         None if verdict_options is None else json.dumps(list(verdict_options)),
         None if filters is None else json.dumps(filters),
         _now(), note),
    )
    conn.commit()
    return cur.lastrowid


def get_queue(conn, queue_id):
    """The descriptor as a dict (with `filters` decoded), or None."""
    row = conn.execute(
        "SELECT * FROM review_queues WHERE id = ?", (queue_id,)).fetchone()
    if row is None:
        return None
    q = _row_to_dict(row)
    q["filters"] = json.loads(q["filters_json"]) if q["filters_json"] else {}
    if q.get("verdict_options"):
        q["verdict_options"] = json.loads(q["verdict_options"])
    return q


def list_queues(conn, *, include_closed=False):
    """Every queue, newest last, each carrying its live total/judged/remaining."""
    sql = "SELECT * FROM review_queues"
    if not include_closed:
        sql += " WHERE closed_at IS NULL"
    sql += " ORDER BY id"
    out = []
    for row in conn.execute(sql).fetchall():
        q = _row_to_dict(row)
        q["filters"] = json.loads(q["filters_json"]) if q["filters_json"] else {}
        q.update(queue_counts(conn, q["id"]))
        out.append(q)
    return out


def close_queue(conn, queue_id):
    """Mark a queue closed. Closed queues leave the header and the list."""
    conn.execute("UPDATE review_queues SET closed_at = ? WHERE id = ?",
                 (_now(), queue_id))
    conn.commit()


# ── the resolver ────────────────────────────────────────────────────────────

def queue_items(conn, queue_id, *, limit=-1, offset=0, include_judged=False,
                include_prior_judged=False, exclude_recording_ids=None):
    """Resolve the queue's source NOW and return its items.

    Unjudged items only unless `include_judged`, and — for a detection queue —
    items the researcher has not already judged under another name unless
    `include_prior_judged`. Each item carries `target_id`, `unit` and
    `judged`; a detection item also carries `prior_verdict` (None when it is
    not a rediscovery) with `prior_annotation_id`, `prior_iou` and
    `prior_onset_gap` behind it. A blind queue's items carry no `score` key at
    all.
    """
    q = get_queue(conn, queue_id)
    if q is None:
        raise ValueError("no such queue: {!r}".format(queue_id))
    items = _resolve(conn, q)
    # The caller may know of recordings that must not be put to anyone — the
    # bridge passes the held-out set (D6). The core is told WHICH recordings,
    # never why: "held out" is an evaluation decision that lives above it.
    if exclude_recording_ids:
        drop = {int(r) for r in exclude_recording_ids}
        items = [it for it in items
                 if it.get("recording_id") is None
                 or int(it["recording_id"]) not in drop]
    if not include_prior_judged:
        items = [it for it in items if it.get("prior_verdict") is None]
    items = _apply_cap(q, items)
    if not include_judged:
        items = [it for it in items if not it["judged"]]
    if offset:
        items = items[offset:]
    if limit is not None and limit >= 0:
        items = items[:limit]
    return items


def queue_counts(conn, queue_id, *, exclude_recording_ids=None):
    """{'total', 'judged', 'remaining'} over the capped, resolved source.

    An item with a prior verdict is outside all three numbers, because it is
    outside the question the queue is putting: `remaining` must equal
    `len(queue_items(...))` and `total` `len(queue_items(...,
    include_judged=True))`, or the progress readout lies about how much is
    left. A caller that wants the rediscoveries back asks `queue_items` for
    them.
    """
    q = get_queue(conn, queue_id)
    if q is None:
        raise ValueError("no such queue: {!r}".format(queue_id))
    items = [it for it in _resolve(conn, q) if it.get("prior_verdict") is None]
    # Counted only if it could be served. A row nobody can be shown is not part
    # of the question the queue is putting, so counting it inflates `total` and
    # "N need you" and breaks total == judged + remaining for every reader.
    if exclude_recording_ids:
        drop = {int(r) for r in exclude_recording_ids}
        items = [it for it in items
                 if it.get("recording_id") is None
                 or int(it["recording_id"]) not in drop]
    items = _apply_cap(q, items)
    judged = sum(1 for it in items if it["judged"])
    return {"total": len(items), "judged": judged,
            "remaining": len(items) - judged}


#: How many recent gestures the pace is taken over. Long enough for the median
#: to mean something, short enough that this morning's pace is not this week's.
PACE_WINDOW = 20


def queue_pace_s(conn, queue_id, *, window=PACE_WINDOW):
    """Median seconds per item over this queue's recent judging, or None.

    The ledger is `review_audit`: its rows for this queue, in the order they
    were written, skipping the ones that were undone and the `undo` gestures
    themselves (undoing is not judging). Each interval between consecutive
    gestures is divided by the number of targets the later gesture wrote, so a
    batch of five taken ten seconds after the previous one counts as two
    seconds an item - which is what the page's "~N s each" claims to be.

    The median, not the mean, because a reviewer who walks away for an hour
    has not become slower; they have stopped. Two gestures are the minimum:
    one is not an interval, and an unmeasured pace says so rather than
    inventing a number.

    `created_at` is ISO to the second, so a pace under a second reads as 0.0.
    That is a real measurement - "faster than this ledger can resolve" - and
    the caller must not mistake it for an absent one.
    """
    rows = conn.execute(
        "SELECT target_ids, created_at FROM review_audit "
        "WHERE queue_id = ? AND undone_at IS NULL AND action <> 'undo' "
        "ORDER BY id", (int(queue_id),)).fetchall()
    if len(rows) < 2:
        return None
    per_item = []
    prev = _parse_ts(rows[0]["created_at"])
    for row in rows[1:]:
        t = _parse_ts(row["created_at"])
        if prev is None or t is None:
            prev = t
            continue
        n = _n_targets(row["target_ids"])
        per_item.append(max(0.0, (t - prev).total_seconds()) / n)
        prev = t
    if not per_item:
        return None
    return round(_median(per_item[-window:]), 2)


def _parse_ts(value):
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _n_targets(value):
    try:
        got = json.loads(value) if value else []
    except (TypeError, ValueError):
        return 1
    return max(1, len(got)) if isinstance(got, list) else 1


def _median(xs):
    xs = sorted(xs)
    mid = len(xs) // 2
    return xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2.0


def header_counts(conn, *, exclude_recording_ids=None):
    """What the header badge shows: unjudged items across every open queue."""
    by_queue = []
    need_you = 0
    for row in conn.execute(
            "SELECT id, name FROM review_queues WHERE closed_at IS NULL "
            "ORDER BY id").fetchall():
        remaining = queue_counts(
            conn, row["id"],
            exclude_recording_ids=exclude_recording_ids)["remaining"]
        need_you += remaining
        by_queue.append({"id": row["id"], "name": row["name"],
                         "remaining": remaining})
    return {"need_you": need_you, "by_queue": by_queue}


# ── internals: one resolver per source kind ─────────────────────────────────

def _resolve(conn, q):
    kind = q["source_kind"]
    if kind in _DETECTION_KINDS:
        items = _resolve_detections(conn, q)
    elif kind in _WINDOW_KINDS:
        items = _resolve_windows(conn, q)
    elif kind == "explore-spans":
        items = _resolve_spans(conn, q)
    elif kind == "extract-events":
        items = _resolve_sequences(conn, q)
    else:                                   # pragma: no cover - CHECKed above
        raise ValueError("unresolvable source_kind: {!r}".format(kind))
    return items


def _apply_cap(q, items):
    """Truncate to the queue's cap.

    Applied AFTER the prior-verdict filter, not before. A cap is a promise
    about how many items the researcher will be ASKED about; spending it on
    rediscoveries that are then filtered out would serve fewer than the cap
    while candidates remained, and would disagree with `queue_counts`, which
    filters first.
    """
    cap = q["cap"]
    if cap is not None and cap >= 0:
        return items[:cap]
    return items


def _superseded_run_ids(conn):
    """Runs the researcher discarded (04-to-05 §2). Their detections stay in
    the table on purpose; they must not reach a queue."""
    return {r["id"] for r in conn.execute(
        "SELECT id FROM runs WHERE superseded_at IS NOT NULL").fetchall()}


def _resolve_detections(conn, q):
    filters = dict(q["filters"])
    if q["source_ref"] is not None and "run_group_id" not in filters:
        filters["run_group_id"] = int(q["source_ref"])
    # The same object Discovery's queue descriptor names, with the status
    # filter off so the queue can report `judged` as well as `remaining`.
    queue = ReviewQueue(conn, adjudication_status=None, **filters)
    superseded = _superseded_run_ids(conn)
    # The VERDICT, not just the flag. A row served as `judged: true` with no
    # verdict made the inspector show "unadjudicated - no verdict yet in this
    # queue" for an item the database had a verdict for: the page contradicting
    # the table it was reading.
    judged_verdicts = {r["detection_id"]: r["verdict"] for r in conn.execute(
        "SELECT detection_id, verdict FROM adjudications").fetchall()}
    judged_ids = set(judged_verdicts)
    judged_tags = _adjudication_tag_values(conn)
    blind = bool(q["blind"])
    live = [c for c in queue.candidates if c["run_id"] not in superseded]
    priors = _prior_verdicts(conn, live)
    items = []
    for cand in live:
        prior = priors.get(cand["id"])
        item = {
            "target_id": cand["id"],
            "unit": q["unit"],
            "detection_id": cand["id"],
            "run_id": cand["run_id"],
            "recording_id": cand["recording_id"],
            "channel": cand["channel"],
            "start_idx": cand["start_idx"],
            "end_idx": cand["end_idx"],
            "judged": cand["id"] in judged_ids,
            "verdict": judged_verdicts.get(cand["id"]),
            "prior_verdict": prior["verdict"] if prior else None,
            "prior_annotation_id": prior["annotation_id"] if prior else None,
            "prior_iou": prior["iou"] if prior else None,
            "prior_onset_gap": prior["onset_gap"] if prior else None,
            # What the database holds against this verdict. Without it the
            # Annotate card lost its tags on every reload, so a tag that DID
            # reach the table was invisible afterwards (fixup-a item 9).
            "tags": judged_tags.get(cand["id"], []),
        }
        if not blind:
            item["score"] = cand["score"]
        items.append(item)
    return items


def _adjudication_tag_values(conn):
    """`{detection_id: [value, ...]}` over every adjudication that carries tags.

    One query for the whole queue rather than one per row: the resolver runs on
    every read. Values only - the category is the vocabulary's business, and the
    card shows the term the researcher chose.
    """
    return _tag_values(
        conn,
        "SELECT a.detection_id AS owner, v.value AS value "
        "FROM adjudications a "
        "JOIN adjudication_tags t ON t.adjudication_id = a.id "
        "JOIN tag_vocabulary v ON v.id = t.tag_id")


def _annotation_tag_values(conn):
    """`{annotation_id: [value, ...]}`. The HUMAN door (CLAUDE.md rule 5): a
    human span's tags live in `annotation_tags` and are never read from, or
    written to, the machine table."""
    return _tag_values(
        conn,
        "SELECT t.annotation_id AS owner, v.value AS value "
        "FROM annotation_tags t JOIN tag_vocabulary v ON v.id = t.tag_id")


def _tag_values(conn, sql):
    out = {}
    try:
        rows = conn.execute(sql).fetchall()
    except Exception:                       # a database older than the tag tables
        return out
    for r in rows:
        out.setdefault(r["owner"], []).append(r["value"])
    return out


def _chunks(ids):
    ids = sorted(ids)
    for i in range(0, len(ids), _ID_CHUNK):
        yield ids[i:i + _ID_CHUNK]


def _run_span_starts(conn, run_ids):
    """`runs.span_start` per run, for `absolute_bounds`.

    A detection row written before 2026-09-21 is span-relative; a human span
    is always channel-absolute. Comparing the two unshifted does not raise —
    it silently finds no rediscovery at all, which is the worst failure this
    function has.
    """
    out = {}
    for chunk in _chunks(run_ids):
        marks = ",".join("?" * len(chunk))
        for r in conn.execute(
                "SELECT id, span_start FROM runs WHERE id IN ({})".format(marks),
                chunk).fetchall():
            out[r["id"]] = int(r["span_start"] or 0)
    return out


def _annotations_by_recording(conn, recording_ids):
    """Human spans for just these recordings, each list ascending by start.

    `recordings` is one row per source file **and channel**, so
    `annotations.recording_id` already narrows to the channel — there is no
    cross-channel comparison to guard against here. Indexed by
    `idx_annotations_recording`.
    """
    out = {}
    for chunk in _chunks(recording_ids):
        marks = ",".join("?" * len(chunk))
        for r in conn.execute(
                "SELECT id, recording_id, start_idx, end_idx, verdict FROM annotations "
                # A soft-deleted span is a span the researcher took back. Letting
                # it match would suppress a candidate, and drop it from the counts,
                # on the strength of a judgement that no longer stands.
                "WHERE deleted_at IS NULL AND recording_id IN ({}) "
                "ORDER BY recording_id, start_idx, id".format(marks),
                chunk).fetchall():
            out.setdefault(r["recording_id"], []).append(
                (int(r["start_idx"]), int(r["end_idx"]), r["verdict"], r["id"]))
    return out


def _prior_verdicts(conn, candidates):
    """`{detection_id: {verdict, annotation_id, iou, onset_gap}}` for the
    candidates that are the same event as a span a person already judged.

    Cost. The naive shape is every candidate against every annotation, and on
    this database that is a full-table scan per queue read. Three things
    narrow it instead:

    1. only the recordings the candidates are actually on are read at all —
       and a `recordings` row is one channel of one file, so that is the
       channel filter too;
    2. within a recording the spans are held ascending by start, and §4.6's
       own onset half bounds the reference start to
       ``candidate.start ± onset × candidate.duration`` — two bisections, not
       a scan;
    3. `rule_from_settings` is read once per queue read, not once per pair.

    So a candidate is compared against the handful of human spans that begin
    near it, and a recording with no annotations costs nothing.

    Pairing is **per candidate**, not the one-to-one greedy of
    `match_span_sets`: two detections of one already-judged event are both
    rediscoveries of it and neither should be put to the researcher. (The
    scoreboard keeps its one-to-one pairing, because there a duplicate *is* a
    second false positive.) Ties go to the higher IoU, then the lower
    annotation id, so the answer is a function of the data alone.
    """
    if not candidates:
        return {}
    span_starts = _run_span_starts(conn, {c["run_id"] for c in candidates})
    by_recording = _annotations_by_recording(
        conn, {c["recording_id"] for c in candidates})
    if not by_recording:
        return {}
    rule = rule_from_settings(conn)
    onset = rule["onset"]

    out = {}
    starts_cache = {}
    for cand in candidates:
        spans = by_recording.get(cand["recording_id"])
        if not spans:
            continue
        starts = starts_cache.get(cand["recording_id"])
        if starts is None:
            starts = [s[0] for s in spans]
            starts_cache[cand["recording_id"]] = starts

        c_start, c_end = absolute_bounds(
            cand["start_idx"], cand["end_idx"],
            span_starts.get(cand["run_id"], 0))
        tolerance = onset * max(0, c_end - c_start)
        lo = bisect_left(starts, math.floor(c_start - tolerance))
        hi = bisect_right(starts, math.floor(c_start + tolerance))

        best = None
        for a_start, a_end, verdict, ann_id in spans[lo:hi]:
            quality = match_quality((c_start, c_end), (a_start, a_end), rule=rule)
            if not quality["ok"]:
                continue
            key = (-quality["iou"], ann_id)
            if best is None or key < best[0]:
                best = (key, {"verdict": verdict, "annotation_id": ann_id,
                              "iou": quality["iou"],
                              "onset_gap": quality["onset_gap"]})
        if best is not None:
            out[cand["id"]] = best[1]
    return out


def _resolve_spans(conn, q):
    """Human spans a person marked `seed` in Explore (04-to-05 §4)."""
    params = []
    sql = ("SELECT id, recording_id, start_idx, end_idx, tag, note, verdict "
           "FROM annotations WHERE verdict = 'seed' AND deleted_at IS NULL")
    rec = q["filters"].get("recording_id")
    if rec is None and q["source_ref"] is not None:
        rec = int(q["source_ref"])
    if rec is not None:
        sql += " AND recording_id = ?"
        params.append(rec)
    sql += " ORDER BY id"
    judged = _audit_judged_ids(conn, q["id"])
    ann_tags = _annotation_tag_values(conn)
    return [{
        "target_id": r["id"],
        "unit": q["unit"],
        "annotation_id": r["id"],
        "recording_id": r["recording_id"],
        "start_idx": r["start_idx"],
        "end_idx": r["end_idx"],
        "tag": r["tag"],
        "note": r["note"],
        "tags": ann_tags.get(r["id"], []),
        "judged": r["id"] in judged,
        "verdict": r["verdict"],
    } for r in conn.execute(sql, params).fetchall()]


def _resolve_sequences(conn, q):
    """Catalogued spans whose singular events have not been resolved yet —
    `sequences.needs_extraction = 1`, the honest state for a claim recorded
    without inventing the events behind it."""
    params = []
    sql = ("SELECT id, sequence_key, recording_id, channel, start_idx, end_idx, "
           "n_events FROM sequences WHERE needs_extraction = 1")
    if q["source_ref"] is not None:
        sql += " AND id = ?"
        params.append(int(q["source_ref"]))
    sql += " ORDER BY id"
    judged = _audit_judged_ids(conn, q["id"])
    return [{
        "target_id": r["id"],
        "unit": q["unit"],
        "sequence_id": r["id"],
        "sequence_key": r["sequence_key"],
        "recording_id": r["recording_id"],
        "channel": r["channel"],
        "start_idx": r["start_idx"],
        "end_idx": r["end_idx"],
        "n_events": r["n_events"],
        "judged": r["id"] in judged,
    } for r in conn.execute(sql, params).fetchall()]


def _resolve_windows(conn, q):
    """Every index of a window set, minus those already in `window_verdicts`.

    A window queue carries no score whatever the `blind` flag says: the point
    of a verification pass is that the model's opinion is not in the room.
    """
    if q["source_ref"] is None:
        return []
    ws_id = int(q["source_ref"])
    row = conn.execute(
        "SELECT n_windows FROM window_sets WHERE id = ?", (ws_id,)).fetchone()
    if row is None or row["n_windows"] is None:
        return []
    judged = {r["window_index"] for r in conn.execute(
        "SELECT window_index FROM window_verdicts WHERE window_set_id = ?",
        (ws_id,)).fetchall()}
    return [{
        "target_id": i,
        "unit": q["unit"],
        "window_set_id": ws_id,
        "window_index": i,
        "judged": i in judged,
    } for i in range(int(row["n_windows"]))]


def _audit_judged_ids(conn, queue_id):
    """Which targets this queue has already been given a verdict on, for the
    kinds whose verdict table cannot be keyed back to the source row.

    A span verdict writes a NEW `annotations` row and an extraction writes
    `sequence_members`, so neither table says "this source item was judged".
    `review_audit` does: it is the ordered ledger of what Review wrote, and a
    row whose `undone_at` is set no longer counts. The ledger entry carries
    the source id under `target_id` / `target_ids` in `payload_json`.
    """
    out = set()
    for row in conn.execute(
            "SELECT payload_json FROM review_audit "
            "WHERE queue_id = ? AND undone_at IS NULL", (queue_id,)).fetchall():
        if not row["payload_json"]:
            continue
        try:
            payload = json.loads(row["payload_json"])
        except (ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        # `write_verdict`/`write_batch` record every target under `targets`,
        # each entry carrying the SOURCE id as `target_id` (and, where they
        # differ, the row it landed on as `row_id`). Reading the wrong key here
        # is why an annotations or sequence queue never registered anything as
        # judged and could never drain. The two older spellings are still read
        # so a ledger written before this fix still counts.
        for entry in payload.get("targets") or ():
            if isinstance(entry, dict) and entry.get("target_id") is not None:
                out.add(entry["target_id"])
        if payload.get("target_id") is not None:
            out.add(payload["target_id"])
        for tid in payload.get("target_ids") or ():
            out.add(tid)
    return out
