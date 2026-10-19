"""
night_a.py — night pass A (2026-10-19): drive Review and Discovery like a tired researcher.

Runs against a bridge you started yourself (never 8765/8766):

    "/c/ProgramData/anaconda3/python.exe" scripts/night/night_a.py --url http://127.0.0.1:8767 \
        --out webui/runtime/night [--only load,keys,overlap,edges,discovery]

Each part prints a JSON line per finding/timing and writes screenshots under --out. Nothing here writes to the
database except through the bridge's own routes (verdicts, undo) — so run it on a sandbox bridge only; against the
real database it would leave verdicts. The `load` part is read-only and is the one to re-run on the real DB.

Parts:
  load       time to each page's main card and the API requests in the first 10 s (Runs, Seed, Compare, Map,
             Review inspector, Review queue open).
  keys       a 10 k queue stepped fast with the arrow keys; verdicts mixed in; checks the card shown is the hash's item
             and every written verdict is on the item it was pressed on.
  overlap    a verdict on an overlap set via the API: every member written, undo removes exactly them.
  edges      an empty queue, a queue with one item, a queue whose run was discarded, a bad queue id, a bad item id.
  discovery  first paint (layout jump), runs hidden by default then shown, the map's poll, the template picker.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

OUT = None
FINDINGS = []


def log(kind, **kw):
    row = {"kind": kind, **kw}
    FINDINGS.append(row)
    print(json.dumps(row), flush=True)


def api(base, path, payload=None, method=None, timeout=120):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=data, method=method or ("POST" if data else "GET"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, body


class Watch:
    """Console errors, page errors, failed requests and API request counts for one page."""

    def __init__(self, page):
        self.page, self.errors, self.failed, self.api = page, [], [], []
        self.t0 = time.perf_counter()
        page.on("console", lambda m: m.type in ("error", "warning") and self.errors.append(f"{m.type}: {m.text[:300]}"))
        page.on("pageerror", lambda e: self.errors.append(f"pageerror: {str(e)[:300]}"))
        page.on("requestfailed", lambda r: self.failed.append(f"{r.url} {r.failure}"))
        page.on("request", lambda r: "/api/" in r.url and self.api.append((time.perf_counter() - self.t0, r.url)))

    def reset(self):
        self.t0 = time.perf_counter()
        self.api.clear(); self.errors.clear(); self.failed.clear()

    def api_in(self, s):
        return [u for t, u in self.api if t <= s]


def shot(page, name):
    path = os.path.join(OUT, f"{name}.png")
    try:
        page.screenshot(path=path, full_page=False)
    except Exception as e:  # noqa: BLE001 — a screenshot is evidence, not the test
        log("shot-failed", name=name, error=str(e)[:200])
    return path


def time_to(page, w, url, testid, timeout=60_000):
    w.reset()
    t0 = time.perf_counter()
    page.goto(url)
    try:
        page.wait_for_selector(f'[data-testid="{testid}"]', state="visible", timeout=timeout)
        ms = (time.perf_counter() - t0) * 1000
    except Exception:  # noqa: BLE001
        ms = None
    return ms


def part_load(base, browser, queue_id, first_item):
    rows = [
        ("Discovery runs", f"{base}/#/discovery/runs", "runs-list"),
        ("Discovery seed", f"{base}/#/discovery/seed", "discovery-seed-page"),
        ("Discovery compare", f"{base}/#/discovery/compare", "discovery-compare-page"),
        ("Discovery map", f"{base}/#/discovery/map", "discovery-map-page"),
        ("Review queue open", f"{base}/#/review", "inspector"),
        ("Review inspector", f"{base}/#/review/queue/{queue_id}/{first_item}", "inspector"),
    ]
    for cold in (True, False):
        for label, url, testid in rows:
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()
            w = Watch(page)
            ms = time_to(page, w, url, testid)
            # also the time to the first non-loading content: the card's own data-testid is on the outer page for
            # Discovery, so wait for its loading card to go
            settle = None
            if "/discovery/" in url:
                t0 = time.perf_counter()
                try:
                    page.wait_for_function("() => !document.querySelector('[data-testid=\"discovery-loading\"]')",
                                           timeout=60_000)
                    settle = (time.perf_counter() - t0) * 1000 + (ms or 0)
                except Exception:  # noqa: BLE001
                    settle = None
            page.wait_for_timeout(max(0, 10_000 - (time.perf_counter() - w.t0) * 1000))
            reqs = w.api_in(10)
            from collections import Counter
            top = Counter(u.split("?")[0].replace(base, "") for u in reqs).most_common(4)
            shot(page, f"load-{'cold' if cold else 'warm'}-{label.replace(' ', '-').lower()}")
            log("load", page=label, cold=cold, paint_ms=None if ms is None else round(ms),
                settled_ms=None if settle is None else round(settle), api_10s=len(reqs), top=top,
                errors=w.errors[:5], failed=w.failed[:3])
            ctx.close()


def db_path(base):
    st, rt = api(base, "/api/runtime")
    return rt.get("db_path") or rt.get("db_copy")


def ro(base):
    import sqlite3
    return sqlite3.connect(f"file:{db_path(base)}?mode=ro", uri=True)


def adjudicated(base, det_ids):
    """{detection id: verdict} for these detections, read straight off the sandbox copy (read-only)."""
    c = ro(base)
    try:
        marks = ",".join(str(int(d)) for d in det_ids) or "NULL"
        return {r[0]: r[1] for r in c.execute(
            f"SELECT detection_id, verdict FROM adjudications WHERE detection_id IN ({marks})")}
    finally:
        c.close()


def item_state(page):
    return page.evaluate("""() => {
      const el = document.querySelector('[data-testid="inspector"]');
      return { hash: location.hash, item: el ? el.getAttribute('data-item') : null,
               title: el ? (el.querySelector('h1') || {}).textContent : null,
               stale: el ? el.classList.contains('stale') : null,
               loading: !!document.querySelector('[data-testid="review-loading"]') }
    }""")


def hash_item(h):
    parts = h.split("?")[0].split("/")
    return parts[-1] if len(parts) >= 5 else None


def open_inspector(browser, url):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    w = Watch(page)
    page.goto(url)
    page.wait_for_selector('[data-testid="inspector"]', timeout=180_000)
    page.wait_for_timeout(1500)
    return ctx, page, w


def wait_card_matches_hash(page, timeout=120_000):
    page.wait_for_function("""() => { const el = document.querySelector('[data-testid="inspector"]');
        const id = location.hash.split('?')[0].split('/').pop(); return el && el.getAttribute('data-item') === id }""",
                           timeout=timeout)


def part_keys(base, browser, queue_id, qd):
    rows = qd["rows"]
    ids = [r["id"] for r in rows]
    unjudged = [r for r in rows if not r.get("judged")]
    ctx, page, w = open_inspector(browser, f"{base}/#/review/queue/{queue_id}/{unjudged[0]['id']}")
    # 1. fast arrow stepping: sample the card against the hash after every press
    mismatches, samples = [], 0
    for i in range(40):
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(40)
        s = item_state(page)
        samples += 1
        if s["item"] and s["item"] != hash_item(s["hash"]):
            mismatches.append(s)
        if s["item"] and s["title"] and s["title"] != s["item"]:
            mismatches.append({"title-vs-item": s})
    t0 = time.perf_counter()
    wait_card_matches_hash(page)
    log("keys-fast-step", presses=40, samples=samples, mismatches=len(mismatches), first=mismatches[:3],
        settle_after_last_ms=round((time.perf_counter() - t0) * 1000), errors=w.errors[:5])
    shot(page, "keys-after-40-steps")
    # 2. a verdict then two quick arrows: does the auto-advance timer yank the page somewhere else?
    at = item_state(page)["item"]
    i0 = ids.index(at)
    page.keyboard.press("i")
    page.wait_for_timeout(60)
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(60)
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(4000)
    landed = hash_item(item_state(page)["hash"])
    log("keys-verdict-then-arrows", verdict_on=at, expected_after_two_arrows=ids[i0 + 2], landed=landed,
        yanked=landed != ids[i0 + 2], errors=w.errors[:5])
    shot(page, "keys-verdict-then-arrows")
    # 3. the verdict landed on the item it was pressed on, and nowhere else
    members = [int(m) for m in (rows[i0].get("members") or [at])]
    got = adjudicated(base, members + [int(ids[i0 + 1]), int(ids[i0 + 2])])
    log("keys-verdict-target", pressed_on=at, members=members, adjudications=got,
        wrong=[d for d in got if d not in members])
    # 4. rapid verdicts with auto-advance: each on a different item?
    wait_card_matches_hash(page)
    seq = []
    for k in range(5):
        wait_card_matches_hash(page)
        seq.append(item_state(page)["item"])
        page.keyboard.press("n")
        page.wait_for_timeout(1200)
    page.wait_for_timeout(2500)
    log("keys-rapid-verdicts", pressed_on=seq, distinct=len(set(seq)), written=adjudicated(base, [int(x) for x in seq]),
        errors=w.errors[:5])
    # 5. undo x5 removes exactly those (and the one from step 2 stays)
    for k in range(5):
        page.keyboard.press("Control+z")
        page.wait_for_timeout(900)
    page.wait_for_timeout(2000)
    log("keys-undo-five", remaining=adjudicated(base, [int(x) for x in seq]),
        step2_kept=adjudicated(base, members), errors=w.errors[:5])
    page.keyboard.press("Control+z")
    page.wait_for_timeout(2000)
    log("keys-undo-sixth", step2_after=adjudicated(base, members))
    ctx.close()


def part_overlap(base, browser, queue_id, qd):
    rows = qd["rows"]
    multi = [r for r in rows if len(r.get("members") or []) > 1 and not r.get("judged")]
    if not multi:
        log("overlap", skipped="no unjudged overlap item in the queue")
        return
    r = multi[0]
    members = [int(m) for m in r["members"]]
    # a link by a non-first member opens the item
    ctx, page, w = open_inspector(browser, f"{base}/#/review/queue/{queue_id}/{members[-1]}")
    s = item_state(page)
    covers = page.locator('[data-testid="covers-line"]').all_inner_texts()
    shot(page, "overlap-item")
    page.keyboard.press("i")
    page.wait_for_timeout(3000)
    got = adjudicated(base, members)
    page.goto(f"{base}/#/review/queue/{queue_id}/{r['id']}")
    wait_card_matches_hash(page)
    page.wait_for_timeout(800)
    page.keyboard.press("Control+z")
    page.wait_for_timeout(3000)
    after = adjudicated(base, members)
    page.keyboard.press("2")          # the class key: burst, implies interesting
    page.wait_for_timeout(3000)
    c = ro(base)
    cls = c.execute(f"SELECT detection_id, verdict, class_label FROM adjudications WHERE detection_id IN "
                    f"({','.join(map(str, members))})").fetchall()
    c.close()
    page.keyboard.press("Control+z")
    page.wait_for_timeout(2500)
    log("overlap", item=r["id"], opened_by=members[-1], shown=s["item"], covers=covers, members=members,
        written=got, all_written=len(got) == len(members), after_undo=after, class_rows=cls,
        after_class_undo=adjudicated(base, members), errors=w.errors[:5])
    ctx.close()


END_SEL = ('[data-testid="inspector"], [data-testid="queue-exhausted"], [data-testid="queue-empty"], '
           '[data-testid="item-not-found"], .error-card, [data-testid="review-unknown"]')


def part_edges(base, browser, queue_id, qd):
    rows = qd["rows"]
    unj = [r for r in rows if not r.get("judged")]
    jd = [r for r in rows if r.get("judged")]
    made = {}
    for name, filt in (("night one item", {"detection_ids": [int(unj[-1]["id"])]}),
                       ("night all judged", {"detection_ids": [int(jd[0]["id"])]}),
                       ("night zero ids", {"detection_ids": []})):
        st, body = api(base, "/api/review/queues", {"name": name, "source_kind": "discovery-run", "filters": filt})
        made[name] = (st, body["queue"]["id"] if st == 200 else body)
        log("edge-create", name=name, status=st, body=made[name][1] if st == 200 else str(body)[:300])
    for name, (st, qid) in made.items():
        if st != 200:
            continue
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        w = Watch(page)
        t0 = time.perf_counter()
        page.goto(f"{base}/#/review/queue/{qid}")
        page.wait_for_timeout(500)
        try:
            page.wait_for_function("() => document.querySelector('" + END_SEL + "')", timeout=180_000)
        except Exception:  # noqa: BLE001
            pass
        ms = (time.perf_counter() - t0) * 1000
        page.wait_for_timeout(1500)
        text = page.locator("main, .rv-root").first.inner_text()[:500] if page.locator(".rv-root").count() else ""
        shot(page, f"edge-{name.replace(' ', '-')}")
        log("edge-open", name=name, queue=qid, ms=round(ms), hash=page.evaluate("location.hash"),
            text=text.replace("\n", " | "), errors=w.errors[:5])
        if name == "night one item":
            page.keyboard.press("ArrowRight"); page.wait_for_timeout(600)
            t1 = page.locator("body").inner_text()
            page.keyboard.press("ArrowLeft"); page.wait_for_timeout(600)
            t2 = page.locator("body").inner_text()
            log("edge-one-item-ends", right_says=[l for l in t1.split("\n") if "item" in l and "last" in l][:2],
                left_says=[l for l in t2.split("\n") if "first" in l][:2])
            page.keyboard.press("n"); page.wait_for_timeout(3500)
            text = page.locator(".rv-root").first.inner_text()[:600]
            shot(page, "edge-one-item-after-verdict")
            log("edge-one-item-after-verdict", hash=page.evaluate("location.hash"), text=text.replace("\n", " | "))
            if page.locator('[data-testid="pick-another-queue"]').count():
                page.locator('[data-testid="pick-another-queue"]').click(); page.wait_for_timeout(3000)
                log("edge-pick-another", hash=page.evaluate("location.hash"),
                    text=page.locator("body").inner_text()[:300].replace("\n", " | "))
            page.goto(f"{base}/#/review/queue/{qid}/{unj[-1]['id']}"); page.wait_for_timeout(3000)
            page.keyboard.press("Control+z"); page.wait_for_timeout(2000)
        ctx.close()
    for label, url in (("bad queue", f"{base}/#/review/queue/999999"),
                       ("bad item", f"{base}/#/review/queue/{queue_id}/nope"),
                       ("bad cluster", f"{base}/#/review/queue/{queue_id}/cluster/77"),
                       ("cluster alias", f"{base}/#/review/cluster/5")):
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        w = Watch(page)
        page.goto(url)
        page.wait_for_timeout(1000)
        try:
            page.wait_for_function("() => !document.querySelector('[data-testid=\"review-loading\"]')", timeout=180_000)
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(1000)
        shot(page, f"edge-{label.replace(' ', '-')}")
        log("edge-bad-id", label=label, hash=page.evaluate("location.hash"),
            text=page.locator("body").inner_text()[:400].replace("\n", " | "), errors=w.errors[:5])
        ctx.close()


def tops(page, testids):
    return page.evaluate("""(ids) => Object.fromEntries(ids.map(id => {
        const el = document.querySelector(`[data-testid="${id}"]`);
        if (!el) return [id, null];
        const r = el.getBoundingClientRect(); return [id, [Math.round(r.top), Math.round(r.height)]] }))""", testids)


def part_discovery(base, browser, queue_id, qd):
    cards = ["discovery-toolbar", "scope-card", "runs-card", "where-fires", "scoreboard", "browser"]
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    w = Watch(page)
    t0 = time.perf_counter()
    page.goto(f"{base}/#/discovery/runs")
    page.wait_for_selector('[data-testid="discovery-runs-page"]', timeout=120_000)
    snaps = []
    for at in (0, 1, 3, 8, 20):
        while (time.perf_counter() - t0) < at:
            page.wait_for_timeout(100)
        snaps.append((at, tops(page, cards)))
        shot(page, f"disc-runs-t{at:02d}")
    moved = {}
    for cid in cards:
        seen = [s[1][cid] for s in snaps if s[1][cid]]
        if len({tuple(x) for x in seen}) > 1:
            moved[cid] = [(s[0], s[1][cid]) for s in snaps]
    try:
        page.wait_for_selector('[data-testid="runs-list"]', timeout=120_000)
        runs_ms = round((time.perf_counter() - t0) * 1000)
    except Exception:  # noqa: BLE001
        runs_ms = None
    log("disc-runs-first-paint", runs_list_ms=runs_ms, moved=moved,
        shown=page.locator('[data-testid="fires-shown-count"]').all_inner_texts(), errors=w.errors[:5])
    # runs hidden by default, then shown
    if page.locator('[data-testid="fires-show-all"]').count():
        t1 = time.perf_counter()
        page.locator('[data-testid="fires-show-all"]').click()
        page.wait_for_timeout(300)
        try:
            page.wait_for_function("() => { const r = document.querySelector('[data-testid=\"fires-refreshing\"]');"
                                   " return r && r.getAttribute('data-on') === '0' }", timeout=300_000)
            ms = round((time.perf_counter() - t1) * 1000)
        except Exception:  # noqa: BLE001
            ms = None
        shot(page, "disc-runs-show-all")
        log("disc-runs-show-all", ms=ms, shown=page.locator('[data-testid="fires-shown-count"]').all_inner_texts(),
            rows=page.locator(".dsc-fires-row").count(), errors=w.errors[:5])
        page.locator('[data-testid="fires-hide-all"]').click()
        page.wait_for_timeout(500)
    # the scoreboard: when do the scores arrive?
    t2 = time.perf_counter()
    try:
        page.wait_for_selector('[data-testid="scoreboard-table"]', timeout=600_000)
        sb_ms = round((time.perf_counter() - t2) * 1000)
    except Exception:  # noqa: BLE001
        sb_ms = None
    log("disc-scoreboard", waited_ms=sb_ms, total_ms=round((time.perf_counter() - t0) * 1000))
    # the template picker while the background scorer works
    page.locator('[data-testid="apply-template"]').click()
    t3 = time.perf_counter()
    w.reset()
    try:
        page.wait_for_selector('[data-testid="template-list"]', timeout=180_000)
        pick_ms = round((time.perf_counter() - t3) * 1000)
    except Exception:  # noqa: BLE001
        pick_ms = None
    scoring0 = page.locator('[data-scoring="1"]').count()
    page.wait_for_timeout(30_000)
    scoring1 = page.locator('[data-scoring="1"]').count()
    reads = [u for u in w.api_in(60) if "/discovery/templates" in u]
    shot(page, "disc-template-picker")
    log("disc-template-picker", paint_ms=pick_ms, scoring_at_open=scoring0, scoring_after_30s=scoring1,
        template_reads_30s=len(reads), errors=w.errors[:5])
    page.keyboard.press("Escape")
    ctx.close()
    # the map: does it keep polling with nothing running?
    for label, url, tid in (("map", f"{base}/#/discovery/map", "discovery-map-page"),
                            ("seed", f"{base}/#/discovery/seed", "discovery-seed-page"),
                            ("compare", f"{base}/#/discovery/compare", "discovery-compare-page")):
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        w = Watch(page)
        page.goto(url)
        page.wait_for_selector(f'[data-testid="{tid}"]', timeout=120_000)
        page.wait_for_timeout(20_000)
        from collections import Counter
        reqs = Counter(u.split("?")[0].split("/api/")[1] for u in w.api_in(25))
        shot(page, f"disc-{label}")
        body = page.locator(f'[data-testid="{tid}"]').inner_text()
        log(f"disc-{label}", requests_20s=dict(reqs), loading_left=page.locator('[data-testid="discovery-loading"]').count(),
            text=body[:600].replace("\n", " | "), errors=w.errors[:5])
        ctx.close()


def part_visual(base, browser, queue_id, qd):
    """C's findings re-checked: run row heights in a long list, the Review toolbar at 1024 px, a bad queue id."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(f"{base}/#/discovery/runs")
    page.wait_for_selector('[data-testid="runs-list"]', timeout=180_000)
    page.wait_for_timeout(1500)
    hs = page.evaluate("() => [...document.querySelectorAll('.dsc-run')].slice(0, 6).map(e => Math.round(e.getBoundingClientRect().height))")
    shot(page, "visual-runs-list")
    log("visual-run-rows", heights=hs)
    ctx.close()
    ctx = browser.new_context(viewport={"width": 1024, "height": 700})
    page = ctx.new_page()
    page.goto(f"{base}/#/review/queue/{queue_id}/{qd['rows'][-1]['id']}")
    page.wait_for_selector('[data-testid="inspector"]', timeout=180_000)
    page.wait_for_timeout(1000)
    tb = page.evaluate("""() => { const t = document.querySelector('.rv-toolbar'); if (!t) return null;
        const r = t.getBoundingClientRect(); const kids = [...t.children].map(c => { const b = c.getBoundingClientRect();
        return [Math.round(b.left), Math.round(b.right), Math.round(b.width)] });
        return { h: Math.round(r.height), w: Math.round(r.width), scrollW: t.scrollWidth, kids } }""")
    shot(page, "visual-review-1024")
    log("visual-review-toolbar-1024", toolbar=tb)
    t0 = time.perf_counter()
    page.goto(f"{base}/#/review/queue/999999")
    page.wait_for_selector('[data-testid="review-unknown"], [data-testid="queue-error"]', timeout=120_000)
    ms = round((time.perf_counter() - t0) * 1000)
    shot(page, "visual-bad-queue")
    log("visual-bad-queue", ms=ms, unknown=page.locator('[data-testid="review-unknown"]').count())
    ctx.close()


def main(argv=None):
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8767")
    ap.add_argument("--out", default=os.path.join("webui", "runtime", "night"))
    ap.add_argument("--only", default="load,keys,overlap,edges,discovery")
    a = ap.parse_args(argv)
    if ":8765" in a.url or ":8766" in a.url:
        sys.exit("refusing 8765/8766: those are the researcher's and the manager's bridges")
    OUT = a.out
    os.makedirs(OUT, exist_ok=True)
    parts = set(a.only.split(","))
    st, queues = api(a.url, "/api/review/queues")
    q = queues[0]
    st, qd = api(a.url, f"/api/review/queues/{q['id']}?thumbs=0")
    first_item = qd["rows"][0]["id"] if qd.get("rows") else None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        if "load" in parts:
            part_load(a.url, browser, q["id"], first_item)
        for name in ("keys", "overlap", "edges", "discovery", "visual"):
            if name in parts and f"part_{name}" in globals():
                globals()[f"part_{name}"](a.url, browser, q["id"], qd)
        browser.close()
    with open(os.path.join(OUT, "night_a_findings.json"), "w", encoding="utf-8") as f:
        json.dump(FINDINGS, f, indent=1)


if __name__ == "__main__":
    main()
