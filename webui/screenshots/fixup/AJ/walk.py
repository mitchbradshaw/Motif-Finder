"""fixup-aj: the researcher's walk on the sandbox bridge (port 8796), screenshots into webui/screenshots/fixup/AJ/.

1. Train a forest locally from Models › Launch → Jobs shows it running, then finished.
2. Create SLURM script for the CNN arm → Jobs lists it as written, with what to copy (and the Ward script, written
   from the cluster block's route).
3. The folder AI's local smoke produced, with its out/ copied back as if from the cluster → the Manifest inbox
   imports it → results imported → opens in Models › Results. A folder holding another recipe's out/ is refused
   with the reason.
"""
import json
import os
import shutil
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8796"
RT = r"C:\Users\mmebr\Documents\CNN\webui\runtime\20261007-004156"
HPC = os.path.join(RT, "hpc", "training")
SMOKE_OUT = (r"C:\Users\mmebr\AppData\Local\Temp\claude\C--Users-mmebr-Documents-CNN"
             r"\220a90bf-6eee-4be4-bd02-3587cfed6902\scratchpad\labrun\jobs\b2cnn_fusion_smoke_0b352d34\out")
SMOKE_NAME = "b2cnn_fusion_smoke_0b352d34"
SHOTS = r"C:\Users\mmebr\Documents\CNN\webui\screenshots\fixup\AJ"
os.makedirs(SHOTS, exist_ok=True)
log = {"steps": []}
only = set(sys.argv[1:])


def api(path, body=None):
    req = urllib.request.Request(URL + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"content-type": "application/json"}, method="GET" if body is None else "POST")
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def note(msg, **kw):
    print(msg, json.dumps(kw, default=str)[:400], flush=True)
    log["steps"].append({"msg": msg, **kw, "t": time.strftime("%H:%M:%S")})


def shot(page, name):
    page.wait_for_timeout(400)
    page.screenshot(path=os.path.join(SHOTS, name), full_page=True)
    note("screenshot", file=name)


