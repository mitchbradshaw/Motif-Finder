"""
test_library_view_filter.py
===========================
fixup-AE: the Library's noise floor is a VIEW filter (Q21), with two more
filters beside it (Q22), all decided in `docs/prompts/fixup/QUESTIONS.md`.

What these tests hold the filter to:

* **the floor is the dataset's** (Settings › Datasets › noise floor, the key
  `meta.<stem>.noise_floor`), and **0.1 mV where it is empty** (Q-X2.5);
* **what is compared with it is the detector's own `drop_depth_mv`**, then
  `interrogation.event_shape`'s depth where the detector gave none; a member
  with neither is *unmeasured* — shown, counted, never hidden and never passed
  as above the floor;
* **nothing is deleted**: the filter returns which members to show and how many
  it hid, per import store and per dataset; the rows are untouched;
* a family whose every member is sub-floor is counted as hidden;
* `fall_duration_s` is a range filter and `is_pure` a toggle; a member the
  filter cannot judge is shown and counted, never silently dropped;
* `scale_band` is NOT a filter: it rides along as provenance with its duration
  range, the same label `passes6._band_label` writes;
* `features.RULE_VERSION` names `rise_time_frac`, the detector's `is_pure` and
  `scale_band` are carried, and the backfill fills a measure a stored row lacks
  (`rise_time_s`) instead of skipping the whole row (E §8.4).

Runnable standalone:  python tests/test_library_view_filter.py
"""

import datetime
import os
import sqlite3
import sys
import tempfile

import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.library import features as F  # noqa: E402
from Working.registration.settings import put_settings  # noqa: E402

SEED_REL = "DATA/library_seed/drop_motifs5/motifs"
SEED = os.path.join(PROJECT_ROOT, *SEED_REL.split("/"))
EVENT = "id001_r1_1213252"
needs_seed = pytest.mark.skipif(not os.path.isfile(os.path.join(SEED, "events.csv")),
                                reason="the tracked seed store is not on this machine")

S10 = "Plots/drop_motifs10/motifs"
S5 = "DATA/library_seed/drop_motifs5/motifs"

#: member id -> (recording, store, detector features, event-shape features)
MEMBERS = {
    1: ("A", S10, {"drop_depth_mv": 0.05, "fall_duration_s": 2.0, "is_pure": 1.0}, {"event_amplitude_mv": 0.4}),
    2: ("A", S10, {"drop_depth_mv": 0.30, "fall_duration_s": 20.0, "is_pure": 0.0, "scale_band": 1.0,
                   "scale_band_lo_s": 4.0, "scale_band_hi_s": 13.0}, {}),
    3: ("A", S10, {}, {"event_amplitude_mv": 0.08}),
    4: ("A", S5, {}, {}),
    5: ("B", S5, {"drop_depth_mv": 0.30, "fall_duration_s": 50.0, "is_pure": 1.0}, {}),
    6: ("B", S5, {"drop_depth_mv": 2.00, "fall_duration_s": 100.0, "is_pure": 1.0}, {}),
}
FAMILIES = {"F-1": [1, 3], "F-2": [2, 4], "F-3": [5, 6]}


@pytest.fixture
def conn():
    d = tempfile.mkdtemp(prefix="view_filter_")
    c = init_db(os.path.join(d, "t.sqlite"))
    c.row_factory = sqlite3.Row
    recs = {"A": q.insert_recording(c, "A.mat", 0, 1.0, 10_000, 0, "DATA/derived/channels/A/CH0.npy"),
            "B": q.insert_recording(c, "B.mat", 0, 10.0, 10_000, 0, "DATA/derived/channels/B/CH0.npy")}
    now = datetime.datetime.now().isoformat()
    rows = []
    for mid, (rec, store, det, shape) in MEMBERS.items():
        digest = f"{mid:032d}"
        c.execute("INSERT INTO motif_entry (id, recording_id, start_idx, end_idx, content_hash, source_kind, "
                  "source_store, source_ref, fs, created_at) VALUES (?, ?, ?, ?, ?, 'event_store', ?, ?, 1.0, ?)",
                  (mid, recs[rec], 10 * mid, 10 * mid + 5, digest, store, f"ev{mid}", now))
        c.execute("INSERT INTO motif_member (id, entry_id, recording_id, start_idx, end_idx, content_hash) "
                  "VALUES (?, ?, ?, ?, ?, ?)", (mid, mid, recs[rec], 10 * mid, 10 * mid + 5, digest))
        rows.append({"content_hash": digest, "fs": 1.0, "measures": shape, "detector": det})
    F.write_features(c, rows)
    c.execute("UPDATE recordings SET units = 'V'")       # the store's "mV" is samples x 1000: mV for a volts file
    put_settings(c, "datasets", {"meta.B.noise_floor": "0.5"})
    c.commit()
    yield c
    c.close()


