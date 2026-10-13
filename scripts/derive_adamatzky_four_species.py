"""
derive_adamatzky_four_species.py
================================
Derive `DATA/derived/channels/<stem>/` from the four PicoLog text exports that
Andrew Adamatzky published as

    Adamatzky A. 2021. Recordings of electrical activity of four species of
    fungi [Dataset]. Zenodo. doi:10.5281/zenodo.5790768  (CC BY 4.0)

and analysed in

    Adamatzky A. 2022. Language of fungi derived from their electrical spiking
    activity. R. Soc. Open Sci. 9: 211926. doi:10.1098/rsos.211926 (PMC8984380)

The four files were dropped into `DATA/raw/` on 2026-10-13 under the names the
Zenodo zips carry (spaces and the "militari" spelling are the record's own):

    Cordyceps militari.txt
    Enoki fungi Flammulina velutipes.txt
    Ghost Fungi Omphalotus nidiformis.txt
    Schizophyllum commune.txt

What the files are (read, not assumed, 2026-10-13)
--------------------------------------------------
Tab-separated PicoLog exports, one header line, no time column. Seven columns
headed ``Differential 1 - 2 Ave. (mV)`` … ``Differential 13 - 14 Ave. (mV)``:
seven differential electrode pairs (the record says eight pairs were logged;
pair 15-16 is not in the export) on a Pico ADC-24, each sample the average of
the logger's measurements over the interval. The unit is in the header (mV).
The sampling rate is NOT in the file: the record and the paper both say "one
sample per second" (the logger averaging up to 600 measurements per sample),
so fs is 1.0 Hz **documented, not read**, and the manifest says so.

Row counts at 1 Hz: Cordyceps 1,900,145 (22.0 d), Enoki 1,210,938 (14.0 d, of
which the last 36.8 h are all-NaN), Ghost 3,279,569 (38.0 d), Schizophyllum
263,959 (3.06 d). The paper's prose ("S. commune 1.5 days, the others ca 5
days") is not an accurate description of these files at any single sampling
rate (the ratios would be 2x, 2.5x, 4.4x and 7.6x), so it is not used.

Quirks handled here, every one of them recorded in the manifest:

* ``Cordyceps militari.txt``: the header and the first 1,048,576 data rows have
  ten fields, the rest seven. 1,048,576 is Excel's row limit, so the file was
  round-tripped through a spreadsheet that added three columns (a derived
  signal and two zero columns) to the rows it could hold. Columns 8-10 are
  dropped; the seven electrode columns are intact throughout.
* NaN rows: PicoLog writes NaN for a sample it did not take. Enoki ends in
  132,504 all-NaN rows (the logger ran on after the recording ended): trimmed.
  Schizophyllum's seventh pair is NaN for its first 272 rows: the first 272
  rows are trimmed from all seven channels so they stay aligned (those rows
  also hold the settling transient after electrode insertion: CH1-CH5 swing to
  +-5 mV there and never again). Every other
  gap (single-sample dropouts, and logger pauses of 4, 60, 90 and 102 samples)
  is **linearly interpolated** so the channels are finite end to end — the
  registration check wants a finite head and tail, and several adapters refuse
  NaN. Each filled run is listed per channel in the manifest (``gaps_filled``)
  so the fill is reversible from the raw file. Nothing else is altered: the
  large excursions on Schizophyllum CH6 (to -71 mV) and Enoki CH3 (to 36 mV)
  are the logger's values and are kept.

Output (the recording kind's convention, docs/DATA_REGISTRATION.md):

    DATA/derived/channels/<stem>/CH0.npy … CH6.npy   1-D float64, millivolts
    DATA/derived/channels/<stem>/manifest.json       source_file, fs, units, …

Stems are the species' binomials: Cordyceps_militaris_fs1, Flammulina_velutipes_fs1,
Omphalotus_nidiformis_fs1, Schizophyllum_commune_fs1. ``source_file`` in the
manifest is the raw file's exact name, since that is the recordings key.

Usage
-----
    python scripts/derive_adamatzky_four_species.py --dry-run     # read, report, write nothing
    python scripts/derive_adamatzky_four_species.py               # derive all four (skips a complete stem)
    python scripts/derive_adamatzky_four_species.py --only Schizophyllum_commune_fs1 --force

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

FS = 1.0
UNITS = "mV"
N_CHANNELS = 7
SOURCE_DOI = "10.5281/zenodo.5790768"
SOURCE_TITLE = "Recordings of electrical activity of four species of fungi (Adamatzky, Zenodo, 2021-12-18, CC BY 4.0)"
PAPER = "Adamatzky A. 2022. Language of fungi derived from their electrical spiking activity. R. Soc. Open Sci. 9:211926. doi:10.1098/rsos.211926"
FS_NOTE = ("1.0 Hz is inferred, not read from the file: the PicoLog export carries no time column. The rate is "
           "documented by the source record (Zenodo 10.5281/zenodo.5790768) and the paper (RSOS 9:211926): "
           "'We recorded electrical activity one sample per second', the ADC-24 averaging up to 600 measurements "
           "per sample ('Ave.' in the column headers). Corroborated on 2026-10-13 against the paper's figure 3, "
           "whose time axes in seconds end where the files do (C. militaris 1.9e6 s = 1,900,145 rows; F. velutipes "
           "1.08e6 s = 1,078,434 finite rows; S. commune 2.6e5 s = 263,959 rows) and whose mV axes match the files' "
           "ranges. Rows are the logger's fixed-interval samples, so the time base is uniform; samples the logger "
           "did not take are NaN rows in the export (see preprocessing).")
CHANNEL_PAIRS = [f"Differential {2 * i + 1} - {2 * i + 2}" for i in range(N_CHANNELS)]

# stem -> (raw file name, species, common name)
SOURCES = {
    "Cordyceps_militaris_fs1": ("Cordyceps militari.txt", "Cordyceps militaris", "caterpillar fungus"),
    "Flammulina_velutipes_fs1": ("Enoki fungi Flammulina velutipes.txt", "Flammulina velutipes", "enoki"),
    "Omphalotus_nidiformis_fs1": ("Ghost Fungi Omphalotus nidiformis.txt", "Omphalotus nidiformis", "ghost fungus"),
    "Schizophyllum_commune_fs1": ("Schizophyllum commune.txt", "Schizophyllum commune", "split gill"),
}


def read_export(path: str) -> tuple[np.ndarray, dict]:
    """The seven electrode columns of a PicoLog export as an (n, 7) float64
    array, NaN where the logger wrote NaN. Returns facts about the file too."""
    import pandas as pd
    with open(path, "r", encoding="utf-8") as f:
        header = f.readline().rstrip("\r\n").split("\t")
    labels = [h for h in header if h.strip()]
    if labels != [f"{p} Ave. (mV)" for p in CHANNEL_PAIRS]:
        raise SystemExit(f"{path}: unexpected header {header!r}")
    # count fields per data line: the only way to see the Cordyceps spreadsheet artefact
    from collections import Counter
    fields = Counter()
    with open(path, "rb") as f:
        f.readline()
        for line in f:
            fields[line.count(b"\t") + 1] += 1
    df = pd.read_csv(path, sep="\t", header=None, skiprows=1, usecols=range(N_CHANNELS),
                     dtype=np.float64, na_values=["NaN", "nan", ""], engine="c")
    X = np.ascontiguousarray(df.to_numpy(dtype=np.float64))
    assert X.shape[1] == N_CHANNELS, X.shape
    assert X.shape[0] == sum(fields.values()), (X.shape, fields)
    facts = {"header": header, "n_rows": int(X.shape[0]), "fields_per_line": {str(k): v for k, v in sorted(fields.items())},
             "raw_extrema_mV": {f"CH{c}": {"min": float(np.nanmin(X[:, c])), "max": float(np.nanmax(X[:, c])),
                                           "n_nan": int(np.isnan(X[:, c]).sum())} for c in range(N_CHANNELS)}}
    if len(header) > N_CHANNELS:
        facts["extra_columns_dropped"] = (f"columns {N_CHANNELS + 1}-{len(header)} (unlabelled) present on the first "
                                          f"{fields.get(len(header), 0):,} data rows only — 1,048,576 is Excel's row limit, so a "
                                          "spreadsheet round-trip added them; dropped, the electrode columns are intact")
    return X, facts


def nan_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """(start, length) of every run of True in a 1-D boolean mask."""
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return []
    cuts = np.flatnonzero(np.diff(idx) > 1)
    starts = np.concatenate(([idx[0]], idx[cuts + 1]))
    ends = np.concatenate((idx[cuts], [idx[-1]]))
    return [(int(s), int(e - s + 1)) for s, e in zip(starts, ends)]


def trim_bounds(X: np.ndarray) -> tuple[int, int]:
    """Rows to drop at the head and tail: a row is dropped while ANY channel
    is NaN there, so every channel starts and ends finite and stays aligned."""
    anynan = ~np.isfinite(X).all(axis=1)
    n = X.shape[0]
    head = 0
    while head < n and anynan[head]:
        head += 1
    tail = 0
    while tail < n - head and anynan[n - 1 - tail]:
        tail += 1
    return head, tail


def fill_gaps(x: np.ndarray) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Linear interpolation across every interior NaN run of a channel whose
    first and last samples are finite. Returns the filled copy and the runs."""
    fin = np.isfinite(x)
    assert fin[0] and fin[-1], "fill_gaps wants a finite head and tail (trim first)"
    runs = nan_runs(~fin)
    if not runs:
        return x, []
    idx = np.arange(x.size)
    y = x.copy()
    y[~fin] = np.interp(idx[~fin], idx[fin], x[fin])
    return y, runs


