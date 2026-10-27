"""
test_newsets_fs2.py
===================
The 2 Hz copies of MJu26a_fs10, SH and SO and their rangpur sweep bundle (2026-10-27,
`scripts/thesis/newsets_fs2.py`).

Pinned:

* the per-channel, chunked block mean gives exactly what `Working/registration/excerpt.py::block_mean` gives on the
  whole channel (the method `scripts/derive_fs2.py` used for CO_fs2 / LM_fs2), drops the trailing partial block and
  counts it, and never needs the whole channel in memory;
* the streaming reader of a .mat's MATLAB `duration` vector (the MCOS function-workspace blob) finds the vector's
  start and checks every step without holding the vector, and says so when a step is not 100 ms;
* the bundle, once built, is batch 3's volts sweep (the 43 settings LM_fs2 got) over the three new recordings, each
  with one phase-randomised draw, units V in every target, and four-field task lines.

Run from the project root:
    python -m pytest tests/test_newsets_fs2.py -q
"""

import glob
import importlib.util
import json
import os
import struct
import sys
import zlib

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

BUNDLES = sorted(glob.glob(os.path.join(PROJECT_ROOT, "docs", "thesis", "hpc", "rq4_newsets_*")))
BATCH3_V = os.path.join(PROJECT_ROOT, "HPC", "Detection", "generated", "rq4_batch3", "LM_fs2", "manifest.json")
SOURCES = {"MJu26a_fs2.mat", "SH_fs2.mat", "SO_fs2.mat"}


def _mod():
    spec = importlib.util.spec_from_file_location("newsets_fs2_t", os.path.join(PROJECT_ROOT, "scripts", "thesis",
                                                                                "newsets_fs2.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_chunked_block_mean_matches_block_mean_on_the_whole_channel(tmp_path):
    from Working.registration.excerpt import block_mean
    M = _mod()
    x = np.random.default_rng(0).normal(size=10_003).cumsum()
    src = tmp_path / "CH0.npy"
    np.save(src, x)
    out = tmp_path / "out.npy"
    info = M.block_mean_file(str(src), str(out), factor=5, chunk=1_000)      # chunks far smaller than the channel
    y = np.load(out)
    assert np.array_equal(y, block_mean(x, 5))
    assert y.dtype == np.float64 and len(y) == 2_000
    assert info["source_samples"] == 10_003 and info["trailing_samples_dropped"] == 3 and info["non_finite"] == 0


def _fake_mat(path, blob):
    with open(path, "wb") as f:
        f.write(b"MATLAB 5.0 MAT-file".ljust(116, b" ") + b"\0" * 8 + struct.pack("<HH", 0x0100, 0x4D49))
        comp = zlib.compress(b"\x01" * 24 + struct.pack("<II", 0, 0))         # a first element, not the last
        f.write(struct.pack("<II", 15, len(comp)) + comp)
        comp = zlib.compress(blob)
        f.write(struct.pack("<II", 15, len(comp)) + comp)


def test_duration_vector_is_read_streaming_and_every_step_checked(tmp_path):
    M = _mod()
    n = 50_000
    t = 1_800_000.0 + 100.0 * np.arange(n)
    junk = np.array([-1.0, 3.0, 7.0, 1e300], dtype="<f8").tobytes()
    p = tmp_path / "ok.mat"
    _fake_mat(p, junk + t.astype("<f8").tobytes() + junk)
    r = M.duration_steps(str(p), n, out_chunk=4096)
    assert r["found"] and r["t0_ms"] == 1_800_000.0 and r["t_end_ms"] == t[-1]
    assert r["checked"] == n and r["bad_steps"] == 0

    t2 = t.copy()
    t2[30_000:] += 100.0                                                       # one 200 ms step
    p2 = tmp_path / "gap.mat"
    _fake_mat(p2, junk + t2.astype("<f8").tobytes())
    r2 = M.duration_steps(str(p2), n, out_chunk=4096)
    assert r2["found"] and r2["bad_steps"] == 1 and r2["first_bad"] == 29_999


@pytest.mark.skipif(not BUNDLES, reason="the new-sets bundle has not been built")
def test_the_bundle_is_batch_3s_volts_sweep_over_the_three_new_recordings():
    root = BUNDLES[-1]
    with open(os.path.join(root, "batch.json"), encoding="utf-8") as fh:
        batch = json.load(fh)
    assert {d["source"] for d in batch["datasets"]} == SOURCES
    ref = None
    if os.path.isfile(BATCH3_V):
        with open(BATCH3_V, encoding="utf-8") as fh:
            ref = {j["label"] for j in json.load(fh)["jobs"]}
    n_tasks = 0
    for d in batch["datasets"]:
        with open(os.path.join(PROJECT_ROOT, d["folder"], "manifest.json"), encoding="utf-8") as fh:
            man = json.load(fh)
        assert man["unit"] == "V" and man["volts"] is True and man["fs"] == 2.0 and not man["refused"]
        labels = {j["label"] for j in man["jobs"]}
        assert len(labels) == 43 and "signal_threshold" in labels and "signal_threshold__threshold_mV_m2" not in labels
        if ref is not None:
            assert labels == ref
        n_ch = 16 if d["source"].startswith("MJu26a") else 4
        for j in man["jobs"]:
            with open(os.path.join(PROJECT_ROOT, j["spec"]), encoding="utf-8") as fh:
                spec = json.load(fh)
            assert spec["null"]["draws"] == 1 and spec["null"]["params"] == {"method": "phase_randomize", "seed": 0}
            assert all(t["units"] == "V" for t in spec["targets"])
            assert len(spec["targets"]) == (2 if j["label"] == "mp_threshold__backend_auto" else n_ch)
        n_tasks += d["tasks"]
    lines = 0
    for f in glob.glob(os.path.join(root, "tasks_*.txt")):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                assert len(parts) == 4, line
                assert os.path.isfile(os.path.join(PROJECT_ROOT, parts[0])), parts[0]
                lines += 1
    assert lines == n_tasks == (42 * 16 + 2) + 2 * (42 * 4 + 2)
