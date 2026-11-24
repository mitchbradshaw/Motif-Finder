"""
test_as_review_momentum.py
==========================
AS (2026-11-24), the page half, run under Node. The researcher: "can you prioritise feeding the next candidate in
faster over saving verdicts, so that momentum can be gained ... and the lag for verdicts to catch up can increase but
still process slowly in the background?"

Measured on a sandbox copy before the change: six steps painted in 20-40 ms, then 0.4-4 s each (p50 858 ms over 50
verdicts 300 ms apart). The five-deep window refilled one read per step, and every verdict also sent a counts read, a
one-id thumbnail read and a carry poll; at about 0.35 s of bridge work per verdict against a 0.3 s gap the bridge fell
behind and every read slowed. What these pin:

* the window is deep (16 unjudged ahead) and is refilled in ONE batched read when it runs low, not one read per step;
* a landing that came from a verdict's advance reads its window at once (the settle is for arrow-key scrubbing);
* saves wait in a queue (`review/saves.ts`, pure): sent in gesture order, several in one request, the newest one
  withdrawn by Ctrl Z while it is unsent, journalled in localStorage so a reload replays it, and a save may wait behind
  an item read only up to a cap.
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
PREFETCH_TS = os.path.join(REVIEW, "prefetch.ts")
SAVES_TS = os.path.join(REVIEW, "saves.ts")


def _read(*parts):
    return io.open(os.path.join(SRC, *parts), encoding="utf-8").read()


def _code(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)//.*$", "", line) for line in text.splitlines())


def _node(module_path, body_js):
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


# ── R1: a deep window, refilled in one batch ─────────────────────────────────

def test_the_window_is_deep_and_the_item_cache_holds_it():
    ahead = int(re.search(r"export const PREFETCH_AHEAD = (\d+)", _read("review", "prefetch.ts")).group(1))
    assert 15 <= ahead <= 20, f"the window is {ahead} deep; a burst empties a shallow one"
    lru = int(re.search(r"const ITEM_LRU_MAX = (\d+)", _read("api", "review.ts")).group(1))
    assert lru >= ahead + 5, "the item cache would evict the window it was asked to keep"


def test_the_window_is_refilled_in_one_batch_when_it_runs_low():
    got = _node(PREFETCH_TS, """
const ids = Array.from({ length: 18 }, (_, i) => 'i' + i);       // 16 ahead, the next unit, the previous one
const all = new Set(ids);
const heldAll = id => all.has(id);
const low = new Set(ids.slice(0, 12));                          // 12 of 18 held: six missing at the far end
const nearMissing = new Set(ids.slice(1));                       // the very next one is missing
const fewMissing = new Set(ids.filter(i => i !== 'i15' && i !== 'i16'));
out = {
  full: M.refillIds(ids, heldAll),
  low: M.refillIds(ids, id => low.has(id)),
  near: M.refillIds(ids, id => nearMissing.has(id)),
  few: M.refillIds(ids, id => fewMissing.has(id)),
  batch: M.REFILL_AT,
};
""")
    assert got["full"] == [], "a full window asked for more"
    assert got["low"] == [f"i{i}" for i in range(12, 18)], "a low window was not refilled with every missing id, nearest first"
    assert got["near"] == ["i0"], "the item the next key press lands on was not asked for at once"
    assert got["few"] == [], "two missing far ahead are worth a request of their own (a read per step again)"
    assert 3 <= got["batch"] <= 8


def test_a_landing_from_a_verdict_reads_its_window_at_once_in_one_call():
    got = _node(CURSOR_TS, """
const log = [];
const io = {
  held: id => id === 'A',
  read: async id => { log.push(['read', id]); return { id } },
  warm: async ids => { log.push(['warm', ids]); await sleep(5) },
  window: got => got ? ['n1', 'n2', 'n3'] : [],
};
const a = new AbortController();
await M.land('A', a.signal, io, 0);
await sleep(5);
const now = log.slice();
log.length = 0;
const b = new AbortController();
await M.land('A', b.signal, io, 40);
await sleep(10);
const early = log.slice();
await sleep(60);
out = { now, early, late: log };
""")
    assert got["now"] == [["read", "A"], ["warm", ["n1", "n2", "n3"]]], \
        "a verdict's landing did not read its window at once, in one call"
    assert got["early"] == [["read", "A"]], "an arrow-key landing read its window inside the settle"
    assert got["late"] == [["read", "A"], ["warm", ["n1", "n2", "n3"]]]


def test_the_inspector_lands_without_the_settle_after_a_verdict_and_batches_the_window():
    code = _code(_read("review", "Inspector.tsx"))
    assert "refillIds(" in code and "prefetchItems(q, " in code, "the window is not read as one batch"
    assert "consumeAdvance(" in code, "a landing from a verdict's advance still waits the settle"
    api = _code(_read("api", "review.ts"))
    assert "export function prefetchItems(" in api and "/items?ids=" in api


# ── R3/R4/R5: the save queue ─────────────────────────────────────────────────

SAVES_IO = """
const store = (() => { const m = new Map(); return { getItem: k => m.has(k) ? m.get(k) : null, setItem: (k, v) => m.set(k, String(v)),
  removeItem: k => m.delete(k), get length() { return m.size }, key: i => [...m.keys()][i] ?? null, dump: () => Object.fromEntries(m) } })();
