"""
test_night_review.py
====================
site-night-2026-10-20, REVIEW (the researcher's second list, the eve of the demo).

1. **Review: no noticeable lag between items.** The Inspector kept only three neighbours warm (the next unjudged
   item and one either side), so a researcher who judged or stepped past the next one waited on a cold read
   plus the 150 ms settle; the auto-advance itself waited 350 ms after the write came back. Now the next five
   items ahead (the five unjudged ones an auto-advance can land on, and the very next unit an arrow lands on)
   and the previous one are kept warm, read one at a time nearest first and only from an item the researcher
   stopped on; an item whose read is already in flight is not made to wait the settle; the cache holds the
   whole window; the advance after an accepted verdict is a frame, not a third of a second. A verdict is still
   sent for the item on screen and the advance still waits for the bridge's answer (night-a's rules).
2. **Library: the dendrogram tree on by default when adding a grouping.** The editor opened on the newest
   grouping (on the real database g-09, amplitude bins), which has no tree, so the tree panel was not there at
   all; on a Ward grouping made before trees were kept it was an amber note with a *Build the tree* button.
   The editor now opens on the newest Ward (tree) grouping of the unit unless a basis is named in the address,
   and builds the missing tree at once, drawing it when the job lands.
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
LIBRARY = os.path.join(SRC, "library")


def _read(*parts):
    return io.open(os.path.join(SRC, *parts), encoding="utf-8").read()


def _code(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)//.*$", "", line) for line in text.splitlines())


def _node(module_path, expr_js):
    """Import an import-free TypeScript module under node and print one JSON value."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(module_path), f"{module_path} does not exist"
    url = "file:///" + module_path.replace("\\", "/").lstrip("/")
    script = f"import * as M from {json.dumps(url)};\nprocess.stdout.write(JSON.stringify({expr_js}));\n"
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script], capture_output=True,
                       text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


# ── 1. the prefetch window ───────────────────────────────────────────────────

PREFETCH_TS = os.path.join(REVIEW, "prefetch.ts")


def _window(units, at, judged, ahead=None):
    args = f"{json.dumps(units)}, {at}, i => {json.dumps(judged)}.includes(i)"
    if ahead is not None:
        args += f", {ahead}"
    return _node(PREFETCH_TS, f"M.prefetchIds({args})")


def _items(n):
    return [{"kind": "item", "id": str(100 + i)} for i in range(n)]


def test_the_window_is_the_next_five_unjudged_then_the_previous_one():
    got = _window(_items(20), 5, [])
    assert got == ["106", "107", "108", "109", "110", "104"]


def test_judged_items_ahead_are_passed_over_but_the_next_unit_is_kept():
    # 6 and 7 are judged: auto-advance goes to 8, an arrow goes to 6
    got = _window(_items(20), 5, [6, 7])
    assert got[:5] == ["108", "109", "110", "111", "112"], got
    assert "106" in got and "104" in got
    assert "107" not in got, "a judged item two ahead is neither where I nor an arrow lands"
    assert len(got) == len(set(got))


def test_clusters_are_not_read_as_items_and_the_queue_ends_are_safe():
    units = _items(3) + [{"kind": "cluster", "no": 4, "members": ["a", "b"]}] + _items(2)
    got = _window(units, 2, [])
    assert all(isinstance(x, str) for x in got) and "a" not in got and "b" not in got
    assert _window(_items(3), 2, []) == ["101"], "at the last item only the previous one is left"
    assert _window(_items(3), 0, []) == ["101", "102"]
    assert _window(_items(3), -1, []) == [], "an item not in the list prefetches nothing"


def test_the_window_size_is_a_parameter_and_the_cache_holds_it():
    assert len(_window(_items(40), 0, [], ahead=3)) == 3
    ahead = int(re.search(r"export const PREFETCH_AHEAD = (\d+)", _read("review", "prefetch.ts")).group(1))
    assert ahead == 5
    lru = int(re.search(r"const ITEM_LRU_MAX = (\d+)", _read("api", "review.ts")).group(1))
    # the window (five ahead, the next unit, the previous one), the item on screen, and room for the ones passed
    assert lru >= ahead + 3 + 2, "the item cache would evict the window it was asked to keep"


