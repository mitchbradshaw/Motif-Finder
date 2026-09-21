import json, sqlite3, sys
import numpy as np
DB = r"C:\Users\mmebr\Documents\CNN\webui\runtime\20260921-162340\annotations.sqlite"
conn = sqlite3.connect("file:" + DB.replace("\\","/") + "?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
cov = json.load(open(r"C:\Users\mmebr\Documents\CNN\webui\screenshots\critique-01-data\coverage.json"))
print("verdict_counts route:", cov.get("verdict_counts"))
print("n_detection_runs route:", cov.get("n_detection_runs"), "run_filter", cov.get("run_filter"), "method_filter", cov.get("method_filter"))
recs = conn.execute("SELECT id, channel, n_samples, fs FROM recordings WHERE source_file='M2_aug_concat_fs1.mat' ORDER BY channel").fetchall()
print("n recs", len(recs), "n_samples", recs[0]["n_samples"], "fs", recs[0]["fs"])
bad=[]
for row in cov["rows"]:
    rid = row["id"]
    a = conn.execute("SELECT COUNT(*) FROM annotations WHERE recording_id=? AND deleted_at IS NULL",(rid,)).fetchone()[0]
    d = conn.execute("SELECT COUNT(*) FROM detections d JOIN runs r ON r.id=d.run_id WHERE r.recording_id=?",(rid,)).fetchone()[0]
    ra = row["counts"]["annotations"]; rd = row["counts"]["detections"]
    sa = sum(row["annotations"]); sd = sum(row["detections"])
    ok = (a==ra and d==rd and sa==ra and sd==rd)
    if not ok: bad.append((rid,row["name"],("sql",a,d),("route",ra,rd),("hist",sa,sd)))
    print(f"rid={rid} {row['name']}: sql ann={a} det={d} | route ann={ra} det={rd} | hist ann={sa} det={sd} | disagree={row['counts']['disagree']} reviewed_pct={row['counts']['reviewed_pct']}")
print("MISMATCH:", bad)
# verdicts over all channels of this file
vc = conn.execute("SELECT verdict, COUNT(*) FROM annotations WHERE deleted_at IS NULL AND recording_id IN (SELECT id FROM recordings WHERE source_file='M2_aug_concat_fs1.mat') GROUP BY verdict").fetchall()
print("sql verdict counts:", {r[0]:r[1] for r in vc})
# n_detection_runs
nr = conn.execute("SELECT COUNT(DISTINCT r.id) FROM runs r JOIN detections d ON d.run_id=r.id JOIN recordings x ON x.id=r.recording_id WHERE x.source_file='M2_aug_concat_fs1.mat'").fetchone()[0]
print("sql n_detection_runs:", nr)
