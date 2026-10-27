"""
library_events.py — turn the Library's partial motifs into events (the researcher's Q2 rule, 2026-10-26).

Why: one dive is often stored as separate fall / bottom / rise members (and the same M2_aug event imported twice, from
`drop_motifs5` and `drop_motifs10`), so a member count is not an event count and one event can sit in three g-05
families. This script applies one rule, per recording channel (a `recordings` row is one channel), and writes the
events table that round B cites.

The rule (spans half-open [start, end), lengths in samples):

  (a) twins     two members whose overlap is >= 90 % of BOTH spans are one unit (union-find, so chains of twins
                collapse together). The unit's span is the union; its longest member stands for it.
  (b) container a unit is a container when another unit lies >= 90 % inside it and it is >= 1.5x that unit's length
                (the fragment audit's "nested" rule). Each nested unit is a PART of the longest container that holds
                it, resolved upward, so a container inside a bigger container is itself a part of the bigger one.
                A top-level container and all its parts are ONE event.
  (c) join      the remaining free units (neither container nor part) are joined when they partially overlap by
                >= 50 % of the shorter span, or abut: one ends within +-GAP_S seconds of where the next starts
                (default 3 s: 3 samples at 1 Hz, 30 at 10 Hz). Why 50 % and not "any overlap": the drop-motif stores
                pad each event, so CONSECUTIVE drops of a train overlap by 10-20 % of a span; joining on any overlap
                made one 93-minute M2_aug train (CH1 at 890,627 s) a single 111-part "event". Pieces of one dive
                overlap their whole far more (the 40-60-sample partials sit 75-85 % inside it). Joining never goes through
                a container: containers and their parts take no part in (c), so a chain of abutting pieces cannot
                walk into a long member and swallow everything it holds (the 104-part event the researcher saw).
                Free units that touch a container are counted, not merged.

Review-promoted entries (`motif_entry.source_kind = 'review'`, the 50 "Review containers": whole trains or regions,
up to ~9 h, promoted as single entries) are NOT events here: they take no part in (a)-(c) and are listed in
`summary.json` as regions with the number of events inside each. The researcher dropped them from the grouping input
for the same reason.

Fig2A_dt0p1 (`reishi_10hz`, the sliding-import pieces) goes through the same rule but is reported separately.

g-05 family labels (grouping 5, Ward cut 0.60) are attached to every part. Accepted members are the Library verdicts
(`annotations.source = 'library_review'`, verdict `interesting`) matched to members by (recording, start, end).

Read-only: the database is opened with `mode=ro`; channel arrays are not read. Writes
docs/thesis/data/library_events/{events.csv, summary.json}.

    "/c/ProgramData/anaconda3/python.exe" scripts/thesis/library_events.py [--gap-s 3] [--grouping 5]

g-11's table (2026-10-27): every ACTIVE recording, never M4 or L_R, written beside g-10's rather than over it:
    "/c/ProgramData/anaconda3/python.exe" scripts/thesis/library_events.py --active-only --out docs/thesis/data/library_events_all_active

`build_events` is imported by `make_events_grouping.py`, so the grouping and the table use the same events.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import sqlite3
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite")
OUT = os.path.join(ROOT, "docs", "thesis", "data", "library_events")
HELD_OUT_FILE = "M4_aug_concat_fs1.mat"
FIG2A_FILE = "Fig2A_dt0p1.csv"

TWIN = 0.90          # (a) overlap >= 90 % of both spans
NEST_IN = 0.90       # (b) >= 90 % of the part inside the container ...
NEST_RATIO = 1.5     # ... and the container >= 1.5x longer
GAP_S = 3.0          # (c) abutting gap, seconds
JOIN_OVERLAP = 0.50  # (c) a partial overlap joins at >= 50 % of the shorter span
GAP_SWEEP = (0.0, 1.0, 2.0, 3.0, 5.0, 10.0)

RULE_TEXT = {
    "twins": f"(a) members overlapping >= {TWIN:.0%} of both spans collapsed into one unit",
    "container": f"(b) a unit holding others (>= {NEST_IN:.0%} inside, container >= {NEST_RATIO}x longer) is one event "
                 "and lists them as parts",
    "joined": (f"(c) free units joined when they overlap by >= {JOIN_OVERLAP:.0%} of the shorter span or abut "
               "(end-to-start within +-g); never through a container"),
}


def ro_connect(db=DB):
    conn = sqlite3.connect("file:" + db.replace("\\", "/") + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_members(conn, grouping_id=5):
    """Every Library member with what the rule and the report need."""
    rows = conn.execute("""
        SELECT m.id AS mid, m.entry_id, m.recording_id AS rec, m.start_idx AS s, m.end_idx AS e,
               COALESCE(e.fs, r.fs) AS fs, e.source_kind AS src, COALESCE(e.source_store, '') AS store,
               r.source_file AS file, r.channel AS ch, COALESCE(r.active, 1) AS active,
               (SELECT v.value FROM motif_entry_tags t JOIN tag_vocabulary v ON v.id = t.tag_id
                 WHERE t.entry_id = e.id AND v.category = 'corpus' LIMIT 1) AS corpus,
               ga.family_label AS fam, ga.omit_reason AS omit
          FROM motif_member m JOIN motif_entry e ON e.id = m.entry_id
          JOIN recordings r ON r.id = m.recording_id
          LEFT JOIN grouping_assignments ga ON ga.member_ref = m.id AND ga.grouping_id = ? AND ga.unit = 'single_motifs'
         ORDER BY m.id""", (int(grouping_id),)).fetchall()
    out = []
    for r in rows:
        m = dict(r)
        if m["file"] == HELD_OUT_FILE:
            continue
        m["s"], m["e"] = int(m["s"]), int(m["e"])
        m["fs"] = float(m["fs"] or 1.0)
        m["corpus"] = m["corpus"] or m["src"]
        out.append(m)
    return out


def accepted_member_ids(conn, members):
    """Members a person accepted: a Library verdict (`annotations.source = 'library_review'`, `interesting`) on the
    member's span, or (2026-10-27) the member's revision-1 detection carrying an own Review verdict
    (`adjudications.carried_from IS NULL`, newest own row `interesting` or `seed`) — the blind-queue events promoted
    verdict-free by `promote_blind_accepted.py`."""
    key = {(m["rec"], m["s"], m["e"]): m["mid"] for m in members}
    ids = set()
    for r in conn.execute("SELECT recording_id, start_idx, end_idx FROM annotations "
                          "WHERE source = 'library_review' AND verdict = 'interesting' AND deleted_at IS NULL"):
        k = (r[0], r[1], r[2])
        if k in key:
            ids.add(key[k])
    have = {m["mid"] for m in members}
    for r in conn.execute("""SELECT rv.member_id,
                                    (SELECT a.verdict FROM adjudications a WHERE a.detection_id = rv.detection_id
                                       AND a.carried_from IS NULL ORDER BY a.id DESC LIMIT 1) v
                               FROM motif_member_revision rv WHERE rv.revision = 1 AND rv.detection_id IS NOT NULL"""):
        if r[0] in have and r[1] in ("interesting", "seed"):
            ids.add(r[0])
    return ids


#: Recordings no all-active analysis reads, whatever their `active` flag (2026-10-27): the held-out exam recording
#: and L_R (a humidity actuator's PID oscillation contaminates it).
ALWAYS_EXCLUDED = (HELD_OUT_FILE, "L_R_Aug_26_PD_raw.mat")


def active_only(members):
    """`members` on active recordings, minus `ALWAYS_EXCLUDED`."""
    return [m for m in members if int(m.get("active", 1) or 0) == 1 and m["file"] not in ALWAYS_EXCLUDED]


class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, i):
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def _inter(a, b):
    return min(a[1], b[1]) - max(a[0], b[0])


def _events_on_channel(ms, gap_samples):
    """The rule on one channel's members (review entries already removed). Returns a list of event dicts."""
    ms = sorted(ms, key=lambda m: (m["s"], -(m["e"] - m["s"]), m["mid"]))
    n = len(ms)
    # (a) twins
    uf = _UF(n)
    for i in range(n):
        a = ms[i]
        la = a["e"] - a["s"]
        for j in range(i + 1, n):
            b = ms[j]
            if b["s"] >= a["e"]:
                break
            lb = b["e"] - b["s"]
            x = _inter((a["s"], a["e"]), (b["s"], b["e"]))
            if x >= TWIN * la and x >= TWIN * lb:
                uf.union(i, j)
    groups = collections.defaultdict(list)
    for i in range(n):
        groups[uf.find(i)].append(ms[i])
    units = []
    for g in groups.values():
        rep = max(g, key=lambda m: (m["e"] - m["s"], -m["mid"]))
        units.append({"members": g, "rep": rep, "s": min(m["s"] for m in g), "e": max(m["e"] for m in g)})
    units.sort(key=lambda u: (u["s"], -(u["e"] - u["s"])))
    L = [u["e"] - u["s"] for u in units]
    # (b) containment: owner = the longest unit that holds this one
    owner = [None] * len(units)
    for i, u in enumerate(units):
        best = None
        for j, c in enumerate(units):
            if j == i or c["s"] >= u["e"]:
                if c["s"] >= u["e"]:
                    break
                continue
            if L[j] >= NEST_RATIO * L[i] and _inter((u["s"], u["e"]), (c["s"], c["e"])) >= NEST_IN * L[i]:
                if best is None or L[j] > L[best]:
                    best = j
        owner[i] = best

    def root(i):
        seen = set()
        while owner[i] is not None and i not in seen:
            seen.add(i)
            i = owner[i]
        return i

    is_container = [False] * len(units)
    for i, o in enumerate(owner):
        if o is not None:
            is_container[root(i)] = True
    parts_of = collections.defaultdict(list)
    for i, o in enumerate(owner):
        if o is not None:
            parts_of[root(i)].append(i)
    free = [i for i in range(len(units)) if owner[i] is None and not is_container[i]]
    containers = [i for i in range(len(units)) if is_container[i]]

    events = []
    for c in containers:
        idx = [c] + sorted(parts_of[c])
        events.append({"units": [units[k] for k in idx], "container": units[c], "rule": "container"})
    # (c) join free units only: a partial overlap of >= JOIN_OVERLAP of the shorter span, or an abutment
    # (|gap| <= g: a gap of at most g, or an overlap of at most g)
    fuf = _UF(len(free))
    order = sorted(range(len(free)), key=lambda k: units[free[k]]["s"])
    for x in range(len(order)):
        a = units[free[order[x]]]
        for y in range(x + 1, len(order)):
            b = units[free[order[y]]]
            if b["s"] - a["e"] > gap_samples:
                break
            x_ab = _inter((a["s"], a["e"]), (b["s"], b["e"]))
            shorter = min(a["e"] - a["s"], b["e"] - b["s"])
            abut = abs(b["s"] - a["e"]) <= gap_samples
            if abut or x_ab >= JOIN_OVERLAP * shorter:
                fuf.union(order[x], order[y])
    fg = collections.defaultdict(list)
    for k in range(len(free)):
        fg[fuf.find(k)].append(units[free[k]])
    for us in fg.values():
        events.append({"units": sorted(us, key=lambda u: u["s"]), "container": None,
                       "rule": "joined" if len(us) > 1 else "single"})
    # touching a container (overlap or within the gap) without being merged
    cspans = [(units[c]["s"], units[c]["e"]) for c in containers]
    for ev in events:
        ev["touches_container"] = False
        if ev["container"] is None:
            s, e = min(u["s"] for u in ev["units"]), max(u["e"] for u in ev["units"])
            ev["touches_container"] = any(cs - e <= gap_samples and s - ce <= gap_samples for cs, ce in cspans)
    return events