def test_the_inspector_keeps_the_window_warm_one_read_at_a_time_from_an_item_stopped_on():
    code = _code(_read("review", "Inspector.tsx"))
    assert "prefetchIds(" in code, "the Inspector does not read the five-ahead window"
    # only from an item the researcher stopped on, and the chain stops the moment they move
    m = re.search(r"const t = window\.setTimeout\(async \(\) => \{(.*?)\}, STEP_SETTLE_MS\)\s*"
                  r"return \(\) => \{ live = false; window\.clearTimeout\(t\) \}", code, re.S)
    assert m, "the window is not prefetched from a settle timer that the next item cancels"
    body = m.group(1)
    assert "if (!live) return" in body and "await prefetchItemThen(" in body, \
        "the window's reads are not sent one at a time, nearest first, stopping when the item changes"


def test_an_item_already_being_read_does_not_wait_the_settle():
    code = _code(_read("review", "Inspector.tsx"))
    assert re.search(r"if \(peekItem\(q, id, opts\) \|\| itemHeld\(q, id, opts\)\) return getItem\(q, id, opts\)", code), \
        "an item whose prefetch is in flight still waits 150 ms before joining it (night-a #24)"
    api = _code(_read("api", "review.ts"))
    assert "export function itemHeld(" in api and "export function prefetchItemThen(" in api


def test_the_advance_after_a_verdict_is_a_frame_not_a_third_of_a_second():
    code = _code(_read("review", "Inspector.tsx"))
    ms = int(re.search(r"const ADVANCE_MS = (\d+)", code).group(1))
    assert ms <= 80, f"auto-advance waits {ms} ms after the write was accepted"
    # …and still only after the write was accepted, and only from the item it was given on
    assert "if (opts.advance && auto) later(() => { if (onItem.current === id) advance() }, ADVANCE_MS)" in code
    w = re.search(r"async function write\(.*?\n  \}\n", code, re.S).group(0)
    assert w.index("await commitWrite(") < w.index("advance()"), "the advance no longer waits for the bridge"


# ── 2. the grouping tree by default ──────────────────────────────────────────

TREE_TS = os.path.join(LIBRARY, "treeSource.ts")

G = [
    {"id": "g-04", "unit": "motifs", "basis": "shape-distance", "method": "ward"},
    {"id": "g-05", "unit": "motifs", "basis": "shape-distance", "method": "ward"},
    {"id": "g-06", "unit": "sequences", "basis": "sequence-similarity", "method": "ward"},
    {"id": "g-08", "unit": "sequences", "basis": "shape-distance", "method": "ward"},
    {"id": "g-09", "unit": "motifs", "basis": "amplitude", "method": "feature_bins"},
    {"id": "g-10", "unit": "motifs", "basis": "shape-distance", "method": "hdbscan"},
]


def _source(unit, current_id):
    cur = next((g for g in G if g["id"] == current_id), None)
    r = _node(TREE_TS, f"M.treeSource({json.dumps(G)}, {json.dumps(unit)}, {json.dumps(cur)})")
    return r and r["id"]


def test_the_editor_opens_on_a_tree_grouping_when_the_current_one_has_no_tree():
    assert _source("motifs", "g-09") == "g-05", "the newest Ward grouping of the unit"
    assert _source("motifs", "g-10") == "g-05", "an HDBSCAN grouping builds no tree either"
    assert _source("motifs", "g-04") == "g-04", "a current Ward grouping is kept (from g-04 means g-04)"
    assert _source("sequences", "g-06") == "g-06"
    assert _source("spike-trains", None) is None


