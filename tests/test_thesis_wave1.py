"""
test_thesis_wave1.py
====================
The wave-1 thesis export (`scripts/thesis/wave1/run_wave1.py`), end to end on a synthetic world: a database built
with `init_db` (recordings, Discovery template and seed runs with real and surrogate detections, annotations,
adjudications, Review queues 25/28/35/36, Library members and groupings, a B4 census, a cached CNN score), channel
.npy files, candidate-event tables (one built by `candidate_events.build_table` itself), an RQ2 panel key, a
drop-motif store and some plots. The R4 MiniRocket is stubbed for the end-to-end run; its real path is exercised on
a small side-feature model when scikit-learn and joblib are importable.

Pinned:
* every step runs ok, the database file is byte-identical afterwards, and the connection cannot write;
* *Schizophyllum commune* appears in no exported file; M4 is exported (its exam was scored);
* arrays are float32 mV with the sidecar the thesis needs; a label (CH4_A2) resolves through the tool's naming;
* every zip part is under the limit and together they hold every exported file once;
* the pool's collapse, its MJu26a-over-L_LM preference and its stratified sample.

Run from the project root:
    python -m pytest tests/test_thesis_wave1.py -q
"""

import glob
import hashlib
import json
import os
import sqlite3
import sys
import zipfile

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "scripts", "thesis")):
    if p not in sys.path:
        sys.path.insert(0, p)

from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery import candidate_events as ce  # noqa: E402
from wave1 import common as C  # noqa: E402
from wave1 import pool as P  # noqa: E402
from wave1 import run_wave1  # noqa: E402
from wave1 import zipper as Z  # noqa: E402

T = "2026-10-20T00:00:00"
VARIANTS = ["drop_detection_v1", "drop_detection_v5", "noise_threshold", "signal_threshold", "wavelet_encoded",
            "symbol_search", "deconvolved_troughs", "OASIS_Deconvolution", "BEADs_invert_detect_v1",
            "cnn_fusion3_10min"]
NEG = "cnn_gasf_1min"
N_M2 = 36_000
CENTRES = [1000 + 600 * k for k in range(56)]
SCOMMUNE = "Schizophyllum commune.txt"
MAX_PART_MB = 3.0


def _lens(k):
    return 60 + 20 * (k % 5)


class StubR4:
    """A stand-in for the frozen R4 in the end-to-end run (the real model is not in this repository)."""
    source = "stub"

    def score(self, rows):
        d = np.log1p((rows["end"] - rows["start"]).to_numpy(float)) - 4.3
        return pd.DataFrame({"r4_decision": d, "r4_readable": True, "r4_interesting": d > 0, "r4_source": "stub",
                             "r4_model_sha256_ok": True})


# ── the synthetic world ────────────────────────────────────────────────────────────────────────────────────

class World:
    def __init__(self, root):
        self.root = str(root)
        self.db = os.path.join(self.root, "DATA", "db", "annotations.sqlite")
        os.makedirs(os.path.dirname(self.db), exist_ok=True)
        self.conn = init_db(self.db)
        self.rng = np.random.default_rng(1)
        self.n_cfg = 0
        self.ids = {}

    # recordings and channels
    def channel(self, sf, ch, fs, n, units, *, rid=None, drops=()):
        stem = os.path.splitext(sf)[0]
        x = -0.3 + 0.0005 * self.rng.standard_normal(n)
        for c, L in drops:
            if c + L < n:
                x[c:c + L] -= 0.01 * np.hanning(L)
        rel = f"DATA/derived/channels/{stem}/CH{ch}.npy"
        os.makedirs(os.path.join(self.root, os.path.dirname(rel)), exist_ok=True)
        np.save(os.path.join(self.root, rel), x)
        if rid is None:
            rid = q.insert_recording(self.conn, sf, ch, fs, n, 0, rel, units=units)
        else:
            self.conn.execute("INSERT INTO recordings (id, source_file, channel, fs, n_samples, global_offset, "
                              "npy_path, units) VALUES (?, ?, ?, ?, ?, 0, ?, ?)", (rid, sf, ch, fs, n, rel, units))
            self.conn.commit()
        self.ids[(sf, ch)] = int(rid)
        return int(rid)

    # runs
    def session(self, sf):
        cur = self.conn.execute("INSERT INTO discovery_sessions (name, source_file, channels_json, created_at, "
                                "updated_at) VALUES ('s', ?, '[]', ?, ?)", (sf, T, T))
        return cur.lastrowid

    def group(self, sid, kind, name, *, dr_id=None, params=None):
        gid = self.conn.execute("INSERT INTO run_groups (created_at) VALUES (?)", (T,)).lastrowid
        cols = "session_id, run_key, kind, label, template_name, run_group_id, params_json, status, created_at, " \
               "updated_at"
        vals = [sid, f"k{gid}", kind, name, name if kind == "template" else None, gid, json.dumps(params or {}),
                "done", T, T]
        if dr_id is not None:
            cols = "id, " + cols
            vals = [dr_id] + vals
        self.conn.execute(f"INSERT INTO discovery_runs ({cols}) VALUES ({','.join('?' * len(vals))})", vals)
        return gid

    def run(self, rid, gid, spans, *, recipe=None, surrogate_of=None, scores=None):
        self.n_cfg += 1
        cid = self.conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES (?, ?, ?)",
                                (f"cfg{self.n_cfg:05d}", json.dumps(recipe or {"n": self.n_cfg}), T)).lastrowid
        n = self.conn.execute("SELECT n_samples FROM recordings WHERE id = ?", (rid,)).fetchone()[0]
        run = self.conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status, "
                                "run_group_id, surrogate_of_run_id) VALUES (?, ?, 0, ?, ?, 'completed', ?, ?)",
                                (cid, rid, n, T, gid, surrogate_of)).lastrowid
        dets = [self.conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, ?, ?, ?)",
                                  (run, int(s), int(e), None if scores is None else float(scores[i]))).lastrowid
                for i, (s, e) in enumerate(spans)]
        self.conn.commit()
        return run, dets

    def queue(self, qid, ids, name):
        self.conn.execute("INSERT INTO review_queues (id, name, source_kind, unit, writes_to, blind, filters_json, "
                          "created_at) VALUES (?, ?, 'discovery-run', 'detection', 'adjudications', 1, ?, ?)",
                          (qid, name, json.dumps({"detection_ids": [int(i) for i in ids], "order": "listed"}), T))
        self.conn.commit()

    def adjudicate(self, det, verdict, *, carried_from=None, queue=None):
        aid = self.conn.execute("INSERT INTO adjudications (detection_id, verdict, created_at, carried_from) "
                                "VALUES (?, ?, ?, ?)", (det, verdict, T, carried_from)).lastrowid
        if queue is not None:
            self.conn.execute("INSERT INTO review_audit (queue_id, action, target_table, target_ids, payload_json, "
                              "created_at) VALUES (?, 'verdict', 'adjudications', ?, ?, ?)",
                              (queue, json.dumps([aid]), json.dumps({"targets": [{"target_id": det}]}), T))
        self.conn.commit()
        return aid


