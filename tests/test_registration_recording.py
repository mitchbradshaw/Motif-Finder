"""
test_registration_recording.py
==============================
`Working/registration/` — the recording kind (stage-3 Prompt 02, standard in
`docs/DATA_REGISTRATION.md`).

A recording candidate is a directory under the channels root holding one
`CH<n>.npy` per channel and, when the deriver wrote one, a `manifest.json`.
Registration turns it into one `recordings` row per channel, writes the
sidecar `registration.manifest.json`, and links excerpts: a candidate that is
a block-mean-decimated subset of a registered channel (r > 0.99, one-sample
peak) is an excerpt of it, not a new recording (user decision 2026-09-21).

Every test runs on a temp tree and a fresh `init_db()` database. Nothing
touches `DATA/`.
"""

import json
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db  # noqa: E402
from Working.registration import (  # noqa: E402
    RegistrationError, check, find_excerpt, list_registered, register, scan, sidecar_path, unregister,
)
from Working.registration.kinds import HELD_OUT_FILE, KINDS  # noqa: E402


# ------------------------------------------------------------ fixtures --

def _db(tmp_path):
    conn = init_db(str(tmp_path / "db" / "annotations.sqlite"))
    return conn


def _write_recording(root, stem, n_channels=2, n=5000, fs=10.0, manifest=True, seed=0, extra=None):
    d = root / stem
    d.mkdir(parents=True)
    rng = np.random.default_rng(seed)
    chans = []
    for i in range(n_channels):
        x = np.cumsum(rng.standard_normal(n)).astype(np.float64)
        np.save(str(d / f"CH{i}.npy"), x)
        chans.append(x)
    if manifest:
        m = {"source_file": f"{stem}.mat", "n_channels": n_channels, "fs": fs,
             "n_samples_per_channel": n, "dtype": "float64", "imported_at": "2026-09-21T00:00:00+00:00"}
        m.update(extra or {})
        (d / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    return d, chans


def _roots(tmp_path):
    root = tmp_path / "channels"
    root.mkdir(exist_ok=True)
    return {"recording": [str(root)]}


# ------------------------------------------------------------------ scan --

def test_recording_kind_is_declared_with_scan_checks_and_table():
    spec = KINDS["recording"]
    assert spec.table == "recordings"
    assert spec.roots and "channels" in spec.roots[0]
    assert callable(spec.scan) and callable(spec.check)
    assert spec.ui  # where it shows up


def test_scan_finds_unregistered_directories_and_marks_registered_ones(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "channels"
    _write_recording(root, "M1", n_channels=2)
    _write_recording(root, "M2", n_channels=1)
    # M2 is already registered: one row pointing at its channel file
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) VALUES (?,?,?,?,?,?)",
                 ("M2.mat", 0, 10.0, 5000, 0, str(root / "M2" / "CH0.npy").replace(os.sep, "/")))
    conn.commit()
    cands = scan("recording", roots=_roots(tmp_path)["recording"], conn=conn)
    by_name = {c.name: c for c in cands}
    assert set(by_name) == {"M1", "M2"}
    assert by_name["M1"].registered is False
    assert by_name["M1"].facts["fs"] == 10.0
    assert by_name["M1"].facts["n_channels"] == 2
    assert by_name["M1"].facts["n_samples"] == 5000
    assert by_name["M2"].registered is True and by_name["M2"].registered_ids == [1]


def test_scan_without_manifest_reads_shape_from_disk_and_warns_fs_unknown(tmp_path):
    root = tmp_path / "channels"
    _write_recording(root, "M100", n_channels=3, n=777, manifest=False)
    (c,) = scan("recording", roots=[str(root)])
    assert c.facts["n_channels"] == 3 and c.facts["n_samples"] == 777
    assert c.facts["fs"] is None
    assert any("fs" in w.lower() for w in c.warnings)


# ----------------------------------------------------------------- check --

