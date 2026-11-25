"""Walk the NeurIPS demo like visitors do, and fail loudly on anything a visitor would see go wrong.

    "/c/ProgramData/anaconda3/python.exe" scripts/neurips_demo/walk.py [--hub http://127.0.0.1:8900] [--visitors 1]
                                                                      [--shots DIR] [--tour]

Each visitor is its own browser context (its own cookies and storage, like its own device): it claims a station at
the hub, then visits every stop and does that stop's one action, timing each. With --tour it follows the guided tour
instead, by clicking what the tour highlights. Collected per visitor: console errors, page errors, failed requests
(4xx/5xx), red error cards, and the time each stop took to show its content. Exit code 1 if anything failed.
Playwright via the conda interpreter (dev tooling, CLAUDE.md "Environment").
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]


async def visitor(browser, hub: str, k: int, shots: Path | None, tour: bool, report: dict, keep: list | None = None):
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
    page = await ctx.new_page()
    errs, fails, times = [], [], {}
    page.on("console", lambda m: errs.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
    page.on("response", lambda r: fails.append(f"{r.status} {r.url}") if r.status >= 400 else None)

    async def shot(name):
        if shots:
            await page.screenshot(path=str(shots / f"v{k}_{name}.png"), full_page=True)

    async def timed(name, coro, ready_sel, timeout=20000):
        t0 = time.perf_counter()
        await coro
        await page.wait_for_selector(ready_sel, timeout=timeout)
        times[name] = round(time.perf_counter() - t0, 3)
        red = await page.locator('[data-testid="render-error"]').count()
        if red:
            errs.append(f"{name}: a red error card")
        await shot(name)

    await timed("hub", page.goto(hub), "text=Start the demo")
    await timed("claim", page.click("text=Start the demo"), '[data-testid="tour-start"]')
    station = page.url
    report.setdefault("stations", []).append(station.split("/#")[0].split("?")[0])
    if tour:
        await walk_tour(page, timed, errs)
    else:
        await walk_stops(page, timed)
    report.setdefault("visitors", []).append({"k": k, "station": station, "times": times, "errors": errs, "failed": fails})
    if keep is not None:
        keep.append((ctx, page, errs))
    else:
        await ctx.close()


async def stress_after(browser, hub: str, admin_key: str, keep: list, report: dict):
    """With every station taken: a further visitor is told to wait; then the operator frees one station and its old
    tab says the copy has moved on (it cannot write into the next visitor's copy)."""
    problems = report.setdefault("stress", [])
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
    page = await ctx.new_page()
    await page.goto(hub)
    await page.click("text=Start the demo")
    await page.wait_for_load_state()
    if "/busy" not in page.url:
        problems.append(f"the visitor after the last station was sent to {page.url}, not /busy")
    await ctx.close()
    ctx0, page0, _ = keep[0]
    station = page0.url.split("#")[0]
    port = int(station.split(":")[2].split("/")[0])
    n = port - int(hub.rsplit(":", 1)[1].strip("/"))
    import urllib.request
    req = urllib.request.Request(f"{hub}/admin/reset/{n}?key={admin_key}", method="POST")
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:          # a 303 to /admin is fine; anything else is not
        if "303" not in str(e):
            problems.append(f"admin reset failed: {e}")
    await page0.reload()
    try:
        await page0.wait_for_selector('[data-testid="station-lost"]', timeout=10000)
    except Exception:
        problems.append("the reset station's old tab did not say the copy moved on")
    for c, _, _ in keep:
        await c.close()


async def walk_stops(page, timed):
    await timed("welcome→explore", page.click('[data-testid="explore-free"]'), '[data-testid="explore-trace"] svg')
    await timed("auto-detect", page.click('[data-testid="auto-btn"]'), '[data-testid="auto-count"]')
    box = await page.locator('[data-testid="explore-trace"] svg').bounding_box()
    await page.mouse.move(box["x"] + box["width"] * 0.42, box["y"] + 120)
    await page.mouse.down()
    await page.mouse.move(box["x"] + box["width"] * 0.47, box["y"] + 130, steps=6)
    await page.mouse.up()
    await page.wait_for_selector('[data-testid="span-label"]')
    await timed("analyse", page.click('[data-testid="analyse-btn"]'), '[data-testid="events-in-span"]')
    await timed("build", page.click('[data-testid="to-build"]'), '[data-testid="knob-segment_s"]')
    await timed("knob", page.click('[data-testid="knob-segment_s"] button >> nth=1'), '[data-testid="events-in-span"]')
    await timed("detector", page.click('[data-testid="det-noise_threshold"]'), '[data-testid="knob-k_sigma"]')
    await timed("discovery", page.click('[data-testid="run-btn"]'), '[data-testid="disc-ratio"]')
    await timed("judge", page.click('[data-testid="judge-btn"]'), '[data-testid="judge-trace"] svg')
    for i, v in enumerate(["v-yes", "v-no", "v-yes", "v-unsure", "v-yes"]):
        sel = '[data-testid="judge-summary"]' if i == 4 else '[data-testid="judge-trace"] svg'
        await timed(f"verdict{i + 1}", page.click(f'[data-testid="{v}"]'), sel)
    await timed("library", page.click('[data-testid="to-library"]'), '[data-testid^="fam-"]')
    await timed("family", page.click('[data-testid^="fam-"] >> nth=0'), '[data-testid="family-detail"]')
    await timed("seed(family)", page.click('[data-testid="family-seed"]'), '[data-testid="seed-summary"], [data-testid="seed-searching"]')
    await page.wait_for_selector('[data-testid="seed-summary"]', timeout=30000)
    await timed("seed(shelf)", page.click('[data-testid^="seed-S"] >> nth=0'), '[data-testid="seed-gallery"]')
    await timed("stats", page.click('[data-testid="to-stats"]'), '[data-testid="stats-grid"]')
    await timed("stats(mine)", page.click('[data-testid="src-mine"]'), '[data-testid="stats-grid"]')
    await timed("stats(auto)", page.click('[data-testid="src-auto"]'), '[data-testid="stats-grid"]')
    # a live seed from Explore
    await timed("explore again", page.click('[data-testid="stop-explore"]'), '[data-testid="explore-trace"] svg')
    await page.click("text=5 min")
    box = await page.locator('[data-testid="explore-trace"] svg').bounding_box()
    await page.mouse.move(box["x"] + box["width"] * 0.40, box["y"] + 120)
    await page.mouse.down()
    await page.mouse.move(box["x"] + box["width"] * 0.55, box["y"] + 130, steps=6)
    await page.mouse.up()
    await timed("seed(live)", page.click('[data-testid="seed-btn"]'), '[data-testid="seed-summary"]', timeout=30000)
    await timed("start over", page.click('[data-testid="start-over"]'), '[data-testid="start-over-yes"]')
    await timed("start over yes", page.click('[data-testid="start-over-yes"]'), '[data-testid="tour-start"]')


async def walk_tour(page, timed, errs):
    await timed("tour start", page.click('[data-testid="tour-start"]'), '[data-testid="tour-pop"]')
    for n in range(40):
        pop = page.locator('[data-testid="tour-pop"]')
        if not await pop.count():
            break
        txt = (await pop.inner_text()).split("\n")
        title = txt[1] if len(txt) > 1 else "?"
        nxt = page.locator('[data-testid="tour-next"]')
        label = (await nxt.inner_text()) if await nxt.count() else ""
        t0 = time.perf_counter()
        if label in ("Next", "Finish"):
            await nxt.click()
        else:
            # a waiting step: do what it points at
            spot = {"Find them all": '[data-testid="auto-btn"]', "Mark a stretch": None,
                    "Take it apart": '[data-testid="analyse-btn"]', "Build your own": '[data-testid="knob-segment_s"] button >> nth=1',
                    "Run it everywhere": '[data-testid="run-btn"]', "People decide": '[data-testid="judge-btn"]',
                    "Your verdict": None, "The Library": '[data-testid^="fam-"] >> nth=0',
                    "More like these": '[data-testid="family-seed"]'}.get(title, "SKIP")
            if title == "Mark a stretch":
                box = await page.locator('[data-testid="explore-trace"] svg').bounding_box()
                await page.mouse.move(box["x"] + box["width"] * 0.30, box["y"] + 120)
                await page.mouse.down()
                await page.mouse.move(box["x"] + box["width"] * 0.36, box["y"] + 130, steps=6)
                await page.mouse.up()
            elif title == "Your verdict":
                for v in ["v-yes", "v-no", "v-yes", "v-yes", "v-unsure"]:
                    await page.click(f'[data-testid="{v}"]')
                    await page.wait_for_timeout(250)
            elif spot == "SKIP":
                errs.append(f"tour step {title!r} waits for something the walker does not know: skipped")
                await nxt.click()
            else:
                await page.click(spot)
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SHOTS / f"tour_{n:02d}.png")) if SHOTS else None
    return


