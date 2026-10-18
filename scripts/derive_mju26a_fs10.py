"""
derive_mju26a_fs10.py
=====================
MJu26a on a uniform 10 Hz grid, registered as the new recording
``MJu26a_fs10`` and made the parent of L_LM_Jul_26_J_raw_fs10
(datasets-derive, 2026-10-18).

Why. ``MJu26a.mat`` holds a matrix ``M`` (16 channels) and a time vector ``t``
that is NOT uniform (dt 0.124-2.83 s, median 0.138 s). ``rederive_channels.py``
wrote the rows as they are with fs = 1/median(dt) = 7.246 Hz, which puts
~636 h of real time on a 564 h axis. L_LM_Jul_26_J_raw_fs10 is a 10 Hz x1000
(millivolt) copy of five of its channels. The researcher decided (grilling,
2026-10-18): put every row on a uniform 10 Hz grid by linear interpolation in
``t``, register it as a NEW recording (the old rows stay: the step cache and
this week's cluster imports key on their files), declare both as volts, and
link each L_LM channel to the MJu26a_fs10 channel it copies, so Review draws
L_LM's shapes from the parent.

What it does, in order -- everything that can refuse runs before anything is
written:

1. reads ``t`` (h5py; v7.3), takes it as seconds unless it carries a MATLAB
   datenum signature (``--t-unit`` overrides), and prints its dt statistics;
2. sizes the grid: ``floor(span x 10) + 1`` samples from ``t[0]``;
3. ALIGNS: for every L_LM channel and every MJu26a channel, on three windows
   (25 / 50 / 75 % through the child, ``--window`` samples each), it puts the
   MJu26a channel on the 10 Hz grid over the window +- ``--max-lag`` samples,
   high-passes both (minus a ``--hp``-sample moving mean: the slow drift is
   shared by every channel and would make them all look alike), and finds the
   lag of the best normalised correlation. A child is linked to the parent
   channel whose correlation is >= ``--min-r`` (0.999) on all three windows
   AT THE SAME OFFSET; the parents must all differ. Otherwise the script
   prints the full table and REFUSES: nothing is written;
4. writes ``<data-root>/derived/channels/MJu26a_fs10/CH0..CH15.npy`` +
   ``manifest.json`` (one channel in memory at a time), registers it through
   the registry with ``source_file = MJu26a_fs10.mat`` (a recording's identity
   is its source file, and the old rows keep ``MJu26a.mat``), declares V on the
   new rows and on the old ``MJu26a.mat`` rows (``declare_units``), links the
   L_LM rows (``Working.registration.kinds.link_parent``, decimation 1,
   ``parent_offset`` = the offset found), sets the display name, and writes
   audit lines.

Usage
-----
    python scripts/derive_mju26a_fs10.py --dry-run      # read, align, print; write nothing
    python scripts/derive_mju26a_fs10.py                # derive + register + declare + link
    python scripts/derive_mju26a_fs10.py --skip-link    # derive + register + declare without the L_LM link
    ... --db <sqlite> --data-root <dir>                 # defaults: <repo>/DATA

Exit status: 0 done (or a clean dry run), 2 refused before writing anything,
3 failed after writing (the new stem directory is removed again).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
for _p in (_REPO, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402

from derive_raw_mat import (  # noqa: E402,F401  (re-exported: the tests reach them here)
    Refusal, axis_facts, open_ro, register_stem, resample_uniform, set_display_name, time_in_seconds, write_channels,
)

ACTOR = "scripts/derive_mju26a_fs10.py"
STEM = "MJu26a_fs10"
SOURCE_FILE = "MJu26a_fs10.mat"
RAW_NAME = "MJu26a.mat"
OLD_SOURCE = "MJu26a.mat"
CHILD_SOURCE = "L_LM_Jul_26_J_raw.mat"
DISPLAY = "MJu26a (10 Hz)"
WINDOW_FRACS = (0.25, 0.5, 0.75)


# ------------------------------------------------------------ the raw file --

class RawMJu:
    """MJu26a.mat (v7.3): the matrix and the time vector, read lazily."""

    def __init__(self, path: str, variable: str = "M", t_unit: str | None = None):
        import h5py
        self.path = path
        self.f = h5py.File(path, "r")
        if variable not in self.f or "t" not in self.f:
            have = [k for k in self.f.keys() if not k.startswith("#")]
            raise Refusal(f"{path}: expected variables {variable!r} and 't', found {have}")
        self.M = self.f[variable]
        if len(self.M.shape) != 2:
            raise Refusal(f"{variable} has shape {self.M.shape}")
        self.ch_axis = int(np.argmin(self.M.shape))
        self.n_channels = int(self.M.shape[self.ch_axis])
        self.n = int(self.M.shape[1 - self.ch_axis])
        t_raw = np.asarray(self.f["t"][()], dtype=np.float64).ravel()
        if len(t_raw) != self.n:
            raise Refusal(f"t has {len(t_raw):,} values for {self.n:,} samples")
        self.t, self.t_note = time_in_seconds(t_raw, t_unit)
        self.ax = axis_facts(self.t)
        self.tr = self.t - self.t[0]

    def row(self, c: int, j0: int = 0, j1: int | None = None) -> np.ndarray:
        j1 = self.n if j1 is None else j1
        sl = self.M[c, j0:j1] if self.ch_axis == 0 else self.M[j0:j1, c]
        return np.asarray(sl, dtype=np.float64)

    def on_grid(self, c: int, a: int, b: int, fs: float) -> np.ndarray:
        """Channel ``c`` on grid samples ``[a, b)`` -- the same numbers
        ``resample_uniform`` gives for those samples (np.interp is local)."""
        g = np.arange(a, b, dtype=np.float64) / fs
        j0 = max(int(np.searchsorted(self.tr, g[0], side="right")) - 1, 0)
        j1 = min(int(np.searchsorted(self.tr, g[-1], side="left")) + 2, self.n)
        return np.interp(g, self.tr[j0:j1], self.row(c, j0, j1))

    def close(self):
        self.f.close()


def grid_len(span_s: float, fs: float) -> int:
    return int(np.floor(span_s * fs + 1e-9)) + 1


# ------------------------------------------------------------- alignment --

def highpass(x, width: int) -> np.ndarray:
    from scipy.ndimage import uniform_filter1d
    x = np.asarray(x, dtype=np.float64)
    return x - uniform_filter1d(x, size=int(width), mode="nearest")


def best_lag(window, segment):
    """``(r, lag)``: the lag into ``segment`` where ``window`` correlates best.
    Uses the registry's FFT normalised cross-correlation
    (``Working.registration.excerpt._xcorr_all``) rather than a second one."""
    from Working.registration.excerpt import _xcorr_all
    x = np.asarray(window, dtype=np.float64)
    if not (np.isfinite(x).all() and np.isfinite(segment).all()):
        return 0.0, None
    x = x - x.mean()
    sd = x.std()
    if sd == 0 or len(segment) < len(x):
        return 0.0, None
    r = _xcorr_all(x / sd, np.asarray(segment, dtype=np.float64))
    i = int(np.argmax(r))
    return float(r[i]), i


def align(raw: RawMJu, children: list, fs: float, m: int, window: int, max_lag: int, hp: int, min_r: float):
    """Every (child, parent) pair on every window. Returns ``(table, links,
    problems)``: ``table[child_ch][parent_ch] = [(r, offset), ...]`` per window,
    ``links`` = one accepted link per child, ``problems`` = why any was not."""
    table, links, problems = {}, [], []
    wins = {}
    for ch in children:
        x = np.load(ch["npy_path"], mmap_mode="r")
        nc = len(x)
        if nc < window:
            raise Refusal(f"{ch['npy_path']} holds {nc:,} samples, fewer than one {window:,}-sample window")
        wins[ch["channel"]] = []
        for frac in WINDOW_FRACS:
            c0 = max(0, min(int(frac * nc) - window // 2, nc - window))
            lo = max(0, c0 - hp)
            xw_full = highpass(np.asarray(x[lo:c0 + window + hp], dtype=np.float64), hp)
            wins[ch["channel"]].append((c0, xw_full[c0 - lo:c0 - lo + window],
                                        np.asarray(x[c0:c0 + window], dtype=np.float64)))
        table[ch["channel"]] = {p: [None] * len(WINDOW_FRACS) for p in range(raw.n_channels)}
        del x
    # one parent segment in memory at a time; children at the same window position share it
    for p in range(raw.n_channels):
        for k in range(len(WINDOW_FRACS)):
            spans = {}
            for c, ws in wins.items():
                c0 = ws[k][0]
                spans.setdefault((max(0, c0 - max_lag), min(m, c0 + window + max_lag)), []).append(c)
            for (a, b), chans in spans.items():
                seg = highpass(raw.on_grid(p, a, b, fs), hp)
                for c in chans:
                    c0, xw, _xraw = wins[c][k]
                    r, lag = best_lag(xw, seg)
                    table[c][p][k] = (r, None if lag is None else a + lag - c0)
                del seg
    for ch in children:
        wins_c = wins[ch["channel"]]
        # the parent whose WORST window is best
        p_best = max(table[ch["channel"]], key=lambda q: min(r for r, _o in table[ch["channel"]][q]))
        res = table[ch["channel"]][p_best]
        offs = {o for _r, o in res}
        rmin = min(r for r, _o in res)
        if rmin < min_r:
            problems.append(f"L_LM CH{ch['channel']}: best parent MJu26a CH{p_best} reaches r = {rmin:.5f} on its "
                            f"worst window, below {min_r}")
            continue
        if len(offs) != 1 or None in offs:
            problems.append(f"L_LM CH{ch['channel']}: MJu26a CH{p_best} correlates (r >= {rmin:.5f}) but at "
                            f"different offsets on the three windows {sorted(o for o in offs if o is not None)}")
            continue
        off = offs.pop()
        # gain and intercept on the raw (not high-passed) middle window: the x1000 of mV against V
        c0, _xw, xraw = wins_c[len(wins_c) // 2]
        praw = raw.on_grid(p_best, c0 + off, c0 + off + window, fs)
        g, b0 = np.polyfit(praw, xraw, 1)
        r_raw = float(np.corrcoef(praw, xraw)[0, 1])
        links.append({"child_id": ch["id"], "child_channel": ch["channel"], "parent_channel": p_best,
                      "offset": int(off), "r_windows": [round(r, 6) for r, _o in res],
                      "gain": float(g), "intercept": float(b0), "r_raw": r_raw})
    parents = [lk["parent_channel"] for lk in links]
    dup = sorted({p for p in parents if parents.count(p) > 1})
    if dup:
        problems.append(f"two L_LM channels choose the same MJu26a channel(s) {dup}")
    return table, links, problems


def print_table(table, n_parents):
    print("   best r per (L_LM channel, MJu26a channel), worst of the three windows (high-passed):")
    print("   L_LM \\ MJu " + " ".join(f"{p:>6}" for p in range(n_parents)))
    for c, row in table.items():
        print(f"   CH{c:<9}" + " ".join(f"{min(r for r, _o in row[p]):6.3f}" for p in range(n_parents)))


# ------------------------------------------------------------------- main --

def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", default=os.path.join(_REPO, "DATA"), help="default: <repo>/DATA")
    ap.add_argument("--db", help="default: <data-root>/db/annotations.sqlite")
    ap.add_argument("--raw", help=f"default: <data-root>/raw/{RAW_NAME}")
    ap.add_argument("--variable", default="M", help="the data matrix in the raw file (default M)")
    ap.add_argument("--t-unit", choices=("s", "days"), help="the unit of t (default: seconds unless it looks like a MATLAB datenum)")
    ap.add_argument("--fs", type=float, default=10.0, help="the uniform grid rate (default 10 Hz, the researcher's choice)")
    ap.add_argument("--child-source", default=CHILD_SOURCE, help=f"the child recording's source file (default {CHILD_SOURCE})")
    ap.add_argument("--window", type=int, default=10_000, help="samples per alignment window (default 10,000)")
    ap.add_argument("--max-lag", type=int, help="offsets searched either side (default 36,000 + |grid length - child length|)")
    ap.add_argument("--hp", type=int, default=601, help="high-pass: subtract a moving mean this many samples wide (default 601 = 60 s)")
    ap.add_argument("--min-r", type=float, default=0.999, help="the correlation a link needs on every window (default 0.999)")
    ap.add_argument("--skip-link", action="store_true", help="derive, register and declare units without linking L_LM")
    ap.add_argument("--dry-run", action="store_true", help="read, align and print; write nothing")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    data_root = os.path.abspath(args.data_root)
    db = args.db or os.path.join(data_root, "db", "annotations.sqlite")
    channels_root = os.path.join(data_root, "derived", "channels")
    raw_path = args.raw or os.path.join(data_root, "raw", RAW_NAME)
    fs = float(args.fs)
    raw = None
    try:
        if not os.path.isfile(raw_path):
            raise Refusal(f"{raw_path} does not exist")
        final = os.path.join(channels_root, STEM)
        if os.path.exists(final):
            raise Refusal(f"the stem {final} exists: refusing to write a second copy")
        conn = open_ro(db)
        try:
            if conn.execute("SELECT COUNT(*) FROM recordings WHERE source_file = ?", (SOURCE_FILE,)).fetchone()[0]:
                raise Refusal(f"{SOURCE_FILE} is already registered")
            cols = ("id", "channel", "fs", "n_samples", "npy_path", "parent_recording_id")
            children = [dict(zip(cols, r)) for r in conn.execute(
                f"SELECT {', '.join(cols)} FROM recordings WHERE source_file = ? AND active = 1 ORDER BY channel",
                (args.child_source,))]
            n_old = conn.execute("SELECT COUNT(*) FROM recordings WHERE source_file = ?", (OLD_SOURCE,)).fetchone()[0]
        finally:
            conn.close()
        raw = RawMJu(raw_path, args.variable, args.t_unit)
        ax, dts = raw.ax, raw.ax["dt"]
        m = grid_len(ax["span_s"], fs)
        print(f"== {os.path.basename(raw_path)}: {args.variable} {raw.n_channels} channels x {raw.n:,} samples")
        print(f"   t         {raw.t_note}; t[0] = {raw.t[0]:.6f}; span {ax['span_s']:,.1f} s = {ax['span_s'] / 3600:.2f} h "
              f"= {ax['span_s'] / 86400:.3f} d")
        print(f"   dt        min {dts['min']:.6g} / median {dts['median']:.6g} / mean {dts['mean']:.6g} / max {dts['max']:.6g} s; "
              f"1/median = {ax['rate_of_median']:.6g} Hz -> {raw.n / ax['rate_of_median'] / 3600:.1f} h if read as even "
              f"(the old MJu26a rows: {n_old} registered)")
        print(f"   grid      {m:,} samples at {fs:g} Hz ({m / fs / 3600:.2f} h), linear interpolation in t, "
              f"{raw.n_channels} channels -> {final}  (source_file {SOURCE_FILE}, display name {DISPLAY!r})")
        links = []
        if args.skip_link:
            print("   link      skipped (--skip-link)")
        else:
            if not children:
                raise Refusal(f"no active rows for {args.child_source}: nothing to link (pass --skip-link to derive without)")
            bad = [c for c in children if abs(float(c["fs"]) - fs) > 1e-6 * fs]
            if bad:
                raise Refusal(f"{args.child_source} runs at {bad[0]['fs']:g} Hz, not {fs:g}: decimation 1 needs equal rates")
            linked = [c for c in children if c["parent_recording_id"] is not None]
            if linked:
                raise Refusal(f"{args.child_source} CH{linked[0]['channel']} is already linked to recording "
                              f"{linked[0]['parent_recording_id']}")
            nc = max(int(c["n_samples"]) for c in children)
            max_lag = args.max_lag if args.max_lag is not None else 36_000 + abs(m - nc)
            print(f"   child     {args.child_source}: {len(children)} channels x {nc:,} samples at {fs:g} Hz "
                  f"({nc / fs / 3600:.2f} h); windows of {args.window:,} at {', '.join(f'{f:.0%}' for f in WINDOW_FRACS)}, "
                  f"offsets +-{max_lag:,}, high-pass {args.hp} samples, link needs r >= {args.min_r}")
            table, links, problems = align(raw, children, fs, m, args.window, max_lag, args.hp, args.min_r)
            print_table(table, raw.n_channels)
            for lk in links:
                print(f"   link      L_LM CH{lk['child_channel']} <- MJu26a_fs10 CH{lk['parent_channel']} at offset "
                      f"{lk['offset']:,} (r per window {lk['r_windows']}; raw r {lk['r_raw']:.5f}; "
                      f"L_LM = {lk['gain']:.2f} x MJu26a + {lk['intercept']:.3g})")
            if problems:
                for pr in problems:
                    print(f"   problem   {pr}")
                raise Refusal("L_LM does not align with MJu26a at r ~ 1 for every channel (table above); "
                              "rerun with --skip-link to derive MJu26a_fs10 without the link")
            for lk in links:
                if lk["offset"] < 0:
                    raise Refusal(f"L_LM CH{lk['child_channel']} starts {-lk['offset']:,} samples BEFORE MJu26a_fs10: "
                                  "parent_offset cannot be negative")
        if args.dry_run:
            print("   dry run: nothing written")
            return 0
        return _write(raw, args, channels_root, db, fs, m, links)
    except Refusal as e:
        print(f"   REFUSED   {e}")
        print("   nothing written")
        return 2
    finally:
        if raw is not None:
            raw.close()


def _write(raw: RawMJu, args, channels_root, db, fs, m, links) -> int:
    from Working.database.schema import init_db
    from Working.registration.kinds import declare_units, link_parent
    from Working.registration.settings import append_audit
    ax, dts = raw.ax, raw.ax["dt"]
    gains = ", ".join(f"CH{lk['child_channel']}: x{lk['gain']:.1f}" for lk in links)
    evidence = (f"L_LM_Jul_26_J (verified mV) equals these samples x ({gains}) at r >= "
                f"{min(min(lk['r_windows']) for lk in links):.4f}" if links else "no L_LM alignment was run")
    units_note = f"declared V by the researcher (grilling 2026-10-18), via {ACTOR}: {evidence}"
    manifest = {
        "source_file": SOURCE_FILE, "raw_file": f"DATA/raw/{RAW_NAME}",
        "derived_from": {"stem": "MJu26a", "source_file": OLD_SOURCE, "variable": args.variable},
        "n_channels": raw.n_channels, "fs": fs,
        "fs_note": (f"{fs:g} Hz is the uniform grid every row was linearly interpolated onto (the researcher's choice, "
                    f"2026-10-18); the source time vector t, read from {RAW_NAME} ({raw.t_note}), is uneven: dt min "
                    f"{dts['min']:.6g} s, median {dts['median']:.6g} s, max {dts['max']:.6g} s"),
        "n_samples_per_channel": m, "dtype": "float64",
        "units": f"V -- {units_note}",
        "time_base": f"uniform: sample i is at t[0] + i / {fs:g} s, t[0] = {raw.t[0]:.6f} in {RAW_NAME}'s t",
        "resampling": {"method": f"linear interpolation of each row of {args.variable} in t onto a uniform {1 / fs:g} s grid "
                                 "from t[0] to at or before t[-1]",
                       "source_samples": raw.n, "grid_samples": m, "span_s": ax["span_s"], "source_dt_s": dts,
                       "warning": "a one-sample excursion between two grid points is shared between them and loses up "
                                  "to half its height on the grid; the raw file keeps it in full"},
        "children": [{"source_file": args.child_source, **lk} for lk in links],
        "imported_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "derived_by": f"{ACTOR} (datasets-derive, 2026-10-18)",
    }

    def columns():
        for c in range(raw.n_channels):
            yield resample_uniform(raw.t, raw.row(c), fs)[1]

    final = write_channels(channels_root, STEM, columns(), manifest)
    conn = init_db(db)
    try:
        try:
            ids, rep, dropped = register_stem(conn, channels_root, STEM, {"notes": f"{RAW_NAME} on a uniform {fs:g} Hz grid, by {ACTOR}"},
                                              ACTOR, skip_excerpt_ids=[lk["child_id"] for lk in links])
            by_ch = {int(r[1]): int(r[0]) for r in conn.execute(
                "SELECT id, channel FROM recordings WHERE source_file = ?", (SOURCE_FILE,))}
            done = [link_parent(conn, lk["child_id"], by_ch[lk["parent_channel"]], lk["offset"], 1) for lk in links]
            try:
                declare_units(conn, OLD_SOURCE, "V", units_note.replace("declared V", "declared V (as MJu26a_fs10, its 10 Hz copy)"),
                              actor=ACTOR)
                old_msg = f"declared V on the old {OLD_SOURCE} rows"
            except KeyError:
                old_msg = f"no {OLD_SOURCE} rows to declare"
            conn.commit()
        except Exception:
            conn.rollback()
            # a registration that went through stays; only a stem nothing points at is removed
            if not conn.execute("SELECT COUNT(*) FROM recordings WHERE source_file = ?", (SOURCE_FILE,)).fetchone()[0]:
                shutil.rmtree(final, ignore_errors=True)
            raise
        for d in done:
            append_audit(conn, "registration", f"Linked {d['child']} to its parent {d['parent']} at sample "
                         f"{d['parent_offset']:,} (decimation 1)", "Datasets", actor=ACTOR, detail=d)
        append_audit(conn, "settings", f"Declared V on {SOURCE_FILE} and {OLD_SOURCE}", "Datasets", actor=ACTOR,
                     detail={"units_note": units_note})
        print(f"   registered {len(ids)} rows (ids {ids[0]}..{ids[-1]}) units {rep.facts.get('units')}; {old_msg}; "
              f"{set_display_name(conn, SOURCE_FILE, DISPLAY, ACTOR)}")
        for d in done:
            print(f"   linked    {d['child']} (id {d['child_id']}) -> {d['parent']} (id {d['parent_id']}) at "
                  f"{d['parent_offset']:,}" + (f"; its last {d['overhang']:,} samples run past the parent's end" if d["overhang"] else ""))
        for e in dropped:
            if e["recording_id"] not in {lk["child_id"] for lk in links}:
                print(f"   kept      {e['source_file']} CH{e['channel']} (id {e['recording_id']}) keeps its existing parent "
                      f"(it is also a {e['decimation']}:1 excerpt of CH{e['candidate_channel']}, r = {e['r']})")
        for e in rep.excerpts:
            print(f"   linked    registered {e['source_file']} CH{e['channel']} (id {e['recording_id']}) as a "
                  f"{e['decimation']}:1 excerpt of CH{e['candidate_channel']} at sample {e['offset']:,} (r = {e['r']})")
        for w in rep.warnings:
            print(f"   warning   {w}")
    finally:
        conn.close()
    print(f"   wrote     {final}: CH0..CH{raw.n_channels - 1}.npy + manifest.json")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # loud, with the reason; exit 3 = failed after (possibly) writing
        print(f"   FAILED    {type(e).__name__}: {e}")
        raise SystemExit(3)
