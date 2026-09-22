"""Smoke test + screenshot capture for the web UI (webui/).

    "/c/ProgramData/anaconda3/python.exe" smoke.py [--url http://127.0.0.1:8765] [--no-run]

Fails (non-zero exit) if:
  * any browser console error or page error occurs on any view (a render error that
    reaches the console is loud by design — the ErrorBoundary logs it);
  * a pane that must paint did not: the corpus heatmap has < 800 filled cells, an
    envelope path has an empty `d`, the chain rows have no plot path/rects/canvas;
  * the server log contains a traceback that was not deliberately provoked;
  * a Must-view flow (open channel → send span → run chain → suffix re-run) breaks.

Screenshots land in screenshots/<nn>-<name>.png, paired to concept frames in REPORT.md.
Uses the repo's Playwright (conda python), not a Node harness.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.environ.get("SMOKE_SHOTS") or os.path.join(HERE, "screenshots")   # two agents' smoke runs must not write the same files

#: Discovery's page states walk live content, so the smoke run first makes two
#: real runs over this section (stage-3 prompt 04). Four hours of two channels
#: is small enough to run in seconds and large enough to have reviewed
#: coverage, which is what gives the scoreboard a denominator.
SMOKE_SECTION_H = (80.0, 84.0)
SMOKE_TEMPLATE = "mp_threshold"
#: added but never started, so the Runs page has something pending to route
SMOKE_PENDING_TEMPLATE = "drop_detection_v1"
#: The k the seed page itself asks for (SeedPage.tsx::SEED_K). A result computed
#: under a different k is a different cache key and the page finds nothing.
SMOKE_SEED_K = 200
#: The seed run's key. Pinned so the page states can name it.
SMOKE_SEED_RUN = "smoke_seed"


class Smoke:
    def __init__(self, url: str, run_chain: bool, pages_only: bool = False, only: str | None = None):
        self.url = url.rstrip("/")
        self.run_chain = run_chain
        self.pages_only = pages_only
        self.only = only
        self.errors: list[str] = []
        self.failures: list[str] = []
        self.shots: list[str] = []
        self.evidence: dict = {}
        self.n = 0

    # ------------------------------------------------------------ helpers --
    def shot(self, page, name: str):
        self.n += 1
        path = os.path.join(SHOTS, f"{self.n:02d}-{name}.png")
        page.screenshot(path=path, full_page=False)
        if os.path.getsize(path) > 1_000_000:          # gitignore rule: *.big.png
            big = path.replace(".png", ".big.png"); os.replace(path, big); path = big
        self.shots.append(path)
        return path

    def check(self, cond: bool, msg: str):
        if not cond:
            self.failures.append(msg)
            print("  FAIL:", msg)
        else:
            print("  ok:", msg)

    #: JS that measures every `.time-axis` label on the page and returns the
    #: overlapping pairs. `d3`'s `.ticks(n)` picks positions knowing nothing
    #: about how wide `fmtAxis` renders them, and `TimeAxis` used to de-collide
    #: only the two ends and only when `ends` was asked for (fixup-a item 17).
    #: A real browser measurement is the only honest check of a text width.
    _AXIS_OVERLAP_JS = """() => {
      const bad = [];
      for (const g of document.querySelectorAll('g.time-axis')) {
        const boxes = Array.from(g.querySelectorAll('text'))
          .map(t => ({ s: t.textContent, r: t.getBoundingClientRect() }))
          .filter(b => b.r.width > 0)
          .sort((a, b) => a.r.left - b.r.left);
        for (let i = 1; i < boxes.length; i++) {
          if (boxes[i].r.left < boxes[i - 1].r.right - 0.5) {
            bad.push(boxes[i - 1].s + ' | ' + boxes[i].s);
          }
        }
      }
      return bad;
    }"""

    def axis_labels(self, page, where: str):
        """No two time-axis labels may overlap, on any surface (fixup-a 17)."""
        bad = page.evaluate(self._AXIS_OVERLAP_JS)
        n = page.evaluate("() => document.querySelectorAll('g.time-axis text').length")
        self.evidence[f"axis_labels_{where}"] = {"labels": n, "overlaps": bad[:8]}
        self.check(not bad, f"{where}: {n} time-axis labels, none overlapping" + (f" — {bad[:4]}" if bad else ""))

    def goto(self, page, hash_: str, settle_ms=600):
        page.goto(f"{self.url}/#/{hash_}", wait_until="networkidle")
        page.wait_for_timeout(settle_ms)

    # --------------------------------------------------------------- views --
    def corpus(self, page):
        print("[corpus]")
        self.goto(page, "explore/corpus", 1200)
        page.wait_for_selector('[data-testid="corpus-heatmap"]', timeout=20000)
        cells = page.locator('[data-testid="heatmap-cell"]')
        n = cells.count()
        filled = page.evaluate("""() => Array.from(document.querySelectorAll('[data-testid="heatmap-cell"]')).filter(r => { const f = getComputedStyle(r).fill || r.getAttribute('fill'); return f && f !== 'none' }).length""")
        distinct = page.evaluate("""() => new Set(Array.from(document.querySelectorAll('[data-testid="heatmap-cell"]')).map(r => r.getAttribute('fill') || getComputedStyle(r).fill)).size""")
        self.evidence["heatmap_cells"] = n; self.evidence["heatmap_distinct_fills"] = distinct
        self.check(n >= 16 * 28, f"heatmap has {n} cells (>= 448)")
        self.check(filled >= 800, f"heatmap painted {filled} cells (>= 800)")
        self.check(distinct >= 3, f"heatmap uses {distinct} distinct fills (>= 3, i.e. real counts, not one colour)")
        self.check(page.locator('[data-testid="nav-rail"]').count() == 1, "nav rail present")
        self.check(page.locator('[data-testid="header"]').count() == 1, "header present")
        self.axis_labels(page, "corpus")

        # fixup-a 6: "N need you" is the live route's number, never a constant.
        # The chip adds this tab's failed runs to it, so the chip's own title
        # carries the review figure apart and THAT is what is compared.
        need = page.locator('[data-testid="need-you"]')
        self.check(need.count() == 1, "the header's need-you chip is present")
        if need.count():
            title = need.first.get_attribute("title") or ""
            counts = json.load(__import__("urllib.request").request.urlopen(self.url + "/api/review/counts"))
            live = int(counts.get("need_you") or 0)
            said = int(re.match(r"\s*(\d+)", title).group(1)) if re.match(r"\s*(\d+)", title) else -1
            self.evidence["need_you"] = {"route": live, "header": said, "chip": need.first.inner_text().strip()}
            self.check(said == live, f"the header's review count is /api/review/counts ({said} vs {live})")

        # fixup-a 13/14: the rail's tag filter is a MultiPick over the LIVE
        # vocabulary, and nothing on this page claims the database has no tags
        rail = page.locator('[data-testid="corpus-rail"]')
        rail_txt = rail.inner_text().lower() if rail.count() else ""
        self.check("no tags in this database" not in rail_txt and "has no tags" not in rail_txt,
                   "the rail no longer claims this database has no tags")
        self.check(rail.count() == 1 and rail.locator('[data-testid="demo-tag"]').count() == 0,
                   "no demo chip is left on the Corpus rail (every read on it is live)")
        tagpick = page.locator('[data-testid="rail-tags"]')
        self.check(tagpick.count() == 1, "the Morphology tag filter is the rail's MultiPick, not 36 checkboxes")
        if tagpick.count():
            tagpick.first.click(); page.wait_for_timeout(400)
            opts = page.locator('[data-testid^="rail-tags-opt-"]').count()
            self.evidence["rail_tag_terms"] = opts
            self.check(opts >= 10, f"the tag list offers {opts} live vocabulary terms")
            self.shot(page, "explore-1-corpus-tag-picker")
            page.keyboard.press("Escape"); page.wait_for_timeout(300)
        self.shot(page, "explore-1-corpus")
        # colour-by toggle
        for label in ("detections", "disagree", "both"):
            b = page.get_by_role("button", name=re.compile(rf"^{label}$", re.I))
            if b.count():
                b.first.click(); page.wait_for_timeout(500)
        self.shot(page, "explore-1-corpus-colour-by")
        # select a channel row
        row = page.locator('[data-testid="heatmap-row-CH4_A2"]')
        if row.count():
            row.first.locator('[data-testid="heatmap-cell"]').first.click(); page.wait_for_timeout(400)
        bar = page.locator('[data-testid="corpus-bottom-bar"]')
        self.check(bar.count() == 1 and "annotations" in bar.inner_text().lower(), "bottom bar shows channel counts")
        self.shot(page, "explore-1-corpus-selected")
        open_btn = page.locator('[data-testid="open-channel"]')
        self.check(open_btn.count() == 1, "Open channel button present")
        open_btn.first.click()
        page.wait_for_timeout(1500)

    def signal(self, page):
        print("[signal]")
        if "explore/signal" not in page.url:
            self.goto(page, "explore/signal/4", 1500)
        page.wait_for_selector('[data-testid="signal-overview"]', timeout=20000)
        page.wait_for_timeout(1200)
        d_len = page.evaluate("""() => [document.querySelector('[data-testid="signal-overview"] path[d]'), document.querySelector('[data-testid="signal-span"] path[d], [data-testid="envelope-path"]')].map(p => p ? (p.getAttribute('d')||'').length : 0)""")
        self.evidence["envelope_path_lengths"] = d_len
        self.check(len(d_len) == 2 and all(l > 500 for l in d_len), f"overview + span envelope paths painted (d lengths {d_len})")
        bands = page.locator('[data-testid="span-bands"] rect').count()
        self.evidence["span_bands"] = bands
        self.check(bands >= 1, f"{bands} tinted span bands drawn in the viewport")
        self.axis_labels(page, "signal")
        self.shot(page, "explore-2-signal")
        # zoom in with the wheel over the span plot, measuring the latency instrumentation
        box = page.locator('[data-testid="signal-span"]').bounding_box()
        if box:
            cx, cy = box["x"] + box["width"] * 0.55, box["y"] + box["height"] * 0.5
            page.mouse.move(cx, cy)
            for _ in range(8):
                page.mouse.wheel(0, -240); page.wait_for_timeout(120)
            page.wait_for_timeout(700)
            # pan
            page.mouse.move(cx, cy); page.mouse.down(); page.mouse.move(cx - 200, cy, steps=8); page.mouse.up()
            page.wait_for_timeout(700)
        stats = page.evaluate("() => window.__zoomStats || []")
        self.evidence["zoom_stats"] = stats[-12:]
        self.check(len(stats) >= 2, f"viewport refetch instrumentation recorded {len(stats)} fetches")
        if stats:
            rts = [s.get("round_trip_ms", 0) for s in stats]
            self.evidence["zoom_round_trip_ms"] = {"min": min(rts), "max": max(rts), "median": sorted(rts)[len(rts) // 2]}
        self.shot(page, "explore-2-signal-zoomed")
        # select a motif via next-motif button
        nxt = page.locator('[data-testid="motif-next"]')
        if nxt.count():
            nxt.first.click(); page.wait_for_timeout(900)
        self.check(page.locator('[data-testid="signal-motif"]').count() == 1, "motif tier present")
        self.shot(page, "explore-2-signal-motif")
        # send span to analyse
        send = page.locator('[data-testid="send-span"]')
        self.check(send.count() == 1, "Send span to Analyse present")
        send.first.click(); page.wait_for_timeout(1200)
        self.check("analyse" in page.url, "sending a span navigates to Analyse")

    def m4(self, page):
        print("[held-out]")
        self.goto(page, "explore/signal/52", 1200)
        txt = page.locator("body").inner_text()
        self.check("held out" in txt.lower(), "M4 channel shows a held-out / locked state")
        self.shot(page, "explore-m4-held-out")

    def analyse(self, page):
        print("[analyse]")
        self.goto(page, "analyse/chain", 1500)
        page.wait_for_selector('[data-testid="chain-page"]', timeout=20000)
        page.wait_for_timeout(800)
        rows = page.locator('[data-testid^="chain-row-"]').count()
        self.check(rows >= 4, f"{rows} chain rows (source + 3 steps)")
        # the axis primitive is shared with Explore, so both workspaces check it
        self.axis_labels(page, "analyse-chain")
        self.shot(page, "chain-1-chain-before-run")
        # insert modal
        ins = page.locator('[data-testid="insert-2"]')
        if ins.count():
            ins.first.click(); page.wait_for_timeout(700)
            self.check(page.locator('[data-testid="insert-modal"]').count() == 1, "insert-stage modal opens")
            cards = page.locator('[data-testid^="modal-card-"]').count()
            self.check(cards >= 20, f"modal lists {cards} adapters")
            disabled = page.evaluate("""() => Array.from(document.querySelectorAll('[data-testid^="modal-card-"]')).filter(c => c.disabled || c.getAttribute('aria-disabled') === 'true' || /nofit|disabled|unfit/.test(c.className)).length""")
            self.check(disabled >= 10, f"{disabled} incompatible adapters shown disabled with reasons")
            self.shot(page, "chain-2-insert-stage")
            page.keyboard.press("Escape"); page.wait_for_timeout(300)
            if page.locator('[data-testid="insert-modal"]').count():
                page.get_by_role("button", name=re.compile("cancel", re.I)).first.click(); page.wait_for_timeout(300)
        if not self.run_chain:
            return
        run = page.locator('[data-testid="run-button"]')
        self.check(run.count() == 1 and run.first.is_enabled(), "run button present and enabled")
        t = time.time(); run.first.click()
        # wait for completion: the terminal footer says "last run" or a failure
        for _ in range(120):
            page.wait_for_timeout(250)
            ft = page.locator('[data-testid="footer-terminal"]').inner_text().lower() if page.locator('[data-testid="footer-terminal"]').count() else ""
            if "last run" in ft or "no result" in ft or "failed" in ft:
                break
        self.evidence["run_wall_s"] = round(time.time() - t, 2)
        badges = [page.locator(f'[data-testid="row-badge-{i}"]').inner_text().strip() for i in range(1, 4) if page.locator(f'[data-testid="row-badge-{i}"]').count()]
        self.evidence["badges_after_run"] = badges
        self.check(all(("cached" in b.lower() or "done" in b.lower()) for b in badges) and len(badges) == 3, f"all rows completed: {badges}")
        painted = page.evaluate("""() => [1,2,3].map(i => { const el = document.querySelector('[data-testid="row-plot-'+i+'"]'); if (!el) return 'missing'; const p = el.querySelector('path[d]'); const r = el.querySelectorAll('rect').length; const c = el.querySelector('canvas'); return (p && p.getAttribute('d').length > 200) ? 'path' : r > 2 ? 'rects' : c ? 'canvas' : 'blank' })""")
        self.evidence["row_plots"] = painted
        self.check(all(p != "blank" and p != "missing" for p in painted), f"every result row painted something: {painted}")
        self.shot(page, "chain-1-chain-completed")
        # block page for the threshold (step index 2) with a draggable line
        page.locator('[data-testid="settings-step-3"]').first.click() if page.locator('[data-testid="settings-step-3"]').count() else self.goto(page, "analyse/block/2", 800)
        page.wait_for_timeout(900)
        self.check(page.locator('[data-testid="block-page"]').count() == 1, "block page opens")
        line = page.locator('[data-testid="threshold-line"]')
        self.check(line.count() >= 1, "draggable threshold line present")
        self.shot(page, "chain-7b-block-threshold")
        if line.count():
            b = line.first.bounding_box()
            if b:
                page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2); page.mouse.down()
                page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2 - 30, steps=6); page.mouse.up()
                page.wait_for_timeout(600)
        self.shot(page, "chain-7b-block-threshold-dragged")
        # back to chain: rows 1,2 should be cached, 3 stale; re-run → suffix cache hit
        self.goto(page, "analyse/chain", 900)
        badges = [page.locator(f'[data-testid="row-badge-{i}"]').inner_text().strip().lower() for i in range(1, 4) if page.locator(f'[data-testid="row-badge-{i}"]').count()]
        self.evidence["badges_after_edit"] = badges
        self.check(len(badges) == 3 and "stale" in badges[2], f"editing the threshold marked row 3 stale: {badges}")
        run = page.locator('[data-testid="run-button"]')
        run.first.click()
        for _ in range(80):
            page.wait_for_timeout(250)
            ft = page.locator('[data-testid="footer-terminal"]').inner_text().lower() if page.locator('[data-testid="footer-terminal"]').count() else ""
            if "last run" in ft or "no result" in ft:
                break
        page.wait_for_timeout(400)
        badges = [page.locator(f'[data-testid="row-badge-{i}"]').inner_text().strip().lower() for i in range(1, 4)]
        titles = [page.locator(f'[data-testid="row-badge-{i}"]').get_attribute("title") or "" for i in range(1, 4)]
        self.evidence["badges_after_rerun"] = badges; self.evidence["badge_titles_after_rerun"] = titles
        self.check("cached" in badges[0] and "cached" in badges[1], f"prefix rows cached after suffix re-run: {badges}")
        self.check(any("0.0" in (b + t) or "0 s" in (b + t) for b, t in zip(badges[:2], titles[:2])), f"prefix rows report 0 s core timings: {list(zip(badges[:2], titles[:2]))}")
        self.shot(page, "chain-1-chain-suffix-rerun")
        # history popover
        h = page.locator('[data-testid="history-button"]')
        if h.count():
            h.first.click(); page.wait_for_timeout(700)
            self.check(page.locator('[data-testid="history-popover"]').count() == 1, "history popover opens")
            self.shot(page, "chain-1b-run-history")
            page.keyboard.press("Escape"); page.wait_for_timeout(300)
        # invalid junction: delete step 2 (matrix profile)
        d = page.locator('[data-testid="delete-step-2"]')
        if d.count():
            d.first.click(); page.wait_for_timeout(900)
            self.check(page.locator('[data-testid="junction-error"]').count() >= 1, "deleting the Scores producer shows the red junction")
            self.shot(page, "chain-1e-invalid-junction")
            undo = page.get_by_role("button", name=re.compile("undo", re.I))
            if undo.count():
                undo.first.click(); page.wait_for_timeout(700)
        # failed block: window_min too long, via the block page param
        self.goto(page, "analyse/block/1", 900)
        p = page.locator('input[data-testid="param-window_min"], [data-testid="param-window_min"] input[type=number]')
        if p.count():
            p.first.fill("500"); p.first.press("Enter"); page.wait_for_timeout(500)
            self.goto(page, "analyse/chain", 800)
            page.locator('[data-testid="run-button"]').first.click()
            for _ in range(80):
                page.wait_for_timeout(250)
                if page.locator('[data-testid="error-card"]').count():
                    break
            page.wait_for_timeout(300)
            self.check(page.locator('[data-testid="error-card"]').count() >= 1, "failed block shows an error card in place of the plot")
            self.shot(page, "chain-1f-failed-block")
            # restore
            self.goto(page, "analyse/block/1", 900)
            p = page.locator('input[data-testid="param-window_min"], [data-testid="param-window_min"] input[type=number]')
            p.first.fill("1"); p.first.press("Enter"); page.wait_for_timeout(400)
        # running state: seed a 20 h source span (72,000 samples, under MP's 80,527 ceiling; MP takes ~3 s)
        page.evaluate("""() => sessionStorage.setItem('ub-proto-a:source', JSON.stringify({recording_id: 4, channel_name: 'CH4_A2', source_file: 'M2_aug_concat_fs1.mat', fs: 1, start_idx: 995040, end_idx: 1067040, label: 'smoke 20 h span'}))""")
        page.reload(wait_until="networkidle"); page.wait_for_timeout(1200)
        run = page.locator('[data-testid="run-button"]')
        if run.count() and run.first.is_enabled():
            run.first.click(); page.wait_for_timeout(700)
            self.shot(page, "chain-1d-running")
            c = page.locator('[data-testid="cancel-button"]')
            if c.count():
                c.first.click(); page.wait_for_timeout(1500)
                self.shot(page, "chain-cancelled")
            for _ in range(120):
                page.wait_for_timeout(250)
                if not page.locator('[data-testid="cancel-button"]').count():
                    break
        # restore the example span for anyone using the page after the smoke test
        page.evaluate("""() => sessionStorage.setItem('ub-proto-a:source', JSON.stringify({recording_id: 4, channel_name: 'CH4_A2', source_file: 'M2_aug_concat_fs1.mat', fs: 1, start_idx: 995040, end_idx: 1002240, label: 'example span'}))""")

    def loud_failure(self, page):
        print("[loud failure]")
        self.goto(page, "analyse/chain?throw=1", 1200)
        self.check(page.locator('[data-testid="render-error"]').count() >= 1, "a thrown render error is shown as a red card (not a blank pane)")
        self.check(any("deliberate render failure" in e for e in self.errors), "the thrown render error reached the browser console")
        self.shot(page, "loud-failure-render-error")
        self.errors = [e for e in self.errors if "deliberate render failure" not in e]

    def discovery(self, page):
        """Discovery (stage-3 prompt 04, spec §7).

        The page states that follow walk live content, so this first puts two
        real runs in the sandbox through the bridge's own routes — a template
        applied across two channels of a four-hour section, and the same
        section's seeded search. Driving it through the API rather than the UI
        is deliberate: the runs are the *fixture* for the page walk, and a
        flow that clicked its way there would fail for a reason that had
        nothing to do with what the states are checking.
        """
        print("[discovery]")
        scope = self.discovery_scope()
        if scope is None:
            self.check(False, "discovery: could not scope a session on this database")
            return
        self.goto(page, "discovery/runs", 1500)
        page.wait_for_selector('[data-testid="discovery-runs-page"]', timeout=20000)
        page.wait_for_timeout(1200)
        rows = page.locator('[data-testid^="run-row-"]').count()
        self.evidence["discovery_run_rows"] = rows
        self.check(rows >= 2, f"{rows} run rows (the human reference plus the runs just made)")
        strips = page.evaluate("""() => Array.from(document.querySelectorAll('[data-testid="scope-strips"] path[d]'))
                                          .map(p => (p.getAttribute('d') || '').length)""")
        self.evidence["discovery_strip_paths"] = strips
        self.check(len(strips) >= 1 and max(strips or [0]) > 200,
                   f"the scope strips painted real overviews (path lengths {strips})")
        cells = page.locator('[data-testid="fires-cell"]').count()
        self.evidence["discovery_fires_cells"] = cells
        self.check(cells > 0, f"where-each-run-fires painted {cells} bins")
        board = page.locator('[data-testid="scoreboard-table"]').inner_text() if \
            page.locator('[data-testid="scoreboard-table"]').count() else ""
        self.check(bool(board.strip()), "the scoreboard has rows")

        # fixup-a 4: a reload keeps the layout height. The 600 px Loading card
        # was a SIBLING of the content, so the 2 s poll inserted it above a
        # painted page every two seconds for the life of a run.
        self.check(page.locator('[data-testid="discovery-refreshing"]').count() == 1,
                   "the Runs page has the quiet in-place reload indicator")
        self.check(page.locator('[data-testid="discovery-loading"]').count() == 0,
                   "the 600 px first-load card is gone once the page has content")
        h0 = page.evaluate("() => document.querySelector('.k-page-inner')?.getBoundingClientRect().height || 0")
        page.wait_for_timeout(2600)      # one full poll interval
        h1 = page.evaluate("() => document.querySelector('.k-page-inner')?.getBoundingClientRect().height || 0")
        self.evidence["discovery_page_height"] = [h0, h1]
        self.check(abs(h1 - h0) < 1.0, f"the page height is unchanged across a poll ({h0} -> {h1})")
        self.shot(page, "discovery-1-runs-live")

        self.goto(page, "discovery/seed", 2000)
        page.wait_for_timeout(1500)
        hist = page.locator('[data-testid="cut-histogram"]').count()
        self.check(hist >= 1, "the seed page draws its match-distance histogram")
        self.shot(page, "discovery-2-seed-live")

        self.goto(page, f"discovery/compare?a={scope['a']}&b={scope['b']}", 2500)
        page.wait_for_timeout(1500)
        self.check(page.locator('[data-testid="what-differs"]').count() >= 1,
                   "compare opens with what differs")
        self.shot(page, "discovery-3-compare-live")

    def discovery_scope(self):
        """Set the session's scope and make two runs, through the bridge.

        Returns the two run keys, or None if this database cannot supply the
        scope (no M2_aug recording, say) — in which case the caller says so
        rather than the page states failing one by one with a selector miss.
        """
        import urllib.error
        import urllib.request

        def call(path, body=None, method="GET"):
            data = json.dumps(body).encode() if body is not None else None
            req = urllib.request.Request(self.url + path, data=data, method=method,
                                         headers={"content-type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=1800) as r:
                    return json.loads(r.read().decode() or "null")
            except urllib.error.HTTPError as e:
                return {"__error__": e.code, "body": e.read().decode(errors="replace")[:300]}

        recs = call("/api/discovery/session").get("recordings") or []
        rec = next((r for r in recs if r["key"].startswith("M2_aug") and not r["heldOut"]), None) \
            or next((r for r in recs if not r["heldOut"]), None)
        if rec is None or len(rec["channels"]) < 2:
            return None
        channels = rec["channels"][:2]
        t1 = min(SMOKE_SECTION_H[1], rec["hours"])
        t0 = max(0.0, min(SMOKE_SECTION_H[0], t1 - 1.0))
        s = call("/api/discovery/session", {"name": "smoke", "recording": rec["key"],
                                            "channels": channels, "section": [t0, t1],
                                            "null": {"method": "phase randomisation", "n": 3}}, "PUT")
        if s.get("__error__"):
            return None
        applied = call("/api/discovery/templates/apply",
                       {"templates": [SMOKE_TEMPLATE], "channels": channels, "t0": t0, "t1": t1,
                        "run": True}, "POST")
        if not isinstance(applied, list) or not applied:
            return None
        a_key = applied[0]["run_key"]
        self._wait_job(call, applied[0].get("job_id"))

        # one template added and NOT started: §7.5's cluster route is about a run
        # that exists and has not run, and `?modal=slurm` needs one to write a
        # script for. `run: false` is the modal's own *Create SLURM script* path.
        call("/api/discovery/templates/apply",
             {"templates": [SMOKE_PENDING_TEMPLATE], "channels": channels, "t0": t0, "t1": t1,
              "run": False}, "POST")

        b_key = None
        # the seed page opens on the draft's seed, so compute the result for THAT
        # seed with the page's own k — a result under any other key is a cache
        # miss and the histogram has nothing to draw
        setup = call("/api/discovery/seed/setup")
        draft = (setup.get("draft") or {}) if not setup.get("__error__") else {}
        seed_id = draft.get("seedId")
        if seed_id:
            # the seed page finds its finished run by the DRAFT's label, and the
            # page states name the run key, so both are pinned to one name here
            # rather than to a hash that changes with the seed
            call("/api/discovery/seed/draft", {"label": SMOKE_SEED_RUN}, "PUT")
            seed_label = SMOKE_SEED_RUN
            started = call("/api/discovery/seed/results",
                           {"seedId": seed_id, "channels": channels, "t0": t0, "t1": t1,
                            "k": SMOKE_SEED_K, "maxDistance": 0.0}, "POST")
            self._wait_job(call, started.get("job_id"))
            run = call("/api/discovery/seed/run", {"seedId": seed_id, "channels": channels,
                                                   "t0": t0, "t1": t1, "k": SMOKE_SEED_K,
                                                   # the seed page looks its finished run up by the
                                                   # draft's own label, so the run must carry it
                                                   "label": seed_label or "smoke_seed"}, "POST")
            if not run.get("__error__"):
                b_key = run["run_key"]
                self._wait_job(call, run.get("job_id"))
        self.evidence["discovery_scope"] = {"recording": rec["key"], "channels": channels,
                                            "section_h": [t0, t1], "runs": [a_key, b_key]}
        return {"a": a_key, "b": b_key or "human", "channels": channels, "t0": t0, "t1": t1}

    @staticmethod
    def _wait_job(call, job_id, timeout_s=1800):
        if not job_id:
            return None
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            snap = call(f"/api/jobs/{job_id}")
            if snap.get("__error__") or snap.get("status") in ("completed", "failed", "cancelled"):
                return snap
            time.sleep(1.0)
        return None

    # ----------------------------------------------------- every page state --
    def routes(self, page):
        """Every route and state named in webui/smoke_pages/<workspace>.json renders: the page mounts,
        the header is present, the main area is not blank, no render-error card appears (unless the
        state expects one), every `expect` selector is present, and no console/page error fires.
        Manifest entry: {"page": "models.launch", "state": "default", "hash": "models/launch?x=1",
        "actions": [{"click": "[data-testid=add-arm]"}, {"press": "Escape"}, {"fill": ["sel", "text"]},
        {"wait": 300}], "expect": ["[data-testid=launch-sources]"], "expect_absent": [], "allow_error_card": false}"""
        print("[routes]")
        # the live flows ran in this same tab: start the page walk from a hard reload, so a row whose error
        # boundary the loud-failure flow tripped (?throw=1) or an in-memory write (a span sent from Explore)
        # cannot leak into the first states. The states themselves keep sharing the tab, as the builders ran them.
        page.goto(f"{self.url}/#/", wait_until="networkidle")
        # the app keeps the source span and the chain in sessionStorage across a reload (state.tsx), so a
        # reload alone is not a fresh tab: clear both storages first, as a new tab would have them
        page.evaluate("() => { try { sessionStorage.clear(); localStorage.clear() } catch (e) {} }")
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(300)
        mdir = os.path.join(HERE, "smoke_pages")
        entries = []
        for fn in sorted(os.listdir(mdir)) if os.path.isdir(mdir) else []:
            if not fn.endswith(".json") or (self.only and not fn.startswith(self.only)):
                continue
            try:
                with open(os.path.join(mdir, fn), encoding="utf-8") as f:
                    for e in json.load(f):
                        entries.append((fn[:-5], e))
            except Exception as e:
                self.failures.append(f"smoke_pages/{fn} unreadable: {e}")
        self.evidence["route_states"] = len(entries)
        self.check(len(entries) > 0, f"{len(entries)} page states listed in smoke_pages/*.json")
        pdir = os.path.join(SHOTS, "pages")
        for unit, e in entries:
            name = f"{e.get('page', '?')}--{e.get('state', 'default')}"
            before = len(self.errors)
            try:
                page.goto(f"{self.url}/#/{e['hash'].lstrip('#/')}", wait_until="networkidle")
                page.wait_for_timeout(e.get("settle_ms", 500))
                for a in e.get("actions", []):
                    if "click" in a: page.locator(a["click"]).first.click(); page.wait_for_timeout(250)
                    elif "press" in a: page.keyboard.press(a["press"]); page.wait_for_timeout(200)
                    elif "fill" in a: page.locator(a["fill"][0]).first.fill(a["fill"][1]); page.wait_for_timeout(200)
                    elif "hover" in a: page.locator(a["hover"]).first.hover(); page.wait_for_timeout(200)
                    elif "wait" in a: page.wait_for_timeout(int(a["wait"]))
                main_txt = page.locator(".main").inner_text() if page.locator(".main").count() else ""
                ok = page.locator('[data-testid="header"]').count() == 1 and len(main_txt.strip()) > 40
                missing = [s for s in e.get("expect", []) if page.locator(s).count() == 0]
                present = [s for s in e.get("expect_absent", []) if page.locator(s).count() > 0]
                err_card = page.locator('[data-testid="render-error"]').count()
                # A state may declare console errors it provokes on purpose (a read that rejects renders a
                # loud error card — the brief's failure state). Declared ones are dropped from the run's
                # error list so they neither fail this state nor the whole run; anything else still fails.
                allowed = e.get("allow_console_error") or []
                if allowed:
                    kept = [x for x in self.errors[before:] if not any(a in x for a in allowed)]
                    self.errors = self.errors[:before] + kept
                self.check(ok and not missing and not present and (err_card == 0 or e.get("allow_error_card")) and len(self.errors) == before,
                           f"{unit}: {name} renders" + (f" — missing {missing}" if missing else "") + (f" — unexpected {present}" if present else "")
                           + (" — render-error card" if err_card and not e.get("allow_error_card") else "") + ("" if ok else " — blank or no header")
                           + (f" — {len(self.errors) - before} console errors" if len(self.errors) > before else ""))
                os.makedirs(os.path.join(pdir, unit), exist_ok=True)
                path = os.path.join(pdir, unit, f"{name}.png")
                page.screenshot(path=path, full_page=bool(e.get("full_page")))
                self.shots.append(path)
            except Exception as ex:
                self.failures.append(f"{unit}: {name}: {type(ex).__name__}: {ex}")
                print("  EXC:", name, ex)

    # ------------------------------------------------------------ driver --
    def run(self):
        from playwright.sync_api import sync_playwright
        os.makedirs(SHOTS, exist_ok=True)
        for f in (os.listdir(SHOTS) if not self.pages_only else []):   # a page-only walk keeps the flow screenshots
            if re.match(r"^\d\d-.*\.(big\.)?png$", f):
                os.remove(os.path.join(SHOTS, f))
        rt = json.load(__import__("urllib.request").request.urlopen(self.url + "/api/runtime"))
        log_path = rt["log_path"]
        log_start = os.path.getsize(log_path) if os.path.isfile(log_path) else 0
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("console", lambda m: self.errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
            page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
            page.on("requestfailed", lambda r: self.errors.append(f"requestfailed: {r.url}") if "fonts.g" not in r.url else None)
            steps = (self.routes,) if self.pages_only else (self.corpus, self.signal, self.m4, self.analyse, self.discovery, self.loud_failure, self.routes)
            for step in steps:
                try:
                    step(page)
                except Exception as e:  # keep going, report everything
                    self.failures.append(f"{step.__name__}: {type(e).__name__}: {e}")
                    print("  EXC:", step.__name__, e)
                    try: self.shot(page, f"{step.__name__}-exception")
                    except Exception: pass
            browser.close()
        # server log check
        tail = ""
        if os.path.isfile(log_path):
            with open(log_path, encoding="utf-8", errors="replace") as f:
                f.seek(log_start); tail = f.read()
        tb = [l for l in tail.splitlines() if "Traceback" in l or "ERROR" in l]
        allowed = ("/api/boom", "deliberate", "must be shorter than the span", "RecipeExecutionError", "run", "window (m=")
        unexpected = [l for l in tb if not any(a in l for a in allowed)]
        self.evidence["server_log_error_lines"] = tb[:20]
        self.check(not unexpected, f"no unexpected server tracebacks ({len(unexpected)} unexpected of {len(tb)} error lines)")
        self.check(not self.errors, f"no browser console/page errors ({len(self.errors)})")
        for e in self.errors[:20]:
            print("   browser:", e[:300])
        out = {"failures": self.failures, "browser_errors": self.errors, "evidence": self.evidence, "screenshots": self.shots}
        with open(os.path.join(SHOTS, "smoke-result.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"\n{len(self.shots)} screenshots, {len(self.failures)} failures")
        return 0 if not self.failures else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("WEBUI_URL", "http://127.0.0.1:8765"))
    ap.add_argument("--no-run", action="store_true", help="skip the run/cancel/fail flows")
    ap.add_argument("--pages-only", action="store_true", help="only walk the page states in smoke_pages/*.json")
    ap.add_argument("--only", default=None, help="restrict the page walk to smoke_pages/<prefix>*.json")
    a = ap.parse_args()
    sys.exit(Smoke(a.url, not a.no_run, a.pages_only, a.only).run())