def write_table(root, sf, events, *, key=None):
    events = events.copy()
    for c in ce.EVENT_COLUMNS:
        if c not in events:
            events[c] = None
    meta = {"key": key or f"{ce._safe(sf)}_synthetic", "version": ce.TABLE_VERSION, "source_file": sf,
            "created_at": T, "n_events": int(len(events)), "recordings": {}}
    members = pd.DataFrame({"event_id": events["event_id"], "detection_id": events["anchor_detection_id"]})
    return ce.save_table(os.path.join(root, "DATA", "derived", "candidate_events"), events[list(ce.EVENT_COLUMNS)],
                         members, meta)


def synthetic_events(rid, ch, n, fs, *, count, seed, dets=None):
    rng = np.random.default_rng(seed)
    starts = np.sort(rng.choice(np.arange(100, n - 400), size=count, replace=False))
    lens = rng.integers(20, 200, size=count)
    na = rng.integers(1, 12, size=count)
    return pd.DataFrame({"event_id": np.arange(count), "recording_id": rid, "channel": ch, "start": starts,
                         "end": starts + lens, "anchor_detection_id": dets if dets is not None else
                         np.arange(10_000_000 + seed * 1000, 10_000_000 + seed * 1000 + count),
                         "anchor_variant": "noise_threshold", "n_members": na, "matched_families": "noise_threshold",
                         "n_matched_families": 1, "agree_families": "noise_threshold", "n_agree": na,
                         "label": None, "label_kind": None, "label_basis": None, "label_refs": None,
                         "inside_interesting": False})


