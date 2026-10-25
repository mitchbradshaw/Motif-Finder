"""
test_webui_site_map_order.py
============================
site-map (2026-10-20), items 3 and 4: Discovery › Map's rows and columns can be hidden, sorted and clustered at
every level. The ordering is a pure helper, `webui/client/src/discovery/mapOrder.ts` (no imports, run here under
Node's type stripping; skips without `node`):

* ``clusterOrder(vectors)`` — average-linkage hierarchical clustering on correlation distance, the dendrogram's
  leaf order; deterministic, no NaN from a flat vector;
* ``arrange(items, mode, hidden, pinned)`` — ``{shown, hidden}``: the shown ITEMS (tq-mappage, 2026-10-25: the
  items themselves, so the page needs no key→object lookup) in the mode's order (``listed`` ·
  ``name`` · ``count`` · ``cluster``), the pinned key (the human row) first in every mode, the hidden keys after
  them in their listed order (the researcher, 2026-10-20: hidden rows sink to the bottom, hidden columns to the
  right); restoring a hidden key puts it back where the current order places it, not at the end;
* ``toggleKey(csv, key)`` / ``splitKeys(csv)`` — the URL's ``hide=`` / ``hidecols=`` lists.

The page's use of them is pinned by source checks at the bottom. tq-mappage (2026-10-25): the page is split into
``discovery/map/`` (one module per level, the hide/sort helpers written once), so the source checks read
``MapPage.tsx`` plus every file under ``discovery/map/``.
"""
import io
import json
import os
import shutil
import subprocess

import re

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(PROJECT_ROOT, "webui", "client", "src", "discovery")
ORDER_TS = os.path.join(SRC, "mapOrder.ts")


