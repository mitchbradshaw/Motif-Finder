"""
test_library_import_event_store.py
==================================
`docs/LIBRARY_STORAGE.md` §5 and §2.4 — turning a detector's event store into
Library rows.

Everything here runs against `tests/fixtures/library/event_store`, a five-event
synthetic store written by `make_fixture.py` in the same directory, never
against `DATA/` or `Plots/`. Its five rows are one each of the five things the
importer has to get right:

    ev1  a new shape
    ev2  a second, different shape
    ev3  ev1's waveform in another recording  -> one entry, two members
    ev4  a near-duplicate of ev1 in the same place -> its own entry, FLAGGED
    ev5  recording_id 999, which binds to nothing -> warned and skipped

The properties this file exists to hold:

  * **idempotence** (PRD story 43) — the second run writes nothing;
  * **a dry run cannot write** — the row counts are identical afterwards;
  * **a near-duplicate is never merged** — two entries, plus a flag carrying
    the rule it was raised under;
  * **the held-out file is refused loudly** — `M4_aug_concat_fs1.mat` never
    enters the library by any route;
  * **an unbindable row is counted, not dropped silently.**

Headless: one temporary SQLite database, no channel `.npy` is ever read (the
waveform comes from the store's own `snippets.npz`).
"""

import json
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

from Working.config import HELD_OUT_RECORDING_FILE
from Working.database import queries as q
from Working.database import vocabulary as V
from Working.database.schema import init_db
from Working.library.importers.event_store import (
    DEFAULT_EXCLUDED_CORPORA,
    WAVEFORM_FIELD,
    ImportReport,
    StoreRefused,
    import_event_store,
    read_event_store,
)

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fixtures", "library")
STORE = os.path.join(FIXTURES, "event_store")
PARTIAL_STORE = os.path.join(FIXTURES, "event_store_partial")

# Every test that wants all five rows has to say so: the module default drops
# the 1 Hz control corpus, and ev3 is in it.
ALL_CORPORA = ()


# ── fixtures ─────────────────────────────────────────────────────────────────

def _make_db(tmp_path, first_source_file="M2_aug_concat_fs1.mat"):
    """A database holding exactly the two recordings the fixture store binds to.

    The store's rows carry `recording_id` 1 and 2 literally, so the two
    recordings must land on ids 1 and 2. They do, because the table is empty
    and the ids are AUTOINCREMENT — asserted rather than assumed, so a future
    migration that seeds `recordings` fails here and not three tests later with
    an unreadable message.
    """
    db = tmp_path / "library.sqlite"
    init_db(str(db))
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    one = q.insert_recording(conn, first_source_file, 0, fs=1.0,
                             n_samples=100_000, global_offset=0,
                             npy_path="DATA/derived/ch0.npy")
    two = q.insert_recording(conn, "M2_aug_concat_fs1.mat", 1, fs=1.0,
                             n_samples=100_000, global_offset=100_000,
                             npy_path="DATA/derived/ch1.npy")
    assert (one, two) == (1, 2), "the fixture store names recording ids 1 and 2"
    return conn


@pytest.fixture()
def conn(tmp_path):
    c = _make_db(tmp_path)
    yield c
    c.close()


def _counts(conn):
    """Row counts of every table the importer may write, for the dry-run guard."""
    tables = ("motif_entry", "motif_member", "motif_member_revision",
              "motif_entry_tags", "tag_vocabulary", "audit_log")
    return {t: conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
            for t in tables}


# ── reading the store ────────────────────────────────────────────────────────

def test_read_event_store_returns_the_five_events_and_their_snippets():
    run = read_event_store(STORE)
    assert len(run["events"]) == 5
    assert len(run["snippets"]) == 5
    assert run["manifest"]["n_motifs"] == 5


def test_the_hashed_waveform_is_the_detrended_one():
    """§2.3 leaves the choice to the importer and requires it to be stated.
    The detrended trace is what detection ran on and what "the same shape" was
    defined against; the raw trace carries the channel's baseline."""
    assert WAVEFORM_FIELD == "detrended_mv"


def test_a_partial_store_is_read_but_refused_by_name():
    """drop_motifs12a is readable and deliberately not imported on this
    machine. The refusal has to say why — a silent skip would look like an
    empty store."""
    assert len(read_event_store(PARTIAL_STORE)["events"]) == 5
    with pytest.raises(StoreRefused) as excinfo:
        import_event_store(sqlite3.connect(":memory:"), PARTIAL_STORE)
    assert "partial" in str(excinfo.value).lower()


# ── the clean import ─────────────────────────────────────────────────────────

