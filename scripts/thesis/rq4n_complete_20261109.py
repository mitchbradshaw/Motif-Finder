"""The completed 2 Hz detector sweep (9 Nov 2026): audit, counts, geometry index, B5 timing and B11 agreement.

Read-only throughout: the live DB and every scratch.sqlite are opened with ?mode=ro; nothing is imported and
nothing is written under DATA/. Findings: docs/rq_roundA_2/findings/rq4n-complete-2026-11-09.md.

Rerun, in this order, from the repo root with the conda interpreter
(PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe"); each step reads the files the one before wrote:

    python scripts/thesis/rq4n_complete_20261109.py audit
        The 8 Nov audit pointed at DATA/derived/hpc/recovery_20261108_latest (manifest `out` paths remapped):
        spec hashes, runtime and model sha256, return-cache sizes. Writes docs/thesis/data/recovery_latest_20261109/
        {audit.json, settings.csv, pending.csv}. Seconds.
    python scripts/thesis/rq4n_complete_20261109.py counts
        Real/surrogate totals from result.json per recording x setting and per family (candidate_events.family_of),
        plus the Table 10.2 check. Writes docs/thesis/data/ch10_2hz_complete/counts_*.csv, table10_2_check.csv.
    python scripts/thesis/rq4n_complete_20261109.py geom
        Channel-absolute detection spans per task, each source accepted only when its count equals result.json:
        recovery scratch.sqlite (real + surrogate), original scratch.sqlite copies, the DB (sessions 13-15, surrogate
        via runs.surrogate_of_run_id), returned spanset.json (real only), then any PC recomputation (below).
        Writes the index to the parquet named by RQ4N_GEOM (default: a session scratchpad, ~3.4 M rows) and
        geometry_coverage{.json,_by_setting.csv,_tasks.csv}. ~10 s.
    python scripts/thesis/rq4n_complete_20261109.py b5
        b5_map_timing's bin_counts / comodulation / shift_null (3-h bins, 200 shifts, seed 20261103) on the index.
        Writes b5_summary.json, b5_channels.csv. ~1.5 min.
    python scripts/thesis/rq4n_complete_20261109.py b11
        build_events + add_agreement (rule from Settings, NEGATIVE_CONTROLS left out) on the real index, the
        surrogate index, and the real index restricted to the surrogate's (channel, setting) pairs; Chapter 6's saved
        tables under DATA/derived/candidate_events read for comparison. Writes b11_summary.json and
        b11_events_<rec>_real.parquet. ~5 min.
    python scripts/thesis/rq4n_complete_20261109.py tables
        tables.md: the markdown tables of the findings note.

Optional, not used for the 9 Nov numbers: scripts/thesis/rq4n_recompute_missing_20261109.py re-runs the classical
tasks with no returned geometry on this PC (chain_job.run_task into RQ4N_RECOMPUTE, never DATA/); `geom` then picks
them up as `recomputed_pc` when both counts match the cluster's. Run it with <= 4 workers (each ~0.7-1.5 GB), and
rerun once: concurrent tasks of one job race on job.json.tmp (WinError 32) and those tasks need a second pass.
"""
from collections import Counter, defaultdict
import fnmatch
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MAIN = Path("C:/Users/mmebr/Documents/CNN")
sys.path.insert(0, str(ROOT))
from Working.discovery.chain_job import spec_hash
from Working.discovery.spans import absolute_bounds
from Working.discovery import candidate_events as ce
from scripts.thesis.accepted_catalogue import csv_write
from scripts.thesis.audit_recovery_return_20261108 import digest
from scripts.thesis import b5_map_timing as b5

BASE = MAIN / "DATA/derived/hpc/recovery_20261108_latest"
OLD_PREFIX = "DATA/derived/hpc/recovery_20261108/"
NEW_PREFIX = "DATA/derived/hpc/recovery_20261108_latest/"
AUD = ROOT / "docs/thesis/data/recovery_latest_20261109"
OUT = ROOT / "docs/thesis/data/ch10_2hz_complete"
GEOM = Path(os.environ.get("RQ4N_GEOM", "C:/Users/mmebr/AppData/Local/Temp/claude/9d11021b66984e2e/"
                           "55c783cf-2a76-451d-bb08-e09ff21dd7b9/scratchpad/rq4n_geometry.parquet"))
RECOMP = Path(os.environ.get("RQ4N_RECOMPUTE", "C:/Users/mmebr/AppData/Local/Temp/claude/9d11021b66984e2e/"
                             "55c783cf-2a76-451d-bb08-e09ff21dd7b9/scratchpad/recompute"))
