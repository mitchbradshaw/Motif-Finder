"""
test_discovery_seeded_search.py
================================
Spec §7.6 — seeded search on real recordings, tested on a synthetic channel
with a planted motif so the recall of the plant is a fact, not an impression.

What this pins, and why each one is a trap the shell could walk into:

* **The matches are the block's own.** `Adapters.detection_seed_matches.
  match_exemplar` is imported, not reimplemented, so the candidates the page
  shows before the run and the detections the run writes come from one
  function with one trivial-match guard.
* **The distance profile is computed, not invented.** `detection.seed_matches`
  returns only the k kept matches; there is no per-position profile in it and
  no matrix profile behind it (`stumpy.match` is a direct search). §7.6's
  profile track comes from `stumpy.mass`, and the module says so.
* **The null is drawn, and it is reproducible.** `preprocessing.surrogate` has
  no `draws` parameter — one call is one realisation with one `seed` — so a
  null *distribution* is N realisations at N seeds, and the same seed must
  give the same distribution twice.
* **A null method the block does not implement is refused out loud.** Settings
  › Nulls names *circular shift of the channel*; the block implements
  `phase_randomize` and `block_shuffle` only. Falling back silently would make
  the page claim one null while computing another — an unfalsifiable × null.
* **The cut re-thresholds without recomputing.** Dragging the line is a filter
  over distances already in hand.
* **Matrix-profile reuse is by content, not by name.** A registered profile is
  reused only when the recording, the window and the span all match.
"""

import json
import os
import shutil
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(PROJECT_ROOT, "Working")) \
        and os.path.dirname(PROJECT_ROOT) != PROJECT_ROOT:
    PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Working.config import HELD_OUT_RECORDING_FILE
from Working.database import queries as q
from Working.database.schema import init_db
from Working.discovery import seeded_search as ss

M = 60
PLANTS = (300, 900, 1500)


def _planted(seed=0, n=2000):
    """Noise with the same dip planted at three places."""
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n) * 0.05
    shape = -np.sin(np.linspace(0.0, np.pi, M))
    for p in PLANTS:
        x[p:p + M] += shape
    return x


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="discovery_seed_")
    db_path = os.path.join(tmpdir, "test.sqlite")
    conn = init_db(db_path)
    for ch in (0, 1):
        npy = os.path.join(tmpdir, f"CH{ch}.npy")
        np.save(npy, _planted(seed=ch))
        q.insert_recording(conn, "fake.mat", ch, 1.0, 2000, 0, npy)
    held = os.path.join(tmpdir, "held.npy")
    np.save(held, _planted(seed=7))
    q.insert_recording(conn, HELD_OUT_RECORDING_FILE, 0, 1.0, 2000, 0, held)
    conn.close()
    yield db_path, tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


def _ids(db_path, source_file="fake.mat"):
    conn = init_db(db_path)
    try:
        return [r["id"] for r in q.list_recordings(conn, source_file)]
    finally:
        conn.close()


# ── the matches ─────────────────────────────────────────────────────────────

def test_the_search_recovers_every_plant():
    x = _planted()
    seed_x = x[PLANTS[0]:PLANTS[0] + M]
    found = ss.candidates(x, seed_x, k=10)
    near = {p for p in PLANTS for c in found if abs(c["index"] - p) <= 3}
    assert near == set(PLANTS), f"plants missed: {set(PLANTS) - near}"
    assert found[0]["distance"] == pytest.approx(0.0, abs=1e-6), "the seed matches itself first"
    assert [c["distance"] for c in found] == sorted(c["distance"] for c in found)


def test_the_plants_are_far_closer_than_anything_else():
    x = _planted()
    found = ss.candidates(x, x[PLANTS[0]:PLANTS[0] + M], k=20)
    plant_d = [c["distance"] for c in found if any(abs(c["index"] - p) <= 3 for p in PLANTS)]
    other_d = [c["distance"] for c in found if not any(abs(c["index"] - p) <= 3 for p in PLANTS)]
    assert len(plant_d) == 3
    if other_d:
        assert max(plant_d) < min(other_d)


def test_a_distance_cut_keeps_only_the_plants():
    x = _planted()
    found = ss.candidates(x, x[PLANTS[0]:PLANTS[0] + M], k=100, max_distance=2.0)
    assert {c["index"] for c in found} == set(PLANTS) or all(
        any(abs(c["index"] - p) <= 3 for p in PLANTS) for c in found)


def test_an_exemplar_longer_than_the_span_is_refused_with_the_numbers():
    with pytest.raises(ValueError, match="longer than"):
        ss.candidates(np.zeros(50), np.zeros(60), k=5)


