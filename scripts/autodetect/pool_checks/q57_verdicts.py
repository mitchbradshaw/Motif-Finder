"""Queue 57's verdicts so far, with each candidate's features (read-only).

A side check of the 24 Nov drop pool (scripts/autodetect/run_pool.py, build_pool.py): queue 57's verdicts with each candidate's features - the evidence for the rule changes (output: checks/q57_verdicts.out.txt and q57_verdicts_<when>.csv).
Read-only on the database. Kept from the session that built the pool; queue 57's detections are ids 13389236-13394543.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/autodetect/pool_checks/q57_verdicts.py
"""
import json
import os
import sqlite3

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # the repo
c = sqlite3.connect(f"file:{os.path.join(ROOT, 'DATA', 'db', 'annotations.sqlite').replace(os.sep, '/')}?mode=ro",
                    uri=True)
rows = c.execute("""
    SELECT d.id, d.meta_json, a.verdict, a.note, a.created_at, a.class_label,
           (SELECT ri.position FROM review_items ri WHERE ri.queue_id = 57 AND ri.target_id = d.id LIMIT 1) AS pos
    FROM adjudications a JOIN detections d ON d.id = a.detection_id
    WHERE a.detection_id BETWEEN 13389236 AND 13394543 AND a.carried_from IS NULL
    ORDER BY a.id""").fetchall() if False else None
# review_items' columns are not known here: read them first
cols = [r[1] for r in c.execute("PRAGMA table_info(review_items)")]
print("review_items columns:", cols)
q = """SELECT d.id AS detection_id, d.meta_json, a.id AS adj_id, a.verdict, a.note, a.created_at, a.carried_from
       FROM adjudications a JOIN detections d ON d.id = a.detection_id
       WHERE a.detection_id BETWEEN 13389236 AND 13394543 ORDER BY a.id"""
df = pd.read_sql_query(q, c)
print(len(df), "verdict rows;", df["carried_from"].notna().sum(), "carried")
df = df[df["carried_from"].isna()]
last = df.groupby("detection_id").tail(1)                 # the latest own look per detection
meta = pd.DataFrame([json.loads(m) for m in last["meta_json"]])
v = pd.concat([last[["detection_id", "verdict", "note", "created_at"]].reset_index(drop=True), meta], axis=1)
sel = pd.read_csv(os.path.join(ROOT, "docs", "autodetect", "20261124_queue", "selected.csv"))
v = v.merge(sel[["ref", "candidate_id", "duration_s", "start_s", "run", "runs"]], on=["ref", "candidate_id"],
            how="left")
print(v["verdict"].value_counts().to_dict())
print("ranks judged: min", v["rank"].min(), "max", v["rank"].max(), "; first unjudged rank:",
      sorted(set(range(1, int(v['rank'].max()) + 2)) - set(v['rank'].astype(int)))[:5])
print("\nby verdict (medians):")
feat = ["rank", "confidence", "p_r4", "clarity", "depth_mv", "sharpness", "duration_s"]
print(v.groupby("verdict")[feat].median().round(3).to_string())
print("\npolarity x verdict:\n", pd.crosstab(v["polarity"], v["verdict"]).to_string())
print("\nref x verdict:\n", pd.crosstab(v["ref"], v["verdict"]).to_string())
v["n_src"] = v["sources"].fillna("").str.count(r"\|") + (v["sources"].fillna("") != "").astype(int)
print("\nn sources x verdict:\n", pd.crosstab(v["n_src"], v["verdict"]).to_string())
neg = v[v["verdict"].isin(["unsure", "artifact", "not_interesting"])]
print("\nthe non-accepted ones:")
print(neg[["rank", "ref", "verdict", "polarity", "confidence", "p_r4", "clarity", "depth_mv", "sharpness",
           "duration_s", "start_s", "m4_like", "sources", "note"]].to_string())
import datetime as _dt  # noqa: E402
v.to_csv(os.path.join(ROOT, "docs", "autodetect", "20261124_pool", "checks",
                      f"q57_verdicts_{_dt.datetime.now():%Y%m%d_%H%M}.csv"), index=False)
