"""
fixup_c_domain_evidence.py
==========================
The evidence for fixup-c (one plot-domain rule): the same Library family, the
same Review candidate and the same Explore channel, screenshotted through a
RUNNING BRIDGE before and after, plus the family payload's size and read time.

    "/c/ProgramData/anaconda3/python.exe" scripts/fixup_c_domain_evidence.py \\
        --url http://127.0.0.1:8765 --out webui/screenshots/fixup/C --tag before

The bridge must be running in `--sandbox` (the default) and should be
restarted immediately beforehand. Two things here write, and only to the
sandbox copy of the database: `--declare-fig2a` declares `Fig2A_dt0p1.csv` as
volts through the audited Settings route (the unit every detector run assumed;
fixup-b left it undeclared, which withholds 67 % of the Library), so the
`drop_motifs10` population can be drawn at all.

Pins (the same as fixup-b's, so the three reports compare): Library family F-01
(M2_aug + Fig2A members), the Fig2A-only family F-117, Explore channel 1
(M2_aug_concat_fs1 CH0), Review queue 2's first candidate (detection 100).

What each page is measured for, off the DOM: the text the page prints about
scale, and — the acceptance test — every trace whose rendered path leaves its
plot box. Before the change `MiniTrace` clamped silently, so a clipped trace
never left its box: it ran along the frame instead. The `pinned_to_frame`
count catches that form: a trace path with a run of points sitting on the
clamp rows.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request

PAGES = [
    ("library-atlas", "library/atlas"),
    ("library-family-F-01", "library/family/F-01"),
    ("library-family-F-117", "library/family/F-117"),
    ("explore-signal-1", "explore/signal/1"),
    ("review-q2-item-100", "review/queue/2/100"),
]

#: Every trace path, its svg and its plot box; and every trace pinned to the
#: frame (a clamp's signature: >= 3 consecutive points on the top or bottom
#: clamp row of a MiniTrace, whose rows are 2 and height-2 in its viewBox).
MEASURE_JS = """() => {
  const out = { outside: [], pinned: 0, traces: 0 };
  for (const svg of document.querySelectorAll('svg')) {
    const box = svg.querySelector('[data-plot-box]') || (svg.classList.contains('k-mini') ? svg : null);
    if (!box) continue;
    const b = box.getBoundingClientRect();
    const paths = svg.querySelectorAll('[data-trace] path, path[data-trace]');
    const list = paths.length ? paths : (svg.classList.contains('k-mini') ? svg.querySelectorAll('path') : []);
    for (const p of list) {
      const d = p.getAttribute('d') || '';
      if (!d) continue;
      out.traces++;
      const r = p.getBoundingClientRect();
      if (r.top < b.top - 0.5 || r.bottom > b.bottom + 0.5 || r.left < b.left - 0.5 || r.right > b.right + 0.5) {
        const host = svg.closest('[data-testid]');
        out.outside.push((host && host.getAttribute('data-testid')) || svg.getAttribute('aria-label') || 'svg');
      }
      if (svg.classList.contains('k-mini')) {
        const h = +(svg.getAttribute('viewBox') || '0 0 0 0').split(' ')[3];
        const ys = Array.from(d.matchAll(/[ML]\\s*[-\\d.]+\\s+([-\\d.]+)/g)).map(m => +m[1]);
        let run = 0, worst = 0;
        for (const y of ys) { if (Math.abs(y - 2) < 0.05 || Math.abs(y - (h - 2)) < 0.05) { run++; worst = Math.max(worst, run) } else run = 0 }
        if (worst >= 3) out.pinned++;
      }
    }
  }
  return out;
}"""

SCALE_TEXT = ("[data-testid=atlas-scale-note], [data-testid=summary-trace-note], [data-testid=plot-clipped], "
              "[data-testid=reference-bar], [data-testid=mv-labels], [data-testid=member-scale-note]")


def _texts(page, selector: str) -> list[str]:
    loc = page.locator(selector)
    return [t.strip() for t in (loc.nth(i).text_content() or "" for i in range(min(loc.count(), 40))) if t.strip()]


def _get(url: str, path: str):
    t = time.perf_counter()
    with urllib.request.urlopen(url + path, timeout=600) as r:
        body = r.read()
    return body, time.perf_counter() - t


def declare_fig2a(url: str) -> str:
    """Declare Fig2A volts on the SANDBOX bridge (refused on anything else)."""
    rt = json.loads(_get(url, "/api/runtime")[0])
    if rt.get("mode") != "sandbox":
        raise SystemExit(f"refusing to declare a unit on a {rt.get('mode')!r} bridge")
    recs = json.loads(_get(url, "/api/recordings")[0])
    rows = recs if isinstance(recs, list) else recs.get("recordings", [])
    ids = sorted({int(ch["id"]) for g in rows for ch in g.get("channels", [])
                  if "Fig2A" in str(g.get("source_file", ""))})
    if not ids:
        return "no Fig2A recording registered"
    req = urllib.request.Request(f"{url}/api/registry/recording/{ids[0]}/units",
                                 data=json.dumps({"units": "V"}).encode(), method="PUT",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return f"declared V on recording {ids[0]}: {r.status}"


def payloads(url: str, families) -> dict:
    """The family read's size and wall-clock, second request (warm caches) and first."""
    out = {}
    for fid in families:
        body, first = _get(url, f"/api/library/family/{fid}")
        _, warm = _get(url, f"/api/library/family/{fid}")
        d = json.loads(body)
        members = (d.get("detail") or {}).get("members") or []
        out[fid] = {"bytes": len(body), "members": len(members),
                    "member_traces": sum(1 for m in members if m.get("trace")),
                    "points_per_member_trace": max((len(m.get("trace") or []) for m in members), default=0),
                    "first_read_s": round(first, 3), "warm_read_s": round(warm, 3)}
    return out


