"""Library fragment / duplicate audit — read-only.

Measures how far the Library's members are pieces or copies of one another, so a family
count can be read as a count of distinct events (docs/rq_roundA_2/findings/
library-fragments-and-duplicates.md, first run 2026-10-17). Run it again whenever the
Library is re-imported or members are added.

    python scripts/library_fragment_audit.py                     # grouping 5, the real database
    python scripts/library_fragment_audit.py --grouping 4 --db path/to/annotations.sqlite

Read-only by construction: the database is opened with `mode=ro` and copied with SQLite's
backup API into a temporary file before any query (so a running bridge's WAL is never
touched), and channel arrays are memory-mapped read-only. Writes nothing in the repo.

Definitions (all on one recording + channel, spans half-open [start, end)):
  twin      another member overlaps >= 90 % of BOTH spans (the same event imported twice)
  nested    >= 90 % of the member lies inside a member >= 1.5x longer
  piece     the member overlaps >= 20 % of the shorter span of a member in ANOTHER family
            (and is neither twin nor nested of it): a fragment of a longer event
  distinct  members merged (union-find) when they overlap >= 50 % of the shorter span;
            each merged group is one event
  shape     a rough rule on the raw slice, for orientation only: net change over the range
            (first and last 10 % means) <= -0.6 drop, >= 0.6 rise; else a dip/bump of
            >= 0.4 of the range in the interior is trough(V)/peak(^); else mixed
"""
from __future__ import annotations

import argparse
import collections
import os
import sqlite3
import sys
import tempfile

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(REPO, "DATA", "db", "annotations.sqlite")


def snapshot(db_path: str) -> str:
    src = sqlite3.connect("file:" + db_path.replace("\\", "/") + "?mode=ro", uri=True)
    fd, tmp = tempfile.mkstemp(suffix=".sqlite", prefix="library_audit_")
    os.close(fd)
    dst = sqlite3.connect(tmp)
    src.backup(dst)
    dst.close()
    src.close()
    return tmp


def load_members(conn, grouping_id):
    rows = conn.execute("""
        SELECT m.id, m.recording_id, m.channel, m.start_idx, m.end_idx, COALESCE(e.fs, r.fs), e.source_kind,
               COALESCE(e.source_store, ''), r.npy_path, r.source_file,
               (SELECT v.value FROM motif_entry_tags t JOIN tag_vocabulary v ON v.id = t.tag_id
                 WHERE t.entry_id = e.id AND v.category = 'corpus'),
               ga.family_id
        FROM motif_member m JOIN motif_entry e ON e.id = m.entry_id
        LEFT JOIN recordings r ON r.id = m.recording_id
        LEFT JOIN grouping_assignments ga ON ga.member_ref = m.id AND ga.grouping_id = ? AND ga.unit = 'single_motifs'
    """, (grouping_id,)).fetchall()
    keys = ("mid", "rec", "ch", "s", "e", "fs", "src", "store", "npy", "file", "corpus", "fam")
    out = []
    for r in rows:
        m = dict(zip(keys, r))
        m["corpus"] = m["corpus"] or m["src"]          # review / annotation entries carry no corpus tag
        out.append(m)
    return out


