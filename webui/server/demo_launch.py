"""Start the whole NeurIPS demo: the hub, the shared seed worker and N private stations, and keep them running.

    webui\\.venv\\Scripts\\python.exe webui\\server\\demo_launch.py [--stations 6] [--port 8900] [--host 0.0.0.0]
                                                              [--public-url http://192.168.137.1:8900/]

Run from the repo root of the demo worktree (it needs DATA/neurips_demo/store and webui/client/dist-neurips). The
hub listens on --port, station n on --port + n, the seed worker on --port + 9 (127.0.0.1 only). A child that dies is
started again within a few seconds. Ctrl+C stops everything. The admin key for /admin is printed at start.
"""
from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stations", type=int, default=6)
    ap.add_argument("--port", type=int, default=8900)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--public-url", default=None)
    ap.add_argument("--dist", default=str(ROOT / "webui" / "client" / "dist-neurips"))
    ap.add_argument("--admin-key", default=None)
    ap.add_argument("--role", default="launch", choices=["launch", "seed"], help=argparse.SUPPRESS)
    a = ap.parse_args()
    os.chdir(ROOT)
    import uvicorn

    if a.role == "seed":
        from demo_hub import create_seed_worker
        uvicorn.run(create_seed_worker(admin_key=a.admin_key), host="127.0.0.1", port=a.port, log_level="warning",
                    access_log=False)
        return

    if not (ROOT / "DATA/neurips_demo/store/manifest.json").exists():
        raise SystemExit("DATA/neurips_demo/store is not built: run scripts/neurips_demo/ first")
    if not (Path(a.dist) / "demo.html").exists():
        raise SystemExit(f"the demo client is not built: {a.dist}/demo.html is missing (npm run build:neurips)")
    key = a.admin_key or secrets.token_urlsafe(9)
    py = sys.executable
    seed_port = a.port + 9
    hub_url = f"http://127.0.0.1:{a.port}"
    specs = {"seed": [py, str(HERE / "demo_launch.py"), "--role", "seed", "--port", str(seed_port), "--admin-key", key]}
    for n in range(1, a.stations + 1):
        specs[f"station{n}"] = [py, str(HERE / "demo_station.py"), "--port", str(a.port + n), "--host", a.host,
                                "--station", str(n), "--admin-key", key, "--hub", hub_url,
                                "--seed-worker", f"http://127.0.0.1:{seed_port}", "--dist", a.dist]
    logs = ROOT / "DATA/neurips_demo/logs"
    logs.mkdir(parents=True, exist_ok=True)
    procs: dict[str, subprocess.Popen] = {}
    stop = threading.Event()

    def start(name):
        f = open(logs / f"{name}.log", "ab")
        procs[name] = subprocess.Popen(specs[name], cwd=str(ROOT), stdout=f, stderr=subprocess.STDOUT,
                                       env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONFAULTHANDLER": "1"})

    for name in specs:
        start(name)

    def supervise():
        while not stop.is_set():
            for name, p in list(procs.items()):
                if p.poll() is not None and not stop.is_set():
                    print(f"[demo] {name} exited ({p.returncode}); starting it again", flush=True)
                    start(name)
            time.sleep(2)

    threading.Thread(target=supervise, name="supervisor", daemon=True).start()

    from demo_hub import Station, create_hub, lan_urls
    stations = [Station(n, a.port + n) for n in range(1, a.stations + 1)]
    app = create_hub(stations=stations, admin_key=key, port=a.port, public_url=a.public_url)
    urls = [a.public_url] if a.public_url else lan_urls(a.port)
    print(f"[demo] MycoWave demo: {a.stations} stations on ports {a.port + 1}-{a.port + a.stations}", flush=True)
    print(f"[demo] on this laptop: http://127.0.0.1:{a.port}/", flush=True)
    for u in urls:
        print(f"[demo] for visitors:   {u}", flush=True)
    print(f"[demo] operator page:  http://127.0.0.1:{a.port}/admin?key={key}", flush=True)
    try:
        uvicorn.run(app, host=a.host, port=a.port, log_level="warning", access_log=False)
    finally:
        stop.set()
        for p in procs.values():
            p.terminate()
        for p in procs.values():
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
