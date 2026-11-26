"""Cut the demo's 24 h slices out of the real data and register them in the demo's work database.

    "/c/ProgramData/anaconda3/python.exe" scripts/neurips_demo/build_slices.py

Run from the demo worktree's root. Reads the real checkout (demo_config.REAL_ROOT) READ ONLY: its database with
?mode=ro and its channel files with mmap. Writes only under <this root>/DATA/neurips_demo/:

    slices/<dataset>/CH<n>.npy      one 1-D float64 array per channel, the 24 h window, as stored (V or mV)
    work/demo.sqlite                init_db + datasets + one recordings row per slice channel (ids 1..16, in
                                    demo_config.SLICE_ID_ORDER),
                                    npy_path repo-relative, units as the source
    store/slices.json               the slice table the precompute and the stations read
    store/researcher_events.json    every human verdict inside the slices, in slice samples (Library, Judge five)

A sample index in the demo is a SLICE index: 0 is the window's first sample. `t0_s` in slices.json is the window's
start in the source recording, so an absolute time is t0_s + i / fs.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import demo_config as C  # noqa: E402

REAL = Path(C.REAL_ROOT)
OUT = ROOT / C.DEMO_DATA
CATALOGUE = REAL / "docs/thesis/data/accepted_catalogue_20261109/accepted_spans.csv"

#: How a human verdict reads in the demo (the five-word vocabulary stays as it is; this is only a reading).
YES = {"interesting", "seed", "accepted"}
NO = {"not_interesting", "artifact", "rejected"}


def _real_db():
    p = REAL / "DATA/db/annotations.sqlite"
    if ROOT.resolve() == REAL.resolve():
        raise SystemExit("run this from the demo worktree, not the real checkout")
    return sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)


def main():
    (OUT / "slices").mkdir(parents=True, exist_ok=True)
    (OUT / "work").mkdir(parents=True, exist_ok=True)
    (OUT / "store").mkdir(parents=True, exist_ok=True)
    real = _real_db()
    real.row_factory = sqlite3.Row
    recs = {(r["source_file"], r["channel"]): dict(r) for r in real.execute("SELECT * FROM recordings")}
    dsets = {r["source_file"]: dict(r) for r in real.execute("SELECT * FROM datasets")}

    slices = []
    rid = 0
    by_key = {d["key"]: d for d in C.DATASETS}
    if sorted(by_key) != sorted(C.SLICE_ID_ORDER):
        raise SystemExit("demo_config.SLICE_ID_ORDER must name every dataset once")
    for ds in (by_key[k] for k in C.SLICE_ID_ORDER):
        for ch in ds["channels"]:
            src = recs[(ds["source_file"], ch)]
            fs = float(src["fs"])
            a = int(round(ds["hours"][0] * 3600 * fs))
            b = int(round(ds["hours"][1] * 3600 * fs))
            x = np.load(REAL / src["npy_path"], mmap_mode="r")
            b = min(b, len(x))
            seg = np.asarray(x[a:b], dtype=np.float64)
            if not np.isfinite(seg).all():
                raise SystemExit(f"{ds['key']} ch{ch}: {int((~np.isfinite(seg)).sum())} non-finite samples")
            rel = f"{C.DEMO_DATA}/slices/{ds['key']}/{C.channel_label(ch)}.npy"
            (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
            np.save(ROOT / rel, seg)
            rid += 1
            slices.append({
                "id": rid, "dataset": ds["key"], "channel": ch, "label": C.channel_label(ch),
                "fs": fs, "n": int(len(seg)), "units": src["units"] or "V", "npy": rel,
                "t0_s": a / fs, "source_file": ds["source_file"], "source_recording_id": src["id"],
                "source_start_idx": a,
            })
            print(f"{ds['key']:11s} {C.channel_label(ch):5s} {len(seg):7d} samples @ {fs:g} Hz from rec {src['id']} "
                  f"[{a}:{b}] {src['units']}")

    _work_db(slices, dsets)
    events = _researcher_events(real, recs, slices)
    (OUT / "store/slices.json").write_text(json.dumps({"datasets": C.DATASETS, "slices": slices}, indent=1))
    (OUT / "store/researcher_events.json").write_text(json.dumps(events))
    n_yes = sum(1 for e in events if e["verdict"] == "yes")
    print(f"researcher events in slices: {len(events)} ({n_yes} yes)")
    for ds in C.DATASETS:
        sub = [e for e in events if e["dataset"] == ds["key"]]
        print(f"  {ds['key']}: {len(sub)} ({sum(e['verdict'] == 'yes' for e in sub)} yes)")


def _work_db(slices, dsets):
    from Working.database.schema import init_db

    db = OUT / "work/demo.sqlite"
    if db.exists():
        db.unlink()
    conn = init_db(str(db))
    for ds in C.DATASETS:
        sf = f"demo_{ds['key']}"
        conn.execute("INSERT OR REPLACE INTO datasets (source_file, display_name, species, notes, updated_at, actor) VALUES (?,?,?,?,datetime('now'),'neurips-demo')",
                     (sf, ds["name"], f"{ds['name'].lower()} ({ds['latin']})",
                      f"NeurIPS demo slice of {ds['source_file']}, {ds['hours'][0]}-{ds['hours'][1]} h"))
    for s in slices:
        conn.execute(
            "INSERT INTO recordings (id, source_file, channel, fs, n_samples, global_offset, npy_path, notes, units, active)"
            " VALUES (?,?,?,?,?,?,?,?,?,1)",
            (s["id"], f"demo_{s['dataset']}", s["channel"], s["fs"], s["n"], 0, s["npy"],
             f"slice of rec {s['source_recording_id']} from sample {s['source_start_idx']}", s["units"]))
    conn.commit()
    conn.close()


def _researcher_events(real, recs, slices):
    """Every human verdict whose span lies inside a slice, mapped to slice samples.

    Three sources: the 9 Nov accepted catalogue (accepted spans), annotations (human spans) and adjudications on
    machine detections. A span is kept when at least half of it lies inside the window. MJu26a was judged on its
    10 Hz copy; its indices are divided by the decimation (5) onto the 2 Hz slice."""
    by_src = {}
    for s in slices:
        ds = next(d for d in C.DATASETS if d["key"] == s["dataset"])
        v = ds["verdict_source"]
        rec = recs[(v["source_file"], s["channel"])]
        by_src[rec["id"]] = (s, v["decimation"])

    out = []

    def add(rec_id, a, b, verdict_word, source, ref):
        hit = by_src.get(int(rec_id))
        if hit is None:
            return
        s, dec = hit
        a = int(a) // dec - s["source_start_idx"]
        b = -(-int(b) // dec) - s["source_start_idx"]
        if b <= a:
            return
        inside = max(0, min(b, s["n"]) - max(a, 0))
        if inside < 0.5 * (b - a):
            return
        verdict = "yes" if verdict_word in YES else "no" if verdict_word in NO else "unsure"
        out.append({"slice": s["id"], "dataset": s["dataset"], "start": max(a, 0), "end": min(b, s["n"]),
                    "verdict": verdict, "word": verdict_word, "source": source, "ref": ref})

    cat = pd.read_csv(CATALOGUE)
    for r in cat.itertuples():
        add(r.recording_id, r.start_idx, r.end_idx, "accepted", "catalogue", r.event_id)
    ids = ",".join(str(i) for i in by_src)
    for r in real.execute(f"SELECT id, recording_id, start_idx, end_idx, verdict FROM annotations "
                          f"WHERE recording_id IN ({ids})"):
        add(r["recording_id"], r["start_idx"], r["end_idx"], r["verdict"], "annotation", f"annotation:{r['id']}")
    for r in real.execute(f"""SELECT j.id, u.recording_id, d.start_idx, d.end_idx, j.verdict FROM adjudications j
                              JOIN detections d ON d.id = j.detection_id JOIN runs u ON u.id = d.run_id
                              WHERE u.recording_id IN ({ids})"""):
        add(r["recording_id"], r["start_idx"], r["end_idx"], r["verdict"], "adjudication", f"adjudication:{r['id']}")
    # one row per distinct span and verdict (the catalogue repeats its sources' spans)
    seen, uniq = set(), []
    for e in sorted(out, key=lambda e: (e["slice"], e["start"], e["end"], e["source"] != "catalogue")):
        key = (e["slice"], e["start"], e["end"], e["verdict"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    return uniq


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
