"""
test_webui_seed_on_demand_client.py
===================================
a2-p4: the client half of "the Seed page computes only when asked". The server
half is `test_webui_seed_on_demand.py` (webui/.venv).

The behavioural half RUNS `webui/client/src/api/seedPeek.ts` under Node (which
strips TypeScript types natively), as `test_webui_cross_page.py` does for
`explore/crossModel.ts`; it skips when `node` is not on PATH. The source-level
half always runs. What it pins:

* **The page's read never starts a search.** `seedResults` peeks: a result in
  hand, a running job joined and watched, or "not run yet" / "cancelled" —
  and the module that does it has no way to start one (no imports, no fetch;
  the POST lives only behind *Run preview*).
* **Run preview and Cancel are on the page**, with the estimate beside the
  button, and a run with no cut says on the apply bar that it keeps all
  k = 200 matches per channel.
* **The picker reaches every family**: a *Family medoids* tab, a grouping
  control, and the store's sixteen spans renamed *Catalogue spans*.
* **The smoke walk checks it**: a not-previewed state that asserts the bridge
  started no job, a cancelled preview, the grouping-aware picker; and the
  scale-bank state that now presses *Run preview*.
"""
import glob
import io
import json
import os
import re
import shutil
import subprocess

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")
PEEK_TS = os.path.join(CLIENT_SRC, "api", "seedPeek.ts")
SMOKE_DIR = os.path.join(PROJECT_ROOT, "webui", "smoke_pages")
SMOKE_PY = os.path.join(PROJECT_ROOT, "webui", "smoke.py")


def _read(path):
    assert os.path.isfile(path), f"{os.path.relpath(path, PROJECT_ROOT)} is missing"
    return io.open(path, encoding="utf-8").read()


def _src(*parts):
    return _read(os.path.join(CLIENT_SRC, *parts))


def _peek(answers, alive_calls=None):
    """Run `peekPreview` over a scripted server: `answers` are what successive GETs return. Reports the outcome,
    how many GETs and sleeps it made, and the progress it reported."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH; the peek is exercised by webui/smoke.py instead")
    assert os.path.isfile(PEEK_TS), "webui/client/src/api/seedPeek.ts does not exist"
    url = "file:///" + PEEK_TS.replace("\\", "/").lstrip("/")
    alive = "undefined" if alive_calls is None else f"() => calls < {int(alive_calls)}"
    script = (
        f"import * as P from {json.dumps(url)};\n"
        f"const answers = {json.dumps(answers)};\n"
        "let calls = 0, sleeps = 0; const progress = [];\n"
        "const get = async () => answers[Math.min(calls++, answers.length - 1)];\n"
        "let out;\n"
        f"try {{ out = await P.peekPreview(get, {{ sleep: async () => {{ sleeps++ }}, pollMs: 1, alive: {alive},\n"
        "  onProgress: p => progress.push(p) }); }\n"
        "catch (e) { out = { threw: String((e && e.message) || e) } }\n"
        "process.stdout.write(JSON.stringify({ out, calls, sleeps, progress }));\n")
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# ── the peek, run ───────────────────────────────────────────────────────────

def test_a_query_nobody_has_run_is_not_run_after_one_read():
    got = _peek([{"ready": False, "job_id": None, "key": "k", "note": "no result for this query yet"}])
    assert got["out"]["status"] == "not-run"
    assert got["calls"] == 1 and got["sleeps"] == 0, "it reads once and stops: nothing to wait for"


def test_a_cancelled_preview_reads_cancelled_not_never_run():
    got = _peek([{"ready": False, "job_id": None, "cancelled": True, "cancelledJob": 7, "note": "cancelled"}])
    assert got["out"]["status"] == "cancelled" and got["out"]["jobId"] == 7
    assert got["calls"] == 1


def test_a_running_preview_is_joined_and_watched_to_its_result():
    pending = {"ready": False, "job_id": 5, "progress": {"done": 1, "total": 4, "message": "CH1 · null 1/3"},
               "elapsedS": 2.0, "etaS": 6.0}
    got = _peek([pending, dict(pending, progress={"done": 3, "total": 4, "message": "CH2"}),
                 {"ready": True, "key": "k", "candidates": []}])
    assert got["out"]["status"] == "ready" and got["out"]["result"]["key"] == "k"
    assert got["calls"] == 3 and got["sleeps"] == 2
    assert [p["jobId"] for p in got["progress"]] == [5, 5]
    assert [p["done"] for p in got["progress"]] == [1, 3]
    assert got["progress"][0]["etaS"] == 6.0


def test_a_preview_cancelled_while_watched_ends_cancelled():
    got = _peek([{"ready": False, "job_id": 5, "progress": {"done": 1, "total": 4}},
                 {"ready": False, "job_id": None, "cancelled": True, "cancelledJob": 5}])
    assert got["out"]["status"] == "cancelled" and got["out"]["jobId"] == 5
    assert got["calls"] == 2


def test_a_peek_the_page_moved_on_from_stops():
    got = _peek([{"ready": False, "job_id": 5, "progress": {"done": 1, "total": 4}}] * 3, alive_calls=1)
    assert "threw" in got["out"] and "superseded" in got["out"]["threw"]
    assert got["calls"] == 1


def test_the_peek_cannot_start_a_search():
    src = _read(PEEK_TS)
    assert not re.search(r"^\s*import\s", src, re.M), "pure: no imports, so Node can run it and it can reach no POST"
    assert "fetch(" not in src and "POST" not in src


# ── the wiring, read ────────────────────────────────────────────────────────

def _function(src, head):
    i = src.index(head)
    nxt = [j for j in (src.find("\nexport ", i + 1), src.find("\nasync function ", i + 1),
                       src.find("\nfunction ", i + 1)) if j > 0]
    return src[i:min(nxt) if nxt else len(src)]


def test_the_pages_read_peeks_and_only_run_preview_posts():
    api = _src("api", "discovery.ts")
    body = _function(api, "async function seedResults")
    assert "peekPreview" in body
    assert "startDiscoverySeedResults" not in body, "the page's read must never start the search"
    run = _function(api, "export const runSeedPreview")
    assert "startDiscoverySeedResults" in run, "Run preview is the one place the preview is started"


def test_the_seed_page_has_run_preview_cancel_and_says_what_a_run_without_a_cut_keeps():
    page = _src("discovery", "SeedPage.tsx")
    for testid in ("seed-not-previewed", "seed-preview-cancelled", "preview-estimate", "apply-no-cut"):
        assert re.search(rf"""['"]{testid}['"]""", page), f"{testid} is not on the page"
    for testid in ("run-preview", "seed-preview-cancel"):
        assert f'testid="{testid}"' in page, f"no {testid} control"
    assert "runSeedPreview(" in page and "cancelJob(" in page
    assert "matches per channel kept" in page, "the apply bar says what a run with no cut keeps"


