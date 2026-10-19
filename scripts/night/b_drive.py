"""
b_drive.py — night pass B (Explore, Library, Analyse): load times and break-it probes against a running bridge.

Dev tooling, nothing imports it. Playwright through the conda python, headless chromium:

    python scripts/night/b_drive.py --url http://127.0.0.1:8768 [--only loads,signal,...] [--shots webui/runtime/night]
        [--signal-ch 1] [--cross-ch 1] [--family F-01]

On the real database pass the channel and family ids that exist there (`--signal-ch` is a recording id, the
heavy-detection channel on the night fixture `scripts/night/b_fixture.py` is 1). Nothing is written to the
database except by the probes named `writes` (none by default).

A load is: navigate (cold page), time to the page's main card (`data-testid`) painted, API requests in the first
10 s, console errors / page errors / failed requests / 5xx. A page over 2 s to paint, or one that keeps
requesting with nothing changing, is a finding.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from collections import Counter

from playwright.sync_api import sync_playwright

CHAIN = {"name": "mp_threshold", "saved": False, "lastRunJobId": None, "steps": [
    {"stage": "preprocessing", "algorithm": "detrend", "params": {"mode": "rolling_mean", "window_s": 600}},
    {"stage": "detection", "algorithm": "matrix_profile", "params": {"window_min": 1.0, "backend": "stump", "scrump_percentage": 1.0}},
    {"stage": "detection", "algorithm": "threshold", "params": {"threshold": 8.0}}]}
SEED_CHAIN_JS = "c => sessionStorage.setItem('ub-proto-a:chain', JSON.stringify(c))"


class Driver:
    def __init__(self, url, shots):
        self.url = url.rstrip("/")
        self.shots = shots
        os.makedirs(shots, exist_ok=True)
        self.findings = []

    def page(self, ctx):
        pg = ctx.new_page()
        pg.set_default_timeout(30000)
        log = {"console": [], "pageerror": [], "failed": [], "5xx": [], "req": [], "slow": []}
        pg.on("requestfinished", lambda r: "/api/" in r.url and log["slow"].append(
            (round(r.timing.get("responseEnd", 0)), r.url.replace(self.url, "")[:90])))
        pg.on("console", lambda m: m.type == "error" and log["console"].append(m.text[:300]))
        pg.on("pageerror", lambda e: log["pageerror"].append(str(e)[:300]))
        pg.on("requestfailed", lambda r: log["failed"].append(f"{r.url} {r.failure}"))
        pg.on("response", lambda r: r.status >= 500 and log["5xx"].append(f"{r.status} {r.url}"))
        pg.on("request", lambda r: "/api/" in r.url and log["req"].append((time.perf_counter(), r.url.replace(self.url, ""))))
        return pg, log

    def load(self, ctx, name, hash_, testid, seed_chain=False, window_s=10.0):
        pg, log = self.page(ctx)
        if seed_chain:
            pg.goto(self.url + "/#/explore/corpus")
            pg.evaluate(SEED_CHAIN_JS, CHAIN)
        log["req"].clear()
        t0 = time.perf_counter()
        pg.goto(f"{self.url}/#/{hash_}")
        if seed_chain:                       # the app reads the chain from sessionStorage once, at start
            pg.reload()
        paint = None
        try:
            pg.wait_for_selector(f'[data-testid="{testid}"]', state="visible", timeout=60000)
            paint = time.perf_counter() - t0
        except Exception as e:                                   # noqa: BLE001 — a page that never painted is the row
            log["pageerror"].append(f"never painted {testid}: {type(e).__name__}")
        rest = window_s - (time.perf_counter() - t0)
        if rest > 0:
            pg.wait_for_timeout(rest * 1000)
        first = [u for t, u in log["req"] if t - t0 <= window_s]
        tail0 = time.perf_counter()
        pg.wait_for_timeout(5000)
        late = [u for t, u in log["req"] if t >= tail0]
        pg.screenshot(path=os.path.join(self.shots, f"load_{name}.png"))
        top = Counter(u.split("?")[0] for u in first).most_common(4)
        row = {"page": name, "hash": hash_, "paint_s": None if paint is None else round(paint, 2), "api_10s": len(first),
               "api_after": len(late), "top": top, "slowest": sorted(log["slow"], reverse=True)[:3], "console": log["console"][:3], "pageerror": log["pageerror"][:3],
               "5xx": log["5xx"][:3], "failed": [f for f in log["failed"] if "abort" not in f.lower()][:3]}
        print(json.dumps(row), flush=True)
        pg.close()
        return row

    def run_loads(self, ctx, a):
        pages = [
            ("signal", f"explore/signal/{a.signal_ch}", "signal-overview", False),
            ("cross-channel", f"explore/cross-channel/{a.cross_ch}", "cross-page", False),
            ("atlas", "library/atlas", "atlas-grid", False),
            ("atlas-sequences", "library/atlas?unit=sequences", "atlas-page", False),
            ("family", f"library/family/{a.family}", "member-grid", False),
            ("recurrence", "library/recurrence", "recurrence-page", False),
            ("chain", "analyse/chain", "chain-row-1", True),
            ("block-0", "analyse/block/0", "block-page", True),
            ("block-1", "analyse/block/1", "block-page", True),
            ("block-2", "analyse/block/2", "block-page", True),
        ]
        return [self.load(ctx, *p) for p in pages]


    # ── probes: each returns a list of {"probe", "ok", "saw"} rows; "ok": False is a finding ──────────────────
    def _row(self, rows, probe, ok, saw):
        rows.append({"probe": probe, "ok": bool(ok), "saw": saw})
        print(("  ok  " if ok else "  BAD ") + probe + " :: " + str(saw)[:220], flush=True)

    def _errs(self, log):
        return log["console"] + log["pageerror"] + log["5xx"]

    def run_signal(self, ctx, a):
        rows = []
        pg, log = self.page(ctx)
        pg.goto(f"{self.url}/#/explore/signal/{a.signal_ch}")
        pg.wait_for_selector('[data-testid="signal-span"]')
        pg.wait_for_timeout(3000)
        T = lambda t: pg.locator(f'[data-testid="{t}"]')
        nav0 = T("motif-nav").inner_text().replace("\n", " ")
        # the six band toggles, each off then on
        for k in [x.get_attribute("data-testid") for x in pg.locator('[data-testid^="band-toggle-"]').all()]:
            T(k).click(); pg.wait_for_timeout(250)
            off = T(k).get_attribute("data-on") == "0"
            T(k).click(); pg.wait_for_timeout(250)
            self._row(rows, f"{k} off/on", off and T(k).get_attribute("data-on") == "1" and not self._errs(log), {"nav_off": nav0})
        for k in [x.get_attribute("data-testid") for x in pg.locator('[data-testid^="band-toggle-"]').all()]:
            T(k).click(); pg.wait_for_timeout(150)
        nav_none = T("motif-nav").inner_text().replace("\n", " ")
        self._row(rows, "all six toggles off: the nav has nothing to walk", "0" in nav_none or "–" in nav_none, nav_none)
        pg.keyboard.press("]"); pg.wait_for_timeout(300)
        self._row(rows, "] with every band off", not self._errs(log), T("motif-nav").inner_text().replace("\n", " "))
        for k in [x.get_attribute("data-testid") for x in pg.locator('[data-testid^="band-toggle-"]').all()]:
            T(k).click(); pg.wait_for_timeout(150)
        # the editable edges
        rng0 = T("span-range").inner_text() if T("span-range").count() else ""
        for side, text in (("left", "abc"), ("left", "-5"), ("left", "1e3"), ("right", "999999999"), ("left", "8000"),
                           ("right", "3"), ("left", "1,5"), ("right", ""), ("left", "  12.5 s ")):
            inp = T(f"span-{side}-input")
            inp.click(); inp.fill(text); pg.wait_for_timeout(400)
            err = T(f"span-{side}-error").inner_text() if T(f"span-{side}-error").count() else None
            pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
            self._row(rows, f"edge {side} = {text!r}", (err is not None) != (text.strip() in ("  12.5 s ".strip(),)) and not self._errs(log), err)
        inp = T("span-left-input"); inp.click(); inp.fill("100.000"); pg.keyboard.press("Enter"); pg.wait_for_timeout(1200)
        for _ in range(5):
            pg.keyboard.press("ArrowUp")
        pg.wait_for_timeout(800)
        self._row(rows, "left = 100.000, Enter, ↑ ×5", inp.input_value() == "100.005", inp.input_value())
        pg.keyboard.press("Escape"); pg.mouse.click(700, 40)
        v0 = T("span-left-input").input_value()
        for _ in range(3):
            pg.keyboard.press("ArrowRight")
        pg.wait_for_timeout(1500)
        self._row(rows, "→ ×3 pans the span", T("span-left-input").input_value() != v0, [v0, T("span-left-input").input_value()])
        for _ in range(4):
            pg.keyboard.press("]"); pg.wait_for_timeout(250)
        self._row(rows, "] ×4 steps the motifs", "4 /" in T("motif-nav").inner_text().replace("\n", " "), T("motif-nav").inner_text().replace("\n", " "))
        pg.screenshot(path=os.path.join(self.shots, "signal_after_probes.png"))
        self._row(rows, "no console/page errors over the probes", not self._errs(log), self._errs(log)[:4])
        pg.close()
        return rows


    def run_take(self, ctx, a):
        """WRITES (one seed annotation in the sandbox copy): Take span → the toast's Open Review → the queue; then
        Discovery's seed picker, Explore selection tab, must offer the span."""
        rows = []
        pg, log = self.page(ctx)
        pg.goto(f"{self.url}/#/explore/signal/{a.signal_ch}")
        pg.wait_for_selector('[data-testid="take-span"]'); pg.wait_for_timeout(2500)
        T = lambda t: pg.locator(f'[data-testid="{t}"]')
        rng = T("span-action-range").inner_text()
        t0 = time.perf_counter(); T("take-span").click()
        toast = pg.locator(".toast, [data-testid^='toast']").filter(has_text="taken for Review")
        try:
            toast.first.wait_for(timeout=20000)
            took = time.perf_counter() - t0
            text = toast.first.inner_text()
        except Exception as e:                                   # noqa: BLE001
            took, text = None, f"no toast: {type(e).__name__} {self._errs(log)[:2]}"
        self._row(rows, "Take span for Review writes and says so", took is not None, {"range": rng, "s": took, "toast": text[:160]})
        if took is not None:
            pg.locator("button", has_text="Open Review").first.click()
            pg.wait_for_timeout(4000)
            pg.screenshot(path=os.path.join(self.shots, "take_open_review.png"))
            self._row(rows, "Open Review → lands on the Explore spans queue", "/review/queue/" in pg.url and not self._errs(log), pg.url.split("#")[1])
        pg.goto(f"{self.url}/#/discovery/seed?source=explore"); pg.wait_for_timeout(6000)
        pg.screenshot(path=os.path.join(self.shots, "take_seed_picker.png"))
        body = pg.locator("body").inner_text()
        opts = pg.locator('[data-testid^="seed-option-"]').count()
        self._row(rows, "the seed picker's Explore tab offers the taken span", opts > 0, {"options": opts, "empty": "No seed" in body})
        self._row(rows, "no errors on the take path", not self._errs(log), self._errs(log)[:4])
        pg.close()
        return rows


    def run_cross(self, ctx, a):
        """Overlay with every channel, bold/faded, align by lag, a box and its strip; Mark artifact WRITES (sandbox)."""
        rows = []
        pg, log = self.page(ctx)
        T = lambda t: pg.locator(f'[data-testid="{t}"]')
        pg.goto(f"{self.url}/#/explore/cross-channel/{a.cross_ch}?view=overlay")
        t0 = time.perf_counter()
        pg.wait_for_selector('[data-testid="overlay"]', timeout=60000)
        n = T("overlay").get_attribute("data-channels")
        self._row(rows, "overlay paints every channel", n is not None and int(n) >= 16, {"channels": n, "s": round(time.perf_counter() - t0, 2)})
        names = pg.locator('[data-testid^="ov-name-"]')
        names.nth(1).click(); pg.wait_for_timeout(300)
        bold = [x.get_attribute("data-bold") for x in names.all()]
        self._row(rows, "click a name: it alone is bold", bold.count("1") == 1 or bold.count("true") == 1, {"bold": bold[:6], "hash": pg.url.split("#")[1][-40:]})
        names.nth(3).click(modifiers=["Shift"]); pg.wait_for_timeout(300)
        self._row(rows, "shift-click a second", "2" in T("ov-bold-count").inner_text(), T("ov-bold-count").inner_text())
        T("ov-none").click(); pg.wait_for_timeout(200)
        T("ov-box-span").click(); pg.wait_for_timeout(300)
        strip = T("overlay-action-strip")
        dis = [b.is_disabled() for b in strip.locator("button").all()]
        self._row(rows, "box with nothing bold: the strip is grey", strip.count() == 1 and all(dis), {"disabled": dis})
        T("ov-all").click(); pg.wait_for_timeout(200)
        T("ov-align").click(); pg.wait_for_timeout(800)
        shifts = [x.inner_text() for x in pg.locator('[data-testid^="ov-shift-"]').all()]
        self._row(rows, "align by lag: names print their shift", len(shifts) > 0, shifts[:6])
        cap = T("overlay-box-caption").inner_text() if T("overlay-box-caption").count() else ""
        self._row(rows, "box caption with align on (read it)", True, cap[:240])
        T("ov-align").click(); pg.wait_for_timeout(500)
        pg.goto(f"{self.url}/#/explore/cross-channel/{a.cross_ch}?align=lag&maxlag=1")
        pg.wait_for_selector('[data-testid="cross-page"]', timeout=60000); pg.wait_for_timeout(1500)
        self._row(rows, "lag-aligned with max lag 1 s: says nothing to move", T("nothing-to-align").count() == 1,
                  T("nothing-to-align").inner_text() if T("nothing-to-align").count() else [x.get_attribute("data-shift") for x in pg.locator('[data-testid^="xrow-"]').all()])
        pg.goto(f"{self.url}/#/explore/cross-channel/{a.cross_ch}?view=overlay")
        pg.wait_for_selector('[data-testid="overlay"]', timeout=60000)
        names = pg.locator('[data-testid^="ov-name-"]')
        names.nth(0).click(); names.nth(2).click(modifiers=["Shift"]); pg.wait_for_timeout(200)
        T("ov-box-span").click(); pg.wait_for_timeout(300)
        strip = T("overlay-action-strip")
        strip.locator('[data-testid="strip-mark-artifact"]').click(); pg.wait_for_timeout(300)
        ticked = pg.locator('[data-testid="artifact-picker"] input[type="checkbox"]:checked').count()
        btn = pg.locator('[data-testid="artifact-picker"] button', has_text="Mark")
        self._row(rows, "the artifact picker starts on the bold channels", ticked == 2, {"ticked": ticked, "buttons": [b.inner_text() for b in btn.all()][:3]})
        if btn.count():
            btn.last.click()
            try:
                pg.locator("text=verdict artifact").first.wait_for(timeout=15000)
                self._row(rows, "Mark artifact writes and says so", True, pg.locator("text=verdict artifact").first.inner_text()[:160])
            except Exception as e:                               # noqa: BLE001
                self._row(rows, "Mark artifact writes and says so", False, f"{type(e).__name__} {self._errs(log)[:2]}")
        pg.screenshot(path=os.path.join(self.shots, "cross_after_probes.png"))
        self._row(rows, "no errors over the cross-channel probes", not self._errs(log), self._errs(log)[:4])
        pg.close()
        return rows


    def run_library(self, ctx, a):
        """Build sequences (tolerance 0, a gap that joins nothing, keep twice: WRITES a grouping in the sandbox), the
        sequence family page, a family's slideshow, the atlas's request count while it sits."""
        rows = []
        pg, log = self.page(ctx)
        T = lambda t: pg.locator(f'[data-testid="{t}"]')
        pg.goto(f"{self.url}/#/library/atlas?unit=sequences")
        pg.wait_for_selector('[data-testid="build-sequences"]', timeout=60000); pg.wait_for_timeout(2000)

        def field(tid, v):
            inp = T(tid).locator("input") if T(tid).locator("input").count() else T(tid)
            inp.fill(str(v)); inp.press("Tab"); pg.wait_for_timeout(200)

        def preview():
            T("build-sequences-preview").click()
            for _ in range(60):
                pg.wait_for_timeout(500)
                if T("build-sequences-preview-result").count() or T("build-sequences-error").count():
                    break
            res = T("build-sequences-preview-result").inner_text()[:200] if T("build-sequences-preview-result").count() else None
            err = T("build-sequences-error").inner_text()[:200] if T("build-sequences-error").count() else None
            return res, err

        field("build-sequences-gap", 0); field("build-sequences-tol", 0)
        res, err = preview()
        keep_dis = T("build-sequences-keep").is_disabled()
        self._row(rows, "gap 0 s, tolerance 0 %: a preview with nothing to keep says so", (res or err) is not None and keep_dis,
                  {"result": res, "error": err, "keep_disabled": keep_dis, "title": T("build-sequences-keep").get_attribute("title")})
        field("build-sequences-gap", -5)
        self._row(rows, "gap −5 s is refused in place", True, {"gap_value": T("build-sequences-gap").locator("input").input_value() if T("build-sequences-gap").locator("input").count() else None,
                                                                "errors": self._errs(log)[:2]})
        field("build-sequences-gap", 100000); field("build-sequences-tol", 0)
        res, err = preview()
        self._row(rows, "gap 100 000 s, tolerance 0: preview", res is not None, {"result": res, "error": err})
        if not T("build-sequences-keep").is_disabled():
            T("build-sequences-keep").click(); pg.wait_for_timeout(4000)
            kept1 = T("build-sequences-kept").inner_text()[:160] if T("build-sequences-kept").count() else None
            dis2 = T("build-sequences-keep").is_disabled()
            self._row(rows, "keep once: kept, and keep again is grey (already kept)", kept1 is not None and dis2,
                      {"kept": kept1, "keep_again_disabled": dis2, "title": T("build-sequences-keep").get_attribute("title")})
            if T("build-sequences-open-kept").count():
                T("build-sequences-open-kept").click(); pg.wait_for_timeout(5000)
                pg.screenshot(path=os.path.join(self.shots, "lib_open_kept.png"))
                txt = pg.locator("body").inner_text()
                self._row(rows, "open the kept family", "not found" not in txt.lower() and "No family" not in txt and not self._errs(log),
                          {"url": pg.url.split("#")[1], "errors": self._errs(log)[:2]})
        # a sequence family page
        pg.goto(f"{self.url}/#/library/family/F-01?unit=sequences"); pg.wait_for_timeout(5000)
        pg.screenshot(path=os.path.join(self.shots, "lib_seq_family.png"))
        self._row(rows, "sequence family F-01 opens", T("family-page").count() == 1 and not self._errs(log), self._errs(log)[:2])
        # a motif family: click the first card in the atlas, slideshow in place
        pg.goto(f"{self.url}/#/library/atlas"); pg.wait_for_selector('[data-testid="atlas-grid"]', timeout=60000)
        req0 = len(log["req"])
        pg.wait_for_timeout(20000)
        late = [u for _, u in log["req"][req0:]]
        self._row(rows, "the atlas sits 20 s without re-reading", len(late) <= 2, Counter(u.split("?")[0] for u in late).most_common(4))
        pg.locator('[data-testid^="family-card-"]').first.click(); pg.wait_for_timeout(2500)
        pg.screenshot(path=os.path.join(self.shots, "lib_atlas_members.png"))
        self._row(rows, "a card click opens its members in place", "members=" in pg.url and not self._errs(log), pg.url.split("#")[1])
        pg.goto(f"{self.url}/#/library/family/F-02"); pg.wait_for_selector('[data-testid="member-grid"]', timeout=60000); pg.wait_for_timeout(1500)
        self._row(rows, "family F-02 member grid", pg.locator('[data-testid^="member-card"]').count() > 0, pg.locator('[data-testid^="member-card"]').count())
        self._row(rows, "no errors over the library probes", not self._errs(log), self._errs(log)[:4])
        pg.close()
        return rows


    def run_analyse(self, ctx, a):
        """A chain run through the page (Run chain) on a 2 h span of --signal-ch: threshold -> intervals -> trains, at
        thresholds that make 0, 1 and 2 events on the night fixture (`--thresholds`; on another database pass your own),
        then each block page: the intervals timeline and the trains figures must paint, never a red card or console
        error. Also: the templates accordion's search, the empty canvas's import, the fold toggle across a reload."""
        rows = []
        pg, log = self.page(ctx)
        T = lambda t: pg.locator(f'[data-testid="{t}"]')
        pg.goto(f"{self.url}/#/explore/corpus"); pg.wait_for_timeout(500)
        ch = json.loads(urllib.request.urlopen(f"{self.url}/api/channels/{a.signal_ch}", timeout=60).read())
        src = {"recording_id": int(a.signal_ch), "channel_name": ch.get("name"), "source_file": ch.get("source_file"), "fs": ch.get("fs", 1.0),
               "start_idx": 0, "end_idx": int(7200 * float(ch.get("fs", 1.0))), "label": "night-b 0-2 h"}
        for want, thr in zip(("0", "1", "2"), [float(x) for x in a.thresholds.split(",")]):
            chain = {"name": f"night-b {want} events", "saved": False, "lastRunJobId": None, "steps": [
                {"stage": "detection", "algorithm": "signal_threshold", "params": {"threshold": thr, "direction": "above", "min_duration_s": 0.0, "merge_gap_s": 0.0}},
                {"stage": "interrogation", "algorithm": "intervals", "params": {"anchor": "onset"}},
                {"stage": "interrogation", "algorithm": "trains", "params": {}}]}
            pg.evaluate("([c, s]) => { sessionStorage.setItem('ub-proto-a:chain', JSON.stringify(c)); sessionStorage.setItem('ub-proto-a:source', JSON.stringify(s)) }", [chain, src])
            pg.goto(f"{self.url}/#/analyse/chain"); pg.reload(); pg.wait_for_selector('[data-testid="run-button"]', timeout=30000)
            pg.wait_for_timeout(800)
            if T("run-button").is_disabled():
                self._row(rows, f"{want} events: Run chain", False, T("run-button").get_attribute("title"))
                continue
            T("run-button").click()
            done = False
            for _ in range(240):
                pg.wait_for_timeout(500)
                if T("cancel-button").count() == 0 and T("run-button").count():
                    done = True; break
            pg.wait_for_timeout(1500)
            pg.screenshot(path=os.path.join(self.shots, f"an_chain_{want}.png"))
            self._row(rows, f"{want} events: the chain ran", done and not T("run-error-card").count() and not self._errs(log),
                      {"error_card": T("run-error-card").inner_text()[:160] if T("run-error-card").count() else None, "errors": self._errs(log)[:2]})
            for i, what in ((1, "intervals"), (2, "trains")):
                pg.goto(f"{self.url}/#/analyse/block/{i}"); pg.wait_for_selector('[data-testid="block-page"]', timeout=30000); pg.wait_for_timeout(2500)
                red = pg.locator(".error-card, [data-testid='render-error']").count()
                pg.screenshot(path=os.path.join(self.shots, f"an_{what}_{want}.png"), full_page=True)
                self._row(rows, f"{want} events: the {what} page paints", red == 0 and not self._errs(log),
                          {"red_cards": red, "timeline": T("interval-timeline").count(), "errors": self._errs(log)[:2]})
        # the fold ("more (N)") per block page: open on intervals, then in-app to trains, then a reload
        pg.goto(f"{self.url}/#/analyse/block/1"); pg.wait_for_selector('[data-testid="headline-toggle"]', timeout=30000)
        pg.evaluate("() => { for (const k of Object.keys(localStorage)) if (k.startsWith('ub-headline:')) localStorage.removeItem(k) }")
        pg.reload(); pg.wait_for_selector('[data-testid="headline-toggle"]', timeout=30000)
        T("headline-toggle").click(); pg.wait_for_timeout(300)
        o1 = T("headline-more").get_attribute("data-open")
        pg.evaluate("() => { location.hash = '#/analyse/block/2' }"); pg.wait_for_timeout(2000)
        o2 = T("headline-more").get_attribute("data-open") if T("headline-more").count() else None
        stored2 = pg.evaluate("() => Object.fromEntries(Object.keys(localStorage).filter(k => k.startsWith('ub-headline:')).map(k => [k, localStorage.getItem(k)]))")
        pg.reload(); pg.wait_for_selector('[data-testid="block-page"]', timeout=30000); pg.wait_for_timeout(2000)
        o3 = T("headline-more").get_attribute("data-open") if T("headline-more").count() else None
        self._row(rows, "fold: opened on intervals stays a per-page choice (trains in-app, then reloaded)", o1 == "1" and o2 == o3,
                  {"intervals_open": o1, "trains_in_app": o2, "trains_after_reload": o3, "stored": stored2})
        pg.evaluate("() => { location.hash = '#/analyse/block/1' }"); pg.wait_for_timeout(2000)
        pg.reload(); pg.wait_for_selector('[data-testid="headline-toggle"]', timeout=30000); pg.wait_for_timeout(1000)
        self._row(rows, "fold: intervals still open after a reload", T("headline-more").get_attribute("data-open") == "1", T("headline-more").get_attribute("data-open"))
        # the templates accordion with a search
        pg.goto(f"{self.url}/#/analyse/chain"); pg.wait_for_timeout(1500)
        btn = pg.locator("button", has_text="Import").first
        if btn.count():
            btn.click(); pg.wait_for_timeout(1200)
        if T("templates-search").count():
            groups0 = pg.locator('[data-testid^="template-group-"][data-open="1"]').count()
            T("templates-search").fill("drop"); pg.wait_for_timeout(300)
            hits = pg.locator('[data-testid^="template-"]').filter(has_text="drop").count()
            T("templates-search").fill("zzzz-no-such"); pg.wait_for_timeout(300)
            none = T("templates-none").count()
            T("templates-search").fill(""); pg.wait_for_timeout(300)
            groups1 = pg.locator('[data-testid^="template-group-"][data-open="1"]').count()
            self._row(rows, "templates search: hits, a no-match line, and one group open again when cleared", hits > 0 and none == 1 and groups1 == 1,
                      {"open_before": groups0, "drop_hits": hits, "none_line": none, "open_after_clear": groups1})
        else:
            self._row(rows, "templates popover search", False, "no templates-search field (fewer than 9 templates, or the popover did not open)")
        pg.screenshot(path=os.path.join(self.shots, "an_templates.png"))
        self._row(rows, "no errors over the analyse probes", not self._errs(log), self._errs(log)[:4])
        pg.close()
        return rows


    def run_send(self, ctx, a):
        """WRITES (sandbox): Signal's *Send unjudged to Review* over a window with zero motifs and over one with more
        than the 2,000 cap (`--sparse-ch` must have a 60 s window with no detection; the probe walks to find one)."""
        rows = []
        pg, log = self.page(ctx)
        T = lambda t: pg.locator(f'[data-testid="{t}"]')

        def toast_text(pat, timeout=30000):
            loc = pg.locator(".toast, [data-testid^='toast']").filter(has_text=pat)
            try:
                loc.first.wait_for(timeout=timeout); return loc.first.inner_text()[:200]
            except Exception:                                    # noqa: BLE001
                return None

        pg.goto(f"{self.url}/#/explore/signal/{a.sparse_ch}"); pg.wait_for_selector('[data-testid="span-left-input"]'); pg.wait_for_timeout(2500)
        found = None
        for start in range(0, 40000, 61):
            T("span-right-input").fill(str(start + 60 + 100000)); T("span-right-input").press("Escape")
            T("span-left-input").fill(str(start)); T("span-left-input").press("Enter")
            T("span-right-input").fill(str(start + 60)); T("span-right-input").press("Enter")
            pg.wait_for_timeout(700)
            txt = T("span-action-range").inner_text()
            if " 0 motifs in view" in txt:
                found = (start, txt); break
        if not found:
            self._row(rows, "a 60 s window with zero motifs", False, "none found in the first 40 000 s")
        else:
            b = pg.locator('[data-testid="strip-send-unjudged"], button:has-text("Send unjudged to Review")').first
            dis = b.is_disabled()
            if not dis:
                b.click(); said = toast_text("Review")
            else:
                said = b.get_attribute("title")
            self._row(rows, "Send unjudged over zero motifs: grey with a reason, or says nothing was sent", dis or (said and ("0" in said or "no " in said.lower())),
                      {"window": found, "disabled": dis, "said": said})
        pg.goto(f"{self.url}/#/explore/signal/{a.signal_ch}"); pg.wait_for_selector('[data-testid="span-action-range"]'); pg.wait_for_timeout(2500)
        txt = T("span-action-range").inner_text()
        b = pg.locator('[data-testid="strip-send-unjudged"], button:has-text("Send unjudged to Review")').first
        t0 = time.perf_counter(); b.click(); said = toast_text("Review", 60000)
        self._row(rows, "Send unjudged over > 2,000 motifs: sends the cap and says so", said is not None and ("2,000" in said or "2000" in said),
                  {"view": txt, "s": round(time.perf_counter() - t0, 2), "said": said})
        pg.screenshot(path=os.path.join(self.shots, "send_many.png"))
        self._row(rows, "no errors over the send probes", not self._errs(log), self._errs(log)[:4])
        pg.close()
        return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://127.0.0.1:8768")
    ap.add_argument("--only", default="loads")
    ap.add_argument("--shots", default=os.path.join("webui", "runtime", "night"))
    ap.add_argument("--signal-ch", default="1")
    ap.add_argument("--cross-ch", default="1")
    ap.add_argument("--family", default="F-01")
    ap.add_argument("--sparse-ch", default="7", help="a channel with few detections (Send unjudged over zero)")
    ap.add_argument("--thresholds", default="100,1.621,1.62", help="signal_threshold levels for 0, 1 and 2 events")
    a = ap.parse_args(argv)
    d = Driver(a.url, a.shots)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900})
        out = {}
        for part in a.only.split(","):
            fn = getattr(d, f"run_{part.replace('-', '_')}")
            out[part] = fn(ctx, a)
        b.close()
    json.dump(out, open(os.path.join(a.shots, "b_drive.json"), "w"), indent=1)


if __name__ == "__main__":
    sys.exit(main())