def build_world(root):
    w = World(root)
    root = w.root
    drops = [(c, _lens(k)) for k, c in enumerate(CENTRES)]
    m2 = "M2_aug_concat_fs1.mat"
    m2r = [w.channel(m2, ch, 1.0, N_M2, "V", drops=drops if ch < 2 else ()) for ch in range(16)]
    for ch in range(14):
        w.channel("M2_concat_fs1.mat", ch, 1.0, 5000, "V")
    m4 = [w.channel("M4_aug_concat_fs1.mat", ch, 1.0, N_M2, None, drops=drops) for ch in range(2)]
    lm = [w.channel("LM_fs2.mat", ch, 2.0, 20_000, "mV") for ch in range(2)]
    mju = w.channel("MJu26a_fs2.mat", 0, 2.0, 20_000, None)
    llm = w.channel("L_LM_Jul_26_J_raw_fs2.mat", 0, 2.0, 20_000, "mV")
    sc = w.channel(SCOMMUNE, 0, 1.0, 10_000, "mV")
    fig = w.channel("Fig2A_dt0p1.csv", 0, 10.0, 5000, None)
    mush = w.channel("Mushroom_260720_0509_4hrs_CH14_fs1.mat", 0, 1.0, 14_400, "V", rid=385)
    w.m2r, w.m4, w.lm, w.sc, w.mush = m2r, m4, lm, sc, mush

    # the sweep on M2_aug channels 0 and 1: ten families, event k found by the first 1 + k % 10 of them
    sid = w.session(m2)
    w.real_runs = {}
    for vi, v in enumerate(VARIANTS):
        gid = w.group(sid, "template", v)
        for rid in m2r[:2]:
            spans = [(c, c + _lens(k)) for k, c in enumerate(CENTRES) if vi < 1 + k % 10]
            if v == "deconvolved_troughs":                         # nested: a long span around some events
                spans += [(c - 100, c + _lens(k) + 200) for k, c in enumerate(CENTRES) if k % 10 == 9]
            recipe, scores = None, None
            if v.startswith("cnn_"):
                spans = sorted({((c // 600) * 600, (c // 600) * 600 + 600) for k, c in enumerate(CENTRES)
                                if vi < 1 + k % 10})
                recipe = {"recording_id": rid, "span": None, "steps": [
                    {"stage": "preprocessing", "algorithm": "sliding_windows", "params": {"window_s": 600}},
                    {"stage": "catalogue", "algorithm": "cnn_window_scores", "params": {"image_type": "fusion"}},
                    {"stage": "detection", "algorithm": "threshold", "params": {"threshold": 0.5}}]}
                scores = [0.9] * len(spans)
            run, _ = w.run(rid, gid, spans, recipe=recipe, scores=scores)
            w.real_runs[(v, rid)] = run
            if v == "drop_detection_v1":                           # its paired null draw, in the same group
                w.run(rid, gid, [(s + 37, s + 77) for s in range(500, N_M2 - 200, 2000)], surrogate_of=run)
            if v.startswith("cnn_"):
                from Working.execution import _recipe_prefix_hash
                from Working.types.scores import Scores
                h = _recipe_prefix_hash(recipe, 1, "V")
                vals = np.repeat(np.linspace(0, 1, N_M2 // 600 + 1), 600)[:N_M2]
                rel = f"DATA/derived/step_cache/{h}/1"
                Scores(values=vals, fs=1.0).to_path(os.path.join(root, rel))
                w.conn.execute("INSERT INTO step_artifacts (recipe_prefix_hash, step_index, path) VALUES (?, 1, ?)",
                               (h, rel))
    gid = w.group(sid, "template", NEG)
    for rid in m2r[:2]:
        w.run(rid, gid, [(c - 30, c + _lens(k) + 30) for k, c in enumerate(CENTRES)])
    # two seed searches (the RQ2 panel's seeds 67 and 68)
    e_id = w.conn.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx) VALUES (?, ?, ?)",
                          (m2r[1], CENTRES[7], CENTRES[7] + 140)).lastrowid
    g67 = w.group(sid, "seed", "drop30", dr_id=67,
                  params={"seedId": f"medoid:{m2r[0]}:{CENTRES[3]}:{CENTRES[3] + 120}"})
    w.seed_run, _ = w.run(m2r[0], g67, [(CENTRES[k], CENTRES[k] + _lens(k)) for k in (3, 13, 23)])
    w.group(sid, "seed", "spike37", dr_id=68, params={"entryId": e_id})
    w.seed_entry = e_id
    # an HPC seed search: no run group, its run named only in params_json.run_ids
    hpc_run, _ = w.run(m2r[1], None, [(CENTRES[k], CENTRES[k] + _lens(k)) for k in (6, 8)])
    w.conn.execute("INSERT INTO discovery_runs (session_id, run_key, kind, label, params_json, status, created_at, "
                   "updated_at) VALUES (?, 'hpc', 'seed', 'hpc_seed', ?, 'done', ?, ?)",
                   (sid, json.dumps({"run_ids": [hpc_run]}), T, T))
    w.conn.commit()

    # human verdicts
    w.accepted = [q.insert_annotation(w.conn, m2r[1], CENTRES[k], CENTRES[k] + _lens(k), "interesting",
                                      source="library_review") for k in range(5, 10)]
    q.insert_annotation(w.conn, m2r[0], CENTRES[4], CENTRES[4] + _lens(4), "seed", source="library_review")
    w.miss = q.insert_annotation(w.conn, m2r[0], 500, 560, "interesting", source="manual_ui")
    labels = ["interesting", "not_interesting", "artifact"]
    w.hand = [q.insert_annotation(w.conn, m2r[0], i * 600, i * 600 + 600, labels[i % 3], source="imported_10min")
              for i in range(30)]
    dele = q.insert_annotation(w.conn, m2r[0], 30 * 600, 31 * 600, "interesting", source="imported_10min")
    w.conn.execute("UPDATE annotations SET deleted_at = ? WHERE id = ?", (T, dele))
    q.insert_annotation(w.conn, sc, 100, 200, "interesting", source="library_review")
    w.conn.commit()

    # the M2_aug candidate-event table, built by the tool itself
    ev, mem, meta = ce.build_table(w.conn, m2)
    w.m2_table = ce.save_table(os.path.join(root, "DATA", "derived", "candidate_events"), ev, mem, meta)
    w.m2_events = ev

    # queue 25: a sample of the table, with own verdicts and one carried copy
    pick = ev.sort_values("event_id").iloc[::max(1, len(ev) // 12)].head(12).copy()
    pick["stratum"] = [ce.level_of(int(n)) for n in pick["n_agree"]]
    s = pd.DataFrame({"event_id": pick["event_id"], "detection_id": pick["anchor_detection_id"],
                      "recording_id": pick["recording_id"], "channel": pick["channel"], "start": pick["start"],
                      "end": pick["end"], "stratum": pick["stratum"], "frame_size": 50, "sample_size": 12,
                      "weight": 50 / 12, "serve_rank": np.arange(len(pick))})
    sdir = os.path.join(w.m2_table, "sample_seed0_l100_f50")
    os.makedirs(sdir)
    s.to_parquet(os.path.join(sdir, "sample.parquet"), index=False)
    s[["event_id"]].assign(label=None).to_parquet(os.path.join(sdir, "labels.parquet"), index=False)
    with open(os.path.join(sdir, "meta.json"), "w") as fh:
        json.dump({"queue_id": 25, "table_key": meta["key"], "name": "sample_seed0_l100_f50"}, fh)
    w.q25 = [int(d) for d in s["detection_id"]]
    w.queue(25, w.q25, "blind M2_aug")
    first = w.adjudicate(w.q25[0], "interesting", queue=25)
    w.adjudicate(w.q25[1], "not_interesting", queue=25)
    w.adjudicate(w.q25[2], "seed", queue=25)
    other = int(mem[~mem["detection_id"].isin(w.q25)]["detection_id"].iloc[0])
    w.adjudicate(other, "interesting", carried_from=first)

    # queue 28: LM_fs2 items and one S. commune item (refused)
    gl = w.group(w.session("LM_fs2.mat"), "template", "noise_threshold")
    _, lm_dets = w.run(lm[0], gl, [(1000, 1100), (5000, 5150), (9000, 9050)])
    gs = w.group(w.session(SCOMMUNE), "template", "noise_threshold")
    _, sc_dets = w.run(sc, gs, [(300, 400)])
    w.q28 = lm_dets + sc_dets
    w.queue(28, w.q28, "blind 2 Hz sets")
    w.queue(40, sc_dets, "Unseen exam · Schizophyllum commune · blind sample")
    w.adjudicate(lm_dets[0], "interesting", queue=28)
    w.adjudicate(sc_dets[0], "interesting", queue=28)

    # queue 35: the RQ2 panel and its key
    gp = w.conn.execute("INSERT INTO run_groups (created_at) VALUES (?)", (T,)).lastrowid
    _, p0 = w.run(m2r[0], gp, [(CENTRES[3], CENTRES[3] + 120), (20_000, 20_377)])
    _, p1 = w.run(m2r[1], gp, [(CENTRES[33], CENTRES[33] + 148)])
    w.q35 = [p0[1], p0[0], p1[0]]
    w.queue(35, w.q35, "RQ2 blind panel")
    items = [{"group": "drop30", "seed": "drop30", "recording_id": m2r[0], "channel": "CH1_A1", "start": CENTRES[3],
              "end": CENTRES[3] + 120, "length": 120, "source": {"discovery_run": 67}, "earlier": None,
              "serve_rank": 2, "panel_detection_id": p0[0]},
             {"group": "control", "seed": None, "control_length": 377, "recording_id": m2r[0], "channel": "CH1_A1",
              "start": 20_000, "end": 20_377, "length": 377, "source": {"uniform": True}, "earlier": None,
              "serve_rank": 1, "panel_detection_id": p0[1]},
             {"group": "spike37", "seed": "spike37", "recording_id": m2r[1], "channel": "CH2_A1",
              "start": CENTRES[33], "end": CENTRES[33] + 148, "length": 148, "source": {"discovery_run": 68},
              "earlier": None, "serve_rank": 3, "panel_detection_id": p1[0]}]
    kd = os.path.join(root, "DATA", "derived", "rq2_blind", "20261026-120000")
    os.makedirs(kd)
    with open(os.path.join(kd, "key.json"), "w") as fh:
        json.dump({"queue_id": 35, "items": items}, fh)
    w.adjudicate(p0[0], "interesting", queue=35)

    # queue 36: the M4 exam (a synthetic M4 table, its sample, verdicts through the queue but one)
    g4 = w.group(w.session("M4_aug_concat_fs1.mat"), "template", "noise_threshold")
    m4_spans = [(c, c + _lens(k)) for k, c in enumerate(CENTRES)]
    _, m4_dets = w.run(m4[0], g4, m4_spans)
    t4 = pd.DataFrame({"event_id": np.arange(len(m4_spans)), "recording_id": m4[0], "channel": 0,
                       "start": [s for s, _ in m4_spans], "end": [e for _, e in m4_spans],
                       "anchor_detection_id": m4_dets, "anchor_variant": "noise_threshold",
                       "n_agree": [1 + k % 10 for k in range(len(m4_spans))], "matched_families": "noise_threshold",
                       "agree_families": "noise_threshold", "n_members": 1, "n_matched_families": 1,
                       "inside_interesting": False})
    w.m4_table = write_table(root, "M4_aug_concat_fs1.mat", t4, key="M4_aug_concat_fs1_ae545821")
    ex = t4.iloc[[1, 2, 3, 5, 8, 9, 20, 40]].copy()
    ex["stratum"] = "agree:1-2"
    sm = pd.DataFrame({"event_id": ex["event_id"], "detection_id": ex["anchor_detection_id"],
                       "recording_id": ex["recording_id"], "channel": 0, "start": ex["start"], "end": ex["end"],
                       "stratum": ex["stratum"], "frame_size": 56, "sample_size": 8, "weight": 7.0,
                       "serve_rank": np.arange(len(ex))})
    sd4 = os.path.join(w.m4_table, "sample_seed20261026_l40_f15")
    os.makedirs(sd4)
    sm.to_parquet(os.path.join(sd4, "sample.parquet"), index=False)
    sm[["event_id"]].assign(label=None).to_parquet(os.path.join(sd4, "labels.parquet"), index=False)
    with open(os.path.join(sd4, "meta.json"), "w") as fh:
        json.dump({"queue_id": 36, "table_key": "M4_aug_concat_fs1_ae545821"}, fh)
    w.q36 = [int(d) for d in sm["detection_id"]]
    w.queue(36, w.q36, "Held-out exam · M4 · blind sample")
    for i, d in enumerate(w.q36[:-1]):
        w.adjudicate(d, ["interesting", "not_interesting", "artifact"][i % 3], queue=36)
    w.adjudicate(w.q36[-1], "interesting")                 # own, but not given through the exam queue

    # tables of the 2 Hz sets (MJu26a and its L_LM copy both), and of S. commune
    write_table(root, "LM_fs2.mat", synthetic_events(lm[0], 0, 20_000, 2.0, count=120, seed=3))
    write_table(root, "MJu26a_fs2.mat", synthetic_events(mju, 0, 20_000, 2.0, count=80, seed=4))
    write_table(root, "L_LM_Jul_26_J_raw_fs2.mat", synthetic_events(llm, 0, 20_000, 2.0, count=80, seed=5))
    write_table(root, SCOMMUNE, synthetic_events(sc, 0, 10_000, 1.0, count=40, seed=6))

    # the Library: g-11 events (tracked csv) and rec 385's members with g-05 families
    for gid_, name in ((5, "g-05"), (11, "g-11")):
        w.conn.execute("INSERT INTO groupings (id, name, unit, basis, method, params_json, created_at) VALUES "
                       "(?, ?, 'single_motifs', 'shape-distance', 'ward', '{}', ?)", (gid_, name, T))
    rows = []
    for i, (rid, k) in enumerate([(m2r[0], 11), (m2r[0], 21), (m2r[1], 12), (m2r[1], 22), (lm[0], None)]):
        s0, e0 = (CENTRES[k], CENTRES[k] + _lens(k)) if k is not None else (4000, 4300)
        e = w.conn.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx) VALUES (?, ?, ?)",
                           (rid, s0, e0)).lastrowid
        m = w.conn.execute("INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx) VALUES (?, ?, ?, ?)",
                           (e, rid, s0, e0)).lastrowid
        if i < 4:
            w.conn.execute("INSERT INTO grouping_assignments (grouping_id, unit, member_ref, family_id, family_label) "
                           "VALUES (11, 'single_motifs', ?, ?, ?)", (m, i % 2, f"F-0{i % 2 + 1}"))
        rec = w.conn.execute("SELECT source_file, channel, fs FROM recordings WHERE id = ?", (rid,)).fetchone()
        rows.append({"event_id": f"EV-{i + 1:05d}", "recording": rec[0], "recording_id": rid, "channel": rec[1],
                     "fs": rec[2], "start_idx": s0, "end_idx": e0, "representative_member": m})
    for s0 in (1000, 5000):
        e = w.conn.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx) VALUES (385, ?, ?)",
                           (s0, s0 + 300)).lastrowid
        m = w.conn.execute("INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx) VALUES "
                           "(?, 385, ?, ?)", (e, s0, s0 + 300)).lastrowid
        w.conn.execute("INSERT INTO grouping_assignments (grouping_id, unit, member_ref, family_id, family_label) "
                       "VALUES (5, 'single_motifs', ?, 3, 'F-03')", (m,))
    w.conn.commit()
    lib = os.path.join(root, "docs", "thesis", "data", "library_events_all_active")
    os.makedirs(lib)
    pd.DataFrame(rows).to_csv(os.path.join(lib, "events.csv"), index=False)
    with open(os.path.join(lib, "events_grouping.json"), "w") as fh:
        json.dump({"grouping_id": 11, "events": 5}, fh)

    # a B4 census: ten propagation co-occurrences in hour 5-6, five artifact ones elsewhere
    cid = w.conn.execute("INSERT INTO cross_census (source_file, detector, hash, run_ids_json, layout_json, rule_json, "
                         "consts_json, status, created_at) VALUES (?, 'drop_detection_v1', 'abc123', '[]', '{}', "
                         "'{}', '{}', 'done', ?)", (m2, T)).lastrowid
    for i in range(10):
        w.conn.execute("INSERT INTO cross_cooccurrence (census_id, det_a_id, det_b_id, rec_a_id, rec_b_id, onset_a_s, "
                       "onset_b_s, lag_s, bin) VALUES (?, 1, 2, ?, ?, ?, ?, 3.0, 'propagation')",
                       (cid, m2r[0], m2r[1], 5 * 3600 + 100 * i, 5 * 3600 + 100 * i + 3))
    for i in range(5):
        w.conn.execute("INSERT INTO cross_cooccurrence (census_id, det_a_id, det_b_id, rec_a_id, rec_b_id, onset_a_s, "
                       "onset_b_s, lag_s, bin) VALUES (?, 1, 2, ?, ?, ?, ?, 0.0, 'artifact')",
                       (cid, m2r[0], m2r[1], 1 * 3600 + 10 * i, 1 * 3600 + 10 * i))
    w.conn.commit()
    b4 = os.path.join(root, "docs", "thesis", "data", "ch10_b4")
    os.makedirs(b4)
    pd.DataFrame([{"census_hash": "abc123", "source_file": m2, "a": m2r[0], "b": m2r[1], "n": 10}]).to_csv(
        os.path.join(b4, "b4_pairs.csv"), index=False)

    # the drop-motif store, its notes, and some plots
    st = os.path.join(root, "Plots", "drop_motifs12a", "motifs")
    os.makedirs(st)
    mot = pd.DataFrame({"event_id": [f"e{i:03d}" for i in range(12)], "species": ["oyster"] * 6 + ["reishi"] * 6,
                        "catalogue_id": 1, "channel": 0, "onset_idx": np.arange(12) * 100})
    mot.to_csv(os.path.join(st, "motifs.csv"), index=False)
    np.savez_compressed(os.path.join(st, "motifs.npz"), **{f"{e}__raw_mv": np.arange(5.0) for e in mot["event_id"]})
    with open(os.path.join(st, "manifest.json"), "w") as fh:
        json.dump({"n_motifs": 12}, fh)
    fig = os.path.join(root, "Plots", "drop_motifs12b")
    os.makedirs(fig)
    for f in ("FIGURES.md", "CLAIMS.md"):
        with open(os.path.join(fig, f), "w") as fh:
            fh.write("# notes\n")
    pd.DataFrame([{"sequence_key": "s1", "species": "oyster", "catalogue_id": 1, "channel": 0,
                   "start_event_id": "e001", "end_event_id": "e003"}]).to_csv(os.path.join(fig, "sequences.csv"),
                                                                              index=False)
    mp = os.path.join(root, "Plots", "Detection", "mp", "profile")
    os.makedirs(mp)
    from PIL import Image
    Image.fromarray(np.zeros((20, 30, 3), np.uint8)).save(os.path.join(mp, "small.png"))
    Image.fromarray(np.zeros((20, 30, 3), np.uint8)).save(os.path.join(mp, "Schizophyllum_commune_profile.png"))
    fs_ = os.path.join(root, "Plots", "family_search")
    os.makedirs(fs_)
    Image.fromarray(np.random.default_rng(0).integers(0, 255, (420, 2400, 3), dtype=np.uint8)).save(
        os.path.join(fs_, "big.png"))
    w.conn.close()
    return w


