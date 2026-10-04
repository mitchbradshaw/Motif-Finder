"""
artifact_queue.py
=================
The *Suspected artifact* Review queue (fixup-AD, QUESTIONS.md Round 12 Q3).

The cross-channel classifier only FLAGS a family member as a suspected artifact
(`Working.library.matching.classify_family_across_channels`: the same event on
a sibling electrode at the same instant, |r| >= 0.98, beating the pair's
random-time null, both swings over the noise floor). A human decides, here.

**Where the verdict lives — `annotations`, over the member's span.** The
ticket said to choose by what the member is: a member from a run has a
detection, an imported one does not. Both go to `annotations`, because the
detection a run member came from already carries the accepting adjudication
that made it a member (Q39: `interesting` or `seed`), `adjudications` holds one
verdict per detection, and an artifact verdict there would overwrite the very
judgement the membership rests on. An annotation over the same span is a new
human observation of that span, which is what this is. Rule 5: nothing here
writes `motif_member`, `motif_edge` or `motif_member_cooccurrence`.

**The vocabulary stays at five words** (the researcher, 2026-10-05). The
reviewer answers *artifact*, or what the span really is — *interesting*, or
*not_interesting* — or *unsure*; every row carries a note saying the span was
flagged as a suspected artifact and by what, so no reader mistakes it for an
ordinary review. A member's verdict is the latest live row of this source over
exactly its span.

No UI library: `webui/server` calls into this, never the other way round.
"""

import json

from Working.database import queries as _queries

#: `review_queues.source_kind` for this queue, and its unit.
SOURCE_KIND = "suspected-artifact"
UNIT = "member"
#: `annotations.source` on every verdict this queue writes.
REVIEW_SOURCE = "cross_channel_review"
#: The five-word vocabulary, minus `seed`: the question is "is this an artifact,
#: and if not, what is it?"
VERDICT_OPTIONS = ("artifact", "interesting", "not_interesting", "unsure")
#: The verdicts that confirm the machine's flag.
CONFIRMING_VERDICTS = ("artifact",)

_CHUNK = 400


def queue_name(family):
    return f"Suspected artifact · {family}"


def _members(conn, member_ids):
    ids = sorted({int(m) for m in member_ids or []})
    out = {}
    for i in range(0, len(ids), _CHUNK):
        part = ids[i:i + _CHUNK]
        marks = ",".join("?" * len(part))
        for r in conn.execute(
                f"SELECT mm.id, mm.recording_id, mm.start_idx, mm.end_idx, r.source_file, r.channel, r.fs "
                f"FROM motif_member mm JOIN recordings r ON r.id = mm.recording_id WHERE mm.id IN ({marks})",
                tuple(part)):
            out[int(r["id"])] = dict(r)
    return out


def _review_rows(conn, members):
    """`{(recording_id, start, end): (annotation_id, verdict)}` — the latest
    live verdict this queue's source holds over each member span."""
    recs = sorted({m["recording_id"] for m in members.values()})
    out = {}
    for i in range(0, len(recs), _CHUNK):
        part = recs[i:i + _CHUNK]
        marks = ",".join("?" * len(part))
        for r in conn.execute(
                f"SELECT id, recording_id, start_idx, end_idx, verdict FROM annotations "
                f"WHERE source = ? AND deleted_at IS NULL AND recording_id IN ({marks}) ORDER BY id",
                (REVIEW_SOURCE, *part)):
            out[(int(r["recording_id"]), int(r["start_idx"]), int(r["end_idx"]))] = (int(r["id"]), r["verdict"])
    return out


def member_verdicts(conn, member_ids):
    """`{member_id: verdict}` for every member a human has answered in this
    queue (any queue of this kind: the verdict belongs to the span)."""
    members = _members(conn, member_ids)
    rows = _review_rows(conn, members)
    out = {}
    for mid, m in members.items():
        hit = rows.get((int(m["recording_id"]), int(m["start_idx"]), int(m["end_idx"])))
        if hit is not None:
            out[mid] = hit[1]
    return out