def _run(body):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert os.path.isfile(ORDER_TS), "webui/client/src/discovery/mapOrder.ts does not exist"
    url = "file:///" + ORDER_TS.replace("\\", "/").lstrip("/")
    script = (f"import * as M from {json.dumps(url)};\n"
              f"const out = (() => {{ {body} }})();\n"
              "process.stdout.write(JSON.stringify(out));\n")
    r = subprocess.run([node, "--no-warnings", "--input-type=module", "-e", script], capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


KEYS = "const keys = r => ({ shown: r.shown.map(x => x.key), hidden: r.hidden.map(x => x.key) });"


def _items(spec):
    return json.dumps([{"key": k, "label": l, "values": v, "count": n} for k, l, v, n in spec])


def test_cluster_order_puts_similar_profiles_side_by_side():
    got = _run("return M.clusterOrder([[1,0,1,0],[0,1,0,1],[2,0,2.1,0],[0,2,0,2.2],[1,0,1.1,0.1]])")
    assert sorted(got) == [0, 1, 2, 3, 4]
    pos = {v: i for i, v in enumerate(got)}
    a = sorted(pos[i] for i in (0, 2, 4))
    b = sorted(pos[i] for i in (1, 3))
    assert a == list(range(a[0], a[0] + 3)) and b == list(range(b[0], b[0] + 2)), got


def test_cluster_order_survives_flat_and_empty_vectors():
    assert _run("return M.clusterOrder([[0,0,0],[1,1,1],[1,2,3]])") is not None
    assert _run("return M.clusterOrder([])") == []
    assert _run("return M.clusterOrder([[3]])") == [0]
    d = _run("return [M.correlationDistance([1,1,1],[1,2,3]), M.correlationDistance([1,2,3],[2,4,6]), "
             "M.correlationDistance([1,2,3],[3,2,1])]")
    assert all(isinstance(x, (int, float)) for x in d)
    assert abs(d[1]) < 1e-9 and abs(d[2] - 2) < 1e-9


ITEMS = _items([
    ("human", "human", [1, 0, 1], 5),
    ("b", "beta", [0, 5, 0], 50),
    ("a", "alpha 10", [5, 0, 5], 10),
    ("c", "alpha 9", [4, 0, 4], 90),
    ("d", "delta", [0, 4, 1], 1),
])


def test_each_mode_orders_the_shown_keys_with_the_pinned_one_first():
    got = _run(f"{KEYS} const it = {ITEMS}; return ['listed','name','count','cluster'].map(m => "
               f"keys(M.arrange(it, m, new Set(), 'human')))")
    listed, name, count, cluster = got
    assert listed == {"shown": ["human", "b", "a", "c", "d"], "hidden": []}
    assert name["shown"] == ["human", "c", "a", "b", "d"], "names compare numerically: alpha 9 before alpha 10"
    assert count["shown"] == ["human", "c", "b", "a", "d"], "most detections first"
    assert cluster["shown"][0] == "human"
    pos = {k: i for i, k in enumerate(cluster["shown"])}
    assert abs(pos["a"] - pos["c"]) == 1 and abs(pos["b"] - pos["d"]) == 1, cluster


def test_hidden_keys_sink_below_the_shown_ones_in_their_listed_order():
    got = _run(f"{KEYS} return keys(M.arrange({ITEMS}, 'count', new Set(['d', 'b', 'human']), 'human'))")
    assert got == {"shown": ["c", "a"], "hidden": ["human", "b", "d"]}


def test_restoring_a_key_puts_it_back_where_the_current_order_places_it():
    got = _run(f"{KEYS} const it = {ITEMS}; return [keys(M.arrange(it, 'name', new Set(['a']), 'human')), "
               f"keys(M.arrange(it, 'name', new Set(), 'human'))]")
    assert got[0]["shown"] == ["human", "c", "b", "d"]
    assert got[1]["shown"] == ["human", "c", "a", "b", "d"], "back in its name position, not appended"


def test_cluster_reads_only_the_values_it_is_given():
    # the page passes each row's values over the SHOWN columns only; a hidden row is not clustered at all
    got = _run(f"{KEYS} return keys(M.arrange({ITEMS}, 'cluster', new Set(['c']), 'human'))")
    assert got["hidden"] == ["c"] and "c" not in got["shown"]


def test_arrange_hands_back_the_items_themselves():
    # tq-mappage: the page passes its own rows / channels (with key, label, values, count) and draws what comes back
    got = _run(f"const it = {ITEMS}.map(x => ({{ ...x, extra: x.key + '!' }})); "
               f"const r = M.arrange(it, 'name', new Set(['b']), 'human'); "
               f"return [r.shown.every(x => it.includes(x)), r.hidden.every(x => it.includes(x)), r.hidden[0].extra]")
    assert got == [True, True, "b!"]


def test_the_url_lists():
    got = _run("return [M.splitKeys(''), M.splitKeys('a,b'), M.toggleKey('', 'x'), M.toggleKey('a,x', 'x'), "
               "M.toggleKey('a', 'b'), M.toggleKey('x', 'x')]")
    assert got == [[], ["a", "b"], "x", "a", "a,b", None]


# ── the page uses them ──────────────────────────────────────────────────────

MAP_DIR = os.path.join(SRC, "map")


def _map_file(name):
    return io.open(os.path.join(MAP_DIR, name), encoding="utf-8").read()


def _page():
    """MapPage.tsx (the route entry) and every module of the map under discovery/map/."""
    assert os.path.isdir(MAP_DIR), "the map's modules live under webui/client/src/discovery/map/"
    parts = [io.open(os.path.join(SRC, "MapPage.tsx"), encoding="utf-8").read()]
    for name in sorted(os.listdir(MAP_DIR)):
        if name.endswith((".ts", ".tsx")):
            parts.append(_map_file(name))
    return "\n".join(parts)


def test_the_page_keeps_the_view_in_the_url():
    src = _page()
    for key in ("hide", "hidecols", "rsort", "csort", "signal"):
        assert f"useQueryState('{key}'" in src or f"useQueryState<SortMode>('{key}'" in src, \
            f"MapPage reads {key} from the URL"
    assert re.search(r"from '(\./|\.\./)mapOrder'", src), "the page orders through mapOrder.ts"


def test_the_page_draws_hidden_rows_and_columns_with_a_restore_button():
    src = _page()
    for testid in ("map-row-hide-", "map-row-show-", "map-col-hide-", "map-col-show-", "map-hidden-line",
                   "map-show-all", "map-rsort", "map-csort", "map-signal"):
        assert testid in src, f"MapPage draws {testid}"


def test_the_page_spreads_no_array_into_math_min_or_max():
    # night (2026-10-20): `Math.max(...xs)` over ~10^5 values is a RangeError; charts/domain's extentOf / maxOf loop instead
    src = _page()
    assert "Math.min(...finite)" not in src and "Math.max(...finite)" not in src
    assert "...cell.counts)" not in src
    assert re.search(r"from '(\.\./)+charts/domain'", src)


def test_the_dataset_level_marks_a_stale_answer_on_its_wrap():
    src = _page()
    assert "data-testid=\"map-dataset-level\" data-stale={m.loading || data.stale ? '1' : '0'}" in src


# ── tq-mappage (2026-10-25): the hide/sort code written once, the signal read lifted ────────────────────────

def test_the_hide_sort_code_is_written_once():
    src = _page()
    assert "byId.get(" not in src and "by.get(k)!" not in src, "arrange hands back items: no key→object round trip"
    assert src.count("function arrangeColumns") == 1 and src.count("arrangeColumns(") >= 3, \
        "level 3 and level 2 order their columns through one helper"
    assert src.count("function orderRows") == 1
    hs = _map_file("hideSort.tsx")
    for name in ("export function arrangeColumns", "export function orderRows", "export function HideableHeader",
                 "export function HideButton"):
        assert name in hs, f"hideSort.tsx owns {name}"
    assert "<HideableHeader" in _map_file("DatasetsLevel.tsx") and "<HideableHeader" in _map_file("DatasetLevel.tsx")


def test_the_signal_strip_is_presentational():
    src = _page()
    assert "'__signal'" not in src, "hover is typed, no sentinel row key"
    assert "onRange" not in src and "setRange" not in src, "the strip pushes no closure up"
    strip = _map_file("SignalStrip.tsx")
    assert "export function useSignal" in strip
    assert "getOverview" not in strip.split("export function SignalStrip", 1)[1], "the strip draws; the hook reads"
    channel = _map_file("ChannelLevel.tsx")
    assert "useSignal(" in channel and "kind: 'signal'" in channel and "extentOf(" in channel
    for state in ("failed", "refused", "loading", "empty", "drawn"):
        assert f'data-state="{state}"' in strip, f"the strip still draws its {state} state"