def test_the_picker_reaches_every_family_and_names_the_catalogue_spans():
    page = _src("discovery", "SeedPage.tsx")
    assert "'Family medoids'" in page and "'Catalogue spans'" in page
    assert "'Family medoid'" not in page, "the store's sixteen spans are not Library families"
    assert "seed-filter-grouping" in page
    picker = _function(page, "function SeedPicker")
    assert "getSeedPicker(" in picker and re.search(r"\bgrouping:", picker), "the picker sends the grouping it reads"
    assert re.search(r"interface DiscSeedPickerQuery\b[^}]*\bgrouping\?:", _read(os.path.join(CLIENT_SRC, "api.ts")), re.S)


# ── the smoke walk ──────────────────────────────────────────────────────────

def _states(path):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


def test_the_smoke_walk_checks_the_seed_page_runs_nothing_on_its_own():
    files = glob.glob(os.path.join(SMOKE_DIR, "*a2_p4_seed.json"))
    assert len(files) == 1, "one a2-p4 seed manifest"
    # it changes the session (the draft seed, its zone, the section) and puts them back at its end, so it walks after
    # every other manifest that opens a Discovery page, and before the w3 cancel state, which must stay last
    mine = os.path.basename(files[0])
    for fn in os.listdir(SMOKE_DIR):
        if fn.endswith(".json") and fn != mine and "discovery/" in _read(os.path.join(SMOKE_DIR, fn)):
            assert fn < mine, f"{fn} opens a Discovery page and walks after {mine}"
    assert mine < "zzzzzzzzzzz_w3_cancel.json"
    states = _states(files[0])
    blob = json.dumps(states)
    not_run = [s for s in states if s.get("jobs_unchanged")]
    assert not_run and any('seed-not-previewed' in json.dumps(s.get("expect")) for s in not_run)
    cancel = [s for s in states if "seed-preview-cancelled" in json.dumps(s.get("expect"))]
    assert cancel and "run-preview" in json.dumps(cancel[0]["actions"]) \
        and "seed-preview-cancel" in json.dumps(cancel[0]["actions"])
    assert "seed-picker-family" in blob and "seed-filter-grouping" in blob


