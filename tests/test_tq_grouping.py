"""
test_tq_grouping.py
===================
tq-grouping (2026-10-25): the Grouping editor split back under 1000 lines, with one job lifecycle.

`library/GroupingPage.tsx` had grown to 1013 lines holding four concerns: the pure draft model, the job hook, the
editor with its tree panel, and the parameter widgets. It also shadowed the app's one extent rule
(`charts/domain.ts::extentOf`) with a private `extentOf` of a different meaning, and `library/treeSource.ts`
re-declared the distance bases, the `g-NN` number and the newest-grouping pick that the page and `chrome.tsx`
already own. These tests pin the new seams:

- `library/groupingDraft.ts` is pure and runs under Node: the draft rules and `isTreeGrouping` (Ward on a distance
  basis), the one tree test the editor and its tree panel share;
- the editor picks its tree grouping with chrome's `newestGrouping`, and `treeSource.ts` is gone;
- `library/useGroupingJob.ts` cancels through one AbortController per start: no `alive`, `gen` or `liveJob`;
- the auto-build is decided in the editor with an `autoBuilt` state, not a `builtOnce` ref behind an `autoBuild` prop.
"""
import io
import json
import os
import re
import shutil
import subprocess

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBRARY = os.path.join(PROJECT_ROOT, "webui", "client", "src", "library")
DRAFT_TS = os.path.join(LIBRARY, "groupingDraft.ts")


def _read(name):
    return io.open(os.path.join(LIBRARY, name), encoding="utf-8").read()


def _code(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)//.*$", "", line) for line in text.splitlines())


def _node(expr_js):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(DRAFT_TS), f"{DRAFT_TS} does not exist"
    url = "file:///" + DRAFT_TS.replace("\\", "/").lstrip("/")
    script = f"import * as M from {json.dumps(url)};\nprocess.stdout.write(JSON.stringify({expr_js}));\n"
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script], capture_output=True,
                       text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


G = [
    {"id": "g-04", "unit": "motifs", "basis": "shape-distance", "method": "ward"},
    {"id": "g-06", "unit": "sequences", "basis": "sequence-similarity", "method": "ward"},
    {"id": "g-07", "unit": "motifs", "basis": "shape-distance"},
    {"id": "g-09", "unit": "motifs", "basis": "amplitude", "method": "feature_bins"},
    {"id": "g-10", "unit": "motifs", "basis": "shape-distance", "method": "hdbscan"},
]


def test_the_draft_model_is_pure_and_names_the_tree_groupings():
    got = _node(f"{json.dumps(G)}.map(g => M.isTreeGrouping(g))")
    assert got == [True, True, True, False, False], "Ward on a distance basis (no method = Ward) is a tree grouping"
    assert _node("[M.isTreeGrouping(null), M.isTreeGrouping(undefined)]") == [False, False]
    assert _node("M.DISTANCE_BASES") == ["shape-distance", "sequence-similarity"]
    assert _node("[M.methodOf({basis: 'amplitude', method: 'kshape'}), M.methodOf({basis: 'shape-distance', method: ''})]") \
        == ["feature_bins", "ward"]
    assert _node("M.binExtent([{lo: 1, hi: 2, n: 3}, {lo: 2, hi: 5, n: 1}])") == [1, 5]
    assert _node("M.binExtent([])") is None
    seed = _node("M.seedFromGrouping({id: 'g-02', unit: 'motifs', basis: 'shape-distance', method: 'ward', cut: 0.6,"
                 " params: 'cut 0.6 · min_group 12 · omit_d 0.4'})")
    assert seed == {"basis": "shape-distance", "cut": 0.6, "nearest": 0.4, "minMembers": 12, "omitSmall": True}


def test_the_editor_is_split_and_tree_source_is_gone():
    assert not os.path.exists(os.path.join(LIBRARY, "treeSource.ts")), "treeSource.ts re-declares the page's rules"
    for f in ("groupingDraft.ts", "useGroupingJob.ts", "TreePanel.tsx", "GroupingParams.tsx"):
        assert os.path.isfile(os.path.join(LIBRARY, f)), f"{f} was not split out"
    n = len(_read("GroupingPage.tsx").splitlines())
    assert n < 600, f"GroupingPage.tsx is {n} lines"
    page = _code(_read("GroupingPage.tsx"))
    assert "newestGrouping(all.filter(isTreeGrouping)" in page, "the tree pick is chrome's newest-grouping rule"
    assert "as Grouping & {" not in page, "Grouping declares method / recipeHash / treeKey: no casts"
    assert "as Grouping & {" not in _code(_read("groupingDraft.ts"))
    for f in ("GroupingPage.tsx", "groupingDraft.ts", "GroupingParams.tsx", "TreePanel.tsx"):
        assert "function extentOf(" not in _read(f), f"{f} shadows charts/domain.ts::extentOf"


def test_one_abort_controller_per_start_cancels_the_grouping_job():
    hook = _code(_read("useGroupingJob.ts"))
    assert "new AbortController()" in hook
    for gone in ("alive.current", "gen.current", "liveJob"):
        assert gone not in hook, f"{gone} is a second record of the same cancellation"
    assert re.search(r"if \(signal\.aborted\) \{ void cancelJob\(", hook), \
        "a job id that arrives after its controller was aborted keeps running"
    assert re.search(r"useEffect\(\(\) => abort, \[\]\)", hook), "unmount does not abort the live job"


def test_the_editor_decides_the_auto_build_once():
    page = _code(_read("GroupingPage.tsx"))
    panel = _code(_read("TreePanel.tsx"))
    assert "autoBuild=" not in page and "autoBuild" not in panel and "builtOnce" not in panel
    assert re.search(r"const \[autoBuilt, setAutoBuilt\] = useState\(false\)", page)
    assert "useGroupingTree(" in page and "export function useGroupingTree(" in panel
    assert "building={" in page
