"""
test_webui_corpus.py
====================
Core pins re-homed onto the web bridge's service modules after the Panel tree
was retired (tag `archive/panel-ui`, 2026-09-21). Each of these guarded a
behaviour that the bridge copied verbatim from `UI/plots.py` or that the old
viewer tests asserted against the shared vocabulary; without them the copy
would be the only reader of every `.npy` in `DATA/` with no test at all.

* the channel memory-map is opened once per file and re-opened when the file
  changes (cache keyed on `(path, mtime_ns)`, never the path alone);
* the y-extent equals a full scan, is memoised, and follows the same key;
* the verdict vocabulary the bridge serves IS `Working.database.schema.VERDICTS`,
  not a second copy;
* the persisted symbol-letter form (`motifs.sax_string`) rolls past `z` as
  `aa`, `ab`, ... byte-for-byte as before;
* a `step_artifacts` row whose directory is gone reads as *not cached*.

Windows refuses to overwrite a file that is memory-mapped — which is exactly
why the Panel-era versions of the first two invalidation tests were permanent
`WinError 32` failures. They now pin the *mechanism* (a new mtime is a new
cache key) by touching the mtime instead of rewriting the bytes. No FastAPI.
"""

import gc
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from Adapters.registry import discover_adapters  # noqa: E402
from Working.database.runs import insert_step_artifact  # noqa: E402
from Working.database.schema import VERDICTS as SCHEMA_VERDICTS, init_db  # noqa: E402
from Working.execution import _recipe_prefix_hash  # noqa: E402
from server import chain, corpus, serialize  # noqa: E402

discover_adapters()


@pytest.fixture(autouse=True)
def _release_mmaps():
    """Drop every cached memory-map before the temp files are cleaned up."""
    yield
    corpus._yrange.cache_clear()
    corpus._mmap.cache_clear()
    gc.collect()


def _npy(tmp_path, values, name="ch.npy"):
    path = str(tmp_path / name)
    np.save(path, np.asarray(values, dtype=np.float64))
    return path


def _bump_mtime(path, seconds=2):
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + seconds * 1_000_000_000))


# ── the channel file is opened once, and re-opened when it changes ────────

def test_channel_mmap_is_reused_for_the_same_file(tmp_path):
    path = _npy(tmp_path, np.arange(100.0))
    a = corpus.load_native(path)
    b = corpus.load_native(path)
    assert a is b, "the same channel file was memory-mapped twice"
    assert float(a[7]) == 7.0


def test_channel_mmap_is_invalidated_when_the_file_changes(tmp_path):
    """A re-materialised channel must not keep serving the old array.

    `Working/` can rewrite a channel `.npy` (re-import, re-materialise). A
    cache keyed on the path alone would hand the page stale data with no way
    to notice, which is a far worse bug than the slowness the cache fixes.
    """
    path = _npy(tmp_path, np.arange(100.0))
    first = corpus.load_native(path)
    misses = corpus._mmap.cache_info().misses
    _bump_mtime(path)
    second = corpus.load_native(path)
    assert second is not first, "stale mmap served after the file changed"
    assert corpus._mmap.cache_info().misses == misses + 1


def test_channel_extent_matches_a_full_scan_and_is_cached(tmp_path):
    path = _npy(tmp_path, [-3.0, 0.0, 7.5, 2.0])
    rec = {"npy_path": path}
    assert corpus.y_range(rec) == [-3.0, 7.5]
    misses = corpus._yrange.cache_info().misses
    assert corpus.y_range(rec) == [-3.0, 7.5]
    assert corpus._yrange.cache_info().misses == misses, "the extent was rescanned"


def test_channel_extent_is_invalidated_when_the_file_changes(tmp_path):
    path = _npy(tmp_path, [0.0, 1.0])
    rec = {"npy_path": path}
    assert corpus.y_range(rec) == [0.0, 1.0]
    misses = corpus._yrange.cache_info().misses
    _bump_mtime(path)
    corpus.y_range(rec)
    assert corpus._yrange.cache_info().misses == misses + 1, "stale extent served after the file changed"


def test_channel_extent_ignores_nans(tmp_path):
    """A matrix-profile score channel carries a NaN tail; the extent must not
    collapse to NaN because of it."""
    path = _npy(tmp_path, [np.nan, -1.0, 4.0, np.nan])
    assert corpus.y_range({"npy_path": path}) == [-1.0, 4.0]


# ── the verdict vocabulary is the schema's, not a copy ────────────────────

