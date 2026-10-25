"""
test_night_a_review.py
======================
night pass A (2026-10-19): what the night's drive of Review on the scale fixture found, pinned at the source
(the drive itself is `scripts/night/night_a.py`, against a sandbox bridge).

* **A finished queue says it is finished.** Every live queue whose items are all judged lands on
  `?state=exhausted`, which read "No more items in the demo fixture … the other 0 are not in the fixture" —
  fixture language on the most ordinary end of a real queue. A queue with no items at all said the same.
* **No fixture ids, no fixture words on the face.** "Pick another queue" navigated to the fixture queue `q-12`
  (a 404 on live data), and the arrow keys at either end of a queue toasted "this is the last item in the demo
  fixture" / "the first item in the queue fixture".
"""
import io
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEW = os.path.join(PROJECT_ROOT, "webui", "client", "src", "review")


def _src(name):
    return io.open(os.path.join(REVIEW, name), encoding="utf-8").read()


def _code(text):
    """The source with its comments taken out (block and line), so a comment's history is not a finding."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)//.*$", "", line) for line in text.splitlines())


def test_no_fixture_words_on_the_review_face():
    for name in ("common.tsx", "Inspector.tsx", "ClusterView.tsx", "Shell.tsx"):
        code = _code(_src(name))
        for phrase in ("demo fixture", "queue fixture", "not in the fixture"):
            assert phrase not in code, f"{name} still shows the researcher '{phrase}'"


def test_pick_another_queue_opens_a_queue_that_exists():
    code = _code(_src("common.tsx"))
    assert "q-12" not in code, "the queue-end view still navigates to the fixture queue q-12"


def test_a_finished_queue_says_done_and_an_empty_one_says_empty():
    code = _code(_src("common.tsx"))
    # the end view is reached through ?state=exhausted on live data: it must name both real ends
    assert "queue-done" in code, "the end view has no 'every item judged' state for a live queue"
    assert "queue-no-items" in code, "a queue with no items says nothing of the kind"


# ── from agent C's site-wide walk (2026-10-19 night), in A's files ──────────

DISCOVERY = os.path.join(PROJECT_ROOT, "webui", "client", "src", "discovery")


def _disc(name):
    return io.open(os.path.join(DISCOVERY, name), encoding="utf-8").read()


def _rule(css, selector):
    m = re.search(r"(^|\n)" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert m, f"no rule for {selector}"
    return m.group(2)


def test_run_rows_keep_their_height_in_a_long_runs_list():
    """With 60 runs the list (a flex column with a max-height) squashed every row to 18 px: names cut, the
    Report button over the name. A row does not shrink; the list scrolls."""
    assert "flex: none" in _rule(_disc("discovery.css"), ".dsc-run")


def test_the_review_toolbar_wraps_at_1024_px():
    """At 1024 px the toolbar did not wrap: the queue picker collapsed under 'machine opinion visible' and
    Shortcuts was clipped."""
    rule = _rule(_src("review.css"), ".rv-toolbar")
    assert "flex-wrap: wrap" in rule and "min-height" in rule and "height: 54px" not in rule.replace("min-height: 54px", "")


def test_an_unknown_queue_is_decided_from_its_own_read():
    """A bad queue id waited 5-14 s behind the whole queue list, then showed a red card flush to the window edge.
    The queue's own read (a 404) decides it, the blind-test page is chosen from that read too, and the red cards sit
    inside the page padding."""
    code = _code(_src("index.tsx"))
    assert "!live && queues.loading" not in code, "the queue route still waits for the queue list"
    assert "status === 404" in code, "a 404 on the queue's own read is not taken as 'no such queue'"
    assert "d.queue.source" in code, "the blind-test page is still chosen off the queue list"
    assert code.count("rv-pad") >= 2, "the queue error cards are not inside the page padding"


def test_the_scoreboard_says_when_it_has_no_rows():
    code = _code(_disc("RunsPage.tsx"))
    assert "scoreboard-empty" in code


def test_an_unknown_run_link_is_an_info_note_not_a_warning():
    code = _code(_disc("RunsPage.tsx"))
    line = next(l for l in code.splitlines() if "run-missing-callout" in l)
    assert 'tone="amber"' not in line and "alert-triangle" not in line


def test_auto_advance_never_moves_a_researcher_who_already_stepped_on():
    """Driven on the scale fixture: I on item A, then two quick arrow presses, landed on the item after A, not two
    on — the auto-advance timer scheduled for A (350 ms, and only after A's POST came back) fired after the
    researcher had moved, and navigated from A. The timer belongs to the item it was set on."""
    # tq-review: the cursor (`cursor.ts`, run under Node by tests/test_tq_review.py) holds the one pending advance
    code = _code(_src("Inspector.tsx"))
    assert "cursor.after(id, " in code, "the delayed advance does not check it is still on its item"
    assert re.search(r"useEffect\(\(\) => \{ cursor\.moveTo\(id\);[^}]*\}, \[cursor, id\]\)", code), \
        "the pending advance is not dropped when the item changes"


def test_stepping_fast_does_not_queue_a_read_for_every_item_passed():
    """Forty arrow presses on the scale fixture left the bridge answering item reads for 25-49 s afterwards (every
    item passed was read, and three neighbours prefetched each time); verdicts pressed meanwhile waited behind them,
    so a key pressed three times wrote the same item three times. An item not yet held is read only once it has
    been on screen for a moment, a superseded read is never sent, and the neighbours are prefetched only from an
    item the researcher stopped on."""
    # tq-review: the item's landing (`cursor.ts`) is the settle, the read and the prefetch chain on one signal, which
    # the read hook aborts when the item changes; tests/test_tq_review.py drives it under Node
    code = _code(_src("Inspector.tsx"))
    assert "useAbortableSourced(" in code and "land(id, signal," in code, "a superseded item read is still sent"
    cursor = _code(_src("cursor.ts"))
    assert "export const STEP_SETTLE_MS = 150" in cursor
    assert "void settled.then(" in cursor and "if (!stayed) return" in cursor, \
        "the neighbours are still prefetched from every item passed"


# ── the critic's three (2026-10-20 01:20) ──────────────────────────────────

def test_undo_and_redo_wait_for_a_write_in_flight():
    """DATA RISK: I on item B on a slow bridge, Ctrl Z inside the round trip, undid A's verdict (B's write joins the
    stack only on its ack) and B's still landed — two rows wrong, the toast naming A. Every commit counts itself in
    flight; undo and redo refuse while one is."""
    # tq-review: the refusal was copied into both pages' undo and redo; `commitUndo`/`commitRedo` now decide it
    # themselves, first, before looking for a write to reverse (the same order and the same text as the copies)
    store = _code(_src("store.ts"))
    for fn in ("commitWrite", "commitUndo", "commitRedo"):
        body = re.search(r"export async function " + fn + r"\(.*?\n}\n", store, re.S).group(0)
        assert "inFlight++" in body and "finally" in body and "inFlight--" in body, f"{fn} is not counted in flight"
        if fn != "commitWrite":
            first = body.splitlines()[1]
            assert "if (inFlight) return { say: BUSY }" in first, f"{fn} does not refuse while a write is in flight"
    assert "const BUSY = 'a verdict is still being written — try again'" in store
    for name in ("Inspector.tsx", "ClusterView.tsx"):
        code = _code(_src(name))
        for fn, commit in (("undo", "commitUndo"), ("redo", "commitRedo")):
            body = re.search(r"const " + fn + r" = async \(\) => \{(.*?)\n  \}", code, re.S).group(1)
            first = body.strip().splitlines()[0]
            assert f"await {commit}(q, " in first, f"{name} {fn} does not go through the store's refusal"


def test_a_class_key_on_a_prior_only_row_writes_instead_of_labelling_the_session():
    """On an explore-spans queue a span marked `seed` is unjudged here but `effective()` returns its prior, so a
    class key took the session-label branch: no write, and the row counted judged. The branches read the JUDGED
    record; the rail, the evidence rail, the cluster batch and the reveal card read it too."""
    queue = _code(_src("queue.ts"))
    assert "export function judgedRecord" in queue
    insp = _code(_src("Inspector.tsx"))
    klass = re.search(r"const klass = async \(ck: string\) => \{(.*?)\n  \}", insp, re.S).group(1)
    assert "if (!jrec)" in klass and "if (!rec)" not in klass
    assert "judged={!!jrec}" in insp
    assert "data.rows[i].baseVerdict" not in insp, "the reveal card still takes a prior verdict for a judged one"
    shell = _code(_src("Shell.tsx"))
    assert shell.count("judgedRecord(records, r)") >= 2 and "const rec = effective(records, r)" not in shell
    cluster = _code(_src("ClusterView.tsx"))
    assert "!judgedRecord(getRecords(), r)" in cluster


def test_the_verdict_flash_belongs_to_its_item():
    # tq-review: the flash is set only when the cursor accepts the advance for this item
    code = _code(_src("Inspector.tsx"))
    assert "const flashes = opts.flash !== false" in code
    assert "cursor.after(id, () => { setFlash(null); if (advances) advance() }) && flashes) setFlash(v)" in code


# ── a span queue read as finished while 622 were left (agent B's drive, Explore → Take span → Open Review) ──

JUDGED_TS = os.path.join(REVIEW, "judged.ts")


def _node_judged(rows):
    import json
    import shutil
    import subprocess
    import pytest
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(JUDGED_TS), "webui/client/src/review/judged.ts does not exist"
    url = "file:///" + JUDGED_TS.replace("\\", "/").lstrip("/")
    script = (f"import * as J from {json.dumps(url)};\n"
              f"process.stdout.write(JSON.stringify({json.dumps(rows)}.map(r => J.rowJudged(r))));\n")
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script], capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_a_row_the_bridge_calls_unjudged_is_unjudged_whatever_verdict_it_carries():
    """An explore-spans queue serves human spans already marked `seed` (`verdict: 'seed'`) that THIS queue has not
    judged (`judged: false`). The client counted any row with a verdict as judged, so the page opened on "No more
    items" while the counter said 622 left. The bridge's flag decides; the verdict is shown as a prefilled prior."""
    # tq-review: the rule reads the bridge's raw row (`rowOf` applies it once, as `QueueRow.judged`)
    got = _node_judged([
        {"verdict": "seed", "judged": False},
        {"verdict": "interesting", "judged": True},
        {"judged": True},
        {"baseVerdict": "interesting"},          # a fixture row with no bridge flag: its verdict says judged
        {},
    ])
    assert got == [False, True, True, True, False]


def test_every_judged_count_in_the_queue_uses_the_one_rule():
    # tq-review: the one rule is applied once, in `rowOf`; every count reads `row.judged`
    code = _code(_src("queue.ts"))
    assert "return row.judged" in code and code.count("(r.judged ? 1 : 0)") == 2
    assert "r.baseVerdict || r.judged" not in code and "!!row.baseVerdict || row.judged" not in code
    api = _code(io.open(os.path.join(PROJECT_ROOT, "webui", "client", "src", "api", "review.ts"), encoding="utf-8").read())
    assert "judged: rowJudged(raw)" in api, "rowOf does not decide judged by the bridge's own flag"