def test_the_editor_seeds_from_the_tree_grouping_and_builds_a_missing_tree_at_once():
    code = _code(_read("library", "GroupingPage.tsx"))
    assert "treeSource(" in code, "the editor still opens on the newest grouping, tree or not"
    # an address naming a basis still wins (a feature-bin link opens on its bins)
    assert re.search(r"basisQ[^\n]*treeSource\(|treeSource\([^\n]*basisQ", code), \
        "a ?basis= in the address no longer opens the editor on that basis"
    assert "autoBuild=" in code, "the tree panel is not told to build a missing tree"
    assert 'data-testid="tree-building"' in code, "while the tree is built the panel says nothing"
    panel = re.search(r"function TreePanel\((.*?)\n}\n", code, re.S).group(1)
    assert "autoBuild" in panel and "builtOnce" in panel, "the panel can start more than one build per editor"


def test_a_carry_that_reaches_no_row_of_this_queue_does_not_re_read_every_row():
    """Measured on the scale fixture: every verdict was carried to other runs' detections of the same event, and the
    page then re-read all 8,700 rows (1.6 s, 6 MB) and emptied the item cache, so the next card waited 2.4-4.6 s for
    a cold read behind the re-read. The carried detections were in no row of the queue. Only a carry INTO this
    queue re-reads its rows now; an ack that names no ids re-reads as before."""
    queue = _code(_read("review", "queue.ts"))
    assert "export function queueHoldsAny(" in queue and "carryOf(r).members" in queue
    insp = _code(_read("review", "Inspector.tsx"))
    assert "carriedIds = ack.carriedIds ?? []" in insp
    assert "if (!carriedIds.length || queueHoldsAny(data, carriedIds)) bumpReviewVersion()" in insp


def test_the_automatic_build_is_for_motif_shape_trees_only():
    """On the sandbox walk the automatic build on a sequence grouping (g-06, sequence similarity) failed in the core
    ("tree.tree_key and tree.from_fit disagree"): a red card and a server traceback where a button used to wait.
    Sequences keep the button until that is fixed in the core."""
    code = _code(_read("library", "GroupingPage.tsx"))
    assert re.search(r"autoBuild=\{d\.unit === 'motifs' && d\.basis === 'shape-distance' && ", code)


# ── fix round (the critic, 2026-10-21 00:40) ─────────────────────────────────

def test_f1_the_carry_fields_come_from_the_fresh_row_first():
    """A carry that reached no row of THIS queue no longer empties the item cache, so an item of another queue read
    before the carry came back from the cache without its `carriedFrom`: the carried line vanished. The row (re-read
    on every queue open) wins over the cached detail, and the other queues' cached items are dropped."""
    insp = _code(_read("review", "Inspector.tsx"))
    assert "const carry: CarryFields = { ...carryOf(d?.entry), ...carryOf(row) }" in insp
    assert "clearItemCacheExcept(q)" in insp
    api = _code(_read("api", "review.ts"))
    assert "export function clearItemCacheExcept(" in api


def test_f2_a_grouping_job_is_cancelled_on_every_exit():
    """The automatic build was left running on browser back, a nav link, a hash change, or a close before the job
    id arrived. The hook cancels its live job on unmount and cancels a job whose id arrives after it was abandoned."""
    code = _code(_read("library", "GroupingPage.tsx"))
    hook = re.search(r"function useGroupingJob\(\) \{(.*?)\n}\n", code, re.S).group(1)
    assert "liveJob.current" in hook and "gen.current" in hook
    assert re.search(r"useEffect\(\(\) => \(\) => \{[^\n]*liveJob\.current[^\n]*cancelJob", hook), \
        "unmount does not cancel the live job"
    assert re.search(r"if \(!alive\.current \|\| mine !== gen\.current\) \{ void cancelJob\(j\.job_id\)", hook), \
        "a job abandoned before its id arrived keeps running"


def test_f3_undo_clears_the_pending_advance_and_navigates_from_where_the_researcher_is():
    code = _code(_read("review", "Inspector.tsx"))
    body = re.search(r"const undo = async \(\) => \{(.*?)\n  \}", code, re.S).group(1)
    assert body.index("timers.current.forEach(t => window.clearTimeout(t))") < body.index("await commitUndo(")
    assert "if (onItem.current !== w.items[0]) navigate(" in body


def test_f4_the_detection_index_reads_the_bridge_field():
    queue = _code(_read("review", "queue.ts"))
    assert "detection_id" in queue and "r.detectionId" not in queue
