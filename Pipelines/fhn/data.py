"""
Read-only inputs for the FHN fits: a drop sequence's events, its cycles, its mean cycle, and the
two nulls a "good fit" is judged against.

* Sequences are rows of the database's `sequences` table (opened `mode=ro`); their events are the
  drop-motif store's rows (`Plots/drop_motifs12a/motifs_PARTIAL/motifs.csv`) on the same catalogue
  id and stored channel, between the run's first and last onset (`Plots/drop_motifs11/sequences.csv`,
  the file the table was imported from). See docs/rq_roundB/notes/drop-motif-sequences.md.
* Samples come from the channel's `npy_path`, memory-mapped read-only, and are converted to mV
  from the recording's `units` column (V -> x1000).
* A cycle runs from 10 % of its length before one onset to 10 % before the next (so the drop sits
  at tau = 0.1), with the chord between the pre-onset levels at its two ends subtracted (as
  `interrogation.cycle_shapes`' default `cycle_detrend = chord`), resampled to n points. Cycles
  shorter than 0.6 x or longer than 1.6 x the run's median gap are left out (a split drop / a gap).
* Null 1, quiet pseudo-cycles: windows of the median cycle length cut where the store has no
  event (none within a quarter cycle either side), inside the stretch the store covered on that
  recording, put through the identical cycle pipeline and averaged in the same number. The
  W3 `chain_cycles` background null, rebuilt here (Adapters/ is not imported).
* Null 2, phase-randomised surrogate: the sequence's own stretch with its Fourier phases
  randomised (amplitude spectrum, hence the periodicity peak, kept), cut at the real onsets.
"""

import csv
import sqlite3
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
DB = REPO / "DATA" / "db" / "annotations.sqlite"
STORE = REPO / "Plots" / "drop_motifs12a" / "motifs_PARTIAL" / "motifs.csv"
SEQ_CSV = REPO / "Plots" / "drop_motifs11" / "sequences.csv"
HELD_OUT_RECORDINGS = set(range(49, 65))          # M4_aug_concat_fs1: never read
PRE_FRAC = 0.1
N_POINTS = 200
GAP_RULE = (0.6, 1.6)


def _ro():
    return sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)


def recording(rec_id):
    if int(rec_id) in HELD_OUT_RECORDINGS:
        raise PermissionError(f"recording {rec_id} is the held-out M4 recording")
    with _ro() as c:
        row = c.execute("select source_file, channel, fs, n_samples, npy_path, units from recordings where id = ?",
                        (int(rec_id),)).fetchone()
    if row is None:
        raise KeyError(rec_id)
    src, ch, fs, n, path, units = row
    if "M4_aug_concat_fs1" in src:
        raise PermissionError("M4_aug_concat_fs1 is held out")
    return dict(id=int(rec_id), source_file=src, channel=int(ch), fs=float(fs), n_samples=int(n),
                npy_path=str(REPO / path), units=units or "V")


def to_mv_factor(units):
    u = (units or "V").strip()
    if u == "V":
        return 1000.0
    if u == "mV":
        return 1.0
    raise ValueError(f"unknown units {units!r}")


def load_mv(rec, start, stop):
    x = np.load(rec["npy_path"], mmap_mode="r")
    seg = np.array(x[max(0, int(start)):min(len(x), int(stop))], dtype=float) * to_mv_factor(rec["units"])
    bad = ~np.isfinite(seg)
    if bad.any() and (~bad).sum() > 2:
        i = np.arange(seg.size)
        seg[bad] = np.interp(i[bad], i[~bad], seg[~bad])
    return seg


