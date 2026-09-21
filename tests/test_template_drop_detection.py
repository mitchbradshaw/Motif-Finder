"""
test_template_drop_detection.py
=================================
The canonical `drop_detection_v1` template (stage-3 D1): detrend
(rolling_mean_nearest) → five-stage encoding → drop detection, through
`execute_recipe`, reproduces `detect_drops5` on a 30 s synthetic sharkfin
train; and, when the real channel is on disk, reproduces the 17 seed events
of span id001 (the reference span, the only one with an independent human
count) from `DATA/library_seed/drop_motifs5/motifs/events.csv` onset for
onset.

Runnable standalone:  python tests/test_template_drop_detection.py
"""

import csv
import os
import shutil
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "webui")):
    if p not in sys.path:
        sys.path.insert(0, p)

from Working.database import queries as q  # noqa: E402
from Working.database.runs import list_detections  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.Detection.drop_motifs.detect5 import Detect5Params, detect_drops5  # noqa: E402
from Working.execution import execute_recipe  # noqa: E402
from Working.templates import apply_template  # noqa: E402
from server.templates import canonical  # noqa: E402

FS = 10.0
SEED_CSV = os.path.join(PROJECT_ROOT, "DATA", "library_seed", "drop_motifs5", "motifs", "events.csv")
REAL_CHANNEL = os.path.join(PROJECT_ROOT, "DATA", "derived", "channels", "M2_aug_concat_fs1", "CH0.npy")
# span id001 (autoderive_summary.json): recording 1 = M2_aug CH0, hours 336-346
ID001 = dict(offset=1209600, n=36000, detrend_window_s=4916.666666666667, segment_seconds=98.33333333333334,
             same_fraction=0.6, slope_sigma=8.0)


def sharkfin(seconds=30.0, period=10.0, fs=FS, seed=0):
    n = int(seconds * fs)
    t = np.arange(n) / fs
    phase = (t % period) / period
    x = np.where(phase < 0.85, phase / 0.85, 1.0 - (phase - 0.85) / 0.15) * 0.01
    x += 0.00002 * np.random.default_rng(seed).standard_normal(n)
    return x


@pytest.fixture
def scratch():
    tmp = tempfile.mkdtemp(prefix="drop_tpl_")
    import Working.config as cfg
    old = cfg.STEP_CACHE_ROOT
    cfg.STEP_CACHE_ROOT = os.path.join(tmp, "cache")
    try:
        yield tmp
    finally:
        cfg.STEP_CACHE_ROOT = old
        shutil.rmtree(tmp, ignore_errors=True)


def _db(tmp, source_file, npy, fs, n):
    db = os.path.join(tmp, "t.sqlite")
    conn = init_db(db)
    q.insert_recording(conn, source_file, 0, fs, n, 0, npy)
    conn.close()
    return db


def test_drop_detection_v1_is_the_canonical_three_block_chain():
    tpl = canonical("drop_detection_v1")
    assert tpl["kind"] == "detection"
    assert [f"{s['stage']}.{s['algorithm']}" for s in tpl["steps"]] == [
        "preprocessing.detrend", "detection.stage_encoding", "detection.drop_detection"]
    assert tpl["steps"][0]["params"]["mode"] == "rolling_mean_nearest"


def test_template_reproduces_detect_drops5_on_a_synthetic_train(scratch):
    x = sharkfin()
    npy = os.path.join(scratch, "CH0.npy"); np.save(npy, x)
    db = _db(scratch, "synthetic.mat", npy, FS, len(x))
    tpl = canonical("drop_detection_v1")
    tpl["steps"][0]["params"]["window_s"] = 12.0
    tpl["steps"][1]["params"]["segment_seconds"] = 0.5
    out = execute_recipe(apply_template(None, tpl, recording_id=1), db_path=db, force=True)
    ref = detect_drops5(x, FS, Detect5Params(detrend_window_s=12.0, segment_seconds=0.5))
    assert len(ref.events) >= 2
    got = list(zip(out["result"].value.starts, out["result"].value.ends))
    assert got == [(e.window_start_idx, e.window_end_idx) for e in ref.events]
    conn = init_db(db)
    try:
        rows = list_detections(conn, out["run_id"])
    finally:
        conn.close()
    assert [(r["start_idx"], r["end_idx"]) for r in rows] == got


@pytest.mark.skipif(not (os.path.isfile(REAL_CHANNEL) and os.path.isfile(SEED_CSV)),
                    reason="M2_aug CH0 or the seed events are not on this machine")
def test_template_reproduces_the_seed_events_of_span_id001(scratch):
    with open(SEED_CSV, newline="", encoding="utf-8") as f:
        seed = [r for r in csv.DictReader(f) if r["span_key"] == "id001"]
    assert len(seed) == 17
    db = _db(scratch, "M2_aug_concat_fs1.mat", REAL_CHANNEL, 1.0, 2_595_600)
    tpl = canonical("drop_detection_v1")
    tpl["steps"][0]["params"]["window_s"] = ID001["detrend_window_s"]
    tpl["steps"][1]["params"].update(segment_seconds=ID001["segment_seconds"], same_fraction=ID001["same_fraction"],
                                     slope_sigma=ID001["slope_sigma"])
    # drop_motifs5 predates two detect5 fixes (bracket_on_fall_runs, walk_onset_back:
    # "False reproduces drop_motifs5-9" in Detect5Params); the seed is reproduced under
    # the flags it was made with, which the block exposes as parameters.
    tpl["steps"][2]["params"].update(slope_sigma=ID001["slope_sigma"], bracket_on_fall_runs=False, walk_onset_back=False)
    span = (ID001["offset"], ID001["offset"] + ID001["n"])
    out = execute_recipe(apply_template(None, tpl, recording_id=1, span=span), db_path=db, force=True)
    # the executor returns the typed value; the onsets are in the labels
    onsets = [int(l.split(";")[0].split("=")[1]) + ID001["offset"] for l in out["result"].value.labels]
    assert onsets == [int(r["onset_idx"]) for r in seed]
    assert [int(l.split(";")[1].split("=")[1]) + ID001["offset"] for l in out["result"].value.labels] == [int(r["trough_idx"]) for r in seed]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
