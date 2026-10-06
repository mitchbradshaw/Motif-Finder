"""
test_hpc_exported_jobs.py
=========================
fixup-AJ, the core side of Jobs' *exported jobs*: every job directory the site
wrote for RQ1 (fixup-AI's B.2 CNN and full-pool Ward) is listed from the
directory itself — its `job.json` is the record the site keeps of what it
wrote — with its recipe hash, when it was written, the script and its
`sbatch` line, the list and size of what must be copied to the cluster (never
the image cache or `out/`), whether results were copied back into it, and,
given a database, the run its results were imported as (by recipe hash, the
identity `hpc_import.import_results` uses).

    /c/ProgramData/anaconda3/python.exe -m pytest tests/test_hpc_exported_jobs.py -q
"""

import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db  # noqa: E402
from Working.recipes import short_hash  # noqa: E402

CNN_KIND = "shape_cluster_cnn"
WARD_KIND = "shape_tree_full"


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def make_cnn_job(root, name="b2cnn_fusion_x", *, smoke=None, created_at="2026-10-07T10:00:00", out=False):
    d = os.path.join(str(root), name)
    recipe = {"kind": CNN_KIND, "pool": {"key": "abc", "name": "pool_abc", "version": 1}, "arm": {"k": 3},
              "inputs": {"encoding": "fusion"}, "smoke": smoke, "name": name}
    h = short_hash(recipe)
    _write(os.path.join(d, "recipe.json"), recipe)
    _write(os.path.join(d, "job.json"), {
        "kind": CNN_KIND, "recipe_hash": h, "created_at": created_at, "encoding": "fusion",
        "model": "CNN · fusion · EfficientNet-B0", "smoke": smoke, "pool": recipe["pool"], "k": 3,
        "n_windows": 480, "n_train": 240, "n_predict": 240,
        "channels": [{"recording_id": 1, "source_file": "M2_aug_concat_fs1.mat", "channel": 0,
                      "path": "DATA/derived/channels/M2_aug_concat_fs1/CH0.npy", "n_samples": 100, "bytes": 1000},
                     {"recording_id": 2, "source_file": "M2_concat_fs1.mat", "channel": 3,
                      "path": "DATA/derived/channels/M2_concat_fs1/CH3.npy", "n_samples": 50, "bytes": 500}]})
    with open(os.path.join(d, "windows.npz"), "wb") as fh:
        fh.write(b"w" * 300)
    if not smoke:
        with open(os.path.join(d, f"b2cnn_fusion_{h}.sh"), "w", newline="\n") as fh:
            fh.write("#!/bin/bash\n")
        with open(os.path.join(d, f"b2cnn_fusion_{h}_null.sh"), "w", newline="\n") as fh:
            fh.write("#!/bin/bash\n")
    os.makedirs(os.path.join(d, "cache"), exist_ok=True)          # GBs on the cluster: never copied
    with open(os.path.join(d, "cache", "img.npy"), "wb") as fh:
        fh.write(b"c" * 100_000)
    if out:
        _write(os.path.join(d, "out", "done.json"), {"recipe_hash": h, "status": "complete",
                                                     "finished_at": "2026-10-07T11:00:00"})
    return d, recipe, h


def make_ward_job(root, name="ward_full_x"):
    d = os.path.join(str(root), name)
    recipe = {"kind": WARD_KIND, "shape_key": "s1", "pool_key": "abc", "seed": 0, "n_train": 1234}
    h = short_hash(recipe)
    _write(os.path.join(d, "recipe.json"), recipe)
    _write(os.path.join(d, "job.json"), {"kind": WARD_KIND, "recipe_hash": h, "created_at": "2026-10-07T09:00:00",
                                         "n": 1234, "pool_key": "abc", "memory": {"request_gb": 2}})
    with open(os.path.join(d, "shapes.npz"), "wb") as fh:
        fh.write(b"s" * 700)
    with open(os.path.join(d, f"ward_full_{h}.sh"), "w", newline="\n") as fh:
        fh.write("#!/bin/bash\n")
    return d, recipe, h


def _by_name(rows):
    return {r["name"]: r for r in rows}


