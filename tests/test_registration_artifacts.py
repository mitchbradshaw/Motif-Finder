"""
test_registration_artifacts.py
==============================
`Working/registration/` — every kind that is not a recording (stage-3 Prompt
02, standard in `docs/DATA_REGISTRATION.md`): model, matrix profile, window
matrix, window set, encoding, drop-motif event store, catalogue spreadsheet,
HPC result bundle.

Each kind: scan a temp tree with fixture files, checks that fail loudly on a
broken file, register writes the right row (`registered_artifacts`, or
`encodings` for an encoding) and the sidecar manifest. Nothing touches
`DATA/`.
"""

import csv
import json
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db  # noqa: E402
from Working.registration import RegistrationError, check, list_registered, register, scan, sidecar_path, unregister  # noqa: E402
from Working.registration.kinds import KINDS  # noqa: E402


def _db(tmp_path, recording=True):
    conn = init_db(str(tmp_path / "db" / "annotations.sqlite"))
    if recording:
        conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) VALUES (?,?,?,?,?,?)",
                     ("M1.mat", 0, 1.0, 14401, 0, "DATA/derived/channels/M1/CH0.npy"))
        conn.commit()
    return conn


def _artifact_rows(conn, kind):
    return conn.execute("SELECT * FROM registered_artifacts WHERE kind = ? AND active = 1", (kind,)).fetchall()


def test_every_kind_in_the_standard_is_declared():
    expected = {"recording", "raw", "model", "window_matrix", "matrix_profile", "window_set", "encoding",
                "drop_motif_store", "catalogue_spreadsheet", "hpc_result"}
    assert expected <= set(KINDS)
    for name, spec in KINDS.items():
        assert spec.name == name and spec.label and spec.roots and spec.table and spec.ui, name
        assert callable(spec.scan) and callable(spec.check), name


# ----------------------------------------------------------------- model --

def test_model_scan_check_register(tmp_path):
    import joblib
    import torch
    from sklearn.ensemble import RandomForestClassifier
    conn = _db(tmp_path)
    models = tmp_path / "MODELS"; models.mkdir()
    derived = tmp_path / "derived_models"; derived.mkdir()
    torch.save({"state_dict": {"fc.weight": torch.zeros(2, 3)}, "epoch": 3}, str(models / "fusion_cnn.pth"))
    rf = RandomForestClassifier(n_estimators=2, random_state=0).fit(np.zeros((4, 3)), [0, 1, 0, 1])
    joblib.dump(rf, str(derived / "catalogue_classifier_deadbeef00000000.joblib"))
    (models / "notes.txt").write_text("not a model", encoding="utf-8")
    cands = {c.name: c for c in scan("model", roots=[str(models), str(derived)], conn=conn)}
    assert set(cands) == {"fusion_cnn.pth", "catalogue_classifier_deadbeef00000000.joblib"}
    assert cands["fusion_cnn.pth"].facts["format"] == "pytorch"
    assert cands["catalogue_classifier_deadbeef00000000.joblib"].facts["format"] == "joblib"
    rep = check(cands["fusion_cnn.pth"], conn)
    assert rep.ok, [x for x in rep.checks if not x.ok]
    assert rep.facts["summary"]["epoch"] == 3 and "fc.weight" in rep.facts["summary"]["keys"]
    rep2 = check(cands["catalogue_classifier_deadbeef00000000.joblib"], conn)
    assert rep2.ok and rep2.facts["summary"]["class"] == "RandomForestClassifier"
    aid = register(conn, cands["fusion_cnn.pth"], report=rep, provenance={"producer": "HPC/Catalogue/train_job.sh"})
    rows = _artifact_rows(conn, "model")
    assert len(rows) == 1 and rows[0]["id"] == aid and rows[0]["path"].endswith("fusion_cnn.pth") and rows[0]["sha1"] == rep.sha1
    assert rows[0]["active"] == 1 and rows[0]["created_at"]
    assert os.path.isfile(sidecar_path(cands["fusion_cnn.pth"])) and sidecar_path(cands["fusion_cnn.pth"]).endswith("fusion_cnn.pth.manifest.json")
    m = json.load(open(sidecar_path(cands["fusion_cnn.pth"]), encoding="utf-8"))
    assert m["kind"] == "model" and m["producer"] == "HPC/Catalogue/train_job.sh" and m["sha1"] == rep.sha1
    reg = list_registered(conn, "model")
    assert len(reg) == 1 and reg[0]["name"] == "fusion_cnn.pth" and reg[0]["manifest"]["kind"] == "model"
    # a second scan sees it registered; a second registration is refused
    c2 = {c.name: c for c in scan("model", roots=[str(models), str(derived)], conn=conn)}["fusion_cnn.pth"]
    assert c2.registered and c2.registered_ids == [aid]
    assert not check(c2, conn).ok
    unregister(conn, "model", aid)
    assert _artifact_rows(conn, "model") == [] and list_registered(conn, "model") == []