def derive(stem: str, dry: bool, force: bool) -> None:
    raw_name, species, common = SOURCES[stem]
    src = os.path.join(RAW, raw_name)
    final = os.path.join(CHANNELS, stem)
    if os.path.isdir(final) and not force:
        have = sorted(fn for fn in os.listdir(final) if fn.endswith(".npy"))
        if len(have) == N_CHANNELS and os.path.isfile(os.path.join(final, "manifest.json")):
            print(f"[{stem}] complete ({len(have)} channels + manifest), skipped — pass --force to redo")
            return
    print(f"[{stem}] reading {src}")
    X, facts = read_export(src)
    n_raw = X.shape[0]
    head, tail = trim_bounds(X)
    Xt = X[head:n_raw - tail]
    n = Xt.shape[0]
    print(f"[{stem}] {n_raw:,} rows x {N_CHANNELS}; fields/line {facts['fields_per_line']}; "
          f"trim head {head:,} / tail {tail:,} -> {n:,} samples = {n / FS / 3600:.1f} h at {FS:g} Hz")
    channels, gaps = [], {}
    for c in range(N_CHANNELS):
        y, runs = fill_gaps(np.ascontiguousarray(Xt[:, c]))
        channels.append(y)
        gaps[f"CH{c}"] = [[s, L] for s, L in runs]
        n_filled = sum(L for _s, L in runs)
        longest = max((L for _s, L in runs), default=0)
        print(f"[{stem}]   CH{c} ({CHANNEL_PAIRS[c]}): {n_filled:,} samples in {len(runs)} gaps filled "
              f"(longest {longest}); min {y.min():.3f} max {y.max():.3f} mV")
        assert np.isfinite(y).all()
    if dry:
        return
    os.makedirs(CHANNELS, exist_ok=True)
    staging = os.path.join(CHANNELS, f".staging_{stem}_{os.getpid()}")
    if os.path.isdir(staging):
        shutil.rmtree(staging)
    os.makedirs(staging)
    for c, y in enumerate(channels):
        np.save(os.path.join(staging, f"CH{c}.npy"), y)
    manifest = {
        "source_file": raw_name,
        "raw_file": f"DATA/raw/{raw_name}",
        "n_channels": N_CHANNELS,
        "fs": FS,
        "fs_note": FS_NOTE,
        "n_samples_per_channel": int(n),
        "dtype": "float64",
        "units": f"{UNITS} as stored (the export's column headers say '(mV)'; nothing is rescaled)",
        "imported_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "derived_by": "scripts/derive_adamatzky_four_species.py on 2026-10-13",
        "species": species,
        "common_name": common,
        "source": {"doi": SOURCE_DOI, "title": SOURCE_TITLE, "paper": PAPER, "license": "CC BY 4.0",
                   "creator": "Andrew Adamatzky (Unconventional Computing Laboratory, UWE Bristol)"},
        "logger": "Pico Technology ADC-24, 24-bit; each sample is the average of the logger's measurements "
                  "over the one-second interval ('Ave.' in the headers)",
        "electrodes": "pairs of iridium-coated stainless steel sub-dermal needle electrodes (Spes Medica), 1-2 cm apart; "
                      "each channel is the potential difference across one pair (the record says eight pairs were "
                      "logged; the export holds seven)",
        "channel_pairs": {f"CH{c}": CHANNEL_PAIRS[c] for c in range(N_CHANNELS)},
        "preprocessing": {
            "raw_rows": int(n_raw),
            "rows_dropped_head": int(head),
            "rows_dropped_tail": int(tail),
            "sample_index_note": "derived sample i is raw data row i + rows_dropped_head (rows counted from the first data line)",
            "why_trimmed": ("rows where any channel was NaN at the start or end of the file were dropped from all "
                            "channels together, so every channel is finite at both ends and the channels stay aligned"),
            "gap_fill": "linear interpolation across every interior run of NaN (a sample the logger did not take)",
            "gaps_filled": gaps,
            "n_samples_filled": {k: int(sum(L for _s, L in v)) for k, v in gaps.items()},
            "values_altered_otherwise": "none: no rescaling, filtering, detrending or clipping",
        },
        "raw_file_facts": facts,
    }
    with open(os.path.join(staging, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    if os.path.isdir(final):
        shutil.rmtree(final)
    os.replace(staging, final)
    print(f"[{stem}] wrote {final}: CH0..CH{N_CHANNELS - 1}.npy ({n:,} float64 each) + manifest.json")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="read and report, write nothing")
    ap.add_argument("--only", action="append", default=[], help="restrict to these stems (repeatable)")
    ap.add_argument("--force", action="store_true", help="rederive a stem that is already complete")
    args = ap.parse_args()
    for stem in SOURCES:
        if args.only and stem not in args.only:
            continue
        derive(stem, args.dry_run, args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
