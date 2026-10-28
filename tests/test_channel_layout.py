"""
test_channel_layout.py
======================
Cross-channel explorer S0 (`docs/prompts/changes/cross-channel-explorer.md`): ONE definition of a
channel's pack and position, read by the census (S1), the pack chips (S2) and Settings (S3).

In plain words: a recording's electrodes sit on separate mushroom packs, and a signal can only travel
through mycelium within a pack. M2's channel names carry the pack in their letter (CH3_A2 is on pack A).
Every other dataset is one "unassigned" pack until the researcher sets packs in Settings › Channels &
events, which also holds each electrode's position in millimetres. The keys use exactly the <rec> and
<ch> that page already uses for ground.<rec>.<ch>: the registry's directory stem and the channel's
display name.

Runnable standalone:  python tests/test_channel_layout.py
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

from Working import channel_layout as CL  # noqa: E402
from Working.database import queries as q  # noqa: E402
from Working.database.schema import init_db  # noqa: E402
from Working.discovery.channels import channel_name  # noqa: E402
from Working.registration.core import list_registered  # noqa: E402
from Working.registration.settings import HELD_OUT_FILE, put_settings  # noqa: E402

M2 = "M2_aug_concat_fs1.mat"
CO = "CO_fs2.mat"
SC = "Schizophyllum commune.txt"


def _register(conn, root, source_file, n, stem):
    """Rows as registration writes them: one per channel, the npy under its directory stem."""
    ids = []
    for ch in range(n):
        ids.append(q.insert_recording(conn, source_file, ch, fs=1.0, n_samples=100, global_offset=0,
                                      npy_path=str(root / "channels" / stem / f"CH{ch}.npy")))
    return ids


@pytest.fixture()
def conn(tmp_path):
    db = tmp_path / "layout.sqlite"
    init_db(str(db))
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    _register(c, tmp_path, M2, 16, "M2_aug_concat_fs1")
    _register(c, tmp_path, CO, 4, "CO_fs2")
    _register(c, tmp_path, SC, 2, "Schizophyllum_commune")    # a directory stem that is not the file stem
    _register(c, tmp_path, HELD_OUT_FILE, 16, "M4_aug_concat_fs1")
    c.commit()
    yield c
    c.close()


def _by_name(layout):
    return {row["name"]: row for row in layout["channels"].values()}


def test_the_keys_are_the_pages_rec_and_ch():
    # the page's own format: fixtures/settings.ts `groundKey = (rec, ch) => ground.${rec}.${ch}`,
    # e.g. gainKey('M2_aug_concat_fs1', 'CH6_B1')
    assert CL.pack_key("M2_aug_concat_fs1", "CH6_B1") == "pack.M2_aug_concat_fs1.CH6_B1"
    assert CL.x_key("M2_aug_concat_fs1", "CH6_B1") == "x_mm.M2_aug_concat_fs1.CH6_B1"
    assert CL.y_key("M2_aug_concat_fs1", "CH6_B1") == "y_mm.M2_aug_concat_fs1.CH6_B1"
    assert CL.PAGE == "channels-events"


def test_rec_is_the_registrys_directory_stem_and_ch_the_display_name(conn):
    for sf in (M2, CO, SC):
        layout = CL.channel_layout(conn, sf)
        entry = next(r for r in list_registered(conn, "recording") if r["source_file"] == sf)
        assert layout["rec"] == entry["name"]
        assert [row["name"] for row in layout["channels"].values()] == [
            channel_name(sf, c["channel"], entry["n_channels"]) for c in entry["channels"]]
    assert CL.channel_layout(conn, SC)["rec"] == "Schizophyllum_commune"


def test_m2_names_give_the_pack_letter(conn):
    layout = CL.channel_layout(conn, M2)
    rows = _by_name(layout)
    assert rows["CH3_A2"]["pack"] == "A" and rows["CH13_D1"]["pack"] == "D"
    assert {row["pack_from"] for row in rows.values()} == {"name"}
    assert layout["packs"] == ["A", "B", "C", "D"]
    assert layout["layout_known"] is True and layout["positions_known"] is False
    assert layout["note"] is None


def test_an_unassigned_recording_is_one_pack_and_says_layout_unknown(conn):
    layout = CL.channel_layout(conn, CO)
    assert {row["pack"] for row in layout["channels"].values()} == {CL.UNASSIGNED}
    assert {row["pack_from"] for row in layout["channels"].values()} == {"unassigned"}
    assert layout["layout_known"] is False
    assert layout["note"] == "packs not set — layout unknown"
    a, b = list(layout["channels"])[:2]
    assert CL.same_pack(layout, a, b) is True            # propagation stays allowed on an unknown layout


def test_a_settings_pack_wins_over_the_letter(conn):
    put_settings(conn, CL.PAGE, {CL.pack_key("M2_aug_concat_fs1", "CH3_A2"): "B"})
    layout = CL.channel_layout(conn, M2)
    rows = _by_name(layout)
    assert rows["CH3_A2"]["pack"] == "B" and rows["CH3_A2"]["pack_from"] == "settings"
    ids = {row["name"]: rid for rid, row in layout["channels"].items()}
    assert CL.same_pack(layout, ids["CH3_A2"], ids["CH5_B1"]) is True
    assert CL.same_pack(layout, ids["CH3_A2"], ids["CH1_A1"]) is False


def test_positions_round_trip(conn):
    put_settings(conn, CL.PAGE, {k: v for i, ch in enumerate(["CH1", "CH2", "CH3", "CH4"])
                                 for k, v in ((CL.x_key("CO_fs2", ch), 10.0 * i), (CL.y_key("CO_fs2", ch), 2.5))})
    layout = CL.channel_layout(conn, CO)
    rows = _by_name(layout)
    assert (rows["CH3"]["x_mm"], rows["CH3"]["y_mm"]) == (20.0, 2.5)
    assert layout["positions_known"] is True
    assert layout["layout_known"] is False               # positions alone do not set packs


def test_an_unreadable_position_fails_loudly(conn):
    put_settings(conn, CL.PAGE, {CL.x_key("CO_fs2", "CH1"): "left"})
    with pytest.raises(ValueError, match="x_mm.CO_fs2.CH1"):
        CL.channel_layout(conn, CO)


def test_an_unregistered_file_is_refused(conn):
    with pytest.raises(LookupError):
        CL.channel_layout(conn, "nope.mat")


def test_the_held_out_file_is_refused_while_the_lock_is_on(conn):
    with pytest.raises(PermissionError):
        CL.channel_layout(conn, HELD_OUT_FILE)


def test_same_pack_reads_a_layout_after_a_json_round_trip(conn):
    layout = json.loads(json.dumps(CL.channel_layout(conn, M2)))
    ids = {row["name"]: rid for rid, row in layout["channels"].items()}
    assert CL.same_pack(layout, ids["CH1_A1"], ids["CH4_A2"]) is True
    assert CL.same_pack(layout, int(ids["CH1_A1"]), int(ids["CH5_B1"])) is False


# ── the fix round (critic, 2026-10-28) ───────────────────────────────────────

def test_a_partly_set_layout_leaves_mixed_pairs_unknown(conn):
    # one channel placed, three not: whether the placed one shares a pack with the others is UNKNOWN, never "no"
    # (a quiet False would turn real propagation into shared driver). Two unplaced channels stay one pack (D10).
    put_settings(conn, CL.PAGE, {CL.pack_key("CO_fs2", "CH1"): "east"})
    layout = CL.channel_layout(conn, CO)
    ids = {row["name"]: rid for rid, row in layout["channels"].items()}
    assert CL.same_pack(layout, ids["CH1"], ids["CH2"]) is None
    assert CL.same_pack(layout, ids["CH2"], ids["CH3"]) is True
    assert layout["layout_known"] is False and layout["note"] == CL.LAYOUT_UNKNOWN


def test_pack_labels_are_upper_cased_and_the_reserved_word_refused(conn):
    put_settings(conn, CL.PAGE, {CL.pack_key("M2_aug_concat_fs1", "CH3_A2"): " b "})
    layout = CL.channel_layout(conn, M2)
    ids = {row["name"]: rid for rid, row in layout["channels"].items()}
    assert layout["channels"][ids["CH3_A2"]]["pack"] == "B"
    assert CL.same_pack(layout, ids["CH3_A2"], ids["CH5_B1"]) is True      # "b" is M2's pack B
    put_settings(conn, CL.PAGE, {CL.pack_key("M2_aug_concat_fs1", "CH3_A2"): "Unassigned"})
    with pytest.raises(ValueError, match="pack.M2_aug_concat_fs1.CH3_A2"):
        CL.channel_layout(conn, M2)


def test_a_boolean_position_is_refused(conn):
    put_settings(conn, CL.PAGE, {CL.x_key("CO_fs2", "CH1"): True})
    with pytest.raises(ValueError, match="x_mm.CO_fs2.CH1"):
        CL.channel_layout(conn, CO)


def test_keys_under_an_unknown_channel_are_listed_not_ignored(conn):
    put_settings(conn, CL.PAGE, {"pack.CO_fs2.CH9": "A", "x_mm.CO_fs2.CH4_OLD": 1.0, "pack.CO_fs2.CH2": "A"})
    layout = CL.channel_layout(conn, CO)
    assert layout["orphan_keys"] == ["pack.CO_fs2.CH9", "x_mm.CO_fs2.CH4_OLD"]
    assert CL.channel_layout(conn, M2)["orphan_keys"] == []                 # another recording's keys are not its own


def test_a_prefetched_registry_gives_the_same_layout(conn):
    reg = list_registered(conn, "recording")
    assert CL.channel_layout(conn, CO, registered=reg) == CL.channel_layout(conn, CO)


def test_the_layout_carries_the_settings_last_save(conn):
    from Working.registration.settings import settings_meta
    assert CL.channel_layout(conn, CO)["settings_updated_at"] is None
    put_settings(conn, CL.PAGE, {CL.pack_key("CO_fs2", "CH2"): "A"})
    layout = CL.channel_layout(conn, CO)
    assert layout["settings_updated_at"] is not None
    assert layout["settings_updated_at"] == settings_meta(conn, CL.PAGE)["updated_at"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
