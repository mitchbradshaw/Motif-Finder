"""
test_dataset_identity.py
========================
fixup-f — a dataset has an identity, and it is a property of the FILE.

`recordings` is one row per channel (`UNIQUE (source_file, channel)`); what the
researcher calls a dataset is the set of rows sharing a `source_file`. Species,
organism id, experiment date, condition, display name and notes belong to that
set, so they live in a `datasets` table keyed by `source_file` rather than
repeated on every channel row (docs/prompts/fixup/F-datasets-and-naming.md §1).

What is pinned here, headless and on temp databases:

* the table is additive, created through `init_db()`, and idempotent;
* a source file with no row has no metadata and is called by its file name —
  the ONE fallback rule (`display_name`), which every label goes through;
* a display name is a label, never an identifier: writing one touches no
  `recordings` row, and `recordings.notes` (per-channel) is never migrated;
* `experiment_date` validates as a date; two datasets cannot share a name;
* a channel is called one thing everywhere: `channel_name`, one-based, and
  the scoreboard goes through it instead of printing the raw index.
"""

import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database.schema import init_db  # noqa: E402


def _db(tmp_path):
    return init_db(str(tmp_path / "db" / "annotations.sqlite"))


def _insert(conn, source_file, channel=0, notes=None):
    cur = conn.execute(
        "INSERT INTO recordings (source_file, channel, fs, n_samples, global_offset, npy_path, notes) "
        "VALUES (?, ?, 1.0, 100, 0, ?, ?)", (source_file, channel, f"{source_file[:-4]}/CH{channel}.npy", notes))
    conn.commit()
    return cur.lastrowid


def _columns(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


# ------------------------------------------------------------------ schema --

def test_init_db_creates_the_datasets_table_keyed_by_source_file(tmp_path):
    conn = _db(tmp_path)
    cols = _columns(conn, "datasets")
    assert {"source_file", "display_name", "species", "organism_id", "experiment_date", "condition", "notes"} <= cols
    pk = [r["name"] for r in conn.execute("PRAGMA table_info(datasets)") if r["pk"]]
    assert pk == ["source_file"], "a dataset is the set of recordings rows sharing a source_file"


def test_init_db_is_idempotent_and_keeps_what_was_written(tmp_path):
    from Working.database import datasets
    conn = _db(tmp_path)
    _insert(conn, "M2_aug_concat_fs1.mat")
    datasets.put_dataset(conn, "M2_aug_concat_fs1.mat", {"display_name": "M2 August", "species": "Pleurotus"})
    conn.close()
    conn = _db(tmp_path)
    conn = init_db(str(tmp_path / "db" / "annotations.sqlite"))
    assert datasets.get_dataset(conn, "M2_aug_concat_fs1.mat")["display_name"] == "M2 August"
    assert conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0] == 1


def test_the_table_is_added_to_a_database_that_predates_it(tmp_path):
    conn = _db(tmp_path)
    _insert(conn, "M1.mat", notes="fs 10 Hz read from M1_M100.mat::t1")
    conn.execute("DROP TABLE datasets"); conn.commit(); conn.close()
    conn = _db(tmp_path)
    assert "datasets" in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    # recordings.notes is per-channel text and is NOT silently folded into the dataset's notes
    assert conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0] == 0
    assert conn.execute("SELECT notes FROM recordings WHERE source_file = 'M1.mat'").fetchone()[0].startswith("fs 10 Hz")


# ---------------------------------------------------------------- the rule --

def test_a_dataset_is_called_by_its_display_name_or_by_its_source_file(tmp_path):
    from Working.database import datasets
    conn = _db(tmp_path)
    _insert(conn, "M2_aug_concat_fs1.mat"); _insert(conn, "M2_concat_fs1.mat")
    assert datasets.display_name(conn, "M2_aug_concat_fs1.mat") == "M2_aug_concat_fs1.mat"
    datasets.put_dataset(conn, "M2_aug_concat_fs1.mat", {"display_name": "M2 August"})
    assert datasets.display_name(conn, "M2_aug_concat_fs1.mat") == "M2 August"
    assert datasets.display_name(conn, "M2_concat_fs1.mat") == "M2_concat_fs1.mat"
    names = datasets.display_names(conn)
    assert names == {"M2_aug_concat_fs1.mat": "M2 August", "M2_concat_fs1.mat": "M2_concat_fs1.mat"}, \
        "every registered source file has a name, named or not"
    # a blank name is no name: back to the file
    datasets.put_dataset(conn, "M2_aug_concat_fs1.mat", {"display_name": "   "})
    assert datasets.display_name(conn, "M2_aug_concat_fs1.mat") == "M2_aug_concat_fs1.mat"


