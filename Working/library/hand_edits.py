"""
hand_edits.py
=============
`docs/LIBRARY_STORAGE.md` §3.3 `hand_edits` and spec §8.3 — what the
researcher decided by hand, kept outside every grouping and re-applied on top
of each one.

    "A member removed by hand stays out of that family on every regroup until
    restored. An edit pointing at a family the new grouping lacks is kept as a
    hand group."

**Keyed by content hash, never by member id.** A member id records when a row
was written; a re-import or a rebuilt grouping renumbers them, and an id-keyed
edit would silently evaporate on exactly the operation it exists to survive.
The hash is the shape itself, so a decision taken in March still binds after a
re-clustering in June.

The module has two halves that are one flow. The store (`record`, `undo`,
`edits_for`, `active_edits`) owns the rows; `apply_to_assignment` is a **pure**
function over plain dicts — a computed grouping's assignments plus the active
edits in, the edited assignments and the orphans out, no connection anywhere
near it. Pure is what lets the grouping engine and the web bridge apply one
copy of the rule instead of two, and lets it be tested without a database.

Nothing here deletes an assignment. A removed member keeps its row with
`family_label = None` and `omit_reason = 'removed_by_hand'`, because §8.2 says
what does not fit is flagged and never deleted, and §8.6 draws a "removed by
hand" strip with *Restore* that needs the row to still be there. An undo is
`active = 0` for the same reason: the catalogue's history stays readable.
"""

import datetime

#: The vocabulary the `hand_edits` CHECK constraint enforces, repeated here so
#: a bad `kind` is refused with a readable message instead of an IntegrityError.
KINDS = ("add_member", "remove_member", "make_exemplar", "tag", "class")

