"""
test_webui_tq_reads.py
======================
tq-reads (2026-10-25): one shared-read primitive instead of five.

The night wave wrote "many callers want the same read at once, so share it" three more times in one night —
`shell/sharedRead.ts` (the header count), `library/groupingsRead.ts` (the Library's groupings) and
`explore/coalesce.ts` (the Signal page's whole-channel reads) — beside two older module-level copies
(`shell/heldOutLock.ts`, `analyse/useAdapters.ts`). Two of them exported an interface called `SharedRead` with
different shapes. They are now one pure module, `api/sharedRead.ts`, plus one React hook, `api/useSharedRead.ts`.

The Node half RUNS the primitive (types stripped natively; skips without `node`). The one option that differs per
use is what a failure means: `onFailure: 'hold'` (the header) keeps the last value and lets the failure stand as
the answer until the TTL passes; `'drop'` (the default) forgets it, so the next read asks again. The source half
pins that the copies are gone and every user reads through the one module.
"""
import io
import json
import os
import re
import shutil
import subprocess

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src")
SHARED_TS = os.path.join(SRC, "api", "sharedRead.ts")


def _src(*parts):
    return io.open(os.path.join(SRC, *parts), encoding="utf-8").read()


def _node(body):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(SHARED_TS), "webui/client/src/api/sharedRead.ts does not exist"
    url = "file:///" + SHARED_TS.replace("\\", "/").lstrip("/")
    script = (f"import * as M from {json.dumps(url)};\n"
              "let n = 0, fail = false, now = 0;\n"
              "const fetcher = async k => { const i = ++n; await null; if (fail) throw new Error('boom'); return String(k) + ':' + i };\n"
              + body + "\nprocess.stdout.write(JSON.stringify(out));\n")
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_hold_keeps_the_last_value_and_does_not_reask_within_the_ttl():
    got = _node("const s = M.makeSharedRead(fetcher, { ttlMs: 1000, initial: 'none', onFailure: 'hold', now: () => now });\n"
                "const v0 = s.snapshot().value; await s.read(); fail = true; now = 2000;\n"
                "const e = []; for (let i = 0; i < 2; i++) { try { await s.read() } catch (x) { e.push(x.message) } }\n"
                "const out = { v0, n, e, value: s.snapshot().value };")
    assert got["v0"] == "none", "before any answer the snapshot is the initial value, never a guess"
    assert got["e"] == ["boom", "boom"], "every caller hears the failure"
    assert got["n"] == 2, "a held failure is the answer until the TTL passes: no second request"
    assert got["value"] == "undefined:1", "the last good value stays on screen"


def test_drop_forgets_a_failure_so_the_next_read_asks_again():
    got = _node("const s = M.makeSharedRead(fetcher, { ttlMs: 1000, now: () => now });\n"
                "fail = true; let e = null; try { await s.read() } catch (x) { e = x.message }\n"
                "fail = false; const x = await s.read();\nconst out = { n, e, x };")
    assert got["e"] == "boom" and got["n"] == 2 and got["x"] == "undefined:2"


def test_the_keyed_form_shares_only_the_read_in_flight_by_default():
    got = _node("const s = M.makeSharedRead(fetcher);\n"
                "const xs = await Promise.all([s.read('a'), s.read('a'), s.read('b')]);\n"
                "const again = await s.read('a');\nconst out = { n, xs, again };")
    assert got["xs"] == ["a:1", "a:1", "b:2"]
    assert got["again"] == "a:3", "with no TTL a settled read is not kept: a re-read after a write is real"


def test_invalidate_bumps_the_version_and_the_snapshot_is_stable_between_changes():
    got = _node("const s = M.makeSharedRead(fetcher, { ttlMs: 1000, now: () => now });\n"
                "let told = 0; s.subscribe(() => told++);\n"
                "const a = s.snapshot(); const same = a === s.snapshot();\n"
                "s.invalidate(); const b = s.snapshot();\n"
                "const out = { same, v0: a.version, v1: b.version, told };")
    assert got["same"], "useSyncExternalStore needs the same snapshot object until something changes"
    assert got["v0"] == 0 and got["v1"] == 1 and got["told"] == 1


def test_the_hook_is_built_on_use_sync_external_store():
    hook = _src("api", "useSharedRead.ts")
    assert "useSyncExternalStore" in hook and "./sharedRead" in hook


def test_the_copies_are_gone():
    for parts in (("shell", "sharedRead.ts"), ("library", "groupingsRead.ts"), ("explore", "coalesce.ts"),
                  ("api", "needYou.ts")):
        assert not os.path.exists(os.path.join(SRC, *parts)), f"{'/'.join(parts)} is a second copy of the shared read"
    defs = []
    for root, _dirs, names in os.walk(SRC):
        for name in names:
            if name.endswith((".ts", ".tsx")):
                text = io.open(os.path.join(root, name), encoding="utf-8").read()
                if re.search(r"\binterface\s+SharedRead\b", text):
                    defs.append(name)
    assert defs == ["sharedRead.ts"], f"exactly one SharedRead interface, found in {defs}"


def test_every_user_reads_through_the_one_module():
    assert "makeSharedRead" in _src("shell", "needYouShared.ts")
    assert "makeSharedRead" in _src("library", "chrome.tsx")
    explore = _src("api", "explore.ts")
    assert "makeSharedRead" in explore and "explore/coalesce" not in explore, "the api layer reads through its own module"
    for parts in (("shell", "heldOutLock.ts"), ("analyse", "useAdapters.ts")):
        text = _src(*parts)
        assert "makeSharedRead" in text, f"{'/'.join(parts)} hand-rolls its own in-flight share"
        assert not re.search(r"^let\s+inflight\b", text, re.M), f"{'/'.join(parts)} keeps a module-level `inflight`"
