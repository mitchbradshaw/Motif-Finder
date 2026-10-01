"""
test_webui_dataset_naming.py
============================
fixup-f at the bridge: Settings › Datasets authors a dataset's identity into
the `datasets` table, audited, and every workspace then calls the dataset by
that name through ONE seam (`corpus.dataset_name`) — with the source file
always carried beside it, because the file is what the disk and the logs say.

* `PUT /api/settings/datasets` with `meta.<stem>.<field>` for the six dataset
  fields lands in `datasets` (not in `settings`), is audited, validates the
  date (422), and reads back through `GET /api/settings/datasets`;
* `GET /api/datasets` is the client seam's one read: every registered source
  file with its resolved name, whether it is named, and its metadata;
* `/api/recordings`, the registry, Discovery's recording options and the
  held-out lock's typed name all print the same name;
* a name is never a key: Discovery's `key`/`stem` and the registry's `name`
  (the directory stem) do not move when a display name is set;
* channels are named through `channel_name` everywhere, including the excerpt
  link Settings › Datasets prints (it used to print the raw index).

FastAPI lives only in `webui/.venv`; under the conda `pytest` this file skips:

    webui/.venv/Scripts/python.exe -m pytest tests/test_webui_dataset_naming.py
"""

import os
import sqlite3
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBUI_DIR = os.path.join(PROJECT_ROOT, "webui")
for p in (PROJECT_ROOT, WEBUI_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

pytest.importorskip("fastapi", reason="FastAPI is only in webui/.venv; run this file with that interpreter")
pytest.importorskip("httpx", reason="fastapi.testclient needs httpx (webui/.venv)")

from fastapi.testclient import TestClient  # noqa: E402

from Working.database.schema import init_db  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runtime import HELD_OUT_FILE, Runtime  # noqa: E402

HELD_STEM = HELD_OUT_FILE[:-4]


def _fresh_db(tmp_path):
    db_dir = tmp_path / "db"; db_dir.mkdir()
    db = db_dir / "annotations.sqlite"
    conn = init_db(str(db))
    ins = "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path) VALUES (?, ?, ?, ?, 0, ?)"
    conn.execute(ins, (HELD_OUT_FILE, 0, 1.0, 10, f"{HELD_STEM}/CH0.npy"))
    for ch in range(5):
        conn.execute(ins, ("L_LM_Jul_26_J_raw.mat", ch, 10.0, 144010, f"L_LM_Jul_26_J_raw_fs10/CH{ch}.npy"))
    parent = conn.execute("SELECT id FROM recordings WHERE source_file = 'L_LM_Jul_26_J_raw.mat' AND channel = 2").fetchone()[0]
    conn.execute(ins, ("Mushroom_CH14_fs1.mat", 0, 1.0, 14401, "Mushroom_CH14_fs1/Mushroom_CH14_fs1_CH00.npy"))
    conn.execute("UPDATE recordings SET parent_recording_id = ?, parent_offset = 100, decimation = 10 WHERE source_file = 'Mushroom_CH14_fs1.mat'", (parent,))
    conn.commit(); conn.close()
    return db


@pytest.fixture
def bridge(tmp_path):
    db = _fresh_db(tmp_path)
    dist = tmp_path / "dist"; (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    rt = Runtime(mode="sandbox", stamp="20261001-f", db_source=str(db), runtime_root=str(tmp_path / "runtime"), client_dist=str(dist))
    rt.setup()
    try:
        app = create_app(rt)
        app.state.registry_roots = {"recording": [str(tmp_path / "none")], "raw": [str(tmp_path / "none")]}
        with TestClient(app) as client:
            yield client, rt
    finally:
        rt.restore()


def _name(client, stem, **fields):
    return client.put("/api/settings/datasets", json={"values": {f"meta.{stem}.{k}": v for k, v in fields.items()}})


# ---------------------------------------------------------------- settings --

def test_a_save_on_settings_datasets_lands_in_the_datasets_table_and_is_audited(bridge):
    client, rt = bridge
    r = _name(client, "L_LM_Jul_26_J_raw_fs10", display_name="Lion's mane J", species="Hericium erinaceus", organism_id="LM-J",
              experiment_date="2026-07-26", condition="baseline", notes="five electrodes")
    assert r.status_code == 200, r.text
    assert len(r.json()["changed"]) == 6
    conn = sqlite3.connect(rt.db_path); conn.row_factory = sqlite3.Row
    row = dict(conn.execute("SELECT * FROM datasets WHERE source_file = 'L_LM_Jul_26_J_raw.mat'").fetchone())
    assert row["display_name"] == "Lion's mane J" and row["organism_id"] == "LM-J" and row["experiment_date"] == "2026-07-26"
    assert conn.execute("SELECT COUNT(*) FROM settings WHERE key LIKE 'meta.%display_name'").fetchone()[0] == 0, \
        "the datasets table is the one store: the name is not also a settings row"
    conn.close()
    back = client.get("/api/settings/datasets").json()
    assert back["values"]["meta.L_LM_Jul_26_J_raw_fs10.display_name"] == "Lion's mane J"
    assert back["values"]["meta.L_LM_Jul_26_J_raw_fs10.organism_id"] == "LM-J"
    rec = next(x for x in back["recordings"] if x["name"] == "L_LM_Jul_26_J_raw_fs10")
    assert rec["display_name"] == "Lion's mane J" and rec["source_file"] == "L_LM_Jul_26_J_raw.mat"
    assert "Hericium erinaceus" in back["species_values"]
    entry = client.get("/api/audit?kind=settings").json()["entries"][0]
    assert entry["where"] == "Datasets" and "L_LM_Jul_26_J_raw.mat" in entry["what"] and "Lion's mane J" in entry["what"], \
        "the audit trail names the FILE: the source file is always reachable"


def test_a_bad_date_and_a_duplicate_name_are_422_and_write_nothing(bridge):
    client, rt = bridge
    assert _name(client, "L_LM_Jul_26_J_raw_fs10", experiment_date="26 July").status_code == 422
    assert _name(client, "L_LM_Jul_26_J_raw_fs10", display_name="J").status_code == 200
    r = _name(client, "Mushroom_CH14_fs1", display_name="j", species="x")
    assert r.status_code == 422 and "already" in r.text
    conn = sqlite3.connect(rt.db_path)
    assert conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0] == 1, "a refused save is all-or-nothing"
    conn.close()


def test_other_dataset_settings_still_live_in_the_settings_table(bridge):
    client, _ = bridge
    r = client.put("/api/settings/datasets", json={"values": {"meta.Mushroom_CH14_fs1.substrate": "oak", "meta.Mushroom_CH14_fs1.species": "Hericium"}})
    assert r.status_code == 200 and set(r.json()["changed"]) == {"meta.Mushroom_CH14_fs1.substrate", "meta.Mushroom_CH14_fs1.species"}
    v = client.get("/api/settings/datasets").json()["values"]
    assert v["meta.Mushroom_CH14_fs1.substrate"] == "oak" and v["meta.Mushroom_CH14_fs1.species"] == "Hericium"


# ---------------------------------------------------------------- the seam --

def test_the_names_route_lists_every_source_file_named_or_not(bridge):
    client, _ = bridge
    _name(client, "L_LM_Jul_26_J_raw_fs10", display_name="Lion's mane J", organism_id="LM-J")
    body = client.get("/api/datasets").json()
    by = {d["source_file"]: d for d in body["datasets"]}
    assert set(by) == {HELD_OUT_FILE, "L_LM_Jul_26_J_raw.mat", "Mushroom_CH14_fs1.mat"}
    named = by["L_LM_Jul_26_J_raw.mat"]
    assert named["name"] == "Lion's mane J" and named["named"] is True and named["organism_id"] == "LM-J"
    assert named["n_channels"] == 5 and named["fs"] == 10.0 and named["stem"] == "L_LM_Jul_26_J_raw_fs10"
    plain = by["Mushroom_CH14_fs1.mat"]
    assert plain["name"] == "Mushroom_CH14_fs1.mat" and plain["named"] is False, "no name: the source file, said to be the file"
    assert plain["has_parent"] is True, "the higher-resolution parent is a derived, read-only fact"


def test_every_workspace_read_prints_the_same_name_and_keeps_its_keys(bridge):
    client, _ = bridge
    before = client.get("/api/discovery/session").json()["recordings"]
    _name(client, "L_LM_Jul_26_J_raw_fs10", display_name="Lion's mane J")
    rec = next(r for r in client.get("/api/recordings").json() if r["source_file"] == "L_LM_Jul_26_J_raw.mat")
    assert rec["display_name"] == "Lion's mane J"
    other = next(r for r in client.get("/api/recordings").json() if r["source_file"] == "Mushroom_CH14_fs1.mat")
    assert other["display_name"] == "Mushroom_CH14_fs1.mat"
    after = client.get("/api/discovery/session").json()["recordings"]
    opt = next(r for r in after if r["file"] == "L_LM_Jul_26_J_raw.mat")
    assert opt["label"] == "Lion's mane J"
    assert [(r["key"], r["stem"], r["file"]) for r in after] == [(r["key"], r["stem"], r["file"]) for r in before], \
        "a display name is never an identifier: nothing keys or routes on it"
    reg = next(r for r in client.get("/api/registry/recording").json()["registered"] if r["source_file"] == "L_LM_Jul_26_J_raw.mat")
    assert reg["name"] == "L_LM_Jul_26_J_raw_fs10" and reg["display_name"] == "Lion's mane J"


def test_the_held_out_unlock_is_typed_against_the_name_the_page_prints(bridge):
    client, _ = bridge
    assert client.get("/api/settings/datasets").json()["held_out"]["name"] == HELD_STEM
    # the lock is on: the held-out dataset's metadata is not written through the interface
    assert _name(client, HELD_STEM, display_name="the final exam").status_code in (409, 423)


# ------------------------------------------------- one channel convention --

def test_the_excerpt_link_names_its_parent_channel_through_channel_name(bridge):
    client, _ = bridge
    regs = client.get("/api/registry/recording").json()["registered"]
    child = next(r for r in regs if r["source_file"] == "Mushroom_CH14_fs1.mat")
    assert child["excerpt_of"]["channel"] == 2
    assert child["excerpt_of"]["channel_name"] == "CH3", "Datasets printed CH2 where Explore and Review print CH3"
    parent = next(r for r in regs if r["source_file"] == "L_LM_Jul_26_J_raw.mat")
    assert [c["name"] for c in parent["channels"]] == ["CH1", "CH2", "CH3", "CH4", "CH5"]
