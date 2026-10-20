"""
build_demo_data.py
==================
Fill a demo checkout's DATA/ with a small slice of the real data, for the
examiners' hands-on session (2026-10-21). The researcher asked (2026-10-20)
for a 4-hour window across about five channels of M2_aug, so that whatever an
examiner runs — an Analyse chain, a seed search, a Discovery run — finishes
in seconds rather than walking 721 hours.

    git -C C:/Users/mmebr/Documents/CNN archive main | tar -x -C C:/Users/mmebr/Documents/CNN-demo
    "/c/ProgramData/anaconda3/python.exe" scripts/build_demo_data.py \
        --root C:/Users/mmebr/Documents/CNN --out C:/Users/mmebr/Documents/CNN-demo

`--root` is the checkout holding the real DATA/ (read only: the database is
opened ?mode=ro and the channel files by np.load). `--out` is a SEPARATE copy
of the code (a `git archive`, not a worktree and not a junction), whose own
DATA/ becomes the demo's. Run the demo bridge from that copy (see
docs/DEMO_DAY.md): the bridge reads the drop-motif seed store from
<its repo>/DATA/library_seed, so only a separate root keeps the real store's
recording ids away from the demo database.

What it writes under <out>/DATA/:

    db/annotations.sqlite         init_db + vocabulary + the window's recordings, Library entries
                                  (with their members) and annotations
    derived/channels/<stem>/      CH<n>.npy, one 1-D float64 slice per channel, + manifest.json
    library_seed/drop_motifs5/motifs/
                                  the seed store's events inside the window (replacing the archive's copy)

Every sample index is shifted by the window start, and every recording id is
renumbered from 1001, so an id from the real database never names a demo
channel: a stray real id fails loudly as "no recording" instead of reading the
wrong channel. Channel numbers are the source's (the UI labels channel 2 as
CH3, as on M2_aug). Runs, review queues, groupings and families start empty.

Default window (chosen 2026-10-20): hours 377-381, channels 2, 3, 5, 6, 7 —
the busiest four hours of M2_aug for catalogue motifs, every channel active,
no NaN.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from Working.database import queries as q  # noqa: E402
from Working.database import vocabulary as v  # noqa: E402
from Working.database.schema import init_db  # noqa: E402

SOURCE_FILE = "M2_aug_concat_fs1.mat"
STORE = Path("DATA/library_seed/drop_motifs5/motifs")
FIRST_ID = 1001


def _copy_rows(src, dst, table, rows, fix):
    """Insert `rows` of `table` into dst with `fix(row) -> dict | None` applied; returns {old id: new id}."""
    cols = [r[1] for r in dst.execute(f"PRAGMA table_info({table})")]
    ids = {}
    for row in rows:
        d = fix(dict(row))
        if not d:
            continue
        old = d.pop("id")
        keep = [c for c in cols if c in d and c != "id"]
        cur = dst.execute(f"INSERT INTO {table} ({', '.join(keep)}) VALUES ({', '.join('?' * len(keep))})", [d[c] for c in keep])
        ids[old] = cur.lastrowid
    return ids


def _store(root: Path, out: Path, rid_map: dict, a0: dict, b0: dict, h0: float, stem: str) -> int:
    """The seed store's events wholly inside the window, re-indexed onto the demo recordings."""
    src, dst = root / STORE, out / STORE
    ev = pd.read_csv(src / "events.csv")
    idx = [c for c in ev.columns if c.endswith("_idx")]
    ev = ev[ev["recording_id"].isin(list(rid_map))].copy()
    lo, hi = ev["recording_id"].map(a0), ev["recording_id"].map(b0)
    ev = ev[(ev["snippet_start_idx"] >= lo) & (ev["snippet_end_idx"] <= hi)].copy()
    for c in idx:  # -1 is the store's "no such region" (an event without an up-region); it stays -1
        ev[c] = ev[c].where(ev[c] < 0, ev[c] - ev["recording_id"].map(a0))
    for c in [c for c in ev.columns if c.endswith("_h")]:
        ev[c] = ev[c] - h0
    ev["recording_id"] = ev["recording_id"].map(rid_map)
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    ev.to_csv(dst / "events.csv", index=False)
    with np.load(src / "snippets.npz") as z:
        keys = {k for k in z.files if any(k.startswith(f"{s}") for s in ev["snippet_key"].astype(str))}
        np.savez(dst / "snippets.npz", **{k: z[k] for k in keys})
    man = json.loads((src / "manifest.json").read_text())
    man.update({"n_motifs": int(len(ev)), "demo": f"events of {SOURCE_FILE} inside {stem}, re-indexed by scripts/build_demo_data.py"})
    (dst / "manifest.json").write_text(json.dumps(man, indent=2))
    return len(ev)


