"""review_burst.py - time Review's verdict steps at the researcher's pace, on a SANDBOX bridge (AS, 2026-11-24).

Dev tooling, not imported by the app. It WRITES verdicts, so it refuses any bridge whose /api/runtime is not a sandbox.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/review_burst.py \
        --url http://127.0.0.1:8830 --queue 57 --n 50 --gap-ms 300 [--rail open] [--scenario burst|undo|refuse|loss]

What it does: opens `#/review/queue/<q>` in headless Chromium, wraps `window.fetch` (a log of every request; hooks to
refuse or hold a write), presses `n` (not interesting) every `gap-ms`, and times each key press to the moment the NEXT
item is painted: the Inspector's `data-item` changed AND its context trace has a drawn path, checked once per frame.
Then it waits until every write is answered (and, on a build that has it, `saves-pending` says "all saved"), waits
for the carries, and checks the copy's `review_audit` (read-only): one row per scripted verdict, in order, once.

Scenarios:
* burst  - N verdicts at gap-ms; the latency table, requests per verdict by route, the save backlog over time.
* undo   - a burst, then Ctrl Z (undoes the last verdict, returns to it); then, with saves held, one verdict and an
           immediate Ctrl Z: nothing may be sent for it.
* refuse - a burst in which verdict `--refuse-at` (1-based) is answered 409 by the fetch wrapper.
* loss   - saves held, `--n` verdicts, reload; afterwards each of them is saved exactly once.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

INIT = r"""
(() => {
  const B = window.__burst = { log: [], keys: [], paints: [], backlog: [], dialogs: 0, hold: false, refuse: null, refuseDelay: 2000, refused: [] };
  const of = window.fetch.bind(window);
  const bodyOf = (init) => { try { return init && init.body ? JSON.parse(init.body) : null } catch { return null } };
  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : input.url;
    const method = (init && init.method) || 'GET';
    const rec = { url, method, t0: performance.now(), t1: null, status: null, body: method === 'POST' ? bodyOf(init) : null };
    B.log.push(rec);
    const isSave = method === 'POST' && /\/verdicts?$/.test(url);
    if (isSave && B.hold) { rec.held = true; return new Promise(() => {}); }
    if (isSave && B.refuse != null && rec.body) {
      // one target refused: a single POST is answered 409; a bulk POST is sent without it and the refusal is put back
      // in its place in the answer
      const want = B.refuse;
      const late = () => new Promise(r => setTimeout(r, B.refuseDelay || 0));
      if (rec.body.target_id === want) {
        B.refuse = null; await late();
        B.refused.push(want); rec.t1 = performance.now(); rec.status = 409;
        return new Response(JSON.stringify({ detail: `burst: refused ${want}` }), { status: 409, headers: { 'content-type': 'application/json' } });
      }
      const list = rec.body.verdicts;
      const at = Array.isArray(list) ? list.findIndex(v => v.target_id === want) : -1;
      if (at >= 0) {
        B.refuse = null; await late();
        B.refused.push(want);
        const rest = list.filter((_, i) => i !== at);
        let ans = { results: [], counts: null };
        if (rest.length) {
          const r = await of(url, { ...init, body: JSON.stringify({ ...rec.body, verdicts: rest }) });
          ans = await r.json();
        }
        ans.results.splice(at, 0, { ok: false, status: 409, error: `burst: refused ${want}`, client_id: list[at].client_id });
        rec.t1 = performance.now(); rec.status = 200;
        return new Response(JSON.stringify(ans), { status: 200, headers: { 'content-type': 'application/json' } });
      }
    }
    try { const r = await of(input, init); rec.status = r.status; rec.t1 = performance.now(); return r; }
    catch (e) { rec.t1 = performance.now(); rec.err = String(e); throw e; }
  };
  const item = () => document.querySelector('[data-testid="inspector"]')?.getAttribute('data-item') ?? null;
  const drawn = () => {
    const p = document.querySelector('[data-testid="inspector"] [data-testid="context-trace"] svg path');
    return !!p && (p.getAttribute('d') || '').length > 10;
  };
  window.addEventListener('keydown', e => { B.keys.push({ key: e.key, ctrl: e.ctrlKey, t: performance.now(), from: item() }); }, true);
  let last = null;
  const frame = (ts) => {
    const it = item();
    if (it && it !== last && drawn()) { B.paints.push({ item: it, t: performance.now() }); last = it; }
    const pend = document.querySelector('[data-testid="saves-pending"]');
    B.backlog.push([performance.now(), pend ? pend.getAttribute('data-pending') : null, B.log.filter(r => r.method === 'POST' && r.t1 == null).length]);
    if (B.backlog.length > 20000) B.backlog.splice(0, 10000);
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
})();
"""


def get_json(url: str):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def pct(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1)))))
    return xs[k]


def latencies(keys, paints):
    """Per verdict key: ms from the key press to the first paint of another item after it."""
    out = []
    for k in keys:
        nxt = next((p for p in paints if p["t"] >= k["t"] and p["item"] != k["from"]), None)
        out.append(None if nxt is None else nxt["t"] - k["t"])
    return out


def route_of(url: str) -> str:
    u = url.split("?")[0] + ("?" if "/items?" in url else "")
    for pat, name in (("/carries", "GET carries"), ("/counts", "GET counts"), ("/thumbs", "GET thumbs"), ("/items?", "GET items (batch)"),
                      ("/items/", "GET item"), ("/verdicts", "POST verdicts"), ("/verdict", "POST verdict"),
                      ("/undo", "POST undo"), ("/review/queues/", "GET queue"), ("/review/queues", "GET queues")):
        if pat in u:
            return name
    return u


def audit_rows(db: str, queue: int, after_id: int):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = c.execute("SELECT id, action, target_ids, undone_at, payload_json FROM review_audit "
                         "WHERE queue_id = ? AND id > ? ORDER BY id", (queue, after_id)).fetchall()
        return [{"id": r[0], "action": r[1], "targets": json.loads(r[2]), "undone": r[3] is not None,
                 "verdict": json.loads(r[4] or "{}").get("verdict"),
                 "pending": bool(json.loads(r[4] or "{}").get("carry_pending"))} for r in rows]
    finally:
        c.close()


def max_audit(db: str) -> int:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return int(c.execute("SELECT COALESCE(MAX(id), 0) FROM review_audit").fetchone()[0])
    finally:
        c.close()


def wait_settled(page, timeout_s=180.0):
    """Until no POST is in flight (held ones excepted) and, where the indicator exists, it says all saved."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        st = page.evaluate("""() => ({ open: __burst.log.filter(r => r.method === 'POST' && r.t1 == null && !r.held).length,
                                        ind: document.querySelector('[data-testid="saves-pending"]')?.getAttribute('data-pending') ?? null })""")
        if st["open"] == 0 and (st["ind"] in (None, "0")):
            return time.monotonic() - t0
        time.sleep(0.1)
    raise SystemExit(f"writes still open after {timeout_s} s")


def wait_carries(db, queue, after_id, timeout_s=300.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        if not any(r["pending"] for r in audit_rows(db, queue, after_id)):
            return time.monotonic() - t0
        time.sleep(0.25)
    return None


def wait_page_quiet(page, quiet_s=1.5, timeout_s=30.0):
    """Until no request has been in flight for `quiet_s` (the page's first reads done), at most `timeout_s`."""
    t0 = time.monotonic()
    time.sleep(1.0)
    while time.monotonic() - t0 < timeout_s:
        if page.evaluate(f"() => !__burst.log.some(r => r.t1 == null && !r.held) && performance.now() - Math.max(0, ...__burst.log.map(r => r.t1 || 0)) > {quiet_s * 1000}"):
            return
        time.sleep(0.2)


def press_burst(page, n, gap_ms, key="n", react_ms=100):
    """`n` key presses `gap_ms` apart - but, like the researcher, never on a card not drawn yet: a press waits for the
    next item to paint (up to 10 s) plus `react_ms`. With every step painting inside the gap this IS a fixed cadence."""
    for i in range(n):
        t0 = time.monotonic()
        before = page.evaluate("() => __burst.paints.length")
        page.keyboard.press(key)
        try:
            page.wait_for_function(f"() => __burst.paints.length > {before}", timeout=10000, polling="raf")
        except Exception:
            pass
        painted = time.monotonic()
        if i == n - 1:
            break
        d = max(t0 + gap_ms / 1000, painted + (react_ms / 1000 if painted - t0 > gap_ms / 1000 else 0)) - time.monotonic()
        if d > 0:
            time.sleep(d)


def summary(page, label, n_keys_from=0):
    b = page.evaluate("() => ({ keys: __burst.keys, paints: __burst.paints, log: __burst.log.map(r => ({ url: r.url, method: r.method, t0: r.t0, t1: r.t1, status: r.status, held: !!r.held })), backlog: __burst.backlog })")
    res = page.evaluate("""() => performance.getEntriesByType('resource').filter(e => e.name.includes('/api/')).map(e => ({
        name: e.name, fetchStart: e.fetchStart, requestStart: e.requestStart, responseStart: e.responseStart, responseEnd: e.responseEnd }))""")
    keys = [k for k in b["keys"][n_keys_from:] if not k["ctrl"] and k["key"] == "n"]
    lat = latencies(keys, b["paints"])
    got = [x for x in lat if x is not None]
    t_first = keys[0]["t"] if keys else 0
    t_last = keys[-1]["t"] if keys else 0
    win = [r for r in b["log"] if t_first - 1 <= r["t0"] <= t_last + 300]
    by = {}
    for r in win:
        by.setdefault(route_of(r["url"]), []).append(r)
    per = {k: round(len(v) / max(1, len(keys)), 2) for k, v in sorted(by.items())}
    dur = {k: round(statistics.median([(r["t1"] or r["t0"]) - r["t0"] for r in v if r["t1"]]), 1) if any(r["t1"] for r in v) else None for k, v in by.items()}
    # Resource Timing: browser queue (requestStart - fetchStart) and bridge time to first byte, by route
    rt = {}
    for e in res:
        if not (t_first - 1 <= e["fetchStart"] <= t_last + 300):
            continue
        name = route_of(e["name"].split("127.0.0.1")[-1].split(":", 1)[-1])
        q = (e["requestStart"] or e["fetchStart"]) - e["fetchStart"]
        srv = (e["responseStart"] - e["requestStart"]) if e["requestStart"] else None
        rt.setdefault(name, {"queue": [], "bridge": []})
        rt[name]["queue"].append(q)
        if srv is not None:
            rt[name]["bridge"].append(srv)
    rts = {k: {"queue_p50": round(statistics.median(v["queue"]), 1) if v["queue"] else None,
               "queue_max": round(max(v["queue"]), 1) if v["queue"] else None,
               "bridge_p50": round(statistics.median(v["bridge"]), 1) if v["bridge"] else None,
               "bridge_max": round(max(v["bridge"]), 1) if v["bridge"] else None} for k, v in rt.items()}
    backlog_max = max((x[2] for x in b["backlog"] if t_first <= x[0] <= t_last + 300), default=0)
    out = {"label": label, "n": len(keys), "painted": len(got),
           "p50": round(pct(got, 50), 1) if got else None, "p95": round(pct(got, 95), 1) if got else None,
           "max": round(max(got), 1) if got else None, "over150": sum(1 for x in lat if x is None or x > 150),
           "steps_ms": [None if x is None else round(x) for x in lat],
           "requests_per_verdict": per, "fetch_ms_p50": dur, "resource_timing": rts,
           "posts_open_max": backlog_max, "keys": keys, "log": b["log"], "paints": b["paints"]}
    print(json.dumps({k: v for k, v in out.items() if k not in ("keys", "log", "paints", "steps_ms")}, indent=1))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True)
    ap.add_argument("--queue", type=int, default=57)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--gap-ms", type=int, default=300)
    ap.add_argument("--rail", choices=("collapsed", "open"), default="collapsed")
    ap.add_argument("--scenario", choices=("burst", "undo", "refuse", "loss"), default="burst")
    ap.add_argument("--refuse-at", type=int, default=20)
    ap.add_argument("--out", default=None, help="write the JSON summary here")
    ap.add_argument("--headed", action="store_true")
    a = ap.parse_args(argv)

    info = get_json(a.url.rstrip("/") + "/api/runtime")
    if info.get("mode") != "sandbox" or not info.get("db_copy"):
        raise SystemExit(f"refusing: {a.url} is not a sandbox bridge (mode={info.get('mode')!r}); this script writes verdicts")
    db = info["db_copy"]
    start_id = max_audit(db)
    result = {"scenario": a.scenario, "url": a.url, "queue": a.queue, "gap_ms": a.gap_ms, "rail": a.rail}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not a.headed)
        ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
        ctx.add_init_script(INIT)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
        dialogs = []

        def on_dialog(d):
            dialogs.append(d.type)
            d.accept()
        page.on("dialog", on_dialog)
        rail = "?rail=queue" if a.rail == "open" else ""
        page.goto(f"{a.url}/#/review/queue/{a.queue}{rail}")
        page.wait_for_selector('[data-testid="inspector"] [data-testid="context-trace"] svg path', timeout=120000)
        if a.rail == "open" and "rail=queue" not in page.url:
            page.evaluate("() => { location.hash = location.hash + (location.hash.includes('?') ? '&' : '?') + 'rail=queue' }")
            page.wait_for_selector('[data-testid="queue-rail"]', timeout=60000)
        wait_page_quiet(page)                # the first window, the queue list: let the page settle before timing
        page.mouse.click(5, 500)            # a user gesture (beforeunload needs one) on nothing clickable

        if a.scenario == "refuse":
            # verdict refuse_at lands on the item on screen at that key press; the hook is armed for it just before
            press_burst(page, a.refuse_at - 1, a.gap_ms)
            target = page.evaluate("() => document.querySelector('[data-testid=\"inspector\"]').getAttribute('data-item')")
            page.evaluate(f"() => {{ __burst.refuse = {json.dumps(target)} }}")
            press_burst(page, a.n - a.refuse_at + 1, a.gap_ms)
            result["refused_target"] = target
        elif a.scenario == "loss":
            page.evaluate("() => { __burst.hold = true }")
            press_burst(page, a.n, a.gap_ms)
            time.sleep(0.5)
            held = page.evaluate("() => __burst.log.filter(r => r.held).length")
            keys = page.evaluate("() => __burst.keys.filter(k => k.key === 'n').map(k => k.from)")
            result["held_posts"] = held
            result["judged_items"] = keys
            page.reload()
            page.wait_for_selector('[data-testid="inspector"] [data-testid="context-trace"] svg path', timeout=120000)
            time.sleep(1.0)
            result["dialogs"] = list(dialogs)
        else:
            press_burst(page, a.n, a.gap_ms)

        if a.scenario != "loss":
            result["summary"] = summary(page, f"{a.scenario} {a.n} x {a.gap_ms} ms, rail {a.rail}")
        if a.scenario == "undo":
            # 1. Ctrl Z straight after the burst, saves and carries still catching up: undoes the last verdict (taking
            #    it back unsent, or undoing it at the bridge once its save is answered) and returns to its item
            last_from = result["summary"]["keys"][-1]["from"]
            t0 = time.monotonic()
            page.keyboard.press("Control+z")
            page.wait_for_function(f"() => document.querySelector('[data-testid=\"inspector\"]')?.getAttribute('data-item') === {json.dumps(last_from)}", timeout=60000)
            result["undo_returned_ms"] = round(1000 * (time.monotonic() - t0))
            wait_settled(page)
            result["undo_settled_ms"] = round(1000 * (time.monotonic() - t0))
        t_set = time.monotonic()
        result["all_saved_s"] = round(wait_settled(page), 2)
        carried = wait_carries(db, a.queue, start_id)
        result["carries_done_s"] = None if carried is None else round(time.monotonic() - t_set, 2)
        ind = page.evaluate("() => document.querySelector('[data-testid=\"saves-pending\"]')?.textContent ?? null")
        result["indicator_text"] = ind

        if a.scenario == "undo":
            rows = audit_rows(db, a.queue, start_id)
            last = [r for r in rows if str(r["targets"][0]) == last_from]
            result["undo_last_rows"] = last           # undone, or none at all (taken back before it was sent)
            result["undo_ok"] = (not last) or (len(last) == 1 and last[0]["undone"])
            # 2. a verdict NOT YET SENT: the save before it is held in flight, so it waits; Ctrl Z takes it back, sends
            #    nothing for it and returns to it
            page.evaluate("() => { __burst.hold = true }")
            n_before = page.evaluate("() => __burst.log.filter(r => r.method === 'POST').length")
            page.keyboard.press("n")                              # this one's save goes out and hangs
            page.wait_for_function("() => __burst.log.some(r => r.held)", timeout=10000)
            time.sleep(0.3)
            here = page.evaluate("() => document.querySelector('[data-testid=\"inspector\"]').getAttribute('data-item')")
            page.keyboard.press("n")                              # this one waits behind it
            time.sleep(0.3)
            page.keyboard.press("Control+z")
            time.sleep(1.0)
            posts = page.evaluate(f"() => __burst.log.filter(r => r.method === 'POST').slice({n_before}).map(r => ({{ url: r.url, held: !!r.held, body: r.body }}))")
            back = page.evaluate("() => document.querySelector('[data-testid=\"inspector\"]').getAttribute('data-item')")
            sent_for_it = [p_ for p_ in posts if any(v.get("target_id") == here for v in (p_["body"] or {}).get("verdicts", []))]
            result["unsent_undo"] = {"item": here, "returned_to": back, "posts_for_it": len(sent_for_it), "posts_after": len(posts),
                                     "ok": back == here and not sent_for_it}
            page.evaluate("() => { __burst.hold = false }")

        rows = audit_rows(db, a.queue, start_id)
        result["audit"] = [{k: r[k] for k in ("id", "action", "targets", "undone", "verdict")} for r in rows]
        result["carry_pending_left"] = sum(1 for r in rows if r["pending"])
        if a.scenario in ("burst", "refuse", "undo"):
            scripted = [k["from"] for k in result["summary"]["keys"]]
            if a.scenario == "refuse":
                scripted.remove(result["refused_target"])     # its first verdict was refused; a later one is fine
            if a.scenario == "undo":
                scripted = scripted[:-1]        # the last was undone (or taken back unsent); judged on its own above
            verdict_rows = [r for r in rows if r["action"] == "verdict"]
            got = [str(r["targets"][0]) for r in verdict_rows][:len(scripted)]
            result["exact"] = got == scripted and len(verdict_rows) >= len(scripted)
            result["exact_detail"] = {"scripted": len(scripted), "rows": len(verdict_rows),
                                      "first_mismatch": next((i for i, (x, y) in enumerate(zip(got, scripted)) if x != y), None),
                                      "duplicates": len(got) - len(set(got))}
            if a.scenario == "refuse":
                result["refusal_card"] = page.evaluate("() => document.querySelector('[data-testid=\"write-refused\"]')?.textContent ?? null")
                result["on_item"] = page.evaluate("() => document.querySelector('[data-testid=\"inspector\"]')?.getAttribute('data-item')")
        if a.scenario == "loss":
            judged = result["judged_items"]
            counts = {t: sum(1 for r in rows if str(r["targets"][0]) == t and r["action"] == "verdict") for t in judged}
            result["saved_counts"] = counts
            result["exact"] = all(v == 1 for v in counts.values()) and len(counts) == len(judged)
        result["errors"] = errors[:20]
        browser.close()

    slim = {k: v for k, v in result.items() if k not in ("audit",)}
    if "summary" in slim:
        slim["summary"] = {k: v for k, v in slim["summary"].items() if k not in ("keys", "log", "paints")}
    print(json.dumps({k: v for k, v in slim.items() if k != "summary"}, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