def test_model_check_fails_on_a_corrupt_file(tmp_path):
    conn = _db(tmp_path)
    models = tmp_path / "MODELS"; models.mkdir()
    (models / "broken.pth").write_bytes(b"\x00\x01nope")
    (c,) = scan("model", roots=[str(models)], conn=conn)
    rep = check(c, conn)
    assert not rep.ok and any(x.name == "readable" and not x.ok for x in rep.checks)


# -------------------------------------------------------- matrix profile --

def _mp_npz(path, n=14401, m=60, fs=1.0, source_file="M1.mat", channel=0, recording_id=1, span=None, finite=True):
    n_out = (n if span is None else span[1] - span[0]) - m + 1
    mp = np.abs(np.random.default_rng(0).standard_normal(n_out)).astype(np.float32)
    if not finite:
        mp[5] = np.nan
    np.savez(path, mp=mp, mpi=np.arange(n_out, dtype=np.int32), m=np.int32(m), fs=np.float32(fs), window_min=np.float32(m / fs / 60),
             n_samples=np.int64(n), source_file=source_file, channel=np.int64(channel), recording_id=np.int64(recording_id),
             config_hash="3d99be78", backend="stump", created_at="2026-08-18T19:29:46+00:00",
             **({"span_start": np.int64(span[0]), "span_end": np.int64(span[1])} if span else {}))


