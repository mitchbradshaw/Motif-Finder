"""
walk_c.py — night pass C (2026-10-19): walk every route of the web UI and measure polish and load.

Run against a SANDBOX bridge (never 8765/8766), e.g. the scale fixture:

    python tests/perf_fixture.py webui/runtime/night/fixture/scale.sqlite
    webui/.venv/Scripts/python.exe webui/run_server.py --sandbox --port 8769 \
        --db webui/runtime/night/fixture/scale.sqlite --dist webui/client/dist
    "/c/ProgramData/anaconda3/python.exe" scripts/night/walk_c.py --url http://127.0.0.1:8769 \
        --out webui/runtime/night

Per route and viewport (1440x900, 1024x700) it records: time to the page's main card, time until no skeleton
is left, /api requests in the first 10 s (and in 5-10 s: a page still asking with nothing changing polls),
console errors/warnings, page errors, failed requests and >=400 responses, layout shifts after first paint
(PerformanceObserver), the visible warning triangles, the grey caption nodes (.muted and friends) in `.main`,
enabled buttons that paint grey, text that spills out of its box, horizontal page scroll, tables with no rows
and no empty state; and for each "bad id" route whether a red card / empty state says so or the page is blank.
Writes `<out>/walk_c.json` and screenshots `<out>/shots/<vp>/<slug>.png` (+ `_t1.png` 1 s later).

Only reads: it never clicks a write action. Use `--only <substr>` to walk a subset, `--quick` to cut the request
window to 4 s.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request

INIT_JS = r"""
(() => {
  window.__ls = [];
  try {
    new PerformanceObserver(list => {
      for (const e of list.getEntries()) {
        if (e.hadRecentInput) continue;
        const srcs = (e.sources || []).map(s => {
          const n = s.node; if (!n || !n.nodeType) return '?';
          const el = n.nodeType === 1 ? n : n.parentElement; if (!el) return '?';
          const tid = el.closest('[data-testid]');
          return (el.tagName || '').toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '')
            + (tid ? ` in [${tid.getAttribute('data-testid')}]` : '') + ` dy=${Math.round(s.currentRect.y - s.previousRect.y)} dh=${Math.round(s.currentRect.height - s.previousRect.height)}`;
        });
        window.__ls.push({ t: Math.round(e.startTime), v: +e.value.toFixed(4), srcs });
      }
    }).observe({ type: 'layout-shift', buffered: true });
  } catch (e) {}
})();
"""

PROBE_JS = r"""
() => {
  const main = document.querySelector('.main') || document.body;
  const vis = el => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity !== 0; };
  const label = el => { const t = el.closest('[data-testid]'); return ((el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 70)) + (t ? `  [${t.getAttribute('data-testid')}]` : ''); };
  const grey = [...main.querySelectorAll('.muted, .lib-cap, .lib-muted-label, .hint, .caption, .s-row-caption, .k-caption, .sub')]
    .filter(el => vis(el) && (el.innerText || '').trim().length > 0);
  const warnIcons = [...main.querySelectorAll('[data-icon="alert-triangle"]')].filter(vis);
  const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);
  let warnText = 0; const warnTextSamples = [];
  while (walker.nextNode()) { const n = walker.currentNode; if (n.nodeValue && n.nodeValue.includes('⚠') && n.parentElement && vis(n.parentElement)) { warnText++; if (warnTextSamples.length < 6) warnTextSamples.push(label(n.parentElement)); } }
  const rgb = s => (s.match(/[\d.]+/g) || []).map(Number);
  const greyBtns = [...main.querySelectorAll('button:not(:disabled), a.k-btn, a.btn')].filter(vis).filter(b => {
    const cs = getComputedStyle(b); const [r, g, bl, a] = rgb(cs.backgroundColor);
    if (a === 0 || cs.backgroundColor === 'transparent') return false;
    const mx = Math.max(r, g, bl), mn = Math.min(r, g, bl);
    if (mx - mn > 12) return false;                      // coloured
    const avg = (r + g + bl) / 3;
    if (avg > 247) return false;                         // white
    if (b.getAttribute('aria-pressed') === 'true' || b.getAttribute('aria-selected') === 'true' || b.closest('.k-seg, .seg, [role=tablist]')) return false; // toggles
    return avg >= 150 && b.innerText.trim().length > 1;  // a light-grey filled button with words
  });
  const spill = [];
  for (const el of main.querySelectorAll('*')) {
    if (spill.length >= 12) break;
    if (!vis(el) || el.closest('svg') || el.tagName === 'svg') continue;
    const cs = getComputedStyle(el);
    if (cs.overflowX !== 'visible') continue;
    if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 && [...el.childNodes].some(n => n.nodeType === 3 && n.nodeValue.trim())) {
      spill.push(`${el.tagName.toLowerCase()} ${el.scrollWidth}>${el.clientWidth}: ${label(el)}`);
    }
  }
  const tables = [...main.querySelectorAll('table')].filter(vis);
  const emptyTables = tables.filter(t => t.tBodies.length && [...t.tBodies].every(b => b.rows.length === 0)).map(label);
  const errCards = [...main.querySelectorAll('.error-card, .k-empty, [data-testid$="-error"], [data-testid*="unknown"], [data-testid*="not-found"], .k-callout.red, .tone-red')].filter(vis).map(label);
  const smallFonts = [...main.querySelectorAll('*')].filter(el => el.childNodes.length && [...el.childNodes].some(n => n.nodeType === 3 && n.nodeValue.trim()) && vis(el) && !el.closest('svg') && parseFloat(getComputedStyle(el).fontSize) < 10.5).slice(0, 400);
  return {
    text_len: (main.innerText || '').trim().length,
    grey: grey.length, grey_samples: grey.slice(0, 40).map(label),
    warn_icons: warnIcons.length, warn_icon_samples: warnIcons.slice(0, 8).map(el => label(el.parentElement || el)),
    warn_text: warnText, warn_text_samples: warnTextSamples,
    grey_buttons: greyBtns.map(b => `${b.className} :: ${label(b)}`).slice(0, 15), grey_button_count: greyBtns.length,
    spill, page_hscroll: document.documentElement.scrollWidth > window.innerWidth + 1 ? `${document.documentElement.scrollWidth}>${window.innerWidth}` : null,
    main_hscroll: main.scrollWidth > main.clientWidth + 1 ? `${main.scrollWidth}>${main.clientWidth}` : null,
    tables: tables.length, empty_tables: emptyTables,
    err_cards: errCards.slice(0, 6), skeletons: [...main.querySelectorAll('.skeleton')].filter(vis).length,
    small_font_nodes: smallFonts.length, small_font_samples: smallFonts.slice(0, 5).map(el => getComputedStyle(el).fontSize + ' ' + label(el)),
    title: (document.querySelector('.main h1, .main .hdr-page, .main header')?.innerText || '').trim().slice(0, 80),
  };
}
"""

PAINTED_JS = r"""
(sel) => {
  const main = document.querySelector('.main'); if (!main) return false;
  if (sel) { const el = document.querySelector(sel); if (!el) return false; const r = el.getBoundingClientRect(); return r.height > 8; }
  if (main.querySelector('[data-testid="workspace-loading"]')) return false;
  const cands = main.querySelectorAll('.k-card, .card, .error-card, .k-empty, table, .k-section, [data-testid]');
  for (const el of cands) {
    if (el.classList.contains('skeleton') || el.querySelector('.skeleton') || (el.getAttribute('data-testid') || '').startsWith('skeleton')) continue;
    const r = el.getBoundingClientRect(); if (r.height > 60 && r.width > 120 && (el.innerText || '').trim().length > 8) return true;
  }
  return false;
}
"""


def api(base, path):
    with urllib.request.urlopen(base + path, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def routes(base):
    """(slug, hash, main-card selector or None, kind) — kind 'page' or 'bad'."""
    recs = api(base, "/api/recordings")
    recs = recs.get("recordings", recs) if isinstance(recs, dict) else recs
    chans = (recs[0].get("channels") or []) if recs else []
    rec = chans[min(3, len(chans) - 1)]["id"] if chans else (recs[0].get("id", 1) if recs else 1)
    try:
        qs = api(base, "/api/review/queues")
        qs = qs.get("queues", qs) if isinstance(qs, dict) else qs
        qid = qs[0]["id"] if qs else "1"
    except Exception:
        qid = "1"
    T = lambda t: f'[data-testid="{t}"]'
    R = [
        ("review-landing", "review", T("inspector")),
        ("review-queue", f"review/queue/{qid}", T("inspector")),
        ("discovery-runs", "discovery/runs", T("runs-card")),
        ("analyse-chain", "analyse/chain", None),
        ("analyse-chain-insert", "analyse/chain?insert=1", '[data-testid="insert-modal"] [data-testid="modal-detail"] h3'),
        ("analyse-block-0", "analyse/block/0", None),
        ("analyse-block-1", "analyse/block/1", T("params-panel")),
        ("analyse-block-2", "analyse/block/2", None),
        ("discovery-seed", "discovery/seed", None),
        ("discovery-compare", "discovery/compare", None),
        ("discovery-stages", "discovery/compare/stages", None),
        ("discovery-map", "discovery/map", None),
        ("explore-corpus", "explore/corpus", None),
        ("library-recurrence", "library/recurrence", None),
        ("library-atlas", "library/atlas", None),
        ("library-family", "library/family/F-03", None),
        ("library-grouping", "library/grouping", None),
        ("library-import", "library/import", None),
        ("library-window-sets", "library/window-sets", None),
        ("library-templates", "library/templates", None),
        ("analyse-interrogation", "analyse/interrogation", None),
        ("analyse-interrogation-1", "analyse/interrogation/block/1", None),
        ("analyse-interrogation-2", "analyse/interrogation/block/2", None),
        ("analyse-training", "analyse/training", None),
        *[(f"analyse-training-{i}", f"analyse/training/block/{i}", None) for i in range(1, 6)],
        ("analyse-glyphs", "analyse/glyphs", None),
        ("jobs", "jobs", None),
        ("reports", "reports", None),
        ("models-launch", "models/launch", None),
        ("models-results", "models/results", None),
        ("models-compare", "models/compare", None),
        ("models-registry", "models/registry", None),
        *[(f"settings-{s}", f"settings/{s}", None) for s in (
            "datasets", "channels-events", "vocabulary", "nulls", "analysis-defaults", "compute-hpc", "blocks",
            "review-queues", "models-registration", "library-groupings", "storage-backups", "export", "audit-log",
            "about", "display", "keyboard")],
        ("kit", "kit", None),
        # last: at scale both read the WHOLE channel's spans (minutes), and the bridge keeps computing an abandoned read,
        # so anything walked after them is timed behind it
        ("explore-signal", f"explore/signal/{rec}", None),
        ("explore-cross", f"explore/cross-channel/{rec}", T("channel-stack")),
    ]
    BAD = [
        ("bad-review-queue", "review/queue/no-such-queue"),
        ("bad-review-item", f"review/queue/{qid}/99999999"),
        ("bad-review-cluster", "review/cluster/99999"),
        ("bad-signal", "explore/signal/999999"),
        ("bad-signal-nan", "explore/signal/abc"),
        ("bad-cross", "explore/cross-channel/999999"),
        ("bad-span-edit", "explore/span-edit/zzz"),
        ("bad-block", "analyse/block/99"),
        ("bad-chain-template", "analyse/chain?template=no_such_template"),
        ("bad-discovery-run", "discovery/runs?run=no-such-run"),
        ("bad-compare", "discovery/compare?a=nope&b=nope"),
        ("bad-map", "discovery/map?dataset=nope&channel=nope"),
        ("bad-seed", "discovery/seed?entry=99999999"),
        ("bad-family", "library/family/NOPE"),
        ("bad-library-page", "library/nope"),
        ("bad-grouping", "library/atlas?grouping=nope"),
        ("bad-interrogation", "analyse/interrogation?family=nope"),
        ("bad-training-block", "analyse/training/block/99"),
        ("bad-models-results", "models/results?run=nope"),
        ("bad-models-page", "models/nope"),
        ("bad-settings", "settings/nope"),
        ("bad-discovery-page", "discovery/nope"),
        ("bad-workspace", "nope"),
    ]
    heavy = {"explore-signal", "explore-cross"}
    return ([(s, h, sel, "page") for s, h, sel in R if s not in heavy] + [(s, h, None, "bad") for s, h in BAD]
            + [(s, h, sel, "page") for s, h, sel in R if s in heavy])


def walk_one(ctx, base, slug, hsh, sel, kind, vp, outdir, window_s):
    page = ctx.new_page()
    cons, perrs, rfail, bad_status, reqs = [], [], [], [], []
    t_nav = [0.0]
    page.on("console", lambda m: cons.append((m.type, m.text[:300])) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: perrs.append(str(e)[:300]))
    page.on("requestfailed", lambda r: rfail.append(f"{r.url.replace(base, '')} {r.failure}"[:200]))
    page.on("response", lambda r: bad_status.append(f"{r.status} {r.url.replace(base, '')}"[:200]) if r.status >= 400 else None)
    page.on("request", lambda r: reqs.append((time.perf_counter() - t_nav[0], r.url.replace(base, ''))) if "/api/" in r.url else None)
    rec = {"slug": slug, "hash": hsh, "kind": kind, "vp": vp}
    t_nav[0] = time.perf_counter()
    try:
        page.goto(f"{base}/#/{hsh}", wait_until="domcontentloaded", timeout=30000)
    except Exception as e:  # noqa: BLE001
        rec["goto_error"] = str(e)[:200]
    try:
        page.wait_for_function(PAINTED_JS, arg=sel, timeout=20000, polling=50)
        rec["t_main_ms"] = round((time.perf_counter() - t_nav[0]) * 1000)
    except Exception:
        rec["t_main_ms"] = None
    try:
        page.wait_for_function("() => { const m = document.querySelector('.main'); return m && ![...m.querySelectorAll('.skeleton,[data-testid=workspace-loading]')].some(e => e.getBoundingClientRect().height > 0) }", timeout=20000, polling=100)
        rec["t_settled_ms"] = round((time.perf_counter() - t_nav[0]) * 1000)
    except Exception:
        rec["t_settled_ms"] = None
    t_paint = (rec["t_main_ms"] or 0) / 1000
    shots = os.path.join(outdir, "shots", vp)
    os.makedirs(shots, exist_ok=True)
    page.wait_for_timeout(600)
    try:
        page.screenshot(path=os.path.join(shots, f"{slug}.png"), full_page=False)
        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(shots, f"{slug}_t1.png"), full_page=False)
    except Exception as e:  # noqa: BLE001
        rec["shot_error"] = str(e)[:200]
    try:
        rec.update(page.evaluate(PROBE_JS))
    except Exception as e:  # noqa: BLE001
        rec["probe_error"] = str(e)[:200]
    rest = window_s - (time.perf_counter() - t_nav[0])
    if rest > 0:
        page.wait_for_timeout(rest * 1000)
    try:
        ls = page.evaluate("() => window.__ls || []")
    except Exception:
        ls = []
    late = [x for x in ls if x["t"] / 1000 > t_paint]
    rec["cls_after_paint"] = round(sum(x["v"] for x in late), 4)
    rec["shifts_after_paint"] = late[:8]
    rec["cls_total"] = round(sum(x["v"] for x in ls), 4)
    within = [u for t, u in reqs if t <= window_s]
    rec["api_requests"] = len(within)
    rec["api_requests_late"] = len([u for t, u in reqs if window_s / 2 <= t <= window_s])
    counts = {}
    for u in within:
        k = re.sub(r"\?.*$", "", u)
        counts[k] = counts.get(k, 0) + 1
    rec["api_endpoints"] = dict(sorted(counts.items(), key=lambda kv: -kv[1])[:12])
    rec["console"] = cons[:15]
    rec["page_errors"] = perrs[:5]
    rec["request_failed"] = rfail[:8]
    rec["bad_status"] = bad_status[:8]
    page.close()
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8769")
    ap.add_argument("--out", default=os.path.join("webui", "runtime", "night"))
    ap.add_argument("--only", default=None)
    ap.add_argument("--vp", default="1440x900,1024x700")
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args(argv)
    base = a.url.rstrip("/")
    if base.endswith(":8765") or base.endswith(":8766"):
        raise SystemExit("walk_c refuses the researcher's and the manager's bridges (8765/8766)")
    os.makedirs(a.out, exist_ok=True)
    from playwright.sync_api import sync_playwright
    rs = routes(base)
    if a.only:
        rs = [r for r in rs if any(o in r[0] for o in a.only.split(","))]
    window_s = 4.0 if a.quick else 10.0
    out = []
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        for vp in a.vp.split(","):
            w, h = (int(x) for x in vp.split("x"))
            ctx = br.new_context(viewport={"width": w, "height": h})
            ctx.add_init_script(INIT_JS)
            # warm the bundle and the bridge's first-read caches once, so the first route is not charged for them
            warm = ctx.new_page(); warm.goto(f"{base}/#/explore/corpus"); warm.wait_for_timeout(3000); warm.close()
            for slug, hsh, sel, kind in rs:
                r = walk_one(ctx, base, slug, hsh, sel, kind, vp, a.out, window_s)
                out.append(r)
                print(f"{vp} {slug:28s} main={r.get('t_main_ms')} settled={r.get('t_settled_ms')} api={r['api_requests']}"
                      f"/{r['api_requests_late']} grey={r.get('grey')} warn={r.get('warn_icons')}+{r.get('warn_text')}"
                      f" greybtn={r.get('grey_button_count')} cls={r['cls_after_paint']} err={len(r['page_errors'])}"
                      f"/{len([c for c in r['console'] if c[0] == 'error'])} spill={len(r.get('spill') or [])}", flush=True)
                with open(os.path.join(a.out, "walk_c.json"), "w", encoding="utf-8") as f:
                    json.dump(out, f, indent=1)
            ctx.close()
        br.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
