"""fixup-AD -- before (W's rule) -> after (AD's rule) on W's three families and on the M2_aug members.

Works on a COPY of W's sandbox database (`webui/runtime/20261004-184434`), made with SQLite's backup API into the
scratch directory given as argv[1]; the channel .npy files are only ever read (mmap). Nothing writes the real DATA.

Before = what W's rule makes of the same windows. W's bin is a pure function of (lag in seconds, r) -- |r| < 0.5
independent, |lag| <= 1 s artifact, <= 50 s propagation -- so it is re-derived exactly from the (lag, r) AD stores,
which are measured on the same windows by the same code. For the three families it is also read straight off W's
stored rows (and the two agree: printed). W's recurrence: a member in an artifact pair is out.

After = `matching.classify_family_across_channels` under the default AD rule, on every family of grouping g-05 that
has a member on M2_aug or on the three families, then `family_recurrence`. No human has judged anything, so
`excluding artifacts` = all; the line beside it says how many are flagged, and what the count would be if every flag
were confirmed.

Writes `measure_ad.json` and prints the tables the report carries.
"""
import json
import os
import sqlite3
import sys
import time
from collections import Counter, defaultdict

ROOT = "C:/Users/mmebr/Documents/CNN"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from Working import cross_channel as xc  # noqa: E402
from Working.library import matching  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = ROOT + "/webui/runtime/20261004-184434/annotations.sqlite"
FAMILIES = ("F-130", "F-119", "F-39")
GROUPING = 5
W_RULE = xc.CrossChannelRule(artifact_min_abs_r=0.5)        # W's three numbers; bin_for with no chance / floor


def w_bin(lag_s, r):
    return xc.bin_for(lag_s, r, W_RULE)


def copy_db(dst_dir):
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, "ad_measure.sqlite")
    if os.path.exists(dst):
        os.remove(dst)
    src = sqlite3.connect(f"file:{SRC}?mode=ro", uri=True)
    out = sqlite3.connect(dst)
    src.backup(out)
    src.close()
    out.close()
    from Working.database.schema import init_db
    return init_db(dst), dst


def family_members(conn, label=None, source_file=None):
    sql = ("SELECT ga.family_label fam, mm.id FROM grouping_assignments ga JOIN motif_member mm ON mm.id = ga.member_ref "
           "JOIN recordings r ON r.id = mm.recording_id WHERE ga.grouping_id = ? AND ga.family_id IS NOT NULL")
    args = [GROUPING]
    if label:
        sql += " AND ga.family_label = ?"
        args.append(label)
    if source_file:
        sql += " AND r.source_file = ?"
        args.append(source_file)
    out = defaultdict(list)
    for r in conn.execute(sql, args):
        out[r["fam"]].append(int(r["id"]))
    return out


def stored_rows(conn, ids):
    """Pairs (distinct) and co-occurrence rows touching `ids`, as stored now."""
    ids = set(ids)
    marks = ",".join("?" * len(ids))
    pairs = {}
    for e in conn.execute(f"SELECT * FROM motif_edge WHERE classification_bin IS NOT NULL AND member_a_id IN ({marks}) "
                          f"AND member_b_id IN ({marks})", (*ids, *ids)):
        k = frozenset((int(e["member_a_id"]), int(e["member_b_id"])))
        info = json.loads(e["classification_json"]) if e["classification_json"] else {}
        pairs[k] = {"bin": e["classification_bin"], "lag_s": info.get("lag_s"), "r": e["waveform_correlation"],
                    "info": info}
    co = []
    for r in conn.execute(f"SELECT * FROM motif_member_cooccurrence WHERE member_id IN ({marks})", tuple(ids)):
        info = json.loads(r["classification_json"]) if r["classification_json"] else {}
        co.append({"member": int(r["member_id"]), "bin": r["classification_bin"], "lag_s": info.get("lag_s"),
                   "r": r["waveform_correlation"], "info": info})
    return pairs, co


def w_recurrence(ids, pairs):
    """W's definition (commit 4cbfef9): a member in an artifact pair is out; propagation once by union-find."""
    art = {m for k, p in pairs.items() if p["bin"] == xc.ARTIFACT for m in k}
    kept = [m for m in ids if m not in art]
    parent = {m: m for m in kept}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x
    for k, p in pairs.items():
        if p["bin"] == xc.PROPAGATION:
            a, b = tuple(k)
            if a in parent and b in parent:
                parent[find(b)] = find(a)
    return {"all": len(ids), "excluding_artifacts": len(kept), "propagation_once": len({find(m) for m in kept})}


def summarise_before(ids, pairs, co, from_stored_bin=True):
    def b(p):
        return p["bin"] if from_stored_bin else (w_bin(p["lag_s"], p["r"]) if p["lag_s"] is not None else p["bin"])
    pb = Counter(b(p) for p in pairs.values())
    wb = Counter(b(c) for c in co if b(c) in (xc.ARTIFACT, xc.PROPAGATION))
    rebinned = {k: dict(p, bin=b(p)) for k, p in pairs.items()}
    flagged = {m for k, p in rebinned.items() if p["bin"] == xc.ARTIFACT for m in k}
    flagged |= {c["member"] for c in co if b(c) == xc.ARTIFACT}
    return {"pairs": {k: pb.get(k, 0) for k in xc.BINS}, "withoutMember": dict(wb),
            "flagged_q40d": len(flagged), "recurrence": w_recurrence(sorted(ids), rebinned)}


