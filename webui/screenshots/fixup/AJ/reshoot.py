import json, os, urllib.request
from playwright.sync_api import sync_playwright
URL = "http://127.0.0.1:8796"
SHOTS = r"C:\Users\mmebr\Documents\CNN\webui\screenshots\fixup\AJ"
rows = json.loads(urllib.request.urlopen(URL + "/api/hpc/exported").read())["jobs"]
full = next(r for r in rows if r["kind"] == "shape_cluster_cnn" and not r["smoke"])
smoke = next(r for r in rows if r["smoke"])
errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1500, "height": 1000})
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{URL}/#/jobs", wait_until="networkidle")
    page.wait_for_selector('[data-testid="exported-table"]')
    page.wait_for_selector('[data-testid="live-local-table"]')
    page.wait_for_timeout(800)
    page.screenshot(path=os.path.join(SHOTS, "00-jobs-overview.png"))
    page.click(f'[data-testid="exported-row-{full["name"]}"]')
    page.wait_for_selector(f'[data-testid="exported-reason-full-{full["name"]}"]')
    page.wait_for_timeout(400)
    page.screenshot(path=os.path.join(SHOTS, "10-jobs-wrong-recipe-refused.png"))
    page.click(f'[data-testid="exported-row-{full["name"]}"]')
    page.click(f'[data-testid="exported-row-{smoke["name"]}"]')
    page.wait_for_selector(f'[data-testid="exported-imported-{smoke["name"]}"]')
    page.wait_for_timeout(400)
    page.screenshot(path=os.path.join(SHOTS, "09-jobs-row-results-imported.png"))
    # the demo half, still wearing its chip
    page.locator('[data-testid="jobs-demo-section"]').scroll_into_view_if_needed()
    page.wait_for_timeout(400)
    page.screenshot(path=os.path.join(SHOTS, "12-jobs-the-demo-half-keeps-its-chip.png"))
    b.close()
print("states:", {r["name"]: (r["state"], r["reason"]) for r in rows})
print("ERRORS:", errors)