def test_check_passes_a_clean_candidate_and_computes_a_hash(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "channels"
    _write_recording(root, "M1")
    (c,) = scan("recording", roots=[str(root)], conn=conn)
    rep = check(c, conn)
    assert rep.ok, [x for x in rep.checks if not x.ok]
    names = {x.name for x in rep.checks}
    assert {"exists", "readable", "shape", "fs", "held_out", "not_registered", "hash"} <= names
    assert rep.sha1 and len(rep.sha1) == 40


def test_check_fails_loudly_on_a_corrupt_channel_file(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "channels"
    d, _ = _write_recording(root, "M1")
    (d / "CH1.npy").write_bytes(b"not an npy file")
    (c,) = scan("recording", roots=[str(root)], conn=conn)
    rep = check(c, conn)
    assert not rep.ok
    bad = [x for x in rep.checks if x.name == "readable"][0]
    assert not bad.ok and "CH1.npy" in bad.detail


def test_check_fails_on_inconsistent_channel_lengths(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "channels"
    d, _ = _write_recording(root, "M1", n_channels=2)
    np.save(str(d / "CH1.npy"), np.zeros(10))
    (c,) = scan("recording", roots=[str(root)], conn=conn)
    rep = check(c, conn)
    assert not rep.ok and any(x.name == "shape" and not x.ok for x in rep.checks)


def test_check_refuses_the_held_out_recording(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "channels"
    stem = HELD_OUT_FILE[:-4]
    _write_recording(root, stem, n_channels=1)
    (c,) = scan("recording", roots=[str(root)], conn=conn)
    rep = check(c, conn)
    assert not rep.ok
    assert any(x.name == "held_out" and not x.ok and HELD_OUT_FILE in x.detail for x in rep.checks)
    with pytest.raises(RegistrationError):
        register(conn, c, report=rep)


def test_check_surfaces_non_uniform_sampling_and_inferred_fs_as_warnings(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "channels"
    _write_recording(root, "MJu26a", n_channels=1, fs=7.25,
                     extra={"time_base": "t.npy", "fs_note": "t is not uniform: dt min 0.124, median 0.138, max 2.83; fs below is 1/median(dt)"})
    np.save(str(root / "MJu26a" / "t.npy"), np.cumsum(np.full(5000, 0.138)))
    _write_recording(root, "L_LM", n_channels=1, fs=10.0, seed=1,
                     extra={"fs_note": "10.0 Hz is inferred, not read from the file"})
    cands = {c.name: c for c in scan("recording", roots=[str(root)], conn=conn)}
    r1 = check(cands["MJu26a"], conn)
    assert r1.ok
    assert any("not uniform" in w for w in r1.warnings)
    r2 = check(cands["L_LM"], conn)
    assert r2.ok
    assert any("inferred" in w for w in r2.warnings)
    assert r2.facts["fs_source"] == "inferred"


def test_fs_unknown_fails_unless_supplied_and_is_then_marked_inferred(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "channels"
    _write_recording(root, "M100", n_channels=1, manifest=False)
    (c,) = scan("recording", roots=[str(root)], conn=conn)
    rep = check(c, conn)
    assert not rep.ok and any(x.name == "fs" and not x.ok for x in rep.checks)
    rep2 = check(c, conn, overrides={"fs": 10.0})
    assert rep2.ok and rep2.facts["fs"] == 10.0 and rep2.facts["fs_source"] == "inferred"
    rid = register(conn, c, report=rep2, provenance={"producer": "test"})
    row = conn.execute("SELECT fs, fs_source FROM recordings WHERE id = ?", (rid,)).fetchone()
    assert row["fs"] == 10.0 and row["fs_source"] == "inferred"


# -------------------------------------------------------------- register --

def test_register_writes_one_row_per_channel_and_the_sidecar(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "channels"
    d, _ = _write_recording(root, "M1", n_channels=3, n=4000, fs=10.0)
    (c,) = scan("recording", roots=[str(root)], conn=conn)
    rep = check(c, conn)
    rid = register(conn, c, report=rep, provenance={"producer": "scripts/rederive_channels.py"}, actor="this installation")
    rows = conn.execute("SELECT * FROM recordings WHERE source_file = 'M1.mat' ORDER BY channel").fetchall()
    assert len(rows) == 3
    assert rows[0]["id"] == rid
    assert [r["channel"] for r in rows] == [0, 1, 2]
    assert all(r["fs"] == 10.0 and r["n_samples"] == 4000 for r in rows)
    assert rows[2]["npy_path"].endswith("M1/CH2.npy") and "\\" not in rows[2]["npy_path"]
    assert rows[0]["fs_source"] == "read"
    assert rows[0]["registered_at"] and rows[0]["registered_by"] == "this installation"
    # the sidecar every registered artifact gets
    sc = sidecar_path(c)
    assert os.path.isfile(sc) and os.path.normpath(sc) == os.path.normpath(str(d / "registration.manifest.json"))
    m = json.loads(open(sc, encoding="utf-8").read())
    for key in ("kind", "source", "fs", "parameters", "producer", "created_at", "code_version", "checks_passed", "sha1"):
        assert key in m, key
    assert m["kind"] == "recording" and m["producer"] == "scripts/rederive_channels.py"
    assert m["checks_passed"] and "hash" in m["checks_passed"]
    # a second scan sees it registered, and list_registered returns it
    (c2,) = scan("recording", roots=[str(root)], conn=conn)
    assert c2.registered and len(c2.registered_ids) == 3
    reg = list_registered(conn, "recording")
    assert any(r["name"] == "M1" and r["n_channels"] == 3 for r in reg)


def test_register_refuses_without_a_passing_report(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "channels"
    _write_recording(root, "M100", n_channels=1, manifest=False)   # fs unknown -> check fails
    (c,) = scan("recording", roots=[str(root)], conn=conn)
    with pytest.raises(RegistrationError):
        register(conn, c)   # runs the checks itself, sees the failure
    assert conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0] == 0


def test_register_refuses_a_recording_already_registered(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "channels"
    _write_recording(root, "M1", n_channels=1)
    (c,) = scan("recording", roots=[str(root)], conn=conn)
    register(conn, c)
    (c2,) = scan("recording", roots=[str(root)], conn=conn)
    rep = check(c2, conn)
    assert not rep.ok and any(x.name == "not_registered" and not x.ok for x in rep.checks)


def test_register_goes_through_the_writer_it_is_given_and_a_human_writer_is_refused(tmp_path):
    """Rule 5: recordings are a machine table. A writer that refuses machine
    tables (the bridge's write_human) must stop the registration before any
    row lands."""
    conn = _db(tmp_path)
    root = tmp_path / "channels"
    _write_recording(root, "M1", n_channels=2)
    (c,) = scan("recording", roots=[str(root)], conn=conn)
    seen = []

    def refusing_writer(conn_, table, row):
        seen.append(table)
        raise PermissionError("rule 5: refuses " + table)

    with pytest.raises(PermissionError):
        register(conn, c, writer=refusing_writer)
    assert seen == ["recordings"]
    assert conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0] == 0


def test_unregister_is_soft_and_a_soft_deleted_recording_is_scanned_as_a_candidate_again(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "channels"
    _write_recording(root, "M1", n_channels=2)
    (c,) = scan("recording", roots=[str(root)], conn=conn)
    rid = register(conn, c)
    unregister(conn, "recording", rid, actor="this installation")
    rows = conn.execute("SELECT id, active FROM recordings WHERE source_file = 'M1.mat'").fetchall()
    assert len(rows) == 2 and all(r["active"] == 0 for r in rows)   # both channels, rows kept
    assert list_registered(conn, "recording") == []
    (c2,) = scan("recording", roots=[str(root)], conn=conn)
    assert c2.registered is False


# --------------------------------------------------------------- excerpt --

def _excerpt_pair(tmp_path, offset=15_000, dec=10, m=1440, n=200_000, seed=3):
    """A long channel at 10 Hz and a short 1 Hz channel that is its block-mean
    excerpt at `offset` (the Mushroom_260720 / L_LM_Jul_26_J case)."""
    root = tmp_path / "channels"
    d, (x,) = _write_recording(root, "LONG", n_channels=1, n=n, fs=10.0, seed=seed)
    seg = x[offset:offset + m * dec].reshape(m, dec).mean(axis=1)
    sd = root / "SHORT"
    sd.mkdir()
    np.save(str(sd / "SHORT_CH00.npy"), seg + 0.001 * np.random.default_rng(1).standard_normal(m))
    return root, x, seg


def test_find_excerpt_locates_a_block_mean_decimated_subset():
    rng = np.random.default_rng(7)
    x = np.cumsum(rng.standard_normal(100_000))
    seg = x[20_000:20_000 + 500 * 10].reshape(500, 10).mean(axis=1)
    hit = find_excerpt(seg, x, decimation=10)
    assert hit["r"] > 0.99
    assert hit["offset"] == 20_000
    assert hit["sharp"] is True
    miss = find_excerpt(np.cumsum(rng.standard_normal(500)), x, decimation=10)
    assert miss["r"] < 0.99 or not miss["sharp"]


def test_registered_short_channel_is_linked_as_an_excerpt_of_the_new_recording(tmp_path):
    conn = _db(tmp_path)
    root, x, seg = _excerpt_pair(tmp_path)
    # the short 1 Hz channel is already registered (row 385's situation), with runs referencing it
    conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) VALUES (?,?,?,?,?,?)",
                 ("SHORT.mat", 0, 1.0, len(seg), 0, str(root / "SHORT" / "SHORT_CH00.npy").replace(os.sep, "/")))
    conn.commit()
    short_id = conn.execute("SELECT id FROM recordings").fetchone()[0]
    cands = {c.name: c for c in scan("recording", roots=[str(root)], conn=conn)}
    rep = check(cands["LONG"], conn)
    assert rep.ok
    assert rep.excerpts, "the registered short channel should be reported as an excerpt of LONG"
    ex = rep.excerpts[0]
    assert ex["recording_id"] == short_id and ex["channel"] == 0 and ex["decimation"] == 10
    assert ex["offset"] == 15_000 and ex["r"] > 0.99
    assert any("excerpt" in w for w in rep.warnings)
    long_id = register(conn, cands["LONG"], report=rep)
    row = conn.execute("SELECT id, parent_recording_id, parent_offset, decimation FROM recordings WHERE id = ?", (short_id,)).fetchone()
    assert row["id"] == short_id                     # the id is kept: runs and detections still point at it
    assert row["parent_recording_id"] == long_id
    assert row["parent_offset"] == 15_000 and row["decimation"] == 10
    reg = {r["name"]: r for r in list_registered(conn, "recording")}
    assert reg["SHORT"]["excerpt_of"] and reg["SHORT"]["excerpt_of"]["name"] == "LONG"


def test_a_candidate_that_is_an_excerpt_of_a_registered_recording_is_refused_unless_allowed(tmp_path):
    conn = _db(tmp_path)
    root, x, seg = _excerpt_pair(tmp_path)
    cands = {c.name: c for c in scan("recording", roots=[str(root)], conn=conn)}
    long_id = register(conn, cands["LONG"])
    # now the SHORT directory is a candidate; it is an excerpt of LONG
    (c,) = [c for c in scan("recording", roots=[str(root)], conn=conn) if c.name == "SHORT"]
    rep = check(c, conn, overrides={"fs": 1.0})
    assert not rep.ok
    fail = [x for x in rep.checks if x.name == "excerpt" and not x.ok]
    assert fail and "LONG" in fail[0].detail
    with pytest.raises(RegistrationError):
        register(conn, c, report=rep)
    # the researcher says so: register it AS an excerpt, linked to its parent
    rep2 = check(c, conn, overrides={"fs": 1.0, "allow_excerpt": True})
    assert rep2.ok
    sid = register(conn, c, report=rep2)
    row = conn.execute("SELECT parent_recording_id, parent_offset, decimation FROM recordings WHERE id = ?", (sid,)).fetchone()
    assert row["parent_recording_id"] == long_id and row["parent_offset"] == 15_000 and row["decimation"] == 10


# ------------------------------------------------------------ raw import --

def test_raw_mat_candidate_derives_channels_through_the_existing_importer_and_registers(tmp_path):
    import scipy.io
    conn = _db(tmp_path)
    raw = tmp_path / "raw"; raw.mkdir()
    chan_root = tmp_path / "channels"; chan_root.mkdir()
    rng = np.random.default_rng(0)
    # a 2-D variable, one column per channel (the M1_M100 / F2B layout)
    M = np.cumsum(rng.standard_normal((3000, 4)), axis=0)
    scipy.io.savemat(str(raw / "F2B_fs10.mat"), {"M": M})
    (c,) = scan("raw", roots=[str(raw)], conn=conn, channels_root=str(chan_root))
    assert c.registered is False
    assert c.facts["fs"] == 10.0                     # from the _fs<N> suffix
    assert c.facts["variables"] and c.facts["variables"][0]["shape"] == [3000, 4]
    rep = check(c, conn)
    assert rep.ok, [x for x in rep.checks if not x.ok]
    rid = register(conn, c, report=rep, channels_root=str(chan_root))
    d = chan_root / "F2B_fs10"
    assert sorted(p.name for p in d.iterdir()) == ["CH0.npy", "CH1.npy", "CH2.npy", "CH3.npy", "manifest.json", "registration.manifest.json"]
    assert np.allclose(np.load(str(d / "CH2.npy")), M[:, 2])
    rows = conn.execute("SELECT * FROM recordings WHERE source_file = 'F2B_fs10.mat' ORDER BY channel").fetchall()
    assert len(rows) == 4 and rows[0]["id"] == rid and rows[0]["n_samples"] == 3000
    # derived now: the raw file scans as registered, the channel dir scans as registered
    (c2,) = scan("raw", roots=[str(raw)], conn=conn, channels_root=str(chan_root))
    assert c2.registered is True
    (c3,) = scan("recording", roots=[str(chan_root)], conn=conn)
    assert c3.registered is True


def test_raw_mat_refuses_the_held_out_file_and_a_file_already_derived(tmp_path):
    import scipy.io
    conn = _db(tmp_path)
    raw = tmp_path / "raw"; raw.mkdir()
    chan_root = tmp_path / "channels"; chan_root.mkdir()
    scipy.io.savemat(str(raw / HELD_OUT_FILE), {"x": np.zeros((32, 1))})
    scipy.io.savemat(str(raw / "done_fs1.mat"), {"x": np.zeros((32, 1))})
    (chan_root / "done_fs1").mkdir()
    np.save(str(chan_root / "done_fs1" / "CH0.npy"), np.zeros(32))
    cands = {c.name: c for c in scan("raw", roots=[str(raw)], conn=conn, channels_root=str(chan_root))}
    held = check(cands[HELD_OUT_FILE[:-4]], conn)
    assert not held.ok and any(x.name == "held_out" and not x.ok for x in held.checks)
    done = check(cands["done_fs1"], conn)
    assert not done.ok and any(x.name == "not_derived" and not x.ok for x in done.checks)
