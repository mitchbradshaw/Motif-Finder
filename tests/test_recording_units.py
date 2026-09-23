"""
test_recording_units.py
=======================
fixup-b — the unit a recording's samples are stored in is recorded ON THE DATA,
not assumed by the page that draws it.

The derived channels under `DATA/derived/channels/` are volts for the M2 exports
and Mushroom_260720, and millivolts for L_LM_Jul_26_J (docs/prompts/fixup/
B-units-and-amplitude.md; the evidence is in the report). The web UI labelled
every one of them "mV" and never converted, because nothing on the data said
what it was: `materialize_channels.py` wrote a manifest with no `units` key and
`recordings` had no column to put it in.

What is pinned here, all headless and on temp trees:

* one vocabulary (`Working.units`): the spellings a manifest may use, and the
  one factor from each unit to millivolts;
* `recordings.units` / `units_note` are additive, through `init_db()`, idempotent;
* the backfill declares only what was verified and leaves the rest undeclared
  WITH a reason, and never overwrites a unit a person declared;
* the backfill touches no detection, annotation or Library row — those are
  sample indices, and a units change that moved one would be in the wrong place;
* registration carries a declared unit through, says an undeclared one in words,
  and refuses one it cannot read;
* both manifest writers emit a `units` key, even when it is null;
* the core keeps receiving the stored samples (volts for a volts file), and the
  step-cache key does not see the unit — so no cached step changed meaning.
"""

import json
import os
import sqlite3
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db  # noqa: E402
from Working.registration import check, register, scan  # noqa: E402


def _db(tmp_path):
    return init_db(str(tmp_path / "db" / "annotations.sqlite"))


def _insert(conn, source_file, channel=0, npy_path="x.npy", n=100, fs=1.0):
    return conn.execute(
        "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
        "VALUES (?, ?, ?, ?, 0, ?)", (source_file, channel, fs, n, npy_path)).lastrowid


def _units(conn, source_file):
    return conn.execute("SELECT units, units_note FROM recordings WHERE source_file = ? ORDER BY channel",
                        (source_file,)).fetchall()


# ------------------------------------------------------------ vocabulary --

def test_parse_units_reads_the_spellings_a_manifest_uses_and_nothing_else():
    from Working.units import parse_units
    assert parse_units("V") == "V"
    assert parse_units("volts") == "V"
    assert parse_units("mV") == "mV"
    assert parse_units("millivolts") == "mV"
    # the free text scripts/rederive_channels.py wrote into L_LM's manifest
    assert parse_units("millivolts as stored (everything else on disk is volts; "
                       "Pipelines/drop_motifs/lionsmane12.py divides by 1000)") == "mV"
    assert parse_units("uV") == "uV" and parse_units("µV") == "uV"
    for unknown in (None, "", "   ", "counts", "a.u.", "arbitrary"):
        assert parse_units(unknown) is None, unknown


def test_the_factor_to_millivolts_is_one_table():
    from Working.units import to_mv_factor
    assert to_mv_factor("V") == 1000.0
    assert to_mv_factor("mV") == 1.0
    assert to_mv_factor("uV") == 0.001
    assert to_mv_factor(None) is None, "an undeclared unit has no factor — it is never assumed to be 1"


# -------------------------------------------------------------- the schema --

def test_init_db_adds_the_units_columns_and_is_idempotent(tmp_path):
    path = str(tmp_path / "db" / "annotations.sqlite")
    init_db(path).close()
    conn = init_db(path)                                  # second run must not fail or duplicate
    cols = [r[1] for r in conn.execute("PRAGMA table_info(recordings)")]
    assert "units" in cols and "units_note" in cols
    assert cols.count("units") == 1