DB = "file:C:/Users/mmebr/Documents/CNN/DATA/db/annotations.sqlite?mode=ro"
FILES = {"MJu26a_fs2": "MJu26a_fs2.mat", "SH_fs2": "SH_fs2.mat", "SO_fs2": "SO_fs2.mat"}
SESSIONS = {"MJu26a_fs2": 13, "SH_fs2": 14, "SO_fs2": 15}


def ro(path):
    return sqlite3.connect("file:" + str(path).replace("\\", "/") + "?mode=ro", uri=True)


# ── 1. audit ────────────────────────────────────────────────────────────────

def audit():
    AUD.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((BASE / "manifest.json").read_text())
    bad_runtime = [p for p, h in manifest["runtime_hashes"].items() if digest(BASE / p) != h]
    bad_models = [p for p, h in manifest["model_hashes"].items() if digest(MAIN / p) != h]
    original = json.loads((ROOT / "docs/thesis/data/hpc_return_20261108/audit.json").read_text())
    recovered, bad, bad_spec = [], [], []
    for t in manifest["tasks"]:
        if t["kind"] != "rq4":
            continue
        out = t["out"].replace(OLD_PREFIX, NEW_PREFIX)
        p = MAIN / out / "return" / f"task{t['task']}" / "result.json"
        spec = json.loads((BASE / t["spec_copy"]).read_text())
        if spec_hash(spec) != t["specHash"]:
            bad_spec.append(t["id"])
        row = {**t, "out_latest": out, "state": "missing", "cache_ok": False}
        if p.exists():
            r = json.loads(p.read_text())
            if r["specHash"] != t["specHash"] or r["task"] != t["task"]:
                bad_spec.append(t["id"] + " (result)")
            row.update(state="failed" if r.get("error") else "complete" if r.get("complete") else "partial",
                       error=r.get("error"), elapsed_s=r.get("elapsedS"), host=r.get("host"),
                       result=str(p.relative_to(MAIN)).replace("\\", "/"), real=(r.get("run") or {}).get("detections"),
                       null=(r.get("draws") or {}).get("detections"),
                       scratch=(MAIN / out / "work" / f"task{t['task']}" / "scratch.sqlite").exists())
            if row["state"] == "complete":
                for cache in r.get("cache", []):
                    folder = (p.parent / cache["path"]).resolve()
                    assert folder.is_relative_to(p.parent.resolve()), str(folder)
                    size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) if folder.is_dir() else -1
                    if size != cache["bytes"]:
                        bad.append({"task": t["id"], "cache": str(folder), "expected": cache["bytes"], "bytes": size})
                row["cache_ok"] = not any(b["task"] == t["id"] for b in bad)
        recovered.append(row)
    lookup = {(r["original_out"], r["task"]): r for r in recovered}
    all_tasks = []
    for old in original["rq4"]:
        new = lookup.get((old["out"].replace("\\", "/"), old["task"]))
        row = dict(old, result=(old.get("result") or "").replace("\\", "/") or None, recovered=False)
        if new:
            row["recovery_state"] = new["state"]
            if new["state"] == "complete" and new["cache_ok"]:
                row.update(state="complete", result=new["result"], run_detections=new["real"],
                           null_detections=new["null"], recovered=True, out_latest=new["out_latest"])
        all_tasks.append(row)
    assert len(all_tasks) == 1014 and len({(r["spec"], r["task"]) for r in all_tasks}) == 1014
    grouped = defaultdict(list)
    for r in all_tasks:
        grouped[(r["recording"], r["setting"])].append(r)
    settings = []
    for (rec, setting), rr in sorted(grouped.items()):
        done = [r for r in rr if r["state"] == "complete"]
        settings.append({"recording": rec, "setting": setting, "family": ce.family_of(setting),
                         "complete": len(done), "total": len(rr), "whole": len(done) == len(rr),
                         "recovered_tasks": sum(r["recovered"] for r in rr),
                         "real_detections": sum(r["run_detections"] or 0 for r in done),
                         "null_detections": sum(sum(r["null_detections"] or []) for r in done)})
    summary = {"bundle": str(BASE.relative_to(MAIN)),
               "runtime_files_checked": len(manifest["runtime_hashes"]), "runtime_hash_mismatches": bad_runtime,
               "model_files_checked": len(manifest["model_hashes"]), "model_hash_mismatches": bad_models,
               "spec_hash_mismatches": bad_spec, "invalid_return_caches": bad,
               "recovery_tasks": len(recovered),
               "recovery_by_pack": {p: dict(Counter(r["state"] for r in recovered if r["pack"] == p))
                                    for p in manifest["packs"] if p != "seed"},
               "recovery_with_scratch": sum(bool(r.get("scratch")) for r in recovered),
               "overall_tasks": dict(Counter(r["state"] for r in all_tasks)),
               "whole_settings": sum(s["whole"] for s in settings), "settings": len(settings),
               "by_recording": {rec: {"complete": sum(r["state"] == "complete" for r in all_tasks if r["recording"] == rec),
                                      "total": sum(r["recording"] == rec for r in all_tasks),
                                      "whole_settings": sum(s["whole"] for s in settings if s["recording"] == rec),
                                      "settings": sum(s["recording"] == rec for s in settings)}
                                for rec in sorted({r["recording"] for r in all_tasks})},
               "seed_half": "unchanged: 64 channels x 200 draws (docs/thesis/data/recovery_return_20261108/seed_summary.json)"}
    (AUD / "audit.json").write_text(json.dumps({"summary": summary, "recovery_tasks": recovered,
                                                "all_tasks": all_tasks, "settings": settings}, indent=1))
    csv_write(AUD / "settings.csv", settings)
    csv_write(AUD / "pending.csv", [r for r in all_tasks if r["state"] != "complete"] or
              [{"recording": "", "setting": "", "task": "", "state": "none pending"}])
    print(json.dumps(summary, indent=1), flush=True)


