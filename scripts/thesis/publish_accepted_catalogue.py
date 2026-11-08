"""Publish a traceable accepted-only Library collection; never change old looks.

By default: preview. --apply takes a SQLite backup including the live WAL, records
the researcher's explicit train-level inclusion once per train, imports ONE
representative per accepted-span component through existing identity/revision
helpers, and saves a source-labelled Library grouping. This is an inventory by
recording, not a new morphology clustering. Existing g-11 is untouched.

No new adjudications or carried labels. Existing human observations are linked,
not re-reviewed. Train child annotations record bulk acceptance and machine-
proposed boundaries explicitly; they are not individual blind judgements.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.thesis.accepted_catalogue import ACCEPT, build, connect
from Working.database import queries as Q, runs as R
from Working.library import dedupe, revisions
from Working.library.identity import hash_span
from Working.library.grouping.engine import run_grouping
from Working.registration.settings import append_audit

NAME = "Accepted catalogue · by recording · boundaries pending (2026-11-08)"
ACTOR = "researcher request, 2026-11-08; accepted catalogue reconciliation"


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def add_trains(c, trains):
    """Idempotent transcription of an explicit human batch decision.

    The parent is the accepted train region; child extents came from a machine
    and say so. One audit per train, never N invented independent human looks.
    """
    made = []
    existing = {}
    for r in c.execute("SELECT id,note FROM annotations WHERE source='researcher_train_region' AND deleted_at IS NULL"):
        data = json.loads(r["note"] or "{}")
        existing[data.get("train_id")] = int(r["id"])
    for train in trains:
        if train["id"] in existing:
            made.append({"train_id": train["id"], "status": "already_present", "parent_annotation_id": existing[train["id"]]})
            continue
        evs = train["events"]
        rid = int(evs[0]["recording_id"])
        # The parent includes the original source coverage, beyond child widths.
        from scripts.thesis.accepted_catalogue import canonical_span
        recs = {r["id"]: dict(r) for r in c.execute("SELECT * FROM recordings")}
        src = recs[train["source_recording_id"]]
        _, s, e = canonical_span(src, round(train["start_s"] * src["fs"]), round(train["end_s"] * src["fs"]), recs)
        parent_note = {"train_id": train["id"], "acceptance_level": "train_level",
                       "researcher_request": "include all spikes in both the long CH15 train and the CH14 excerpt; case studies for Chapter 10",
                       "date": "2026-11-08", "boundary_method": train["method"],
                       "prominence_mv": train["prominence_mv"], "individual_blind_looks": 0}
        parent = Q.insert_annotation(c, rid, s, e, "interesting", "researcher_train_region",
                    note=json.dumps(parent_note), event_count=len(evs), commit=False)
        children = []
        for ev in evs:
            detail = {"train_id": train["id"], "proposal_id": ev["event_id"], "peak_idx": ev["peak_idx"],
                      "boundary_status": "machine_proposed", "acceptance_level": "train_level",
                      "individually_blind_reviewed": False,
                      "source_recording_id": ev["source_recording_id"],
                      "source_start_idx": ev["source_start_idx"], "source_end_idx": ev["source_end_idx"],
                      "method": train["method"], "prominence_mv": ev["prominence_mv"]}
            aid = Q.insert_annotation(c, rid, ev["start_idx"], ev["end_idx"], "interesting",
                    "researcher_train_acceptance", note=json.dumps(detail), event_count=1,
                    parent_annotation_id=parent, relation_kind="sub_window", commit=False)
            children.append(aid)
        audit = append_audit(c, "accepted-train-transcription", f"{train['label']}: {len(children)} spikes included by researcher at train level; machine boundary proposals",
                "Library", route="scripts.thesis.publish_accepted_catalogue.add_trains", actor=ACTOR,
                detail={"parent_annotation_id": parent, "child_annotation_ids": children, **parent_note}, commit=False)
        made.append({"train_id": train["id"], "status": "created", "parent_annotation_id": parent,
                     "child_annotation_ids": children, "audit_id": audit})
    return made


def member_for(c, event, source, recs):
    """One occurrence, using existing shape identity and revision machinery.

    The displayed representative is the reviewed source's own span (mapped if
    it is a registered physical copy). The union and every source remain in the
    external catalogue. This avoids presenting an unreviewed union as a redraw.
    """
    rid = int(event["recording_id"])
    rec = recs[rid]
    s, e = int(source["canonical_start"]), int(source["canonical_end"])
    # The event-store importer can hash its detrended stored snippet, whereas
    # hash_span reads the native recording. Prefer an existing occurrence before
    # comparing hashes; reusing it must never rewrite its import provenance.
    held = c.execute("SELECT * FROM motif_entry WHERE recording_id=? AND start_idx=? AND end_idx=?",
                     (rid, s, e)).fetchone()
    digest = held["content_hash"] if held and held["content_hash"] else hash_span(c, rid, rec["channel"], s, e)
    det = source.get("detection_id")
    aid = source["id"] if source["ref"].startswith("annotation:") else None
    entry = int(held["id"]) if held else dedupe.find_duplicates(c, digest)
    if entry is None:
        entry = R.insert_motif_entry(c, rid, s, e, detection_id=det,
                notes="Accepted catalogue representative; full source links in accepted_catalogue/catalogue.json; boundaries pending",
                created_at=now(), commit=False)
        c.execute("UPDATE motif_entry SET content_hash=?,channel=?,fs=?,scale='event',source_kind='accepted-catalogue',source_store=?,source_ref=? WHERE id=?",
                  (digest, rec["channel"], rec["fs"], "all human-reviewed sources", event["event_id"], entry))
    member = R.get_or_create_motif_member(c, entry, rid, s, e, commit=False)
    c.execute("UPDATE motif_member SET content_hash=COALESCE(content_hash,?),channel=COALESCE(channel,?) WHERE id=?", (digest, rec["channel"], member))
    current = revisions.current_revision(c, member)
    # A prior exact occurrence may lack the accepted-source link. Attach it as a
    # revision; no original observation, annotation or detection is changed.
    pointer = "annotation_id" if aid is not None else "detection_id"
    value = aid if aid is not None else det
    if current is None or current[pointer] != value:
        revisions.add_revision(c, member, origin="human" if aid is not None else "machine",
                annotation_id=aid, detection_id=det if aid is None else None,
                start_idx=s, end_idx=e, content_hash=digest, commit=False)
    return int(member), digest


def publish(c, events, rows, recs):
    sources = {r["ref"]: r for r in rows}
    items, links = [], []
    for ev in events:
        if not ev["thesis_scope"]:
            continue  # wider-project catalogue is preserved in the export
        src = sources[ev["representative_ref"]]
        member, digest = member_for(c, ev, src, recs)
        items.append({"member_ref": member, "content_hash": digest, "cluster_label": ev["dataset"]})
        links.append({"event_id": ev["event_id"], "member_id": member,
                      "representative_ref": src["ref"], "source_refs": ev["source_refs"],
                      "union_start_idx": ev["start_idx"], "union_end_idx": ev["end_idx"],
                      "display_start_idx": src["canonical_start"], "display_end_idx": src["canonical_end"]})
    mids = [i["member_ref"] for i in items]
    if len(set(mids)) != len(mids):
        raise ValueError("One member selected for two events; inspect split provenance before publishing")
    params = {"min_group": 1, "omit_small": False}
    result = run_grouping(items, unit="single_motifs", basis="custom", method="labels", params=params)
    fit = {"catalogue": "all reviewed sources, researcher-authorised M4 inclusion, physical copies reconciled",
           "counting_unit": "accepted observations; broad sequence parents are not certified individual events",
           "boundary_status": "pending; accepted spans, not verified single-waveform durations",
           "families_are": "recording labels, not morphology families",
           "source_manifest": "docs/thesis/data/accepted_catalogue/catalogue.json",
           "acceptance_levels": dict(collections.Counter(e["acceptance_level"] for e in events if e["thesis_scope"]))}
    prior = c.execute("SELECT id FROM groupings WHERE name=?", (NAME,)).fetchone()
    vals = ("single_motifs", "custom", "labels", json.dumps(params), result.n_families,
            result.n_assigned, result.n_omitted, result.recipe_hash, now(), ACTOR, json.dumps(fit))
    if prior:
        gid = int(prior[0])
        c.execute("UPDATE groupings SET unit=?,basis=?,method=?,params_json=?,n_families=?,n_assigned=?,n_omitted=?,recipe_hash=?,created_at=?,actor=?,fit_summary_json=? WHERE id=?", (*vals, gid))
        c.execute("DELETE FROM grouping_assignments WHERE grouping_id=?", (gid,))
    else:
        gid = c.execute("INSERT INTO groupings(name,unit,basis,method,params_json,n_families,n_assigned,n_omitted,recipe_hash,created_at,actor,fit_summary_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (NAME, *vals)).lastrowid
    for a in result.assignments:
        c.execute("INSERT INTO grouping_assignments(grouping_id,unit,member_ref,content_hash,family_id,family_label,distance,is_medoid,omit_reason) VALUES (?,?,?,?,?,?,?,?,?)",
                   (gid, "single_motifs", int(a.ref), a.content_hash, a.family_id, a.family_label, a.distance, int(a.is_medoid), a.omit_reason))
    by_annotation = {ref: link["member_id"] for link in links for ref in link["source_refs"] if ref.startswith("annotation:")}
    for sequence in c.execute("SELECT id,source_ref FROM sequences WHERE source_kind='catalogue_checked_segments'").fetchall():
        source = json.loads(sequence["source_ref"])
        for position, aid in enumerate(source["child_annotation_ids"]):
            mid = by_annotation.get(f"annotation:{aid}")
            if mid is not None:
                c.execute("UPDATE sequence_members SET member_id=? WHERE sequence_id=? AND position=?", (mid, sequence["id"], position))
    audit = append_audit(c, "accepted-catalogue-publish", f"g-{gid:02d}: {len(items)} accepted-span representatives, by recording",
            "Library", route="scripts.thesis.publish_accepted_catalogue.publish", actor=ACTOR,
            detail={"grouping_id": gid, "name": NAME, "members": links, **fit}, commit=False)
    return {"grouping_id": gid, "members": len(items), "recording_groups": result.n_families,
            "audit_id": audit, "links": links}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", required=True, type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "docs/thesis/data/accepted_catalogue")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--decisions", type=pathlib.Path, help="explicit human boundary-editor export to validate/apply")
    args = ap.parse_args(argv)
    db = args.project_root / "DATA/db/annotations.sqlite"
    trains = json.loads((args.out / "mju_trains.json").read_text())
    c = connect(db)
    rows, events, recs = build(c)
    c.close()
    if not args.apply:
        if args.decisions:
            from scripts.thesis.accepted_boundary_review import validate_decisions, signature
            doc = json.loads(args.decisions.read_text(encoding="utf-8"))
            key = doc.get("manifest_hash", "")
            if not isinstance(key, str) or len(key) != 20 or any(ch not in "0123456789abcdef" for ch in key):
                raise ValueError("Invalid review manifest identifier")
            manifest = json.loads((args.out / f"review_manifest_{key}.json").read_text())
            print("validated boundary decisions:", len(validate_decisions(doc, manifest)))
        print(json.dumps({"mode": "preview", "current_span_components": len(events),
            "thesis_components": sum(e["thesis_scope"] for e in events),
            "proposed_train_members": {t["id"]: len(t["events"]) for t in trains}, "writes": 0}, indent=2))
        return
    # SQLite backup includes ongoing WAL writes; never copy the bare DB file.
    backup = db.parent / "backups" / ("accepted_catalogue_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S") + ".sqlite")
    backup.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(db), timeout=120)
    dst = sqlite3.connect(str(backup))
    src.backup(dst)
    dst.close()
    src.close()
    print("backup:", backup, flush=True)
    c = sqlite3.connect(str(db), timeout=120)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        c.execute("BEGIN IMMEDIATE")
        tr = add_trains(c, trains)
        boundary_changes = []
        if args.decisions:
            from scripts.thesis.accepted_boundary_review import apply_decisions
            boundary_changes = apply_decisions(c, args.decisions, args.out)
        rows, events, recs = build(c)
        pub = publish(c, events, rows, recs)
        # No defects introduced into foreign-key relationships; old unrelated
        # inconsistencies are measured separately in the verification report.
        c.commit()
    except BaseException:
        c.rollback()
        raise
    finally:
        c.close()
    report = {"backup": str(backup), "trains": tr, "boundary_changes": boundary_changes, **pub}
    (args.out / "published.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"links", "trains"}}, indent=2))


if __name__ == "__main__":
    main()