def build_events(members, gap_s=GAP_S):
    """Events over `members` (dicts from `load_members`), review entries excluded. Each event dict carries
    `members` (all, twins and parts included), `rep` (representative member), `rule`, span and families."""
    by = collections.defaultdict(list)
    for m in members:
        if m["src"] == "review":
            continue
        by[m["rec"]].append(m)
    out = []
    for rec in sorted(by):
        ms = by[rec]
        fs = ms[0]["fs"]
        for ev in _events_on_channel(ms, gap_s * fs):
            mem = [m for u in ev["units"] for m in u["members"]]
            if ev["container"] is not None:
                rep, rep_why = ev["container"]["rep"], "container"
            else:
                longest = max(ev["units"], key=lambda u: (u["rep"]["e"] - u["rep"]["s"], -u["rep"]["mid"]))
                rep = longest["rep"]
                rep_why = "single" if len(ev["units"]) == 1 else "longest part"
            rules = []
            if any(len(u["members"]) > 1 for u in ev["units"]):
                rules.append("twins")
            if ev["rule"] in ("container", "joined"):
                rules.append(ev["rule"])
            fams = sorted({m["fam"] for m in mem if m["fam"]})
            out.append({
                "rec": rec, "file": ms[0]["file"], "ch": ms[0]["ch"], "fs": fs,
                "s": min(m["s"] for m in mem), "e": max(m["e"] for m in mem),
                "members": sorted(mem, key=lambda m: (m["s"], m["mid"])), "n_units": len(ev["units"]),
                "rep": rep, "rep_why": rep_why, "rule": "+".join(rules) or "single",
                "families": fams, "corpora": sorted({str(m["corpus"]) for m in mem}),
                "touches_container": ev["touches_container"],
            })
    out.sort(key=lambda ev: (ev["file"], ev["rec"], ev["s"]))
    for i, ev in enumerate(out, 1):
        ev["event_id"] = f"EV-{i:05d}"
    return out


