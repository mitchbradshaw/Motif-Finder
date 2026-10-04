"""AE measurement: what the floor hides per store / dataset, families before -> after, judged before -> after,
the rose reference — on a backfilled COPY of the real database. Writes JSON to stdout."""
import json
import os
import sqlite3
import sys
import time

ROOT = r"C:\Users\mmebr\Documents\CNN"
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from Working.library import rose_reference as RR  # noqa: E402
from Working.library import verdicts as V  # noqa: E402
from Working.library import view_filter as VF  # noqa: E402

db = sys.argv[1]
c = sqlite3.connect(db)
c.row_factory = sqlite3.Row
out = {}
for gid, in c.execute("SELECT id FROM groupings WHERE unit = 'single_motifs' ORDER BY id").fetchall():
    rows = [dict(r) for r in c.execute(
        "SELECT ga.family_label, mm.id AS member_id, mm.entry_id, mm.recording_id, mm.start_idx, mm.end_idx "
        "FROM grouping_assignments ga JOIN motif_member mm ON mm.id = ga.member_ref "
        "WHERE ga.grouping_id = ? AND ga.unit = 'single_motifs' AND ga.family_id IS NOT NULL", (gid,))]
    fams = {}
    for r in rows:
        fams.setdefault(r["family_label"], []).append(r["member_id"])
    t = time.time()
    res = VF.filter_members(c, rows, VF.ViewFilter(), families=fams)
    t_filter = time.time() - t
    kept_fams = {r["family_label"] for r in rows if r["member_id"] in res["kept"]}
    t = time.time()
    ver = V.member_verdicts(c, rows)
    t_ver = time.time() - t
    exact = 0
    ann = {(r[0], r[1], r[2]) for r in c.execute("SELECT recording_id, start_idx, end_idx FROM annotations")}
    for r in rows:
        exact += (r["recording_id"], r["start_idx"], r["end_idx"]) in ann
    by_rule = {}
    for v in ver.values():
        if v["judged"]:
            by_rule[v["by"]] = by_rule.get(v["by"], 0) + 1
    # with the floor and filters, Q22's example
    f2 = VF.filter_members(c, rows, VF.ViewFilter(fall_min_s=10, fall_max_s=300, pure_only=True), families=fams,
                           measures=res["measures"])
    out[f"g-{gid:02d}"] = {
        "members": len(rows), "families_before": len(fams), "families_after": len(kept_fams),
        "families_all_sub_floor": len(res["report"]["families_all_sub_floor"]),
        "report": {k: res["report"][k] for k in ("floor", "unmeasured", "shown", "n")},
        "judged_exact_span": exact, "judged_resolver": sum(v["judged"] for v in ver.values()), "judged_by": by_rule,
        "accepted": len(V.accepted(ver)),
        "q22_example": {"shown": f2["report"]["shown"], "fall": f2["report"]["fall"], "pure": f2["report"]["pure"],
                        "families_after": len({r["family_label"] for r in rows if r["member_id"] in f2["kept"]})},
        "seconds": {"filter": round(t_filter, 2), "verdicts": round(t_ver, 2)},
    }
# every member, not only a grouping's
allm = [dict(r) for r in c.execute("SELECT id AS member_id, entry_id, recording_id FROM motif_member")]
r = VF.filter_members(c, allm, VF.ViewFilter())
out["all_members"] = {k: r["report"][k] for k in ("floor", "unmeasured", "shown", "n")}
t = time.time()
out["rose"] = RR.compute(c)
out["rose"]["seconds"] = round(time.time() - t, 2)
print(json.dumps(out, indent=1, default=str))
