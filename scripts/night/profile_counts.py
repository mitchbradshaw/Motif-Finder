"""night pass A: profile the Review header counts and the queue list on a database copy (read-only use)."""
import cProfile, pstats, sqlite3, sys, time, os
sys.path.insert(0, os.getcwd())
from Working.review import queues as Q
db = sys.argv[1]
conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
for label, fn in (("header_counts", lambda: Q.header_counts(conn, exclude_recording_ids=set())),
                  ("list_queues", lambda: Q.list_queues(conn, exclude_recording_ids=set()))):
    for i in range(2):
        t = time.perf_counter(); fn(); print(label, i, round(time.perf_counter() - t, 2), flush=True)
pr = cProfile.Profile(); pr.enable(); Q.header_counts(conn, exclude_recording_ids=set()); pr.disable()
pstats.Stats(pr).sort_stats("cumulative").print_stats(18)