def test_a_clean_import_of_five_events(conn):
    report = import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)

    assert isinstance(report, ImportReport)
    assert report.n_rows == 5
    # ev1, ev2 and ev4 create entries; ev3 joins ev1's; ev5 binds to nothing.
    assert report.n_created == 3
    assert report.n_duplicate == 1
    assert report.n_near_flagged == 1
    assert report.n_skipped == 1

    assert conn.execute("SELECT COUNT(*) FROM motif_entry").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM motif_member").fetchone()[0] == 4
    # Every member gets revision 1, origin machine (§2.5).
    revisions = conn.execute(
        "SELECT COUNT(*) FROM motif_member_revision WHERE origin = 'machine'"
    ).fetchone()[0]
    assert revisions == 4


def test_provenance_is_carried_onto_every_entry(conn):
    import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA,
                       source_store="tests/fixtures/library/event_store")
    rows = conn.execute(
        "SELECT source_kind, source_store, source_ref, channel, fs, scale "
        "FROM motif_entry ORDER BY id"
    ).fetchall()
    assert [r["source_kind"] for r in rows] == ["event_store"] * 3
    assert all(r["source_store"] == "tests/fixtures/library/event_store"
               for r in rows)
    assert rows[0]["source_ref"] == "id001_r1_1000"
    assert rows[0]["channel"] == 0
    assert rows[0]["fs"] == 1.0
    assert all(r["scale"] == "event" for r in rows)


def test_the_content_hash_is_on_the_entry_and_on_its_members(conn):
    import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)
    for row in conn.execute("SELECT id, content_hash FROM motif_entry"):
        assert row["content_hash"] and len(row["content_hash"]) == 32
        members = conn.execute(
            "SELECT content_hash FROM motif_member WHERE entry_id = ?",
            (row["id"],)).fetchall()
        assert all(m["content_hash"] == row["content_hash"] for m in members)


# ── §2.4: exact, near, new ───────────────────────────────────────────────────

def test_an_exact_duplicate_becomes_a_second_member_not_a_second_entry(conn):
    """ev3 is ev1's waveform in another recording. Same hash means the same
    entry and never a second one (§2.1) — and a shape recurring somewhere else
    is the whole point of the library, so it must not be dropped either."""
    import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)
    entry = conn.execute(
        "SELECT id FROM motif_entry WHERE source_ref = 'id001_r1_1000'"
    ).fetchone()
    members = conn.execute(
        "SELECT recording_id, start_idx, end_idx FROM motif_member "
        "WHERE entry_id = ? ORDER BY recording_id", (entry["id"],)
    ).fetchall()
    assert [(m["recording_id"], m["start_idx"], m["end_idx"]) for m in members] \
        == [(1, 1000, 1100), (2, 2000, 2100)]


def test_a_near_duplicate_gets_its_own_entry_and_a_flag(conn):
    """ev4 overlaps ev1 at IoU 0.818 with a 10-sample onset delta on a
    100-sample span — inside both halves of the §4.6 rule — but hashes
    differently. Flagged for review, never merged."""
    report = import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)

    near = conn.execute(
        "SELECT id FROM motif_entry WHERE source_ref = 'id003_r1_1010'"
    ).fetchone()
    first = conn.execute(
        "SELECT id FROM motif_entry WHERE source_ref = 'id001_r1_1000'"
    ).fetchone()
    assert near is not None and near["id"] != first["id"]

    assert len(report.flags) == 1
    flag = report.flags[0]
    assert flag["source_ref"] == "id003_r1_1010"
    assert flag["iou"] == pytest.approx(0.8181818, abs=1e-6)
    # The rule travels with the flag (§4.6: the rule is recorded on the run).
    assert flag["iou_threshold"] == 0.5
    assert flag["onset_tolerance_fraction"] == 0.25

    logged = conn.execute(
        "SELECT COUNT(*) FROM audit_log WHERE kind = 'library_near_duplicate'"
    ).fetchone()[0]
    assert logged == 1


# ── idempotence and the dry run ──────────────────────────────────────────────

def test_a_second_run_imports_nothing(conn):
    """PRD story 43. Re-import must resolve onto what is already there rather
    than fork the catalogue."""
    import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)
    before = _counts(conn)

    again = import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)

    assert again.n_created == 0
    assert again.outcomes.get("already_present", 0) == 4
    assert _counts(conn) == before


def test_a_dry_run_writes_nothing_but_reports_everything(conn):
    before = _counts(conn)
    report = import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA,
                                dry_run=True)

    assert report.dry_run is True
    assert report.n_created == 3
    assert report.n_duplicate == 1
    assert report.n_near_flagged == 1
    assert report.n_skipped == 1
    assert _counts(conn) == before


