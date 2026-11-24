"""Read-only inventory: every recording, and queue 57's verdicts so far.

A side check of the 24 Nov drop pool (scripts/autodetect/run_pool.py, build_pool.py): every recording in the database, the held-out lock, and queue 57's verdict counts - what the pool could search (output: docs/autodetect/20261124_pool/checks/inventory.out.txt).
Read-only on the database. Kept from the session that built the pool; queue 57's detections are ids 13389236-13394543.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/pool_checks/inventory.py
"""
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # the repo
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite")
c = sqlite3.connect(f"file:{DB.replace(os.sep, '/')}?mode=ro", uri=True)
c.row_factory = sqlite3.Row

cols = [r[1] for r in c.execute("PRAGMA table_info(recordings)")]
print("recordings columns:", cols)
rows = c.execute("SELECT * FROM recordings ORDER BY source_file, channel").fetchall()
by_file = {}
for r in rows:
    d = dict(r)
    by_file.setdefault(d["source_file"], []).append(d)
print(f"\n{len(rows)} recordings in {len(by_file)} source files\n")
for f, rs in by_file.items():
    fs = sorted({r["fs"] for r in rs})
    n = sorted({r["n_samples"] for r in rs})
    units = sorted({str(r.get("units")) for r in rs})
    ids = [r["id"] for r in rs]
    par = [r.get("parent_recording_id") for r in rs if r.get("parent_recording_id")]
    hours = n[0] / fs[0] / 3600 if fs and fs[0] else float("nan")
    print(f"{f:55s} ch={len(rs):3d} ids {min(ids)}-{max(ids)} fs={fs} n={n[:2]}{'..' if len(n) > 2 else ''} "
          f"~{hours:.0f} h units={units} parents={par[:3]}")

# the held-out lock
for r in c.execute("SELECT page, key, value_json FROM settings WHERE key LIKE '%held%' OR key LIKE '%lock%'"):
    print("setting:", dict(r))

# queue 57 verdicts
q = c.execute("SELECT * FROM review_queues WHERE id = 57").fetchone()
print("\nqueue 57:", {k: q[k] for k in q.keys() if k in ("id", "name", "source", "writes_to", "archived_at", "status")})
acols = [r[1] for r in c.execute("PRAGMA table_info(adjudications)")]
print("adjudications columns:", acols)
n = c.execute("""SELECT a.verdict, COUNT(*) FROM adjudications a
                 WHERE a.detection_id BETWEEN 13389236 AND 13394543 GROUP BY a.verdict""").fetchall()
print("queue-57 detection verdicts:", [tuple(x) for x in n])
