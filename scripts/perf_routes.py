"""
perf_routes.py — time the reads the pages make, the way the pages make them (AR, the speed pass).

Dev tooling: nothing in the app imports this. Point it at a running bridge:

    python scripts/perf_routes.py --url http://127.0.0.1:8767 [-n 5] [--writes] [--only review,discovery]

It discovers its own ids (the biggest review queue, its items, the session's runs and channels) from the bridge's
answers, hits each route N times and prints a table of median and p95 wall time in ms at the client, and the
payload size. `--writes` also times a verdict round trip (a verdict on an unjudged item, then its undo — the
database ends as it began); without it nothing is written.

The scale fixture it is meant to stand on is `tests/perf_fixture.py` (`python tests/perf_fixture.py out.sqlite`,
then `webui/run_server.py --sandbox --port 8767 --db out.sqlite --dist <dist>`).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.parse
import urllib.request


def _get(base, path, timeout):
    t0 = time.perf_counter()
    with urllib.request.urlopen(base + path, timeout=timeout) as r:
        body = r.read()
    return (time.perf_counter() - t0) * 1e3, body


def _post(base, path, payload, timeout):
    t0 = time.perf_counter()
    req = urllib.request.Request(base + path, data=json.dumps(payload).encode(), method="POST",
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    return (time.perf_counter() - t0) * 1e3, body


def _p95(xs):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.95 * (len(xs) - 1))))]


class Table:
    def __init__(self):
        self.rows = []

    def time(self, label, fn, n):
        times, size, err = [], 0, None
        for _ in range(n):
            try:
                ms, body = fn()
            except Exception as e:                       # a failed read is a row that says so
                err = f"{type(e).__name__}: {e}"[:80]
                break
            times.append(ms)
            size = len(body)
        self.rows.append((label, times, size, err))
        last = self.rows[-1]
        print(self._fmt(last), flush=True)
        return last

    @staticmethod
    def _fmt(row):
        label, times, size, err = row
        if err:
            return f"{label:<64} {'FAILED':>9} {'':>9} {'':>8}  {err}"
        return f"{label:<64} {statistics.median(times):>9.0f} {_p95(times):>9.0f} {size / 1024:>8.1f}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8767")
    ap.add_argument("-n", type=int, default=5, help="reads per route (default 5)")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--writes", action="store_true", help="also time a verdict round trip (verdict, then undo)")
    ap.add_argument("--only", default="", help="comma list of groups: review, corpus, discovery")
    ap.add_argument("--px", type=int, default=900)
    ap.add_argument("--pad", type=int, default=120)
    a = ap.parse_args(argv)
    base, n, to = a.url.rstrip("/"), a.n, a.timeout
    groups = set(filter(None, a.only.split(","))) or {"review", "corpus", "discovery"}
    get = lambda p: (lambda: _get(base, p, to))          # noqa: E731
    t = Table()
    print(f"{'route (as the page issues it)':<64} {'median':>9} {'p95':>9} {'kB':>8}")
    print("-" * 94)

    if "review" in groups:
        t.time("GET /api/review/queues", get("/api/review/queues"), n)
        t.time("GET /api/review/counts", get("/api/review/counts"), n)
        queues = json.loads(_get(base, "/api/review/queues", to)[1])
        if queues:
            big = max(queues, key=lambda q: q.get("total") or 0)
            qid = big["id"]
            t.time(f"GET /api/review/queues/{qid} (whole, with thumbnails; {big.get('total')} items)",
                   get(f"/api/review/queues/{qid}"), max(1, min(n, 2)))
            t.time(f"GET /api/review/queues/{qid}?thumbs=0 (rows, no thumbnails)",
                   get(f"/api/review/queues/{qid}?thumbs=0"), n)
            t.time(f"GET /api/review/queues/{qid}/counts", get(f"/api/review/queues/{qid}/counts"), n)
            rows = json.loads(_get(base, f"/api/review/queues/{qid}?thumbs=0", to)[1])["rows"]
            mid = len(rows) // 2
            ids = [r["id"] for r in rows[mid:mid + max(3, n)]]
            if ids:
                t.time(f"GET /api/review/queues/{qid}/thumbs?ids=<10>",
                       get(f"/api/review/queues/{qid}/thumbs?ids=" + ",".join(r["id"] for r in rows[mid:mid + 10])), n)
                q = f"?px={a.px}&pad_s={a.pad}"
                it = iter(ids * n)
                t.time(f"GET /api/review/queues/{qid}/items/<id>{q} (consecutive items)",
                       lambda: _get(base, f"/api/review/queues/{qid}/items/{next(it)}{q}", to), n)
                t.time(f"GET /api/review/queues/{qid}/items/<id>/channels{q}",
                       get(f"/api/review/queues/{qid}/items/{ids[0]}/channels{q}"), n)
                if a.writes:
                    unjudged = [r["id"] for r in rows if not r.get("judged") and not r.get("baseVerdict")][:n]

                    def one():
                        tid = unjudged.pop(0)
                        ms, body = _post(base, f"/api/review/queues/{qid}/verdict",
                                         {"target_id": tid, "verdict": "unsure"}, to)
                        _post(base, f"/api/review/queues/{qid}/undo", {}, to)
                        return ms, body
                    if unjudged:
                        t.time(f"POST /api/review/queues/{qid}/verdict (then undo, untimed)", one, len(unjudged))

    if "corpus" in groups:
        files = json.loads(_get(base, "/api/recordings", to)[1])
        sf = None
        if isinstance(files, list) and files:
            sf = max(files, key=lambda f: len(f.get("channels") or [])).get("source_file")
        if sf:
            t.time(f"GET /api/corpus/{sf}/coverage?bins=57&verdicts=seed,interesting",
                   get(f"/api/corpus/{urllib.parse.quote(sf)}/coverage?bins=57&verdicts=seed,interesting"), n)

    if "discovery" in groups:
        t.time("GET /api/discovery/session", get("/api/discovery/session"), n)
        t.time("GET /api/discovery/runs", get("/api/discovery/runs"), n)
        t.time("GET /api/discovery/templates (the picker)", get("/api/discovery/templates"), n)
        sess = json.loads(_get(base, "/api/discovery/session", to)[1])["session"]
        runs = [r for r in json.loads(_get(base, "/api/discovery/runs", to)[1]) if r.get("key") != "human"]
        chans = sess["channels"][:3]
        t0h, t1h = sess["section"]
        keys = ",".join(["human"] + [r["key"] for r in runs])
        cq = urllib.parse.quote(",".join(chans))
        t.time(f"GET /api/discovery/fires (3 channels, {len(runs)} runs)",
               get(f"/api/discovery/fires?channels={cq}&t0={t0h}&t1={t1h}&runs={urllib.parse.quote(keys)}"), n)
        ten = urllib.parse.quote(",".join(r["key"] for r in runs[:10]))
        t.time("GET /api/discovery/scoreboard (10 runs, 3 channels)",
               get(f"/api/discovery/scoreboard?runs={ten}&channels={cq}&t0={t0h}&t1={t1h}"), max(1, min(n, 2)))
        t.time("GET /api/discovery/map", get("/api/discovery/map"), max(1, min(n, 3)))
        rec = urllib.parse.quote(sess.get("recordingFile") or sess["recording"])
        t.time("GET /api/discovery/map/dataset?chunks=4",
               get(f"/api/discovery/map/dataset?recording={rec}&chunks=4"), max(1, min(n, 3)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
