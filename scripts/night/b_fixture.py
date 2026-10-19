"""
b_fixture.py — night pass B: the scale fixture (tests/perf_fixture.py) at a size an interaction walk can stand on,
plus what B's pages need and the perf fixture does not hold:

* one extra run on channel 0 with ~90 k detections (the Signal page's heavy channel);
* a Library: motif entries/members over the 16 channels, a motif grouping of 12 families (with omitted members),
  sequences of those members and a sequence grouping.

Dev tooling; nothing imports it.  python scripts/night/b_fixture.py <out.sqlite> [--hours 72]
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from perf_fixture import build, NOW  # noqa: E402


def add_heavy_run(conn, rec_id, n_samples, cfg_id, n=90_000, seed=1):
    rng = np.random.default_rng(seed)
    gid = conn.execute("INSERT INTO run_groups (created_at) VALUES (?)", (NOW,)).lastrowid
    rid = conn.execute(
        "INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, finished_at, "
        "run_group_id) VALUES (?, ?, 0, ?, ?, 'completed', ?, ?)", (cfg_id, rec_id, n_samples, NOW, NOW, gid)).lastrowid
    starts = np.sort(rng.integers(0, n_samples - 100, n))
    ends = starts + rng.integers(5, 60, n)
    conn.executemany("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, ?)",
                     zip([rid] * n, starts.tolist(), ends.tolist(), rng.random(n).tolist()))
    return rid


def add_library(conn, rec_ids, n_samples, n_fam=12, per_fam=25, seed=2):
    rng = np.random.default_rng(seed)
    gid = conn.execute(
        "INSERT INTO groupings (name, unit, basis, method, params_json, cut, n_families, n_assigned, n_omitted, "
        "recipe_hash, created_at, actor) VALUES ('motifs · shape', 'single_motifs', 'shape-distance', 'ward', "
        "'{\"min_group\": 2}', 0.42, ?, ?, ?, 'night-b', ?, 'night fixture')",
        (n_fam, n_fam * per_fam, 10, NOW)).lastrowid
    members = []
    k = 0
    for f in range(n_fam + 1):                       # the last "family" is the omitted members
        count = per_fam if f < n_fam else 10
        for j in range(count):
            rid = rec_ids[int(rng.integers(0, len(rec_ids)))]
            a = int(rng.integers(0, n_samples - 2000))
            b = a + int(rng.integers(30, 400))
            h = f"nb{k}"
            entry = conn.execute(
                "INSERT INTO motif_entry (recording_id, start_idx, end_idx, scale, content_hash, created_at) "
                "VALUES (?, ?, ?, 'event', ?, ?)", (rid, a, b, h, NOW)).lastrowid
            mid = conn.execute("INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx, content_hash) "
                               "VALUES (?, ?, ?, ?, ?)", (entry, rid, a, b, h)).lastrowid
            if f < n_fam:
                conn.execute(
                    "INSERT INTO grouping_assignments (grouping_id, unit, member_ref, content_hash, family_id, "
                    "family_label, distance, is_medoid) VALUES (?, 'single_motifs', ?, ?, ?, ?, ?, ?)",
                    (gid, mid, h, f + 1, f"F-{f + 1:02d}", float(rng.random()) * 0.4, 1 if j == 0 else 0))
                members.append((mid, rid, a, b, f))
            else:
                conn.execute(
                    "INSERT INTO grouping_assignments (grouping_id, unit, member_ref, content_hash, family_id, "
                    "family_label, distance, omit_reason) VALUES (?, 'single_motifs', ?, ?, NULL, 'F-01', 0.9, "
                    "'past the cut')", (gid, mid, h))
            k += 1
    # sequences: triples of members on the same recording, in time order
    by_rec = {}
    for m in members:
        by_rec.setdefault(m[1], []).append(m)
    seq_ids = []
    for rid, ms in by_rec.items():
        ms.sort(key=lambda m: m[2])
        for i in range(0, len(ms) - 2, 3):
            ev = ms[i:i + 3]
            sid = conn.execute(
                "INSERT INTO sequences (sequence_key, origin, recording_id, channel, start_idx, end_idx, n_events, "
                "needs_extraction, source_kind, created_at) VALUES (?, 'machine', ?, 0, ?, ?, 3, 0, 'sequence_csv', ?)",
                (f"nsq-{rid}-{i}", rid, ev[0][2], ev[-1][3], NOW)).lastrowid
            for p, m in enumerate(ev):
                conn.execute("INSERT INTO sequence_members (sequence_id, position, member_id, start_idx, end_idx, "
                             "gap_before) VALUES (?, ?, ?, ?, ?, ?)",
                             (sid, p, m[0], m[2], m[3], None if p == 0 else float(m[2] - ev[p - 1][3])))
            seq_ids.append(sid)
    sg = conn.execute(
        "INSERT INTO groupings (name, unit, basis, method, params_json, cut, n_families, n_assigned, n_omitted, "
        "recipe_hash, created_at, actor) VALUES ('sequences · order', 'sequences', 'sequence-similarity', 'ward', "
        "'{\"min_group\": 2}', 0.5, 3, ?, 0, 'night-b-seq', ?, 'night fixture')", (len(seq_ids), NOW)).lastrowid
    for i, s in enumerate(seq_ids):
        conn.execute("INSERT INTO grouping_assignments (grouping_id, unit, member_ref, content_hash, family_id, "
                     "family_label, distance, is_medoid) VALUES (?, 'sequences', ?, ?, ?, ?, 0.1, ?)",
                     (sg, s, f"nsqh{s}", i % 3 + 1, f"F-{i % 3 + 1:02d}", 1 if i < 3 else 0))
    return gid, sg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--hours", type=float, default=72.0)
    ap.add_argument("--druns", type=int, default=6)
    ap.add_argument("--detections", type=int, default=300_000)
    a = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    info = build(a.out, n_channels=16, hours=a.hours, n_druns=a.druns, n_detections=a.detections, n_annotations=3000,
                 n_templates=12, queue_size=2000, n_adjudications=200, n_reviewed=400)
    conn = sqlite3.connect(a.out)
    cfg = conn.execute("SELECT id FROM configs LIMIT 1").fetchone()[0]
    heavy = add_heavy_run(conn, info["recordings"][0], info["n_samples"], cfg)
    g, sg = add_library(conn, info["recordings"], info["n_samples"])
    conn.commit()
    conn.close()
    print(json.dumps({"db": a.out, "heavy_run": heavy, "motif_grouping": g, "seq_grouping": sg,
                      "recordings": info["recordings"], "session_id": info["session_id"]}))


if __name__ == "__main__":
    main()
