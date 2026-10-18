"""
perf_fixture.py
===============
AR, the speed pass: a database the size the real one is heading for, built in
seconds so the speed tests and `scripts/perf_routes.py` can stand on it.

Not a test module (no ``test_`` prefix): the speed tests import `build` and
call it at the size they need, and ``python tests/perf_fixture.py <out.sqlite>``
builds the full one for the timing harness.

What the full build holds (the real database on 2026-10-18 x 1, the prompt's
table): one recording file of 16 channels x 721 h at 1 Hz; 60 Discovery runs
of 16 channels each (960 `runs` rows, each Discovery run its own run group, a
few paired surrogates); 5,000,000 detections spread over those runs with a
heavy tail (a few runs of 60k, most a few thousand); 12,000 annotations;
reviewed spans; 70 detection templates, each the template of one Discovery run;
a review queue of 10,000 detections (an exact detection set, as Discovery's
*Send picked* makes); 700 adjudications. Channel `.npy` files are a float32
trace per channel at full length: their content does not matter for timing,
their length does (the item card reads a window of one).

Everything is a plain `init_db()` database with plain SQL inserts: no adapter
runs, nothing under `DATA/`.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db  # noqa: E402

SOURCE_FILE = "SCALE_concat_fs1.mat"
NOW = "2026-10-18T09:00:00+00:00"
RECIPE = {"steps": [{"stage": "detection", "algorithm": "drop_detection", "params": {}}]}
VERDICTS = ("interesting", "not_interesting", "seed", "artifact", "unsure")

FULL = dict(n_channels=16, hours=721.0, n_druns=60, n_detections=5_000_000, n_annotations=12_000,
            n_templates=70, queue_size=10_000, n_adjudications=700, n_reviewed=1_600)


def channel_names(n):
    from Working.discovery.channels import channel_name
    return [channel_name(SOURCE_FILE, ch, n) for ch in range(n)]


def build(path, *, n_channels=16, hours=721.0, n_druns=60, n_detections=5_000_000, n_annotations=12_000,
          n_templates=70, queue_size=10_000, n_adjudications=700, n_reviewed=1_600, npy_dir=None,
          seed=20261018, write_npy=True):
    """Build the database at `path` (overwritten) and return what it holds:
    ``{"db", "recordings", "druns": [{"key", "run_ids", "template"}], "queue_id",
    "queue_ids" (the queue's detection ids, in order), "session_id",
    "n_detections", "build_s"}``."""
    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)
    if os.path.exists(path):
        os.remove(path)
    npy_dir = npy_dir or os.path.join(os.path.dirname(os.path.abspath(path)), "npy")
    os.makedirs(npy_dir, exist_ok=True)
    n_samples = int(round(hours * 3600))
    conn = init_db(path)
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA journal_mode = MEMORY")

    # ── recordings: one file, n_channels channels, at full length ──────────
    rec_ids = []
    for ch in range(n_channels):
        npy = os.path.join(npy_dir, f"scale_ch{ch:02d}.npy")
        if write_npy and not os.path.isfile(npy):
            x = np.cumsum(rng.standard_normal(n_samples).astype(np.float32)) * np.float32(0.01)
            np.save(npy, x.astype(np.float32))
        rec_ids.append(conn.execute(
            "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, units) "
            "VALUES (?, ?, 1.0, ?, 0, ?, 'mV')", (SOURCE_FILE, ch, n_samples, npy)).lastrowid)
    names = channel_names(n_channels)

    cfg = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES ('scale-cfg', ?, ?)",
                       (json.dumps(RECIPE, sort_keys=True), NOW)).lastrowid

    # ── templates: the detection kind, each named after one Discovery run ──
    tnames = [f"scale_template_{i:02d}" for i in range(n_templates)]
    conn.executemany(
        "INSERT INTO templates (name, steps_json, kind, version, builtin, description, created_at, updated_at) "
        "VALUES (?, ?, 'detection', 1, 0, 'scale fixture', ?, ?)",
        [(n, json.dumps(RECIPE["steps"]), NOW, NOW) for n in tnames])

    # ── the session and its Discovery runs ─────────────────────────────────
    sid = conn.execute(
        "INSERT INTO discovery_sessions (name, source_file, channels_json, span_start, span_end, null_json, "
        "created_at, updated_at) VALUES ('scale screen', ?, ?, 0, ?, NULL, ?, ?)",
        (SOURCE_FILE, json.dumps(names), n_samples, NOW, NOW)).lastrowid

    # detections per run: a heavy tail, summing to n_detections
    n_runs = n_druns * n_channels
    weights = rng.pareto(1.2, n_runs) + 0.2
    per_run = np.floor(weights / weights.sum() * n_detections).astype(np.int64)
    per_run = np.minimum(per_run, 80_000)
    short = n_detections - int(per_run.sum())
    if short > 0:
        per_run += short // n_runs
        per_run[: short % n_runs] += 1

    druns, run_rows, k = [], [], 0
    for d in range(n_druns):
        gid = conn.execute("INSERT INTO run_groups (created_at) VALUES (?)", (NOW,)).lastrowid
        ids = []
        for ch in range(n_channels):
            rid = conn.execute(
                "INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, finished_at, "
                "run_group_id) VALUES (?, ?, 0, ?, ?, 'completed', ?, ?)",
                (cfg, rec_ids[ch], n_samples, NOW, NOW, gid)).lastrowid
            ids.append(rid)
            run_rows.append((rid, int(per_run[k])))
            k += 1
        if d % 10 == 0:          # a paired surrogate on the first channel of every tenth run
            sur = conn.execute(
                "INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, finished_at, "
                "run_group_id, surrogate_of_run_id) VALUES (?, ?, 0, ?, ?, 'completed', ?, ?, ?)",
                (cfg, rec_ids[0], n_samples, NOW, NOW, gid, ids[0])).lastrowid
            run_rows.append((sur, 200))
        key = f"scale_{d:02d}"
        tname = tnames[d % n_templates] if n_templates else None
        conn.execute(
            "INSERT INTO discovery_runs (session_id, run_key, kind, label, colour, template_name, run_group_id, "
            "params_json, status, created_at, updated_at) VALUES (?, ?, 'template', ?, '#0a84ff', ?, ?, ?, 'done', ?, ?)",
            (sid, key, key, tname, gid, json.dumps({"run_ids": ids, "stage_count": 1}), NOW, NOW))
        druns.append({"key": key, "run_ids": ids, "template": tname, "run_group_id": gid})

    # ── detections: bulk, sorted by onset within each run ─────────────────
    rid_col = np.repeat(np.array([r for r, n in run_rows], dtype=np.int64),
                        np.array([max(0, n) for r, n in run_rows], dtype=np.int64))
    starts = rng.integers(0, max(1, n_samples - 700), len(rid_col))
    order = np.lexsort((starts, rid_col))            # by run, then by onset: the order a sweep writes them
    rid_col, starts = rid_col[order], starts[order]
    ends = starts + rng.integers(30, 600, len(rid_col))
    scores = rng.random(len(rid_col))
    # the run indexes are rebuilt once after the bulk insert (as init_db states them), which is several
    # times faster than maintaining them row by row
    idx_sql = [r[0] for r in conn.execute("SELECT sql FROM sqlite_master WHERE type = 'index' AND "
                                          "tbl_name = 'detections' AND sql IS NOT NULL")]
    for name, in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'detections' "
                              "AND sql IS NOT NULL").fetchall():
        conn.execute(f"DROP INDEX {name}")
    conn.executemany("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, ?)",
                     zip(rid_col.tolist(), starts.tolist(), ends.tolist(), scores.tolist()))
    for sql in idx_sql:
        conn.execute(sql)
    conn.commit()
    n_det = conn.execute("SELECT MAX(id) FROM detections").fetchone()[0] or 0

    # ── the human side: annotations, reviewed spans ────────────────────────
    ann = []
    for i in range(n_annotations):
        rec = rec_ids[i % n_channels]
        a = int(rng.integers(0, n_samples - 1000))
        ann.append((rec, a, a + int(rng.integers(30, 900)), VERDICTS[int(rng.integers(0, 5))], NOW))
    conn.executemany("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                     "VALUES (?, ?, ?, ?, 'scale', ?)", ann)
    rev = []
    for i in range(n_reviewed):
        rec = rec_ids[i % n_channels]
        a = int(rng.integers(0, n_samples - 4000))
        rev.append((rec, a, a + 3600, 'scale', NOW))
    conn.executemany("INSERT INTO reviewed_spans (recording_id, start_idx, end_idx, source, reviewed_at) "
                     "VALUES (?, ?, ?, ?, ?)", rev)

    # ── the review queue: an exact detection set of queue_size real detections ──
    real_runs = [rid for d in druns for rid in d["run_ids"]]
    marks = ",".join(str(r) for r in real_runs)
    pool = [r[0] for r in conn.execute(f"SELECT id FROM detections WHERE run_id IN ({marks}) ORDER BY id")]
    pick = sorted(int(x) for x in rng.choice(pool, size=min(queue_size, len(pool)), replace=False)) if pool else []
    qid = conn.execute(
        "INSERT INTO review_queues (name, source_kind, unit, writes_to, blind, filters_json, created_at, note) "
        "VALUES ('scale queue', 'discovery-run', 'detection', 'adjudications', 0, ?, ?, 'scale fixture')",
        (json.dumps({"detection_ids": pick}), NOW)).lastrowid
    # adjudications on the first queue items and some elsewhere
    adj = pick[: n_adjudications // 2] + [int(x) for x in rng.choice(pool, size=n_adjudications - n_adjudications // 2,
                                                                      replace=False)] if pool else []
    conn.executemany("INSERT OR IGNORE INTO adjudications (detection_id, verdict, created_at) VALUES (?, ?, ?)",
                     [(d, ("interesting", "not_interesting")[i % 2], NOW) for i, d in enumerate(adj)])
    conn.commit()
    conn.close()
    return {"db": path, "recordings": rec_ids, "channel_names": names, "druns": druns, "queue_id": qid,
            "queue_ids": pick, "session_id": sid, "n_detections": int(n_det), "n_samples": n_samples,
            "build_s": time.perf_counter() - t0}


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), "perf_scale.sqlite")
    info = build(out, **FULL)
    print(json.dumps({k: v for k, v in info.items() if k not in ("queue_ids", "druns")}, indent=1))
    print(f"built in {info['build_s']:.1f} s")
