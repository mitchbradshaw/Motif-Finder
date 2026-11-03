"""Screenshots of the live site for the thesis and its reports.

Each shot opens one page of the bridge (8765 by default), optionally seeds the browser storage the page reads, runs
a few steps (click, fill, press, wait), waits for the element that shows the result, and saves a PNG. A page error or
a browser console error fails the shot loudly, so a picture of a red card is never saved as a result. It changes
nothing by itself: it clicks only what a shot names.

    python scripts/thesis/site_shots.py shots.json [--out docs/thesis/figures/roundb] [--base http://127.0.0.1:8765]

shots.json is a list of:
    {"name": "b5_map_overview",                 # the PNG's name
     "hash": "discovery/map",                    # the page, as after "#/" in the address bar
     "wait": "[data-testid=\"map-card\"]",       # what must be on the page before the picture
     "element": "[data-testid=\"map-card\"]",   # optional: picture one element instead of the viewport
     "full_page": false,                         # optional: the whole scrolled page
     "steps": [{"click": "sel"}, {"fill": ["sel", "text"]}, {"press": "Escape"}, {"wait": "sel"}, {"sleep": 500}],
     "session_storage": {"key": "value"}, "local_storage": {"key": "value"},
     "viewport": [1440, 900], "timeout_ms": 120000, "settle_ms": 1500}
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = os.path.join(ROOT, "docs", "thesis", "figures", "roundb")


def _storage_script(session, local):
    lines = [f"window.sessionStorage.setItem({json.dumps(k)}, {json.dumps(v)});" for k, v in (session or {}).items()]
    lines += [f"window.localStorage.setItem({json.dumps(k)}, {json.dumps(v)});" for k, v in (local or {}).items()]
    return "try {" + "".join(lines) + "} catch (e) {}"


def shoot(shots, out_dir=DEFAULT_OUT, base="http://127.0.0.1:8765", scale=2.0):
    from playwright.sync_api import sync_playwright

    os.makedirs(out_dir, exist_ok=True)
    saved, failed = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for s in shots:
            vw, vh = s.get("viewport", [1440, 900])
            ctx = browser.new_context(viewport={"width": vw, "height": vh}, device_scale_factor=scale)
            if s.get("session_storage") or s.get("local_storage"):
                ctx.add_init_script(_storage_script(s.get("session_storage"), s.get("local_storage")))
            page = ctx.new_page()
            errors = []
            page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
            timeout = int(s.get("timeout_ms", 120000))
            try:
                page.goto(f"{base}/#/{s['hash']}", timeout=timeout)
                for step in s.get("steps", []):
                    if "click" in step:
                        page.click(step["click"], timeout=timeout)
                    elif "fill" in step:
                        page.fill(step["fill"][0], step["fill"][1], timeout=timeout)
                    elif "press" in step:
                        page.keyboard.press(step["press"])
                    elif "wait" in step:
                        page.wait_for_selector(step["wait"], timeout=timeout)
                    elif "sleep" in step:
                        page.wait_for_timeout(int(step["sleep"]))
                if s.get("wait"):
                    page.wait_for_selector(s["wait"], timeout=timeout)
                page.wait_for_timeout(int(s.get("settle_ms", 1500)))
                if errors:
                    raise RuntimeError("; ".join(errors[:3]))
                path = os.path.join(out_dir, f"{s['name']}.png")
                target = page.locator(s["element"]).first if s.get("element") else page
                if s.get("element"):
                    target.screenshot(path=path, timeout=timeout)
                else:
                    page.screenshot(path=path, full_page=bool(s.get("full_page")), timeout=timeout)
                saved.append(path)
                print(f"saved {os.path.relpath(path, ROOT)}")
            except Exception as exc:                                   # noqa: BLE001 - reported, never a picture
                failed.append((s["name"], f"{type(exc).__name__}: {exc}"))
                print(f"FAILED {s['name']}: {type(exc).__name__}: {str(exc)[:300]}", file=sys.stderr)
            finally:
                ctx.close()
        browser.close()
    return saved, failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("shots")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument("--scale", type=float, default=2.0)
    a = ap.parse_args(argv)
    with open(a.shots, encoding="utf-8") as fh:
        shots = json.load(fh)
    _, failed = shoot(shots, a.out, a.base, a.scale)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