def test_matrix_profile_scan_check_register_binds_by_content(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "mp"; root.mkdir()
    (root / "_legacy").mkdir()
    _mp_npz(str(root / "_legacy" / "0_mp_M1_CH0.npz"))
    # the npz says recording_id 99 (another machine's id): binding is by (source_file, channel)
    _mp_npz(str(root / "mp_v2_M1_CH0_WIN1min.npz"), recording_id=99)
    _mp_npz(str(root / "mp_v2_M1_CH0_WIN5min_span0-10000.npz"), m=300, span=(0, 10000))
    cands = {c.name: c for c in scan("matrix_profile", roots=[str(root)], conn=conn)}
    assert set(cands) == {"mp_v2_M1_CH0_WIN1min.npz", "mp_v2_M1_CH0_WIN5min_span0-10000.npz"}   # _legacy skipped
    c = cands["mp_v2_M1_CH0_WIN1min.npz"]
    assert c.facts["stem"] == "M1" and c.facts["channel"] == 0 and c.facts["window_min"] == 1.0 and c.facts["span"] is None
    rep = check(c, conn)
    assert rep.ok, [x for x in rep.checks if not x.ok]
    assert rep.facts["recording_id"] == 1                  # bound by content, not the stored id
    assert any("recording_id" in w for w in rep.warnings)    # ...and the mismatch is said out loud
    names = {x.name for x in rep.checks}
    assert {"exists", "readable", "keys", "fs", "span", "length", "finite", "hash", "recording"} <= names
    aid = register(conn, c, report=rep)
    row = _artifact_rows(conn, "matrix_profile")[0]
    assert row["id"] == aid and row["recording_id"] == 1 and row["channel"] == 0 and row["fs"] == 1.0
    assert row["span_start"] == 0 and row["span_end"] == 14401
    assert json.loads(row["params_json"])["m"] == 60 and json.loads(row["params_json"])["config_hash"] == "3d99be78"
    c2 = cands["mp_v2_M1_CH0_WIN5min_span0-10000.npz"]
    rep2 = check(c2, conn)
    assert rep2.ok and rep2.facts["span"] == [0, 10000]


def test_matrix_profile_checks_fail_on_wrong_fs_span_length_and_nonfinite(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "mp"; root.mkdir()
    _mp_npz(str(root / "mp_v2_M1_CH0_WIN1min.npz"), fs=2.0)                         # fs != recording fs
    _mp_npz(str(root / "mp_v2_M1_CH0_WIN5min_span0-20000.npz"), m=300, span=(0, 20000))  # span past the end
    _mp_npz(str(root / "mp_v2_M1_CH0_WIN3min.npz"), m=180, finite=False)              # NaN inside
    _mp_npz(str(root / "mp_v2_M1_CH0_WIN2min.npz"), m=120, n=14000)                   # length disagrees with the recording
    _mp_npz(str(root / "mp_v2_NOPE_CH0_WIN1min.npz"), source_file="NOPE.mat")        # no such recording
    cands = {c.name: c for c in scan("matrix_profile", roots=[str(root)], conn=conn)}
    failing = {"mp_v2_M1_CH0_WIN1min.npz": "fs", "mp_v2_M1_CH0_WIN5min_span0-20000.npz": "span",
               "mp_v2_M1_CH0_WIN3min.npz": "finite", "mp_v2_M1_CH0_WIN2min.npz": "length", "mp_v2_NOPE_CH0_WIN1min.npz": "recording"}
    for name, chk in failing.items():
        rep = check(cands[name], conn)
        assert not rep.ok, name
        assert any(x.name == chk and not x.ok for x in rep.checks), (name, chk, [(x.name, x.ok) for x in rep.checks])
        with pytest.raises(RegistrationError):
            register(conn, cands[name], report=rep)
    assert _artifact_rows(conn, "matrix_profile") == []


# --------------------------------------------------------- window matrix --

def test_window_matrix_npz_and_legacy_csv(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "wm"; root.mkdir()
    mats = tmp_path / "MATRICES"; mats.mkdir()
    n, m = 14401, 600
    starts = np.arange(0, n - m + 1, m, dtype=np.int64)
    np.savez(str(root / "wm_v1_M1_CH0_WIN10min_STEP100pct.npz"), values=np.zeros((len(starts), 3), np.float32), computed=np.ones((len(starts), 3), bool),
             columns=np.array(["a", "b", "c"]), start_idx=starts, m=np.int32(m), step=np.int32(m), fs=np.float32(1.0), window_min=np.float32(10.0),
             step_frac=np.float32(1.0), span_start=np.int64(0), span_end=np.int64(n - 1), n_samples=np.int64(n), complete=True, source_file="M1.mat",
             channel=np.int32(0), recording_id=np.int64(1), config_hash="f0f0b17b", created_at="2026-08-10T23:48:23+00:00")
    with open(mats / "M1_10min_24wins_consecutive.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["window_start", "f1", "f2"]); [w.writerow([i * 600, 0.1, 0.2]) for i in range(24)]
    cands = {c.name: c for c in scan("window_matrix", roots=[str(root), str(mats)], conn=conn)}
    assert set(cands) == {"wm_v1_M1_CH0_WIN10min_STEP100pct.npz", "M1_10min_24wins_consecutive.csv"}
    rep = check(cands["wm_v1_M1_CH0_WIN10min_STEP100pct.npz"], conn)
    assert rep.ok, [x for x in rep.checks if not x.ok]
    assert rep.facts["n_windows"] == len(starts) and rep.facts["recording_id"] == 1
    aid = register(conn, cands["wm_v1_M1_CH0_WIN10min_STEP100pct.npz"], report=rep)
    row = _artifact_rows(conn, "window_matrix")[0]
    assert row["id"] == aid and row["recording_id"] == 1 and json.loads(row["params_json"])["n_windows"] == len(starts)
    rep2 = check(cands["M1_10min_24wins_consecutive.csv"], conn)
    assert rep2.ok and rep2.facts["format"] == "csv" and rep2.facts["n_rows"] == 24 and rep2.facts["columns"][:2] == ["window_start", "f1"]
    assert any("legacy" in w.lower() for w in rep2.warnings)


def test_window_matrix_incomplete_warns_and_shape_mismatch_fails(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "wm"; root.mkdir()
    base = dict(columns=np.array(["a"]), m=np.int32(600), step=np.int32(600), fs=np.float32(1.0), window_min=np.float32(10.0), step_frac=np.float32(1.0),
                span_start=np.int64(0), span_end=np.int64(14400), n_samples=np.int64(14401), source_file="M1.mat", channel=np.int32(0),
                recording_id=np.int64(1), config_hash="x", created_at="")
    np.savez(str(root / "wm_v1_M1_CH0_WIN10min_STEP100pct.npz"), values=np.zeros((24, 1), np.float32), computed=np.zeros((24, 1), bool),
             start_idx=np.arange(24) * 600, complete=False, **base)
    np.savez(str(root / "wm_v1_M1_CH0_WIN10min_STEP50pct.npz"), values=np.zeros((24, 1), np.float32), computed=np.ones((24, 1), bool),
             start_idx=np.arange(20) * 600, complete=True, **base)
    cands = {c.name: c for c in scan("window_matrix", roots=[str(root)], conn=conn)}
    r1 = check(cands["wm_v1_M1_CH0_WIN10min_STEP100pct.npz"], conn)
    assert r1.ok and any("incomplete" in w.lower() or "computed" in w.lower() for w in r1.warnings)
    r2 = check(cands["wm_v1_M1_CH0_WIN10min_STEP50pct.npz"], conn)
    assert not r2.ok and any(x.name == "shape" and not x.ok for x in r2.checks)


# ------------------------------------------------------------ window set --

def test_window_set_convention(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "window_sets"; root.mkdir()
    d = root / "ws_M1_1ch_600s"; d.mkdir()
    starts = np.arange(0, 12000, 600, dtype=np.int64)
    np.savez(str(d / "windows.npz"), starts=starts, length=np.int64(600), fs=np.float64(1.0), source_file="M1.mat", channel=np.int64(0),
             labels=np.zeros(len(starts), np.int64))
    (d / "manifest.json").write_text(json.dumps({"kind": "window_set", "name": "ws_M1_1ch_600s", "recording": "M1.mat", "channel": 0, "fs": 1.0,
                                                 "length": 600, "n_windows": int(len(starts)), "labels_source": "annotations.source = 'imported_10min'"}), encoding="utf-8")
    (root / "broken").mkdir()
    (root / "broken" / "manifest.json").write_text("{not json", encoding="utf-8")
    cands = {c.name: c for c in scan("window_set", roots=[str(root)], conn=conn)}
    assert set(cands) == {"ws_M1_1ch_600s", "broken"}
    rep = check(cands["ws_M1_1ch_600s"], conn)
    assert rep.ok, [x for x in rep.checks if not x.ok]
    assert rep.facts["n_windows"] == len(starts) and rep.facts["recording_id"] == 1
    aid = register(conn, cands["ws_M1_1ch_600s"], report=rep)
    row = _artifact_rows(conn, "window_set")[0]
    assert row["id"] == aid and row["recording_id"] == 1 and row["span_end"] == int(starts[-1]) + 600
    assert not check(cands["broken"], conn).ok


# -------------------------------------------------------------- encoding --

def test_encoding_registers_into_the_encodings_table(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "encodings"; root.mkdir()
    np.savez(str(root / "enc_sax_dsax_M1_CH0_ab12cd34.npz"), values=np.zeros(200, np.int8), encoding_type="sax_dsax", source_file="M1.mat",
             channel=np.int64(0), fs=np.float64(1.0), span_start=np.int64(0), span_end=np.int64(4000), config_hash="ab12cd34")
    (c,) = scan("encoding", roots=[str(root)], conn=conn)
    rep = check(c, conn)
    assert rep.ok, [x for x in rep.checks if not x.ok]
    eid = register(conn, c, report=rep)
    row = conn.execute("SELECT * FROM encodings WHERE id = ?", (eid,)).fetchone()
    assert row["recording_id"] == 1 and row["encoding_type"] == "sax_dsax" and row["config_hash"] == "ab12cd34"
    assert row["span_start"] == 0 and row["span_end"] == 4000 and row["path"].endswith("enc_sax_dsax_M1_CH0_ab12cd34.npz")
    assert KINDS["encoding"].table == "encodings"
    (c2,) = scan("encoding", roots=[str(root)], conn=conn)
    assert c2.registered and c2.registered_ids == [eid]


# ---------------------------------------------------- drop-motif store --

def _drop_store(d, keys=("m1", "m2"), missing_snippet=False, recording_id=1):
    d.mkdir(parents=True)
    with open(d / "events.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["event_id", "span_key", "span_label", "recording_id", "source_file", "channel", "fs", "onset_idx", "trough_idx",
                    "snippet_start_idx", "snippet_end_idx", "snippet_key", "drop_depth_mv", "fall_duration_s"])
        for i, k in enumerate(keys):
            w.writerow([k, "id001", "ID 1", recording_id, "M1.mat", 0, 1.0, 100 + i * 50, 120 + i * 50, 90 + i * 50, 140 + i * 50, k, 0.5, 20.0])
    # the store.py layout: three arrays per event, <snippet_key>__raw_mv / __detrended_mv / __t_s
    arrays = {}
    for k in (keys[:-1] if missing_snippet else keys):
        for suffix in ("__raw_mv", "__detrended_mv", "__t_s"):
            arrays[k + suffix] = np.zeros(50)
    np.savez(str(d / "snippets.npz"), **arrays)
    (d / "manifest.json").write_text(json.dumps({"detector": "detect5", "n_motifs": len(keys), "params": {"slope_sigma": 3.0}}), encoding="utf-8")


def test_drop_motif_store_contract(tmp_path):
    conn = _db(tmp_path)
    root = tmp_path / "drop_motifs"
    _drop_store(root / "run_a")
    _drop_store(root / "run_b", keys=("x1", "x2", "x3"), missing_snippet=True)
    _drop_store(root / "run_c", recording_id=77)
    cands = {c.name: c for c in scan("drop_motif_store", roots=[str(root)], conn=conn)}
    assert set(cands) == {"run_a", "run_b", "run_c"}
    rep = check(cands["run_a"], conn)
    assert rep.ok, [x for x in rep.checks if not x.ok]
    assert rep.facts["n_events"] == 2 and rep.facts["detector"] == "detect5"
    aid = register(conn, cands["run_a"], report=rep)
    row = _artifact_rows(conn, "drop_motif_store")[0]
    assert row["id"] == aid and row["path"].endswith("run_a") and json.loads(row["params_json"])["n_events"] == 2
    rb = check(cands["run_b"], conn)
    assert not rb.ok and any(x.name == "snippets" and not x.ok and "x3" in x.detail for x in rb.checks)
    rc = check(cands["run_c"], conn)
    assert rc.ok and any("recording_id 77" in w for w in rc.warnings)     # unknown recording: said, not guessed


# ------------------------------------------------ catalogue spreadsheet --

def test_catalogue_spreadsheet_reports_unparseable_cells_instead_of_guessing(tmp_path):
    import openpyxl
    conn = _db(tmp_path)
    root = tmp_path / "catalogue"; root.mkdir()
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["ID_Number", "ID_Name", "Experiment", "Channel", "StartTime_h", "StopTime_h", "Elements", "DATASET", "STATUS", "Parent_ID"])
    ws.append([1, "0001_E01_00_00_0336.0000_0346.0000", "E01", 0, 336, 346, "sharkfin", "M2_aug", "candidate", 0])
    ws.append([2, "0002_E01_00_00_0337.9000_0338.1800", "E01", 0, "abc", 338.18, "sharkfin", "M2_aug", "candidate", 1])
    ws.append([3, "0003", "E01", "CH0?", 314.448, 316.831, "crestedwave ; sharkfin", "M2_aug", "candidate", 0])
    wb.save(str(root / "signal_catalog.xlsx"))
    (c,) = scan("catalogue_spreadsheet", roots=[str(root)], conn=conn)
    rep = check(c, conn)
    assert rep.ok, [x for x in rep.checks if not x.ok]
    assert rep.facts["n_rows"] == 3
    bad = rep.facts["unparseable"]
    assert {(b["row"], b["column"]) for b in bad} == {(3, "StartTime_h"), (4, "Channel")}
    assert bad[0]["value"] in ("abc", "CH0?")
    assert any("2 unparseable" in w for w in rep.warnings)
    rows = rep.facts["rows"]
    assert rows[0]["ID_Number"] == 1 and rows[0]["StartTime_h"] == 336.0 and rows[1]["StartTime_h"] is None
    aid = register(conn, c, report=rep)
    row = _artifact_rows(conn, "catalogue_spreadsheet")[0]
    assert row["id"] == aid and json.loads(row["params_json"])["n_rows"] == 3 and len(json.loads(row["params_json"])["unparseable"]) == 2


def test_catalogue_spreadsheet_without_the_required_columns_fails(tmp_path):
    import openpyxl
    conn = _db(tmp_path)
    root = tmp_path / "catalogue"; root.mkdir()
    wb = openpyxl.Workbook(); wb.active.append(["foo", "bar"]); wb.save(str(root / "other.xlsx"))
    (c,) = scan("catalogue_spreadsheet", roots=[str(root)], conn=conn)
    rep = check(c, conn)
    assert not rep.ok and any(x.name == "columns" and not x.ok and "ID_Number" in x.detail for x in rep.checks)


# ---------------------------------------------------------- HPC results --

def test_hpc_result_bundle_checks_recipe_hash_shapes_and_paused_run(tmp_path):
    from Working.database.runs import get_or_create_config, insert_run
    from Working.recipes import make_recipe, short_hash
    conn = _db(tmp_path)
    recipe = make_recipe(1, [{"stage": "detection", "algorithm": "matrix_profile", "params": {"window_min": 1.0, "backend": "stump"}}])
    h = short_hash(recipe)
    results = tmp_path / "HPC" / "results"
    job = results / f"mp_M1_CH0_WIN1min_{h}"; job.mkdir(parents=True)
    (job / f"mp_M1_CH0_WIN1min_{h}.json").write_text(json.dumps(recipe), encoding="utf-8")
    _mp_npz(str(job / "mp_v2_M1_CH0_WIN1min.npz"))
    # a paused run waiting for exactly this recipe
    config_id, _ = get_or_create_config(conn, recipe)
    run_id = insert_run(conn, config_id, 1, 0, 14401, status="paused")
    conn.commit()
    (c,) = scan("hpc_result", roots=[str(results)], conn=conn)
    assert c.name == job.name and c.facts["recipe_hash"] == h
    rep = check(c, conn)
    assert rep.ok, [x for x in rep.checks if not x.ok]
    names = {x.name for x in rep.checks}
    assert {"recipe", "recipe_hash", "recording", "shape", "length", "finite"} <= names
    assert rep.facts["paused_run_id"] == run_id
    assert rep.facts["artifacts"][0]["name"] == "mp_v2_M1_CH0_WIN1min.npz"
    aid = register(conn, c, report=rep)
    rows = _artifact_rows(conn, "hpc_result")
    assert len(rows) == 1 and rows[0]["id"] == aid and rows[0]["recording_id"] == 1
    assert json.loads(rows[0]["params_json"])["recipe_hash"] == h and json.loads(rows[0]["params_json"])["paused_run_id"] == run_id
    # the run itself is left to the job model (Prompt 01): still paused here
    assert conn.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()[0] == "paused"


def test_hpc_result_bundle_with_a_bad_artifact_fails(tmp_path):
    from Working.recipes import make_recipe, short_hash
    conn = _db(tmp_path)
    recipe = make_recipe(1, [{"stage": "detection", "algorithm": "matrix_profile", "params": {"window_min": 1.0, "backend": "stump"}}])
    h = short_hash(recipe)
    results = tmp_path / "HPC" / "results"
    job = results / "job1"; job.mkdir(parents=True)
    (job / "job1.json").write_text(json.dumps(recipe), encoding="utf-8")
    _mp_npz(str(job / "mp_v2_M1_CH0_WIN1min.npz"), n=999)      # per-channel length disagrees with the recording
    (c,) = scan("hpc_result", roots=[str(results)], conn=conn)
    rep = check(c, conn)
    assert not rep.ok and any(x.name in ("shape", "length") and not x.ok for x in rep.checks)
    assert rep.facts.get("paused_run_id") is None
    job2 = results / "job2"; job2.mkdir()
    (job2 / "job2.json").write_text("{nope", encoding="utf-8")
    cands = {c.name: c for c in scan("hpc_result", roots=[str(results)], conn=conn)}
    assert not check(cands["job2"], conn).ok