# ── the distance profile (what §7.6's profile track draws) ──────────────────

def test_the_distance_profile_has_one_value_per_position_and_dips_at_the_plants():
    x = _planted()
    prof = ss.distance_profile(x, x[PLANTS[0]:PLANTS[0] + M])
    assert len(prof) == len(x) - M + 1
    assert int(np.argmin(prof)) == PLANTS[0]
    for p in PLANTS:
        assert prof[p] < np.median(prof) / 2


def test_the_profile_over_a_view_window_is_the_same_values_as_the_whole():
    """The page draws one channel and one zoomed view at a time; the view must
    be a slice of the same quantity, not a separately-normalised one."""
    x = _planted()
    seed_x = x[PLANTS[1]:PLANTS[1] + M]
    whole = ss.distance_profile(x, seed_x)
    view = ss.distance_profile(x, seed_x, view=(800, 1100))
    assert view["t0"] == 800
    assert np.allclose(view["distance"], whole[800:1100 - M + 1], atol=1e-4)
    assert len(view["signal"]) == 300


# ── the null ────────────────────────────────────────────────────────────────

def test_the_null_is_reproducible_from_its_seed():
    x = _planted()
    seed_x = x[PLANTS[0]:PLANTS[0] + M]
    a = ss.null_distances(x, seed_x, draws=5, seed=11)
    b = ss.null_distances(x, seed_x, draws=5, seed=11)
    c = ss.null_distances(x, seed_x, draws=5, seed=12)
    assert a["distances"] == b["distances"]
    assert a["distances"] != c["distances"]
    assert a["draws"] == 5
    assert a["method"] == "phase_randomize"


def test_the_null_is_far_from_the_seed_where_the_plants_are_not():
    x = _planted()
    seed_x = x[PLANTS[0]:PLANTS[0] + M]
    plants = [c["distance"] for c in ss.candidates(x, seed_x, k=3)]
    null = ss.null_distances(x, seed_x, draws=5, seed=0, k=3)["distances"]
    assert min(null) > max(plants)


def test_the_null_reports_progress_per_draw():
    x = _planted()
    seen = []
    ss.null_distances(x, x[300:360], draws=4, seed=0, on_progress=lambda i, n: seen.append((i, n)))
    assert seen == [(1, 4), (2, 4), (3, 4), (4, 4)]


def test_block_shuffle_is_the_other_method_the_block_implements():
    x = _planted()
    out = ss.null_distances(x, x[300:360], draws=2, seed=0, method="block_shuffle")
    assert out["method"] == "block_shuffle"
    assert len(out["distances"]) > 0


# ── a null the block cannot compute is refused, never substituted ───────────

def test_a_settings_null_method_the_block_implements_resolves():
    r = ss.resolve_null("phase randomisation")
    assert r["supported"] is True and r["method"] == "phase_randomize"
    assert ss.resolve_null("block shuffle")["method"] == "block_shuffle"
    assert ss.resolve_null(None)["method"] == "phase_randomize"


def test_circular_shift_is_refused_and_the_reason_names_the_block():
    r = ss.resolve_null("circular shift of the channel")
    assert r["supported"] is False
    assert r["method"] is None
    assert "preprocessing.surrogate" in r["reason"]
    assert "phase_randomize" in r["reason"] and "block_shuffle" in r["reason"]
    assert "circular shift of the channel" in r["reason"]


def test_an_unsupported_method_raises_rather_than_falling_back():
    with pytest.raises(ValueError, match="preprocessing.surrogate"):
        ss.null_distances(_planted(), _planted()[300:360], draws=2, seed=0, method="circular shift")


# ── the cut ─────────────────────────────────────────────────────────────────

def test_the_cut_rethresholds_the_distances_already_in_hand():
    dists = [0.1, 0.4, 1.2, 3.0, 5.0]
    null = {"distances": [2.0, 2.5, 4.0, 6.0], "draws": 2}
    at_1_5 = ss.cut_counts(dists, null, 1.5)
    assert at_1_5["kept"] == 3
    assert at_1_5["null_gives"] == 0.0
    # a null that gives nothing is the strongest result there is, and the row
    # says so rather than leaving a bare None that reads as "not computed"
    assert at_1_5["x_null"] is None
    assert at_1_5["draws"] == 2
    assert "gives nothing" in at_1_5["note"]
    assert ss.cut_counts(dists, null, 3.0)["kept"] == 4
    assert ss.cut_counts(dists, null, 3.0)["null_gives"] == pytest.approx(1.0)
    assert ss.cut_counts(dists, null, 3.0)["x_null"] == pytest.approx(4.0)
    assert ss.cut_counts(dists, null, 10.0)["kept"] == 5


