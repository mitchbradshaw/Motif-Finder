"""
ledger_checks.py — recompute, read-only, the numbers the thesis numbers ledger (docs/thesis/numbers_ledger.md)
marks *verified*. Opens DATA/db/annotations.sqlite with mode=ro; reads machine-written result files; writes one
JSON, docs/thesis/data/ledger_checks.json. Never reads anything on M4_aug_concat_fs1 (recordings 49-64) and never
opens Review queue 35 or its key.

    "/c/ProgramData/anaconda3/python.exe" scripts/thesis/ledger_checks.py
"""
from __future__ import annotations

import glob
import json
import os
import sqlite3
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
DB = os.path.join(ROOT, "DATA", "db", "annotations.sqlite").replace("\\", "/")
OUT = os.path.join(ROOT, "docs", "thesis", "data", "ledger_checks.json")
HELD_OUT_FILE = "M4_aug_concat_fs1.mat"
#: a cut-off for "labels as of the poster": the RQ2 blind panel (queue 35) was built on 2026-10-26 and may be being
#: judged now; nothing created on or after this instant is counted, so the panel is never read.
LABEL_CUTOFF = "2026-10-26T00:00:00"


def ro():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def q(c, sql, args=()):
    return [dict(r) for r in c.execute(sql, args).fetchall()]


def recordings(c):
    rows = q(c, "SELECT r.id, r.source_file, r.channel, r.fs, r.n_samples, r.units, r.active, d.species "
                "FROM recordings r LEFT JOIN datasets d ON d.source_file = r.source_file "
                "WHERE r.source_file != ?", (HELD_OUT_FILE,))
    files = {}
    for r in rows:
        f = files.setdefault(r["source_file"], {"channels": 0, "fs": r["fs"], "hours": r["n_samples"] / r["fs"] / 3600,
                                               "units": r["units"], "active": r["active"], "species": r["species"]})
        f["channels"] += 1
    active = {k: v for k, v in files.items() if v["active"]}
    return {"files_excluding_M4": files, "n_files_excluding_M4": len(files), "n_active_files_excluding_M4": len(active),
            "n_active_channels_excluding_M4": sum(v["channels"] for v in active.values()),
            "species_declared": sorted({v["species"] for v in files.values() if v["species"]}),
            "active_channel_hours_excluding_M4": round(sum(v["channels"] * v["hours"] for v in active.values()), 1),
            "note": "M4_aug_concat_fs1 (the held-out exam) is left out of every figure here; add 1 file / 16 channels "
                    "for the corpus as registered"}


def human_labels(c):
    """Every human judgement in the database (own looks only), by store, created before LABEL_CUTOFF, M4 left out."""
    ann = q(c, "SELECT a.source, a.verdict, COUNT(*) n FROM annotations a JOIN recordings r ON r.id = a.recording_id "
               "WHERE r.source_file != ? AND a.deleted_at IS NULL AND a.created_at < ? GROUP BY 1, 2 ORDER BY 1, 2",
            (HELD_OUT_FILE, LABEL_CUTOFF))
    adj = q(c, "SELECT a.verdict, (a.carried_from IS NULL) own, COUNT(*) n FROM adjudications a "
               "JOIN detections d ON d.id = a.detection_id JOIN runs r ON r.id = d.run_id "
               "JOIN recordings rec ON rec.id = r.recording_id "
               "WHERE rec.source_file != ? AND a.created_at < ? GROUP BY 1, 2 ORDER BY 2, 1",
            (HELD_OUT_FILE, LABEL_CUTOFF))
    wv = q(c, "SELECT w.verdict, COUNT(*) n FROM window_verdicts w JOIN window_sets s ON s.id = w.window_set_id "
              "LEFT JOIN recordings r ON r.id = s.recording_id "
              "WHERE (r.source_file IS NULL OR r.source_file != ?) AND w.created_at < ? GROUP BY 1",
           (HELD_OUT_FILE, LABEL_CUTOFF))
    n_ann = sum(r["n"] for r in ann)
    n_adj_own = sum(r["n"] for r in adj if r["own"])
    n_adj_carried = sum(r["n"] for r in adj if not r["own"])
    n_wv = sum(r["n"] for r in wv)
    by_source = {}
    for r in ann:
        by_source[r["source"]] = by_source.get(r["source"], 0) + r["n"]
    return {"cutoff": LABEL_CUTOFF, "annotations_by_source_verdict": ann, "annotations_by_source": by_source,
            "annotations_total": n_ann, "adjudications_own": n_adj_own, "adjudications_carried_copies": n_adj_carried,
            "adjudications_by_verdict": adj, "window_verdicts": n_wv,
            "total_own_human_judgements": n_ann + n_adj_own + n_wv,
            "total_if_carried_copies_counted": n_ann + n_adj_own + n_adj_carried + n_wv}


