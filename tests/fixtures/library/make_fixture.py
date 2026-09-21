"""
make_fixture.py
===============
Writes the synthetic event store and sequence table that
`tests/test_library_import_event_store.py` and
`tests/test_library_import_sequences.py` import from.

Why a generated fixture rather than a slice of the real stores: the real ones
are 2.5-13 MB of snippets each and none of them contains, in five rows, all of
the cases the importer has to get right. This one is built so that every branch
of `Working/library/importers/event_store.py` has exactly one event to exercise
it, and so the whole bundle stays under 100 kB and can be read by eye.

    ev1  id001_r1_1000    new shape, recording 1 / channel 0, [1000, 1100)
    ev2  id001_r1_5000    a different shape, same recording and channel
    ev3  id002_r2_2000    ev1's waveform EXACTLY, in another recording
                          -> the same entry, a second member (2.4 "exact")
                          -> corpus `reishi_1hz`, so it is also the row the
                             `exclude_corpora` decision drops
    ev4  id003_r1_1010    a near-duplicate of ev1: same recording and channel,
                          IoU 0.818, onset 10 samples out of a 100-sample span
                          -> its OWN entry plus a flag, never merged (2.4 "near")
    ev5  id004_r999_7000  recording_id 999, which no database row binds
                          -> a counted warning and a skip, never a crash

`event_store_partial/` is the same five events under a manifest carrying
`partial: true`. It stands in for `Plots/drop_motifs12a/*_PARTIAL`, which this
machine refuses to import (see `event_store.PARTIAL_STORE_REFUSAL`), so that
the refusal can be tested without shipping 13 MB of Lion's mane snippets.

`sequences.csv` is two rows: one whose member events resolve out of the store by
the verified recovery rule, and one whose endpoints name events no store holds,
which is the `needs_extraction = 1` case.

Regenerate with

    "/c/ProgramData/anaconda3/python.exe" tests/fixtures/library/make_fixture.py

Deterministic: no RNG, and the waveforms are closed-form. Regenerating must
produce byte-identical arrays, because the content hashes the tests assert on
are hashes of these samples.
"""

import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
STORE_DIR = os.path.join(HERE, "event_store")
PARTIAL_DIR = os.path.join(HERE, "event_store_partial")
SEQUENCES_CSV = os.path.join(HERE, "sequences.csv")

FS = 1.0

# The column order the seed store uses, trimmed to what an importer reads plus
# the four tag columns drop_motifs10 added (`corpus`, `species`, `framing` and
# `morphology`). `Working.Detection.drop_motifs.store.load_events` coerces the
# index columns back to int64 by name, so the names have to match its
# `_INT_COLUMNS` exactly or an index arrives as a float and slices nothing.
COLUMNS = [
    "event_id", "span_key", "span_label", "catalogue_id",
    "recording_id", "source_file", "channel", "fs",
    "morphology", "species", "corpus", "framing",
    "onset_idx", "onset_h", "trough_idx",
    "snippet_start_idx", "snippet_end_idx", "snippet_key",
    "drop_depth_mv", "cluster_id",
]


def _drop(n, *, depth=12.0, wobble=0.0):
    """A synthetic fall: flat, a fast drop, a slow recovery.

    `wobble` adds a small closed-form ripple. It is how ev4 is made to be the
    same *kind* of shape as ev1 in the same place without being the same shape:
    the hash has to separate them (so they are two entries) while the span
    arithmetic still calls them near-duplicates (so one is flagged against the
    other). A near-duplicate that also hashed identically would be classified
    `exact` and never reach the flag path at all.
    """
    t = np.linspace(0.0, 1.0, int(n))
    fall = -depth / (1.0 + np.exp(-40.0 * (t - 0.25)))
    recovery = depth * 0.6 * np.clip((t - 0.35) / 0.65, 0.0, 1.0)
    y = fall + recovery
    if wobble:
        y = y + wobble * np.sin(9.0 * np.pi * t)
    return np.round(y, 6)


W1 = _drop(100)                 # ev1 and ev3 — byte-identical, hence one entry
W2 = _drop(120, depth=3.0)      # ev2 — a different shape
W3 = _drop(100, wobble=0.9)     # ev4 — near, not exact