def _members(conn):
    return [dict(r) for r in conn.execute(
        "SELECT mm.id AS member_id, mm.entry_id, mm.recording_id FROM motif_member mm ORDER BY mm.id")]


# ── the floor ───────────────────────────────────────────────────────────────

def test_the_floor_is_the_datasets_setting_and_0_1_mV_where_it_is_empty(conn):
    from Working.library import view_filter as VF
    floors = VF.dataset_floors(conn)
    assert floors["A.mat"]["floor_mv"] == pytest.approx(0.1)
    assert floors["A.mat"]["set"] is False
    assert floors["B.mat"]["floor_mv"] == pytest.approx(0.5)
    assert floors["B.mat"]["set"] is True


def test_the_detector_depth_is_compared_first_then_event_shape_and_neither_is_unmeasured(conn):
    from Working.library import view_filter as VF
    m = VF.member_measures(conn, _members(conn))
    assert (m[1]["status"], m[1]["depth_source"]) == ("sub_floor", "detector")      # 0.05 < 0.1, not the 0.4
    assert (m[2]["status"], m[2]["depth_source"]) == ("above", "detector")
    assert (m[3]["status"], m[3]["depth_source"]) == ("sub_floor", "interrogation.event_shape")
    assert (m[4]["status"], m[4]["depth_source"]) == ("unmeasured", None)
    assert m[5]["status"] == "sub_floor" and m[5]["floor_mv"] == pytest.approx(0.5)  # B's own floor
    assert m[6]["status"] == "above"


def test_the_depth_is_read_in_the_recordings_declared_unit(conn):
    from Working.library import view_filter as VF
    conn.execute("UPDATE recordings SET units = 'mV' WHERE source_file = 'B.mat'")
    m = VF.member_measures(conn, _members(conn))
    assert m[6]["depth_mv"] == pytest.approx(0.002), "a millivolt file's samples x 1000 is not mV"
    conn.execute("UPDATE recordings SET units = NULL WHERE source_file = 'B.mat'")
    m = VF.member_measures(conn, _members(conn))
    assert m[6]["status"] == "unmeasured" and "unit undeclared" in m[6]["why"]


def test_the_default_view_hides_sub_floor_members_and_says_how_many_by_store_and_dataset(conn):
    from Working.library import view_filter as VF
    out = VF.filter_members(conn, _members(conn), VF.ViewFilter(), families=FAMILIES)
    assert out["kept"] == {2, 4, 6}
    r = out["report"]
    assert r["floor"]["on"] is True
    assert r["floor"]["sub_floor"] == 3 and r["unmeasured"] == 1
    assert r["floor"]["by_store"][S10] == {"n": 3, "sub_floor": 2, "unmeasured": 0}
    assert r["floor"]["by_store"][S5] == {"n": 3, "sub_floor": 1, "unmeasured": 1}
    assert r["floor"]["by_dataset"]["A.mat"]["sub_floor"] == 2
    assert r["floor"]["by_dataset"]["B.mat"]["sub_floor"] == 1
    # F-1 is all sub-floor: hidden and counted; F-2 keeps its unmeasured member
    assert r["families_all_sub_floor"] == ["F-1"]


def test_show_sub_floor_brings_every_member_back_and_still_counts_them(conn):
    from Working.library import view_filter as VF
    out = VF.filter_members(conn, _members(conn), VF.ViewFilter(floor=False), families=FAMILIES)
    assert out["kept"] == {1, 2, 3, 4, 5, 6}
    assert out["report"]["floor"]["on"] is False and out["report"]["floor"]["sub_floor"] == 3
    assert out["report"]["families_all_sub_floor"] == []


def test_nothing_is_deleted(conn):
    from Working.library import view_filter as VF
    before = conn.execute("SELECT COUNT(*) FROM motif_member").fetchone()[0]
    VF.filter_members(conn, _members(conn), VF.ViewFilter(), families=FAMILIES)
    assert conn.execute("SELECT COUNT(*) FROM motif_member").fetchone()[0] == before


# ── the two filters (Q22) ───────────────────────────────────────────────────

def test_fall_duration_is_a_range_and_a_member_without_one_is_shown_and_counted(conn):
    from Working.library import view_filter as VF
    out = VF.filter_members(conn, _members(conn), VF.ViewFilter(floor=False, fall_min_s=10, fall_max_s=300))
    assert out["kept"] == {2, 3, 4, 5, 6}                   # 1 falls in 2 s; 3 and 4 have no fall measured
    assert out["report"]["fall"]["hidden"] == 1 and out["report"]["fall"]["unmeasured"] == 2