def test_a_dry_run_leaves_the_real_import_unchanged(conn):
    """The dry run is what the Import page calls before the user commits, so
    running it first must not change what the real import then does."""
    import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA, dry_run=True)
    real = import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)
    assert real.n_created == 3
    assert conn.execute("SELECT COUNT(*) FROM motif_entry").fetchone()[0] == 3


# ── refusals, warnings and skips ─────────────────────────────────────────────

def test_the_held_out_file_is_refused_loudly(tmp_path):
    """`M4_aug_concat_fs1.mat` is held out on every route. An event binding to
    it refuses the import rather than importing four of five events quietly."""
    conn = _make_db(tmp_path, first_source_file=HELD_OUT_RECORDING_FILE)
    try:
        with pytest.raises(ValueError) as excinfo:
            import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)
        assert HELD_OUT_RECORDING_FILE in str(excinfo.value)
        assert conn.execute("SELECT COUNT(*) FROM motif_entry").fetchone()[0] == 0
    finally:
        conn.close()


def test_an_unknown_recording_is_warned_and_counted_not_crashed(conn):
    report = import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)
    assert report.skipped.get("unknown_recording") == 1
    assert any("999" in w for w in report.warnings)
    assert any(s["source_ref"] == "id004_r999_7000" and s["outcome"] == "skipped"
               for s in report.samples)


def test_the_control_corpus_is_excluded_by_name_and_by_default(conn):
    """The 1 Hz control corpus is the same organism recorded twice; importing
    it double-counts. Named and overridable, not hard-coded — the fixture's ev3
    carries `corpus = reishi_1hz` so both halves are testable."""
    assert DEFAULT_EXCLUDED_CORPORA == ("reishi_1hz",)
    report = import_event_store(conn, STORE)
    assert report.skipped.get("excluded_corpus") == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM motif_member WHERE recording_id = 2"
    ).fetchone()[0] == 0


# ── tags (§3.4) ──────────────────────────────────────────────────────────────

def test_species_corpus_morphology_and_framing_become_tags(conn):
    import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)
    entry = conn.execute(
        "SELECT id FROM motif_entry WHERE source_ref = 'id001_r1_1000'"
    ).fetchone()
    tags = V.get_motif_entry_tags(conn, entry["id"])
    # Every label of every occurrence lands on the shape, because tags attach to
    # `motif_entry` and there is no `motif_member_tags` table to hold a label
    # that belongs to one occurrence (LIBRARY_STORAGE.md §3.4).
    #
    # `id002_r2_2000` is this same waveform in another recording, in another
    # species, and its source row calls the morphology something else. So the
    # entry ends up carrying both of each. That is not a defect to tidy away:
    # a shape found in an oyster and in a reishi is exactly the cross-recording
    # recurrence the Library exists to show, and two source rows disagreeing
    # about a morphology is a finding PRD Part 2 reports in the real data.
    # Keeping only the label that happened to be imported first would delete it.
    assert sorted(tags["element"]) == ["stegasaurus", "trough"]
    assert sorted(tags["species"]) == ["oyster", "reishi"]
    assert sorted(tags["corpus"]) == ["oyster", "reishi_1hz"]
    assert sorted(tags["framing"]) == ["sliding", "span"]


def test_an_existing_vocabulary_row_is_reused_and_the_typo_normalised(conn):
    """`sharkfin` and `trough` already exist in the real `tag_vocabulary`, and
    the catalogue's `Stegasauras` is the vocabulary's `stegasaurus`. Neither
    may produce a second row.

    The row is seeded here rather than assumed: `init_db()` creates
    `tag_vocabulary` empty, and the 28 rows this assertion was written against
    live only in `DATA/db/annotations.sqlite`, which no test may read."""
    conn.execute(
        "INSERT INTO tag_vocabulary (category, value) VALUES ('element', 'trough')")
    before = conn.execute(
        "SELECT id FROM tag_vocabulary WHERE category = 'element' AND value = 'trough'"
    ).fetchone()["id"]
    report = import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)
    after = conn.execute(
        "SELECT id FROM tag_vocabulary WHERE category = 'element' AND value = 'trough'"
    ).fetchone()["id"]
    assert after == before
    assert "element=trough" in report.tags_reused

    assert conn.execute(
        "SELECT COUNT(*) FROM tag_vocabulary WHERE value = 'Stegasauras'"
    ).fetchone()[0] == 0

    # `id002_r2_2000` carries the typo, and by the fixture's design it is ev1's
    # waveform exactly in another recording — so it resolves onto ev1's entry as
    # a second member and never gets an entry of its own. Its tag therefore
    # lands on that entry, which is the behaviour worth pinning: a tag follows
    # the shape, and two occurrences of one shape do not become two entries just
    # because their source rows spell a morphology differently.
    entry = conn.execute(
        "SELECT id FROM motif_entry WHERE source_ref = 'id001_r1_1000'"
    ).fetchone()
    assert "stegasaurus" in V.get_motif_entry_tags(conn, entry["id"])["element"]
    assert conn.execute(
        "SELECT COUNT(*) FROM motif_member WHERE entry_id = ?", (entry["id"],)
    ).fetchone()[0] == 2