def review_annotation_id(conn, member_id):
    """The annotation a verdict on this member lands on, or None (a new one)."""
    members = _members(conn, [member_id])
    m = members.get(int(member_id))
    if m is None:
        return None
    hit = _review_rows(conn, members).get((int(m["recording_id"]), int(m["start_idx"]), int(m["end_idx"])))
    return hit[0] if hit else None


# ── what flagged a member ───────────────────────────────────────────────────

def flags_for(conn, member_ids):
    """`{member_id: [flag, ...]}` — every suspected-artifact match that flags
    the member, as the classifier stored it, oriented to the member: the
    sibling's `recording_id` and channel, `lag` / `lag_s` (the sibling relative
    to the member), signed `r`, `amplitude_ratio` (sibling swing / member
    swing), `chance` (percentile, threshold, K) and `other_member` when the
    sibling holds a family member."""
    from Working import cross_channel as xc
    from Working.library.matching import _beat_chance

    members = _members(conn, member_ids)
    ids = sorted(members)
    out = {mid: [] for mid in ids}
    rec_of = {}
    for i in range(0, len(ids), _CHUNK):
        part = ids[i:i + _CHUNK]
        marks = ",".join("?" * len(part))
        for e in conn.execute(
                f"SELECT * FROM motif_edge WHERE classification_bin = ? AND "
                f"(member_a_id IN ({marks}) OR member_b_id IN ({marks}))",
                (xc.ARTIFACT, *part, *part)):
            if not _beat_chance(e["classification_json"]):
                continue
            info = json.loads(e["classification_json"])
            fl = info.get("floor") or {}
            for me, other, sign in ((int(e["member_a_id"]), int(e["member_b_id"]), 1),
                                    (int(e["member_b_id"]), int(e["member_a_id"]), -1)):
                if me not in out:
                    continue
                if other not in rec_of:
                    row = conn.execute("SELECT recording_id FROM motif_member WHERE id = ?", (other,)).fetchone()
                    rec_of[other] = int(row[0]) if row else None
                ratio = info.get("amplitude_ratio")
                if sign < 0 and ratio:
                    ratio = 1.0 / ratio
                lag = e["lag"]
                if any(f["recording_id"] == rec_of[other] and f.get("other_member") == other for f in out[me]):
                    continue        # a seed match carries one edge per distance: one flag per pair
                out[me].append({
                    "recording_id": rec_of[other], "other_member": other,
                    "lag": (sign * lag) if lag is not None else None,
                    "lag_s": (sign * info["lag_s"]) if info.get("lag_s") is not None else None,
                    "r": e["waveform_correlation"], "amplitude_ratio": ratio,
                    "chance": info.get("chance"), "floor": fl, "window": info.get("window")})
        for r in conn.execute(
                f"SELECT * FROM motif_member_cooccurrence WHERE classification_bin = ? AND member_id IN ({marks})",
                (xc.ARTIFACT, *part)):
            if not _beat_chance(r["classification_json"]):
                continue
            info = json.loads(r["classification_json"])
            out[int(r["member_id"])].append({
                "recording_id": int(r["recording_id"]), "other_member": None, "lag": r["lag"],
                "lag_s": info.get("lag_s"), "r": r["waveform_correlation"],
                "amplitude_ratio": info.get("amplitude_ratio"), "chance": info.get("chance"),
                "floor": info.get("floor") or {}, "window": info.get("window")})
    return out


def _channel_label(conn, recording_id):
    from Working.discovery.channels import channel_name

    row = conn.execute("SELECT source_file, channel FROM recordings WHERE id = ?", (int(recording_id),)).fetchone()
    if row is None:
        return f"recording {recording_id}"
    n = conn.execute("SELECT COUNT(*) FROM recordings WHERE source_file = ?", (row["source_file"],)).fetchone()[0]
    return channel_name(row["source_file"], int(row["channel"]), int(n))