def test_the_kept_count_is_monotone_in_the_cut():
    dists = list(np.linspace(0, 10, 50))
    null = {"distances": list(np.linspace(2, 12, 40)), "draws": 4}
    kept = [ss.cut_counts(dists, null, c)["kept"] for c in np.linspace(0, 12, 25)]
    assert kept == sorted(kept)


def test_the_recommended_cut_sits_below_the_nulls_own_distances():
    x = _planted()
    seed_x = x[PLANTS[0]:PLANTS[0] + M]
    dists = [c["distance"] for c in ss.candidates(x, seed_x, k=50)]
    null = ss.null_distances(x, seed_x, draws=5, seed=0, k=50)
    cut = ss.recommended_cut(dists, null)
    assert cut is not None
    assert cut < min(null["distances"])
    assert ss.cut_counts(dists, null, cut)["kept"] >= 3


def test_the_recommended_cut_is_none_when_the_null_is_everywhere():
    assert ss.recommended_cut([1.0, 2.0], {"distances": [0.1, 0.2], "draws": 1}) is None


# ── the seed itself ─────────────────────────────────────────────────────────

def test_a_seed_is_taken_by_content_and_carries_its_hash(db):
    db_path, _ = db
    conn = init_db(db_path)
    try:
        seed = ss.seed_from_content(conn, "fake.mat", 0, 300, 360)
        assert seed["samples"] == 60
        assert seed["length_s"] == pytest.approx(60.0)
        assert seed["fs"] == 1.0
        assert seed["recording_id"] == _ids(db_path)[0]
        assert len(seed["hash"]) >= 8
        assert seed["binding"] == {"source_kind": "library_exemplar", "entry_id": 0,
                                   "source_file": "fake.mat", "channel": 0,
                                   "start_idx": 300, "end_idx": 360}
        # entry_id 0 = taken off a channel, not promoted from the library; the
        # binding still resolves by content (motif_entry is empty on this machine)
        again = ss.seed_from_content(conn, "fake.mat", 0, 300, 360)
        assert again["hash"] == seed["hash"]
        elsewhere = ss.seed_from_content(conn, "fake.mat", 0, 900, 960)
        assert elsewhere["hash"] != seed["hash"]
    finally:
        conn.close()


def test_a_seed_on_the_held_out_recording_is_refused(db):
    db_path, _ = db
    conn = init_db(db_path)
    try:
        with pytest.raises(PermissionError, match=HELD_OUT_RECORDING_FILE):
            ss.seed_from_content(conn, HELD_OUT_RECORDING_FILE, 0, 300, 360)
    finally:
        conn.close()


def test_a_seed_outside_the_recording_is_refused_with_the_numbers(db):
    db_path, _ = db
    conn = init_db(db_path)
    try:
        with pytest.raises(ValueError, match="2000"):
            ss.seed_from_content(conn, "fake.mat", 0, 1980, 2100)
    finally:
        conn.close()


def test_the_exemplar_signal_is_the_samples_on_disk(db):
    db_path, tmpdir = db
    conn = init_db(db_path)
    try:
        seed = ss.seed_from_content(conn, "fake.mat", 0, 300, 360)
        sig = ss.exemplar_signal(conn, seed)
        assert len(sig.x) == 60
        assert np.allclose(sig.x, np.load(os.path.join(tmpdir, "CH0.npy"))[300:360])
        assert sig.fs == 1.0
    finally:
        conn.close()


def test_the_recipe_binds_the_exemplar_as_a_library_exemplar_and_validates(db):
    db_path, _ = db
    conn = init_db(db_path)
    try:
        seed = ss.seed_from_content(conn, "fake.mat", 0, 300, 360)
        ids = _ids(db_path)
        recipe = ss.seed_recipe(seed, ids, span=(0, 2000), k=25, max_distance=2.0)
    finally:
        conn.close()
    step = recipe["steps"][0]
    assert step["stage"] == "detection" and step["algorithm"] == "seed_matches"
    assert step["params"]["k"] == 25 and step["params"]["max_distance"] == 2.0
    assert step["side_inputs"]["exemplar"]["source_kind"] == "library_exemplar"
    assert step["side_inputs"]["exemplar"]["start_idx"] == 300
    assert recipe["fan_out"] == {"kind": "channels", "targets": ids}
    assert recipe["span"] == [0, 2000]


