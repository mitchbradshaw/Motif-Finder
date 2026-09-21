"""
rederive_channels.py
====================
Rebuild `DATA/derived/channels/` from `DATA/raw/` after the 2026-09-21 loss
(a `git worktree remove` followed the CNN-dm6 worktree's junctions and emptied
the real `DATA/db` and `DATA/derived`; see CLAUDE.md, Environment).

The database was recovered from a bridge copy and already holds the
`recordings` rows for the registered stems, so this script must reproduce the
files those rows point at, byte for byte in size, and must not add rows. The
unregistered stems (M1, M100, M101_t, MJu26a, L_LM_Jul_26_J_raw_fs10) had no
rows before and get none now — stage-3 Prompt 02 registers them. What each
raw file holds was read, not assumed (`scipy.io.whosmat` / `h5py`, 2026-09-21):

    M2_aug_concat_fs1.mat        x      (41,529,600 x 1)  flat, 16 channels end to end
    M2_aug_concat_fs2.mat        VECTOR (81,676,784 x 1)  flat, 16 channels
    M2_concat_fs1.mat            VECTOR (16,271,232 x 1)  flat, 16 channels
    M4_aug_concat_fs1.mat        VECTOR (29,087,968 x 1)  flat, 16 channels (held out)
    Fig2A_dt0p1.csv              5 columns x 12,001 rows, fs 10 Hz
    Mushroom_260720_..._fs1.mat  data (14,401 x 1) + fs, n_channels, channel_indices, source_file
    M1_M100.mat                  M1 (10,868,600 x 13), M100 (10,868,600 x 13), t1
    M101_t.mat                   M101 (10,860,035 x 13), t101 (0.1 s steps), SD, Td
    L_LM_Jul_26_J_raw.mat        M23 (22,892,769 x 5)  - millivolts on disk, see lionsmane12.py
    MJu26a.mat (v7.3)            M (16 x 14,722,842), t (1 x 14,722,842)  - non-uniform t

Expected outputs (file names and byte sizes from the pre-loss inventory taken
at 11:20 on 2026-09-21) are in EXPECTED below; `--verify` checks them.

Usage
-----
    python scripts/rederive_channels.py --dry-run          # print the plan, write nothing
    python scripts/rederive_channels.py                    # rebuild everything missing
    python scripts/rederive_channels.py --only M1 --only MJu26a
    python scripts/rederive_channels.py --verify           # sizes + shapes against EXPECTED

Resumable: a file that already exists with the expected size is left alone.
Each stem is written to a staging directory and swapped in atomically.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
os.chdir(_REPO)

import numpy as np  # noqa: E402

RAW = os.path.join("DATA", "raw")
CHANNELS = os.path.join("DATA", "derived", "channels")
DB = os.path.join("DATA", "db", "annotations.sqlite")
HEADER = 128  # bytes of .npy header for a 1-D float64 array of these lengths


def _npy_bytes(n: int) -> int:
    return HEADER + 8 * n


# stem -> {filename: expected bytes}. Every number here is from the inventory.
EXPECTED: dict[str, dict[str, int]] = {
    "M2_aug_concat_fs1": {f"CH{i}.npy": _npy_bytes(2_595_600) for i in range(16)},
    "M2_aug_concat_fs2": {f"CH{i}.npy": _npy_bytes(5_104_799) for i in range(16)},
    "M2_concat_fs1": {f"CH{i}.npy": _npy_bytes(1_016_952) for i in range(16)},
    "M4_aug_concat_fs1": {f"CH{i}.npy": _npy_bytes(1_817_998) for i in range(16)},
    "Fig2A_dt0p1": {**{f"CH{i}.npy": _npy_bytes(12_001) for i in range(5)}, "manifest.json": None},
    "Mushroom_260720_0509_4hrs_CH14_fs1": {
        "Mushroom_260720_0509_4hrs_CH14_fs1_CH00.npy": _npy_bytes(14_401)},
    "M1": {f"CH{i}.npy": _npy_bytes(10_868_600) for i in range(13)},
    "M100": {f"CH{i}.npy": _npy_bytes(10_868_600) for i in range(13)},
    "M101_t": {f"CH{i}.npy": _npy_bytes(10_860_035) for i in range(13)},
    "L_LM_Jul_26_J_raw_fs10": {**{f"CH{i}.npy": _npy_bytes(22_892_769) for i in range(5)},
                               "manifest.json": None},
    "MJu26a": {**{f"CH{i}.npy": _npy_bytes(14_722_842) for i in range(16)},
               "t.npy": _npy_bytes(14_722_842), "manifest.json": None},
}
# sanity: the inventory's literal byte counts
assert EXPECTED["M1"]["CH0.npy"] == 86_948_928
assert EXPECTED["M101_t"]["CH0.npy"] == 86_880_408
assert EXPECTED["MJu26a"]["CH0.npy"] == 117_782_864
assert EXPECTED["L_LM_Jul_26_J_raw_fs10"]["CH0.npy"] == 183_142_280
assert EXPECTED["M2_aug_concat_fs1"]["CH0.npy"] == 20_764_928
assert EXPECTED["Fig2A_dt0p1"]["CH0.npy"] == 96_136
assert EXPECTED["Mushroom_260720_0509_4hrs_CH14_fs1"][
    "Mushroom_260720_0509_4hrs_CH14_fs1_CH00.npy"] == 115_336


def _stem_complete(stem: str) -> bool:
    d = os.path.join(CHANNELS, stem)
    for name, size in EXPECTED[stem].items():
        p = os.path.join(d, name)
        if not os.path.isfile(p):
            return False
        if size is not None and os.path.getsize(p) != size:
            return False
    return True


def _manifest(source_file, n_channels, fs, n_samples, dtype, **extra):
    m = {"source_file": source_file, "n_channels": n_channels, "fs": fs,
         "n_samples_per_channel": int(n_samples), "dtype": str(dtype),
         "imported_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
         "rederived_from": "DATA/raw on 2026-09-21 by scripts/rederive_channels.py "
                           "after the derived tree was lost; see CLAUDE.md, Environment"}
    m.update(extra)
    return m


def _swap_in(stem: str, staging: str) -> None:
    final = os.path.join(CHANNELS, stem)
    if os.path.isdir(final):
        shutil.rmtree(final)
    os.replace(staging, final)


def _staging(stem: str) -> str:
    os.makedirs(CHANNELS, exist_ok=True)
    s = os.path.join(CHANNELS, f".staging_{stem}_{os.getpid()}")
    if os.path.isdir(s):
        shutil.rmtree(s)
    os.makedirs(s)
    return s


# ── the registered stems: reuse the materialiser so paths and rows agree ──

def do_flat16(stem: str, dry: bool) -> None:
    """The four `_fs<N>` files: the materialiser splits the flat vector into 16
    channels and its INSERT OR IGNORE leaves the existing rows alone."""
    from Working.database.schema import init_db
    from Pipelines.materialize_channels.materialize_channels import _materialize_one
    src = os.path.join(RAW, f"{stem}.mat")
    print(f"[{stem}] flat vector -> 16 channels via materialize_channels ({src})")
    if dry:
        return
    conn = init_db(DB)
    before = conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0]
    _materialize_one(conn, src)
    after = conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0]
    conn.close()
    assert before == after, f"{stem}: recordings rows changed {before} -> {after} (must not)"


def do_fig2a(dry: bool) -> None:
    from Working.database.schema import init_db
    from Pipelines.materialize_channels.materialize_channels import materialize_arbitrary_file
    src = os.path.join(RAW, "Fig2A_dt0p1.csv")
    print(f"[Fig2A_dt0p1] 5-column csv -> 5 channels at 10 Hz via materialize_arbitrary_file ({src})")
    if dry:
        return
    conn = init_db(DB)
    before = conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0]
    materialize_arbitrary_file(conn, src, n_channels=5, fs=10.0)
    after = conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0]
    conn.close()
    assert before == after, f"Fig2A: recordings rows changed {before} -> {after} (must not)"


def do_mushroom(dry: bool) -> None:
    import scipy.io
    stem = "Mushroom_260720_0509_4hrs_CH14_fs1"
    src = os.path.join(RAW, f"{stem}.mat")
    print(f"[{stem}] self-describing 1-channel excerpt -> {stem}_CH00.npy (row 385 exists)")
    if dry:
        return
    m = scipy.io.loadmat(src, squeeze_me=True)
    data = np.asarray(m["data"], dtype=np.float64).ravel()
    assert data.shape[0] == 14_401, data.shape
    assert int(m["n_channels"]) == 1
    staging = _staging(stem)
    np.save(os.path.join(staging, f"{stem}_CH00.npy"), data)
    _swap_in(stem, staging)


# ── the unregistered stems: 2-D matrices, one column (or row) per channel ──

def do_columns(stem: str, src_name: str, var: str, n_channels: int, n_samples: int,
               fs, dry: bool, manifest_extra: dict | None = None) -> None:
    """A v5 .mat whose variable is (n_samples x n_channels): CH<i> = column i."""
    import scipy.io
    src = os.path.join(RAW, src_name)
    print(f"[{stem}] {src_name}::{var} ({n_samples:,} x {n_channels}) -> CH0..CH{n_channels - 1}"
          + (" + manifest.json" if manifest_extra is not None else ""))
    if dry:
        return
    mat = scipy.io.loadmat(src, variable_names=[var])
    M = mat[var]
    assert M.shape == (n_samples, n_channels), M.shape
    staging = _staging(stem)
    for i in range(n_channels):
        np.save(os.path.join(staging, f"CH{i}.npy"), np.ascontiguousarray(M[:, i], dtype=np.float64))
    if manifest_extra is not None:
        with open(os.path.join(staging, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(_manifest(src_name, n_channels, fs, n_samples, "float64", **manifest_extra), f, indent=2)
    del M, mat
    _swap_in(stem, staging)


def do_mju26a(dry: bool) -> None:
    """v7.3: M is (16 x N) row-major in HDF5; t is the (non-uniform) time base."""
    stem, src_name = "MJu26a", "MJu26a.mat"
    src = os.path.join(RAW, src_name)
    print(f"[{stem}] {src_name}::M (16 x 14,722,842) -> CH0..CH15, ::t -> t.npy, + manifest.json")
    if dry:
        return
    import h5py
    staging = _staging(stem)
    with h5py.File(src, "r") as f:
        M, t = f["M"], f["t"]
        assert M.shape == (16, 14_722_842), M.shape
        assert t.shape == (1, 14_722_842), t.shape
        for i in range(16):
            np.save(os.path.join(staging, f"CH{i}.npy"), np.asarray(M[i, :], dtype=np.float64))
        tt = np.asarray(t[0, :], dtype=np.float64)
        np.save(os.path.join(staging, "t.npy"), tt)
        dt = np.diff(tt)
        fs_note = (f"t is not uniform: dt min {dt.min():.6g}, median {np.median(dt):.6g}, "
                   f"max {dt.max():.6g} (units as stored in the .mat); fs below is 1/median(dt)")
        fs = float(1.0 / np.median(dt)) if np.median(dt) > 0 else None
    with open(os.path.join(staging, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(_manifest(src_name, 16, fs, 14_722_842, "float64", time_base="t.npy",
                            fs_note=fs_note), fh, indent=2)
    _swap_in(stem, staging)


PLAN = [
    ("M2_aug_concat_fs1", lambda d: do_flat16("M2_aug_concat_fs1", d)),
    ("M2_aug_concat_fs2", lambda d: do_flat16("M2_aug_concat_fs2", d)),
    ("M2_concat_fs1", lambda d: do_flat16("M2_concat_fs1", d)),
    ("M4_aug_concat_fs1", lambda d: do_flat16("M4_aug_concat_fs1", d)),
    ("Fig2A_dt0p1", do_fig2a),
    ("Mushroom_260720_0509_4hrs_CH14_fs1", do_mushroom),
    ("M1", lambda d: do_columns("M1", "M1_M100.mat", "M1", 13, 10_868_600, None, d)),
    ("M100", lambda d: do_columns("M100", "M1_M100.mat", "M100", 13, 10_868_600, None, d)),
    ("M101_t", lambda d: do_columns("M101_t", "M101_t.mat", "M101", 13, 10_860_035, None, d)),
    ("L_LM_Jul_26_J_raw_fs10", lambda d: do_columns(
        "L_LM_Jul_26_J_raw_fs10", "L_LM_Jul_26_J_raw.mat", "M23", 5, 22_892_769, 10.0, d,
        manifest_extra={
            "units": "millivolts as stored (everything else on disk is volts; "
                     "Pipelines/drop_motifs/lionsmane12.py divides by 1000)",
            "fs_note": "10.0 Hz is inferred, not read from the file: the .mat carries a scalar "
                       "MATLAB duration, not a timestamp vector; verified against catalogue id 385 "
                       "(Mushroom_260720, a 10:1 decimated four-hour excerpt of CH2 at sample "
                       "15,777,590, r = 0.9995) - see lionsmane12.py"})),
    ("MJu26a", do_mju26a),
]


def verify() -> int:
    bad = 0
    for stem, files in EXPECTED.items():
        d = os.path.join(CHANNELS, stem)
        for name, size in files.items():
            p = os.path.join(d, name)
            if not os.path.isfile(p):
                print(f"MISSING  {p}"); bad += 1; continue
            got = os.path.getsize(p)
            if size is not None and got != size:
                print(f"SIZE     {p}: {got} != {size}"); bad += 1; continue
            if name.endswith(".npy"):
                arr = np.load(p, mmap_mode="r")
                if arr.ndim != 1 or arr.dtype != np.float64 or arr.shape[0] != (size - HEADER) // 8:
                    print(f"SHAPE    {p}: {arr.shape} {arr.dtype}"); bad += 1; continue
                if not np.isfinite(arr[:1000]).all():
                    print(f"NONFINITE {p} (first 1000 samples)"); bad += 1; continue
            print(f"ok       {p}")
    # the registered rows must still resolve
    import sqlite3
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    missing = [r for r in conn.execute("SELECT id, npy_path FROM recordings")
               if not os.path.isfile(r[1])]
    conn.close()
    for rid, p in missing:
        print(f"ROW      recordings.id={rid} -> {p} does not exist"); bad += 1
    print(f"{'ALL GOOD' if not bad else str(bad) + ' PROBLEMS'}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    ap.add_argument("--only", action="append", default=[], help="restrict to these stems (repeatable)")
    ap.add_argument("--verify", action="store_true", help="check files against the expected inventory and exit")
    args = ap.parse_args()
    if args.verify:
        return verify()
    if not os.path.isfile(DB):
        print(f"refusing: {DB} is absent; restore the database first (the registered stems' rows live there)")
        return 2
    for stem, step in PLAN:
        if args.only and stem not in args.only:
            continue
        if _stem_complete(stem):
            print(f"[{stem}] complete, skipped")
            continue
        step(args.dry_run)
    if not args.dry_run:
        return verify()
    return 0


if __name__ == "__main__":
    sys.exit(main())
