"""
make_events_grouping.py — the de-duplicated Library grouping round B cites (the researcher's Q1, 2026-10-26).

Items: ONE representative per event of `library_events.py` (the Q2 rule), over every Library recording except
  * Fig2A_dt0p1.csv (`reishi_10hz`, the sliding-import pieces: 67 % of g-05's members), and
  * the 50 Review-promoted entries (`source_kind = 'review'`, whole trains or regions; `library_events` already
    keeps them out of the events).
Representative: the event's container member when it has one (rule b); otherwise its longest part (a single member,
or the longest of a twin set or of a joined run). Not the union span: a grouping assignment names a `motif_member`
row and the Atlas and Family pages draw that member's own span, so a union span would need a new Library entry —
a write this job does not make. For a joined run the longest part covers most of the union (the partial pieces
sit 75-85 % inside it), so the shape clustered is the shape the page draws.

Method: Ward with g-05's method and parameters (basis shape-distance, cut 0.60, min_group 10, omit_d 0.5,
resample_length 256), on the same waveform the bridge's regroup job hands the engine (`library._native_waveform`,
the 64-point envelope in the stored unit), through the core `engine.run_grouping`. The tree is kept under
`DATA/derived/library/grouping_trees/` exactly as a project regroup keeps it, so the Grouping editor can draw it.

Stability ("wobble"): each item's 64 values get Gaussian noise with sd = p x that item's own standard deviation,
p = 1 % and 2 %, 5 seeded repeats each; the jittered set is regrouped with the same settings and compared with the
saved assignment by the adjusted Rand index (sklearn), over all items (an omitted item is its own singleton) and
over the items assigned in both. The cophenetic correlation of the Ward tree is computed too.

Writes (only with --apply): ONE `groupings` row and its `grouping_assignments`, through `webui.server.writes.write_human`
as the bridge's own save does (rule 5: a grouping is a human table), with the stability in `fit_summary_json`.
Before writing it takes a backup through the bridge's own route (POST http://127.0.0.1:8765/api/backups), and
refuses to write if that fails. Without --apply it computes everything and writes nothing to the database.

Run with the web UI's venv (it imports the bridge's waveform helper):
    webui/.venv/Scripts/python.exe scripts/thesis/make_events_grouping.py            # dry run
    webui/.venv/Scripts/python.exe scripts/thesis/make_events_grouping.py --apply    # backup, then save

Output: docs/thesis/data/library_events/events_grouping.json (what was saved, or would be).
Undo: DELETE FROM grouping_assignments WHERE grouping_id = <id>; DELETE FROM groupings WHERE id = <id>; and remove
the tree file the row names.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import sqlite3
import sys
import urllib.request

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import library_events as LE  # noqa: E402
from Working.library.grouping import engine as engine_mod  # noqa: E402
from Working.library.grouping import tree as tree_mod  # noqa: E402
from Working.library.grouping.methods import ward as ward_mod  # noqa: E402

DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite")
OUT = os.path.join(ROOT, "docs", "thesis", "data", "library_events", "events_grouping.json")
BRIDGE = "http://127.0.0.1:8765"
NAME = "thesis · events · de-duplicated (2026-10-26)"
G05 = 5
UNIT, BASIS, METHOD = "single_motifs", "shape-distance", "ward"
PARAMS = {"cut": 0.6, "min_group": 10, "omit_d": 0.5}
JITTERS, REPEATS = (0.01, 0.02), 5


def items_for(events, index, native_waveform):
    items, skipped = [], []
    for ev in events:
        rep = ev["rep"]
        meta = index["by_id"].get(int(rep["rec"]))
        if meta is None or meta.get("held_out"):
            skipped.append((ev["event_id"], "held out or unknown recording"))
            continue
        trace = native_waveform(index, rep["rec"], rep["s"], rep["e"], px=64)
        if not trace:
            skipped.append((ev["event_id"], "no samples on disk"))
            continue
        items.append({"member_ref": int(rep["mid"]), "content_hash": None, "values": trace, "fs": meta["fs"],
                      "recording_id": meta["recording_id"], "channel": meta["name"],
                      "start_idx": int(rep["s"]), "end_idx": int(rep["e"]), "event": ev})
    return items, skipped


def labels_of(result):
    """Family label per item, an omitted item as its own singleton."""
    return [a.family_label if a.family_label else f"__omitted_{i}" for i, a in enumerate(result.assignments)]


def stability(items, base_labels):
    from sklearn.metrics import adjusted_rand_score
    out = {"definition": ("Gaussian noise, sd = p x the item's own sd, added to each item's 64 envelope values; "
                          "regrouped with the same settings; adjusted Rand index vs the saved assignment, over all "
                          "items (omitted = own singleton) and over items assigned in both"),
           "repeats": REPEATS}
    base = np.asarray(base_labels, dtype=object)
    base_assigned = np.array([not str(x).startswith("__omitted_") for x in base])
    for p in JITTERS:
        rows = []
        for rep in range(REPEATS):
            rng = np.random.default_rng(1000 * int(round(p * 100)) + rep)
            jit = []
            for it in items:
                v = np.asarray(it["values"], dtype=float)
                sd = float(np.std(v)) or 1.0
                jit.append({**{k: it[k] for k in ("member_ref", "content_hash", "fs")},
                            "values": (v + rng.normal(0.0, p * sd, size=v.shape)).tolist()})
            res = engine_mod.run_grouping(jit, unit=UNIT, basis=BASIS, method=METHOD, params=PARAMS)
            lab = np.asarray(labels_of(res), dtype=object)
            both = base_assigned & np.array([not str(x).startswith("__omitted_") for x in lab])
            rows.append({"seed": 1000 * int(round(p * 100)) + rep, "families": res.n_families,
                         "ari_all": float(adjusted_rand_score(base, lab)),
                         "ari_assigned_in_both": float(adjusted_rand_score(base[both], lab[both])) if both.sum() > 1 else None,
                         "n_assigned_in_both": int(both.sum())})
        aris = [r["ari_all"] for r in rows]
        out[f"jitter_{int(round(p * 100))}pct"] = {
            "ari_all_min": round(min(aris), 3), "ari_all_max": round(max(aris), 3),
            "ari_all_mean": round(float(np.mean(aris)), 3), "runs": rows}
    return out


def cophenetic(items):
    from scipy.cluster.hierarchy import cophenet
    vec = ward_mod.shape_vectors([it["values"] for it in items])
    cond = ward_mod.condensed_distances(vec)
    c, _ = cophenet(ward_mod.ward_linkage(cond), cond)
    return float(c)


def bridge_backup():
    req = urllib.request.Request(BRIDGE + "/api/backups", data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="take a bridge backup, then save the grouping")
    ap.add_argument("--gap-s", type=float, default=LE.GAP_S)
    ap.add_argument("--no-stability", action="store_true")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    from webui.server import library as lib
    from webui.server import writes

    ro = LE.ro_connect(DB)
    try:
        members = LE.load_members(ro, G05)
        accepted = LE.accepted_member_ids(ro, members)
        index = lib._recordings_index(ro)
        events = [ev for ev in LE.build_events(members, args.gap_s) if ev["file"] != LE.FIG2A_FILE]
        items, skipped = items_for(events, index, lib._native_waveform)
        hashes = {r["id"]: r["content_hash"] for r in ro.execute("SELECT id, content_hash FROM motif_member")}
    finally:
        ro.close()
    for it in items:
        it["content_hash"] = hashes.get(it["member_ref"])
    print(f"{len(events)} events (Fig2A and review entries excluded) -> {len(items)} items; skipped {len(skipped)}")

    tree_root = os.path.join(ROOT, tree_mod.TREE_ROOT) if args.apply else None
    engine_items = [{k: v for k, v in it.items() if k != "event"} for it in items]
    result = engine_mod.run_grouping(engine_items, unit=UNIT, basis=BASIS, method=METHOD, params=PARAMS,
                                     tree_root=tree_root)
    labels = labels_of(result)
    print(f"families {result.n_families}, assigned {result.n_assigned}, omitted {result.n_omitted} "
          f"{dict(result.omitted_by_reason)}")

    # report
    fam_recs = collections.defaultdict(set)
    fam_members = collections.Counter()
    per_rec = collections.defaultdict(lambda: {"items": 0, "assigned": 0})
    for it, a in zip(items, result.assignments):
        f = it["event"]["file"]
        per_rec[f]["items"] += 1
        if a.family_label:
            per_rec[f]["assigned"] += 1
            fam_recs[a.family_label].add(f)
            fam_members[a.family_label] += 1
    acc_items = [(it, a) for it, a in zip(items, result.assignments)
                 if any(m["mid"] in accepted for m in it["event"]["members"])]
    report = {
        "name": NAME, "method": METHOD, "basis": BASIS, "params": PARAMS, "gap_s": args.gap_s,
        "items_rule": ("one representative per event of scripts/thesis/library_events.py: the container member, "
                       "else the longest part; Fig2A_dt0p1 and the Review-promoted entries excluded"),
        "events": len(events), "items": len(items), "skipped": skipped,
        "families": result.n_families, "assigned": result.n_assigned, "omitted": result.n_omitted,
        "omitted_by_reason": dict(result.omitted_by_reason),
        "members_per_recording": dict(per_rec),
        "families_with_2plus_recordings": sorted(f for f, r in fam_recs.items() if len(r) >= 2),
        "family_sizes": dict(sorted(fam_members.items(), key=lambda kv: -kv[1])),
        "accepted_events": {"items": len(acc_items), "assigned": sum(1 for _, a in acc_items if a.family_label),
                            "families": len({a.family_label for _, a in acc_items if a.family_label})},
        "cophenetic_correlation": round(cophenetic(engine_items), 4),
    }
    if not args.no_stability:
        report["stability"] = stability(engine_items, labels)
        print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "runs"}
                          for k, v in report["stability"].items() if k.startswith("jitter")}))
    print(f"cophenetic {report['cophenetic_correlation']}; families with 2+ recordings "
          f"{len(report['families_with_2plus_recordings'])}; per recording {dict(per_rec)}")

    if args.apply:
        backup = bridge_backup()
        if not backup or not os.path.isfile(str(backup.get("path") or "")):
            raise SystemExit(f"bridge backup did not report a file: {backup!r}; nothing written")
        report["backup"] = backup.get("path")
        print("backup", backup.get("path"))
        fit_summary = dict(result.fit_summary or {})
        fit_summary.update({"rows": len(items), "assigned": result.n_assigned,
                            "stability": report.get("stability"),
                            "cophenetic_correlation": report["cophenetic_correlation"],
                            "items_rule": report["items_rule"], "events_table": "docs/thesis/data/library_events/"})
        from webui.server import corpus
        conn = corpus.connect(DB)
        try:
            now = dt.datetime.now().isoformat(timespec="seconds")
            assigned = [a for a in result.assignments if a.family_label]
            gid = writes.write_human(conn, "groupings", {
                "name": NAME, "unit": UNIT, "basis": BASIS, "method": METHOD,
                "params_json": json.dumps(PARAMS, sort_keys=True), "cut": PARAMS["cut"],
                "filters_json": json.dumps({"items": report["items_rule"], "gap_s": args.gap_s,
                                            "excluded": ["Fig2A_dt0p1.csv (reishi_10hz)", "source_kind = 'review'"],
                                            "script": "scripts/thesis/make_events_grouping.py"}, sort_keys=True),
                "n_families": len({a.family_label for a in assigned}), "n_assigned": len(assigned),
                "n_omitted": len(result.assignments) - len(assigned),
                "recipe_hash": engine_mod.recipe_hash({"unit": UNIT, "basis": BASIS, "method": METHOD,
                                                       "params": PARAMS}),
                "created_at": now, "actor": "thesis script (make_events_grouping.py)",
                "fit_summary_json": json.dumps(engine_mod.json_safe(fit_summary), sort_keys=True),
                "tree_path": lib._stored_tree_path(result.tree["path"]) if result.tree else None,
                "tree_key": result.tree["key"] if result.tree else None,
            })
            for a in result.assignments:
                writes.write_human(conn, "grouping_assignments", {
                    "grouping_id": gid, "unit": UNIT, "member_ref": int(a.ref), "content_hash": a.content_hash,
                    "family_id": a.family_id, "family_label": a.family_label, "distance": a.distance,
                    "is_medoid": 1 if a.is_medoid else 0, "omit_reason": a.omit_reason})
            conn.commit()
        finally:
            conn.close()
        report["grouping_id"] = gid
        report["tree"] = result.tree and {"key": result.tree["key"], "path": lib._stored_tree_path(result.tree["path"])}
        print(f"saved grouping g-{gid:02d}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(engine_mod.json_safe(report), fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
