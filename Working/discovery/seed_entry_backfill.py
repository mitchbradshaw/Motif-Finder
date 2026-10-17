"""
seed_entry_backfill.py
======================
a2-p4 (round A_2, change 4.5): link the seed runs made from a *catalogue span*
to the Library entry at the same span, so *Add N matches to E-xxxx* can add
their accepted matches to the Library.

Why
---
The Seed page's old "Family medoid" tab offered the drop-motif store's sixteen
catalogue spans (`DATA/library_seed/drop_motifs5`), with seed ids
`medoid:<recording>:<start>:<end>`. The bridge looked a Library entry up for
`library:` ids only, so a run made from a catalogue span was written with
`entryId: null`, and Discovery › Runs › *Add N matches* refused it ("this
run's seed is not a Library entry"). Both of the researcher's judged dip
searches were such runs: `dip_search` (Discovery runs 9-11, 256 of 263
accepted) and `dip_search_allch` (run 13, 94 of 104).

Since a2-p4 a catalogue span whose span IS a Library entry's span resolves to
that entry when a run is made (`webui/server/discovery.py::_seed_by_id`). This
module gives the rows made before that the same link, by the same rule.

The rule, exactly
-----------------
A row of `discovery_runs` is linked when all of these hold:

* `kind = 'seed'` and its `params_json.seedId` is a catalogue span
  (`medoid:<recording id>:<start>:<end>`, all integers);
* `params_json.entryId` is empty (null, absent or 0);
* a `motif_entry` row has exactly that recording id, start and end — the
  lookup `discovery.py::_entry_for_span` makes (the core cannot import the
  bridge, so the one-line query is repeated here).

Then `params_json.entryId` is set to that entry's id, and **nothing else
changes**: no other key of the params, no other column (`updated_at`
included), no other row. `library:` and `explore:` runs are never touched,
even at an entry's span, nor is any run that already names an entry.

Audited and idempotent
----------------------
`backfill(conn, apply=True)` writes the links and ONE `audit_log` row (kind
`library`) naming every run it linked with its entry before and after, in one
transaction. A second backfill finds every such run already linked: it links
nothing and writes no audit row. `apply=False` (the default) writes nothing
and reports what it would do. `scripts/backfill_seed_entry_ids.py` is the
command line around it; it refuses the real database unless told `--real`.
"""
from __future__ import annotations

import json

#: The seed-id prefix of a catalogue span (the drop-motif store's sixteen spans).
CATALOGUE_SPAN = "medoid"

RULE = ("a seed run made from a catalogue span (seed id medoid:<recording>:<start>:<end>) with no entry is linked to "
        "the Library entry with exactly that recording, start and end; only params_json.entryId changes")

WHERE = "scripts/backfill_seed_entry_ids.py"


def _span(seed_id):
    """`(recording id, start, end)` of a catalogue-span seed id, or None when the id is not one or is unreadable."""
    parts = str(seed_id or "").split(":")
    if len(parts) != 4 or parts[0] != CATALOGUE_SPAN:
        return None
    try:
        return int(parts[1]), int(parts[2]), int(parts[3])
    except ValueError:
        return None


def plan(conn):
    """Every catalogue-span seed run, with what the backfill does to it: `link` (its entry), `already` (it names
    an entry), `unmatched` (no entry at its span) or `unreadable` (its seed id is not a span). Reads only."""
    out = []
    rows = conn.execute("SELECT id, session_id, run_key, label, kind, params_json, removed_at FROM discovery_runs "
                        "WHERE kind = 'seed' ORDER BY id").fetchall()
    for rid_, session_id, run_key, label, _kind, params_json, removed_at in (tuple(r) for r in rows):
        try:
            params = json.loads(params_json or "{}")
        except ValueError:
            params = None
        seed_id = (params or {}).get("seedId")
        if not str(seed_id or "").startswith(CATALOGUE_SPAN + ":"):
            continue
        row = {"id": int(rid_), "sessionId": int(session_id), "runKey": run_key, "label": label, "seedId": seed_id,
               "before": (params or {}).get("entryId"), "entryId": (params or {}).get("entryId"),
               "runIds": len((params or {}).get("run_ids") or []), "action": None, "reason": None,
               # taken off its session: Discovery › History brings it back, and with it the *Add N matches* button
               "removed": bool(removed_at)}
        span = _span(seed_id)
        if params is None or span is None:
            row.update(action="unreadable", reason=f"seed id {seed_id!r} is not medoid:<recording>:<start>:<end>")
        elif params.get("entryId"):
            row.update(action="already", reason=f"already names entry {params['entryId']}")
        else:
            e = conn.execute("SELECT id FROM motif_entry WHERE recording_id = ? AND start_idx = ? AND end_idx = ?",
                             span).fetchone()
            if e is None:
                row.update(action="unmatched", reason=f"no Library entry at recording {span[0]} [{span[1]}, {span[2]})")
            else:
                row.update(action="link", entryId=int(e[0]))
        out.append(row)
    return out


def backfill(conn, *, apply=False, actor=None, where=WHERE):
    """Link the catalogue-span seed runs to their entries (see the module docstring for the rule).

    Returns ``{applied, linked, already, unmatched, unreadable, auditId, rule}``; each list holds the runs as
    `plan` describes them. With ``apply=False`` nothing is written. With ``apply=True`` the links and one audit row
    are written in one transaction, and only when there is something to link."""
    rows = plan(conn)
    report = {"applied": bool(apply), "rule": RULE, "auditId": None,
              "linked": [r for r in rows if r["action"] == "link"],
              "already": [r for r in rows if r["action"] == "already"],
              "unmatched": [r for r in rows if r["action"] == "unmatched"],
              "unreadable": [r for r in rows if r["action"] == "unreadable"]}
    if not apply or not report["linked"]:
        return report
    from Working.registration.settings import ACTOR, append_audit
    try:
        for r in report["linked"]:
            (text,) = conn.execute("SELECT params_json FROM discovery_runs WHERE id = ?", (r["id"],)).fetchone()
            params = json.loads(text or "{}")
            params["entryId"] = r["entryId"]
            conn.execute("UPDATE discovery_runs SET params_json = ? WHERE id = ?", (json.dumps(params), r["id"]))
        labels = ", ".join(f"{r['label']} ({r['runKey']}, run {r['id']}) -> E-{r['entryId']:04d}"
                           for r in report["linked"])
        report["auditId"] = append_audit(
            conn, "library",
            f"Linked {len(report['linked'])} catalogue-span seed run(s) to the Library entry at their seed's span: "
            f"{labels}", where, route="discovery/runs", actor=actor or ACTOR, commit=False,
            detail={"rule": RULE, "runs": [{k: r[k] for k in ("id", "runKey", "label", "seedId", "before", "entryId",
                                                               "runIds")} for r in report["linked"]]})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return report