def test_a_new_vocabulary_value_is_created_and_reported(conn):
    report = import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)
    assert "species=oyster" in report.tags_created
    assert conn.execute(
        "SELECT COUNT(*) FROM tag_vocabulary WHERE category = 'species'"
    ).fetchone()[0] >= 1


# ── the progress hook the bridge drives a job with ───────────────────────────

def test_progress_is_called_once_per_event_with_a_total(conn):
    seen = []
    import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA,
                       progress=lambda done, total, message: seen.append(
                           (done, total, message)))
    assert [d for d, _, _ in seen] == [1, 2, 3, 4, 5]
    assert all(t == 5 for _, t, _ in seen)
    assert all(isinstance(m, str) and m for _, _, m in seen)


# ── what the Import page reads off the report ───────────────────────────────

def test_an_occurrence_already_described_counts_as_a_duplicate(conn):
    """`n_duplicate`'s own docstring: events that resolved onto an existing
    shape, "whether they added a member **or found their occurrence already
    there**". A re-import is the second half, and it was not counted — so the
    Import page's "already describe a shape this library holds" check read 0
    on a bundle that was already held row for row."""
    import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)
    again = import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)

    assert again.outcomes.get("already_present") == 4
    assert again.n_already_present == 4
    assert again.n_created == 0
    assert again.n_duplicate == 4


def test_the_report_dict_states_the_outcomes_the_page_would_otherwise_add_up(conn):
    """The bridge draws the headline motif count and the re-import check off
    this dict. Every term is on it by name — `n_rows`, `n_created`,
    `n_already_present`, `n_duplicate`, `n_motifs` — so no reader has to
    reconstruct the arithmetic out of the `Counter`."""
    import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)
    payload = import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA,
                                 dry_run=True).as_dict()

    assert payload["n_rows"] == 5
    assert payload["n_created"] == 0
    assert payload["n_already_present"] == 4
    assert payload["n_duplicate"] == 4
    # the headline count: every row this bundle contributes a shape for
    assert payload["n_motifs"] == 4


def test_the_dry_run_reports_the_span_conflict_the_real_run_will_hit(conn):
    """§5.3's promise is that the dry run says what the import will say. A
    span already held by a different shape is refused by the real run and was
    previewed as `created`, so the page promised an entry the import then
    dropped."""
    import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)
    conn.execute("UPDATE motif_entry SET content_hash = ? WHERE source_ref = ?",
                 ("0" * 32, "id001_r1_1000"))
    conn.commit()
    before = _counts(conn)

    dry = import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA,
                             dry_run=True)
    assert dry.skipped.get("span_holds_another_shape") == 1
    assert any("cannot share one exemplar span" in w for w in dry.warnings)
    assert _counts(conn) == before

    real = import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)
    assert real.skipped.get("span_holds_another_shape") == 1
    assert dry.n_created == real.n_created


def test_a_near_duplicate_flag_names_both_spans(conn):
    """The flag judges a pair, so it has to carry both spans. The incumbent's
    stays `start_idx`/`end_idx` — the shape `find_near_duplicates` produced —
    and the candidate's is named as the candidate's."""
    report = import_event_store(conn, STORE, exclude_corpora=ALL_CORPORA)

    flag = report.flags[0]
    assert flag["source_ref"] == "id003_r1_1010"
    assert (flag["candidate_start_idx"], flag["candidate_end_idx"]) == (1010, 1110)
    assert (flag["start_idx"], flag["end_idx"]) == (1000, 1100)
    assert flag["onset_delta"] == abs(flag["candidate_start_idx"] - flag["start_idx"])

    detail = json.loads(conn.execute(
        "SELECT detail_json FROM audit_log WHERE kind = 'library_near_duplicate'"
    ).fetchone()[0])
    assert detail["start_idx"] == 1000 and detail["candidate_start_idx"] == 1010
