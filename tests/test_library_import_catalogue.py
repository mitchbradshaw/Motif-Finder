"""
test_library_import_catalogue.py
================================
`docs/LIBRARY_STORAGE.md` §5 — the `signal_catalog.xlsx` importer.

The spreadsheet is 37 rows of a researcher's own notebook, and almost nothing
in it is a foreign key. The three bindings it does have are the ones tested
here:

* **to a recording** — `Pack` and `Channel` are per-pack, so the global channel
  is `Pack*4 + Channel`. The scout verified that rule against all 15 catalogue
  ids present in the drop-motif seed, 15/15;
* **to a span** — `StartTime_h * 3600` at the recording's own `fs`;
* **to a species** — only indirectly, through `(Experiment, Pack)` decoded
  against a free-text legend, and the two experiments give `Pack` *different*
  meanings. A row whose pair is not in the legend gets no species rather than a
  guess.

Six of the 37 rows were never imported. One of them (ID 19) is importable and
is backfilled; the other five are not, and the importer must say why for each
rather than dropping them silently or inventing a binding. Both halves are
tested.

The hard property is **idempotence**: 31 of these rows are already in the live
database as `annotations` rows with `source = 'excel_catalog'`, and a second
run must recognise them rather than double the catalogue. The test builds that
state explicitly — an annotation at the bound span, inserted before the import
runs — because "re-running my own import is a no-op" is the weaker claim and
would pass on an importer that keys on something only it writes.

Headless: one temp-file database and one temp workbook per test. Nothing here
reads `DATA/catalogue/signal_catalog.xlsx` or `DATA/db/annotations.sqlite`.
"""

import os
import sqlite3
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import openpyxl

from Working.database import queries as q
from Working.database.schema import init_db
from Working.database.vocabulary import get_annotation_tags
from Working.library.importers.catalogue import (
    CATALOGUE_SOURCE,
    SPECIES_BY_EXPERIMENT_PACK,
    global_channel,
    import_catalogue,
    split_elements,
)

COLUMNS = [
    "ID_Number", "ID_Name", "Experiment", "GrowTent", "Pack", "Channel",
    "StartTime_h", "StopTime_h", "Length_s", "AmplitudeMax", "AmplitudeMin",
    "Elements", "sequence_structure", "Notes", "Reference_Notes", "DATASET",
    "STATUS", "Parent_ID",
]

N_SAMPLES = 3_000_000


def _row(**kw):
    """One spreadsheet row with the shape the real sheet has, overridden by kw."""
    base = dict.fromkeys(COLUMNS)
    base.update({
        "ID_Number": 1, "Experiment": "E01", "GrowTent": "GT01", "Pack": 0,
        "Channel": 0, "StartTime_h": 336.0, "StopTime_h": 346.0,
        "Elements": "sharkfin", "sequence_structure": "16 cycles; 20 - 70 mV",
        "DATASET": "M2_aug", "STATUS": "candidate", "Parent_ID": 0,
    })
    base.update(kw)
    return base


