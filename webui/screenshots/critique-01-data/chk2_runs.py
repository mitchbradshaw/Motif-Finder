import json, sqlite3, urllib.request
import numpy as np
DB = r"C:/Users/mmebr/Documents/CNN/webui/runtime/20260921-162340/annotations.sqlite"
conn = sqlite3.connect("file:"+DB+"?mode=ro", uri=True); conn.row_factory = sqlite3.Row
route = json.load(urllib.request.urlopen("http://127.0.0.1:8765/api/corpus/M2_aug_concat_fs1.mat/runs"))
rr = {r["id"]: r for r in route["runs"]}
sql = conn.execute("""SELECT r.id, r.recording_id, r.status, r.config_id, (SELECT COUNT(*) FROM detections d WHERE d.run_id=r.id) n
 FROM runs r JOIN recordings x ON x.id=r.recording_id WHERE x.source_file='M2_aug_concat_fs1.mat' ORDER BY r.id DESC""").fetchall()
print("sql run count", len(sql), "route run count", len(route["runs"]))
missing = [r["id"] for r in sql if r["id"] not in rr]
print("runs in SQL but NOT in route:", missing)
import sys; sys.path.insert(0, r"C:/Users/mmebr/Documents/CNN")
from Working.database.runs import load_recipe
for r in sql:
    try:
        rec = load_recipe(conn, r["config_id"]); algos=[s["algorithm"] for s in rec["steps"]]
    except Exception as e:
        algos = ["<ERR %s>" % e]
    got = rr.get(r["id"])
    flag = ""
    if got:
        if got["algorithms"] != algos: flag += " ALGOS-MISMATCH"
        if got["n_detections"] != r["n"]: flag += " NDET-MISMATCH"
        if got["status"] != r["status"]: flag += " STATUS-MISMATCH"
    print(r["id"], "cfg",r["config_id"], "sqlstatus",r["status"],"sql_n",r["n"], "sql_algos",algos, "| route", (got["method"],got["n_detections"],got["algorithms"]) if got else None, flag)