def make_spec(root):
    with open(C.SPEC_PATH, encoding="utf-8") as fh:
        spec = json.load(fh)
    spec["windows"][0].update(start_h=1, end_h=2)
    spec["windows"][1].update(start_h=2, end_h=4)
    hours = {"gallery": 2, "b1_trains": 1, "b4_stack": 1, "agreement_excerpt": 2, "cnn_scores": 3}
    for r in spec["rules"]:
        r["hours"] = hours[r["rule"]]
        r.setdefault("fallback_start_h", 1)
        if r["rule"] == "gallery":
            r["fallback_start_h"] = 1
        if r["rule"] == "agreement_excerpt":
            r["min_judged"] = 1
    spec["pool"]["per_recording"] = 30
    spec["pool"]["thumbnails_per_level"] = 3
    spec["m4_exam"]["hours"] = 2
    spec["drop_motifs"].update(max_npz_mb=0, subset_n=4)        # the store is "too big": a subset is drawn
    p = os.path.join(str(root), "spec.json")
    with open(p, "w") as fh:
        json.dump(spec, fh)
    return p


def _sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    root = tmp_path_factory.mktemp("wave1_world")
    w = build_world(root)
    sha = _sha(w.db)
    out = os.path.join(str(root), "OUT", "wave1")
    spec = make_spec(root)
    mp = pytest.MonkeyPatch()
    mp.setattr(P, "make_r4_scorer", lambda ctx: StubR4())
    try:
        rc = run_wave1.main(["--root", str(root), "--db", w.db, "--out", out, "--spec", spec,
                             "--max-part-mb", str(MAX_PART_MB)])
    finally:
        mp.undo()
    return {"w": w, "root": str(root), "out": out, "data": os.path.join(out, "data"), "rc": rc, "sha": sha,
            "spec": spec}


