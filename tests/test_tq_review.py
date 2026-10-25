"""
test_tq_review.py
=================
tq-review (2026-10-25, code-quality wave): the Review inspector's cursor as one state model.

"Where the researcher is and what is pending for that spot" was spread over seven mechanisms in `Inspector.tsx`
(two settle timers, a `live` flag, an `onItem` ref, a `timers` ref cleared in three places, guards inside the flash
and advance callbacks) plus a refusal copied four times across Inspector and ClusterView. It is now
`review/cursor.ts`: `land()` is one landing on an item (one settle, one signal, the read, then the prefetch window one
at a time) and `createCursor()` holds where the researcher is and the one pending advance. These tests run that file
under Node and pin that the copies are gone; the behaviour is the night-a / night-review behaviour, unchanged.
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
REVIEW = os.path.join(SRC, "review")
CURSOR_TS = os.path.join(REVIEW, "cursor.ts")
JUDGED_TS = os.path.join(REVIEW, "judged.ts")


def _read(*parts):
    return io.open(os.path.join(SRC, *parts), encoding="utf-8").read()


def _code(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)//.*$", "", line) for line in text.splitlines())


def _node(module_path, body_js):
    """Import a pure TypeScript module under node as `M`, run `body_js` (top-level await allowed; it sets `out`)
    and return `out` as JSON."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(module_path), f"{module_path} does not exist"
    url = "file:///" + module_path.replace("\\", "/").lstrip("/")
    script = (f"import * as M from {json.dumps(url)};\n"
              "const sleep = ms => new Promise(r => setTimeout(r, ms));\n"
              "let out = null;\n"
              f"{body_js}\n"
              "process.stdout.write(JSON.stringify(out));\n")
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script], capture_output=True,
                       text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# A fake item store: `held` ids answer at once; every read and warm is logged with the time it was sent.
IO = """
const log = [];
const t0 = Date.now();
const io = (held = [], fail = false) => ({
  held: id => held.includes(id),
  read: async id => { log.push(['read', id]); if (fail) throw new Error('boom'); return { id } },
  warm: async id => { log.push(['warm', id]); await sleep(5) },
  window: got => got ? ['n1', 'n2', 'n3'] : [],
});
"""


# ── land(): one landing on an item ───────────────────────────────────────────

def test_an_item_not_held_is_read_only_after_the_settle_and_never_if_the_researcher_moves_on():
    got = _node(CURSOR_TS, IO + """
const a = new AbortController();
const p = M.land('A', a.signal, io(), 40).catch(e => e.name);
await sleep(10); a.abort();
const r1 = await p;
const b = new AbortController();
const q = M.land('B', b.signal, io(), 40);
await sleep(10); const early = log.filter(x => x[1] === 'B').length;
const r2 = await q;
out = { r1, r2, early, log };
""")
    assert got["r1"] == "AbortError", "a superseded landing must reject as an abort (the read hook drops it)"
    assert ["read", "A"] not in got["log"], "an item passed within the settle was read"
    assert got["early"] == 0, "an item not held was read before the settle"
    assert got["r2"] == {"id": "B"}


def test_a_held_item_is_read_at_once_with_no_settle():
    got = _node(CURSOR_TS, IO + """
const a = new AbortController();
const p = M.land('A', a.signal, io(['A']), 200);
await sleep(5);
out = { read: log.some(x => x[0] === 'read' && x[1] === 'A'), r: await p };
a.abort();
""")
    assert got["read"], "a held item waited the settle before its read (night-a #24)"
    assert got["r"] == {"id": "A"}


def test_the_window_is_warmed_one_at_a_time_nearest_first_and_only_after_the_settle():
    got = _node(CURSOR_TS, IO + """
const a = new AbortController();
await M.land('A', a.signal, io(['A']), 30);
const before = log.filter(x => x[0] === 'warm').length;
await sleep(80);
out = { before, log };
a.abort();
""")
    assert got["before"] == 0, "the window was read before the researcher stopped on the item"
    assert got["log"] == [["read", "A"], ["warm", "n1"], ["warm", "n2"], ["warm", "n3"]]


def test_moving_on_stops_the_window_and_a_failed_read_warms_nothing():
    got = _node(CURSOR_TS, IO + """
const a = new AbortController();
const slow = io(['A']); slow.warm = async id => { log.push(['warm', id]); await sleep(30) };
await M.land('A', a.signal, slow, 10);
await sleep(25); a.abort();          // during the first warm
await sleep(80);
const moved = log.slice();
log.length = 0;
const b = new AbortController();
const err = await M.land('B', b.signal, io(['B'], true), 10).catch(e => e.message);
await sleep(40);
out = { moved, err, failed: log };
""")
    assert got["moved"] == [["read", "A"], ["warm", "n1"]], "the window kept reading after the researcher moved"
    assert got["err"] == "boom", "a failed read is not reported to the card"
    assert got["failed"] == [["read", "B"]], "the window was warmed around a failed read"