def shape_of(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 4:
        return None
    rng = x.max() - x.min()
    if rng == 0:
        return "flat"
    k = max(1, len(x) // 10)
    a, b = x[:k].mean(), x[-k:].mean()
    net = (b - a) / rng
    dip, bump = (min(a, b) - x.min()) / rng, (x.max() - max(a, b)) / rng
    pmin, pmax = np.argmin(x) / len(x), np.argmax(x) / len(x)
    if net <= -0.6:
        return "drop"
    if net >= 0.6:
        return "rise"
    if dip >= 0.4 and 0.1 < pmin < 0.9 and dip >= bump:
        return "trough(V)"
    if bump >= 0.4 and 0.1 < pmax < 0.9:
        return "peak(^)"
    return "mixed"


def classify(members):
    """Set twin / nested / piece flags in place (O(n^2) per channel; channels hold <= ~700 members)."""
    by = collections.defaultdict(list)
    for m in members:
        by[(m["rec"], m["ch"])].append(m)
        m.update(twin=False, nested=False, piece=False)
    for v in by.values():
        v.sort(key=lambda m: m["s"])
        for a in v:
            la = a["e"] - a["s"]
            for b in v:
                if b is a:
                    continue
                inter = min(a["e"], b["e"]) - max(a["s"], b["s"])
                if inter <= 0:
                    continue
                lb = b["e"] - b["s"]
                if inter >= 0.9 * la and inter >= 0.9 * lb:
                    a["twin"] = True
                elif lb >= 1.5 * la and inter >= 0.9 * la:
                    a["nested"] = True
                elif inter >= 0.2 * min(la, lb) and None not in (a["fam"], b["fam"]) and a["fam"] != b["fam"]:
                    a["piece"] = True
    return by


def distinct_events(ms):
    """Union-find over >= 50 %-of-the-shorter overlaps, per channel."""
    parent = list(range(len(ms)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    by = collections.defaultdict(list)
    for i, m in enumerate(ms):
        by[(m["rec"], m["ch"])].append(i)
    for idx in by.values():
        idx.sort(key=lambda i: ms[i]["s"])
        for x in range(len(idx)):
            a = ms[idx[x]]
            for y in range(x + 1, len(idx)):
                b = ms[idx[y]]
                if b["s"] >= a["e"]:
                    break
                inter = min(a["e"], b["e"]) - max(a["s"], b["s"])
                if inter >= 0.5 * min(a["e"] - a["s"], b["e"] - b["s"]):
                    parent[find(idx[x])] = find(idx[y])
    groups = collections.defaultdict(list)
    for i in range(len(ms)):
        groups[find(i)].append(ms[i])
    return list(groups.values())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--grouping", type=int, default=5, help="the grouping whose families are audited (default 5: Ward 0.60)")
    ap.add_argument("--no-shapes", action="store_true", help="skip reading channel arrays (no shape column)")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    tmp = snapshot(args.db)
    try:
        conn = sqlite3.connect(tmp)
        g = conn.execute("SELECT name, method, cut, n_families, n_assigned FROM groupings WHERE id = ?", (args.grouping,)).fetchone()
        members = load_members(conn, args.grouping)
        verdicts = conn.execute("SELECT recording_id, start_idx, end_idx, verdict FROM annotations "
                                "WHERE source = 'library_review' AND deleted_at IS NULL").fetchall()
    finally:
        conn.close()
        os.remove(tmp)

    print(f"members {len(members)} · grouping {args.grouping} = {g}")
    if not args.no_shapes:
        cache = {}
        for m in members:
            if m["npy"]:
                if m["npy"] not in cache:
                    cache[m["npy"]] = np.load(os.path.join(REPO, m["npy"]), mmap_mode="r")
                m["shape"] = shape_of(cache[m["npy"]][m["s"]:m["e"]])
            else:
                m["shape"] = None

    classify(members)
    print("\nby corpus: members · median length s · twin · nested · piece of another family's event")
    for corp in sorted({m["corpus"] for m in members}, key=lambda c: -sum(m["corpus"] == c for m in members)):
        ms = [m for m in members if m["corpus"] == corp]
        n = len(ms)
        med = np.median([(m["e"] - m["s"]) / m["fs"] for m in ms if m["fs"]])
        files = collections.Counter(m["file"] for m in ms).most_common(2)
        print(f"  {corp:12s} {n:5d}  {med:7.1f}  {sum(m['twin'] for m in ms) / n:5.0%}  {sum(m['nested'] for m in ms) / n:5.0%}"
              f"  {sum(m['piece'] for m in ms) / n:5.0%}   files {files}")
        if not args.no_shapes:
            print(f"               shapes {dict(collections.Counter(m['shape'] for m in ms).most_common())}")

    fams = collections.defaultdict(list)
    for m in members:
        if m["fam"] is not None:
            fams[m["fam"]].append(m)
    dom = collections.Counter(collections.Counter(m["corpus"] for m in ms).most_common(1)[0][0] for ms in fams.values())
    print(f"\nfamilies {len(fams)}, by dominant corpus: {dict(dom)}")
    ev = distinct_events(members)
    print(f"whole library: {len(members)} members -> {len(ev)} distinct events (>= 50 % overlap merged; long members can "
          f"chain several events, so this is a floor)")

    key = {(m["rec"], m["s"], m["e"]): m for m in members}
    accepted = [key[(r[0], r[1], r[2])] for r in verdicts if r[3] == "interesting" and (r[0], r[1], r[2]) in key]
    print(f"\nlibrary_review verdicts: {len(verdicts)} ({collections.Counter(r[3] for r in verdicts)}); "
          f"accepted members {len(accepted)} -> {len(distinct_events(accepted))} distinct events")
    for f, n in collections.Counter(m["fam"] for m in accepted).most_common():
        ms = [m for m in accepted if m["fam"] == f]
        print(f"  family {f}: {n} accepted -> {len(distinct_events(ms))} distinct events on "
              f"{len({(m['rec'], m['ch']) for m in ms})} channel(s)")


if __name__ == "__main__":
    sys.exit(main())
