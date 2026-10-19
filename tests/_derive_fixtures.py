"""
_derive_fixtures.py
===================
Small synthetic MATLAB files for `tests/test_derive_raw_mat.py` and
`tests/test_derive_mju26a_fs10.py` (datasets-derive, 2026-10-18).

Nothing here touches `DATA/`: every file is written under a pytest temp
directory. The v7.3 writer builds a MATLAB-shaped HDF5 file with h5py (a
512-byte user block carrying the MAT header, `MATLAB_class` attributes, and
MATLAB's column-major orientation, so a MATLAB ``N x C`` matrix is an HDF5
``(C, N)`` dataset).
"""
from __future__ import annotations

import importlib.util
import os
import sys

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def load_script(name: str):
    """Import ``scripts/<name>.py`` as a module (scripts/ is not a package)."""
    path = os.path.join(PROJECT_ROOT, "scripts", f"{name}.py")
    spec = importlib.util.spec_from_file_location(f"_script_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def write_v5(path, variables: dict) -> str:
    import scipy.io
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    scipy.io.savemat(str(path), variables)
    return str(path)


def write_v73(path, variables: dict) -> str:
    """``variables`` maps name -> a MATLAB-shaped numpy array (rows x cols);
    each is stored transposed, as MATLAB does."""
    import h5py
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with h5py.File(str(path), "w", userblock_size=512) as f:
        for name, arr in variables.items():
            a = np.asarray(arr)
            if a.ndim == 1:
                a = a.reshape(-1, 1)
            ds = f.create_dataset(name, data=np.ascontiguousarray(a.T))
            ds.attrs["MATLAB_class"] = np.bytes_("double" if a.dtype.kind == "f" else "uint32")
    head = b"MATLAB 7.3 MAT-file, Platform: PCWIN64, Created on: Sun Oct 18 00:00:00 2026 HDF5 schema 1.00 ."
    head = head.ljust(116, b" ") + b"\x00" * 8 + b"\x00\x02" + b"IM"
    with open(str(path), "r+b") as fh:
        fh.write(head.ljust(512, b"\x00"))
    return str(path)


def tree(root) -> list:
    """Every file under ``root`` with its size: a dry run must leave this unchanged."""
    out = []
    for dp, _dn, fns in os.walk(str(root)):
        for fn in fns:
            p = os.path.join(dp, fn)
            out.append((os.path.relpath(p, str(root)), os.path.getsize(p)))
    return sorted(out)


def register_stem(conn, channels_root, stem):
    """Register a channel directory through the registry, as Settings › Datasets does."""
    from Working.registration import check, register, scan
    cand = next(c for c in scan("recording", roots=[str(channels_root)], conn=conn) if c.name == stem)
    rep = check(cand, conn)
    assert rep.ok, [(c.name, c.detail) for c in rep.failures()]
    return register(conn, cand, report=rep)


def write_stem(channels_root, stem, channels, fs, source_file, units=None):
    import json
    d = os.path.join(str(channels_root), stem)
    os.makedirs(d)
    for i, x in enumerate(channels):
        np.save(os.path.join(d, f"CH{i}.npy"), np.ascontiguousarray(x, dtype=np.float64))
    man = {"source_file": source_file, "n_channels": len(channels), "fs": fs,
           "n_samples_per_channel": int(len(channels[0])), "dtype": "float64"}
    if units:
        man["units"] = units
    with open(os.path.join(d, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f)
    return d