# ── 3. geometry index ───────────────────────────────────────────────────────

def _scratch_geom(path, n_real, n_sur):
    """(real starts, ends), [surrogate (starts, ends)], recording_id from one scratch.sqlite; absolute bounds.
    A scratch that holds a rerun has several real runs: the newest completed one whose count equals result.json's
    is taken, and the newest completed surrogate of it whose count equals the draw's."""
    c = ro(path)
    try:
        runs = c.execute("SELECT id, recording_id, span_start, surrogate_of_run_id, status FROM runs ORDER BY id").fetchall()
        cnt = dict(c.execute("SELECT run_id, COUNT(*) FROM detections GROUP BY run_id").fetchall())

        def det(run_id, span0):
            rows = c.execute("SELECT start_idx, end_idx FROM detections WHERE run_id = ? ORDER BY start_idx",
                             (run_id,)).fetchall()
            ab = [absolute_bounds(s, e, span0) for s, e in rows]
            return np.array([a for a, _ in ab], np.int64), np.array([b for _, b in ab], np.int64)
        real = [r for r in runs if r[3] is None and r[4] == "completed" and cnt.get(r[0], 0) == n_real]
        if not real:
            return None
        rid, rec, s0 = real[-1][:3]
        sur = [r for r in runs if r[3] == rid and r[4] == "completed" and n_sur and cnt.get(r[0], 0) == n_sur[0]]
        return det(rid, s0), ([det(sur[-1][0], sur[-1][2])] if sur else []), int(rec), len(real), len(sur)
    finally:
        c.close()


def _cache_geom(result_path, res, target):
    real_keys = set(target["prefixHashes"])
    for entry in sorted(res.get("cache", []), key=lambda r: r["step"], reverse=True):
        if entry["prefixHash"] not in real_keys:
            continue
        folder = (result_path.parent / entry["path"]).resolve()
        if not folder.is_relative_to(result_path.parent.resolve()):
            raise ValueError("Cache path escape")
        p = folder / "spanset.json"
        if p.exists():
            g = json.loads(p.read_text())
            return np.asarray(g["starts"], np.int64), np.asarray(g["ends"], np.int64)
    return None


def _db_runs(conn):
    """{(recording_id, setting): (real run id, span_start, surrogate run id or None, surrogate span_start)}."""
    out = {}
    for rec, sess in SESSIONS.items():
        rows = conn.execute(
            "SELECT r.id, r.recording_id, dr.template_name, r.span_start, r.span_end FROM runs r "
            "JOIN recordings rec ON rec.id = r.recording_id "
            "JOIN discovery_runs dr ON dr.run_group_id = r.run_group_id AND dr.kind = 'template' "
            "AND dr.superseded_at IS NULL AND dr.removed_at IS NULL "
            "WHERE rec.source_file = ? AND r.status = 'completed' AND r.superseded_at IS NULL "
            "AND r.surrogate_of_run_id IS NULL ORDER BY r.id", (FILES[rec],)).fetchall()
        best = {}
        for rid, recid, tpl, s0, s1 in rows:
            rank = (int(s1) - int(s0), int(rid))
            k = (int(recid), tpl)
            if k not in best or rank > best[k][0]:
                best[k] = (rank, int(rid), int(s0 or 0))
        for k, (_, rid, s0) in best.items():
            sur = conn.execute("SELECT MIN(id), span_start FROM runs WHERE surrogate_of_run_id = ? "
                               "AND status = 'completed'", (rid,)).fetchone()
            out[k] = (rid, s0, sur[0], int(sur[1] or 0) if sur[0] is not None else None)
    return out


