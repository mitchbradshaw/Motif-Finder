"""night pass A: profile one bridge GET in-process (webui/.venv python) on a COPY of a database.
Usage: python scripts/night/profile_route.py <db copy> <path> [n]"""
import cProfile, os, pstats, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [ROOT, os.path.join(ROOT, "webui")]
from fastapi.testclient import TestClient
from server.app import create_app
from server.runtime import Runtime
db, path = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 2
rt = Runtime("sandbox", stamp="night-prof", db_source=db, runtime_root=os.path.join(ROOT, "webui", "runtime", "night", "prof_rt")).setup()
try:
    with TestClient(create_app(rt)) as c:
        for i in range(n):
            t = time.perf_counter(); r = c.get(path); print(i, r.status_code, round(time.perf_counter() - t, 2), len(r.content), flush=True)
        pr = cProfile.Profile(); pr.enable(); c.get(path); pr.disable()
        pstats.Stats(pr).sort_stats("cumulative").print_stats(30)
finally:
    rt.restore()
