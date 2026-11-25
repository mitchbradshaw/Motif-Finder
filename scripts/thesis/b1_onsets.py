"""
b1_onsets.py - the drop detector's own fall onsets and troughs for every run B1 reads, recomputed in memory, read-only.

Why: a ``drop_detection_v1`` detection's ``start_idx`` is the start of the window the detector framed. That start sits
on the stage encoder's 98.33 s segment grid and can come minutes before the fall itself, so intervals measured between
window starts carry up to a segment of grid quantisation plus the window's own padding. The fall's onset (the shoulder
it departs from) and its trough are written only into the detector's span label (``onset=<i>;trough=<j>;<morphology>``,
channel-absolute), and the database does not store labels (``detections.meta_json`` is empty).

So each run is recomputed here from its own configuration, read from the database, on its own channel file, read the
way the executor reads it (``Working.execution._load_signal``: the memory-mapped ``npy_path`` sliced to the span,
``t = arange(start, end) / fs``) and with the recording's declared units. Every recomputed window must match the run's
database rows exactly, start and end, or the script stops: a mismatch means the code has moved since the run, and the
onsets would then not be the run's.

Writes ``docs/thesis/data/ch10_b1/b1_onsets.csv``: one row per detection (run, detection_id, start_idx, end_idx,
onset_idx, trough_idx, morphology), sample indices channel-absolute. Resumable: runs already in the file are skipped.
Nothing is written anywhere else; the database is opened read-only.

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/thesis/b1_onsets.py [run ...]
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))

import b1_intervals as b1  # noqa: E402

OUT = os.path.join(b1.OUT, "b1_onsets.csv")
CHAIN = ["detrend", "stage_encoding", "drop_detection"]
COLS = ["run", "detection_id", "start_idx", "end_idx", "onset_idx", "trough_idx", "morphology"]


def recompute(c, run):
    """The run's detections with the detector's own onset and trough, checked against the database rows."""
    from Adapters.detection_drop_detection import _run as drop
    from Adapters.detection_stage_encoding import _run as encode
    from Adapters.preprocessing_detrend import _run as detrend

    cfg = json.loads(c.execute("SELECT c.config_json FROM runs r JOIN configs c ON c.id = r.config_id WHERE r.id = ?",
                               (run,)).fetchone()[0])
    steps = [s["algorithm"] for s in cfg["steps"]]
    if steps != CHAIN:
        raise ValueError(f"run {run}: unexpected chain {steps}")
    npy, fs, units, span0, span1 = c.execute(
        "SELECT rec.npy_path, rec.fs, rec.units, r.span_start, r.span_end FROM runs r "
        "JOIN recordings rec ON rec.id = r.recording_id WHERE r.id = ?", (run,)).fetchone()
    s0, s1 = (int(v) for v in cfg["span"])
    if (s0, s1) != (int(span0), int(span1)):
        raise ValueError(f"run {run}: config span {s0, s1} is not the run's {span0, span1}")
    fs = float(fs)
    x = np.asarray(np.load(os.path.join(ROOT, npy), mmap_mode="r")[s0:s1])
    t = np.arange(s0, s1) / fs
    p = [s["params"] for s in cfg["steps"]]
    xd = detrend(x, t, fs, **p[0]).value.x
    enc = encode(xd, t, fs, **p[1])
    res = drop(xd, t, fs, value=enc.value, units=units or "V", **p[2]).value
    rc = pd.DataFrame({"start_idx": np.asarray(res.starts, int) + s0, "end_idx": np.asarray(res.ends, int) + s0,
                       "label": list(res.labels), "score": np.asarray(res.scores, float)})
    db = pd.read_sql("SELECT id AS detection_id, start_idx, end_idx, score AS score_db FROM detections WHERE run_id = ?",
                     c, params=(run,))
    # A run can hold two detections with the same window (two falls bracketed by one span): pair them up by depth.
    rc = rc.sort_values(["start_idx", "end_idx", "score"]).reset_index(drop=True)
    db = db.sort_values(["start_idx", "end_idx", "score_db"]).reset_index(drop=True)
    for d in (rc, db):
        d["k"] = d.groupby(["start_idx", "end_idx"]).cumcount()
    m = db.merge(rc, on=["start_idx", "end_idx", "k"], how="outer", indicator=True, validate="one_to_one")
    if len(rc) != len(db) or not (m["_merge"] == "both").all():
        raise ValueError(f"run {run}: recomputed {len(rc)} windows do not match the {len(db)} database rows")
    if not np.allclose(m["score"], m["score_db"], rtol=1e-6, atol=1e-9):
        raise ValueError(f"run {run}: recomputed depths do not match the database scores")
    lab = m["label"].str.extract(r"onset=(\d+);trough=(\d+);(\w+)")
    m["onset_idx"] = lab[0].astype(int)
    m["trough_idx"] = lab[1].astype(int)
    m["morphology"] = lab[2]
    m["run"] = run
    if not ((m["onset_idx"] >= m["start_idx"]) & (m["trough_idx"] > m["onset_idx"])
            & (m["trough_idx"] <= m["end_idx"])).all():
        raise ValueError(f"run {run}: an onset or trough falls outside its window")
    return m[COLS].sort_values("onset_idx")


def main(only=None):
    db = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    runs = b1.channel_runs(c)
    todo = [int(r) for r in runs["run"]] if not only else [int(r) for r in only]
    done = set(pd.read_csv(OUT)["run"].astype(int)) if os.path.exists(OUT) else set()
    for k, run in enumerate(todo, 1):
        if run in done:
            continue
        t0 = time.time()
        rows = recompute(c, run)
        lead = (rows["onset_idx"] - rows["start_idx"])
        rows.to_csv(OUT, mode="a", header=not os.path.exists(OUT), index=False)
        print(f"[{k}/{len(todo)}] run {run}: {len(rows)} windows match the database; the onset is a median "
              f"{lead.median() if len(rows) else 0:.0f} samples after the window start (max "
              f"{lead.max() if len(rows) else 0}); {time.time() - t0:.1f} s", flush=True)
    c.close()


if __name__ == "__main__":
    main(sys.argv[1:])
