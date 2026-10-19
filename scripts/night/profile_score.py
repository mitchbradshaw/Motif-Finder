"""night pass A: time one template's background score on a database copy (the picker's scorer, off the bridge)."""
import cProfile, pstats, sqlite3, sys, time, os
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.join(os.getcwd(), "webui"))
from Working.discovery import scoreboard as SB
db = sys.argv[1]
conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row
import json
rows = conn.execute("SELECT params_json FROM discovery_runs ORDER BY id LIMIT 3").fetchall()
for r in rows:
    ids = json.loads(r[0])["run_ids"]
    t = time.perf_counter(); SB.score_runs(conn, ids); print("score_runs", round(time.perf_counter() - t, 2), flush=True)
ids = json.loads(rows[0][0])["run_ids"]
pr = cProfile.Profile(); pr.enable(); SB.score_runs(conn, ids); pr.disable()
pstats.Stats(pr).sort_stats("tottime").print_stats(15)