def _db_det(conn, run_id, s0):
    rows = conn.execute("SELECT start_idx, end_idx FROM detections WHERE run_id = ? ORDER BY start_idx",
                        (int(run_id),)).fetchall()
    ab = [absolute_bounds(s, e, s0) for s, e in rows]
    return np.array([a for a, _ in ab], np.int64), np.array([b for _, b in ab], np.int64)


def _original_scratches(row):
    out = MAIN / row["out"]
    name = out.name
    cands = [out / "work" / f"task{row['task']}" / "scratch.sqlite",
             out.parent / out.parent.name / name / "work" / f"task{row['task']}" / "scratch.sqlite"]
    return [p for p in cands if p.exists()]


def geom():
    t0 = time.time()
    a = json.loads((AUD / "audit.json").read_text())
    conn = sqlite3.connect(DB, uri=True)
    dbr = _db_runs(conn)
    rows, cover = [], []
    for row in a["all_tasks"]:
        if row["state"] != "complete":
            cover.append({**{k: row[k] for k in ("recording", "setting", "task", "channel")}, "real_src": None,
                          "sur_src": None, "note": "not complete"})
            continue
        result_path = MAIN / row["result"]
        res = json.loads(result_path.read_text())
        spec = json.loads((MAIN / row["spec"]).read_text())
        assert spec_hash(spec) == res["specHash"]
        target = spec["targets"][row["task"]]
        recid = int(target["recordingId"])
        n_real = (res.get("run") or {}).get("detections")
        n_sur = list((res.get("draws") or {}).get("detections") or [])
        real = sur = None
        real_src = sur_src = None
        notes = []
        scratches = []
        if row.get("recovered"):
            scratches = [MAIN / row["out_latest"] / "work" / f"task{row['task']}" / "scratch.sqlite"]
        else:
            scratches = _original_scratches(row)
        for sp in scratches:
            if not sp.exists():
                continue
            g = _scratch_geom(sp, n_real, n_sur)
            if g is None:
                notes.append(f"{sp.parent.name}: no real run with {n_real} detections")
                continue
            (rs, re_), surs, rr, nreal_runs, nsur_runs = g
            if rr != recid:
                notes.append("scratch recording mismatch")
                continue
            if nreal_runs > 1 or nsur_runs > 1:
                notes.append(f"rerun in scratch: {nreal_runs} matching real, {nsur_runs} matching surrogate runs; newest taken")
            if real is None:
                real, real_src = (rs, re_), "scratch_latest" if row.get("recovered") else "scratch_original"
            if surs and sur is None:
                sur, sur_src = surs[0], real_src
            elif not surs and n_sur:
                notes.append(f"scratch has no surrogate run with {n_sur[0]} detections")
        k = (recid, row["setting"])
        if (real is None or sur is None) and k in dbr:
            rid, s0, sid, ss0 = dbr[k]
            if real is None:
                g = _db_det(conn, rid, s0)
                if len(g[0]) == n_real:
                    real, real_src = g, "db"
                else:
                    notes.append(f"db real {len(g[0])} != result {n_real}")
            if sur is None and sid is not None:
                g = _db_det(conn, sid, ss0)
                if [len(g[0])] == n_sur:
                    sur, sur_src = g, "db"
                else:
                    notes.append(f"db surrogate {len(g[0])} != result {n_sur}")
        if real is None:
            g = _cache_geom(result_path, res, target)
            if g is not None and len(g[0]) == n_real:
                real, real_src = g, "return_cache_spanset"
            elif g is not None:
                notes.append(f"spanset {len(g[0])} != result {n_real}")
        if real is None or sur is None:
            # recomputed on this PC by rq4n_recompute_missing_20261109.py (chain_job.run_task, scratchpad only);
            # accepted only where both counts equal the cluster's result.json
            sp = RECOMP / row["recording"] / Path(row["out"]).name / "work" / f"task{row['task']}" / "scratch.sqlite"
            if sp.exists():
                g = _scratch_geom(sp, n_real, n_sur)
                if g is None:
                    notes.append(f"recomputed: no real run with {n_real} detections")
                elif g[2] == recid and not g[1]:
                    notes.append("recomputed: surrogate count differs from result.json; task not accepted")
                elif g[2] == recid:          # real AND surrogate counts equal the cluster's
                    if real is None:
                        real, real_src = g[0], "recomputed_pc"
                    if sur is None:
                        sur, sur_src = g[1][0], "recomputed_pc"
        for kind, gg in (("real", real), ("surrogate", sur)):
            if gg is None:
                continue
            rows.append(pd.DataFrame({"recording": row["recording"], "setting": row["setting"], "task": row["task"],
                                      "recording_id": recid, "kind": kind, "start": gg[0], "end": gg[1]}))
        cover.append({"recording": row["recording"], "setting": row["setting"], "task": row["task"],
                      "channel": row["channel"], "recording_id": recid, "recovered": bool(row.get("recovered")),
                      "result_real": n_real, "result_surrogate": n_sur[0] if n_sur else None,
                      "real_src": real_src, "sur_src": sur_src, "note": "; ".join(notes)})
    conn.close()
    df = pd.concat(rows, ignore_index=True)
    for c in ("recording", "setting", "kind"):
        df[c] = df[c].astype("category")
    GEOM.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(GEOM, index=False)
    OUT.mkdir(parents=True, exist_ok=True)
    cov = pd.DataFrame(cover)
    cov.to_csv(OUT / "geometry_coverage_tasks.csv", index=False)
    by = cov.groupby(["recording", "setting"]).agg(tasks=("task", "size"), real=("real_src", lambda s: s.notna().sum()),
                                                   surrogate=("sur_src", lambda s: s.notna().sum())).reset_index()
    by.to_csv(OUT / "geometry_coverage_by_setting.csv", index=False)
    summ = {"tasks": len(cov), "real_geometry": int(cov["real_src"].notna().sum()),
            "surrogate_geometry": int(cov["sur_src"].notna().sum()),
            "real_by_source": cov["real_src"].value_counts().to_dict(),
            "surrogate_by_source": cov["sur_src"].value_counts().to_dict(),
            "settings_whole_real": int((by["real"] == by["tasks"]).sum()),
            "settings_whole_surrogate": int((by["surrogate"] == by["tasks"]).sum()),
            "settings_some_surrogate": int((by["surrogate"] > 0).sum()),
            "by_recording": {r: {"real": int(g["real_src"].notna().sum()), "surrogate": int(g["sur_src"].notna().sum()),
                                 "tasks": len(g)} for r, g in cov.groupby("recording")},
            "tasks_with_notes": int((cov["note"].fillna("") != "").sum()),
            "geometry_rows": len(df), "parquet": str(GEOM), "seconds": round(time.time() - t0, 1)}
    (OUT / "geometry_coverage.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


# ── 2. counts ───────────────────────────────────────────────────────────────

def counts():
    a = json.loads((AUD / "audit.json").read_text())
    t = pd.DataFrame([r for r in a["all_tasks"] if r["state"] == "complete"])
    t["real"] = t["run_detections"].fillna(0).astype(int)
    t["sur"] = t["null_detections"].map(lambda v: sum(v or []))
    t["family"] = t["setting"].map(ce.family_of)
    by_set = t.groupby(["recording", "setting", "family"]).agg(
        channels=("task", "size"), real=("real", "sum"), surrogate=("sur", "sum"),
        channels_with_real=("real", lambda s: int((s > 0).sum())),
        channels_with_surrogate=("sur", lambda s: int((s > 0).sum()))).reset_index()
    OUT.mkdir(parents=True, exist_ok=True)
    by_set.to_csv(OUT / "counts_by_setting.csv", index=False)
    fam = by_set.groupby(["family", "recording"]).agg(settings=("setting", "size"), real=("real", "sum"),
                                                      surrogate=("surrogate", "sum")).reset_index()
    fam.to_csv(OUT / "counts_by_family.csv", index=False)
    wide = fam.pivot(index="family", columns="recording", values=["real", "surrogate"])
    wide.columns = [f"{rec}_{k}" for k, rec in wide.columns]
    wide["settings"] = fam.groupby("family")["settings"].max()
    order = [f"{r}_{k}" for r in FILES for k in ("real", "surrogate")]
    wide = wide[["settings"] + order]
    wide.to_csv(OUT / "counts_by_family_wide.csv")
    checks = {"drop_detection_v1": [(463, 33), (21, 0), (28, 0)],
              "OASIS_Deconvolution": [(127429, 2007), (20095, 353), (25556, 364)],
              "OASIS_Deconvolution__threshold_5": [(2453, 68), (859, 19), (400, 11)],
              "wavelet_encoded": [(1883, 38714), (21, 7241), (12, 7286)]}
    out = []
    for s, exp in checks.items():
        for rec, (er, es) in zip(FILES, exp):
            g = by_set[(by_set.recording == rec) & (by_set.setting == s)].iloc[0]
            out.append({"setting": s, "recording": rec, "real": int(g.real), "surrogate": int(g.surrogate),
                        "table_real": er, "table_surrogate": es, "match": (int(g.real), int(g.surrogate)) == (er, es)})
    pd.DataFrame(out).to_csv(OUT / "table10_2_check.csv", index=False)
    print(pd.DataFrame(out).to_string())
    print(wide.to_string())


# ── 4. B5 ───────────────────────────────────────────────────────────────────

def _load_geom():
    df = pd.read_parquet(GEOM)
    for c in ("recording", "setting", "kind"):
        df[c] = df[c].astype(str)
    return df


def b5_all(draws=200, seed=20261103):
    df = _load_geom()
    conn = sqlite3.connect(DB, uri=True)
    cov = pd.read_csv(OUT / "geometry_coverage_tasks.csv")
    results = {}
    for rec, sf in FILES.items():
        chans = conn.execute("SELECT id, channel, fs, n_samples FROM recordings WHERE source_file = ? ORDER BY channel",
                             (sf,)).fetchall()
        rng = np.random.default_rng(seed)
        d = df[df.recording == rec]
        cr = cov[cov.recording == rec]
        per, tot_r, tot_s, tot_rs = [], [], [], []
        silent = []
        for rid, ch, fs, n in chans:
            c = cr[cr.recording_id == rid]
            real_sets = sorted(c.loc[c.real_src.notna(), "setting"])
            sur_sets = sorted(c.loc[c.sur_src.notna() & c.real_src.notna(), "setting"])
            if len(real_sets) < 2:
                continue
            g = d[d.recording_id == rid]
            def M(sets, kind):
                return np.array([b5.bin_counts(g.loc[(g.setting == s) & (g.kind == kind), "start"].to_numpy(), n, fs, 3.0)
                                 for s in sets])
            R = M(real_sets, "real")
            row = {"recording": rec, "recording_id": int(rid), "channel": int(ch), "settings_real": len(real_sets),
                   "bins": R.shape[1]}
            c_r = b5.comodulation(R)
            nr = b5.shift_null(R, draws, rng)
            row.update(real_C=c_r, real_shift_mean=float(np.nanmean(nr)), real_p=(1 + int(np.sum(nr >= c_r))) / (draws + 1),
                       silent_bins_real=int((R.sum(axis=0) == 0).sum()),
                       silent_bins_real_excl_1min=int((R[[not fnmatch.fnmatchcase(s, "cnn_*_1min") for s in real_sets]]
                                                       .sum(axis=0) == 0).sum()),
                       min_bin_total_real=int(R.sum(axis=0).min()))
            tot_r.append(b5._zrows(R).mean(axis=0))
            row["settings_sur"] = len(sur_sets)
            if len(sur_sets) >= 2:
                S = M(sur_sets, "surrogate")
                Rs = M(sur_sets, "real")
                c_s, c_rs = b5.comodulation(S), b5.comodulation(Rs)
                ns = b5.shift_null(S, draws, rng)
                row.update(sur_C=c_s, sur_shift_mean=float(np.nanmean(ns)),
                           sur_p=(1 + int(np.sum(ns >= c_s))) / (draws + 1), real_C_same_settings=c_rs,
                           silent_bins_sur=int((S.sum(axis=0) == 0).sum()))
                tot_s.append(b5._zrows(S).mean(axis=0))
                tot_rs.append(b5._zrows(Rs).mean(axis=0))
            per.append(row)
        bands = {}
        for name, T in (("real", tot_r), ("real_same_settings", tot_rs), ("surrogate", tot_s)):
            T = np.array(T)
            if len(T) >= 2:
                cc = b5.comodulation(T)
                nl = b5.shift_null(T, draws, rng)
                bands[name] = {"C": cc, "shift_mean": float(np.nanmean(nl)), "p": (1 + int(np.sum(nl >= cc))) / (draws + 1),
                               "channels": len(T)}
        P = pd.DataFrame(per)
        results[rec] = {"channels": per, "bands": bands,
                        "median_real_C": float(P.real_C.median()), "median_real_shift": float(P.real_shift_mean.median()),
                        "channels_real_beyond_shift": int((P.real_p < 0.05).sum()), "n_channels": len(P),
                        "median_settings_real": float(P.settings_real.median()),
                        "median_sur_C": float(P.sur_C.median()) if "sur_C" in P else None,
                        "median_real_C_same_settings": float(P.real_C_same_settings.median()) if "sur_C" in P else None,
                        "channels_sur_beyond_shift": int((P.sur_p < 0.05).sum()) if "sur_p" in P else None,
                        "channels_with_sur": int(P.sur_C.notna().sum()) if "sur_C" in P else 0,
                        "settings_sur_range": [int(P.settings_sur.min()), int(P.settings_sur.max())],
                        "channels_with_silent_bin_real": int((P.silent_bins_real > 0).sum()),
                        "channels_with_silent_bin_real_excl_1min": int((P.silent_bins_real_excl_1min > 0).sum()),
                        "timecourse_real": np.median(np.array(tot_r), axis=0).tolist()}
        print(rec, json.dumps({k: v for k, v in results[rec].items() if k not in ("channels", "timecourse_real")},
                              default=float))
    conn.close()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "b5_summary.json").write_text(json.dumps(results, indent=1, default=float))
    pd.DataFrame([r for v in results.values() for r in v["channels"]]).to_csv(OUT / "b5_channels.csv", index=False)


