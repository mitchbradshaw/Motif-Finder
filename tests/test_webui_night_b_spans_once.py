"""
test_webui_night_b_spans_once.py
================================
night-b: the Signal page read the WHOLE channel's spans twice at once — `getSignalLive` (api/explore.ts) and the
page's own ‹ N / M › list (SignalPage.tsx) both call `getSpans(id, 0, duration)` on mount — and Cross-channel
read it a third way through `getCrossChannel`. On a channel with ~90 k detections each read is 2.5–5 s on the
bridge, and the two concurrent copies slow each other (fixture bridge: 2.7 s + 5.4 s for one page open).

`explore/coalesce.ts` hands a caller the identical read already in flight; nothing is kept once it settles, so a
re-read after a write is a fresh read. RUN under Node (types stripped natively); skips without `node`. The source
half pins that the three whole-channel call sites go through it.
"""
import io
import json
import os
import shutil
import subprocess

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")
COALESCE_TS = os.path.join(CLIENT_SRC, "explore", "coalesce.ts")


def _run(body):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(COALESCE_TS), "webui/client/src/explore/coalesce.ts does not exist"
    url = "file:///" + COALESCE_TS.replace("\\", "/").lstrip("/")
    script = (f"import * as C from {json.dumps(url)};\n"
              "let n = 0, fail = false; const read = async k => { const i = ++n; await null; if (fail) throw new Error('boom'); return k + ':' + i };\n"
              "const once = C.coalesced(read);\n" + body + "\nprocess.stdout.write(JSON.stringify(out));\n")
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_the_same_read_at_once_is_one_read():
    got = _run("const xs = await Promise.all([once('a'), once('a'), once('b')]);\nconst out = { n, xs };")
    assert got["n"] == 2 and got["xs"] == ["a:1", "a:1", "b:2"]


def test_a_read_after_the_first_settled_is_fresh():
    got = _run("await once('a'); const x = await once('a');\nconst out = { n, x };")
    assert got["n"] == 2 and got["x"] == "a:2", "nothing is cached past the read: a re-read after a write is real"


def test_a_failure_reaches_every_waiting_caller_and_is_not_kept():
    got = _run("fail = true; const r = await Promise.allSettled([once('a'), once('a')]);\n"
               "fail = false; const x = await once('a');\n"
               "const out = { n, r: r.map(v => v.status), x };")
    assert got["r"] == ["rejected", "rejected"]
    assert got["n"] == 2 and got["x"] == "a:2"


def _src(*parts):
    return io.open(os.path.join(CLIENT_SRC, *parts), encoding="utf-8").read()


def test_the_whole_channel_reads_share_one_read():
    api = _src("api", "explore.ts")
    assert "getSpans(channelId, 0, ch.duration_s)" not in api
    assert "getSpans(referenceId, 0, ch.duration_s)" not in api
    assert "getSpans(ch.id, 0, ch.duration_s)" not in _src("explore", "SignalPage.tsx")
    assert api.count("getWholeChannelSpans(") >= 2 and "export const getWholeChannelSpans" in api
    assert "getWholeChannelSpans" in _src("explore", "SignalPage.tsx")


def test_the_channel_read_is_shared_too():
    """night-b: on the scale fixture Cross-channel read `/api/channels/{id}` twice AT ONCE (the window read and the
    detections chip's, both through api/explore.ts) — 37 s and 30 s on a fresh bridge, the page 45 s to paint. Both
    go through the same in-flight share as the spans."""
    api = _src("api", "explore.ts")
    assert "await getChannel(channelId)" not in api and "await getChannel(referenceId)" not in api
    assert "getChannelShared(" in api
