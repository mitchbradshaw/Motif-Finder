"""Public poster: render poster.html to an A1 PDF and PNG previews (Playwright + Chromium, dev tooling only).

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/public_poster/render.py [--scale 1]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import style as S  # noqa: E402

W_MM, H_MM = 841, 594
PX_PER_MM = 96 / 25.4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.0, help="device scale for the PNG (3 = print quality)")
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    html = os.path.join(S.OUT, "poster.html")
    url = "file:///" + html.replace("\\", "/")
    w, h = round(W_MM * PX_PER_MM), round(H_MM * PX_PER_MM)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=a.scale)
        errors = []
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("requestfailed", lambda r: errors.append("failed: " + r.url))
        pg.goto(url, wait_until="networkidle")
        pg.wait_for_timeout(500)
        name = "poster_preview.png" if a.scale <= 1 else f"poster_x{a.scale:g}.png"
        pg.screenshot(path=os.path.join(S.OUT, name), full_page=False)
        if not a.no_pdf:
            pg.pdf(path=os.path.join(S.OUT, "poster_A1.pdf"), width=f"{W_MM}mm", height=f"{H_MM}mm",
                   print_background=True, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        # overflow check: any element whose content spills out of its box
        spill = pg.evaluate("""() => [...document.querySelectorAll('.card, .intro-text, .legend, .lead, .strip, header *')]
            .filter(e => e.scrollHeight > e.clientHeight + 2 || e.scrollWidth > e.clientWidth + 2)
            .map(e => (e.className || e.tagName) + ': ' + e.scrollWidth + 'x' + e.scrollHeight + ' in ' + e.clientWidth + 'x' + e.clientHeight)""")
        b.close()
    print("errors:", errors or "none")
    print("overflow:", spill or "none")
    print("wrote", name, "" if a.no_pdf else "and poster_A1.pdf")


if __name__ == "__main__":
    main()