errors = []
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1500, "height": 1000})
    page.on("console", lambda m: errors.append(f"console {m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

    if not only or "1" in only:
        # 1 — a forest trained locally, seen running then finished on Jobs
        page.goto(f"{URL}/#/models/launch?arm=b2&template=14&pool=8", wait_until="networkidle")
        page.wait_for_selector('[data-testid="b2-train-locally"]:not([disabled])', timeout=120000)
        before = {j["job_id"] for j in api("/api/jobs?limit=200")}
        page.click('[data-testid="b2-train-locally"]')
        jid = None
        for _ in range(60):
            new = [j for j in api("/api/jobs?limit=200") if j["job_id"] not in before and j.get("kind") == "training"]
            if new:
                jid = new[0]["job_id"]
                break
            time.sleep(0.5)
        note("forest job started", job_id=jid)
        page.evaluate("h => { location.hash = h }", "#/jobs")
        page.wait_for_selector(f'[data-testid="live-job-row-{jid}"][data-status="running"]', timeout=60000)
        page.wait_for_timeout(2500)
        shot(page, "01-jobs-forest-running.png")
        t0 = time.time()
        page.wait_for_selector(f'[data-testid="live-job-row-{jid}"]:not([data-status="running"])', timeout=1800000)
        st = page.get_attribute(f'[data-testid="live-job-row-{jid}"]', "data-status")
        note("forest job ended", job_id=jid, status=st, waited_s=round(time.time() - t0))
        page.click(f'[data-testid="live-job-row-{jid}"]')
        shot(page, "02-jobs-forest-finished.png")
        log["forest_job"] = api(f"/api/jobs/{jid}")

    if "1b" in only:
        jid = 64
        page.goto(f"{URL}/#/jobs", wait_until="networkidle")
        page.wait_for_selector(f'[data-testid="live-job-row-{jid}"][data-status="completed"]', timeout=60000)
        page.click(f'[data-testid="live-job-row-{jid}"]')
        shot(page, "02-jobs-forest-finished.png")
        log["forest_job"] = api(f"/api/jobs/{jid}")

    if not only or "2" in only:
        # 2 — Create SLURM script (CNN arm) → Jobs lists it as written, with what to copy
        page.goto(f"{URL}/#/models/launch?arm=b2&template=14&pool=8&model=cnn", wait_until="networkidle")
        page.wait_for_selector('[data-testid="b2-slurm"]:not([disabled])', timeout=120000)
        page.click('[data-testid="b2-slurm"]')
        page.wait_for_selector('[data-testid="b2-slurm-out"]', timeout=900000)
        shot(page, "03-launch-cnn-slurm-written.png")
        # the cluster block's Ward over every training window (the route its card calls)
        ward = api("/api/shape/trees/835b72599ef0619a/ward-slurm", {})
        note("ward script", job_dir=ward["job_dir"], recipe=ward["recipe_hash"], n=ward["n"])
        page.goto(f"{URL}/#/jobs", wait_until="networkidle")
        page.wait_for_selector('[data-testid="exported-table"]', timeout=60000)
        rows = api("/api/hpc/exported")["jobs"]
        full = next(r for r in rows if r["kind"] == "shape_cluster_cnn" and not r["smoke"])
        log["full_cnn"] = {k: full[k] for k in ("name", "recipe_hash", "state", "total_bytes", "sbatch_command")}
        log["full_cnn"]["n_copy"] = len(full["copy"])
        page.click(f'[data-testid="exported-row-{full["name"]}"]')
        page.wait_for_selector(f'[data-testid="exported-copy-{full["name"]}"]')
        shot(page, "04-jobs-cnn-script-written-what-to-copy.png")

    if not only or "3" in only:
        rows = api("/api/hpc/exported")["jobs"]
        full = next(r for r in rows if r["kind"] == "shape_cluster_cnn" and not r["smoke"])
        # 3 — the smoke's out/ copied back, as if from the cluster
        dest = os.path.join(HPC, SMOKE_NAME, "out")
        if not os.path.isdir(dest):
            shutil.copytree(SMOKE_OUT, dest)
        page.goto(f"{URL}/#/jobs", wait_until="networkidle")
        page.wait_for_selector(f'[data-testid="exported-row-{SMOKE_NAME}"][data-state="returned"]', timeout=60000)
        shot(page, "05-jobs-results-copied-back.png")
        page.click('[data-testid="open-inbox"]')
        page.wait_for_selector('[data-testid="inbox-live"]')
        page.click(f'[data-testid="inbox-pick-{SMOKE_NAME}"]')
        shot(page, "06-inbox-folder-chosen.png")
        page.click('[data-testid="inbox-import"]')
        page.wait_for_selector('[data-testid="inbox-outcome"]:not([data-outcome="importing"])', timeout=600000)
        outcome = page.get_attribute('[data-testid="inbox-outcome"]', "data-outcome")
        note("inbox import", outcome=outcome, message=page.inner_text('[data-testid="inbox-outcome-message"]'))
        shot(page, "07-inbox-results-imported.png")
        page.click('[data-testid="inbox-open"]')
        page.wait_for_selector('[data-testid="b2-blind-line"]', timeout=120000)
        log["opened"] = page.evaluate("() => location.hash")
        shot(page, "08-models-results-the-imported-run.png")
        # the imported row on Jobs
        page.goto(f"{URL}/#/jobs", wait_until="networkidle")
        page.wait_for_selector(f'[data-testid="exported-row-{SMOKE_NAME}"][data-state="imported"]', timeout=60000)
        shot(page, "09-jobs-row-results-imported.png")

        # a folder from a different recipe: the full CNN job's folder with the smoke's out/ copied into it by mistake
        wrong = os.path.join(full["job_dir"], "out")
        if not os.path.isdir(wrong):
            shutil.copytree(SMOKE_OUT, wrong)
        page.goto(f"{URL}/#/jobs", wait_until="networkidle")
        page.wait_for_selector(f'[data-testid="exported-row-{full["name"]}"][data-state="returned"]', timeout=60000)
        page.click(f'[data-testid="exported-import-{full["name"]}"]')
        page.wait_for_selector(f'[data-testid="exported-row-{full["name"]}"][data-state="refused"]', timeout=120000)
        page.click(f'[data-testid="exported-row-{full["name"]}"]')
        log["refused_reason"] = page.inner_text(f'[data-testid="exported-reason-{full["name"]}"]')
        note("refused", reason=log["refused_reason"])
        shot(page, "10-jobs-wrong-recipe-refused.png")
        page.click('[data-testid="open-inbox"]')
        page.wait_for_selector('[data-testid="inbox-attempts"]')
        shot(page, "11-inbox-attempts.png")
        log["attempts"] = api("/api/hpc/inbox")["attempts"]
        log["exported"] = [{k: r[k] for k in ("name", "kind", "recipe_hash", "state", "reason", "total_bytes", "imported")}
                           for r in api("/api/hpc/exported")["jobs"]]
    b.close()

log["errors"] = errors
with open(os.path.join(SHOTS, f"walk{'-' + '-'.join(sorted(only)) if only else ''}.json"), "w", encoding="utf-8") as fh:
    json.dump(log, fh, indent=1, default=str)
print("ERRORS:", errors)