def test_a_source_file_with_no_row_simply_has_no_metadata(tmp_path):
    from Working.database import datasets
    conn = _db(tmp_path)
    _insert(conn, "M1.mat")
    d = datasets.get_dataset(conn, "M1.mat")
    assert d["source_file"] == "M1.mat"
    assert all(d[f] is None for f in datasets.FIELDS)


def test_put_returns_what_changed_and_never_touches_recordings(tmp_path):
    from Working.database import datasets
    conn = _db(tmp_path)
    rid = _insert(conn, "M1.mat", notes="per-channel text")
    before = tuple(conn.execute("SELECT * FROM recordings WHERE id = ?", (rid,)).fetchone())
    changed = datasets.put_dataset(conn, "M1.mat", {"species": "Hericium erinaceus", "organism_id": "LM-J",
                                                    "experiment_date": "2026-07-20", "condition": "baseline",
                                                    "notes": "the dataset's own note"})
    assert set(changed) == {"species", "organism_id", "experiment_date", "condition", "notes"}
    assert datasets.put_dataset(conn, "M1.mat", {"species": "Hericium erinaceus"}) == [], "an unchanged value is not a change"
    assert tuple(conn.execute("SELECT * FROM recordings WHERE id = ?", (rid,)).fetchone()) == before, \
        "a display name is a label: the keys, the files and recordings.notes are untouched"
    d = datasets.get_dataset(conn, "M1.mat")
    assert d["organism_id"] == "LM-J" and d["experiment_date"] == "2026-07-20" and d["notes"] == "the dataset's own note"
    assert datasets.species_values(conn) == ["Hericium erinaceus"], "species is free text with the existing values offered"


def test_put_refuses_a_bad_date_a_duplicate_name_an_unknown_field_and_an_unknown_file(tmp_path):
    from Working.database import datasets
    conn = _db(tmp_path)
    _insert(conn, "M2_aug_concat_fs1.mat"); _insert(conn, "M2_concat_fs1.mat")
    with pytest.raises(ValueError, match="experiment_date"):
        datasets.put_dataset(conn, "M2_concat_fs1.mat", {"experiment_date": "20 July"})
    with pytest.raises(ValueError, match="experiment_date"):
        datasets.put_dataset(conn, "M2_concat_fs1.mat", {"experiment_date": "2026-02-30"})
    datasets.put_dataset(conn, "M2_aug_concat_fs1.mat", {"display_name": "M2"})
    with pytest.raises(ValueError, match="already"):
        datasets.put_dataset(conn, "M2_concat_fs1.mat", {"display_name": "m2"})
    with pytest.raises(ValueError, match="already"):
        # nor may a name be another dataset's FILE name: that is the confusion the table exists to end
        datasets.put_dataset(conn, "M2_concat_fs1.mat", {"display_name": "M2_aug_concat_fs1.mat"})
    with pytest.raises(ValueError, match="field"):
        datasets.put_dataset(conn, "M2_concat_fs1.mat", {"source_file": "renamed.mat"})
    with pytest.raises(KeyError):
        datasets.put_dataset(conn, "nope.mat", {"display_name": "x"})
    assert conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0] == 1, "a refused write leaves nothing behind"


# --------------------------------------------------- one channel convention --

def test_a_channel_is_named_one_based_whatever_the_file():
    from Working.discovery.channels import channel_index_note, channel_name
    assert channel_name("M2_aug_concat_fs1.mat", 0, 16) == "CH1_A1"
    assert channel_name("L_LM_Jul_26_J_raw.mat", 2, 5) == "CH3"
    assert channel_name("Fig2A_dt0p1.csv", 4, 5) == "CH5"
    # the stored index stays reachable beside the name: it is what the file on disk is called
    assert channel_index_note(2) == "recordings.channel = 2 · CH2.npy"


def test_the_scoreboard_names_a_channel_through_channel_name(tmp_path):
    from Working.discovery import scoreboard
    conn = _db(tmp_path)
    for ch in range(5):
        rid = _insert(conn, "L_LM_Jul_26_J_raw.mat", ch)
    rec = conn.execute("SELECT * FROM recordings WHERE id = ?", (rid,)).fetchone()
    assert scoreboard._channel_name(conn, rec) == "CH5", "one convention: the scoreboard used to print the raw index, CH4"