const body = (id, v = 'not_interesting') => ({ client_id: 'c' + id, target_id: id, verdict: v });
"""


def test_saves_go_in_gesture_order_several_in_one_request_one_queue_at_a_time():
    got = _node(SAVES_TS, SAVES_IO + """
const q = new M.SaveQueue();
q.add('57', body('a'), 'A', 1); q.add('57', body('b'), 'B', 2); q.add('58', body('c'), 'C', 3); q.add('57', body('d'), 'D', 4);
const first = q.take().map(p => p.meta);
const states = q.items.map(p => p.state);
const second = q.take();                                   // nothing waiting at the head: the head is sending
q.done(q.items[0]); q.done(q.items[0]);
const third = q.take().map(p => p.meta);
q.done(q.items[0]);
const fourth = q.take().map(p => p.meta);
out = { first, states, second: second.length, third, fourth, max: M.SAVE_BATCH_MAX };
""")
    assert got["first"] == ["A", "B"], "a bulk save mixed queues or skipped the order"
    assert got["states"] == ["sending", "sending", "waiting", "waiting"]
    assert got["second"] == 0, "a second request went while the first was out (audit order is the gestures')"
    assert got["third"] == ["C"] and got["fourth"] == ["D"]
    assert 10 <= got["max"] <= 100


def test_ctrl_z_withdraws_the_newest_unsent_save_and_waits_for_one_in_flight():
    got = _node(SAVES_TS, SAVES_IO + """
const q = new M.SaveQueue();
q.add('57', body('a'), 'A', 1); q.add('57', body('b'), 'B', 2);
const w1 = q.withdrawLast('57');
const left = q.items.map(p => p.meta);
q.take();
const w2 = q.withdrawLast('57');
const w3 = q.withdrawLast('99');
out = { w1: w1 && w1.meta, left, w2, w3, n: q.count('57') };
""")
    assert got["w1"] == "B", "the newest unsent verdict was not taken back"
    assert got["left"] == ["A"]
    assert got["w2"] == "sending", "a save in flight was withdrawn (the bridge may already hold it)"
    assert got["w3"] is None and got["n"] == 1


def test_the_journal_keeps_each_unsaved_verdict_until_its_ack_and_replays_only_a_dead_pages():
    got = _node(SAVES_TS, SAVES_IO + """
M.touchPage(store, 'me', 10_000);
M.touchPage(store, 'old', 1_000);
M.touchPage(store, 'twin', 9_500);
M.journalAdd(store, '57', { ...body('a'), at: 1, label: 'a' }, 'old');
M.journalAdd(store, '57', { ...body('b'), at: 2, label: 'b' }, 'twin');
M.journalAdd(store, '57', { ...body('c'), at: 3, label: 'c' }, 'me');
M.journalAdd(store, '58', { ...body('d'), at: 4, label: 'd' }, 'old');
const orphans = M.orphaned(store, '57', 'me', 10_000).map(e => e.target_id);
M.journalRemove(store, '57', 'ca');
const after = M.journalEntries(store, '57').map(e => e.target_id);
const other = M.journalEntries(store, '58').map(e => e.target_id);
out = { orphans, after, other, stale: M.PAGE_STALE_MS };
""")
    assert got["orphans"] == ["a"], "a verdict of a page still open (another tab) or of this page was replayed"
    assert got["after"] == ["b", "c"], "the ack did not take its verdict out of the journal"
    assert got["other"] == ["d"], "the journal is not kept per queue"
    assert 3000 <= got["stale"] <= 30000


def test_a_save_waits_behind_an_item_read_only_up_to_the_cap():
    got = _node(SAVES_TS, """
out = { idle: M.mayFlush(0, 100, 150), busy: M.mayFlush(1, 100, 150), capped: M.mayFlush(2, 100, 100 + M.SAVE_WAIT_CAP_MS),
        cap: M.SAVE_WAIT_CAP_MS };
""")
    assert got["idle"] is True and got["busy"] is False, "a save went while the next item was being read"
    assert got["capped"] is True, "a save starved behind reads"
    assert 500 <= got["cap"] <= 5000


def test_the_store_saves_verdicts_through_the_queue_with_a_journal_and_an_unload_warning():
    store = _code(_read("review", "store.ts"))
    assert "export async function commitSave(" in store, "verdicts are not saved through the queue"
    assert "journalAdd(" in store and "journalRemove(" in store, "an unsaved verdict is not journalled"
    assert "beforeunload" in store, "closing the page with verdicts unsaved does not warn"
    assert "withdrawLast(" in store, "Ctrl Z cannot take back a verdict not yet sent"
    assert "crypto.randomUUID()" in store, "a save carries no client id (exactly-once)"
    assert "postVerdicts(" in store
    shell = _code(_read("review", "Shell.tsx"))
    assert 'data-testid="saves-pending"' in shell, "the save backlog is not shown"


def test_per_verdict_reads_are_gone_from_the_step():
    store = _code(_read("review", "store.ts"))
    body = re.search(r"export async function commitSave\(.*?\n}\n", store, re.S).group(0)
    assert "bumpCountsVersion()" not in body, "every verdict still re-reads the counts"
    api = _code(_read("api", "review.ts"))
    assert "/carries?ids=" in api, "every verdict still polls its own carry"
