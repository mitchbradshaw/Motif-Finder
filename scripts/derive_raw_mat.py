"""
derive_raw_mat.py
=================
Derive a raw MATLAB matrix into ``<data-root>/derived/channels/<stem>_fs<rate>/``
(``CH0.npy`` .. + ``manifest.json``), register it through the registry, and
declare its unit (datasets-derive, 2026-10-18). Written for the six files the
researcher added to ``DATA/raw`` in October 2026 -- ``CO``, ``LM``, ``SH``,
``SO``, ``F2B`` and ``L_R_Aug_26_PD_raw`` -- and for any later one.

Usage
-----
    python scripts/derive_raw_mat.py DATA/raw/CO.mat --dry-run       # print the inference, write nothing
    python scripts/derive_raw_mat.py CO LM SH SO F2B --dry-run        # names resolve under <data-root>/raw
    python scripts/derive_raw_mat.py CO                               # derive + register + declare units
    python scripts/derive_raw_mat.py L_R_Aug_26_PD_raw --fs 10        # state a rate the file cannot give
    python scripts/derive_raw_mat.py F2B --units mV                   # state a unit the values cannot give
    ... --db <sqlite> --data-root <dir>                               # defaults: <repo>/DATA

Exit status: 0 done (or a clean dry run), 2 refused before writing anything,
3 failed after writing: the file's database writes are rolled back (one
transaction) and its new stem directory is removed, so a rerun starts clean.

What it infers, in plain words
------------------------------
1. **Which variable is the data.** The one numeric 2-D matrix in the file
   whose short side is <= 64 (the channels). Two such matrices refuse until
   ``--variable`` names one. Orientation: the long side is samples.
2. **The sampling rate**, in this order:
   a. a time axis that can be read -- ``--time-file``, else a ``<stem>_time.mat``
      in ``<data-root>/derived/time_axes/`` or beside the raw file (what
      ``scripts/export_mat_time.m`` writes from
      MATLAB's own datetime/duration object), else a numeric vector named
      ``t``/``time`` in the file with one value per sample. A uniform axis gives
      the rate (read); an uneven one is linearly interpolated onto a uniform
      grid at the rate ``--fs`` states (refused without ``--fs``), as MJu26a is.
      A ``--fs`` that contradicts a uniform axis refuses.
   b. no readable axis: the six October files carry their time axis only as a
      MATLAB object (``MatlabOpaque``) that scipy cannot decode, so the count
      rule applies: N = d x 86,400 x 10 + 1 (a whole number of days on a
      uniform 10 Hz grid with its inclusive end sample) gives **10 Hz, inferred
      from the sample count, not read** -- 10 Hz is the lab's logging rate
      (L_LM_Jul_26_J, MJu26a at 10 Hz). Any other count refuses and prints the
      10 Hz and 1 Hz durations, until ``--fs`` states the rate (recorded as
      inferred: not read from the file).
3. **The unit**, from the value range: 99 % of |samples| below 2 is volts (a
   bioelectric signal in the +-1 V range); between 20 and 5000 is millivolts
   (the hundreds); anything else refuses until ``--units`` states it. Written as
   ``units`` with the reason, so the registry records the note.

Then it writes the stem through a staging directory, registers it through the
registry (``Working.registration``: scan, check, register -- never a hand-made
row), sets the dataset's display name (the file stem without ``_raw``), and
writes an audit line. An existing stem directory or registered source file
refuses. ``--dry-run`` opens the database read-only and writes nothing.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import sqlite3
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import numpy as np  # noqa: E402

LAB_FS = 10.0                    # the lab's logging rate: the one the count rule accepts
UNIFORM_RTOL = 1e-3              # an axis is uniform when max(dt) - min(dt) <= this x median(dt)
V_MAX = 2.0                      # 99th percentile of |x| at or below this: volts
MV_RANGE = (20.0, 5000.0)        # ... inside this: millivolts
MAX_CHANNELS = 64
TIME_NAMES = ("t", "time", "tt", "t_s", "times", "timestamp", "timestamps")
ACTOR = "scripts/derive_raw_mat.py"


class Refusal(Exception):
    """An inference that is not certain enough to write on. The message says
    what is missing and which flag states it."""


# ------------------------------------------------------------ the rules --

def fs_token(fs: float) -> str:
    """10.0 -> 'fs10', 0.8 -> 'fs0p8' (the rule of ``derive_dwij_mfs2.fs_token``;
    not imported because that module changes directory on import)."""
    s = f"{float(fs):.4g}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return "fs" + s.replace(".", "p")


def _days(n_minus_1: int, fs: float) -> float:
    return n_minus_1 / (86400.0 * fs)


def infer_fs_from_count(n: int):
    """``(fs, note)``: 10 Hz when ``n - 1`` is a whole number of days at 10 Hz,
    else ``(None, why)`` naming the 10 Hz and 1 Hz durations."""
    n = int(n)
    d10 = _days(n - 1, LAB_FS)
    if n > 1 and (n - 1) % int(86400 * LAB_FS) == 0:
        others = [f"{fs:g} Hz = {_days(n - 1, fs):g} d" for fs in (1.0, 2.0, 5.0, 20.0)
                  if (n - 1) % int(86400 * fs) == 0]
        note = (f"{LAB_FS:g} Hz inferred from the sample count, not read from the file: {n:,} samples = "
                f"{int(round(d10))} days x 86,400 s x {LAB_FS:g} Hz + 1, the inclusive end sample of a uniform "
                f"{LAB_FS:g} Hz grid ({LAB_FS:g} Hz is the lab's logging rate)")
        if others:
            note += "; the count is also whole days at " + ", ".join(others) + " -- the lab rate was taken"
        return LAB_FS, note
    d1 = _days(n - 1, 1.0)
    return None, (f"{n:,} samples is not a whole number of days at {LAB_FS:g} Hz ({d10:.3g} days) or at "
                  f"1 Hz ({d1:.3g} days), and no time axis could be read: state the rate with --fs")


def infer_units(x):
    """``(unit, note)`` from the value range, or ``(None, why)``."""
    a = np.abs(np.asarray(x, dtype=np.float64).ravel())
    a = a[np.isfinite(a)]
    if not len(a):
        return None, "no finite samples to read a unit from: state it with --units"
    m = float(np.percentile(a, 99))
    if m <= V_MAX:
        return "V", (f"inferred from the value range: 99% of |samples| are below {m:.3g}, the +-1 range of a "
                     "volts recording (as millivolts it would be a sub-millivolt signal)")
    if MV_RANGE[0] <= m <= MV_RANGE[1]:
        return "mV", (f"inferred from the value range: 99% of |samples| are below {m:.4g}, the hundreds of a "
                      "millivolt recording (as volts it would be hundreds of volts)")
    return None, (f"99% of |samples| are below {m:.4g}: neither the +-1 range of volts (<= {V_MAX:g}) nor the "
                  f"hundreds of millivolts ({MV_RANGE[0]:g}-{MV_RANGE[1]:g}); state the unit with --units")


def time_in_seconds(t, unit: str | None = None):
    """``(seconds, note)``. ``unit`` 's' or 'days' forces it; otherwise a
    MATLAB datenum (values near 7.4e5 with sub-second steps in days) is
    converted, and anything else is taken as seconds and said so."""
    t = np.asarray(t, dtype=np.float64).ravel()
    if unit == "days":
        return t * 86400.0, "MATLAB days (stated with --t-unit days), x86400 to seconds"
    if unit == "s":
        return t, "seconds (stated with --t-unit s)"
    if len(t) > 1:
        med = float(np.median(np.diff(t)))
        if 7.0e5 <= t[0] <= 8.0e5 and 0 < med < 0.01:
            return t * 86400.0, (f"MATLAB datenum days (first value {t[0]:.6f}, median step {med:.3g} d), "
                                 "x86400 to seconds")
    return t, "seconds (as stored: no datenum signature; pass --t-unit days if it is MATLAB days)"


def axis_facts(t_s) -> dict:
    dt = np.diff(np.asarray(t_s, dtype=np.float64))
    if not len(dt):
        raise Refusal("the time axis has one value")
    bad = int((~np.isfinite(dt)).sum() + (dt <= 0).sum())
    if bad:
        raise Refusal(f"the time axis is not strictly increasing ({bad} steps <= 0 or non-finite)")
    med = float(np.median(dt))
    return {"n": int(len(dt) + 1), "span_s": float(t_s[-1] - t_s[0]),
            "dt": {"min": float(dt.min()), "median": med, "max": float(dt.max()), "mean": float(dt.mean())},
            "uniform": bool(dt.max() - dt.min() <= UNIFORM_RTOL * med), "rate_of_median": 1.0 / med}


def resample_uniform(t, x, fs: float):
    """Linear interpolation of ``x`` (sampled at times ``t``) onto
    ``0, 1/fs, 2/fs, ... <= t[-1] - t[0]`` (seconds from the first sample).
    The rule of ``derive_dwij_mfs2.resample``, by grid rate."""
    t = np.asarray(t, dtype=np.float64)
    tr = t - t[0]
    m = int(np.floor(tr[-1] * fs + 1e-9)) + 1
    grid = np.arange(m, dtype=np.float64) / fs
    return grid, np.interp(grid, tr, np.asarray(x, dtype=np.float64))


# ------------------------------------------------------------ the file --

def mat_format(path: str) -> str:
    import h5py
    return "v7.3" if h5py.is_hdf5(path) else "v5"


def list_variables(path: str, fmt: str):
    """[(name, MATLAB shape, MATLAB class)] without loading data."""
    if fmt == "v7.3":
        import h5py
        out = []
        with h5py.File(path, "r") as f:
            for k in f.keys():
                if k.startswith("#"):
                    continue
                ds = f[k]
                cls = ds.attrs.get("MATLAB_class", b"")
                cls = cls.decode() if isinstance(cls, bytes) else str(cls)
                shape = list(reversed(ds.shape)) if hasattr(ds, "shape") else None
                if not hasattr(ds, "shape"):
                    cls = cls or "struct"
                elif ds.attrs.get("MATLAB_object_decode") is not None or cls not in (
                        "double", "single", "int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64", "logical"):
                    cls = f"opaque:{cls or ds.dtype}"
                out.append((k, shape, cls))
        return out
    from Working.registration.kinds import _mat_variables
    vs, _fmt = _mat_variables(path)
    return [(n, list(s) if s else None, t) for n, s, t in vs]


def opaque_classes(path: str, fmt: str, variables) -> list:
    """[(name, class)] of the MATLAB objects scipy/h5py cannot decode (a
    datetime, duration or timetable is the likely time axis)."""
    out = []
    for name, shape, cls in variables:
        if not (cls.startswith("opaque") or cls in ("object", "struct")):
            continue
        what = cls.split(":", 1)[1] if ":" in cls else "unknown class"
        if fmt == "v5":
            try:
                import scipy.io
                v = scipy.io.loadmat(path, variable_names=[name]).get(name)
                if v is not None and getattr(v, "dtype", None) is not None and v.dtype.names and "s2" in v.dtype.names:
                    s2 = v.ravel()[0]["s2"]
                    what = s2.decode() if isinstance(s2, bytes) else str(s2)
            except Exception as e:
                what = f"unreadable ({type(e).__name__})"
        out.append((name, what))
    return out


def _numeric(cls: str) -> bool:
    return cls in ("double", "single", "float64", "float32", "int8", "int16", "int32", "int64",
                   "uint8", "uint16", "uint32", "uint64")


def pick_matrix(variables, variable: str | None = None):
    """``(name, n_samples, n_channels)`` of the data matrix, or Refusal."""
    if variable:
        v = next((x for x in variables if x[0] == variable), None)
        if v is None:
            raise Refusal(f"--variable {variable!r} is not in the file ({', '.join(x[0] for x in variables)})")
        mats = [v]
    else:
        mats = [v for v in variables if v[1] and len(v[1]) == 2 and _numeric(v[2])
                and min(v[1]) > 1 and min(v[1]) <= MAX_CHANNELS and v[0].lower() not in TIME_NAMES]
    if not mats:
        raise Refusal("no numeric 2-D matrix with <= 64 channels in the file: name the variable with --variable")
    if len(mats) > 1:
        raise Refusal("more than one candidate matrix (" + ", ".join(f"{n} {s[0]:,}x{s[1]:,}" for n, s, _c in mats)
                      + "): name the data with --variable")
    name, shape, cls = mats[0]
    if not shape or len(shape) != 2 or not _numeric(cls):
        raise Refusal(f"{name} is {cls} {shape}, not a numeric 2-D matrix")
    return name, int(max(shape)), int(min(shape))


def load_matrix(path: str, fmt: str, name: str) -> np.ndarray:
    """The matrix as (samples x channels) float64."""
    if fmt == "v7.3":
        import h5py
        with h5py.File(path, "r") as f:
            a = np.asarray(f[name][()], dtype=np.float64)
    else:
        import scipy.io
        a = np.asarray(scipy.io.loadmat(path, variable_names=[name])[name], dtype=np.float64)
    if a.ndim != 2:
        raise Refusal(f"{name} has {a.ndim} dimensions")
    return a.T if a.shape[0] < a.shape[1] else a


def _load_any(path: str) -> dict:
    """Every numeric variable of a small .mat (v5 or v7.3) as a flat float64 array."""
    if mat_format(path) == "v7.3":
        import h5py
        out = {}
        with h5py.File(path, "r") as f:
            for k in f.keys():
                ds = f[k]
                if hasattr(ds, "shape") and ds.dtype.kind in "fiu":
                    out[k] = np.asarray(ds[()], dtype=np.float64).ravel()
        return out
    import scipy.io
    m = scipy.io.loadmat(path)
    return {k: np.asarray(v, dtype=np.float64).ravel() for k, v in m.items()
            if not k.startswith("__") and isinstance(v, np.ndarray) and v.dtype.kind in "fiu"}


def read_time_axis(path: str, fmt: str, variables, n: int, time_file: str | None = None, t_unit: str | None = None,
                   time_dirs=()):
    """``(t_seconds | None, source, notes)``. ``source`` names where the axis was
    read from; ``notes`` say why none could be."""
    notes = []
    stem = os.path.splitext(os.path.basename(path))[0]
    found = [p for p in (os.path.join(d, f"{stem}_time.mat") for d in (*time_dirs, os.path.dirname(path)))
             if os.path.isfile(p)]
    tf = time_file or (found[0] if found else None)
    if time_file and not os.path.isfile(time_file):
        raise Refusal(f"--time-file {time_file} does not exist")
    if tf:
        vals = _load_any(tf)
        if "t0" in vals:             # MATLAB char: one UTF-16 code per element
            notes.append(f"{os.path.basename(tf)}: the recording starts at "
                         + "".join(chr(int(c)) for c in vals["t0"] if 0 < c < 0x110000))
        if "t_s" in vals and len(vals["t_s"]) == 1:
            vals.pop("t_s")          # a scalar datetime: a start time, not an axis
        if "t_s" in vals:
            t = vals["t_s"]
            if len(t) != n:
                raise Refusal(f"{os.path.basename(tf)}: t_s has {len(t):,} values for {n:,} samples")
            return t, f"{os.path.basename(tf)} (t_s, seconds, exported by scripts/export_mat_time.m)", notes
        if "dur_s" in vals and len(vals["dur_s"]) == 1:
            d = float(vals["dur_s"][0])
            if d <= 0:
                raise Refusal(f"{os.path.basename(tf)}: dur_s = {d}")
            step = d if d <= 60 else d / (n - 1)
            return (np.arange(n, dtype=np.float64) * step,
                    f"{os.path.basename(tf)} (dur_s = {d:g} s, a scalar MATLAB duration read as "
                    + ("the sample interval" if d <= 60 else "the span from first to last sample") + ")", notes)
        if "t0" not in vals:
            raise Refusal(f"{os.path.basename(tf)} holds neither t_s (one time per sample) nor a scalar dur_s")
        # only a start time: no axis -- the count rule decides, and the start time is in the notes
        notes.append(f"{os.path.basename(tf)} holds the start time only (a scalar datetime), not one time per sample")
        return None, None, notes
    for name, shape, cls in variables:
        if name.lower() in TIME_NAMES and _numeric(cls) and shape and int(np.prod(shape)) == n:
            if fmt == "v7.3":
                import h5py
                with h5py.File(path, "r") as f:
                    raw = np.asarray(f[name][()], dtype=np.float64).ravel()
            else:
                import scipy.io
                raw = np.asarray(scipy.io.loadmat(path, variable_names=[name])[name], dtype=np.float64).ravel()
            t, how = time_in_seconds(raw, t_unit)
            return t, f"the file's own '{name}' ({how})", notes
    ops = opaque_classes(path, fmt, variables)
    if ops:
        notes.append("the file's time axis is a MATLAB object that cannot be decoded here ("
                     + ", ".join(f"'{nm}': {c}" for nm, c in ops)
                     + "; scipy reads it as MatlabOpaque) -- run scripts/export_mat_time.m in MATLAB to write "
                     + f"DATA/derived/time_axes/{stem}_time.mat, then rerun to read it")
    else:
        notes.append("the file carries no time axis")
    return None, None, notes


# ---------------------------------------------------------- the database --

class Deferred:
    """A connection whose ``commit()`` waits for the caller's.

    The registry's ``register()``, ``append_audit()`` and ``put_dataset()``
    each commit on their own; one derive calls all of them, and a failure
    between two of those commits (a locked database under the researcher's
    bridge, a refused display name) would leave rows registered and a stem on
    disk that the next run refuses on. Handing them this wrapper makes the
    whole derive ONE transaction: the caller commits or rolls back the real
    connection (critic round, 2026-10-18)."""

    def __init__(self, conn):
        object.__setattr__(self, "_conn", conn)

    def commit(self):
        pass

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __setattr__(self, name, value):
        setattr(self._conn, name, value)


def open_ro(db: str) -> sqlite3.Connection:
    if not os.path.isfile(db):
        raise Refusal(f"the database {db} does not exist")
    return sqlite3.connect(f"file:{os.path.abspath(db)}?mode=ro", uri=True)


def already_registered(conn, source_file: str) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM recordings WHERE source_file = ?", (source_file,)).fetchone()[0])


def repo_relative(path: str) -> str:
    """``path`` relative to the repository when it lies inside it, else absolute.

    ``recordings.npy_path`` is repo-relative by convention (the registry's
    roots are ``DATA/derived/channels``; ``webui/server/runtime.py`` chdirs to
    the repo so the core can ``np.load`` it as stored). A row registered from
    an absolute root would carry ``C:/Users/.../DATA/...`` instead: right on
    this machine, wrong in every copy of the database (the cluster, a worktree
    sandbox) -- critic round, 2026-10-18."""
    ap = os.path.abspath(path)
    try:
        rel = os.path.relpath(ap, _REPO)
    except ValueError:               # another drive
        return ap
    return ap if rel == ".." or rel.startswith(".." + os.sep) else rel


def stale_staging(channels_root: str, stem: str) -> list:
    """Staging directories a killed run left for ``stem`` (dot-named, so the
    registry never lists them; up to 16 x 183 MB for MJu26a_fs10)."""
    if not os.path.isdir(channels_root):
        return []
    pre = f".staging_{stem}_"
    return sorted(os.path.join(channels_root, n) for n in os.listdir(channels_root) if n.startswith(pre))


def refuse_stale_staging(channels_root: str, stem: str):
    left = stale_staging(channels_root, stem)
    if left:
        raise Refusal(f"a previous run was stopped while writing {stem}: delete {', '.join(left)} "
                      "(a half-written copy nothing points at) and rerun")


def register_stem(conn, channels_root: str, stem: str, provenance: dict, actor: str, skip_excerpt_ids=()) -> tuple:
    """Register ``<channels_root>/<stem>`` through the registry (scan, check,
    register). The excerpt rule may link already-registered short rows to the
    new channels; a row that already has a parent, or one the caller links
    itself (``skip_excerpt_ids``), keeps what it has. Returns
    ``(row ids, report, dropped excerpt links)``; Refusal when a check fails.

    A root inside the repository is scanned repo-relative from the repo root
    (``repo_relative``), so the rows carry repo-relative paths and the excerpt
    rule finds the registered rows' repo-relative files whatever the caller's
    working directory."""
    rel = repo_relative(channels_root)
    if os.path.isabs(rel):
        return _register_stem(conn, channels_root, stem, provenance, actor, skip_excerpt_ids)
    prev = os.getcwd()
    os.chdir(_REPO)
    try:
        return _register_stem(conn, rel, stem, provenance, actor, skip_excerpt_ids)
    finally:
        os.chdir(prev)


def _register_stem(conn, channels_root: str, stem: str, provenance: dict, actor: str, skip_excerpt_ids=()) -> tuple:
    from Working.registration import check, register, scan
    from Working.registration.settings import append_audit
    cand = next((c for c in scan("recording", roots=[channels_root], conn=conn) if c.name == stem), None)
    if cand is None:
        raise Refusal(f"the registry does not see {stem} under {channels_root}")
    rep = check(cand, conn)
    kept, dropped = [], []
    for e in rep.excerpts:
        r = conn.execute("SELECT parent_recording_id FROM recordings WHERE id = ?", (int(e["recording_id"]),)).fetchone()
        if e["recording_id"] in set(skip_excerpt_ids) or (r is not None and r[0] is not None):
            dropped.append(e)
        else:
            kept.append(e)
    rep.excerpts = kept
    # the scan's "will be linked" warning must not follow a link that is not made
    gone = tuple(f"registered {e['source_file']} CH{e['channel']} (id {e['recording_id']})" for e in dropped)
    if gone:
        rep.warnings = [w for w in rep.warnings if not w.startswith(gone)]
    if not rep.ok:
        raise Refusal("the registry's checks fail: " + "; ".join(f"{c.name}: {c.detail}" for c in rep.failures()))
    register(conn, cand, report=rep, provenance=provenance, actor=actor)
    ids = list(rep.facts.get("registered_ids") or [])
    append_audit(conn, "registration", f"Registered recording {stem} ({len(ids)} channels) by {actor}",
                 "Datasets", actor=actor, detail={"kind": "recording", "path": cand.path, "ids": ids,
                                                  "sha1": rep.sha1, "warnings": rep.warnings,
                                                  "excerpts_linked": kept, "excerpts_kept_as_they_were": dropped})
    return ids, rep, dropped


def set_display_name(conn, source_file: str, name: str, actor: str) -> str:
    from Working.database.datasets import put_dataset
    try:
        put_dataset(conn, source_file, {"display_name": name}, actor=actor)
        return f"display name {name!r}"
    except (ValueError, KeyError) as e:
        return f"display name NOT set ({e}); set it in Settings › Datasets"


def write_channels(channels_root: str, stem: str, columns, manifest: dict) -> str:
    """Write ``CH<i>.npy`` for each array ``columns`` yields + ``manifest.json``
    into a staging directory, then swap it in. ``columns`` is an iterable so
    a caller can produce one channel at a time."""
    final = os.path.join(channels_root, stem)
    if os.path.exists(final):
        raise Refusal(f"{final} exists")
    refuse_stale_staging(channels_root, stem)
    staging = os.path.join(channels_root, f".staging_{stem}_{os.getpid()}")
    if os.path.isdir(staging):
        shutil.rmtree(staging)
    os.makedirs(staging)
    try:
        for i, y in enumerate(columns):
            np.save(os.path.join(staging, f"CH{i}.npy"), np.ascontiguousarray(y, dtype=np.float64))
            del y                    # before the generator makes the next channel: one in memory, not two
        with open(os.path.join(staging, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        os.replace(staging, final)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return final


# -------------------------------------------------------------- the plan --

def short_name(stem: str) -> str:
    return stem[:-4] if stem.endswith("_raw") else stem


def plan_file(path: str, args, channels_root: str, conn_ro) -> dict:
    """Every inference for one file, and the samples; Refusal at anything uncertain."""
    fmt = mat_format(path)
    variables = list_variables(path, fmt)
    name, n, n_ch = pick_matrix(variables, args.variable)
    base = os.path.splitext(os.path.basename(path))[0]
    p = {"path": path, "basename": os.path.basename(path), "format": f"MATLAB {fmt}", "variables": variables,
         "variable": name, "n_raw": n, "n_channels": n_ch}
    print(f"== {p['basename']}  ({p['format']})")
    for vn, sh, cls in variables:
        print(f"   variable  {vn}: {cls} {('x'.join(f'{d:,}' for d in sh)) if sh else '(no dims)'}")
    print(f"   matrix    {name}: {n:,} samples x {n_ch} channels")
    t, source, notes = read_time_axis(path, fmt, variables, n, args.time_file, args.t_unit,
                                       time_dirs=[os.path.join(os.path.dirname(channels_root), "time_axes")])
    for nt in notes:
        print(f"   time      {nt}")
    resampling = {"method": "none: the samples are kept as stored, on the uniform grid they were recorded on"}
    if t is not None:
        ax = axis_facts(t)
        dts = ax["dt"]
        print(f"   time      read from {source}: span {ax['span_s'] / 86400:.4g} d, dt min {dts['min']:.6g} / "
              f"median {dts['median']:.6g} / max {dts['max']:.6g} s -> {'uniform' if ax['uniform'] else 'UNEVEN'}")
        if ax["uniform"]:
            fs_read = round(1.0 / dts["median"], 6)
            if args.fs is not None and abs(args.fs - fs_read) > 1e-3 * fs_read:
                raise Refusal(f"--fs {args.fs:g} contradicts the uniform time axis read from {source} ({fs_read:g} Hz)")
            fs, fs_source = fs_read, "read"
            fs_note = (f"{fs:g} Hz read from {source}: the time axis is uniform "
                       f"(dt median {dts['median']:.6g} s, min {dts['min']:.6g}, max {dts['max']:.6g})")
            grid_n = n
        else:
            if args.fs is None:
                raise Refusal(f"the time axis read from {source} is uneven (dt {dts['min']:.4g}-{dts['max']:.4g} s, "
                              f"1/median = {ax['rate_of_median']:.4g} Hz): state the uniform grid rate with --fs "
                              f"(the lab rate is {LAB_FS:g} Hz)")
            fs, fs_source = float(args.fs), "read"
            fs_note = (f"{fs:g} Hz is the uniform grid the samples were linearly interpolated onto (stated with --fs); "
                       f"the source time axis, read from {source}, is uneven: dt min {dts['min']:.6g} s, median "
                       f"{dts['median']:.6g} s, max {dts['max']:.6g} s (1/median = {ax['rate_of_median']:.6g} Hz)")
            grid_n = int(np.floor(ax["span_s"] * fs + 1e-9)) + 1
            resampling = {"method": f"linear interpolation of each channel from its time axis onto a uniform "
                                    f"{1 / fs:g} s grid from the first sample's time to at or before the last's",
                          "time_axis": source, "source_samples": n, "grid_samples": grid_n,
                          "source_dt_s": dts, "span_s": ax["span_s"],
                          "warning": "a one-sample excursion between two grid points is shared between them and "
                                     "loses up to half its height on the grid; the raw file keeps it in full"}
    else:
        if args.fs is not None:
            fs, fs_source = float(args.fs), "inferred"
            cnt, cnt_note = infer_fs_from_count(n)
            stated = (f"{fs:g} Hz stated by {args.fs_stated_by}, not read from the file" if args.fs_stated_by
                      else f"{fs:g} Hz stated with --fs at derivation and recorded as inferred: not read from the file")
            fs_note = (f"{stated} "
                       f"({notes[0] if notes else 'no time axis'}); the count rule alone: "
                       + (cnt_note if cnt is not None else cnt_note.split(", and no time axis")[0]))
        else:
            fs, fs_note = infer_fs_from_count(n)
            if fs is None:
                raise Refusal(fs_note)
            fs_source = "inferred"
            fs_note += f"; {notes[0]}" if notes else ""
        grid_n = n
    print(f"   rate      {fs:g} Hz ({fs_source}): {fs_note}")
    stem = f"{base}_{fs_token(fs)}"
    X = load_matrix(path, fmt, name)
    if X.shape != (n, n_ch):
        raise Refusal(f"{name} loads as {X.shape}, expected {(n, n_ch)}")
    sub = X[:: max(1, n // 200_000)]
    if args.units:
        from Working.units import parse_units
        units = parse_units(args.units)
        if units is None:
            raise Refusal(f"--units {args.units!r} is not one of V, mV, uV")
        guess, _g = infer_units(sub)
        units_note = f"stated with --units at derivation (the value range alone says {guess or 'nothing certain'})"
    else:
        units, units_note = infer_units(sub)
        if units is None:
            raise Refusal(units_note)
    print(f"   units     {units}: {units_note}")
    for c in range(n_ch):
        col = X[:, c]
        nan = int((~np.isfinite(col)).sum())
        print(f"   CH{c:<3}    min {np.nanmin(col):.6g}  median {np.nanmedian(col[:: max(1, n // 200_000)]):.6g}  "
              f"max {np.nanmax(col):.6g}" + (f"  NON-FINITE {nan:,}" if nan else ""))
    print(f"   grid      {grid_n:,} samples at {fs:g} Hz = {grid_n / fs / 86400:.4g} d ({grid_n / fs / 3600:.2f} h)")
    final = os.path.join(channels_root, stem)
    if os.path.exists(final):
        raise Refusal(f"the stem {final} exists: refusing to write a second copy")
    refuse_stale_staging(channels_root, stem)
    if conn_ro is not None and already_registered(conn_ro, p["basename"]):
        raise Refusal(f"{p['basename']} is already registered ({already_registered(conn_ro, p['basename'])} rows)")
    display = args.name or short_name(base)
    print(f"   stem      {stem} -> {final}  (source_file {p['basename']}, display name {display!r})")
    p.update({"fs": fs, "fs_source": fs_source, "fs_note": fs_note, "t": t, "resampling": resampling,
              "units": units, "units_note": units_note, "stem": stem, "final": final, "X": X,
              "grid_n": grid_n, "display": display, "time_notes": notes})
    return p


def derive(p: dict, channels_root: str, db: str) -> int:
    X, t, fs = p["X"], p["t"], p["fs"]
    resampled = p["resampling"]["method"].startswith("linear")

    def columns():
        for c in range(X.shape[1]):
            yield resample_uniform(t, X[:, c], fs)[1] if resampled else X[:, c]

    raw_file = p["path"].replace(os.sep, "/")
    manifest = {
        "source_file": p["basename"], "raw_file": raw_file, "variable": p["variable"],
        "n_channels": p["n_channels"], "fs": fs, "fs_note": p["fs_note"],
        "n_samples_per_channel": p["grid_n"], "dtype": "float64",
        "units": f"{p['units']} -- {p['units_note']}",
        "time_base": "uniform: sample i is at i / fs seconds from the first sample",
        "resampling": p["resampling"],
        "imported_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "derived_by": f"{ACTOR} (datasets-derive, 2026-10-18)",
    }
    final = write_channels(channels_root, p["stem"], columns(), manifest)
    p["X"] = X = None                # the matrix is on disk now
    from Working.database.schema import init_db
    real = init_db(db)
    conn = Deferred(real)            # one transaction: registration, audit and display name land together or not at all
    try:
        try:
            ids, rep, dropped = register_stem(conn, channels_root, p["stem"],
                                              {"notes": f"derived from {p['basename']} by {ACTOR}"}, ACTOR)
            name_msg = set_display_name(conn, p["basename"], p["display"], ACTOR)
            real.commit()
        except BaseException:
            real.rollback()
            shutil.rmtree(final, ignore_errors=True)
            print(f"   ROLLED BACK every database write for {p['basename']} and removed {final}")
            raise
        print(f"   registered {len(ids)} rows (ids {ids[0]}..{ids[-1]}), units {p['units']}, fs_source "
              f"{rep.facts.get('fs_source')}; {name_msg}")
        for e in rep.excerpts:
            print(f"   linked    registered {e['source_file']} CH{e['channel']} (id {e['recording_id']}) as a "
                  f"{e['decimation']}:1 excerpt of CH{e['candidate_channel']} at sample {e['offset']:,} (r = {e['r']})")
        for e in dropped:
            print(f"   kept      {e['source_file']} CH{e['channel']} (id {e['recording_id']}) keeps its existing parent "
                  f"(it is also a {e['decimation']}:1 excerpt of CH{e['candidate_channel']}, r = {e['r']})")
        for w in rep.warnings:
            print(f"   warning   {w}")
    finally:
        real.close()
    print(f"   wrote     {final}: CH0..CH{p['n_channels'] - 1}.npy + manifest.json")
    return 0


def resolve(path: str, raw_root: str) -> str:
    for cand in (path, os.path.join(raw_root, path), os.path.join(raw_root, path + ".mat")):
        if os.path.isfile(cand):
            return cand
    raise Refusal(f"{path}: no such file (looked under {raw_root} too)")


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="raw .mat files (a bare name resolves under <data-root>/raw)")
    ap.add_argument("--fs", type=float, help="the sampling rate (Hz) when the file cannot give it, or the grid for an uneven axis")
    ap.add_argument("--fs-stated-by", help="who stated the --fs rate, for the record (e.g. 'the researcher (2026-10-19)'); "
                                           "the note then says so; fs_source stays 'inferred' (not read)")
    ap.add_argument("--units", help="V | mV | uV when the value range cannot tell")
    ap.add_argument("--variable", help="the data matrix when the file holds more than one")
    ap.add_argument("--time-file", help="a .mat holding t_s (seconds, one per sample) or a scalar dur_s")
    ap.add_argument("--t-unit", choices=("s", "days"), help="the unit of a numeric time vector in the file")
    ap.add_argument("--name", help="the dataset's display name (default: the file stem without _raw)")
    ap.add_argument("--data-root", default=os.path.join(_REPO, "DATA"), help="default: <repo>/DATA")
    ap.add_argument("--db", help="default: <data-root>/db/annotations.sqlite")
    ap.add_argument("--dry-run", action="store_true", help="print every inference, write nothing")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.fs_stated_by and args.fs is None:
        print("   REFUSED   --fs-stated-by names who stated a rate, but no --fs rate was given")
        return 2
    data_root = os.path.abspath(args.data_root)
    db = args.db or os.path.join(data_root, "db", "annotations.sqlite")
    channels_root = os.path.join(data_root, "derived", "channels")
    raw_root = os.path.join(data_root, "raw")
    status = 0
    for f in args.files:
        p = None                     # the previous file's matrix goes before the next one loads
        try:
            path = resolve(f, raw_root)
            conn_ro = open_ro(db)
            try:
                p = plan_file(path, args, channels_root, conn_ro)
            finally:
                conn_ro.close()
            if args.dry_run:
                print("   dry run: nothing written")
                continue
            status = max(status, derive(p, channels_root, db))
        except Refusal as e:
            print(f"   REFUSED   {f}: {e}")
            print("   nothing written")
            status = max(status, 2)
        except Exception as e:
            print(f"   FAILED    {f}: {type(e).__name__}: {e}")
            status = 3
    return status


if __name__ == "__main__":
    sys.exit(main())