def test_bridge_verdicts_are_the_shared_schema_vocabulary():
    """Extending `Working.database.schema.VERDICTS` must extend what the pages
    offer by itself; a second tuple in the bridge is the drift the two deleted
    viewer tests existed to prevent."""
    assert corpus.VERDICTS == SCHEMA_VERDICTS
    assert corpus.VERDICTS is SCHEMA_VERDICTS
    assert len(SCHEMA_VERDICTS) == 5 and SCHEMA_VERDICTS[0] == "seed"


# ── the persisted symbol string keeps its byte-identical letter form ──────

def test_symbol_letters_roll_past_z_exactly_as_persisted_strings_do():
    """cSAX/pSAX strings are already on disk and in `motifs.sax_string`;
    changing the letter form would invalidate stored data."""
    fixed = [0, 0, 1, 2, 2, 2, 1, 0, 25, 26, 27]
    assert "".join(serialize._letter(s) for s in fixed) == "aabcccbazaaab"
    assert [serialize._letter(i) for i in (25, 26, 27, 51, 52)] == ["z", "aa", "ab", "az", "ba"]


# ── a cache row whose directory is gone is not a cached step ──────────────

def test_cache_status_reports_a_row_whose_directory_is_missing_as_not_cached(tmp_path):
    conn = init_db(":memory:")
    try:
        recipe = chain.build_recipe(1, (0, 100), [{"stage": "preprocessing", "algorithm": "lowpass"}])
        step0_hash = _recipe_prefix_hash(recipe, 0)
        insert_step_artifact(conn, step0_hash, 0, str(tmp_path / "cache" / "missing"))

        status = chain.cache_status(recipe, conn)
        assert status[0]["prefix_hash"] == step0_hash
        assert status[0]["cached"] is False, "a row pointing at a deleted directory is stale, not cached"

        present = tmp_path / "cache" / "present"
        present.mkdir(parents=True)
        insert_step_artifact(conn, step0_hash, 0, str(present))
        assert chain.cache_status(recipe, conn)[0]["cached"] is True
    finally:
        conn.close()


# ── `both` is a sum, and is named as one (fixup-a item 16) ──────────────────

def _corpus_db(tmp_path):
    """Two channels of one file, with annotations and detections that overlap
    on purpose, so a sum and an intersection give different numbers."""
    from Working.database import queries as q
    from Working.database import runs as R
    db = str(tmp_path / "cov.sqlite")
    conn = init_db(db)
    ids = [q.insert_recording(conn, "F.mat", ch, 1.0, 1000, 0, _npy(tmp_path, np.zeros(1000), f"c{ch}.npy"))
           for ch in (0, 1)]
    cfg, _ = R.get_or_create_config(conn, {"recording_id": ids[0], "span": [0, 1000],
                                           "steps": [{"stage": "detection", "algorithm": "threshold", "params": {}}]})
    run = R.insert_run(conn, cfg, ids[0], 0, 1000)
    for a, b in ((100, 200), (300, 400), (700, 800)):
        q.insert_annotation(conn, ids[0], a, b, "interesting", "manual_ui")
    for a, b, sc in ((150, 250, 0.9), (320, 380, 0.8)):
        R.insert_detection(conn, run, a, b, score=sc)
    return conn


def test_both_is_the_sum_of_the_two_layers_not_their_intersection(tmp_path):
    """The map colours by total activity and `both` is `annotations + detections`
    per bin. The label was the lie, not the number - so this pins the number, in
    case a later reading of the word "both" tries to make it an intersection."""
    conn = _corpus_db(tmp_path)
    try:
        cov = corpus.coverage(conn, "F.mat", bins=10)
    finally:
        conn.close()
    row = cov["rows"][0]
    assert row["both"] == [a + d for a, d in zip(row["annotations"], row["detections"])]
    assert sum(row["both"]) == sum(row["annotations"]) + sum(row["detections"])
    assert sum(row["both"]) > 0, "the fixture must put something in both layers"
    doc = corpus.coverage.__doc__.lower()
    assert "sum" in doc and "not the bins where" in doc, "the docstring made the same claim the label did"


def test_the_run_filter_reaches_the_detection_layers(tmp_path):
    """fixup-a item 15: the Corpus page fetches `coverage?run=` now, so an
    unmatched run id must empty the detection layers rather than being ignored."""
    conn = _corpus_db(tmp_path)
    try:
        everything = corpus.coverage(conn, "F.mat", bins=10)
        nothing = corpus.coverage(conn, "F.mat", bins=10, run_ids=[-1])
    finally:
        conn.close()
    assert sum(everything["rows"][0]["detections"]) > 0
    assert sum(nothing["rows"][0]["detections"]) == 0, "run=-1 matches no run: the layer is empty, not unfiltered"
    assert nothing["run_filter"] == []
    assert sum(nothing["rows"][0]["annotations"]) == sum(everything["rows"][0]["annotations"]),         "the run filter restricts DETECTIONS only"