def test_the_scale_bank_state_presses_run_preview():
    state = next(s for s in _states(os.path.join(SMOKE_DIR, "library_edges.json"))
                 if s["state"] == "fixup-v-scale-bank-searches-every-length")
    acts = json.dumps(state["actions"])
    assert "run-preview" in acts and acts.index("run-preview") < acts.index("null-per-length")


def test_smoke_asserts_a_state_started_no_job():
    smoke = _read(SMOKE_PY)
    assert re.search(r"def jobs_unchanged\(self", smoke), "the check is a Smoke method, like no_overlap"
    assert "/api/health" in smoke and 'e.get("jobs_unchanged")' in smoke


# ── fix round (critic of 2026-10-17) ───────────────────────────────────────

def test_a_failed_preview_is_a_state_that_offers_the_run_again():
    """F1: the GET's 500 for a failed newest job made the page's read fail, and its Retry only read again — the
    query could never be run again from the page. The failure is now a state of the query, with its message and
    traceback, and the page offers Run preview beside it."""
    err = {"message": "the seeded search failed: RuntimeError: a draw broke", "traceback": "Traceback (most recent ...)"}
    got = _peek([{"ready": False, "job_id": None, "failed": True, "failedJob": 9, "error": err, "note": "failed"}])
    assert got["out"]["status"] == "failed"
    assert got["out"]["jobId"] == 9 and got["out"]["error"] == err
    assert got["calls"] == 1
    page = _src("discovery", "SeedPage.tsx")
    shown = _function(page, "function NotPreviewed")
    assert "seed-preview-failed" in shown and "traceback" in shown, "the failure is shown loud, traceback included"
    assert 'testid="run-preview"' in shown, "beside Run preview"


def test_a_preview_a_run_is_drawing_is_watched_without_a_preview_cancel():
    """F5: the GET reports a preview being drawn by a run (`drawnBy`); the page watches it, and offers no
    *Cancel preview* for it — cancelling that job would cancel the run."""
    pending = {"ready": False, "job_id": 12, "progress": {"done": 1, "total": 3, "message": "CH1 · null 1/2"},
               "drawnBy": {"runKey": "seed_abc", "label": "seed abc"}}
    got = _peek([pending, {"ready": True, "key": "k", "candidates": []}])
    assert got["out"]["status"] == "ready"
    assert got["progress"][0]["drawnBy"] == {"runKey": "seed_abc", "label": "seed abc"}
    page = _src("discovery", "SeedPage.tsx")
    assert re.search(r"onCancel=\{progress\.drawnBy \? undefined : cancelPreview\}", page), \
        "no preview Cancel for a preview a run is drawing"
    assert "draws this preview first; it appears here when the run finishes" not in page, \
        "the page-memory hold is gone: the server says which run draws which query"


def test_reviews_promotion_card_opens_the_family_in_the_grouping_it_was_read_in():
    """F3: *Open in Library* navigated to `library/family/<F>` without its grouping, so the Library opened the newest
    grouping of any basis and said the family was not in it."""
    parts = _src("review", "parts.tsx")
    links = _function(parts, "function PromotedEntryLinks")
    assert "grouping" in links and re.search(r"grouping=|set\('grouping'", links), \
        "the family link carries the grouping its family was read in"


def test_the_seed_page_says_when_its_remembered_seed_moved_off_the_held_out_recording():
    """a2 integration (P1 x P4). Once the lock is back on, the bridge opens the first available seed in place of a
    remembered one on the held-out recording and says why in `draft.heldOutNote` (a2-p1's m2). The page shows that
    sentence rather than switching seeds silently: the setup mapping carries it and the page renders it."""
    api = _src("api", "discovery.ts")
    assert re.search(r"heldOutNote:\s*p\.draft\.heldOutNote", api), "getSeedSetup drops the bridge's heldOutNote"
    page = _src("discovery", "SeedPage.tsx")
    assert 'testid="seed-draft-held-out-note"' in page and "setup.data.heldOutNote" in page, \
        "the Seed page does not show why its seed moved off the held-out recording"