def test_the_window_is_locked_to_the_exemplars_native_length(db):
    """§7.6: 'window at the exemplar's **native length** (locked)'."""
    db_path, _ = db
    conn = init_db(db_path)
    try:
        seed = ss.seed_from_content(conn, "fake.mat", 0, 300, 360)
        params = ss.recommended_params(seed)
        assert params["windowSamples"] == 60
        assert params["algorithm"] == "mass"
        assert params["exclusionS"] == pytest.approx(30.0)      # m/2 at fs = 1
        assert params["windowLocked"] is True
    finally:
        conn.close()


# ── matrix-profile reuse, by content ────────────────────────────────────────

def _register_profile(conn, path, recording_id, channel, m, span, fs=1.0):
    conn.execute(
        "INSERT INTO registered_artifacts (kind, path, name, recording_id, channel, span_start, span_end, fs, "
        "params_json, producer, created_at, active) VALUES ('matrix_profile', ?, ?, ?, ?, ?, ?, ?, ?, 'test', "
        "'2026-09-21T00:00:00', 1)",
        (path, os.path.basename(path), recording_id, channel, span[0], span[1], fs, json.dumps({"m": m})))
    conn.commit()


def test_a_registered_profile_is_reused_when_recording_window_and_span_match(db):
    db_path, tmpdir = db
    conn = init_db(db_path)
    try:
        rid = _ids(db_path)[0]
        path = os.path.join(tmpdir, "mp_v2_fake_CH0_WIN1min.npz")
        np.savez(path, mp=np.zeros(2000 - 60 + 1, dtype=np.float32), m=60, fs=1.0,
                 n_samples=2000, source_file="fake.mat", channel=0)
        _register_profile(conn, path, rid, 0, 60, (0, 2000))
        hit = ss.find_reusable_profile(conn, rid, 60, span=(0, 2000))
        assert hit is not None
        assert hit["path"] == path
        assert hit["m"] == 60
        assert hit["reason"].startswith("reusing")
    finally:
        conn.close()


def test_a_mismatched_window_is_not_reused(db):
    db_path, tmpdir = db
    conn = init_db(db_path)
    try:
        rid = _ids(db_path)[0]
        path = os.path.join(tmpdir, "mp_v2_fake_CH0_WIN5min.npz")
        np.savez(path, mp=np.zeros(1701, dtype=np.float32), m=300, fs=1.0,
                 n_samples=2000, source_file="fake.mat", channel=0)
        _register_profile(conn, path, rid, 0, 300, (0, 2000))
        assert ss.find_reusable_profile(conn, rid, 60, span=(0, 2000)) is None
    finally:
        conn.close()


def test_a_profile_that_does_not_cover_the_span_is_not_reused(db):
    db_path, tmpdir = db
    conn = init_db(db_path)
    try:
        rid = _ids(db_path)[0]
        path = os.path.join(tmpdir, "mp_v2_fake_CH0_WIN1min_span0-1000.npz")
        np.savez(path, mp=np.zeros(941, dtype=np.float32), m=60, fs=1.0,
                 n_samples=2000, source_file="fake.mat", channel=0)
        _register_profile(conn, path, rid, 0, 60, (0, 1000))
        assert ss.find_reusable_profile(conn, rid, 60, span=(0, 2000)) is None
        assert ss.find_reusable_profile(conn, rid, 60, span=(0, 1000)) is not None
    finally:
        conn.close()


def test_a_profile_whose_file_has_gone_is_not_reused(db):
    db_path, tmpdir = db
    conn = init_db(db_path)
    try:
        rid = _ids(db_path)[0]
        _register_profile(conn, os.path.join(tmpdir, "missing.npz"), rid, 0, 60, (0, 2000))
        assert ss.find_reusable_profile(conn, rid, 60, span=(0, 2000)) is None
    finally:
        conn.close()


def test_an_unregistered_recording_has_nothing_to_reuse(db):
    db_path, _ = db
    conn = init_db(db_path)
    try:
        assert ss.find_reusable_profile(conn, _ids(db_path)[1], 60, span=(0, 2000)) is None
    finally:
        conn.close()


def test_seed_matches_needs_no_matrix_profile_and_the_module_says_so():
    """`detection.seed_matches` calls `stumpy.match` directly — there is no
    profile to reuse in a seeded search, and claiming one would be a story
    about work that never happened. The reuse path belongs to the
    matrix-profile templates."""
    assert ss.USES_MATRIX_PROFILE is False
    assert "stumpy.match" in ss.WHY_NO_PROFILE
