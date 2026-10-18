"""
test_derive_mju26a_fs10.py
==========================
`scripts/derive_mju26a_fs10.py` (datasets-derive, 2026-10-18) and the
registry's explicit parent link `Working.registration.kinds.link_parent`.

MJu26a.mat holds a matrix `M` and an uneven time vector `t`. The script puts
every row on a uniform 10 Hz grid by linear interpolation, writes the stem
`MJu26a_fs10`, registers it through the registry, declares it (and the old
`MJu26a.mat` rows) as volts, and links each channel of
L_LM_Jul_26_J_raw_fs10 (a 10 Hz x1000 copy of five MJu26a channels) to the
MJu26a_fs10 channel it copies, with the sample offset found by searching
every (child, parent) pair over a range of offsets on a high-passed window.
A child that does not correlate at ~1 is refused, and then nothing is
written at all.

Synthetic and small, under a temp directory; nothing touches `DATA/`.
"""
import json
import os
import sqlite3
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (PROJECT_ROOT, os.path.join(PROJECT_ROOT, "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from _derive_fixtures import load_script, register_stem, tree, write_stem, write_v73  # noqa: E402
from Working.database.schema import init_db  # noqa: E402

mju = load_script("derive_mju26a_fs10")

N_RAW = 20_000
OFFSET = 1234
CHILD_N = 22_000
CHILD_OF = {0: 2, 1: 0}          # L_LM channel -> MJu26a channel it copies


def _raw(seed=0):
    rng = np.random.default_rng(seed)
    dt = rng.choice([0.124, 0.138, 0.138, 0.138, 0.2, 0.4], size=N_RAW - 1)
    dt[500] = 2.83
    t = 73_000.0 + np.concatenate([[0.0], np.cumsum(dt)])
    drift = 0.02 * np.sin((t - t[0]) / 900.0)
    M = np.stack([-0.3 + drift + 0.002 * np.cumsum(rng.standard_normal(N_RAW)) / 30
                  + 0.0005 * rng.standard_normal(N_RAW) for _ in range(3)])
    return t, M


def _grid(t, x, fs=10.0):
    span = t[-1] - t[0]
    m = int(np.floor(span * fs + 1e-9)) + 1
    return np.interp(np.arange(m) / fs, t - t[0], x)


@pytest.fixture
def env(tmp_path):
    data = tmp_path / "DATA"
    raw = data / "raw"
    ch = data / "derived" / "channels"
    raw.mkdir(parents=True)
    ch.mkdir(parents=True)
    db = data / "db" / "annotations.sqlite"
    conn = init_db(str(db))
    t, M = _raw()
    # MATLAB's M is 16 x N (here 3 x N); h5py sees it transposed, as in the real file
    write_v73(raw / "MJu26a.mat", {"M": M, "t": t.reshape(1, -1)})
    # the old, unevenly sampled rows as rederive_channels.py wrote them
    dt = np.diff(t)
    write_stem(ch, "MJu26a", list(M), 1.0 / np.median(dt), "MJu26a.mat")
    register_stem(conn, ch, "MJu26a")
    conn.close()
    return {"data": data, "raw": raw, "channels": ch, "db": db, "t": t, "M": M}


def _add_child(env, correlated=True):
    t, M = env["t"], env["M"]
    rng = np.random.default_rng(9)
    chans = []
    for c in range(2):
        if correlated:
            p = _grid(t, M[CHILD_OF[c]])
            chans.append(1000.0 * p[OFFSET:OFFSET + CHILD_N] + 300.0 - 50.0 * c)
        else:
            chans.append(-300 + 2.0 * np.cumsum(rng.standard_normal(CHILD_N)) / 30)
    write_stem(env["channels"], "L_LM_Jul_26_J_raw_fs10", chans, 10.0, "L_LM_Jul_26_J_raw.mat", units="mV")
    conn = init_db(str(env["db"]))
    register_stem(conn, env["channels"], "L_LM_Jul_26_J_raw_fs10")
    conn.close()


def _run(env, *args):
    return mju.main([*map(str, args), "--db", str(env["db"]), "--data-root", str(env["data"]), "--window", "2000"])


def _rows(env, source_file):
    conn = sqlite3.connect(str(env["db"]))
    conn.row_factory = sqlite3.Row
    out = [dict(r) for r in conn.execute("SELECT * FROM recordings WHERE source_file = ? ORDER BY channel", (source_file,))]
    conn.close()
    return out


# ------------------------------------------------------------ the grid --

def test_uniform_grid_interpolates_an_uneven_axis_onto_10hz():
    t, M = _raw()
    grid, y = mju.resample_uniform(t, M[1], 10.0)
    assert np.allclose(np.diff(grid), 0.1)
    assert grid[0] == 0.0 and grid[-1] <= t[-1] - t[0] + 1e-9
    assert len(grid) == int(np.floor((t[-1] - t[0]) * 10 + 1e-9)) + 1
    np.testing.assert_allclose(y, np.interp(grid, t - t[0], M[1]))


def test_time_unit_seconds_and_matlab_datenum_days():
    t, _ = _raw()
    secs, note = mju.time_in_seconds(t)
    np.testing.assert_array_equal(secs, t)
    assert "seconds" in note
    days = 739_000.0 + (t - t[0]) / 86400.0
    secs, note = mju.time_in_seconds(days)
    np.testing.assert_allclose(secs - secs[0], t - t[0], atol=1e-4)
    assert "datenum" in note


# ----------------------------------------------------------- end to end --

def test_derives_registers_declares_volts_and_links_the_child_at_its_offset(env, capsys):
    _add_child(env)
    assert _run(env) == 0
    d = env["channels"] / "MJu26a_fs10"
    t, M = env["t"], env["M"]
    for c in range(3):
        np.testing.assert_allclose(np.load(d / f"CH{c}.npy"), _grid(t, M[c]))
    with open(d / "manifest.json", encoding="utf-8") as f:
        man = json.load(f)
    assert man["fs"] == 10.0 and man["source_file"] == "MJu26a_fs10.mat"
    assert "MJu26a.mat" in man["raw_file"]
    assert "linear" in man["resampling"]["method"]
    assert man["resampling"]["source_dt_s"]["max"] == pytest.approx(2.83)
    assert man["units"].startswith("V")
    new = _rows(env, "MJu26a_fs10.mat")
    assert [r["channel"] for r in new] == [0, 1, 2]
    assert {r["units"] for r in new} == {"V"} and {r["fs"] for r in new} == {10.0}
    old = _rows(env, "MJu26a.mat")
    assert {r["units"] for r in old} == {"V"} and all(r["units_note"] for r in old)
    child = _rows(env, "L_LM_Jul_26_J_raw.mat")
    by_ch = {r["channel"]: r["id"] for r in new}
    for r in child:
        assert r["parent_recording_id"] == by_ch[CHILD_OF[r["channel"]]]
        assert r["parent_offset"] == OFFSET
        assert r["decimation"] == 1
    out = capsys.readouterr().out
    assert "1234" in out or "1,234" in out


def test_a_child_that_does_not_correlate_is_refused_and_nothing_is_written(env, capsys):
    _add_child(env, correlated=False)
    before = tree(env["data"])
    db_rows = _rows(env, "MJu26a.mat")
    assert _run(env) != 0
    assert tree(env["data"]) == before
    assert _rows(env, "MJu26a_fs10.mat") == []
    assert _rows(env, "MJu26a.mat") == db_rows
    assert all(r["parent_recording_id"] is None for r in _rows(env, "L_LM_Jul_26_J_raw.mat"))
    out = capsys.readouterr().out
    assert "refus" in out.lower()


def test_dry_run_prints_the_alignment_and_writes_nothing(env, capsys):
    _add_child(env)
    before = tree(env["data"])
    db_bytes = env["db"].read_bytes()
    assert _run(env, "--dry-run") == 0
    assert tree(env["data"]) == before
    assert env["db"].read_bytes() == db_bytes
    out = capsys.readouterr().out
    assert "MJu26a_fs10" in out and ("1234" in out or "1,234" in out) and "dry run" in out.lower()


def test_refuses_when_the_stem_exists(env):
    _add_child(env)
    assert _run(env) == 0
    before = tree(env["data"])
    assert _run(env) != 0
    assert tree(env["data"]) == before


# ------------------------------------------------- the registry's link --

def test_link_parent_validates_rate_and_offset(env):
    from Working.registration.kinds import link_parent
    _add_child(env)
    conn = init_db(str(env["db"]))
    child = _rows(env, "L_LM_Jul_26_J_raw.mat")[0]
    old = _rows(env, "MJu26a.mat")[0]          # 7.2 Hz: not 1 x the child's 10 Hz
    with pytest.raises(ValueError, match="Hz"):
        link_parent(conn, child["id"], old["id"], 0, 1)
    with pytest.raises(ValueError, match="offset"):
        link_parent(conn, child["id"], child["id"] + 0, -5, 1)
    conn.close()
