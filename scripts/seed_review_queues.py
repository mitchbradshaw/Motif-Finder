"""Seed the two real Review queues named by stage-3 Prompt 05, Work item 4.

Run against a bridge started in ``--project`` mode (the REAL
``DATA/db/annotations.sqlite``), so the queues are created through the same
``POST /api/review/queues`` route the UI uses rather than by reaching past it
with SQL. A queue created by a side door would not prove the route works.

    "/c/ProgramData/anaconda3/python.exe" scripts/seed_review_queues.py \
        --url http://127.0.0.1:8765

It is **idempotent**: a queue whose name already exists is left alone and
reported as `kept`, so re-running after a restart does not pile up duplicates.

Dev tooling. Nothing under `Working/`, `Adapters/` or `Pipelines/` imports it.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

# ---------------------------------------------------------------- the queues

# 1. Library's `extract events` queue (Prompt 03): every sequence catalogued
#    with `needs_extraction = 1` — the claim was recorded, the singular events
#    were not invented, and this queue is where a person resolves them.
#    `source_ref = None` means the whole corpus rather than one sequence.
EXTRACT = {
    "name": "Library - extract events",
    "source_kind": "extract-events",
    "source_ref": None,
    "note": "Sequences catalogued with needs_extraction = 1 (Prompt 03). "
            "Mark the individual events; the sequence loses the flag when the reviewer says it is complete.",
}

# 2. A detections queue over a real template-application run.
#
#    NOTE, and it is the reason `source_ref` is None here: Prompt 04's
#    descriptor keys a Discovery queue on `run_group_id`, but on THIS machine
#    `run_groups`, `discovery_runs` and `discovery_sessions` are all empty --
#    Prompt 04 ran against the sandbox database, so nothing it made was
#    persisted into the project database. Every run carrying detections has
#    `run_group_id IS NULL`.
#
#    So the queue is pointed at the run directly, through the `filters` dict
#    that `queue_items` passes to `ReviewQueue` (which has accepted `run_id`
#    since ticket 20). That is not a workaround for a missing feature; it is
#    the same filter composition Discovery would use, with one filter instead
#    of another. When a real Discovery fan-out writes a run group here, a
#    `source_ref` queue will resolve it with no change to this file.
DETECTIONS = {
    "name": "drop_detection_v1 - Mushroom_260720 CH14",
    "source_kind": "discovery-run",
    "source_ref": None,
    "filters": {"run_id": 32},
    "note": "Template application of drop_detection_v1 to Mushroom_260720_0509_4hrs_CH14_fs1.mat "
            "(run 32, recording 385). Pointed at the run, not a run group: this database has no run_groups.",
}

QUEUES = (EXTRACT, DETECTIONS)


def _get(url: str):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(url: str, body: dict):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="http://127.0.0.1:8765",
                    help="the bridge, which MUST be running in --project mode")
    a = ap.parse_args(argv)
    base = a.url.rstrip("/") + "/api/review"

    try:
        existing = _get(base + "/queues")
    except urllib.error.URLError as e:
        print("cannot reach the bridge at %s: %s" % (a.url, e), file=sys.stderr)
        print("start it with:  webui/.venv/Scripts/python.exe webui/run_server.py --project --port 8765",
              file=sys.stderr)
        return 2

    by_name = {q.get("name"): q for q in existing}
    made = []
    for spec in QUEUES:
        if spec["name"] in by_name:
            q = by_name[spec["name"]]
            print("kept    %-44s id=%s" % (spec["name"], q.get("id")))
            made.append(q)
            continue
        q = _post(base + "/queues", spec)
        q = q.get("queue", q)
        print("created %-44s id=%s" % (spec["name"], q.get("id")))
        made.append(q)

    print()
    print("%-44s %8s %8s %10s  %s" % ("queue", "total", "judged", "remaining", "writes"))
    for q in _get(base + "/queues"):
        print("%-44s %8s %8s %10s  %s" % (
            str(q.get("name"))[:44], q.get("total"), q.get("judged"),
            q.get("remaining"), q.get("writes_to")))

    counts = _get(base + "/counts")
    print()
    print("header 'N need you':", counts.get("need_you"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