def test_the_backfill_declares_what_was_verified_and_says_why_the_rest_is_not(tmp_path):
    path = str(tmp_path / "db" / "annotations.sqlite")
    conn = init_db(path)
    _insert(conn, "M2_aug_concat_fs1.mat", 0); _insert(conn, "M2_aug_concat_fs1.mat", 1)
    _insert(conn, "Mushroom_260720_0509_4hrs_CH14_fs1.mat")
    _insert(conn, "L_LM_Jul_26_J_raw.mat")
    _insert(conn, "Fig2A_dt0p1.csv")
    _insert(conn, "MJu26a.mat")
    _insert(conn, "some_new_file.mat")
    conn.commit(); conn.close()

    conn = init_db(path)
    assert [r[0] for r in _units(conn, "M2_aug_concat_fs1.mat")] == ["V", "V"]
    assert _units(conn, "Mushroom_260720_0509_4hrs_CH14_fs1.mat")[0][0] == "V"
    assert _units(conn, "L_LM_Jul_26_J_raw.mat")[0][0] == "mV"
    for sf in ("Fig2A_dt0p1.csv", "MJu26a.mat"):
        units, note = _units(conn, sf)[0]
        assert units is None, f"{sf}: a unit nobody verified must not be asserted"
        assert note and "undeclared" in note.lower(), f"{sf}: an undeclared unit must say why, in words: {note!r}"
    for units, note in _units(conn, "M2_aug_concat_fs1.mat"):
        assert note and "verified" in note.lower(), "a declared unit carries its evidence"
    assert _units(conn, "some_new_file.mat")[0] == (None, None), "a file the table does not know is left alone"


def test_the_backfill_never_overwrites_a_unit_a_person_declared(tmp_path):
    path = str(tmp_path / "db" / "annotations.sqlite")
    conn = init_db(path)
    _insert(conn, "Fig2A_dt0p1.csv")
    _insert(conn, "M2_aug_concat_fs1.mat")
    conn.commit(); conn.close()
    conn = init_db(path)
    conn.execute("UPDATE recordings SET units = 'V', units_note = 'declared by the researcher' WHERE source_file = 'Fig2A_dt0p1.csv'")
    conn.execute("UPDATE recordings SET units = 'mV', units_note = 'declared by the researcher' WHERE source_file = 'M2_aug_concat_fs1.mat'")
    conn.commit(); conn.close()
    conn = init_db(path)
    assert _units(conn, "Fig2A_dt0p1.csv")[0] == ("V", "declared by the researcher")
    assert _units(conn, "M2_aug_concat_fs1.mat")[0] == ("mV", "declared by the researcher")


def _snapshot(conn, tables):
    out = {}
    for t in tables:
        out[t] = [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY id")]
    return out


def test_the_backfill_moves_no_detection_annotation_or_library_row(tmp_path):
    """Detections, annotations and Library members are stored in SAMPLE INDICES.
    Nothing about a unit may move one — if a row changes, the conversion is in
    the wrong place."""
    path = str(tmp_path / "db" / "annotations.sqlite")
    conn = init_db(path)
    rid = _insert(conn, "M2_aug_concat_fs1.mat")
    cfg = conn.execute("INSERT INTO configs (config_hash, config_json, created_at) VALUES ('h', '{}', 't')").lastrowid
    run = conn.execute("INSERT INTO runs (config_id, recording_id, span_start, span_end, started_at, status) "
                       "VALUES (?, ?, 0, 100, 't', 'done')", (cfg, rid)).lastrowid
    conn.execute("INSERT INTO detections (run_id, start_idx, end_idx, score) VALUES (?, 10, 20, 0.5)", (run,))
    conn.execute("INSERT INTO annotations (recording_id, start_idx, end_idx, verdict, source, created_at) "
                 "VALUES (?, 30, 40, 'interesting', 'human', 't')", (rid,))
    entry = conn.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx, scale, content_hash, created_at) "
                         "VALUES (?, 50, 60, 'event', 'h1', 't')", (rid,)).lastrowid
    conn.execute("INSERT INTO motif_member (entry_id, recording_id, start_idx, end_idx, content_hash) VALUES (?, ?, 50, 60, 'h1')",
                 (entry, rid))
    conn.commit()
    tables = ["detections", "annotations", "motif_entry", "motif_member"]
    before = _snapshot(conn, tables)
    conn.close()
    conn = init_db(path)
    assert _units(conn, "M2_aug_concat_fs1.mat")[0][0] == "V", "the backfill ran"
    assert _snapshot(conn, tables) == before


