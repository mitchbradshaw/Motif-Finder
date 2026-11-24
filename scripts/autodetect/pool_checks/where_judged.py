"""Where the judgements and queue items sit, by source file (read-only).

A side check of the 24 Nov drop pool (scripts/autodetect/run_pool.py, build_pool.py): where the judged events and the queue items sit, by file - what 'already judged' and 'already in a queue' remove (output: checks/where_judged.out.txt).
Read-only on the database. Kept from the session that built the pool; queue 57's detections are ids 13389236-13394543.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/pool_checks/where_judged.py
"""
import collections
import importlib.util
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # the repo
sys.path.insert(0, ROOT)
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace(os.sep, "/")
spec = importlib.util.spec_from_file_location("cat", os.path.join(ROOT, "scripts", "thesis", "accepted_catalogue.py"))
cat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cat)

c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
c.row_factory = sqlite3.Row
t0 = time.perf_counter()
rows, recs = cat.collect(c)
print(f"collect(): {len(rows)} rows in {time.perf_counter() - t0:.1f} s")
k = collections.Counter()
for r in rows:
    f = recs[int(r["canonical_recording_id"])]["source_file"]
    k[(f, r["kind"], r["verdict"])] += 1
by_file = collections.defaultdict(dict)
for (f, kind, v), n in k.items():
    by_file[f][f"{kind}:{v}"] = n
for f in sorted(by_file):
    print(f"{f:45s}", dict(sorted(by_file[f].items())))
print("keys of a row:", sorted(rows[0].keys()))

# queue items by source file (every queue, any state)
from Working.review import queues as Q
t0 = time.perf_counter()
qs = c.execute("SELECT id, name, closed_at, archived_at, writes_to FROM review_queues ORDER BY id").fetchall()
items_by = collections.Counter()
n_items = 0
for q in qs:
    try:
        items = Q.queue_items(c, int(q["id"]))
    except Exception as e:  # noqa: BLE001
        print("queue", q["id"], "unreadable:", type(e).__name__, e)
        continue
    n_items += len(items)
    for it in items:
        rid = it.get("recording_id")
        if rid is None:
            items_by[("(no recording)", q["writes_to"])] += 1
            continue
        items_by[(recs[int(rid)]["source_file"], q["writes_to"])] += 1
print(f"\n{len(qs)} queues, {n_items} items in {time.perf_counter() - t0:.1f} s")
for (f, w), n in sorted(items_by.items()):
    print(f"  {f:45s} {w:12s} {n}")
