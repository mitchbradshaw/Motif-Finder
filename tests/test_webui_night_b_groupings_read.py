"""
test_webui_night_b_groupings_read.py
====================================
night-b: the atlas's `/api/library/groupings` storm. Opening the atlas fired TEN reads of the groupings list
within ~10 ms (the family page nine, a `?grouping=` the list does not hold eleven): `useAllGroupings` is called by
the page, the gate, both resolved-id hooks, the grouping bar and the drawer, and every call mounted its own read.
On the walk this looked like "the atlas reads groupings every 2 s" — it was ten at once, behind one sqlite
connection, on every Library open.

The fix is one shared read per moment: `library/groupingsRead.ts` hands every caller the read already in flight,
and a reload anywhere re-reads once for every caller (which also retires the stale-list problem the gate's
"re-read once" patch worked around). This file RUNS that module under Node (types stripped natively), as
`test_webui_seed_on_demand_client.py` does for `seedPeek.ts`; it skips when `node` is not on PATH. The source
half pins that `useAllGroupings` reads through it.
"""
import io
import json
import os
import re
import shutil
import subprocess

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")
READ_TS = os.path.join(CLIENT_SRC, "library", "groupingsRead.ts")
CHROME_TSX = os.path.join(CLIENT_SRC, "library", "chrome.tsx")


def _run(body):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(READ_TS), "webui/client/src/library/groupingsRead.ts does not exist"
    url = "file:///" + READ_TS.replace("\\", "/").lstrip("/")
    script = (f"import * as R from {json.dumps(url)};\n"
              "let fetches = 0, now = 0, fail = false;\n"
              "const fetcher = async () => { fetches++; if (fail) throw new Error('boom'); return ['g' + fetches] };\n"
              "const s = R.sharedRead(fetcher, { ttlMs: 2000, now: () => now });\n"
              + body +
              "\nprocess.stdout.write(JSON.stringify(out));\n")
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_ten_callers_at_once_make_one_read():
    got = _run("const xs = await Promise.all(Array.from({ length: 10 }, () => s.read()));\n"
               "const out = { fetches, xs };")
    assert got["fetches"] == 1
    assert all(x == ["g1"] for x in got["xs"])


def test_a_reload_reads_once_more_and_tells_every_caller():
    got = _run("let told = 0; const off1 = s.subscribe(() => told++); s.subscribe(() => told++);\n"
               "await s.read(); const v0 = s.version(); s.invalidate(); off1();\n"
               "const after = await Promise.all([s.read(), s.read(), s.read()]);\n"
               "s.invalidate();\n"
               "const out = { fetches, told, bumped: s.version() !== v0, after };")
    assert got["fetches"] == 2, "one read for the first open, one for the reload — not one per caller"
    assert got["told"] == 3, "both subscribers hear the first reload; the unsubscribed one not the second"
    assert got["bumped"] and got["after"] == [["g2"]] * 3


def test_a_later_open_reads_fresh_rather_than_serving_an_old_list():
    got = _run("await s.read(); now = 2500; const x = await s.read();\nconst out = { fetches, x };")
    assert got["fetches"] == 2 and got["x"] == ["g2"]


def test_a_failed_read_is_not_served_again():
    got = _run("fail = true; let e1 = null; try { await s.read() } catch (e) { e1 = e.message }\n"
               "fail = false; const x = await s.read();\nconst out = { fetches, e1, x };")
    assert got["e1"] == "boom", "the failure reaches the caller (a red card), it is not swallowed"
    assert got["fetches"] == 2 and got["x"] == ["g2"]


def test_use_all_groupings_reads_through_the_shared_read():
    src = io.open(CHROME_TSX, encoding="utf-8").read()
    body = src[src.index("export function useAllGroupings"):]
    body = body[:body.index("\n}\n")]
    assert "useSourced(getGroupings" not in body, "each caller mounting its own read is the storm"
    assert re.search(r"sharedRead|GROUPINGS\.read", src), "useAllGroupings reads through groupingsRead.ts"