def _workbook(path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(COLUMNS)
    for r in rows:
        ws.append([r.get(c) for c in COLUMNS])
    wb.save(str(path))
    return str(path)


@pytest.fixture()
def conn(tmp_path):
    """A database registering channels 0, 1 and 3 of `M2_aug_concat_fs1.mat` —
    the global channels `Pack*4 + Channel` resolves to in these fixtures."""
    db = tmp_path / "catalogue.sqlite"
    init_db(str(db))
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    for channel in (0, 1, 3):
        q.insert_recording(
            c, "M2_aug_concat_fs1.mat", channel, fs=1.0, n_samples=N_SAMPLES,
            global_offset=0,
            npy_path=str(tmp_path / f"M2_aug_concat_fs1_CH{channel:02d}.npy"),
        )
    yield c
    c.close()


# ── the three bindings ───────────────────────────────────────────────────────

def test_the_global_channel_is_pack_times_four_plus_channel():
    """The rule the scout verified 15/15 against the seed."""
    assert global_channel(0, 0) == 0
    assert global_channel(0, 3) == 3
    assert global_channel(3, 3) == 15
    assert global_channel(1, 2) == 6


def test_a_row_binds_to_a_recording_and_a_span(conn, tmp_path):
    xlsx = _workbook(tmp_path / "cat.xlsx", [_row()])

    report = import_catalogue(conn, xlsx)

    assert report.counts["annotations"] == 1
    ann = conn.execute(
        "SELECT * FROM annotations WHERE source = ?", (CATALOGUE_SOURCE,)
    ).fetchone()
    assert ann["start_idx"] == 336 * 3600
    assert ann["end_idx"] == 346 * 3600
    assert ann["recording_id"] == q.get_recording(conn, "M2_aug_concat_fs1.mat", 0)["id"]
    assert ann["status"] == "candidate"
    assert "16 cycles" in ann["note"]


def test_pack_one_channel_three_lands_on_global_channel_seven(conn, tmp_path):
    """A row whose global channel is not registered must be reported, not bound
    to the wrong trace: `Pack*4 + Channel` = 7 and only 0, 1 and 3 exist here."""
    xlsx = _workbook(tmp_path / "cat.xlsx", [_row(Pack=1, Channel=3)])

    report = import_catalogue(conn, xlsx)

    assert report.counts["annotations"] == 0
    assert len(report.skips) == 1
    assert "channel 7" in report.skips[0]["reason"]


def test_a_catalogue_row_writes_a_human_sequence_needing_extraction(conn, tmp_path):
    xlsx = _workbook(tmp_path / "cat.xlsx", [_row()])

    import_catalogue(conn, xlsx)

    seq = conn.execute("SELECT * FROM sequences").fetchone()
    assert seq["origin"] == "human"
    assert seq["source_kind"] == "catalogue"
    assert seq["needs_extraction"] == 1
    assert seq["annotation_id"] is not None
    assert seq["n_events"] == 16
    # Rule 5: a catalogue row is human data and writes no machine row.
    assert conn.execute("SELECT COUNT(*) FROM detections").fetchone()[0] == 0


# ── species ──────────────────────────────────────────────────────────────────

def test_species_needs_the_experiment_as_well_as_the_pack(conn, tmp_path):
    """E01 Pack 0 is Lion's mane; E02 Pack 0 is White Oyster. A `Pack`-only
    rule would label half the catalogue wrong."""
    assert SPECIES_BY_EXPERIMENT_PACK[("E01", 0)] != SPECIES_BY_EXPERIMENT_PACK[("E02", 0)]
    xlsx = _workbook(tmp_path / "cat.xlsx", [
        _row(ID_Number=1, Experiment="E01", Pack=0, Channel=0),
        _row(ID_Number=2, Experiment="E02", Pack=0, Channel=1,
             StartTime_h=10.0, StopTime_h=11.0),
    ])

    import_catalogue(conn, xlsx)

    rows = conn.execute(
        "SELECT * FROM annotations WHERE source = ? ORDER BY start_idx",
        (CATALOGUE_SOURCE,),
    ).fetchall()
    species = [get_annotation_tags(conn, r["id"]).get("species") for r in rows]
    assert species == [["white_oyster"], ["lions_mane"]]


def test_an_unknown_experiment_pack_pair_gets_no_species(conn, tmp_path):
    xlsx = _workbook(tmp_path / "cat.xlsx", [_row(Experiment="E09", Pack=0)])
    import_catalogue(conn, xlsx)
    ann = conn.execute(
        "SELECT * FROM annotations WHERE source = ?", (CATALOGUE_SOURCE,)
    ).fetchone()
    assert "species" not in get_annotation_tags(conn, ann["id"])


# ── elements and tags ────────────────────────────────────────────────────────

def test_elements_split_on_both_separators_and_correct_the_known_typo():
    assert split_elements("crestedwave ; sharkfin") == ["crestedwave", "sharkfin"]
    assert split_elements("sharkfin; tonic bursting") == ["sharkfin", "tonic_bursting"]
    assert split_elements("Stegasauras") == ["stegasaurus"]
    assert split_elements("sharkfins") == ["sharkfin"]
    assert split_elements("'...'") == []
    assert split_elements(None) == []


def test_tags_are_created_once_and_then_reused(conn, tmp_path):
    xlsx = _workbook(tmp_path / "cat.xlsx", [
        _row(ID_Number=1, Elements="sharkfin; Stegasauras"),
        _row(ID_Number=2, Channel=1, Elements="sharkfin",
             StartTime_h=10.0, StopTime_h=11.0),
    ])

    import_catalogue(conn, xlsx)

    n_terms = conn.execute(
        "SELECT COUNT(*) FROM tag_vocabulary WHERE category = 'element' "
        "AND value IN ('sharkfin', 'stegasaurus')"
    ).fetchone()[0]
    assert n_terms == 2
    rows = conn.execute(
        "SELECT * FROM annotations WHERE source = ? ORDER BY start_idx",
        (CATALOGUE_SOURCE,),
    ).fetchall()
    tags = [sorted(get_annotation_tags(conn, r["id"])["element"]) for r in rows]
    assert tags == [["sharkfin"], ["sharkfin", "stegasaurus"]]


# ── the rows that cannot be imported ─────────────────────────────────────────

@pytest.mark.parametrize("override,fragment", [
    ({"DATASET": None}, "DATASET"),
    ({"DATASET": "labview restarts every 100000 sampels"}, "note"),
    ({"StartTime_h": None}, "StartTime_h"),
    ({"StopTime_h": None}, "StopTime_h"),
    ({"DATASET": "Mushroom_25_12_06_0954"}, "no registered recording"),
])
def test_a_row_that_cannot_bind_is_reported_with_its_reason(conn, tmp_path,
                                                            override, fragment):
    xlsx = _workbook(tmp_path / "cat.xlsx", [_row(**override)])

    report = import_catalogue(conn, xlsx)

    assert report.counts["annotations"] == 0
    assert len(report.skips) == 1
    assert fragment in report.skips[0]["reason"]
    assert report.skips[0]["ref"] == "ID 1"


def test_the_held_out_recording_is_refused(conn, tmp_path):
    """`M4_aug_concat_fs1.mat` is refused on every route — the evaluation
    recording stays untouched until the freeze by construction."""
    xlsx = _workbook(tmp_path / "cat.xlsx", [_row(DATASET="M4_aug")])

    report = import_catalogue(conn, xlsx)

    assert report.counts["annotations"] == 0
    assert "held out" in report.skips[0]["reason"]
    assert conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0] == 0