def test_pure_only_hides_impure_windows_and_counts_the_unknown(conn):
    from Working.library import view_filter as VF
    out = VF.filter_members(conn, _members(conn), VF.ViewFilter(floor=False, pure_only=True))
    assert out["kept"] == {1, 3, 4, 5, 6}                   # 2 holds more than one fall
    assert out["report"]["pure"]["hidden"] == 1 and out["report"]["pure"]["unmeasured"] == 2


def test_the_filters_compose_and_the_rule_is_printed(conn):
    from Working.library import view_filter as VF
    v = VF.ViewFilter(fall_min_s=10, fall_max_s=300, pure_only=True)
    out = VF.filter_members(conn, _members(conn), v)
    assert out["kept"] == {4, 6}
    text = out["report"]["rule"]
    assert "noise floor" in text and "10" in text and "300" in text and "pure" in text


def test_scale_band_is_provenance_with_its_duration_range_not_a_filter(conn):
    from Working.library import view_filter as VF
    m = VF.member_measures(conn, _members(conn))
    assert m[2]["scale_band"] == 1 and m[2]["scale_band_label"] == "4-13 s"
    assert m[1]["scale_band"] is None and m[1]["scale_band_label"] is None
    assert not hasattr(VF.ViewFilter(), "scale_band")


def test_the_view_reads_from_query_strings():
    from Working.library import view_filter as VF
    v = VF.ViewFilter.from_query(floor="0", fall_min="10", fall_max="", pure="1")
    assert (v.floor, v.fall_min_s, v.fall_max_s, v.pure_only) == (False, 10.0, None, True)
    assert VF.ViewFilter.from_query() == VF.ViewFilter()       # on by default, nothing else


# ── features.py: RULE_VERSION, is_pure / scale_band, the backfill of a missing measure ──

def test_rule_version_names_rise_time_frac():
    assert "rise_time_frac=" in F.RULE_VERSION


def test_the_detector_measures_carry_is_pure_and_scale_band():
    got = F.detector_measures({"drop_depth_mv": "0.3", "is_pure": "0", "scale_band": "2"})
    assert got["is_pure"] == 0.0 and got["scale_band"] == 2.0


def test_scale_band_ranges_are_per_span_the_way_the_detector_labelled_them():
    events = [{"span_key": "id001", "scale_band": "1", "fall_duration_s": "4"},
              {"span_key": "id001", "scale_band": "1", "fall_duration_s": "13"},
              {"span_key": "id021", "scale_band": "1", "fall_duration_s": "174"},
              {"span_key": "id021", "scale_band": "0", "fall_duration_s": "2"}]
    r = F.scale_band_ranges(events)
    assert r[("id001", 1)] == (4.0, 13.0) and r[("id021", 1)] == (174.0, 174.0)
    assert F.scale_band_label(4.0, 13.0) == "4-13 s" and F.scale_band_label(0.25, 0.3) == "0.25 s"


@needs_seed
def test_the_backfill_fills_a_measure_a_stored_row_lacks(tmp_path):
    from Working.Detection.drop_motifs import store as S
    from Working.library.identity import content_hash
    c = init_db(str(tmp_path / "t.sqlite"))
    digest = content_hash(S.load_snippets(SEED)[EVENT]["detrended_mv"])
    rid = q.insert_recording(c, "M2_aug_concat_fs1.mat", 0, 1.0, 10, 0, "nowhere.npy")
    c.execute("INSERT INTO motif_entry (recording_id, start_idx, end_idx, content_hash, source_kind, source_store, "
              "source_ref, fs, created_at) VALUES (?, 1, 9, ?, 'event_store', ?, ?, 1.0, ?)",
              (rid, digest, SEED_REL, EVENT, datetime.datetime.now().isoformat()))
    c.commit()
    F.backfill_library(c, repo_root=PROJECT_ROOT)
    c.execute("DELETE FROM motif_features WHERE feature IN ('rise_time_s', 'is_pure')")
    c.commit()
    report = F.backfill_library(c, repo_root=PROJECT_ROOT)
    assert report["measured"] == 1, "a row missing a current measure is completed, not skipped"
    got = F.read_features(c, [digest])[digest]
    assert "rise_time_s" in got and "detector_is_pure" in got
    again = F.backfill_library(c, repo_root=PROJECT_ROOT)
    assert again["measured"] == 0 and again["already_present"] == 1
    c.close()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
