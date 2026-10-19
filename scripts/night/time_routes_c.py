"""
time_routes_c.py — night pass C: time, one at a time on a quiet bridge, the reads the busiest pages make on
first paint (Review inspector, Discovery runs, Explore signal, Analyse chain, the header on every page).

    "/c/ProgramData/anaconda3/python.exe" scripts/night/time_routes_c.py --url http://127.0.0.1:8769 [--queue 1] [--channel 4]

Prints `seconds  bytes  status  route`. Serial on purpose: a parallel burst measures the bridge's queue, not a read.
The whole-channel span read (the Signal page's) is last and capped by --slow-timeout, since at scale it can run for
minutes and every request behind it waits.
"""
import argparse
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8769")
    ap.add_argument("--queue", default="1")
    ap.add_argument("--channel", default="4")
    ap.add_argument("--slow-timeout", type=float, default=180)
    a = ap.parse_args(argv)
    base = a.url.rstrip("/")
    if base.endswith(":8765") or base.endswith(":8766"):
        raise SystemExit("refuses the researcher's and the manager's bridges")
    rec = urllib.request.urlopen(base + "/api/recordings", timeout=60)
    import json
    files = json.loads(rec.read())
    src = urllib.parse.quote(files[0]["source_file"]) if files else "x"
    ch, q = a.channel, a.queue
    routes = [
        # every page: the shell
        "/api/review/counts", "/api/held-out", "/api/runs?limit=1",
        # Review inspector
        "/api/review/queues", f"/api/review/queues/{q}?thumbs=0", f"/api/review/queues/{q}/counts",
        # Discovery runs
        "/api/discovery/session", "/api/discovery/runs", "/api/discovery/scoreboard", "/api/discovery/bands",
        "/api/discovery/templates", "/api/discovery/seeds", "/api/discovery/overview", "/api/discovery/history",
        # Explore corpus / signal
        "/api/recordings", "/api/datasets", f"/api/corpus/{src}/coverage", f"/api/channels/{ch}", f"/api/corpus/{src}/runs",
        f"/api/channels/{ch}/tags", f"/api/channels/{ch}/window?t0=0&t1=7200&px=1200",
        # Analyse chain
        "/api/adapters", "/api/templates", "/api/settings", "/api/jobs",
        # the Signal page's whole-channel span read, last
        f"/api/channels/{ch}/spans",
    ]
    for r in routes:
        t = time.perf_counter()
        timeout = a.slow_timeout if r.endswith("/spans") else 120
        try:
            with urllib.request.urlopen(base + r, timeout=timeout) as resp:
                n, st = len(resp.read()), resp.status
        except urllib.error.HTTPError as e:
            n, st = 0, e.code
        except Exception as e:  # noqa: BLE001 - a timeout is the finding
            n, st = 0, type(e).__name__
        print(f"{time.perf_counter() - t:8.2f}s {n:>10} {st} {r}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
