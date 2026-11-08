"""Reconcile every human-reviewed source, without inventing event boundaries.

Read-only on the research DB. All accepted observations are retained, including
fixed-window labels, but windows/known sequences cannot bridge distinct events.
An overlap component is an accepted SPAN, not proof of one complete waveform.
Boundary flags and proposals are machine suggestions, never human judgements.

python scripts/thesis/accepted_catalogue.py --project-root ../CNN
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import json
import pathlib
import sqlite3
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
ACCEPT = {"interesting", "seed"}
WINDOW_SOURCES = {"imported_10min", "blind_test_review"}
THESIS_FILES = {
    "M2_aug_concat_fs1.mat": "M2_aug", "M2_concat_fs1.mat": "M2_concat",
    "M4_aug_concat_fs1.mat": "M4", "CO_fs2.mat": "CO", "LM_fs2.mat": "LM",
    "MJu26a_fs10.mat": "MJu26a", "MJu26a_fs2.mat": "MJu26a",
    "L_LM_Jul_26_J_raw.mat": "MJu26a", "L_LM_Jul_26_J_raw_fs2.mat": "MJu26a",
    "Mushroom_260720_0509_4hrs_CH14_fs1.mat": "MJu26a",
    "SH_fs2.mat": "SH", "SO_fs2.mat": "SO",
}
# Documented in newsets_fs2.py/Chapter 5; verified against waveform windows.
# Zero-based physical channels. CH3 of the five-channel copy is physical CH15.
LLM_CHANNELS = (9, 12, 13, 14, 15)


def connect(db):
    c = sqlite3.connect(pathlib.Path(db).resolve().as_uri() + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    c.execute("BEGIN")  # one cutoff, even while the researcher continues Review
    return c


def canonical_span(rec, start, end, recs):
    """Physical recording/channel and half-open coverage, not signal amplitude.

    A block-mean sample covers its five source samples. Map interval edges by
    that coverage; sample centres are +0.2 s on the 2-Hz copies. No waveform is
    resampled here. The old CH14 excerpt has a registered offset/decimation.
    """
    rid = int(rec["id"])
    s, e = int(start), int(end)
    if rec["parent_recording_id"] is not None:
        parent = recs[int(rec["parent_recording_id"])]
        factor = rec.get("decimation") or (float(parent["fs"]) / float(rec["fs"]))
        offset = int(rec.get("parent_offset") or 0)
        return canonical_span(parent, round(offset + s * factor), round(offset + e * factor), recs)
    file, channel = rec["source_file"], int(rec["channel"])
    if file in {"L_LM_Jul_26_J_raw.mat", "L_LM_Jul_26_J_raw_fs2.mat"}:
        channel = LLM_CHANNELS[channel]
        file = "MJu26a_fs10.mat"
    elif file == "MJu26a_fs2.mat":
        file = "MJu26a_fs10.mat"
    target = next((r for r in recs.values() if r["source_file"] == file and r["channel"] == channel), rec)
    factor = float(target["fs"]) / float(rec["fs"])
    return int(target["id"]), round(s * factor), round(e * factor)


def overlap_components(rows):
    """Strict positive overlap on ONE physical channel; abutting spans stay apart.

    Input excludes context-only windows/sequence regions. Every original source
    survives in the resulting component. Never merge across channels/datasets.
    """
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[row["canonical_recording_id"]].append(row)
    out = []
    for rid, rr in sorted(grouped.items()):
        current, end = [], -1
        for row in sorted(rr, key=lambda r: (r["canonical_start"], r["canonical_end"], r["ref"])):
            if current and row["canonical_start"] >= end:
                out.append(current)
                current = []
            current.append(row)
            end = max(end, row["canonical_end"]) if len(current) > 1 else row["canonical_end"]
        if current:
            out.append(current)
    return out


def collect(c):
    from Working.database.queries import not_surrogate
    from Working.discovery.spans import absolute_bounds, legacy_ambiguous
    from Working.review.span_edits import detection_edits
    edits = detection_edits(c)
    current_annotations = {int(r[0]) for r in c.execute(
        "SELECT rv.annotation_id FROM motif_member m JOIN motif_member_revision rv "
        "ON rv.id=m.current_revision_id WHERE rv.annotation_id IS NOT NULL")}
    obsolete_edits = {int(r[0]) for r in c.execute(
        "SELECT rv.annotation_id FROM motif_member_revision rv JOIN annotations a ON a.id=rv.annotation_id "
        "WHERE rv.superseded_at IS NOT NULL AND a.source='review-span-edit'")} - current_annotations
    current_annotations.update(int(r["annotation_id"]) for r in edits.values())
    edit_verdicts = {int(r["annotation_id"]): r["verdict"] for r in c.execute(
        "SELECT x.annotation_id,a.verdict FROM review_span_edits x "
        "JOIN adjudications a ON a.detection_id=x.detection_id")} if edits else {}

    # This store is empty on the reconciled installation. Refuse to overlook
    # newly introduced window-set judgements on a future refresh.
    if c.execute("SELECT COUNT(*) FROM window_verdicts").fetchone()[0]:
        raise ValueError("window_verdicts now contains labels: resolve its window-set coordinates before refreshing this catalogue")

    recs = {int(r["id"]): dict(r) for r in c.execute("SELECT * FROM recordings")}
    audit_queues = collections.defaultdict(set)
    for r in c.execute("SELECT queue_id,target_table,target_ids,payload_json FROM review_audit WHERE undone_at IS NULL"):
        # Family-review targets name motif_member rows, whereas their written
        # verdicts are annotations. The payload records both identities.
        payload = json.loads(r["payload_json"] or "{}")
        written = [t["row_id"] for t in payload.get("targets", []) if t.get("row_id") is not None]
        targets = written or json.loads(r["target_ids"] or "[]")
        for target in targets:
            audit_queues[(r["target_table"], int(target))].add(int(r["queue_id"]))
    # Older looks sometimes precede audit instrumentation; keep queue membership too.
    det_queues, run_queues = collections.defaultdict(set), collections.defaultdict(set)
    for r in c.execute("SELECT id,filters_json FROM review_queues WHERE writes_to='adjudications'"):
        f = json.loads(r["filters_json"] or "{}")
        for det in f.get("detection_ids", []):
            det_queues[int(det)].add(int(r["id"]))
        for run in ([f["run_id"]] if f.get("run_id") else f.get("run_ids", [])):
            run_queues[int(run)].add(int(r["id"]))
    sequence_annotations = {int(r[0]) for r in c.execute(
        "SELECT annotation_id FROM sequences WHERE annotation_id IS NOT NULL AND (n_events>1 OR needs_extraction=1)")}
    rows = []

    def add(row, kind, ref, queues):
        rec = recs[int(row["recording_id"])]
        crid, cs, ce = canonical_span(rec, row["start_idx"], row["end_idx"], recs)
        canonical = recs[crid]
        file = rec["source_file"]
        rows.append({**row, "ref": ref, "kind": kind,
                     "queue_ids": sorted(queues), "source_file": file,
                     "recording_channel": int(rec["channel"]), "fs": float(rec["fs"]),
                     "canonical_recording_id": crid, "canonical_start": cs, "canonical_end": ce,
                     "dataset": THESIS_FILES.get(file, pathlib.Path(file).stem),
                     "physical_channel": int(canonical["channel"]),
                     "thesis_scope": file in THESIS_FILES,
                     "active_source": bool(rec["active"]),
                     "valid_bounds": 0 <= cs < ce <= int(canonical["n_samples"]),
                     "accepted": row["verdict"] in ACCEPT})

    # Latest OWN observation per detection. Carried labels never become new looks.
    for r in c.execute(f"""
        WITH latest AS (SELECT detection_id,MAX(id) id FROM adjudications
                         WHERE carried_from IS NULL GROUP BY detection_id)
        SELECT a.id,a.detection_id,a.verdict,a.created_at,a.note,d.start_idx,d.end_idx,
               d.run_id,r.recording_id,r.span_start,r.span_end,r.started_at
          FROM latest l JOIN adjudications a ON a.id=l.id
          JOIN detections d ON d.id=a.detection_id JOIN runs r ON r.id=d.run_id
         WHERE {not_surrogate('r')} ORDER BY a.id"""):
        row = dict(r)
        row["stored_start_idx"], row["stored_end_idx"] = row["start_idx"], row["end_idx"]
        row["start_idx"], row["end_idx"] = absolute_bounds(row["start_idx"], row["end_idx"], row["span_start"])
        edit = edits.get(int(row["detection_id"]))
        if edit:
            row["start_idx"], row["end_idx"] = edit["start_idx"], edit["end_idx"]
            row["extent_annotation_id"] = edit["annotation_id"]
        row["placement_ambiguous"] = legacy_ambiguous(row["span_start"], row["span_end"], row["started_at"])
        row["source"] = "adjudication"
        qs = audit_queues[("adjudications", int(row["detection_id"]))]
        qs = qs | det_queues[row["detection_id"]] | run_queues[row["run_id"]]
        add(row, "event_span", f"adjudication:{row['id']}", qs)
    for r in c.execute("SELECT * FROM annotations WHERE deleted_at IS NULL ORDER BY id"):
        row = dict(r)
        if row["id"] in obsolete_edits:
            continue  # Explicit revision history, including edits predating soft-supersession.
        row["current_extent_link"] = row["id"] in current_annotations
        if row["id"] in edit_verdicts:
            row["verdict"] = edit_verdicts[row["id"]]
        if row["source"] in WINDOW_SOURCES:
            kind = "labelled_window"
        elif row["id"] in sequence_annotations or (row["event_count"] or 0) > 1:
            kind = "reviewed_region"
        else:
            kind = "event_span"
        add(row, kind, f"annotation:{row['id']}", audit_queues[("annotations", row["id"])])
    return rows, recs


def library_audit(c):
    from Working.library.verdicts import member_verdicts

    mm = [dict(r) for r in c.execute("""SELECT m.id member_id,m.recording_id,m.start_idx,m.end_idx,
        e.source_kind,e.source_store,r.source_file FROM motif_member m
        JOIN motif_entry e ON e.id=m.entry_id JOIN recordings r ON r.id=m.recording_id ORDER BY m.id""")]
    vv = member_verdicts(c, mm)
    counts = collections.defaultdict(collections.Counter)
    for m in mm:
        v = vv.get(m["member_id"], {})
        m.update(v)
        counts[str(m["source_kind"])][str(v.get("verdict", "unjudged"))] += 1
        m["evidence_level"] = "window_inference" if v.get("by") == "containment" else v.get("by") or "none"
    return mm, {k: dict(v) for k, v in sorted(counts.items())}


def csv_write(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in r.items()})


def build(c):
    rows, recs = collect(c)
    positive = [r for r in rows if r["accepted"]]
    negatives = collections.defaultdict(list)
    for r in rows:
        if r["kind"] == "event_span" and not r.get("placement_ambiguous") and r["verdict"] in {"not_interesting", "artifact"}:
            negatives[r["canonical_recording_id"]].append(r)
    eligible = [r for r in positive if r["kind"] == "event_span" and r["valid_bounds"] and not r.get("placement_ambiguous")]
    # Train members have separate extrema even when their recovery tails overlap.
    # Retain older broad looks as evidence of these members, never as a bridge
    # that glues a train back into one event. This is the researcher's 8-Nov rule.
    checked = [r for r in eligible if r.get("source") == "catalogue_boundary_review"]
    latest_decisions = {}
    for r in checked:
        r["boundary_details"] = json.loads(r.get("note") or "{}")
        key = r["boundary_details"]["original_event_id"]
        if key not in latest_decisions or r["id"] > latest_decisions[key]["id"]:
            latest_decisions[key] = r
    checked = [r for r in checked if r["boundary_details"]["decision_key"] ==
               latest_decisions[r["boundary_details"]["original_event_id"]]["boundary_details"]["decision_key"]]
    superseded = {ref for r in checked for ref in r["boundary_details"]["supersedes_source_refs"]}
    by_ref = {r["ref"]: r for r in positive}
    train_members, ordinary = [], []
    for r in eligible:
        if r["ref"] in superseded or r.get("source") == "catalogue_boundary_review":
            continue
        if r.get("source") == "researcher_train_acceptance":
            r["train_details"] = json.loads(r.get("note") or "{}")
            train_members.append(r)
        else:
            ordinary.append(r)
    linked = collections.defaultdict(list)
    unlinked = []
    for r in ordinary:
        matched = []
        for t in train_members:
            if t["canonical_recording_id"] != r["canonical_recording_id"]:
                continue
            p = t["train_details"]["peak_idx"]
            if r["canonical_start"] <= p < r["canonical_end"]:
                matched.append(t)
        if matched:
            r["train_members_supported"] = [t["ref"] for t in matched]
            for t in matched:
                linked[t["ref"]].append(r)
        else:
            unlinked.append(r)
    # Later accepted machine proposals referring to a checked event add evidence;
    # they cannot undo the explicitly drawn split/trim by bridging its children.
    checked_links = collections.defaultdict(list)
    kept_train_members = []
    for r in train_members:
        matches = [t for t in checked
                   if t["canonical_recording_id"] == r["canonical_recording_id"]
                   and min(t["canonical_end"], r["canonical_end"]) - max(t["canonical_start"], r["canonical_start"]) >=
                   .5 * min(t["canonical_end"]-t["canonical_start"], r["canonical_end"]-r["canonical_start"])]
        if matches:
            for t in matches:
                checked_links[t["ref"]].extend([r, *linked[r["ref"]]])
        else:
            kept_train_members.append(r)
    train_members = kept_train_members
    remaining = []
    for r in unlinked:
        matches = []
        for t in checked:
            overlap = min(t["canonical_end"], r["canonical_end"]) - max(t["canonical_start"], r["canonical_start"])
            if t["canonical_recording_id"] == r["canonical_recording_id"] and overlap > 0 and overlap >= .5 * min(t["canonical_end"]-t["canonical_start"], r["canonical_end"]-r["canonical_start"]):
                matches.append(t)
        if matches:
            for t in matches:
                checked_links[t["ref"]].append(r)
        else:
            remaining.append(r)
    components = []
    for group in overlap_components(remaining):
        redraws = [r for r in group if r.get("source") == "review-span-edit" and r.get("current_extent_link")]
        if not redraws:
            components.append(group)
            continue
        # Distinct current redraws remain distinct, even if their recovery tails
        # overlap. Original broad observations are evidence, never merge bridges.
        for redraw in redraws:
            components.append([redraw, *[r for r in group if r not in redraws and
                r["canonical_start"] < redraw["canonical_end"] and
                r["canonical_end"] > redraw["canonical_start"]]])
    # Train boundaries are authoritative machine proposals for this extraction;
    # the older context spans survive as evidence but cannot widen them again.
    components += [[t, *linked[t["ref"]]] for t in train_members]
    components += [[t, *[by_ref[ref] for ref in t["boundary_details"]["supersedes_source_refs"] if ref in by_ref],
                    *checked_links[t["ref"]]] for t in checked]
    events = []
    for sources in components:
        rid = sources[0]["canonical_recording_id"]
        rec = recs[rid]
        correction = sources[0] if sources[0].get("source") == "catalogue_boundary_review" else None
        redraw = sources[0] if sources[0].get("source") == "review-span-edit" else None
        train = None if correction else next((r for r in sources if r.get("source") == "researcher_train_acceptance"), None)
        definitive = correction or redraw or train
        s = definitive["canonical_start"] if definitive else min(r["canonical_start"] for r in sources)
        e = definitive["canonical_end"] if definitive else max(r["canonical_end"] for r in sources)
        ident = f"{rid}:{s}:{e}"
        eid = "accepted-" + hashlib.sha256(ident.encode()).hexdigest()[:16]
        # A later human redraw is authoritative about boundaries, not overwritten by
        # a padded detector union. Keep the union separately for inspection.
        edited = [r for r in sources if r.get("source") == "review-span-edit"]
        rep = definitive or max(edited or sources, key=lambda r: (r["canonical_end"] - r["canonical_start"], r["ref"]))
        conflicts = []
        for n in negatives[rid]:
            for r in sources:
                overlap = min(n["canonical_end"], r["canonical_end"]) - max(n["canonical_start"], r["canonical_start"])
                if overlap > 0 and overlap >= .9 * max(n["canonical_end"]-n["canonical_start"], r["canonical_end"]-r["canonical_start"]):
                    conflicts.append(n["ref"])
                    break
        events.append({"event_id": eid, "dataset": sources[0]["dataset"],
                       "thesis_scope": sources[0]["thesis_scope"], "recording_id": rid,
                       "channel": int(rec["channel"]), "fs": float(rec["fs"]),
                       "start_idx": s, "end_idx": e, "start_s": s / rec["fs"], "end_s": e / rec["fs"],
                       "span_s": (e - s) / rec["fs"], "source_count": len(sources),
                       "source_refs": [r["ref"] for r in sources],
                       "other_event_sized_negative_refs": sorted(set(conflicts)),
                       "queue_ids": sorted({q for r in sources for q in r["queue_ids"]}),
                       "representative_ref": rep["ref"],
                       "representative_start": rep["canonical_start"],
                       "representative_end": rep["canonical_end"],
                       "boundary_status": "human_checked" if correction else "human_edited" if redraw else "machine_proposed" if train else "needs_check",
                       "acceptance_level": "boundary_review" if correction else "train_level" if train else "individual_span",
                       "train_id": train["train_details"]["train_id"] if train else None,
                       "peak_idx": train["train_details"]["peak_idx"] if train else None,
                       "source_verdict": "accepted",
                       "count_as_verified_single_event": bool(correction)})
    return rows, events, recs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", type=pathlib.Path, default=ROOT)
    ap.add_argument("--out", type=pathlib.Path, default=ROOT / "docs/thesis/data/accepted_catalogue")
    ap.add_argument("--skip-library-audit", action="store_true")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    c = connect(args.project_root / "DATA/db/annotations.sqlite")
    try:
        rows, events, recs = build(c)
        members, la = ([], {}) if args.skip_library_audit else library_audit(c)
        cutoff = {t: c.execute(f"SELECT MAX(id) FROM {t}").fetchone()[0]
                  for t in ("adjudications", "annotations", "review_audit")}
    finally:
        c.close()
    positive = [r for r in rows if r["accepted"]]
    report = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "cutoff": cutoff,
        "read_only": True, "accepted_observations": len(positive),
        "accepted_observations_by_kind": dict(collections.Counter(r["kind"] for r in positive)),
        "accepted_observations_by_source": dict(collections.Counter(r["source"] for r in positive)),
        "accepted_span_components": len(events),
        "thesis_span_components": sum(e["thesis_scope"] for e in events),
        "per_dataset": dict(collections.Counter(e["dataset"] for e in events)),
        "event_source_links": sum(e["source_count"] for e in events),
        "unique_event_sources": len({r for e in events for r in e["source_refs"]}),
        "train_level_members": sum(e["acceptance_level"] == "train_level" for e in events),
        "components_with_other_event_sized_negative_judgement": sum(bool(e["other_event_sized_negative_refs"]) for e in events),
        "boundary_checks_pending": sum(e["boundary_status"] != "human_checked" for e in events),
        "library_members_by_source_and_resolved_verdict": la,
        "rules": ["Latest own adjudication per detection; carried copies are not new observations.",
                  "Every live human annotation retained, with source and queue links where known.",
                  "Known physical copies mapped before deduplication; recording/channel preserved.",
                  "Strict positive overlap combines event-span observations; touching is insufficient.",
                  "Fixed review windows and known multi-event regions retained separately; never bridge events.",
                  "Researcher-accepted train members retain separate extrema, including overlapping recoveries; older broad looks are provenance, not merge bridges.",
                  "Acceptance of a span does not certify one waveform or its exact boundaries.",
                  "No new verdicts, annotations, detections, groupings, or Library entries written.",
                  "Thesis scope and wider-project material both retained, explicitly distinguished."],
    }
    (args.out / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (args.out / "catalogue.json").write_text(json.dumps({"summary": report, "events": events,
        "observations": rows, "recordings": recs}, ensure_ascii=False), encoding="utf-8")
    csv_write(args.out / "accepted_observations.csv", positive)
    csv_write(args.out / "accepted_spans.csv", events)
    csv_write(args.out / "accepted_regions.csv", [r for r in positive if r["kind"] != "event_span"])
    if not args.skip_library_audit:
        csv_write(args.out / "library_members_audit.csv", members)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
