"""Audit the completed follow-up reviews from a consistent, read-only DB snapshot.

No verdicts are written. The frozen blind-panel membership determines its
denominators; current queue counters are also reported but never substituted.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from Working.review import queues
from scripts.rq2_blind import wilson
from scripts.thesis.accepted_catalogue import build, csv_write

ACCEPT = {"interesting", "seed"}


def tally(verdicts):
    counts = Counter(verdicts)
    n = sum(counts.values())
    k = sum(counts[v] for v in ACCEPT)
    decided = k + counts["not_interesting"]
    return {"reviewed": n, "accepted": k, "rate": k / n if n else None,
            "wilson95": wilson(k, n) if n else None, "verdicts": dict(counts),
            "decided": decided, "rate_excluding_unsure_artifact": k / decided if decided else None}


def audit(c, project, out):
    out.mkdir(parents=True, exist_ok=True)
    all_latest, own_latest = {}, {}
    for r in c.execute("SELECT id,detection_id,verdict,carried_from,created_at FROM adjudications ORDER BY id"):
        all_latest[r["detection_id"]] = dict(r)
        if r["carried_from"] is None:
            own_latest[r["detection_id"]] = dict(r)
    queue_report = {}
    for qid in (38, 45, 46):
        q = queues.get_queue(c, qid)
        views = queues.queue_view(c, qid)
        served = queues.select_items(q, views, include_judged=True)
        audit_rows = [dict(r) for r in c.execute(
            "SELECT * FROM review_audit WHERE queue_id=? AND undone_at IS NULL ORDER BY id", (qid,))]
        # Repeated clicks/changes are one current decision, keyed by source item.
        actions = {}
        for r in audit_rows:
            p = json.loads(r["payload_json"] or "{}")
            if r["action"] not in {"verdict", "batch"}:
                continue
            for target in p.get("targets", []):
                actions[target["target_id"]] = {
                    "target_id": target["target_id"], "row_id": target["row_id"],
                    "verdict": p.get("verdict"), "audit_id": r["id"], "created_at": r["created_at"]}
        queue_report[str(qid)] = {
            "name": q["name"], "counts": queues.queue_counts(c, qid),
            "served_verdicts": tally([v["verdict"] for v in served if v.get("verdict")]),
            "own_distinct_targets": tally([a["verdict"] for a in actions.values() if a["verdict"]]),
            "own_actions": list(actions.values()), "views": views}

    key = json.loads((project / "DATA/derived/rq2_blind/20261108-drop-transfer/key.json").read_text())
    panel = []
    for item in key["presentations"]:
        ids = item["represented_detection_ids"]
        own = [own_latest[d] for d in ids if d in own_latest]
        current = [all_latest[d] for d in ids if d in all_latest]
        choices = {r["verdict"] for r in own}
        if len(choices) > 1:
            raise ValueError(f"Conflicting own answers within a frozen presentation: {ids}")
        chosen = max(own, key=lambda r: r["id"]) if own else None
        panel.append({"recording": item["recording"], "group": item["group"],
                      "panel_detection_id": item["panel_detection_id"], "represented_ids": ids,
                      "verdict": chosen["verdict"] if chosen else None,
                      "own_adjudication_id": chosen["id"] if chosen else None,
                      "carried_only": bool(current) and not own,
                      "start": item["start"], "end": item["end"], "recording_id": item["recording_id"]})
    grouped = defaultdict(list)
    for r in panel:
        if r["verdict"]:
            grouped[(r["recording"], r["group"])].append(r["verdict"])
            grouped[("All", r["group"])].append(r["verdict"])
    scores = [{"recording": rec, "group": group, **tally(v)}
              for (rec, group), v in sorted(grouped.items())]
    panel_summary = {"queue_id": 38, "frozen_presentations": len(panel),
                     "own_reviewed_presentations": sum(bool(r["verdict"]) for r in panel),
                     "carried_only_presentations": sum(r["carried_only"] for r in panel),
                     "unanswered_presentations": sum(not r["verdict"] and not r["carried_only"] for r in panel),
                     "planned_groups": key["presentation_groups"], "scores": scores,
                     "repeats_reserved": 46,
                     "repeats_released": (project / "DATA/derived/rq2_blind/20261108-drop-transfer/retest/key.json").exists()}
    observations, events, recs = build(c)
    thesis = [e for e in events if e["thesis_scope"]]
    positive = [r for r in observations if r["accepted"]]
    catalogue = {"thesis_accepted_span_components": len(thesis),
                 "wider_project_components": len(events)-len(thesis),
                 "by_recording": dict(Counter(e["dataset"] for e in thesis)),
                 "by_boundary_status": dict(Counter(e["boundary_status"] for e in thesis)),
                 "accepted_observations": len(positive),
                 "accepted_observations_by_kind": dict(Counter(r["kind"] for r in positive)),
                 "components_linked_to_queue": {str(q): sum(q in e["queue_ids"] for e in thesis) for q in (38,45,46)},
                 "conflicting_negative_components": sum(bool(e["other_event_sized_negative_refs"]) for e in thesis)}
    result = {"queues": queue_report, "rq2": panel_summary, "catalogue": catalogue,
              "cutoff": {t: c.execute(f"SELECT MAX(id) FROM {t}").fetchone()[0]
                         for t in ("adjudications", "annotations", "review_audit")}}
    (out / "audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (out / "catalogue.json").write_text(json.dumps({"events": events, "observations": observations,
                                                  "recordings": recs}), encoding="utf-8")
    csv_write(out / "rq2_presentations.csv", panel)
    csv_write(out / "rq2_acceptance.csv", scores)
    csv_write(out / "accepted_spans.csv", thesis)
    print(json.dumps({"queues": {k: {kk: vv for kk, vv in v.items() if kk not in {"views", "own_actions"}}
                               for k, v in queue_report.items()},
                      "rq2": panel_summary, "catalogue": catalogue}, indent=2), flush=True)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "docs/thesis/data/reviews_completed_20261108")
    args = ap.parse_args()
    c = sqlite3.connect(args.snapshot.resolve().as_uri()+"?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    c.execute("BEGIN")
    try:
        audit(c, args.project_root, args.out)
    finally:
        c.close()


if __name__ == "__main__":
    main()