EVENTS = [
    dict(event_id="id001_r1_1000", span_key="id001", span_label="ID 1",
         catalogue_id=1, recording_id=1, source_file="CH0.npy", channel=0,
         morphology="trough", species="oyster", corpus="oyster",
         framing="span", start=1000, values=W1),
    dict(event_id="id001_r1_5000", span_key="id001", span_label="ID 1",
         catalogue_id=1, recording_id=1, source_file="CH0.npy", channel=0,
         morphology="sharkfin", species="oyster", corpus="oyster",
         framing="span", start=5000, values=W2),
    dict(event_id="id002_r2_2000", span_key="id002", span_label="ID 2",
         catalogue_id=2, recording_id=2, source_file="CH1.npy", channel=1,
         # `Stegasauras` is the spelling the catalogue spreadsheet carries and
         # `stegasaurus` is the spelling `tag_vocabulary` already holds; the
         # importer normalises it, and this row is what proves it does.
         morphology="Stegasauras", species="reishi", corpus="reishi_1hz",
         framing="sliding", start=2000, values=W1),
    dict(event_id="id003_r1_1010", span_key="id003", span_label="ID 3",
         catalogue_id=3, recording_id=1, source_file="CH0.npy", channel=0,
         morphology="trough", species="oyster", corpus="oyster",
         framing="span", start=1010, values=W3),
    dict(event_id="id004_r999_7000", span_key="id004", span_label="ID 4",
         catalogue_id=4, recording_id=999, source_file="CH9.npy", channel=9,
         morphology="trough", species="oyster", corpus="oyster",
         framing="span", start=7000, values=_drop(100, depth=25.0)),
]


def _rows_and_arrays():
    rows, arrays = [], {}
    for event in EVENTS:
        values = np.asarray(event["values"], dtype=float)
        start = int(event["start"])
        # End indices are EXCLUSIVE: `len(array) == end - start`, measured
        # across all four real stores (scout 06-data §1). The fixture holds the
        # same invariant so a test that trips over an off-by-one here is
        # reporting a real defect and not a fixture that disagrees with disk.
        end = start + len(values)
        rows.append({
            "event_id": event["event_id"],
            "span_key": event["span_key"],
            "span_label": event["span_label"],
            "catalogue_id": event["catalogue_id"],
            "recording_id": event["recording_id"],
            "source_file": event["source_file"],
            "channel": event["channel"],
            "fs": FS,
            "morphology": event["morphology"],
            "species": event["species"],
            "corpus": event["corpus"],
            "framing": event["framing"],
            "onset_idx": start,
            "onset_h": start / 3600.0,
            "trough_idx": start + int(0.3 * len(values)),
            "snippet_start_idx": start,
            "snippet_end_idx": end,
            "snippet_key": event["event_id"],
            "drop_depth_mv": float(np.round(np.ptp(values), 4)),
            "cluster_id": -1,
        })
        arrays[f"{event['event_id']}__raw_mv"] = values - 450.0
        arrays[f"{event['event_id']}__detrended_mv"] = values
        arrays[f"{event['event_id']}__t_s"] = np.arange(start, end, dtype=float) / FS
    return rows, arrays


def _write_store(out_dir, rows, arrays, manifest):
    os.makedirs(out_dir, exist_ok=True)
    pd.DataFrame(rows, columns=COLUMNS).to_csv(
        os.path.join(out_dir, "events.csv"), index=False)
    np.savez_compressed(os.path.join(out_dir, "snippets.npz"), **arrays)
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)


def main():
    rows, arrays = _rows_and_arrays()

    _write_store(STORE_DIR, rows, arrays, {
        "kind": "drop_motifs_fixture", "version": 1, "n_motifs": len(rows),
        "detector": "synthetic", "partial": False,
        "note": "Generated by tests/fixtures/library/make_fixture.py.",
    })
    _write_store(PARTIAL_DIR, rows, arrays, {
        "kind": "drop_motifs_fixture", "version": 1, "n_motifs": len(rows),
        "detector": "synthetic", "partial": True,
        "regions_present": ["B"], "regions_missing": ["A"],
        "note": "Stands in for Plots/drop_motifs12a/*_PARTIAL — refused.",
    })

    # Sequence one resolves: catalogue 1 / channel 0 holds ev1 (onset 1000) and
    # ev2 (onset 5000) and nothing else, so the recovery rule returns them in
    # that order. Sequence two names endpoints no store holds, which is the
    # needs_extraction case — the claim is recorded, the events are not invented.
    pd.DataFrame([
        {"sequence_key": "oyster_id1_ch0_1000s", "species": "oyster",
         "catalogue_id": 1, "channel": 0,
         "start_event_id": "id001_r1_1000", "end_event_id": "id001_r1_5000",
         "n": 2, "start_onset_s": 1000.0, "end_onset_s": 5000.0,
         "median_interval_s": 4000.0},
        {"sequence_key": "reishi_id77_ch2_999s", "species": "reishi",
         "catalogue_id": 77, "channel": 2,
         "start_event_id": "id077_r7_999", "end_event_id": "id077_r7_4321",
         "n": 9, "start_onset_s": 999.0, "end_onset_s": 4321.0,
         "median_interval_s": 415.0},
    ]).to_csv(SEQUENCES_CSV, index=False)

    for path in (STORE_DIR, PARTIAL_DIR, SEQUENCES_CSV):
        size = (sum(os.path.getsize(os.path.join(path, f)) for f in os.listdir(path))
                if os.path.isdir(path) else os.path.getsize(path))
        print(f"{path}  {size} B")


if __name__ == "__main__":
    main()