def summarise_after(conn, ids, out):
    rec = matching.family_recurrence(conn, ids)
    flagged = [m for m, st in rec["members"].items() if st["flagged"]]
    # the count if a human confirmed every flag (and the member twins went with them)
    pairs, co = stored_rows(conn, ids)
    twins = {m for k, p in pairs.items() if p["bin"] == xc.ARTIFACT and (p["info"].get("chance") or {}).get("beats")
             for m in k}
    gone = set(flagged) | twins
    return {"pairs": {k: out["counts"][k] for k in xc.BINS}, "withoutMember": out["counts"]["withoutMember"],
            "tooShort": rec["tooShort"], "flagged": rec["flagged"], "flaggedIds": sorted(flagged),
            "recurrence": {k: rec[k] for k in ("all", "excluding_artifacts", "propagation_once")},
            "ifEveryFlagConfirmed": len(ids) - len(gone)}


def main():
    scratch = sys.argv[1]
    conn, path = copy_db(scratch)
    t0 = time.time()
    result = {"source": SRC, "copy": path, "rule": xc.DEFAULT_RULE.as_dict(), "families": {}, "m2_aug": {}}

    # ── W's three families: before straight off W's stored rows ──
    fams = {f: family_members(conn, f)[f] for f in FAMILIES}
    before = {}
    for f, ids in fams.items():
        pairs, co = stored_rows(conn, ids)
        before[f] = summarise_before(ids, pairs, co, from_stored_bin=True)

    # ── after: classify every g-05 family touching M2_aug, plus the three ──
    m2 = family_members(conn, source_file="M2_aug_concat_fs1.mat")
    targets = sorted(set(m2) | set(FAMILIES))
    full = {}
    timing = {}
    for f in targets:
        ids = family_members(conn, f)[f]
        t = time.time()
        full[f] = (ids, matching.classify_family_across_channels(conn, ids, exclude_source_files=("M4_aug_concat_fs1.mat",)))
        timing[f] = time.time() - t
    result["timing_s"] = {"total": time.time() - t0, "slowest": sorted(timing.items(), key=lambda kv: -kv[1])[:5]}

    for f in FAMILIES:
        ids, out = full[f]
        pairs, co = stored_rows(conn, ids)
        result["families"][f] = {
            "members": len(ids),
            "before": before[f],
            "before_rederived": summarise_before(ids, pairs, co, from_stored_bin=False),
            "after": summarise_after(conn, ids, out),
            "by_dataset": {},
        }

    # ── the M2_aug members, every family that has one ──
    m2_ids = sorted(m for ids in m2.values() for m in ids)
    agg_b, agg_a = Counter(), Counter()
    wb_b, wb_a = Counter(), Counter()
    flag_b, flag_a, short = set(), set(), set()
    rec_b, rec_a = Counter(), Counter()
    for f in sorted(m2):
        ids, out = full[f]
        pairs, co = stored_rows(conn, ids)
        m2set = set(m2[f])
        # rows that touch an M2_aug member
        pairs_m2 = {k: p for k, p in pairs.items() if k & m2set}
        co_m2 = [c for c in co if c["member"] in m2set]
        sb = summarise_before(m2[f], pairs_m2, co_m2, from_stored_bin=False)
        for k, v in sb["pairs"].items():
            agg_b[k] += v
        for k, v in sb["withoutMember"].items():
            wb_b[k] += v
        for k, p in pairs_m2.items():
            agg_a[p["bin"]] += 1
            if w_bin(p["lag_s"], p["r"]) == xc.ARTIFACT if p["lag_s"] is not None else False:
                flag_b |= set(k) & m2set
        for c in co_m2:
            if c["bin"] in (xc.ARTIFACT, xc.PROPAGATION):
                wb_a[c["bin"]] += 1
            if c["lag_s"] is not None and w_bin(c["lag_s"], c["r"]) == xc.ARTIFACT:
                flag_b.add(c["member"])
        rec = matching.family_recurrence(conn, ids)
        for m in m2set:
            st = rec["members"][m]
            flag_a |= {m} if st["flagged"] else set()
            short |= {m} if st["tooShort"] else set()
        rb = w_recurrence(sorted(m2set), {k: dict(p, bin=w_bin(p["lag_s"], p["r"]) if p["lag_s"] is not None else p["bin"])
                                          for k, p in pairs_m2.items()})
        for k, v in rb.items():
            rec_b[k] += v
        ra = matching.family_recurrence(conn, sorted(m2set))
        for k in ("all", "excluding_artifacts", "propagation_once"):
            rec_a[k] += ra[k]
    result["m2_aug"] = {
        "members": len(m2_ids), "families": len(m2),
        "before": {"pairs": dict(agg_b), "withoutMember": dict(wb_b), "flagged_q40d": len(flag_b),
                   "recurrence_summed_per_family": dict(rec_b),
                   "note": "W's bins on the same windows; members W could classify but AD calls too short are not "
                           "re-measured (no AD row), so their W bins are missing here"},
        "after": {"pairs": dict(agg_a), "withoutMember": dict(wb_a), "flagged": len(flag_a), "tooShort": len(short),
                  "flaggedIds": sorted(flag_a), "recurrence_summed_per_family": dict(rec_a)},
    }
    json.dump(result, open(os.path.join(HERE, "measure_ad.json"), "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in result.items() if k != "families"}, indent=1, default=str)[:4000])
    for f, d in result["families"].items():
        print(f, json.dumps(d, default=str))


if __name__ == "__main__":
    main()