# ── createCursor(): where the researcher is, and the one pending advance ─────

def test_the_advance_belongs_to_the_item_it_was_set_on():
    got = _node(CURSOR_TS, """
const c = M.createCursor(20);
const fired = [];
c.moveTo('A');
const set = c.after('A', () => fired.push('A'));
const refused = c.after('B', () => fired.push('B'));     // the researcher is not on B
c.moveTo('A');                                            // a re-read of the same item (a version bump) keeps it
await sleep(40);
c.after('A', () => fired.push('A2'));
c.moveTo('C');                                            // moving on cancels it
await sleep(40);
c.moveTo('D'); c.after('D', () => fired.push('D')); c.cancel();   // an undo cancels it
await sleep(40);
out = { set, refused, fired, at: c.at };
""")
    assert got["set"] is True and got["refused"] is False
    assert got["fired"] == ["A"], got["fired"]
    assert got["at"] == "D"


def test_the_window_rule_stays_in_prefetch_and_the_timings_are_unchanged():
    code = _code(io.open(CURSOR_TS, encoding="utf-8").read()) if os.path.isfile(CURSOR_TS) else ""
    assert re.search(r"export const STEP_SETTLE_MS = 150\b", code), "the settle is no longer 150 ms"
    assert re.search(r"export const ADVANCE_MS = 60\b", code), "the advance is no longer one frame (60 ms)"
    assert "import" not in code, "cursor.ts must stay pure so Node can run it"


# ── the Inspector holds no timer or ref bookkeeping of its own ───────────────

def test_the_inspector_has_no_timers_refs_or_live_flags_for_the_cursor():
    code = _code(_read("review", "Inspector.tsx"))
    for gone in ("timers.current", "onItem", "let live", "STEP_SETTLE_MS", "ADVANCE_MS", "window.setTimeout",
                 "peekItem(q, id, opts) || itemHeld"):
        assert gone not in code, f"Inspector.tsx still carries {gone!r}"
    assert "land(id, signal," in code and "createCursor" in code


# ── the "try again" refusal lives once, in the store ─────────────────────────

def test_the_write_in_flight_refusal_is_one_copy_in_the_store():
    text = "a verdict is still being written — try again"
    for name in ("Inspector.tsx", "ClusterView.tsx"):
        code = _code(_read("review", name))
        assert "writesInFlight" not in code and text not in code, f"{name} still copies the in-flight refusal"
    store = _code(_read("review", "store.ts"))
    assert store.count(text) == 1, "the refusal text is not defined once in store.ts"
    assert "writesInFlight" not in store


# ── QueueRow.judged is the one truth ─────────────────────────────────────────

def test_judged_is_computed_once_from_the_bridge_flag():
    rows = [
        {"verdict": "seed", "baseVerdict": "seed", "judged": False},   # explore-spans: a prior, not judged here
        {"verdict": "interesting", "baseVerdict": "interesting", "judged": True},
        {"judged": 1},
        {"judged": 0, "baseVerdict": "interesting"},
        {"baseVerdict": "interesting"},           # a fixture row with no bridge flag: its verdict says judged
        {"verdict": "artifact"},
        {},
        None,
    ]
    got = _node(JUDGED_TS, f"out = {json.dumps(rows)}.map(r => M.rowJudged(r));")
    assert got == [False, True, True, False, True, True, False, False]
    api = _code(_read("api", "review.ts"))
    assert "servedJudged" not in api, "the wrong flag and its corrected copy are still both kept"
    assert "judged: rowJudged(raw)" in api


# ── carry: typed fields, one invalidation decision beside the caches ─────────

def test_the_carry_fields_are_picked_and_the_invalidation_is_one_function():
    api = _code(_read("api", "review.ts"))
    assert "as CarryFields" not in api, "carryOf is still a bare cast"
    assert "export function invalidateAfterCarry(" in api
    assert "(r as unknown as" not in _code(_read("review", "queue.ts")) + api
    insp = _code(_read("review", "Inspector.tsx"))
    assert "clearItemCacheExcept" not in insp and "queueHoldsAny" not in insp
    assert "if (invalidateAfterCarry(data, carriedIds)) bumpReviewVersion()" in insp


def test_queue_sources_and_404s_are_typed():
    code = _code(_read("review", "index.tsx")) + _code(_read("review", "Inspector.tsx"))
    assert "source as string" not in code, "QueueSource still lacks the sources the pages compare against"
    assert "instanceof ApiError" in _code(_read("review", "index.tsx"))
