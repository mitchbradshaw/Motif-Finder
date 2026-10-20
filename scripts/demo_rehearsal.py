"""
demo_rehearsal.py
=================
Warm a demo bridge and time it, page by page, before the examiners arrive.

    "/c/ProgramData/anaconda3/python.exe" scripts/demo_rehearsal.py --url http://127.0.0.1:8800

Opens every page the demo can reach in a headless chromium (Playwright, the
same dev tooling webui/smoke.py uses), waits for each page's /api requests to
go quiet, and times every request. Two passes by default: the first is the
cold start (a sandbox bridge starts with an empty step cache), the second is
what an examiner sees after the warm-up. Prints every request and every page
over --slow seconds (default 3) with its route and time, and writes the full
table as markdown with --report.

Running it IS the warm-up: every cache a page fills on its first visit is
filled. Point it at a sandbox bridge only — never the project bridge on 8765.
It clicks nothing that writes: page visits only (an Analyse run, a seed
search or a template apply are left to the person rehearsing by hand).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from urllib.parse import urlparse

PAGES = [
    "explore/corpus", "explore/signal/{ch}", "analyse/chain", "analyse/interrogation",
    "discovery/runs", "discovery/seed", "discovery/map", "discovery/compare",
    "library/atlas", "library/recurrence", "library/sequences", "library/templates", "library/window-sets",
    "review", "jobs", "reports", "settings/datasets", "settings/analysis-defaults",
]

# The live talk's own pages on the project bridge (docs/DEMO_DAY.md, "The live talk"): every one should be a
# cache hit or an existing run. Run keys and queue ids are the ones made on 2026-10-20.
TALK = [
    "explore/corpus", "explore/signal/4", "analyse/chain", "library/templates",
    "discovery/runs", "reports/detection-run/demo%20%C2%B7%20drop%20detector", "review/queue/30",
    "library/atlas", "library/family/F-30?grouping=g-05", "discovery/seed?entry=191", "review/queue/31",
    "reports/detection-run/seed_056a5d", "reports/detection-run/dip_search_allch", "discovery/map",
    *[f"discovery/map?dataset={d}" for d in ("M2_aug_concat_fs1", "M2_concat_fs1", "CO_fs2", "LM_fs2",
                                             "L_LM_Jul_26_J_raw", "L_LM_Jul_26_J_raw_fs2", "M4_aug_concat_fs1")],
    "review/queue/27", "review/queue/28",
]


def channel_ids(url: str) -> list[int]:
    with urllib.request.urlopen(f"{url}/api/recordings", timeout=120) as r:
        return [c["id"] for rec in json.load(r) for c in rec["channels"]]


def visit(page, url: str, route: str, quiet_s: float, cap_s: float) -> tuple[float, list[tuple[str, float, int]]]:
    """Open #/<route>; return (seconds until its /api traffic went quiet, [(request, seconds, status)])."""
    started: dict = {}
    done: list[tuple[str, float, int]] = []
    finished_at = [0.0]

    def on_request(req):
        if "/api/" in req.url:
            started[req] = time.perf_counter()

    def on_finished(req, failed=False):
        t0 = started.pop(req, None)
        if t0 is not None:
            finished_at[0] = time.perf_counter()
            resp = None if failed else req.response()
            p = urlparse(req.url)
            done.append((f"{req.method} {p.path}{'?' + p.query if p.query else ''}", time.perf_counter() - t0,
                         resp.status if resp else -1))

    page.on("request", on_request)
    page.on("requestfinished", on_finished)
    page.on("requestfailed", lambda r: on_finished(r, True))
    t0 = time.perf_counter()
    page.goto(f"{url}/#/{route}")
    last = time.perf_counter()
    while time.perf_counter() - t0 < cap_s:
        page.wait_for_timeout(250)
        if started:
            last = time.perf_counter()
        elif time.perf_counter() - last >= quiet_s:
            break
    ready = max(finished_at[0], t0) - t0  # when the page's last /api answer arrived
    for req, t in list(started.items()):
        done.append((f"{req.method} {urlparse(req.url).path} (still running at the cap)", time.perf_counter() - t, -1))
    page.remove_listener("request", on_request)
    page.remove_listener("requestfinished", on_finished)
    page.goto("about:blank")
    return ready, done


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True, help="the demo bridge, e.g. http://127.0.0.1:8800 (never :8765)")
    ap.add_argument("--passes", type=int, default=2)
    ap.add_argument("--slow", type=float, default=3.0, help="report requests/pages over this many seconds")
    ap.add_argument("--quiet", type=float, default=2.0, help="a page is ready after this long with no /api request open")
    ap.add_argument("--cap", type=float, default=300.0, help="give up waiting on one page after this many seconds")
    ap.add_argument("--report", default=None, help="write the full timing table here (markdown)")
    ap.add_argument("--talk", action="store_true", help="walk the live talk's pages (TALK) instead of every page")
    ap.add_argument("--allow-project", action="store_true",
                    help="walk a --project bridge too (page visits only; for warming the talk bridge on the real database)")
    a = ap.parse_args()
    url = a.url.rstrip("/")
    if urlparse(url).port == 8765 and not a.allow_project:
        raise SystemExit("8765 is the researcher's project bridge; pass --allow-project to warm it for the talk")
    with urllib.request.urlopen(f"{url}/api/runtime", timeout=60) as r:
        if json.load(r).get("mode") != "sandbox" and not a.allow_project:
            raise SystemExit(f"{url} is not a sandbox bridge; pass --allow-project to walk it anyway")
    routes = TALK if a.talk else [p.format(ch=c) for p in PAGES for c in (channel_ids(url) if "{ch}" in p else [None])]

    from playwright.sync_api import sync_playwright
    rows: list[tuple[int, str, str, float, int]] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for n in range(1, a.passes + 1):
            print(f"-- pass {n} ({'cold' if n == 1 else 'warm'})", flush=True)
            for route in routes:
                ready, reqs = visit(page, url, route, a.quiet, a.cap)
                rows.append((n, route, "(page ready)", ready, 0))
                rows += [(n, route, q, t, s) for q, t, s in reqs]
                flag = "SLOW " if ready > a.slow else "     "
                print(f"{flag}{ready:7.1f} s  #/{route}  ({len(reqs)} requests)", flush=True)
                for q, t, s in sorted(reqs, key=lambda x: -x[1]):
                    if t > a.slow or s >= 400 or s < 0:
                        print(f"           {t:7.1f} s  {s}  {q}", flush=True)
        browser.close()
    if errors:
        print(f"{len(errors)} page error(s):", *errors[:10], sep="\n  ")
    if a.report:
        with open(a.report, "w", encoding="utf-8") as f:
            f.write(f"# Demo rehearsal — {url}\n\n| pass | page | request | s | status |\n|---|---|---|---|---|\n")
            f.writelines(f"| {n} | `#/{r}` | `{q}` | {t:.2f} | {s or ''} |\n" for n, r, q, t, s in rows)
    slow_warm = [r for r in rows if r[0] == a.passes and r[3] > a.slow]
    print(f"{len(slow_warm)} step(s) over {a.slow:g} s on the last pass")
    return 1 if slow_warm or errors else 0


if __name__ == "__main__":
    sys.exit(main())