def flag_note(conn, family, member_id, flags):
    """The note every verdict row carries: that the span was flagged as a
    suspected artifact, and by what."""
    parts = []
    for f in flags:
        bits = [_channel_label(conn, f["recording_id"])]
        if f.get("lag_s") is not None:
            bits.append(f"lag {f['lag_s']:+.1f} s")
        if f.get("r") is not None:
            bits.append(f"r {f['r']:+.3f}")
        if f.get("amplitude_ratio") is not None:
            bits.append(f"amplitude ×{f['amplitude_ratio']:.2f}")
        ch = f.get("chance") or {}
        if ch.get("percentile") is not None:
            bits.append(f"{ch['percentile']:.0f}th percentile of {ch.get('k')} random times")
        parts.append(" ".join(bits))
    where = f"{family} · m-{member_id}" if family else f"m-{member_id}"
    return ("flagged as a suspected artifact by cross-channel classification (" + where + ")"
            + (": " + "; ".join(parts) if parts else ""))


# ── the queue ───────────────────────────────────────────────────────────────

def create_artifact_queue(conn, *, family, member_ids, grouping=None):
    """*Send suspected artifacts to Review*: the family's queue, made through
    `create_queue` — or the open one that already IS this queue. The filters
    hold every member of the family; which of them are flagged is resolved
    live, so a re-classification changes the queue with nothing to keep in
    step."""
    from Working.review import queues as Q

    filters = {"member_ids": sorted(int(m) for m in member_ids), "family": family}
    if grouping is not None:
        filters["grouping"] = grouping
    found = Q.find_open_queue(conn, source_kind=SOURCE_KIND, filters=filters, source_ref=family)
    if found is not None:
        return found
    return Q.create_queue(conn, name=queue_name(family), source_kind=SOURCE_KIND, source_ref=family,
                          verdict_options=list(VERDICT_OPTIONS), filters=filters,
                          note=("members the cross-channel classifier flagged as suspected artifacts; a verdict "
                                "lands in annotations over the member's span, with a note saying why it was asked"))


def resolve_items(conn, q):
    """The queue's items NOW: the members of its family the classifier flags,
    each with what flagged it and the verdict a human gave, if any."""
    from Working.library.matching import family_recurrence

    ids = [int(m) for m in (q["filters"].get("member_ids") or [])]
    if not ids:
        return []
    rec = family_recurrence(conn, ids)
    flagged = sorted(mid for mid, st in rec["members"].items() if st["flagged"])
    members = _members(conn, flagged)
    flags = flags_for(conn, flagged)
    family = q["filters"].get("family") or q.get("source_ref")
    items = []
    for mid in flagged:
        m = members[mid]
        verdict = rec["members"][mid]["verdict"]
        items.append({
            "target_id": mid, "unit": q["unit"], "member_id": mid,
            "recording_id": int(m["recording_id"]), "channel": int(m["channel"]),
            "start_idx": int(m["start_idx"]), "end_idx": int(m["end_idx"]),
            "judged": verdict is not None, "verdict": verdict, "family": family,
            "flags": flags.get(mid, []), "tags": [],
            "artifact": {"computed": True, "level": "high", "p": None,
                         "coherence": max((abs(f["r"]) for f in flags.get(mid, []) if f.get("r") is not None),
                                          default=None),
                         "clipping": "not computed", "stepChange": "not computed",
                         "electrodeFlag": "suspected artifact (cross-channel)",
                         "reason": flag_note(conn, family, mid, flags.get(mid, []))},
        })
    return items


def write_member_verdict(conn, queue, member_id, verdict, note=None, tags=None):
    """One human verdict on one flagged member, into `annotations` over its
    span. Re-describes this source's existing row for the span in place, or
    inserts one. Returns `(prior, annotation_id)`; `prior` is
    `{"inserted": True}` for a new row, so undo withdraws it."""
    from Working.database import vocabulary as _vocabulary

    if verdict not in VERDICT_OPTIONS:
        raise ValueError(f"a suspected-artifact queue takes {', '.join(VERDICT_OPTIONS)}; got {verdict!r}")
    m = _members(conn, [member_id]).get(int(member_id))
    if m is None:
        raise ValueError(f"no family member with id {member_id}")
    filters = json.loads(queue["filters_json"]) if queue["filters_json"] else {}
    family = filters.get("family") or queue["source_ref"]
    text = flag_note(conn, family, int(member_id), flags_for(conn, [member_id]).get(int(member_id), []))
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