def _status(run, step):
    with open(os.path.join(run["data"], "_status", f"{step}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _csv(run, *parts):
    return pd.read_csv(os.path.join(run["data"], *parts))


def _sidecar(path):
    with open(path[:-4] + ".json", encoding="utf-8") as fh:
        return json.load(fh)


# ── the run as a whole ─────────────────────────────────────────────────────────────────────────────────────

def test_every_step_runs_ok_and_the_database_is_untouched(run):
    assert run["rc"] == 0
    for step in run_wave1.STEP_ORDER:
        st = _status(run, step)
        assert st["status"] == "ok", (step, st.get("error"))
    assert _sha(run["w"].db) == run["sha"]
    assert not glob.glob(run["w"].db + "-*")
    report = open(os.path.join(run["out"], "REPORT.md"), encoding="utf-8").read()
    assert "| pool | **ok** |" in report and "Zip parts" in report


def test_the_connection_cannot_write(run):
    conn, note = C.open_ro(run["w"].db)
    with pytest.raises(sqlite3.Error):
        conn.execute("INSERT INTO run_groups (created_at) VALUES ('x')")
    conn.close()


def test_s_commune_is_in_no_exported_file(run):
    sc = run["w"].sc
    for dp, _dn, fns in os.walk(run["out"]):
        for fn in fns:
            assert "chizophyllum" not in fn and "commune" not in fn.lower()
            p = os.path.join(dp, fn)
            if fn.endswith((".csv", ".json", ".md", ".log")):
                text = open(p, encoding="utf-8").read()
                assert "Schizophyllum" not in text, p
            if fn.endswith(".csv"):
                df = pd.read_csv(p)
                if "recording_id" in df.columns:
                    assert sc not in set(pd.to_numeric(df["recording_id"], errors="coerce").dropna().astype(int)), p
    items = _csv(run, "queues", "queue_items.csv")
    assert set(items[items["queue"] == 28]["detection_id"]) == set(run["w"].q28[:3])


# ── arrays ─────────────────────────────────────────────────────────────────────────────────────────────────

def test_overviews_are_the_mean_of_each_minute_in_mv(run):
    w = run["w"]
    p = os.path.join(run["data"], "overviews", "M2_aug__overview60s.npz")
    x = np.load(p)["x"]
    meta = _sidecar(p)
    assert x.dtype == np.float32 and x.shape == (16, N_M2 // 60)
    raw = np.load(os.path.join(run["root"], "DATA", "derived", "channels", "M2_aug_concat_fs1", "CH1.npy"))
    assert np.allclose(x[1], raw.reshape(-1, 60).mean(axis=1) * 1000, rtol=1e-5)
    assert meta["converted_to"] == "mV" and meta["dt_s"] == 60 and meta["channels"][1]["recording_id"] == w.m2r[1]
    assert {os.path.basename(f) for f in glob.glob(os.path.join(run["data"], "overviews", "*.npz"))} == {
        f"{s}__overview60s.npz" for s in ("M2_aug", "M2_concat", "M4_aug", "LM_fs2", "L_LM_fs2", "MJu26a_fs2",
                                          "Mushroom_260720", "Fig2A")}


def test_full_channels_and_the_unit_of_an_undeclared_file(run):
    d = os.path.join(run["data"], "full_channels")
    names = sorted(os.path.basename(f) for f in glob.glob(os.path.join(d, "*.npz")))
    assert names == ["Fig2A__CH0__full.npz", "M2_concat__CH0__full.npz", "M2_concat__CH13__full.npz",
                     "M2_concat__CH2__full.npz", "Mushroom_260720__CH0__full.npz"]
    meta = _sidecar(os.path.join(d, "Fig2A__CH0__full.npz"))
    assert meta["units_original"] is None and meta["mv_factor"] == 1000.0 and "undeclared" in meta["units_note"]
    m385 = _sidecar(os.path.join(d, "Mushroom_260720__CH0__full.npz"))
    assert m385["recording_id"] == 385 and m385["fs"] == 1.0
    for k in ("source_file", "recording_id", "channel", "fs", "t0_s", "units_original", "converted_to"):
        assert k in meta


def test_windows_resolve_the_label_and_keep_the_fallback_beside_it(run):
    res = json.load(open(os.path.join(run["data"], "windows", "resolved_windows.json")))
    by = {x["name"]: x for x in res}
    a = by["M2_aug_CH4_A2_377-381h"]
    assert a["channels"] == [3] and "CH4_A2" in a["channel_resolution"]
    assert by["M2_aug_CH4_A2_377-381h__fallback_index4"]["channels"] == [4]
    p = os.path.join(run["data"], "windows", "M2_aug_CH4_A2_377-381h.npz")
    x = np.load(p)["x"]
    raw = np.load(os.path.join(run["root"], "DATA", "derived", "channels", "M2_aug_concat_fs1", "CH3.npy"))
    assert np.allclose(x, (raw[3600:7200] * 1000).astype(np.float32))
    rules = {x["rule"] for x in res}
    assert {"gallery", "b1_trains", "b4_stack", "agreement_excerpt", "cnn_scores"} <= rules
    g = [x for x in res if x["rule"] == "gallery" and x["recording"] == "M2_aug"][0]
    assert g["channels"] == [1]                               # the channel with the accepted events
    b4 = [x for x in res if x["rule"] == "b4_stack"][0]
    assert len(b4["channels"]) == 16 and b4["start_s"] <= 5 * 3600 and b4["end_s"] >= 5 * 3600 + 900
    assert np.load(os.path.join(run["data"], "windows", b4["name"] + ".npz"))["x"].shape[0] == 16
    co = pd.read_csv(os.path.join(run["data"], "windows", b4["name"] + "__b4_cooccurrences.csv"))
    assert co["counted"].all() and len(co) == 10
    b1 = [x for x in res if x["rule"] == "b1_trains"]
    assert [x["recording"] for x in b1] == ["M2_aug"]       # no drop_detection_v1 run on the other round-B sets
    assert any(x["rule"] == "gallery" and x["recording"] == "Fig2A" and x["end_idx"] == 5000 for x in res)


def test_cnn_window_scores_come_from_the_step_cache(run):
    res = json.load(open(os.path.join(run["data"], "windows", "resolved_windows.json")))
    cw = [x for x in res if x["rule"] == "cnn_scores"][0]
    sc = pd.read_csv(os.path.join(run["data"], "windows", cw["name"] + "__cnn_window_scores.csv"))
    assert set(sc["variant"]) == {"cnn_fusion3_10min"} and sc["p_interesting"].between(0, 1).all()
    assert ((sc["end_idx"] - sc["start_idx"]) <= 600).all() and sc["start_idx"].min() >= cw["start_idx"]


# ── tables ─────────────────────────────────────────────────────────────────────────────────────────────────

def test_detections_in_windows_flag_surrogates_and_carry_candidates_and_verdicts(run):
    res = json.load(open(os.path.join(run["data"], "windows", "resolved_windows.json")))
    g = [x for x in res if x["rule"] == "gallery" and x["recording"] == "M2_aug"][0]
    det = _csv(run, "detections_in_windows", g["name"] + "__detections.csv")
    assert det["is_surrogate"].any() and (~det["is_surrogate"]).any()
    assert set(det.loc[det["is_surrogate"], "variant"]) == {"drop_detection_v1"}
    assert {"cnn_10min", "cnn_1min", "drop_detection_v1", "seed_search"} <= set(det["family"])
    assert set(det.loc[det["run_kind"] == "seed", "variant"]) == {"seed:hpc_seed"}
    assert ((det["start_s"] < g["end_s"]) & (det["end_s"] > g["start_s"])).all()
    assert det.loc[~det["is_surrogate"] & (det["run_kind"] == "template"), "rule1_chosen"].all()
    cand = _csv(run, "detections_in_windows", g["name"] + "__candidates.csv")
    assert len(cand) and cand["n_agree"].max() >= 5
    ver = _csv(run, "detections_in_windows", g["name"] + "__verdicts.csv")
    assert set(ver["store"]) >= {"annotations"}


def test_drop_v1_all_reads_the_default_runs(run):
    det = _csv(run, "drop_v1_all", "drop_v1_detections.csv")
    runs = _csv(run, "drop_v1_all", "drop_v1_runs.csv")
    assert set(runs["recording_id"]) == set(run["w"].m2r[:2])
    assert len(det) == 2 * len(CENTRES)                       # every event is found by drop_detection_v1; no nulls


def test_queues_carry_strata_verdicts_and_the_seeds(run):
    w = run["w"]
    it = _csv(run, "queues", "queue_items.csv")
    q25 = it[it["queue"] == 25]
    assert list(q25["detection_id"]) == w.q25 and q25["stratum"].notna().all()
    assert q25.iloc[0]["verdict_own"] == "interesting" and q25.iloc[2]["verdict_own"] == "seed"
    q35 = it[it["queue"] == 35].set_index("detection_id")
    assert q35.loc[w.q35[0], "stratum"] == "control" and q35.loc[w.q35[2], "stratum"] == "spike37"
    seeds = _csv(run, "queues", "queue35_seeds.csv").set_index("discovery_run")
    assert seeds.loc[67, "start_idx"] == CENTRES[3] and seeds.loc[67, "recording_id"] == w.m2r[0]
    assert seeds.loc[68, "start_idx"] == CENTRES[7] and seeds.loc[68, "recording_id"] == w.m2r[1]
    q36 = it[it["queue"] == 36]
    assert q36["own_verdict_via_this_queue"].sum() == len(w.q36) - 1
    idx = pd.read_csv(os.path.join(run["data"], "queues", "queue25_windows_index.csv"))
    z = np.load(os.path.join(run["data"], "queues", "queue25_windows.npz"))
    assert len(idx) == 12 and len(z["offsets"]) == 13 and (idx["n"] <= C.CAP_SAMPLES).all()
    r = idx.iloc[0]
    span = r["end"] - r["start"]
    assert r["win_start_idx"] == r["start"] - span and r["win_end_idx"] == r["end"] + span


def test_library_events_get_their_g11_family_and_rec385_its_g05(run):
    ev = _csv(run, "library_events", "events_with_family.csv")
    assert list(ev["g11_family_label"].fillna("-")) == ["F-01", "F-02", "F-01", "F-02", "-"]
    idx = pd.read_csv(os.path.join(run["data"], "library_events", "library_event_windows_index.csv"))
    assert len(idx) == 5
    m = _csv(run, "library_events", "rec385_members_g05.csv")
    assert len(m) == 2 and set(m["g05_family_label"]) == {"F-03"}


def test_hand_labels_all_live_ones_and_ten_windows_per_class(run):
    hl = _csv(run, "hand_labels", "hand_labels.csv")
    assert len(hl) == 30 and set(hl["label"]) == {"interesting", "not_interesting", "artifact"}
    idx = pd.read_csv(os.path.join(run["data"], "hand_labels", "hand_label_windows_index.csv"))
    assert idx["label"].value_counts().to_dict() == {"interesting": 10, "not_interesting": 10, "artifact": 10}
    assert (idx["win_start_idx"] == (idx["start"] - 1800).clip(lower=0)).all()


def test_misses_find_the_accepted_event_no_family_touches(run):
    m = _csv(run, "misses", "misses.csv").set_index("annotation_id")
    assert bool(m.loc[run["w"].miss, "miss"]) is True
    assert not m.loc[run["w"].accepted, "miss"].any()
    idx = pd.read_csv(os.path.join(run["data"], "misses", "miss_windows_index.csv"))
    assert run["w"].miss in set(idx["annotation_id"])


def test_the_drop_motif_store_and_the_plots(run):
    d = os.path.join(run["data"], "drop_motifs_store")
    sub = np.load(os.path.join(d, "store", "motifs_subset.npz"))
    keys = {k.split("__")[0] for k in sub.files}
    assert {"e001", "e002", "e003"} <= keys and len(keys) == 7          # the sequence + 1 oyster, 3 reishi
    ev = pd.read_csv(os.path.join(d, "store", "motifs_subset_events.csv"))
    assert set(ev.loc[ev["in_sequence"], "event_id"]) == {"e001", "e002", "e003"}
    assert os.path.isfile(os.path.join(d, "store", "motifs.csv"))
    assert os.path.isfile(os.path.join(d, "notes", "drop_motifs12b", "FIGURES.md"))
    pm = _csv(run, "existing_plots", "plots_manifest.csv").set_index("path")
    assert pm.loc["Plots/family_search/big.png", "status"].startswith("downscaled")
    from PIL import Image
    with Image.open(os.path.join(run["data"], "existing_plots", "family_search", "big.png")) as im:
        assert im.size[0] == 2000


# ── the pool and the exam ──────────────────────────────────────────────────────────────────────────────────

def test_pool_counts_collapse_sample_and_scores(run):
    counts = _csv(run, "pool", "pool_counts.csv").set_index("recording")
    assert set(counts.index) == {"M2_aug", "LM_fs2", "MJu26a_fs2"}          # never M4, S. commune or L_LM
    used = json.load(open(os.path.join(run["data"], "pool", "pool_tables.json")))
    assert any("MJu26a_fs2 used" in n for n in used["notes"])
    m2 = counts.loc["M2_aug"]
    assert m2["collapsed_ge5"] < m2["n_ge5"]                               # the nested long spans collapsed
    assert m2["collapsed_ge9"] <= m2["n_ge9"]
    s = _csv(run, "pool", "pool_sample_M2_aug.csv")
    assert len(s) == min(30, m2["collapsed_ge5"]) and (s["n_agree"] >= 5).all()
    assert {"amplitude_mv", "swing_mv", "duration_s", "asymmetry", "r4_decision", "overlaps_seed_match"} <= set(s)
    assert (s["r4_source"] == "stub").all() and s["swing_mv"].notna().all()
    seeds = [(run["w"].m2r[0], CENTRES[k], CENTRES[k] + _lens(k)) for k in (3, 13, 23)] + \
            [(run["w"].m2r[1], CENTRES[k], CENTRES[k] + _lens(k)) for k in (6, 8)]
    want = [any(r == sr and a < se and b > ss for sr, ss, se in seeds)
            for r, a, b in zip(s["recording_id"], s["start"], s["end"])]
    assert list(s["overlaps_seed_match"].astype(bool)) == want and any(want)
    z = np.load(os.path.join(run["data"], "pool", "pool_waveforms_M2_aug.npz"))
    assert z["waves"].shape == (len(s), 64) and list(z["event_id"]) == list(s["event_id"])


def test_m4_exam_items_verdicts_window_and_scores(run):
    w = run["w"]
    it = _csv(run, "m4_exam", "exam_items.csv")
    assert list(it["detection_id"]) == w.q36
    assert it["exam_verdict"].notna().sum() == len(w.q36) - 1 and it["verdict_newest_own"].notna().all()
    assert (it["r4_source"] == "stub").all()
    win = glob.glob(os.path.join(run["data"], "m4_exam", "m4_exam__CH0__*.npz"))
    assert len(win) == 1 and _sidecar(win[0])["source_file"] == "M4_aug_concat_fs1.mat"
    cand = pd.read_csv(glob.glob(os.path.join(run["data"], "m4_exam", "*__candidates_r4.csv"))[0])
    assert cand["is_exam_item"].any() and cand["r4_decision"].notna().all()
    idx = pd.read_csv(os.path.join(run["data"], "m4_exam", "exam_item_windows_index.csv"))
    assert len(idx) == len(w.q36)


# ── the zip parts ──────────────────────────────────────────────────────────────────────────────────────────

def test_zip_parts_are_under_the_limit_and_hold_every_file_once(run):
    parts = sorted(glob.glob(os.path.join(run["out"], "wave1_part*.zip")))
    assert len(parts) >= 2
    seen = []
    for p in parts:
        assert os.path.getsize(p) <= MAX_PART_MB * 1e6
        with zipfile.ZipFile(p) as z:
            assert z.testzip() is None
            seen += [n for n in z.namelist() if n.startswith("data/") and not n.startswith("data/_status/")]
    with zipfile.ZipFile(parts[0]) as z:
        assert {"REPORT.md", "MANIFEST.csv", "wave1.log"} <= set(z.namelist())
    on_disk = sorted(os.path.relpath(os.path.join(dp, f), run["out"]).replace("\\", "/")
                     for dp, _dn, fns in os.walk(run["data"]) for f in fns if "_status" not in dp)
    assert sorted(seen) == on_disk
    man = pd.read_csv(os.path.join(run["out"], "MANIFEST.csv"))
    assert sorted(man["file"]) == on_disk


def test_a_file_too_big_for_a_part_is_split(tmp_path):
    class Ctx:
        out = str(tmp_path)
        data_dir = os.path.join(str(tmp_path), "data")
        notes = []

        def warn(self, m):
            self.notes.append(m)

        def log(self, m):
            pass
    ctx = Ctx()
    os.makedirs(os.path.join(ctx.data_dir, "x"))
    rng = np.random.default_rng(0)
    pd.DataFrame({"a": rng.random(20_000), "b": rng.random(20_000)}).to_csv(
        os.path.join(ctx.data_dir, "x", "big.csv"), index=False)
    with open(os.path.join(ctx.data_dir, "x", "blob.npz"), "wb") as fh:
        fh.write(rng.bytes(150_000))
    limit = 100_000
    plan, splits = Z.plan_parts(ctx, limit)
    assert {s["file"] for s in splits} == {"data/x/big.csv", "data/x/blob.npz"}
    for part in plan:
        assert sum(z + Z.overhead(a) for _p, a, z in part) + 1024 <= limit
    pieces = sorted(glob.glob(os.path.join(ctx.data_dir, "x", "big.part*.csv")))
    back = pd.concat([pd.read_csv(p) for p in pieces], ignore_index=True)
    assert len(back) == 20_000
    blob = b"".join(open(p, "rb").read() for p in sorted(glob.glob(os.path.join(ctx.data_dir, "x", "blob.npz.split*"))))
    assert len(blob) == 150_000


def test_rerunning_one_step_keeps_the_others_and_rezips(run):
    mp = pytest.MonkeyPatch()
    mp.setattr(P, "make_r4_scorer", lambda ctx: StubR4())
    try:
        rc = run_wave1.main(["--root", run["root"], "--db", run["w"].db, "--out", run["out"], "--spec", run["spec"],
                             "--only", "meta", "--max-part-mb", str(MAX_PART_MB)])
    finally:
        mp.undo()
    assert rc == 0
    assert _status(run, "pool")["status"] == "ok" and _status(run, "meta")["status"] == "ok"
    assert os.path.isfile(os.path.join(run["data"], "pool", "pool_counts.csv"))
    assert _sha(run["w"].db) == run["sha"]


# ── units of the pool ──────────────────────────────────────────────────────────────────────────────────────

def test_collapse_keeps_the_most_agreed_and_drops_what_it_covers():
    ev = pd.DataFrame({"event_id": [0, 1, 2, 3, 4], "recording_id": 1,
                       "start": [100, 100, 110, 400, 100], "end": [200, 160, 130, 450, 300],
                       "n_agree": [9, 9, 7, 5, 5]})
    kept = P.collapse(ev, {1: 1.0}, {1: 1000})
    # 1 (9, shortest) first; 0 (9) is 60 % covered by it -> dropped; 2 inside 1 -> dropped; 3 free; 4 is 30 % covered
    assert list(kept) == [False, True, False, True, True]


def test_allocate_gives_a_short_level_s_share_to_the_others():
    assert P.allocate({"5-6": 3000, "7-8": 100, "9+": 10}, 2000) == {"5-6": 1890, "7-8": 100, "9+": 10}
    assert P.allocate({"5-6": 1000, "7-8": 100, "9+": 10}, 2000) == {"5-6": 1000, "7-8": 100, "9+": 10}
    assert sum(P.allocate({"a": 700, "b": 700, "c": 700}, 2000).values()) == 2000


def test_the_real_r4_path_on_a_small_side_feature_model(run, tmp_path):
    pytest.importorskip("sklearn")
    joblib = pytest.importorskip("joblib")
    from sklearn.linear_model import RidgeClassifierCV
    from sklearn.preprocessing import StandardScaler
    rng = np.random.default_rng(0)
    X = rng.standard_normal((40, 4))
    y = (X[:, 1] > 0).astype(int)
    model = {"minirocket": None, "use_side": True, "features": "side", "n_features": 0, "seed": 0, "length": 64,
             "pad": 0.25, "side": ["duration_s", "p2p_mv", "noise_mv", "snr"], "platt": None,
             "scaler": StandardScaler().fit(X)}
    model["ridge"] = RidgeClassifierCV().fit(model["scaler"].transform(X), y)
    md = os.path.join(run["root"], "DATA", "derived", "models", "r4test")
    os.makedirs(md, exist_ok=True)
    joblib.dump(model, os.path.join(md, "model.joblib"))
    spec = json.load(open(run["spec"]))
    spec["r4"] = {"manifest": None, "manifest_tracked": None, "model_dir": "DATA/derived/models/r4test", "batch": 3}
    ctx = C.Ctx(root=run["root"], db_path=run["w"].db, out=str(tmp_path / "o"), spec=spec, echo=False)
    try:
        rows = pd.DataFrame({"recording_id": [run["w"].m2r[0]] * 5 + [run["w"].m4[0]],
                             "start": [c for c in CENTRES[:5]] + [CENTRES[2]],
                             "end": [c + 100 for c in CENTRES[:5]] + [CENTRES[2] + 80]})
        out = P.R4(ctx).score(rows)
    finally:
        ctx.close()
    assert out["r4_readable"].all() and np.isfinite(out["r4_decision"]).all()
    assert (out["r4_source"] == "R4").all() and "r4_side_p2p_mv" in out


def test_r4_unavailable_leaves_the_scores_empty_with_the_reason(run, tmp_path):
    spec = json.load(open(run["spec"]))
    spec["r4"] = {"manifest": None, "manifest_tracked": None, "model_dir": "DATA/derived/models/absent"}
    ctx = C.Ctx(root=run["root"], db_path=run["w"].db, out=str(tmp_path / "o"), spec=spec, echo=False)
    try:
        out = P.r4_scores(ctx, pd.DataFrame({"recording_id": [run["w"].m2r[0]], "start": [1000], "end": [1100]}))
    finally:
        ctx.close()
    assert out["r4_decision"].isna().all() and out["r4_source"].iloc[0].startswith("unavailable")
    assert any("R4 scores not computed" in n for n in ctx.notes)


def test_the_table_read_is_the_one_holding_a_sample_else_the_newest(tmp_path):
    class Ctx:
        cache = {}
    tabs = []
    for key, created, sample in (("old_with_sample", "2026-10-18", True), ("newer_plain", "2026-10-30", False),
                                 ("oldest", "2026-10-01", False)):
        d = tmp_path / key
        d.mkdir()
        (d / "meta.json").write_text("{}")
        if sample:
            (d / "sample_seed0").mkdir()
            (d / "sample_seed0" / "sample.parquet").write_text("x")
        tabs.append({"dir": str(d), "key": key, "source_file": "A.mat", "created_at": created})
    ctx = Ctx()
    ctx.cache["candidate_tables"] = tabs
    assert C.newest_table(ctx, "A.mat")["key"] == "old_with_sample"
    ctx.cache["candidate_tables"] = [t for t in tabs if t["key"] != "old_with_sample"]
    assert C.newest_table(ctx, "A.mat")["key"] == "newer_plain"
    assert C.newest_table(ctx, SCOMMUNE) is None
