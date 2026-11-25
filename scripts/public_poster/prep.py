"""Public poster (25 Nov 2026): the drop table every waveform figure reads.

Plain words: one row per drop, from our own recordings whose species is recorded, each with its waveform scaled to
"one unit deep, one unit of fall time" and the shape measures the grids use.

Sources (read-only):
* the 24 Nov auto-detect pool's core drops (`DATA/derived/autodetect/pool_20261124/events.csv`,
  `event_shapes.npz`, `p_accept.parquet`), kept where the verdict model rates them likely real (p >= P_MIN);
* the reviewed library drops of the 23 Nov drop plots (`docs/library_analysis/20261123_plots/events.csv`,
  `event_shapes.npz`), which the pool left out on purpose because they had been judged.

The two sets do not overlap: the pool excludes every drop that matches a judged or queued span.

Datasets: ours, species recorded (oyster M2_aug, M4; chocolate oyster CO; snow oyster SO; Asian shiitake SH;
lion's mane LM, MJu26a). Left out: Adamatzky's four species (Cordyceps, Enoki, S_commune), the Dwij loggers, the
species-unknown 10 Hz recordings (M1, L_R_Aug_26_PD, F2B), and M2_concat, whose species is recorded two ways (the
database: lion's mane, the researcher's labels of 3 Nov; the thesis corpus table and figstyle: oyster).

    PYTHONIOENCODING=utf-8 "/c/ProgramData/anaconda3/python.exe" scripts/public_poster/prep.py
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
POOL = os.path.join(ROOT, "DATA", "derived", "autodetect", "pool_20261124")
LIB = os.path.join(ROOT, "docs", "library_analysis", "20261123_plots")
OUT = os.path.join(ROOT, "docs", "public_poster_20261125", "data")

P_MIN = float(os.environ.get("POSTER_P_MIN", "0.8"))   # the Auto-detect session's advice (25 Nov): the cleaner set

SPECIES = {   # dataset -> species (the database's datasets table and the thesis corpus table agree on these)
    "M2_aug": "oyster", "M4": "oyster",
    "CO": "chocolate oyster", "SO": "snow oyster",
    "SH": "Asian shiitake",
    "LM": "lion's mane", "MJu26a": "lion's mane",
}


def load_pool():
    ev = pd.read_csv(os.path.join(POOL, "events.csv"))
    z = np.load(os.path.join(POOL, "event_shapes.npz"))
    assert np.all(z["event_id"] == ev["event_id"].astype(str).to_numpy()), "pool shapes out of step with events"
    ev["steepness"], ev["position"] = z["steepness"], z["position"]
    W = z["W"]
    ev["candidate_id"] = ev["event_id"].str.split("-").str[2].astype(int)
    pa = pd.read_parquet(os.path.join(POOL, "p_accept.parquet"))[["recording_id", "candidate_id", "p_accept"]]
    ev = ev.merge(pa, on=["recording_id", "candidate_id"], how="left", validate="one_to_one")
    keep = ev["dataset"].isin(SPECIES) & (ev["p_accept"] >= P_MIN)
    ev, W = ev[keep].reset_index(drop=True), W[keep.to_numpy()]
    ev["set"] = "pool"
    return ev, W


def load_library():
    ev = pd.read_csv(os.path.join(LIB, "events.csv"))
    z = np.load(os.path.join(LIB, "event_shapes.npz"))
    assert np.all(z["event_id"] == ev["event_id"].astype(str).to_numpy()), "library shapes out of step with events"
    ev["steepness"], ev["position"] = z["steepness"], z["position"]
    W = z["W"]
    keep = ev["dataset"].isin(SPECIES)
    ev, W = ev[keep].reset_index(drop=True), W[keep.to_numpy()]
    ev["set"] = "library"
    ev["p_accept"] = np.nan
    return ev, W


MJU_FS10_FIRST, MJU_FS2_FIRST = 650, 692   # MJu26a_fs10 recording id of channel 0, and of the 2 Hz copy's channel 0


def dp_module():
    """The NeurIPS session's drop-plot helpers (read-only use: `recordings`, `window`, `shape`, `fall_anatomy`)."""
    import sys
    sys.path.insert(0, os.path.join(ROOT, "scripts", "library_analysis"))
    import drop_plots_20261123 as dp
    return dp