def test_the_importable_rows_still_import_when_a_neighbour_cannot(conn, tmp_path):
    """The backfill case: five of the six missing rows are unimportable and one
    is not, and the five must not take the sixth down with them."""
    xlsx = _workbook(tmp_path / "cat.xlsx", [
        _row(ID_Number=14, DATASET=None),
        _row(ID_Number=15, StartTime_h=None),
        _row(ID_Number=19, StartTime_h=337.9, StopTime_h=338.18),
    ])

    report = import_catalogue(conn, xlsx)

    assert report.counts["annotations"] == 1
    assert {s["ref"] for s in report.skips} == {"ID 14", "ID 15"}
    assert conn.execute(
        "SELECT start_idx FROM annotations WHERE source = ?", (CATALOGUE_SOURCE,)
    ).fetchone()[0] == round(337.9 * 3600)


# ── idempotence ──────────────────────────────────────────────────────────────

def test_a_row_already_in_the_database_is_recognised_not_duplicated(conn, tmp_path):
    """The 31 live rows: an `annotations` row at the bound span with
    `source = 'excel_catalog'`, written before this importer existed."""
    recording_id = q.get_recording(conn, "M2_aug_concat_fs1.mat", 0)["id"]
    q.insert_annotation(
        conn, recording_id, 336 * 3600, 346 * 3600, "interesting",
        source=CATALOGUE_SOURCE, note="16 cycles; 20 - 70 mV", status="candidate",
    )
    xlsx = _workbook(tmp_path / "cat.xlsx", [_row()])

    report = import_catalogue(conn, xlsx)

    assert report.counts["annotations"] == 0
    assert report.counts["already_imported"] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM annotations WHERE source = ?", (CATALOGUE_SOURCE,)
    ).fetchone()[0] == 1


def test_re_running_the_import_writes_nothing_new(conn, tmp_path):
    xlsx = _workbook(tmp_path / "cat.xlsx", [
        _row(ID_Number=1),
        _row(ID_Number=2, Channel=1, StartTime_h=10.0, StopTime_h=11.0),
    ])
    import_catalogue(conn, xlsx)
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("annotations", "sequences", "annotation_tags")}

    second = import_catalogue(conn, xlsx)

    assert second.counts["annotations"] == 0
    assert second.counts["already_imported"] == 2
    assert counts == {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in ("annotations", "sequences", "annotation_tags")}


def test_dry_run_writes_nothing(conn, tmp_path):
    xlsx = _workbook(tmp_path / "cat.xlsx", [_row()])

    report = import_catalogue(conn, xlsx, dry_run=True)

    assert report.dry_run is True
    assert report.counts["annotations"] == 1
    assert conn.execute("SELECT COUNT(*) FROM annotations").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM sequences").fetchone()[0] == 0


def test_progress_is_called_per_row(conn, tmp_path):
    xlsx = _workbook(tmp_path / "cat.xlsx", [
        _row(ID_Number=1),
        _row(ID_Number=2, Channel=1, StartTime_h=10.0, StopTime_h=11.0),
    ])
    seen = []
    import_catalogue(conn, xlsx,
                     progress=lambda done, total, what: seen.append((done, total)))
    assert seen and seen[-1] == (2, 2)