def _store_rows():
    with open(STORE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sequence(seq_id):
    """The sequence row, its recording, and its event onsets/troughs (recording-local samples)."""
    with _ro() as c:
        row = c.execute("select id, sequence_key, recording_id, channel, start_idx, end_idx, n_events from sequences "
                        "where id = ?", (int(seq_id),)).fetchone()
    sid, key, rec_id, ch, s0, s1, n = row
    rec = recording(rec_id)
    with open(SEQ_CSV, newline="", encoding="utf-8") as f:
        meta = next(r for r in csv.DictReader(f) if r["sequence_key"] == key)
    fs = rec["fs"]
    lo, hi = float(meta["start_onset_s"]) * fs - 0.5, float(meta["end_onset_s"]) * fs + 0.5
    rows = [r for r in _store_rows() if r["catalogue_id"] == meta["catalogue_id"] and r["channel"] == meta["channel"]]
    ev = sorted((int(r["onset_idx"]), int(r["trough_idx"])) for r in rows if lo <= int(r["onset_idx"]) <= hi)
    onsets = np.array([e[0] for e in ev])
    troughs = np.array([e[1] for e in ev])
    if len(onsets) != int(n):
        raise ValueError(f"sequence {sid}: {len(onsets)} store events, the table says {n}")
    all_rec = [r for r in _store_rows() if str(r["recording_id"]) == str(rec_id)]
    return dict(id=int(sid), key=key, recording=rec, n_events=int(n), onsets=onsets, troughs=troughs,
                species=meta["species"], median_gap_s=float(meta["median_interval_s"]),
                store_onsets=np.array(sorted(int(r["onset_idx"]) for r in all_rec)),
                store_cover=(min(int(r["onset_idx"]) for r in all_rec), max(int(r["trough_idx"]) for r in all_rec)))


def cut_cycle(x, a, b, n_points=N_POINTS, pre=PRE_FRAC):
    """One cycle of x between anchors a < b (sample indices into x): from a - pre L to b - pre L,
    chord-detrended between the pre-anchor levels at its two ends, resampled to n_points."""
    L = b - a
    s0, s1 = a - pre * L, b - pre * L
    if s0 < 1 or s1 > len(x) - 2:
        return None
    k = max(2, int(round(0.05 * L)))
    lvl0 = np.median(x[max(0, a - k):a + 1])
    lvl1 = np.median(x[max(0, b - k):b + 1])
    pos = s0 + (s1 - s0) * np.arange(n_points) / n_points
    y = np.interp(pos, np.arange(len(x)), x)
    tau = np.arange(n_points) / n_points
    # the chord through the pre-anchor levels, placed at the anchors (tau = pre and 1 + pre)
    chord = lvl0 + (lvl1 - lvl0) * (tau - pre)
    return y - chord


def cycles(x, anchors, n_points=N_POINTS, gap_rule=GAP_RULE, x_offset=0):
    """Cycles between consecutive anchors (recording samples; x starts at sample x_offset)."""
    a = np.asarray(anchors) - x_offset
    L = np.diff(a)
    med = np.median(L)
    keep, out, lens = [], [], []
    for k in range(len(L)):
        if not (gap_rule[0] * med <= L[k] <= gap_rule[1] * med):
            continue
        c = cut_cycle(x, int(a[k]), int(a[k + 1]), n_points)
        if c is not None:
            out.append(c)
            lens.append(L[k])
            keep.append(k)
    return np.array(out), np.array(lens, float), np.array(keep)


def sequence_cycles(seq, n_points=N_POINTS):
    rec = seq["recording"]
    on = seq["onsets"]
    L = np.median(np.diff(on))
    s0, s1 = int(on[0] - 2 * L), int(on[-1] + 2 * L)
    s0 = max(0, s0)
    x = load_mv(rec, s0, s1)
    C, lens, keep = cycles(x, on, n_points, x_offset=s0)
    return dict(x=x, x_start=s0, cycles=C, lengths_samples=lens, kept=keep, mean=C.mean(axis=0),
                tau=np.arange(n_points) / n_points, median_len_samples=float(np.median(lens)))


def quiet_windows(seq, L, margin=0.25, stride_frac=0.25):
    """Starts of length-L windows with no store event within margin*L either side, inside the
    stretch the store covered on this recording."""
    ev = seq["store_onsets"]
    lo, hi = seq["store_cover"]
    starts = np.arange(lo + margin * L, hi - (1 + margin) * L, max(1.0, stride_frac * L))
    ok = []
    for s in starts:
        a, b = s - margin * L, s + (1 + margin) * L
        i = np.searchsorted(ev, a)
        if i >= len(ev) or ev[i] > b:
            ok.append(int(s))
    return np.array(ok, dtype=int)


def quiet_null_means(seq, n_cycles, L, n_draws, seed=0, n_points=N_POINTS, min_windows=8):
    """n_draws mean pseudo-cycles, each the mean of n_cycles quiet windows (with replacement)."""
    W = quiet_windows(seq, L)
    if len(W) < min_windows:
        return None, len(W)
    rng = np.random.default_rng(seed)
    rec = seq["recording"]
    pad = int(np.ceil(0.2 * L)) + 4
    means = []
    for _ in range(n_draws):
        pick = rng.choice(W, size=n_cycles, replace=True)
        cs = []
        for s in pick:
            a = int(s + PRE_FRAC * L)                    # an "anchor" placed as a real one would be
            x = load_mv(rec, a - pad, a + int(L) + pad)
            c = cut_cycle(x, pad, pad + int(L), n_points)
            if c is not None:
                cs.append(c)
        means.append(np.mean(cs, axis=0))
    return np.array(means), len(W)


def phase_randomise(x, rng):
    X = np.fft.rfft(x - x.mean())
    ph = rng.uniform(0, 2 * np.pi, X.size)
    ph[0] = 0.0
    if x.size % 2 == 0:
        ph[-1] = 0.0
    return np.fft.irfft(np.abs(X) * np.exp(1j * ph), n=x.size) + x.mean()


def surrogate_null_means(seqc, seq, n_draws, seed=0, n_points=N_POINTS):
    rng = np.random.default_rng(seed + 1000)
    means = []
    for _ in range(n_draws):
        xs = phase_randomise(seqc["x"], rng)
        C, _, _ = cycles(xs, seq["onsets"], n_points, x_offset=seqc["x_start"])
        means.append(C.mean(axis=0))
    return np.array(means)
