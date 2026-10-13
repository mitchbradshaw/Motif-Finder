"""
derive_dwij_mfs2.py
===================
Derive `DATA/derived/channels/Dwij_<A-D>_fs0p8/` from the four `mfs2` logger
CSV exports dropped into `DATA/raw/` on 2026-10-13:

    record-mfs2-2026-09-01-14-31-11.csv  -> Dwij_A_fs0p8   (16 min, 773 rows)
    record-mfs2-2026-09-01-15-22-51.csv  -> Dwij_B_fs0p8   (17.4 h)
    record-mfs2-2026-09-02-08-49-40.csv  -> Dwij_C_fs0p8   (8.3 h; the data begins 17.5 h after the name's time)
    record-mfs2-2026-09-08-09-49-38.csv  -> Dwij_D_fs0p8   (29.3 h)

The letters are chronological by the file name's start time. The researcher
asked for the stems to be `Dwij_<letter>_fs<rate>` and for the unit to be mV
(2026-10-13).

What the files are (read, not assumed, 2026-10-13)
--------------------------------------------------
Comma-separated, one header line:

    Time,ADC1 (white),ADC2 (green),ADC3 (blue),ADC4 (red),Mic (dBFS)

`Time` is an ISO-8601 UTC timestamp with millisecond resolution, one per
row, strictly increasing, no duplicates, no NaN anywhere. ADC1-4 are four
single-ended channels named by wire colour. `Mic (dBFS)` is -120.00 on every
row of every file (no microphone was attached) and is not kept.

**Unit.** The values are millivolts as the device writes them: in file C all
four channels rail at 2047.9998 = 2048 - 1/4096, the full scale of a +-2048 mV
converter with 2^23 counts per side (0.244 uV per count; the export prints
six decimals, so the last digit is rounded). The researcher states mV.

**Rate.** The interval between rows is NOT constant, which is why the rows are
resampled rather than taken as uniform:

    A  1.238 s throughout (+-2 ms jitter)
    B  1.240 s throughout; 2 missed rows (2.24 s steps)
    C  1.239 s for the first quarter, then 1.251 s; 2 missed rows
    D  1.239 s for the first quarter, then 1.251 s; 4 missed rows

Every file is put on one uniform grid of **1.25 s (0.8 Hz)**, the dominant
native interval of C and D and within 1 % of A and B, by linear interpolation
in absolute time from each file's first timestamp; the grid stops at the last
timestamp. No sample is invented beyond the native rate (A and B are decimated
by 0.8 %, C and D are within 0.1 % of native) and the few missed rows are
bridged by the same interpolation; each is listed in the manifest. Rail values
(2047.9998) and other large excursions are kept as recorded, but note that a
single rail sample lands on the grid as an interpolation between it and its
neighbours, so a one-row excursion loses up to half its height on the grid
(file A's single 68 mV row becomes 37 mV; the manifest lists both extrema).
`--grid-dt 1.0` would put the files on a 1 Hz grid instead
(upsampling by 1.25x); the stems would then be `_fs1`.

Output (the recording kind's convention, docs/DATA_REGISTRATION.md):

    DATA/derived/channels/Dwij_<L>_fs0p8/CH0.npy … CH3.npy   1-D float64, millivolts
    DATA/derived/channels/Dwij_<L>_fs0p8/manifest.json      source_file, fs, units, t0_utc, …

Usage
-----
    python scripts/derive_dwij_mfs2.py --dry-run
    python scripts/derive_dwij_mfs2.py
    python scripts/derive_dwij_mfs2.py --only Dwij_C_fs0p8 --force
    python scripts/derive_dwij_mfs2.py --grid-dt 1.0          # a 1 Hz grid, stems *_fs1

Registration is a separate step: Settings › Datasets (the recording kind scans
DATA/derived/channels) or `POST /api/registry/recording/register`.
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

UNITS = "mV"
COLUMNS = ["ADC1 (white)", "ADC2 (green)", "ADC3 (blue)", "ADC4 (red)"]
MIC = "Mic (dBFS)"
RAIL_MV = 2048.0 - 1.0 / 4096.0

# letter -> raw file name (chronological by the name's start time)
SOURCES = {
    "A": "record-mfs2-2026-09-01-14-31-11.csv",
    "B": "record-mfs2-2026-09-01-15-22-51.csv",
    "C": "record-mfs2-2026-09-02-08-49-40.csv",
    "D": "record-mfs2-2026-09-08-09-49-38.csv",
}


def fs_token(grid_dt: float) -> str:
    """1.25 -> 'fs0p8', 1.0 -> 'fs1' (no dots in a stem: they are key separators)."""
    fs = 1.0 / grid_dt
    s = f"{fs:.4g}".rstrip("0").rstrip(".")
    return "fs" + s.replace(".", "p")


def stem_for(letter: str, grid_dt: float) -> str:
    return f"Dwij_{letter}_{fs_token(grid_dt)}"


def read_export(path: str):
    """Timestamps (seconds from the first row), the (n, 4) mV matrix and facts."""
    import pandas as pd
    df = pd.read_csv(path)
    expect = ["Time"] + COLUMNS + [MIC]
    if list(df.columns) != expect:
        raise SystemExit(f"{path}: unexpected columns {list(df.columns)!r}")
    t = pd.to_datetime(df["Time"], utc=True, format="ISO8601")
    if not t.is_monotonic_increasing or t.duplicated().any():
        raise SystemExit(f"{path}: timestamps are not strictly increasing")
    ts = (t - t.iloc[0]).dt.total_seconds().to_numpy(dtype=np.float64)
    X = np.ascontiguousarray(df[COLUMNS].to_numpy(dtype=np.float64))
    if not np.isfinite(X).all():
        raise SystemExit(f"{path}: NaN in the ADC columns")
    mic = df[MIC].to_numpy(dtype=np.float64)
    dt = np.diff(ts)
    med = float(np.median(dt))
    eighths = [round(float(np.median(c)), 4) for c in np.array_split(dt, 8)]
    missed = [{"after_row": int(i), "step_s": round(float(dt[i]), 3), "at_h": round(float(ts[i] / 3600), 3)}
              for i in np.flatnonzero(dt > 1.5 * med)]
    name_time = os.path.basename(path)[len("record-mfs2-"):-len(".csv")]
    named = _dt.datetime.strptime(name_time, "%Y-%m-%d-%H-%M-%S").replace(tzinfo=_dt.timezone.utc)
    t0 = t.iloc[0].to_pydatetime()
    facts = {
        "n_rows": int(len(df)),
        "t0_utc": t0.isoformat(),
        "t_last_utc": t.iloc[-1].to_pydatetime().isoformat(),
        "span_s": float(ts[-1]),
        "file_name_start_utc": named.isoformat(),
        "first_row_minus_file_name_start_s": float((t0 - named).total_seconds()),
        "native_dt_s": {"median": med, "mean": float(dt.mean()), "min": float(dt.min()), "max": float(dt.max()),
                        "std": float(dt.std()), "median_per_eighth": eighths},
        "missed_rows": missed,
        "mic_dbfs": {"min": float(mic.min()), "max": float(mic.max()), "constant": bool(mic.min() == mic.max())},
        "raw_extrema_mV": {c: {"min": float(X[:, i].min()), "max": float(X[:, i].max())} for i, c in enumerate(COLUMNS)},
        "rail_samples": {c: int((X[:, i] >= RAIL_MV - 1e-3).sum()) for i, c in enumerate(COLUMNS)},
    }
    return ts, X, facts


def resample(ts: np.ndarray, X: np.ndarray, grid_dt: float):
    """Linear interpolation of every channel onto t = 0, dt, 2dt, … <= ts[-1]."""
    n = int(np.floor(ts[-1] / grid_dt)) + 1
    grid = np.arange(n, dtype=np.float64) * grid_dt
    Y = np.empty((n, X.shape[1]), dtype=np.float64)
    for c in range(X.shape[1]):
        Y[:, c] = np.interp(grid, ts, X[:, c])
    return grid, Y


def derive(letter: str, grid_dt: float, dry: bool, force: bool) -> None:
    raw_name = SOURCES[letter]
    stem = stem_for(letter, grid_dt)
    src = os.path.join(RAW, raw_name)
    final = os.path.join(CHANNELS, stem)
    if os.path.isdir(final) and not force:
        have = sorted(fn for fn in os.listdir(final) if fn.startswith("CH") and fn.endswith(".npy"))
        if len(have) == len(COLUMNS) and os.path.isfile(os.path.join(final, "manifest.json")):
            print(f"[{stem}] complete ({len(have)} channels + manifest), skipped — pass --force to redo")
            return
    print(f"[{stem}] reading {src}")
    ts, X, facts = read_export(src)
    nd = facts["native_dt_s"]
    print(f"[{stem}] {facts['n_rows']:,} rows, {facts['span_s'] / 3600:.2f} h from {facts['t0_utc']}; native dt median "
          f"{nd['median']:.3f} s (per eighth {nd['median_per_eighth']}), {len(facts['missed_rows'])} missed rows; "
          f"mic constant={facts['mic_dbfs']['constant']}; rail samples {facts['rail_samples']}")
    grid, Y = resample(ts, X, grid_dt)
    fs = 1.0 / grid_dt
    print(f"[{stem}] -> {len(grid):,} samples on a {grid_dt:g} s grid ({fs:g} Hz) = {len(grid) / fs / 3600:.2f} h")
    for c, col in enumerate(COLUMNS):
        print(f"[{stem}]   CH{c} ({col}): min {Y[:, c].min():.3f} max {Y[:, c].max():.3f} mV")
    assert np.isfinite(Y).all()
    if dry:
        return
    os.makedirs(CHANNELS, exist_ok=True)
    staging = os.path.join(CHANNELS, f".staging_{stem}_{os.getpid()}")
    if os.path.isdir(staging):
        shutil.rmtree(staging)
    os.makedirs(staging)
    for c in range(len(COLUMNS)):
        np.save(os.path.join(staging, f"CH{c}.npy"), np.ascontiguousarray(Y[:, c]))
    manifest = {
        "source_file": raw_name,
        "raw_file": f"DATA/raw/{raw_name}",
        "n_channels": len(COLUMNS),
        "fs": fs,
        "fs_note": (f"{fs:g} Hz is the uniform grid the rows were resampled onto, not a rate read from the file: the "
                    f"export's timestamps run at a native interval of {nd['median']:.3f} s (median; per eighth "
                    f"{nd['median_per_eighth']}, {len(facts['missed_rows'])} missed rows), which is not constant across "
                    "or within the four mfs2 files, so each was linearly interpolated in absolute time onto a "
                    f"{grid_dt:g} s grid from its first timestamp. Time of sample i (UTC) = t0_utc + i * {grid_dt:g} s."),
        "n_samples_per_channel": int(len(grid)),
        "dtype": "float64",
        "units": f"{UNITS} as stored: the mfs2 export writes millivolts (the converter rails at {RAIL_MV:.4f} = 2048 - 1/4096 mV, "
                 "a +-2048 mV full scale with 2^23 counts per side); the researcher confirmed mV on 2026-10-13; nothing is rescaled",
        "imported_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "derived_by": "scripts/derive_dwij_mfs2.py on 2026-10-13",
        "t0_utc": facts["t0_utc"],
        "time_base": f"uniform: t0_utc + i * {grid_dt:g} s",
        "device": "mfs2 logger (record-mfs2-<start>.csv export: Time ISO-8601 UTC ms, ADC1-4 in mV, Mic dBFS)",
        "channel_labels": {f"CH{c}": col for c, col in enumerate(COLUMNS)},
        "dropped_columns": {MIC: f"constant {facts['mic_dbfs']['min']:g} dBFS on every row (no microphone); not a recording channel"},
        "preprocessing": {
            "resampling": f"linear interpolation of each channel from its timestamps onto a uniform {grid_dt:g} s grid "
                          "starting at the first row's time and ending at or before the last row's time",
            "grid_dt_s": grid_dt,
            "raw_rows": facts["n_rows"],
            "grid_samples": int(len(grid)),
            "missed_rows_bridged": facts["missed_rows"],
            "values_altered_otherwise": "none: no rescaling, filtering, detrending or clipping; rail values are kept",
            "single_sample_excursions": ("a one-row excursion that falls between two grid points is shared between them by "
                                         "the interpolation and so loses up to half its height on the grid (compare "
                                         "grid_extrema_mV with raw_file_facts.raw_extrema_mV); the raw file keeps it in full"),
            "grid_extrema_mV": {col: {"min": float(Y[:, c].min()), "max": float(Y[:, c].max())} for c, col in enumerate(COLUMNS)},
        },
        "raw_file_facts": facts,
    }
    with open(os.path.join(staging, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    if os.path.isdir(final):
        shutil.rmtree(final)
    os.replace(staging, final)
    print(f"[{stem}] wrote {final}: CH0..CH{len(COLUMNS) - 1}.npy ({len(grid):,} float64 each) + manifest.json")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="read, resample and report, write nothing")
    ap.add_argument("--only", action="append", default=[], help="restrict to these stems (repeatable)")
    ap.add_argument("--force", action="store_true", help="rederive a stem that is already complete")
    ap.add_argument("--grid-dt", type=float, default=1.25, help="uniform grid interval in seconds (default 1.25 = 0.8 Hz)")
    args = ap.parse_args()
    for letter in SOURCES:
        if args.only and stem_for(letter, args.grid_dt) not in args.only:
            continue
        derive(letter, args.grid_dt, args.dry_run, args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