def review_regions(members, events):
    """The Review-promoted entries as regions: how many events lie >= 90 % inside each."""
    by = collections.defaultdict(list)
    for ev in events:
        by[ev["rec"]].append(ev)
    rows = []
    for m in members:
        if m["src"] != "review":
            continue
        inside = [ev for ev in by.get(m["rec"], [])
                  if _inter((m["s"], m["e"]), (ev["s"], ev["e"])) >= NEST_IN * (ev["e"] - ev["s"])]
        rows.append({"member_id": m["mid"], "entry_id": m["entry_id"], "file": m["file"], "recording_id": m["rec"],
                     "start_s": round(m["s"] / m["fs"], 1), "end_s": round(m["e"] / m["fs"], 1),
                     "length_s": round((m["e"] - m["s"]) / m["fs"], 1), "events_inside": len(inside),
                     "members_inside": sum(len(ev["members"]) for ev in inside)})
    return rows


def _dist(values):
    c = collections.Counter(values)
    keys = sorted(c)
    return {str(k): c[k] for k in keys}


def _block(events, accepted):
    n_members = sum(len(ev["members"]) for ev in events)
    multi = [ev for ev in events if len(ev["families"]) >= 2]
    acc_m = [m for ev in events for m in ev["members"] if m["mid"] in accepted]
    acc_ev = [ev for ev in events if any(m["mid"] in accepted for m in ev["members"])]
    parts = [len(ev["members"]) for ev in events]
    bucket = lambda k: str(k) if k <= 5 else ("6-10" if k <= 10 else ("11-20" if k <= 20 else ">20"))
    return {
        "members": n_members, "events": len(events),
        "members_per_event_mean": round(n_members / len(events), 3) if events else None,
        "parts_per_event": {b: sum(1 for p in parts if bucket(p) == b)
                            for b in ("1", "2", "3", "4", "5", "6-10", "11-20", ">20")},
        "max_parts": max(parts) if parts else 0,
        "by_rule": dict(collections.Counter(ev["rule"] for ev in events)),
        "events_spanning_2plus_g05_families": len(multi),
        "events_with_any_g05_family": sum(1 for ev in events if ev["families"]),
        "events_spanning_2plus_g05_families_share_of_familied": (
            round(len(multi) / max(1, sum(1 for ev in events if ev["families"])), 3)),
        "events_touching_a_container_unmerged": sum(1 for ev in events if ev["touches_container"]),
        "accepted": {"members": len(acc_m), "events": len(acc_ev),
                     "g05_families_of_accepted_members": len({m["fam"] for m in acc_m if m["fam"]}),
                     "g05_families_of_accepted_events": len({f for ev in acc_ev for f in ev["families"]}),
                     "accepted_events_spanning_2plus_g05_families": sum(1 for ev in acc_ev if len(ev["families"]) >= 2)},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=DB)
    ap.add_argument("--grouping", type=int, default=5)
    ap.add_argument("--gap-s", type=float, default=GAP_S)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--active-only", action="store_true",
                    help="only members on active recordings, never M4 or L_R (g-11's input); use with --out")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    conn = ro_connect(args.db)
    try:
        members = load_members(conn, args.grouping)
        if args.active_only:
            members = active_only(members)
        accepted = accepted_member_ids(conn, members)
        n_verdicts = conn.execute("SELECT verdict, COUNT(*) FROM annotations WHERE source = 'library_review' "
                                  "AND deleted_at IS NULL GROUP BY verdict").fetchall()
    finally:
        conn.close()

    events = build_events(members, args.gap_s)
    regions = review_regions(members, events)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "events.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["event_id", "recording", "recording_id", "channel", "fs", "start_idx", "end_idx", "start_s",
                    "end_s", "length_s", "n_parts", "parts", "g05_families", "n_g05_families", "rule",
                    "representative_member", "representative_why", "corpus", "fig2a", "accepted_parts",
                    "touches_container"])
        for ev in events:
            parts = ";".join(f"{m['mid']}:{m['fam'] or '-'}" for m in ev["members"])
            w.writerow([ev["event_id"], ev["file"], ev["rec"], ev["ch"], ev["fs"], ev["s"], ev["e"],
                        round(ev["s"] / ev["fs"], 2), round(ev["e"] / ev["fs"], 2),
                        round((ev["e"] - ev["s"]) / ev["fs"], 2), len(ev["members"]), parts,
                        ";".join(ev["families"]), len(ev["families"]), ev["rule"], ev["rep"]["mid"], ev["rep_why"],
                        ";".join(ev["corpora"]), int(ev["file"] == FIG2A_FILE),
                        sum(1 for m in ev["members"] if m["mid"] in accepted), int(ev["touches_container"])])

    fig = [ev for ev in events if ev["file"] == FIG2A_FILE]
    rest = [ev for ev in events if ev["file"] != FIG2A_FILE]
    per_rec = collections.defaultdict(lambda: {"members": 0, "events": 0, "channels": set()})
    for ev in events:
        r = per_rec[ev["file"]]
        r["members"] += len(ev["members"])
        r["events"] += 1
        r["channels"].add(ev["rec"])
    sweep = {}
    for g in GAP_SWEEP:
        evs = build_events(members, g)
        sweep[str(g)] = {"all": len(evs), "without_fig2a": sum(1 for ev in evs if ev["file"] != FIG2A_FILE),
                         "max_parts": max(len(ev["members"]) for ev in evs)}
    summary = {
        "generated_by": "scripts/thesis/library_events.py",
        "database": "DATA/db/annotations.sqlite (mode=ro)",
        "g05_grouping_id": args.grouping,
        "active_only": bool(args.active_only),
        "rule": {**RULE_TEXT, "gap_s": args.gap_s, "twin_overlap": TWIN, "nest_inside": NEST_IN,
                 "nest_ratio": NEST_RATIO,
                 "review_entries": "the Review-promoted entries (source_kind 'review') are regions, not events: they "
                                   "take no part in (a)-(c); see review_regions"},
        "library_members": len(members),
        "review_entries_excluded": len(regions),
        "library_review_verdicts": {r[0]: r[1] for r in n_verdicts},
        "accepted_members_matched": len(accepted),
        "per_recording": {k: {"members": v["members"], "events": v["events"], "channels": len(v["channels"])}
                          for k, v in sorted(per_rec.items(), key=lambda kv: -kv[1]["members"])},
        "all": _block(events, accepted),
        "without_fig2a": _block(rest, accepted),
        "fig2a_only": _block(fig, accepted),
        "gap_sensitivity_events": sweep,
        "review_regions": regions,
    }
    with open(os.path.join(args.out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)
    print(json.dumps({k: summary[k] for k in ("library_members", "review_entries_excluded", "per_recording",
                                              "gap_sensitivity_events")}, indent=1))
    for k in ("all", "without_fig2a", "fig2a_only"):
        print(k, json.dumps(summary[k]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