# ── 5. B11 ──────────────────────────────────────────────────────────────────

LEVELS = ["1-2", "3-4", "5-6", "7-8", "9+"]


def _levels(n_agree):
    n = np.asarray(n_agree)
    bins = [((n >= 1) & (n <= 2)), ((n >= 3) & (n <= 4)), ((n >= 5) & (n <= 6)), ((n >= 7) & (n <= 8)), (n >= 9)]
    return {lv: int(b.sum()) for lv, b in zip(LEVELS, bins)}


def _census(det, rule, label):
    t0 = time.time()
    det = det[det["end"] > det["start"]].copy()
    det["detection_id"] = np.arange(len(det), dtype=np.int64)
    det["run_id"] = det["recording_id"]
    ev, mem = ce.build_events(det[["detection_id", "run_id", "recording_id", "variant", "start", "end"]], rule=rule)
    ev = ce.add_agreement(ev, det)
    lv = _levels(ev["n_agree"])
    fams = sorted(det["variant"].map(ce.family_of).unique())
    out = {"label": label, "detections": int(len(det)), "candidates": int(len(ev)), "levels": lv,
           "levels_pct": {k: round(100 * v / max(1, len(ev)), 2) for k, v in lv.items()},
           "families_available": len(fams), "families": fams, "settings": int(det["variant"].nunique()),
           "median_n_agree": float(ev["n_agree"].median()) if len(ev) else None,
           "seconds": round(time.time() - t0, 1)}
    print(label, json.dumps({k: v for k, v in out.items() if k != "families"}), flush=True)
    return out, ev