def mju_library_to_2hz(ev, W, dp, recs):
    """The reviewed MJu26a drops sit on the 10 Hz copy; the pool's on the 2 Hz copy. Move the 10 Hz ones onto the
    2 Hz copy (same channel, sample index / 5) and redraw their waveform and fall anatomy there, so every MJu26a
    drop is measured at one rate. Depth, fall, width and recovery keep their 10 Hz values (physical units)."""
    m = (ev["dataset"] == "MJu26a") & (ev["fs"] == 10.0)
    for i in np.flatnonzero(m.to_numpy()):
        r = ev.loc[i]
        rid2 = MJU_FS2_FIRST + (int(r.recording_id) - MJU_FS10_FIRST)
        assert recs[rid2]["channel"] == recs[int(r.recording_id)]["channel"], "channel map broken"
        top, bottom = int(round(r.top_idx / 5)), int(round(r.bottom_idx / 5))
        bottom = max(bottom, top + 1)
        w = dp.shape(recs, rid2, top, bottom - top, -0.5, 5.0, W.shape[1], depth=float(r.depth_mv))
        W[i] = w if w is not None else np.nan
        seg = dp.window(recs, rid2, top, bottom + 1)
        s, p = dp.fall_anatomy(seg) if seg is not None else (np.nan, np.nan)
        rec_idx = r.recovery_idx / 5 if np.isfinite(r.recovery_idx) else np.nan
        ev.loc[i, ["recording_id", "fs", "top_idx", "bottom_idx", "recovery_idx", "steepness", "position"]] = \
            [rid2, 2.0, top, bottom, rec_idx, s, p]
    print(f"moved {int(m.sum())} reviewed MJu26a drops from the 10 Hz copy to the 2 Hz one", flush=True)


def anatomy_at_1hz(ev, dp, recs):
    """Steepness and plunge position read at one common rate (1 Hz, block means of 2 for the 2 Hz recordings), so
    the oyster recordings (1 Hz) and the others (2 Hz) are compared fairly: steepness counts samples."""
    s1 = ev["steepness"].to_numpy(float).copy()
    p1 = ev["position"].to_numpy(float).copy()
    for i in np.flatnonzero((ev["fs"] == 2.0).to_numpy()):
        r = ev.loc[i]
        a, b = int(r.top_idx) // 2 * 2, (int(r.bottom_idx) // 2 + 1) * 2
        seg = dp.window(recs, int(r.recording_id), a, b)
        if seg is None or len(seg) < 4:
            s1[i], p1[i] = np.nan, np.nan
            continue
        x1 = seg[: len(seg) // 2 * 2].reshape(-1, 2).mean(axis=1)
        s1[i], p1[i] = dp.fall_anatomy(x1) if len(x1) >= 2 else (1.0, 0.5)
    ev["steepness_1hz"], ev["position_1hz"] = s1, p1


def main():
    os.makedirs(OUT, exist_ok=True)
    pe, pw = load_pool()
    le, lw = load_library()
    cols = ["event_id", "set", "dataset", "recording_id", "channel", "fs", "top_idx", "bottom_idx", "recovery_idx",
            "depth_mv", "fall_s", "width_s", "recovery_s", "steep_s", "long_tail", "t_h", "fall_rate_mv_s",
            "steepness", "position", "p_accept"]
    le["p_accept"] = le["p_accept"].astype(float)
    ev = pd.concat([pe[cols], le[cols]], ignore_index=True)
    W = np.vstack([pw, lw])
    import sqlite3
    dp = dp_module()
    conn = sqlite3.connect(f"file:{dp.DB}?mode=ro", uri=True)
    recs = dp.recordings(conn)
    mju_library_to_2hz(ev, W, dp, recs)
    anatomy_at_1hz(ev, dp, recs)
    ev["species"] = ev["dataset"].map(SPECIES)
    ev["recovery_ratio"] = ev["recovery_s"] / ev["fall_s"]
    ev["shape_ok"] = np.all(np.isfinite(W), axis=1)
    ev.to_parquet(os.path.join(OUT, "drops.parquet"))
    np.save(os.path.join(OUT, "drop_shapes.npy"), W.astype(np.float32))
    print(f"P_MIN={P_MIN}: {len(ev):,} drops ({(ev['set'] == 'pool').sum():,} pool, {(ev['set'] == 'library').sum():,} "
          f"library), {ev['recording_id'].nunique()} channels")
    print(ev.groupby(["species", "dataset"]).agg(drops=("event_id", "size"), channels=("recording_id", "nunique"),
                                                 shape_ok=("shape_ok", "sum")).to_string())


if __name__ == "__main__":
    main()
