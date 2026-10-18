"""
test_derive_raw_mat.py
======================
`scripts/derive_raw_mat.py` (datasets-derive, 2026-10-18): the generic deriver
that turns a raw MATLAB matrix (CO, LM, SH, SO, F2B, L_R_Aug_26_PD_raw and any
later one) into `<data-root>/derived/channels/<stem>_fs<rate>/CH<i>.npy` +
`manifest.json`, registers it through the registry, and declares its unit.

The rules pinned here, in plain words:

* the sampling rate is READ from a time axis when one can be read (a numeric
  `t` in the file, or the `<stem>_time.mat` that `scripts/export_mat_time.m`
  writes from MATLAB's datetime object); an uneven axis is linearly
  interpolated onto a uniform grid at the rate `--fs` names;
* with no readable axis, 10 Hz is inferred when the sample count is a whole
  number of days at 10 Hz plus the inclusive end sample (N = d*864000 + 1),
  and the manifest says "inferred from the sample count, not read";
  any other count refuses until `--fs` states the rate;
* values in the +-1 range are volts, values in the hundreds millivolts; in
  between refuses until `--units` states it;
* `--dry-run` writes nothing; a second run on the same file refuses.

Every file is synthetic and small, under a temp directory. Nothing touches
`DATA/`.
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

from _derive_fixtures import load_script, tree, write_v5, write_v73  # noqa: E402
from Working.database.schema import init_db  # noqa: E402

drm = load_script("derive_raw_mat")

DAY_10HZ = 86400 * 10


# ------------------------------------------------------------ fixtures --

@pytest.fixture
def env(tmp_path):
    data = tmp_path / "DATA"
    (data / "raw").mkdir(parents=True)
    (data / "derived" / "channels").mkdir(parents=True)
    db = data / "db" / "annotations.sqlite"
    init_db(str(db)).close()
    return {"data": data, "raw": data / "raw", "channels": data / "derived" / "channels", "db": db}


def _run(env, *args):
    return drm.main([*map(str, args), "--db", str(env["db"]), "--data-root", str(env["data"])])


def _rows(env, source_file=None):
    conn = sqlite3.connect(str(env["db"]))
    conn.row_factory = sqlite3.Row
    sql = "SELECT * FROM recordings"
    args = ()
    if source_file:
        sql += " WHERE source_file = ?"
        args = (source_file,)
    out = [dict(r) for r in conn.execute(sql + " ORDER BY channel", args)]
    conn.close()
    return out


def _volts(n, c, seed=0):
    rng = np.random.default_rng(seed)
    return -0.3 + 0.01 * np.cumsum(rng.standard_normal((n, c)), axis=0) / np.sqrt(n)


def _manifest(env, stem):
    with open(env["channels"] / stem / "manifest.json", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------ inference rules --

def test_count_rule_infers_10hz_from_whole_days_plus_the_inclusive_end():
    fs, note = drm.infer_fs_from_count(20 * DAY_10HZ + 1)
    assert fs == 10.0
    assert "inferred from the sample count, not read" in note
    assert "20" in note
    fs, _ = drm.infer_fs_from_count(6 * DAY_10HZ + 1)          # F2B: 5,184,001
    assert fs == 10.0


def test_count_rule_refuses_a_count_that_is_no_round_number_and_names_both_candidates():
    fs, note = drm.infer_fs_from_count(3_851_550)              # L_R_Aug_26_PD_raw
    assert fs is None
    assert "10 Hz" in note and "1 Hz" in note
    assert "4.46" in note and "44.6" in note


def test_units_rule_volts_millivolts_and_the_gap_between():
    rng = np.random.default_rng(1)
    u, note = drm.infer_units(-0.3 + 0.2 * rng.standard_normal(5000))
    assert u == "V" and "inferred from the value range" in note
    u, note = drm.infer_units(-180 + 60 * rng.standard_normal(5000))
    assert u == "mV" and "inferred from the value range" in note
    u, note = drm.infer_units(8 + rng.standard_normal(5000))
    assert u is None and "--units" in note


def test_fs_token_names_the_stem():
    assert drm.fs_token(10.0) == "fs10"
    assert drm.fs_token(1.0) == "fs1"
    assert drm.fs_token(0.8) == "fs0p8"


# ------------------------------------------------------------ end to end --

def test_a_uniform_10hz_matrix_of_whole_days_infers_10hz_writes_registers_and_declares_volts(env):
    n = 1 * DAY_10HZ + 1
    X = _volts(n, 2)
    write_v5(env["raw"] / "CO.mat", {"CO": X})
    assert _run(env, env["raw"] / "CO.mat") == 0
    d = env["channels"] / "CO_fs10"
    assert sorted(os.listdir(d)) == ["CH0.npy", "CH1.npy", "manifest.json", "registration.manifest.json"]
    np.testing.assert_array_equal(np.load(d / "CH1.npy"), X[:, 1])
    man = _manifest(env, "CO_fs10")
    assert man["fs"] == 10.0 and man["n_samples_per_channel"] == n and man["source_file"] == "CO.mat"
    assert "inferred from the sample count, not read" in man["fs_note"]
    assert man["units"].startswith("V") and "inferred from the value range" in man["units"]
    assert man["resampling"]["method"].startswith("none")
    rows = _rows(env, "CO.mat")
    assert [r["channel"] for r in rows] == [0, 1]
    assert all(r["fs"] == 10.0 and r["n_samples"] == n and r["units"] == "V" and r["fs_source"] == "inferred" for r in rows)
    assert all("inferred from the value range" in r["units_note"] for r in rows)
    conn = sqlite3.connect(str(env["db"]))
    name = conn.execute("SELECT display_name FROM datasets WHERE source_file = 'CO.mat'").fetchone()
    conn.close()
    assert name == ("CO",)


def test_a_v73_file_is_read_oriented_and_millivolts_are_inferred_from_hundreds(env):
    rng = np.random.default_rng(2)
    n = 3000
    X = -180 + 40 * np.cumsum(rng.standard_normal((n, 3)), axis=0) / np.sqrt(n)
    write_v73(env["raw"] / "F2B.mat", {"F2B": X})
    assert _run(env, env["raw"] / "F2B.mat", "--fs", "10") == 0
    d = env["channels"] / "F2B_fs10"
    for i in range(3):
        np.testing.assert_allclose(np.load(d / f"CH{i}.npy"), X[:, i])
    man = _manifest(env, "F2B_fs10")
    assert man["units"].startswith("mV")
    assert "--fs" in man["fs_note"]
    assert {r["units"] for r in _rows(env, "F2B.mat")} == {"mV"}


def test_an_uneven_time_axis_is_interpolated_onto_the_stated_rate_and_the_manifest_says_so(env):
    rng = np.random.default_rng(3)
    n = 4000
    dt = rng.uniform(0.08, 0.3, n - 1)
    t = np.concatenate([[0.0], np.cumsum(dt)]) + 1000.0
    X = _volts(n, 2, seed=3)
    write_v5(env["raw"] / "SO.mat", {"SO": X, "t": t.reshape(-1, 1)})
    assert _run(env, env["raw"] / "SO.mat", "--fs", "10") == 0
    d = env["channels"] / "SO_fs10"
    span = t[-1] - t[0]
    m = int(np.floor(span * 10 + 1e-9)) + 1
    grid = np.arange(m) / 10.0
    y = np.load(d / "CH0.npy")
    assert len(y) == m
    np.testing.assert_allclose(y, np.interp(grid, t - t[0], X[:, 0]))
    man = _manifest(env, "SO_fs10")
    assert man["fs"] == 10.0 and man["n_samples_per_channel"] == m
    assert "linear" in man["resampling"]["method"]
    assert man["resampling"]["source_dt_s"]["min"] == pytest.approx(dt.min())
    assert man["resampling"]["source_dt_s"]["median"] == pytest.approx(np.median(dt))
    assert "read from" in man["fs_note"]
    assert "warning" in man["resampling"]
    assert {r["fs_source"] for r in _rows(env, "SO.mat")} == {"read"}


def test_an_uneven_time_axis_without_fs_refuses_and_writes_nothing(env, capsys):
    rng = np.random.default_rng(4)
    n = 3000
    t = np.concatenate([[0.0], np.cumsum(rng.uniform(0.08, 0.3, n - 1))])
    write_v5(env["raw"] / "SH.mat", {"SH": _volts(n, 2), "t": t.reshape(-1, 1)})
    before = tree(env["data"])
    assert _run(env, env["raw"] / "SH.mat") != 0
    assert tree(env["data"]) == before
    assert "--fs" in capsys.readouterr().out


def test_the_matlab_exported_time_file_beside_the_raw_file_gives_a_read_rate(env):
    n = 2500
    write_v5(env["raw"] / "LM.mat", {"LM": _volts(n, 2)})
    write_v73(env["raw"] / "LM_time.mat", {"t_s": np.arange(n, dtype=np.float64)})   # 1 Hz, uniform
    assert _run(env, env["raw"] / "LM.mat") == 0
    man = _manifest(env, "LM_fs1")
    assert man["fs"] == 1.0
    assert "read from" in man["fs_note"] and "LM_time.mat" in man["fs_note"]
    assert "inferred" not in man["fs_note"]
    assert {r["fs_source"] for r in _rows(env, "LM.mat")} == {"read"}


def test_a_stated_fs_that_contradicts_a_read_uniform_axis_refuses(env):
    n = 2500
    write_v5(env["raw"] / "LM.mat", {"LM": _volts(n, 2), "t": np.arange(n, dtype=np.float64).reshape(-1, 1)})
    before = tree(env["data"])
    assert _run(env, env["raw"] / "LM.mat", "--fs", "10") != 0
    assert tree(env["data"]) == before


def test_an_ambiguous_count_refuses_without_fs_and_derives_with_it(env, capsys):
    write_v5(env["raw"] / "L_R_Aug_26_PD_raw.mat", {"M1": _volts(5001, 3)})
    before = tree(env["data"])
    assert _run(env, env["raw"] / "L_R_Aug_26_PD_raw.mat") != 0
    assert tree(env["data"]) == before
    assert _rows(env) == []
    out = capsys.readouterr().out
    assert "10 Hz" in out and "1 Hz" in out
    assert _run(env, env["raw"] / "L_R_Aug_26_PD_raw.mat", "--fs", "1") == 0
    assert (env["channels"] / "L_R_Aug_26_PD_raw_fs1" / "CH2.npy").is_file()
    conn = sqlite3.connect(str(env["db"]))
    name = conn.execute("SELECT display_name FROM datasets WHERE source_file = 'L_R_Aug_26_PD_raw.mat'").fetchone()
    conn.close()
    assert name == ("L_R_Aug_26_PD",)


def test_ambiguous_units_refuse_without_units(env):
    rng = np.random.default_rng(5)
    write_v5(env["raw"] / "CO.mat", {"CO": 8 + rng.standard_normal((2000, 2))})
    before = tree(env["data"])
    assert _run(env, env["raw"] / "CO.mat", "--fs", "10") != 0
    assert tree(env["data"]) == before
    assert _run(env, env["raw"] / "CO.mat", "--fs", "10", "--units", "mV") == 0
    assert {r["units"] for r in _rows(env, "CO.mat")} == {"mV"}
    assert "stated" in _manifest(env, "CO_fs10")["units"]


def test_two_candidate_matrices_refuse_without_variable(env):
    write_v5(env["raw"] / "CO.mat", {"A": _volts(2000, 2), "B": _volts(2000, 3)})
    before = tree(env["data"])
    assert _run(env, env["raw"] / "CO.mat", "--fs", "10") != 0
    assert tree(env["data"]) == before
    assert _run(env, env["raw"] / "CO.mat", "--fs", "10", "--variable", "B") == 0
    assert len(_rows(env, "CO.mat")) == 3


def test_dry_run_writes_nothing_and_prints_the_inference(env, capsys):
    write_v5(env["raw"] / "CO.mat", {"CO": _volts(1 * DAY_10HZ + 1, 2)})
    before = tree(env["data"])
    db_bytes = env["db"].read_bytes()
    assert _run(env, env["raw"] / "CO.mat", "--dry-run") == 0
    assert tree(env["data"]) == before
    assert env["db"].read_bytes() == db_bytes
    out = capsys.readouterr().out
    assert "CO_fs10" in out and "10 Hz" in out and "V" in out and "dry run" in out.lower()


def test_registering_the_same_file_twice_is_refused(env):
    write_v5(env["raw"] / "CO.mat", {"CO": _volts(2000, 2)})
    assert _run(env, env["raw"] / "CO.mat", "--fs", "10") == 0
    rows = _rows(env)
    before = tree(env["data"])
    assert _run(env, env["raw"] / "CO.mat", "--fs", "10") != 0
    assert _rows(env) == rows
    assert tree(env["data"]) == before


# ------------------------------------------------- critic round (2026-10-18) --

def test_a_failure_after_registration_leaves_no_rows_and_no_stem(env, monkeypatch, capsys):
    import Working.database.datasets as datasets
    X = _volts(1 * DAY_10HZ + 1, 2)
    write_v5(env["raw"] / "CO.mat", {"CO": X})
    before = tree(env["data"])

    def boom(*a, **k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(datasets, "put_dataset", boom)
    assert _run(env, "CO") == 3
    assert _rows(env, "CO.mat") == []
    assert tree(env["data"]) == before
    monkeypatch.undo()
    assert _run(env, "CO") == 0
    assert len(_rows(env, "CO.mat")) == 2