def b11():
    df = _load_geom()
    df = df[~df.setting.map(lambda s: any(fnmatch.fnmatchcase(s, p) for p in ce.NEGATIVE_CONTROLS))]
    df = df.rename(columns={"setting": "variant"})
    conn = sqlite3.connect(DB, uri=True)
    rule = ce.rule_from_settings(conn)
    conn.close()
    res = {"rule": rule, "recordings": {}}
    for rec in FILES:
        d = df[df.recording == rec]
        real = d[d.kind == "real"]
        sur = d[d.kind == "surrogate"]
        pairs = set(zip(sur.recording_id, sur.variant))
        real_same = real[[p in pairs for p in zip(real.recording_id, real.variant)]]
        r = {}
        r["real_all"], ev = _census(real, rule, f"{rec} real, all settings")
        ev.to_parquet(OUT / f"b11_events_{rec}_real.parquet", index=False)
        r["real_same_as_surrogate"], _ = _census(real_same, rule, f"{rec} real, surrogate settings")
        r["surrogate"], _ = _census(sur, rule, f"{rec} surrogate")
        r["surrogate_pairs"] = len(pairs)
        res["recordings"][rec] = r
        (OUT / "b11_summary.json").write_text(json.dumps(res, indent=1, default=float))
    # Chapter 6's saved tables, for comparison
    ch6 = {}
    for meta in sorted((MAIN / "DATA/derived/candidate_events").glob("*/meta.json")):
        try:
            m = json.loads(meta.read_text())
            ev = pd.read_parquet(meta.parent / "events.parquet", columns=["n_agree"])
            ch6[meta.parent.name] = {"source_file": m.get("source_file"), "candidates": len(ev),
                                     "families": len(m.get("families", [])), "levels": _levels(ev["n_agree"]),
                                     "created_at": m.get("created_at")}
        except Exception as e:  # noqa: BLE001 - reported, not hidden
            ch6[meta.parent.name] = {"error": repr(e)}
    res["chapter6_tables"] = ch6
    (OUT / "b11_summary.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(ch6, indent=1))


def tables():
    """Markdown tables of everything above, for the findings note (printed; written to tables.md)."""
    L = []
    w = pd.read_csv(OUT / "counts_by_family_wide.csv")
    L += ["| family | settings | " + " | ".join(f"{r} real | {r} sur." for r in FILES) + " |",
          "|---|---:|" + "---:|" * 6]
    for _, r in w.iterrows():
        L.append(f"| {r.family} | {r.settings} | " + " | ".join(f"{int(r[f'{x}_real']):,} | {int(r[f'{x}_surrogate']):,}"
                                                              for x in FILES) + " |")
    tot = w.sum(numeric_only=True)
    L.append("| **all** | " + f"{int(tot.settings)} | " + " | ".join(f"{int(tot[f'{x}_real']):,} | {int(tot[f'{x}_surrogate']):,}"
                                                                     for x in FILES) + " |")
    L.append("")
    cov = json.loads((OUT / "geometry_coverage.json").read_text())
    L.append("Geometry coverage: " + json.dumps({k: cov[k] for k in ("tasks", "real_geometry", "surrogate_geometry",
                                                                       "real_by_source", "surrogate_by_source",
                                                                       "settings_whole_real", "settings_whole_surrogate",
                                                                       "by_recording")}))
    L.append("")
    b = json.loads((OUT / "b5_summary.json").read_text())
    L += ["| recording | channels | settings/channel (median) | real C median | shift mean | channels p<0.05 | "
          "surrogate settings | surrogate C median | real C same settings | bands real C (p) | bands surrogate C (p) |",
          "|---|---:|---:|---:|---:|---:|---|---:|---:|---|---|"]
    for rec, r in b.items():
        bd = r["bands"]
        L.append(f"| {rec} | {r['n_channels']} | {r['median_settings_real']:.0f} | {r['median_real_C']:.2f} | "
                 f"{r['median_real_shift']:.2f} | {r['channels_real_beyond_shift']} | "
                 f"{r['settings_sur_range'][0]}–{r['settings_sur_range'][1]} | {r['median_sur_C']:.2f} | "
                 f"{r['median_real_C_same_settings']:.2f} | {bd['real']['C']:.2f} ({bd['real']['p']:.3f}) | "
                 f"{bd['surrogate']['C']:.2f} ({bd['surrogate']['p']:.3f}) |")
    L.append("")
    e = json.loads((OUT / "b11_summary.json").read_text())
    L += ["| recording | geometry | settings | families | detections | candidates | " + " | ".join(LEVELS) + " |",
          "|---|---|---:|---:|---:|---:|" + "---:|" * 5]
    for rec, r in e["recordings"].items():
        for k, lab in (("real_all", "real, all settings"), ("real_same_as_surrogate", "real, surrogate's settings"),
                       ("surrogate", "surrogate")):
            x = r[k]
            L.append(f"| {rec} | {lab} | {x['settings']} | {x['families_available']} | {x['detections']:,} | "
                     f"{x['candidates']:,} | " + " | ".join(f"{x['levels_pct'][lv]:.1f} %" for lv in LEVELS) + " |")
    L.append("")
    L += ["| recording | 5+ real (like for like) | 5+ surrogate | 7+ real (like for like) | 7+ surrogate | "
          "7+ real, all settings | 9+ real, all settings |", "|---|---:|---:|---:|---:|---:|---:|"]
    for rec, r in e["recordings"].items():
        def share(x, lvs):
            return 100 * sum(x["levels"][lv] for lv in lvs) / max(1, x["candidates"])
        a, s_, ra = r["real_same_as_surrogate"], r["surrogate"], r["real_all"]
        L.append(f"| {rec} | {share(a, LEVELS[2:]):.1f} % | {share(s_, LEVELS[2:]):.1f} % | {share(a, LEVELS[3:]):.2f} % | "
                 f"{share(s_, LEVELS[3:]):.2f} % | {share(ra, LEVELS[3:]):.1f} % | {share(ra, LEVELS[4:]):.2f} % |")
    L.append("")
    cb = pd.read_csv(OUT / "geometry_coverage_by_setting.csv")
    cb["family"] = cb["setting"].map(ce.family_of)
    g = cb.groupby(["recording", "family"])[["tasks", "real", "surrogate"]].sum().reset_index()
    g = g[(g.real < g.tasks) | (g.surrogate < g.tasks)]
    L += ["| recording | family | tasks | real geometry | surrogate geometry |", "|---|---|---:|---:|---:|"]
    L += [f"| {x.recording} | {x.family} | {x.tasks} | {x.real} | {x.surrogate} |" for x in g.itertuples()]
    L.append("")
    L += ["| Chapter 6 table | candidates | families | " + " | ".join(LEVELS) + " |", "|---|---:|---:|" + "---:|" * 5]
    for k, x in e.get("chapter6_tables", {}).items():
        n = max(1, x["candidates"])
        L.append(f"| {x['source_file']} | {x['candidates']:,} | {x['families']} | "
                 + " | ".join(f"{100 * x['levels'][lv] / n:.1f} %" for lv in LEVELS) + " |")
    s = "\n".join(L)
    (OUT / "tables.md").write_text(s, encoding="utf-8")
    print(s)


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "audit"
    {"audit": audit, "geom": geom, "counts": counts, "b5": b5_all, "b11": b11, "tables": tables}[stage]()
