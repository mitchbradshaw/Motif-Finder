"""
profile_routes_c.py — night pass C: time the slow first-paint reads IN PROCESS (FastAPI TestClient on a sandbox
copy of the scale fixture), each twice (cold, warm). Separates a read's own cost from the bridge's contention: on
a loaded machine the bridge's numbers ran 5-50x these. (cProfile sees nothing here: handlers run on the threadpool.)

    PYTHONIOENCODING=utf-8 webui/.venv/Scripts/python.exe scripts/night/profile_routes_c.py \
        webui/runtime/night/fixture/scale.sqlite [route ...]

From Git Bash set MSYS_NO_PATHCONV=1, or a route argument such as /api/x is rewritten into a Windows path.
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "webui"))

from fastapi.testclient import TestClient  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import Runtime  # noqa: E402

DEFAULT = ["/api/review/counts", "/api/review/queues", "/api/review/queues/1?thumbs=0", "/api/review/queues/1/counts",
           "/api/discovery/runs", "/api/discovery/templates", "/api/channels/4"]


def main(argv):
    db = os.path.abspath(argv[0])
    routes = argv[1:] or DEFAULT
    rt = Runtime("sandbox", stamp="night-c-profile", db_source=db,
                 runtime_root=os.path.join(ROOT, "webui", "runtime", "night", "profile_rt")).setup()
    try:
        with TestClient(create_app(rt)) as client:
            for r in routes:
                t = time.perf_counter()
                resp = client.get(r)
                cold = time.perf_counter() - t
                t = time.perf_counter()
                client.get(r)
                warm = time.perf_counter() - t
                print(f"{r}  {resp.status_code}  {len(resp.content)} B  cold {cold:.2f}s  warm {warm:.2f}s", flush=True)
    finally:
        rt.restore()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