def test_every_written_job_is_listed_with_its_hash_its_script_and_what_to_copy(tmp_path):
    from Working.hpc.job_export import list_exported_jobs
    root = tmp_path / "hpc"
    cnn_dir, _r, h = make_cnn_job(root)
    ward_dir, _w, wh = make_ward_job(root)
    (root / "not_a_job").mkdir()                                   # a stray folder is not a job
    rows = _by_name(list_exported_jobs([str(root)]))
    assert set(rows) == {"b2cnn_fusion_x", "ward_full_x"}

    cnn = rows["b2cnn_fusion_x"]
    assert cnn["kind"] == CNN_KIND and cnn["recipe_hash"] == h and cnn["recipe_ok"] is True
    assert cnn["written_at"] == "2026-10-07T10:00:00" and cnn["smoke"] is False
    assert os.path.normcase(cnn["job_dir"]) == os.path.normcase(os.path.abspath(cnn_dir))
    assert cnn["sbatch_command"].startswith("sbatch ") and cnn["sbatch_command"].endswith(f"b2cnn_fusion_{h}.sh")
    assert {s["name"] for s in cnn["scripts"]} == {f"b2cnn_fusion_{h}.sh", f"b2cnn_fusion_{h}_null.sh"}
    whats = [c["what"] for c in cnn["copy"]]
    assert whats.count("job directory") == 1 and whats.count("channel array") == 2
    jd = next(c for c in cnn["copy"] if c["what"] == "job directory")
    assert 300 <= jd["bytes"] < 100_000                            # the image cache is not part of the copy
    assert cnn["total_bytes"] == sum(c["bytes"] for c in cnn["copy"])
    assert cnn["returned"] is None and cnn["imported"] is None

    ward = rows["ward_full_x"]
    assert ward["kind"] == WARD_KIND and ward["recipe_hash"] == wh
    assert [c["what"] for c in ward["copy"]] == ["job directory"] and ward["total_bytes"] >= 700
    assert ward["sbatch_command"].endswith(f"ward_full_{wh}.sh")


def test_results_copied_back_an_edited_recipe_and_a_smoke_are_said_so(tmp_path):
    from Working.hpc.job_export import list_exported_jobs
    root = tmp_path / "hpc"
    make_cnn_job(root, "back", out=True)
    edited, recipe, _h = make_cnn_job(root, "edited")
    _write(os.path.join(edited, "recipe.json"), {**recipe, "arm": {"k": 9}})
    make_cnn_job(root / "smoke", "b2cnn_fusion_smoke_y", smoke={"n_train": 10, "n_predict": 4})
    rows = _by_name(list_exported_jobs([str(root), str(root / "smoke")]))
    assert rows["back"]["returned"]["status"] == "complete"
    assert rows["edited"]["recipe_ok"] is False
    sm = rows["b2cnn_fusion_smoke_y"]
    assert sm["smoke"] is True and sm["sbatch_command"] is None and sm["scripts"] == []


def test_a_job_whose_recipe_hash_was_imported_names_its_run(tmp_path):
    from Working.database import runs as R
    from Working.hpc.job_export import list_exported_jobs
    root = tmp_path / "hpc"
    _d, recipe, h = make_cnn_job(root)
    conn = init_db(str(tmp_path / "t.sqlite"))
    try:
        rid = conn.execute("INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) "
                           "VALUES ('a.mat', 0, 1.0, 10, 0, 'x.npy')").lastrowid
        cid, ch = R.get_or_create_config(conn, recipe)
        assert ch == h
        run = R.insert_run(conn, cid, rid, 0, 10, status="completed", name="B.2 CNN fusion")
        conn.commit()
        rows = _by_name(list_exported_jobs([str(root)], conn=conn))
    finally:
        conn.close()
    assert rows["b2cnn_fusion_x"]["imported"] == {"run_id": run, "name": "B.2 CNN fusion"}


def test_an_unreadable_job_is_listed_loudly_not_skipped(tmp_path):
    from Working.hpc.job_export import list_exported_jobs
    root = tmp_path / "hpc"
    d = root / "broken"
    d.mkdir(parents=True)
    (d / "job.json").write_text("{not json", encoding="utf-8")
    rows = _by_name(list_exported_jobs([str(root)]))
    assert rows["broken"]["error"] and rows["broken"]["kind"] is None