def biggest_families(url: str, n: int = 2) -> list[str]:
    fams = json.loads(_get(url, "/api/library/families")[0])
    fams = sorted(fams, key=lambda f: -int(f.get("members") or 0))
    return [f["id"] for f in fams[:n]]


def shoot(url: str, out_dir: str, tag: str) -> dict:
    from playwright.sync_api import sync_playwright

    os.makedirs(out_dir, exist_ok=True)
    record: dict = {"tag": tag, "url": url, "pages": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors: list[str] = []
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        for name, route in PAGES:
            errors.clear()
            page.goto(f"{url}/#/{route}", wait_until="networkidle")
            # a cold Atlas read takes tens of seconds: wait for every loading skeleton to go, then settle
            try:
                page.wait_for_function("() => !document.querySelector('.skeleton')", timeout=120000)
            except Exception as e:                      # say so in the record rather than shoot a skeleton silently
                errors.append(f"still loading after 120 s: {e}")
            page.wait_for_timeout(1500)
            path = os.path.join(out_dir, f"{tag}-{name}.png")
            page.screenshot(path=path, full_page=True)
            record["pages"][name] = {"route": route, "screenshot": os.path.relpath(path).replace(os.sep, "/"),
                                     "scale_text": _texts(page, SCALE_TEXT), "traces": page.evaluate(MEASURE_JS),
                                     "errors": list(errors)}
        browser.close()
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    ap.add_argument("--out", default=os.path.join("webui", "screenshots", "fixup", "C"))
    ap.add_argument("--tag", required=True)
    ap.add_argument("--declare-fig2a", action="store_true")
    a = ap.parse_args()
    url = a.url.rstrip("/")
    rec = {"declared": declare_fig2a(url) if a.declare_fig2a else None}
    big = biggest_families(url)
    rec["payload"] = payloads(url, ["F-01", "F-117", *[f for f in big if f not in ("F-01", "F-117")]])
    rec.update(shoot(url, a.out, a.tag))
    with open(os.path.join(a.out, f"{a.tag}.json"), "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=2)
    print(json.dumps({k: rec[k] for k in ("declared", "payload")}, indent=2))
    for k, v in rec["pages"].items():
        print(k, "traces", v["traces"]["traces"], "outside", len(v["traces"]["outside"]), "pinned", v["traces"]["pinned"], v["scale_text"][:3], v["errors"][:2])


if __name__ == "__main__":
    main()