SHOTS: Path | None = None


async def main():
    global SHOTS
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", default="http://127.0.0.1:8900")
    ap.add_argument("--visitors", type=int, default=1)
    ap.add_argument("--shots", default=str(ROOT / "DATA/neurips_demo/shots"))
    ap.add_argument("--tour", action="store_true")
    ap.add_argument("--stress", action="store_true", help="after the walks: a busy visitor and an operator reset")
    ap.add_argument("--admin-key", default="booth")
    a = ap.parse_args()
    SHOTS = Path(a.shots) if a.shots else None
    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
    report: dict = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        keep = [] if a.stress else None
        t0 = time.perf_counter()
        await asyncio.gather(*(visitor(browser, a.hub, k, SHOTS if k == 0 else None, a.tour, report, keep)
                               for k in range(a.visitors)))
        report["wall_s"] = round(time.perf_counter() - t0, 1)
        if a.stress:
            await stress_after(browser, a.hub, a.admin_key, keep, report)
        await browser.close()
    bad = 0
    for v in report["visitors"]:
        slow = {k: t for k, t in v["times"].items() if t > 1.0}
        print(f"visitor {v['k']} on {v['station'].split('#')[0]}: {len(v['times'])} steps, "
              f"median {sorted(v['times'].values())[len(v['times']) // 2]:.2f} s, slow {slow}")
        for e in v["errors"] + v["failed"]:
            print("   !", e[:300])
            bad += 1
    for prob in report.get("stress", []):
        print("   ! stress:", prob)
        bad += 1
    if "wall_s" in report:
        print(f"{len(report['visitors'])} visitors in parallel, {report['wall_s']} s wall")
    stations = report["stations"]
    if len(set(stations)) != len(stations):
        print("   ! two visitors were given the same station:", stations)
        bad += 1
    (ROOT / "DATA/neurips_demo/walk_report.json").write_text(json.dumps(report, indent=1))
    print("OK" if not bad else f"{bad} problem(s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    asyncio.run(main())