#: Why a member has no family after the edits were applied.
REMOVED_BY_HAND = "removed_by_hand"


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def record(conn, *, content_hash, kind, family_label=None, value=None,
           grouping_id=None, actor=None, created_at=None, commit=True):
    """Store one hand edit and return its id.

    `grouping_id = None` means the edit applies to **every** grouping, which is
    the normal case: a decision about a shape is not a decision about one
    clustering of it. Pass a grouping id only for an edit that is genuinely
    about one saved answer.

    `actor` is free text; user accounts are future scope, so today's callers
    pass "this installation" (the convention `Working.registration.core` uses).
    """
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    if not content_hash:
        raise ValueError(
            "A hand edit needs a content_hash: it is keyed by the shape, not "
            "by a member id, so that it survives a regroup and a re-import."
        )
    cur = conn.execute(
        """INSERT INTO hand_edits
               (content_hash, kind, family_label, value, grouping_id, active,
                created_at, actor)
           VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
        (content_hash, kind, family_label, value, grouping_id,
         created_at or _now(), actor),
    )
    if commit:
        conn.commit()
    return cur.lastrowid


def undo(conn, edit_id, commit=True):
    """Withdraw an edit by setting `active = 0`.

    The row stays: a removal that is restored is part of what happened to the
    catalogue, and deleting it would make the member look as though it had
    never been touched.
    """
    conn.execute("UPDATE hand_edits SET active = 0 WHERE id = ?", (int(edit_id),))
    if commit:
        conn.commit()


def restore(conn, edit_id, commit=True):
    """Re-activate a withdrawn edit — the inverse of `undo`, and the reason
    `undo` does not delete."""
    conn.execute("UPDATE hand_edits SET active = 1 WHERE id = ?", (int(edit_id),))
    if commit:
        conn.commit()


def edits_for(conn, content_hash, *, grouping_id=None, include_inactive=False):
    """The active edits on one shape, oldest first.

    A grouping sees its own edits **and** the global ones (`grouping_id IS
    NULL`); asking for a grouping never hides an edit that applies everywhere.
    """
    sql = ["SELECT * FROM hand_edits WHERE content_hash = ?"]
    params = [content_hash]
    if not include_inactive:
        sql.append("AND active = 1")
    if grouping_id is not None:
        sql.append("AND (grouping_id IS NULL OR grouping_id = ?)")
        params.append(int(grouping_id))
    sql.append("ORDER BY id")
    return conn.execute(" ".join(sql), params).fetchall()


def active_edits(conn, grouping_id=None):
    """Every active edit that applies to `grouping_id` (or to everything when
    it is None), oldest first — the list `apply_to_assignment` consumes."""
    sql = ["SELECT * FROM hand_edits WHERE active = 1"]
    params = []
    if grouping_id is not None:
        sql.append("AND (grouping_id IS NULL OR grouping_id = ?)")
        params.append(int(grouping_id))
    sql.append("ORDER BY id")
    return conn.execute(" ".join(sql), params).fetchall()


def _field(edit, name, default=None):
    """One field of an edit, from a `sqlite3.Row` or a plain dict alike — the
    store's rows go into the pure function unchanged, so it must read both."""
    try:
        value = edit[name]
    except (KeyError, IndexError):
        return default
    return default if value is None else value


def apply_to_assignment(assignments, edits):
    """Re-apply hand edits on top of one computed grouping (spec §8.3).

    Parameters
    ----------
    assignments : iterable of dict
        A computed grouping's answer, one dict per member, carrying at least
        `content_hash` and `family_label`. Not mutated: every returned row is a
        copy, so the engine keeps its computed answer for the preview to count
        against (§8.2).
    edits : iterable of dict or sqlite3.Row
        Active hand edits — what `active_edits` returns, unchanged.

    Returns
    -------
    dict
        ``{"assignments": [...], "orphans": [...], "counts": {...}}``

        `orphans` are edits naming a family this grouping does not have. They
        are handed back rather than dropped or forced in, to be kept as a hand
        group — spec §8.3's "F-03 additions" case — because an addition to a
        family that no longer exists is still a decision someone made.

    How each kind lands
    -------------------
    ``add_member``     joins that family, creating a row if the shape is not in
                       this grouping at all (it may have been omitted).
    ``remove_member``  leaves the family and stays listed, flagged
                       `removed_by_hand` — "stays out of that family on every
                       regroup until restored".
    ``make_exemplar``  marks that member.
    ``tag`` / ``class`` attach to the member.

    A ``remove_member`` or ``make_exemplar`` edit naming a family is scoped to
    it; one with no `family_label` applies wherever the member landed. Matching
    is by **label**, which is what the row carries — a grouping that renames
    its families orphans those edits rather than mis-applying them, which is
    the safe direction: an orphan is visible and a mis-application is not.
    """
    rows = []
    index = {}
    for assignment in assignments:
        row = dict(assignment)
        row.setdefault("hand", False)
        rows.append(row)
        index.setdefault(row.get("content_hash"), []).append(row)

    families = {row.get("family_label") for row in rows if row.get("family_label")}

    orphans = {}
    applied = 0

    def _orphan(edit, family_label):
        bucket = orphans.setdefault(family_label, {
            "family_label": family_label,
            "hand_group_label": f"{family_label} additions",
            "content_hashes": [],
            "edits": [],
        })
        content_hash = _field(edit, "content_hash")
        if content_hash not in bucket["content_hashes"]:
            bucket["content_hashes"].append(content_hash)
        bucket["edits"].append(dict(edit) if not isinstance(edit, dict) else edit)

    for edit in edits:
        kind = _field(edit, "kind")
        content_hash = _field(edit, "content_hash")
        family_label = _field(edit, "family_label")
        value = _field(edit, "value")
        targets = index.get(content_hash, [])

        if kind == "add_member":
            if family_label and family_label not in families:
                _orphan(edit, family_label)
                continue
            if not targets:
                # The shape is in the catalogue but not in this grouping's
                # answer — omitted by the cut, most likely. The hand edit puts
                # it back, which is the whole point of an addition.
                row = {"content_hash": content_hash, "family_label": family_label,
                       "member_ref": None, "hand": True}
                rows.append(row)
                index.setdefault(content_hash, []).append(row)
                applied += 1
                continue
            for row in targets:
                row["family_label"] = family_label
                row["family_id"] = None
                row["omit_reason"] = None
                row["removed_by_hand"] = False
                row["hand"] = True
            applied += 1

        elif kind == "remove_member":
            if family_label and family_label not in families:
                _orphan(edit, family_label)
                continue
            hit = False
            for row in targets:
                if family_label and row.get("family_label") != family_label:
                    continue
                row["family_label"] = None
                row["family_id"] = None
                row["omit_reason"] = REMOVED_BY_HAND
                row["removed_by_hand"] = True
                row["hand"] = True
                hit = True
            applied += 1 if hit else 0

        elif kind == "make_exemplar":
            if family_label and family_label not in families:
                _orphan(edit, family_label)
                continue
            for row in targets:
                row["is_exemplar"] = True
                row["hand"] = True
            applied += 1 if targets else 0

        elif kind == "tag":
            for row in targets:
                tags = list(row.get("tags") or [])
                if value is not None and value not in tags:
                    tags.append(value)
                row["tags"] = tags
                row["hand"] = True
            applied += 1 if targets else 0

        elif kind == "class":
            for row in targets:
                row["class_label"] = value
                row["hand"] = True
            applied += 1 if targets else 0

        else:
            raise ValueError(f"Unknown hand-edit kind {kind!r}; expected one of {KINDS}")

    return {
        "assignments": rows,
        "orphans": list(orphans.values()),
        "counts": {
            "applied": applied,
            "orphaned": sum(len(o["edits"]) for o in orphans.values()),
            "removed_by_hand": sum(1 for r in rows if r.get("removed_by_hand")),
        },
    }