# -------------------------------------------------------------- registration --

def _write_recording(root, stem, n_channels=2, n=4000, fs=10.0, units=None, write_units_key=True):
    d = root / stem
    d.mkdir(parents=True)
    rng = np.random.default_rng(1)
    for i in range(n_channels):
        np.save(str(d / f"CH{i}.npy"), np.cumsum(rng.standard_normal(n)).astype(np.float64))
    m = {"source_file": f"{stem}.mat", "n_channels": n_channels, "fs": fs, "n_samples_per_channel": n, "dtype": "float64"}
    if write_units_key:
        m["units"] = units
    (d / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    return d


def test_scan_reads_the_units_the_manifest_declares(tmp_path):
    root = tmp_path / "channels"
    _write_recording(root, "A1", units="mV")
    (c,) = scan("recording", roots=[str(root)])
    assert c.facts["units"] == "mV"
    assert not any("unit" in w for w in c.warnings)


def test_an_undeclared_unit_is_said_in_words_and_never_assumed(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "channels"
    _write_recording(root, "A2", write_units_key=False)
    (c,) = scan("recording", roots=[str(root)], conn=conn)
    assert c.facts["units"] is None
    assert any("units" in w and "undeclared" in w for w in c.warnings), c.warnings
    rep = check(c, conn)
    assert rep.ok, "an undeclared unit is flagged, not refused: the file is still readable data"
    rid = register(conn, c, report=rep)
    row = conn.execute("SELECT units FROM recordings WHERE id = ?", (rid,)).fetchone()
    assert row[0] is None, "an undeclared unit is stored as undeclared, not as a guess"
    stored = json.loads(conn.execute("SELECT warnings_json FROM recordings WHERE id = ?", (rid,)).fetchone()[0])
    assert any("undeclared" in w for w in stored), "the warning follows the row"


def test_a_supplied_unit_is_carried_through_to_every_channel_row(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "channels"
    _write_recording(root, "A3", n_channels=3, write_units_key=False)
    (c,) = scan("recording", roots=[str(root)], conn=conn)
    rep = check(c, conn, overrides={"units": "V"})
    assert rep.ok
    assert not any("undeclared" in w for w in rep.warnings), "the supplied unit answers the scan's warning"
    register(conn, c, report=rep)
    rows = conn.execute("SELECT units, units_note FROM recordings WHERE source_file = 'A3.mat' ORDER BY channel").fetchall()
    assert [r[0] for r in rows] == ["V", "V", "V"]
    assert all(r[1] for r in rows), "the note says where the unit came from"


def test_a_unit_that_cannot_be_read_fails_its_check(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "channels"
    _write_recording(root, "A4", write_units_key=False)
    (c,) = scan("recording", roots=[str(root)], conn=conn)
    rep = check(c, conn, overrides={"units": "furlongs"})
    assert not rep.ok
    bad = [x for x in rep.failures() if x.name == "units"]
    assert bad and "furlongs" in bad[0].detail


def test_a_unit_can_be_declared_for_an_already_registered_recording(tmp_path):
    from Working.registration.kinds import declare_units
    conn = _db(tmp_path)
    for ch in range(3):
        _insert(conn, "Fig2A_dt0p1.csv", ch)
    conn.commit()
    out = declare_units(conn, "Fig2A_dt0p1.csv", "V", note="the researcher confirmed volts")
    assert out["channels"] == 3 and out["units"] == "V"
    rows = _units(conn, "Fig2A_dt0p1.csv")
    assert all(r == ("V", "the researcher confirmed volts") for r in rows)
    with pytest.raises(ValueError):
        declare_units(conn, "Fig2A_dt0p1.csv", "furlongs")
    with pytest.raises(KeyError):
        declare_units(conn, "no_such_file.mat", "V")


# ----------------------------------------------------------- manifest writers --

def test_derive_channels_writes_a_units_key_even_when_it_is_unknown(tmp_path):
    from Working.registration.kinds import derive_channels
    src = tmp_path / "raw.csv"
    np.savetxt(str(src), np.random.default_rng(0).standard_normal((50, 2)), delimiter=",")
    root = tmp_path / "channels"
    d = derive_channels(str(src), {"variable": "columns", "layout": "columns", "n_channels": 2}, 10.0, str(root))
    man = json.loads(open(os.path.join(d, "manifest.json"), encoding="utf-8").read())
    assert "units" in man and man["units"] is None
    d2 = derive_channels(str(src), {"variable": "columns", "layout": "columns", "n_channels": 2}, 10.0, str(root),
                         stem="raw_v", extra={"units": "V"})
    assert json.loads(open(os.path.join(d2, "manifest.json"), encoding="utf-8").read())["units"] == "V"


def test_materialize_arbitrary_file_writes_the_units_key_and_the_row(tmp_path, monkeypatch):
    import Pipelines.materialize_channels.materialize_channels as mc
    monkeypatch.setattr(mc, "CHANNEL_DIR", str(tmp_path / "channels"))
    conn = _db(tmp_path)
    src = tmp_path / "two.csv"
    np.savetxt(str(src), np.random.default_rng(0).standard_normal((40, 2)), delimiter=",")
    mc.materialize_arbitrary_file(conn, str(src), n_channels=2, fs=10.0, units="mV")
    man = json.loads(open(os.path.join(str(tmp_path / "channels"), "two", "manifest.json"), encoding="utf-8").read())
    assert man["units"] == "mV"
    assert [r[0] for r in _units(conn, "two.csv")] == ["mV", "mV"]

    src2 = tmp_path / "three.csv"
    np.savetxt(str(src2), np.random.default_rng(1).standard_normal((40, 2)), delimiter=",")
    mc.materialize_arbitrary_file(conn, str(src2), n_channels=2, fs=10.0)
    man2 = json.loads(open(os.path.join(str(tmp_path / "channels"), "three", "manifest.json"), encoding="utf-8").read())
    assert "units" in man2 and man2["units"] is None, "the key is always written; null says undeclared"


# ------------------------------------------------ the core is not moved --

def test_the_core_still_receives_the_stored_samples(tmp_path):
    """detect5/store multiply by 1000 themselves: a converted array reaching them
    would yield amplitudes 1000x too large. The executor's loader is untouched."""
    from Working.execution import _load_signal
    x = np.array([-0.45839212, -0.45842311, -0.45842109, -0.44], dtype=np.float64)
    p = str(tmp_path / "CH0.npy"); np.save(p, x)
    rec = {"npy_path": p, "n_samples": len(x), "fs": 1.0, "units": "V"}
    got = _load_signal(rec, None)
    xs = got[0] if isinstance(got, tuple) else got
    assert np.array_equal(np.asarray(xs), x), "the core must receive volts for a volts file"


def test_the_step_cache_key_does_not_see_the_unit(tmp_path):
    """The cache key is the recipe-prefix hash. Declaring a unit does not change
    the core's input, so it must not change the key either — and a cached step
    keeps its meaning (see the report, 'the step cache')."""
    from Working.execution import _recipe_prefix_hash
    recipe = {"recording_id": 7, "span": [0, 100], "steps": [{"stage": "preprocessing", "algorithm": "detrend", "params": {}}]}
    before = _recipe_prefix_hash(recipe, 0)
    conn = _db(tmp_path)
    _insert(conn, "M2_aug_concat_fs1.mat")
    conn.commit()
    assert _recipe_prefix_hash(recipe, 0) == before
    assert "units" not in json.dumps(recipe)