def run_group_verdicts(c, groups):
    out = {}
    for g in groups:
        rows = q(c, "SELECT a.verdict, (a.carried_from IS NULL) own, COUNT(*) n FROM runs r "
                    "JOIN detections d ON d.run_id = r.id JOIN adjudications a ON a.detection_id = d.id "
                    "WHERE r.run_group_id = ? AND r.surrogate_of_run_id IS NULL GROUP BY 1, 2", (g,))
        n_det = q(c, "SELECT COUNT(d.id) n FROM runs r JOIN detections d ON d.run_id = r.id "
                     "WHERE r.run_group_id = ? AND r.surrogate_of_run_id IS NULL", (g,))[0]["n"]
        own = {r["verdict"]: r["n"] for r in rows if r["own"]}
        acc = own.get("interesting", 0) + own.get("seed", 0)
        no = own.get("not_interesting", 0)
        out[str(g)] = {"detections": n_det, "own": own, "carried": {r["verdict"]: r["n"] for r in rows if not r["own"]},
                       "accepted": acc, "not": no, "judged_any_word": sum(own.values()),
                       "precision_yes_over_yes_no": (acc / (acc + no)) if acc + no else None,
                       "precision_artifact_as_not": (acc / (acc + no + own.get("artifact", 0)))
                       if acc + no + own.get("artifact", 0) else None}
    return out


def ladder(root):
    out = {}
    for f in sorted(glob.glob(os.path.join(root, "DATA", "derived", "candidate_events", "*", "sample_seed0_*",
                                           "estimate.json"))):
        table = os.path.basename(os.path.dirname(os.path.dirname(f)))
        if table.startswith("M4_"):
            continue
        d = json.load(open(f, encoding="utf-8"))
        g = d["groups"]
        out[table] = {"answered": d["answered"], "unsure": d["unsure"], "pending": d["pending"],
                      "queue_id": d.get("queue_id"), "created_at": d.get("created_at"),
                      "groups": {k: {kk: g[k].get(kk) for kk in ("n_events", "n_judged_before", "positives_before",
                                                                   "n_unjudged", "n_sampled", "precision", "ci")}
                                 for k in g if k == "all" or k.startswith("agree:") or k.startswith("family:")}}
    return out


def sample_raw_shares(root):
    """The share of SAMPLED items accepted per agreement level (no census weighting), the other way to read the ladder."""
    import pandas as pd
    out = {}
    for d in sorted(glob.glob(os.path.join(root, "DATA", "derived", "candidate_events", "*", "sample_seed0_*"))):
        table = os.path.basename(os.path.dirname(d))
        if table.startswith("M4_"):
            continue
        lp = os.path.join(d, "labels.parquet")
        sp = os.path.join(d, "sample.parquet")
        if not (os.path.isfile(sp)):
            continue
        s = pd.read_parquet(sp)
        out[table] = {"columns": list(s.columns)[:40], "n": int(len(s))}
        if os.path.isfile(lp):
            lab = pd.read_parquet(lp)
            out[table]["label_columns"] = list(lab.columns)[:40]
    return out


def blocks():
    from Adapters import registry
    reg = registry.REGISTRY if hasattr(registry, "REGISTRY") else None
    names = None
    for attr in ("REGISTRY", "ADAPTERS", "registry"):
        if hasattr(registry, attr):
            v = getattr(registry, attr)
            if isinstance(v, dict):
                names = sorted(v)
                break
    if names is None and hasattr(registry, "discover_adapters"):
        names = sorted(registry.discover_adapters())
    retired = sorted(getattr(registry, "RETIRED", []) or [])
    return {"n_registered": len(names) if names else None, "names": names, "retired": retired}


def templates(c):
    rows = q(c, "SELECT id, name, kind, builtin, description FROM templates ORDER BY id")
    for r in rows:
        r["description"] = (r["description"] or "")[:80]
    return rows


def main():
    c = ro()
    res = {"recordings": recordings(c), "human_labels": human_labels(c),
           "seed_and_demo_run_groups": run_group_verdicts(c, (9, 12, 18, 66, 67, 308, 309)),
           "ladder": ladder(ROOT), "templates": templates(c)}
    try:
        res["blocks"] = blocks()
    except Exception as e:  # noqa: BLE001 - reported, not hidden
        res["blocks"] = {"error": repr(e)}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    print(json.dumps({k: res[k] for k in ("human_labels",)}, indent=1, default=str)[:3000])
    r = res["recordings"]
    print("files", r["n_files_excluding_M4"], "active", r["n_active_files_excluding_M4"], "ch",
          r["n_active_channels_excluding_M4"], "species", r["species_declared"], "ch-h", r["active_channel_hours_excluding_M4"])
    for f, v in r["files_excluding_M4"].items():
        print("  ", f, v)
    print("blocks", {k: v for k, v in res["blocks"].items() if k != "names"})
    for g, v in res["seed_and_demo_run_groups"].items():
        print("rg", g, v)
    for t, v in res["ladder"].items():
        print(t, v["answered"], v["unsure"], v["pending"])
        for k in ("all", "agree:1-2", "agree:3-4", "agree:5-6", "agree:7-8", "agree:9+", "family:drop_detection_v1",
                  "family:drop_detection_v5", "family:wavelet_encoded", "family:deconvolved_troughs",
                  "family:matrix_profile"):
            x = v["groups"].get(k)
            if x:
                print("   %-28s samp %4s prec %s ci %s" % (k, x["n_sampled"], None if x["precision"] is None else round(x["precision"], 3),
                                                       [None if y is None else round(y, 3) for y in (x["ci"] or [])]))


if __name__ == "__main__":
    main()