def build(root: Path, out: Path, hours: tuple[float, float], channels: list[int]) -> str:
    root, out = root.resolve(), out.resolve()
    if out == root or not (out / "webui" / "run_server.py").is_file():
        raise SystemExit(f"--out must be a separate copy of the code (git archive), not {out}")
    data = out / "DATA"
    for p in (data / "db", data / "derived"):
        if p.exists():
            shutil.rmtree(p)
    src = sqlite3.connect(f"file:{(root / 'DATA/db/annotations.sqlite').as_posix()}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    rows = {r["channel"]: r for r in src.execute("SELECT * FROM recordings WHERE source_file = ?", (SOURCE_FILE,))}
    if missing := [c for c in channels if c not in rows]:
        raise SystemExit(f"{SOURCE_FILE} has no channel(s) {missing}")

    h0, h1 = hours
    stem = f"M2_aug_demo_{h0:g}-{h1:g}h"
    chan_dir = data / "derived" / "channels" / stem
    chan_dir.mkdir(parents=True)
    conn = init_db(str(data / "db" / "annotations.sqlite"))
    v.seed_vocabulary(conn)
    conn.execute("INSERT OR REPLACE INTO sqlite_sequence (name, seq) VALUES ('recordings', ?)", (FIRST_ID - 1,))
    rid_map, a0, b0 = {}, {}, {}
    for c in channels:
        r = rows[c]
        a, b = int(round(h0 * 3600 * r["fs"])), int(round(h1 * 3600 * r["fs"]))
        if b > r["n_samples"]:
            raise SystemExit(f"CH{c} has {r['n_samples']} samples; the window ends at {b}")
        np.save(chan_dir / f"CH{c}.npy", np.array(np.load(root / r["npy_path"], mmap_mode="r")[a:b], dtype=np.float64))
        q.insert_recording(conn, f"{stem}.mat", c, r["fs"], b - a, 0, f"DATA/derived/channels/{stem}/CH{c}.npy",
                           notes=f"demo slice of {SOURCE_FILE} channel {c}, samples {a}-{b} (hours {h0:g}-{h1:g}); "
                                 f"scripts/build_demo_data.py", commit=False, units=r["units"], units_note=r["units_note"])
        new = conn.execute("SELECT id FROM recordings WHERE source_file = ? AND channel = ?", (f"{stem}.mat", c)).fetchone()[0]
        rid_map[r["id"]], a0[r["id"]], b0[r["id"]] = new, a, b

    def moved(d):
        rid = d["recording_id"]
        if rid not in rid_map or not (a0[rid] <= d["start_idx"] and d["end_idx"] <= b0[rid]):
            return None
        return {**d, "recording_id": rid_map[rid], "start_idx": d["start_idx"] - a0[rid], "end_idx": d["end_idx"] - a0[rid]}

    marks = ",".join("?" * len(rid_map))
    entries = _copy_rows(src, conn, "motif_entry", src.execute(f"SELECT * FROM motif_entry WHERE recording_id IN ({marks})", list(rid_map)),
                         lambda d: (m := moved(d)) and {**m, "detection_id": None})
    members = _copy_rows(src, conn, "motif_member", src.execute(f"SELECT * FROM motif_member WHERE recording_id IN ({marks})", list(rid_map)),
                         lambda d: d["entry_id"] in entries and (m := moved(d)) and {**m, "entry_id": entries[d["entry_id"]], "current_revision_id": None})
    notes = _copy_rows(src, conn, "annotations", src.execute(f"SELECT * FROM annotations WHERE deleted_at IS NULL AND recording_id IN ({marks})", list(rid_map)),
                       lambda d: (m := moved(d)) and {**m, "parent_annotation_id": None})
    meta = src.execute("SELECT * FROM datasets WHERE source_file = ?", (SOURCE_FILE,)).fetchone()
    if meta is not None:
        conn.execute("INSERT INTO datasets (source_file, display_name, species, organism_id, experiment_date, condition, notes, updated_at, actor) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), 'build_demo_data')",
                     (f"{stem}.mat", f"M2_aug · hours {h0:g}-{h1:g} (demo)", meta["species"], meta["organism_id"],
                      meta["experiment_date"], meta["condition"], f"4-hour demo slice of {SOURCE_FILE}"))
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")  # the sandbox copies the main file only
    conn.close()
    n_events = _store(root, out, rid_map, a0, b0, h0, stem)
    (chan_dir / "manifest.json").write_text(json.dumps({"source_file": SOURCE_FILE, "hours": [h0, h1], "channels": channels,
        "recording_ids": {str(k): v_ for k, v_ in rid_map.items()}, "fs": rows[channels[0]]["fs"], "units": rows[channels[0]]["units"]}, indent=2))
    return (f"{stem}: {len(channels)} channels (ids {min(rid_map.values())}-{max(rid_map.values())}), "
            f"{len(entries)} Library entries, {len(members)} members, {len(notes)} annotations, {n_events} seed-store events")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="the checkout with the real DATA/ (read only)")
    ap.add_argument("--out", required=True, help="a separate code copy (git archive) whose DATA/ becomes the demo's")
    ap.add_argument("--hours", nargs=2, type=float, default=[377, 381], metavar=("FROM", "TO"))
    ap.add_argument("--channels", nargs="+", type=int, default=[2, 3, 5, 6, 7])
    a = ap.parse_args()
    print(build(Path(a.root), Path(a.out), tuple(a.hours), a.channels))


if __name__ == "__main__":
    main()
